# BÁO CÁO THIẾT KẾ PHẦN CỨNG VÀ QUY TẮC ĐI DÂY PCB XE TỰ HÀNH AGV

* **Dự án:** Xe Tự Hành AGV 4 Bánh Mecanum - Tích hợp Điều Hướng SLAM LiDAR & AI Vision
* **Bộ điều khiển trung tâm:** ESP32-S3-DevKitC-1 (N16R8V)
* **Phần mềm thiết kế Schematic & PCB:** Altium Designer
* **Quy cách chế tạo mạch:** Mạch in 2 lớp (2-Layer FR4 PCB, kích thước $150 \times 90\text{ mm}$, độ dày 1.6mm, độ dày đồng 1oz/35µm)
* **Ngày cập nhật sơ đồ nguyên lý mới nhất:** 18/11/2026 (Đã bổ sung Header `P2` cho Cảm biến góc từ 360° `AS5600`)

---

## PHẦN 1: TỔNG QUAN KIẾN TRÚC PHẦN CỨNG HỆ THỐNG

Hệ thống điện tử trên xe tự hành AGV được thiết kế theo cấu trúc module hóa phân tầng, đảm bảo tính ổn định cao, chống nhiễu tuyệt đối và bảo vệ tối đa các linh kiện:

1. **Khối Xử Lý Trung Tâm (Master Controller):**
   * Sử dụng vi điều khiển **ESP32-S3 DevKitC-1 (N16R8V)** trang bị Dual-Core Xtensa LX7 240MHz.
   * Đảm nhiệm giao tiếp Wi-Fi WebSocket lên Server, nhận gói tin điều khiển vận tốc $(V_x, V_y, \omega)$, tính toán động học nghịch 4 bánh Mecanum, xuất xung PWM điều khiển 2 mạch cầu H TB6612FNG, đọc cảm biến LiDAR YDLidar X2 qua UART (GPIO11/12), kích hoạt cảm biến siêu âm HC-SR05 né vật cản khẩn cấp (GPIO14/13) và giao tiếp **bus I2C kép (SDA = GPIO6, SCL = GPIO10)** điều khiển đồng thời IC mở rộng PWM **PCA9685 (`0x40`)** và cảm biến phản hồi góc tuyệt đối 360° **AS5600 (`0x36`)** cho khớp Đế Cánh Tay.

2. **Khối Quản Lý Nguồn & Hạ Áp (Power Management System):**
   * **Nguồn sơ cấp:** Pin sạc Li-ion 3S (11.1V danh định, 12.6V khi sạc đầy) cấp nguồn trực tiếp qua cọc nguồn `HD6`.
   * **Hạ áp Logic 5.1V (`PS1` - Module Buck LM2596):** Hạ từ 12V xuống 5.1V cấp riêng cho ESP32-S3, Module Camera ESP32-CAM, Mắt quét LiDAR X2, Cảm biến siêu âm HC-SR05 và nguồn logic cho 2 chip TB6612FNG.
   * **Hạ áp Động Cơ & Servo 6.0V (`PS2` - Module Buck LM2596):** Hạ từ 12V xuống 6.0V cấp dòng cho:
     * Chân `VM` của cả 2 chip TB6612FNG: **Bảo vệ an toàn tuyệt đối cho 4 động cơ 3-6V (chống cháy motor do quá áp 12V)**.
     * Thanh ray công suất $V^+$ của PCA9685 nuôi các động cơ Servo.

3. **Khối Công Suất Động Cơ (Motor Actuation System):**
   * Sử dụng **2 Module Driver TB6612FNG Dual H-Bridge MOSFET** (`U2` và `U4`).
   * Điều khiển 4 động cơ giảm tốc DC 3-6V gắn bánh xe Mecanum 80mm. Mỗi kênh đều có tụ hóa $470\mu\text{F}/25\text{V}$ bù áp tức thời và tụ gốm $100\text{nF}$ dập nhiễu cao tần.

4. **Khối Điều Khiển Cơ Cấu Chấp Hành & Phản Hồi Góc Cánh Tay (Servo Expansion & AS5600 Encoder):**
   * **Module PCA9685 (`U1`, địa chỉ I2C `0x40`):** Giao tiếp bus I2C (`SDA` = Net `SV1.2` trên `GPIO6`, `SCL` = Net `SV1.1` trên `GPIO10`) với ESP32-S3. Tạo xung phần cứng 12-bit PWM độc lập điều khiển 1 Servo MG996R 360° (Kênh 0 - Đế xoay) và 3 Servo MG996R 180° (Kênh 1, 2, 3 - Vai, Khuỷu, Kẹp).
   * **Module Cảm Biến Góc Từ Tính 12-bit AS5600 (`P2`, địa chỉ I2C `0x36`):** Đấu song song trên cùng bus I2C (`SV1.1` / `SV1.2`) qua Header 4 chân `P2` trên PCB, đọc góc xoay thực tế từ `0.0°` đến `360.0°` (4096 bước) của khớp Đế Servo 360° để dừng chính xác từng độ.

5. **Khối Cảm Biến Định Vị & Truyền Hình Ảnh (Perception & Vision):**
   * **2D LiDAR YDLidar X2:** Truyền dữ liệu về ESP32-S3 qua UART (TX nối GPIO11, M_EN nối GPIO12).
   * **Cảm biến siêu âm HC-SR05 / HY-SRF05:** Bố trí phía trước xe (TRIG nối GPIO14, ECHO qua cầu trở $1\text{k}\Omega : 2\text{k}\Omega$ nối GPIO13).
   * **Camera AI ESP32-CAM:** Cấp nguồn 5V, truyền video qua Wi-Fi lên Server nhận diện AI.

---

## PHẦN 2: BẢNG KẾT NỐI CHI TIẾT TOÀN BỘ LINH KIỆN (BẢN CẬP NHẬT MỚI NHẤT)

### 2.1. Bảng sơ đồ chân vi điều khiển trung tâm ESP32-S3 DevKitC-1 (`U3`)

| Chân trên Bo DevKit | Tên Pin / Net Label | Hướng tín hiệu | Kết nối đến linh kiện | Chức năng chi tiết trong hệ thống AGV |
| :--- | :--- | :--- | :--- | :--- |
| **J1_1, J1_2** | `3V3` / `M1.1` | Nguồn ra | Chân `STBY` của 2×TB6612 & Pin 1 (`VCC`) của Header `P2 (AS5600)` | Kéo chân Standby kích hoạt 2 Driver động cơ và cấp nguồn chuẩn 3.3V cho cảm biến góc từ `AS5600` |
| **J1_6** | `GPIO6` / `SV1.2` | I/O (SDA) | Chân `SDA` của `PCA9685` **và** Pin 4 (`SDA`) của `P2 (AS5600)` | Đường truyền dữ liệu bus I2C chung cho cả PCA9685 (`0x40`) và AS5600 (`0x36`) |
| **J1_16** | `GPIO10` / `SV1.1` | Output (SCL) | Chân `SCL` của `PCA9685` **và** Pin 3 (`SCL`) của `P2 (AS5600)` | Đường xung nhịp đồng hồ bus I2C (400kHz) chung cho cả PCA9685 và AS5600 |
| **J1_17** | `GPIO11` / `LIDA-TX` | Input (RX2) | Chân `TX` của YDLidar X2 | Nhận dòng byte dữ liệu điểm đo quét laser 360 độ |
| **J1_18** | `GPIO12` / `LIDA-EN` | Output | Chân `M_EN` của YDLidar X2 | Bật / Tắt motor quay quét laser của mắt LiDAR |
| **J1_19** | `GPIO13` | Input | Điểm giữa cầu phân áp $1\text{k}\Omega : 2\text{k}\Omega$ | Nhận xung phản hồi `ECHO` từ HC-SR05 (giảm áp từ 5V xuống 3.3V) |
| **J1_20** | `GPIO14` / `HC-SR05.1` | Output | Chân `TRIG` của HC-SR05 | Phát xung siêu âm $10\mu\text{s}$ kích hoạt đo khoảng cách |
| **J3_18** | `GPIO21` / `M1.2` | Output (PWM) | Chân `PWMA` của TB6612 #1 | Điều xung PWM tốc độ Động cơ 1 (Trước - Trái) |
| **J3_16** | `GPIO48` / `M1.3` | Output (DIR) | Chân `AIN1` của TB6612 #1 | Điều khiển chiều quay Động cơ 1 (Trước - Trái) |
| **J3_17** | `GPIO47` / `M1.4` | Output (DIR) | Chân `AIN2` của TB6612 #1 | Điều khiển chiều quay Động cơ 1 (Trước - Trái) |
| **J3_12** | `GPIO36` / `M1.7` | Output (PWM) | Chân `PWMB` của TB6612 #1 | Điều xung PWM tốc độ Động cơ 2 (Trước - Phải) *(Lưu ý: Tắt PSRAM khi nạp code)* |
| **J3_15** | `GPIO45` / `M1.8` | Output (DIR) | Chân `BIN1` của TB6612 #1 | Điều khiển chiều quay Động cơ 2 (Trước - Phải) |
| **J3_13** | `GPIO35` / `M1.9` | Output (DIR) | Chân `BIN2` của TB6612 #1 | Điều khiển chiều quay Động cơ 2 (Trước - Phải) *(Lưu ý: Tắt PSRAM khi nạp code)* |
| **J3_10** | `GPIO38` / `M1.12` | Output (PWM) | Chân `PWMA` của TB6612 #2 | Điều xung PWM tốc độ Động cơ 3 (Sau - Trái) |
| **J3_8** | `GPIO40` / `M1.13` | Output (DIR) | Chân `AIN1` của TB6612 #2 | Điều khiển chiều quay Động cơ 3 (Sau - Trái) |
| **J3_9** | `GPIO39` / `M1.14` | Output (DIR) | Chân `AIN2` của TB6612 #2 | Điều khiển chiều quay Động cơ 3 (Sau - Trái) |
| **J3_5** | `GPIO2` / `M1.17` | Output (PWM) | Chân `PWMB` của TB6612 #2 | Điều xung PWM tốc độ Động cơ 4 (Sau - Phải) |
| **J3_7** | `GPIO41` / `M1.18` | Output (DIR) | Chân `BIN1` của TB6612 #2 | Điều khiển chiều quay Động cơ 4 (Sau - Phải) |
| **J3_6** | `GPIO42` / `M1.19` | Output (DIR) | Chân `BIN2` của TB6612 #2 | Điều khiển chiều quay Động cơ 4 (Sau - Phải) |
| **J1_21** | `5V0` / `5v1` | Nguồn vào | Ngõ ra `OUT+` của Buck LM2596 #1 | Cấp nguồn 5.1V nuôi toàn bộ vi điều khiển ESP32-S3 |
| **J1_22, J3_1, J3_21, J3_22** | `GND` | Nguồn âm | Net `GND_Logic` | Nối chung mass hệ thống logic vi điều khiển |

---

### 2.2. Bảng kết nối Driver TB6612FNG #1 (`U2` - Cụm Động Cơ Trước: M1 & M2)

| Số chân IC | Ký hiệu chân | Net kết nối trên Schematic | Kết nối thực tế / Ngoại vi | Chức năng kỹ thuật |
| :---: | :--- | :--- | :--- | :--- |
| **1** | `VM` | `6v` | Ngõ ra Buck 2 (qua tụ $C_1$ $470\mu\text{F}$) | Nguồn công suất động cơ 3-6V an toàn |
| **2** | `VCC` | `5v1` | Ngõ ra Buck 1 (qua tụ $C_2$ $100\text{nF}$) | Nguồn logic nội IC ($2.7\text{V} - 5.5\text{V}$) |
| **3, 8, 9** | `GND` | `GND_PWR` | Nối về cực âm Cọc nguồn `HD6` | Mass công suất thoát dòng lớn của motor |
| **4** | `A01` | `M1.5` | Pin 1 của Cọc Terminal `HD2` | Cực dương Động cơ GA25 Trước - Trái (M1) |
| **5** | `A02` | `M1.6` | Pin 2 của Cọc Terminal `HD2` | Cực âm Động cơ GA25 Trước - Trái (M1) |
| **6** | `B02` | `M1.11` | Pin 2 của Cọc Terminal `HD3` | Cực âm Động cơ GA25 Trước - Phải (M2) |
| **7** | `B01` | `M1.10` | Pin 1 của Cọc Terminal `HD3` | Cực dương Động cơ GA25 Trước - Phải (M2) |
| **10** | `PWMB` | `M1.7` | `GPIO36` (`J3_12`) của ESP32-S3 | Tín hiệu xung PWM tốc độ Motor 2 (Tần số 20kHz) |
| **11** | `BIN2` | `M1.9` | `GPIO35` (`J3_13`) của ESP32-S3 | Logic điều khiển chiều quay Motor 2 |
| **12** | `BIN1` | `M1.8` | `GPIO45` (`J3_15`) của ESP32-S3 | Logic điều khiển chiều quay Motor 2 |
| **13** | `STBY` | `M1.1` | Chân `3V3` (`J1_2`) của ESP32-S3 | Kéo CAO để giải phóng chế độ ngủ Standby |
| **14** | `AIN1` | `M1.3` | `GPIO48` (`J3_16`) của ESP32-S3 | Logic điều khiển chiều quay Motor 1 |
| **15** | `AIN2` | `M1.4` | `GPIO47` (`J3_17`) của ESP32-S3 | Logic điều khiển chiều quay Motor 1 |
| **16** | `PWMA` | `M1.2` | `GPIO21` (`J3_18`) của ESP32-S3 | Tín hiệu xung PWM tốc độ Motor 1 (Tần số 20kHz) |

---

### 2.3. Bảng kết nối Driver TB6612FNG #2 (`U4` - Cụm Động Cơ Sau: M3 & M4)

| Số chân IC | Ký hiệu chân | Net kết nối trên Schematic | Kết nối thực tế / Ngoại vi | Chức năng kỹ thuật |
| :---: | :--- | :--- | :--- | :--- |
| **1** | `VM` | `6v` | Ngõ ra Buck 2 (qua tụ $C_3$ $470\mu\text{F}$) | Nguồn công suất động cơ Sau 3-6V an toàn |
| **2** | `VCC` | `5v1` | Ngõ ra Buck 1 (qua tụ $C_4$ $100\text{nF}$) | Nguồn logic nội IC TB6612 |
| **3, 8, 9** | `GND` | `GND_PWR` | Nối về cực âm Cọc nguồn `HD6` | Mass công suất thoát dòng lớn của motor |
| **4** | `A01` | `M1.15` | Pin 1 của Cọc Terminal `HD4` | Cực dương Động cơ GA25 Sau - Trái (M3) |
| **5** | `A02` | `M1.16` | Pin 2 của Cọc Terminal `HD4` | Cực âm Động cơ GA25 Sau - Trái (M3) |
| **6** | `B02` | `M1.21` | Pin 2 của Cọc Terminal `HD5` | Cực âm Động cơ GA25 Sau - Phải (M4) |
| **7** | `B01` | `M1.20` | Pin 1 của Cọc Terminal `HD5` | Cực dương Động cơ GA25 Sau - Phải (M4) |
| **10** | `PWMB` | `M1.17` | `GPIO2` (`J3_5`) của ESP32-S3 | Tín hiệu xung PWM tốc độ Motor 4 |
| **11** | `BIN2` | `M1.19` | `GPIO42` (`J3_6`) của ESP32-S3 | Logic điều khiển chiều quay Motor 4 |
| **12** | `BIN1` | `M1.18` | `GPIO41` (`J3_7`) của ESP32-S3 | Logic điều khiển chiều quay Motor 4 |
| **13** | `STBY` | `M1.1` | Chân `3V3` (`J1_2`) của ESP32-S3 | Kéo CAO để giải phóng chế độ ngủ Standby |
| **14** | `AIN1` | `M1.13` | `GPIO40` (`J3_8`) của ESP32-S3 | Logic điều khiển chiều quay Motor 3 |
| **15** | `AIN2` | `M1.14` | `GPIO39` (`J3_9`) của ESP32-S3 | Logic điều khiển chiều quay Motor 3 |
| **16** | `PWMA` | `M1.12` | `GPIO38` (`J3_10`) của ESP32-S3 | Tín hiệu xung PWM tốc độ Motor 3 |

---

### 2.4. Bảng kết nối 2 Module Hạ Áp DC-DC Buck LM2596 (`PS1` & `PS2`)

| Ký hiệu | Tên Pin Module | Net kết nối | Điện áp định mức | Chức năng & Tải tiêu thụ |
| :---: | :--- | :--- | :---: | :--- |
| **`PS1`** *(Buck Logic)* | `IN+` | `+12` | 11.1V - 12.6V | Nhận nguồn từ cọc pin chính `HD6` |
| | `IN-` | `GND_PWR` | 0V | Mass đầu vào công suất cao |
| | `OUT+` | `5v1` | **5.1V DC (3A)** | Cấp nguồn nuôi: ESP32-S3, ESP32-CAM, YDLidar X2, HC-SR05, VCC Logic TB6612, VCC PCA9685 |
| | `OUT-` | `GND_Logic` | 0V | Mass đầu ra nguồn sạch nuôi vi điều khiển |
| **`PS2`** *(Buck Động Cơ & Servo)* | `IN+` | `+12` | 11.1V - 12.6V | Nhận nguồn từ cọc pin chính `HD6` |
| | `IN-` | `GND_PWR` | 0V | Mass đầu vào công suất cao |
| | `OUT+` | `6v` | **6.0V DC (3A)** | Cấp nguồn cho: Chân `VM` của 2 chip TB6612 nuôi 4 động cơ 3-6V, và thanh ray $V^+$ của PCA9685 nuôi Servo |
| | `OUT-` | `GND_Logic` | 0V | Nối chung mass hệ thống logic |

---

### 2.5. Bảng kết nối Module Mở Rộng 16 Kênh PWM PCA9685 (`U1`)

| Tên nhóm chân | Ký hiệu chân | Net kết nối | Điện áp | Mục đích sử dụng |
| :--- | :--- | :--- | :---: | :--- |
| **Nguồn Logic IC** | `VCC_1, VCC_2` | `5v1` | 5.0V | Nguồn nuôi chip PCA9685 |
| **Nguồn Công Suất**| `V+_1` đến `V+_18` | `6v` | 6.0V | Cấp điện dòng cao trực tiếp cho các động cơ Servo |
| **Mass Hệ Thống** | `GND_1` đến `GND_18`| `GND_Logic`| 0V | Mass chung cho chip PCA9685 và các Servo |
| **Kích Hoạt Ngõ Ra**| `OE_1, OE_2` | `GND_Logic` | 0V | Kéo thấp xuống mass để cho phép ngõ ra PWM hoạt động liên tục |
| **Giao Tiếp I2C** | `SDA_1, SDA_2` | `SV1.2` | 3.3V | Nối vào chân **`GPIO6` (`J1_6`)** của ESP32-S3 |
| | `SCL_1, SCL_2` | `SV1.1` | 3.3V | Nối vào chân **`GPIO10` (`J1_16`)** của ESP32-S3 |

---

### 2.6. Bảng kết nối Cảm biến Siêu âm HC-SR05 / HY-SRF05 (`JP1`)

| Số chân `JP1` | Ký hiệu trên Cảm biến | Net kết nối | Mức điện áp | Mô tả & Cách đấu nối bảo vệ chân chip |
| :---: | :--- | :--- | :---: | :--- |
| **Pin 1** | `VCC` | `5v1` | +5.0V | Cấp nguồn nuôi bộ phát siêu âm 40kHz |
| **Pin 2** | `TRIG` | `HC-SR05.1` | 3.3V | Cắm vào chân **`GPIO14` (`J1_20`)** của ESP32-S3 |
| **Pin 3** | `ECHO` | `HC-SR05.2` | 5.0V $\rightarrow$ 3.33V | **Đi qua cầu phân áp trở:** Nối vào 1 đầu điện trở $R_1 (1\text{k}\Omega)$, đầu ra nối vào **`GPIO13` (`J1_19`)** |
| **Pin 4** | `OUT` | *Bỏ trống (NC)* | -- | Chân chuyển chế độ của HY-SRF05, không cắm vào mass |
| **Pin 5** | `GND` | `GND_Logic` | 0V | Chân mass thực sự của cảm biến |

---

### 2.7. Bảng kết nối Cảm biến Laser 2D YDLidar X2 (`P1` - Lida-x2)

| Chân Header | Tên tín hiệu | Net kết nối | Hướng truyền | Chức năng |
| :---: | :--- | :--- | :---: | :--- |
| **Pin 1** | `VCC` | `5v1` | Nguồn vào | Cấp nguồn 5V nuôi quang học và motor quay |
| **Pin 2** | `TX` | `LIDA-TX` | Lidar $\rightarrow$ ESP32 | Nối vào chân **`GPIO11` (`J1_17`)** (UART RX2 của ESP32) |
| **Pin 3** | `M_EN` / `M_CTR`| `LIDA-EN` | ESP32 $\rightarrow$ Lidar | Nối vào chân **`GPIO12` (`J1_18`)** (Điều khiển bật/tắt motor quét) |
| **Pin 4** | `GND` | `GND_Logic` | 0V | Mass hệ thống logic |

---

### 2.8. [MỚI BỔ SUNG] Bảng kết nối Cảm biến Góc Từ 360° AS5600 (`P2` - Header 4 Chân 2.54mm)

> **Hướng dẫn vẽ thêm trên Altium Designer (`Sheet1.SchDoc` & `PCB1.PcbDoc`):**
> * Lấy 1 linh kiện **Header 4-Pin (khoảng cách chân chuẩn `2.54mm`)**, đặt tên là **`P2`** (hoặc `AS5600`).
> * **Vị trí đặt trên PCB (`PCB1.PcbDoc`):** Đặt `P2` ở **cạnh trên của bo mạch, ngay sát bên cạnh Header `P1` (YDLidar X2) và đầu trên của Module `PCA9685` (`U1`)**. Tại vị trí này, cả 4 đường mạng (`M1.1 / 3V3`, `GND_Logic`, `SV1.1`, `SV1.2`) đều nằm ngay sát cạnh dưới $10\text{ mm}$, đi dây cực ngắn không cần nhảy Via phức tạp!

| Chân Header `P2` trên PCB | Nối tới chân trên Module `AS5600` | Tên Net trên Schematic (`Sheet1.SchDoc`) | Kết nối về ESP32-S3 / PCA9685 | Mức điện áp & Quy tắc đi dây PCB |
| :---: | :---: | :---: | :--- | :--- |
| **Pin 1** | `VCC` | **`M1.1`** *(hoặc `3V3`)* | Chân `3V3` (`J1_1` / `J1_2`) của ESP32-S3 *(hoặc dùng `5v1` nếu để nguyên R1 trên AS5600)* | **3.3V DC** (Độ rộng đường mạch: `0.5 mm`). Cấp áp chuẩn 3.3V cho chip AS5600 |
| **Pin 2** | `GND` *(và nối tắt chân `DIR` vào `GND` trên bo AS5600)* | **`GND_Logic`** | Mass chung hệ thống logic (`GND`) | **0V** (Phủ đồng Polygon Pour `GND_Logic` trực tiếp vào chân) |
| **Pin 3** | `SCL` | **`SV1.1`** | Nối chung đường **`GPIO10` (`J1_16`)** & chân `SCL_1` của `PCA9685` | **3.3V I2C Clock** (Độ rộng đường mạch: `0.3 mm – 0.4 mm`, đi song song cạnh dây `SDA`) |
| **Pin 4** | `SDA` | **`SV1.2`** | Nối chung đường **`GPIO6` (`J1_6`)** & chân `SDA_1` của `PCA9685` | **3.3V I2C Data** (Độ rộng đường mạch: `0.3 mm – 0.4 mm`). Địa chỉ I2C của AS5600 là `0x36` (không trùng với `0x40` của PCA9685) |

*Lưu ý đối với các chân còn lại trên bo cảm biến `AS5600` (nằm trên nóc Cabin):*
* **Chân `DIR` trên bo AS5600:** Hàn nối tắt trực tiếp sang chân `GND` ngay sát cạnh nó trên bo AS5600 (để cố định chiều tăng góc thuận kim đồng hồ $0^\circ \to 360^\circ$, nhờ đó chỉ cần kéo đúng **4 sợi dây** từ nóc Cabin xuống Header `P2` trên PCB).
* **Chân `OUT` và `GPO` trên bo AS5600:** Bỏ trống (không sử dụng).

---

## PHẦN 3: ĐOẠN MÃ NGUỒN C++ KHAI BÁO CHÂN (DÙNG ĐỂ LẬP TRÌNH XE AGV)

Dưới đây là file cấu hình chân `PinMap_AGV.h` bạn có thể copy trực tiếp vào Arduino IDE hoặc PlatformIO:

```cpp
#ifndef PINMAP_AGV_H
#define PINMAP_AGV_H

// ==========================================
// 1. ĐỘNG CƠ CẦU TRƯỚC (DRIVER TB6612 #1)
// ==========================================
#define M1_PWM_PIN    21    // Động cơ 1 (Trước-Trái) - Xung PWM
#define M1_IN1_PIN    48    // Động cơ 1 - Chiều quay AIN1
#define M1_IN2_PIN    47    // Động cơ 1 - Chiều quay AIN2

#define M2_PWM_PIN    36    // Động cơ 2 (Trước-Phải) - Xung PWM (Lưu ý: Tắt PSRAM khi nạp)
#define M2_IN1_PIN    45    // Động cơ 2 - Chiều quay BIN1
#define M2_IN2_PIN    35    // Động cơ 2 - Chiều quay BIN2 (Lưu ý: Tắt PSRAM khi nạp)

// ==========================================
// 2. ĐỘNG CƠ CẦU SAU (DRIVER TB6612 #2)
// ==========================================
#define M3_PWM_PIN    38    // Động cơ 3 (Sau-Trái) - Xung PWM
#define M3_IN1_PIN    40    // Động cơ 3 - Chiều quay AIN1
#define M3_IN2_PIN    39    // Động cơ 3 - Chiều quay AIN2

#define M4_PWM_PIN    2     // Động cơ 4 (Sau-Phải) - Xung PWM
#define M4_IN1_PIN    41    // Động cơ 4 - Chiều quay BIN1
#define M4_IN2_PIN    42    // Động cơ 4 - Chiều quay BIN2

// ==========================================
// 3. BUS I2C KÉP: 16 SERVO (PCA9685) + CẢM BIẾN GÓC 360° (AS5600)
// ==========================================
#define I2C_SDA_PIN       6     // Chân dữ liệu SDA (Net SV1.2 - Dùng chung PCA9685 & AS5600)
#define I2C_SCL_PIN       10    // Chân xung nhịp SCL (Net SV1.1 - Dùng chung PCA9685 & AS5600)
#define PCA9685_I2C_ADDR  0x40  // Địa chỉ I2C của Module 16 Kênh Servo PCA9685 (U1)
#define AS5600_I2C_ADDR   0x36  // Địa chỉ I2C của Cảm biến góc từ 360° AS5600 (P2)

// ==========================================
// 4. MẮT QUÉT 2D LIDAR (YDLIDAR X2)
// ==========================================
#define LIDAR_RX_PIN  11    // Nhận dữ liệu PointCloud từ Lidar TX
#define LIDAR_EN_PIN  12    // Bật / tắt motor quay quét

// ==========================================
// 5. CẢM BIẾN SIÊU ÂM TRÁNH VA CHẠM (HC-SR05)
// ==========================================
#define SONAR_TRIG_PIN 14   // Chân phát xung Trigger
#define SONAR_ECHO_PIN 13   // Chân nhận xung Echo (qua cầu phân áp 1k:2k)

#endif // PINMAP_AGV_H
```

---

## PHẦN 4: LƯU Ý SỐNG CÒN KHI NẠP CODE TRÊN ARDUINO IDE

> ⚠️ **CỰC KỲ QUAN TRỌNG VỀ BỘ NHỚ PSRAM:**  
> Vì chân `GPIO35` và `GPIO36` trên một số phiên bản ESP32-S3 được nối vào chân dữ liệu của bộ nhớ Octal PSRAM:  
> Khi nạp code trong Arduino IDE, bạn **BẮT BUỘC** phải vào menu:  
> 👉 **`Tools` $\rightarrow$ `PSRAM` $\rightarrow$ Chọn `Disabled` (Tắt PSRAM)**.  
> Khi tắt PSRAM, chip ESP32-S3 sẽ giải phóng hoàn toàn 2 chân này để làm GPIO điều khiển Động cơ 2 êm ru mà không bị treo chip!
