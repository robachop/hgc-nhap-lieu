#!/usr/bin/env python3
"""
tao_ke_hoach.py — Tạo kế hoạch tự động từ Excel và deploy lên PWA.

Usage:
    python3 tao_ke_hoach.py [file_excel.xlsx] [YYYY-MM-DD]

    Nếu không truyền file  → tìm file mới nhất trong ~/Downloads
    Nếu không truyền ngày  → ngày làm việc tiếp theo (bỏ qua CN)

Phân công 4 người:
    - Phong : C___          (bơm nước long / kéo rút)     ← sheet "Dãy kéo rút"
    - Ha    : Px___ + PM00  (phá xác + pha muối)          ← sheet "Dãy kéo rút"
    - Mien  : S[1-7]__      (đảo trộn) — suy ra +1 ngày   ← sheet "S500"
    - Hao   : (khung trống thành phẩm — tự nhập tại chỗ)

Cách đọc sheet "Dãy kéo rút" (Phong + Ha):
    - Row 0: header (col1=Bể cấp, col2=Bể Nhận, col3=LSX)
    - Rows 1+: data — đọc cols 1,2,3 cho đến hết dữ liệu
    - be_cap: BM00 hoặc Xxxx → "" (để trống, tự điền); Txxx → dùng nguyên

Cách suy ra đảo trộn cho Miên (sheet "S500"):
    - Lấy các bể Miên đang đảo trộn (S[cycle][day]) trong `LOOKBACK` ngày gần nhất
    - Với mỗi bể: lấy bản ghi mới nhất, cộng thêm số ngày tới ngày kế hoạch
    - Chu kỳ 1 tối đa 15 ngày (biến động), chu kỳ 2–7 tối đa 5 ngày
    - Bể vượt quá max chu kỳ → coi như đã hết chu kỳ → KHÔNG tự tạo (Miên tự thêm)
"""

import sys, json, datetime, subprocess, re
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    print("pip install pandas openpyxl"); sys.exit(1)

# ── Config ────────────────────────────────────────────────────
REPO_DIR = Path(__file__).parent.parent   # /tmp/hgc-nhap-lieu
BASE_URL  = "https://robachop.github.io/hgc-nhap-lieu/"
WORKERS   = ['Phong', 'Ha', 'Mien', 'Hao']          # thứ tự sinh trang
CYCLE_MAX = {1: 15, 2: 5, 3: 5, 4: 5, 5: 5, 6: 5, 7: 5}  # số ngày tối đa mỗi chu kỳ đảo trộn
LOOKBACK  = 6                                        # cửa sổ ngày tìm bể đang đảo trộn

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
        return f"C-Nước long {int(lsx[1])} dãy {int(lsx[2])}"
    if lsx.startswith("Px") and len(lsx) == 4:
        return f"Thành phẩm dãy {int(lsx[2])}"
    if re.match(r'^S[1-7]\d\d$', lsx):
        return f"S-Đảo trộn {int(lsx[1])} ngày {int(lsx[2:])}"
    return lsx

def group(lsx):
    if lsx == "PM00":               return "PM_pha_muoi"
    if lsx.startswith("Px"):        return "PX_rut_kiet"
    if lsx.startswith("C"):         return "C_keo_rut"
    if re.match(r'^S[1-7]\d\d$', lsx): return "S_dao_tron"
    return "other"

def dvt(lsx):
    return "lít"

# Phân công theo LSX trong sheet "Dãy kéo rút"
#   C___  → Phong ; Px___ + PM00 → Ha
def nguoi(lsx):
    if lsx.startswith('C'):  return 'Phong'
    return 'Ha'

# ── Đọc sheet "Dãy kéo rút" → Phong + Ha ─────────────────────
def read_day_keo_rut(excel_path):
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

# ── Kiểm tồn thành phẩm (PT00) ───────────────────────────────
def append_pt00(by_worker, worker, be_cap=''):
    """Thêm 1 lệnh PT00 (P-Thành phẩm tồn) vào cuối danh sách của 1 người.
    Tim chốt 2026-07-02: suy luận tồn = nhập - xuất không an toàn (đã kiểm
    chứng bằng dữ liệu S500 thật, lệch hàng nghìn lít) -> luôn kèm 1 lệnh
    kiểm tồn thật (PT00) cho Ha (sau khi đấu) và Hao (trước khi xuất)."""
    tasks = by_worker.setdefault(worker, [])
    n = len(tasks) + 1
    mo_ta = f'P-Thành phẩm tồn — kiểm tra bể {be_cap}' if be_cap \
        else 'P-Thành phẩm tồn — kiểm tra lượng tồn thật tại bể đang làm'
    tasks.append({
        "id":       f"t{n}",
        "nguoi":    worker,
        "lsx":      "PT00",
        "mo_ta":    mo_ta,
        "be_cap":   be_cap,
        "be_nhan":  "",
        "luong_dk": 0,
        "dvt":      "lít",
        "cong":     5,
        "group":    "P_xuat_tp"
    })
    return by_worker

# ── Suy ra đảo trộn cho Miên từ sheet "S500" ─────────────────
def read_dao_tron(excel_path, target_date):
    """
    Suy ra kế hoạch đảo trộn cho Miên: lấy bể đang đảo dở → cộng +1 ngày
    cho tới ngày kế hoạch. Bể vượt max chu kỳ → bỏ (Miên tự thêm qua nút ➕).
    An toàn: mọi lỗi đọc S500 → trả [] (không làm hỏng Phong/Ha).
    """
    try:
        df = pd.read_excel(excel_path, sheet_name="S500", header=0)
        df['ngay'] = pd.to_datetime(df['Ngày thực hiện'], errors='coerce')
        df['lsx']  = df['Lệnh sản xuất'].astype(str).str.strip()
        last = df['ngay'].max()

        m = df[(df['Người thực hiện1'] == 'Mien')
               & (df['lsx'].str.match(r'^S[1-7]\d\d$'))
               & (df['ngay'] >= last - pd.Timedelta(days=LOOKBACK))].copy()
        if m.empty:
            print("  ⚠️  Không tìm thấy bể đảo trộn nào của Miên trong S500 gần đây")
            return []

        m['cycle'] = m['lsx'].str[1].astype(int)
        m['day']   = m['lsx'].str[2:].astype(int)
        m = m.sort_values('ngay')
        latest = m.groupby('Bể / xe').tail(1)

        tdt   = pd.Timestamp(target_date)
        tasks = []
        n = 0
        skipped = 0
        for _, x in latest.sort_values(['cycle', 'Bể / xe']).iterrows():
            delta  = (tdt - x['ngay']).days
            newday = int(x['day']) + delta
            cyc    = int(x['cycle'])
            if delta <= 0 or newday > CYCLE_MAX[cyc]:
                skipped += 1
                continue
            n += 1
            lsx = f"S{cyc}{newday:02d}"
            tasks.append({
                "id":       f"t{n}",
                "nguoi":    "Mien",
                "lsx":      lsx,
                "mo_ta":    mo_ta(lsx),
                "be_cap":   "",
                "be_nhan":  str(x['Bể / xe']).strip(),
                "luong_dk": 0,
                "dvt":      "lít",
                "cong":     5,
                "group":    "S_dao_tron"
            })
        print(f"  📅 S500 ngày cuối: {last.strftime('%d/%m/%Y')} | đảo trộn: {n} bể (bỏ {skipped} bể hết chu kỳ)")
        return tasks
    except Exception as e:
        print(f"  ⚠️  Lỗi đọc đảo trộn Miên: {e}")
        return []

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

def deploy(target_date, by_worker, do_push=True):
    date_str = target_date.strftime("%d/%m/%Y")

    files_to_add = []
    links = {}
    # Sinh trang cho TẤT CẢ người trong WORKERS (kể cả 0 task → khung trống)
    for worker in WORKERS:
        tasks = by_worker.get(worker, [])
        plan_file, html_file, url = deploy_worker(target_date, worker, tasks)
        files_to_add += [f"plans/{plan_file}", html_file]
        links[worker] = BASE_URL + html_file
        tag = f"{len(tasks)} tasks" if tasks else "khung trống"
        print(f"  ✅ {worker}: {tag} → {html_file}")

    if not do_push:
        print("  ⏸  (Chưa push — chế độ tạo local)")
        return links

    msg     = f"Ke hoach {date_str}: " + ", ".join(f"{w}={len(by_worker.get(w, []))}" for w in WORKERS)
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

    print(f"📊 Đọc sheet 'Dãy kéo rút' (Phong + Ha)...")
    by_worker = read_day_keo_rut(excel_path)

    # Luôn kèm 1 lệnh kiểm tồn thật (PT00) cho Ha — xem append_pt00() ở trên
    append_pt00(by_worker, 'Ha')

    # ⚠️ ĐÃ TẮT 2026-07-02: Miên không dùng logic suy luận từ S500 nữa (read_dao_tron()),
    # giờ dùng script riêng scripts/gen_mien_tuan.py đọc sheet "Tuần XX" (Miên viết tay).
    # Không được bật lại dòng dưới — sẽ ghi đè nhầm lên kế hoạch Miên đang dùng đúng.
    # by_worker['Mien'] = read_dao_tron(excel_path, target)
    by_worker['Mien'] = []   # không tự tạo — dùng gen_mien_tuan.py riêng cho Miên

    by_worker['Hao'] = []   # khung trống thành phẩm — Hao tự nhập

    from collections import Counter
    for w in WORKERS:
        tasks = by_worker.get(w, [])
        grp = Counter(t['group'] for t in tasks)
        detail = ', '.join(f"{g}:{n}" for g, n in grp.most_common()) or "khung trống"
        print(f"  → {w}: {len(tasks)} tasks ({detail})")

    print(f"\n🚀 Deploy lên GitHub Pages...")
    links = deploy(target, by_worker)

    print(f"\n{'═'*54}")
    print(f"  ✅ XONG! Gửi link qua Zalo:")
    for w in WORKERS:
        print(f"  {w:8}: {links.get(w, '—')}")
    print(f"{'═'*54}\n")

if __name__ == '__main__':
    main()
