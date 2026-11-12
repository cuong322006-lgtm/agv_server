# HỒ SƠ BÀN GIAO MÃ NGUỒN VÀ HƯỚNG DẪN PHÁT TRIỂN AI TỰ HÀNH AGV
## (Dành cho Lập trình viên & Trợ lý Antigravity AI)

**Dự án:** Hệ thống Điều khiển, Giám sát Thị giác AI và Bản đồ Radar 2D cho Xe Tự Hành AGV  
**Tập thể phát triển:** Nhóm AGV 2026  
**Thư mục gốc:** `agv_server`  
**Ngày bàn giao:** 03/11/2026  

---

## 1. TỔNG QUAN HIỆN TRẠNG DỰ ÁN

Phần hạ tầng kết nối phần cứng và giao thức mạng cơ bản **ĐÃ HOÀN TẤT 100% VÀ ĐÃ TEST THỰC TẾ ỔN ĐỊNH**:

1. **Khối Thu hình ảnh & Thị giác AI (ESP32-CAM):**
   * Sử dụng cảm biến OV2640, 4MB PSRAM, DMA transfer.
   * Truyền luồng ảnh JPEG HQVGA qua kết nối bảo mật WSS (`/ws/stream_cam`) đạt 12-15 FPS.
   * Cơ chế **Zero-Bufferbloat ACK 'K'**: Server xử lý xong khung hình mới gửi tín hiệu cho phép ESP32-CAM chụp khung tiếp theo, triệt tiêu hoàn toàn hiện tượng trễ hình ảnh (Latency < 50ms).
   * Tự động điều chỉnh độ nén thích ứng băng thông mạng (ABR Quality 12 - 16).
   * Server tích hợp sẵn mô hình YOLOv8 (`yolov8n.pt`) nhận diện người/vật cản và `pyzbar` quét mã vạch/mã QR.

2. **Khối Quét Laser Radar 360° & Động học AGV (ESP32-S3 + YDLidar X2):**
   * Cảm biến YDLidar X2 quét 360 độ, dải đo 0.12m - 8.0m, tần số 3000 mẫu/giây.
   * Thuật toán **Auto-Swap & Auto-Lock UART (GPIO 16/15)**: Tự động đảo chiều chân và kích xung `0xA5 0x60`, tự thích ứng với mọi loại cáp cắm mà không cần chỉnh phần cứng.
   * Đường ống WebSocket Full-Duplex WSS Native (loại bỏ hoàn toàn thư viện ngoài, biên dịch thành công 100% trên Arduino IDE).
   * Chiều nhận lệnh Downlink: Nhận trực tiếp các ký tự điều khiển động học (`W, A, S, D, G, X`) từ Server tức thời với độ trễ < 15ms.

3. **Khối Cấu hình Mạng Thông minh (Smart Wireless Provisioning):**
   * Bộ nhớ Flash NVS (`Preferences`): Lưu tên và mật khẩu Wi-Fi vĩnh viễn, không mất khi tắt ắc quy.
   * Captive Portal DNS cổng 53: Khi không có Wi-Fi quen thuộc, phát AP `AGV_CAM_WIFI` hoặc `AGV_S3_WIFI` (Mật khẩu WPA2: `12345678`). Điện thoại vừa kết nối là **TỰ ĐỘNG BUNG CỬA SỔ CÀI ĐẶT** lên màn hình (không cần gõ 192.168.4.1).
   * Cơ chế **Đồng bộ kép P2P 1-chạm**: Chỉ cần nhập Wi-Fi trên 1 trong 2 ESP, mạch đó tự động gửi HTTP POST `/peer_sync` sang mạch còn lại. Cả 2 cùng lưu vào Flash và cùng kết nối mạng mới.
   * Hỗ trợ nút Xóa mạng đã lưu (`/clear` trên web điện thoại hoặc `#WIFI:CLEAR` từ xa trên Web Dashboard).

---

## 2. CẤU TRÚC THƯ MỤC DỰ ÁN

```text
agv_server/
├── AGENTS.md                  # Hướng dẫn quy tắc cho Antigravity AI
├── HANDOVER_AI_GUIDE.md       # Tài liệu bàn giao chi tiết này
├── README.md                  # Hướng dẫn nhanh tổng quan dự án
├── requirements.txt           # Danh sách thư viện Python cần cài đặt
├── install.bat                # Script 1-click tự động tạo venv và cài thư viện
├── start_server.bat           # Script 1-click khởi chạy FastAPI Server (Port 8000)
├── start_tunnel.bat           # Script 1-click mở đường hầm Cloudflare ra Internet
├── main.py                    # Server FastAPI trung tâm, WebSocket, API và Dashboard HTML
├── vision_ai.py               # Xử lý hình ảnh, YOLOv8, QR Code, Cubic Smoothing
├── slam_mapper.py             # Bộ xử lý dữ liệu Lidar, giải mã 0xAA 0x55, Odometry 2D
├── lidar_tcp_server.py        # Module hỗ trợ Lidar parser
├── run_tunnel_sync.py         # Tự động đồng bộ link Cloudflare Tunnel lên ntfy.sh
├── cloudflared.exe            # Binary Cloudflare Tunnel client
├── yolov8n.pt                 # Trọng số mô hình YOLOv8 Nano đã huấn luyện
├── Báo cáo/                   # Toàn bộ tài liệu báo cáo kỹ thuật dự án
│   ├── Báo cáo Tổng hợp 3 Module ESP32 AGV.doc  # Báo cáo kỹ thuật tổng thể master
│   ├── Báo cáo ESP32 Cam.doc
│   └── Báo cáo ESP32 S3 Lidar.doc
└── firmware/                  # Toàn bộ mã nguồn vi điều khiển ESP32
    ├── esp32_cam_stream/
    │   └── esp32_cam_stream.ino
    └── esp32_s3_lidar/
        └── esp32_s3_lidar.ino
```

---

## 3. CÁC HÀM VÀ BIẾN ĐẦU VÀO ĐỂ LẬP TRÌNH AI

Để phát triển tiếp phần AI, cộng sự chỉ cần làm việc chủ yếu trên mã nguồn Python trong `agv_server`:

### A. Lấy dữ liệu cảm biến Lidar 360° (đối tượng `slam_mapper`):
```python
from slam_mapper import slam_mapper

# 1. Mảng khoảng cách 360 độ (mm):
distances = slam_mapper.polar_dist_mm  # np.ndarray shape (360,), dtype=float32
# Ví dụ: Khoảng cách phía trước xe (góc 0 độ):
front_distance_mm = distances[0]
# Khoảng cách phía bên phải (góc 90 độ):
right_distance_mm = distances[90]
# Khoảng cách phía sau (góc 180 độ):
back_distance_mm = distances[180]
# Khoảng cách phía bên trái (góc 270 độ):
left_distance_mm = distances[270]

# 2. Vị trí ước tính của xe (Odometry):
robot_x = slam_mapper.robot_x_mm       # Tọa độ X (mm)
robot_y = slam_mapper.robot_y_mm       # Tọa độ Y (mm)
robot_angle = slam_mapper.robot_heading_deg  # Góc xoay (độ: 0..360)
```

### B. Lấy dữ liệu Camera & Thị giác máy tính (đối tượng `vision_ai`):
```python
from vision_ai import vision_ai

# 1. Ảnh gốc OpenCV BGR:
frame = vision_ai.latest_raw_frame     # ndarray shape (240, 320, 3)

# 2. Danh sách vật cản phát hiện được từ YOLOv8:
boxes = vision_ai.latest_boxes         # List các tuple (x1, y1, x2, y2, label)
# Ví dụ: [(45, 60, 150, 210, "person 0.89")]

# 3. Mã QR trạm hàng / pallet:
qr_content = vision_ai.latest_qr_data  # Chuỗi text, ví dụ: "STATION_PICKUP_01"
qr_corners = vision_ai.latest_qr_pts   # Tọa độ 4 góc của QR trên ảnh
```

### C. Ra lệnh điều khiển xe di chuyển:
Trong `main.py`, đã có hàm `send_agv_command(cmd: str)`:
```python
# Gọi trong một hàm async bất kỳ:
await send_agv_command('W')  # Tiến
await send_agv_command('S')  # Lùi
await send_agv_command('A')  # Quay trái
await send_agv_command('D')  # Quay phải
await send_agv_command('G')  # Phanh khẩn cấp
await send_agv_command('X')  # Dừng tự do
```

---

## 4. CHI TIẾT 2 NHIỆM VỤ CẦN PHÁT TRIỂN TIẾP

### Nhiệm vụ 1: AI Tự Động Tìm Đường Đến Vị Trí Lấy Hàng (Autonomous Pathfinding)
1. **Tạo bản đồ chiếm chỗ (Occupancy Grid Map):**
   * Chuyển đổi mảng cự ly 360 độ `slam_mapper.polar_dist_mm` sang các ô lưới 2D kích thước `(200, 200)` tương ứng với diện tích phòng `10m x 10m` (mỗi ô 50mm x 50mm).
   * Ô có vật cản gán giá trị `1` (Occupied), ô trống gán giá trị `0` (Free).
2. **Quy hoạch đường đi toàn cục (Global Path Planning):**
   * Sử dụng thuật toán **A* (A-Star)** với hàm heuristic khoảng cách Euclidean.
   * Đầu vào: Vị trí hiện tại của xe `(robot_x, robot_y)` và tọa độ đích `(goal_x, goal_y)`.
   * Đầu ra: Danh sách các điểm waypoint cần đi qua.
3. **Tránh vật cản cục bộ & Điều khiển bám đường (Path Tracking & Collision Avoidance):**
   * Nếu có vật cản đột ngột xuất hiện ở cự ly `< 500mm` phía trước (`distances[350..359]` và `distances[0..10]`): Phát lệnh `'G'` phanh khẩn cấp ngay.
   * Tính toán góc sai lệch `heading_error = target_heading - robot_heading_deg`.
   * Nếu `heading_error > 15°`: Phát lệnh `'A'` (quay trái) hoặc `'D'` (quay phải) để căn chỉnh hướng.
   * Khi góc đã chuẩn: Phát lệnh `'W'` tiến tới waypoint tiếp theo.

### Nhiệm vụ 2: AI Tự Động Bốc Xếp Hàng (Docking & Cargo Handling)
1. **Nhận diện và tiếp cận pallet:**
   * Sử dụng Camera để tìm mã QR dán trên kệ hàng (ví dụ mã chứa nội dung `"SHELF_A_LEVEL_1"`).
   * Tính tâm mã QR: `cx = (qr_corners[0][0] + qr_corners[2][0]) / 2`.
   * Tâm ảnh là `320 / 2 = 160`.
   * Điều khiển vi sai Visual Servoing:
     * Nếu `cx < 150`: Lệch trái $\rightarrow$ phát lệnh quay `'A'`.
     * Nếu `cx > 170`: Lệch phải $\rightarrow$ phát lệnh quay `'D'`.
     * Nếu `150 <= cx <= 170`: Đang thẳng hướng $\rightarrow$ phát lệnh tiến `'W'`.
2. **Kích hoạt cơ cấu nâng hạ:**
   * Khi cự ly Lidar phía trước đạt ngưỡng dừng cập bến (ví dụ `front_distance_mm <= 150mm`): Phát lệnh dừng `'G'`.
   * Gửi tín hiệu kích hoạt nâng càng hoặc gắp hàng (có thể bổ sung ký tự lệnh mới như `'U'` - Up / `'J'` - Down trong firmware ESP32-S3).

---

## 5. HƯỚNG DẪN CÀI ĐẶT TRÊN MÁY TÍNH CỘNG SỰ

Khi chuyển toàn bộ thư mục `agv_server` sang máy tính mới:
1. Đảm bảo máy tính đã cài đặt **Python 3.10, 3.11 hoặc 3.12** (chọn tick *"Add python.exe to PATH"* khi cài đặt).
2. Mở thư mục dự án và nhấp đúp vào tệp:
   `install.bat`
   *Tập lệnh sẽ tự tạo thư mục môi trường ảo `venv` cục bộ trên máy mới và tự cài đặt toàn bộ thư viện cần thiết.*
3. Khi cài đặt xong, nhấp đúp vào:
   `start_server.bat`
4. Mở trình duyệt truy cập `http://localhost:8000` để bắt đầu thử nghiệm và phát triển các module AI!

---

## 6. LỘ TRÌNH ĐÓNG GÓI .EXE SAU KHI HOÀN THIỆN
Sau khi nhóm hoàn thiện xong 2 module AI (tìm đường và bốc hàng), chúng ta sẽ sử dụng công cụ **PyInstaller** kết hợp **Inno Setup** để đóng gói toàn bộ server Python thành 1 file thực thi duy nhất:
`AGV_Setup_v1.0.exe`
Người dùng cuối chỉ cần click Next để cài đặt mà không cần cài Python hay chạy bất kỳ dòng lệnh nào.
