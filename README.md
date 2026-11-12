# HỆ THỐNG ĐIỀU KHIỂN & GIÁM SÁT XE TỰ HÀNH AGV TẬP TRUNG
## DUAL ESP32 (ESP32-CAM + ESP32-S3) + YDLIDAR X2 + FASTAPI + AI YOLOV8

Dự án phát triển hệ thống điều khiển và giám sát xe tự hành AGV với 3 phân hệ công nghệ cốt lõi:
1. **Thị giác Máy tính (ESP32-CAM):** Thu nhận và truyền hình ảnh thời gian thực 12-15 FPS qua WSS (Zero-Bufferbloat ACK 'K', Smart ABR 12-16).
2. **Cảm biến Laser Radar 2D & Động học AGV (ESP32-S3 + YDLidar X2):** Quét 360 độ (3000 pts/s), tự động dò và khóa chân UART (GPIO 16/15) + xung kích 0xA5 0x60, nhận lệnh điều khiển W, A, S, D, G, X qua WSS native.
3. **Cấu hình Wi-Fi Thông minh & Bảo mật:** Bộ nhớ Flash NVS (`Preferences`), Captive Portal DNS cổng 53 tự bung cửa sổ trên điện thoại khi kết nối Wi-Fi `AGV_CAM_WIFI` / `AGV_S3_WIFI` (Pass: `12345678`), đồng bộ P2P 1-chạm giữa 2 bo mạch, và xóa mạng từ xa.

---

## KHỞI CHẠY HỆ THỐNG NHANH (QUICK START)

### 1. Cài đặt môi trường (Chỉ làm 1 lần đầu)
Nhấp đúp chuột vào tệp:
`install.bat`
*(Hệ thống sẽ tự động tạo môi trường ảo Python `venv` và cài đặt đầy đủ tất cả thư viện cần thiết)*

### 2. Khởi động Máy chủ Điều khiển
Nhấp đúp chuột vào tệp:
`start_server.bat`
Mở trình duyệt truy cập:
`http://localhost:8000`

### 3. Mở đường hầm kết nối Internet ra ngoài (Tùy chọn)
Nhấp đúp chuột vào tệp:
`start_tunnel.bat`
*(Hệ thống sẽ mở đường hầm Cloudflare Tunnel bảo mật và tự động phát tên miền lên ntfy.sh cho 2 mạch ESP32)*

---

## HƯỚNG DẪN DÀNH CHO NHÓM PHÁT TRIỂN AI
Vui lòng đọc 2 tài liệu chi tiết trong thư mục:
* `AGENTS.md`: Hướng dẫn chuyên sâu dành riêng cho trợ lý Antigravity AI.
* `HANDOVER_AI_GUIDE.md`: Cẩm nang bàn giao chi tiết các biến, hàm và lộ trình phát triển module Tự động Tìm đường & Bốc xếp hàng.
* `Báo cáo/Báo cáo Tổng hợp 3 Module ESP32 AGV.doc`: Báo cáo kỹ thuật toàn diện của dự án.
