/*
 * CODE CHO ESP32-S3: ĐỌC DỮ LIỆU YDLIDAR X2 + TỰ BUNG CỬA SỔ WIFI & ĐỒNG BỘ KÉP 2 ESP
 * Đã trang bị:
 * 1. Tự động kiểm tra cả 2 chiều dây Xanh/Vàng (GPIO 16 = RX / GPIO 15 = M_EN và ngược lại GPIO 15 = RX / GPIO 16 = M_EN) + Lệnh kích 0xA5 0x60.
 * 2. Khi đã nhận được luồng byte Laser từ YDLidar X2 -> Khóa cứng cấu hình chân đó để truyền 100% tốc độ cao!
 * 3. Đường ống WebSocket 2 chiều (/ws/push_lidar): Quét Radar 360° không biên & nhận lệnh W, A, S, D, G, X tức thì!
 * 4. Lưu Wi-Fi vĩnh viễn vào bộ nhớ Flash + Captive Portal DNS: Vừa bắt Wi-Fi "AGV_S3_WIFI"
 *    trên điện thoại là TỰ ĐỘNG BUNG TRANG CÀI ĐẶT lên màn hình (không cần gõ 192.168.4.1)!
 * 5. Đồng bộ kép P2P: Nhập Wi-Fi 1 lần trên 1 mạch là cả 2 mạch cùng lưu và cùng kết nối!
 * 6. [MỚI NÂNG CẤP] Nút "XÓA MẠNG ĐÃ LƯU" trên cả Web điện thoại lẫn Web Dashboard để quay về mạng mặc định!
 */

#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <Preferences.h>
#include <WebServer.h>
#include <DNSServer.h>
#include <stdarg.h>

// ================= 1. CẤU HÌNH WIFI MẶC ĐỊNH & DỰ PHÒNG =================
const char* target_ssid     = "cuong";          // Ưu tiên mặc định 1: Hotspot điện thoại
const char* password        = "3007322006";     // Mật khẩu của 'cuong'
const char* backup_ssid     = "TP-Link_2726";   // Ưu tiên mặc định 2: Wi-Fi ở nhà
const char* backup_password = "40363455";       // Mật khẩu của 'TP-Link_2726'

Preferences wifiPrefs;
WebServer portalServer(80);
DNSServer dnsServer;
const byte DNS_PORT = 53;
String saved_ssid = "";
String saved_pass = "";
bool portal_saved_new_wifi = false;
bool received_from_peer    = false;
const char* ap_setup_name  = "AGV_S3_WIFI";
const char* peer_ap_name   = "AGV_CAM_WIFI";
// === [MỚI NÂNG CẤP - MẬT KHẨU BẢO VỆ WIFI CỨU HỘ CỦA 2 ESP32 (Tối thiểu 8 ký tự)] ===
const char* ap_password    = "12345678";        // Bạn có thể đổi mật khẩu này theo ý muốn!
// ===================================================================================

// ================= 2. ĐỊA CHỈ ĐƯỜNG HẦM & TỰ ĐỘNG ĐỒNG BỘ =================
String tunnel_host            = "resolve-extends-agreement-imagination.trycloudflare.com";
const char* tunnel_sync_topic = "cuong_agv_tunnel_2026_secret";
const char* agv_secret_key    = "Cuong_AGV_Secret_2026";

// ================= 3. CẤU HÌNH CHÂN KẾT NỐI YDLIDAR X2 =================
int active_lidar_rx_pin    = 16;
int active_lidar_motor_pin = 15;
bool lidar_pin_locked      = false;

WiFiClientSecure secureClient;
bool ws_connected = false;

#define BUF_SIZE 1024
uint8_t lidar_buf[BUF_SIZE];
uint8_t ws_pkt_buf[BUF_SIZE + 16];
unsigned long pkt_count = 0;
unsigned long last_heartbeat_ms = 0;
unsigned long last_pin_check_ms = 0;

void s3Printf(const char* format, ...) {
  char buf[256];
  va_list args;
  va_start(args, format);
  vsnprintf(buf, sizeof(buf), format, args);
  va_end(args);

  Serial.print(buf);
  ets_printf("%s", buf);
}

void s3Println(const char* msg) {
  s3Printf("%s\n", msg);
}

void loadWiFiFromFlash() {
  wifiPrefs.begin("agv_wifi", true);
  saved_ssid = wifiPrefs.getString("ssid", "");
  saved_pass = wifiPrefs.getString("pass", "");
  wifiPrefs.end();
  if (saved_ssid.length() > 0) {
    s3Printf("[FLASH-WIFI] Đã đọc Wi-Fi lưu trong bộ nhớ Flash: '%s'\n", saved_ssid.c_str());
  }
}

void saveWiFiToFlash(const String& new_ssid, const String& new_pass) {
  wifiPrefs.begin("agv_wifi", false);
  wifiPrefs.putString("ssid", new_ssid);
  wifiPrefs.putString("pass", new_pass);
  wifiPrefs.end();
  saved_ssid = new_ssid;
  saved_pass = new_pass;
  s3Printf("[FLASH-WIFI] --> ĐÃ LƯU VĨNH VIỄN WIFI MỚI VÀO FLASH: '%s'\n", new_ssid.c_str());
}

// Xóa sạch Wi-Fi trong Flash để trở về mạng mặc định
void clearWiFiFromFlash() {
  wifiPrefs.begin("agv_wifi", false);
  wifiPrefs.clear();
  wifiPrefs.end();
  saved_ssid = "";
  saved_pass = "";
  s3Println("\n[FLASH-WIFI] 🗑️ ĐÃ XÓA SẠCH WIFI TRONG FLASH! TRỞ VỀ MẠNG GỐC (cuong / TP-Link_2726)!");
}

// Bắn lệnh xóa Wi-Fi sang mạch ESP32-CAM còn lại
void syncClearToSiblingESP() {
  s3Printf("\n[PEER-SYNC] 🔄 Đang truyền lệnh XÓA WIFI sang mạch '%s'...\n", peer_ap_name);
  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  delay(100);
  WiFi.begin(peer_ap_name, ap_password);
  int tries = 0;
  while (WiFi.status() != WL_CONNECTED && tries < 12) {
    delay(400);
    s3Printf("*");
    tries++;
  }
  s3Println("");
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    if (http.begin("http://192.168.4.1/peer_clear")) {
      http.POST("");
      http.end();
      s3Printf("[PEER-SYNC] ✅ Đã báo mạch '%s' cùng XÓA FLASH thành công!\n", peer_ap_name);
    }
  }
  WiFi.disconnect();
  delay(150);
}

void syncWiFiToSiblingESP(const String& ssid_to_send, const String& pass_to_send) {
  s3Printf("\n[PEER-SYNC] 🔄 Đang tự động truyền Wi-Fi '%s' sang mạch '%s'...\n", ssid_to_send.c_str(), peer_ap_name);
  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  delay(100);

  WiFi.begin(peer_ap_name, ap_password);
  int tries = 0;
  while (WiFi.status() != WL_CONNECTED && tries < 16) {
    delay(500);
    s3Printf("*");
    tries++;
  }
  s3Println("");

  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    if (http.begin("http://192.168.4.1/peer_sync")) {
      http.addHeader("Content-Type", "text/plain");
      String payload = ssid_to_send + "\n" + pass_to_send;
      int code = http.POST(payload);
      if (code == 200) {
        s3Printf("[PEER-SYNC] ✅ ĐÃ ĐỒNG BỘ WI-FI SANG '%s' THÀNH CÔNG! CẢ 2 MẠCH CÙNG KẾT NỐI!\n", peer_ap_name);
      } else {
        s3Printf("[PEER-SYNC] ⚠️ Phản hồi từ '%s': HTTP %d\n", peer_ap_name, code);
      }
      http.end();
    }
  } else {
    s3Printf("[PEER-SYNC] ℹ️ Không thấy '%s' phát AP (mạch kia có thể đã kết nối mạng trước).\n", peer_ap_name);
  }

  WiFi.disconnect();
  delay(150);
}

void handlePeerSync() {
  String body = portalServer.arg("plain");
  int nl = body.indexOf('\n');
  if (nl > 0) {
    String s = body.substring(0, nl);
    String p = body.substring(nl + 1);
    s.trim();
    p.trim();
    if (s.length() > 0) {
      s3Printf("\n[PEER-SYNC] 📥 Đã nhận Wi-Fi '%s' từ mạch ESP32-CAM truyền sang!\n", s.c_str());
      saveWiFiToFlash(s, p);
      portalServer.send(200, "text/plain", "OK_SYNCED");
      delay(300);
      received_from_peer = true;
      portal_saved_new_wifi = true;
      return;
    }
  }
  portalServer.send(400, "text/plain", "BAD_SYNC");
}

void handlePeerClear() {
  s3Println("\n[PEER-SYNC] 📥 Đã nhận lệnh XÓA WIFI từ mạch ESP32-CAM!");
  clearWiFiFromFlash();
  portalServer.send(200, "text/plain", "OK_CLEARED");
  delay(300);
  received_from_peer = true;
  portal_saved_new_wifi = true;
}

void handlePortalRoot() {
  int n = WiFi.scanNetworks();
  String html = "<!DOCTYPE html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>";
  html += "<title>Cài Đặt Wi-Fi AGV (Đồng Bộ 2 ESP)</title>";
  html += "<style>body{font-family:sans-serif;background:#1e272e;color:#fff;padding:18px;text-align:center;}";
  html += ".box{max-width:380px;margin:auto;background:#2f3640;padding:20px;border-radius:12px;border:2px solid #0fbcf9;}";
  html += "input,button{width:92%;padding:12px;margin:8px 0;border-radius:6px;border:none;font-size:15px;}";
  html += "button{background:#0fbcf9;color:#1e272e;font-weight:bold;cursor:pointer;}";
  html += ".net{background:#1e272e;padding:10px;margin:5px 0;border-radius:6px;cursor:pointer;text-align:left;border:1px solid #485460;}";
  html += "</style></head><body><div class='box'>";
  html += "<h2 style='color:#0fbcf9;margin-top:0;'>🧭 CÀI ĐẶT WI-FI XE AGV</h2>";
  html += "<p style='font-size:13px;color:#0be881;'>✨ Nhập 1 lần tại đây sẽ tự động đồng bộ cho cả <b>ESP32-S3</b> và <b>ESP32-CAM</b>!</p>";

  for (int i = 0; i < n; i++) {
    String s = WiFi.SSID(i);
    if (s == ap_setup_name || s == peer_ap_name) continue;
    html += "<div class='net' onclick=\"document.getElementById('s').value='" + s + "'\">📶 <b>" + s + "</b> (" + String(WiFi.RSSI(i)) + " dBm)</div>";
  }
  WiFi.scanDelete();

  html += "<form action='/save' method='POST'>";
  html += "<input id='s' name='ssid' placeholder='Tên Wi-Fi (2.4GHz)' required value='" + saved_ssid + "'>";
  html += "<input name='pass' type='text' placeholder='Mật khẩu Wi-Fi'>";
  html += "<button type='submit'>💾 LƯU & ĐỒNG BỘ CẢ 2 ESP32</button>";
  html += "</form>";

  if (saved_ssid.length() > 0) {
    html += "<div style='margin-top:16px;padding-top:12px;border-top:1px dashed #57606f;'>";
    html += "<p style='font-size:12px;color:#ffa801;margin:4px 0;'>Mạng đang lưu trong Flash: <b>" + saved_ssid + "</b></p>";
    html += "<form action='/clear' method='POST' onsubmit='return confirm(\"Xóa mạng đã lưu để 2 ESP quay về Wi-Fi mặc định?\");'>";
    html += "<button type='submit' style='background:#ff3f34;color:white;'>🗑️ XÓA MẠNG ĐÃ LƯU (VỀ MẶC ĐỊNH)</button></form></div>";
  }

  html += "</div></body></html>";
  portalServer.send(200, "text/html", html);
}

void handleCaptiveRedirect() {
  portalServer.sendHeader("Location", "http://192.168.4.1/", true);
  portalServer.send(302, "text/plain", "");
}

void handlePortalSave() {
  String s = portalServer.arg("ssid");
  String p = portalServer.arg("pass");
  s.trim();
  p.trim();
  if (s.length() > 0) {
    saveWiFiToFlash(s, p);
    String resp = "<!DOCTYPE html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'></head>";
    resp += "<body style='background:#1e272e;color:#0be881;font-family:sans-serif;text-align:center;padding:40px;'>";
    resp += "<h2>✅ ĐÃ LƯU WI-FI MỚI: " + s + "</h2>";
    resp += "<p>Đang tự động truyền Wi-Fi sang mạch <b>ESP32-CAM</b> và kết nối vào mạng mới...</p></body></html>";
    portalServer.send(200, "text/html", resp);
    delay(800);
    received_from_peer = false;
    portal_saved_new_wifi = true;
  }
}

void handlePortalClear() {
  clearWiFiFromFlash();
  String resp = "<!DOCTYPE html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'></head>";
  resp += "<body style='background:#1e272e;color:#ff4757;font-family:sans-serif;text-align:center;padding:40px;'>";
  resp += "<h2>🗑️ ĐÃ XÓA MẠNG ĐÃ LƯU!</h2>";
  resp += "<p>Đang đồng bộ xóa sang <b>ESP32-CAM</b> và kết nối lại mạng mặc định (cuong / TP-Link_2726)...</p></body></html>";
  portalServer.send(200, "text/html", resp);
  delay(800);
  syncClearToSiblingESP();
  received_from_peer = false;
  portal_saved_new_wifi = true;
}

void startSmartWiFiPortal() {
  s3Println("\n=======================================================");
  s3Printf("[AP-PORTAL] Không tìm thấy Wi-Fi quen thuộc! Đang phát Wi-Fi: '%s' (Mật khẩu: '%s')\n", ap_setup_name, ap_password);
  s3Println("[AP-PORTAL] Nhập Wi-Fi 1 lần trên 1 mạch là CẢ 2 ESP CÙNG KẾT NỐI (Được bảo vệ mật khẩu)!");
  s3Println("=======================================================");

  WiFi.mode(WIFI_AP_STA);
  IPAddress apIP(192, 168, 4, 1);
  WiFi.softAPConfig(apIP, apIP, IPAddress(255, 255, 255, 0));
  WiFi.softAP(ap_setup_name, ap_password);

  dnsServer.setErrorReplyCode(DNSReplyCode::NoError);
  dnsServer.start(DNS_PORT, "*", apIP);

  portal_saved_new_wifi = false;
  received_from_peer = false;
  portalServer.on("/", HTTP_GET, handlePortalRoot);
  portalServer.on("/save", HTTP_POST, handlePortalSave);
  portalServer.on("/clear", HTTP_POST, handlePortalClear);
  portalServer.on("/peer_sync", HTTP_POST, handlePeerSync);
  portalServer.on("/peer_clear", HTTP_POST, handlePeerClear);
  portalServer.on("/generate_204", HTTP_GET, handlePortalRoot);
  portalServer.on("/gen_204", HTTP_GET, handlePortalRoot);
  portalServer.on("/hotspot-detect.html", HTTP_GET, handlePortalRoot);
  portalServer.on("/connecttest.txt", HTTP_GET, handleCaptiveRedirect);
  portalServer.on("/redirect", HTTP_GET, handlePortalRoot);
  portalServer.onNotFound(handlePortalRoot);
  portalServer.begin();

  unsigned long portal_start = millis();
  while (!portal_saved_new_wifi && (millis() - portal_start < 180000)) {
    dnsServer.processNextRequest();
    portalServer.handleClient();
    delay(5);
  }

  dnsServer.stop();
  portalServer.stop();
  WiFi.softAPdisconnect(true);
  WiFi.mode(WIFI_STA);
  delay(150);

  if (portal_saved_new_wifi && !received_from_peer && saved_ssid.length() > 0) {
    syncWiFiToSiblingESP(saved_ssid, saved_pass);
  }
}

void connectToWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;

  loadWiFiFromFlash();

  WiFi.mode(WIFI_STA);
  delay(150);
  WiFi.setSleep(false);
  WiFi.setMinSecurity(WIFI_AUTH_WPA_PSK);

  String chosen_ssid = "";
  String chosen_pass = "";

  s3Println("\n[WiFi] Đang quét các mạng Wi-Fi 2.4GHz xung quanh...");
  int n = WiFi.scanNetworks();
  if (n > 0) {
    if (saved_ssid.length() > 0) {
      String sv_low = saved_ssid;
      sv_low.toLowerCase();
      for (int i = 0; i < n; ++i) {
        String scanned = WiFi.SSID(i);
        String s_low = scanned;
        s_low.toLowerCase();
        if (s_low == sv_low || s_low.indexOf(sv_low) != -1) {
          chosen_ssid = scanned;
          chosen_pass = saved_pass;
          s3Printf("   --> [KHỚP WIFI ĐÃ LƯU TRONG FLASH]: '%s' (%d dBm)\n", chosen_ssid.c_str(), WiFi.RSSI(i));
          break;
        }
      }
    }
    if (chosen_ssid.length() == 0) {
      String t1_low = String(target_ssid);
      t1_low.toLowerCase();
      String t2_low = String(backup_ssid);
      t2_low.toLowerCase();
      for (int i = 0; i < n; ++i) {
        String scanned = WiFi.SSID(i);
        String s_low = scanned;
        s_low.toLowerCase();
        if (s_low == t1_low || s_low.indexOf(t1_low) != -1) {
          chosen_ssid = scanned;
          chosen_pass = String(password);
          s3Printf("   --> [TỰ ĐỘNG CHỌN MẠNG ƯU TIÊN 1]: '%s' (%d dBm)\n", chosen_ssid.c_str(), WiFi.RSSI(i));
          break;
        } else if (chosen_ssid.length() == 0 && (s_low == t2_low || s_low.indexOf(t2_low) != -1)) {
          chosen_ssid = scanned;
          chosen_pass = String(backup_password);
          s3Printf("   --> [TỰ ĐỘNG CHỌN MẠNG DỰ PHÒNG]: '%s' (%d dBm)\n", chosen_ssid.c_str(), WiFi.RSSI(i));
        }
      }
    }
  }
  WiFi.scanDelete();

  if (chosen_ssid.length() == 0) {
    startSmartWiFiPortal();
    loadWiFiFromFlash();
    chosen_ssid = (saved_ssid.length() > 0) ? saved_ssid : String(target_ssid);
    chosen_pass = (saved_ssid.length() > 0) ? saved_pass : String(password);
  }

  s3Printf("[WiFi] Đang kết nối tới: '%s' ...\n", chosen_ssid.c_str());
  WiFi.begin(chosen_ssid.c_str(), chosen_pass.c_str());

  int tries = 0;
  while (WiFi.status() != WL_CONNECTED && tries < 24) {
    delay(500);
    s3Printf(".");
    tries++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    IPAddress dns1(8, 8, 8, 8);
    IPAddress dns2(1, 1, 1, 1);
    WiFi.config(WiFi.localIP(), WiFi.gatewayIP(), WiFi.subnetMask(), dns1, dns2);
    s3Printf("\n[WiFi] Đã kết nối thành công! IP của ESP32-S3: %s\n", WiFi.localIP().toString().c_str());
  } else {
    s3Println("\n[WiFi] Kết nối thất bại -> Bật Captive Portal tự bung cửa sổ (AGV_S3_WIFI)...");
    startSmartWiFiPortal();
  }
}

void syncLatestTunnelFromCloud() {
  if (WiFi.status() != WL_CONNECTED) return;
  WiFiClientSecure syncClient;
  syncClient.setInsecure();
  syncClient.setTimeout(5);
  HTTPClient http;
  String url = "https://ntfy.sh/" + String(tunnel_sync_topic) + "/raw?poll=1&since=24h";
  s3Println("[AUTO-SYNC] Đang kiểm tra địa chỉ Đường Hầm mới nhất từ Đám mây...");
  if (http.begin(syncClient, url)) {
    int code = http.GET();
    if (code == 200) {
      String payload = http.getString();
      payload.trim();
      int lastNl = payload.lastIndexOf('\n');
      if (lastNl != -1) {
        payload = payload.substring(lastNl + 1);
        payload.trim();
      }
      if (payload.endsWith(".trycloudflare.com") && payload.length() > 18) {
        if (payload != tunnel_host) {
          tunnel_host = payload;
          s3Printf("[AUTO-SYNC] --> ĐÃ CẬP NHẬT ĐƯỜNG HẦM MỚI: %s\n", tunnel_host.c_str());
        } else {
          s3Printf("[AUTO-SYNC] Đường hầm hiện tại vẫn là mới nhất: %s\n", tunnel_host.c_str());
        }
      }
    }
    http.end();
  }
}

bool tryLidarPinPair(int rx_pin, int motor_pin, long baud) {
  Serial1.end();
  pinMode(motor_pin, OUTPUT);
  digitalWrite(motor_pin, HIGH);
  pinMode(rx_pin, INPUT_PULLUP);
  Serial1.setRxBufferSize(4096);
  int tx_pin = (rx_pin == 17 || motor_pin == 17) ? 18 : 17;
  Serial1.begin(baud, SERIAL_8N1, rx_pin, tx_pin);

  uint8_t start_cmd[] = {0xA5, 0x60};
  Serial1.write(start_cmd, 2);

  unsigned long t0 = millis();
  while (millis() - t0 < 450) {
    if (Serial1.available() >= 16) {
      active_lidar_rx_pin = rx_pin;
      active_lidar_motor_pin = motor_pin;
      lidar_pin_locked = true;
      s3Printf("[LIDAR-LOCKED] --> ĐÃ NHẬN DỮ LIỆU YDLIDAR X2! (RX = GPIO %d, M_EN = GPIO %d, Baud = %ld)\n",
               rx_pin, motor_pin, baud);
      return true;
    }
    delay(10);
  }
  return false;
}

void autoDetectLidarPin() {
  if (lidar_pin_locked) return;

  s3Println("[LIDAR-SCAN] Đang dò tín hiệu UART từ YDLidar X2...");
  if (tryLidarPinPair(16, 15, 115200)) return;
  if (tryLidarPinPair(15, 16, 115200)) return;
  int extra_pins[] = {17, 18, 7, 6, 5, 4, 44};
  for (int i = 0; i < 7; i++) {
    if (tryLidarPinPair(extra_pins[i], 15, 115200)) return;
  }
  if (tryLidarPinPair(16, 15, 128000)) return;
  if (tryLidarPinPair(15, 16, 128000)) return;

  pinMode(15, OUTPUT);
  digitalWrite(15, HIGH);
  Serial1.end();
  Serial1.setRxBufferSize(4096);
  Serial1.begin(115200, SERIAL_8N1, 16, 17);
  active_lidar_rx_pin = 16;
  active_lidar_motor_pin = 15;
}

void handleControlCommand(char cmd) {
  switch (cmd) {
    case 'W':
      s3Println("[CONTROL] ⬆️ NHẬN LỆNH: TIẾN LÊN (W)");
      break;
    case 'S':
      s3Println("[CONTROL] ⬇️ NHẬN LỆNH: LÙI LẠI (S)");
      break;
    case 'A':
      s3Println("[CONTROL] ⬅️ NHẬN LỆNH: RẼ TRÁI (A)");
      break;
    case 'D':
      s3Println("[CONTROL] ➡️ NHẬN LỆNH: RẼ PHẢI (D)");
      break;
    case 'G':
      s3Println("[CONTROL] 🦾 NHẬN LỆNH: GẮP HÀNG (G)");
      break;
    case 'X':
      s3Println("[CONTROL] 🛑 NHẬN LỆNH: DỪNG XE (X)");
      break;
    default:
      break;
  }
}

void readIncomingServerCommands() {
  while (secureClient.available()) {
    uint8_t c = secureClient.read();
    if (c == 'W' || c == 'A' || c == 'S' || c == 'D' || c == 'G' || c == 'X') {
      handleControlCommand((char)c);
    }
    else if (c == '#') {
      String cmdLine = secureClient.readStringUntil('\n');
      cmdLine.trim();
      if (cmdLine.startsWith("WIFI:")) {
        String payload = cmdLine.substring(5);
        if (payload == "CLEAR" || payload.startsWith("CLEAR")) {
          clearWiFiFromFlash();
          s3Println("[WIFI-OTA] Đã nhận lệnh XÓA FLASH từ Dashboard! Đang kết nối lại Wi-Fi mặc định...");
          secureClient.stop();
          ws_connected = false;
          WiFi.disconnect();
          delay(200);
          connectToWiFi();
          return;
        }
        int sep = payload.indexOf('|');
        if (sep != -1) {
          String new_s = payload.substring(0, sep);
          String new_p = payload.substring(sep + 1);
          new_s.trim();
          new_p.trim();
          if (new_s.length() > 0) {
            saveWiFiToFlash(new_s, new_p);
            s3Println("[WIFI-OTA] Đang chuyển sang mạng Wi-Fi mới vừa nhận từ Server...");
            secureClient.stop();
            ws_connected = false;
            WiFi.disconnect();
            delay(200);
            connectToWiFi();
            return;
          }
        }
      }
    }
  }
}

bool connectWebSocketTunnel() {
  secureClient.stop();
  secureClient.setInsecure();
  secureClient.setTimeout(6);

  s3Printf("[WSS-LIDAR] Đang mở đường ống tới %s ...\n", tunnel_host.c_str());
  if (!secureClient.connect(tunnel_host.c_str(), 443)) {
    s3Println("[WSS-LIDAR] Chưa kết nối được tới Cloudflare Tunnel! Đang đồng bộ lại...");
    syncLatestTunnelFromCloud();
    return false;
  }
  secureClient.setNoDelay(true);

  String req = "GET /ws/push_lidar HTTP/1.1\r\n";
  req += "Host: " + tunnel_host + "\r\n";
  req += "Upgrade: websocket\r\n";
  req += "Connection: Upgrade\r\n";
  req += "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n";
  req += "Sec-WebSocket-Version: 13\r\n";
  req += "X-AGV-Key: " + String(agv_secret_key) + "\r\n\r\n";

  secureClient.print(req);

  unsigned long start = millis();
  while (secureClient.connected() && !secureClient.available()) {
    if (millis() - start > 5000) {
      s3Println("[WSS-LIDAR] Quá thời gian chờ bắt tay WebSocket!");
      secureClient.stop();
      return false;
    }
    delay(5);
  }

  String statusLine = secureClient.readStringUntil('\n');
  statusLine.trim();
  while (secureClient.available()) {
    String line = secureClient.readStringUntil('\n');
    if (line == "\r" || line.length() == 0) break;
  }

  if (statusLine.indexOf("101") != -1) {
    s3Println("[WSS-LIDAR] ĐÃ MỞ ĐƯỜNG ỐNG WEBSOCKET LIDAR 2 CHIỀU THÀNH CÔNG!");
    ws_connected = true;
    return true;
  } else {
    s3Printf("[WSS-LIDAR] Phản hồi từ đường hầm: %s\n", statusLine.c_str());
    syncLatestTunnelFromCloud();
    secureClient.stop();
    ws_connected = false;
    return false;
  }
}

bool sendWebSocketBinaryLidar(const uint8_t* data, size_t len) {
  if (!secureClient.connected()) {
    ws_connected = false;
    return false;
  }

  size_t hdr_len = 0;
  ws_pkt_buf[0] = 0x82;
  if (len <= 125) {
    ws_pkt_buf[1] = 0x80 | (uint8_t)len;
    hdr_len = 2;
  } else {
    ws_pkt_buf[1] = 0x80 | 126;
    ws_pkt_buf[2] = (uint8_t)((len >> 8) & 0xFF);
    ws_pkt_buf[3] = (uint8_t)(len & 0xFF);
    hdr_len = 4;
  }

  ws_pkt_buf[hdr_len]     = 0x00;
  ws_pkt_buf[hdr_len + 1] = 0x00;
  ws_pkt_buf[hdr_len + 2] = 0x00;
  ws_pkt_buf[hdr_len + 3] = 0x00;
  hdr_len += 4;

  memcpy(ws_pkt_buf + hdr_len, data, len);
  size_t total_len = hdr_len + len;

  size_t written = secureClient.write(ws_pkt_buf, total_len);
  if (written != total_len) {
    ws_connected = false;
    secureClient.stop();
    return false;
  }
  return true;
}

void setup() {
  Serial.begin(115200);
  delay(800);
  s3Println("\n=== KHỞI ĐỘNG ESP32-S3 + YDLIDAR X2 (WSS TUNNEL + CAPTIVE PORTAL + ĐỒNG BỘ KÉP 2 ESP) ===");

  autoDetectLidarPin();
  connectToWiFi();
  syncLatestTunnelFromCloud();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    ws_connected = false;
    connectToWiFi();
    return;
  }

  if (!ws_connected || !secureClient.connected()) {
    if (!connectWebSocketTunnel()) {
      delay(500);
      return;
    }
  }

  readIncomingServerCommands();

  int available_bytes = Serial1.available();
  if (available_bytes >= 32) {
    lidar_pin_locked = true;
    int bytes_to_read = min(available_bytes, BUF_SIZE);
    int bytes_read = Serial1.readBytes(lidar_buf, bytes_to_read);

    if (bytes_read > 0) {
      unsigned long t0 = millis();
      if (sendWebSocketBinaryLidar(lidar_buf, bytes_read)) {
        pkt_count++;
        last_heartbeat_ms = millis();
        readIncomingServerCommands();
        if (pkt_count == 1 || pkt_count % 20 == 0) {
          s3Printf("[LIDAR-WSS] Gói #%lu | %d bytes (RX=GPIO %d) | Gửi: %lu ms\n",
                   pkt_count, bytes_read, active_lidar_rx_pin, millis() - t0);
        }
      } else {
        s3Println("[LIDAR-WSS] Đường ống ngắt, đang tự động nối lại...");
      }
    }
  } else {
    if (millis() - last_heartbeat_ms > 1200) {
      uint8_t hb = 0x00;
      sendWebSocketBinaryLidar(&hb, 1);
      last_heartbeat_ms = millis();
      readIncomingServerCommands();
    }
    if (!lidar_pin_locked && millis() - last_pin_check_ms > 6000) {
      last_pin_check_ms = millis();
      if (active_lidar_rx_pin == 16) {
        tryLidarPinPair(15, 16, 115200);
      } else {
        tryLidarPinPair(16, 15, 115200);
      }
    }
    delay(8);
  }
}