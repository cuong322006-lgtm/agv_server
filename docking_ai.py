"""
Module AI Tự Động Cập Cảng Bốc Xếp Hàng (Autonomous Docking & Cargo Handling)
Dành cho Xe Tự Hành AGV

Bao gồm:
1. Visual Servoing Controller: Điều khiển vi sai hướng xe dựa trên vị trí tâm mã QR
   trên khung hình Camera (320x240).
2. Lidar Distance Fusion: Đo khoảng cách thực tế góc 0° phía trước bằng YDLidar X2
   để tiếp cận pallet chính xác từng milimét.
3. Cargo Handling State Machine: Máy trạng thái tự động thực hiện quy trình:
   Tìm kiếm trạm -> Căn chỉnh tâm -> Tiếp cận cự ly chuẩn (150mm) ->
   Nâng/Hạ càng ('U'/'J') hoặc Gắp hàng ('G') -> Lùi an toàn ra khỏi trạm.
"""

import asyncio
import time
from typing import Optional, Tuple


class DockingAI:
    def __init__(self, vision_ai, slam_mapper, send_cmd_fn):
        self.vision_ai = vision_ai
        self.slam_mapper = slam_mapper
        self.send_command = send_cmd_fn

        # Cấu hình tham số căn chỉnh
        self.image_width = 320
        self.image_height = 240
        self.center_x_target = 160.0    # Tâm lý tưởng của ảnh 320px
        self.deadband_px = 18.0         # Vùng dung sai: 160 +- 18px (142px đến 178px)
        
        self.target_dock_distance_mm = 150.0  # Khoảng cách dừng chuẩn milimét tới pallet
        self.distance_tolerance_mm = 25.0

        # Trạng thái máy
        self.state = "IDLE"  # IDLE, SEARCHING, ALIGNING, APPROACHING, PRECISION_DOCK, CARGO_ACTION, UNDOCKING, COMPLETED, FAILED
        self.target_tag: str = ""
        self.action: str = "lift"  # "lift" (nâng càng 'U'), "drop" (hạ càng 'J'), "gripper" ('G'), "dock_only"
        self.status_message = "Sẵn sàng nhận lệnh cập cảng bốc xếp"

        self._is_running = False
        self._dock_task: Optional[asyncio.Task] = None

    async def _dispatch_cmd(self, cmd: str):
        if self.send_command:
            try:
                res = self.send_command(cmd)
                if asyncio.iscoroutine(res):
                    await res
            except Exception as e:
                print(f"[!] Lỗi phát lệnh '{cmd}': {e}")

    def get_status(self) -> dict:
        qr_center = self._get_qr_center()
        front_dist = self._get_front_lidar_distance()
        return {
            "state": self.state,
            "target_tag": self.target_tag,
            "action": self.action,
            "qr_detected": bool(self.vision_ai.latest_qr_data),
            "current_qr_tag": self.vision_ai.latest_qr_data,
            "qr_center_x": qr_center[0] if qr_center else None,
            "front_distance_mm": round(front_dist, 1) if front_dist < 9999 else None,
            "status_message": self.status_message
        }

    def _get_qr_center(self) -> Optional[Tuple[float, float]]:
        """Lấy tọa độ tâm (cx, cy) của mã QR trên ảnh 320x240"""
        pts = self.vision_ai.latest_qr_pts
        if pts is not None and len(pts) >= 4:
            cx = float(np_mean_x := sum(p[0] for p in pts) / len(pts))
            cy = float(np_mean_y := sum(p[1] for p in pts) / len(pts))
            return cx, cy
        return None

    def _get_front_lidar_distance(self) -> float:
        """Đo khoảng cách thực tế phía trước xe từ chùm tia Lidar (góc 355°..359° và 0°..5° theo hướng robot)"""
        distances = self.slam_mapper.polar_dist_mm
        theta = getattr(self.slam_mapper, "robot_theta_deg", 0.0)
        front_rel_angles = list(range(355, 360)) + list(range(0, 6))
        valid_dists = []
        for rel_deg in front_rel_angles:
            world_idx = int(round(rel_deg + theta)) % 360
            d = float(distances[world_idx])
            if d > 40.0:
                valid_dists.append(d)
        if valid_dists:
            return min(valid_dists)
        return float('inf')

    async def start_docking(self, target_tag: str = "", action: str = "lift") -> bool:
        """
        Khởi chạy tiến trình bốc dỡ hàng tự động:
        - target_tag: Mã chuỗi QR của trạm (bỏ trống "" nếu chấp nhận bất kỳ mã trạm nào).
        - action: "lift" (nâng hàng 'U'), "drop" (hạ hàng 'J'), "gripper" (kẹp 'G'), "dock_only" (chỉ đỗ xe).
        """
        await self.stop_docking()

        self.target_tag = (target_tag or "").strip()
        self.action = action.strip().lower()
        self._is_running = True
        self.state = "SEARCHING"
        self.status_message = f"Bắt đầu chu trình tự động bốc xếp hàng (Hành động: {self.action.upper()})..."

        print(f"[*] [DOCKING-AI] Bắt đầu tự động cập cảng. Tag='{self.target_tag}', Action='{self.action}'")
        self._dock_task = asyncio.create_task(self._docking_loop())
        return True

    async def stop_docking(self):
        """Hủy tiến trình bốc dỡ hàng và dừng xe an toàn"""
        self._is_running = False
        if self._dock_task and not self._dock_task.done():
            self._dock_task.cancel()
            try:
                await self._dock_task
            except asyncio.CancelledError:
                pass
        self._dock_task = None
        self.state = "IDLE"
        self.status_message = "Đã dừng tiến trình cập cảng"
        await self._dispatch_cmd('X')

    async def _docking_loop(self):
        """Vòng lặp máy trạng thái điều khiển Visual Servoing & Bốc hàng"""
        search_turns = 0
        last_seen_qr_time = time.time()

        try:
            while self._is_running:
                now = time.time()
                qr_data = self.vision_ai.latest_qr_data
                qr_center = self._get_qr_center()
                front_dist_mm = self._get_front_lidar_distance()

                # Kiểm tra tính hợp lệ của mã QR đối chiếu với mục tiêu
                tag_matched = False
                if qr_data:
                    if not self.target_tag or (self.target_tag.upper() in qr_data.upper()):
                        tag_matched = True
                        last_seen_qr_time = now

                # -----------------------------------------------------------------
                # TRẠNG THÁI 1: SEARCHING (Tìm kiếm trạm hàng)
                # -----------------------------------------------------------------
                if self.state == "SEARCHING":
                    if tag_matched and qr_center:
                        print(f"[*] [DOCKING-AI] Đã bắt được mục tiêu '{qr_data}'! Chuyển sang căn chỉnh hướng...")
                        self.state = "ALIGNING"
                        continue

                    # Nếu chưa thấy mã QR, xoay nhẹ quét tìm xung quanh
                    self.status_message = "Đang quay nhẹ quét tìm mã QR trạm hàng..."
                    search_turns += 1
                    if search_turns <= 8:
                        await self._dispatch_cmd('D')  # Quay phải nhẹ
                    elif search_turns <= 20:
                        await self._dispatch_cmd('A')  # Đảo chiều quay trái
                    else:
                        search_turns = 0

                    await asyncio.sleep(0.3)
                    continue

                # Nếu đang ở các bước sau mà mất dấu QR quá 4.5 giây:
                if not tag_matched and (now - last_seen_qr_time > 4.5) and self.state not in ["CARGO_ACTION", "UNDOCKING"]:
                    print("[!] [DOCKING-AI] Mất dấu mã QR trong tầm nhìn! Quay lại trạng thái tìm kiếm...")
                    self.state = "SEARCHING"
                    search_turns = 0
                    continue

                # -----------------------------------------------------------------
                # TRẠNG THÁI 2: ALIGNING (Căn chỉnh tâm mã QR vào giữa khung hình)
                # -----------------------------------------------------------------
                if self.state == "ALIGNING":
                    if not qr_center:
                        await asyncio.sleep(0.08)
                        continue

                    cx, cy = qr_center
                    offset_x = cx - self.center_x_target

                    if abs(offset_x) > self.deadband_px:
                        if offset_x < 0:
                            # Mã nằm bên trái -> quay trái xe 'A'
                            self.status_message = f"Căn chỉnh: Lệch trái {int(abs(offset_x))}px -> Quay trái (A)"
                            await self._dispatch_cmd('A')
                        else:
                            # Mã nằm bên phải -> quay phải xe 'D'
                            self.status_message = f"Căn chỉnh: Lệch phải {int(offset_x)}px -> Quay phải (D)"
                            await self._dispatch_cmd('D')
                        await asyncio.sleep(0.12)
                    else:
                        # Đã thẳng tâm!
                        print("[*] [DOCKING-AI] Đã thẳng tâm pallet! Bắt đầu tiến tới...")
                        self.state = "APPROACHING"
                        await asyncio.sleep(0.05)
                    continue

                # -----------------------------------------------------------------
                # TRẠNG THÁI 3: APPROACHING (Tiến lại gần trạm hàng)
                # -----------------------------------------------------------------
                if self.state == "APPROACHING":
                    # Kiểm tra khoảng cách Lidar phía trước
                    if front_dist_mm <= 350.0:
                        print(f"[*] [DOCKING-AI] Cự ly Lidar đã vào phạm vi gần ({int(front_dist_mm)}mm) -> Chuyển sang Precision Dock!")
                        self.state = "PRECISION_DOCK"
                        continue

                    # Tiếp tục hiệu chỉnh tâm nếu lệch
                    if qr_center:
                        cx, _ = qr_center
                        offset_x = cx - self.center_x_target
                        if abs(offset_x) > self.deadband_px * 1.5:
                            # Lệch tương đối nhiều -> nhích nhẹ để nắn thẳng lại
                            cmd = 'A' if offset_x < 0 else 'D'
                            await self._dispatch_cmd(cmd)
                            await asyncio.sleep(0.08)
                            continue

                    # Thẳng hướng -> Tiến tới 'W'
                    self.status_message = f"Đang tiến vào trạm | Lidar trước: {int(front_dist_mm)}mm"
                    await self._dispatch_cmd('W')
                    await asyncio.sleep(0.18)
                    continue

                # -----------------------------------------------------------------
                # TRẠNG THÁI 4: PRECISION_DOCK (Căn chỉnh cự ly siêu gần milimét)
                # -----------------------------------------------------------------
                if self.state == "PRECISION_DOCK":
                    target_d = self.target_dock_distance_mm

                    if front_dist_mm <= target_d + self.distance_tolerance_mm:
                        # Đã vào đúng cự ly cập cảng chuẩn!
                        print(f"[*] [DOCKING-AI] Cập cảng chuẩn xác! Cự ly: {int(front_dist_mm)}mm. Khóa phanh xe!")
                        await self._dispatch_cmd('G')  # Phanh khẩn cấp lập tức
                        await asyncio.sleep(0.4)
                        self.state = "CARGO_ACTION"
                        continue

                    # Vẫn còn cách xa một chút -> Nhấp từng bước tiến ngắn
                    self.status_message = f"Áp sát pallet: {int(front_dist_mm)}mm -> Mục tiêu: {int(target_d)}mm"
                    await self._dispatch_cmd('W')
                    await asyncio.sleep(0.09)
                    await self._dispatch_cmd('X')  # Nhả ngay để xe không lao quá đà
                    await asyncio.sleep(0.15)
                    continue

                # -----------------------------------------------------------------
                # TRẠNG THÁI 5: CARGO_ACTION (Thực hiện bốc xếp hàng: Nâng/Hạ/Gắp)
                # -----------------------------------------------------------------
                if self.state == "CARGO_ACTION":
                    if self.action == "lift":
                        self.status_message = "Đang kích hoạt cơ cấu NÂNG CÀNG gắp hàng (Lệnh 'U')..."
                        print("[*] [DOCKING-AI] Gửi lệnh NÂNG CÀNG (U) xuống ESP32-S3...")
                        await self._dispatch_cmd('U')
                        await asyncio.sleep(2.5)  # Chờ cơ cấu nâng cơ khí hoàn tất
                    elif self.action == "drop":
                        self.status_message = "Đang kích hoạt cơ cấu HẠ CÀNG nhả hàng (Lệnh 'J')..."
                        print("[*] [DOCKING-AI] Gửi lệnh HẠ CÀNG (J) xuống ESP32-S3...")
                        await self._dispatch_cmd('J')
                        await asyncio.sleep(2.5)  # Chờ cơ cấu hạ cơ khí hoàn tất
                    elif self.action == "gripper":
                        self.status_message = "Đang kích hoạt TAY GẮP kẹp hàng (Lệnh 'G')..."
                        print("[*] [DOCKING-AI] Gửi lệnh TAY GẮP (G) xuống ESP32-S3...")
                        await self._dispatch_cmd('G')
                        await asyncio.sleep(1.8)
                    else:
                        self.status_message = "Chế độ Dock-Only: Xe đã đỗ thành công tại trạm hàng."
                        await asyncio.sleep(0.5)

                    print("[*] [DOCKING-AI] Thao tác bốc dỡ hoàn tất! Bắt đầu lùi xe an toàn...")
                    self.state = "UNDOCKING"
                    continue

                # -----------------------------------------------------------------
                # TRẠNG THÁI 6: UNDOCKING (Lùi xe an toàn ra khỏi trạm)
                # -----------------------------------------------------------------
                if self.state == "UNDOCKING":
                    self.status_message = "Đang lùi an toàn ra khỏi trạm hàng..."
                    # Lùi 3 bước nhịp nhàng (-48cm) để xe thoát khỏi chân kệ pallet
                    for step in range(3):
                        await self._dispatch_cmd('S')
                        await asyncio.sleep(0.2)
                    await self._dispatch_cmd('X')
                    await asyncio.sleep(0.3)

                    self.state = "COMPLETED"
                    self.status_message = f"HOÀN THÀNH XUẤT SẮC CHU TRÌNH BỐC DỠ ({self.action.upper()}) TẠI TRẠM!"
                    print(f"[*] [DOCKING-AI] {self.status_message}")
                    break

        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.state = "FAILED"
            self.status_message = f"Lỗi trong quá trình cập cảng: {e}"
            print(f"[!] [DOCKING-AI] {self.status_message}")
        finally:
            self._is_running = False
