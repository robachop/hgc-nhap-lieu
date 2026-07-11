#!/usr/bin/env python3
"""
doi_chieu.py — Đối chiếu kế hoạch (plan) đã tạo với dữ liệu thực tế (actual)
từ Google Sheet "HGC Kết quả nhập liệu" (tab KetQua), áp dụng logic
actual+1 cho ngày kế tiếp — đúng theo BƯỚC 0 bắt buộc trong CLAUDE.md.

Chuẩn hoá lại phần trước đây làm bằng Python viết tay mỗi phiên
(xem _Giao Bang.md 2026-07-10, 2026-07-11) thành hàm dùng lại được,
để không phải suy nghĩ lại logic parse mỗi lần gọi kế hoạch mới.

⚠️ Cột trong sheet KetQua dựa theo mô tả đã xác nhận ở phiên 2026-07-10:
   "Người thực hiện1", "Ngày thực hiện", "Lệnh sản xuất", "Diễn giải"
   Nếu Google Sheet đổi tên cột, sửa CỘT_* bên dưới trước khi chạy.

Dùng làm module (import) hoặc CLI:
    python3 scripts/doi_chieu.py <ketqua.xlsx> <worker> <ngay_actual YYYY-MM-DD> \
        [--apply plans/mien-DDMMYYYY.json]

    Không có --apply → chỉ IN ra chỗ lệch, không sửa file (an toàn để xem trước).
    Có --apply       → tự vá file JSON kế hoạch ngày kế tiếp.
"""
import sys, re, json, argparse, datetime
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    print("pip install pandas openpyxl"); sys.exit(1)

COT_NGUOI = "Người thực hiện1"
COT_NGAY = "Ngày thực hiện"
COT_LSX = "Lệnh sản xuất"
COT_DIENGIAI = "Diễn giải"

RE_BE_DAO_TRON = re.compile(r"bể\s+(\d+)", re.IGNORECASE)
RE_LSX_DAO_TRON = re.compile(r"^S([1-7])(\d\d)$")


def doc_actual(ketqua_path, sheet_name="KetQua"):
    """Đọc sheet KetQua, chuẩn hoá kiểu ngày."""
    df = pd.read_excel(ketqua_path, sheet_name=sheet_name)
    df[COT_NGAY] = pd.to_datetime(df[COT_NGAY], errors="coerce")
    return df


def doi_chieu_dao_tron(df, worker, ngay_actual):
    """
    Đối chiếu nhóm 'đảo trộn' (Miên, mã LSX dạng S{ck}{ngày}).
    Trả về dict {bể: {"actual_lsx":..., "actual_ck":..., "actual_day":...,
                        "de_xuat_lsx_ngay_ke":...}}
    """
    ngay_actual = pd.Timestamp(ngay_actual)
    mask = (
        (df[COT_NGUOI] == worker)
        & (df[COT_NGAY].dt.date == ngay_actual.date())
        & (df[COT_LSX].astype(str).str.match(RE_LSX_DAO_TRON))
    )
    rows = df[mask]
    if rows.empty:
        print(f"  ⚠️  Không có dữ liệu actual cho {worker} ngày {ngay_actual.date()}")
        return {}

    ket_qua = {}
    for _, row in rows.iterrows():
        dien_giai = str(row.get(COT_DIENGIAI, ""))
        m_be = RE_BE_DAO_TRON.search(dien_giai)
        if not m_be:
            continue  # dòng không parse được bể — bỏ qua, không đoán
        be = int(m_be.group(1))

        lsx = str(row[COT_LSX]).strip()
        m_lsx = RE_LSX_DAO_TRON.match(lsx)
        if not m_lsx:
            continue
        ck, ngay = int(m_lsx.group(1)), int(m_lsx.group(2))

        # 1 bể có thể có nhiều dòng actual trong ngày — giữ lệnh có ngày lớn nhất
        prev = ket_qua.get(be)
        if prev is None or ngay > prev["actual_day"]:
            ket_qua[be] = {
                "actual_lsx": lsx,
                "actual_ck": ck,
                "actual_day": ngay,
                "de_xuat_lsx_ngay_ke": f"S{ck}{ngay + 1:02d}",
            }
    return ket_qua


def so_voi_plan(ket_qua, plan_path):
    """So đề xuất actual+1 với plan JSON đang có sẵn cho ngày kế tiếp.
    Trả về list các bể lệch: [{"be":..., "plan_lsx":..., "de_xuat":...}]"""
    plan_path = Path(plan_path)
    if not plan_path.exists():
        print(f"  ⚠️  Chưa có file plan {plan_path} — không so được, chỉ in đề xuất")
        return [{"be": be, "plan_lsx": None, "de_xuat": v["de_xuat_lsx_ngay_ke"]}
                for be, v in ket_qua.items()]

    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    # map bể (từ be_nhan dạng "L148") -> task
    task_by_be = {}
    for t in plan.get("tasks", []):
        m = re.match(r"^[LT](\d+)$", str(t.get("be_nhan", "")))
        if m:
            task_by_be[int(m.group(1))] = t

    lech = []
    for be, v in ket_qua.items():
        task = task_by_be.get(be)
        plan_lsx = task["lsx"] if task else None
        if plan_lsx != v["de_xuat_lsx_ngay_ke"]:
            lech.append({"be": be, "plan_lsx": plan_lsx, "de_xuat": v["de_xuat_lsx_ngay_ke"], "task": task})
    return lech


def ap_dung(lech, plan_path):
    """Vá trực tiếp các bể lệch vào file plan JSON (chỉ sửa field 'lsx' + mô tả)."""
    plan_path = Path(plan_path)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    task_by_be = {}
    for t in plan.get("tasks", []):
        m = re.match(r"^[LT](\d+)$", str(t.get("be_nhan", "")))
        if m:
            task_by_be[int(m.group(1))] = t

    n_sua = 0
    for item in lech:
        be, de_xuat = item["be"], item["de_xuat"]
        task = task_by_be.get(be)
        if task is None:
            continue  # bể mới, không tự thêm — Miên tự thêm qua nút ➕ trên app
        m = re.match(r"^S(\d)(\d\d)$", de_xuat)
        if not m:
            continue
        ck = int(m.group(1))
        task["lsx"] = de_xuat
        task["mo_ta"] = re.sub(r"\(CK\d\)", f"(CK{ck})", task.get("mo_ta", "")) if "(CK" in task.get("mo_ta", "") else task.get("mo_ta", "")
        n_sua += 1

    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ✅ Đã vá {n_sua}/{len(lech)} bể vào {plan_path.name}")
    return n_sua


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ketqua_xlsx")
    ap.add_argument("worker")
    ap.add_argument("ngay_actual")
    ap.add_argument("--apply", metavar="PLAN_JSON", default=None)
    ap.add_argument("--sheet", default="KetQua")
    args = ap.parse_args()

    print(f"📊 Đọc {args.ketqua_xlsx} (sheet {args.sheet})...")
    df = doc_actual(args.ketqua_xlsx, args.sheet)

    ket_qua = doi_chieu_dao_tron(df, args.worker, args.ngay_actual)
    print(f"  → {len(ket_qua)} bể có actual ngày {args.ngay_actual}")

    if args.apply:
        lech = so_voi_plan(ket_qua, args.apply)
        if not lech:
            print(f"  ✅ {args.apply}: KHỚP HOÀN TOÀN — không cần sửa")
        else:
            print(f"  ⚠️  {len(lech)} bể lệch:")
            for item in lech:
                print(f"     bể {item['be']:>3}: plan={item['plan_lsx']} → đề xuất={item['de_xuat']}")
            ap_dung(lech, args.apply)
    else:
        for be, v in sorted(ket_qua.items()):
            print(f"  bể {be:>3}: actual={v['actual_lsx']} → đề xuất ngày kế={v['de_xuat_lsx_ngay_ke']}")


if __name__ == "__main__":
    main()
