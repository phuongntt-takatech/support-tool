"""Menu tương tác: double-click menu.bat, chọn việc bằng số. Không cần nhớ lệnh hay cờ.

Mỗi mục gọi lại đúng các hàm của lệnh tương ứng (inspect / build / review / pick / status).
"""
from __future__ import annotations

import os
from pathlib import Path

from . import registry
from .config import INPUT, ROOT
from .util import list_videos, sha256_file

LINE = "─" * 60


def _ask(prompt: str) -> str:
    try:
        return input(prompt).strip()
    except EOFError:
        return "0"


def _pause() -> None:
    _ask("\nNhấn Enter để quay lại menu…")


def ai_available() -> tuple[bool, str]:
    """AI đặt tên có dùng được trên máy này không (không gọi mạng)."""
    from .gemini import api_key, models
    if api_key():
        return True, f"Gemini: {' → '.join(models())}"
    return False, "chưa có GEMINI_API_KEY"


def _input_videos() -> list[Path]:
    INPUT.mkdir(exist_ok=True)
    return list_videos(INPUT)


def _built_in_input() -> list[tuple[Path, dict]]:
    """Video trong input/ đã có template (khớp theo mã băm)."""
    recs = {r["source"]["sha256"]: r for r in registry.load_all() if r.get("build")}
    out = []
    for v in _input_videos():
        rec = recs.get(sha256_file(v))
        if rec:
            out.append((v, rec))
    return out


def _choose_many(n: int, prompt: str) -> list[int] | None:
    """Nhập '1 3 4', '1-3' hoặc 'a' (tất cả). Trả chỉ số 0-based, None nếu huỷ."""
    raw = _ask(prompt).lower()
    if not raw:
        return None
    if raw in ("a", "all", "tat ca", "tất cả"):
        return list(range(n))
    picked = set()
    for part in raw.replace(",", " ").split():
        if "-" in part:
            a, b = part.split("-", 1)
            if a.isdigit() and b.isdigit():
                picked.update(range(int(a) - 1, int(b)))
        elif part.isdigit():
            picked.add(int(part) - 1)
    return sorted(i for i in picked if 0 <= i < n) or None


# ---- Các mục ----

def do_inspect() -> None:
    from . import inspect_cmd
    if not _input_videos():
        print(f"Thư mục input/ chưa có video. Chép video phông xanh vào:\n  {INPUT}")
        return
    inspect_cmd.run(INPUT)
    print("\nBước tiếp: (tuỳ chọn) mở registry\\inventory.csv điền Giữ / Bỏ, nguồn, giấy phép; rồi chọn mục 2.")


def do_build() -> None:
    from . import build, review
    if not _input_videos():
        print(f"Thư mục input/ chưa có video. Chép video phông xanh vào:\n  {INPUT}")
        return
    ok, why = ai_available()
    print(f"AI đặt tên: {'dùng được' if ok else 'không dùng'} ({why})"
          + ("" if ok else " → lấy tên tạm từ tên file, sửa sau trong sổ ghi"))
    build.run(INPUT, as_new=False, no_ai=not ok, force=False)


def do_review() -> None:
    from . import review
    review.run([], do_mark=False, all_built=False, note="", regen=False, open_browser=True, yes=False)


def do_mark() -> None:
    from . import review
    recs = {r["name"]: r for r in registry.load_all()}
    todo = [n for n in registry.load_order()
            if n in recs and recs[n].get("build") and not recs[n].get("publish") and not registry.review_valid(recs[n])]
    if not todo:
        print("Không có template nào chờ đánh dấu.")
        return
    print("Template chưa soát:")
    for i, n in enumerate(todo, 1):
        w = len(recs[n]["build"].get("warnings", []))
        print(f"  {i:>2}. {n:<42} {w:>2} cảnh báo  {recs[n]['titles'].get('en', '')}")
    idx = _choose_many(len(todo), "Chọn số (vd: 1 3 hoặc 1-4), 'a' = tất cả, Enter = huỷ: ")
    if idx is None:
        print("Huỷ.")
        return
    note = _ask("Ghi chú (có thể bỏ trống): ")
    review.mark([todo[i] for i in idx], False, note)


def do_rebuild() -> None:
    from . import build, review
    items = _built_in_input()
    if not items:
        print("Trong input/ không có video nào đã có template (build lại cần video nguồn nằm trong input/).")
        return
    print("Video đã có template (dùng sau khi sửa overrides trong sổ ghi):")
    for i, (v, rec) in enumerate(items, 1):
        print(f"  {i:>2}. {v.name:<45} → {rec['name']}")
    idx = _choose_many(len(items), "Chọn số video cần build lại, 'a' = tất cả, Enter = huỷ: ")
    if idx is None:
        print("Huỷ.")
        return
    ok, why = ai_available()
    names = []
    for i in idx:
        n = build.build_one(items[i][0], no_ai=not ok, rebuild=True)
        if n:
            names.append(n)
    if names:
        review.generate_index()
        lost = [n for n in names if not registry.review_valid(registry.load(n))]
        print(f"\nĐã build lại {len(names)} template.")
        if lost:
            print(f"{len(lost)} template có file ra thay đổi nên cần soát lại (mục 3, rồi mục 4): {', '.join(lost)}")


def do_pick() -> None:
    from . import pick
    items = _built_in_input()
    if not items:
        print("Trong input/ không có video nào đã có template.")
        return
    for i, (v, rec) in enumerate(items, 1):
        print(f"  {i:>2}. {v.name:<45} → {rec['name']}")
    idx = _choose_many(len(items), "Chọn 1 video, Enter = huỷ: ")
    if not idx:
        return
    v, rec = items[idx[0]]
    frames = _ask("Các frame cần chọn tay (vd: 0 150 299; xem số frame lỗi trong trang soát): ")
    fl = [int(x) for x in frames.replace(",", " ").split() if x.isdigit()]
    if not fl:
        print("Huỷ.")
        return
    pick.run(rec["name"], fl, v)
    if _ask("Build lại ngay với các góc vừa chọn? (y/N): ").lower() == "y":
        from . import build, review
        ok, _ = ai_available()
        if build.build_one(v, no_ai=not ok, rebuild=True):
            review.generate_index()


def do_status() -> None:
    from . import cli
    registry.sync_inventory_status()
    cli.main(["status"])
    n_in = len(_input_videos())
    print(f"\nVideo trong input/: {n_in}")


def do_retitle() -> None:
    from . import retitle
    ok, why = ai_available()
    if not ok:
        print(f"AI chưa dùng được: {why}. Xem mục \"Kết nối AI\" trong README.md.")
        return
    recs = [r for r in registry.load_all() if r.get("build") and not r.get("publish")]
    if not recs:
        print("Chưa có template nào.")
        return
    print("Template (đánh dấu * = đang dùng tên tạm từ tên file):")
    for i, r in enumerate(recs, 1):
        mark = "*" if retitle.needs_title(r) else " "
        print(f"  {i:>2}. {mark} {r['name']:<42} {r.get('titles', {}).get('en', '')}")
    raw = _ask("Chọn số (vd: 1 3), 't' = mọi template có dấu *, 'a' = tất cả, Enter = huỷ: ").lower()
    if raw == "t":
        names = [r["name"] for r in recs if retitle.needs_title(r)]
    elif raw in ("a", "all"):
        names = [r["name"] for r in recs]
    else:
        picked = []
        for part in raw.replace(",", " ").split():
            if part.isdigit() and 1 <= int(part) <= len(recs):
                picked.append(recs[int(part) - 1]["name"])
        names = picked
    if not names:
        print("Huỷ.")
        return
    retitle.run(names)


def do_open_folder() -> None:
    INPUT.mkdir(exist_ok=True)
    os.startfile(str(INPUT))  # noqa: S606 (Windows)


ITEMS = [
    ("1", "Kiểm kê video mới trong input/", do_inspect),
    ("2", "Build video mới trong input/", do_build),
    ("3", "Mở trang soát", do_review),
    ("4", "Đánh dấu đã soát", do_mark),
    ("5", "Build lại video (sau khi sửa sổ ghi)", do_rebuild),
    ("6", "Chọn góc bằng tay (khi dò thất bại)", do_pick),
    ("7", "Trạng thái", do_status),
    ("8", "Mở thư mục input/", do_open_folder),
    ("9", "AI đặt tên + dịch cho template đã build (không build lại)", do_retitle),
]


def main() -> None:
    os.chdir(ROOT)
    while True:
        print(f"\n{LINE}\n  VIDEO TEMPLATE DATA TOOL\n{LINE}")
        print("  Chép video phông xanh vào input/, rồi làm lần lượt 1 → 2 → 3 → 4.\n")
        for key, label, _ in ITEMS:
            print(f"  {key}. {label}")
        print("  0. Thoát")
        choice = _ask("\nChọn: ")
        if choice in ("0", "q", ""):
            if choice == "":
                continue
            return
        action = next((f for k, _, f in ITEMS if k == choice), None)
        if not action:
            print("Không có mục này.")
            continue
        print(LINE)
        try:
            action()
        except SystemExit as e:  # die() trong các lệnh: báo lỗi rồi quay lại menu
            if e.code not in (0, None):
                print("\nĐã dừng vì lỗi ở trên.")
        except KeyboardInterrupt:
            print("\nĐã huỷ.")
        except Exception:  # lỗi bất ngờ: không để cửa sổ tự đóng, ghi log để báo lại
            import traceback
            from datetime import datetime
            from .config import OUT
            tb = traceback.format_exc()
            OUT.mkdir(exist_ok=True)
            log_path = OUT / "menu_error.log"
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"\n===== {datetime.now():%Y-%m-%d %H:%M:%S} — mục {choice} =====\n{tb}")
            print(f"\n!! Lỗi không lường trước:\n{tb}")
            print(f"Đã ghi lỗi vào {log_path}. Gửi file này cho người bảo trì tool.")
        _pause()
