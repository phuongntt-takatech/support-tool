"""D9.7: danh sách mã ngôn ngữ của app (khoá của `titles` = mã thư mục values-xx)."""
from __future__ import annotations

import re

from .config import DATA, cfg
from .util import Warn

# Tên ngôn ngữ gửi kèm cho AI (mã Android cũ: in = Indonesia, iw = Hebrew).
LANG_NAMES = {
    "am": "Amharic", "ar": "Arabic", "bg": "Bulgarian", "bn": "Bengali", "ca": "Catalan", "cs": "Czech",
    "da": "Danish", "de": "German", "el": "Greek", "en": "English", "es": "Spanish", "fa": "Persian",
    "fr": "French", "hi": "Hindi", "hr": "Croatian", "hu": "Hungarian", "in": "Indonesian", "it": "Italian",
    "iw": "Hebrew", "ja": "Japanese", "ka": "Georgian", "ko": "Korean", "lt": "Lithuanian",
    "mn": "Mongolian (Cyrillic)", "mr": "Marathi", "ms": "Malay", "nl": "Dutch", "no": "Norwegian Bokmål",
    "pl": "Polish", "pt": "Portuguese (European)", "ro": "Romanian", "ru": "Russian", "sk": "Slovak",
    "sl": "Slovenian", "sr": "Serbian (Cyrillic script)", "sv": "Swedish", "sw": "Swahili", "ta": "Tamil",
    "te": "Telugu", "th": "Thai", "tr": "Turkish", "uk": "Ukrainian", "vi": "Vietnamese",
    "zh": "Chinese (Simplified)",
}


def _copy_codes() -> list[str]:
    return [l.strip() for l in (DATA / "locales.txt").read_text(encoding="utf-8").splitlines() if l.strip()]


def load_codes() -> tuple[list[str], list[Warn]]:
    warns: list[Warn] = []
    copy = _copy_codes()
    repo = cfg().app_repo
    xml = repo / "app/src/main/res/xml/locales_config.xml" if repo else None
    if xml and xml.exists():
        codes = re.findall(r'android:name="([^"]+)"', xml.read_text(encoding="utf-8"))
        if sorted(codes) != sorted(copy):
            extra = sorted(set(codes) - set(copy))
            missing = sorted(set(copy) - set(codes))
            warns.append(Warn("locales_diff",
                              f"Danh sách ngôn ngữ của repo app khác bản sao (app thêm {extra}, app bỏ {missing}); "
                              f"cập nhật data/locales.txt"))
    else:
        codes = copy
        warns.append(Warn("locales_copy", "Không tìm thấy repo app (config.local.json → appRepo), đang dùng bản sao data/locales.txt"))
    return codes, warns
