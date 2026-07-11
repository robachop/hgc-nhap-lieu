#!/usr/bin/env python3
"""
regen_phong_ha.py — Tạo lại kế hoạch Phong + Hà từ sheet "Dãy kéo rút",
KHÔNG đụng file JSON của Miên/Hao (khác với tao_ke_hoach.py main() vốn
ghi đè cả 4 người).

Lý do tồn tại: Miên (từ 2026-06-28) dùng nguồn riêng (gen_mien_tuan.py,
sheet "Tuần XX") và Hao nhập tay — nếu chạy tao_ke_hoach.py main() sẽ xoá
mất kế hoạch Miên/Hao đang đúng và tạo lại kiểu suy luận S500 đã lỗi thời.

Trước đây script này sống tạm ở /tmp (bị xoá mỗi khi Mac restart, phải
gõ lại từ đầu — xem _Giao Bang.md phiên 2026-07-02 phiên 5). Từ 2026-07-11
lưu cố định vào scripts/ trong repo để không mất nữa.

Dùng:
    python3 scripts/regen_phong_ha.py "<file Dãy kéo rút.xlsx>" YYYY-MM-DD
"""
import sys, datetime, subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from tao_ke_hoach import read_day_keo_rut, append_pt00, deploy_worker


def main():
    if len(sys.argv) < 3:
        print("Dùng: python3 scripts/regen_phong_ha.py <file.xlsx> YYYY-MM-DD")
        sys.exit(1)

    excel_path = Path(sys.argv[1])
    target = datetime.date.fromisoformat(sys.argv[2])

    day_vn = ['Thứ 2', 'Thứ 3', 'Thứ 4', 'Thứ 5', 'Thứ 6', 'Thứ 7', 'CN'][target.weekday()]
    print(f"\n📅 Tạo lại Phong + Hà cho: {day_vn} {target.strftime('%d/%m/%Y')}")
    print(f"📊 Đọc sheet 'Dãy kéo rút'...")

    by_worker = read_day_keo_rut(excel_path)
    append_pt00(by_worker, 'Ha')

    # Chỉ deploy Phong + Ha. deploy() sinh trang cho toàn bộ WORKERS, nên
    # ta giới hạn danh sách truyền vào — dùng phiên bản rút gọn thay vì
    # gọi thẳng deploy() (vốn lặp qua WORKERS toàn cục và sẽ tạo cả trang
    # Mien/Hao trống nếu không có trong by_worker).
    files_to_add = []
    for worker in ('Phong', 'Ha'):
        tasks = by_worker.get(worker, [])
        plan_file, html_file, url = deploy_worker(target, worker, tasks)
        files_to_add += [f"plans/{plan_file}", html_file]
        print(f"  ✅ {worker}: {len(tasks)} tasks → {html_file}")

    repo_dir = Path(__file__).parent.parent
    date_str = target.strftime("%d/%m/%Y")
    msg = f"Ke hoach {date_str}: " + ", ".join(f"{w}={len(by_worker.get(w, []))}" for w in ('Phong', 'Ha'))
    add_cmd = " ".join(files_to_add)
    result = subprocess.run(
        f'cd "{repo_dir}" && git add {add_cmd} && git commit -m "{msg}" && git push origin main',
        shell=True, capture_output=True, text=True
    )
    if result.returncode == 0:
        print(f"  ✅ Đã push lên GitHub Pages")
    else:
        print(f"  ⚠️  Git: {result.stdout.strip()} {result.stderr.strip()}")

    slug = target.strftime("%d%m%Y")
    print(f"\n{'═'*54}")
    print(f"  ✅ XONG! Link:")
    print(f"  Phong   : https://robachop.github.io/hgc-nhap-lieu/kehoach-phong-{slug}.html")
    print(f"  Ha      : https://robachop.github.io/hgc-nhap-lieu/kehoach-ha-{slug}.html")
    print(f"{'═'*54}\n")


if __name__ == '__main__':
    main()
