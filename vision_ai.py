import os
import cv2
import numpy as np
import base64
import threading
import time
from collections import deque
import torch
from ultralytics import YOLO

# Gioi han PyTorch 2 luong de CPU luon uu tien cho luong Video
torch.set_num_threads(2)

class VisionAI:
    def __init__(self):
        print("[*] Dang nap mo hinh YOLOv8...")
        base_dir = os.path.dirname(os.path.abspath(__file__))
        model_path = os.path.join(base_dir, 'yolov8n.pt')
        try:
            target_model = model_path if os.path.exists(model_path) else 'yolov8n.pt'
            self.model = YOLO(target_model)
            print(f"[*] YOLOv8 da nap thanh cong tu: {target_model}")
        except Exception as e:
            print(f"[!] Loi nap YOLO: {e}")
            self.model = None

        self.source = "push"
        self.qr_detector = cv2.QRCodeDetector()

        self.rotate_mode = 0
        self.flip_h = False
        self.flip_v = False

        self.running = False
        self.video_thread = None
        self.infer_thread = None
        self.source_version = 0

        # Hop thu nhan byte sieu toc (0.001ms) khong lam nghen WebSocket cua ESP32-CAM
        self.incoming_lock = threading.Lock()
        self.incoming_jpg_bytes = None
        self.incoming_seq = 0
        self.incoming_event = threading.Event()

        self.latest_raw_frame = None
        self.raw_frame_id = 0
        self.latest_b64_jpeg = None
        self.rendered_frame_id = 0
        self.frame_lock = threading.Lock()

        self.rx_timestamps = deque(maxlen=40)
        self.ai_timestamps = deque(maxlen=20)

        self.ai_overlay_lock = threading.Lock()
        self.latest_boxes = []
        self.latest_qr_data = ""
        self.latest_qr_pts = None
        self.last_ai_update = 0.0

        self.status_msg = "Dang doi ESP32-CAM gui anh..."
        self.ai_fps = 0.0
        self.cam_fps = 0.0

        # === [MOI NANG CAP - THU THAP DATASET THUNG HANG CHO YOLOV8] ===
        self.dataset_dir = os.path.join(base_dir, 'dataset_thung_hang')
        os.makedirs(self.dataset_dir, exist_ok=True)
        self.auto_capture_active = False
        self.auto_capture_target = 150
        self.auto_capture_count = 0
        self.capture_interval = 0.5
        self.last_capture_time = 0.0
        self.last_captured_frame_id = -1
        self.last_saved_filename = ""

    def _calc_real_fps(self, ts_deque: deque, now: float) -> float:
        while ts_deque and (now - ts_deque[0] > 2.0):
            ts_deque.popleft()
        if len(ts_deque) < 2:
            return 0.0
        span = max(now - ts_deque[0], 0.1)
        return (len(ts_deque) - 1) / span

    def receive_pushed_frame(self, jpg_bytes: bytes) -> bool:
        """
        NHAN TUC THOI (0.001ms): Chi cat mang byte vao bo nho roi tra ve ngay lap tuc
        de cong WebSocket gui chu 'K' ve cho ESP32-CAM ma khong phai doi OpenCV!
        """
        if not jpg_bytes or len(jpg_bytes) < 60:
            return False

        now = time.time()
        self.rx_timestamps.append(now)
        self.cam_fps = self._calc_real_fps(self.rx_timestamps, now)

        with self.incoming_lock:
            self.incoming_jpg_bytes = jpg_bytes
            self.incoming_seq += 1
            seq = self.incoming_seq

        self.incoming_event.set()

        if seq == 1 or seq % 30 == 0:
            print(f"[*] [SMOOTH-CAM] Nhan muot Frame #{seq} ({len(jpg_bytes)} bytes | {self.cam_fps:.1f} FPS)")
        return True

    def get_overlay_metadata(self):
        return None

    def set_transform(self, rotate_mode: int = None, flip_h: bool = None, flip_v: bool = None):
        if rotate_mode is not None:
            self.rotate_mode = rotate_mode % 4
        if flip_h is not None:
            self.flip_h = bool(flip_h)
        if flip_v is not None:
            self.flip_v = bool(flip_v)
        print(f"[*] Da chinh chieu Video: Rotate={self.rotate_mode * 90} deg, FlipH={self.flip_h}, FlipV={self.flip_v}")

    def apply_transform(self, frame):
        if self.rotate_mode == 1:
            frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
        elif self.rotate_mode == 2:
            frame = cv2.rotate(frame, cv2.ROTATE_180)
        elif self.rotate_mode == 3:
            frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)

        if self.flip_h and self.flip_v:
            frame = cv2.flip(frame, -1)
        elif self.flip_h:
            frame = cv2.flip(frame, 1)
        elif self.flip_v:
            frame = cv2.flip(frame, 0)
        return frame

    def start_camera(self):
        if self.running:
            return True
        self.running = True
        self.video_thread = threading.Thread(target=self._video_worker_loop, daemon=True)
        self.infer_thread = threading.Thread(target=self._inference_loop, daemon=True)
        self.video_thread.start()
        self.infer_thread.start()
        return True

    def set_camera_source(self, source_str: str):
        self.source = str(source_str).strip()
        self.start_camera()
        return True

    def _video_worker_loop(self):
        """
        Luong xu ly hinh anh rieng biet (Tach khoi WebSocket):
        - Khu vet ro o vuong JPEG (Deblocking) + Phong muot Cubic len 320x240.
        - Ve khung AI + FPS sieu net, ma hoa Base64 day len Dashboard Web.
        """
        last_seq = -1

        while self.running:
            signaled = self.incoming_event.wait(timeout=0.1)
            if not signaled:
                continue

            self.incoming_event.clear()

            with self.incoming_lock:
                jpg_bytes = self.incoming_jpg_bytes
                cur_seq = self.incoming_seq

            if jpg_bytes is None:
                continue

            last_seq = cur_seq
            frame = cv2.imdecode(np.frombuffer(jpg_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
            if frame is None:
                continue

            frame = self.apply_transform(frame)

            # Neu anh gui len nho hon 320x240 (vi du HQVGA 240x176) thi phong muot Cubic len 320x240,
            # con neu anh da la VGA (640x480) hoac CIF (400x296) thi GIU NGUYEN do phan giai goc sieu net!
            if frame.shape[1] < 320 or frame.shape[0] < 240:
                frame = cv2.resize(frame, (320, 240), interpolation=cv2.INTER_CUBIC)
                smooth = cv2.GaussianBlur(frame, (3, 3), 0)
                frame = cv2.addWeighted(frame, 1.35, smooth, -0.35, 0)

            with self.frame_lock:
                self.latest_raw_frame = frame
                self.raw_frame_id = cur_seq

            # === [TU DONG CHUP ANH SACH (KHONG Dính CHỮ AI/FPS) VAO DATASET] ===
            if self.auto_capture_active:
                now_cap = time.time()
                if (now_cap - self.last_capture_time >= self.capture_interval) and (cur_seq != self.last_captured_frame_id):
                    self._save_clean_frame_to_dataset(frame, cur_seq)
                    self.auto_capture_count += 1
                    self.last_capture_time = now_cap
                    self.last_captured_frame_id = cur_seq
                    if self.auto_capture_count >= self.auto_capture_target:
                        self.auto_capture_active = False
                        print(f"[*] [DATASET] Da tu dong chup du {self.auto_capture_count}/{self.auto_capture_target} anh mau!")

            out = frame.copy()
            with self.ai_overlay_lock:
                if time.time() - self.last_ai_update < 1.5:
                    for (x1, y1, x2, y2, label) in self.latest_boxes:
                        cv2.rectangle(out, (x1, y1), (x2, y2), (0, 216, 214), 2)
                        cv2.putText(out, label, (x1, max(16, y1 - 6)),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 216, 214), 2, cv2.LINE_AA)
                    if self.latest_qr_pts is not None and self.latest_qr_data:
                        pts = self.latest_qr_pts
                        for i in range(len(pts)):
                            pt1 = tuple(pts[i])
                            pt2 = tuple(pts[(i + 1) % len(pts)])
                            cv2.line(out, pt1, pt2, (0, 255, 0), 3)
                        cv2.putText(out, f"QR: {self.latest_qr_data}", (pts[0][0], max(20, pts[0][1] - 10)),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 0), 2, cv2.LINE_AA)

            info_text = f"FPS: {self.cam_fps:.1f} | AI: {self.ai_fps:.1f}"
            cv2.putText(out, info_text, (8, 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.48, (0, 255, 128), 1, cv2.LINE_AA)

            # Nen JPEG 74% de giam 45% dung luong Base64 day qua WebSocket len Web Dashboard (chong giat lag VGA)
            ret, buffer = cv2.imencode('.jpg', out, [int(cv2.IMWRITE_JPEG_QUALITY), 74])
            if ret:
                self.latest_b64_jpeg = base64.b64encode(buffer).decode('utf-8')
                self.rendered_frame_id = cur_seq

    def _inference_loop(self):
        """Luong AI chay doc lap o hau canh"""
        last_processed_id = -1
        qr_step = 0

        while self.running:
            frame = None
            cur_id = -1
            with self.frame_lock:
                if self.latest_raw_frame is not None:
                    frame = self.latest_raw_frame.copy()
                    cur_id = self.raw_frame_id

            if frame is None:
                time.sleep(0.2)
                continue

            if cur_id == last_processed_id:
                time.sleep(0.04)
                continue

            last_processed_id = cur_id

            new_boxes = []
            if self.model:
                results = self.model(frame, imgsz=256, verbose=False)
                if len(results) > 0 and results[0].boxes is not None:
                    names = results[0].names
                    for box in results[0].boxes:
                        coords = box.xyxy[0].cpu().numpy().astype(int)
                        cls_id = int(box.cls[0].item())
                        conf = float(box.conf[0].item())
                        label = f"{names.get(cls_id, str(cls_id))} {conf:.2f}"
                        new_boxes.append((coords[0], coords[1], coords[2], coords[3], label))

            new_qr_data = self.latest_qr_data
            new_qr_pts = self.latest_qr_pts
            qr_step += 1
            if qr_step % 2 == 0:
                try:
                    qr_data, bbox, _ = self.qr_detector.detectAndDecode(frame)
                    if bbox is not None and qr_data:
                        new_qr_data = qr_data
                        new_qr_pts = bbox[0].astype(int)
                    else:
                        new_qr_data = ""
                        new_qr_pts = None
                except Exception:
                    pass

            now = time.time()
            self.ai_timestamps.append(now)
            self.ai_fps = self._calc_real_fps(self.ai_timestamps, now)

            with self.ai_overlay_lock:
                self.latest_boxes = new_boxes
                self.latest_qr_data = new_qr_data
                self.latest_qr_pts = new_qr_pts
                self.last_ai_update = now

            time.sleep(0.12)

    def _save_clean_frame_to_dataset(self, clean_frame, frame_seq: int) -> str:
        os.makedirs(self.dataset_dir, exist_ok=True)
        ts_str = time.strftime("%Y%m%d_%H%M%S")
        ms = int((time.time() % 1) * 1000)
        fname = f"thung_hang_{ts_str}_{ms:03d}_f{frame_seq}.jpg"
        fpath = os.path.join(self.dataset_dir, fname)
        cv2.imwrite(fpath, clean_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
        self.last_saved_filename = fname
        return fname

    def get_total_dataset_files(self) -> int:
        if not os.path.exists(self.dataset_dir):
            return 0
        return len([f for f in os.listdir(self.dataset_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))])

    def capture_single_dataset_image(self) -> dict:
        with self.frame_lock:
            if self.latest_raw_frame is None:
                return {
                    "success": False,
                    "message": "Chưa có hình ảnh từ ESP32-CAM! Hãy bật nguồn ESP32-CAM trước.",
                    "total_files": self.get_total_dataset_files()
                }
            clean_copy = self.latest_raw_frame.copy()
            seq = self.raw_frame_id

        fname = self._save_clean_frame_to_dataset(clean_copy, seq)
        total = self.get_total_dataset_files()
        print(f"[*] [DATASET] Da chup 1 anh mau sach: {fname} (Tong: {total} anh)")
        return {
            "success": True,
            "filename": fname,
            "total_files": total,
            "folder": self.dataset_dir,
            "message": f"Đã lưu ảnh sạch: {fname} (Tổng trong kho: {total} ảnh)"
        }

    def toggle_auto_capture(self, target_count: int = 150, interval_sec: float = 0.5) -> dict:
        if self.auto_capture_active:
            self.auto_capture_active = False
            total = self.get_total_dataset_files()
            return {
                "active": False,
                "captured": self.auto_capture_count,
                "target": self.auto_capture_target,
                "total_files": total,
                "message": f"Đã dừng chụp tự động ({self.auto_capture_count}/{self.auto_capture_target} tấm). Tổng kho: {total} ảnh."
            }
        else:
            with self.frame_lock:
                has_frame = self.latest_raw_frame is not None
            if not has_frame:
                return {
                    "active": False,
                    "captured": 0,
                    "target": target_count,
                    "total_files": self.get_total_dataset_files(),
                    "message": "Chưa có luồng video từ ESP32-CAM để chụp tự động!"
                }
            self.auto_capture_target = max(1, int(target_count))
            self.capture_interval = max(0.1, float(interval_sec))
            self.auto_capture_count = 0
            self.last_capture_time = 0.0
            self.auto_capture_active = True
            total = self.get_total_dataset_files()
            print(f"[*] [DATASET] Bat dau tu dong chup {self.auto_capture_target} anh (moi {self.capture_interval}s)...")
            return {
                "active": True,
                "captured": 0,
                "target": self.auto_capture_target,
                "total_files": total,
                "message": f"Đang tự động chụp 0/{self.auto_capture_target} tấm (0.5s/tấm)..."
            }

    def get_dataset_status(self) -> dict:
        return {
            "active": self.auto_capture_active,
            "captured": self.auto_capture_count,
            "target": self.auto_capture_target,
            "total_files": self.get_total_dataset_files(),
            "last_file": self.last_saved_filename,
            "folder": self.dataset_dir
        }

    def get_processed_frame_base64(self):
        return self.latest_b64_jpeg

    def stop_camera(self):
        self.running = False
