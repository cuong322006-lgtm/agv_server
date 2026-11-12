import cv2
import numpy as np
import math
import base64
import time


class SLAMMapper:
    def __init__(self, map_size=520, max_range_mm=6000):
        self.map_size = map_size
        self.max_range_mm = max_range_mm  # Mở full phạm vi 6.0m (đường kính 12m 360 độ)
        self.scale = (map_size // 2) / max_range_mm

        # Mảng lưu khoảng cách thực tế của 360 góc (0..359 độ) từ mắt thần YDLidar X2
        # Mặc định mở full max_range_mm (Không có tường biên đóng khung)
        self.polar_dist_mm = np.full(360, float(self.max_range_mm), dtype=np.float32)
        self.polar_updated_at = np.zeros(360, dtype=np.float64)

        self.total_packets = 0
        self.last_hw_scan_time = 0.0
        self.last_s3_seen_time = 0.0
        self.s3_connected = False

        # Trạng thái vị trí xe AGV trên bản đồ
        self.robot_x_mm = 0.0
        self.robot_y_mm = 0.0
        self.robot_theta_deg = 0.0
        self.last_command = "X (Dang cho lenh)"
        self.gripper_active = False
        self.trajectory = [(0.0, 0.0)]

        # Góc kim quét Radar xoay 360 độ liên tục
        self.sweep_angle_deg = 0.0
        self.last_render_time = time.time()

        print("[*] Radar SLAM 360° Thuần Phần Cứng YDLidar X2 (Full-Range 6m) đã khởi tạo.")

    def notify_s3_heartbeat(self):
        self.last_s3_seen_time = time.time()
        self.s3_connected = True

    def apply_control_command(self, cmd: str):
        self.last_s3_seen_time = time.time()
        self.s3_connected = True
        cmd = (cmd or "").strip().upper()
        if not cmd:
            return

        step_mm = 160.0
        turn_deg = 15.0

        if cmd == 'W':
            rad = math.radians(self.robot_theta_deg - 90.0)
            self.robot_x_mm += step_mm * math.cos(rad)
            self.robot_y_mm += step_mm * math.sin(rad)
            self.last_command = "W - TIEN LEN (+16cm)"
        elif cmd == 'S':
            rad = math.radians(self.robot_theta_deg - 90.0)
            self.robot_x_mm -= step_mm * math.cos(rad)
            self.robot_y_mm -= step_mm * math.sin(rad)
            self.last_command = "S - LUI LAI (-16cm)"
        elif cmd == 'A':
            self.robot_theta_deg = (self.robot_theta_deg - turn_deg) % 360.0
            self.last_command = f"A - RE TRAI ({int(self.robot_theta_deg)} deg)"
        elif cmd == 'D':
            self.robot_theta_deg = (self.robot_theta_deg + turn_deg) % 360.0
            self.last_command = f"D - RE PHAI ({int(self.robot_theta_deg)} deg)"
        elif cmd == 'G':
            self.gripper_active = not self.gripper_active
            state_str = "DANG GAP" if self.gripper_active else "MO TAY GAP"
            self.last_command = f"G - {state_str}"
        elif cmd == 'X':
            self.last_command = "X - DUNG XE"

        limit = self.max_range_mm * 0.45
        self.robot_x_mm = max(-limit, min(limit, self.robot_x_mm))
        self.robot_y_mm = max(-limit, min(limit, self.robot_y_mm))
        self.trajectory.append((self.robot_x_mm, self.robot_y_mm))
        if len(self.trajectory) > 200:
            self.trajectory.pop(0)

    def update_scan(self, points):
        """
        Chỉ cập nhật 100% từ dữ liệu tia Laser thật của YDLidar X2!
        Vật cản cách bao nhiêu mét thì đường biên Radar co đúng về vòng tròn khoảng cách đó.
        """
        if not points:
            return

        now = time.time()
        self.total_packets += 1
        self.last_hw_scan_time = now
        self.last_s3_seen_time = now
        self.s3_connected = True

        for angle_deg, dist_mm in points:
            world_angle = (angle_deg + self.robot_theta_deg) % 360.0
            bucket = int(round(world_angle)) % 360

            if dist_mm <= 40 or dist_mm >= self.max_range_mm:
                self.polar_dist_mm[bucket] = float(self.max_range_mm)
                self.polar_updated_at[bucket] = now
            else:
                self.polar_dist_mm[bucket] = float(dist_mm)
                self.polar_updated_at[bucket] = now
                # Làm liền đường biên giữa 2 tia kế cận (±1 độ)
                b_prev = (bucket - 1) % 360
                b_next = (bucket + 1) % 360
                if now - self.polar_updated_at[b_prev] > 0.15:
                    self.polar_dist_mm[b_prev] = float(dist_mm)
                if now - self.polar_updated_at[b_next] > 0.15:
                    self.polar_dist_mm[b_next] = float(dist_mm)

    def reset_map(self):
        self.polar_dist_mm.fill(float(self.max_range_mm))
        self.polar_updated_at.fill(0.0)
        self.robot_x_mm = 0.0
        self.robot_y_mm = 0.0
        self.robot_theta_deg = 0.0
        self.trajectory = [(0.0, 0.0)]
        self.last_command = "R - DA XOA BAN DO"

    def get_map_base64(self):
        now = time.time()
        dt = max(0.01, min(0.2, now - self.last_render_time))
        self.last_render_time = now

        # Kim quét Radar xoay 300 độ/giây
        self.sweep_angle_deg = (self.sweep_angle_deg + 300.0 * dt) % 360.0

        # Tự động giải phóng các góc mà vật cản đã dời đi sau 1.2 giây để biên mở rộng ra ngay lập tức
        stale_mask = (now - self.polar_updated_at) > 1.2
        self.polar_dist_mm[stale_mask] = float(self.max_range_mm)

        vis_map = np.full((self.map_size, self.map_size, 3), (28, 34, 40), dtype=np.uint8)
        center_x, center_y = self.map_size // 2, self.map_size // 2
        rx = int(center_x + self.robot_x_mm * self.scale)
        ry = int(center_y + self.robot_y_mm * self.scale)

        # 1. Tính đa giác Đường Biên Radar 360 độ từ dữ liệu thực của Lidar
        contour_pts = []
        obstacle_pts = []
        obstacle_count = 0

        for deg in range(360):
            d_mm = float(self.polar_dist_mm[deg])
            rad = math.radians(deg - 90.0)
            px = int(rx + d_mm * self.scale * math.cos(rad))
            py = int(ry + d_mm * self.scale * math.sin(rad))
            contour_pts.append([px, py])

            if d_mm < self.max_range_mm * 0.96:
                obstacle_count += 1
                obstacle_pts.append((px, py))

        if len(contour_pts) == 360:
            poly_arr = np.array([contour_pts], dtype=np.int32)
            overlay = vis_map.copy()
            cv2.fillPoly(overlay, poly_arr, (65, 95, 75))
            cv2.addWeighted(overlay, 0.45, vis_map, 0.55, 0, vis_map)
            cv2.polylines(vis_map, poly_arr, True, (180, 240, 100), 1, cv2.LINE_AA)

        # 2. Vẽ lưới góc 30 độ và các vòng tròn khoảng cách (1m -> 6m)
        for deg_line in range(0, 360, 30):
            rad_l = math.radians(deg_line - 90.0)
            lx = int(center_x + (self.map_size // 2) * math.cos(rad_l))
            ly = int(center_y + (self.map_size // 2) * math.sin(rad_l))
            cv2.line(vis_map, (center_x, center_y), (lx, ly), (50, 60, 70), 1)

        for r_meter in range(1, int(self.max_range_mm // 1000) + 1):
            r_pix = int(r_meter * 1000 * self.scale)
            cv2.circle(vis_map, (rx, ry), r_pix, (85, 105, 115), 1, cv2.LINE_AA)
            cv2.putText(vis_map, f"{r_meter}m", (rx + 4, ry - r_pix + 13),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.38, (160, 190, 200), 1, cv2.LINE_AA)

        # 3. Vẽ các điểm Vật Cản thực tế từ tia Laser YDLidar X2 (màu đỏ tươi, đã bỏ chấm vàng ảo)
        for (px, py) in obstacle_pts:
            if 0 <= px < self.map_size and 0 <= py < self.map_size:
                cv2.circle(vis_map, (px, py), 3, (0, 50, 255), -1, cv2.LINE_AA)

        # 4. Kim quét Radar xoay 360 độ
        sweep_rad = math.radians(self.sweep_angle_deg - 90.0)
        sx = int(rx + (self.map_size * 0.48) * math.cos(sweep_rad))
        sy = int(ry + (self.map_size * 0.48) * math.sin(sweep_rad))
        cv2.line(vis_map, (rx, ry), (sx, sy), (0, 255, 120), 2, cv2.LINE_AA)

        # 5. Vẽ quỹ đạo & vị trí xe AGV
        if len(self.trajectory) > 1:
            pts = []
            for tx_mm, ty_mm in self.trajectory:
                tx = int(center_x + tx_mm * self.scale)
                ty = int(center_y + ty_mm * self.scale)
                pts.append([tx, ty])
            pts_arr = np.array(pts, dtype=np.int32)
            cv2.polylines(vis_map, [pts_arr], False, (255, 160, 0), 2, cv2.LINE_AA)

        robot_color = (255, 0, 255) if self.gripper_active else (0, 230, 80)
        cv2.circle(vis_map, (rx, ry), 8, robot_color, -1, cv2.LINE_AA)
        cv2.circle(vis_map, (rx, ry), 9, (255, 255, 255), 1, cv2.LINE_AA)

        head_rad = math.radians(self.robot_theta_deg - 90.0)
        hx = int(rx + 24 * math.cos(head_rad))
        hy = int(ry + 24 * math.sin(head_rad))
        cv2.arrowedLine(vis_map, (rx, ry), (hx, hy), (100, 255, 100), 2, cv2.LINE_AA, tipLength=0.35)

        # 6. Thanh trạng thái HUD báo rõ ràng đã nhận được tia Laser từ dây TX của Lidar hay chưa
        hw_active = (now - self.last_hw_scan_time) < 3.0
        s3_online = (now - self.last_s3_seen_time) < 6.0

        cv2.rectangle(vis_map, (0, 0), (self.map_size, 54), (18, 22, 28), -1)

        if hw_active:
            status_text = f"YDLidar X2 DANG QUET: {obstacle_count} diem can (Goi #{self.total_packets})"
            status_color = (50, 255, 120)
        elif s3_online:
            status_text = "ESP32-S3 ONLINE | CHUA CO TIN HIEU TU DAY TX CUA LIDAR!"
            status_color = (0, 200, 255)
        else:
            status_text = "Lidar: Waiting for ESP32-S3..."
            status_color = (80, 80, 255)

        cv2.putText(vis_map, status_text, (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.44, status_color, 1, cv2.LINE_AA)

        pose_text = f"Lenh: {self.last_command} | Toa do: ({self.robot_x_mm/1000:.2f}m, {self.robot_y_mm/1000:.2f}m, {int(self.robot_theta_deg)} deg)"
        cv2.putText(vis_map, pose_text, (10, 44), cv2.FONT_HERSHEY_SIMPLEX, 0.43, (210, 215, 220), 1, cv2.LINE_AA)

        ret, buffer = cv2.imencode('.jpg', vis_map, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        if not ret:
            return None
        return base64.b64encode(buffer).decode('utf-8')
