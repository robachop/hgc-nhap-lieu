#!/usr/bin/env python3
"""
kiem_tra_wo.py — Kiểm tra lỗi cấu trúc trong file kế hoạch (plan) TRƯỚC khi
phát hành WO cho công nhân.

Bối cảnh: Tim chốt 2026-07-27 sau sự cố Phong bị kẹt nút "Gửi kết quả" do 2
task trùng id (khi Cod đổi việc Ha/Phong, ghép 2 danh sách task độc lập mà
không đánh số lại — xem `_Giao Bang.md` 2026-07-27). App `entry.js` tra cứu
kết quả theo đúng `id`, nên 2 task trùng id sẽ CHIA SẺ chung 1 ô kết quả —
1 task vĩnh viễn kẹt "pending" dù công nhân đã bấm chọn, không tự sửa được.

Script này tự động gọi từ `lap_ke_hoach_ngay.py` (BẮT BUỘC, chặn commit+push
nếu có lỗi) — không cần Cod nhớ chạy tay mỗi lần.

Dùng độc lập (khi cần kiểm tra 1 file bất kỳ):
    python3 scripts/kiem_tra_wo.py plans/phong-27072026.json [plans/khac.json ...]
"""
import sys, json
from pathlib import Path
from collections import defaultdict


def kiem_tra_plan(path):
    """Trả về list các dòng lỗi (tiếng Việt, LUÔN nêu rõ đúng job/vị trí nào
    lỗi — không báo chung chung "có lỗi" mà không biết sửa ở đâu). Rỗng = OK."""
    loi = []
    try:
        plan = json.loads(Path(path).read_text(encoding='utf-8'))
    except Exception as e:
        return [f"Không đọc được file JSON: {e}"]

    tasks = plan.get('tasks', [])

    # 1. TRÙNG ID — lỗi nghiêm trọng nhất, đã gây kẹt nút Gửi thật ngoài đời
    # (Phong, 27/07/2026). App tra cứu/ghi kết quả theo đúng field "id", trùng
    # id = 2 task chia sẻ chung 1 ô kết quả, 1 cái kẹt "pending" vĩnh viễn.
    theo_id = defaultdict(list)
    for i, t in enumerate(tasks):
        theo_id[t.get('id')].append((i, t))
    for tid, items in theo_id.items():
        if len(items) > 1:
            chi_tiet = '; '.join(
                f"{t.get('lsx', '?')} · bể {t.get('be_nhan') or '—'} (vị trí {i + 1}/{len(tasks)})"
                for i, t in items)
            loi.append(f"TRÙNG ID \"{tid}\" ở {len(items)} lệnh khác nhau — {chi_tiet}")

    # 2. Thiếu id hoặc thiếu mã LSX — nêu rõ vị trí + các thông tin còn lại để
    # dễ tìm đúng dòng trong file mà sửa.
    for i, t in enumerate(tasks):
        nhan_dang = f"vị trí {i + 1}/{len(tasks)} (bể {t.get('be_nhan') or '—'})"
        if not t.get('id'):
            loi.append(f"Thiếu id ở {nhan_dang}, lsx={t.get('lsx', '?')}")
        if not t.get('lsx'):
            loi.append(f"Thiếu mã LSX ở {nhan_dang}, id={t.get('id', '?')}")

    return loi


def main():
    if len(sys.argv) < 2:
        print("Dùng: python3 scripts/kiem_tra_wo.py <file1.json> [file2.json ...]")
        sys.exit(1)

    co_loi = False
    for path in sys.argv[1:]:
        loi = kiem_tra_plan(path)
        if loi:
            co_loi = True
            print(f"\n❌ {path}:")
            for l in loi:
                print(f"   - {l}")
        else:
            print(f"✅ {path}: không phát hiện lỗi")

    if co_loi:
        print("\n🚫 CÓ LỖI — KHÔNG phát hành WO cho tới khi sửa xong (xem chi tiết ở trên).")
        sys.exit(1)
    print("\n✅ Tất cả file đều hợp lệ.")


if __name__ == '__main__':
    main()
