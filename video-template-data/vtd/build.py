"""Lệnh build: D4–D9 cho một video (hoặc cả thư mục).

Trình tự: lượt 1 dò (analyze) → lượt 2 ghép poster mẫu + nén video.mp4 một lần → kiểm tra sau nén →
thumb.webp, preview.mp4 → placeholder.json → AI đặt tên (sau khi ghép, D1.13) → đổi thư mục tạm thành `name`
→ cập nhật sổ ghi → tạo file soát lỗi (review).
"""
from __future__ import annotations

import shutil
from fractions import Fraction
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from . import placeholder, registry, review
from .analyze import MD5_STRIDE, Analysis, analyze, frame_md5
from .compose import composite, despill
from .config import OUT, TEMPLATE_FILES, cfg, review_out, templates_out
from .locales import load_codes
from .media import (Encoder, ProbeInfo, count_frames, extract_frame, first_frame_pts, iter_frames, probe,
                    require_ffmpeg, stream_durations, transcode)
from .naming import ai_titles, fallback_title, make_name
from .posters import build_sample
from .util import Warn, die, list_videos, log


class BuildError(Exception):
    pass


def _manual_quads(rec: dict | None) -> dict[int, np.ndarray]:
    if not rec:
        return {}
    out = {}
    for k, q in (rec.get("overrides", {}).get("manualQuads") or {}).items():
        out[int(k)] = np.array([q[c] for c in ("tl", "tr", "br", "bl")], dtype=np.float64) - placeholder.PIXEL_OFFSET
    return out


def _encode_video(info: ProbeInfo, an: Analysis, out: Path) -> tuple[int, list[Warn]]:
    """Lượt 2: đọc lại giống hệt lượt 1, ghép poster mẫu, nén một lần (D6)."""
    c = cfg()
    warns: list[Warn] = []
    pw, ph = an.poster_size
    poster, is_temp = build_sample(pw, ph)
    if is_temp:
        warns.append(Warn("temp_sample", "Biểu tượng + chữ của ảnh mẫu đang cắt tạm từ ảnh tham chiếu 850 px (hơi mờ khi khung lớn); "
                                         "có assets/sample_poster_content.png độ phân giải cao thì build lại trước publish"))
    fps = info.target_fraction
    gop = max(1, round(float(fps)))
    audio_copy = (info.audio_codec == "aac")
    enc = Encoder(out, info.width, info.height, fps, crf=c["videoEncode"]["crf"], preset=c["videoEncode"]["preset"],
                  gop=gop, audio_src=info.path if info.has_audio else None, audio_copy=audio_copy)
    band = c["despill"]["bandPx"]
    i = 0
    try:
        for f in iter_frames(info):
            if i in an.frame_md5 and frame_md5(f) != an.frame_md5[i]:
                raise BuildError(f"Lượt đọc thứ hai khác lượt một ở frame {i} (video VFR?) — dừng")
            q = an.quad_at(i) if i < an.n_frames else an.quads[-1]
            if an.despill:
                despill(f, q, band)
            composite(f, poster, q)
            enc.write(f)
            i += 1
    finally:
        enc.close()
    if i != an.n_frames:
        raise BuildError(f"Hai lượt đọc ra số frame khác nhau ({an.n_frames} và {i}) — dừng")
    return i, warns


def _post_checks(path: Path, info: ProbeInfo, n: int) -> list[Warn]:
    """D6.8: lệch thì dừng; thời lượng hình / tiếng lệch thì cảnh báo."""
    out = probe(path, with_hash=False)
    got = count_frames(path)
    if got != n:
        raise BuildError(f"video.mp4 có {got} frame, khác {n} frame đã dò — dừng")
    pts = first_frame_pts(path)
    if not (abs(pts) < 1e-3):
        raise BuildError(f"Frame đầu của video.mp4 không ở 0 (pts {pts}) — dừng")
    if out.rotation:
        raise BuildError("video.mp4 còn cờ xoay — dừng")
    if (out.width, out.height) != (info.width, info.height):
        raise BuildError(f"Kích thước video.mp4 {out.width}x{out.height} sai — dừng")
    if Fraction(out.r_fps) != info.target_fraction:
        raise BuildError(f"fps video.mp4 {out.r_fps} khác {info.target_fps} — dừng")
    warns = []
    d = stream_durations(path)
    if "audio" in d and "video" in d and abs(d["audio"] - d["video"]) > 0.1:
        warns.append(Warn("av_duration", f"Thời lượng hình {d['video']:.2f} s và tiếng {d['audio']:.2f} s lệch nhau"))
    if info.has_audio and "audio" not in d:
        raise BuildError("Video gốc có tiếng nhưng video.mp4 không có — dừng")
    return warns


def _make_thumb(video: Path, info: ProbeInfo, frame_idx: int, out: Path) -> np.ndarray:
    """D8.2: previewFrame đọc lại từ video.mp4 đã nén; giữ tỷ lệ; rộng 540 (không phóng to)."""
    c = cfg()["thumb"]
    frame = extract_frame(video, frame_idx, info.width, info.height)
    w = min(c["width"], info.width)
    h = round(info.height * w / info.width)
    small = cv2.resize(frame, (w, h), interpolation=cv2.INTER_AREA)
    Image.fromarray(cv2.cvtColor(small, cv2.COLOR_BGR2RGB)).save(out, "WEBP", quality=c["quality"], method=6)
    back = Image.open(out)
    if abs(back.width / back.height - info.width / info.height) / (info.width / info.height) > 0.005:
        raise BuildError("thumb.webp sai tỷ lệ so với video — dừng")
    return frame


def _make_preview(video: Path, info: ProbeInfo, out: Path, crf_override: int | None) -> list[Warn]:
    """D8.3 / D8.4."""
    c = cfg()["preview"]
    fps = info.target_fraction
    out_fps = fps if float(fps) <= c["maxFps"] + 0.01 else Fraction(c["maxFps"])
    s = c["shortSide"]
    if info.width >= info.height:
        w, h = round(info.width * s / info.height / 2) * 2, s
    else:
        w, h = s, round(info.height * s / info.width / 2) * 2
    vf = []
    if out_fps != fps:
        vf.append(f"fps=fps={out_fps.numerator}/{out_fps.denominator}")
    if c.get("denoise"):
        vf.append(c["denoise"])
    vf.append(f"scale={w}:{h}:flags=lanczos")
    vf.append("format=yuv420p")
    gop = max(1, round(float(out_fps) * c["keyintSec"]))
    crf = crf_override if crf_override is not None else c["crf"]
    transcode(video, out, ["-map", "0:v:0", "-an", "-vf", ",".join(vf),
                           "-c:v", "libx264", "-preset", c["preset"], "-crf", str(crf),
                           "-profile:v", "main", "-g", str(gop), "-keyint_min", str(gop), "-sc_threshold", "0",
                           "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
                           "-color_range", "tv", "-movflags", "+faststart"])
    p = probe(out, with_hash=False)
    if p.has_audio:
        raise BuildError("preview.mp4 còn tiếng — dừng")
    if min(p.width, p.height) != s:
        raise BuildError(f"preview.mp4 cạnh ngắn {min(p.width, p.height)} khác {s} — dừng")
    dv = stream_durations(video).get("video", 0)
    dp = stream_durations(out).get("video", 0)
    if abs(dv - dp) > 1.5 / float(out_fps):
        raise BuildError(f"preview.mp4 dài {dp:.2f} s khác video.mp4 {dv:.2f} s — dừng")
    warns = []
    mb = out.stat().st_size / 1e6
    if mb > c["warnMB"]:
        warns.append(Warn("preview_size", f"preview.mp4 nặng {mb:.2f} MB (> {c['warnMB']} MB)"))
    return warns


def _jpeg(frame: np.ndarray, max_w: int = 1280) -> bytes:
    if frame.shape[1] > max_w:
        frame = cv2.resize(frame, (max_w, round(frame.shape[0] * max_w / frame.shape[1])), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 88])
    return buf.tobytes()


def build_one(video: Path, *, as_new: bool = False, no_ai: bool = False, force: bool = False,
              rebuild: bool = False) -> str | None:
    c = cfg()
    log(f"\n== build {video.name} ==")
    info = probe(video)
    inv = registry.inventory_row(info.sha256)
    if inv and inv.get("decision", "").strip().lower() in ("bỏ", "bo", "skip") and not force:
        log("  Bỏ qua: sổ kiểm kê ghi quyết định 'Bỏ' (dùng --force để build vẫn)")
        return None
    existing = [] if as_new else registry.find_by_source(info.sha256)
    rec = existing[0] if existing else None
    if rec and rec.get("build") and not rebuild and not rec.get("publish"):
        # Đã làm rồi thì không làm nữa (nhận ra bằng mã băm, kể cả khi đổi tên file).
        log(f"  Bỏ qua: đã có template '{rec['name']}' (build {rec['build']['at']}). Dùng --rebuild để build lại.")
        return None
    if rec and rec.get("publish"):
        if not rebuild:
            log(f"  Bỏ qua: đã publish thành template '{rec['name']}'.")
            return None
        log(f"  Từ chối: template '{rec['name']}' đã publish, không build lại (D7). Dùng --as-new để tạo template mới.")
        return None
    if len(existing) > 1:
        log(f"  Video này có {len(existing)} template; build lại '{rec['name']}'")

    overrides = (rec or {}).get("overrides", {})
    log("  Lượt 1: dò 4 góc…")
    an = analyze(info, manual=_manual_quads(rec), overrides=overrides)
    log(f"  Nhóm {an.group}, {an.n_frames} frame, nới {an.expand_px} px, khử hắt sáng {'bật' if an.despill else 'tắt'}, "
        f"posterRatio {an.poster_ratio[0]}:{an.poster_ratio[1]} (đo {an.ratio_measured:.3f}), previewFrame {an.preview_frame}")

    tmp = OUT / "tmp" / f"build_{info.sha256[:12]}"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    warns: list[Warn] = list(an.warnings)
    try:
        log("  Lượt 2: ghép poster mẫu + nén video.mp4…")
        _, w2 = _encode_video(info, an, tmp / "video.mp4")
        warns += w2
        warns += _post_checks(tmp / "video.mp4", info, an.n_frames)
        log("  Thumb + preview…")
        pframe_img = _make_thumb(tmp / "video.mp4", info, an.preview_frame, tmp / "thumb.webp")
        warns += _make_preview(tmp / "video.mp4", info, tmp / "preview.mp4", overrides.get("previewCrf"))
        text = placeholder.render(info.width, info.height, info.target_fraction, an.poster_ratio, an.preview_frame,
                                  c["bleedPx"], an.quads)
        placeholder.write(tmp / "placeholder.json", text)
        errs = placeholder.validate(placeholder.load(tmp / "placeholder.json"), an.n_frames)
        if errs:
            raise BuildError("placeholder.json không hợp lệ: " + "; ".join(errs))
    except BuildError as e:
        die(str(e))

    # --- Tên hiển thị + name ---
    codes, lw = load_codes()
    warns += lw
    all_recs = registry.load_all()
    if rec and rec.get("titles", {}).get("en"):
        titles, tsrc = rec["titles"], rec.get("titlesSource")
        log(f"  Giữ tên đã có: {titles['en']}")
    else:
        existing_titles = [r["titles"]["en"] for r in all_recs if r.get("titles", {}).get("en")]
        titles, tsrc = None, None
        if not no_ai:
            log("  AI đặt tên + dịch…")
            imgs = [_jpeg(pframe_img)]
            if an.group == "B":
                for extra in (int(an.n_frames * 0.25), int(an.n_frames * 0.75)):
                    if abs(extra - an.preview_frame) > an.n_frames * 0.1:
                        imgs.append(_jpeg(extract_frame(tmp / "video.mp4", extra, info.width, info.height)))
            titles, aw = ai_titles(imgs, existing_titles, codes)
            warns += aw
            tsrc = "ai" if titles else None
        if not titles:
            en = fallback_title(video.name, existing_titles)
            titles, tsrc = {"en": en}, "fallback"
            warns.append(Warn("title_fallback", f"Tên lấy từ tên file: '{en}', chưa có bản dịch — sửa trong sổ ghi"))
        log(f"  Tên: {titles['en']} ({tsrc})")

    if rec:
        name = rec["name"]
    else:
        taken = {r["name"] for r in all_recs} | {p.name for p in templates_out().glob("*")}
        name = make_name(titles["en"], taken)
        rec = registry.new_record(name, video.name, info.sha256, str(video))

    dest = templates_out() / name
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(tmp), str(dest))

    hashes = registry.outputs_hashes(name)
    rec["source"].update({"file": video.name, "lastPath": str(video)})
    rec["titles"] = titles
    rec["titlesSource"] = tsrc
    rec.setdefault("overrides", dict(registry.DEFAULT_OVERRIDES))
    rec["build"] = {
        "at": registry.now_iso(),
        "group": an.group,
        "frames": an.n_frames,
        "fps": info.target_fps,
        "size": [info.width, info.height],
        "expandPx": an.expand_px,
        "blurPx": [round(an.blur_min, 1), round(an.blur_max, 1)],
        "despill": an.despill,
        "previewFrame": an.preview_frame,
        "posterRatio": {"w": an.poster_ratio[0], "h": an.poster_ratio[1]},
        "posterRatioMeasured": round(an.ratio_measured, 4),
        "posterSize": list(an.poster_size),
        "interpolatedFrames": an.interpolated[:200],
        "stats": an.stats,
        "probe": {k: v for k, v in info.to_dict().items() if k != "path"},
        "outputs": hashes,
        "warnings": [w.to_dict() for w in warns],
    }
    if rec.get("review") and rec["review"].get("outputsHash") != registry.combined_hash(hashes):
        rec["review"] = None  # build lại → dấu "đã soát" tự mất (D7.6)
    registry.save(rec)
    if name not in registry.load_order():
        registry.order_insert_front(name)
    registry.upsert_inventory(info.sha256, {"status": "Đã build", "name": name, "file": video.name})
    log(f"  Xong: out/templates/{name}/ ({len(warns)} cảnh báo)")
    review.generate(name)
    return name


def run(target: Path, *, as_new: bool, no_ai: bool, force: bool, rebuild: bool = False) -> None:
    require_ffmpeg()
    videos = list_videos(target)
    if not videos:
        log(f"Không có video nào trong {target}")
        return
    names = []
    for v in videos:
        n = build_one(v, as_new=as_new, no_ai=no_ai, force=force, rebuild=rebuild)
        if n:
            names.append(n)
    log(f"\nTổng: {len(videos)} video, build {len(names)}, bỏ qua {len(videos) - len(names)}.")
    registry.sync_inventory_status()
    for rec in registry.load_all():  # bù trang soát còn thiếu nếu lần trước bị ngắt
        if rec.get("build") and not (review_out() / rec["name"] / "summary.json").exists():
            review.generate(rec["name"])
            names.append(rec["name"])
    if names:
        review.generate_index()
        log("Soát: menu mục 3, hoặc lệnh .venv\\Scripts\\python vtd.py review")
