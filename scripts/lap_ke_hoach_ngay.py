#!/usr/bin/env python3
"""
lap_ke_hoach_ngay.py — Script điều phối: gộp toàn bộ quy trình lên lịch
hàng ngày (Bước 0 → đối chiếu → sinh kế hoạch → deploy → verify) thành
1 lệnh, thay vì gọi tay nhiều bước rời rạc mỗi phiên.

⚠️ KHÔNG tự tải Google Sheet — Cod vẫn cần dùng Drive connector (MCP)
trong phiên chat để tải "HGC Kết quả nhập liệu" về 1 file .xlsx trước
(không có auth độc lập cho script chạy nền). Script này bắt đầu TỪ SAU
bước đó — nhận đường dẫn xlsx đã tải làm tham số.

Việc script này gộp lại (trước đây phải gọi tay từng bước):
    1. Đối chiếu Miên (đảo trộn) — actual+1, tự vá plan ngày kế nếu lệch
    2. (Tuỳ chọn) Tạo lại Phong/Hà nếu có file "Dãy kéo rút" mới
    3. Git add + commit + push MỘT LẦN cho tất cả thay đổi
    4. Verify cả 4 link live (curl), tự nudge (empty commit) nếu có link
       chưa lên sau khi đợi, verify lại 1 lần
    5. In bảng tổng kết sẵn để dán vào _Giao Bang.md mục C

Dùng:
    python3 scripts/lap_ke_hoach_ngay.py \\
        --ketqua "<file KetQua đã tải>.xlsx" \\
        --ngay-actual 2026-07-11 \\
        --ngay-ke-hoach 2026-07-12 \\
        [--day-keo-rut "<file Dãy kéo rút mới>.xlsx"]   # nếu Tim gửi file mới cho Phong/Hà

Ví dụ tối thiểu (chỉ đối chiếu + verify, không có file Dãy kéo rút mới):
    python3 scripts/lap_ke_hoach_ngay.py --ketqua ketqua.xlsx \\
        --ngay-actual 2026-07-11 --ngay-ke-hoach 2026-07-12
"""
import os, sys, subprocess, argparse, time, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import doi_chieu

REPO_DIR = Path(__file__).parent.parent
BASE_URL = "https://robachop.github.io/hgc-nhap-lieu/"
CF_BASE_URL = "https://hgc-nhap-lieu.pages.dev/"
WORKERS = ["phong", "ha", "mien", "hao"]


def curl_status(url):
    try:
        r = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", f"{url}?cb={int(time.time())}"],
            capture_output=True, text=True, timeout=15,
        )
        return r.stdout.strip()
    except Exception:
        return "ERR"


def git_commit_push(message):
    result = subprocess.run(
        f'cd "{REPO_DIR}" && git add -A plans/ kehoach-*.html && git commit -m "{message}" && git push origin main',
        shell=True, capture_output=True, text=True,
    )
    ok = result.returncode == 0
    out = (result.stdout + result.stderr).strip()
    return ok, out


def nudge_pages():
    result = subprocess.run(
        f'cd "{REPO_DIR}" && git commit --allow-empty -m "Nudge Pages rebuild" && git push origin main',
        shell=True, capture_output=True, text=True,
    )
    return result.returncode == 0


def deploy_cloudflare():
    """Deploy song song lên Cloudflare Pages (Phương án B — dự phòng khi GitHub
    Actions/Pages outage, xem _Giao Bang.md 2026-07-20). Cần CLOUDFLARE_API_TOKEN
    + CLOUDFLARE_ACCOUNT_ID trong biến môi trường — KHÔNG hardcode token vào đây
    vì repo này PUBLIC. Nếu thiếu biến môi trường, bỏ qua (không chặn Phương án A)."""
    if not os.environ.get("CLOUDFLARE_API_TOKEN") or not os.environ.get("CLOUDFLARE_ACCOUNT_ID"):
        print("   ⏸  Thiếu CLOUDFLARE_API_TOKEN/CLOUDFLARE_ACCOUNT_ID trong env — bỏ qua Phương án B "
              "(xem lệnh export trong 'Tài Khoản & Token — Hạ Tầng.md')")
        return False
    result = subprocess.run(
        ["npx", "--yes", "wrangler@latest", "pages", "deploy", ".",
         "--project-name", "hgc-nhap-lieu", "--branch", "main", "--commit-dirty=true"],
        cwd=REPO_DIR, capture_output=True, text=True, timeout=180,
    )
    ok = result.returncode == 0
    if not ok:
        print(f"   ⚠️  Deploy Cloudflare lỗi: {(result.stdout + result.stderr).strip()[-500:]}")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ketqua", required=True, help="File KetQua đã tải từ Google Sheet")
    ap.add_argument("--ngay-actual", required=True, help="Ngày lấy actual để đối chiếu, YYYY-MM-DD")
    ap.add_argument("--ngay-ke-hoach", required=True, help="Ngày lên kế hoạch (thường = ngay-actual + 1)")
    ap.add_argument("--day-keo-rut", default=None, help="File Excel 'Dãy kéo rút' mới (nếu Tim gửi) — tạo lại Phong/Hà")
    args = ap.parse_args()

    slug = datetime.date.fromisoformat(args.ngay_ke_hoach).strftime("%d%m%Y")

    print(f"{'═'*60}")
    print(f"  LẬP KẾ HOẠCH {args.ngay_ke_hoach} (đối chiếu actual {args.ngay_actual})")
    print(f"{'═'*60}\n")

    # ── Bước 1: Đối chiếu + vá Miên ─────────────────────────────
    print("① Đối chiếu Miên (đảo trộn)...")
    plan_mien = REPO_DIR / "plans" / f"mien-{slug}.json"
    df = doi_chieu.doc_actual(args.ketqua)
    ket_qua = doi_chieu.doi_chieu_dao_tron(df, "Mien", args.ngay_actual)
    print(f"   → {len(ket_qua)} bể có actual")
    lech = doi_chieu.so_voi_plan(ket_qua, plan_mien)
    if not lech:
        print(f"   ✅ {plan_mien.name}: khớp hoàn toàn, không cần sửa")
    else:
        print(f"   ⚠️  {len(lech)} bể lệch — đang vá:")
        for item in lech:
            print(f"      bể {item['be']:>3}: plan={item['plan_lsx']} → {item['de_xuat']}")
        doi_chieu.ap_dung(lech, plan_mien)

    # ── Bước 2 (tuỳ chọn): Tạo lại Phong/Hà ─────────────────────
    if args.day_keo_rut:
        print("\n② Tạo lại Phong + Hà từ file Dãy kéo rút mới...")
        r = subprocess.run(
            [sys.executable, str(REPO_DIR / "scripts" / "regen_phong_ha.py"),
             args.day_keo_rut, args.ngay_ke_hoach],
            capture_output=True, text=True,
        )
        print("  " + r.stdout.replace("\n", "\n  "))
        if r.returncode != 0:
            print(f"   ⚠️  Lỗi: {r.stderr}")
    else:
        print("\n② Không có file Dãy kéo rút mới — giữ nguyên Phong/Hà hiện có")

    # ── Bước 3: Commit + push (nếu bước 2 chưa tự push) ─────────
    print("\n③ Commit + push...")
    ok, out = git_commit_push(f"Doi chieu + ke hoach {args.ngay_ke_hoach}")
    if ok:
        print("   ✅ Đã push")
    elif "nothing to commit" in out:
        print("   ℹ️  Không có gì mới để push (đã push ở bước 2, hoặc plan Mien không đổi)")
    else:
        print(f"   ⚠️  {out}")

    # ── Bước 4: Verify 4 link Phương án A (GitHub Pages), tự nudge nếu cần ──
    print("\n④ Verify 4 link — Phương án A (GitHub Pages)...")
    time.sleep(20)
    links = {w: f"{BASE_URL}kehoach-{w}-{slug}.html" for w in WORKERS}
    status = {w: curl_status(u) for w, u in links.items()}
    not_live = [w for w, s in status.items() if s != "200"]

    if not_live:
        print(f"   ⚠️  Chưa live: {not_live} — nudge build...")
        nudge_pages()
        time.sleep(25)
        status = {w: curl_status(u) for w, u in links.items()}
        not_live = [w for w, s in status.items() if s != "200"]

    for w, u in links.items():
        icon = "✅" if status[w] == "200" else "❌"
        print(f"   {icon} {w:6}: {status[w]}  {u}")

    if not_live:
        print(f"\n   ⚠️  Vẫn chưa live: {not_live} — kiểm tra build: gh api repos/robachop/hgc-nhap-lieu/pages/builds/latest")

    # ── Bước 4b: Deploy + verify Phương án B (Cloudflare Pages, dự phòng) ──
    print("\n④b Deploy — Phương án B (Cloudflare Pages, dự phòng)...")
    cf_ok = deploy_cloudflare()
    cf_links = {w: f"{CF_BASE_URL}kehoach-{w}-{slug}.html" for w in WORKERS}
    if cf_ok:
        cf_status = {w: curl_status(u) for w, u in cf_links.items()}
        for w, u in cf_links.items():
            icon = "✅" if cf_status[w] in ("200", "308") else "❌"
            print(f"   {icon} {w:6}: {cf_status[w]}  {u}")
    else:
        cf_status = {w: "SKIP" for w in WORKERS}

    # ── Bước 5: Bảng tổng kết dán vào _Giao Bang.md ─────────────
    print(f"\n{'═'*60}")
    print("  BẢNG DÁN VÀO _Giao Bang.md MỤC C:")
    print(f"{'═'*60}")
    date_display = datetime.date.fromisoformat(args.ngay_ke_hoach).strftime("%d/%m/%Y")
    for w, u in links.items():
        trang_thai = "✅ Live — sẵn sàng duyệt" if status[w] == "200" else "❌ Chưa live, kiểm tra lại"
        print(f"| {date_display} | {w.capitalize()} | {u} | {trang_thai} |")
    print(f"\n  Phương án B (Cloudflare, dùng khi A lỗi):")
    for w, u in cf_links.items():
        trang_thai = "✅ Live" if cf_status[w] in ("200", "308") else ("⏸ Chưa deploy" if cf_status[w] == "SKIP" else "❌ Lỗi")
        print(f"  | {w.capitalize()} | {u} | {trang_thai} |")
    print(f"{'═'*60}\n")


if __name__ == "__main__":
    main()
