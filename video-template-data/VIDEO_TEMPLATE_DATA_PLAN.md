# Kế hoạch tạo dữ liệu Video Template (từ video designer → bộ data sẵn sàng lên Firebase)

**Liên quan:** `VIDEO_TEMPLATE_PLAN.md` (thiết kế app, K1–K16 đã duyệt 27/11/2026). File này cụ thể hoá **L1–L4** (mục 8.4 "Để xử lý sau") và mục 10.4 của plan đó.
**Trạng thái (cập nhật 27/11/2026):** đã duyệt D1–D11; **đã code** `inspect`, `build`, `review`, `pick`, `retitle`, `menu.bat` trong thư mục `video-template-data` của repo Support Tool (thay cho "repo riêng"). **Chưa làm `publish` (D10, D11).** Các chỗ đổi so với bản duyệt ghi "sửa 27/11/2026" ngay tại khối liên quan; tổng hợp ở README.md, mục "Lịch sử quyết định và thay đổi". Chưa sửa `VIDEO_TEMPLATE_PLAN.md` của app.

---

## 1. Mục tiêu

**Đầu vào:** chỉ có các file video designer tìm sẵn (thư mục "30 NEW 10.2026" trên Synology Drive), khoảng 20+ file mp4, **khung là màn xanh**.

**Đầu ra:** mỗi template một **thư mục hợp lệ** đúng định nghĩa của app, cộng **catalog** và **pack**:

```
<name>/
  video.mp4          ← video đã chuẩn hoá VÀ ĐÃ GHÉP poster mẫu "YOUR POSTER HERE" vào khung (PA1)
  placeholder.json   ← 4 góc theo từng frame (chính là 4 góc dùng để ghép), fps, previewFrame, bleedPx, posterRatio, video.width/height (không có formatVersion)
  thumb.webp         ← cắt từ video.mp4 tại previewFrame (K10.5)
  preview.mp4        ← bản 360p cắt từ video.mp4
catalog.json         ← templates[ name, videoRatio, durationMs, titles ]
video_template_pack/ ← bản sao thumb.webp + preview.mp4 (PAD pack, K1.15)
```

Sau đó upload lên Firebase Storage (`<appId>/templates/video_templates/`), tăng `video_template_catalog_version` trên Realtime DB.

---

## 2. Quan sát từ video designer gửi (27/11/2026, qua ảnh chụp danh sách + một video mở thử)

| Quan sát | Ví dụ | Ảnh hưởng |
|---|---|---|
| **Khung là màn xanh (green screen)** | `0_Prores_4444_Electronics_1280x720.mp4`: biển quảng cáo ở bãi biển, vùng poster xanh lá đặc; nhiều tên file có "Green", "Green_Screen" | Trả lời L1. Công cụ dùng màu xanh để **dò 4 góc** và làm **mặt nạ ghép** poster mẫu (mục 3) |
| Có khung **màu trắng** thay vì xanh | `5962422_Screen_White_1280x720.mp41.mp4` | Không dò theo màu xanh được; phải đo góc cách khác |
| **Nhiều tỷ lệ / độ phân giải** | 1280×720, 720×1280, 720×1080, 1280×672 | Đúng như dự kiến (`videoRatio`, waterfall). 720p là trần, khớp Q5 |
| Dung lượng 3–9 MB, khoảng 10 giây | | Khớp spec 8–12 giây |
| Tên file lộn xộn | `2.mp4`, `990981_..._1.mp41.mp4`, `(1)` trùng | Phải đặt lại `name` theo `[a-z0-9_]` (D7 của plan app) |
| Có bản trùng | `0_Billboard_Green_1280x720.mp4` và `... (1).mp4` | Cần lọc trùng |
| "Prores_4444" trong tên | | Có thể nguồn gốc là ProRes có kênh alpha, nhưng file nhận được là mp4; kiểm tra thực tế |

**Chưa biết, phải kiểm tra từng file (D2):** khung đứng yên hay chuyển động (camera lia, zoom); có **vật che** đi qua khung không (người, lá cây, xe); có tiếng không; fps; có cờ xoay không; khung xanh có **bị đổ bóng / phản chiếu**, có **hắt sáng xanh** lên xung quanh không.

---

## 3. Cách làm: ghép poster mẫu vào màn xanh, giữ nguyên PA1 (chốt 27/11/2026)

```
video gốc (khung xanh) ──► dò 4 góc mỗi frame ──► ghép ảnh "YOUR POSTER HERE" vào khung ──► video.mp4 (đã có poster mẫu)
                                     └────────────── cùng 4 góc đó ghi vào placeholder.json ──────────────┘
```

- **PA1 của plan app giữ nguyên:** `video.mp4` có sẵn poster mẫu; app **đè** poster của user lên vùng 4 góc (đã nới `bleedPx`), không tách màu. App **không bao giờ thấy màu xanh**.
- **Màu xanh chỉ là công cụ đo đạc:** dùng để **tìm 4 góc** ở mọi frame (thay việc đo tay / tracking, phần tốn công nhất của L3) và làm **mặt nạ ghép**; sau đó biến mất khỏi sản phẩm.
- **Quy tắc D1 của plan app áp dụng nguyên văn:** "JSON là nguồn gốc", poster mẫu được ghép bằng **chính** 4 góc ghi vào JSON. App đè cùng 4 góc + `bleedPx` nên poster mẫu bị che kín theo cấu tạo. D2–D6 cũng áp dụng, chỉ đổi "designer làm" thành "công cụ làm".
- **K10.5 giữ nguyên:** thumb = frame `previewFrame` của `video.mp4` (đã có poster mẫu), giữ tỷ lệ, không cắt. Màn List, preview, Choose Poster đều thấy poster mẫu thật, thống nhất.
- **Poster mẫu:** dùng **chính ảnh "YOUR POSTER HERE"** (K10.11) cho mọi template, để List, preview và Choose Poster nhìn thống nhất. Ảnh có chữ tiếng Anh, không dịch (K16.9).

**Chi tiết khi ghép:**
- **Viền xanh nhoè** (do nén, chroma 4:2:0, chuyển động): công cụ **nới khung ra một chút** cho poster mẫu phủ hết phần xanh nhoè, và **ghi chính khung đã nới vào JSON** (D1). App nới thêm `bleedPx` (mặc định 2) để che mép poster mẫu.
- **Phủ kín cả tứ giác, không dùng mặt nạ xanh** (sửa 27/11/2026, D2): trong vùng xanh của một số video có **chữ / dấu**; mặt nạ xanh sẽ để lộ chúng qua poster mẫu. Video hiện có **không có vật che**, nên ghép **phủ kín toàn bộ tứ giác đã nới**, đúng hệt cách app đè. Video có vật che (nếu sau này có) thì bỏ, hoặc bàn lại PA2.
- **Nén một lần:** đọc video gốc thành các frame **đúng nhịp đã chuẩn hoá** (≤ 30 fps, frame đầu ở 0), dò góc và ghép trên chính các frame đó, nén **một lần** ra `video.mp4`. Frame thứ i của file ra chắc chắn là frame đã dùng để đo `quads[i]` (K2.2); chất lượng chỉ giảm một lần.
- **Hắt sáng xanh** lên vật xung quanh khung (cột, viền kim loại): nếu thấy rõ, khử bớt màu xanh ở vùng sát ngoài khung khi ghép.

---

## 4. Quy trình (các khối cần bàn)

| Khối | Tên | Làm gì |
|---|---|---|
| **D1** | Công cụ và môi trường | **Đã duyệt 27/11/2026**, xem mục 7 |
| **D2** | Kiểm kê và phân loại | **Đã duyệt 27/11/2026**, xem mục 8 |
| **D3** | Đặt tên và tiêu đề | **Gộp vào D1** (27/11/2026): xem mục 7.2, 7.3 và D1.12, D1.13 |
| **D4** | Dò 4 góc | **Đã duyệt 27/11/2026**, xem mục 9 |
| **D5** | Xác định tham số | **Đã duyệt 27/11/2026**, xem mục 10 |
| **D6** | Ghép poster mẫu + nén `video.mp4` | **Đã duyệt 27/11/2026**, xem mục 11 |
| **D7** | Kiểm chứng bằng mắt | **Đã duyệt 27/11/2026**, xem mục 12 |
| **D8** | Tạo thumb và preview | **Đã duyệt 27/11/2026**, xem mục 13 |
| **D9** | Ghi `placeholder.json` và catalog | **Đã duyệt 27/11/2026**, xem mục 14 |
| **D10** | Kiểm tra toàn bộ trước khi upload | **Đã duyệt 27/11/2026**, xem mục 15 |
| **D11** | Upload và pack | **Đã duyệt 27/11/2026**, xem mục 16 |

---

## 5. Câu hỏi mở (bàn trong từng khối)

| # | Câu hỏi | Khối |
|---|---|---|
| O1 | ~~Vật che~~: **đã trả lời 27/11/2026**, video hiện có không có vật che | D2 |
| O2 | ~~Khung trắng~~: **đã trả lời 27/11/2026**, mọi video hiện có đều là vùng xanh; video khác loại sau này sẽ bị `inspect` cảnh báo | D2 |
| O3 | ~~Tiếng~~: **đã chốt 27/11/2026**, giữ tiếng gốc (có thì giữ, không có thì để không có); giấy phép tiếng đi cùng giấy phép video (L4) | D6 |
| O4 | ~~`posterRatio`~~: **đã chốt ở D5.2** (đo ở frame ít nghiêng nhất, làm tròn về tỷ lệ chuẩn) | D5 |
| O5 | ~~Poster mẫu~~: **đã chốt**, ảnh "YOUR POSTER HERE"; **sửa 27/11/2026:** công cụ tự dựng theo tỷ lệ từng khung thay vì ghép Fill (D6.2, D6.3) | D6 |
| O6 | ~~Upload~~: **đã chốt ở D11** (lần đầu có thể tay qua Console theo đúng thứ tự; sau đó script bằng `gcloud`) | D11 |
| O7 | Giấy phép video (L4): ghi ở sổ kiểm kê (D2, mục 15.4); thiếu thì **cảnh báo** lúc publish, không chặn (D10.7) | D2, D10 |

---

## 6. Thứ tự đề xuất

1. D1 (công cụ) → D2 (kiểm kê, cần tải video về máy) → D3.
2. D4 → D5 → D6 → D7: làm thử trọn vẹn trên **1–2 video dễ** (khung xanh, đứng yên, không vật che) trước, rồi mới chạy cho cả bộ.
3. D8 → D9 → D10 → D11.

Bộ data của 1–2 video đầu tiên cũng chính là **dữ liệu thật cho V0 spike** của plan app.

**Ảnh hưởng tới `VIDEO_TEMPLATE_PLAN.md` (sửa khi bạn ok):** L1 có câu trả lời (màn xanh, công cụ ghép poster mẫu, PA1 giữ nguyên); D1–D6 do công cụ làm thay designer; L3 trỏ sang file này.

---

## 7. D1 – Công cụ và môi trường (**đã duyệt 27/11/2026**)

**Mục tiêu công cụ:** đầu vào **chỉ là một video phông xanh**; đầu ra là trọn bộ data đúng định dạng của app. Dùng lại được: sau này designer tìm thêm video thì đưa vào công cụ để thêm template.

### 7.1. Bốn lệnh

| Lệnh | Làm gì | Chạy lại được không |
|---|---|---|
| `inspect` | Kiểm tra môi trường (ffmpeg, key Gemini), đọc thông số video (độ phân giải, fps, thời lượng, có tiếng, cờ xoay), đo tỷ lệ khung có màu xanh theo thời gian, **cảnh báo nghi có vật che** (vùng xanh thủng hoặc co lại giữa chừng) | Thoải mái |
| `build` | Làm trọn D3–D9 cho một video (hoặc cả thư mục): đặt tên, dò 4 góc, nới khung, ghép poster mẫu, nén `video.mp4`, cắt thumb / preview, ghi `placeholder.json`, kèm **file soát lỗi** | Thoải mái |
| `review` | Mở file soát lỗi: video poster bàn cờ đè đúng như app (D7), ảnh vẽ 4 góc ở nhiều frame, báo cáo cảnh báo, tên AI đặt | Thoải mái |
| `publish` | Kiểm tra toàn bộ (D10) → dựng catalog → upload Firebase → tăng `catalogVersion` → (tuỳ chọn) xuất thumb / preview cho pack | **Không đảo ngược** (D7 "không upload đè"); từ chối nếu `name` đã tồn tại trên Firebase; nên yêu cầu xác nhận "đã review" |

### 7.2. Công cụ tự suy ra (đầu vào chỉ có video)

| Thứ cần | Cách |
|---|---|
| Tên hiển thị + 48 bản dịch | AI đặt từ hình ảnh (mục 7.3) |
| `name` | Tên tiếng Anh viết thường, khoảng trắng thành `_`, thêm **ngày giờ tạo** (`beach_billboard_20261127_1530`); trùng phút thì thêm giây / số thứ tự; luôn kiểm tra chưa tồn tại. Tạo **một lần** ở lần `build` đầu, ghi vào sổ ghi; build lại dùng đúng tên đó; sửa tên trước `publish` thì được tạo lại, sau `publish` cố định mãi (D7) |
| Tên 4 file trong thư mục | **Cố định** `video.mp4`, `placeholder.json`, `thumb.webp`, `preview.mp4` (D8: app và assetssdk tìm theo tên cố định) |
| 4 góc, nới khung, `previewFrame`, `posterRatio`, `bleedPx`, `fps`, `videoRatio`, `durationMs` | Tự động (D4, D5); chỉnh tay trong sổ ghi chỉ khi `review` thấy sai |
| Thứ tự hiển thị | Danh sách thứ tự trong sổ ghi; **template mới lên đầu** (D1.12); muốn đổi thì sửa tay |

### 7.3. Đặt tên bằng AI

**Quy định đặt tên (gửi cho AI):**

| Quy định | Đúng | Sai |
|---|---|---|
| 2–3 từ, tối đa khoảng 24 ký tự | "Beach Billboard" | "A Beautiful Billboard Standing By The Sunny Beach" |
| Mẫu **[bối cảnh] + [vật đặt poster]** | "City Bus Stop", "Store Window", "Gallery Wall", "Street Kiosk", "Living Room Frame" | "Summer Vibes", "Dream Space" |
| Viết hoa chữ đầu mỗi từ, tiếng Anh | "Night Street Kiosk" | "night street kiosk" |
| Không từ quảng cáo | | "Amazing", "Stunning", "Ultimate", "Pro", "Best" |
| Không từ kỹ thuật | | "Template", "Mockup", "Video", "Green Screen", "Poster", "Placeholder" |
| Không số, thương hiệu, tên người, emoji, dấu câu | | "Billboard 2", "Samsung TV" |
| Không trùng tên đã có (không phân biệt hoa thường) | | |
| Cùng loại vật đã có thì phân biệt bằng **bối cảnh**, không bằng số | "Highway Billboard" khi đã có "Beach Billboard" | "Beach Billboard 2" |

Bản dịch 48 ngôn ngữ (cùng lần gọi): ngắn, tự nhiên, cùng nghĩa, độ dài tương đương; gửi kèm đúng danh sách mã ngôn ngữ của app (`locales_config.xml`). Danh sách "vật đặt poster được phép" chưa bắt buộc; thêm sau nếu tên chưa đồng bộ.

**Cách gọi:** (sửa 27/11/2026) **Gemini** qua REST, key free `GEMINI_API_KEY`, chuỗi 3 model `gemini-3.8-flash` → `gemini-3.6-flash` → `gemini-3.5-flash-lite`, hết hạn mức thì chuyển model (cùng bộ với tool `populate-templates-meta`); trước đó dự kiến `claude-opus-5-5`; gửi frame `previewFrame` **đã ghép poster mẫu** (template chuyển động thì thêm 1–2 frame), dặn "khung có chữ *YOUR POSTER HERE* là chỗ đặt poster, đặt tên theo bối cảnh và loại vật chứa khung"; gửi kèm quy định, **danh sách tên tiếng Anh đã có**, danh sách mã ngôn ngữ. Bắt AI trả **dữ liệu có cấu trúc cố định** (tên tiếng Anh + bảng ngôn ngữ). Công cụ kiểm tra: số từ, độ dài, ký tự, viết hoa, từ cấm, trùng tên, đủ ngôn ngữ; sai thì gọi lại **một lần** kèm lý do; vẫn sai / lỗi mạng / không có key thì dùng tên làm sạch từ tên file và **cảnh báo** trong `review`. Tên hiện trong báo cáo `review`, sửa được trong sổ ghi trước `publish`. Chi phí ước tính vài cent mỗi template.

### 7.4. Ngôn ngữ và môi trường

**Python + OpenCV + ffmpeg.** OpenCV: dò vùng xanh, tìm 4 góc, ghép theo phối cảnh, cửa sổ bấm chọn góc khi dò thất bại. ffmpeg: đọc frame đúng nhịp, nén `video.mp4` (H.264, ≤ 30 fps, keyframe mỗi giây, giữ tiếng), cắt thumb, làm preview, đọc thông số và đếm frame (`ffprobe`). Phần toán ghép (homography, nới khung) viết theo đúng công thức K2.3 / K2.5 của plan app; D7 và V0 spike đối chiếu.

| Cài | Ghi chú |
|---|---|
| Python ≥ 3.12 | Cài một lần |
| ffmpeg (+ ffprobe), thêm vào PATH | `inspect` kiểm tra và in phiên bản |
| Môi trường ảo (virtualenv) riêng cho công cụ | Không lẫn với phần mềm khác |
| Thư viện: OpenCV, numpy, Pillow, thư viện Google Cloud / Firebase (Gemini gọi REST, không cần SDK) | **Ghim phiên bản** để chạy lại sau này ra đúng kết quả |
| Key Gemini | Biến môi trường `GEMINI_API_KEY` (key free AI Studio); **không** ghi key vào repo |
| Đăng nhập Google Cloud (cho `publish` bằng script) | `gcloud` bằng tài khoản của dev; không dùng file khoá dịch vụ. Lần đầu upload tay qua Console. Cần hỏi team quyền ghi Storage + Realtime DB |

### 7.5. Repo riêng

Công cụ nằm ở **một repo riêng**, không nằm trong repo app (không phải `tools/` của PosterMaker).

| Trong repo công cụ | Đưa vào git |
|---|---|
| README (cài đặt, cách chạy từng lệnh) | Có |
| Mã công cụ (Python) | Có |
| Sổ ghi từng template (video nguồn ở đâu, `name`, tên, chỉnh tay) | Có |
| Bộ tên dịch theo ngôn ngữ, danh sách thứ tự hiển thị | Có |
| Ảnh poster mẫu "YOUR POSTER HERE" | Có |
| Danh sách mã ngôn ngữ của app | Có (bản sao, xem rủi ro) |
| `out/`, video nguồn | **Không** |

**Hệ quả của việc tách repo:**
- **Danh sách 48 ngôn ngữ** phải khớp `locales_config.xml` của app: giữ một bản sao trong repo công cụ, hoặc công cụ đọc thẳng file của app qua đường dẫn cấu hình. Lệch thì `titles` thiếu / thừa ngôn ngữ.
- **Pack (K1.15):** `publish` xuất thumb + preview ra một thư mục đúng cấu trúc `templates/video_templates/<name>/`; dev chép sang `video_template_pack/src/main/assets/` của repo app (hoặc công cụ chép thẳng nếu có đường dẫn tới repo app). Pack chỉ cần cho template có lúc phát hành app.
- **Định dạng data** (`placeholder.json`, catalog) là **hợp đồng** giữa hai repo: đổi bên nào cũng phải đối chiếu plan app 8.4 / 8.19.
- `VIDEO_TEMPLATE_DATA_PLAN.md` chuyển sang repo công cụ khi bàn xong; `VIDEO_TEMPLATE_PLAN.md` (app) giữ ở repo app.

### 7.6. Các điểm chốt D1

| # | Điểm | Chốt |
|---|---|---|
| D1.1 | Đầu vào | Chỉ một video phông xanh |
| D1.2 | Lệnh | `inspect`, `build`, `review`, `publish` (mục 7.1) |
| D1.3 | Sổ ghi | Mỗi template một file cấu hình trong repo công cụ; catalog dựng lại từ sổ ghi; `out/` và video nguồn không vào git |
| D1.4 | Đặt tên | AI theo quy định mục 7.3, gửi kèm tên đã có, dịch luôn; kiểm tra + gọi lại một lần; dự phòng từ tên file |
| D1.12 | Thứ tự hiển thị (gộp từ D3) | Template mới **lên đầu** danh sách trên màn List |
| D1.13 | Lúc gọi AI đặt tên (gộp từ D3) | **Sau** khi ghép poster mẫu (D6), vì AI cần ảnh đã có poster mẫu; build trong **thư mục tạm**, có tên rồi mới đổi tên thư mục thành `name` |
| D1.5 | `name` | Tên tiếng Anh viết thường + ngày giờ tạo; tạo một lần, cố định sau `publish` |
| D1.6 | Tên file | Cố định 4 tên (D8) |
| D1.7 | Ngôn ngữ | Python + OpenCV + ffmpeg, môi trường ảo, ghim phiên bản |
| D1.8 | Vị trí | **Repo riêng** (mục 7.5) |
| D1.9 | Bí mật | Key Gemini, đăng nhập Google không nằm trong repo |
| D1.10 | Upload | Lần đầu tay; sau đó script bằng tài khoản dev |
| D1.11 | Chạy cả lô | `build` nhận một video hoặc cả thư mục |

**Rủi ro:** ffmpeg không có trong PATH (`inspect` báo rõ); quyền ghi Firebase chưa rõ (hỏi team); danh sách ngôn ngữ lệch giữa hai repo; dev mới với Python (giữ code chia nhỏ theo bước).

---

## 8. D2 – Kiểm kê và phân loại (**đã duyệt 27/11/2026**)

**Thực tế bộ video hiện có (dev xác nhận 27/11/2026):** mỗi video **một vùng xanh**; một số vùng xanh có **chữ / dấu** bên trong (kệ, phủ kín hết là được); **luôn thấy đủ 4 góc**, không bị cắt; **không có vật che**; có cả **đứng yên** và **chuyển động**; không có màn cong / góc bo tròn; không có bản trùng; tất cả là vùng xanh (không có khung trắng).

### 8.1. Phân loại

| Nhóm | Mô tả | Quyết định |
|---|---|---|
| **A** | Đứng yên | Giữ; **1 quad** cho cả video; dùng cho **lô thử đầu tiên** |
| **B** | Chuyển động (lia, zoom, nghiêng) | Giữ; dò góc từng frame, làm mượt |
| **I** | Vấn đề kỹ thuật (> 30 fps, VFR, cờ xoay) | Giữ; chuẩn hoá ở D6 |
| **J** | Thời lượng ngoài 8–12 giây | **Giữ nguyên** cả ngắn hơn 8 giây lẫn dài hơn 12 giây (không cắt, không lặp) |
| **H** | Nhiều cảnh ghép lại | Chưa thấy; chỉ là cảnh báo cho video sau này |

### 8.2. `inspect` đo gì

| Đo | Cách | Dùng để |
|---|---|---|
| Thông số kỹ thuật | ffprobe: độ phân giải, cờ xoay, fps (cố định không), số frame, thời lượng, có tiếng, codec, **mã băm file** | Chuẩn hoá ở D6; nhận ra file kể cả khi bị đổi tên |
| Đứng yên hay chuyển động | Độ dịch của 4 góc giữa các frame (dưới khoảng 1 px là đứng yên) | Nhóm A / B; nhóm A ghi 1 quad |
| **Ảnh tổng hợp** | 6 frame rải đều, tô viền ngoài vùng xanh và đánh dấu 4 góc | Dev xem nhanh dò có đúng không |
| **Rào chắn** cho video sau này (chỉ cảnh báo, không chặn) | Không thấy vùng xanh ở frame nào đó; có hơn một vùng xanh; vùng xanh chạm mép hình; vùng xanh không giống hình 4 cạnh; chuyển cảnh | Video khác loại (khung trắng, nhiều màn hình...) bị phát hiện để bàn riêng |

**Không có** cảnh báo "nghi vật che": chữ / dấu bên trong vùng xanh tạo lỗ, sẽ báo sai liên tục.

### 8.3. Vùng xanh có chữ / dấu

Dò 4 góc theo **đường viền ngoài cùng** của vùng xanh, bỏ qua mọi lỗ bên trong (D4). Ghép poster mẫu **phủ kín cả tứ giác đã nới**, không dùng mặt nạ xanh (D6, mục 3): dùng mặt nạ thì chữ / dấu lộ qua poster mẫu. Kết quả: công cụ và app dùng **cùng một cách đè**.

### 8.4. Sổ kiểm kê

Một bảng trong repo công cụ, mỗi video nguồn một dòng:

| Cột | Ví dụ |
|---|---|
| Tên file gốc | `0_Prores_4444_Electronics_1280x720.mp4` |
| Mã băm | (nhận ra file khi đổi tên) |
| Thông số | 1280×720, 30 fps, 10,0 giây, có tiếng |
| Nhóm | A |
| Cảnh báo | (trống) |
| Quyết định | Giữ / Bỏ / Để sau |
| Lý do | "Vùng xanh, đứng yên" |
| **Nguồn và giấy phép** | Ví dụ "Pexels #990981, miễn phí thương mại" |
| Trạng thái | Chưa làm / Đã build / Đã review / Đã publish, kèm `name` sau khi build |

Máy đề xuất nhóm; **dev quyết** sau khi xem ảnh tổng hợp và cảnh báo.

**Giấy phép (L4):** nhiều tên file bắt đầu bằng dãy số (`990981_...`, `5365057_...`, `5962422_...`), giống mã video của các kho video (Pexels, Pixabay, Storyblocks...). Mỗi kho có điều khoản khác nhau; **hỏi designer nguồn từng video**, ghi vào sổ **trước khi publish**.

### 8.5. Các điểm chốt D2

| # | Điểm | Chốt |
|---|---|---|
| D2.1 | Thông số kỹ thuật | ffprobe: độ phân giải, xoay, fps, số frame, thời lượng, tiếng, codec, mã băm |
| D2.2 | Phân loại | A đứng yên (1 quad) / B chuyển động; I chuẩn hoá ở D6; **thời lượng giữ nguyên** (ngắn hơn 8 hay dài hơn 12 giây đều không cắt, không lặp) |
| D2.3 | Chữ / dấu trong vùng xanh | Dò theo viền ngoài, bỏ qua lỗ; ghép phủ kín cả tứ giác, **không mặt nạ xanh** (đã sửa D4, D6, mục 3) |
| D2.4 | Rào chắn | Cảnh báo (không chặn): mất vùng xanh, nhiều vùng xanh, chạm mép, không giống 4 cạnh, chuyển cảnh; không có cảnh báo vật che |
| D2.5 | Người quyết | Dev xem ảnh tổng hợp 6 frame + cảnh báo, ghi giữ / bỏ |
| D2.6 | Sổ kiểm kê | Mỗi video một dòng, có cột nguồn / giấy phép và trạng thái |
| D2.7 | Lô thử đầu tiên | 1–2 video nhóm A |
| D2.8 | Ngưỡng đo | Ước lượng ban đầu, chỉnh lại sau lô thật đầu tiên |

**Rủi ro:**
- Chữ / dấu nằm **sát mép** vùng xanh làm viền ngoài bị khuyết, góc lệch vài px; nới khung + phủ kín thường che được, soát ở `review`.
- Video dài hơn 12 giây giữ nguyên → thời gian xuất trên máy yếu tăng theo (đo ở V0 của plan app).
- Giấy phép chưa rõ → nếu đã publish mới biết không được dùng thương mại thì phải gỡ khỏi catalog.

---

## 9. D4 – Dò 4 góc (**đã duyệt 27/11/2026**)

**Mục tiêu:** với mỗi frame của video đã chuẩn hoá nhịp, tìm 4 góc của vùng xanh thật chính xác (lệch thì poster của user lệch khỏi khung hoặc lộ viền poster mẫu). Nhiệm vụ duy nhất: **frame vào, quad (+ độ tin cậy) ra**; làm mượt, nới khung, chọn tay là các bước xếp sau.

### 9.1. Tìm vùng xanh trong một frame

| Bước | Làm gì | Vì sao |
|---|---|---|
| 1 | **Học màu xanh của chính video** ở vài frame đầu (cụm xanh đậm, đồng nhất, lớn nhất) | Mỗi video một sắc xanh, sáng tối khác nhau |
| 2 | Đánh dấu điểm đủ giống màu chuẩn, so theo **sắc màu**, ít phụ thuộc độ sáng | Phần khung bị bóng râm vẫn được nhận là xanh |
| 3 | Dọn nhiễu, lấp khe nhỏ, **chỉ giữ vùng xanh lớn nhất** | Cây cỏ, áo xanh trong cảnh không bị nhầm là khung |
| 4 | Lấy **viền ngoài cùng**, bỏ qua lỗ bên trong (D2.3) | Chữ / dấu trong vùng xanh không kéo lệch góc |

### 9.2. Từ viền ngoài ra 4 góc

**Khớp 4 đường thẳng cho 4 cạnh, góc = giao điểm hai cạnh kề.** Mỗi cạnh dùng hàng trăm điểm, sai số từng điểm triệt tiêu nhau, chính xác **dưới 1 px**; góc mờ hoặc bị chữ / dấu khuyết vẫn tính đúng vì suy ra từ cạnh. Mép lấy tại **điểm giữa dải chuyển màu** để ổn định giữa các frame. Xếp góc **tl, tr, br, bl, chiều kim đồng hồ**; kiểm tra tứ giác lồi, đúng chiều, đủ lớn (luật của app).

Không chọn: lấy 4 điểm "nhọn" nhất của viền (góc mờ làm điểm nhảy vài px giữa các frame, poster rung); bám điểm đặc trưng kiểu Mocha / Blender (màn xanh trơn, không có họa tiết để bám; thứ rõ nhất là 4 cạnh).

### 9.3. Theo thời gian

| Nhóm | Cách |
|---|---|
| **A (đứng yên)** | Dò mọi frame, lấy **trung vị** từng góc, ghi **1 quad**. Ngưỡng đứng yên: góc dịch dưới khoảng 1 px suốt video |
| **B (chuyển động)** | Dò từng frame. **Làm mượt hai chiều** (nhìn cả frame trước và sau, vì công cụ có cả video) để bỏ rung nhẹ mà **không trễ** chuyển động thật; mức làm mượt nhỏ để khung chuyển động nhanh không bị "trôi". Mỗi frame có **độ tin cậy** (cạnh có thẳng, diện tích hợp lý); frame tin cậy thấp hoặc nhảy xa bất thường thì bỏ kết quả dò, **nội suy** từ frame trước và sau |

### 9.4. Nới khung

Quad ghi vào JSON là **quad đã nới** (D1 của plan app, mục 3), để poster mẫu phủ hết viền xanh nhoè.

| Bước | Làm gì |
|---|---|
| Đo viền nhoè | Từ mép ra ngoài, đếm số px còn ám xanh (nén, chroma 4:2:0, hắt sáng sát mép) |
| Chọn độ nới | Viền nhoè lớn nhất + 1 px dự phòng; **một con số cho cả video** (không đổi theo frame, để mép không rung). Dev chấp nhận **nới thừa một chút** ở đoạn khung nhỏ (ví dụ khung tiến lại gần camera), **nhưng không quá nhiều** |
| Cách nới | Dịch từng cạnh ra ngoài theo pháp tuyến rồi lấy giao điểm, **giống hệt K2.5** của app |
| Trần | Tối đa khoảng **6 px**; vượt trần, hoặc chênh lệch viền nhoè giữa đầu và cuối video lớn, thì **cảnh báo** trong `review` (nới nhiều đè lên viền thật của biển / màn hình) |

App nới thêm `bleedPx` (mặc định 2) để che mép poster mẫu.

### 9.5. Khi dò thất bại

| Tình huống | Xử lý |
|---|---|
| Vài frame lẻ | Nội suy (9.3) |
| Nhiều frame liên tiếp, hoặc frame đầu / cuối | Báo trong `review`; **chế độ chọn tay**: cửa sổ đơn giản hiện frame, dev bấm 4 góc ở vài frame mốc, công cụ nội suy phần còn lại; kết quả lưu vào **sổ ghi** để build lại không phải chọn lại |

Với bộ video hiện có (vùng xanh rõ, đủ 4 góc, không vật che) chế độ chọn tay có thể không cần; là dự phòng cho video sau này.

### 9.6. Đầu ra

- **Mảng quad:** 1 phần tử (nhóm A) hoặc **đúng bằng số frame** của video đã chuẩn hoá (nhóm B); toạ độ theo **pixel frame đã chuẩn hoá** (đã xoay, đã đổi nhịp), 2 chữ số thập phân.
- **File soát lỗi:** ảnh vẽ quad lên vài frame; **đồ thị toạ độ 4 góc theo thời gian** (đường mượt là tốt, răng cưa là rung); danh sách frame đã nội suy; độ nới đã chọn.

### 9.7. Các điểm chốt D4

| # | Điểm | Chốt |
|---|---|---|
| D4.1 | Màu xanh | Học màu chuẩn của từng video; so theo sắc màu |
| D4.2 | Vùng xanh | Dọn nhiễu, giữ vùng lớn nhất, lấy viền ngoài (bỏ lỗ chữ / dấu) |
| D4.3 | 4 góc | Khớp 4 đường thẳng (mép tại điểm giữa dải chuyển màu), góc = giao điểm; tl, tr, br, bl; kiểm tra lồi, đúng chiều, đủ lớn |
| D4.4 | Nhóm A | Trung vị từng góc, 1 quad |
| D4.5 | Nhóm B | Làm mượt hai chiều nhẹ; frame tin cậy thấp / nhảy bất thường thì nội suy |
| D4.6 | Nới khung | Viền nhoè lớn nhất + 1 px, **một số cho cả video**, chấp nhận nới thừa ít; nới như K2.5; trần khoảng 6 px, vượt hoặc chênh lớn thì cảnh báo |
| D4.7 | Dò thất bại | Nội suy; nhiều thì chọn tay ở frame mốc, lưu vào sổ ghi |
| D4.8 | Đầu ra | Mảng quad theo pixel frame đã chuẩn hoá, 2 chữ số thập phân; file soát lỗi (ảnh quad, đồ thị góc, frame nội suy, độ nới) |

**Rủi ro:**
- Làm mượt quá tay → poster trôi khỏi khung ở đoạn camera đổi hướng nhanh; giữ mức nhỏ, soát bằng video bàn cờ.
- Mờ chuyển động mạnh → poster sắc nét đặt lên khung mờ trông hơi "dán" (giới hạn của PA1, chấp nhận).
- Màu chuẩn học sai (frame đầu tối, vật xanh khác lớn hơn khung) → dò nhầm; rào chắn D2 cảnh báo.
- Nới chạm viền thật của biển / màn hình → cảnh báo khi vượt trần, vẫn phải nhìn ở `review`.

---

## 10. D5 – Tham số của `placeholder.json` (**đã duyệt 27/11/2026**)

| Trường | Cách lấy |
|---|---|
| `video.width`, `video.height` | Kích thước video **đã chuẩn hoá** (đã xoay nếu có cờ xoay) |
| `video.fps` | fps của video đã chuẩn hoá; chỉ tham khảo (K2.2) |
| `bleedPx` | **2** cho mọi template, ghi rõ trong JSON (D4 đã nới khung phủ viền xanh; 2 đủ che mép poster mẫu theo K3.9) |
| `quads` | Từ D4 (đã nới) |
| **`posterRatio`** | Mục 10.1 |
| **`previewFrame`** | Mục 10.2 |

**Không có `formatVersion`** (bỏ 27/11/2026). Việc tiến hoá định dạng (catalog mới cho cấu trúc mới...) **chưa xét lúc này**.

### 10.1. `posterRatio`

Tỷ lệ của khung phẳng mà user kéo / zoom poster (K7) và của ảnh bake (K9). Sai thì poster của user bị **méo** trong video (hình tròn thành bầu dục). Khung có thể nghiêng phối cảnh, nên đo cạnh trên ảnh không ra tỷ lệ thật.

**Cách lấy:** chọn frame khung **ít nghiêng nhất** (hai cạnh đối gần song song nhất), đo trung bình hai cạnh ngang chia trung bình hai cạnh dọc, rồi **làm tròn về tỷ lệ chuẩn gần nhất** nếu lệch dưới khoảng 5%: 1:1, 4:5, 3:4, 2:3, 9:16, 5:4, 4:3, 3:2, 16:9. Không khớp: giữ số đo (2 chữ số) + **cảnh báo** trong `review`. Ghi đè được trong sổ ghi. Không chọn: tính phối cảnh đầy đủ (cần thông số ống kính, video không có).

**Khung tỷ lệ lạ** (ví dụ 1:2): **chấp nhận**, không cảnh báo, không bỏ; poster Fit vào, khoảng trống do nền Blur / Color lấp.

### 10.2. `previewFrame`

Dùng làm thumbnail ở màn List (K10.5) và ảnh nền ở Choose Poster / Adjust (K10). Công cụ tự chọn theo thứ tự ưu tiên: không nằm ở 10% đầu / cuối video; khung ít chuyển động quanh frame đó (ít mờ); toàn cảnh sắc nét; khung to và ít nghiêng. Nhóm A: frame sắc nhất ở khoảng giữa. Ghi đè được trong sổ ghi; dev soát thumbnail ở `review`.

### 10.3. Các điểm chốt D5

| # | Điểm | Chốt |
|---|---|---|
| D5.1 | Đọc thẳng | `video.width/height`, `fps` từ video đã chuẩn hoá; không có `formatVersion` |
| D5.2 | `posterRatio` | Frame ít nghiêng nhất, làm tròn về tỷ lệ chuẩn nếu lệch dưới khoảng 5%; không khớp thì giữ số đo + cảnh báo; ghi đè được |
| D5.3 | Khung tỷ lệ lạ | Chấp nhận khoảng trống, không cảnh báo |
| D5.4 | `previewFrame` | Tự chọn theo 10.2; ghi đè được |
| D5.5 | `bleedPx` | 2, ghi rõ |
| D5.6 | Ảnh mẫu | Ghép Fill (chi tiết ở D6) |

**Rủi ro:** khung nghiêng mạnh suốt video → đo sai, dev ghi đè; hai tỷ lệ chuẩn gần nhau (3:2 và 4:3) → có thể làm tròn nhầm, cảnh báo khi lưỡng lự, chỉnh ngưỡng sau lô đầu; `previewFrame` tự chọn chưa chắc đẹp về bố cục → soát ở `review`.

---

## 11. D6 – Ghép poster mẫu + nén `video.mp4` (**đã duyệt 27/11/2026**)

Tạo `video.mp4`: video gốc (khung xanh) → ghép ảnh "YOUR POSTER HERE" vào khung ở từng frame → nén thành file chuẩn cho app. Thumb, preview và thứ user thấy ở màn List đều cắt từ file này.

### 11.1. Trình tự

| Lượt | Làm gì |
|---|---|
| **1: dò** | ffmpeg đọc video gốc thành frame **đã chuẩn hoá** (xoay đúng chiều, ≤ 30 fps, frame đầu ở 0); OpenCV dò 4 góc mọi frame (D4), làm mượt, nới khung, chọn `previewFrame`, `posterRatio` (D5) |
| **2: ghép và nén** | ffmpeg đọc lại video gốc **đúng như lượt 1**; mỗi frame ghép poster mẫu theo quad tương ứng, đẩy thẳng vào ffmpeg nén `video.mp4`, gắn tiếng gốc. **Nén một lần duy nhất** |

Đọc hai lần thay vì giữ frame trong bộ nhớ (10 giây 720p khoảng 800 MB ảnh thô). Hai lượt phải ra cùng số frame, cùng thứ tự: công cụ đếm và so vài frame mẫu (giống hệt từng điểm ảnh), lệch thì dừng.

### 11.2. Ảnh mẫu

**Sửa 27/11/2026 (sau khi nhận ảnh designer):** ảnh designer là **3:4, 850×1134, nền trắng, viền đứt nét bo góc sát mép, chữ "YOUR POSTER HERE"** (khác yêu cầu cũ: vuông, nền phủ kín, chữ trong 50% giữa). Ghép Fill vào khung khác 3:4 sẽ cắt mất viền, khung 16:9 mất cả chữ. Chốt: **công cụ tự dựng ảnh mẫu theo đúng tỷ lệ `posterRatio` của từng template**: nền trắng, viền đứt nét bo góc sát mép khung (thông số đo từ bản thiết kế, quy theo cạnh ngắn), biểu tượng + chữ đặt giữa, thu vừa. Biểu tượng + chữ xin designer bản PNG độ phân giải cao (`assets/sample_poster_content.png`); trong lúc chờ cắt tạm từ ảnh 850 px và cảnh báo. Chữ dùng đúng ảnh designer: **"YOUR POSTER HERE"**.

**Chuẩn bị cho từng template:** dựng theo `posterRatio` (không méo, không cắt); cỡ khoảng **lần to nhất khung xuất hiện trong video** (như ảnh bake K9.2). **App ở Choose Poster (K10.11) phải vẽ ảnh mặc định giống hệt quy tắc này** (cần sửa plan app, đang ghi Fill).

### 11.3. Ghép vào từng frame

| Chi tiết | Cách | Vì sao |
|---|---|---|
| Biến dạng | Homography ảnh mẫu (chữ nhật) → **quad đã nới**, đúng công thức app (K2) | Khớp cách app đè poster của user |
| Phủ kín | Toàn bộ tứ giác, không mặt nạ xanh (D2.3) | Chữ / dấu trong vùng xanh không lộ |
| Mép | Làm mịn khoảng 1 px, như K3.5 | Không răng cưa; app đè `bleedPx` 2 che hết mép |
| Ánh sáng | **Dán phẳng**, không bóng / phản chiếu / chỉnh màu theo cảnh | App dán poster của user phẳng (PA1); màn List không được "hứa" đẹp hơn thứ user nhận được |

### 11.4. Khử hắt sáng xanh

Bật **khi đo thấy ám xanh** (D4 đo viền nhoè), ở **dải hẹp khoảng 4–8 px ngoài quad**: giảm thành phần xanh lá xuống bằng mức đỏ / xanh dương (ám xanh thành xám trung tính). **Tắt được trong sổ ghi** (viền thật của biển vốn màu xanh).

### 11.5. Nén

| Thông số | Chọn |
|---|---|
| Codec | H.264, yuv420p |
| Chất lượng | Cao, cố định theo chất lượng (khoảng CRF 18), chế độ nén chậm (app nén lại một lần nữa khi xuất video của user, K5); 720p 10 giây khoảng 5–8 MB |
| Nhịp | Giữ fps gốc nếu ≤ 30; > 30 về 30; VFR về nhịp cố định |
| Keyframe | Mỗi giây một keyframe (K10.7) |
| Bắt đầu | Frame đầu ở 0 |
| Xoay | Xoay thật các điểm ảnh, bỏ cờ xoay |
| Độ phân giải | Giữ nguyên gốc (hiện ≤ 720p) |
| Thời lượng | Giữ nguyên (D2) |
| Nhãn màu | Ghi rõ chuẩn màu (BT.709, dải TV) như video gốc, tránh lệch màu giữa các máy |
| **Tiếng** | **Giữ tiếng gốc** (chốt 27/11/2026): AAC thì chép nguyên; định dạng khác thì nén lại AAC; không có tiếng thì để không có |
| Mục lục mp4 | Đưa lên đầu file |

### 11.6. Kiểm tra ngay sau khi nén

| Kiểm tra | Lệch thì |
|---|---|
| Số frame `video.mp4` = số frame lượt 1 = số quad (nhóm B) | **Dừng**, báo lỗi |
| Frame đầu ở 0, không cờ xoay, đúng kích thước / fps | Dừng, báo lỗi |
| Thời lượng hình và tiếng khớp | Cảnh báo |

### 11.7. Các điểm chốt D6

| # | Điểm | Chốt |
|---|---|---|
| D6.1 | Trình tự | Hai lượt đọc giống hệt (dò; ghép + nén); so số frame và vài frame mẫu |
| D6.2 | Ảnh mẫu | **Sửa 27/11/2026:** "YOUR POSTER HERE", nền trắng, viền đứt nét; công cụ tự dựng theo tỷ lệ; biểu tượng + chữ xin designer bản độ phân giải cao |
| D6.3 | Chuẩn bị ảnh mẫu | **Sửa 27/11/2026:** dựng theo `posterRatio` (thay Fill), cỡ theo lần to nhất của khung; app K10.11 vẽ giống hệt |
| D6.4 | Ghép | Homography vào quad đã nới, phủ kín, mép mịn khoảng 1 px, dán phẳng |
| D6.5 | Khử hắt sáng | Khi đo thấy ám xanh, dải 4–8 px ngoài quad, tắt được |
| D6.6 | Nén | H.264 yuv420p, khoảng CRF 18, fps ≤ 30, keyframe mỗi giây, frame đầu ở 0, xoay thật, giữ độ phân giải / thời lượng, nhãn màu, mục lục ở đầu |
| D6.7 | Tiếng | **Giữ tiếng gốc** (AAC chép nguyên; khác thì nén AAC; không có thì để không có) |
| D6.8 | Kiểm tra sau nén | Số frame khớp số quad, frame đầu ở 0, không cờ xoay, đúng kích thước / fps; lệch thì dừng |

**Rủi ro:**
- Hai lượt đọc ra khác nhau (video VFR) → quad gán nhầm frame; đã so số frame + vài frame mẫu.
- Nhãn màu sai → poster mẫu lệch màu; soát ở `review`, V0 của app cũng kiểm tra màu.
- Khử hắt sáng ăn vào viền thật màu xanh → tắt trong sổ ghi.
- Ảnh mẫu tạm khác ảnh thật → build lại khi có ảnh của designer (trước `publish`).
- Tiếng gốc: giấy phép đi cùng giấy phép video (L4, cột nguồn / giấy phép trong sổ kiểm kê).

---

## 12. D7 – Kiểm chứng bằng mắt (**đã duyệt 27/11/2026**)

Trả lời: "nếu user đặt poster vào template này, video có lỗi gì không?" Lỗi cần bắt: lộ viền poster mẫu / xanh quanh poster của user; rung, trôi, lệch frame; méo (`posterRatio` sai); nới đè lên viền thật của biển / màn hình.

### 12.1. Hai loại soát, làm cả hai

| Loại | Thấy được | Không thấy |
|---|---|---|
| **Giả lập app**: poster bàn cờ đè lên quad, nới thêm `bleedPx` 2, mép mịn 1 px, đúng phép toán app | Đúng thứ user sẽ thấy: lộ viền, méo, rung | Quad lệch vào / ra bao nhiêu px |
| **Viền quad**: vẽ viền quad (đã nới) nét mảnh, 4 chấm góc, số frame | Quad bám mép khung, frame nào lệch | Có lộ viền khi đè không |

**Poster bàn cờ:** ô đen trắng tương phản cao (mép rung / lệch thấy ngay); hình tròn ở giữa (méo tỷ lệ thành bầu dục); viền đỏ sát mép (phủ hết chưa); chữ "TOP" ở cạnh trên (lật / xoay nhầm, sai thứ tự góc).

### 12.2. File soát mỗi template

| File | Soát gì |
|---|---|
| Video giả lập app | Lộ viền, rung, trôi |
| Video viền quad (có số frame) | Quad bám mép khung |
| Ảnh tổng hợp khoảng 12 frame (mỗi frame hai bản) | Xem nhanh cả video |
| **Ảnh phóng to 4 góc ×4** ở frame đầu, giữa, cuối, frame chuyển động nhanh nhất | Lỗi 1–2 px không thấy ở cỡ thường |
| Đồ thị toạ độ 4 góc theo thời gian (D4) | Răng cưa là rung, gãy là dò sai |
| Báo cáo tổng | Tên tiếng Anh + 48 bản dịch, nhóm A / B, `posterRatio` (đo và sau làm tròn), `previewFrame`, độ nới, số frame, cảnh báo, thumbnail |

### 12.3. Tự động hỗ trợ (chỉ ra chỗ nên nhìn)

| Kiểm tra | Cảnh báo khi |
|---|---|
| Sót xanh: điểm còn ám xanh ở dải mảnh ngay ngoài mép poster bàn cờ | Có frame vượt ngưỡng (ghi số frame) |
| Rung: dao động nhỏ của góc giữa các frame liền nhau sau làm mượt (nhóm B) | > khoảng 0,5 px |
| Nhảy góc | Góc dịch đột ngột so với frame trước |
| Nới lấn viền thật | Độ nới ≥ khoảng 5 px |

Báo cáo liệt kê frame bị cảnh báo kèm ảnh phóng to của đúng frame đó. Ngưỡng chỉnh sau lô đầu (cảnh có màu xanh sát khung có thể báo sai).

### 12.4. Cách xem

**Trang HTML** mỗi template (mọi ảnh, đồ thị, video, tên, cảnh báo trên một trang, mở bằng trình duyệt); khi chạy cả lô có **trang mục lục** (thumbnail, số cảnh báo, trạng thái; **template có cảnh báo lên đầu**). Tua từng frame bằng VLC (phím `E`) hoặc mpv; ghi trong README (trình phát mặc định của Windows không tua từng frame được). Báo cáo nằm trong `out/`, không vào git.

### 12.5. Đánh dấu "đã soát"

- Đánh dấu trong **sổ ghi** (ngày, ghi chú); `publish` chỉ nhận template đã soát (D1).
- **Đánh dấu hàng loạt được** (chốt 27/11/2026): một lệnh đánh dấu nhiều / tất cả template đã build. Công cụ in danh sách sẽ được đánh dấu kèm **số cảnh báo** của từng cái, hỏi xác nhận một lần.
- Dấu gắn với **mã băm các file ra** lúc đánh dấu: `build` lại thì dấu tự mất, phải soát lại (tránh soát bản cũ rồi publish bản mới).

### 12.6. Độ chính xác của giả lập

Công cụ (CPU, Python) và app (GPU, shader K3) cùng công thức (homography, nới theo K2.5, mép mịn theo K3.5) nhưng có thể lệch dưới 1 px do làm tròn; chấp nhận nhờ dư nới (D4) + `bleedPx` 2. **V0 của app** đối chiếu lần cuối: render cùng template bằng app thật với poster bàn cờ, so với video giả lập của công cụ.

### 12.7. Các điểm chốt D7

| # | Điểm | Chốt |
|---|---|---|
| D7.1 | Loại soát | Cả hai: giả lập app (bàn cờ + `bleedPx` 2) và viền quad |
| D7.2 | Poster bàn cờ | Ô đen trắng, hình tròn giữa, viền đỏ sát mép, chữ "TOP" cạnh trên |
| D7.3 | File soát | Như 12.2 |
| D7.4 | Tự động hỗ trợ | Sót xanh, rung > 0,5 px, nhảy góc, nới gần trần; kèm ảnh phóng to |
| D7.5 | Cách xem | Trang HTML mỗi template + trang mục lục (có cảnh báo lên đầu); VLC / mpv |
| D7.6 | Đã soát | Trong sổ ghi, **đánh dấu hàng loạt được** (xác nhận một lần, có số cảnh báo); gắn mã băm file ra; `publish` chỉ nhận template đã soát |
| D7.7 | Độ chính xác | Đúng công thức app; lệch dưới 1 px chấp nhận; V0 của app đối chiếu |

**Rủi ro:** đánh dấu hàng loạt dễ bỏ sót template có lỗi nhỏ → trang mục lục đưa template có cảnh báo lên đầu, danh sách xác nhận hiện số cảnh báo; kiểm tra sót xanh báo sai khi cảnh có màu xanh sát khung; báo cáo vài MB mỗi template (trong `out/`).

---

## 13. D8 – Thumb và preview (**đã duyệt 27/11/2026**)

Hai file nhẹ cho màn List, đều **cắt từ `video.mp4` đã ghép và đã nén** (user thấy đúng poster mẫu ở mọi nơi). Nằm trên Firebase và trong pack `video_template_pack` (K1.15).

### 13.1. `thumb.webp`

| Chi tiết | Chốt | Vì sao |
|---|---|---|
| Frame | `previewFrame`, **đọc lại từ file `video.mp4` đã nén** (không dùng frame trong bộ nhớ trước khi nén) | App chụp frame này từ chính `video.mp4` để thay ảnh nhỏ bằng ảnh nét (K10.7); hai ảnh chỉ khác độ nét |
| Tỷ lệ | Giữ nguyên tỷ lệ video, không cắt, không thêm chữ / viền (K10.5) | Quy đổi toạ độ bằng một tỷ lệ (K10.6) |
| Kích thước | **Rộng 540 px** (nửa màn 1080 px, một ô lưới 2 cột); chiều cao theo tỷ lệ; gốc nhỏ hơn thì giữ nguyên, không phóng to | Đủ nét cho ô lưới; ảnh nền tạm ở Choose Poster hơi mờ vài giây (chấp nhận) |
| Định dạng | WebP có nén, chất lượng khoảng 80 (khoảng 30–60 KB) | |

### 13.2. `preview.mp4`

| Chi tiết | Chốt |
|---|---|
| Nguồn | `video.mp4` (đã có poster mẫu) |
| Kích thước | Cạnh ngắn **360 px** (640×360 hoặc 360×640) |
| Thời lượng | Giữ nguyên |
| Codec | H.264, cấu hình tương thích rộng; BT.709; mục lục mp4 ở đầu |
| **Tiếng** | **Bỏ** (chốt 27/11/2026): preview ở List luôn im lặng (đã sửa K11.10 / P7 của plan app thành "báo PO"). Không đảo ngược được cho template đã upload |

### 13.3. Giảm dung lượng preview

Pack được tải ngầm cho **mọi user** (K1.15), nên preview phải nhẹ.

| # | Chỗ giảm | Mức giảm ước lượng | Chốt |
|---|---|---|---|
| 1 | Bỏ tiếng | 15–20% | **Làm** |
| 2 | Chất lượng nén (CRF) | Mỗi +2 bậc khoảng 20–25% | **Khoảng 28**, soát bằng mắt |
| 3 | Chế độ nén chậm hơn | 5–10% | **Làm** (chỉ tốn thời gian build) |
| 4 | Giãn keyframe | 5–15% | **Mỗi 2 giây** |
| 5 | Giảm fps | 10–15% | **fps > 24 thì về 24** (preview chỉ để xem; quy tắc fps của K2 chỉ áp dụng cho `video.mp4`) |
| 6 | Giảm kích thước (360 → 320) | khoảng 20% | **Không**, giữ 360 |
| 7 | Khử nhiễu nhẹ trước khi nén | 5–20% | **Làm, mức nhẹ** |
| 8 | Giới hạn dung lượng cứng (nén hai lượt) | Không vượt trần | **Không**; chỉ cảnh báo |
| 9 | H.265 / AV1 | 30–50% | **Không** (không phải máy nào cũng giải mã phần cứng) |
| 10 | Cắt ngắn preview | khoảng 50% | **Không**, giữ trọn thời lượng |

**Mục tiêu:** khoảng **0,25–0,4 MB / 10 giây**; pack 20 template khoảng **6–8 MB**. Preview > khoảng 0,6 MB thì cảnh báo; template nào vỡ khối (cảnh chuyển động nhiều) thì hạ CRF riêng trong sổ ghi. Tham số nén preview nằm ở một chỗ cấu hình, ghi đè được theo template.

### 13.4. Kiểm tra

| Kiểm tra | Lệch thì |
|---|---|
| Thumb: tỷ lệ khớp video (sai lệch làm tròn dưới 0,5%) | Dừng |
| Thumb đúng là frame `previewFrame` đọc từ `video.mp4` | Dừng |
| Preview: thời lượng khớp `video.mp4`, đúng kích thước, **không có tiếng** | Dừng |
| Preview > khoảng 0,6 MB | Cảnh báo |

### 13.5. Các điểm chốt D8

| # | Điểm | Chốt |
|---|---|---|
| D8.1 | Nguồn | Cắt từ `video.mp4` đã ghép, đã nén |
| D8.2 | `thumb.webp` | `previewFrame` đọc lại từ `video.mp4`; giữ tỷ lệ; **rộng 540 px**; WebP khoảng 80 |
| D8.3 | `preview.mp4` | Cạnh ngắn 360, giữ thời lượng, H.264 tương thích rộng, BT.709, mục lục ở đầu, **không tiếng** |
| D8.4 | Giảm dung lượng | Bỏ tiếng, CRF khoảng 28, nén chậm, keyframe 2 giây, fps > 24 về 24, khử nhiễu nhẹ |
| D8.5 | Không làm | Dưới 360, giới hạn cứng, H.265 / AV1, cắt ngắn |
| D8.6 | Mục tiêu | 0,25–0,4 MB / 10 giây; > 0,6 MB cảnh báo |
| D8.7 | Kiểm tra | Như 13.4 |
| D8.8 | Hệ quả app | K11.10: preview im lặng; P7 đổi thành "báo PO" (đã sửa plan app) |

**Rủi ro:** CRF 28 với cảnh chuyển động nhiều có thể vỡ khối (soát, hạ CRF riêng); khử nhiễu quá tay làm cảnh bệt (giữ nhẹ); preview im lặng không đảo ngược được cho template đã upload; số template tăng lên 50–100 thì pack vượt 20–40 MB, nên xem lại việc chỉ đưa một phần template vào pack.

---

## 14. D9 – Ghi `placeholder.json` và catalog (**đã duyệt 27/11/2026**)

Định dạng đã chốt ở plan app (8.4, 8.19). D9 quyết định công cụ ghi ra thế nào cho đúng, ổn định, dễ soát.

### 14.1. `placeholder.json` (mỗi template, tạo lúc `build`)

| Trường | Giá trị |
|---|---|
| `video.width`, `video.height`, `video.fps` | Từ video đã chuẩn hoá (D5); fps có thể lẻ (29.97) nếu gốc vậy |
| `posterRatio` | `w`, `h`: tỷ lệ chuẩn ghi **số nguyên** (3, 4); không khớp tỷ lệ chuẩn thì `w` = tỷ lệ đo được (2 chữ số), `h` = 1. App đọc dạng số thực (đã ghi chú ở plan app, bảng trường K1) |
| `previewFrame` | Chỉ số frame (D5) |
| `bleedPx` | 2 |
| `quads` | 1 phần tử (nhóm A) hoặc đúng số frame (nhóm B); mỗi phần tử `tl`, `tr`, `br`, `bl`, mỗi góc `[x, y]`, 2 chữ số thập phân |

**Cách ghi:** mỗi quad một dòng (đọc được bằng mắt, 300 frame khoảng 30 KB); thứ tự trường cố định; UTF-8. Cùng dữ liệu ghi lại ra **y hệt từng byte**, để dấu "đã soát" (gắn mã băm, D7) không mất vô cớ.

### 14.2. `catalog.json` (một file chung, tạo lúc `publish`)

| Trường | Lấy từ |
|---|---|
| `name` | Sổ ghi (D1.5) |
| `videoRatio` | Kích thước video chia ước chung lớn nhất (1280×720 → 16:9, 720×1080 → 2:3, 1280×672 → 40:21) |
| `durationMs` | Thời lượng **hình** thật trong `video.mp4`, số nguyên ms (không lấy thời lượng tiếng) |
| `titles` | Tên tiếng Anh + bản dịch từ sổ ghi (D1.4) |

**Thành phần:** template đã publish + template đang publish trong lượt này; template mới build chưa publish thì chưa có. Thứ tự theo danh sách trong sổ ghi, mới lên đầu (D1.12). **Ẩn / gỡ template: chưa xét lúc này.**

**Cách ghi:** UTF-8, không chuyển chữ thành `\u....`, thứ tự trường cố định, có xuống dòng (xem khác biệt dễ). Ghi vào `out/` để dev **xem trước** (D10). **Lưu bản catalog đã publish vào repo công cụ** (lịch sử git). `publish` có chế độ **chỉ cập nhật catalog** (sửa bản dịch, đổi thứ tự) mà không upload lại thư mục template.

### 14.3. Danh sách ngôn ngữ

| Nguồn | Khi nào |
|---|---|
| Đọc `locales_config.xml` của repo app qua **đường dẫn cấu hình cục bộ** (không vào git, mỗi người tự đặt) | Mặc định |
| Bản sao danh sách trong repo công cụ | Không tìm thấy repo app |
| Hai nguồn khác nhau | **Cảnh báo** (app có thể đã thêm ngôn ngữ, cần dịch bổ sung) |

Thêm ngôn ngữ cho template cũ: dịch thêm, publish lại riêng catalog, tăng `catalogVersion`; không đụng thư mục template (D7).

### 14.4. Sửa plan app cho khớp

K16.7 (quy trình dịch tên) đã sửa: AI đặt tên và dịch trong lúc `build`, sửa tay trong sổ ghi, skill `android-i18n-fill` chỉ để soát lại nếu muốn. Bảng trường K1: `posterRatio` là số thực.

### 14.5. Các điểm chốt D9

| # | Điểm | Chốt |
|---|---|---|
| D9.1 | `placeholder.json` | Như 14.1; mỗi quad một dòng; thứ tự trường cố định; UTF-8; ghi lại ra y hệt |
| D9.2 | Thời điểm | `placeholder.json` lúc `build`; `catalog.json` lúc `publish` (xem trước trong `out/`) |
| D9.3 | `catalog.json` | `name`, `videoRatio` (chia ước chung lớn nhất), `durationMs` (thời lượng hình), `titles` |
| D9.4 | Thành phần | Đã publish + đang publish; thứ tự theo sổ ghi, mới lên đầu; ẩn / gỡ chưa xét |
| D9.5 | Định dạng | UTF-8, không `\u....`, thứ tự cố định, xuống dòng |
| D9.6 | Lịch sử | Lưu bản catalog đã publish vào repo công cụ; có chế độ chỉ cập nhật catalog |
| D9.7 | Ngôn ngữ | Đọc `locales_config.xml` của repo app (đường dẫn cấu hình cục bộ); dự phòng bản sao; lệch thì cảnh báo |
| D9.8 | Plan app | Đã sửa K16.7 và ghi chú `posterRatio` số thực |

**Rủi ro:** quên publish lại catalog sau khi sửa bản dịch (dùng chế độ chỉ cập nhật catalog); DTO app đọc `posterRatio` kiểu số nguyên sẽ hỏng với tỷ lệ đo được (đã ghi chú ở plan app); đường dẫn repo app khác nhau giữa các máy (cấu hình cục bộ).

---

## 15. D10 – Kiểm tra toàn bộ trước khi upload (**đã duyệt 27/11/2026**)

Cửa chặn cuối của `publish`: upload rồi không sửa được (D7). Gom các kiểm tra rải ở D4–D9, chia **lỗi (chặn)** và **cảnh báo (không chặn)**.

### 15.1. Chính sách

| Loại | `publish` làm gì |
|---|---|
| **Lỗi** | Luôn chặn |
| Cảnh báo **đã thấy lúc soát** (preview hơi nặng, nới gần trần, tỷ lệ không chuẩn...) | Không dừng: đánh dấu "đã soát" (có số cảnh báo, D7) là đã chấp nhận |
| Cảnh báo **mới phát sinh lúc publish** | Hiện ra, **hỏi xác nhận một lần** |

### 15.2. Lỗi (chặn)

**A. Từng thư mục template**

| # | Kiểm tra |
|---|---|
| A1 | Đúng 4 file đúng tên, không thừa |
| A2 | `placeholder.json` đọc được theo đúng luật của app, và **chặt hơn app**: mọi quad lồi, đúng chiều, đủ lớn; toạ độ trong khung hình (cho lố vài px vì nới) |
| A3 | Số quad = 1 hoặc **đúng bằng** số frame thật của `video.mp4` (đếm lại bằng ffprobe; khớp tuyệt đối, dù app cho lệch ±1) |
| A4 | `video.mp4`: H.264, yuv420p, frame đầu ở 0, không cờ xoay, fps ≤ 30 cố định, kích thước = JSON, có tiếng nếu gốc có |
| A5 | `previewFrame` trong khoảng; `posterRatio` dương, hợp lý; `bleedPx` = 2 |
| A6 | `thumb.webp` đọc được, rộng ≤ 540, tỷ lệ khớp video |
| A7 | `preview.mp4` cạnh ngắn 360, **không tiếng**, thời lượng khớp `video.mp4` |
| A8 | **Đã soát**, dấu khớp mã băm file hiện tại (D7) |
| A9 | `name` hợp lệ. Hỏi thẳng Firebase (không chỉ tin sổ ghi): thư mục đã có **và đã nằm trong catalog** (template đang chạy thật) → **lỗi, chặn** (giữ D7); đã có nhưng **chưa nằm trong catalog** (upload dở lần trước) → **cảnh báo**, upload lại đè (D11.2) |
| A10 | `titles` có `en`; tên tiếng Anh đúng quy định (D1.4) |

**B. Catalog**

| # | Kiểm tra |
|---|---|
| B1 | JSON hợp lệ; `name` không trùng |
| B2 | Mỗi template trong catalog có thư mục trên Firebase hoặc nằm trong lượt publish này |
| B3 | `durationMs` > 0; `videoRatio` số nguyên dương |
| B4 | Thứ tự khớp sổ ghi |

**C. Môi trường**

| # | Kiểm tra |
|---|---|
| C1 | Đã đăng nhập Google, **có quyền ghi** Storage + Realtime DB (thử trước khi upload) |
| C2 | ffmpeg / ffprobe có sẵn |

### 15.3. Cảnh báo mới lúc publish (hỏi xác nhận một lần)

| # | Kiểm tra |
|---|---|
| W1 | Thiếu bản dịch ở ngôn ngữ nào (sẽ hiện tên tiếng Anh, K16.6) |
| W2 | Danh sách ngôn ngữ của repo app khác bản sao (D9.7) |
| W3 | Không tìm thấy repo app, đang dùng bản sao danh sách ngôn ngữ |
| W4 | **Cột nguồn / giấy phép trống hoặc "chưa rõ"** (chốt 27/11/2026: cảnh báo, không chặn) |

### 15.4. Nguồn và giấy phép

Ghi ở **sổ kiểm kê** (D2) trong repo công cụ, theo **video nguồn** (một video nguồn có thể sinh nhiều template; sổ ghi của template trỏ về video nguồn qua mã băm). **Ghi chép nội bộ**, không lên Firebase, không vào app.

| Phần | Ví dụ |
|---|---|
| Nguồn (kho video / trang web) | Pexels |
| Mã hoặc link video trên kho | `pexels.com/video/990981` |
| Loại giấy phép | "Miễn phí, dùng thương mại, không cần ghi nguồn" |
| Ngày kiểm tra | 27/11/2026 |
| Người xác nhận | Designer / dev |

Lấy từ designer (video tải từ đâu); tên file bắt đầu bằng dãy số có thể là mã video trên kho. Video nguồn không nhớ được nguồn thì ghi "chưa rõ" (publish chỉ cảnh báo). Cần ghi để gỡ đúng template nếu sau này phát hiện vi phạm.

### 15.5. Chạy thử và báo cáo

- **Chạy thử:** chạy toàn bộ A–C và W, in **kế hoạch** mà không upload: template sẽ upload, catalog mới (trong `out/`) khác bản cũ ở đâu, `catalogVersion` từ bao nhiêu lên bao nhiêu, file xuất cho pack.
- `publish` thật **chạy lại toàn bộ kiểm tra**, không dùng kết quả lần chạy thử.
- Mỗi lần publish thật lưu **báo cáo** (thời điểm, template, kết quả kiểm tra, cảnh báo đã xác nhận) vào repo công cụ cùng bản catalog (D9.6).

### 15.6. Các điểm chốt D10

| # | Điểm | Chốt |
|---|---|---|
| D10.1 | Lỗi | Luôn chặn: A (thư mục), B (catalog), C (môi trường) |
| D10.2 | Cảnh báo đã thấy lúc soát | Không dừng |
| D10.3 | Cảnh báo mới lúc publish | Hỏi xác nhận một lần (W1–W4) |
| D10.4 | Số quad | Khớp tuyệt đối số frame thật |
| D10.5 | Tên trên Firebase | Hỏi thẳng Firebase |
| D10.6 | Quyền ghi | Thử trước khi upload |
| D10.7 | Giấy phép | Ghi ở sổ kiểm kê; trống / "chưa rõ" thì **cảnh báo**, không chặn |
| D10.8 | Chạy thử | Toàn bộ kiểm tra + kế hoạch, không upload |
| D10.9 | Báo cáo | Lưu báo cáo publish thật vào repo công cụ |

**Rủi ro:** kiểm tra quá chặt chặn nhầm (chỉnh ngưỡng sau lô đầu, báo lỗi nói rõ lý do và vị trí); giấy phép chỉ cảnh báo nên có thể publish video chưa rõ nguồn (báo cáo publish ghi lại để tra sau); khoảng giữa chạy thử và chạy thật có người khác upload (chạy thật kiểm tra lại toàn bộ).

---

## 16. D11 – Upload và pack (**đã duyệt 27/11/2026**)

`publish` là **chỗ duy nhất chạm Firebase**. Template chỉ thật sự "lên app" khi **có tên trong catalog** và `catalogVersion` đã tăng.

### 16.1. Thứ tự (hỏng ở bước nào cũng an toàn)

| Bước | Làm gì | Hỏng ở bước này thì |
|---|---|---|
| 1 | Upload 4 file của từng template lên `<appId>/templates/video_templates/<name>/` | Chưa trong catalog, user không thấy. Chạy lại: cảnh báo "upload dở", upload lại đè |
| 2 | Kiểm tra từng file đã lên đủ (so dung lượng + mã băm) | Như bước 1 |
| 3 | Upload `catalog.json` mới (đè bản cũ; catalog vốn thay mỗi lần publish) | App cũ chưa tải (version chưa tăng); user mới cài có thể tải nhưng file template đã đủ. Chạy lại: đi tiếp |
| 4 | **Tăng `catalogVersion`** trên Realtime DB, **làm cuối cùng** ("công tắc" công bố, K1.13) | Chạy lại: tăng |
| 5 | Xuất thumb + preview cho pack vào `out/pack/templates/video_templates/<name>/` | Không ảnh hưởng user |
| 6 | Cập nhật sổ ghi (đã publish, ngày, `catalogVersion`); lưu bản catalog + báo cáo vào repo công cụ (D9.6, D10.9) | Không ảnh hưởng user |

Chuẩn bị xong hết (1–3) rồi mới công bố bằng **một thao tác** (4). Mỗi bước chạy lại được, không tạo bản trùng, không tăng `catalogVersion` hai lần cho cùng nội dung.

### 16.2. Upload dở và template đang chạy

| Tình huống | Xử lý |
|---|---|
| Thư mục có trên Firebase, **chưa trong catalog** (upload dở) | **Cảnh báo**, upload lại đủ 4 file đè lên, đi tiếp. Không vi phạm D7 vì chưa user nào nhận bản dở |
| Thư mục có trên Firebase **và đã trong catalog** (template đang chạy) | **Chặn, giữ D7** (chốt 27/11/2026): không bao giờ upload đè. User đã tải bản cũ sẽ dùng bản cũ mãi, user mới nhận bản mới. Template lỗi thì làm template mới với `name` mới |

### 16.3. Chi tiết upload

| Chi tiết | Chốt |
|---|---|
| Loại file | `video/mp4`, `application/json`, `image/webp` |
| Lưu đệm `catalog.json` | **Không** (cùng đường dẫn bị thay mỗi lần publish) |
| Lưu đệm file template | Lâu (không bao giờ đổi, D7) |
| Đường dẫn / khoá | `<appId>/templates/video_templates/`, `video_template_catalog_version` (K1) — **xác nhận với team**; ghi cả hai vào **một file cấu hình** của công cụ, đối chiếu với code app ở V0 |
| Đăng nhập | `gcloud` bằng tài khoản dev (D1.10); quyền ghi Storage + Realtime DB cần hỏi team (D10 C1 thử trước) |
| Lần đầu | Có thể upload tay qua Firebase Console theo **đúng thứ tự** 16.1 |

### 16.4. Pack

`publish` xuất thumb + preview của **mọi template đã publish** ra `out/pack/...` đúng cấu trúc K1.15. Trước mỗi lần **phát hành app**, chép sang `video_template_pack/src/main/assets/` của repo app (hoặc công cụ chép thẳng nếu có đường dẫn cấu hình tới repo app, D9.7). Pack chỉ có ích cho template có lúc phát hành app; template thêm sau chỉ cần Firebase. Đưa "chép pack" vào checklist phát hành app.

### 16.5. Các điểm chốt D11

| # | Điểm | Chốt |
|---|---|---|
| D11.1 | Thứ tự | File template → kiểm tra đủ → `catalog.json` → **tăng `catalogVersion` cuối** → xuất pack → cập nhật sổ ghi, lưu catalog + báo cáo |
| D11.2 | Upload dở (chưa trong catalog) | Cảnh báo, upload lại đè, đi tiếp |
| D11.3 | Template đang chạy (đã trong catalog) | **Chặn, giữ D7** |
| D11.4 | Kiểm tra sau upload | Dung lượng + mã băm từng file |
| D11.5 | Siêu dữ liệu | Đúng loại file; catalog không lưu đệm; file template lưu đệm lâu |
| D11.6 | Firebase | Đường dẫn + khoá trong một file cấu hình, xác nhận với team; `gcloud` |
| D11.7 | Pack | Xuất `out/pack/...`; chép sang repo app trước khi phát hành |
| D11.8 | Lần đầu | Có thể tay qua Console theo đúng thứ tự |

**Rủi ro:** quyền ghi Firebase chưa rõ (hỏi team); đường dẫn / tên khoá lệch với code app thì app không thấy template (một file cấu hình, đối chiếu ở V0); quên chép pack trước khi phát hành app (template vẫn chạy qua Firebase, chỉ tốn dữ liệu user).

---

## 17. Tổng kết (27/11/2026)

**Đã duyệt toàn bộ D1–D11** (D3 gộp vào D1). Bước tiếp theo: chuyển file này sang **repo công cụ riêng**, rồi bắt đầu code theo thứ tự mục 6 (làm trọn vẹn 1–2 video nhóm A trước). Bộ data đầu tiên cũng là dữ liệu thật cho **V0 spike** của plan app.

**Việc cần làm trước / song song khi code:**

| # | Việc | Hỏi ai |
|---|---|---|
| 1 | ~~Ảnh mẫu~~ đã nhận 27/11/2026 (3:4, 850 px); còn xin **biểu tượng + chữ "YOUR POSTER HERE" bản PNG độ phân giải cao** (D6.2) | Designer |
| 1b | Sửa plan app K10.11: Choose Poster vẽ ảnh mặc định theo quy tắc dựng của công cụ (không Fill) | Dev |
| 2 | Nguồn và giấy phép từng video (D10.7, sổ kiểm kê) | Designer |
| 3 | Quyền ghi Firebase Storage + Realtime DB; xác nhận đường dẫn `<appId>/templates/video_templates/` và khoá `video_template_catalog_version` | Team |
| 4 | Báo PO: preview ở màn List im lặng (D8) | PO |
| 5 | Tải toàn bộ video về một thư mục trên máy (ngoài repo) để chạy `inspect` | Dev |
