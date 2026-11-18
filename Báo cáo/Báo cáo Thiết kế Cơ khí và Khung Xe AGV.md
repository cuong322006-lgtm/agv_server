# BÁO CÁO THIẾT KẾ CƠ KHÍ VÀ KÍCH THƯỚC KHUNG XE TỰ HÀNH AGV (KIỂU XE TẢI ĐẦU VUÔNG)

* **Dự án:** Xe Tự Hành AGV 4 Bánh Mecanum – Tích hợp Điều Hướng SLAM LiDAR, AI Vision & Cánh Tay Robot Bốc Xếp Hàng
* **Kiểu dáng thiết kế:** Xe tải đầu vuông công nghiệp (Cab-Over Square Truck AGV)
* **Hệ truyền động:** 4 Động cơ giảm tốc kim loại 1:90 (Chuẩn TT) + 4 Bánh xe đa hướng Mecanum 80mm
* **Cơ cấu chấp hành:** Cánh tay Robot 3 bậc tự do (PCA9685 I2C + 3 Servo 180° + 1 Servo 360° dự phòng) tích hợp Camera Eye-in-Hand
* **Ngày lập bản vẽ thông số:** 16/11/2026

---

## PHẦN 1: TỔNG QUAN KIẾN TRÚC CƠ KHÍ & VẬT LIỆU CHẾ TẠO

Thiết kế cơ khí của xe tự hành AGV được lấy cảm hứng từ dòng **xe tải đầu vuông (Cab-Over Truck)** gồm 2 phân khu rõ rệt: **Đầu Cabin điều hướng & gắp hàng** phía trước ($10 \times 25 \times 10\text{ cm}$) và **Thùng chở hàng kèm khoang máy** phía sau ($25 \times 25 \times 5\text{ cm}$).

### 1.1. Giải pháp phân bổ vật liệu tối ưu tải trọng
Để đảm bảo **4 động cơ giảm tốc bánh răng kim loại 1:90 (3–6V)** hoạt động đạt hiệu suất cao nhất khi di chuyển ngang (Strafe) bằng bánh Mecanum 80mm và không gây quá dòng cho 2 IC cầu H **TB6612FNG**, tổng trọng lượng bản thân xe (chưa tính hàng) được kiểm soát dưới ngưỡng **`2.0 – 2.5 kg`** thông qua kết cấu vật liệu lai (Hybrid Chassis):
1. **Khung gầm chịu lực chính (Main Chassis Frame):** Sử dụng **thép tấm mỏng đục lỗ ($1.0\text{ mm} - 1.2\text{ mm}$)** hoặc khung xương thép hộp mỏng giúp hạ thấp trọng tâm (Center of Gravity), chống võng sàn và chịu lực vặn xoắn khi đi ngang.
2. **Vỏ Cabin đầu vuông & Thành thùng hàng:** Sử dụng tấm **Alu (nhôm nhựa), Mica hoặc nhựa In 3D** gắn trên khung xương thép để giữ form vuông vức, thẩm mỹ cao và giảm 50% khối lượng phần thân trên.
3. **Giá đỡ động cơ (Motor Mounts):** Sử dụng **4 gá ôm chữ U chuyên dụng chuẩn TT (`G140`/`G141`)** hoặc gá hợp kim nhôm chữ L, cố định mỗi động cơ bằng 2 bu-lông `M3 × 30mm` xuyên thân kèm đai ốc chống trôi.

---

## PHẦN 2: SƠ ĐỒ BỐ TRÍ HÌNH HỌC TỔNG THỂ (TOP VIEW & SIDE VIEW)

### 2.1. Bản vẽ mặt bằng nhìn từ trên xuống (Top View)

```text
                  [MẶT TRƯỚC ĐẦU XE - RỘNG 250mm (25cm)]
                  +-------[HC-SR05 Chính Giữa]-------+
     Bánh Trước   |  (Lidar X2)    [ĐẾ CÁNH TAY]     |   Bánh Trước
     Trái 80mm ===|   Cách trái     Chính giữa       |=== Phải 80mm
    (Tâm X=65mm)  |     50mm       (X=40, Y=125)     |   (Tâm X=65mm)
                  |       CABIN (100 x 250 mm)       |
                  +----------------------------------+  <-- Vách ngăn X = 100mm (10cm)
                  |                                  |
                  |         THÙNG CHỞ HÀNG           |
                  |       (250 x 250 x 50 mm)        |
                  |                                  |
                  |    [Dưới gầm sàn thùng chứa:     |
     Bánh Sau     |     Mạch PCB 150x90mm + Pin]     |   Bánh Sau
     Trái 80mm ===|                                  |=== Phải 80mm
    (Tâm X=285mm) |                                  |   (Tâm X=285mm)
                  +----------------------------------+
                  [ĐUÔI XE - TỔNG CHIỀU DÀI X = 350mm (35cm)]
```

### 2.2. Bản vẽ mặt cắt dọc nhìn ngang (Side Elevation View)

```text
          [ESP32-CAM gắn trên cổ tay]
                 \   [Cánh Tay 3 Servo]
       [Lidar X2] \      ||
         [===]     \____/||\____
      +------------+               (Nóc Cabin cao 175mm so với mặt đất)
      |            |
      |   CABIN    |   +------------------------+  (Mép thành thùng cao 125mm)
      | 100x100mm  |   |   LÒNG THÙNG CHỞ HÀNG  |  (Thành thùng cao 50mm)
  [o] |            |---|     (Dài 250 mm)       |  <-- Mặt sàn thùng (Cao 75mm)
HC-SR +------------+---+------------------------+
      |   KHOANG GẦM KỸ THUẬT (Cao 45mm)        |  <-- Chứa PCB 150x90mm + Pin 3S
      +-----(O)--------------------------(O)----+  <-- Đáy gầm cách đất 30mm
           Bánh Trước 80mm             Bánh Sau 80mm
           (Tâm X = 65mm)              (Tâm X = 285mm)
```

---

## PHẦN 3: BẢNG THÔNG SỐ KÍCH THƯỚC CHI TIẾT TOÀN BỘ THÂN XE

| STT | Hạng mục thiết kế cơ khí | Kích thước (`cm`) | Kích thước (`mm`) | Dung sai & Ghi chú gia công |
| :-: | :--- | :---: | :---: | :--- |
| **I** | **KÍCH THƯỚC BAO CHUNG (OVERALL)** | | | |
| 1 | Chiều dài tổng thể khung xe ($L$) | **`35.0 cm`** | **`350 mm`** | Gồm `100 mm` đầu Cabin + `250 mm` Thùng xe |
| 2 | Chiều rộng thân khung xe ($W$) | **`25.0 cm`** | **`250 mm`** | Chiều rộng phủ bì cả 2 bánh Mecanum lắp ngoài: `~320 mm` |
| 3 | Khoảng sáng gầm xe ($H_{\text{clear}}$) | **`3.0 cm`** | **`30 mm`** | Từ mặt đất đến mặt đáy khoang gầm kỹ thuật |
| 4 | Chiều dày khoang gầm kỹ thuật ($H_{\text{bay}}$) | **`4.5 cm`** | **`45 mm`** | Độ cao từ `30 mm` đến `75 mm` (chứa vừa PCB + ESP32-S3 + Pin) |
| 5 | Độ cao mặt sàn thùng hàng ($H_{\text{bed}}$) | **`7.5 cm`** | **`75 mm`** | Tính từ mặt đất lên mặt sàn đặt thùng hàng |
| **II** | **KÍCH THƯỚC CABIN ĐẦU VUÔNG** | | | |
| 6 | Chiều dài Cabin ($L_{\text{cab}}$) | **`10.0 cm`** | **`100 mm`** | Tính từ mũi xe ($X = 0$) đến vách ngăn thùng ($X = 100\text{ mm}$) |
| 7 | Chiều rộng Cabin ($W_{\text{cab}}$) | **`25.0 cm`** | **`250 mm`** | Đồng bộ bề ngang với thân xe |
| 8 | Chiều cao Cabin ($H_{\text{cab}}$) | **`10.0 cm`** | **`100 mm`** | Tính từ mặt sàn thùng (`75 mm`) $\rightarrow$ Đỉnh nóc cao `175 mm` |
| **III** | **KÍCH THƯỚC THÙNG CHỞ HÀNG PHÍA SAU** | | | |
| 9 | Chiều dài lòng thùng ($L_{\text{cargo}}$) | **`25.0 cm`** | **`250 mm`** | Từ vách sau Cabin ($X = 100\text{ mm}$) đến đuôi xe ($X = 350\text{ mm}$) |
| 10 | Chiều rộng lòng thùng ($W_{\text{cargo}}$) | **`25.0 cm`** | **`250 mm`** | Mặt sàn vuông $250 \times 250\text{ mm}$, thiết kế dạng nắp mở bản lề |
| 11 | Chiều cao thành thùng ($H_{\text{wall}}$) | **`5.0 cm`** | **`50 mm`** | Giữ thùng hàng không xê dịch khi xe tăng/giảm tốc |
| **IV** | **HỆ THỐNG BÁNH XE MECANUM & ĐỘNG CƠ** | | | |
| 12 | Kích thước bánh xe Mecanum | **`8.0 × 3.8 cm`** | **`80 × 38 mm`** | 4 bánh đa hướng (2 bánh Trái + 2 bánh Phải), khớp trục TT |
| 13 | Độ cao tâm trục động cơ so với đất | **`4.0 cm`** | **`40 mm`** | Bằng đúng bán kính bánh xe $R = 40\text{ mm}$ |
| 14 | Tọa độ trục 2 bánh trước ($X_{\text{front}}$) | **`6.5 cm`** | **`65 mm`** | Tính từ mũi xe (nằm thẳng dưới trọng tâm Cabin & Cánh tay) |
| 15 | Tọa độ trục 2 bánh sau ($X_{\text{rear}}$) | **`28.5 cm`** | **`285 mm`** | Cách đuôi xe `65 mm` |
| 16 | Chiều dài cơ sở 2 trục ($L_{\text{wheelbase}}$) | **`22.0 cm`** | **`220 mm`** | Khoảng cách tâm trục trước $\leftrightarrow$ tâm trục sau |
| 17 | Khoảng cách tâm 2 lỗ bắt ốc trên Motor | **`1.75 cm`** | **`17.5 mm`** | Lỗ $\Phi 3.2\text{ mm}$, dùng bu-lông `M3 × 30mm` + gá chữ U `G140`/`G141` |

---

## PHẦN 4: TỌA ĐỘ ĐỊNH VỊ CẢM BIẾN, CÁNH TAY ROBOT & BO MẠCH ĐIỆN TỬ

### 4.1. Cụm Cánh Tay Robot 3 Bậc Tự Do & Camera Eye-in-Hand (Trên Nóc Cabin)
* **Vị trí tâm trục xoay Đế Cánh Tay (Base Servo):**
  * **Tọa độ ngang ($Y$):** **`125 mm` (`12.5 cm`)** — nằm chính giữa trục đối xứng dọc của xe.
  * **Tọa độ dọc ($X$):** **`40 mm` (`4.0 cm`)** tính từ mép trước Cabin (cách vách sau Cabin `60 mm`). Vị trí này giúp cánh tay vươn ra khỏi mũi xe dễ dàng mà không cạ vào trán Cabin.
* **Cấu hình các khớp Servo (Điều khiển qua mạch PCA9685 I2C `0x40`):**
  * **Kênh 0 (Khớp Đế xoay ngang - Servo 180°):**
    * Góc `0°`: Hướng thẳng ra phía trước đầu xe để tiếp cận và gắp thùng hàng.
    * Góc `0° ± 30°`: Lia qua lại để camera quét tìm mã QR và căn chỉnh tâm thùng hàng.
    * Góc `180°`: Quay ngược ra phía sau để đặt thùng hàng xuống chính giữa thùng xe ($250 \times 250\text{ mm}$).
  * **Kênh 1 (Khớp Vai / Khuỷu nâng hạ - Servo 180°):** Điều khiển độ vươn và nâng/hạ thùng hàng.
  * **Kênh 2 (Khớp Ngàm Kẹp - Servo 180°):** Đóng/mở kẹp gắp thùng hàng.
  * *(Dự phòng: 01 Servo 360° có thể dùng cho cơ cấu tời/cuốn hoặc băng tải phụ nếu mở rộng).*
* **Vị trí gắn Camera AI ESP32-CAM ("Eye-in-Hand"):**
  * Gắn cố định trên **cổ tay cánh tay (phía trên ngàm kẹp `30 mm`)**, trục quang học song song với hướng mở của ngón kẹp để vừa tìm mã QR từ xa vừa căn tâm thùng hàng chính xác khi hạ kẹp.

### 4.2. Cảm Biến Quét Laser 360° YDLidar X2 (Trên Nóc Cabin)
* **Tọa độ tâm mắt đọc YDLidar X2:**
  * **Tọa độ ngang ($Y$):** Cách mép trái Cabin **`50 mm` (`5.0 cm`)** (cách tâm đế cánh tay `75 mm` về phía bên trái).
  * **Tọa độ dọc ($X$):** Cách mép trước Cabin **`45 mm` (`4.5 cm`)**.
* **Độ cao lắp đặt:** Bắt trên 4 trụ đồng (Standoff M3) cao **`30 – 40 mm`** trên mặt nóc Cabin để thấu kính laser nằm ở độ cao ~`210 mm` so với mặt đất.
* **Xử lý chống nhiễu góc khuất:** Phần mềm SLAM & Pathfinding tự động lọc bỏ các điểm phản xạ có cự ly `< 150 mm` (vùng thân cánh tay bên cạnh) để không tạo vật cản ảo.

### 4.3. Cảm Biến Siêu Âm HC-SR05 (Mặt Trước Cabin)
* **Vị trí khoét lỗ:** Chính giữa mặt trước cản Cabin ($Y = 125\text{ mm}$), độ cao cách mặt đất **`60 mm` (`6.0 cm`)**.
* **Kích thước lỗ khoét:** 2 lỗ tròn đường kính **`16 mm`**, khoảng cách tâm 2 lỗ **`26 mm`**.

### 4.4. Khoang Gầm Kỹ Thuật & Quy Tắc Lắp Đặt 4 Bánh Mecanum
1. **Khoang Gầm Kỹ Thuật (Dưới sàn thùng xe $250 \times 250 \times 45\text{ mm}$):**
   * Bố trí **Bo mạch PCB trung tâm ($150 \times 90\text{ mm}$)** trên 4 trụ đồng cách điện cao `10 mm` ở giữa khoang.
   * Bố trí **Khối Pin Li-ion 3S 12V** nằm sát trục giữa xe để cân bằng trọng lượng 4 bánh.
   * Mặt sàn thùng hàng phía trên ($250 \times 250\text{ mm}$) làm dạng **nắp đậy có bản lề** để mở lên thao tác công tắc nguồn, nạp chương trình và bảo trì mạch dễ dàng.
2. **Quy tắc lắp chiều con lăn 4 bánh Mecanum 80mm (Chuẩn chữ `X`):**
   * Khi nhìn từ trên đỉnh xe xuống mặt đất, đường chéo của các con lăn cao su tiếp đất trên 4 bánh xe **BẮT BUỘC phải hội tụ về tâm xe tạo thành hình chữ `X`**:
     * **Bánh Trước - Trái:** Con lăn hướng `\`
     * **Bánh Trước - Phải:** Con lăn hướng `/`
     * **Bánh Sau - Trái:** Con lăn hướng `/`
     * **Bánh Sau - Phải:** Con lăn hướng `\`
