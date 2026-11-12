import os
import sys
import shutil
import subprocess
import datetime

def find_git_exe():
    candidates = [
        r"C:\Program Files\Git\cmd\git.exe",
        r"C:\Program Files\Git\bin\git.exe",
        r"C:\Program Files (x86)\Git\cmd\git.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Git\cmd\git.exe"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    try:
        out = subprocess.check_output(["where", "git"], text=True, stderr=subprocess.DEVNULL)
        first = out.strip().splitlines()[0].strip()
        if os.path.exists(first):
            return first
    except Exception:
        pass
    return None

def ensure_git():
    git_exe = find_git_exe()
    if git_exe:
        return git_exe

    print("=" * 72)
    print(" [!] MAY TINH CUA BAN CHUA CAI DAT PHAN MEM GIT!")
    print(" [*] He thong dang tu dong tai va cai dat Git for Windows...")
    print("=" * 72)
    try:
        subprocess.call(["winget", "install", "--id", "Git.Git", "-e", "--source", "winget"])
    except Exception as e:
        print(f"[!] Khong goi duoc winget: {e}")

    git_exe = find_git_exe()
    if git_exe:
        print(f"[+] Da cai dat Git thanh cong tai: {git_exe}")
        return git_exe

    print("\n[!] Vui long tai va cai Git (chi mat 30 giay) tai link chinh thuc:")
    print("    👉 https://git-scm.com/download/win")
    print("    Sau khi cai xong, hay chay lai file .bat nay nhe!")
    return None

def run_git(git_exe, args, check=False):
    cmd = [git_exe] + args
    return subprocess.run(cmd, check=check)

def run_git_output(git_exe, args):
    cmd = [git_exe] + args
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return res.returncode, res.stdout.strip(), res.stderr.strip()

def backup_modified_files(git_exe, base_dir):
    """Tu dong sao luu cac file dang sua tren may vao Goi_Update_Code/Backup_May_Hien_Tai"""
    # Tat quotepath de git status tra ve ten file tieng Viet chuẩn (như 'Báo cáo/...')
    run_git(git_exe, ["config", "core.quotepath", "false"])
    code, status_out, _ = run_git_output(git_exe, ["status", "--porcelain"])
    if code != 0 or not status_out:
        return []
    modified_files = []
    for line in status_out.splitlines():
        if len(line) > 3:
            rel_path = line[3:].strip().strip('"')
            full_path = os.path.join(base_dir, rel_path)
            if os.path.isfile(full_path):
                modified_files.append(rel_path)

    if modified_files:
        now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = os.path.join(base_dir, "Goi_Update_Code", f"Backup_May_Hien_Tai_{now_str}")
        for rel_path in modified_files:
            src = os.path.join(base_dir, rel_path)
            dst = os.path.join(backup_dir, rel_path)
            try:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
            except Exception:
                pass
        print(f"[*] Da tu dong sao luu {len(modified_files)} file dang sua tren may nay vao:")
        print(f"    -> {backup_dir}")
    return modified_files

def get_project_root():
    cur_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(cur_dir) if os.path.basename(cur_dir).lower() == "src" else cur_dir

def do_push():
    base_dir = get_project_root()
    os.chdir(base_dir)

    print("=" * 72)
    print("      [1] DAY CODE MOI NHAT LEN GITHUB (1-CLICK GIT PUSH)")
    print("=" * 72)

    git_exe = ensure_git()
    if not git_exe:
        return

    if not os.path.exists(os.path.join(base_dir, ".git")):
        print("[*] Dang khoi tao kho Git cuc bo lan dau tien...")
        run_git(git_exe, ["init"])
        run_git(git_exe, ["branch", "-M", "main"])

    run_git(git_exe, ["config", "core.quotepath", "false"])
    code, name_out, _ = run_git_output(git_exe, ["config", "user.name"])
    if code != 0 or not name_out:
        run_git(git_exe, ["config", "user.name", "AGV Developer"])
        run_git(git_exe, ["config", "user.email", "agv_team@local.dev"])

    code, remote_url, _ = run_git_output(git_exe, ["remote", "get-url", "origin"])
    if code != 0 or not remote_url:
        print("\n[!] Chua gan link kho chua GitHub (Remote Origin)!")
        print("[*] Cach lay link: Vao https://github.com/new tao 1 repo ten la 'agv_server'")
        print("    (Vi du link: https://github.com/ten_cua_ban/agv_server.git)\n")
        repo_url = input("--> Dan link GitHub Repository cua ban vao day roi nhan Enter: ").strip()
        if not repo_url:
            print("[!] Ban chua nhap link. Huy thao tac!")
            return
        run_git(git_exe, ["remote", "add", "origin", repo_url])
        remote_url = repo_url
        print(f"[+] Da luu link GitHub: {remote_url}\n")
    else:
        print(f"[*] Kho GitHub hien tai: {remote_url}")

    print("\n[*] Cac file vua duoc sua doi / them moi:")
    run_git(git_exe, ["status", "-s"])

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    default_msg = f"Cap nhat code AGV ({now_str})"
    user_msg = input(f"\n--> Nhap ghi chu cap nhat (Nhan Enter de dung '{default_msg}'): ").strip()
    commit_msg = user_msg if user_msg else default_msg

    print("\n[*] Dang gom file va day len GitHub...")
    run_git(git_exe, ["add", "."])
    run_git(git_exe, ["commit", "-m", commit_msg])
    run_git(git_exe, ["branch", "-M", "main"])

    res = run_git(git_exe, ["push", "-u", "origin", "main"])
    if res.returncode == 0:
        print("\n" + "=" * 72)
        print(" [THANH CONG] DA DAY 100% CODE MOI NHAT LEN GITHUB!")
        print(" Bay gio may kia chi can bam '2_Keo_Code_Moi_Ve.bat' la xong!")
        print("=" * 72)
    else:
        print("\n[!] May kia vua day code moi len truoc. Dang tu dong gop code 2 may...")
        pull_res = run_git(git_exe, ["pull", "origin", "main", "--rebase", "--autostash"])
        if pull_res.returncode != 0:
            run_git(git_exe, ["rebase", "--abort"])
            run_git(git_exe, ["pull", "origin", "main", "--no-rebase", "-X", "ours"])
        res2 = run_git(git_exe, ["push", "-u", "origin", "main"])
        if res2.returncode == 0:
            print("\n[THANH CONG] Da gop code 2 may va day 100% code len GitHub!")
        else:
            print("\n[!] Co loi khi day len GitHub. Hay kiem tra lai quyen Collaborator hoac dang nhap GitHub.")

def do_pull():
    base_dir = get_project_root()
    os.chdir(base_dir)

    print("=" * 72)
    print("      [2] KEO CODE MOI NHAT TU GITHUB VE MAY (1-CLICK GIT PULL)")
    print("=" * 72)

    git_exe = ensure_git()
    if not git_exe:
        return

    if not os.path.exists(os.path.join(base_dir, ".git")):
        print("[*] Thu muc nay chua ket noi Git. Dang khoi tao ket noi...")
        run_git(git_exe, ["init"])
        run_git(git_exe, ["branch", "-M", "main"])
        repo_url = input("--> Dan link GitHub Repository cua nhom vao day: ").strip()
        if not repo_url:
            print("[!] Ban chua nhap link!")
            return
        run_git(git_exe, ["remote", "add", "origin", repo_url])
        backup_modified_files(git_exe, base_dir)
        print("[*] Dang tai code moi nhat tu GitHub ve may...")
        run_git(git_exe, ["fetch", "origin", "main"])
        run_git(git_exe, ["reset", "--hard", "origin/main"])
        print("\n" + "=" * 72)
        print(" [THANH CONG] DA DONG BO 100% CODE MOI NHAT TU GITHUB VE MAY!")
        print("=" * 72)
        return

    run_git(git_exe, ["config", "core.quotepath", "false"])
    code, remote_url, _ = run_git_output(git_exe, ["remote", "get-url", "origin"])
    if code != 0 or not remote_url:
        repo_url = input("--> Dan link GitHub Repository cua nhom vao day: ").strip()
        if not repo_url:
            return
        run_git(git_exe, ["remote", "add", "origin", repo_url])

    # Luon sao luu cac file dang sua tren may truoc khi pull
    modified = backup_modified_files(git_exe, base_dir)
    if modified:
        print("\n[!] PHAT HIEN MAY NAY CUNG VUA SUA CODE O CAC FILE:")
        for m in modified:
            print(f"    - {m}")
        print("\nBan muon xu ly nhu the nao khi keo code moi tu GitHub ve?")
        print("  [1] Tu dong GOP CHUNG (Giu ca code may nay vua sua + code moi tren GitHub) - KHUYEN DUNG")
        print("  [2] Lay 100% code moi tren GitHub de len (Bản đang sửa đã được Backup an toàn)")
        choice = input("--> Chon 1 hoac 2 (Nhan Enter de chon [1]): ").strip()
    else:
        choice = "1"

    print(f"\n[*] Dang keo cac file vua sua tu GitHub ({remote_url}) ve may...")
    if choice == "2":
        run_git(git_exe, ["fetch", "origin", "main"])
        run_git(git_exe, ["reset", "--hard", "origin/main"])
        print("\n" + "=" * 72)
        print(" [THANH CONG] DA CAP NHAT 100% THEO BAN TREN GITHUB!")
        print("=" * 72)
        return

    # Dung co --autostash chinh chu cua Git de TU DONG cat moi thay doi (ke ca file CRLF hoac file moi),
    # keo code tu GitHub ve xong roi tu dong bung ra lai ma KHONG BAO GIO bi loi 'You have unstaged changes'!
    res = run_git(git_exe, ["pull", "origin", "main", "--rebase", "--autostash"])
    if res.returncode != 0:
        print("\n[!] Phat hien xung dot khi rebase -> Dang chuyen sang che do Gop (Merge) an toan...")
        run_git(git_exe, ["rebase", "--abort"])
        run_git(git_exe, ["stash", " clear"])
        run_git(git_exe, ["add", "."])
        run_git(git_exe, ["commit", "-m", "Luu tam thay doi cuc bo truoc khi pull"])
        res = run_git(git_exe, ["pull", "origin", "main", "--no-rebase", "-X", "theirs"])

    if res.returncode == 0:
        print("\n" + "=" * 72)
        print(" [THANH CONG] DA KEO VA GOP CODE MOI NHAT TU GITHUB VE MAY!")
        print(" Hay tat va bat lai 'start_server.bat' de ap dung thay doi.")
        print("=" * 72)

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "push"
    if mode == "pull":
        do_pull()
    else:
        do_push()
