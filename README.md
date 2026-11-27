# Support Tool

## Tổng quan

Repository này tập hợp các công cụ hỗ trợ cho quá trình phát triển và vận hành sản phẩm. Mỗi công cụ được đặt trong một thư mục riêng, kèm hướng dẫn cài đặt và sử dụng chi tiết.

## Mục lục

- [1. Search tool — tạo metadata tìm kiếm cho PosterMaker](#1-search-tool--tạo-metadata-tìm-kiếm-cho-postermaker)
- [2. Bundletool — build và cài ứng dụng Android](#2-bundletool--build-và-cài-ứng-dụng-android)
- [3. Video Template data tool — tạo data Video Template cho PosterMaker](#3-video-template-data-tool--tạo-data-video-template-cho-postermaker)

## 1. Search tool — tạo metadata tìm kiếm cho PosterMaker

`populate-templates-meta` là công cụ Node.js tạo, kiểm tra và publish metadata tìm kiếm cho các template của ứng dụng **Poster Maker Android**. Đây là công cụ chuẩn bị dữ liệu để ứng dụng có thể tìm và phân loại template; không phải giao diện tìm kiếm trong ứng dụng.

Công cụ đọc template và ảnh preview, sau đó tạo metadata gồm tên hiển thị, màu sắc, phong cách, hướng ảnh, tags và các cụm chữ xuất hiện trên poster (`searchContent`). Gemini hỗ trợ tạo tên, tags và bản dịch cho nhiều ngôn ngữ; code lọc các dòng chữ giữ chỗ và kiểm tra kết quả để `searchContent` chỉ chứa nội dung lấy từ template. Metadata được tạo thành draft để kiểm tra trước khi publish lên Firebase.

Quy trình chính:

1. **Generate:** tạo draft metadata, mặc định nhắm tới môi trường debug.
2. **Review:** xem báo cáo HTML/CSV, rà soát và chỉnh draft nếu cần.
3. **Publish:** publish draft lên Firebase sau bước xác nhận; production có thêm điều kiện bảo vệ.
4. **Check:** kiểm tra tính nhất quán giữa metadata và danh sách template.

Thư mục công cụ: [`populate-templates-meta/`](./populate-templates-meta/)

Hướng dẫn cài đặt, cấu hình, lệnh CLI và quy trình publish: [`populate-templates-meta/README.md`](./populate-templates-meta/README.md).

## 2. Bundletool — build và cài ứng dụng Android

`bundletool` chứa script Windows để build gói cài đặt từ Android App Bundle (`.aab`) và cài lên thiết bị Android đang kết nối. Chạy `push_aab.bat` trong thư mục công cụ.

- Nếu `output.apks` đã tồn tại, script bỏ qua bước build và cài gói đó.
- Nếu chưa có output, script build từ file `.aab` đầu tiên tìm thấy trong thư mục `bundletool`.
- Muốn build AAB khác, xóa `output.apks` cũ và chuyển các AAB không dùng vào thư mục con như `tmp`, chỉ để AAB cần build ở thư mục chính.

Xem yêu cầu chuẩn bị và hướng dẫn chi tiết tại [`bundletool/README.md`](./bundletool/README.md).

## 3. Video Template data tool — tạo data Video Template cho PosterMaker

`video-template-data` là công cụ Python (OpenCV + ffmpeg) biến video phông xanh thành thư mục template cho tính năng **Video Template**: dò 4 góc khung xanh ở mọi frame, ghép poster mẫu "Your poster will appear here", nén `video.mp4`, tạo `placeholder.json`, `thumb.webp`, `preview.mp4`, và nhờ AI đặt tên + dịch sang các ngôn ngữ của app. Có trang HTML để soát bằng mắt (giả lập poster bàn cờ đúng cách app đè) và sổ ghi để cập nhật data về sau.

Thư mục công cụ: [`video-template-data/`](./video-template-data/)

Cài đặt xong thì double-click `video-template-data/menu.bat` để chọn việc bằng số (chép video vào `input/`, kiểm kê, build video mới, soát, đánh dấu). Hướng dẫn chi tiết: [`video-template-data/README.md`](./video-template-data/README.md).
