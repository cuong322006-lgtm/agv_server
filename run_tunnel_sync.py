import os
import subprocess
import re
import ssl
import urllib.request

NTFY_URL = "https://ntfy.sh/cuong_agv_tunnel_2026_secret"
CURRENT_TUNNEL_URL = ""

def publish_tunnel_domain(domain: str):
    global CURRENT_TUNNEL_URL
    CURRENT_TUNNEL_URL = f"https://{domain}"
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(base_dir, "current_tunnel_url.txt"), "w", encoding="utf-8") as f:
            f.write(CURRENT_TUNNEL_URL)
    except Exception:
        pass
    try:
        ctx = ssl._create_unverified_context()
        req = urllib.request.Request(NTFY_URL, data=domain.encode('utf-8'), method='PUT')
        urllib.request.urlopen(req, timeout=5, context=ctx)
        print(f"\n[AUTO-SYNC] ===> DA DONG BO TU DONG LINK TUNNEL MOI LEN DAM MAY CHO ESP32: {domain} ===\n")
    except Exception as e:
        print(f"[!] Khong the dong bo len ntfy: {e}")

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    cloudflared_path = os.path.join(base_dir, "cloudflared.exe")
    if not os.path.exists(cloudflared_path):
        cloudflared_path = "cloudflared.exe"

    cmd = [cloudflared_path, "tunnel", "--protocol", "http2", "--url", "http://127.0.0.1:8000"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    pattern = re.compile(r"https://([a-zA-Z0-9\-]+\.trycloudflare\.com)")
    synced = False

    for line in proc.stdout:
        print(line, end="")
        if not synced:
            m = pattern.search(line)
            if m:
                domain = m.group(1)
                publish_tunnel_domain(domain)
                synced = True

if __name__ == "__main__":
    main()
