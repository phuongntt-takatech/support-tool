"""D4.7: chế độ chọn tay khi dò thất bại. Cửa sổ hiện frame, dev bấm 4 góc theo thứ tự tl, tr, br, bl;
kết quả lưu vào sổ ghi (overrides.manualQuads) để build lại không phải chọn lại."""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from . import placeholder, registry
from .geometry import is_valid_quad, order_corners, quad_to_dict
from .media import extract_frame, probe, require_ffmpeg
from .util import die, log

HELP = "Bấm 4 góc (tl, tr, br, bl) | r: chọn lại | Enter: lưu | s: bỏ qua frame | Esc: thoát"


def _pick_on(frame: np.ndarray, title: str) -> np.ndarray | None:
    pts: list[tuple[float, float]] = []
    scale = min(1.0, 1400 / frame.shape[1], 850 / frame.shape[0])

    def on_mouse(ev, x, y, flags, _):
        if ev == cv2.EVENT_LBUTTONDOWN and len(pts) < 4:
            pts.append((x / scale, y / scale))

    cv2.namedWindow(title, cv2.WINDOW_AUTOSIZE)
    cv2.setMouseCallback(title, on_mouse)
    while True:
        vis = cv2.resize(frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        for i, p in enumerate(pts):
            cv2.circle(vis, (int(p[0] * scale), int(p[1] * scale)), 5, (0, 0, 255), -1)
            cv2.putText(vis, ["tl", "tr", "br", "bl"][i], (int(p[0] * scale) + 6, int(p[1] * scale) - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        if len(pts) == 4:
            cv2.polylines(vis, [np.int32(np.array(pts) * scale)], True, (255, 0, 255), 1, cv2.LINE_AA)
        cv2.putText(vis, HELP, (10, vis.shape[0] - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
        cv2.imshow(title, vis)
        k = cv2.waitKey(20) & 0xFF
        if k == ord("r"):
            pts.clear()
        elif k in (13, 10) and len(pts) == 4:
            cv2.destroyWindow(title)
            return order_corners(np.array(pts))
        elif k == ord("s"):
            cv2.destroyWindow(title)
            return None
        elif k == 27:
            cv2.destroyAllWindows()
            raise KeyboardInterrupt


def run(name: str, frames: list[int], video: Path | None) -> None:
    require_ffmpeg()
    rec = registry.load(name)
    if not rec:
        die(f"Không có template '{name}' trong sổ ghi (build trước một lần, hoặc kiểm tra tên)")
    src = Path(video) if video else Path(rec["source"]["lastPath"])
    if not src.exists():
        die(f"Không thấy video nguồn {src}; chỉ đường dẫn bằng --video")
    info = probe(src, with_hash=False)
    # Frame theo nhịp đã chuẩn hoá: đọc bằng iter_frames để đúng chỉ số
    from .media import iter_frames
    wanted = set(frames)
    got = {}
    for i, f in enumerate(iter_frames(info)):
        if i in wanted:
            got[i] = f
        if len(got) == len(wanted):
            break
    manual = rec.setdefault("overrides", {}).setdefault("manualQuads", {})
    try:
        for fi in sorted(got):
            q = _pick_on(got[fi], f"Frame {fi} - {name}")
            if q is None:
                continue
            ok, why = is_valid_quad(q)
            if not ok:
                log(f"  Frame {fi}: quad không hợp lệ ({why}), bỏ")
                continue
            manual[str(fi)] = quad_to_dict(q + placeholder.PIXEL_OFFSET)
            log(f"  Frame {fi}: đã lưu")
    except KeyboardInterrupt:
        log("  Dừng chọn tay")
    registry.save(rec)
    log(f"Đã lưu {len(manual)} frame mốc vào sổ ghi. Chạy lại: .venv\\Scripts\\python vtd.py build \"{src}\" --rebuild")
