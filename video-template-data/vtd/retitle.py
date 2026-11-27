"""Đặt lại tên hiển thị + bản dịch bằng AI cho template đã build (không build lại video, giữ nguyên `name`).

Dùng cho template đang có tên tạm lấy từ tên file (build lúc AI chưa dùng được), hoặc muốn AI đặt lại.
"""
from __future__ import annotations

import cv2

from . import registry, review
from .config import templates_out
from .locales import load_codes
from .media import extract_frame, require_ffmpeg
from .naming import ai_titles
from .util import log

AI_WARN_CODES = {"title_fallback", "ai_auth", "ai_error", "ai_invalid", "ai_sdk_blocked"}


def needs_title(rec: dict) -> bool:
    return bool(rec.get("build")) and rec.get("titlesSource") != "ai"


def _jpeg(frame) -> bytes:
    if frame.shape[1] > 1280:
        frame = cv2.resize(frame, (1280, round(frame.shape[0] * 1280 / frame.shape[1])), interpolation=cv2.INTER_AREA)
    return cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 88])[1].tobytes()


def retitle_one(rec: dict, codes: list[str]) -> bool:
    name = rec["name"]
    b = rec["build"]
    video = templates_out() / name / "video.mp4"
    if not video.exists():
        log(f"  {name}: thiếu {video}, bỏ qua")
        return False
    w, h = b["size"]
    n, pf = b["frames"], b["previewFrame"]
    frames = [pf]
    if b["group"] == "B":
        frames += [f for f in (int(n * 0.25), int(n * 0.75)) if abs(f - pf) > n * 0.1]
    images = [_jpeg(extract_frame(video, f, w, h)) for f in frames]
    existing = [r["titles"]["en"] for r in registry.load_all()
                if r["name"] != name and r.get("titles", {}).get("en")]
    log(f"  {name}: gọi AI đặt tên (tên hiện tại: {rec.get('titles', {}).get('en', '-')})…")
    titles, warns = ai_titles(images, existing, codes)
    if not titles:
        for wn in warns:
            log(f"  ! {wn.message}")
        return False
    old = rec.get("titles", {}).get("en")
    rec["titles"] = titles
    rec["titlesSource"] = "ai"
    b["warnings"] = [wn for wn in b.get("warnings", []) if wn.get("code") not in AI_WARN_CODES]
    registry.save(rec)
    log(f"  {name}: {old} → {titles['en']} ({len(titles)} ngôn ngữ)")
    review.generate(name)  # cập nhật trang soát (tên, bản dịch, số cảnh báo)
    return True


def run(names: list[str], redo: bool = False) -> None:
    """names rỗng: mọi template đang dùng tên tạm (redo=True: mọi template chưa publish)."""
    require_ffmpeg()
    codes, lw = load_codes()
    for wn in lw:
        log(f"! {wn.message}")
    recs = {r["name"]: r for r in registry.load_all()}
    if names:
        targets = [recs[n] for n in names if n in recs]
        missing = [n for n in names if n not in recs]
        for n in missing:
            log(f"Không có template '{n}'")
    else:
        targets = [r for r in recs.values() if r.get("build") and not r.get("publish")
                   and (redo or needs_title(r))]
    if not targets:
        log("Không có template nào cần đặt tên.")
        return
    ok = sum(retitle_one(r, codes) for r in targets)
    review.generate_index()
    log(f"\nĐã đặt tên {ok}/{len(targets)} template. Soát lại tên + bản dịch trong trang soát (menu mục 3).")
