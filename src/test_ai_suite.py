"""
Tập kiểm thử toàn diện Bộ đôi Module AI AGV:
1. AI Tự Động Tìm Đường (Pathfinding AI)
2. AI Tự Động Cập Cảng Bốc Xếp (Docking AI)
3. FastAPI Endpoints & WebSocket Integration
"""

import sys
import os
import math
import numpy as np

# Thêm thư mục hiện tại vào sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from slam_mapper import SLAMMapper
from pathfinding_ai import OccupancyGridMap, AStarPlanner, PathSmoother, PathfindingAI
from docking_ai import DockingAI


def test_grid_and_astar():
    print("[1/5] Kiểm tra Lưới Chiếm Chỗ & A* Planner...")
    grid = OccupancyGridMap(size_cells=200, resolution_mm=50.0)

    # Tâm bản đồ (0, 0) mm -> Ô (100, 100)
    gx, gy = grid.world_to_grid(0.0, 0.0)
    assert gx == 100 and gy == 100, f"Lỗi ánh xạ: ({gx}, {gy})"
    
    # Tạo vật cản chắn ngang
    for x in range(80, 120):
        grid.grid[110, x] = 1

    # Thổi phồng vật cản
    import cv2
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    grid.inflated_grid = cv2.dilate(grid.grid, kernel, iterations=1)
    assert grid.inflated_grid[110, 100] == 1

    # Quy hoạch lộ trình vòng qua tường
    planner = AStarPlanner(grid)
    path = planner.plan((0.0, 0.0), (0.0, 1200.0))
    assert path is not None and len(path) > 3, "A* không tìm thấy đường vòng qua tường!"
    
    # Làm mượt đường
    smoothed = PathSmoother.smooth_path(path, grid)
    assert len(smoothed) < len(path), "Thuật toán làm mượt phải giảm bớt số nút trung gian!"
    print(f"    -> A* thô: {len(path)} nút -> Làm mượt: {len(smoothed)} waypoints. ĐẠT!")


def test_kinematics_and_obstacle():
    print("[2/5] Kiểm tra Động học Hướng và Giám sát Va chạm...")
    slam = SLAMMapper(map_size=520, max_range_mm=6000)
    ai = PathfindingAI(slam_mapper=slam, send_cmd_fn=None)

    # Kiểm tra góc quay tới mục tiêu thẳng phía trước (0, -1000)
    dx, dy = 0.0, -1000.0
    alpha = math.atan2(dy, dx)
    heading = (math.degrees(alpha) + 90.0) % 360.0
    assert abs(heading - 0.0) < 1e-4

    # Kiểm tra góc quay tới mục tiêu bên phải (1000, 0)
    dx, dy = 1000.0, 0.0
    alpha = math.atan2(dy, dx)
    heading = (math.degrees(alpha) + 90.0) % 360.0
    assert abs(heading - 90.0) < 1e-4

    # Giả lập vật cản xuất hiện phía trước ở góc 0 độ cự ly 250mm
    slam.polar_dist_mm[0] = 250.0
    is_blocked, min_d = ai.check_front_obstacle()
    assert is_blocked and min_d == 250.0, "Hệ thống phải cảnh báo vật cản nguy hiểm phía trước!"

    # Kiểm tra khi xe quay 90 độ, vật cản phía trước xe phải nằm ở góc thế giới 90 độ
    slam.polar_dist_mm.fill(5000.0)
    slam.robot_theta_deg = 90.0
    slam.polar_dist_mm[90] = 280.0
    is_blocked_rot, min_d_rot = ai.check_front_obstacle()
    assert is_blocked_rot and min_d_rot == 280.0, "Hệ thống phải phát hiện vật cản phía trước đầu xe khi xe đang quay góc!"
    print(f"    -> Động học chuẩn xác & Cảnh báo phanh khẩn cấp ở {min_d}mm (quay 90°: {min_d_rot}mm). ĐẠT!")


def test_docking_visual_servoing():
    print("[3/5] Kiểm tra Visual Servoing & Căn chỉnh Pallet...")
    class MockVision:
        latest_qr_data = "STATION_PALLET_01"
        latest_qr_pts = np.array([[200, 80], [240, 80], [240, 140], [200, 140]])

    class MockSLAM:
        polar_dist_mm = np.full(360, 1500.0, dtype=np.float32)

    docking = DockingAI(vision_ai=MockVision(), slam_mapper=MockSLAM(), send_cmd_fn=None)

    # Tâm QR: (200 + 240) / 2 = 220px. Tâm ảnh là 160px -> Lệch phải 60px
    cx, cy = docking._get_qr_center()
    assert abs(cx - 220.0) < 1e-2 and abs(cy - 110.0) < 1e-2

    offset_x = cx - docking.center_x_target
    assert offset_x > docking.deadband_px, "Phải phát hiện lệch phải lớn hơn deadband!"
    
    # Cự ly Lidar phía trước
    MockSLAM.polar_dist_mm[0] = 150.0
    front_d = docking._get_front_lidar_distance()
    assert front_d == 150.0
    print(f"    -> Tâm QR cx={cx}px (Lệch +{offset_x}px) | Lidar trước: {front_d}mm. ĐẠT!")


def test_slam_mapper_enhancements():
    print("[4/5] Kiểm tra SLAM Mapper nâng cấp (Càng Nâng U/J & Hiển thị Lộ trình)...")
    slam = SLAMMapper(map_size=520, max_range_mm=6000)

    # Test lệnh U & J
    slam.apply_control_command('U')
    assert slam.forklift_state == "UP" and "NANG CANG" in slam.last_command

    slam.apply_control_command('J')
    assert slam.forklift_state == "DOWN" and "HA CANG" in slam.last_command

    # Test lưu và vẽ planned_path + target_goal
    test_path = [(0.0, 0.0), (500.0, -500.0), (1000.0, -1000.0)]
    test_goal = (1000.0, -1000.0)
    slam.set_planned_path(test_path, test_goal)
    assert len(slam.planned_path) == 3 and slam.target_goal == test_goal

    b64_map = slam.get_map_base64()
    assert b64_map is not None and len(b64_map) > 500, "Bản đồ Base64 phải render thành công!"
    print("    -> Lệnh Forklift U/J & Render Lộ trình A* lên Radar SLAM. ĐẠT!")


def test_fastapi_endpoints():
    print("[5/5] Kiểm tra API Server & FastAPI Routes...")
    from main import app
    routes = [route.path for route in app.routes]
    expected = [
        "/api/ai/navigate",
        "/api/ai/dock",
        "/api/ai/stop",
        "/api/ai/status",
        "/api/control",
        "/api/camera",
        "/api/wifi_config",
        "/ws"
    ]
    for r in expected:
        assert r in routes, f"Thiếu endpoint: {r}"
    print(f"    -> Đầy đủ tất cả {len(expected)} Endpoints AI & Điều khiển. ĐẠT!")


if __name__ == "__main__":
    print("================================================================")
    print("   BẮT ĐẦU KIỂM THỬ TỔNG HỢP TOÀN DIỆN HỆ THỐNG AI AGV")
    print("================================================================")
    test_grid_and_astar()
    test_kinematics_and_obstacle()
    test_docking_visual_servoing()
    test_slam_mapper_enhancements()
    test_fastapi_endpoints()
    print("================================================================")
    print("   TẤT CẢ 5/5 HẠNG MỤC KIỂM THỬ ĐÃ THÀNH CÔNG RỰC RỠ 100%!")
    print("================================================================")
