"""Ảnh mẫu "YOUR POSTER HERE" (D6.2, D6.3, sửa 27/11/2026) và poster bàn cờ để soát (D7.2)."""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .config import ROOT, OUT, cfg

SAMPLE_TEXT = "YOUR POSTER HERE"


def _font(size: int):
    for name in ("arialbd.ttf", "arial.ttf", "segoeui.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def _pil_to_bgr(img: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.array(img.convert("RGB")), cv2.COLOR_RGB2BGR)


def _hex_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _content() -> tuple[Image.Image, bool]:
    """Phần biểu tượng + chữ (RGBA). (ảnh, có phải bản tạm cắt từ ảnh tham chiếu không)."""
    sp = cfg()["samplePoster"]
    path = ROOT / sp["content"]
    if path.exists():
        img = Image.open(path).convert("RGBA")
        return img, False
    ref = Image.open(ROOT / sp["reference"]).convert("RGBA")
    return ref.crop(tuple(sp["referenceContentBox"])), True


def _rounded_rect_path(x0, y0, x1, y1, r, step):
    """Các điểm dọc theo viền chữ nhật bo góc, bắt đầu ở đầu cung góc trên trái, theo chiều kim đồng hồ."""
    pts = []

    def arc(cx, cy, a0, a1):
        n = max(4, int(abs(a1 - a0) * r / step))
        for t in np.linspace(a0, a1, n, endpoint=False):
            pts.append((cx + r * np.cos(t), cy + r * np.sin(t)))

    def line(ax, ay, bx, by):
        L = np.hypot(bx - ax, by - ay)
        n = max(2, int(L / step))
        for t in np.linspace(0, 1, n, endpoint=False):
            pts.append((ax + (bx - ax) * t, ay + (by - ay) * t))
    arc(x0 + r, y0 + r, np.pi, 1.5 * np.pi)
    line(x0 + r, y0, x1 - r, y0)
    arc(x1 - r, y0 + r, 1.5 * np.pi, 2 * np.pi)
    line(x1, y0 + r, x1, y1 - r)
    arc(x1 - r, y1 - r, 0, 0.5 * np.pi)
    line(x1 - r, y1, x0 + r, y1)
    arc(x0 + r, y1 - r, 0.5 * np.pi, np.pi)
    line(x0, y1 - r, x0, y0 + r)
    pts.append(pts[0])
    return np.array(pts)


def _dashed_border(draw: ImageDraw.ImageDraw, w: int, h: int, u: float, color) -> None:
    sp = cfg()["samplePoster"]
    inset, stroke, radius = sp["insetPx"] * u, max(2.0, sp["strokePx"] * u), sp["radiusPx"] * u
    dash, gap = sp["dashPx"] * u, sp["gapPx"] * u
    path = _rounded_rect_path(inset, inset, w - inset, h - inset, radius, step=max(0.5, u * 0.5))
    seg = np.hypot(*np.diff(path, axis=0).T)
    cum = np.concatenate([[0], np.cumsum(seg)])
    total = cum[-1]
    period = dash + gap
    k = max(1, round(total / period))
    scale = total / (k * period)  # chia đều để chu vi là số nguyên lần chu kỳ, các góc nhìn giống nhau
    dash, period = dash * scale, period * scale
    for i in range(k):
        a, b = i * period, i * period + dash
        sel = (cum >= a) & (cum <= b)
        pts = [tuple(p) for p in path[sel]]
        if len(pts) >= 2:
            draw.line(pts, fill=color, width=int(round(stroke)), joint="curve")  # đầu nét vuông như bản gốc


def build_sample(w: int, h: int) -> tuple[np.ndarray, bool]:
    """Dựng ảnh mẫu "YOUR POSTER HERE" đúng tỷ lệ w:h (quyết định 27/11/2026, thay Fill của D6.3):
    nền trắng, viền đứt nét bo góc sát mép theo đúng khung, biểu tượng + chữ đặt giữa, thu vừa.
    Trả (ảnh BGR, có phải bản tạm không)."""
    sp = cfg()["samplePoster"]
    ss = 2  # vẽ to gấp đôi rồi thu nhỏ cho mịn
    W, H = w * ss, h * ss
    u = min(W, H) / sp["designWidthPx"]
    canvas = Image.new("RGBA", (W, H), _hex_rgb(sp["background"]) + (255,))
    content, is_temp = _content()
    cw, ch = content.size
    scale = min(sp["contentMaxW"] * W / cw, sp["contentMaxH"] * H / ch)
    tw, th = max(1, round(cw * scale)), max(1, round(ch * scale))
    content = content.resize((tw, th), Image.LANCZOS)
    x = (W - tw) // 2
    y = round(H * sp["contentCenterY"] - th / 2)
    canvas.alpha_composite(content, (x, y))
    _dashed_border(ImageDraw.Draw(canvas), W, H, u, _hex_rgb(sp["borderColor"]) + (255,))
    img = canvas.convert("RGB").resize((w, h), Image.LANCZOS)
    return _pil_to_bgr(img), is_temp


def fill_crop(img: np.ndarray, w: int, h: int) -> np.ndarray:
    """Cắt Fill theo tỷ lệ w:h (không méo) rồi đổi cỡ."""
    ih, iw = img.shape[:2]
    target = w / h
    if iw / ih > target:
        cw = int(round(ih * target)); x = (iw - cw) // 2
        img = img[:, x:x + cw]
    else:
        ch = int(round(iw / target)); y = (ih - ch) // 2
        img = img[y:y + ch, :]
    interp = cv2.INTER_AREA if img.shape[1] > w else cv2.INTER_CUBIC
    return cv2.resize(img, (w, h), interpolation=interp)


def checkerboard(w: int, h: int) -> np.ndarray:
    """Ô đen trắng, hình tròn giữa (méo → bầu dục), viền đỏ sát mép, chữ TOP ở cạnh trên."""
    cell = max(8, min(w, h) // 12)
    yy, xx = np.mgrid[0:h, 0:w]
    board = (((xx // cell) + (yy // cell)) % 2).astype(np.uint8) * 255
    img = cv2.cvtColor(board, cv2.COLOR_GRAY2BGR)
    t = max(2, min(w, h) // 60)
    cv2.rectangle(img, (0, 0), (w - 1, h - 1), (0, 0, 255), t)
    r = int(min(w, h) * 0.3)
    cv2.circle(img, (w // 2, h // 2), r, (255, 120, 0), max(3, t * 2), cv2.LINE_AA)
    pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    d = ImageDraw.Draw(pil)
    font = _font(max(12, min(w, h) // 8))
    tw = d.textlength("TOP", font=font)
    box = d.textbbox((0, 0), "TOP", font=font)
    x, y = (w - tw) / 2, t * 2 + cell * 0.2
    d.rectangle([x - 6, y - 2, x + tw + 6, y + box[3] + 6], fill=(255, 255, 0))
    d.text((x, y), "TOP", fill=(200, 0, 0), font=font)
    return cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
