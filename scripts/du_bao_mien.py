#!/usr/bin/env python3
"""
du_bao_mien.py — Dự báo NGẮN HẠN lịch đảo trộn Miên cho các ngày sắp tới,
dựa trên plan mới nhất đã đối chiếu actual. CHỈ BÁO CÁO (report-only),
KHÔNG tạo kế hoạch thật — Tim xác nhận 2026-07-20/21, xem chi tiết quy trình
tại 00 Context/Quy Trình Vòng Quay Chượp — Toàn Nhà Máy.md.

Phạm vi: chỉ các bể ĐANG có trong plan hiện tại (không mở rộng ra 220 bể —
đơn giản trước, mở rộng sau nếu cần, theo đúng nguyên tắc Tim chốt 2026-07-21).

Dùng:
    python3 scripts/du_bao_mien.py --plan plans/mien-21072026.json \\
        --tu-ngay 2026-07-22 --so-ngay 7
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
        return vn_holidays[date][:6]
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True, help="File plan JSON mới nhất, vd plans/mien-21072026.json")
    ap.add_argument("--tu-ngay", required=True, help="Ngày bắt đầu dự báo, YYYY-MM-DD")
    ap.add_argument("--so-ngay", type=int, default=7, help="Số ngày dự báo (mặc định 7)")
    args = ap.parse_args()

    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    tasks = [t for t in plan["tasks"] if parse_lsx(t["lsx"])]

    start = datetime.date.fromisoformat(args.tu_ngay)
    vn_holidays = holidays.Vietnam(years=sorted({start.year, (start + datetime.timedelta(days=args.so_ngay)).year}))
    dates = [start + datetime.timedelta(days=i) for i in range(args.so_ngay)]

    print("=" * 78)
    print(f"  DỰ BÁO NGẮN HẠN — ĐẢO TRỘN MIÊN — {args.so_ngay} ngày từ {start.strftime('%d/%m/%Y')}")
    print(f"  Nguồn: {args.plan} ({len(tasks)} bể đang theo dõi)")
    print("  ⚠️  Report-only — KHÔNG tự tạo kế hoạch/task thật")
    print("=" * 78 + "\n")

    col_w = 9
    header = "Bể".ljust(6) + "".join(d.strftime("%d/%m").ljust(col_w) for d in dates)
    print(header)
    print("-" * len(header))

    het_ck_count = 0
    for t in tasks:
        ck, ngay0 = parse_lsx(t["lsx"])
        be = t["be_nhan"]
        row = be.ljust(6)
        ngay = ngay0
        da_het = False
        for d in dates:
            nghi = is_nghi(d, vn_holidays)
            if nghi:
                row += f"({nghi})".ljust(col_w)
                continue
            if da_het:
                row += "-".ljust(col_w)
                continue
            ngay += 1
            if ngay > CYCLE_MAX.get(ck, 5):
                row += "HẾT CK".ljust(col_w)
                da_het = True
                het_ck_count += 1
            else:
                row += f"S{ck}{ngay:02d}".ljust(col_w)
        print(row)

    print("\n" + "=" * 78)
    print(f"  Tổng: {len(tasks)} bể theo dõi, {het_ck_count} bể sẽ hết chu kỳ trong {args.so_ngay} ngày tới")
    print("  'HẾT CK' = bể hết vòng đang đảo trong ngày đó — Miên tự thêm vòng mới qua")
    print("  nút ➕ khi tới lúc thật (~28-38 ngày sau khi bắt đầu vòng hiện tại), KHÔNG")
    print("  đoán trước ngày chính xác. '(CN)'/'(Tết...)' = ngày nghỉ, không đảo trộn.")
    print("=" * 78 + "\n")


if __name__ == "__main__":
    main()
