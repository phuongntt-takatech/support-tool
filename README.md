# Support Tool

## Tổng quan

Repository này tập hợp các công cụ hỗ trợ cho quá trình phát triển và vận hành sản phẩm. Mỗi công cụ được đặt trong một thư mục riêng, kèm hướng dẫn cài đặt và sử dụng chi tiết.

## Mục lục

- [1. Search tool — tạo metadata tìm kiếm cho PosterMaker](#1-search-tool--tạo-metadata-tìm-kiếm-cho-postermaker)

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