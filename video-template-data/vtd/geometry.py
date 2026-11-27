"""Toán tứ giác: thứ tự góc, kiểm tra lồi, nới khung (K2.5), homography (K2), độ nghiêng.

Quy ước: quad là mảng numpy (4, 2) theo thứ tự tl, tr, br, bl (chiều kim đồng hồ trên ảnh, trục y hướng xuống).
"""
from __future__ import annotations

import cv2
import numpy as np

CORNERS = ("tl", "tr", "br", "bl")


def signed_area(q: np.ndarray) -> float:
    x, y = q[:, 0], q[:, 1]
    return 0.5 * float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y))


def order_corners(pts: np.ndarray) -> np.ndarray:
    """Xếp 4 điểm thành tl, tr, br, bl (chiều kim đồng hồ trên ảnh)."""
    pts = np.asarray(pts, dtype=np.float64).reshape(4, 2)
    c = pts.mean(axis=0)
    ang = np.arctan2(pts[:, 1] - c[1], pts[:, 0] - c[0])
    pts = pts[np.argsort(ang)]  # tăng dần góc với y hướng xuống = chiều kim đồng hồ
    start = int(np.argmin(pts[:, 0] + pts[:, 1]))
    return np.roll(pts, -start, axis=0)


def is_valid_quad(q: np.ndarray, min_area: float = 100.0) -> tuple[bool, str]:
    """Luật của app (và chặt hơn): lồi, đúng chiều, đủ lớn."""
    if not np.all(np.isfinite(q)):
        return False, "toạ độ không hữu hạn"
    area = signed_area(q)
    if area <= 0:
        return False, "sai chiều (không theo chiều kim đồng hồ)"
    if area < min_area:
        return False, f"diện tích quá nhỏ ({area:.0f} px²)"
    for i in range(4):
        a, b, c = q[i], q[(i + 1) % 4], q[(i + 2) % 4]
        cross = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
        if cross <= 0:
            return False, "không lồi"
    return True, ""


def line_intersection(p1, d1, p2, d2) -> np.ndarray:
    """Giao điểm hai đường p1 + t*d1 và p2 + s*d2."""
    a = np.array([[d1[0], -d2[0]], [d1[1], -d2[1]]], dtype=np.float64)
    b = np.array([p2[0] - p1[0], p2[1] - p1[1]], dtype=np.float64)
    t = np.linalg.solve(a, b)[0]
    return np.array([p1[0] + t * d1[0], p1[1] + t * d1[1]])


def expand_quad(q: np.ndarray, d: float) -> np.ndarray:
    """K2.5: dịch mỗi cạnh ra ngoài theo pháp tuyến d px rồi lấy giao điểm hai cạnh kề."""
    if d == 0:
        return q.copy()
    q = np.asarray(q, dtype=np.float64)
    lines = []
    for i in range(4):
        a, b = q[i], q[(i + 1) % 4]
        dirv = b - a
        dirv = dirv / np.linalg.norm(dirv)
        # Với thứ tự kim đồng hồ trên ảnh (y xuống), pháp tuyến ngoài là (dy, -dx).
        normal = np.array([dirv[1], -dirv[0]])
        lines.append((a + normal * d, dirv))
    out = np.zeros((4, 2))
    for i in range(4):
        prev_line = lines[(i - 1) % 4]
        cur_line = lines[i]
        out[i] = line_intersection(prev_line[0], prev_line[1], cur_line[0], cur_line[1])
    return out


def edge_lengths(q: np.ndarray) -> np.ndarray:
    return np.linalg.norm(np.roll(q, -1, axis=0) - q, axis=1)  # top, right, bottom, left


def tilt_score(q: np.ndarray) -> float:
    """0 = hai cặp cạnh đối song song hoàn toàn. Đơn vị: radian (tổng lệch góc)."""
    def ang(v):
        return np.arctan2(v[1], v[0])
    top = q[1] - q[0]
    bottom = q[2] - q[3]
    left = q[3] - q[0]
    right = q[2] - q[1]
    d1 = abs((ang(top) - ang(bottom) + np.pi) % (2 * np.pi) - np.pi)
    d2 = abs((ang(left) - ang(right) + np.pi) % (2 * np.pi) - np.pi)
    return float(d1 + d2)


def measured_ratio(q: np.ndarray) -> float:
    lens = edge_lengths(q)
    return float((lens[0] + lens[2]) / (lens[1] + lens[3]))


def homography(src_w: float, src_h: float, quad: np.ndarray) -> np.ndarray:
    src = np.array([[0, 0], [src_w, 0], [src_w, src_h], [0, src_h]], dtype=np.float32)
    return cv2.getPerspectiveTransform(src, quad.astype(np.float32))


def quad_to_dict(q: np.ndarray) -> dict:
    return {name: [round(float(q[i, 0]), 2), round(float(q[i, 1]), 2)] for i, name in enumerate(CORNERS)}


def quad_from_dict(d: dict) -> np.ndarray:
    return np.array([d[name] for name in CORNERS], dtype=np.float64)
