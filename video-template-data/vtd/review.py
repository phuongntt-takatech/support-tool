"""D7: kiểm chứng bằng mắt.

Mỗi template: video giả lập app (poster bàn cờ + bleedPx 2, đúng phép toán shader), video viền quad,
ảnh tổng hợp ~12 frame (mỗi frame hai bản), ảnh phóng to 4 góc ×4, đồ thị toạ độ góc, báo cáo tổng
(trang HTML). Có trang mục lục (template có cảnh báo lên đầu). Đánh dấu "đã soát" gắn mã băm file ra.
"""
from __future__ import annotations

import html
import json
import webbrowser
from pathlib import Path

import cv2
import numpy as np

from . import placeholder, registry
from .compose import composite, draw_outline
from .config import cfg, review_out, templates_out
from .geometry import expand_quad
from .media import Encoder, iter_frames, probe
from .posters import checkerboard
from .util import Warn, die, log, read_json, write_json

ZOOM_HALF = 12
ZOOM_SCALE = 4


def _leak(frame: np.ndarray, quad: np.ndarray, thr: int) -> float:
    """Tỷ lệ điểm còn ám xanh ở dải 1–3 px ngay ngoài mép poster bàn cờ."""
    H, W = frame.shape[:2]
    x0, y0 = np.maximum(np.floor(quad.min(axis=0)).astype(int) - 6, 0)
    x1, y1 = np.minimum(np.ceil(quad.max(axis=0)).astype(int) + 7, [W, H])
    roi = frame[y0:y1, x0:x1].astype(np.int16)
    inside = np.zeros(roi.shape[:2], np.uint8)
    cv2.fillConvexPoly(inside, np.round((quad - [x0, y0]) * 16).astype(np.int32), 1, shift=4)
    dist = cv2.distanceTransform((1 - inside).astype(np.uint8), cv2.DIST_L2, 5)
    band = (dist >= 1) & (dist <= 3)
    if not band.any():
        return 0.0
    excess = roi[..., 1] - np.maximum(roi[..., 0], roi[..., 2])
    return float(np.mean(excess[band] > thr))


def _zoom(frame: np.ndarray, quad: np.ndarray) -> np.ndarray:
    tiles = []
    H, W = frame.shape[:2]
    for p in quad:
        cx, cy = int(round(p[0])), int(round(p[1]))
        pad = cv2.copyMakeBorder(frame, ZOOM_HALF, ZOOM_HALF + 1, ZOOM_HALF, ZOOM_HALF + 1, cv2.BORDER_CONSTANT, value=(40, 40, 40))
        crop = pad[cy:cy + 2 * ZOOM_HALF + 1, cx:cx + 2 * ZOOM_HALF + 1]
        if crop.shape[0] != 2 * ZOOM_HALF + 1 or crop.shape[1] != 2 * ZOOM_HALF + 1:
            crop = np.zeros((2 * ZOOM_HALF + 1, 2 * ZOOM_HALF + 1, 3), np.uint8)
        big = cv2.resize(crop, None, fx=ZOOM_SCALE, fy=ZOOM_SCALE, interpolation=cv2.INTER_NEAREST)
        tiles.append(cv2.copyMakeBorder(big, 2, 2, 2, 2, cv2.BORDER_CONSTANT, value=(255, 255, 255)))
    return np.hstack(tiles)


def _svg_plot(series: np.ndarray, axis: int, title: str) -> str:
    """Toạ độ 4 góc theo thời gian (lệch so với trung bình của chính góc đó)."""
    n = series.shape[0]
    w, h, padl, padb = 720, 220, 50, 24
    vals = series[:, :, axis] - series[:, :, axis].mean(axis=0, keepdims=True)
    lim = max(1.0, float(np.abs(vals).max()) * 1.1)
    colors = ["#e53935", "#fdd835", "#1e88e5", "#43a047"]
    names = ["tl", "tr", "br", "bl"]

    def X(i):
        return padl + (w - padl - 10) * (i / max(n - 1, 1))

    def Y(v):
        return 10 + (h - padb - 10) * (1 - (v + lim) / (2 * lim))
    parts = [f'<svg viewBox="0 0 {w} {h}" class="plot" role="img" aria-label="{html.escape(title)}">',
             f'<text x="{padl}" y="12" class="pt">{html.escape(title)} (px, lệch so với trung bình)</text>',
             f'<line x1="{padl}" y1="{Y(0):.1f}" x2="{w - 10}" y2="{Y(0):.1f}" class="axis"/>',
             f'<text x="4" y="{Y(lim) + 4:.1f}" class="pt">+{lim:.1f}</text>',
             f'<text x="4" y="{Y(-lim):.1f}" class="pt">-{lim:.1f}</text>',
             f'<text x="{w - 60}" y="{h - 4}" class="pt">frame {n - 1}</text>']
    step = max(1, n // 600)
    for c in range(4):
        pts = " ".join(f"{X(i):.1f},{Y(vals[i, c]):.2f}" for i in range(0, n, step))
        parts.append(f'<polyline fill="none" stroke="{colors[c]}" stroke-width="1.2" points="{pts}"/>')
        parts.append(f'<text x="{padl + 10 + c * 40}" y="{h - 4}" fill="{colors[c]}" class="pt">{names[c]}</text>')
    parts.append("</svg>")
    return "".join(parts)


def generate(name: str) -> dict:
    """Tạo bộ file soát cho một template. Trả tóm tắt (số cảnh báo...)."""
    rec = registry.load(name)
    if not rec:
        die(f"Không có template '{name}' trong sổ ghi")
    tdir = templates_out() / name
    vpath = tdir / "video.mp4"
    if not vpath.exists():
        die(f"Chưa build: thiếu {vpath}")
    c = cfg()
    rc = c["review"]
    log(f"  Tạo file soát cho {name}…")
    data = placeholder.load(tdir / "placeholder.json")
    quads = placeholder.quads_cv(data)
    bleed = float(data["bleedPx"])
    info = probe(vpath, with_hash=False)
    n = rec["build"]["frames"]
    rdir = review_out() / name
    rdir.mkdir(parents=True, exist_ok=True)

    pr = data["posterRatio"]
    ratio = float(pr["w"]) / float(pr["h"])
    L = 600
    cw, ch = (L, round(L / ratio)) if ratio >= 1 else (round(L * ratio), L)
    board = checkerboard(cw, ch)

    def q_at(i):
        return quads[0] if len(quads) == 1 else quads[min(i, len(quads) - 1)]

    # Frame đáng soát: rải đều cho ảnh tổng hợp; đầu/giữa/cuối/chuyển động nhanh nhất cho ảnh phóng to.
    sheet_idx = sorted({int(round(i * (n - 1) / max(rc["sheetFrames"] - 1, 1))) for i in range(rc["sheetFrames"])})
    warns: list[Warn] = []
    if len(quads) > 1:
        speed = np.linalg.norm(np.diff(quads, axis=0), axis=2).max(axis=1)
        fastest = int(np.argmax(speed)) + 1
        second = quads[2:] - 2 * quads[1:-1] + quads[:-2]
        jit = np.linalg.norm(second, axis=2).max(axis=1) / 2
        jitter_frames = [int(i) + 1 for i in np.nonzero(jit > rc["jitterPx"])[0]]
        if jitter_frames:
            warns.append(Warn("jitter", f"Rung > {rc['jitterPx']} px ở {len(jitter_frames)} frame", jitter_frames))
        med_speed = float(np.median(speed)) if len(speed) else 0
        jump_thr = max(c["temporal"]["jumpPx"], 4 * med_speed)
        jump_frames = [int(i) + 1 for i in np.nonzero(speed > jump_thr)[0]]
        if jump_frames:
            warns.append(Warn("jump", f"Góc dịch đột ngột ở {len(jump_frames)} frame", jump_frames))
        extra_zoom = jump_frames[:1] + jitter_frames[:1]
    else:
        fastest = n // 2
        extra_zoom = []
    zoom_idx = sorted(set([0, n // 2, n - 1, fastest] + extra_zoom))
    if rec["build"]["expandPx"] >= rc["nearCapPx"]:
        warns.append(Warn("expand_near_cap", f"Độ nới {rec['build']['expandPx']} px gần trần: kiểm tra có đè viền thật của biển / màn hình không"))

    sim_enc = Encoder(rdir / "sim.mp4", info.width, info.height, info.target_fraction, crf=23, preset="veryfast",
                      gop=max(1, round(float(info.target_fraction))))
    out_enc = Encoder(rdir / "outline.mp4", info.width, info.height, info.target_fraction, crf=23, preset="veryfast",
                      gop=max(1, round(float(info.target_fraction))))
    sheet_tiles, zoom_imgs, leak_frames, leak_zoom = [], {}, [], {}
    i = 0
    try:
        for f in iter_frames(info):
            q = q_at(i)
            q_sim = expand_quad(q, bleed)
            sim = composite(f.copy(), board, q_sim)
            outl = draw_outline(f.copy(), q, f"#{i}")
            lk = _leak(sim, q_sim, rc["leakExcessThr"])
            if lk > rc["leakFrac"]:
                leak_frames.append(i)
                if len(leak_zoom) < 4:
                    leak_zoom[i] = np.vstack([_zoom(sim, q_sim), _zoom(outl, q)])
            sim_enc.write(sim)
            out_enc.write(outl)
            if i in sheet_idx:
                pair = np.hstack([sim, outl])
                s = 640 / pair.shape[1]
                sheet_tiles.append((i, cv2.resize(pair, (640, round(pair.shape[0] * s)), interpolation=cv2.INTER_AREA)))
            if i in zoom_idx:
                zoom_imgs[i] = np.vstack([_zoom(sim, q_sim), _zoom(outl, q)])
            i += 1
    finally:
        sim_enc.close()
        out_enc.close()
    if leak_frames:
        warns.append(Warn("green_leak", f"Sót xanh quanh poster ở {len(leak_frames)} frame", leak_frames))

    # Ảnh tổng hợp: 3 cột (mỗi ô = giả lập | viền quad)
    tiles = [t for _, t in sheet_tiles]
    while len(tiles) % 3:
        tiles.append(np.zeros_like(tiles[0]))
    sheet = np.vstack([np.hstack(tiles[k:k + 3]) for k in range(0, len(tiles), 3)])
    cv2.imwrite(str(rdir / "sheet.jpg"), sheet, [cv2.IMWRITE_JPEG_QUALITY, 85])
    zoom_files = []
    for fi, img in sorted(zoom_imgs.items()):
        fn = f"zoom_{fi:05d}.png"
        cv2.imwrite(str(rdir / fn), img)
        zoom_files.append((fi, fn, "góc"))
    for fi, img in sorted(leak_zoom.items()):
        fn = f"leak_{fi:05d}.png"
        cv2.imwrite(str(rdir / fn), img)
        zoom_files.append((fi, fn, "sót xanh"))

    all_q = np.repeat(quads, n, axis=0) if len(quads) == 1 else quads
    plots = _svg_plot(all_q, 0, "Toạ độ x") + _svg_plot(all_q, 1, "Toạ độ y")
    build_warns = rec["build"].get("warnings", [])
    review_warns = [w.to_dict() for w in warns]
    summary = {"name": name, "warnings": len(build_warns) + len(review_warns), "reviewWarnings": review_warns}
    write_json(rdir / "summary.json", summary)
    _write_page(rec, data, rdir, sheet_idx, zoom_files, plots, build_warns, review_warns)
    return summary


def _status(rec: dict) -> str:
    if rec.get("publish"):
        return "Đã publish"
    if registry.review_valid(rec):
        return "Đã soát"
    if rec.get("review"):
        return "Dấu soát cũ (đã build lại)"
    return "Chưa soát"


CSS = """
:root{--bg:#fafafa;--fg:#1f2328;--muted:#656d76;--card:#fff;--line:#d0d7de;--warn:#b35900;--warnbg:#fff4e5;--ok:#1a7f37}
@media (prefers-color-scheme:dark){:root{--bg:#0d1117;--fg:#e6edf3;--muted:#8d96a0;--card:#161b22;--line:#30363d;--warn:#f0a35e;--warnbg:#2d1f0f;--ok:#3fb950}}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.5 system-ui,Segoe UI,sans-serif}
main{max-width:1200px;margin:0 auto;padding:16px}
h1{font-size:22px;margin:8px 0}h2{font-size:17px;margin:24px 0 8px;border-bottom:1px solid var(--line);padding-bottom:4px}
.muted{color:var(--muted)}table{border-collapse:collapse;width:100%;background:var(--card)}
td,th{border:1px solid var(--line);padding:4px 8px;text-align:left;vertical-align:top}
.warn{background:var(--warnbg);color:var(--warn);padding:6px 10px;border-radius:6px;margin:4px 0}
.ok{color:var(--ok)}img,video{max-width:100%;border:1px solid var(--line);border-radius:4px;background:#000}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:8px}
.card a{color:inherit;text-decoration:none}.plot{width:100%;background:var(--card);border:1px solid var(--line)}
.plot .pt{font-size:11px;fill:var(--muted)}.plot .axis{stroke:var(--line)}
.two{display:grid;grid-template-columns:1fr 1fr;gap:12px}@media(max-width:700px){.two{grid-template-columns:1fr}}
code{font-size:12px}
"""


def _write_page(rec, data, rdir: Path, sheet_idx, zoom_files, plots, build_warns, review_warns) -> None:
    name = rec["name"]
    b = rec["build"]
    e = html.escape
    rows = [
        ("Video nguồn", f"{e(rec['source']['file'])} <span class=muted>({rec['source']['sha256'][:12]})</span>"),
        ("Kích thước / fps / số frame", f"{b['size'][0]}×{b['size'][1]}, {b['fps']} fps, {b['frames']} frame"),
        ("Nhóm", "A (đứng yên, 1 quad)" if b["group"] == "A" else "B (chuyển động, mỗi frame một quad)"),
        ("posterRatio", f"{data['posterRatio']['w']}:{data['posterRatio']['h']} (đo được {b['posterRatioMeasured']})"),
        ("previewFrame", str(data["previewFrame"])),
        ("Nới khung", f"{b['expandPx']} px (viền nhoè đo {b['blurPx'][0]}–{b['blurPx'][1]} px); khử hắt sáng: {'bật' if b['despill'] else 'tắt'}"),
        ("Frame đã nội suy", ", ".join(map(str, b["interpolatedFrames"][:60])) or "không có"),
        ("Trạng thái", e(_status(rec))),
    ]
    warn_html = "".join(
        f"<div class=warn>[{e(w['code'])}] {e(w['message'])}"
        + (f" <span class=muted>frame: {', '.join(map(str, w.get('frames', [])[:30]))}</span>" if w.get("frames") else "")
        + "</div>" for w in build_warns + review_warns) or "<p class=ok>Không có cảnh báo.</p>"
    titles = rec.get("titles", {})
    title_rows = "".join(f"<tr><td><code>{e(k)}</code></td><td>{e(v)}</td></tr>" for k, v in titles.items())
    zoom_html = "".join(
        f"<figure><img src='{fn}' alt='Phóng to frame {fi}'><figcaption class=muted>Frame {fi} ({kind}): "
        f"hàng trên giả lập app, hàng dưới viền quad; tl, tr, br, bl, ×{ZOOM_SCALE}</figcaption></figure>"
        for fi, fn, kind in zoom_files)
    page = f"""<!doctype html><html lang=vi><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Soát {e(name)}</title><style>{CSS}</style></head><body><main>
<p><a href="../index.html">← Mục lục</a></p>
<h1>{e(titles.get('en', name))}</h1><p class=muted><code>{e(name)}</code> · tên do {e(str(rec.get('titlesSource')))} đặt · build {e(b['at'])}</p>
<h2>Cảnh báo</h2>{warn_html}
<h2>Video</h2><div class=two>
<figure><video src="sim.mp4" controls loop muted playsinline></video><figcaption class=muted>Giả lập app: poster bàn cờ, nới thêm bleedPx {data['bleedPx']}. Soát lộ viền, rung, trôi, méo hình tròn.</figcaption></figure>
<figure><video src="outline.mp4" controls loop muted playsinline></video><figcaption class=muted>Viền quad (đã nới) + số frame. Soát quad bám mép khung.</figcaption></figure></div>
<p class=muted>Tua từng frame: mở file bằng VLC (phím E) hoặc mpv (phím .).</p>
<h2>Ảnh tổng hợp</h2><img src="sheet.jpg" alt="Ảnh tổng hợp các frame {', '.join(map(str, sheet_idx))}"><p class=muted>Frame: {', '.join(map(str, sheet_idx))}</p>
<h2>Phóng to 4 góc</h2>{zoom_html}
<h2>Đồ thị toạ độ góc</h2><p class=muted>Đường mượt là tốt; răng cưa là rung; gãy là dò sai.</p>{plots}
<h2>Thông số</h2><table>{''.join(f'<tr><th>{k}</th><td>{v}</td></tr>' for k, v in rows)}</table>
<h2>Thumbnail</h2><img src="../../templates/{e(name)}/thumb.webp" alt="Thumbnail">
<h2>Tên ({len(titles)} ngôn ngữ)</h2><table>{title_rows}</table>
<p class=muted>Sửa tên / bản dịch / ghi đè thông số trong <code>registry/templates/{e(name)}.json</code>.</p>
</main></body></html>"""
    (rdir / "index.html").write_text(page, encoding="utf-8")


def generate_index() -> Path:
    order = registry.load_order()
    recs = {r["name"]: r for r in registry.load_all()}
    items = []
    for pos, name in enumerate(order):
        rec = recs.get(name)
        if not rec or not rec.get("build"):
            continue
        sp = review_out() / name / "summary.json"
        count = read_json(sp)["warnings"] if sp.exists() else len(rec["build"].get("warnings", []))
        items.append((count, pos, name, rec))
    items.sort(key=lambda t: (-t[0], t[1]))  # có cảnh báo lên đầu
    e = html.escape
    cards = "".join(
        f"<div class=card><a href='{e(name)}/index.html'><img src='../templates/{e(name)}/thumb.webp' alt=''>"
        f"<strong>{e(rec['titles'].get('en', name))}</strong><br><code>{e(name)}</code><br>"
        f"<span class='{'warn' if cnt else 'ok'}'>{cnt} cảnh báo</span> · {e(_status(rec))}</a></div>"
        for cnt, _, name, rec in items)
    page = f"""<!doctype html><html lang=vi><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Soát Video Template</title><style>{CSS}</style></head><body><main><h1>Soát Video Template</h1>
<p class=muted>{len(items)} template; có cảnh báo xếp trước. Đánh dấu đã soát: <code>python vtd.py review --mark NAME…</code> hoặc <code>--all</code>.</p>
<div class=grid>{cards}</div></main></body></html>"""
    p = review_out() / "index.html"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(page, encoding="utf-8")
    return p


def mark(names: list[str], all_built: bool, note: str, yes: bool = False) -> None:
    """D7.6: đánh dấu đã soát (hàng loạt được), xác nhận một lần, gắn mã băm file ra."""
    recs = {r["name"]: r for r in registry.load_all()}
    if all_built:
        names = [n for n in registry.load_order() if n in recs and recs[n].get("build") and not recs[n].get("publish")
                 and not registry.review_valid(recs[n])]
    if not names:
        log("Không có template nào cần đánh dấu.")
        return
    rows = []
    for n in names:
        rec = recs.get(n)
        if not rec or not rec.get("build"):
            die(f"'{n}' chưa build")
        sp = review_out() / n / "summary.json"
        if not sp.exists():
            die(f"'{n}' chưa có file soát (chạy: python vtd.py review --regen {n})")
        rows.append((n, read_json(sp)["warnings"], rec))
    log("Sẽ đánh dấu ĐÃ SOÁT:")
    for n, cnt, rec in rows:
        log(f"  {n:<45} {cnt:>3} cảnh báo   {rec['titles'].get('en', '')}")
    if not yes:
        ans = input("Xác nhận đã xem kỹ các template trên? (gõ y): ").strip().lower()
        if ans != "y":
            log("Huỷ.")
            return
    for n, cnt, rec in rows:
        rec["review"] = {"at": registry.now_iso(), "note": note, "warningCount": cnt,
                         "outputsHash": registry.combined_hash(registry.outputs_hashes(n))}
        registry.save(rec)
        registry.upsert_inventory(rec["source"]["sha256"], {"status": "Đã review"})
    generate_index()
    log(f"Đã đánh dấu {len(rows)} template.")


def run(names: list[str], *, do_mark: bool, all_built: bool, note: str, regen: bool, open_browser: bool,
        yes: bool) -> None:
    if do_mark:
        mark(names, all_built, note, yes)
        return
    built = [r["name"] for r in registry.load_all() if r.get("build")]
    if regen:
        targets = names or built
    else:
        # Bù trang soát còn thiếu (ví dụ lần build trước bị ngắt giữa chừng)
        targets = [n for n in (names or built) if not (review_out() / n / "summary.json").exists()]
    for n in targets:
        generate(n)
    idx = generate_index()
    target = idx if not names else review_out() / names[0] / "index.html"
    log(f"Trang soát: {target}")
    if open_browser:
        webbrowser.open(target.resolve().as_uri())
