#!/usr/bin/env python3
"""
trang_thai_nha_may.py — Trạng thái & dự báo TOÀN NHÀ MÁY (Miên/Phong/Ha/Hao),
gộp 3 kiểu view khác nhau vì bản chất công việc khác nhau (xem
00 Context/Quy Trình Vòng Quay Chượp — Toàn Nhà Máy.md mục 6):

  1. Miên (đảo trộn S___): DỰ BÁO +N ngày — tái sử dụng tinh_du_bao() từ
     du_bao_mien.py, vì mã có "ngày con" đếm được rõ ràng (+1 mỗi ngày).
  2. Phong/Ha (kéo rút C___, 9 dãy): CHỈ SNAPSHOT vị trí hiện tại — KHÔNG dự
     báo ngày mai, vì 1 lần làm đẩy nước qua nhiều vòng cùng lúc, không theo
     lịch +1 ngày/vòng (đã xác nhận qua dữ liệu thật 20/07: Phong ghi liền
     C610→C510→C410→C310→C210→C110 cùng 1 ngày cho dãy 1).
  3. Hao (xuất TP PT/PP): lịch giao hàng sắp tới, đọc từ
     10 Tài nguyên/Lịch Xuất Thành Phẩm — Nam Ngư.md (dữ liệu đã có sẵn).

Report-only — KHÔNG tạo kế hoạch/task thật. Không mở rộng ra 220 bể, chỉ bể
có hoạt động trong actual gần đây (theo đúng phạm vi Tim chốt 2026-07-21).

Dùng:
    python3 scripts/trang_thai_nha_may.py --ketqua /tmp/ketqua.xlsx \\
        --plan-mien plans/mien-21072026.json --tu-ngay 2026-07-22 \\
        --so-ngay 7 --lich-xuat "../.../Lịch Xuất Thành Phẩm — Nam Ngư.md" \\
        --html trang-thai-nha-may.html
"""
import argparse, datetime, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import pandas as pd
from du_bao_mien import tinh_du_bao

COT_NGUOI = "Người thực hiện1"
COT_NGAY = "Ngày thực hiện"
COT_LSX = "Lệnh sản xuất"
COT_BE = "Bể / xe"

RE_C = re.compile(r'^C([1-9])([0-9])0$')  # C<vong><day>0 — bỏ CX00/CY00/CZ00 (vòng 10-12, hiếm)


def doc_actual(ketqua_path):
    df = pd.read_excel(ketqua_path, sheet_name="KetQua")
    df[COT_NGAY] = pd.to_datetime(df[COT_NGAY], errors="coerce")
    return df


def snapshot_keo_rut(df, worker, hom_nay):
    """Với mỗi dãy (1-9), tìm ngày hoạt động gần nhất + vòng nhỏ nhất (tiến xa
    nhất, gần 'cuối dãy' nhất) trong ngày đó. Trả về list dict theo dãy."""
    rows = df[df[COT_NGUOI] == worker].copy()
    rows = rows[rows[COT_LSX].astype(str).str.match(RE_C)]
    if rows.empty:
        return []

    rows["_vong"] = rows[COT_LSX].astype(str).str.extract(RE_C)[0].astype(int)
    rows["_day"] = rows[COT_LSX].astype(str).str.extract(RE_C)[1].astype(int)

    ket_qua = []
    for day, grp in rows.groupby("_day"):
        latest_date = grp[COT_NGAY].max()
        rows_latest_date = grp[grp[COT_NGAY] == latest_date]
        best = rows_latest_date.loc[rows_latest_date["_vong"].idxmin()]
        so_ngay_truoc = (hom_nay - latest_date.date()).days
        ket_qua.append({
            "day": int(day),
            "vong": int(best["_vong"]),
            "be": best[COT_BE],
            "ngay": latest_date.date(),
            "so_ngay_truoc": so_ngay_truoc,
        })
    ket_qua.sort(key=lambda x: x["day"])
    return ket_qua


def doc_lich_xuat_hao(md_path, tu_ngay, so_ngay):
    """Parse bảng markdown Lịch Xuất Thành Phẩm, lọc trong khoảng ngày."""
    text = Path(md_path).read_text(encoding="utf-8")
    ket_thuc = tu_ngay + datetime.timedelta(days=so_ngay)
    ket_qua = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|") or "Tháng" in line or set(line) <= {"|", "-", " "}:
            continue
        cols = [c.strip() for c in line.strip("|").split("|")]
        if len(cols) < 9:
            continue
        _, ngay_str, item, lo, dam, sl, noi_den, ghi_chu, loai_xe = cols[:9]
        be_nguon = cols[9] if len(cols) > 9 else ""
        m = re.match(r"(\d{2})/(\d{2})/(\d{4})", ngay_str)
        if not m:
            continue
        ngay = datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        if tu_ngay <= ngay < ket_thuc:
            ket_qua.append({
                "ngay": ngay, "item": item, "lo": lo.replace("*", ""),
                "sl": sl, "noi_den": noi_den, "loai_xe": loai_xe,
                "be_nguon": be_nguon.replace("*", ""),
            })
    ket_qua.sort(key=lambda x: x["ngay"])
    return ket_qua


def xuat_html(mien_kq, so_ngay_mien, phong_kq, ha_kq, hao_kq, tu_ngay, so_ngay, out_path):
    def date_headers(dates):
        return "".join(f"<th>{d.strftime('%d/%m')}<br><span class=\"dow\">{['T2','T3','T4','T5','T6','T7','CN'][d.weekday()]}</span></th>" for d in dates)

    mien_rows_html = ""
    for row in mien_kq["rows"]:
        cells = ""
        for c in row["cells"]:
            cls = {"nghi": "c-nghi", "het_ck": "c-hetck", "trong": "c-trong", "binh_thuong": "c-binhthuong"}[c["loai"]]
            cells += f'<td class="{cls}">{c["text"]}</td>'
        mien_rows_html += f'<tr><td class="be-col">{row["be"]}</td>{cells}</tr>\n'

    def keo_rut_table(kq, ten):
        if not kq:
            return f"<p class='empty'>Không có dữ liệu {ten} gần đây.</p>"
        rows = ""
        for r in kq:
            canh_bao = ' class="c-canhbao"' if r["so_ngay_truoc"] > 7 else ""
            rows += (f'<tr><td class="be-col">Dãy {r["day"]}</td>'
                     f'<td{canh_bao}>Vòng {r["vong"]}</td>'
                     f'<td>{r["be"]}</td>'
                     f'<td>{r["ngay"].strftime("%d/%m/%Y")}</td>'
                     f'<td{canh_bao}>{r["so_ngay_truoc"]} ngày trước</td></tr>\n')
        return f"""<div class="table-wrap"><table>
          <thead><tr><th>Dãy</th><th>Vòng hiện tại</th><th>Bể</th><th>Cập nhật gần nhất</th><th>Cách đây</th></tr></thead>
          <tbody>{rows}</tbody></table></div>"""

    def lich_xuat_table(kq):
        if not kq:
            return "<p class='empty'>Không có chuyến giao hàng nào trong khoảng thời gian này.</p>"
        rows = ""
        for r in kq:
            rows += (f'<tr><td>{r["ngay"].strftime("%d/%m/%Y")}</td><td>{r["item"]}</td>'
                     f'<td>{r["lo"]}</td><td>{r["sl"]} lít</td><td>{r["noi_den"]}</td>'
                     f'<td>{r["loai_xe"]}</td><td>{r["be_nguon"]}</td></tr>\n')
        return f"""<div class="table-wrap"><table>
          <thead><tr><th>Ngày</th><th>ITEM</th><th>Lô</th><th>SL</th><th>Nơi đến</th><th>Loại xe</th><th>Bể nguồn</th></tr></thead>
          <tbody>{rows}</tbody></table></div>"""

    html = f"""<!DOCTYPE html>
<html lang="vi"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Trạng thái & Dự báo toàn nhà máy — {tu_ngay.strftime('%d/%m/%Y')}</title>
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
  .section {{ margin-bottom:22px; }}
  .sec-title {{ font-size:16px; font-weight:700; margin-bottom:8px; display:flex; align-items:center; gap:8px; }}
  .sec-sub {{ font-size:12.5px; color:#64748b; margin-bottom:10px; }}
  .table-wrap {{ overflow-x:auto; background:#fff; border:1px solid #e2e8f0; border-radius:14px; }}
  table {{ border-collapse:collapse; width:100%; font-size:12.5px; white-space:nowrap; }}
  th, td {{ padding:8px 10px; text-align:center; border-bottom:1px solid #f1f5f9; }}
  th {{ background:#f8fafc; color:#475569; font-weight:700; }}
  .dow {{ font-weight:400; color:#94a3b8; font-size:10px; }}
  .be-col {{ font-weight:700; text-align:left; background:#f8fafc; }}
  .c-binhthuong {{ color:#0f172a; font-weight:600; }}
  .c-nghi {{ color:#94a3b8; font-style:italic; }}
  .c-hetck {{ background:#fee2e2; color:#b91c1c; font-weight:700; }}
  .c-trong {{ color:#cbd5e1; }}
  .c-canhbao {{ background:#fee2e2; color:#b91c1c; font-weight:700; }}
  .empty {{ text-align:center; color:#64748b; font-size:13px; padding:20px; background:#fff;
           border:1px solid #e2e8f0; border-radius:14px; }}
  footer {{ text-align:center; color:#94a3b8; font-size:12px; margin-top:18px; }}
</style>
</head><body>
<div class="wrap">
  <header>
    <div class="h-title">🏭 Trạng thái &amp; Dự báo toàn nhà máy — từ {tu_ngay.strftime('%d/%m/%Y')}</div>
    <div class="h-sub">Nhà máy Hương Giang · Report-only, không phải kế hoạch thật</div>
  </header>
  <div class="note">
    ⚠️ 3 phần dưới đây KHÁC KIỂU nhau vì bản chất công việc khác nhau: Miên có
    <b>dự báo ngày cụ thể</b> (đảo trộn đếm ngày rõ ràng); Phong/Ha chỉ có
    <b>ảnh chụp vị trí hiện tại</b> (kéo rút không theo lịch ngày cố định);
    Hao là <b>lịch giao hàng đã biết trước</b> (không phải chu kỳ).
  </div>

  <div class="section">
    <div class="sec-title">🌀 Miên — Dự báo đảo trộn ({so_ngay_mien} ngày)</div>
    <div class="sec-sub">{mien_kq['so_be']} bể đang theo dõi · {mien_kq['het_ck_count']} bể sẽ hết chu kỳ trong {so_ngay_mien} ngày tới</div>
    <div class="table-wrap"><table>
      <thead><tr><th>Bể</th>{date_headers(mien_kq['dates'])}</tr></thead>
      <tbody>{mien_rows_html}</tbody></table></div>
  </div>

  <div class="section">
    <div class="sec-title">🔄 Phong — Vị trí hiện tại trong 9 dãy kéo rút</div>
    <div class="sec-sub">Snapshot mới nhất, không dự báo ngày mai · Đỏ = quá 7 ngày không cập nhật</div>
    {keo_rut_table(phong_kq, "Phong")}
  </div>

  <div class="section">
    <div class="sec-title">🔄 Ha — Vị trí hiện tại trong 9 dãy kéo rút</div>
    <div class="sec-sub">Snapshot mới nhất, không dự báo ngày mai · Đỏ = quá 7 ngày không cập nhật</div>
    {keo_rut_table(ha_kq, "Ha")}
  </div>

  <div class="section">
    <div class="sec-title">🚚 Hao — Lịch xuất thành phẩm sắp tới</div>
    <div class="sec-sub">Theo Lịch Xuất Thành Phẩm — Nam Ngư (đã biết trước, không phải dự báo)</div>
    {lich_xuat_table(hao_kq)}
  </div>

  <footer>Tạo tự động bởi scripts/trang_thai_nha_may.py — {datetime.date.today().strftime('%d/%m/%Y')}</footer>
</div>
</body></html>"""
    Path(out_path).write_text(html, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ketqua", required=True)
    ap.add_argument("--plan-mien", required=True)
    ap.add_argument("--lich-xuat", required=True, help="File Lịch Xuất Thành Phẩm — Nam Ngư.md")
    ap.add_argument("--tu-ngay", required=True)
    ap.add_argument("--so-ngay", type=int, default=7)
    ap.add_argument("--html", required=True)
    args = ap.parse_args()

    tu_ngay = datetime.date.fromisoformat(args.tu_ngay)
    hom_nay = datetime.date.today()

    df = doc_actual(args.ketqua)
    mien_kq = tinh_du_bao(args.plan_mien, tu_ngay, args.so_ngay)
    phong_kq = snapshot_keo_rut(df, "Phong", hom_nay)
    ha_kq = snapshot_keo_rut(df, "Ha", hom_nay)
    hao_kq = doc_lich_xuat_hao(args.lich_xuat, tu_ngay, args.so_ngay)

    xuat_html(mien_kq, args.so_ngay, phong_kq, ha_kq, hao_kq, tu_ngay, args.so_ngay, args.html)

    print(f"✅ Đã xuất: {args.html}")
    print(f"   Miên: {mien_kq['so_be']} bể | Phong: {len(phong_kq)} dãy | Ha: {len(ha_kq)} dãy | Hao: {len(hao_kq)} chuyến")


if __name__ == "__main__":
    main()
