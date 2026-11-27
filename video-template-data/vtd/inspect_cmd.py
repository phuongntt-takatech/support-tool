"""Lệnh inspect (D2): kiểm tra môi trường, đọc thông số, đo đứng yên / chuyển động, ảnh tổng hợp 6 frame,
rào chắn; ghi vào sổ kiểm kê. Máy chỉ đề xuất nhóm, dev quyết ở cột decision."""
from __future__ import annotations

import os
from fractions import Fraction
from pathlib import Path

import cv2
import numpy as np

from . import registry
from .analyze import analyze
from .config import OUT, cfg
from .detect import detect_quad
from .locales import load_codes
from .media import iter_frames, probe, require_ffmpeg, tool_version
from .util import list_videos, log


def check_env() -> None:
    log("== Môi trường ==")
    for exe in (cfg().ffmpeg, cfg().ffprobe):
        v = tool_version(exe)
        log(f"  {exe}: {v or 'KHÔNG CÓ — cài ffmpeg và thêm vào PATH'}")
    from .gemini import api_key, models
    log(f"  AI (Gemini): {'có GEMINI_API_KEY, model ' + ' → '.join(models()) if api_key() else 'chưa có GEMINI_API_KEY (build sẽ dùng tên từ tên file)'}")
    codes, warns = load_codes()
    log(f"  Ngôn ngữ app: {len(codes)} mã")
    for w in warns:
        log(f"  ! {w.message}")
    content = Path(__file__).resolve().parent.parent / cfg()["samplePoster"]["content"]
    log(f"  Ảnh mẫu: {'biểu tượng + chữ từ ' + content.name if content.exists() else 'cắt tạm từ ảnh tham chiếu (chờ bản độ phân giải cao của designer)'}")


def _sheet(info, an, path: Path) -> None:
    """6 frame rải đều, tô viền ngoài vùng xanh và đánh dấu 4 góc."""
    n = an.n_frames
    picks = [int(round(i * (n - 1) / 5)) for i in range(6)]
    tiles = []
    for idx, f in enumerate(iter_frames(info)):
        if idx not in picks:
            continue
        det = detect_quad(f, an.key)
        vis = f.copy()
        if det.contour is not None:
            cv2.drawContours(vis, [det.contour], -1, (255, 0, 255), 2, cv2.LINE_AA)
        if det.quad is not None:
            for p in det.quad:
                cv2.circle(vis, (int(round(p[0])), int(round(p[1]))), 6, (0, 0, 255), -1, cv2.LINE_AA)
        label = f"#{idx} {'OK' if det.ok else 'LOI: ' + '; '.join(det.reasons)[:60]}"
        cv2.putText(vis, label, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 4, cv2.LINE_AA)
        cv2.putText(vis, label, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 1, cv2.LINE_AA)
        scale = 480 / vis.shape[1]
        tiles.append(cv2.resize(vis, (480, int(vis.shape[0] * scale)), interpolation=cv2.INTER_AREA))
        if idx >= picks[-1]:
            break
    while len(tiles) < 6:
        tiles.append(np.zeros_like(tiles[0]))
    rows = [np.hstack(tiles[i:i + 3]) for i in (0, 3)]
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 85])


def inspect_one(video: Path, recheck: bool = False) -> bool:
    """Trả True nếu đã kiểm tra, False nếu bỏ qua (video đã có trong sổ kiểm kê)."""
    log(f"\n== {video.name} ==")
    info = probe(video)
    row = registry.inventory_row(info.sha256)
    if row and row.get("width") and not recheck:
        if row.get("file") != video.name:
            registry.upsert_inventory(info.sha256, {"file": video.name}, machine_only=True)
        log(f"  Bỏ qua: đã có trong sổ kiểm kê (nhóm {row.get('group')}, trạng thái {row.get('status')}). "
            f"Dùng --recheck để kiểm tra lại.")
        return False
    fps = float(info.target_fraction)
    log(f"  {info.width}x{info.height}, {float(Fraction(info.r_fps)):.3f} fps{' (VFR)' if info.vfr else ''}, "
        f"{info.duration:.2f} s, {'có' if info.has_audio else 'không'} tiếng ({info.audio_codec or '-'}), "
        f"codec {info.vcodec}, xoay {info.rotation}°")
    an = analyze(info, light=True, progress=False)
    tags = [an.group]
    notes = []
    if float(Fraction(info.r_fps)) > cfg()["normalize"]["maxFps"] + 0.01 or info.vfr or info.rotation:
        tags.append("I")
        notes.append("cần chuẩn hoá (fps/VFR/xoay)")
    if not (8 <= info.duration <= 12):
        tags.append("J")
        notes.append(f"thời lượng {info.duration:.1f} s ngoài 8–12 s (giữ nguyên)")
    warns = [w.message for w in an.warnings] + notes
    log(f"  Nhóm đề xuất: {'+'.join(tags)} ({'đứng yên' if an.group == 'A' else 'chuyển động'}, "
        f"góc lệch tối đa {an.stats['maxCornerDevPx']} px, dò được {an.stats['okFrames']}/{an.n_frames} frame)")
    for w in warns:
        log(f"  ! {w}")
    sheet = OUT / "inspect" / f"{info.sha256[:8]}_{video.stem}.jpg"
    _sheet(info, an, sheet)
    log(f"  Ảnh tổng hợp: {sheet}")
    registry.upsert_inventory(info.sha256, {
        "file": video.name, "width": info.width, "height": info.height,
        "fps": f"{fps:.3f}", "duration_s": f"{info.duration:.2f}",
        "audio": info.audio_codec or "", "rotation": info.rotation,
        "group": "+".join(tags), "warnings": " | ".join(warns),
    }, machine_only=True)
    return True


def run(target: Path, recheck: bool = False) -> None:
    check_env()
    require_ffmpeg()
    videos = list_videos(target)
    if not videos:
        log(f"\nKhông có video nào trong {target}")
        return
    done = sum(inspect_one(v, recheck) for v in videos)
    log(f"\nTổng: {len(videos)} video, kiểm tra {done}, bỏ qua {len(videos) - done} (đã có trong sổ).")
    log(f"\nĐã ghi sổ kiểm kê: registry/inventory.csv — điền cột decision (Giữ / Bỏ / Để sau), reason, nguồn và giấy phép.")
