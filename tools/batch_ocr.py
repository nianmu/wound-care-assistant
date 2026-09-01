"""批量 OCR 扫描版 PDF → UTF-8 txt（RapidOCR GPU 优先，开发机后台任务）。

用法:
    python tools/batch_ocr.py [dpi=280]
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

# 允许直接运行（python tools/batch_ocr.py）时按文件路径导入
sys.path.insert(0, str(Path(__file__).resolve().parent))

from convert_pdf_gpu import convert_pdf_ocr  # noqa: E402

# 待处理的三本扫描版教材（data/raw 下）
TARGETS = [
    "伤口护理学",
    "伤口造口失禁患者个案护理",
    "失禁护理学",
]


def main() -> None:
    dpi = int(sys.argv[1]) if len(sys.argv) > 1 else 280
    raw = Path(__file__).resolve().parent.parent / "data" / "raw"
    results: list[str] = []
    for keyword in TARGETS:
        pdfs = [p for p in raw.glob("*.pdf") if keyword in p.name]
        if not pdfs:
            results.append(f"[跳过] 未找到包含「{keyword}」的 PDF")
            continue
        pdf = pdfs[0]
        out = raw / f"{keyword}.txt"
        print(f"\n===== 开始: {pdf.name} → {out.name} =====", flush=True)
        t0 = time.time()
        try:
            convert_pdf_ocr(pdf, out, dpi=dpi)
            chars = len(out.read_text(encoding="utf-8")) if out.exists() else 0
            results.append(f"[完成] {keyword}: {chars} 字符, 用时 {(time.time()-t0)/60:.1f} 分钟")
        except Exception as e:  # noqa: BLE001 - 批量任务要容错继续
            results.append(f"[失败] {keyword}: {e}")
    print("\n================= 汇总 =================", flush=True)
    for r in results:
        print(r, flush=True)


if __name__ == "__main__":
    main()