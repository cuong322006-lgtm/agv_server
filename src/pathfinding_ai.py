"""
Module AI Tự Động Tìm Đường (Autonomous Pathfinding & Navigation)
Dành cho Xe Tự Hành AGV

Bao gồm:
1. OccupancyGridMap: Lưới chiếm chỗ 2D tạo từ dữ liệu Lidar 360 độ (polar_dist_mm),
   kèm tầng mở rộng vật cản an toàn (Obstacle Inflation Layer).
2. AStarPlanner: Thuật toán quy hoạch đường đi toàn cục A* với hàm heuristic Euclidean.
3. PathSmoother: Làm mượt quỹ đạo, loại bỏ điểm gãy khúc dư thừa bằng Ray-Casting.
4. PathfindingAI: Quản lý vòng lặp điều khiển bám đường (Path Tracking), giám sát va chạm
   khẩn cấp thời gian thực và phát lệnh động học (W, A, D, G, X) xuống xe.
"""

import asyncio
import math
import time
from typing import List, Tuple, Optional
import numpy as np
import cv2
import heapq


class OccupancyGridMap:
    def __init__(self, size_cells: int = 200, resolution_mm: float = 50.0):
        """
        Lưới 2D bản đồ chiếm chỗ.
        Mặc định: 200 x 200 ô, mỗi ô 50mm x 50mm -> Phạm vi bao quát 10m x 10m.
        Tọa độ thế giới (0, 0) mm nằm tại tâm lưới (size_cells // 2, size_cells // 2).
        """
        self.size = size_cells
        self.resolution_mm = resolution_mm
        self.half_size = size_cells // 2
        self.grid = np.zeros((size_cells, size_cells), dtype=np.uint8)  # 0: trống, 1: vật cản
        self.inflated_grid = np.zeros((size_cells, size_cells), dtype=np.uint8)

    def world_to_grid(self, x_mm: float, y_mm: float) -> Tuple[int, int]:
        gx = int(round(self.half_size + (x_mm / self.resolution_mm)))
        gy = int(round(self.half_size + (y_mm / self.resolution_mm)))
        gx = max(0, min(self.size - 1, gx))
        gy = max(0, min(self.size - 1, gy))
        return gx, gy

    def grid_to_world(self, gx: int, gy: int) -> Tuple[float, float]:
        x_mm = (gx - self.half_size) * self.resolution_mm
        y_mm = (gy - self.half_size) * self.resolution_mm
        return x_mm, y_mm

    def update_from_lidar(
        self,
        polar_dist_mm: np.ndarray,
        robot_x_mm: float,
        robot_y_mm: float,
        robot_theta_deg: float,
        max_valid_range_mm: float = 5500.0,
        inflation_radius_mm: float = 220.0
    ):
        """
        Cập nhật lưới chiếm chỗ từ mảng khoảng cách 360 độ của YDLidar X2.
        Tự động thổi phồng vật cản (Inflation) bằng bán kính thân xe để chống va quẹt.
        """
        self.grid.fill(0)
        
        # 1. Đánh dấu các ô vật cản thực tế từ 360 tia Lidar
        for deg in range(360):
            d_mm = float(polar_dist_mm[deg])
            # Chỉ ghi nhận vật cản hợp lệ (trong tầm quét thực)
            if 60.0 < d_mm < max_valid_range_mm * 0.95:
                # Hệ quy chiếu chuẩn của xe AGV: 0 độ là hướng đầu xe (-90 độ lượng giác)
                rad = math.radians(deg - 90.0)
                # Tọa độ vật cản trong hệ tọa độ thế giới
                ox_mm = robot_x_mm + d_mm * math.cos(rad)
                oy_mm = robot_y_mm + d_mm * math.sin(rad)
                
                gx, gy = self.world_to_grid(ox_mm, oy_mm)
                self.grid[gy, gx] = 1

        # 2. Thổi phồng vật cản (Obstacle Inflation) bằng phép toán hình thái học Dilate
        inflation_cells = max(1, int(round(inflation_radius_mm / self.resolution_mm)))
        kernel_size = 2 * inflation_cells + 1
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
        self.inflated_grid = cv2.dilate(self.grid, kernel, iterations=1)

    def is_cell_free(self, gx: int, gy: int, use_inflation: bool = True) -> bool:
        if 0 <= gx < self.size and 0 <= gy < self.size:
            target_map = self.inflated_grid if use_inflation else self.grid
            return target_map[gy, gx] == 0
        return False

    def find_nearest_free_cell(self, gx: int, gy: int, max_radius_cells: int = 10) -> Tuple[int, int]:
        """Nếu điểm đích hoặc xuất phát vô tình rơi vào vùng đệm an toàn, tìm ô tự do gần nhất"""
        if self.is_cell_free(gx, gy, use_inflation=True):
            return gx, gy
        
        for r in range(1, max_radius_cells + 1):
            for dx in range(-r, r + 1):
                for dy in (-r, r):
                    nx, ny = gx + dx, gy + dy
                    if self.is_cell_free(nx, ny, use_inflation=True):
                        return nx, ny
            for dy in range(-r + 1, r):
                for dx in (-r, r):
                    nx, ny = gx + dx, gy + dy
                    if self.is_cell_free(nx, ny, use_inflation=True):
                        return nx, ny
        return gx, gy


class AStarPlanner:
    def __init__(self, grid_map: OccupancyGridMap):
        self.grid_map = grid_map

    def plan(
        self,
        start_world: Tuple[float, float],
        goal_world: Tuple[float, float]
    ) -> Optional[List[Tuple[float, float]]]:
        """
        Tìm đường từ start_world (x_mm, y_mm) đến goal_world (x_mm, y_mm) bằng thuật toán A*.
        Trả về danh sách các điểm nút dẫn đường [(x_mm, y_mm), ...].
        """
        sx, sy = self.grid_map.world_to_grid(*start_world)
        gx, gy = self.grid_map.world_to_grid(*goal_world)

        # Điều chỉnh nếu điểm rơi vào vùng bị chiếm chỗ/vùng thổi phồng
        sx, sy = self.grid_map.find_nearest_free_cell(sx, sy)
        gx, gy = self.grid_map.find_nearest_free_cell(gx, gy)

        start = (sx, sy)
        goal = (gx, gy)

        if start == goal:
            return [goal_world]

        # 8 hướng di chuyển: 4 hướng thẳng (cost 1.0) và 4 hướng chéo (cost ~1.414)
        neighbors = [
            (0, 1, 1.0), (1, 0, 1.0), (0, -1, 1.0), (-1, 0, 1.0),
            (1, 1, 1.414), (-1, 1, 1.414), (1, -1, 1.414), (-1, -1, 1.414)
        ]

        def heuristic(a: Tuple[int, int], b: Tuple[int, int]) -> float:
            return math.hypot(a[0] - b[0], a[1] - b[1])

        # Priority queue: (f_score, g_score, current_node)
        open_set = []
        heapq.heappush(open_set, (heuristic(start, goal), 0.0, start))
        
        came_from = {}
        g_score = {start: 0.0}
        closed_set = set()

        while open_set:
            _, current_g, current = heapq.heappop(open_set)

            if current in closed_set:
                continue
            closed_set.add(current)

            if current == goal:
                # Tìm thấy đường! Tái tạo lộ trình
                path = []
                curr = current
                while curr in came_from:
                    path.append(self.grid_map.grid_to_world(*curr))
                    curr = came_from[curr]
                path.append(self.grid_map.grid_to_world(*start))
                path.reverse()
                # Điểm cuối cùng gán đúng tọa độ đích mong muốn
                path[-1] = goal_world
                return path

            cx, cy = current
            for dx, dy, cost in neighbors:
                nx, ny = cx + dx, cy + dy
                neighbor = (nx, ny)

                if not self.grid_map.is_cell_free(nx, ny, use_inflation=True):
                    continue

                # Kiểm tra cắt góc chéo qua vật cản
                if dx != 0 and dy != 0:
                    if not self.grid_map.is_cell_free(cx + dx, cy, use_inflation=True) or \
                       not self.grid_map.is_cell_free(cx, cy + dy, use_inflation=True):
                        continue

                tentative_g = current_g + cost
                if tentative_g < g_score.get(neighbor, float('inf')):
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f_score = tentative_g + heuristic(neighbor, goal)
                    heapq.heappush(open_set, (f_score, tentative_g, neighbor))

        # Không tìm thấy đường khả thi
        return None


class PathSmoother:
    @staticmethod
    def smooth_path(path: List[Tuple[float, float]], grid_map: OccupancyGridMap) -> List[Tuple[float, float]]:
        """
        Làm mượt đường đi A*: Loại bỏ các waypoint zíc-zắc trung gian
        nếu giữa 2 điểm có tầm nhìn thẳng không bị chắn bởi vật cản (Ray-Casting line-of-sight).
        """
        if not path or len(path) <= 2:
            return path

        def has_line_of_sight(p1: Tuple[float, float], p2: Tuple[float, float]) -> bool:
            x0, y0 = grid_map.world_to_grid(*p1)
            x1, y1 = grid_map.world_to_grid(*p2)
            
            # Thuật toán vẽ đường thẳng Bresenham để kiểm tra toàn bộ điểm trên đoạn thẳng
            dx = abs(x1 - x0)
            dy = abs(y1 - y0)
            x, y = x0, y0
            n = 1 + dx + dy
            x_inc = 1 if x1 > x0 else -1
            y_inc = 1 if y1 > y0 else -1
            error = dx - dy
            dx *= 2
            dy *= 2

            for _ in range(n):
                if not grid_map.is_cell_free(x, y, use_inflation=True):
                    return False
                if error > 0:
                    x += x_inc
                    error -= dy
                else:
                    y += y_inc
                    error += dx
            return True

        smoothed = [path[0]]
        current_idx = 0

        while current_idx < len(path) - 1:
            furthest_visible = current_idx + 1
            for check_idx in range(len(path) - 1, current_idx, -1):
                if has_line_of_sight(path[current_idx], path[check_idx]):
                    furthest_visible = check_idx
                    break
            smoothed.append(path[furthest_visible])
            current_idx = furthest_visible

        return smoothed


class PathfindingAI:
    """
    Module AI quản lý việc tự hành và bám quỹ đạo:
    - Tiếp nhận tọa độ đích (Goal x, y).
    - Cập nhật Lidar vào Lưới chiếm chỗ Occupancy Grid.
    - Tìm đường A* và làm mượt bằng PathSmoother.
    - Chạy vòng lặp điều khiển bám đường (Path Tracking Controller) theo chu kỳ.
    - Giám sát khoảng cách an toàn phía trước để chủ động phanh khẩn cấp 'G' nếu xuất hiện vật cản bất ngờ.
    """
    def __init__(self, slam_mapper, send_cmd_fn):
        self.slam_mapper = slam_mapper
        self.send_command = send_cmd_fn

        self.grid_map = OccupancyGridMap(size_cells=200, resolution_mm=50.0)
        self.planner = AStarPlanner(self.grid_map)

        # Trạng thái điều hướng
        self.state = "IDLE"  # IDLE, PLANNING, NAVIGATING, OBSTACLE_BLOCKED, REACHED_GOAL, FAILED
        self.goal_x_mm: Optional[float] = None
        self.goal_y_mm: Optional[float] = None
        self.waypoints: List[Tuple[float, float]] = []
        self.current_waypoint_idx = 0

        # Cấu hình ngưỡng điều khiển
        self.waypoint_reached_threshold_mm = 160.0  # Khoảng cách coi như đã chạm waypoint
        self.goal_reached_threshold_mm = 120.0      # Khoảng cách chạm đích cuối cùng
        self.heading_tolerance_deg = 14.0          # Dung sai góc lệch (độ)
        self.emergency_stop_distance_mm = 320.0     # Cự ly phanh khẩn cấp phía trước

        # Tác vụ nền asyncio
        self._nav_task: Optional[asyncio.Task] = None
        self._is_running = False
        self.status_message = "Sẵn sàng nhận lệnh điều hướng"

    async def _dispatch_cmd(self, cmd: str):
        if self.send_command:
            try:
                res = self.send_command(cmd)
                if asyncio.iscoroutine(res):
                    await res
            except Exception as e:
                print(f"[!] Lỗi phát lệnh '{cmd}': {e}")

    def get_status(self) -> dict:
        cur_wp = self.waypoints[self.current_waypoint_idx] if (self.waypoints and self.current_waypoint_idx < len(self.waypoints)) else None
        return {
            "state": self.state,
            "goal": {"x": self.goal_x_mm, "y": self.goal_y_mm} if self.goal_x_mm is not None else None,
            "total_waypoints": len(self.waypoints),
            "current_waypoint_idx": self.current_waypoint_idx,
            "current_waypoint": {"x": cur_wp[0], "y": cur_wp[1]} if cur_wp else None,
            "robot_pose": {
                "x": round(self.slam_mapper.robot_x_mm, 1),
                "y": round(self.slam_mapper.robot_y_mm, 1),
                "theta": round(self.slam_mapper.robot_theta_deg, 1)
            },
            "status_message": self.status_message
        }

    async def set_goal(self, goal_x_mm: float, goal_y_mm: float) -> bool:
        """Thiết lập tọa độ đích đến và khởi chạy tìm đường tự động"""
        await self.stop_navigation()

        self.goal_x_mm = float(goal_x_mm)
        self.goal_y_mm = float(goal_y_mm)
        self.state = "PLANNING"
        self.status_message = f"Đang quy hoạch lộ trình đến ({int(goal_x_mm)}, {int(goal_y_mm)}) mm..."

        # 1. Cập nhật bản đồ vật cản từ Lidar hiện tại
        self.grid_map.update_from_lidar(
            polar_dist_mm=self.slam_mapper.polar_dist_mm,
            robot_x_mm=self.slam_mapper.robot_x_mm,
            robot_y_mm=self.slam_mapper.robot_y_mm,
            robot_theta_deg=self.slam_mapper.robot_theta_deg
        )

        # 2. Chạy thuật toán A*
        start_pt = (self.slam_mapper.robot_x_mm, self.slam_mapper.robot_y_mm)
        goal_pt = (self.goal_x_mm, self.goal_y_mm)
        raw_path = self.planner.plan(start_pt, goal_pt)

        if not raw_path:
            self.state = "FAILED"
            self.status_message = "Không tìm thấy đường đi khả thi tới đích (Bị chắn bởi vật cản)!"
            print(f"[!] [PATHFINDING] {self.status_message}")
            return False

        # 3. Làm mượt lộ trình (Smoothing)
        smoothed_path = PathSmoother.smooth_path(raw_path, self.grid_map)
        self.waypoints = smoothed_path
        self.current_waypoint_idx = 1 if len(smoothed_path) > 1 else 0

        # Gửi đường đi lên slam_mapper để vẽ lên Web Dashboard
        if hasattr(self.slam_mapper, "set_planned_path"):
            self.slam_mapper.set_planned_path(self.waypoints, (self.goal_x_mm, self.goal_y_mm))

        print(f"[*] [PATHFINDING] Đã tìm thấy lộ trình gồm {len(self.waypoints)} waypoints:")
        for idx, wp in enumerate(self.waypoints):
            print(f"    WP#{idx}: ({int(wp[0])}, {int(wp[1])}) mm")

        # 4. Bắt đầu luồng bám đường
        self._is_running = True
        self.state = "NAVIGATING"
        self.status_message = "Đang di chuyển bám đường tới đích..."
        self._nav_task = asyncio.create_task(self._navigation_loop())
        return True

    async def stop_navigation(self):
        """Hủy lộ trình và dừng xe ngay lập tức"""
        self._is_running = False
        if self._nav_task and not self._nav_task.done():
            self._nav_task.cancel()
            try:
                await self._nav_task
            except asyncio.CancelledError:
                pass
        self._nav_task = None
        self.state = "IDLE"
        self.status_message = "Đã dừng điều hướng"
        self.waypoints = []
        self.current_waypoint_idx = 0
        if hasattr(self.slam_mapper, "clear_planned_path"):
            self.slam_mapper.clear_planned_path()
        await self._dispatch_cmd('G')

    def check_front_obstacle(self) -> Tuple[bool, float]:
        """
        Quét cung phía trước đầu xe (góc 345°..359° và 0°..15° theo hướng robot)
        Trả về: (có_vật_cản_gần, khoảng_cách_gần_nhất_mm)
        """
        distances = self.slam_mapper.polar_dist_mm
        theta = getattr(self.slam_mapper, "robot_theta_deg", 0.0)
        # Góc tương đối phía trước đầu xe (345° đến 15°)
        front_rel_angles = list(range(345, 360)) + list(range(0, 16))
        front_dists = []
        for rel_deg in front_rel_angles:
            world_idx = int(round(rel_deg + theta)) % 360
            d = float(distances[world_idx])
            if d > 40.0:
                front_dists.append(d)

        if not front_dists:
            return False, float('inf')

        min_front = min(front_dists)
        is_blocked = min_front < self.emergency_stop_distance_mm
        return is_blocked, min_front

    async def _navigation_loop(self):
        """Vòng lặp điều khiển bám đường tần số cao (15 Hz)"""
        print("[*] [PATHFINDING] Vòng lặp bám đường đã kích hoạt.")
        replan_cooldown = 0.0

        try:
            while self._is_running and self.current_waypoint_idx < len(self.waypoints):
                now = time.time()
                rx = self.slam_mapper.robot_x_mm
                ry = self.slam_mapper.robot_y_mm
                r_theta = self.slam_mapper.robot_theta_deg

                # 1. KIỂM TRA AN TOÀN VA CHẠM THỜI GIAN THỰC
                is_blocked, min_d = self.check_front_obstacle()
                if is_blocked:
                    self.state = "OBSTACLE_BLOCKED"
                    self.status_message = f"Phanh khẩn cấp! Vật cản phía trước cách {int(min_d)} mm"
                    await self._dispatch_cmd('G')
                    await asyncio.sleep(0.4)

                    # Nếu bị kẹt quá 2.5s -> Kích hoạt tìm đường vòng mới (Dynamic Replanning)
                    if now - replan_cooldown > 2.5:
                        replan_cooldown = now
                        print(f"[*] [PATHFINDING] Đang tính toán đường vòng tránh chướng ngại vật...")
                        self.grid_map.update_from_lidar(
                            polar_dist_mm=self.slam_mapper.polar_dist_mm,
                            robot_x_mm=rx,
                            robot_y_mm=ry,
                            robot_theta_deg=r_theta
                        )
                        new_path = self.planner.plan((rx, ry), (self.goal_x_mm, self.goal_y_mm))
                        if new_path:
                            self.waypoints = PathSmoother.smooth_path(new_path, self.grid_map)
                            self.current_waypoint_idx = 1 if len(self.waypoints) > 1 else 0
                            if hasattr(self.slam_mapper, "set_planned_path"):
                                self.slam_mapper.set_planned_path(self.waypoints, (self.goal_x_mm, self.goal_y_mm))
                            self.state = "NAVIGATING"
                            self.status_message = "Đã tìm thấy đường vòng mới, tiếp tục bám đích!"
                            continue
                    await asyncio.sleep(0.1)
                    continue

                self.state = "NAVIGATING"

                # 2. XỬ LÝ WAYPOINT TIẾP THEO
                target_wp = self.waypoints[self.current_waypoint_idx]
                dx = target_wp[0] - rx
                dy = target_wp[1] - ry
                dist_to_wp = math.hypot(dx, dy)

                # Kiểm tra xem đã đến waypoint hiện tại chưa
                is_final_wp = (self.current_waypoint_idx == len(self.waypoints) - 1)
                reach_dist = self.goal_reached_threshold_mm if is_final_wp else self.waypoint_reached_threshold_mm

                if dist_to_wp <= reach_dist:
                    self.current_waypoint_idx += 1
                    if self.current_waypoint_idx >= len(self.waypoints):
                        # ĐÃ ĐẾN ĐÍCH CUỐI CÙNG!
                        self.state = "REACHED_GOAL"
                        self.status_message = f"Đã đến đích thành công tại ({int(self.goal_x_mm)}, {int(self.goal_y_mm)}) mm!"
                        await self._dispatch_cmd('X')
                        print(f"[*] [PATHFINDING] {self.status_message}")
                        break
                    else:
                        print(f"[*] [PATHFINDING] Đã qua Waypoint #{self.current_waypoint_idx - 1}, tiến tới WP #{self.current_waypoint_idx}")
                        continue

                # 3. TÍNH TOÁN SAI SỐ HƯỚNG (HEADING ERROR)
                # Trong hệ quy chiếu slam_mapper:
                # W di chuyển: dx = step * cos(theta - 90 deg), dy = step * sin(theta - 90 deg)
                # Đặt alpha = theta - 90 deg => alpha = atan2(dy, dx) => theta_target = degrees(alpha) + 90
                alpha_rad = math.atan2(dy, dx)
                target_heading_deg = (math.degrees(alpha_rad) + 90.0) % 360.0

                # Sai lệch góc: góc dương => cần quay phải ('D'), góc âm => cần quay trái ('A')
                heading_err = (target_heading_deg - r_theta + 180.0) % 360.0 - 180.0

                # 4. PHÁT LỆNH ĐỘNG HỌC
                if abs(heading_err) > self.heading_tolerance_deg:
                    if heading_err > 0:
                        # Cần quay phải
                        await self._dispatch_cmd('D')
                    else:
                        # Cần quay trái
                        await self._dispatch_cmd('A')
                    await asyncio.sleep(0.08)
                else:
                    # Hướng đã chuẩn, tiến thẳng tới waypoint
                    await self._dispatch_cmd('W')
                    await asyncio.sleep(0.12)

                self.status_message = (
                    f"WP {self.current_waypoint_idx}/{len(self.waypoints)-1} | "
                    f"Cách: {int(dist_to_wp)}mm | Lệch góc: {int(heading_err)}°"
                )

        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.state = "FAILED"
            self.status_message = f"Lỗi trong vòng lặp điều hướng: {e}"
            print(f"[!] [PATHFINDING] {self.status_message}")
        finally:
            self._is_running = False
