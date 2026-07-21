#!/usr/bin/env python3
"""
du_bao_mien.py — Dự báo NGẮN HẠN lịch đảo trộn Miên cho các ngày sắp tới,
dựa trên plan mới nhất đã đối chiếu actual. CHỈ BÁO CÁO (report-only),
KHÔNG tạo kế hoạch thật — Tim xác nhận 2026-07-20/21, xem chi tiết quy trình
tại 00 Context/Quy Trình Vòng Quay Chượp — Toàn Nhà Máy.md.

Phạm vi: chỉ các bể ĐANG có trong plan hiện tại (không mở rộng ra 220 bể —
đơn giản trước, mở rộng sau nếu cần, theo đúng nguyên tắc Tim chốt 2026-07-21).

Dùng (in ra terminal):
    python3 scripts/du_bao_mien.py --plan plans/mien-21072026.json \\
        --tu-ngay 2026-07-22 --so-ngay 7

Dùng (xuất thêm file HTML để Tim tự mở xem, không cần nhờ Cod):
    python3 scripts/du_bao_mien.py --plan plans/mien-21072026.json \\
        --tu-ngay 2026-07-22 --so-ngay 7 --html du-bao-mien-22072026.html
"""
import argparse, datetime, json, re
from pathlib import Path

try:
    import holidays
except ImportError:
    print("pip install holidays"); raise SystemExit(1)

CYCLE_MAX = {1: 17, 2: 5, 3: 5, 4: 5, 5: 5, 6: 5, 7: 5}
RE_LSX = re.compile(r'^S([1-7])(\d{2})$')


def parse_lsx(lsx):
    m = RE_LSX.match(str(lsx))
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def is_nghi(date, vn_holidays):
    if date.weekday() == 6:
        return "CN"
    if date in vn_holidays:
        return vn_holidays[date][:10]
    return None


def tinh_du_bao(plan_path, tu_ngay, so_ngay):
    """Tính toán thuần tuý — trả về dict dùng chung cho cả in terminal lẫn xuất HTML."""
    plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    tasks = [t for t in plan["tasks"] if parse_lsx(t["lsx"])]

    vn_holidays = holidays.Vietnam(years=sorted({tu_ngay.year, (tu_ngay + datetime.timedelta(days=so_ngay)).year}))
    dates = [tu_ngay + datetime.timedelta(days=i) for i in range(so_ngay)]

    rows = []
    het_ck_count = 0
    for t in tasks:
        ck, ngay0 = parse_lsx(t["lsx"])
        be = t["be_nhan"]
        cells = []
        ngay = ngay0
        da_het = False
        for d in dates:
            nghi = is_nghi(d, vn_holidays)
            if nghi:
                cells.append({"loai": "nghi", "text": nghi})
                continue
            if da_het:
                cells.append({"loai": "trong", "text": "-"})
                continue
            ngay += 1
            if ngay > CYCLE_MAX.get(ck, 5):
                cells.append({"loai": "het_ck", "text": "HẾT CK"})
                da_het = True
                het_ck_count += 1
            else:
                cells.append({"loai": "binh_thuong", "text": f"S{ck}{ngay:02d}"})
        rows.append({"be": be, "cells": cells})

    return {
        "dates": dates,
        "rows": rows,
        "so_be": len(tasks),
        "het_ck_count": het_ck_count,
        "plan_path": str(plan_path),
    }


def in_terminal(kq, so_ngay):
    print("=" * 78)
    print(f"  DỰ BÁO NGẮN HẠN — ĐẢO TRỘN MIÊN — {so_ngay} ngày từ {kq['dates'][0].strftime('%d/%m/%Y')}")
    print(f"  Nguồn: {kq['plan_path']} ({kq['so_be']} bể đang theo dõi)")
    print("  ⚠️  Report-only — KHÔNG tự tạo kế hoạch/task thật")
    print("=" * 78 + "\n")

    col_w = 9
    header = "Bể".ljust(6) + "".join(d.strftime("%d/%m").ljust(col_w) for d in kq["dates"])
    print(header)
    print("-" * len(header))

    for row in kq["rows"]:
        line = row["be"].ljust(6)
        for c in row["cells"]:
            text = f"({c['text']})" if c["loai"] == "nghi" else c["text"]
            line += text.ljust(col_w)
        print(line)

    print("\n" + "=" * 78)
    print(f"  Tổng: {kq['so_be']} bể theo dõi, {kq['het_ck_count']} bể sẽ hết chu kỳ trong {so_ngay} ngày tới")
    print("  'HẾT CK' = bể hết vòng đang đảo trong ngày đó — Miên tự thêm vòng mới qua")
    print("  nút ➕ khi tới lúc thật (~28-38 ngày sau khi bắt đầu vòng hiện tại), KHÔNG")
    print("  đoán trước ngày chính xác. '(CN)'/'(Tết...)' = ngày nghỉ, không đảo trộn.")
    print("=" * 78 + "\n")


def xuat_html(kq, so_ngay, out_path):
    date_headers = "".join(f"<th>{d.strftime('%d/%m')}<br><span class=\"dow\">{['T2','T3','T4','T5','T6','T7','CN'][d.weekday()]}</span></th>" for d in kq["dates"])

    body_rows = ""
    for row in kq["rows"]:
        cells_html = ""
        for c in row["cells"]:
            cls = {"nghi": "c-nghi", "het_ck": "c-hetck", "trong": "c-trong", "binh_thuong": "c-binhthuong"}[c["loai"]]
            cells_html += f'<td class="{cls}">{c["text"]}</td>'
        body_rows += f'<tr><td class="be-col">{row["be"]}</td>{cells_html}</tr>\n'

    html = f"""<!DOCTYPE html>
<html lang="vi"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Dự báo đảo trộn Miên — {kq['dates'][0].strftime('%d/%m/%Y')}</title>
<style>
  * {{ box-sizing: border-box; -webkit-text-size-adjust:100%; }}
  body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
         background:#f1f5f9; color:#0f172a; padding:16px; }}
  .wrap {{ max-width:1100px; margin:0 auto; }}
  header {{ background:#0f172a; color:#fff; border-radius:14px; padding:18px 20px; margin-bottom:14px; }}
  .h-title {{ font-size:19px; font-weight:700; }}
  .h-sub {{ color:#94a3b8; font-size:13px; margin-top:4px; }}
  .note {{ background:#fef3c7; border:1px solid #fcd34d; color:#78350f; border-radius:10px;
          padding:10px 14px; font-size:13px; margin-bottom:14px; line-height:1.5; }}
  .stats {{ display:flex; gap:10px; margin-bottom:16px; flex-wrap:wrap; }}
  .stat {{ flex:1; min-width:90px; background:#fff; border:1px solid #e2e8f0; border-radius:12px;
          padding:12px; text-align:center; }}
  .sv {{ font-size:24px; font-weight:800; color:#2563eb; }}
  .sl {{ font-size:12px; color:#64748b; margin-top:2px; }}
  .table-wrap {{ overflow-x:auto; background:#fff; border:1px solid #e2e8f0; border-radius:14px; }}
  table {{ border-collapse:collapse; width:100%; font-size:12.5px; white-space:nowrap; }}
  th, td {{ padding:8px 10px; text-align:center; border-bottom:1px solid #f1f5f9; }}
  th {{ background:#f8fafc; color:#475569; font-weight:700; position:sticky; top:0; }}
  .dow {{ font-weight:400; color:#94a3b8; font-size:10px; }}
  .be-col {{ font-weight:700; text-align:left; background:#f8fafc; position:sticky; left:0; }}
  .c-binhthuong {{ color:#0f172a; font-weight:600; }}
  .c-nghi {{ color:#94a3b8; font-style:italic; }}
  .c-hetck {{ background:#fee2e2; color:#b91c1c; font-weight:700; }}
  .c-trong {{ color:#cbd5e1; }}
  footer {{ text-align:center; color:#94a3b8; font-size:12px; margin-top:18px; }}
</style>
</head><body>
<div class="wrap">
  <header>
    <div class="h-title">📈 Dự báo đảo trộn Miên — {so_ngay} ngày từ {kq['dates'][0].strftime('%d/%m/%Y')}</div>
    <div class="h-sub">Nhà máy Hương Giang · Nguồn: {kq['plan_path']} · Report-only, không phải kế hoạch thật</div>
  </header>
  <div class="note">
    ⚠️ Đây là <b>dự báo ngắn hạn</b>, KHÔNG phải kế hoạch chính thức — chỉ để xem trước xu hướng.
    Ô đỏ "HẾT CK" = bể hết vòng đang đảo, Miên tự thêm vòng mới qua nút ➕ khi tới lúc thật
    (~28-38 ngày sau). Ô nghiêng xám = Chủ Nhật/ngày lễ, không đảo trộn.
  </div>
  <div class="stats">
    <div class="stat"><div class="sv">{kq['so_be']}</div><div class="sl">Bể đang theo dõi</div></div>
    <div class="stat"><div class="sv">{kq['het_ck_count']}</div><div class="sl">Sẽ hết chu kỳ trong {so_ngay} ngày</div></div>
  </div>
  <div class="table-wrap">
    <table>
      <thead><tr><th>Bể</th>{date_headers}</tr></thead>
      <tbody>
        {body_rows}
      </tbody>
    </table>
  </div>
  <footer>Tạo tự động bởi scripts/du_bao_mien.py — {datetime.date.today().strftime('%d/%m/%Y')}</footer>
</div>
</body></html>"""
    Path(out_path).write_text(html, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True, help="File plan JSON mới nhất, vd plans/mien-21072026.json")
    ap.add_argument("--tu-ngay", required=True, help="Ngày bắt đầu dự báo, YYYY-MM-DD")
    ap.add_argument("--so-ngay", type=int, default=7, help="Số ngày dự báo (mặc định 7)")
    ap.add_argument("--html", default=None, help="Nếu có, xuất thêm file HTML tại đường dẫn này")
    args = ap.parse_args()

    start = datetime.date.fromisoformat(args.tu_ngay)
    kq = tinh_du_bao(args.plan, start, args.so_ngay)
    in_terminal(kq, args.so_ngay)

    if args.html:
        xuat_html(kq, args.so_ngay, args.html)
        print(f"✅ Đã xuất HTML: {args.html}\n")


if __name__ == "__main__":
    main()
