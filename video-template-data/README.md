# Video Template data tool

Công cụ tạo và cập nhật data cho tính năng **Video Template** của PosterMaker. 

Đầu vào chỉ là **video phông xanh** designer tìm được. Đầu ra là thư mục template đúng định dạng app đọc:

```text
out/templates/<name>/
  video.mp4          video đã chuẩn hoá, ĐÃ GHÉP poster mẫu "YOUR POSTER HERE" vào khung (PA1)
  placeholder.json   4 góc theo từng frame (chính là 4 góc đã dùng để ghép), fps, previewFrame, bleedPx, posterRatio
  thumb.webp         frame previewFrame cắt từ video.mp4, rộng 540
  preview.mp4        bản 360p, không tiếng, cho màn danh sách
```

> Đợt hiện tại có `inspect`, `build`, `review`, `pick`, `retitle`, `status` và `menu.bat`. Lệnh **`publish`** (dựng catalog, upload Firebase, tăng `video_template_catalog_version`, xuất pack) **chưa làm**: chờ team xác nhận quyền ghi Firebase và đường dẫn / khoá. Xem mục [Việc còn mở](#việc-còn-mở).

## Bối cảnh

**Tính năng:** *[Android/iOS] Feature Video Template*. App có sẵn các video template, mỗi template có một khung (placeholder) đặt poster. User chọn template, chọn ảnh poster (Gallery / My Poster), kéo / zoom poster trong khung, chọn nền Blur / Color, app render ra video hoàn chỉnh. Entry point ở màn Magic Studio và Saved; màn danh sách dạng waterfall 2 cột, có nút Play / Pause và chip thời lượng; video mẫu dài khoảng 8–12 giây.

| Tài liệu | Ở đâu | Dùng để |
|---|---|---|
| Spec tính năng (user flow, wireframe, kịch bản SC-01…SC-13) | ClickUp: [Feature Video Template](https://app.clickup.com/9008108912/v/dc/8cetnbg-43396/8cetnbg-19416) | Yêu cầu của PO: màn List, Choose Poster, Adjust Placeholder, Loading, Result |
| Proposal liên quan | ClickUp: [proposal](https://app.clickup.com/9008108912/docs/8cetnbg-42836/8cetnbg-19076) (private) | Đề xuất ban đầu |
| Design | Figma: [Poster Maker - 2025](https://www.figma.com/design/Qffp55M8Wb9C02GHcoTQlT/Poster-Maker---2025?node-id=9230-18762) | Màn Home / Magic Studio (cập nhật 20/11/2026) |
| Plan phía app (K1–K16, định dạng data) | Repo PosterMaker: `VIDEO_TEMPLATE_PLAN.md` (mục 8.4 `placeholder.json`, 8.19 catalog) | **Hợp đồng** giữa app và tool: đổi định dạng bên nào cũng phải đối chiếu |
| Plan phía data (D1–D11) | [VIDEO_TEMPLATE_DATA_PLAN.md](VIDEO_TEMPLATE_DATA_PLAN.md) trong thư mục này | Mọi quyết định của tool; các chỗ sửa sau khi duyệt đều ghi "sửa 27/11/2026" |
| Video nguồn | Synology Drive, thư mục "30 NEW 10.2026" (designer tìm, khoảng 20+ mp4 phông xanh) | Chép vào `input/` để chạy |

**Cách làm đã chốt (PA1, plan app):** `video.mp4` đã có sẵn poster mẫu; app chỉ **đè** poster của user lên đúng 4 góc ghi trong `placeholder.json` (nới thêm `bleedPx`), không tách màu xanh trên máy user. Màu xanh chỉ là công cụ đo của tool: dùng để dò 4 góc ở mọi frame, rồi bị phủ kín bởi poster mẫu.

## Cài đặt (một lần)

1. **Python 3.11+** (máy dev hiện dùng 3.11.6).
2. **ffmpeg + ffprobe** trong PATH. Ví dụ:

   ```powershell
   winget install Gyan.FFmpeg
   ```

   Mở terminal mới rồi kiểm tra `ffmpeg -version`. Terminal chưa nhận PATH (hoặc không muốn thêm PATH) thì ghi đường dẫn đầy đủ của `ffmpeg.exe` / `ffprobe.exe` vào `config.local.json`; winget cài ở `%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg_...\ffmpeg-<phiên bản>-full_build\bin\`.
3. Môi trường ảo + thư viện (đã ghim phiên bản trong `requirements.txt`):

   ```powershell
   cd "C:\Projects\Support Tool\video-template-data"
   python -m venv .venv
   .venv\Scripts\python -m pip install -r requirements.txt
   ```

4. Cấu hình máy riêng: chép `config.local.example.json` thành `config.local.json`, sửa `appRepo` trỏ tới repo PosterMaker (để đọc danh sách ngôn ngữ từ `locales_config.xml`). File này không vào git.
5. Kết nối AI để đặt tên + dịch (xem mục **Kết nối AI** ngay dưới). Không kết nối thì `build` vẫn chạy, dùng tên tạm từ tên file và cảnh báo.

### Kết nối AI

AI **Gemini** (Google AI Studio, dùng được key tài khoản **free**) đặt tên hiển thị tiếng Anh theo quy định và dịch sang các ngôn ngữ của app. Tool gọi Gemini qua REST bằng thư viện chuẩn của Python, không cần cài thêm gì.

1. Lấy key free tại [Google AI Studio](https://aistudio.google.com/apikey) (hoặc xin team; dùng chung key với tool `populate-templates-meta` được). **Không** ghi key vào repo, file cấu hình hay README.
2. Lưu key vào biến môi trường của tài khoản Windows (chỉ làm một lần). Mở PowerShell, chạy (thay `<KEY>` bằng key thật):

   ```powershell
   [Environment]::SetEnvironmentVariable("GEMINI_API_KEY", "<KEY>", "User")
   ```

   Đóng hết cửa sổ terminal / menu đang mở rồi mở lại để nhận key.
3. Kiểm tra: mở `menu.bat`, chọn **1**; dòng "AI (Gemini)" phải báo có key.
4. Từ đây mục **2** (build) tự gọi AI. Template đã build lúc chưa có AI (tên tạm) thì chọn mục **9**, gõ `t`: AI đặt tên cho mọi template đang dùng tên tạm; không build lại video, `name` giữ nguyên.

Gỡ key: `[Environment]::SetEnvironmentVariable("GEMINI_API_KEY", $null, "User")`.

**Chuyển model khi bị giới hạn** (`config.json` → `ai`):

| Trường | Mặc định | Ý nghĩa |
|---|---|---|
| `models` | `gemini-3.8-flash`, `gemini-3.6-flash`, `gemini-3.5-flash-lite` | Thử theo thứ tự. Hết hạn mức trong ngày, model không dùng được, hoặc lỗi lặp lại thì chuyển model sau; model đang dùng được giữ cho các template sau trong cùng lần chạy |
| `rpm` | 4 | Số lượt gọi tối đa mỗi phút (tool tự giãn nhịp); để ≤ hạn mức thấp nhất của các model trong AI Studio |
| `rateLimitSwitchAfter` | 3 | Bị giới hạn theo phút bao nhiêu lần liên tiếp thì chuyển model (trước đó: chờ theo `retryDelay` của API rồi thử lại) |
| `maxAttempts` | 5 | Số lần thử lại khi lỗi tạm thời (5xx, mạng) trước khi chuyển model |
| `thinkingBudget` | `null` | `0` tắt "thinking" (nhanh, rẻ hạn mức hơn) ở model cho phép; `null` = mặc định của model |

Đổi danh sách model: sửa `models` theo các model đang có trong AI Studio (cùng bộ với tool `populate-templates-meta`). Hết cả 3 model thì build vẫn chạy, dùng tên tạm và cảnh báo `ai_error`; hôm sau chạy mục **9** để đặt tên lại.

## Cách dùng nhanh: `menu.bat`

Sau khi cài đặt (mục trên), **double-click `menu.bat`** trong thư mục `video-template-data`. Menu hiện các việc, chọn bằng số:

```text
  1. Kiểm kê video mới trong input/
  2. Build video mới trong input/
  3. Mở trang soát
  4. Đánh dấu đã soát
  5. Build lại video (sau khi sửa sổ ghi)
  6. Chọn góc bằng tay (khi dò thất bại)
  7. Trạng thái
  8. Mở thư mục input/
  9. AI đặt tên + dịch cho template đã build (không build lại)
  0. Thoát
```

Mỗi đợt video mới:

1. Chọn **8** (hoặc mở thư mục `input/`), chép video phông xanh vào.
2. Chọn **1** kiểm kê. Tuỳ chọn: mở `registry\inventory.csv` điền Giữ / Bỏ, nguồn, giấy phép.
3. Chọn **2** build. Chỉ video mới được làm; video đã làm tự bỏ qua. AI đặt tên được dùng nếu máy gọi được, không thì tự lấy tên tạm từ tên file (không cần nhớ cờ `--no-ai`).
4. Chọn **3** mở trang soát trên trình duyệt, xem từng template.
5. Có lỗi: sửa `registry\templates\<name>.json` (bảng ở mục "Sửa tay trong sổ ghi"), rồi chọn **5**, chọn video cần build lại theo số. Dò thất bại thì chọn **6**.
6. Template còn tên tạm (build lúc AI chưa dùng được): chọn **9**, gõ `t`.
7. Chọn **4** đánh dấu đã soát (chọn số, hoặc `a` cho tất cả).
8. Commit thư mục `registry/` vào git.

Lưu ý:
- **Đóng `inventory.csv` trong Excel trước khi chạy mục 1, 2, 5** (Excel khoá file). Quên đóng thì tool báo và chờ: đóng Excel rồi nhấn Enter là chạy tiếp.
- Lỗi bất ngờ được in ra và ghi vào `out\menu_error.log`, menu không tự đóng; gửi file log cho người bảo trì.
- Lần chạy trước bị ngắt giữa chừng: chạy lại mục 2, tool tự bù trang soát và trạng thái sổ kiểm kê còn thiếu.

Phần dưới mô tả từng lệnh chi tiết; dùng khi cần chạy bằng dòng lệnh hoặc tự động hoá.

## Quy trình (dòng lệnh)

Mọi lệnh chạy trong thư mục `video-template-data`:

```powershell
cd "C:\Projects\Support Tool\video-template-data"
.venv\Scripts\python vtd.py <lệnh> ...
```

### 0. Bỏ video vào `input/`

Chép video phông xanh (mp4, mov, m4v, mkv, webm) vào thư mục **`input/`** (nằm ngay trong `video-template-data`). Thư mục này **không vào git** (`.gitignore` chỉ giữ file `input/.gitkeep`), nên mỗi máy tự chép video vào. Video gốc vẫn lưu lâu dài ở Synology Drive.

`inspect` và `build` không truyền đường dẫn thì mặc định đọc cả `input/`. Vẫn có thể truyền một file hoặc thư mục khác.

**Chỉ làm video mới:** công cụ nhận ra video bằng **mã băm nội dung** (SHA-256), không theo tên file, nên đổi tên hay chép lại cùng một video vẫn được coi là video cũ:

| Lệnh | Video đã làm rồi | Muốn làm lại |
|---|---|---|
| `inspect` | Bỏ qua nếu đã có trong `registry/inventory.csv` | Thêm `--recheck` |
| `build` | Bỏ qua nếu đã có template trong `registry/templates/` | Thêm `--rebuild` |

Ví dụ: đã làm data cho 20 video, nay chép thêm 2 video vào `input/` rồi chạy `inspect` và `build` thì chỉ 2 video mới được xử lý, 20 video cũ báo "Bỏ qua". Cuối mỗi lệnh có dòng tổng kết (bao nhiêu video làm, bao nhiêu bỏ qua). Video đã làm xong để nguyên hay xoá khỏi `input/` đều được; riêng lệnh `pick` cần video nguồn còn đó (hoặc truyền `--video`).

### 1. `inspect` — kiểm kê

```powershell
.venv\Scripts\python vtd.py inspect
.venv\Scripts\python vtd.py inspect "D:\VideoTemplates\30 NEW 10.2026"
```

Lệnh đầu đọc `input/`; lệnh sau đọc thư mục chỉ định.

- In môi trường (ffmpeg, key Gemini, danh sách ngôn ngữ, ảnh mẫu).
- Mỗi video: thông số (kích thước, fps, VFR, xoay, thời lượng, tiếng, codec), đề xuất nhóm **A** (đứng yên) / **B** (chuyển động), **I** (cần chuẩn hoá fps / VFR / xoay), **J** (ngoài 8–12 giây, vẫn giữ nguyên).
- Rào chắn (chỉ cảnh báo): không thấy vùng xanh, nhiều vùng xanh, vùng xanh chạm mép, không giống hình 4 cạnh, nghi chuyển cảnh.
- Ảnh tổng hợp 6 frame: `out/inspect/<mã băm>_<tên>.jpg`.
- Ghi / cập nhật **sổ kiểm kê** `registry/inventory.csv` (mở bằng Excel). Dev điền: `decision` (Giữ / Bỏ / Để sau), `reason`, `source`, `source_ref`, `license`, `license_checked_at`, `license_confirmed_by`. Chạy lại `inspect` không xoá các cột dev đã điền.

### 2. `build` — tạo template

```powershell
.venv\Scripts\python vtd.py build
.venv\Scripts\python vtd.py build "input\0_Billboard_Green_1280x720.mp4"
```

Lệnh đầu build mọi video **mới** trong `input/`; lệnh sau build một video.

Làm trọn cho từng video:

1. **Lượt 1 – dò:** đọc frame đã chuẩn hoá (xoay đúng chiều, ≤ 30 fps cố định, frame đầu ở 0); học màu xanh của video; dò 4 góc mọi frame (khớp 4 đường thẳng, mép ở điểm giữa dải chuyển màu); nhóm A lấy trung vị → 1 quad, nhóm B làm mượt hai chiều + nội suy frame dò lỗi; đo viền nhoè → nới khung (một số cho cả video, trần 6 px); chọn `previewFrame`, `posterRatio`.
2. **Lượt 2 – ghép và nén:** đọc lại video giống hệt lượt 1 (so số frame + mã băm vài frame), khử hắt sáng xanh sát khung (nếu đo thấy), ghép poster mẫu phủ kín tứ giác đã nới theo đúng phép toán shader của app, nén **một lần** ra `video.mp4` (H.264, CRF 18, keyframe mỗi giây, BT.709, giữ tiếng gốc).
3. Kiểm tra sau nén (số frame = số quad, frame đầu ở 0, không cờ xoay, đúng kích thước / fps); lệch là dừng.
4. `thumb.webp`, `preview.mp4`, `placeholder.json`.
5. AI (Gemini, chuyển model khi bị giới hạn) xem frame đã ghép poster mẫu, đặt tên tiếng Anh theo quy định + dịch sang mọi ngôn ngữ của app. Sai quy định thì gọi lại một lần; vẫn sai thì dùng tên từ tên file + cảnh báo.
6. Tạo `name` (tên tiếng Anh viết thường + ngày giờ, ví dụ `beach_billboard_20261127_1530`), chuyển thư mục tạm thành `out/templates/<name>/`, ghi **sổ ghi** `registry/templates/<name>.json`, thêm `name` lên **đầu** `registry/order.json`.
7. Tạo file soát (xem `review`).

Tuỳ chọn: `--rebuild` (build lại video đã có template), `--no-ai` (không gọi AI), `--as-new` (tạo thêm một template mới từ video đã có template), `--force` (build cả video sổ kiểm kê ghi "Bỏ").

**Build lại** (`--rebuild`) dùng lại đúng `name` và tên hiển thị đã có, và **xoá dấu "đã soát"** nếu file ra thay đổi. Template đã publish thì không build lại được (D7); muốn sửa thì dùng `--as-new` để tạo template mới.

> Chưa có `GEMINI_API_KEY` hoặc hết hạn mức mọi model: build vẫn chạy, lấy tên tạm từ tên file và cảnh báo; sau đó dùng mục **9** (lệnh `retitle`) để AI đặt tên lại.

### 3. `review` — soát bằng mắt

```powershell
.venv\Scripts\python vtd.py review
.venv\Scripts\python vtd.py review beach_billboard_20261127_1530
```

Mở `out/review/index.html` (mục lục, template có cảnh báo lên đầu) hoặc trang của một template, gồm:

- **Video giả lập app**: poster bàn cờ (ô đen trắng, hình tròn giữa, viền đỏ sát mép, chữ TOP ở cạnh trên) đè lên quad, nới thêm `bleedPx` 2. Soát lộ viền xanh / poster mẫu, rung, trôi, méo (tròn thành bầu dục), lật.
- **Video viền quad** có số frame: quad bám mép khung không.
- Ảnh tổng hợp ~12 frame, ảnh **phóng to 4 góc ×4** (frame đầu, giữa, cuối, chuyển động nhanh nhất, frame bị cảnh báo).
- Đồ thị toạ độ 4 góc theo thời gian (mượt là tốt, răng cưa là rung).
- Cảnh báo tự động: sót xanh quanh poster, rung > 0,5 px, nhảy góc, nới gần trần, cùng cảnh báo lúc build.
- Thông số, thumbnail, tên + bản dịch.

Tua từng frame: VLC (phím `E`) hoặc mpv (phím `.`); trình phát mặc định của Windows không tua từng frame được.

Đánh dấu đã soát (gắn với mã băm 4 file ra; build lại là mất dấu):

```powershell
.venv\Scripts\python vtd.py review --mark beach_billboard_20261127_1530 --note "ok"
.venv\Scripts\python vtd.py review --mark --all
```

Công cụ in danh sách sẽ được đánh dấu kèm số cảnh báo, hỏi xác nhận một lần. `--regen` tạo lại file soát (ví dụ sau khi sửa tên trong sổ ghi).

### 4. Sửa tay trong sổ ghi

`registry/templates/<name>.json`:

| Trường | Dùng khi |
|---|---|
| `titles` | Sửa tên tiếng Anh / bản dịch (khoá là mã thư mục `values-xx` của app: `in`, `iw`, `zh`...) |
| `overrides.previewFrame` | Thumbnail chọn tự động chưa đẹp |
| `overrides.posterRatio` | `{"w": 3, "h": 4}` khi tỷ lệ đo sai |
| `overrides.expandPx` | Ép độ nới khung (px) |
| `overrides.despill` | `false` khi viền thật của biển vốn màu xanh |
| `overrides.group` | Ép nhóm `"A"` / `"B"` |
| `overrides.previewCrf` | Preview bị vỡ khối → hạ CRF riêng (mặc định 28) |
| `overrides.manualQuads` | Do lệnh `pick` ghi |

Sửa `overrides` xong thì build lại video đó với `--rebuild`:

```powershell
.venv\Scripts\python vtd.py build "input\ten_video.mp4" --rebuild
```

### 5. `pick` — chọn góc tay (dự phòng)

Khi `review` báo "Dò thất bại … nên chọn tay":

```powershell
.venv\Scripts\python vtd.py pick beach_billboard_20261127_1530 --frames 0,150,299
```

Cửa sổ hiện từng frame, bấm 4 góc theo thứ tự tl → tr → br → bl, Enter để lưu (r: chọn lại, s: bỏ qua, Esc: thoát). Các frame mốc lưu vào sổ ghi; build lại sẽ dùng chúng và nội suy phần còn lại.

### 6. `retitle` — AI đặt lại tên (không build lại)

```powershell
.venv\Scripts\python vtd.py retitle
.venv\Scripts\python vtd.py retitle night_street_kiosk_20261127_1440
```

Không truyền `name`: đặt tên cho mọi template chưa publish đang dùng tên tạm (build lúc AI chưa dùng được). Truyền `name`: đặt lại tên cho đúng template đó, kể cả template đã có tên AI. `--redo` (không truyền `name`): đặt lại cho mọi template chưa publish. Lấy frame từ `video.mp4` đã build, cập nhật `titles` trong sổ ghi và trang soát; **`name` giữ nguyên**.

### `status`

```powershell
.venv\Scripts\python vtd.py status
```

## Ảnh mẫu "YOUR POSTER HERE"

Quyết định 27/11/2026: **công cụ tự dựng ảnh mẫu theo đúng tỷ lệ `posterRatio` của từng template** (thay cho cắt Fill một ảnh cố định), để khung tỷ lệ nào cũng đủ viền và không mất chữ:

- Nền trắng; viền đứt nét bo góc màu `#545EF3` chạy sát mép khung (nét, khoảng cách mép, bo góc, độ dài gạch / khoảng hở theo bản thiết kế, quy theo cạnh ngắn của khung, chia đều cho các góc giống nhau).
- Biểu tượng + chữ "YOUR POSTER HERE" đặt giữa, thu vừa (tối đa 76,5% chiều rộng, 56,8% chiều cao, tâm ở 47,6% chiều cao như bản thiết kế 3:4).
- Thông số nằm ở `config.json` → `samplePoster`.

Phần biểu tượng + chữ lấy từ `assets/sample_poster_content.png` (PNG nền trong hoặc nền trắng, **độ phân giải cao**, xin designer). Chưa có file đó thì công cụ cắt tạm từ ảnh tham chiếu `assets/sample_poster_reference.jpg` (850×1134, hơi mờ khi khung lớn) và cảnh báo `temp_sample`; có bản thật thì build lại trước khi publish.

**Ảnh hưởng tới app:** màn Choose Poster (K10.11) đang vẽ ảnh mặc định kiểu Fill; phải đổi sang dựng giống hệt quy tắc trên (hoặc dùng frame `previewFrame` của `video.mp4`, vốn đã có poster mẫu) để List, preview và Choose Poster thống nhất.

## Thư mục

| Đường dẫn | Nội dung | Git |
|---|---|---|
| `menu.bat` | Double-click để mở menu | Có |
| `vtd/` | Mã công cụ (`vtd/menu.py` là menu) | Có |
| `config.json` | Ngưỡng, tham số nén (ước lượng ban đầu, chỉnh sau lô thật đầu tiên) | Có |
| `config.local.json` | Đường dẫn máy riêng (repo app, ffmpeg) | Không |
| `registry/templates/*.json` | Sổ ghi từng template | Có |
| `registry/order.json` | Thứ tự hiển thị (mới lên đầu) | Có |
| `registry/inventory.csv` | Sổ kiểm kê video nguồn (kèm nguồn / giấy phép) | Có |
| `data/locales.txt` | Bản sao danh sách ngôn ngữ của app (dự phòng; lệch thì cảnh báo) | Có |
| `assets/` | Ảnh poster mẫu | Có |
| `input/` | Chỗ bỏ video nguồn (git chỉ giữ `.gitkeep`) | Không |
| `out/` | Kết quả build, file soát, ảnh inspect | Không |

## Quy ước toạ độ

`placeholder.json` dùng hệ toạ độ của app: gốc ở góc trên trái của pixel đầu tiên, tâm pixel thứ `i` ở `i + 0.5` (khớp shader: `vVideoUv` 0..1 ↔ 0..width). Bên trong công cụ dùng quy ước OpenCV (tâm pixel ở `i`); chuyển đổi nằm ở `vtd/placeholder.py`.

## Bản đồ code ↔ plan

Muốn biết một đoạn code làm theo quyết định nào thì tra bảng này rồi đọc khối tương ứng trong [VIDEO_TEMPLATE_DATA_PLAN.md](VIDEO_TEMPLATE_DATA_PLAN.md) (D…) hoặc `VIDEO_TEMPLATE_PLAN.md` của app (K…).

| File | Làm gì | Theo |
|---|---|---|
| `vtd/media.py` | ffprobe, đọc frame đã chuẩn hoá (xoay, ≤ 30 fps, frame đầu ở 0), nén H.264 | D2.1, D6.1, D6.6 |
| `vtd/detect.py` | Học màu xanh, mặt nạ, viền ngoài, khớp 4 đường thẳng, mép ở điểm giữa dải chuyển màu | D4.1–D4.3 |
| `vtd/analyze.py` | Lượt 1: dò mọi frame, nhóm A/B, làm mượt / nội suy, đo viền nhoè → nới khung, `posterRatio`, `previewFrame`, rào chắn | D2.2, D2.4, D4.4–D4.7, D5 |
| `vtd/geometry.py` | Thứ tự góc, kiểm tra lồi, nới khung theo pháp tuyến | D4.3, K2.5 |
| `vtd/compose.py` | Ghép ảnh vào quad đúng công thức shader (coverage = clamp(edgePx + 0.5)), khử hắt sáng xanh | D6.4, D6.5, K2, K3 |
| `vtd/posters.py` | Dựng ảnh mẫu "YOUR POSTER HERE" theo tỷ lệ; poster bàn cờ để soát | D6.2, D6.3 (sửa), D7.2 |
| `vtd/build.py` | Lượt 2 ghép + nén một lần, kiểm tra sau nén, thumb, preview, `placeholder.json`, đặt tên, sổ ghi | D6, D8, D9.1, D1.5, D1.13 |
| `vtd/placeholder.py` | Ghi / đọc / kiểm tra `placeholder.json` (mỗi quad một dòng, ghi lại ra y hệt) | D9.1, D10 A2–A5 |
| `vtd/naming.py`, `vtd/gemini.py` | Quy định tên, gọi AI (Gemini, chuyển model), kiểm tra, tên dự phòng, tạo `name` | D1.4, mục 7.3, D1.5 |
| `vtd/locales.py` | Danh sách ngôn ngữ từ `locales_config.xml` của app, dự phòng bản sao | D9.7 |
| `vtd/review.py` | Trang soát HTML, video giả lập bàn cờ, viền quad, phóng to góc, đồ thị, cảnh báo tự động, đánh dấu đã soát | D7 |
| `vtd/registry.py` | Sổ ghi template, thứ tự hiển thị, sổ kiểm kê | D1.3, D1.12, D2.6, D7.6 |
| `vtd/inspect_cmd.py` | Kiểm kê, phân loại, ảnh 6 frame | D2 |
| `vtd/pick.py` | Chọn góc tay ở frame mốc | D4.7 |
| `vtd/retitle.py` | AI đặt lại tên cho template đã build (không build lại) | Thêm sau (xem lịch sử) |
| `vtd/menu.py`, `menu.bat` | Menu chọn bằng số | Thêm sau (xem lịch sử) |

## Lịch sử quyết định và thay đổi

Những chỗ **khác plan ban đầu** hoặc phát sinh khi làm. Người sau đọc mục này trước khi "sửa lại cho đúng plan".

| Ngày | Thay đổi | Lý do / nguồn | Ảnh hưởng |
|---|---|---|---|
| 27/11/2026 | Duyệt toàn bộ D1–D11 | Plan data | Nền tảng của tool |
| 27/11/2026 | Tool đặt ở **thư mục con của repo Support Tool** (không phải repo riêng như D1.8); Python 3.11; sổ ghi JSON, sổ kiểm kê CSV | Dev chọn | Plan gốc vẫn ghi "repo riêng" |
| 27/11/2026 | Toạ độ quad ghi theo **hệ mép pixel** (tâm pixel ở i + 0.5) | Đối chiếu shader trong plan app (K3) | V0 của app cần kiểm lại |
| 27/11/2026 | Tìm mép bằng **pha trộn màu tuyến tính** thay vì ngưỡng "giống xanh" | Thử trên video tổng hợp thấy quad co vào khoảng 0,5 px | Sai số còn khoảng 0,2 px |
| 27/11/2026 | **Ảnh mẫu đổi theo design:** designer gửi ảnh 3:4, nền trắng, viền đứt nét, chữ "YOUR POSTER HERE". Tool **tự dựng ảnh mẫu theo tỷ lệ từng khung** thay vì cắt Fill (sửa D6.2, D6.3) | Ghép Fill vào khung khác 3:4 sẽ cắt mất viền, khung 16:9 mất cả chữ | App **K10.11** (Choose Poster) phải vẽ ảnh mặc định giống hệt; chờ designer gửi bản PNG độ phân giải cao |
| 27/11/2026 | Chữ mẫu **"YOUR POSTER HERE"** thay cho "Your poster will appear here" | Theo ảnh designer | Prompt AI, plan đã sửa |
| 27/11/2026 | AI đặt tên đổi từ **Claude** sang **Gemini** (key free), chuỗi 3 model `gemini-3.8-flash` → `gemini-3.6-flash` → `gemini-3.5-flash-lite`, tự chuyển khi hết hạn mức / quá tải | Dev yêu cầu dùng key tài khoản free; cùng bộ model với tool `populate-templates-meta` | `gemini-3.8-flash` hay quá tải (503), tool tự chuyển sang 3.6 |
| 27/11/2026 | Gọi Gemini qua **REST bằng thư viện chuẩn**, không dùng SDK | Windows Smart App Control trên máy dev chặn DLL của thư viện bên thứ ba (đã gặp với `jiter` của SDK Anthropic, `numpy.random`) | Không cần cài thêm gì cho AI |
| 27/11/2026 | Đặt lại tên bằng AI (mục 9 / `retitle`) **giữ nguyên `name`** | Dev chọn | `name` của template build lúc chưa có AI vẫn theo tên tạm |
| 27/11/2026 | Quy định tên: chỉ cấm **cụm** "Green Screen" (không cấm riêng "Screen", "Green") | Code cũ cấm từng từ, loại oan "Mall Screen" | |
| 27/11/2026 | Quy định tên: tên mẫu chỉ để minh hoạ, **chép nguyên văn bị loại**; AI phải gọi đúng loại vật (lightbox, sign, screen, frame...) | AI trả "Night Street Kiosk" (chép ví dụ) cho một biển hộp đèn | Template `night_street_kiosk_20261127_1440` đã đổi tên hiển thị thành "Night Street Lightbox" |
| 27/11/2026 | Thư mục **`input/`** (không vào git) + **chỉ làm video mới** (nhận ra theo mã băm) | Dev yêu cầu: thêm video thì chỉ làm video mới | `--recheck`, `--rebuild` để làm lại |
| 27/11/2026 | **`menu.bat`** chọn việc bằng số | Dev yêu cầu dễ dùng cho người sau | |
| 27/11/2026 | Ghi sổ khi file đang mở trong Excel thì **chờ** thay vì dừng; lỗi bất ngờ ghi `out\menu_error.log` | Lần chạy thật đầu tiên bị dừng vì `inventory.csv` đang mở trong Excel | Chạy lại mục 2 tự bù phần còn thiếu |

## Việc còn mở

| Việc | Ai | Ghi chú |
|---|---|---|
| Lệnh **`publish`** (D10, D11): kiểm tra toàn bộ, dựng `catalog.json`, upload Firebase Storage, tăng `video_template_catalog_version`, xuất pack | Dev, sau khi team xác nhận | Cần quyền ghi Storage + Realtime DB; xác nhận đường dẫn `<appId>/templates/video_templates/` và khoá. Trong lúc chờ có thể upload tay qua Console đúng thứ tự (file template → `catalog.json` → tăng version) |
| Bản PNG độ phân giải cao của biểu tượng + chữ "YOUR POSTER HERE" → `assets/sample_poster_content.png`, rồi build lại mọi template (`--rebuild`) | Designer | Hiện cắt tạm từ ảnh 850 px (cảnh báo `temp_sample`) |
| Sửa plan app: K10.11 (ảnh mặc định ở Choose Poster dựng theo quy tắc của tool, không Fill), K16.7 (AI là Gemini), L1 / L3 (trỏ sang plan data) | Dev | `VIDEO_TEMPLATE_PLAN.md` trong repo app chưa sửa |
| Nguồn + giấy phép từng video trong `registry/inventory.csv` | Designer / dev | `publish` sẽ cảnh báo nếu trống |
| Chỉnh ngưỡng trong `config.json` sau lô video thật đầu tiên | Dev | Các ngưỡng hiện là ước lượng ban đầu (D2.8) |
| Có cho phép từ "Video" trong tên không (vd. "Video Wall") | Dev / PO | Plan đang cấm; chưa quyết |
| Báo PO: preview ở màn List im lặng (không tiếng) | Dev | D8, plan data mục 17 |
| Dấu "đã soát" chỉ gắn với 4 file ra; sửa tên / bản dịch không làm mất dấu | | Nên đặt tên xong rồi mới đánh dấu |
