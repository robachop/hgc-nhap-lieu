#!/usr/bin/env python3
"""
lich_gop.py — Bảng GỘP: đã thực hiện (trái) + hôm nay (giữa) + kế hoạch sắp
tới (phải), 1 bảng duy nhất theo nhóm công việc. Tim chốt 2026-07-21: Tim và
Cod sẽ xem bảng này HÀNG NGÀY trước khi ra WO (work order) cho nhân viên —
đây là bước bắt buộc trong quy trình lên lịch hàng ngày, xem CLAUDE.md dự án.

Report-only — KHÔNG tạo kế hoạch/task thật.

Dùng (mặc định hôm nay = ngày chạy script, 8 ngày qua + 5 ngày tới):
    python3 scripts/lich_gop.py --ketqua /tmp/ketqua.xlsx --hom-nay 2026-07-22

Tuỳ chọn:
    --so-ngay-qua N     (mặc định 8 — gồm cả hôm nay)
    --so-ngay-toi N      (mặc định 5)
    --plan-hom-nay-ngay YYYY-MM-DD  (nếu kế hoạch hôm nay dùng ngày khác hôm
                                      nay, mặc định = --hom-nay)
    --html <đường dẫn>  (mặc định lich_gop.html cùng thư mục chạy)
"""
import argparse, json, re, sys, datetime
from collections import defaultdict, Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import pandas as pd
from du_bao_mien import tinh_du_bao, parse_lsx
from trang_thai_nha_may import doc_actual, snapshot_ca_day, doc_lich_xuat_hao

COT_NGUOI = "Người thực hiện1"
COT_NGAY = "Ngày thực hiện"
COT_LSX = "Lệnh sản xuất"
COT_BE = "Bể / xe"
COT_BE_CAP = "Bể / xe cấp"
COT_LUONG = "Lượng thực tế"
COT_LO = "Lô"

REPO_DIR = Path(__file__).parent.parent
PLAN_DIR = REPO_DIR / "plans"
LICH_XUAT_PATH = ("/Users/macos/Library/Mobile Documents/iCloud~md~obsidian/Documents/Buu/"
                  "20 Projects (Dự án)/Nhập liệu real time/10 Tài nguyên/"
                  "Lịch Xuất Thành Phẩm — Nam Ngư.md")

DOW = ['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN']


def phan_loai(lsx):
    """Phân loại nhóm công việc — quy ước RIÊNG cho bảng lịch làm việc (khác
    `phan_loai_mo_ta1` gốc trong trang_thai_nha_may.py: ở đây gộp chung các
    vòng đảo trộn/nước long thành 1 nhóm, tách riêng Đấu/Tồn/Xuất thành phẩm,
    và tách riêng Pha muối (PM00/MP00/MP01) khỏi Phá xác (PX00) — Tim chốt
    2026-07-21, PX00 luôn xếp cuối cùng vòng quay chượp)."""
    lsx = str(lsx)
    if lsx == "S000": return "S-Khác"
    if lsx in ("S010", "S020"): return "S-Bể trống"
    if lsx in ("S030", "S031", "S032"): return "S-Nhập cá"
    if lsx == "S040": return "S-Phân bổ cá"
    if re.match(r'^SM0[1-6]$', lsx): return "S-Bổ sung muối"
    if lsx == "S050": return "S-Rút kiệt gài nén"
    if lsx == "S090": return "S-Gài nén"
    if re.match(r'^B\d{3}$', lsx): return "S-Nước bổi"
    if re.match(r'^S([1-7])\d{2}$', lsx): return "S-Đảo trộn"
    if lsx in ("S800", "S900"): return "S-Trống"
    if lsx == "C000": return "C-Cá chín"
    if re.match(r'^C0[1-4]0$', lsx): return "C-Rút kiệt đảo trong"
    if lsx == "C090": return "C-Tách cốt"
    if re.match(r'^N\d{3}$', lsx): return "P-Cốt nhỉ"
    if re.match(r'^C([1-9])\d0$', lsx): return "C-Kéo rút nước long"
    if lsx in ("CX00", "CY00", "CZ00"): return "C-Kéo rút nước long"
    if lsx in ("PM00", "MP00", "MP01"): return "Pha muối"
    if lsx == "PX00": return "Phá xác"
    if re.match(r'^Px[1-9]0$', lsx): return "P-Đấu thành phẩm"  # mã tạm, be_nhan="Bể TP" chưa chốt
    if re.match(r'^P\d{3}$', lsx): return "P-Đấu thành phẩm"
    if re.match(r'^PT\d{2}$', lsx): return "P-Tồn thành phẩm"
    if re.match(r'^PP\d{2}$', lsx): return "P-Xuất thành phẩm"
    return None


# ── Màu/nhãn chữ theo "độ tin cậy dự báo" — CHỐT 2026-07-21, không tự đổi ──
MAU_CHU = {"xanh": "#166534", "vang": "#854d0e", "do": "#991b1b"}
NHAN = {"xanh": "🟢 Có quy luật", "vang": "🟡 Xu hướng, chưa rõ", "do": "🔴 Không quy luật"}
PHAN_LOAI = {
    "S-Đảo trộn": ("xanh", "Ngày con đếm được rõ, dự báo chính xác từng bể"),
    "C-Kéo rút nước long": ("xanh", "Cấu trúc L/T đáng tin, không đoán được ngày cụ thể tiến triển"),
    "C-Rút kiệt đảo trong": ("vang", "Phong làm đều nhưng chưa đối chiếu chu kỳ rõ ràng"),
    "P-Cốt nhỉ": ("vang", "Ha làm nhưng rất hiếm gặp, chưa đủ dữ liệu thấy chu kỳ"),
    "P-Đấu thành phẩm": ("do", "Đích bể TP không cố định theo dãy, đổi tuỳ đợt"),
    "Pha muối": ("do", "Việc phát sinh, không đoán trước được"),
    "Phá xác": ("do", "Việc phát sinh, không đoán trước được"),
    "P-Tồn thành phẩm": ("do", "Cả Ha lẫn Hao cùng làm, không cố định 1 người"),
    "P-Xuất thành phẩm": ("xanh", "Theo lịch giao hàng đã biết trước (nguồn ngoài, đáng tin)"),
    "S-Bể trống": ("do", "Phụ thuộc cá về thực tế, Miên tự báo khi có"),
    "S-Nước bổi": ("vang", "Có hoạt động nhưng thưa, chưa rõ quy luật"),
}
DEFAULT_LOAI = ("vang", "Chưa đủ dữ liệu để đánh giá")

# ── Màu NỀN riêng theo luật S/C/P/khác — CHỐT 2026-07-21, CHỈ đổi nền, không
# đụng chữ/nhãn ở trên. Theo CHỮ ĐẦU MÃ LSX THẬT, không theo tên hiển thị.
NHOM_PREFIX_THAT = {
    "S-Bể trống": "S", "S-Nhập cá": "S", "S-Phân bổ cá": "S", "S-Bổ sung muối": "S",
    "S-Rút kiệt gài nén": "S", "S-Gài nén": "S", "S-Đảo trộn": "S", "S-Trống": "S",
    "S-Nước bổi": "B",
    "C-Cá chín": "C", "C-Rút kiệt đảo trong": "C", "C-Tách cốt": "C", "C-Kéo rút nước long": "C",
    "P-Cốt nhỉ": "N",
    "Pha muối": "P", "Phá xác": "P",
    "P-Đấu thành phẩm": "P", "P-Tồn thành phẩm": "P", "P-Xuất thành phẩm": "P",
}
NEN_THEO_CHU = {"S": "#fee2e2", "C": "#fef9c3", "P": "#dcfce7"}
NEN_MAC_DINH = "#f3e8ff"  # B/N/M/khác

THU_TU_QUY_TRINH = [
    "S-Bể trống", "S-Nhập cá", "S-Phân bổ cá", "S-Bổ sung muối",
    "S-Rút kiệt gài nén", "S-Gài nén", "S-Nước bổi",
    "S-Đảo trộn", "S-Trống",
    "C-Cá chín", "C-Rút kiệt đảo trong", "C-Tách cốt", "P-Cốt nhỉ",
    "C-Kéo rút nước long",
    "Pha muối",
    "P-Đấu thành phẩm", "P-Tồn thành phẩm", "P-Xuất thành phẩm",
    "Phá xác",  # LUÔN CUỐI CÙNG
]

# ── Dự đoán THỬ NGHIỆM "bước kế tiếp" — thêm 2026-07-23, Tim yêu cầu phát
# triển thêm khả năng tiên đoán, gợi ý bằng ví dụ S020 (S-Bể trống) hàng loạt
# trong ngày. Ý tưởng: nếu 1 bể làm xong bước X hôm nay → đoán bể đó làm
# bước KẾ TIẾP trong quy trình vào NGÀY MAI (chỉ 1 ngày, không đoán xa hơn).
# CHỈ áp dụng đoạn chuẩn bị đầu chuỗi (trước Đảo trộn) — đây là chuỗi thao
# tác liên tiếp nhau trong ít ngày mỗi khi có mẻ cá mới, ít bị gián đoạn.
# KHÔNG áp dụng cho: S-Gài nén→Đảo trộn (Đảo trộn đã có model chu kỳ riêng,
# chính xác hơn), S-Nước bổi (tài liệu Quy Trình mục 2 ghi rõ "KHÔNG áp dụng
# +1 ngày"), S-Trống→Cá chín và Tách cốt→Cốt nhỉ (khoảng cách thời gian
# không cố định, có thể vài ngày tới vài tuần, không phải next-day).
# Đây là GIẢ ĐỊNH BAN ĐẦU — Tim xác nhận/sửa dần từng bước cho sát hơn.
NHOM_KE_TIEP = {
    "S-Bể trống": "S-Nhập cá",
    "S-Nhập cá": "S-Phân bổ cá",
    "S-Phân bổ cá": "S-Bổ sung muối",
    "S-Bổ sung muối": "S-Rút kiệt gài nén",
    "S-Rút kiệt gài nén": "S-Gài nén",
}


def xay_ban_do_be_lsx_xuat(df):
    """Xây map bể cấp (Lxxx) → mã LSX xuất TP (PPx0), quét TOÀN BỘ actual
    (không giới hạn khung ngày hiện). Xác nhận 2026-07-22: mỗi bể luôn gắn
    1 mã PP cố định trong suốt lịch sử (L113→PP10, L114→PP20, L133→PP30,
    L134→PP40... không đổi theo ngày/lô) — nên suy luận được LSX cho lô
    tương lai chỉ từ bể nguồn trong Lịch Xuất Thành Phẩm, không cần đợi
    actual của chính lô đó."""
    dem = defaultdict(Counter)
    for _, row in df.iterrows():
        lsx = row[COT_LSX]
        be_cap = row[COT_BE_CAP]
        if pd.isna(lsx) or pd.isna(be_cap):
            continue
        lsx, be_cap = str(lsx), str(be_cap)
        if re.match(r'^PP[1-9]0$', lsx) and be_cap.startswith("L"):
            dem[be_cap][lsx] += 1
    return {be: c.most_common(1)[0][0] for be, c in dem.items()}


def xac_nhan_be_theo_lo(df):
    """Kiểm chứng bể thành phẩm thật của mỗi lô S0xx — quét TOÀN BỘ actual các
    lệnh Đấu TP (P\\d{3}) + Tồn TP (PT\\d{2}), đây là nơi Lô + Bể/xe (bể nhận)
    được công nhân ghi trực tiếp khi đấu/tồn, đáng tin hơn ảnh chụp Lịch Xuất
    Thành Phẩm (Tim gõ tay, dễ đảo nhầm số bể — xem _Giao Bang.md 2026-07-22,
    phát hiện đảo S077/S078). Trả về {lô: Counter(bể)}."""
    dem = defaultdict(Counter)
    for _, row in df.iterrows():
        lsx = row[COT_LSX]
        lo = row[COT_LO]
        be = row[COT_BE]
        if pd.isna(lsx) or pd.isna(lo) or pd.isna(be):
            continue
        lsx, lo, be = str(lsx), str(lo), str(be)
        if re.match(r'^P\d{3}$', lsx) or re.match(r'^PT\d{2}$', lsx):
            dem[lo][be] += 1
    return dem


def kiem_chung_lich_xuat(hao_kq, be_thuc_te_theo_lo):
    """Đối chiếu bể nguồn ghi trong Lịch Xuất Thành Phẩm (hao_kq, do Tim gõ
    tay từ ảnh) với bể thực tế theo actual Đấu TP/Tồn TP. Trả về list cảnh
    báo — chỉ báo khi CÓ actual mà KHÔNG khớp (lô chưa tới giai đoạn đấu thì
    bỏ qua, không đoán/không báo động nhầm)."""
    da_xet = set()
    canh_bao = []
    for r in hao_kq:
        lo, be_khai = r["lo"], r["be_nguon"]
        if not lo or not be_khai or lo in da_xet:
            continue
        da_xet.add(lo)
        dem = be_thuc_te_theo_lo.get(lo)
        if not dem:
            continue  # lô chưa có Đấu TP/Tồn TP nào — chưa kiểm chứng được
        be_thuc_te, so_dong = dem.most_common(1)[0]
        if be_thuc_te != be_khai:
            canh_bao.append({
                "lo": lo, "be_khai": be_khai, "be_thuc_te": be_thuc_te, "so_dong": so_dong,
            })
    return canh_bao


def doc_actual_theo_nhom(df, tu_ngay, den_ngay):
    """Gộp actual KetQua theo nhóm + ngày, cho khung [tu_ngay, den_ngay]."""
    data = defaultdict(lambda: defaultdict(list))
    for _, row in df.iterrows():
        lsx = row[COT_LSX]
        ng = row[COT_NGAY]
        if pd.isna(lsx) or pd.isna(ng):
            continue
        d = ng.date()
        if d < tu_ngay or d > den_ngay:
            continue
        g = phan_loai(lsx)
        if not g:
            continue
        data[g][d].append({
            "lsx": str(lsx), "be": row[COT_BE], "be_cap": row[COT_BE_CAP],
            "luong": row[COT_LUONG], "nguoi": row[COT_NGUOI], "lo": row[COT_LO],
        })
    return data


def doc_ke_hoach_hom_nay(hom_nay_slug):
    """Đọc 4 file plan/<người>-<hom_nay_slug>.json (kế hoạch ĐÃ GỬI công nhân
    hôm nay), phân loại theo nhóm."""
    ke_hoach = defaultdict(list)
    for worker, prefix in [("Phong", "phong"), ("Ha", "ha"), ("Mien", "mien"), ("Hao", "hao")]:
        fpath = PLAN_DIR / f"{prefix}-{hom_nay_slug}.json"
        if not fpath.exists():
            continue
        plan = __import__("json").loads(fpath.read_text(encoding="utf-8"))
        for t in plan["tasks"]:
            g = phan_loai(t["lsx"])
            if not g:
                continue  # mã tạm Px_0 chưa chốt bể — bỏ qua, không đoán
            ke_hoach[g].append({**t, "nguoi": worker})
    return ke_hoach


def chi_tiet_actual(rows):
    lines = "".join(
        f"<tr><td>{r['lsx']}</td><td>{r['be'] or '—'}</td><td>{r['be_cap'] or '—'}</td>"
        f"<td>{r['luong'] if r['luong'] is not None and not pd_isna(r['luong']) else '—'}</td>"
        f"<td>{r['nguoi']}</td></tr>"
        for r in rows)
    return (f"<table class='chitiet'><thead><tr><th>LSX</th><th>Bể nhận</th><th>Bể cấp</th>"
            f"<th>Lượng</th><th>Người</th></tr></thead><tbody>{lines}</tbody></table>")


def pd_isna(v):
    try:
        return pd.isna(v)
    except Exception:
        return v is None


def cell_actual(actual_data, nhom, d):
    rows = actual_data.get(nhom, {}).get(d, [])
    if not rows:
        return "—", True
    nguoi_count = defaultdict(int)
    for r in rows:
        nguoi_count[r["nguoi"]] += 1
    tom_tat = ", ".join(f"{n}({c})" for n, c in nguoi_count.items())
    return f"<details><summary>{tom_tat}</summary>{chi_tiet_actual(rows)}</details>", False


def cell_lap_lai_tu_actual(actual_data, nhom, d_nguon, nhan):
    """Lặp lại actual của d_nguon (thường = hôm nay) cho ngày tương lai —
    dùng cho nhóm không có trong plan JSON (vd Rút kiệt đảo trong: Phong
    làm đều hàng ngày trên cùng bể nhưng việc này chưa được đưa vào WO
    chính thức, xem _Giao Bang.md 2026-07-22)."""
    rows = actual_data.get(nhom, {}).get(d_nguon, [])
    if not rows:
        return "—", True
    nguoi_count = defaultdict(int)
    for r in rows:
        nguoi_count[r["nguoi"]] += 1
    tom_tat = ", ".join(f"{n}({c}) {nhan}" for n, c in nguoi_count.items())
    return f"<details><summary>{tom_tat}</summary>{chi_tiet_actual(rows)}</details>", False


def cell_ke_hoach_hom_nay(ke_hoach_hom_nay, nhom, nhan="[kế hoạch]"):
    items = ke_hoach_hom_nay.get(nhom, [])
    if not items:
        return "—", True
    nguoi_count = defaultdict(int)
    for t in items:
        nguoi_count[t["nguoi"]] += 1
    tom_tat = ", ".join(f"{n}({c}) {nhan}" for n, c in nguoi_count.items())
    detail = "".join(
        f"<tr><td>{t['lsx']}</td><td>{t.get('be_nhan') or '—'}</td><td>{t.get('be_cap') or '—'}</td>"
        f"<td>{t.get('luong_dk', '—')}</td><td>{t['nguoi']}</td></tr>"
        for t in items)
    return (f"<details><summary>{tom_tat}</summary>"
            f"<table class='chitiet'><thead><tr><th>LSX</th><th>Bể nhận</th><th>Bể cấp</th>"
            f"<th>Lượng dự kiến</th><th>Người</th></tr></thead><tbody>{detail}</tbody></table></details>", False)


def cell_ke_hoach_dao_tron(dao_tron_ke_hoach, d):
    """Render Y HỆT khuôn 5 cột dùng cho ô 'hôm nay' (LSX/Bể nhận/Bể cấp/
    Lượng dự kiến/Người) — Tim chốt 2026-07-23: mọi ô kế hoạch tương lai phải
    cùng 1 mẫu với ô thực hiện/hôm nay, không tự sáng tạo khuôn 2 cột riêng
    cho đảo trộn nữa. Bể cấp suy ra từ Bể nhận (Lxxx → Txxx, cùng số — đúng
    quy ước plan JSON thật của Miên, vd L015↔T015)."""
    items = dao_tron_ke_hoach.get(d, [])
    if not items:
        return "—", True
    het = sum(1 for x in items if x["lsx"] == "HẾT CK")
    tom_tat = f"Mien({len(items)}) [kế hoạch]" + (f" ({het} hết CK)" if het else "")
    detail = "".join(
        f"<tr><td>{x['lsx']}</td><td>{x['be']}</td><td>{'T' + x['be'][1:] if x['be'].startswith('L') else '—'}</td>"
        f"<td>—</td><td>Mien</td></tr>"
        for x in items)
    return (f"<details><summary>{tom_tat}</summary>"
            f"<table class='chitiet'><thead><tr><th>LSX</th><th>Bể nhận</th><th>Bể cấp</th>"
            f"<th>Lượng dự kiến</th><th>Người</th></tr></thead><tbody>{detail}</tbody></table></details>", False)


def ma_phuong_tien(loai_xe):
    """Loại xe (chữ, đọc từ Lịch Xuất Thành Phẩm) → mã phương tiện nhận
    XT00/XB00 — khớp đúng cách actual ghi trong KetQua (Bể nhận = XT00/XB00,
    Bể cấp = Lxxx). Tim chốt 2026-07-22: kế hoạch phải ghi cùng khuôn với
    actual, không dùng chữ mô tả xe."""
    loai_xe = (loai_xe or "").strip()
    if "Bồn" in loai_xe:
        return "XB00"
    if "Tải" in loai_xe:
        return "XT00"
    return loai_xe or "—"


NHOM_LSX_DU_DOAN = {
    "S-Nhập cá": "S030",
    "S-Phân bổ cá": "S040",
    "S-Bổ sung muối": "SM0x",
    "S-Rút kiệt gài nén": "S050",
    "S-Gài nén": "S090",
}


def du_doan_buoc_ke_tiep(actual_data, hom_nay):
    """Dự đoán THỬ NGHIỆM: với mỗi bể có actual HÔM NAY ở 1 nhóm nằm trong
    NHOM_KE_TIEP, đoán bể đó chuyển sang bước KẾ TIẾP vào NGÀY MAI. Trả về
    {nhóm_kế_tiếp: [{"be", "tu_nhom", "nguoi_hom_nay", "luong"}]}."""
    ket_qua = defaultdict(list)
    for nhom_hien_tai, nhom_ke_tiep in NHOM_KE_TIEP.items():
        for r in actual_data.get(nhom_hien_tai, {}).get(hom_nay, []):
            be = r["be"]
            if not be or pd_isna(be):
                continue
            ket_qua[nhom_ke_tiep].append({
                "be": be, "tu_nhom": nhom_hien_tai, "nguoi_hom_nay": r["nguoi"], "luong": r["luong"],
            })
    return ket_qua


def cell_du_doan(du_doan, nhom):
    """Render Y HỆT khuôn 5 cột dùng cho ô 'hôm nay' (LSX/Bể nhận/Bể cấp/
    Lượng dự kiến/Người) — Tim chốt 2026-07-23: kế hoạch (dự đoán) và thực
    hiện phải cùng 1 mẫu, chỉ khác nhãn. CHỈ đổi hiển thị báo cáo, KHÔNG đưa
    vào file kế hoạch/WO thật (Tim xác nhận đây vẫn là báo cáo report-only,
    chờ Tim duyệt trước khi giao việc thật)."""
    items = du_doan.get(nhom, [])
    if not items:
        return "—", True
    lsx = NHOM_LSX_DU_DOAN.get(nhom, "?")
    nguoi_count = defaultdict(int)
    for it in items:
        nguoi_count[it["nguoi_hom_nay"]] += 1
    tom_tat = ", ".join(f"{n}({c}) [dự đoán]" for n, c in nguoi_count.items())
    detail = "".join(
        f"<tr><td>{lsx}</td><td>{x['be']}</td><td>—</td>"
        f"<td>{x['luong'] if x['luong'] is not None and not pd_isna(x['luong']) else '—'}</td>"
        f"<td>{x['nguoi_hom_nay']}</td></tr>"
        for x in items)
    return (f"<details><summary>{tom_tat}</summary>"
            f"<table class='chitiet'><thead><tr><th>LSX</th><th>Bể nhận</th><th>Bể cấp</th>"
            f"<th>Lượng dự kiến</th><th>Người</th></tr></thead><tbody>{detail}</tbody></table></details>", False)




def cell_ke_hoach_xuat_tp(hao_ke_hoach, d, be_to_lsx):
    items = hao_ke_hoach.get(d, [])
    if not items:
        return "—", True
    tom_tat = f"{len(items)} chuyến"
    detail = "".join(
        f"<tr><td>{be_to_lsx.get(r['be_nguon'], '?')}</td><td>{r['item']}</td><td>{r['lo']}</td>"
        f"<td>{r['be_nguon'] or '—'}</td><td>{ma_phuong_tien(r['loai_xe'])}</td>"
        f"<td>{r['sl']} lít</td><td>{r['noi_den']}</td></tr>"
        for r in items)
    return (f"<details><summary>{tom_tat}</summary>"
            f"<table class='chitiet'><thead><tr><th>LSX (suy luận)</th><th>ITEM</th><th>Lô</th><th>Bể cấp</th>"
            f"<th>Phương tiện nhận</th><th>SL</th><th>Nơi đến</th></tr></thead>"
            f"<tbody>{detail}</tbody></table></details>", False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ketqua", required=True)
    ap.add_argument("--hom-nay", default=None, help="YYYY-MM-DD, mặc định = ngày chạy script")
    ap.add_argument("--so-ngay-qua", type=int, default=8, help="Số ngày quá khứ hiện (gồm hôm nay)")
    ap.add_argument("--so-ngay-toi", type=int, default=5, help="Số ngày tương lai hiện")
    ap.add_argument("--lich-xuat", default=LICH_XUAT_PATH)
    ap.add_argument("--html", default="lich_gop.html")
    args = ap.parse_args()

    hom_nay = datetime.date.fromisoformat(args.hom_nay) if args.hom_nay else datetime.date.today()
    hom_nay_slug = hom_nay.strftime("%d%m%Y")
    tu_ngay_qua = hom_nay - datetime.timedelta(days=args.so_ngay_qua - 1)
    ngay_mai = hom_nay + datetime.timedelta(days=1)
    ngay_list = [tu_ngay_qua + datetime.timedelta(days=i) for i in range(args.so_ngay_qua + args.so_ngay_toi)]

    df = doc_actual(args.ketqua)
    actual_data = doc_actual_theo_nhom(df, tu_ngay_qua, hom_nay)
    ke_hoach_hom_nay = doc_ke_hoach_hom_nay(hom_nay_slug)

    # Đảo trộn: ƯU TIÊN đọc thẳng WO thật của ngày mai (nếu đã tồn tại, vd
    # sau khi chạy lap_ke_hoach_ngay.py) làm cột ngày mai — KHÔNG tự tính lại
    # từ plan hôm nay, tránh lệch với WO thật đã vá theo actual (Tim chốt
    # 2026-07-23: báo cáo và WO phải đồng nhất, phát hiện thực tế 12/22 bể
    # lệch do doi_chieu.py từng bỏ sót bể khi đối chiếu). Chỉ dùng
    # tinh_du_bao() để TIẾP TỤC dự báo các ngày XA HƠN ngày mai (chưa có WO
    # thật), lấy WO ngày mai làm anchor mới thay vì plan hôm nay.
    mien_ngay_mai_slug = ngay_mai.strftime("%d%m%Y")
    mien_ngay_mai_path = PLAN_DIR / f"mien-{mien_ngay_mai_slug}.json"
    mien_hom_nay_path = PLAN_DIR / f"mien-{hom_nay_slug}.json"

    dao_tron_ngay_mai_that = []
    if mien_ngay_mai_path.exists():
        plan_ngay_mai = json.loads(mien_ngay_mai_path.read_text(encoding="utf-8"))
        for t in plan_ngay_mai["tasks"]:
            if parse_lsx(t["lsx"]):
                dao_tron_ngay_mai_that.append({"be": t["be_nhan"], "lsx": t["lsx"]})
        mien_kq = (tinh_du_bao(str(mien_ngay_mai_path), ngay_mai + datetime.timedelta(days=1),
                                args.so_ngay_toi - 1)
                   if args.so_ngay_toi > 1 else None)
        mien_kq_offset = 1  # cột đầu (ngay_mai) đã lấy từ WO thật ở trên, mien_kq bắt đầu từ ngay_mai+1
    else:
        mien_kq = tinh_du_bao(str(mien_hom_nay_path), ngay_mai, args.so_ngay_toi) \
            if mien_hom_nay_path.exists() else None
        mien_kq_offset = 0
    chuoi_day_kq = snapshot_ca_day(df, hom_nay)
    hao_kq = doc_lich_xuat_hao(args.lich_xuat, ngay_mai, args.so_ngay_toi)
    be_to_lsx_xuat = xay_ban_do_be_lsx_xuat(df)
    be_thuc_te_theo_lo = xac_nhan_be_theo_lo(df)
    canh_bao_be_lo = kiem_chung_lich_xuat(hao_kq, be_thuc_te_theo_lo)
    if canh_bao_be_lo:
        print(f"\n⚠️  {len(canh_bao_be_lo)} lô LỆCH bể giữa Lịch Xuất Thành Phẩm và actual Đấu TP/Tồn TP:")
        for c in canh_bao_be_lo:
            print(f"   Lô {c['lo']}: lịch ghi {c['be_khai']}, actual thật là {c['be_thuc_te']} "
                  f"({c['so_dong']} dòng Đấu TP/Tồn TP) — SỬA LẠI Lịch Xuất Thành Phẩm trước khi ra WO!")
    else:
        print("\n✅ Đối chiếu bể theo lô: không phát hiện lệch (hoặc lô còn quá mới, chưa có Đấu TP).")

    dao_tron_ke_hoach = defaultdict(list)
    for item in dao_tron_ngay_mai_that:
        dao_tron_ke_hoach[ngay_mai].append(item)
    if mien_kq:
        for row in mien_kq["rows"]:
            for i, c in enumerate(row["cells"]):
                d = ngay_mai + datetime.timedelta(days=i + mien_kq_offset)
                if c["loai"] == "binh_thuong":
                    dao_tron_ke_hoach[d].append({"be": row["be"], "lsx": c["text"]})
                elif c["loai"] == "het_ck":
                    dao_tron_ke_hoach[d].append({"be": row["be"], "lsx": "HẾT CK"})

    hao_ke_hoach = defaultdict(list)
    for r in hao_kq:
        hao_ke_hoach[r["ngay"]].append(r)

    du_doan = du_doan_buoc_ke_tiep(actual_data, hom_nay)
    if du_doan:
        print(f"\n🔮 Dự đoán thử nghiệm bước kế tiếp cho {ngay_mai.strftime('%d/%m')}:")
        for nhom, items in du_doan.items():
            print(f"   {nhom}: {len(items)} bể ({', '.join(x['be'] for x in items)}) "
                  f"— vì hôm nay làm {items[0]['tu_nhom']}")

    _tat_ca = set(actual_data.keys()) | set(ke_hoach_hom_nay.keys()) | \
        {"S-Đảo trộn", "C-Kéo rút nước long", "P-Đấu thành phẩm", "P-Xuất thành phẩm"} | set(du_doan.keys())
    _giua = [g for g in THU_TU_QUY_TRINH if g in _tat_ca and g != "Phá xác"]
    _con_lai = sorted(_tat_ca - set(THU_TU_QUY_TRINH))
    tat_ca_nhom = _giua + _con_lai + (["Phá xác"] if "Phá xác" in _tat_ca else [])

    header_cells = ""
    for d in ngay_list:
        cls = "col-qua" if d < hom_nay else ("col-homnay" if d == hom_nay else "col-tuong-lai")
        header_cells += f"<th class='{cls}'>{d.strftime('%d/%m')}<br><span class='dow'>{DOW[d.weekday()]}</span></th>"

    rows_html = ""
    for nhom in tat_ca_nhom:
        loai, ly_do = PHAN_LOAI.get(nhom, DEFAULT_LOAI)
        mau_chu, nhan = MAU_CHU[loai], NHAN[loai]
        mau = NEN_THEO_CHU.get(NHOM_PREFIX_THAT.get(nhom, ""), NEN_MAC_DINH)
        cells = ""
        for d in ngay_list:
            col_cls = "col-qua" if d < hom_nay else ("col-homnay" if d == hom_nay else "col-tuong-lai")
            if d < hom_nay:
                noi_dung, trong = cell_actual(actual_data, nhom, d)
            elif d == hom_nay:
                noi_dung, trong = cell_actual(actual_data, nhom, d)
                if trong:
                    noi_dung, trong = cell_ke_hoach_hom_nay(ke_hoach_hom_nay, nhom)
            else:
                if nhom == "S-Đảo trộn":
                    noi_dung, trong = cell_ke_hoach_dao_tron(dao_tron_ke_hoach, d)
                elif nhom == "C-Kéo rút nước long":
                    noi_dung, trong = cell_ke_hoach_hom_nay(
                        ke_hoach_hom_nay, "C-Kéo rút nước long", f"[lặp lại {hom_nay.strftime('%d/%m')}]")
                elif nhom == "C-Rút kiệt đảo trong":
                    noi_dung, trong = cell_lap_lai_tu_actual(
                        actual_data, "C-Rút kiệt đảo trong", hom_nay, f"[lặp lại {hom_nay.strftime('%d/%m')}]")
                elif nhom == "P-Xuất thành phẩm":
                    noi_dung, trong = cell_ke_hoach_xuat_tp(hao_ke_hoach, d, be_to_lsx_xuat)
                elif nhom == "P-Đấu thành phẩm":
                    # Tim chốt 2026-07-23: để TRỐNG bể (Bể TP/mã Px_0 chưa
                    # chốt) giống hệt WO thật — KHÔNG tự đoán bể cụ thể (x)
                    # tới khi Tim hướng dẫn cách suy x đúng. Lặp lại nguyên
                    # kế hoạch Px10-Px90 hôm nay, giống cách làm Kéo rút.
                    noi_dung, trong = cell_ke_hoach_hom_nay(
                        ke_hoach_hom_nay, "P-Đấu thành phẩm", f"[lặp lại {hom_nay.strftime('%d/%m')}]")
                elif d == ngay_mai and nhom in du_doan:
                    noi_dung, trong = cell_du_doan(du_doan, nhom)
                else:
                    noi_dung, trong = "—", True
            td_cls = f"{col_cls}{' trong' if trong else ''}"
            cells += f"<td class='{td_cls}'>{noi_dung}</td>"
        rows_html += (f'<tr><td class="nhom-col" style="background:{mau};color:{mau_chu}">'
                      f'<b>{nhom}</b><br><span class="tag">{nhan}</span></td>{cells}</tr>\n')

    canh_bao_html = ""
    if canh_bao_be_lo:
        dong = "".join(
            f"<li>Lô <b>{c['lo']}</b>: Lịch Xuất Thành Phẩm ghi <b>{c['be_khai']}</b>, "
            f"nhưng actual Đấu TP/Tồn TP thật là <b>{c['be_thuc_te']}</b> "
            f"({c['so_dong']} dòng) — cần sửa lại Lịch Xuất Thành Phẩm trước khi ra WO!</li>"
            for c in canh_bao_be_lo)
        canh_bao_html = (f'<div class="canh-bao">🚨 <b>PHÁT HIỆN LỆCH BỂ GIỮA LỊCH XUẤT THÀNH PHẨM VÀ ACTUAL '
                          f'(Đấu TP/Tồn TP)</b> — kiểm tra trước khi ra WO xuất thành phẩm:'
                          f'<ul>{dong}</ul></div>')

    html = f"""<!DOCTYPE html>
<html lang="vi"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lịch làm việc gộp — {ngay_list[0].strftime('%d/%m')}-{ngay_list[-1].strftime('%d/%m/%Y')}</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
         background:#f1f5f9; color:#0f172a; padding:16px; }}
  .wrap {{ max-width:1600px; margin:0 auto; }}
  header {{ background:#0f172a; color:#fff; border-radius:14px; padding:18px 20px; margin-bottom:14px; }}
  .h-title {{ font-size:19px; font-weight:700; }}
  .h-sub {{ color:#94a3b8; font-size:13px; margin-top:4px; }}
  .note {{ background:#fef3c7; border:1px solid #fcd34d; color:#78350f; border-radius:10px;
          padding:10px 14px; font-size:13px; margin-bottom:14px; line-height:1.6; }}
  .canh-bao {{ background:#fee2e2; border:1px solid #fca5a5; color:#7f1d1d; border-radius:10px;
          padding:10px 14px; font-size:13px; margin-bottom:14px; line-height:1.7; }}
  .canh-bao b {{ color:#991b1b; }}
  .legend {{ display:flex; gap:14px; margin-bottom:14px; flex-wrap:wrap; font-size:12.5px; }}
  .legend span {{ padding:4px 10px; border-radius:8px; }}
  .table-wrap {{ overflow-x:auto; background:#fff; border:1px solid #e2e8f0; border-radius:14px; }}
  table {{ border-collapse:collapse; width:100%; font-size:11px; white-space:nowrap; }}
  th, td {{ padding:6px 8px; text-align:center; border-bottom:1px solid #f1f5f9; border-right:1px solid #f1f5f9;
           vertical-align:top; }}
  th {{ background:#f8fafc; color:#475569; font-weight:700; position:sticky; top:0; }}
  .dow {{ font-weight:400; color:#94a3b8; font-size:9px; }}
  .nhom-col {{ font-weight:700; text-align:left; position:sticky; left:0; min-width:170px; white-space:normal; }}
  .tag {{ font-size:10px; font-weight:400; }}
  .trong {{ color:#cbd5e1; }}
  .col-qua {{ }}
  .col-homnay {{ background:#eff6ff !important; border-left:2px solid #2563eb; border-right:2px solid #2563eb; }}
  th.col-homnay {{ background:#dbeafe !important; color:#1e40af; }}
  .col-tuong-lai {{ background:#fafafa; }}
  details summary {{ cursor:pointer; font-size:11px; }}
  details summary:hover {{ text-decoration:underline; }}
  table.chitiet {{ margin-top:6px; font-size:10.5px; white-space:normal; }}
  table.chitiet th, table.chitiet td {{ padding:3px 6px; }}
  footer {{ text-align:center; color:#94a3b8; font-size:12px; margin-top:18px; }}
</style>
</head><body>
<div class="wrap">
  <header>
    <div class="h-title">📅 Lịch làm việc — Đã thực hiện | Hôm nay | Kế hoạch ({ngay_list[0].strftime('%d/%m')}-{ngay_list[-1].strftime('%d/%m/%Y')})</div>
    <div class="h-sub">Trái = đã thực hiện (thật) · Giữa (viền xanh dương) = hôm nay {hom_nay.strftime('%d/%m')} · Phải = kế hoạch sắp tới</div>
  </header>
  <div class="note">
    ⚠️ Xem bảng này trước khi ra WO cho nhân viên (Tim chốt 2026-07-21). Bấm vào ô để xem chi tiết
    LSX/bể/lượng (đã thực hiện) hoặc bể/LSX dự kiến (kế hoạch). Nhóm đỏ bên phải để trống vì không
    đoán trước được — trừ ô có nhãn 🔮 (dự đoán thử nghiệm bước kế tiếp, xem legend).
  </div>
  {canh_bao_html}
  <div class="legend">
    <span style="background:#dcfce7;color:#166534">🟢 Có quy luật rõ</span>
    <span style="background:#fef9c3;color:#854d0e">🟡 Có xu hướng, chưa rõ</span>
    <span style="background:#fee2e2;color:#991b1b">🔴 Không quy luật</span>
    <span style="background:#dbeafe;color:#1e40af">📍 Cột hôm nay</span>
    <span style="background:#f5f3ff;color:#5b21b6;border:1px dashed #a78bfa">🔮 Dự đoán thử nghiệm (chỉ ngày mai, cần Tim xác nhận)</span>
  </div>
  <div class="table-wrap">
    <table>
      <thead><tr><th>Nhóm công việc</th>{header_cells}</tr></thead>
      <tbody>{rows_html}</tbody>
    </table>
  </div>
  <footer>Tạo tự động bởi scripts/lich_gop.py — {datetime.date.today().strftime('%d/%m/%Y')}</footer>
</div>
</body></html>"""

    Path(args.html).write_text(html, encoding="utf-8")
    print(f"✅ Đã xuất: {args.html}")
    print(f"   Hôm nay: {hom_nay} | Quá khứ: {ngay_list[0]}-{hom_nay} | Tương lai: {ngay_mai}-{ngay_list[-1]}")
    print(f"   Số nhóm: {len(tat_ca_nhom)}")


if __name__ == "__main__":
    main()
