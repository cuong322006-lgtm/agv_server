import asyncio
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Header, HTTPException, Response
from fastapi.responses import HTMLResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel
import uvicorn
import io
import zipfile
import time as py_time
from lidar_tcp_server import LidarTCPServer
from vision_ai import VisionAI
from slam_mapper import SLAMMapper
import json
import sys

def get_project_root() -> str:
    d = os.path.dirname(os.path.abspath(__file__))
    if d not in sys.path:
        sys.path.insert(0, d)
    return os.path.dirname(d) if os.path.basename(d).lower() == "src" else d

PROJECT_ROOT = get_project_root()

app = FastAPI(title="AGV Server Dashboard (Secure Multi-Network)")

# ================= MÃ KHÓA BẢO MẬT CHỐNG LỘ DỮ LIỆU =================
# Chỉ những mạch ESP32 gửi kèm Header "X-AGV-Key: Cuong_AGV_Secret_2026" mới được phép đẩy dữ liệu!
AGV_SECRET_KEY = os.environ.get("AGV_SECRET_KEY", "Cuong_AGV_Secret_2026")

# Khởi tạo các module
slam_mapper = SLAMMapper(map_size=500, max_range_mm=5000)
lidar_server = LidarTCPServer(host='0.0.0.0', port=8888, slam_mapper=slam_mapper)
vision_ai = VisionAI()

class CameraSourceRequest(BaseModel):
    source: str

class CameraTransformRequest(BaseModel):
    action: str

class ControlCommandRequest(BaseModel):
    command: str

# === [MỚI NÂNG CẤP - ĐỔI WIFI TỪ XA CHO CẢ 2 MẠCH ESP32 KHÔNG CẦN NẠP LẠI CODE] ===
class RemoteWiFiConfigRequest(BaseModel):
    ssid: str
    password: str

pending_cam_wifi_cfg = None
pending_s3_wifi_cfg = None
# ==================================================================================

def verify_secret_key(x_agv_key: str):
    if x_agv_key != AGV_SECRET_KEY:
        print(f"[!] CẢNH BÁO BẢO MẬT: Từ chối kết nối trái phép (Sai X-AGV-Key: {x_agv_key})")
        raise HTTPException(status_code=403, detail="Forbidden: Invalid X-AGV-Key")

# ================= API NHẬN DỮ LIỆU ĐẨY LÊN TỪ ESP32 (XUYÊN MẠNG) =================

import socket as py_socket

def get_current_lan_ip() -> str:
    try:
        s = py_socket.socket(py_socket.AF_INET, py_socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

@app.post("/api/push_frame", response_class=PlainTextResponse)
async def push_frame(request: Request, x_agv_key: str = Header(default="")):
    """
    ESP32-CAM chủ động bắn ảnh JPEG lên địa chỉ này (kèm mật khẩu X-AGV-Key).
    Trả về địa chỉ LAN hiện tại của Laptop để nếu ESP32-CAM ở cùng mạng thì tự động
    chuyển sang bắn trực tiếp LAN (25 FPS), nếu khác mạng thì giữ nguyên Tunnel!
    """
    verify_secret_key(x_agv_key)
    jpg_bytes = await request.body()
    vision_ai.receive_pushed_frame(jpg_bytes)
    return f"http://{get_current_lan_ip()}:8000/api/push_frame"

@app.post("/api/push_lidar", response_class=PlainTextResponse)
async def push_lidar(request: Request, x_agv_key: str = Header(default="")):
    """
    ESP32-S3 chủ động bắn gói dữ liệu YDLidar X2 lên địa chỉ này (kèm mật khẩu X-AGV-Key)
    và nhận lại ngay lệnh điều khiển (W, A, S, D, G, X) trong phần trả lời!
    """
    verify_secret_key(x_agv_key)
    raw_bytes = await request.body()
    cmd = lidar_server.receive_pushed_lidar(raw_bytes)
    return cmd

@app.websocket("/ws/push_frame")
async def ws_push_frame(websocket: WebSocket):
    """
    Đường ống WebSocket Siêu Tốc (WSS/WS) qua Đường Hầm Cloudflare cho ESP32-CAM:
    ESP32-CAM chỉ cần kết nối 1 lần và bắn liên hoàn các khung hình JPEG lên mà KHÔNG CẦN ĐỢI phản hồi!
    Loại bỏ 100% độ trễ khứ hồi (Round-Trip) và xóa vĩnh viễn lỗi -11!
    """
    key = websocket.headers.get("x-agv-key", "")
    if key != AGV_SECRET_KEY:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    print("[*] [WSS-TUNNEL] ESP32-CAM đã mở đường ống WebSocket Siêu Tốc qua Đường Hầm!")
    try:
        while True:
            jpg_bytes = await websocket.receive_bytes()
            # === [MỚI NÂNG CẤP - BẮN CẤU HÌNH WIFI MỚI XUỐNG ESP32-CAM NẾU CÓ] ===
            global pending_cam_wifi_cfg
            if pending_cam_wifi_cfg:
                await websocket.send_text(pending_cam_wifi_cfg)
                print(f"[*] [WIFI-OTA] Đã bắn cấu hình Wi-Fi mới xuống ESP32-CAM!")
                pending_cam_wifi_cfg = None
            else:
                # Phản hồi 1 ký tự 'K' ngay lập tức để chống đầy bộ đệm mạng (Zero Bufferbloat)
                await websocket.send_text("K")
            vision_ai.receive_pushed_frame(jpg_bytes)
    except Exception as e:
        print(f"[*] [WSS-TUNNEL] ESP32-CAM ngắt kết nối WebSocket: {e}")

@app.websocket("/ws/push_lidar")
async def ws_push_lidar(websocket: WebSocket):
    """
    Đường ống WebSocket 2 chiều qua Đường Hầm cho ESP32-S3 (Lidar + Điều khiển tức thì).
    """
    key = websocket.headers.get("x-agv-key", "")
    if key != AGV_SECRET_KEY:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    slam_mapper.notify_s3_heartbeat()
    print("[*] [WSS-TUNNEL] ESP32-S3 (Lidar & Control) đã mở đường ống WebSocket 2 chiều qua Đường Hầm!")
    try:
        while True:
            # === [MỚI NÂNG CẤP - BẮN CẤU HÌNH WIFI MỚI XUỐNG ESP32-S3 NẾU CÓ] ===
            global pending_s3_wifi_cfg
            if pending_s3_wifi_cfg:
                await websocket.send_text(pending_s3_wifi_cfg)
                print(f"[*] [WIFI-OTA] Đã bắn cấu hình Wi-Fi mới xuống ESP32-S3!")
                pending_s3_wifi_cfg = None
            try:
                raw_bytes = await asyncio.wait_for(websocket.receive_bytes(), timeout=0.05)
                if len(raw_bytes) > 1:
                    cmd = lidar_server.receive_pushed_lidar(raw_bytes)
                else:
                    cmd = lidar_server.receive_pushed_lidar(b"")
                await websocket.send_text(cmd if cmd else "K")
            except asyncio.TimeoutError:
                cmd = lidar_server.receive_pushed_lidar(b"")
                if cmd:
                    await websocket.send_text(cmd)
    except Exception as e:
        print(f"[*] [WSS-TUNNEL] ESP32-S3 ngắt kết nối WebSocket: {e}")

HTML = """
<!DOCTYPE html>
<html>
    <head>
        <meta charset="utf-8">
        <title>AGV Web Dashboard - Secure Push Mode</title>
        <style>
            body { font-family: 'Segoe UI', sans-serif; display: flex; flex-direction: column; align-items: center; background-color: #1e272e; color: #f5f6fa; margin: 0; padding: 15px; }
            h1 { margin: 5px 0 8px 0; color: #00d8d6; font-size: 24px; }
            .badge { background: #05c46b; color: #1e272e; padding: 4px 12px; border-radius: 20px; font-size: 13px; font-weight: bold; margin-bottom: 12px; }
            .toolbar { display: flex; gap: 10px; align-items: center; background: #2f3640; padding: 10px 18px; border-radius: 10px; margin-bottom: 12px; flex-wrap: wrap; justify-content: center; }
            .toolbar input { padding: 8px 12px; border-radius: 6px; border: 1px solid #57606f; width: 220px; background: #1e272e; color: white; }
            .btn { padding: 8px 13px; border: none; border-radius: 6px; cursor: pointer; font-weight: bold; background: #0fbcf9; color: #1e272e; transition: 0.15s; }
            .btn:hover { background: #4bcffa; }
            .btn-secondary { background: #a55eea; color: white; }
            .btn-secondary:hover { background: #b87ff3; }
            .btn-danger { background: #ff5e57; color: white; }
            .container { display: flex; gap: 20px; flex-wrap: wrap; justify-content: center; }
            .box { border: 2px solid #485460; border-radius: 10px; padding: 8px; width: 520px; height: 420px; display: flex; align-items: center; justify-content: center; background-color: #000; color: #ccc; overflow: hidden; position: relative; }
            img { width: 100%; height: 100%; object-fit: contain; }
            .controls { display: flex; gap: 10px; align-items: center; margin-top: 15px; background: #2f3640; padding: 12px 25px; border-radius: 10px; flex-wrap: wrap; justify-content: center; }
            .ctrl-btn { width: 45px; height: 45px; font-size: 16px; font-weight: bold; border-radius: 8px; border: none; background: #ffa801; color: #1e272e; cursor: pointer; }
            .ctrl-btn:active { transform: scale(0.95); background: #ffd32a; }
        </style>
    </head>
    <body>
        <h1>Bảng Điều Khiển AGV (ESP32-CAM & YDLidar X2)</h1>
        <div class="badge">🔒 Bảo mật X-AGV-Key Đã Bật | Chế độ: ESP32 Chủ Động Bắn Dữ Liệu (Push Mode)</div>
        
        <div class="toolbar">
            <label><b>Chế độ Camera:</b></label>
            <input type="text" id="cam-url" value="push" placeholder="push (Mặc định) hoặc 0 (Webcam)" />
            <button class="btn" onclick="changeCamera()">Đổi Chế Độ</button>
            
            <span style="margin-left: 8px;"><b>Chỉnh chiều Video:</b></span>
            <button class="btn btn-secondary" onclick="transformCam('rotate_90')">↻ Xoay 90°</button>
            <button class="btn btn-secondary" onclick="transformCam('rotate_180')">⇅ Lật Ngược 180°</button>
            <button class="btn btn-secondary" onclick="transformCam('flip_h')">⇄ Lật Ngang</button>
            <button class="btn btn-secondary" onclick="transformCam('flip_v')">⇵ Lật Dọc</button>
            
            <button class="btn btn-danger" style="margin-left: 8px;" onclick="resetMap()">Xóa Bản Đồ SLAM</button>
        </div>

        <!-- === [MỚI NÂNG CẤP - THANH ĐỔI WIFI TỪ XA CHO CẢ 2 MẠCH ESP32 TRÊN WEB DASHBOARD] === -->
        <div class="toolbar" style="border: 1px solid #05c46b;">
            <label><b>📡 Cài đặt Wi-Fi từ xa (Lưu vào Flash 2 ESP32):</b></label>
            <input type="text" id="remote-ssid" placeholder="Nhập Tên Wi-Fi 2.4GHz mới..." style="width: 190px;" />
            <input type="text" id="remote-pass" placeholder="Nhập Mật khẩu Wi-Fi..." style="width: 170px;" />
            <button class="btn" style="background: #05c46b; color: #1e272e;" onclick="pushRemoteWiFi()">Lưu &amp; Đổi Wi-Fi 2 Mạch</button>
            <button class="btn btn-danger" style="background: #ff3f34; color: white; margin-left: 6px;" onclick="clearRemoteWiFi()">🗑️ Xóa Wi-Fi Đã Lưu (Về Gốc)</button>
            <span id="wifi-ota-status" style="color: #ffd32a; font-weight: bold; margin-left: 8px;"></span>
        </div>

        <!-- === [MỚI NÂNG CẤP - THANH CHIA SẺ LINK CHO MÁY KHÁC XEM (INTERNET TUNNEL & LAN)] === -->
        <div class="toolbar" style="border: 1px solid #00d8d6; background: #1e272e;">
            <label style="color: #00d8d6;"><b>🌐 Link cho máy khác / điện thoại xem:</b></label>
            <input type="text" id="share-tunnel-url" readonly value="Đang lấy link Internet (.trycloudflare.com)..." style="width: 340px; color: #0be881; font-weight: bold; cursor: pointer;" onclick="copyShareLink('share-tunnel-url')" />
            <button class="btn" style="background: #00d8d6; color: #1e272e;" onclick="copyShareLink('share-tunnel-url')">📋 Copy Link Internet (Mọi mạng)</button>
            <span style="color: #7f8fa6; margin: 0 4px;">|</span>
            <input type="text" id="share-lan-url" readonly value="http://127.0.0.1:8000" style="width: 195px; color: #ffd32a; font-weight: bold; cursor: pointer;" onclick="copyShareLink('share-lan-url')" />
            <button class="btn btn-secondary" onclick="copyShareLink('share-lan-url')">📋 Copy Link LAN (Cùng Wi-Fi)</button>
            <span id="copy-link-status" style="color: #0be881; font-weight: bold; margin-left: 6px;"></span>
        </div>

        <!-- === [MỚI NÂNG CẤP - THANH THU THẬP DATASET YOLOV8 & ĐÓNG GÓI UPDATE CODE] === -->
        <div class="toolbar" style="border: 1px solid #ffa801; background: #262c36;">
            <label style="color: #ffd32a;"><b>📸 Thu thập Dataset YOLOv8 (Ảnh gốc sạch):</b></label>
            <button class="btn" style="background: #ffd32a; color: #1e272e;" onclick="captureOneDataset()">📸 Chụp 1 Ảnh Mẫu</button>
            <button id="btn-auto-cap" class="btn" style="background: #ff9f1a; color: #1e272e;" onclick="toggleAutoDataset()">⚡ Tự Động Chụp 150 Ảnh (0.5s/tấm)</button>
            <span id="dataset-status" style="color: #0be881; font-weight: bold; margin-left: 6px;">Kho ảnh: Đang kiểm tra...</span>
            <span style="margin-left: 12px; color: #7f8fa6;">|</span>
            <button class="btn" style="background: #00d8d6; color: #1e272e; margin-left: 6px;" onclick="window.location.href='/api/download_update'">📦 Tải Gói Update Code (.zip)</button>
        </div>

        <div class="container">
            <div>
                <h3 style="text-align: center; margin: 5px;">Camera Stream (YOLOv8 + QR)</h3>
                <div class="box" id="camera-box">
                    <img id="camera-feed" src="" alt="Camera Feed" style="display:none;" />
                    <canvas id="ai-overlay" style="position:absolute; top:0; left:0; width:100%; height:100%; pointer-events:none;"></canvas>
                    <span id="cam-wait-text">Đang khởi tạo luồng video...</span>
                </div>
            </div>
            <div>
                <h3 style="text-align: center; margin: 5px;">Bản Đồ SLAM (YDLidar X2)</h3>
                <div class="box" id="map-box">
                    <img id="map-feed" src="" alt="SLAM Map" style="display:none;" />
                    <span id="map-wait-text">Đang khởi tạo bản đồ...</span>
                </div>
            </div>
        </div>

        <div class="controls">
            <span><b>Điều khiển ESP32-S3 (hoặc nhấn phím W/A/S/D/G/X):</b></span>
            <button class="ctrl-btn" onclick="sendCmd('W')">W</button>
            <button class="ctrl-btn" onclick="sendCmd('A')">A</button>
            <button class="ctrl-btn" onclick="sendCmd('S')">S</button>
            <button class="ctrl-btn" onclick="sendCmd('D')">D</button>
            <button class="ctrl-btn" style="width:auto; padding:0 12px; background:#05c46b;" onclick="sendCmd('G')">Gắp (G)</button>
            <button class="ctrl-btn" style="width:auto; padding:0 12px; background:#ff3f34; color:white;" onclick="sendCmd('X')">Dừng (X)</button>
            <span id="cmd-status" style="margin-left:10px; color:#0be881;"></span>
        </div>
        
        <script>
            var wsProtocol = (location.protocol === "https:") ? "wss://" : "ws://";
            var ws = new WebSocket(wsProtocol + location.host + "/ws");
            var camImg = document.getElementById('camera-feed');
            var aiCanvas = document.getElementById('ai-overlay');
            var aiCtx = aiCanvas.getContext('2d');
            var camWaitText = document.getElementById('cam-wait-text');
            var mapImg = document.getElementById('map-feed');
            var mapWaitText = document.getElementById('map-wait-text');
            
            function drawOverlay(meta) {
                if (!meta) return;
                var w = meta.w || 320;
                var h = meta.h || 240;
                if (aiCanvas.width !== w) aiCanvas.width = w;
                if (aiCanvas.height !== h) aiCanvas.height = h;
                aiCtx.clearRect(0, 0, w, h);

                // Vẽ thông số FPS & AI bằng GPU
                aiCtx.fillStyle = "rgba(0, 0, 0, 0.45)";
                aiCtx.fillRect(4, 4, 175, 22);
                aiCtx.font = "bold 12px Segoe UI, sans-serif";
                aiCtx.fillStyle = "#0be881";
                aiCtx.fillText("FPS: " + meta.fps + " | AI: " + meta.ai_fps, 10, 19);

                // Vẽ khung nhận diện YOLOv8
                if (meta.boxes && meta.boxes.length > 0) {
                    aiCtx.strokeStyle = "#00d8d6";
                    aiCtx.lineWidth = 2;
                    aiCtx.fillStyle = "#00d8d6";
                    for (var i = 0; i < meta.boxes.length; i++) {
                        var b = meta.boxes[i];
                        aiCtx.strokeRect(b.x1, b.y1, b.x2 - b.x1, b.y2 - b.y1);
                        aiCtx.fillText(b.label, b.x1, Math.max(14, b.y1 - 4));
                    }
                }
                if (meta.qr) {
                    aiCtx.fillStyle = "#ffd32a";
                    aiCtx.font = "bold 14px Segoe UI, sans-serif";
                    aiCtx.fillText("QR: " + meta.qr, 10, h - 12);
                }
            }

            ws.onmessage = function(event) {
                var msg = JSON.parse(event.data);
                if (msg.camera) {
                    camImg.style.display = "block";
                    camWaitText.style.display = "none";
                    camImg.src = "data:image/jpeg;base64," + msg.camera;
                }
                if (msg.meta) {
                    drawOverlay(msg.meta);
                }
                if (msg.map) {
                    mapImg.style.display = "block";
                    mapWaitText.style.display = "none";
                    mapImg.src = "data:image/jpeg;base64," + msg.map;
                }
                if (msg.dataset) {
                    updateDatasetUI(msg.dataset);
                }
            };

            async function changeCamera() {
                var src = document.getElementById('cam-url').value;
                await fetch('/api/camera', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({source: src})
                });
            }

            async function transformCam(action) {
                await fetch('/api/camera/transform', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({action: action})
                });
            }

            async function resetMap() {
                await fetch('/api/reset_map', {method: 'POST'});
            }

            async function sendCmd(cmd) {
                var res = await fetch('/api/control', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({command: cmd})
                });
                var data = await res.json();
                document.getElementById('cmd-status').innerText = data.status;
            }

            // === [MỚI NÂNG CẤP - HÀM BẮN CẤU HÌNH WIFI MỚI XUỐNG CẢ 2 MẠCH ESP32] ===
            async function pushRemoteWiFi() {
                var ssid = document.getElementById('remote-ssid').value.trim();
                var pass = document.getElementById('remote-pass').value.trim();
                if (!ssid) {
                    alert("Vui lòng nhập Tên Wi-Fi 2.4GHz!");
                    return;
                }
                var res = await fetch('/api/wifi_config', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ssid: ssid, password: pass})
                });
                var data = await res.json();
                document.getElementById('wifi-ota-status').innerText = data.status;
            }

            async function clearRemoteWiFi() {
                if (!confirm("Bạn có chắc muốn XÓA Wi-Fi đã lưu trong Flash của cả 2 ESP để quay về Wi-Fi mặc định (cuong / TP-Link_2726)?")) return;
                var res = await fetch('/api/wifi_config', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ssid: "CLEAR", password: ""})
                });
                var data = await res.json();
                document.getElementById('wifi-ota-status').innerText = data.status;
            }

            // === [MỚI NÂNG CẤP - HÀM CHỤP DATASET ẢNH SẠCH CHO YOLOV8] ===
            function updateDatasetUI(ds) {
                if (!ds) return;
                var statusEl = document.getElementById('dataset-status');
                var btnAuto = document.getElementById('btn-auto-cap');
                if (ds.active) {
                    btnAuto.style.background = "#ff3f34";
                    btnAuto.style.color = "white";
                    btnAuto.innerText = "🛑 Dừng Chụp Tự Động (" + ds.captured + "/" + ds.target + ")";
                    statusEl.innerText = "⚡ Đang chụp: " + ds.captured + "/" + ds.target + " tấm | Tổng kho: " + ds.total_files + " ảnh";
                } else {
                    btnAuto.style.background = "#ff9f1a";
                    btnAuto.style.color = "#1e272e";
                    btnAuto.innerText = "⚡ Tự Động Chụp 150 Ảnh (0.5s/tấm)";
                    statusEl.innerText = "📁 Tổng trong kho (dataset_thung_hang): " + ds.total_files + " ảnh";
                }
            }

            async function captureOneDataset() {
                var res = await fetch('/api/dataset/capture_one', {method: 'POST'});
                var data = await res.json();
                document.getElementById('dataset-status').innerText = data.message;
            }

            async function toggleAutoDataset() {
                var res = await fetch('/api/dataset/toggle_auto', {method: 'POST'});
                var data = await res.json();
                updateDatasetUI(data);
            }

            // Tải số lượng ảnh ban đầu khi mở trang
            fetch('/api/dataset/status').then(r => r.json()).then(d => updateDatasetUI(d)).catch(() => {});

            // === [MỚI NÂNG CẤP - LẤY VÀ COPY LINK CHO MÁY KHÁC XEM (TỰ DỪNG KHI ĐÃ CÓ LINK ĐỂ KHÔNG TRÔI CMD)] ===
            var shareLinkTimer = null;
            async function refreshShareLinks() {
                try {
                    var res = await fetch('/api/share_links');
                    var data = await res.json();
                    if (data.lan_url) {
                        document.getElementById('share-lan-url').value = data.lan_url;
                    }
                    if (data.tunnel_url) {
                        document.getElementById('share-tunnel-url').value = data.tunnel_url;
                        if (data.tunnel_url.indexOf("https://") === 0 && shareLinkTimer) {
                            clearInterval(shareLinkTimer);
                            shareLinkTimer = null;
                        }
                    }
                } catch (e) {}
            }
            refreshShareLinks();
            shareLinkTimer = setInterval(refreshShareLinks, 3000);

            function copyShareLink(inputId) {
                var inp = document.getElementById(inputId);
                var val = inp.value;
                if (!val || val.indexOf("http") !== 0) {
                    alert("Đường hầm Cloudflare đang khởi tạo (khoảng 3-5 giây sau khi bật Server), vui lòng đợi một chút!");
                    return;
                }
                navigator.clipboard.writeText(val).then(function() {
                    var st = document.getElementById('copy-link-status');
                    st.innerText = "✅ Đã Copy: " + val;
                    setTimeout(function() { st.innerText = ""; }, 4000);
                }).catch(function() {
                    inp.select();
                    document.execCommand('copy');
                    var st = document.getElementById('copy-link-status');
                    st.innerText = "✅ Đã Copy!";
                    setTimeout(function() { st.innerText = ""; }, 4000);
                });
            }

            document.addEventListener('keydown', function(e) {
                if (document.activeElement.tagName === 'INPUT') return;
                var key = e.key.toUpperCase();
                if (['W', 'A', 'S', 'D', 'G', 'X'].includes(key)) {
                    sendCmd(key);
                }
            });
        </script>
    </body>
</html>
"""

@app.get("/")
async def get():
    return HTMLResponse(HTML)

@app.post("/api/camera")
async def set_camera(req: CameraSourceRequest):
    ok = vision_ai.set_camera_source(req.source)
    return {"success": ok, "source": req.source}

@app.post("/api/camera/transform")
async def transform_camera(req: CameraTransformRequest):
    act = req.action
    if act == "rotate_90":
        vision_ai.set_transform(rotate_mode=vision_ai.rotate_mode + 1)
    elif act == "rotate_180":
        vision_ai.set_transform(rotate_mode=vision_ai.rotate_mode + 2)
    elif act == "flip_h":
        vision_ai.set_transform(flip_h=not vision_ai.flip_h)
    elif act == "flip_v":
        vision_ai.set_transform(flip_v=not vision_ai.flip_v)
    return {
        "rotate_deg": vision_ai.rotate_mode * 90,
        "flip_h": vision_ai.flip_h,
        "flip_v": vision_ai.flip_v
    }

@app.post("/api/reset_map")
async def reset_map():
    slam_mapper.reset_map()
    return {"success": True}

@app.post("/api/control")
async def control_agv(req: ControlCommandRequest):
    status_msg = await lidar_server.send_command(req.command)
    return {"status": status_msg}

# === [MỚI NÂNG CẤP - API CẬP NHẬT WIFI TỪ XA CHO CẢ ESP32-CAM & ESP32-S3] ===
@app.post("/api/wifi_config")
async def update_remote_wifi(req: RemoteWiFiConfigRequest):
    global pending_cam_wifi_cfg, pending_s3_wifi_cfg
    if req.ssid.strip() == "CLEAR":
        cfg_str = "#WIFI:CLEAR\n"
        pending_cam_wifi_cfg = cfg_str
        pending_s3_wifi_cfg = cfg_str
        print("[*] [WIFI-OTA] Đã xếp lệnh XÓA FLASH về mặc định cho cả 2 ESP32!")
        return {"status": "Đã gửi lệnh XÓA Wi-Fi đã lưu về mặc định cho cả 2 ESP!"}
    cfg_str = f"#WIFI:{req.ssid.strip()}|{req.password.strip()}\n"
    pending_cam_wifi_cfg = cfg_str
    pending_s3_wifi_cfg = cfg_str
    print(f"[*] [WIFI-OTA] Đã xếp lệnh đổi Wi-Fi sang '{req.ssid.strip()}' cho cả ESP32-CAM và ESP32-S3!")
    return {"status": f"Đã gửi Wi-Fi '{req.ssid.strip()}' xuống 2 mạch ESP32!"}

# === [MỚI NÂNG CẤP - API CHỤP DATASET YOLOV8 & ĐÓNG GÓI UPDATE CODE] ===
@app.post("/api/dataset/capture_one")
async def api_capture_one_dataset():
    return vision_ai.capture_single_dataset_image()

@app.post("/api/dataset/toggle_auto")
async def api_toggle_auto_dataset():
    return vision_ai.toggle_auto_capture(target_count=150, interval_sec=0.5)

@app.get("/api/dataset/status")
async def api_dataset_status():
    return vision_ai.get_dataset_status()

@app.get("/api/share_links")
async def api_share_links():
    """Trả về cả Link Internet (Cloudflare Tunnel) và Link LAN nội bộ để copy gửi cho máy khác."""
    lan_ip = get_current_lan_ip()
    lan_url = f"http://{lan_ip}:8000"
    tunnel_url = ""
    try:
        import run_tunnel_sync
        if getattr(run_tunnel_sync, "CURRENT_TUNNEL_URL", ""):
            tunnel_url = run_tunnel_sync.CURRENT_TUNNEL_URL
    except Exception:
        pass
    if not tunnel_url:
        try:
            base_dir = PROJECT_ROOT
            txt_path = os.path.join(base_dir, "tools", "current_tunnel_url.txt")
            if not os.path.exists(txt_path):
                txt_path = os.path.join(base_dir, "current_tunnel_url.txt")
            if os.path.exists(txt_path):
                with open(txt_path, "r", encoding="utf-8") as f:
                    tunnel_url = f.read().strip()
        except Exception:
            pass
    return {
        "lan_url": lan_url,
        "tunnel_url": tunnel_url if tunnel_url else "Đang khởi tạo link .trycloudflare.com (đợi 3s)..."
    }

@app.get("/api/download_update")
async def api_download_update():
    """
    Tự động gom toàn bộ các file code (.py, .bat, .md, firmware/*.ino và model .pt mới nếu có)
    nén thành 1 file Update_Code_AGV.zip ngay trong bộ nhớ RAM và tải thẳng về trình duyệt!
    Bỏ qua thư mục venv (2GB) và cloudflared.exe (55MB) để gói cập nhật siêu nhẹ (<100KB).
    """
    base_dir = PROJECT_ROOT
    update_dir = os.path.join(base_dir, "Goi_Update_Code")
    os.makedirs(update_dir, exist_ok=True)
    mem_zip = io.BytesIO()
    allowed_exts = ('.py', '.bat', '.md', '.ino', '.h', '.cpp', '.json', '.yaml', '.yml', '.gitignore')
    skip_dirs = {'venv', '__pycache__', '.git', 'dataset_thung_hang', 'Goi_Update_Code'}

    with zipfile.ZipFile(mem_zip, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(base_dir):
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            for file in files:
                if file.lower().startswith("update_code_agv") and file.lower().endswith(".zip"):
                    continue
                # Lấy tất cả file code hoặc file model AI mới (như best.pt, thung_hang.pt)
                is_code = file.lower().endswith(allowed_exts)
                is_custom_model = file.lower().endswith('.pt') and file.lower() != 'yolov8n.pt'
                if is_code or is_custom_model:
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, base_dir)
                    zf.write(full_path, arcname=rel_path)

    # Đồng thời lưu luôn file zip vừa đóng gói vào thư mục E:\agv_server\Goi_Update_Code\
    zip_bytes = mem_zip.getvalue()
    try:
        latest_path = os.path.join(update_dir, "Update_Code_AGV.zip")
        with open(latest_path, "wb") as f_out:
            f_out.write(zip_bytes)
    except Exception:
        pass

    mem_zip.seek(0)
    headers = {
        "Content-Disposition": 'attachment; filename="Update_Code_AGV.zip"'
    }
    return StreamingResponse(mem_zip, media_type="application/zip", headers=headers)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("[*] Web Dashboard đã kết nối WebSocket!")
    
    vision_ai.start_camera()
    
    try:
        last_sent_cam_id = -1
        last_map_sent_time = 0.0
        while True:
            payload = {}
            cur_cam_id = getattr(vision_ai, "rendered_frame_id", 0)
            b64_frame = vision_ai.get_processed_frame_base64()
            if b64_frame and cur_cam_id != last_sent_cam_id:
                payload["camera"] = b64_frame
                payload["meta"] = vision_ai.get_overlay_metadata()
                last_sent_cam_id = cur_cam_id

            now = asyncio.get_event_loop().time()
            if now - last_map_sent_time >= 0.08:
                b64_map = slam_mapper.get_map_base64()
                if b64_map:
                    payload["map"] = b64_map
                payload["dataset"] = vision_ai.get_dataset_status()
                last_map_sent_time = now

            if payload:
                await websocket.send_text(json.dumps(payload))
                
            await asyncio.sleep(0.008)
    except WebSocketDisconnect:
        print("[*] Web Dashboard đã ngắt kết nối WebSocket.")
    except Exception as e:
        print(f"[!] Lỗi WebSocket: {e}")

def auto_start_tunnel_if_needed():
    import threading
    base_dir = PROJECT_ROOT
    cloudflared_path = os.path.join(base_dir, "tools", "cloudflared.exe")
    if not os.path.exists(cloudflared_path):
        cloudflared_path = os.path.join(base_dir, "cloudflared.exe")
    if not os.path.exists(cloudflared_path):
        return

    try:
        import subprocess
        out = subprocess.check_output('tasklist /FI "IMAGENAME eq cloudflared.exe"', shell=True, text=True, stderr=subprocess.DEVNULL)
        if "cloudflared.exe" in out:
            print("[*] Phat hien cloudflared.exe cu dang chay ngam -> Dang khoi dong lai Tunnel moi de dong bo ntfy.sh...")
            subprocess.call('taskkill /F /IM cloudflared.exe', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

    print("[*] Dang tu dong kich hoat Cloudflare Tunnel va Dong bo ntfy.sh...")
    def _tunnel_worker():
        try:
            import run_tunnel_sync
            run_tunnel_sync.main()
        except Exception as err:
            print(f"[!] Loi khoi dong Cloudflare Tunnel: {err}")

    t = threading.Thread(target=_tunnel_worker, daemon=True)
    t.start()

@app.on_event("startup")
async def startup_event():
    print("[*] Đang khởi động AGV Server (Port 8000 - Push Mode Bảo Mật & Port 8888 - TCP Lidar)...")
    vision_ai.start_camera()
    asyncio.create_task(lidar_server.start())
    auto_start_tunnel_if_needed()

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        ws_ping_interval=None,
        ws_ping_timeout=None,
        ws_max_size=16777216  # Mở rộng ống nhận WebSocket lên 16 MB/khung hình để gửi nguyên tệp ảnh lớn không bị cắt
    )
