#!/usr/bin/env python3
"""
trang_thai_nha_may.py — Trạng thái & dự báo TOÀN NHÀ MÁY, tổ chức theo
NHÓM CÔNG VIỆC (Mô tả 1 trong sheet "LSX Mẫu"), KHÔNG theo người cố định.

Quyết định 2026-07-21 (Tim chỉ đạo): kế hoạch/báo cáo nên phân theo nhóm công
việc trước — người chỉ là gán TẠM, không cố định 100%, có thể đổi để cân đối
tải hoặc hỗ trợ nhau (đã thấy thật: nhóm "P-Thành phẩm" cả Ha lẫn Hao cùng
làm; nhóm "P-Phá xác" chủ yếu Ha nhưng Phong cũng có làm). Vì vậy mỗi nhóm
tính "người phụ trách" ĐỘNG từ dữ liệu thật gần đây, không hardcode theo tên.

3 kiểu hiển thị theo bản chất từng nhóm (xem 00 Context/Quy Trình Vòng Quay
Chượp — Toàn Nhà Máy.md mục 6):
  1. Đảo trộn (S1xx-S7xx, theo vòng): DỰ BÁO +N ngày theo bể — có "ngày con"
     đếm được rõ ràng.
  2. Nhóm theo dãy (Nước long C1xx-C9xx, Đấu thành phẩm P1xx-P6xx): SNAPSHOT
     vị trí/hoạt động gần nhất mỗi dãy — không dự báo ngày mai (không tuần tự).
  3. Nhóm khác (Bể trống, Nước bổi, Phá xác...): chỉ đếm hoạt động gần đây +
     người đang làm, không có cấu trúc dãy/vòng để snapshot chi tiết hơn.

Report-only — KHÔNG tạo kế hoạch/task thật. Không mở rộng ra 220 bể, chỉ bể
có hoạt động trong actual gần đây.

Dùng:
    python3 scripts/trang_thai_nha_may.py --ketqua /tmp/ketqua.xlsx \\
        --plan-mien plans/mien-21072026.json --tu-ngay 2026-07-22 \\
        --so-ngay 7 --lich-xuat "../.../Lịch Xuất Thành Phẩm — Nam Ngư.md" \\
        --html trang-thai-nha-may.html
"""
import argparse, datetime, re, sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import pandas as pd
from du_bao_mien import tinh_du_bao

COT_NGUOI = "Người thực hiện1"
COT_NGAY = "Ngày thực hiện"
COT_LSX = "Lệnh sản xuất"
COT_BE = "Bể / xe"


def phan_loai_mo_ta1(lsx):
    """Map LSX -> nhóm công việc (Mô tả 1, theo đúng sheet LSX Mẫu chuẩn)."""
    lsx = str(lsx)
    if lsx == "S000": return "S-Khác"
    if lsx in ("S010", "S020"): return "S-Bể trống"
    if lsx in ("S030", "S031", "S032"): return "S-Nhập cá"
    if lsx == "S040": return "S-Phân bổ cá"
    if re.match(r'^SM0[1-6]$', lsx): return "S-Bổ sung muối"
    if lsx == "S050": return "S-Rút kiệt gài nén"
    if lsx == "S090": return "S-Gài nén"
    if re.match(r'^B\d{3}$', lsx): return "S-Nước bổi"
    m = re.match(r'^S([1-7])\d{2}$', lsx)
    if m: return f"S-Đảo trộn {m.group(1)}"
    if lsx in ("S800", "S900"): return "S-Trống"
    if lsx == "C000": return "C-Cá chín"
    if re.match(r'^C0[1-4]0$', lsx): return "C-Rút kiệt đảo trong"
    if lsx == "C090": return "C-Tách cốt"
    if re.match(r'^N\d{3}$', lsx): return "P-Đấu thành phẩm (cốt nhỉ)"
    m = re.match(r'^C([1-9])\d0$', lsx)
    if m: return f"C-Nước long {m.group(1)}"
    if lsx == "CX00": return "C-Nước long 10"
    if lsx == "CY00": return "C-Nước long 11"
    if lsx == "CZ00": return "C-Nước long 12"
    if lsx in ("PM00", "MP00", "MP01", "PX00"): return "P-Phá xác"
    if re.match(r'^P\d{3}$', lsx) or re.match(r'^PT\d{2}$', lsx) or re.match(r'^PP\d{2}$', lsx):
        return "P-Thành phẩm"
    return None  # mã tạm/khác (Px1, Px2...) — bỏ qua trong thống kê nhóm


RE_C_KEO_RUT = re.compile(r'^C([1-9])([0-9])0$')
RE_P_DAU = re.compile(r'^P([1-6])([0-9])0$')
BE_TP = {1: "L113", 2: "L114", 3: "L133", 4: "L134", 5: "L138", 6: "L213"}


def doc_actual(ketqua_path):
    df = pd.read_excel(ketqua_path, sheet_name="KetQua")
    df[COT_NGAY] = pd.to_datetime(df[COT_NGAY], errors="coerce")
    return df


def nguoi_phu_trach(df, mask, top_n=3):
    """Đếm người nào thực hiện các dòng khớp mask, sắp theo tần suất — dùng để
    hiển thị 'người đang phụ trách' ĐỘNG thay vì giả định cố định."""
    c = Counter(df.loc[mask, COT_NGUOI].dropna())
    return c.most_common(top_n)


def snapshot_theo_day(df, re_pattern, hom_nay, nhom_idx=1, vi_tri_idx=0, dao_nguoc=False):
    """Snapshot chung cho nhóm có cấu trúc '9 dãy' (Nước long, Đấu thành phẩm)
    — KHÔNG lọc theo người, quét TẤT CẢ ai đã làm. Với mỗi dãy, lấy ngày mới
    nhất, rồi lấy dòng có vị trí 'tiến xa nhất' (min nếu dao_nguoc=False) làm
    đại diện, kèm TÊN NGƯỜI đã làm dòng đó (động, không giả định)."""
    rows = df[df[COT_LSX].astype(str).str.match(re_pattern)].copy()
    if rows.empty:
        return []
    ext = rows[COT_LSX].astype(str).str.extract(re_pattern)
    rows["_vt"] = ext[vi_tri_idx].astype(int)
    rows["_day"] = ext[nhom_idx].astype(int)
    rows = rows[rows["_day"] != 0]

    ket_qua = []
    for day, grp in rows.groupby("_day"):
        latest_date = grp[COT_NGAY].max()
        rows_latest = grp[grp[COT_NGAY] == latest_date]
        best = rows_latest.loc[rows_latest["_vt"].idxmax() if dao_nguoc else rows_latest["_vt"].idxmin()]
        ket_qua.append({
            "day": int(day),
            "vi_tri": int(best["_vt"]),
            "be": best[COT_BE],
            "nguoi": best[COT_NGUOI],
            "ngay": latest_date.date(),
            "so_ngay_truoc": (hom_nay - latest_date.date()).days,
        })
    ket_qua.sort(key=lambda x: x["day"])
    return ket_qua


def snapshot_ca_day(df, hom_nay):
    """Gộp Kéo rút (C910...C110) + Đấu thành phẩm (P1y0...P6y0) thành 1 chuỗi
    liên tục theo dãy (Tim chỉnh 2026-07-21: 'Cx10 là dãy 1 cho tới Px10 là
    thành phẩm' — cùng 1 dãy, không phải 2 việc tách rời). Vị trí dùng để so
    sánh 'tiến xa nhất': vòng kéo rút 9→1 (số nhỏ = tiến xa hơn), rồi P
    (đấu xong) tiến xa hơn mọi vòng C → gán vị trí 0 để luôn thắng khi so sánh
    cùng ngày."""
    c_rows = df[df[COT_LSX].astype(str).str.match(RE_C_KEO_RUT)].copy()
    if not c_rows.empty:
        ext = c_rows[COT_LSX].astype(str).str.extract(RE_C_KEO_RUT)
        c_rows["_day"] = ext[1].astype(int)
        c_rows["_vt"] = ext[0].astype(int)
        c_rows["_giai_doan"] = "keo_rut"

    p_rows = df[df[COT_LSX].astype(str).str.match(RE_P_DAU)].copy()
    if not p_rows.empty:
        ext = p_rows[COT_LSX].astype(str).str.extract(RE_P_DAU)
        p_rows["_day"] = ext[1].astype(int)
        p_rows["_be_tp_idx"] = ext[0].astype(int)
        p_rows["_vt"] = 0  # đấu xong luôn "tiến xa" hơn mọi vòng kéo rút (1-9)
        p_rows["_giai_doan"] = "dau_tp"

    frames = [x for x in (c_rows, p_rows) if not x.empty]
    if not frames:
        return []
    rows = pd.concat(frames, ignore_index=True)
    rows = rows[rows["_day"] != 0]

    ket_qua = []
    for day, grp in rows.groupby("_day"):
        latest_date = grp[COT_NGAY].max()
        rows_latest = grp[grp[COT_NGAY] == latest_date]
        best = rows_latest.loc[rows_latest["_vt"].idxmin()]
        if best["_giai_doan"] == "dau_tp":
            trang_thai = f"Đã đấu → {BE_TP.get(int(best['_be_tp_idx']), '?')}"
        else:
            trang_thai = f"Kéo rút, vòng {int(best['_vt'])}"
        ket_qua.append({
            "day": int(day),
            "trang_thai": trang_thai,
            "be": best[COT_BE],
            "nguoi": best[COT_NGUOI],
            "ngay": latest_date.date(),
            "so_ngay_truoc": (hom_nay - latest_date.date()).days,
        })
    ket_qua.sort(key=lambda x: x["day"])
    return ket_qua


def doc_lich_xuat_hao(md_path, tu_ngay, so_ngay):
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


def nguoi_str(nguoi_list):
    if not nguoi_list:
        return "—"
    return ", ".join(f"{n} ({c})" for n, c in nguoi_list)


def xuat_html(mien_kq, so_ngay_mien, nguoi_dao_tron, chuoi_day_kq, nguoi_chuoi_day,
              phaxac_nguoi, hao_kq, tu_ngay, so_ngay, out_path):

    def date_headers(dates):
        return "".join(f"<th>{d.strftime('%d/%m')}<br><span class=\"dow\">{['T2','T3','T4','T5','T6','T7','CN'][d.weekday()]}</span></th>" for d in dates)

    mien_rows_html = ""
    for row in mien_kq["rows"]:
        cells = ""
        for c in row["cells"]:
            cls = {"nghi": "c-nghi", "het_ck": "c-hetck", "trong": "c-trong", "binh_thuong": "c-binhthuong"}[c["loai"]]
            cells += f'<td class="{cls}">{c["text"]}</td>'
        mien_rows_html += f'<tr><td class="be-col">{row["be"]}</td>{cells}</tr>\n'

    def chuoi_day_table(kq):
        if not kq:
            return "<p class='empty'>Không có dữ liệu gần đây.</p>"
        rows = ""
        for r in kq:
            canh_bao = ' class="c-canhbao"' if r["so_ngay_truoc"] > 7 else ""
            rows += (f'<tr><td class="be-col">Dãy {r["day"]}</td>'
                     f'<td{canh_bao}>{r["trang_thai"]}</td>'
                     f'<td>{r["be"]}</td><td>{r["nguoi"]}</td>'
                     f'<td>{r["ngay"].strftime("%d/%m/%Y")}</td>'
                     f'<td{canh_bao}>{r["so_ngay_truoc"]} ngày trước</td></tr>\n')
        return f"""<div class="table-wrap"><table>
          <thead><tr><th>Dãy</th><th>Trạng thái hiện tại</th><th>Bể</th><th>Người làm gần nhất</th><th>Cập nhật</th><th>Cách đây</th></tr></thead>
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

    # Dãy kéo rút → thành phẩm: 1 chuỗi liên tục (Tim 2026-07-21: "Cx10 là dãy 1
    # cho tới Px10 là thành phẩm") — gộp kéo rút (C) + đấu TP (P) làm 1 bảng,
    # mỗi dãy 1 dòng, không tách theo loại nước long hay tách riêng đấu TP.
    chuoi_day_html = f"""
  <div class="section">
    <div class="sec-title">💧 Dãy kéo rút → thành phẩm — 9 dãy</div>
    <div class="sec-sub">Đang làm: {nguoi_str(nguoi_chuoi_day)} · Mỗi dãy 1 chuỗi liên tục: kéo rút (vòng 9→1) rồi đấu vào bể TP · Snapshot mới nhất, không dự báo ngày mai</div>
    {chuoi_day_table(chuoi_day_kq)}
  </div>"""

    html = f"""<!DOCTYPE html>
<html lang="vi"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Trạng thái theo nhóm công việc — {tu_ngay.strftime('%d/%m/%Y')}</title>
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
    <div class="h-title">🏭 Trạng thái theo nhóm công việc — từ {tu_ngay.strftime('%d/%m/%Y')}</div>
    <div class="h-sub">Nhà máy Hương Giang · Report-only, không phải kế hoạch thật</div>
  </header>
  <div class="note">
    ⚠️ Tổ chức theo <b>NHÓM CÔNG VIỆC</b> (theo LSX Mẫu), không theo người cố định —
    "Người đang làm" tính động từ dữ liệu thật gần đây, có thể đổi ngày này qua ngày khác
    để cân đối tải hoặc hỗ trợ nhau (vd nhóm Thành phẩm hiện có cả Ha lẫn Hao cùng làm).
  </div>

  <div class="section">
    <div class="sec-title">🌀 Đảo trộn — Dự báo {so_ngay_mien} ngày</div>
    <div class="sec-sub">Đang làm: {nguoi_str(nguoi_dao_tron)} · {mien_kq['so_be']} bể theo dõi · {mien_kq['het_ck_count']} bể sẽ hết chu kỳ</div>
    <div class="table-wrap"><table>
      <thead><tr><th>Bể</th>{date_headers(mien_kq['dates'])}</tr></thead>
      <tbody>{mien_rows_html}</tbody></table></div>
  </div>
{chuoi_day_html}

  <div class="section">
    <div class="sec-title">🧹 Phá xác / Pha muối</div>
    <div class="sec-sub">Đang làm: {nguoi_str(phaxac_nguoi)} · Không có cấu trúc dãy để snapshot chi tiết hơn</div>
  </div>

  <div class="section">
    <div class="sec-title">🚚 Xuất/Tồn thành phẩm — Lịch giao hàng sắp tới</div>
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
    ap.add_argument("--lich-xuat", required=True)
    ap.add_argument("--tu-ngay", required=True)
    ap.add_argument("--so-ngay", type=int, default=7)
    ap.add_argument("--html", required=True)
    args = ap.parse_args()

    tu_ngay = datetime.date.fromisoformat(args.tu_ngay)
    hom_nay = datetime.date.today()

    df = doc_actual(args.ketqua)
    mien_kq = tinh_du_bao(args.plan_mien, tu_ngay, args.so_ngay)

    mask_dao_tron = df[COT_LSX].astype(str).str.match(r'^S[1-7]\d{2}$')
    nguoi_dao_tron = nguoi_phu_trach(df, mask_dao_tron)

    # Dãy kéo rút → thành phẩm: 1 bảng DUY NHẤT, mỗi dãy 1 dòng, gộp cả kéo
    # rút (C) lẫn đấu TP (P) — cùng 1 chuỗi liên tục theo dãy (Tim 2026-07-21:
    # "Cx10 là dãy 1 cho tới Px10 là thành phẩm"), KHÔNG tách theo loại nước
    # long hay tách riêng đấu TP như 2 bản trước.
    chuoi_day_kq = snapshot_ca_day(df, hom_nay)
    mask_chuoi_day = df[COT_LSX].astype(str).str.match(RE_C_KEO_RUT) | df[COT_LSX].astype(str).str.match(RE_P_DAU)
    nguoi_chuoi_day = nguoi_phu_trach(df, mask_chuoi_day)

    mask_phaxac = df[COT_LSX].astype(str).isin(["PM00", "MP00", "MP01", "PX00"])
    phaxac_nguoi = nguoi_phu_trach(df, mask_phaxac)

    hao_kq = doc_lich_xuat_hao(args.lich_xuat, tu_ngay, args.so_ngay)

    xuat_html(mien_kq, args.so_ngay, nguoi_dao_tron, chuoi_day_kq, nguoi_chuoi_day,
              phaxac_nguoi, hao_kq, tu_ngay, args.so_ngay, args.html)

    print(f"✅ Đã xuất: {args.html}")
    print(f"   Đảo trộn: {mien_kq['so_be']} bể ({nguoi_str(nguoi_dao_tron)})")
    print(f"   Dãy kéo rút→thành phẩm: {len(chuoi_day_kq)} dãy ({nguoi_str(nguoi_chuoi_day)})")
    print(f"   Phá xác: ({nguoi_str(phaxac_nguoi)})")
    print(f"   Xuất TP sắp tới: {len(hao_kq)} chuyến")


if __name__ == "__main__":
    main()
