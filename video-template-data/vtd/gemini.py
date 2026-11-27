"""Gọi Gemini (Google AI Studio) qua REST, chỉ dùng thư viện chuẩn (không thêm DLL nào để Smart App Control chặn).

- Key: biến môi trường GEMINI_API_KEY (cùng tên với tool populate-templates-meta).
- Chuỗi model trong config.json → ai.models; hết hạn mức ngày / model lỗi thì chuyển model sau.
- Bị giới hạn theo phút (429 không phải theo ngày): chờ đúng retryDelay rồi thử lại cùng model;
  lặp lại nhiều lần liên tiếp thì chuyển model.
- Lỗi tạm thời (5xx, mạng): thử lại với thời gian chờ tăng dần.
- Tự giãn nhịp gọi theo ai.rpm (mặc định 4 lượt / phút, hợp hạn mức tài khoản free).
"""
from __future__ import annotations

import base64
import json
import os
import re
import time
import urllib.error
import urllib.request

from .config import cfg
from .util import log

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DAILY = re.compile(r"PerDay|per[ _]day|daily", re.I)


class AIError(Exception):
    """Lỗi không gọi được AI (thiếu key, hết hạn mức mọi model, lỗi cố định...)."""


class _State:
    """Trạng thái dùng chung trong một lần chạy: model đang dùng, model đã hết hạn mức, nhịp gọi."""
    index = 0
    last_call = 0.0


def api_key() -> str | None:
    k = os.environ.get("GEMINI_API_KEY", "").strip()
    return k or None


def models() -> list[str]:
    return list(dict.fromkeys(m.strip() for m in cfg()["ai"]["models"] if m.strip()))


def current_model() -> str | None:
    ms = models()
    return ms[_State.index] if _State.index < len(ms) else None


def _retry_delay(body: str) -> float:
    m = re.search(r'"retryDelay"\s*:\s*"(\d+(?:\.\d+)?)s"', body)
    if m:
        return float(m.group(1))
    m = re.search(r"retry(?:Delay)?[^0-9]{0,20}(\d+(?:\.\d+)?)\s*(ms|s)\b", body, re.I)
    if m:
        v = float(m.group(1))
        return v / 1000 if m.group(2).lower() == "ms" else v
    return 0.0


def _throttle() -> None:
    rpm = float(cfg()["ai"].get("rpm") or 4)
    wait = _State.last_call + 60.0 / rpm - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    _State.last_call = time.monotonic()


def _post(model: str, payload: dict, key: str) -> tuple[int, str]:
    req = urllib.request.Request(API.format(model=model), data=json.dumps(payload).encode("utf-8"), method="POST",
                                 headers={"Content-Type": "application/json", "x-goog-api-key": key})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return r.status, r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
        return 0, f"network: {e}"


def _short(body: str) -> str:
    try:
        return json.loads(body)["error"]["message"].split("\n")[0][:200]
    except (ValueError, KeyError, TypeError):
        return body.strip().split("\n")[0][:200]


def _switch(reason: str) -> None:
    old = current_model()
    _State.index += 1
    new = current_model()
    log(f"    Gemini: {old} {reason} → {'chuyển sang ' + new if new else 'hết model để thử'}")


def generate_json(images: list[bytes], prompt: str, schema: dict) -> tuple[dict, str]:
    """Gửi ảnh JPEG + prompt, nhận JSON theo schema. Trả (dữ liệu, model đã dùng)."""
    key = api_key()
    if not key:
        raise AIError("chưa có GEMINI_API_KEY")
    ac = cfg()["ai"]
    parts = [{"inlineData": {"mimeType": "image/jpeg", "data": base64.b64encode(img).decode("ascii")}} for img in images]
    parts.append({"text": prompt})
    gen = {"responseMimeType": "application/json", "responseSchema": schema, "temperature": 0.4}
    if ac.get("thinkingBudget") is not None:
        gen["thinkingConfig"] = {"thinkingBudget": int(ac["thinkingBudget"])}
    payload = {"contents": [{"role": "user", "parts": parts}], "generationConfig": gen}

    max_attempts = int(ac.get("maxAttempts", 5))
    while current_model():
        model = current_model()
        rate_streak = 0
        for attempt in range(1, max_attempts + 1):
            _throttle()
            status, body = _post(model, payload, key)
            if status == 200:
                data = json.loads(body)
                cand = (data.get("candidates") or [{}])[0]
                text = "".join(p.get("text", "") for p in cand.get("content", {}).get("parts", []) if not p.get("thought"))
                if not text:
                    block = data.get("promptFeedback", {}).get("blockReason")
                    raise AIError(f"Gemini trả rỗng (finishReason={cand.get('finishReason')}, blockReason={block})")
                start, end = text.find("{"), text.rfind("}")
                if start < 0 or end < start:
                    raise AIError("Gemini không trả JSON")
                try:
                    return json.loads(text[start:end + 1]), model
                except json.JSONDecodeError as e:
                    raise AIError(f"JSON của Gemini hỏng: {e}") from e
            if status in (401, 403) or (status == 400 and "API key" in body):
                raise AIError(f"GEMINI_API_KEY không hợp lệ hoặc không có quyền ({status}: {_short(body)})")
            if status == 429 or "RESOURCE_EXHAUSTED" in body:
                if DAILY.search(body):
                    _switch("hết hạn mức trong ngày")
                    break
                rate_streak += 1
                if rate_streak >= int(ac.get("rateLimitSwitchAfter", 3)):
                    _switch("bị giới hạn tốc độ nhiều lần liên tiếp")
                    break
                wait = max(_retry_delay(body), 10.0)
                log(f"    Gemini {model}: giới hạn theo phút, chờ {wait:.0f} s rồi thử lại…")
                time.sleep(wait)
                continue
            if status == 404 or (status == 400 and "model" in body.lower() and "not" in body.lower()):
                _switch(f"không dùng được ({status}: {_short(body)})")
                break
            if status == 0 or status >= 500:
                if attempt == max_attempts:
                    _switch(f"lỗi tạm thời lặp lại ({status or 'mạng'}: {_short(body)})")
                    break
                wait = min(2 * 2 ** (attempt - 1), 60)
                log(f"    Gemini {model}: lỗi tạm thời ({status or 'mạng'}), thử lại sau {wait} s…")
                time.sleep(wait)
                continue
            raise AIError(f"Gemini {model} lỗi {status}: {_short(body)}")
        else:
            _switch("thử nhiều lần không thành công")
    raise AIError(f"Đã thử hết các model ({', '.join(models())}); hạn mức free có thể đã hết, thử lại sau (thường reset theo ngày)")
