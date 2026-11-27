"""Tiện ích chung: băm file, ghi JSON ổn định, in log, gom cảnh báo."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".mkv", ".webm"}


def log(msg: str) -> None:
    print(msg, flush=True)


def die(msg: str, code: int = 1) -> None:
    print(f"LỖI: {msg}", file=sys.stderr, flush=True)
    raise SystemExit(code)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, data, *, indent: int = 2) -> None:
    """UTF-8, không \\u...., giữ thứ tự khoá như dữ liệu đưa vào, xuống dòng cuối file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, indent=indent) + "\n"
    path.write_bytes(text.encode("utf-8"))


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def list_videos(target: Path) -> list[Path]:
    if target.is_dir():
        return sorted(p for p in target.iterdir() if p.is_file() and p.suffix.lower() in VIDEO_EXTS)
    if target.is_file():
        return [target]
    die(f"Không tìm thấy: {target}")
    return []


def slugify(text: str) -> str:
    s = text.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return re.sub(r"_+", "_", s).strip("_")


@dataclass
class Warn:
    code: str
    message: str
    frames: list[int] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = {"code": self.code, "message": self.message}
        if self.frames:
            d["frames"] = self.frames[:50]
        return d


def fmt_fps(num: int, den: int) -> str:
    return f"{num}/{den}"
