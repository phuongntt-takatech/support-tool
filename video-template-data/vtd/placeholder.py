"""D9.1: ghi / đọc / kiểm tra placeholder.json.

- Thứ tự trường cố định, mỗi quad một dòng, UTF-8; cùng dữ liệu ghi ra y hệt từng byte.
- Toạ độ trong JSON theo hệ của app: gốc ở góc trên trái của pixel đầu tiên (tâm pixel i ở i + 0.5),
  khớp shader (vVideoUv ∈ [0,1] ↔ 0..width). Bên trong công cụ dùng quy ước OpenCV (tâm pixel ở i),
  nên khi ghi cộng 0.5, khi đọc trừ 0.5.
"""
from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path

import numpy as np

from .geometry import CORNERS, is_valid_quad

PIXEL_OFFSET = 0.5


def _num(v: float) -> str:
    return f"{v:.2f}"


def _fps_value(fps: Fraction):
    f = float(fps)
    return int(f) if abs(f - round(f)) < 1e-9 else round(f, 3)


def _ratio_value(v):
    return v if isinstance(v, int) else round(float(v), 2)


def render(width: int, height: int, fps: Fraction, poster_ratio: tuple, preview_frame: int,
           bleed_px, quads_cv: np.ndarray) -> str:
    lines = ["{"]
    lines.append(f'  "video": {{ "width": {width}, "height": {height}, "fps": {json.dumps(_fps_value(fps))} }},')
    pw, ph = poster_ratio
    lines.append(f'  "posterRatio": {{ "w": {json.dumps(_ratio_value(pw))}, "h": {json.dumps(_ratio_value(ph))} }},')
    lines.append(f'  "previewFrame": {int(preview_frame)},')
    lines.append(f'  "bleedPx": {json.dumps(bleed_px)},')
    lines.append('  "quads": [')
    rows = []
    for q in quads_cv:
        qa = q + PIXEL_OFFSET
        parts = [f'"{name}": [{_num(qa[i, 0])}, {_num(qa[i, 1])}]' for i, name in enumerate(CORNERS)]
        rows.append("    { " + ", ".join(parts) + " }")
    lines.append(",\n".join(rows))
    lines.append("  ]")
    lines.append("}")
    return "\n".join(lines) + "\n"


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def quads_cv(data: dict) -> np.ndarray:
    return np.array([[q[name] for name in CORNERS] for q in data["quads"]], dtype=np.float64) - PIXEL_OFFSET


def validate(data: dict, frame_count: int | None = None) -> list[str]:
    """Kiểm tra theo luật của app và chặt hơn app (D10 A2, A3, A5). Trả danh sách lỗi."""
    errs = []
    try:
        w, h = int(data["video"]["width"]), int(data["video"]["height"])
        fps = float(data["video"]["fps"])
    except (KeyError, TypeError, ValueError):
        return ["thiếu / sai trường video.width/height/fps"]
    if w <= 0 or h <= 0 or not (0 < fps <= 30.01):
        errs.append(f"video không hợp lệ ({w}x{h}, {fps} fps)")
    pr = data.get("posterRatio") or {}
    try:
        if float(pr["w"]) <= 0 or float(pr["h"]) <= 0 or not (0.2 <= float(pr["w"]) / float(pr["h"]) <= 5):
            errs.append("posterRatio không hợp lý")
    except (KeyError, TypeError, ValueError):
        errs.append("thiếu posterRatio")
    if data.get("bleedPx") != 2:
        errs.append("bleedPx phải là 2")
    quads = data.get("quads")
    if not isinstance(quads, list) or not quads:
        return errs + ["quads rỗng"]
    n = len(quads)
    if frame_count is not None and n not in (1, frame_count):
        errs.append(f"số quad {n} khác 1 và khác số frame {frame_count}")
    pf = data.get("previewFrame")
    limit = frame_count if frame_count is not None else n
    if not isinstance(pf, int) or not (0 <= pf < max(limit, 1)):
        errs.append(f"previewFrame {pf} ngoài khoảng")
    margin = 12
    for i, q in enumerate(quads):
        try:
            arr = np.array([q[name] for name in CORNERS], dtype=np.float64)
        except (KeyError, TypeError, ValueError):
            errs.append(f"quad {i} thiếu góc"); continue
        ok, why = is_valid_quad(arr, min_area=w * h * 0.002)
        if not ok:
            errs.append(f"quad {i}: {why}")
        if np.any(arr[:, 0] < -margin) or np.any(arr[:, 0] > w + margin) or \
           np.any(arr[:, 1] < -margin) or np.any(arr[:, 1] > h + margin):
            errs.append(f"quad {i}: toạ độ ra ngoài khung hình")
        if len(errs) > 20:
            errs.append("…")
            break
    return errs
