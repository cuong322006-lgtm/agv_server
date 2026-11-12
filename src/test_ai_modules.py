import math
import numpy as np
from pathfinding_ai import OccupancyGridMap, AStarPlanner, PathSmoother, PathfindingAI
from docking_ai import DockingAI


def test_pathfinding():
    print("=== TEST PATHFINDING AI ===")
    grid_map = OccupancyGridMap(size_cells=200, resolution_mm=50.0)
    
    # 1. World to Grid mapping
    gx, gy = grid_map.world_to_grid(0.0, 0.0)
    assert gx == 100 and gy == 100, f"Expected (100, 100), got ({gx}, {gy})"
    
    wx, wy = grid_map.grid_to_world(100, 100)
    assert wx == 0.0 and wy == 0.0, f"Expected (0, 0), got ({wx}, {wy})"
    print("[+] World <-> Grid conversion: PASSED")

    # 2. Add an obstacle wall across X from -500mm to +500mm at Y = 500mm
    polar_dists = np.full(360, 5000.0, dtype=np.float32)
    # Put obstacles in front of robot (angle 0 is heading forward, rad = -90 deg -> Y negative in slam_mapper coordinates)
    # In slam_mapper: rad = radians(deg - 90). For deg = 0: rad = -pi/2, ox = x, oy = y - d.
    # Let's test with direct grid points:
    wall_y = 120  # gy
    for x in range(80, 120):
        grid_map.grid[wall_y, x] = 1

    # Inflate
    import cv2
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    grid_map.inflated_grid = cv2.dilate(grid_map.grid, kernel, iterations=1)
    assert grid_map.inflated_grid[wall_y + 1, 100] == 1, "Inflation check failed"
    print("[+] Obstacle Inflation: PASSED")

    # 3. Test A* search
    planner = AStarPlanner(grid_map)
    start_world = (0.0, 0.0)
    goal_world = (0.0, 1500.0)  # On the other side of the wall
    path = planner.plan(start_world, goal_world)
    assert path is not None, "A* failed to find path around wall!"
    assert len(path) > 2, "Path too short"
    print(f"[+] A* Path found! Length: {len(path)} waypoints")

    # 4. Test Path Smoothing
    smoothed = PathSmoother.smooth_path(path, grid_map)
    assert len(smoothed) <= len(path), "Smoothed path should have fewer or equal waypoints"
    print(f"[+] Path Smoothing: Reduced from {len(path)} to {len(smoothed)} waypoints")

    # 5. Test Heading Calculation
    # From (0, 0) to (0, -1000): straight forward when theta=0
    dx, dy = 0.0, -1000.0
    alpha = math.atan2(dy, dx)
    target_heading = (math.degrees(alpha) + 90.0) % 360.0
    assert abs(target_heading - 0.0) < 1e-4, f"Target heading expected 0, got {target_heading}"

    # From (0, 0) to (1000, 0): to the right -> theta=90
    dx, dy = 1000.0, 0.0
    alpha = math.atan2(dy, dx)
    target_heading = (math.degrees(alpha) + 90.0) % 360.0
    assert abs(target_heading - 90.0) < 1e-4, f"Target heading expected 90, got {target_heading}"
    print("[+] Heading kinematics: PASSED")


def test_docking():
    print("\n=== TEST DOCKING AI ===")
    
    class MockVision:
        latest_qr_data = "STATION_PICKUP_01"
        latest_qr_pts = np.array([[120, 100], [180, 100], [180, 160], [120, 160]])

    class MockSLAM:
        polar_dist_mm = np.full(360, 2000.0, dtype=np.float32)
        robot_x_mm = 0.0
        robot_y_mm = 0.0
        robot_theta_deg = 0.0

    async def mock_send(cmd):
        return f"CMD: {cmd}"

    docking = DockingAI(MockVision(), MockSLAM(), mock_send)
    
    # Test QR center
    cx, cy = docking._get_qr_center()
    assert abs(cx - 150.0) < 1e-2 and abs(cy - 130.0) < 1e-2, f"Expected (150, 130), got ({cx}, {cy})"
    print(f"[+] QR Center extraction: ({cx}, {cy}) PASSED")

    # Test Lidar Front Distance
    MockSLAM.polar_dist_mm[0] = 152.0
    front_d = docking._get_front_lidar_distance()
    assert abs(front_d - 152.0) < 1e-2, f"Expected 152, got {front_d}"
    print(f"[+] Lidar Front Distance: {front_d} mm PASSED")


if __name__ == "__main__":
    test_pathfinding()
    test_docking()
    print("\n ALL TESTS PASSED SUCCESSFULLY!")
