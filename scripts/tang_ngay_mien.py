#!/usr/bin/env python3
"""
tang_ngay_mien.py — Tạo skeleton kế hoạch Miên (đảo trộn) cho ngày kế tiếp
bằng cách tăng +1 ngày mã LSX (S{ck}{ngày}) từ plan ngày trước đó — dùng khi
KHÔNG có file Excel "Tuần XX" mới từ Tim (gen_mien_tuan.py cần file này).

Logic tăng ngày giống hệt tinh_du_bao()/doi_chieu_dao_tron() đã dùng hàng
ngày cho dự báo lich_gop.py — chỉ khác là GHI ra file plan mới thay vì chỉ
hiển thị. Bể nào hết chu kỳ (ngày kế > CYCLE_MAX) sẽ bị XOÁ khỏi skeleton
(Miên tự thêm mẻ mới qua nút ➕ trên app, không đoán). Sau khi tạo skeleton
này, vẫn chạy tiếp lap_ke_hoach_ngay.py để đối chiếu/vá theo actual thật.

Dùng:
    python3 scripts/tang_ngay_mien.py plans/mien-22072026.json 2026-07-23
    -> ghi plans/mien-23072026.json
"""
import sys, json, re, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from doi_chieu import CYCLE_MAX


def main():
    if len(sys.argv) < 3:
        print("Dùng: python3 scripts/tang_ngay_mien.py <plan_cu.json> YYYY-MM-DD")
        sys.exit(1)
    plan_cu_path = Path(sys.argv[1])
    ngay_moi = datetime.date.fromisoformat(sys.argv[2])
    plan = json.loads(plan_cu_path.read_text(encoding="utf-8"))

    tasks_moi = []
    n_het_ck = 0
    for t in plan["tasks"]:
        m = re.match(r"^S(\d)(\d\d)$", t["lsx"])
        if not m:
            tasks_moi.append(t)  # không phải mã đảo trộn, giữ nguyên
            continue
        ck, ngay = int(m.group(1)), int(m.group(2))
        ngay_ke = ngay + 1
        if ngay_ke > CYCLE_MAX.get(ck, 5):
            n_het_ck += 1
            continue  # hết chu kỳ -> xoá, Miên tự thêm mẻ mới qua nút ➕
        t = dict(t)
        t["lsx"] = f"S{ck}{ngay_ke:02d}"
        tasks_moi.append(t)

    plan_moi = {"date": ngay_moi.isoformat(), "tasks": tasks_moi}
    slug = ngay_moi.strftime("%d%m%Y")
    out_path = plan_cu_path.parent / f"mien-{slug}.json"
    out_path.write_text(json.dumps(plan_moi, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ Đã tạo {out_path} — {len(tasks_moi)} task ({n_het_ck} bể hết CK bị xoá, Miên tự thêm qua ➕)")


if __name__ == "__main__":
    main()
