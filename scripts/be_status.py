#!/usr/bin/env python3
"""
be_status.py — Xuất trạng thái hiện tại của 220 bể chượp nguồn (L001-L220)
ra file `be-status.json` để trang `hientrang.html` (khách quét QR tại bể)
đọc và hiển thị.

KHÔNG tạo kế hoạch/task thật, chỉ đọc actual (KetQua) và phân loại — dùng
lại nguyên `phan_loai()` (lich_gop.py) + `parse_lsx()` (du_bao_mien.py) để
không lặp lại logic phân loại mã LSX đã có sẵn.

Câu chữ hiển thị cho khách (dict CAU_THAN_THIEN bên dưới) cố tình để RIÊNG,
dễ sửa — AI Công việc có thể tinh chỉnh lời văn sau mà không đụng logic.

Dùng:
    python3 scripts/be_status.py --ketqua /tmp/ketqua.xlsx --out be-status.json
"""
import argparse, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import pandas as pd
from doi_chieu import doc_actual
from du_bao_mien import parse_lsx
from lich_gop import phan_loai

COT_NGAY = "Ngày thực hiện"
COT_LSX = "Lệnh sản xuất"
COT_BE = "Bể / xe"
COT_HOAN_THANH = "Completion time"

SO_BE = 220  # L001 .. L220

# Nhãn kỹ thuật (từ phan_loai) -> câu tiếng Việt thân thiện cho khách tham
# quan. Nhóm "S-Đảo trộn" có {ck}/{ngay} chèn từ parse_lsx(). Thiếu nhãn nào
# trong dict này -> dùng thẳng nhãn kỹ thuật (không bao giờ crash/thiếu chữ).
CAU_THAN_THIEN = {
    "S-Mở vòng mới": "Vừa mở vòng ủ chượp mới",
    "S-Bể trống": "Bể đang trống, chờ nhập cá",
    "S-Nhập cá": "Đang nhập cá",
    "S-Phân bổ cá": "Đang phân bổ cá vào bể",
    "S-Bổ sung muối": "Đang bổ sung muối",
    "S-Rút kiệt gài nén": "Đang rút kiệt, chuẩn bị gài nén",
    "S-Gài nén": "Vừa gài nén",
    "S-Nước bổi": "Đang xử lý nước bổi",
    "S-Đảo trộn": "Đang đảo trộn — chu kỳ {ck}, ngày {ngay}",
    "S-Trống": "Đang chờ (giữa giai đoạn ủ)",
    "C-Cá chín": "Cá đã chín, chuẩn bị rút kiệt",
    "C-Rút kiệt đảo trong": "Đang rút kiệt đảo trong",
    "C-Tách cốt": "Đang tách cốt (rút nước cốt)",
    "Phá xác": "Đã phá xác, chuẩn bị mở vòng ủ mới",
}
CHUA_CO_DU_LIEU = "Chưa có dữ liệu nhập liệu cho bể này"


def be_ids():
    return [f"L{n:03d}" for n in range(1, SO_BE + 1)]


def trang_thai_cho_be(df, be_id):
    sub = df[df[COT_BE] == be_id]
    if sub.empty:
        return {"trang_thai": CHUA_CO_DU_LIEU, "cap_nhat": None}

    sub = sub.sort_values([COT_NGAY, COT_HOAN_THANH])
    dong_moi_nhat = sub.iloc[-1]
    lsx = dong_moi_nhat[COT_LSX]
    nhan = phan_loai(lsx)

    if nhan is None:
        trang_thai = str(lsx)
    elif nhan == "S-Đảo trộn":
        parsed = parse_lsx(lsx)
        if parsed:
            ck, ngay = parsed
            trang_thai = CAU_THAN_THIEN[nhan].format(ck=ck, ngay=ngay)
        else:
            trang_thai = nhan
    else:
        trang_thai = CAU_THAN_THIEN.get(nhan, nhan)

    ngay_thuc_hien = dong_moi_nhat[COT_NGAY]
    cap_nhat = ngay_thuc_hien.strftime("%Y-%m-%d") if pd.notna(ngay_thuc_hien) else None

    return {"trang_thai": trang_thai, "cap_nhat": cap_nhat}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ketqua", required=True, help="File KetQua đã tải (.xlsx)")
    ap.add_argument("--out", default=str(Path(__file__).parent.parent / "be-status.json"))
    args = ap.parse_args()

    df = doc_actual(args.ketqua)
    df[COT_NGAY] = pd.to_datetime(df[COT_NGAY], errors="coerce")

    ket_qua = {}
    dem_co_du_lieu = 0
    for be_id in be_ids():
        ket_qua[be_id] = trang_thai_cho_be(df, be_id)
        if ket_qua[be_id]["trang_thai"] != CHUA_CO_DU_LIEU:
            dem_co_du_lieu += 1

    Path(args.out).write_text(
        json.dumps(ket_qua, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"✅ Đã xuất {args.out}: {SO_BE} bể, {dem_co_du_lieu} bể có dữ liệu thật")


if __name__ == "__main__":
    main()
