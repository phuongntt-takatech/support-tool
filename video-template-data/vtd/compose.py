"""Ghép ảnh phẳng vào quad, theo đúng phép toán shader của app (K2, K3: coverage = clamp(edgePx + 0.5)).

Toạ độ quad theo quy ước OpenCV (tâm pixel ở số nguyên). Trong shader, tâm pixel i ở i + 0.5 và quad
trong JSON cũng ở hệ mép pixel; hai bên cùng lệch 0,5 nên phép so sánh tương đương.
"""
from __future__ import annotations

import cv2
import numpy as np


def _roi(quad: np.ndarray, shape, pad: int) -> tuple[int, int, int, int]:
    H, W = shape[:2]
    x0, y0 = np.floor(quad.min(axis=0)).astype(int) - pad
    x1, y1 = np.ceil(quad.max(axis=0)).astype(int) + pad + 1
    return max(x0, 0), max(y0, 0), min(x1, W), min(y1, H)


def composite(frame: np.ndarray, poster: np.ndarray, quad: np.ndarray) -> np.ndarray:
    """Đè poster (ảnh chữ nhật) lên quad, phủ kín tứ giác, mép mịn khoảng 1 px. Sửa trực tiếp frame."""
    ph, pw = poster.shape[:2]
    rect = np.array([[0, 0], [pw, 0], [pw, ph], [0, ph]], dtype=np.float32)
    Hm = cv2.getPerspectiveTransform(quad.astype(np.float32), rect).astype(np.float64)  # video px -> poster px
    x0, y0, x1, y1 = _roi(quad, frame.shape, 2)
    if x1 <= x0 or y1 <= y0:
        return frame
    xs, ys = np.meshgrid(np.arange(x0, x1, dtype=np.float64), np.arange(y0, y1, dtype=np.float64))
    X = Hm[0, 0] * xs + Hm[0, 1] * ys + Hm[0, 2]
    Y = Hm[1, 0] * xs + Hm[1, 1] * ys + Hm[1, 2]
    Z = Hm[2, 0] * xs + Hm[2, 1] * ys + Hm[2, 2]
    Zs = np.where(np.abs(Z) < 1e-12, 1e-12, Z)
    u, v = X / Zs, Y / Zs
    dudx = (Hm[0, 0] - u * Hm[2, 0]) / Zs
    dudy = (Hm[0, 1] - u * Hm[2, 1]) / Zs
    dvdx = (Hm[1, 0] - v * Hm[2, 0]) / Zs
    dvdy = (Hm[1, 1] - v * Hm[2, 1]) / Zs
    per_u = np.maximum(np.abs(dudx) + np.abs(dudy), 1e-7)
    per_v = np.maximum(np.abs(dvdx) + np.abs(dvdy), 1e-7)
    edge_u = np.minimum(u, pw - u) / per_u
    edge_v = np.minimum(v, ph - v) / per_v
    cov = np.clip(edge_u + 0.5, 0, 1) * np.clip(edge_v + 0.5, 0, 1)
    cov = np.where(Z > 0, cov, 0.0).astype(np.float32)
    if not np.any(cov > 0):
        return frame
    mapx = (np.clip(u, 0, pw) - 0.5).astype(np.float32)
    mapy = (np.clip(v, 0, ph) - 0.5).astype(np.float32)
    sample = cv2.remap(poster, mapx, mapy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    roi = frame[y0:y1, x0:x1].astype(np.float32)
    c3 = cov[..., None]
    frame[y0:y1, x0:x1] = np.clip(roi * (1 - c3) + sample.astype(np.float32) * c3 + 0.5, 0, 255).astype(np.uint8)
    return frame


def despill(frame: np.ndarray, quad: np.ndarray, band: int) -> np.ndarray:
    """D6.5: ở dải hẹp ngoài quad, hạ kênh xanh lá xuống bằng max(đỏ, xanh dương). Sửa trực tiếp frame."""
    x0, y0, x1, y1 = _roi(quad, frame.shape, band + 3)
    roi = frame[y0:y1, x0:x1]
    inside = np.zeros(roi.shape[:2], np.uint8)
    pts = np.round((quad - [x0, y0]) * 16).astype(np.int32)
    cv2.fillConvexPoly(inside, pts, 1, lineType=cv2.LINE_8, shift=4)
    dist = cv2.distanceTransform((1 - inside).astype(np.uint8), cv2.DIST_L2, 5)
    sel = (dist > 0) & (dist <= band)
    b, g, r = roi[..., 0], roi[..., 1], roi[..., 2]
    cap = np.maximum(b, r)
    g[sel] = np.minimum(g[sel], cap[sel])
    return frame


def draw_outline(frame: np.ndarray, quad: np.ndarray, label: str | None = None) -> np.ndarray:
    """D7: viền quad nét mảnh + 4 chấm góc + số frame."""
    pts = np.round(quad * 16).astype(np.int32).reshape(-1, 1, 2)
    cv2.polylines(frame, [pts], True, (255, 0, 255), 1, cv2.LINE_AA, shift=4)
    colors = [(0, 0, 255), (0, 255, 255), (255, 0, 0), (0, 255, 0)]  # tl đỏ, tr vàng, br lam, bl lục
    for i, p in enumerate(quad):
        cv2.circle(frame, (int(round(p[0] * 16)), int(round(p[1] * 16))), 3 * 16, colors[i], -1, cv2.LINE_AA, shift=4)
    if label:
        cv2.putText(frame, label, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 4, cv2.LINE_AA)
        cv2.putText(frame, label, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 1, cv2.LINE_AA)
    return frame
