# HƯỚNG DẪN DÀNH CHO ANTIGRAVITY AI (AGENTS.MD)
# DỰ ÁN XE TỰ HÀNH AGV: THỊ GIÁC AI (VISION), RADAR LASER 2D (LIDAR) VÀ ĐIỀU KHIỂN ĐỘNG HỌC

Tài liệu này được biên soạn đặc biệt để bất kỳ trợ lý lập trình Antigravity AI nào khi mở dự án này đều hiểu ngay lập tức toàn bộ kiến trúc, dữ liệu hiện có và cách lập trình tiếp các tính năng AI tự hành.

---

## 1. TỔNG QUAN HỆ THỐNG ĐÃ HOÀN THÀNH (CURRENT STATUS: 100% HARDWARE & PROTOCOL READY)

Hệ thống điều khiển trung tâm Xe Tự Hành AGV bao gồm:
1. **AI-Thinker ESP32-CAM:** Thu nhận hình ảnh quang học từ cảm biến OV2640, đẩy luồng JPEG (HQVGA 240x176) qua WebSocket WSS `/ws/stream_cam` (12-15 FPS, trễ < 50ms nhờ cơ chế Zero-Bufferbloat ACK 'K').
2. **ESP32-S3 Dev Module + YDLidar X2:** Quét laser 360° (3000 mẫu/s, tầm quét 8m), tự động nhận diện chân UART (GPIO 16/15), đẩy dòng byte nhị phân qua WebSocket WSS `/ws/push_lidar`. Đồng thời nhận lệnh điều khiển động học tức thì (`W, A, S, D, G, X`).
3. **Phân hệ Mạng Thông Minh (Smart Provisioning):** Bộ nhớ Flash NVS (`Preferences`), Captive Portal DNS cổng 53 tự bung cửa sổ cài đặt Wi-Fi khi bắt mạng `AGV_CAM_WIFI` hoặc `AGV_S3_WIFI` (Mật khẩu: `12345678`), tự động đồng bộ P2P 1-chạm giữa 2 ESP và hỗ trợ xóa mạng từ xa.
4. **Máy chủ FastAPI (`main.py`):** Xử lý bất đồng bộ, nạp mô hình YOLOv8 (`yolov8n.pt`), giải mã mã vạch/QR (`pyzbar`), xử lý bản đồ Radar 2D (`slam_mapper.py`), và phục vụ giao diện Web Dashboard tại `http://localhost:8000`.

---

## 2. DỮ LIỆU ĐẦU VÀO CÓ SẴN CHO MODULE AI (AI SENSORY INPUTS)

Khi lập trình các thuật toán AI tự hành, bạn lấy dữ liệu trực tiếp từ 2 đối tượng toàn cục đã được khởi tạo trong `main.py`:

### A. Dữ liệu Radar Laser 2D (`slam_mapper` từ `slam_mapper.py`)
* `slam_mapper.polar_dist_mm`: Mảng NumPy 360 phần tử (`np.float32`), lưu khoảng cách thực tế tính bằng milimét (mm) từ tâm xe đến vật cản ở 360 góc quét (từ 0° đến 359°).
  - Góc 0°: Phía trước đầu xe.
  - Góc 90°: Phía bên phải xe.
  - Góc 180°: Phía sau đuôi xe.
  - Góc 270°: Phía bên trái xe.
* `slam_mapper.robot_x_mm`, `slam_mapper.robot_y_mm`: Tọa độ vị trí ước tính của xe trên mặt phẳng 2D (Odometry tính bằng mm).
* `slam_mapper.robot_heading_deg`: Hướng xoay hiện tại của xe (tính bằng độ: 0°..360°).
* `slam_mapper.max_range_mm`: Cự ly quét tối đa (mặc định 5000mm - 5 mét).

### B. Dữ liệu Thị giác Máy tính (`vision_ai` từ `vision_ai.py`)
* `vision_ai.latest_raw_frame`: Khung hình ảnh gốc (OpenCV BGR ndarray, kích thước 320x240).
* `vision_ai.latest_boxes`: Danh sách các vật cản phát hiện được bởi YOLOv8. Mỗi phần tử là tuple: `(x1, y1, x2, y2, label)` ví dụ: `(50, 60, 180, 220, "person 0.88")`.
* `vision_ai.latest_qr_data`: Chuỗi ký tự giải mã được từ mã QR (chuỗi rỗng `""` nếu không có mã QR trong khung hình).
* `vision_ai.latest_qr_pts`: Tọa độ 4 đỉnh của mã QR trên khung hình ảnh để tính toán góc lệch và khoảng cách căn chỉnh xe.

---

## 3. CÁCH ĐIỀU KHIỂN CHUYỂN ĐỘNG XE AGV (KINEMATICS ACTUATION)

Để điều khiển xe di chuyển hoặc dừng, AI chỉ cần gửi ký tự lệnh:
* `'W'`: Tiến thẳng (Forward)
* `'S'`: Lùi lại (Backward)
* `'A'`: Quay trái tại chỗ (Rotate Left)
* `'D'`: Quay phải tại chỗ (Rotate Right)
* `'G'`: Phanh khẩn cấp (Active Emergency Brake)
* `'X'`: Dừng tự do (Coast Stop)

### Cách gọi lệnh trong mã nguồn Python (`main.py`):
```python
# Gửi lệnh trực tiếp xuống ESP32-S3 qua WebSocket đang mở:
await send_agv_command('W')  # Xe tiến
await asyncio.sleep(0.5)      # Chạy trong 500ms
await send_agv_command('G')  # Dừng xe
```
*Lưu ý:* Hàm `send_agv_command(cmd: str)` đã được tích hợp sẵn trong `main.py`, tự động kiểm tra kết nối WebSocket của ESP32-S3 và cập nhật Odometry ước tính cho xe.

---

## 4. NHIỆM VỤ PHÁT TRIỂN TIẾP THEO (AI ROADMAP CHO CỘNG SỰ)

### Nhiệm vụ 1: Module AI Tự Động Tìm Đường (Autonomous Pathfinding & Navigation)
* **Mục tiêu:** Nhận tọa độ đích đến (Goal: `x_goal, y_goal` hoặc mã QR trạm hàng), tự động quy hoạch lộ trình và điều khiển xe di chuyển đến đích mà không va chạm.
* **Đề xuất kỹ thuật:**
  1. Tạo lưới chiếm chỗ (Occupancy Grid Map 2D) từ mảng `slam_mapper.polar_dist_mm`.
  2. Sử dụng giải thuật tìm đường toàn cục (Global Planner): **A* (A-Star)** hoặc **Dijkstra** trên Grid Map để tìm danh sách các điểm nút dẫn đường (Waypoints).
  3. Sử dụng giải thuật tránh vật cản cục bộ (Local Obstacle Avoidance): **Vector Field Histogram (VFH)** hoặc **Dynamic Window Approach (DWA)** để né các vật cản di động (như người đi bộ, chướng ngại vật bất ngờ).
  4. Bộ điều khiển bám đường (Path Tracker): Tính toán sai số góc giữa hướng hiện tại (`robot_heading_deg`) và hướng tới waypoint tiếp theo để tự động phát lệnh `W, A, D`.

### Nhiệm vụ 2: Module AI Tự Động Cập Cảng Bốc Xếp Hàng (Autonomous Docking & Cargo Handling)
* **Mục tiêu:** Khi đến gần trạm lấy hàng (nhận diện qua mã QR dán trên kệ hoặc pallet), AI tự động căn chỉnh góc và cự ly chính xác milimét, sau đó phát tín hiệu bốc dỡ hàng.
* **Đề xuất kỹ thuật:**
  1. **Visual Servoing (Điều khiển dựa trên thị giác):**
     - Dựa vào tâm của mã QR `(qr_center_x, qr_center_y)` trên ảnh:
       - Nếu `qr_center_x < 140`: Phát lệnh `'A'` (quay trái nhẹ).
       - Nếu `qr_center_x > 180`: Phát lệnh `'D'` (quay phải nhẹ).
       - Nếu `140 <= qr_center_x <= 180`: Xe đang nhìn thẳng vào tâm pallet, phát lệnh `'W'` tiến tới.
     - Dựa vào diện tích khung QR hoặc cự ly Lidar ở góc 0° để dừng xe khi cách pallet đúng khoảng cách định trước (ví dụ 150mm).
  2. **Tín hiệu bốc xếp hàng (Cánh tay 3 Servo qua PCA9685 I2C):**
     - Mạch PCA9685 đã được kết nối trên ESP32-S3 tại chân `SDA = GPIO 6`, `SCL = GPIO 10` (địa chỉ I2C `0x40`).
     - Gồm 3 kênh Servo: Kênh 0 (Khớp Đế / Vươn cánh tay), Kênh 1 (Khớp Khuỷu / Hạ-Nâng tay), Kênh 2 (Kẹp Gắp thùng hàng).
     - Chu trình thả hàng lên lưng xe không cần cảm biến thùng xe: Dùng **Chu trình Động học Cố định (Fixed Kinematic Trajectory)** kết hợp **Nội suy mượt (Smooth Interpolation 15ms/bước)** và theo dõi trạng thái góc Servo trả về (`ARM_STATUS:IDLE -> GRABBING -> LIFTING -> PLACING_ON_BED -> RELEASED -> HOME`).

---

## 5. NHẬT KÝ CẬP NHẬT MỚI NHẤT & VIỆC CẦN LÀM TIẾP THEO (CẬP NHẬT 12/11/2026)

> **CHÚ Ý DÀNH CHO ANTIGRAVITY AI TRÊN MÁY ĐỒNG NGHIỆP:**
> Khi người dùng giải nén bản cập nhật `Update_Code_AGV.zip` này vào thư mục `agv_server`, hãy đọc kỹ các thay đổi vừa được thực hiện dưới đây để tiếp tục hỗ trợ người dùng ngay lập tức mà không cần hỏi lại từ đầu:

### A. Những tính năng VỪA ĐƯỢC CẬP NHẬT trong gói Update này:
1. **Sửa lỗi SSL (`CERTIFICATE_VERIFY_FAILED`) trong `run_tunnel_sync.py`:**
   - Đã thêm `ssl._create_unverified_context()` khi đồng bộ link Cloudflare Tunnel lên `ntfy.sh` để không bị lỗi chứng chỉ SSL khi đồng hồ Windows lệch năm (2026).
2. **Thanh công cụ Chụp Dataset YOLOv8 (Ảnh gốc sạch $320 \times 240$) trong `vision_ai.py` & `main.py`:**
   - Đã thêm các API `/api/dataset/capture_one`, `/api/dataset/toggle_auto`, `/api/dataset/status`.
   - Đã thêm 2 nút trên Web Dashboard:
     - `📸 Chụp 1 Ảnh Mẫu`: Lưu 1 khung hình gốc sạch (`self.latest_raw_frame`, không dính chữ FPS hay khung AI) vào thư mục `dataset_thung_hang/`.
     - `⚡ Tự Động Chụp 150 Ảnh (0.5s/tấm)`: Tự động chụp liên tiếp 150 tấm ảnh sạch cách nhau 0.5s vào `dataset_thung_hang/` để làm dữ liệu huấn luyện YOLOv8 nhận diện thùng hàng (`thung_hang`).
3. **Hệ thống đóng gói Update tự động (`pack_update.py`, `dong_goi_update.bat`, `/api/download_update`):**
   - Tự động gom toàn bộ file code (`.py`, `.bat`, `.md`, `.ino`) và model `.pt` mới vào thư mục `Goi_Update_Code/Update_Code_AGV.zip` (< 100 KB).

### B. NHIỆM VỤ TIẾP THEO ANTIGRAVITY AI CẦN LÀM KHI NGƯỜI DÙNG YÊU CẦU:
1. **Bước 1 - Thu thập & Gán nhãn Dataset Thùng Hàng (`dataset_thung_hang/`):**
   - Hướng dẫn/hỗ trợ người dùng dùng nút chụp tự động trên Web Dashboard để thu thập 80–150 tấm ảnh thùng hàng có dán mã QR từ ESP32-CAM.
   - Hỗ trợ gán nhãn (Labeling) lớp `0: thung_hang` (hoặc viết script tự động gợi ý nhãn / chuẩn bị cấu trúc thư mục `dataset/images/train`, `dataset/labels/train` và file `data.yaml`).
2. **Bước 2 - Huấn luyện mô hình YOLOv8n (`best.pt`):**
   - Chạy lệnh huấn luyện YOLOv8 (`yolo task=detect mode=train model=yolov8n.pt data=data.yaml epochs=50 imgsz=320`) ngay bằng môi trường `venv` hoặc Google Colab, sau đó nạp `best.pt` vào `vision_ai.py`.
3. **Bước 3 - Tích hợp Bộ điều khiển Mission AI ("Đi lấy thùng hàng mã QR = X"):**
   - Trên Web Dashboard, thêm ô nhập/chọn mã thùng hàng cần lấy (ví dụ: `THUNG_01`) và nút `[🚀 Đi Lấy Thùng Hàng]`.
   - Kết hợp 3 nguồn cảm biến:
     - **YDLidar X2 (`slam_mapper.polar_dist_mm`)**: Quét 360° tìm lối đi thông thoáng và né vật cản từ xa ($0.15\text{m} - 8\text{m}$).
     - **ESP32-CAM (`vision_ai.latest_boxes` + `vision_ai.latest_qr_data`)**: Phát hiện thùng hàng từ xa bằng YOLOv8, tiến lại gần đọc mã QR để xác nhận đúng mã thùng hàng yêu cầu, sau đó dùng **Visual Servoing** căn chỉnh tâm thùng hàng vào giữa khung hình ($X \approx 160$).
     - **Cảm biến siêu âm HC-SR05 + Cánh tay 3 Servo PCA9685**: Đo khoảng cách áp sát chính xác ($8\text{cm} - 12\text{cm}$), dừng xe (`X`/`G`), và kích hoạt chuỗi gắp thùng hàng đặt lên thùng xe theo quỹ đạo nội suy mượt.

---

## 6. HƯỚNG DẪN KHỞI CHẠY NHANH TRÊN MÁY MỚI (QUICK START)

1. **Cài đặt thư viện (Chỉ chạy 1 lần đầu tiên):**
   Chạy tệp `install.bat`. Tập lệnh sẽ tự tạo môi trường ảo Python (`venv`) và cài đặt đầy đủ tất cả thư viện: `fastapi`, `uvicorn`, `opencv-python`, `ultralytics`, `pyzbar`, v.v.
2. **Khởi chạy hệ thống:**
   Chạy tệp `start_server.bat`. Máy chủ sẽ mở tại `http://localhost:8000`.
3. **Mở đường hầm Internet ra ngoài (Tùy chọn):**
   Chạy tệp `start_tunnel.bat` nếu muốn điều khiển xe từ xa qua 4G/Internet ngoài mạng LAN.
