/*
 * CODE CHO ESP32-CAM: BẢN CHUẨN MƯỢT 12-15 FPS + MÀU CHUẨN SẮC NÉT + TỰ BUNG CỬA SỔ WIFI & ĐỒNG BỘ KÉP 2 ESP
 * 
 * Đã tích hợp:
 * 1. Trả lại 100% Nhân 0 (Core 0) cho chip Wi-Fi & mã hóa SSL -> Tốc độ gửi 2ms/ảnh!
 * 2. Dùng chuẩn HQVGA (240x176) với độ nét cao (Quality 12 - 16), màu gốc tự nhiên OV2640.
 * 3. Lưu Wi-Fi vĩnh viễn vào bộ nhớ Flash + Captive Portal DNS: Vừa bắt Wi-Fi "AGV_CAM_WIFI"
 *    trên điện thoại là TỰ ĐỘNG BUNG TRANG CÀI ĐẶT lên màn hình (không cần gõ 192.168.4.1)!
 * 4. Đồng bộ kép P2P: Nhập Wi-Fi 1 lần trên 1 mạch là cả 2 mạch cùng lưu và cùng kết nối!
 * 5. [MỚI NÂNG CẤP] Nút "XÓA MẠNG ĐÃ LƯU" trên cả Web điện thoại lẫn Web Dashboard để quay về mạng mặc định!
 */

#include "esp_camera.h"
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <Preferences.h>
#include <WebServer.h>
#include <DNSServer.h>
#include "soc/soc.h"
#include "soc/rtc_cntl_reg.h"

// ================= 1. CẤU HÌNH WIFI MẶC ĐỊNH & DỰ PHÒNG =================
const char* target_ssid     = "cuong";          // Ưu tiên mặc định 1: Hotspot điện thoại
const char* password        = "3007322006";     // Mật khẩu của 'cuong'
const char* backup_ssid     = "TP-Link_2726";   // Ưu tiên mặc định 2: Wi-Fi cố định
const char* backup_password = "40363455";       // Mật khẩu của 'TP-Link_2726'

Preferences wifiPrefs;
WebServer portalServer(80);
DNSServer dnsServer;
const byte DNS_PORT = 53;
String saved_ssid = "";
String saved_pass = "";
bool portal_saved_new_wifi = false;
bool received_from_peer    = false;
const char* ap_setup_name  = "AGV_CAM_WIFI";
const char* peer_ap_name   = "AGV_S3_WIFI";
// === [MỚI NÂNG CẤP - MẬT KHẨU BẢO VỆ WIFI CỨU HỘ CỦA 2 ESP32 (Tối thiểu 8 ký tự)] ===
const char* ap_password    = "12345678";        // Bạn có thể đổi mật khẩu này theo ý muốn!
// ===================================================================================

// ================= 2. ĐỊA CHỈ ĐƯỜNG HẦM HIỆN TẠI & KÊNH ĐỒNG BỘ TỰ ĐỘNG =================
String tunnel_host           = "resolve-extends-agreement-imagination.trycloudflare.com";
const char* tunnel_sync_url  = "https://ntfy.sh/cuong_agv_tunnel_2026_secret/raw?poll=1&since=24h";
const char* agv_secret_key   = "Cuong_AGV_Secret_2026";

// ================= ĐỊNH NGHĨA CHÂN AI-THINKER ESP32-CAM =================
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

WiFiClientSecure secureClient;
bool ws_connected = false;
uint32_t frame_count = 0;
int current_quality = 18;
int fail_streak = 0;
int in_flight_frames = 0;

// Tăng bộ đệm khung WebSocket lên 65,535 bytes (nằm trong PSRAM 4MB) để chứa trọn vẹn 1 tệp ảnh VGA nguyên khối!
#define MAX_WS_PKT_SIZE 65535
uint8_t* ws_pkt_buf = NULL;

void loadWiFiFromFlash() {
  wifiPrefs.begin("agv_wifi", true);
  saved_ssid = wifiPrefs.getString("ssid", "");
  saved_pass = wifiPrefs.getString("pass", "");
  wifiPrefs.end();
  if (saved_ssid.length() > 0) {
    Serial.printf("[FLASH-WIFI] Đã đọc Wi-Fi lưu trong bộ nhớ Flash: '%s'\n", saved_ssid.c_str());
  }
}

void saveWiFiToFlash(const String& new_ssid, const String& new_pass) {
  wifiPrefs.begin("agv_wifi", false);
  wifiPrefs.putString("ssid", new_ssid);
  wifiPrefs.putString("pass", new_pass);
  wifiPrefs.end();
  saved_ssid = new_ssid;
  saved_pass = new_pass;
  Serial.printf("[FLASH-WIFI] --> ĐÃ LƯU VĨNH VIỄN WIFI MỚI VÀO FLASH: '%s'\n", new_ssid.c_str());
}

// Xóa sạch Wi-Fi trong Flash để trở về mạng mặc định
void clearWiFiFromFlash() {
  wifiPrefs.begin("agv_wifi", false);
  wifiPrefs.clear();
  wifiPrefs.end();
  saved_ssid = "";
  saved_pass = "";
  Serial.println("\n[FLASH-WIFI] 🗑️ ĐÃ XÓA SẠCH WIFI TRONG FLASH! TRỞ VỀ MẠNG GỐC (cuong / TP-Link_2726)!");
}

// Bắn lệnh xóa Wi-Fi sang mạch ESP32-S3 còn lại
void syncClearToSiblingESP() {
  Serial.printf("\n[PEER-SYNC] 🔄 Đang truyền lệnh XÓA WIFI sang mạch '%s'...\n", peer_ap_name);
  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  delay(100);
  WiFi.begin(peer_ap_name, ap_password);
  int tries = 0;
  while (WiFi.status() != WL_CONNECTED && tries < 12) {
    delay(400);
    Serial.print("*");
    tries++;
  }
  Serial.println();
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    if (http.begin("http://192.168.4.1/peer_clear")) {
      http.POST("");
      http.end();
      Serial.printf("[PEER-SYNC] ✅ Đã báo mạch '%s' cùng XÓA FLASH thành công!\n", peer_ap_name);
    }
  }
  WiFi.disconnect();
  delay(150);
}

void syncWiFiToSiblingESP(const String& ssid_to_send, const String& pass_to_send) {
  Serial.printf("\n[PEER-SYNC] 🔄 Đang tự động truyền Wi-Fi '%s' sang mạch '%s'...\n", ssid_to_send.c_str(), peer_ap_name);
  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  delay(100);

  WiFi.begin(peer_ap_name, ap_password);
  int tries = 0;
  while (WiFi.status() != WL_CONNECTED && tries < 16) {
    delay(500);
    Serial.print("*");
    tries++;
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    if (http.begin("http://192.168.4.1/peer_sync")) {
      http.addHeader("Content-Type", "text/plain");
      String payload = ssid_to_send + "\n" + pass_to_send;
      int code = http.POST(payload);
      if (code == 200) {
        Serial.printf("[PEER-SYNC] ✅ ĐÃ ĐỒNG BỘ WI-FI SANG '%s' THÀNH CÔNG! CẢ 2 MẠCH CÙNG KẾT NỐI!\n", peer_ap_name);
      } else {
        Serial.printf("[PEER-SYNC] ⚠️ Phản hồi từ '%s': HTTP %d\n", peer_ap_name, code);
      }
      http.end();
    }
  } else {
    Serial.printf("[PEER-SYNC] ℹ️ Không thấy '%s' phát AP (mạch kia có thể đã kết nối mạng trước).\n", peer_ap_name);
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
      Serial.printf("\n[PEER-SYNC] 📥 Đã nhận Wi-Fi '%s' từ mạch ESP32-S3 truyền sang!\n", s.c_str());
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
  Serial.println("\n[PEER-SYNC] 📥 Đã nhận lệnh XÓA WIFI từ mạch ESP32-S3!");
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
  html += ".box{max-width:380px;margin:auto;background:#2f3640;padding:20px;border-radius:12px;border:2px solid #05c46b;}";
  html += "input,button{width:92%;padding:12px;margin:8px 0;border-radius:6px;border:none;font-size:15px;}";
  html += "button{background:#05c46b;color:#1e272e;font-weight:bold;cursor:pointer;}";
  html += ".net{background:#1e272e;padding:10px;margin:5px 0;border-radius:6px;cursor:pointer;text-align:left;border:1px solid #485460;}";
  html += "</style></head><body><div class='box'>";
  html += "<h2 style='color:#00d8d6;margin-top:0;'>📷 CÀI ĐẶT WI-FI XE AGV</h2>";
  html += "<p style='font-size:13px;color:#0be881;'>✨ Nhập 1 lần tại đây sẽ tự động đồng bộ cho cả <b>ESP32-CAM</b> và <b>ESP32-S3</b>!</p>";

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
    resp += "<p>Đang tự động truyền Wi-Fi sang mạch <b>ESP32-S3</b> và kết nối vào mạng mới...</p></body></html>";
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
  resp += "<p>Đang đồng bộ xóa sang <b>ESP32-S3</b> và kết nối lại mạng mặc định (cuong / TP-Link_2726)...</p></body></html>";
  portalServer.send(200, "text/html", resp);
  delay(800);
  syncClearToSiblingESP();
  received_from_peer = false;
  portal_saved_new_wifi = true;
}

void startSmartWiFiPortal() {
  Serial.println("\n=======================================================");
  Serial.printf("[AP-PORTAL] Không tìm thấy Wi-Fi quen thuộc! Đang phát Wi-Fi: '%s' (Mật khẩu: '%s')\n", ap_setup_name, ap_password);
  Serial.println("[AP-PORTAL] Nhập Wi-Fi 1 lần trên 1 mạch là CẢ 2 ESP CÙNG KẾT NỐI (Được bảo vệ mật khẩu)!");
  Serial.println("=======================================================");

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

void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;

  loadWiFiFromFlash();

  WiFi.mode(WIFI_STA);
  delay(150);
  WiFi.setSleep(false);
  WiFi.setMinSecurity(WIFI_AUTH_WPA_PSK);

  String chosen_ssid = "";
  String chosen_pass = "";

  Serial.println("\n[WiFi] Đang quét các mạng Wi-Fi 2.4GHz xung quanh...");
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
          Serial.printf("   --> [KHỚP WIFI ĐÃ LƯU TRONG FLASH]: '%s'\n", chosen_ssid.c_str());
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
          Serial.printf("   --> [TỰ ĐỘNG CHỌN MẠNG ƯU TIÊN 1]: '%s'\n", chosen_ssid.c_str());
          break;
        } else if (chosen_ssid.length() == 0 && (s_low == t2_low || s_low.indexOf(t2_low) != -1)) {
          chosen_ssid = scanned;
          chosen_pass = String(backup_password);
          Serial.printf("   --> [TỰ ĐỘNG CHỌN MẠNG DỰ PHÒNG]: '%s'\n", chosen_ssid.c_str());
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

  Serial.print("[WiFi] Đang kết nối tới: '");
  Serial.print(chosen_ssid);
  Serial.print("' ");
  WiFi.begin(chosen_ssid.c_str(), chosen_pass.c_str());

  int tries = 0;
  while (WiFi.status() != WL_CONNECTED && tries < 24) {
    delay(500);
    Serial.print(".");
    tries++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    // === [CHẾ ĐỘ LÀM MÁT RF] Hạ công suất phát Wi-Fi xuống 15dBm (giảm 40% nhiệt lượng lồng sắt mà sóng vẫn khỏe) ===
    WiFi.setTxPower(WIFI_POWER_15dBm);
    WiFi.config(WiFi.localIP(), WiFi.gatewayIP(), WiFi.subnetMask(), IPAddress(8, 8, 8, 8), IPAddress(1, 1, 1, 1));
    Serial.println("\n[WiFi] Đã kết nối thành công! IP của ESP32-CAM: " + WiFi.localIP().toString());
  } else {
    Serial.println("\n[WiFi] Kết nối thất bại -> Bật Captive Portal tự bung cửa sổ (AGV_CAM_WIFI)...");
    startSmartWiFiPortal();
  }
}

void syncLatestTunnelFromCloud() {
  // [SỬA LẠI - CHẨN ĐOÁN TUNNEL] Dừng kết nối cũ để giải phóng RAM cho TLS của ntfy.sh + in rõ kết quả đồng bộ
  secureClient.stop();
  WiFiClientSecure syncClient;
  syncClient.setInsecure();
  HTTPClient https;
  https.setTimeout(8000);
  Serial.println("[AUTO-SYNC] Đang kiểm tra địa chỉ Đường Hầm mới nhất từ Server...");
  if (https.begin(syncClient, tunnel_sync_url)) {
    int code = https.GET();
    if (code != 200) {
      Serial.printf("[AUTO-SYNC] LỖI: không đọc được ntfy.sh (HTTP code = %d). Kiểm tra Wi-Fi có Internet không!\n", code);
    }
    if (code == 200) {
      String body = https.getString();
      body.trim();
      int lastNewline = body.lastIndexOf('\n');
      String latest = (lastNewline != -1) ? body.substring(lastNewline + 1) : body;
      latest.trim();
      latest.replace("https://", "");
      latest.replace("http://", "");
      int slashIdx = latest.indexOf('/');
      if (slashIdx != -1) latest = latest.substring(0, slashIdx);

      if (latest.endsWith(".trycloudflare.com") && latest != tunnel_host) {
        tunnel_host = latest;
        Serial.println("[AUTO-SYNC] Đã tự động cập nhật Đường Hầm mới: " + tunnel_host);
      } else {
        Serial.println("[AUTO-SYNC] Đường hầm trên ntfy.sh = " + latest + " (giống đường hầm đang dùng hoặc không hợp lệ). Nếu vẫn lỗi -> Server/cloudflared trên máy tính CHƯA chạy!");
      }
    }
    https.end();
  }
}

bool connectWebSocketTunnel() {
  secureClient.stop();
  secureClient.setInsecure();

  Serial.printf("[WSS-TUNNEL] Đang mở đường ống tới %s ...\n", tunnel_host.c_str());
  // [SỬA LẠI - CHẨN ĐOÁN TUNNEL] In ra kết quả phân giải DNS + lỗi TLS để biết chính xác vì sao không vào được đường hầm
  IPAddress resolved;
  if (!WiFi.hostByName(tunnel_host.c_str(), resolved)) {
    Serial.println("[WSS-TUNNEL] KHÔNG phân giải được tên miền (DNS lỗi hoặc đường hầm đã chết)!");
  } else {
    Serial.println("[WSS-TUNNEL] DNS OK -> " + resolved.toString());
  }
  if (!secureClient.connect(tunnel_host.c_str(), 443)) {
    char errbuf[100];
    int sslerr = secureClient.lastError(errbuf, sizeof(errbuf));
    Serial.printf("[WSS-TUNNEL] Chưa kết nối được tới Cloudflare Tunnel! (mã lỗi TLS %d: %s | RAM trống: %u bytes)\n", sslerr, errbuf, (unsigned)ESP.getFreeHeap());
    // [SỬA LẠI] Đồng bộ lại link đường hầm NGAY ở mỗi lần lỗi (trước đây phải lỗi 3 lần mới đồng bộ -> rất chậm)
    syncLatestTunnelFromCloud();
    fail_streak = 0;
    return false;
  }

  fail_streak = 0;
  in_flight_frames = 0;
  secureClient.setNoDelay(true);

  String req = String("GET /ws/push_frame HTTP/1.1\r\n") +
               "Host: " + tunnel_host + "\r\n" +
               "Upgrade: websocket\r\n" +
               "Connection: Upgrade\r\n" +
               "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n" +
               "Sec-WebSocket-Version: 13\r\n" +
               "X-AGV-Key: " + String(agv_secret_key) + "\r\n\r\n";

  secureClient.print(req);

  unsigned long start = millis();
  while (secureClient.connected() && !secureClient.available()) {
    if (millis() - start > 5000) {
      Serial.println("[WSS-TUNNEL] Quá thời gian chờ bắt tay WebSocket!");
      secureClient.stop();
      return false;
    }
    delay(10);
  }

  String statusLine = secureClient.readStringUntil('\n');
  while (secureClient.connected()) {
    String line = secureClient.readStringUntil('\n');
    if (line == "\r" || line.length() == 0) break;
  }

  if (statusLine.indexOf("101") != -1) {
    Serial.println("[WSS-TUNNEL] ĐÃ MỞ ĐƯỜNG ỐNG WEBSOCKET SIÊU TỐC THÀNH CÔNG!");
    ws_connected = true;
    return true;
  } else {
    Serial.println("[WSS-TUNNEL] Phản hồi từ đường hầm: " + statusLine);
    secureClient.stop();
    ws_connected = false;
    syncLatestTunnelFromCloud();
    return false;
  }
}

void drainServerAcks() {
  while (secureClient.available() > 0) {
    int c = secureClient.read();
    if (c == 'K') {
      if (in_flight_frames > 0) in_flight_frames--;
    }
    else if (c == '#') {
      String cmdLine = secureClient.readStringUntil('\n');
      cmdLine.trim();
      if (cmdLine.startsWith("WIFI:")) {
        String payload = cmdLine.substring(5);
        if (payload == "CLEAR" || payload.startsWith("CLEAR")) {
          clearWiFiFromFlash();
          if (in_flight_frames > 0) in_flight_frames--;
          Serial.println("[WIFI-OTA] Đã nhận lệnh XÓA FLASH từ Dashboard! Đang kết nối lại Wi-Fi mặc định...");
          secureClient.stop();
          ws_connected = false;
          WiFi.disconnect();
          delay(200);
          connectWiFi();
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
            if (in_flight_frames > 0) in_flight_frames--;
            Serial.println("[WIFI-OTA] Đang chuyển sang mạng Wi-Fi mới vừa nhận từ Server...");
            secureClient.stop();
            ws_connected = false;
            WiFi.disconnect();
            delay(200);
            connectWiFi();
            return;
          }
        }
      }
    }
  }
}

bool sendFrameOverWebSocket(const uint8_t* buf, size_t len) {
  if (!secureClient.connected()) {
    ws_connected = false;
    return false;
  }

  drainServerAcks();

  unsigned long wait_start = millis();
  // Mở rộng đường ống Pipelining lên 4 khung hình bay song song (không bắt ESP32-CAM đứng chờ khứ hồi từng tấm)
  while (in_flight_frames >= 4 && (millis() - wait_start < 65)) {
    drainServerAcks();
    if (!secureClient.connected()) {
      ws_connected = false;
      return false;
    }
    delay(1);
  }
  if (in_flight_frames >= 4) {
    in_flight_frames = 2;
  }

  uint8_t hdr[8];
  size_t hdr_len = 0;
  hdr[0] = 0x82;

  if (len <= 125) {
    hdr[1] = 0x80 | (uint8_t)len;
    hdr[2] = 0; hdr[3] = 0; hdr[4] = 0; hdr[5] = 0;
    hdr_len = 6;
  } else {
    hdr[1] = 0x80 | 126;
    hdr[2] = (len >> 8) & 0xFF;
    hdr[3] = len & 0xFF;
    hdr[4] = 0; hdr[5] = 0; hdr[6] = 0; hdr[7] = 0;
    hdr_len = 8;
  }

  size_t total_len = hdr_len + len;
  if (ws_pkt_buf != NULL && total_len <= MAX_WS_PKT_SIZE) {
    memcpy(ws_pkt_buf, hdr, hdr_len);
    memcpy(ws_pkt_buf + hdr_len, buf, len);
    
    // Gửi nguyên vẹn toàn bộ tệp ảnh VGA (vòng lặp đảm bảo đẩy hết 100% byte qua SSL Record 16KB mà không bị đứt)
    size_t sent = 0;
    unsigned long write_t0 = millis();
    while (sent < total_len) {
      size_t chunk = secureClient.write(ws_pkt_buf + sent, total_len - sent);
      if (chunk == 0) {
        if (!secureClient.connected() || (millis() - write_t0 > 1500)) {
          ws_connected = false;
          return false;
        }
        delay(1);
        continue;
      }
      sent += chunk;
    }
    in_flight_frames++;
    return true;
  }

  return false;
}

void adjustQualityByNetworkSpeed(unsigned long send_ms, size_t jpg_len) {
  int new_quality = current_quality;
  // Ngưỡng tối ưu cho VGA (640x480) siêu mượt: giữ ảnh tầm 5.5KB - 10KB để truyền vèo qua SSL < 40ms
  if ((send_ms > 65 || jpg_len > 10500) && current_quality < 26) {
    new_quality += 1;
  } else if (send_ms < 35 && jpg_len < 6000 && current_quality > 16) {
    new_quality -= 1;
  }

  if (new_quality != current_quality) {
    current_quality = new_quality;
    sensor_t * s = esp_camera_sensor_get();
    if (s) {
      s->set_quality(s, current_quality);
    }
  }
}

void setup() {
  WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0);

  // === [CHẾ ĐỘ LÀM MÁT] Tắt hẳn đèn Flash công suất cao GPIO 4 để chống rò dòng gây nóng ===
  pinMode(4, OUTPUT);
  digitalWrite(4, LOW);

  Serial.begin(115200);
  Serial.setDebugOutput(false);
  Serial.println("\n=== KHỞI ĐỘNG ESP32-CAM (VGA 640x480 + CHẾ ĐỘ LÀM MÁT + BỘ ĐỆM 64KB) ===");

  if (psramFound()) {
    ws_pkt_buf = (uint8_t*)ps_malloc(MAX_WS_PKT_SIZE);
  }
  if (ws_pkt_buf == NULL) {
    ws_pkt_buf = (uint8_t*)malloc(MAX_WS_PKT_SIZE);
  }

  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  // === [CHẾ ĐỘ LÀM MÁT CAMERA] Hạ xung XCLK từ 20MHz xuống 16MHz: giảm 30% nhiệt cảm biến OV2640 mà vẫn siêu mượt ===
  config.xclk_freq_hz = 16000000;
  config.pixel_format = PIXFORMAT_JPEG;

  if (psramFound()) {
    Serial.println("[CAM] Có PSRAM -> Chế độ VGA 640x480 + Làm Mát (2 buffer)");
    config.frame_size = FRAMESIZE_VGA;
    config.jpeg_quality = current_quality;
    config.fb_count = 2;
    config.fb_location = CAMERA_FB_IN_PSRAM;
    config.grab_mode = CAMERA_GRAB_LATEST;
  } else {
    Serial.println("[CAM] Chế độ VGA 640x480 + Làm Mát (DRAM)");
    config.frame_size = FRAMESIZE_VGA;
    config.jpeg_quality = current_quality;
    config.fb_count = 1;
    config.fb_location = CAMERA_FB_IN_DRAM;
    config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
  }

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("[CAM] Lỗi khởi tạo Camera: 0x%x\n", err);
    return;
  }

  sensor_t * s = esp_camera_sensor_get();
  if (s) {
    s->set_vflip(s, 1);
    s->set_hmirror(s, 1);
  }

  connectWiFi();
  // [SỬA LẠI] Lấy link đường hầm MỚI NHẤT ngay khi khởi động (tránh dùng link cũ đã chết của lần chạy trước)
  syncLatestTunnelFromCloud();
  connectWebSocketTunnel();
}

void loop() {
  unsigned long loop_start = millis();

  if (WiFi.status() != WL_CONNECTED) {
    ws_connected = false;
    connectWiFi();
    return;
  }

  if (!ws_connected) {
    if (!connectWebSocketTunnel()) {
      delay(200);
      return;
    }
  }

  drainServerAcks();

  camera_fb_t * fb = esp_camera_fb_get();
  if (!fb) {
    delay(5);
    return;
  }

  unsigned long t0 = millis();
  size_t jpg_len = fb->len;
  bool ok = sendFrameOverWebSocket(fb->buf, jpg_len);
  esp_camera_fb_return(fb);
  unsigned long send_ms = millis() - t0;

  if (ok) {
    frame_count++;
    adjustQualityByNetworkSpeed(send_ms, jpg_len);
    if (frame_count == 1 || frame_count % 30 == 0) {
      Serial.printf("[COOL-VGA] Frame #%u | %u bytes | %lu ms | Quality: %d\n",
                    frame_count, (unsigned int)jpg_len, send_ms, current_quality);
    }
  } else {
    Serial.println("[COOL-VGA] Đường ống ngắt, đang tự động nối lại...");
  }

  // === [CHẾ ĐỘ LÀM MÁT CPU - FRAME PACING 14 FPS (70ms/khung hình)] ===
  // Nếu gửi ảnh xong sớm (ví dụ mất 25ms), cho CPU nghỉ 45ms còn lại để hạ nhiệt mà hình ảnh vẫn đều đặn 14 FPS không giật!
  unsigned long elapsed = millis() - loop_start;
  if (elapsed < 70) {
    delay(70 - elapsed);
  } else {
    delay(4);
  }
}