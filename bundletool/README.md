# Bundletool

## Mục đích

Thư mục này chứa script `push_aab.bat` để tạo gói APK có thể cài trực tiếp từ file Android App Bundle (`.aab`), sau đó cài gói đó lên thiết bị Android đang kết nối. Script dùng `bundletool.jar` và tùy chọn `--local-testing`.

## Chuẩn bị

- Windows, Java có thể chạy bằng lệnh `java` trong Command Prompt/PowerShell.
- `bundletool.jar` nằm trong thư mục `bundletool`.
- File `.aab` muốn cài nằm trực tiếp trong thư mục `bundletool` (không nằm trong thư mục con).
- Thiết bị Android đã kết nối và được `adb` nhận diện.

Script hiện trỏ tới ADB tại `C:\Users\Dell\AppData\Local\Android\Sdk\platform-tools\adb.exe`. Nếu Android SDK trên máy nằm ở vị trí khác, sửa giá trị `ADB_PATH` trong `push_aab.bat` cho đúng.

## Cách chạy

1. Đặt file `.aab` cần cài trong thư mục `bundletool`.
2. Kết nối thiết bị Android và chấp nhận lời nhắc cho phép USB debugging nếu có.
3. Chạy `push_aab.bat` (nhấp đúp hoặc chạy từ Command Prompt trong thư mục `bundletool`).
4. Chờ script build/cài đặt và kiểm tra thông báo thành công hoặc lỗi trên cửa sổ.

Khi chưa có `output.apks`, script tìm file `.aab` trong thư mục hiện tại, tạo `output.apks` bằng `bundletool.jar`, rồi cài gói này lên thiết bị.

## Lưu ý về file đầu vào và output

- Nếu đã có `output.apks`, script **bỏ qua bước build** và cài trực tiếp file đó. Vì vậy, `output.apks` cũ có thể khiến script cài bản build trước thay vì file `.aab` mới.
- Nếu có nhiều file `.aab`, script lấy file đầu tiên trong danh sách mà Windows trả về.
- Muốn build một file `.aab` khác: xóa `output.apks` cũ, chỉ để file muốn build trong thư mục `bundletool`; có thể chuyển các file `.aab` còn lại vào thư mục con như `tmp` để script không chọn chúng. Sau đó chạy lại `push_aab.bat`.
- Nếu muốn cài lại đúng gói đã build trước đó, giữ nguyên `output.apks` và chạy script.

Script luôn dùng tên `output.apks` cho gói đầu ra và yêu cầu nhấn phím để đóng cửa sổ sau khi chạy.
