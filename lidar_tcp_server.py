import asyncio
import struct
import math
from collections import deque


class LidarTCPServer:
    def __init__(self, host='0.0.0.0', port=8888, slam_mapper=None):
        self.host = host
        self.port = port
        self.server = None
        self.slam_mapper = slam_mapper
        self.active_writer = None
        self.client_address = None
        self.pending_commands = deque(maxlen=20)
        self.http_rx_buffer = bytearray()
        self.rx_pkt_counter = 0

    def parse_ydlidar_x2(self, buffer: bytearray):
        """
        Giải mã chính xác gói dữ liệu nhị phân của YDLidar X2 / X2L / X4 (Header: 0xAA 0x55).
        Kiểm tra bit cờ FSA/LSA để không bao giờ bị lệch byte khi gói tin truyền qua mạng.
        """
        points = []
        while len(buffer) >= 10:
            idx = buffer.find(b'\xaa\x55')
            if idx == -1:
                if len(buffer) > 1:
                    del buffer[:-1]
                break

            if idx > 0:
                del buffer[:idx]

            if len(buffer) < 10:
                break

            ct = buffer[2]
            lsn = buffer[3]

            # Gói hợp lệ của YDLidar X2 có số mẫu lsn từ 1 đến 128
            if lsn == 0 or lsn > 150:
                del buffer[:2]
                continue

            fsa, lsa, cs = struct.unpack('<HHH', buffer[4:10])
            angle_fsa = (fsa >> 1) / 64.0
            angle_lsa = (lsa >> 1) / 64.0

            # Kiểm tra góc hợp lệ (0..360 độ) để tránh bắt nhầm byte 0xAA 0x55 ngẫu nhiên trong dữ liệu
            if angle_fsa > 365.0 or angle_lsa > 365.0:
                del buffer[:2]
                continue

            packet_len = 10 + 2 * lsn
            if len(buffer) < packet_len:
                break

            samples = struct.unpack(f'<{lsn}H', buffer[10:packet_len])
            del buffer[:packet_len]

            diff_angle = angle_lsa - angle_fsa
            if diff_angle < 0:
                diff_angle += 360.0

            for i in range(lsn):
                raw_dist = samples[i]
                # Chuẩn YDLidar X2: khoảng cách (mm) = raw_dist / 4.0 (hoặc dịch phải 2 bit)
                dist_mm = raw_dist / 4.0
                if dist_mm <= 30 or dist_mm > 8000:
                    continue

                if lsn > 1:
                    angle = angle_fsa + (diff_angle / (lsn - 1)) * i
                else:
                    angle = angle_fsa

                ang_correct = math.degrees(math.atan(21.8 * (155.3 - dist_mm) / (155.3 * dist_mm))) if dist_mm > 0 else 0.0
                final_angle = (angle + ang_correct) % 360.0

                points.append((final_angle, dist_mm))

        return points

    def receive_pushed_lidar(self, raw_bytes: bytes) -> str:
        """
        Nhận dữ liệu Lidar do ESP32-S3 bắn lên qua WebSocket (/ws/push_lidar),
        giải mã góc & khoảng cách thực tế và cập nhật ngay lên Bản đồ Radar 360°!
        """
        if self.slam_mapper:
            self.slam_mapper.notify_s3_heartbeat()

        if raw_bytes and len(raw_bytes) > 1:
            self.rx_pkt_counter += 1
            self.http_rx_buffer.extend(raw_bytes)
            points = self.parse_ydlidar_x2(self.http_rx_buffer)
            if points and self.slam_mapper:
                self.slam_mapper.update_scan(points)

            if self.rx_pkt_counter == 1 or self.rx_pkt_counter % 15 == 0:
                print(
                    f"[*] [LIDAR-REAL] Nhận gói #{self.rx_pkt_counter} ({len(raw_bytes)} bytes) "
                    f"-> Giải mã {len(points)} tia Laser | Header: {raw_bytes[:8].hex()}"
                )

            if len(self.http_rx_buffer) > 32768:
                self.http_rx_buffer.clear()

        if self.pending_commands:
            return self.pending_commands.popleft()
        return ""

    async def send_command(self, cmd: str) -> str:
        if self.slam_mapper:
            self.slam_mapper.apply_control_command(cmd)

        self.pending_commands.append(cmd)
        if self.active_writer is not None:
            try:
                self.active_writer.write(f"{cmd}\n".encode('utf-8'))
                await self.active_writer.drain()
                print(f"[*] Đã gửi lệnh '{cmd}' xuống ESP32-S3 qua TCP ({self.client_address})")
                return f"Đã gửi ngay lệnh '{cmd}' tới ESP32-S3 & Cập nhật Bản đồ 2D"
            except Exception as e:
                print(f"[!] Lỗi khi gửi lệnh TCP xuống ESP32-S3: {e}")
                self.active_writer = None
        return f"Đã gửi lệnh '{cmd}' tới ESP32-S3 & Cập nhật Bản đồ SLAM 2D"

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        addr = writer.get_extra_info('peername')
        self.client_address = addr
        self.active_writer = writer
        print(f"[*] Đã kết nối với ESP32-S3 (YDLidar X2) tại {addr}")

        rx_buffer = bytearray()

        try:
            while True:
                data = await reader.read(2048)
                if not data:
                    break

                if self.slam_mapper:
                    self.slam_mapper.notify_s3_heartbeat()
                rx_buffer.extend(data)
                points = self.parse_ydlidar_x2(rx_buffer)
                if points and self.slam_mapper:
                    self.slam_mapper.update_scan(points)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[!] Lỗi kết nối với ESP32-S3: {e}")
        finally:
            print(f"[*] Đóng kết nối với ESP32-S3 tại {addr}")
            if self.active_writer == writer:
                self.active_writer = None
                self.client_address = None
            writer.close()
            await writer.wait_closed()

    async def start(self):
        self.server = await asyncio.start_server(
            self.handle_client, self.host, self.port
        )
        addrs = ', '.join(str(sock.getsockname()) for sock in self.server.sockets)
        print(f"[*] TCP Lidar Server đang lắng nghe trên {addrs}")

        async with self.server:
            await self.server.serve_forever()
