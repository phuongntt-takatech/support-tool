"""Điểm vào dòng lệnh: python vtd.py <lệnh> ..."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import INPUT


def main(argv: list[str] | None = None) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(prog="vtd", description="Công cụ tạo data Video Template (PosterMaker)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("inspect", help="Kiểm tra môi trường + đọc thông số, phân loại video, ghi sổ kiểm kê")
    sp.add_argument("path", type=Path, nargs="?", default=INPUT,
                    help="một video hoặc thư mục video (mặc định: thư mục input/)")
    sp.add_argument("--recheck", action="store_true", help="kiểm tra lại cả video đã có trong sổ kiểm kê")

    sp = sub.add_parser("build", help="Dò góc, ghép poster mẫu, nén, thumb/preview, placeholder.json, đặt tên")
    sp.add_argument("path", type=Path, nargs="?", default=INPUT,
                    help="một video hoặc thư mục video (mặc định: thư mục input/)")
    sp.add_argument("--rebuild", action="store_true",
                    help="build lại cả video đã có template (ví dụ sau khi sửa overrides)")
    sp.add_argument("--as-new", action="store_true", help="tạo template mới dù video này đã có template")
    sp.add_argument("--no-ai", action="store_true", help="không gọi AI đặt tên (dùng tên từ tên file)")
    sp.add_argument("--force", action="store_true", help="build cả video sổ kiểm kê ghi 'Bỏ'")

    sp = sub.add_parser("review", help="Mở trang soát; --mark để đánh dấu đã soát")
    sp.add_argument("names", nargs="*", help="name của template (bỏ trống = tất cả)")
    sp.add_argument("--mark", action="store_true", help="đánh dấu đã soát các template chỉ định")
    sp.add_argument("--all", action="store_true", help="cùng --mark: mọi template đã build chưa soát")
    sp.add_argument("--note", default="", help="ghi chú khi đánh dấu")
    sp.add_argument("--yes", action="store_true", help="không hỏi xác nhận (cẩn thận)")
    sp.add_argument("--regen", action="store_true", help="tạo lại file soát")
    sp.add_argument("--no-open", action="store_true", help="không mở trình duyệt")

    sp = sub.add_parser("pick", help="Chọn tay 4 góc ở vài frame mốc (khi dò thất bại)")
    sp.add_argument("name")
    sp.add_argument("--frames", required=True, help="danh sách frame, ví dụ 0,120,299")
    sp.add_argument("--video", type=Path, help="đường dẫn video nguồn nếu đã chuyển chỗ")

    sp = sub.add_parser("retitle", help="AI đặt tên + dịch cho template đã build (không build lại, giữ name)")
    sp.add_argument("names", nargs="*", help="name template (bỏ trống = mọi template đang dùng tên tạm)")
    sp.add_argument("--redo", action="store_true", help="cùng names trống: đặt lại cả template đã có tên AI")

    sub.add_parser("status", help="Liệt kê template và trạng thái")
    sub.add_parser("menu", help="Menu chọn bằng số (mặc định khi không truyền lệnh)")

    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        argv = ["menu"]
    a = p.parse_args(argv)
    if a.cmd == "menu":
        from . import menu
        menu.main()
    elif a.cmd == "inspect":
        from . import inspect_cmd
        inspect_cmd.run(a.path, recheck=a.recheck)
    elif a.cmd == "build":
        from . import build
        build.run(a.path, as_new=a.as_new, no_ai=a.no_ai, force=a.force, rebuild=a.rebuild)
    elif a.cmd == "review":
        from . import review
        review.run(a.names, do_mark=a.mark, all_built=a.all, note=a.note, regen=a.regen,
                   open_browser=not a.no_open, yes=a.yes)
    elif a.cmd == "retitle":
        from . import retitle
        retitle.run(a.names, redo=a.redo)
    elif a.cmd == "pick":
        from . import pick
        frames = [int(x) for x in a.frames.split(",") if x.strip()]
        pick.run(a.name, frames, a.video)
    elif a.cmd == "status":
        from . import registry, review
        order = registry.load_order()
        recs = {r["name"]: r for r in registry.load_all()}
        names = order + sorted(n for n in recs if n not in order)
        if not names:
            print("Chưa có template nào.")
        for n in names:
            r = recs.get(n)
            if r:
                w = len((r.get("build") or {}).get("warnings", []))
                print(f"{n:<45} {review._status(r):<28} {w:>3} cảnh báo  {r['titles'].get('en', '')}")


if __name__ == "__main__":
    main()
