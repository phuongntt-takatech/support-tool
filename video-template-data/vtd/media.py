"""Làm việc với ffmpeg / ffprobe: đọc thông số, đọc frame đã chuẩn hoá, nén video."""
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, asdict
from fractions import Fraction
from pathlib import Path

import numpy as np

from .config import cfg
from .util import die, sha256_file


def tool_version(exe: str) -> str | None:
    if not shutil.which(exe):
        return None
    try:
        out = subprocess.run([exe, "-version"], capture_output=True, text=True, timeout=20).stdout
        return out.splitlines()[0] if out else "?"
    except OSError:
        return None


def require_ffmpeg() -> None:
    for exe in (cfg().ffmpeg, cfg().ffprobe):
        if not tool_version(exe):
            die(f"Không tìm thấy '{exe}'. Cài ffmpeg và thêm vào PATH, hoặc đặt đường dẫn trong config.local.json.")


def _ffprobe_json(args: list[str]) -> dict:
    cmd = [cfg().ffprobe, "-v", "error", "-of", "json", *args]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if res.returncode != 0:
        die(f"ffprobe lỗi: {res.stderr.strip()}")
    return json.loads(res.stdout or "{}")


def _frac(s: str | None) -> Fraction | None:
    if not s or s in ("0/0", "N/A"):
        return None
    try:
        f = Fraction(s)
        return f if f > 0 else None
    except (ValueError, ZeroDivisionError):
        return None


@dataclass
class ProbeInfo:
    path: str
    sha256: str
    width: int            # kích thước hiển thị (đã tính cờ xoay)
    height: int
    rotation: int
    r_fps: str
    avg_fps: str
    vfr: bool
    target_fps: str       # nhịp sau chuẩn hoá (D6: ≤ 30, cố định)
    nb_frames: int | None
    duration: float
    vcodec: str
    pix_fmt: str
    color_space: str
    has_audio: bool
    audio_codec: str | None

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def target_fraction(self) -> Fraction:
        return Fraction(self.target_fps)


def probe(path: Path, *, with_hash: bool = True) -> ProbeInfo:
    data = _ffprobe_json(["-show_streams", "-show_format", str(path)])
    streams = data.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), None)
    if v is None:
        die(f"{path.name}: không có luồng hình")
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)

    rotation = 0
    for sd in v.get("side_data_list", []) or []:
        if "rotation" in sd:
            rotation = int(round(float(sd["rotation"])))
    if not rotation and v.get("tags", {}).get("rotate"):
        rotation = int(v["tags"]["rotate"])
    rotation %= 360
    w, h = int(v["width"]), int(v["height"])
    if rotation in (90, 270):
        w, h = h, w

    r = _frac(v.get("r_frame_rate"))
    avg = _frac(v.get("avg_frame_rate")) or r
    if r is None:
        r = avg
    if r is None:
        die(f"{path.name}: không đọc được fps")
    vfr = abs(float(r) - float(avg)) / float(r) > 0.01
    max_fps = cfg()["normalize"]["maxFps"]
    if vfr:
        target = Fraction(min(max_fps, round(float(avg))))
    elif float(r) > max_fps + 0.01:
        target = Fraction(max_fps)
    else:
        target = r

    nb = v.get("nb_frames")
    duration = float(v.get("duration") or data.get("format", {}).get("duration") or 0)
    return ProbeInfo(
        path=str(path),
        sha256=sha256_file(path) if with_hash else "",
        width=w,
        height=h,
        rotation=rotation,
        r_fps=f"{r.numerator}/{r.denominator}",
        avg_fps=f"{avg.numerator}/{avg.denominator}",
        vfr=vfr,
        target_fps=f"{target.numerator}/{target.denominator}",
        nb_frames=int(nb) if nb and str(nb).isdigit() else None,
        duration=duration,
        vcodec=v.get("codec_name", "?"),
        pix_fmt=v.get("pix_fmt", "?"),
        color_space=v.get("color_space", "unknown"),
        has_audio=a is not None,
        audio_codec=a.get("codec_name") if a else None,
    )


def _in_matrix(info: ProbeInfo) -> str:
    cs = info.color_space
    if cs in ("smpte170m", "bt470bg"):
        return "bt601"
    if cs == "bt709":
        return "bt709"
    return "bt709" if info.height >= 720 or info.width >= 1280 else "bt601"


def iter_frames(info: ProbeInfo, *, normalize: bool = True):
    """Đọc frame BGR đúng nhịp đã chuẩn hoá: xoay đúng chiều, fps mục tiêu, frame đầu ở 0.

    Hai lần gọi với cùng video luôn ra cùng chuỗi frame (D6.1).
    """
    fps = info.target_fraction
    vf = []
    if normalize:
        vf.append("setpts=PTS-STARTPTS")
        vf.append(f"fps=fps={fps.numerator}/{fps.denominator}:round=near")
    vf.append(f"scale=in_color_matrix={_in_matrix(info)}:in_range=tv:flags=bicubic+accurate_rnd+full_chroma_int")
    vf.append("format=bgr24")
    cmd = [cfg().ffmpeg, "-v", "error", "-nostdin", "-i", info.path, "-map", "0:v:0", "-an",
           "-vf", ",".join(vf), "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=10 ** 7)
    size = info.width * info.height * 3
    try:
        while True:
            buf = proc.stdout.read(size)
            if len(buf) < size:
                break
            yield np.frombuffer(buf, np.uint8).reshape(info.height, info.width, 3).copy()
    finally:
        proc.stdout.close()
        err = proc.stderr.read().decode("utf-8", "replace")
        proc.stderr.close()
        rc = proc.wait()
        if rc not in (0, None) and rc != -15 and err.strip():
            # Generator có thể bị đóng sớm (break); khi đó ffmpeg có thể báo broken pipe, bỏ qua.
            if "Broken pipe" not in err and "Error writing" not in err:
                die(f"ffmpeg đọc frame lỗi: {err.strip()}")


class Encoder:
    """Nhận frame BGR qua stdin, nén H.264 yuv420p BT.709 (D6.6)."""

    def __init__(self, out: Path, width: int, height: int, fps: Fraction, *, crf: int, preset: str,
                 gop: int, audio_src: str | None = None, audio_copy: bool = True,
                 extra_vf: str | None = None, profile: str | None = None) -> None:
        out.parent.mkdir(parents=True, exist_ok=True)
        cmd = [cfg().ffmpeg, "-v", "error", "-y", "-nostdin",
               "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{width}x{height}",
               "-r", f"{fps.numerator}/{fps.denominator}", "-i", "-"]
        if audio_src:
            cmd += ["-i", audio_src]
        cmd += ["-map", "0:v:0"]
        if audio_src:
            cmd += ["-map", "1:a:0", "-c:a", "copy" if audio_copy else "aac"]
            if not audio_copy:
                cmd += ["-b:a", "160k"]
        else:
            cmd += ["-an"]
        vf = []
        if extra_vf:
            vf.append(extra_vf)
        vf.append("scale=out_color_matrix=bt709:out_range=tv:flags=bicubic+accurate_rnd+full_chroma_int")
        vf.append("format=yuv420p")
        cmd += ["-vf", ",".join(vf),
                "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
                "-g", str(gop), "-keyint_min", str(gop), "-sc_threshold", "0",
                "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
                "-movflags", "+faststart"]
        if profile:
            cmd += ["-profile:v", profile]
        cmd += [str(out)]
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        self.count = 0

    def write(self, frame: np.ndarray) -> None:
        self.proc.stdin.write(np.ascontiguousarray(frame).tobytes())
        self.count += 1

    def close(self) -> None:
        self.proc.stdin.close()
        err = self.proc.stderr.read().decode("utf-8", "replace")
        rc = self.proc.wait()
        if rc != 0:
            die(f"ffmpeg nén lỗi: {err.strip()}")


def transcode(src: Path, out: Path, args: list[str]) -> None:
    cmd = [cfg().ffmpeg, "-v", "error", "-y", "-nostdin", "-i", str(src), *args, str(out)]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if res.returncode != 0:
        die(f"ffmpeg lỗi: {res.stderr.strip()}")


def count_frames(path: Path) -> int:
    data = _ffprobe_json(["-count_frames", "-select_streams", "v:0",
                          "-show_entries", "stream=nb_read_frames", str(path)])
    return int(data["streams"][0]["nb_read_frames"])


def first_frame_pts(path: Path) -> float:
    data = _ffprobe_json(["-select_streams", "v:0", "-read_intervals", "%+#1",
                          "-show_entries", "frame=pts_time,best_effort_timestamp_time", str(path)])
    frames = data.get("frames", [])
    if not frames:
        return float("nan")
    t = frames[0].get("pts_time") or frames[0].get("best_effort_timestamp_time")
    return float(t)


def stream_durations(path: Path) -> dict:
    data = _ffprobe_json(["-show_streams", str(path)])
    res = {}
    for s in data.get("streams", []):
        if s.get("duration"):
            res[s["codec_type"]] = float(s["duration"])
    return res


def extract_frame(info_or_path, index: int, width: int, height: int) -> np.ndarray:
    """Lấy đúng frame thứ index (đếm từ 0) của một video đã chuẩn hoá (CFR, frame đầu ở 0)."""
    path = info_or_path.path if isinstance(info_or_path, ProbeInfo) else str(info_or_path)
    cmd = [cfg().ffmpeg, "-v", "error", "-nostdin", "-i", path, "-map", "0:v:0",
           "-vf", f"select=eq(n\\,{index}),scale=in_color_matrix=bt709:in_range=tv:flags=bicubic+accurate_rnd+full_chroma_int,format=bgr24",
           "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    res = subprocess.run(cmd, capture_output=True)
    size = width * height * 3
    if res.returncode != 0 or len(res.stdout) < size:
        die(f"Không lấy được frame {index} của {path}: {res.stderr.decode('utf-8', 'replace').strip()}")
    return np.frombuffer(res.stdout[:size], np.uint8).reshape(height, width, 3).copy()
