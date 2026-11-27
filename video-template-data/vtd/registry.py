"""Sổ ghi (D1.3): mỗi template một file JSON trong registry/templates/, danh sách thứ tự hiển thị
(registry/order.json, mới lên đầu), và sổ kiểm kê video nguồn (registry/inventory.csv, D2.6)."""
from __future__ import annotations

import csv
import hashlib
from datetime import datetime
from pathlib import Path

from .config import INVENTORY_CSV, ORDER_JSON, TEMPLATES_REG, TEMPLATE_FILES, templates_out
from .util import die, read_json, sha256_file, write_json

DEFAULT_OVERRIDES = {
    "group": None,          # "A" / "B": ép nhóm
    "previewFrame": None,   # chỉ số frame
    "posterRatio": None,    # {"w": 3, "h": 4}
    "expandPx": None,       # độ nới khung (px)
    "despill": None,        # true / false: bật / tắt khử hắt sáng xanh
    "previewCrf": None,     # CRF riêng cho preview.mp4
    "manualQuads": {},      # {"<frame>": {"tl": [x,y], ...}} — toạ độ theo hệ của placeholder.json
}


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def record_path(name: str) -> Path:
    return TEMPLATES_REG / f"{name}.json"


def load(name: str) -> dict | None:
    p = record_path(name)
    return read_json(p) if p.exists() else None


def load_all() -> list[dict]:
    if not TEMPLATES_REG.exists():
        return []
    return [read_json(p) for p in sorted(TEMPLATES_REG.glob("*.json"))]


def save(rec: dict) -> None:
    write_json(record_path(rec["name"]), rec)


def find_by_source(sha: str) -> list[dict]:
    return [r for r in load_all() if r.get("source", {}).get("sha256") == sha]


def new_record(name: str, source_file: str, sha: str, path: str) -> dict:
    return {
        "name": name,
        "createdAt": now_iso(),
        "source": {"file": source_file, "sha256": sha, "lastPath": path},
        "titles": {},
        "titlesSource": None,
        "overrides": dict(DEFAULT_OVERRIDES),
        "build": None,
        "review": None,
        "publish": None,
    }


# ---- thứ tự hiển thị ----

def load_order() -> list[str]:
    return read_json(ORDER_JSON) if ORDER_JSON.exists() else []


def save_order(order: list[str]) -> None:
    write_json(ORDER_JSON, order)


def order_insert_front(name: str) -> None:
    order = [n for n in load_order() if n != name]
    save_order([name] + order)


# ---- mã băm file ra (gắn dấu "đã soát", D7) ----

def outputs_hashes(name: str) -> dict:
    d = templates_out() / name
    return {f: sha256_file(d / f) for f in TEMPLATE_FILES if (d / f).exists()}


def combined_hash(hashes: dict) -> str:
    h = hashlib.sha256()
    for k in sorted(hashes):
        h.update(f"{k}:{hashes[k]}\n".encode())
    return h.hexdigest()


def review_valid(rec: dict) -> bool:
    rv = rec.get("review")
    return bool(rv) and rv.get("outputsHash") == combined_hash(outputs_hashes(rec["name"]))


# ---- sổ kiểm kê ----

INV_COLUMNS = [
    "file", "sha256", "width", "height", "fps", "duration_s", "audio", "rotation",
    "group", "warnings",            # máy điền (inspect)
    "decision", "reason",           # dev điền: Giữ / Bỏ / Để sau
    "source", "source_ref", "license", "license_checked_at", "license_confirmed_by",  # nguồn, giấy phép (L4)
    "status", "name",               # Chưa làm / Đã build / Đã review / Đã publish
]
MACHINE_COLUMNS = {"file", "width", "height", "fps", "duration_s", "audio", "rotation", "group", "warnings"}


def load_inventory() -> list[dict]:
    if not INVENTORY_CSV.exists():
        return []
    with open(INVENTORY_CSV, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _open_for_write(path: Path):
    """Mở file để ghi; nếu đang bị Excel (hoặc chương trình khác) khoá thì chờ người dùng đóng."""
    while True:
        try:
            return open(path, "w", encoding="utf-8-sig", newline="")
        except PermissionError:
            print(f"\n!! Không ghi được {path.name}: file đang mở trong Excel (hoặc chương trình khác).")
            try:
                ans = input("   Đóng file trong Excel rồi nhấn Enter để thử lại (gõ q để dừng): ").strip().lower()
            except EOFError:
                ans = "q"
            if ans == "q":
                die(f"Dừng vì {path.name} đang bị khoá. Đóng Excel rồi chạy lại; tool tự bù phần còn thiếu.")


def save_inventory(rows: list[dict]) -> None:
    INVENTORY_CSV.parent.mkdir(parents=True, exist_ok=True)
    with _open_for_write(INVENTORY_CSV) as f:
        w = csv.DictWriter(f, fieldnames=INV_COLUMNS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in INV_COLUMNS})


def sync_inventory_status() -> None:
    """Đồng bộ cột status / name của sổ kiểm kê theo sổ ghi (bù lại nếu lần trước bị ngắt giữa chừng)."""
    rows = load_inventory()
    if not rows:
        return
    by_sha = {}
    for rec in load_all():
        if rec.get("build"):
            by_sha.setdefault(rec["source"]["sha256"], rec)
    changed = False
    for row in rows:
        rec = by_sha.get(row.get("sha256"))
        if not rec:
            continue
        status = "Đã publish" if rec.get("publish") else ("Đã review" if review_valid(rec) else "Đã build")
        if row.get("status") != status or row.get("name") != rec["name"]:
            row["status"], row["name"] = status, rec["name"]
            changed = True
    if changed:
        save_inventory(rows)


def inventory_row(sha: str) -> dict | None:
    return next((r for r in load_inventory() if r.get("sha256") == sha), None)


def upsert_inventory(sha: str, values: dict, *, machine_only: bool = False) -> None:
    """Cập nhật một dòng theo mã băm; giữ nguyên các cột dev đã điền."""
    rows = load_inventory()
    row = next((r for r in rows if r.get("sha256") == sha), None)
    if row is None:
        row = {k: "" for k in INV_COLUMNS}
        row["sha256"] = sha
        row["status"] = "Chưa làm"
        rows.append(row)
    for k, v in values.items():
        if machine_only and k not in MACHINE_COLUMNS:
            continue
        row[k] = v
    save_inventory(rows)
