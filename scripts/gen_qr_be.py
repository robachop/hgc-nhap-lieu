#!/usr/bin/env python3
"""
gen_qr_be.py — Sinh 220 mã QR (1 mã/bể L001-L220), mỗi mã dẫn tới trang
`hientrang.html?be=Lxxx` (xem `be_status.py`) — Tim in ra và dán tại từng
bể để khách tham quan quét xem hiện trạng.

Xuất ra:
  - 220 file PNG (1 file/bể)
  - 1 trang `qr_be_in.html` — lưới toàn bộ 220 QR kèm nhãn tên bể, có CSS
    @media print để in trực tiếp (không cần in 220 file lẻ)

⚠️ Output KHÔNG commit vào repo git — đây là tài nguyên in ấn, lưu tại
vault `90 Đính kèm/QR Bể/` theo đúng quy tắc lưu file ảnh/đính kèm.

Cần cài trước: pip install "qrcode[pil]"

Dùng:
    python3 scripts/gen_qr_be.py --out-dir "<đường dẫn vault>/90 Đính kèm/QR Bể"
"""
import argparse
from pathlib import Path

import qrcode

SO_BE = 220
BASE_URL = "https://robachop.github.io/hgc-nhap-lieu/hientrang.html?be="


def be_ids():
    return [f"L{n:03d}" for n in range(1, SO_BE + 1)]


def sinh_qr_png(out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    for be_id in be_ids():
        url = BASE_URL + be_id
        img = qrcode.make(url, box_size=8, border=2)
        img.save(out_dir / f"qr-{be_id}.png")
    print(f"✅ Đã sinh {SO_BE} file PNG vào {out_dir}")


TRANG_IN_TEMPLATE = """<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<title>QR Bể — In dán tại nhà máy</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',Arial,sans-serif;background:#f1f5f9;padding:20px}}
h1{{font-size:16px;margin-bottom:4px}}
.sub{{font-size:12px;color:#64748b;margin-bottom:16px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:14px}}
.tem{{background:#fff;border:1.5px solid #e2e8f0;border-radius:10px;padding:10px;
      text-align:center;break-inside:avoid}}
.tem img{{width:100%;height:auto;display:block;margin-bottom:6px}}
.tem .ten{{font-size:15px;font-weight:800;color:#0f172a}}
@media print {{
  body{{background:#fff;padding:0}}
  .grid{{gap:8px}}
  .tem{{border:1px solid #94a3b8;page-break-inside:avoid}}
}}
</style>
</head>
<body>
<h1>QR Bể — HGC Nhà máy Hương Giang</h1>
<div class="sub">{so_be} bể (L001-L{so_be:03d}) · Quét để xem hiện trạng bể · In trang này ra giấy, cắt theo từng ô, dán tại bể tương ứng</div>
<div class="grid">
{items}
</div>
</body>
</html>
"""

TEM_TEMPLATE = '  <div class="tem"><img src="qr-{be_id}.png" alt="QR {be_id}"><div class="ten">{be_id}</div></div>'


def sinh_trang_in(out_dir: Path):
    items = "\n".join(TEM_TEMPLATE.format(be_id=b) for b in be_ids())
    html = TRANG_IN_TEMPLATE.format(so_be=SO_BE, items=items)
    (out_dir / "qr_be_in.html").write_text(html, encoding="utf-8")
    print(f"✅ Đã sinh trang in {out_dir / 'qr_be_in.html'}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True, help="Thư mục lưu 220 PNG + trang in")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    sinh_qr_png(out_dir)
    sinh_trang_in(out_dir)


if __name__ == "__main__":
    main()
