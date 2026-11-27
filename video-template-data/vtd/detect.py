"""D4: dò 4 góc vùng xanh trong một frame.

Nhiệm vụ duy nhất: frame vào → quad (+ độ tin cậy) ra. Làm mượt, nới khung, chọn tay là bước sau.
Toạ độ trả về theo quy ước OpenCV (tâm pixel ở số nguyên). Đổi sang quy ước của app (mép pixel)
chỉ diễn ra lúc ghi placeholder.json (xem placeholder.py).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from .config import cfg
from .geometry import order_corners, is_valid_quad, line_intersection, signed_area


@dataclass
class KeyColor:
    hue: float   # thang OpenCV 0..180
    sat: float
    val: float

    def to_dict(self) -> dict:
        return {"hue": round(self.hue, 1), "sat": round(self.sat, 1), "val": round(self.val, 1)}


@dataclass
class Detection:
    quad: np.ndarray | None
    ok: bool
    reasons: list[str] = field(default_factory=list)
    fill_ratio: float = 0.0
    line_rms: float = 0.0
    area: float = 0.0
    touches_border: bool = False
    extra_regions: int = 0
    contour: np.ndarray | None = None


def learn_key_color(frames: list[np.ndarray]) -> KeyColor | None:
    """B1 (D4.1): học màu xanh của chính video = cụm xanh đậm, đồng nhất, lớn nhất ở vài frame đầu."""
    hues, sats, vals = [], [], []
    for f in frames:
        hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
        h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
        cand = ((h >= 35) & (h <= 90) & (s >= 80) & (v >= 40)).astype(np.uint8)
        cand = cv2.morphologyEx(cand, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        n, labels, stats, _ = cv2.connectedComponentsWithStats(cand, connectivity=8)
        if n <= 1:
            continue
        idx = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        if stats[idx, cv2.CC_STAT_AREA] < f.shape[0] * f.shape[1] * cfg()["detect"]["minAreaFrac"]:
            continue
        sel = labels == idx
        hues.append(h[sel]); sats.append(s[sel]); vals.append(v[sel])
    if not hues:
        return None
    return KeyColor(float(np.median(np.concatenate(hues))), float(np.median(np.concatenate(sats))),
                    float(np.median(np.concatenate(vals))))


def green_map(frame: np.ndarray, key: KeyColor) -> np.ndarray:
    """B2: mức "giống màu chuẩn" 0..1, so theo sắc màu, ít phụ thuộc độ sáng (bóng râm vẫn là xanh)."""
    d = cfg()["detect"]
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV).astype(np.float32)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    dh = np.abs(h - key.hue)
    dh = np.minimum(dh, 180 - dh)
    tol = d["hueTol"]
    m_h = np.clip((tol + 4 - dh) / 8.0, 0, 1)
    min_sat = min(d["minSat"], 0.5 * key.sat)
    m_s = np.clip((s - (min_sat - 20)) / 40.0, 0, 1)
    m_v = np.clip((v - (d["minVal"] - 15)) / 30.0, 0, 1)
    return (m_h * m_s * m_v).astype(np.float32)


def _rough_quad(contour: np.ndarray) -> np.ndarray | None:
    hull = cv2.convexHull(contour)
    peri = cv2.arcLength(hull, True)
    for k in np.linspace(0.01, 0.12, 23):
        approx = cv2.approxPolyDP(hull, k * peri, True)
        if len(approx) == 4:
            return order_corners(approx.reshape(4, 2).astype(np.float64))
        if len(approx) < 4:
            break
    return None


def _refine_points(frame_f: np.ndarray, pts: np.ndarray, normal: np.ndarray, rng: float) -> np.ndarray:
    """Dời từng điểm viền theo pháp tuyến tới điểm giữa dải chuyển màu.

    Mức pha trộn tính tuyến tính theo màu: chiếu màu từng điểm lên đoạn [màu nền bên ngoài → màu xanh
    bên trong] của chính đường cắt đó; mép = chỗ pha trộn 50%. Không dùng mức "giống xanh" (phi tuyến,
    làm quad co vào khoảng 0,5 px).
    """
    steps = np.linspace(-rng, rng, int(rng * 8) + 1, dtype=np.float32)
    xs = (pts[:, 0:1] + steps[None, :] * normal[0]).astype(np.float32)
    ys = (pts[:, 1:2] + steps[None, :] * normal[1]).astype(np.float32)
    col = cv2.remap(frame_f, xs, ys, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)  # (N, S, 3)
    cin = col[:, :4].mean(axis=1)
    cout = col[:, -4:].mean(axis=1)
    d = cin - cout
    dd = np.einsum("nc,nc->n", d, d)
    good = dd > 400  # chênh màu đủ lớn (≈ 20 mức) mới tin được
    prof = np.einsum("nsc,nc->ns", col - cout[:, None, :], d) / np.maximum(dd, 1e-6)[:, None]
    above = prof >= 0.5
    # chuyển từ trong (xanh) ra ngoài (không xanh): above[k] và not above[k+1]
    cross = above[:, :-1] & ~above[:, 1:]
    has = cross.any(axis=1)
    k = np.argmax(cross, axis=1)
    rows = np.arange(len(pts))
    p0 = prof[rows, k]
    p1 = prof[rows, np.minimum(k + 1, len(steps) - 1)]
    frac = np.where(np.abs(p0 - p1) > 1e-6, (p0 - 0.5) / (p0 - p1 + 1e-12), 0.5)
    s = steps[k] + frac * (steps[1] - steps[0])
    out = pts + s[:, None] * normal[None, :]
    return out[has & good]


def detect_quad(frame: np.ndarray, key: KeyColor, gmap: np.ndarray | None = None) -> Detection:
    d = cfg()["detect"]
    H, W = frame.shape[:2]
    if gmap is None:
        gmap = green_map(frame, key)
    mask = (gmap >= 0.5).astype(np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if n <= 1:
        return Detection(None, False, ["không thấy vùng xanh"])
    areas = stats[1:, cv2.CC_STAT_AREA]
    order = np.argsort(areas)[::-1]
    idx = 1 + int(order[0])
    big = float(areas[order[0]])
    if big < H * W * d["minAreaFrac"]:
        return Detection(None, False, ["vùng xanh quá nhỏ"])
    extra = int(np.sum(areas[order[1:]] > big * d["secondRegionFrac"])) if len(order) > 1 else 0
    x, y, w, h = stats[idx, :4]
    touches = x <= 0 or y <= 0 or x + w >= W or y + h >= H

    frame_f = frame.astype(np.float32)
    region = (labels == idx).astype(np.uint8)
    contours, _ = cv2.findContours(region, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)  # B4: viền ngoài, bỏ lỗ
    contour = max(contours, key=cv2.contourArea)
    rough = _rough_quad(contour)
    det = Detection(None, False, [], touches_border=touches, extra_regions=extra, contour=contour)
    if rough is None:
        det.reasons.append("vùng xanh không giống hình 4 cạnh")
        return det

    pts = contour.reshape(-1, 2).astype(np.float64)
    # Gán điểm viền cho cạnh gần nhất, bỏ phần sát góc (góc mờ / bo).
    dists, params = [], []
    for i in range(4):
        a, b = rough[i], rough[(i + 1) % 4]
        ab = b - a
        L2 = float(ab @ ab)
        t = np.clip(((pts - a) @ ab) / L2, 0, 1)
        proj = a + t[:, None] * ab
        dists.append(np.linalg.norm(pts - proj, axis=1))
        params.append(((pts - a) @ ab) / L2)
    dists = np.stack(dists, axis=1)
    side = np.argmin(dists, axis=1)
    ex = d["cornerExcludeFrac"]
    lines, rms_all = [], []
    for i in range(4):
        t = params[i]
        sel = (side == i) & (t > ex) & (t < 1 - ex) & (dists[:, i] < 6)
        sp = pts[sel]
        if len(sp) < 20:
            det.reasons.append(f"cạnh {i} có quá ít điểm")
            return det
        a, b = rough[i], rough[(i + 1) % 4]
        dirv = (b - a) / np.linalg.norm(b - a)
        normal = np.array([dirv[1], -dirv[0]])  # pháp tuyến ra ngoài
        refined = _refine_points(frame_f, sp, normal, d["refineRangePx"])
        if len(refined) < 20:
            det.reasons.append(f"cạnh {i}: không tìm được mép")
            return det
        vx, vy, x0, y0 = cv2.fitLine(refined.astype(np.float32), cv2.DIST_HUBER, 0, 0.01, 0.01).ravel()
        dv = np.array([vx, vy], dtype=np.float64)
        p0 = np.array([x0, y0], dtype=np.float64)
        resid = (refined - p0) @ np.array([-dv[1], dv[0]])
        rms_all.append(float(np.sqrt(np.mean(resid ** 2))))
        lines.append((p0, dv))

    corners = np.array([line_intersection(*lines[(i - 1) % 4], *lines[i]) for i in range(4)])
    quad = order_corners(corners)
    det.quad = quad
    det.line_rms = max(rms_all)
    det.area = signed_area(quad)
    det.fill_ratio = float(cv2.contourArea(contour)) / max(det.area, 1.0)
    valid, why = is_valid_quad(quad, min_area=H * W * d["minAreaFrac"])
    if not valid:
        det.reasons.append(why)
    if det.line_rms > d["maxLineRmsPx"]:
        det.reasons.append(f"cạnh không thẳng (rms {det.line_rms:.2f} px)")
    if det.fill_ratio < d["minFillRatio"] or det.fill_ratio > 1.04:
        det.reasons.append(f"vùng xanh không khớp tứ giác (lấp {det.fill_ratio:.3f})")
    det.ok = not det.reasons
    return det
