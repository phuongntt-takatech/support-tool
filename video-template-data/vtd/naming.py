"""D1.4 / mục 7.3: AI đặt tên hiển thị + dịch; kiểm tra; dự phòng từ tên file; tạo `name` (D1.5)."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from .config import cfg
from .locales import LANG_NAMES
from .util import Warn, log, slugify

FORBIDDEN = {
    "amazing", "stunning", "ultimate", "pro", "best", "awesome", "beautiful", "perfect", "premium", "epic",
    "template", "mockup", "mock", "video", "greenscreen", "poster", "placeholder", "chroma",
}
# Cụm từ kỹ thuật cấm (mục 7.3): chỉ cấm cả cụm, "Screen" hay "Green" đứng riêng vẫn hợp lệ ("Mall Screen").
FORBIDDEN_PHRASES = ("green screen",)

# Tên mẫu chỉ để minh hoạ cách đặt tên; AI không được dùng lại nguyên văn (tool tự loại, gọi lại kèm lý do).
EXAMPLE_TITLES = ("Beach Billboard", "City Bus Stop", "Store Window", "Gallery Wall", "Street Kiosk",
                  "Living Room Frame", "Night Street Kiosk", "Highway Billboard")

RULES = f"""Naming rules for the English title:
- 2 to 3 words, at most about 24 characters.
- Pattern: [setting] + [object that holds the poster].
  * [setting] = what the scene actually shows: place, time of day or season (e.g. city street, night, winter,
    office, mall, subway, beach, living room).
  * [object] = the precise everyday name of the physical thing the poster area belongs to. Look closely and choose
    the most accurate word, e.g. billboard, lightbox, sign, screen, display, monitor, TV, frame, canvas, easel,
    standee, kiosk (only a small booth or stall), bus stop, window, wall, phone, tablet, laptop, magazine, flag.
    A freestanding illuminated advertising sign on a sidewalk is a "Lightbox" or "Sign", not a "Kiosk".
- Style examples only (show the pattern; NEVER reuse them verbatim): {", ".join(EXAMPLE_TITLES)}.
  Bad style: "Summer Vibes", "Dream Space".
- English, Title Case (capitalize every word).
- No marketing words (Amazing, Stunning, Ultimate, Pro, Best, ...).
- No technical words (Template, Mockup, Video, Green Screen, Poster, Placeholder).
- No digits, brand names, people's names, emoji or punctuation. Letters and spaces only.
- Must not duplicate an existing title (case-insensitive).
- If an object of the same kind already exists, distinguish by setting, never by a number
  (e.g. "Highway Billboard" when "Beach Billboard" exists; never "Beach Billboard 2").

Translations: short, natural, same meaning, similar length to the English title, in the native script of each
language. Use the common everyday word for that object in that language (do not just transliterate English)."""


def validate_title(en: str, existing: list[str]) -> list[str]:
    errs = []
    words = en.split()
    if not (2 <= len(words) <= 3):
        errs.append(f"cần 2–3 từ (đang có {len(words)})")
    if len(en) > 24:
        errs.append(f"dài {len(en)} ký tự (tối đa khoảng 24)")
    if not re.fullmatch(r"[A-Za-z]+( [A-Za-z]+)*", en):
        errs.append("chỉ được chữ cái và khoảng trắng (không số, dấu câu, emoji)")
    if any(w[:1] != w[:1].upper() for w in words):
        errs.append("mỗi từ phải viết hoa chữ đầu")
    bad = [w for w in words if w.lower() in FORBIDDEN]
    bad += [p.title() for p in FORBIDDEN_PHRASES if p in " ".join(words).lower()]
    if bad:
        errs.append(f"có từ cấm: {', '.join(bad)}")
    if en.lower() in {e.lower() for e in existing}:
        errs.append("trùng tên đã có")
    if en.lower() in {e.lower() for e in EXAMPLE_TITLES}:
        errs.append("chép nguyên văn tên mẫu trong quy định; hãy đặt tên theo đúng cảnh và đúng vật trong hình")
    return errs


def validate_translations(tr: dict, codes: list[str], en: str) -> list[str]:
    errs = []
    missing = [c for c in codes if c != "en" and not (isinstance(tr.get(c), str) and tr[c].strip())]
    if missing:
        errs.append(f"thiếu bản dịch: {', '.join(missing)}")
    limit = max(40, int(len(en) * 3))
    long = [c for c, v in tr.items() if isinstance(v, str) and (len(v) > limit or "\n" in v)]
    if long:
        errs.append(f"bản dịch quá dài / nhiều dòng: {', '.join(long)}")
    return errs


def _schema(codes: list[str]) -> dict:
    """Schema kiểu Gemini (OpenAPI subset)."""
    others = [c for c in codes if c != "en"]
    return {
        "type": "OBJECT",
        "properties": {
            "en": {"type": "STRING"},
            "translations": {
                "type": "OBJECT",
                "properties": {c: {"type": "STRING"} for c in others},
                "required": others,
            },
        },
        "required": ["en", "translations"],
    }


def _prompt(existing: list[str], codes: list[str], feedback: str | None) -> str:
    lang_lines = "\n".join(f"- {c}: {LANG_NAMES.get(c, c)}" for c in codes if c != "en")
    text = (
        "These are frames from a short video template for a poster-maker app. The area showing the text "
        "\"YOUR POSTER HERE\" (inside a dashed border) is where the user's poster will be placed. Name the template "
        "after its setting and the kind of object that holds that poster area.\n\n"
        f"{RULES}\n\nExisting English titles (do not reuse): {json.dumps(existing, ensure_ascii=False)}\n\n"
        f"Translate the English title into each of these app languages (keys are Android resource codes):\n{lang_lines}\n\n"
        "Answer with JSON only: {\"en\": <English title>, \"translations\": {<code>: <title>, ...}}.\n"
    )
    if feedback:
        text += f"\nYour previous answer broke these rules, fix them: {feedback}\n"
    return text


def ai_titles(images: list[bytes], existing: list[str], codes: list[str]) -> tuple[dict | None, list[Warn]]:
    """Trả (titles, cảnh báo). titles None nếu thất bại → dùng dự phòng."""
    from .gemini import AIError, generate_json
    warns: list[Warn] = []
    feedback = None
    for attempt in range(2):  # gọi lại một lần kèm lý do (mục 7.3)
        try:
            data, model = generate_json(images, _prompt(existing, codes, feedback), _schema(codes))
        except AIError as e:
            warns.append(Warn("ai_error", f"Không gọi được AI: {e}; dùng tên từ tên file"))
            return None, warns
        en = str(data.get("en", "")).strip()
        tr = {k: str(v).strip() for k, v in (data.get("translations") or {}).items()}
        errs = validate_title(en, existing) + validate_translations(tr, codes, en)
        if not errs:
            titles = {"en": en}
            titles.update({c: tr[c] for c in codes if c != "en"})
            log(f"    Tên do {model} đặt")
            return titles, warns
        feedback = "; ".join(errs)
        log(f"    AI đặt tên chưa đạt ({feedback}), gọi lại một lần")
    warns.append(Warn("ai_invalid", f"Tên AI đặt vẫn sai quy định sau khi gọi lại: {feedback}; dùng tên từ tên file"))
    return None, warns


NOISE = {"prores", "mp", "mov", "screen", "green", "greenscreen", "chroma", "key", "mockup", "template",
         "video", "final", "copy", "hd", "fhd", "uhd", "k", "fps", "white", "poster"}


def fallback_title(filename: str, existing: list[str]) -> str:
    stem = Path(filename).stem
    words = re.findall(r"[A-Za-z]+", stem.replace("_", " "))
    words = [w for w in words if w.lower() not in NOISE and len(w) > 1 and not re.fullmatch(r"x", w, re.I)]
    title = " ".join(w.capitalize() for w in words[:3]) or "Untitled Scene"
    if len(title.split()) < 2:
        title = f"{title} Scene"
    base, n = title, 2
    while title.lower() in {e.lower() for e in existing}:
        title = f"{base} {chr(64 + n)}"  # không dùng số; thêm chữ cái để khác (dev sửa lại)
        n += 1
    return title


def make_name(en_title: str, taken: set[str], now: datetime | None = None) -> str:
    """D1.5: tên tiếng Anh viết thường + ngày giờ tạo; trùng phút thì thêm giây, rồi số thứ tự."""
    now = now or datetime.now()
    base = slugify(en_title) or "template"
    cand = f"{base}_{now:%Y%m%d_%H%M}"
    if cand not in taken:
        return cand
    cand = f"{base}_{now:%Y%m%d_%H%M%S}"
    i = 2
    out = cand
    while out in taken:
        out = f"{cand}_{i}"; i += 1
    return out
