#!/usr/bin/env python3
"""
tao_ke_hoach.py — Tạo kế hoạch tự động từ Excel và deploy lên PWA.

Usage:
    python3 tao_ke_hoach.py [file_excel.xlsx] [YYYY-MM-DD]

    Nếu không truyền file  → tìm file mới nhất trong ~/Downloads
    Nếu không truyền ngày  → ngày làm việc tiếp theo (bỏ qua CN)

Cách đọc sheet "Dãy kéo rút" (Phong):
    - Row 0: header (col1=Bể cấp, col2=Bể Nhận, col3=LSX)
    - Rows 1+: data — đọc cols 1,2,3 cho đến hết dữ liệu
    - be_cap: BM00 hoặc Xxxx → "" (để trống, Phong tự điền)
    - be_cap: Txxx → dùng nguyên
"""

import sys, json, datetime, subprocess
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    print("pip install pandas openpyxl"); sys.exit(1)

# ── Config ────────────────────────────────────────────────────
REPO_DIR = Path(__file__).parent.parent   # /tmp/hgc-nhap-lieu
BASE_URL  = "https://robachop.github.io/hgc-nhap-lieu/"

# ── Helpers ───────────────────────────────────────────────────
def next_workday(ref=None):
    if ref is None: ref = datetime.date.today()
    d = ref + datetime.timedelta(days=1)
    while d.weekday() == 6:   # bỏ CN
        d += datetime.timedelta(days=1)
    return d

def mo_ta(lsx):
    if lsx == "PM00": return "P-Pha muối"
    if lsx.startswith("C") and len(lsx) == 4 and lsx[1:].isdigit():
        lan = int(lsx[1])
        day = int(lsx[2])
        return f"C-Nước long {lan} dãy {day}"
    if lsx.startswith("Px") and len(lsx) == 4:
        day = int(lsx[2])
        return f"Phá xác dãy {day}"
    return lsx

def group(lsx):
    if lsx == "PM00":           return "PM_pha_muoi"
    if lsx.startswith("C"):     return "C_keo_rut"
    if lsx.startswith("Px"):    return "PX_rut_kiet"
    return "other"

def dvt(lsx):
    return "kg" if lsx.startswith("Px") else "lít"

# Phân công theo LSX
# C___  → Phong
# Px___ + PM00 → Ha
def nguoi(lsx):
    if lsx.startswith('C'):  return 'Phong'
    return 'Ha'

# ── Đọc sheet "Dãy kéo rút" ──────────────────────────────────
def read_day_keo_rut(excel_path):
    """
    Đọc sheet 'Dãy kéo rút', tách task theo người:
      - Cxxx  → Phong
      - Pxxx + PM00 → Ha
    Trả về dict: {'Phong': [...], 'Ha': [...]}
    """
    df = pd.read_excel(excel_path, sheet_name="Dãy kéo rút", header=None)

    plan_date_raw = df.iloc[0, 0]
    plan_date = plan_date_raw.strftime('%d/%m/%Y') if hasattr(plan_date_raw, 'strftime') else str(plan_date_raw)
    print(f"  📅 Ngày ghi trong sheet Dãy kéo rút: {plan_date}")

    by_worker = {'Phong': [], 'Ha': []}
    counters  = {'Phong': 0, 'Ha': 0}

    for i in range(1, len(df)):
        be_cap_raw = str(df.iloc[i, 1]) if pd.notna(df.iloc[i, 1]) else ''
        be_nhan    = str(df.iloc[i, 2]).strip() if pd.notna(df.iloc[i, 2]) else ''
        lsx        = str(df.iloc[i, 3]).strip() if pd.notna(df.iloc[i, 3]) else ''

        if not lsx or lsx == 'nan':
            continue

        be_cap = '' if be_cap_raw.strip() in ('BM00', 'Xxxx', 'nan', '') else be_cap_raw.strip()
        w      = nguoi(lsx)
        counters[w] += 1

        by_worker[w].append({
            "id":       f"t{counters[w]}",
            "nguoi":    w,
            "lsx":      lsx,
            "mo_ta":    mo_ta(lsx),
            "be_cap":   be_cap,
            "be_nhan":  be_nhan,
            "luong_dk": 0,
            "dvt":      dvt(lsx),
            "cong":     5,
            "group":    group(lsx)
        })

    return by_worker

# ── Deploy ────────────────────────────────────────────────────
def deploy_worker(target_date, worker, tasks):
    """Tạo plan JSON + redirect HTML cho 1 người, trả về link."""
    slug     = target_date.strftime("%d%m%Y")
    date_str = target_date.strftime("%d/%m/%Y")
    w_lower  = worker.lower()

    plan      = {"date": target_date.isoformat(), "tasks": tasks}
    plan_file = f"{w_lower}-{slug}.json"
    plan_path = REPO_DIR / "plans" / plan_file
    plan_path.parent.mkdir(exist_ok=True)
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')

    app_url   = f"{BASE_URL}?plan_file={w_lower}-{slug}&w={worker}"
    html_file = f"kehoach-{w_lower}-{slug}.html"
    html_path = REPO_DIR / html_file
    html = f"""<!DOCTYPE html>
<html lang="vi"><head><meta charset="UTF-8">
<meta http-equiv="refresh" content="0;url={app_url}">
<title>HGC Kế Hoạch {worker} — {date_str}</title>
</head><body>
<p>Đang chuyển hướng... <a href="{app_url}">Bấm đây nếu không tự chuyển</a></p>
<script>window.location.replace("{app_url}");</script>
</body></html>"""
    html_path.write_text(html, encoding='utf-8')
    return plan_file, html_file, app_url

def deploy(target_date, by_worker):
    date_str = target_date.strftime("%d/%m/%Y")
    slug     = target_date.strftime("%d%m%Y")

    files_to_add = []
    links = {}
    for worker, tasks in by_worker.items():
        if not tasks:
            continue
        plan_file, html_file, url = deploy_worker(target_date, worker, tasks)
        files_to_add += [f"plans/{plan_file}", html_file]
        links[worker] = BASE_URL + html_file
        print(f"  ✅ {worker}: {len(tasks)} tasks → {html_file}")

    msg    = f"Ke hoach {date_str}: " + ", ".join(f"{w}={len(t)}" for w,t in by_worker.items() if t)
    add_cmd = " ".join(files_to_add)
    result = subprocess.run(
        f'cd "{REPO_DIR}" && git add {add_cmd} && git commit -m "{msg}" && git push origin main',
        shell=True, capture_output=True, text=True
    )
    if result.returncode == 0:
        print(f"  ✅ Đã push lên GitHub Pages")
    else:
        print(f"  ⚠️  Git: {result.stdout.strip()} {result.stderr.strip()}")

    return links

# ── Main ──────────────────────────────────────────────────────
def main():
    # File Excel
    if len(sys.argv) >= 2:
        excel_path = Path(sys.argv[1])
    else:
        downloads  = Path.home() / 'Downloads'
        candidates = sorted(downloads.glob('*Phân công*.xlsx'),
                            key=lambda p: p.stat().st_mtime, reverse=True)
        if not candidates:
            print("❌ Không tìm thấy file Excel. Truyền đường dẫn:")
            print("   python3 tao_ke_hoach.py <file.xlsx> [YYYY-MM-DD]")
            sys.exit(1)
        excel_path = candidates[0]
        print(f"📂 Dùng file mới nhất: {excel_path.name}")

    # Ngày kế hoạch
    if len(sys.argv) >= 3:
        target = datetime.date.fromisoformat(sys.argv[2])
    else:
        target = next_workday()

    day_vn = ['Thứ 2','Thứ 3','Thứ 4','Thứ 5','Thứ 6','Thứ 7','CN'][target.weekday()]
    print(f"\n📅 Lên kế hoạch cho: {day_vn} {target.strftime('%d/%m/%Y')}")
    print(f"📊 Đọc sheet 'Dãy kéo rút'...")

    by_worker = read_day_keo_rut(excel_path)

    from collections import Counter
    for w, tasks in by_worker.items():
        grp = Counter(t['group'] for t in tasks)
        detail = ', '.join(f"{g}:{n}" for g,n in grp.most_common())
        print(f"  → {w}: {len(tasks)} tasks ({detail})")

    print(f"\n🚀 Deploy lên GitHub Pages...")
    links = deploy(target, by_worker)

    print(f"\n{'═'*50}")
    print(f"  ✅ XONG! Gửi link qua Zalo:")
    for w, link in links.items():
        print(f"  {w:8}: {link}")
    print(f"{'═'*50}\n")

if __name__ == '__main__':
    main()
