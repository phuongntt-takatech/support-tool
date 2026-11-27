"""Đọc cấu hình: config.json (trong git) + config.local.json (máy riêng, không vào git)."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
INPUT = ROOT / "input"   # chỗ bỏ video nguồn (không vào git)
REGISTRY = ROOT / "registry"
TEMPLATES_REG = REGISTRY / "templates"
INVENTORY_CSV = REGISTRY / "inventory.csv"
ORDER_JSON = REGISTRY / "order.json"
DATA = ROOT / "data"

# 4 file cố định trong mỗi thư mục template (D8 của plan app).
TEMPLATE_FILES = ("video.mp4", "placeholder.json", "thumb.webp", "preview.mp4")


class Config:
    def __init__(self) -> None:
        self.data = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
        local_path = ROOT / "config.local.json"
        self.local = json.loads(local_path.read_text(encoding="utf-8")) if local_path.exists() else {}

    def __getitem__(self, key: str):
        return self.data[key]

    @property
    def ffmpeg(self) -> str:
        return self.local.get("ffmpeg") or "ffmpeg"

    @property
    def ffprobe(self) -> str:
        return self.local.get("ffprobe") or "ffprobe"

    @property
    def app_repo(self) -> Path | None:
        p = self.local.get("appRepo")
        return Path(p) if p else None


_cfg: Config | None = None


def cfg() -> Config:
    global _cfg
    if _cfg is None:
        _cfg = Config()
    return _cfg


def templates_out() -> Path:
    return OUT / "templates"


def review_out() -> Path:
    return OUT / "review"
