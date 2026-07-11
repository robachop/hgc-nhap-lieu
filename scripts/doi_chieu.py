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

# Số ngày tối đa mỗi chu kỳ đảo trộn (giống tao_ke_hoach.py). Bể vượt quá
# max chu kỳ nếu +1 nghĩa là ĐÃ XONG chu kỳ — không tự đề xuất tiếp, Miên tự
# thêm mẻ mới qua nút ➕ trên app. Bug phát hiện 2026-07-11: bản đầu của hàm
# này thiếu check này, đề xuất nhầm 2 bể đã hết chu kỳ khi chạy thật lần đầu
# (bể 31 CK3 ngày 5→6, bể 191 CK5 ngày 5→6, cả hai vượt max=5) — xử lý tay
# lúc đó, vá thẳng vào đây để lần sau không lặp lại.
CYCLE_MAX = {1: 15, 2: 5, 3: 5, 4: 5, 5: 5, 6: 5, 7: 5}


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
            ngay_ke = ngay + 1
            het_chu_ky = ngay_ke > CYCLE_MAX.get(ck, 5)
            ket_qua[be] = {
                "actual_lsx": lsx,
                "actual_ck": ck,
                "actual_day": ngay,
                "het_chu_ky": het_chu_ky,
                # None nếu hết chu kỳ — KHÔNG đề xuất, Miên tự thêm qua nút ➕
                "de_xuat_lsx_ngay_ke": None if het_chu_ky else f"S{ck}{ngay_ke:02d}",
            }
    n_het = sum(1 for v in ket_qua.values() if v["het_chu_ky"])
    if n_het:
        print(f"  ℹ️  {n_het} bể đã hết chu kỳ (ngày kế > max cho phép) — không đề xuất, Miên tự thêm qua nút ➕: "
              f"{[be for be, v in ket_qua.items() if v['het_chu_ky']]}")
    return ket_qua


def so_voi_plan(ket_qua, plan_path):
    """So đề xuất actual+1 với plan JSON đang có sẵn cho ngày kế tiếp.
    Trả về list các bể lệch: [{"be":..., "plan_lsx":..., "de_xuat":...}]
    Bể hết chu kỳ (de_xuat=None): nếu vẫn còn task trong plan cũ → báo "cần xoá"
    (task["_xoa"]=True); nếu không có task thì bỏ qua, không có gì để làm."""
    plan_path = Path(plan_path)
    if not plan_path.exists():
        print(f"  ⚠️  Chưa có file plan {plan_path} — không so được, chỉ in đề xuất")
        return [{"be": be, "plan_lsx": None, "de_xuat": v["de_xuat_lsx_ngay_ke"]}
                for be, v in ket_qua.items() if not v["het_chu_ky"]]

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
        if v["het_chu_ky"]:
            if task is not None:
                lech.append({"be": be, "plan_lsx": task["lsx"], "de_xuat": None,
                             "task": task, "xoa": True})
            continue  # không có task và hết chu kỳ -> không có gì để làm
        plan_lsx = task["lsx"] if task else None
        if plan_lsx != v["de_xuat_lsx_ngay_ke"]:
            lech.append({"be": be, "plan_lsx": plan_lsx, "de_xuat": v["de_xuat_lsx_ngay_ke"], "task": task, "xoa": False})
    return lech


def ap_dung(lech, plan_path):
    """Vá trực tiếp các bể lệch vào file plan JSON (sửa field 'lsx' + mô tả,
    hoặc XOÁ hẳn task nếu bể đã hết chu kỳ — item có 'xoa': True)."""
    plan_path = Path(plan_path)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    task_by_be = {}
    for t in plan.get("tasks", []):
        m = re.match(r"^[LT](\d+)$", str(t.get("be_nhan", "")))
        if m:
            task_by_be[int(m.group(1))] = t

    def _be_cua_task(t):
        m = re.match(r"^[LT](\d+)$", str(t.get("be_nhan", "")))
        return int(m.group(1)) if m else None

    be_can_xoa = {item["be"] for item in lech if item.get("xoa")}
    if be_can_xoa:
        plan["tasks"] = [t for t in plan["tasks"] if _be_cua_task(t) not in be_can_xoa]
        print(f"  🗑️  Đã xoá {len(be_can_xoa)} bể hết chu kỳ khỏi plan: {sorted(be_can_xoa)} (Miên tự thêm mẻ mới qua ➕ nếu có)")
        lech = [item for item in lech if not item.get("xoa")]

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
                if item.get("xoa"):
                    print(f"     bể {item['be']:>3}: plan={item['plan_lsx']} → HẾT CHU KỲ, cần xoá khỏi plan")
                else:
                    print(f"     bể {item['be']:>3}: plan={item['plan_lsx']} → đề xuất={item['de_xuat']}")
            ap_dung(lech, args.apply)
    else:
        for be, v in sorted(ket_qua.items()):
            if v["het_chu_ky"]:
                print(f"  bể {be:>3}: actual={v['actual_lsx']} → HẾT CHU KỲ, không đề xuất (Miên tự thêm mẻ mới)")
            else:
                print(f"  bể {be:>3}: actual={v['actual_lsx']} → đề xuất ngày kế={v['de_xuat_lsx_ngay_ke']}")


if __name__ == "__main__":
    main()
