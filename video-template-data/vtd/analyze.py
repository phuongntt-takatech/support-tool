"""Lượt 1 (D6.1): đọc frame đã chuẩn hoá, dò góc mọi frame (D4), xử lý theo thời gian,
đo viền nhoè để nới khung, chọn previewFrame và posterRatio (D5).
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field

import cv2
import numpy as np

from .config import cfg
from .detect import KeyColor, detect_quad, green_map, learn_key_color
from .geometry import expand_quad, edge_lengths, measured_ratio, signed_area, tilt_score
from .media import ProbeInfo, iter_frames
from .util import Warn, die, log

MD5_STRIDE = 37  # so khớp hai lượt đọc ở các frame này (D6.1)


@dataclass
class Analysis:
    info: ProbeInfo
    key: KeyColor
    n_frames: int
    group: str                       # "A" đứng yên / "B" chuyển động
    quads_detected: np.ndarray       # (N,4,2) sau làm mượt / nội suy, CHƯA nới (quy ước OpenCV)
    quads: np.ndarray                # (1 hoặc N,4,2) ĐÃ nới — chính là quad ghi vào JSON (đổi quy ước khi ghi)
    expand_px: int
    blur_max: float
    blur_min: float
    despill: bool
    preview_frame: int
    poster_ratio: tuple             # (w, h) — số nguyên nếu tỷ lệ chuẩn
    ratio_measured: float
    ratio_snapped: str | None
    poster_size: tuple               # (w, h) px của ảnh mẫu khi ghép
    interpolated: list[int]
    ok_flags: list[bool]
    frame_md5: dict
    warnings: list[Warn] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    def quad_at(self, i: int) -> np.ndarray:
        return self.quads[0] if len(self.quads) == 1 else self.quads[i]


def frame_md5(frame: np.ndarray) -> str:
    return hashlib.md5(frame.tobytes()).hexdigest()


def _sharpness(gray_small: np.ndarray) -> float:
    return float(cv2.Laplacian(gray_small, cv2.CV_32F).var())


def measure_blur(frame: np.ndarray, quad: np.ndarray, max_ring: int, thr: float) -> float:
    """Đo bề rộng viền ám xanh ngoài mép quad (px)."""
    H, W = frame.shape[:2]
    x0, y0 = np.floor(quad.min(axis=0)).astype(int) - max_ring - 3
    x1, y1 = np.ceil(quad.max(axis=0)).astype(int) + max_ring + 3
    x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, W), min(y1, H)
    roi = frame[y0:y1, x0:x1].astype(np.int16)
    inside = np.zeros(roi.shape[:2], np.uint8)
    pts = np.round((quad - [x0, y0]) * 16).astype(np.int32)
    cv2.fillConvexPoly(inside, pts, 1, lineType=cv2.LINE_8, shift=4)
    dist = cv2.distanceTransform((1 - inside).astype(np.uint8), cv2.DIST_L2, 5)
    excess = roi[..., 1] - np.maximum(roi[..., 0], roi[..., 2])
    rings = []
    for r in range(1, max_ring + 1):
        sel = (dist > r - 0.5) & (dist <= r + 0.5)
        rings.append(float(excess[sel].mean()) if sel.any() else 0.0)
    bg = float(np.median(rings[-3:]))
    width = 0.0
    for r, val in enumerate(rings, start=1):
        if val - bg > thr:
            width = float(r)
        else:
            break
    return width


def snap_ratio(r: float) -> tuple[tuple, str | None, bool]:
    """Làm tròn về tỷ lệ chuẩn gần nhất nếu lệch < tolerance. Trả (w,h), nhãn, lưỡng lự."""
    pc = cfg()["posterRatio"]
    cands = []
    for s in pc["standards"]:
        a, b = (int(x) for x in s.split(":"))
        dev = abs(r - a / b) / (a / b)
        if dev < pc["tolerance"]:
            cands.append((dev, a, b, s))
    cands.sort()
    if not cands:
        return (round(r, 2), 1), None, False
    ambiguous = len(cands) > 1 and cands[1][0] - cands[0][0] < 0.02
    _, a, b, s = cands[0]
    return (a, b), s, ambiguous


def _gauss_smooth(series: np.ndarray, sigma: float) -> np.ndarray:
    """Làm mượt hai chiều (không trễ) theo trục 0."""
    if sigma <= 0 or len(series) < 3:
        return series.copy()
    rad = max(1, int(math.ceil(3 * sigma)))
    k = np.exp(-0.5 * (np.arange(-rad, rad + 1) / sigma) ** 2)
    k /= k.sum()
    pad = np.pad(series, [(rad, rad)] + [(0, 0)] * (series.ndim - 1), mode="edge")
    out = np.zeros_like(series)
    for j, w in enumerate(k):
        out += w * pad[j:j + len(series)]
    return out


def _runs(flags: list[bool]) -> list[tuple[int, int]]:
    """Các đoạn liên tiếp flag=False (start, end inclusive)."""
    runs, start = [], None
    for i, f in enumerate(flags):
        if not f and start is None:
            start = i
        if f and start is not None:
            runs.append((start, i - 1)); start = None
    if start is not None:
        runs.append((start, len(flags) - 1))
    return runs


def analyze(info: ProbeInfo, *, manual: dict[int, np.ndarray] | None = None,
            overrides: dict | None = None, progress: bool = True, light: bool = False) -> Analysis:
    """light=True dùng cho inspect: bỏ đo viền nhoè / chọn previewFrame chi tiết."""
    c = cfg()
    overrides = overrides or {}
    manual = manual or {}
    frames_iter = iter_frames(info)
    first: list[np.ndarray] = []
    for f in frames_iter:
        first.append(f)
        if len(first) >= max(c["detect"]["learnFrames"], 1):
            break
    if not first:
        die(f"{info.path}: không đọc được frame nào")
    key = learn_key_color(first)
    if key is None:
        # thử thêm vài frame nữa
        for f in frames_iter:
            first.append(f)
            if len(first) % 10 == 0:
                key = learn_key_color(first[-10:])
                if key or len(first) > 60:
                    break
    if key is None:
        die(f"{info.path}: không tìm thấy vùng xanh để học màu chuẩn (video khác loại? xem inspect)")

    est_n = max(1, int(round(info.duration * float(info.target_fraction))))
    bleed_stride = max(1, est_n // c["bleed"]["sampleFrames"])
    dets, sharp, diffs, md5s, blurs = [], [], [], {}, []
    prev_small = None
    no_green, extra, touch, notquad, cuts = [], [], [], [], []

    def process(i: int, f: np.ndarray) -> None:
        nonlocal prev_small
        gmap = green_map(f, key)
        det = detect_quad(f, key, gmap)
        dets.append(det)
        gray = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
        small = cv2.resize(gray, (min(480, f.shape[1]), int(min(480, f.shape[1]) * f.shape[0] / f.shape[1])),
                           interpolation=cv2.INTER_AREA)
        sharp.append(_sharpness(small))
        if prev_small is not None:
            d = float(np.mean(np.abs(small.astype(np.int16) - prev_small.astype(np.int16))))
            diffs.append(d)
            if d > c["detect"]["sceneCutDiff"]:
                cuts.append(i)
        else:
            diffs.append(0.0)
        prev_small = small
        if i % MD5_STRIDE == 0:
            md5s[i] = frame_md5(f)
        if any(r in ("không thấy vùng xanh", "vùng xanh quá nhỏ") for r in det.reasons):
            no_green.append(i)
        if det.extra_regions:
            extra.append(i)
        if det.touches_border:
            touch.append(i)
        if any("4 cạnh" in r or "khớp tứ giác" in r for r in det.reasons):
            notquad.append(i)
        if not light and det.ok and i % bleed_stride == 0:
            blurs.append(measure_blur(f, det.quad, c["bleed"]["maxRingPx"], c["bleed"]["greenExcessThr"]))

    idx = 0
    for f in first:
        process(idx, f); idx += 1
    for f in frames_iter:
        process(idx, f); idx += 1
        if progress and idx % 60 == 0:
            log(f"    … đã dò {idx} frame")
    n = idx
    warns: list[Warn] = []

    # Rào chắn D2.4 (chỉ cảnh báo)
    if no_green:
        warns.append(Warn("no_green", f"{len(no_green)} frame không thấy vùng xanh", no_green))
    if extra:
        warns.append(Warn("multi_green", f"{len(extra)} frame có hơn một vùng xanh lớn", extra))
    if touch:
        warns.append(Warn("touch_edge", f"{len(touch)} frame vùng xanh chạm mép hình", touch))
    if notquad:
        warns.append(Warn("not_quad", f"{len(notquad)} frame vùng xanh không giống hình 4 cạnh", notquad))
    if cuts:
        warns.append(Warn("scene_cut", f"Nghi chuyển cảnh ở {len(cuts)} frame", cuts))

    # --- Theo thời gian (D4.3) ---
    tc = c["temporal"]
    raw = np.full((n, 4, 2), np.nan)
    ok = [False] * n
    for i, det in enumerate(dets):
        if det.ok:
            raw[i] = det.quad
            ok[i] = True
    for fi, q in manual.items():
        if 0 <= fi < n:
            raw[fi] = q
            ok[fi] = True
    if not any(ok):
        die(f"{info.path}: không dò được quad ở frame nào (dùng lệnh pick để chọn tay)")

    # Bỏ frame nhảy xa bất thường so với lân cận
    valid_idx = [i for i in range(n) if ok[i]]
    jumps = []
    for pos, i in enumerate(valid_idx):
        if i in manual:
            continue
        nb = [valid_idx[j] for j in range(max(0, pos - 3), min(len(valid_idx), pos + 4)) if j != pos]
        if len(nb) < 2:
            continue
        med = np.median(raw[nb], axis=0)
        if np.max(np.linalg.norm(raw[i] - med, axis=1)) > tc["jumpPx"]:
            jumps.append(i)
    for i in jumps:
        ok[i] = False
        raw[i] = np.nan
    if jumps:
        warns.append(Warn("jump_detect", f"{len(jumps)} frame dò nhảy bất thường, đã bỏ và nội suy", jumps))

    good = np.array(ok)
    med = np.nanmedian(raw[good], axis=0)
    maxdev = float(np.max(np.linalg.norm(raw[good] - med, axis=2)))
    group = overrides.get("group") or ("A" if maxdev < tc["staticPx"] and not manual else "B")

    interpolated = [i for i in range(n) if not ok[i]]
    if group == "A":
        detected = np.repeat(med[None], n, axis=0)
    else:
        filled = raw.copy()
        xs = np.arange(n)
        gi = xs[good]
        for corner in range(4):
            for axis in range(2):
                filled[:, corner, axis] = np.interp(xs, gi, raw[good, corner, axis])
        detected = _gauss_smooth(filled, tc["smoothSigma"])
        for fi, q in manual.items():
            if 0 <= fi < n:
                detected[fi] = q
    for s, e in _runs(ok):
        if (e - s + 1) > tc["maxGapFrames"] or s == 0 or e == n - 1:
            if not all(fi in manual for fi in (s, e)):
                warns.append(Warn("needs_pick", f"Dò thất bại frame {s}–{e}: nên chọn tay (lệnh pick)",
                                  list(range(s, e + 1))))

    # --- Nới khung (D4.6) ---
    bc = c["bleed"]
    blur_max = max(blurs) if blurs else 0.0
    blur_min = min(blurs) if blurs else 0.0
    expand = int(math.ceil(blur_max)) + bc["safetyPx"]
    if "expandPx" in overrides and overrides["expandPx"] is not None:
        expand = int(overrides["expandPx"])
    if expand > bc["capPx"]:
        warns.append(Warn("expand_cap", f"Viền nhoè {blur_max:.0f} px → nới {expand} px vượt trần {bc['capPx']} px, đã khoá ở trần"))
        expand = bc["capPx"]
    if blur_max - blur_min > bc["spreadWarnPx"]:
        warns.append(Warn("blur_spread", f"Viền nhoè chênh lệch lớn trong video ({blur_min:.0f}–{blur_max:.0f} px)"))
    despill = blur_max >= 1.0
    if overrides.get("despill") is not None:
        despill = bool(overrides["despill"])

    base = detected[:1] if group == "A" else detected
    quads = np.stack([expand_quad(q, expand) for q in base])

    # --- posterRatio (D5.2) ---
    tilts = np.array([tilt_score(q) for q in base])
    ref = base[int(np.argmin(tilts))]
    r_meas = measured_ratio(ref)
    (pw, ph), snapped, ambiguous = snap_ratio(r_meas)
    if snapped is None:
        warns.append(Warn("ratio_nonstandard", f"posterRatio đo được {r_meas:.3f} không khớp tỷ lệ chuẩn"))
    elif ambiguous:
        warns.append(Warn("ratio_ambiguous", f"posterRatio {r_meas:.3f} lưỡng lự giữa hai tỷ lệ chuẩn, đã chọn {snapped}"))
    if overrides.get("posterRatio"):
        pr = overrides["posterRatio"]
        pw, ph = pr["w"], pr["h"]
        snapped = f"ghi đè {pw}:{ph}"

    # --- previewFrame (D5.4 / mục 10.2) ---
    pf_cfg = c["previewFrame"]
    sharp_a = np.array(sharp)
    if overrides.get("previewFrame") is not None:
        pframe = int(np.clip(overrides["previewFrame"], 0, n - 1))
    elif group == "A":
        lo, hi = int(n * pf_cfg["staticMiddleFrac"]), int(math.ceil(n * (1 - pf_cfg["staticMiddleFrac"])))
        hi = max(hi, lo + 1)
        pframe = lo + int(np.argmax(sharp_a[lo:hi]))
    else:
        lo, hi = int(n * pf_cfg["edgeFrac"]), int(math.ceil(n * (1 - pf_cfg["edgeFrac"])))
        hi = max(hi, lo + 1)
        speed = np.zeros(n)
        for i in range(n):
            a, b = max(0, i - 1), min(n - 1, i + 1)
            speed[i] = float(np.mean(np.linalg.norm(detected[b] - detected[a], axis=1)))
        area = np.array([signed_area(q) for q in detected])
        tilt = np.array([tilt_score(q) for q in detected])

        def norm(v):
            v = v[lo:hi]
            return (v - v.min()) / (v.max() - v.min() + 1e-9)
        score = norm(sharp_a) - norm(speed) + 0.5 * norm(area) - 0.5 * norm(tilt)
        bad = np.array([not ok[i] for i in range(lo, hi)])
        score[bad] -= 10
        pframe = lo + int(np.argmax(score))

    # --- Kích thước ảnh mẫu (D6.3): cạnh dài = lần to nhất khung xuất hiện ---
    longest = max(float(edge_lengths(q).max()) for q in quads)
    L = int(min(math.ceil(longest), c["posterMaxPx"]))
    ratio = pw / ph
    poster_size = (L, max(1, round(L / ratio))) if ratio >= 1 else (max(1, round(L * ratio)), L)

    stats = {
        "maxCornerDevPx": round(maxdev, 2),
        "okFrames": int(sum(ok)),
        "blurSamples": [round(b, 1) for b in blurs],
        "keyColor": key.to_dict(),
        "posterLongestPx": round(longest, 1),
    }
    return Analysis(
        info=info, key=key, n_frames=n, group=group, quads_detected=detected, quads=quads,
        expand_px=expand, blur_max=blur_max, blur_min=blur_min, despill=despill,
        preview_frame=pframe, poster_ratio=(pw, ph), ratio_measured=r_meas, ratio_snapped=snapped,
        poster_size=poster_size, interpolated=interpolated, ok_flags=ok, frame_md5=md5s,
        warnings=warns, stats=stats,
    )
