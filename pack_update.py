import os
import zipfile
import datetime
import shutil

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Tao thu muc rieng de chua cac ban dong goi Update
    update_dir = os.path.join(base_dir, "Goi_Update_Code")
    os.makedirs(update_dir, exist_ok=True)

    # Xoa file Update_Code_AGV.zip cu o thu muc goc (neu co tu truoc) de gon gang
    old_root_zip = os.path.join(base_dir, "Update_Code_AGV.zip")
    if os.path.exists(old_root_zip):
        try:
            os.remove(old_root_zip)
        except Exception:
            pass

    now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    latest_zip = os.path.join(update_dir, "Update_Code_AGV.zip")
    versioned_zip = os.path.join(update_dir, f"Update_Code_AGV_{now_str}.zip")

    # Chi dong goi cac file code va mo hinh AI moi (bo qua venv 2GB, cloudflared.exe 55MB va thu muc update)
    allowed_exts = ('.py', '.bat', '.md', '.ino', '.h', '.cpp', '.json', '.yaml', '.yml', '.gitignore')
    skip_dirs = {'venv', '__pycache__', '.git', 'dataset_thung_hang', 'Goi_Update_Code'}

    files_to_pack = []
    for root, dirs, files in os.walk(base_dir):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for file in files:
            if file.lower().startswith("update_code_agv") and file.lower().endswith(".zip"):
                continue
            is_code = file.lower().endswith(allowed_exts)
            is_custom_model = file.lower().endswith('.pt') and file.lower() != 'yolov8n.pt'
            if is_code or is_custom_model:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, base_dir)
                mtime = os.path.getmtime(full_path)
                size_kb = os.path.getsize(full_path) / 1024.0
                files_to_pack.append((rel_path, full_path, mtime, size_kb))

    # Sap xep theo thoi gian sua doi moi nhat len dau de nguoi dung nhin thay ngay file vua sua!
    files_to_pack.sort(key=lambda x: x[2], reverse=True)

    print("=" * 74)
    print("   HE THONG DONG GOI CAP NHAT CODE AGV SERVER (SIÊU NHẸ - <100 KB)")
    print("=" * 74)
    print(f" [{'THOI GIAN SUA CUOI':<19}] | [{'DUNG LUONG':>9}] | {'TEN FILE TRONG GOI UPDATE'}")
    print("-" * 74)

    with zipfile.ZipFile(latest_zip, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for idx, (rel_path, full_path, mtime, size_kb) in enumerate(files_to_pack):
            dt_str = datetime.datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
            tag = " <-- [MOI SUA]" if idx < 3 else ""
            print(f" [{dt_str}] | {size_kb:>7.1f} KB | {rel_path}{tag}")
            zf.write(full_path, arcname=rel_path)

    # Luu them 1 ban co gan ngay gio de luu lich su cac ban cap nhat
    shutil.copy2(latest_zip, versioned_zip)

    total_zip_kb = os.path.getsize(latest_zip) / 1024.0
    print("-" * 74)
    print(f"[+] DA DONG GOI THANH CONG {len(files_to_pack)} FILE CODE VAO THU MUC RIENG:")
    print(f"    📂 Thu muc chua: {update_dir}")
    print(f"    1. File luon moi nhat : Update_Code_AGV.zip ({total_zip_kb:.1f} KB)")
    print(f"    2. File luu theo gio  : Update_Code_AGV_{now_str}.zip ({total_zip_kb:.1f} KB)")
    print("[*] Thu muc 'Goi_Update_Code' se tu dong mo len ngay bay gio de ban keo file gui Zalo!")
    print("=" * 74)

    # Tu dong bat cua so Windows Explorer mo thang thu muc Goi_Update_Code
    try:
        os.startfile(update_dir)
    except Exception:
        pass

if __name__ == "__main__":
    main()
