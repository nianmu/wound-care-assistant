"""扫描版 PDF → UTF-8 txt（RapidOCR GPU 优先，失败回退 Tesseract）。

开发机运行。带页码标记输出（@@PAGE:N@@），服务器解析后可在回答中定位原文页码。

前置：pip install rapidocr onnxruntime-directml（GPU / DML）
回退：Tesseract + chi_sim（CPU）

用法:
    python tools/convert_pdf_gpu.py 扫描版.pdf [输出目录或路径] [dpi=280]
"""
from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

PAGE_MARK = "@@PAGE:{}@@"


def _ocr_rapid(pdf_path: Path, out: Path, dpi: int, engine) -> tuple[int, list[str]]:
    """用 RapidOCR 逐页识别（GPU/DML）。返回 (识别页数, 全部页文本带页码标记)。"""
    import fitz  # PyMuPDF

    doc = fitz.open(pdf_path)
    parts: list[str] = []
    n_ocr = 0
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for i, page in enumerate(doc):
            parts.append(PAGE_MARK.format(i + 1))
            # 有文字层的页直接取文本，跳过 OCR
            direct = page.get_text("text").strip()
            if direct:
                parts.append(direct)
                continue
            pix = page.get_pixmap(dpi=dpi)
            img = tmp / f"p{i:04d}.png"
            pix.save(img)
            res = engine(str(img))
            texts = getattr(res, "txts", None) or [line[1] for line in (res or [])]
            parts.append("\n".join(texts).strip())
            n_ocr += 1
            if n_ocr % 20 == 0:
                print(f"  [RapidOCR] 已识别 {n_ocr} 页（总进度 {i+1}/{len(doc)} 页）", flush=True)
    doc.close()
    return n_ocr, parts


def _ocr_tesseract_fallback(pdf_path: Path, out: Path, dpi: int) -> None:
    """Tesseract 回退（CPU），复用 convert_pdf_ocr.py 的带页码实现。"""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from convert_pdf_ocr import convert_pdf_ocr as fallback

    fallback(pdf_path, out, dpi=dpi)


def convert_pdf_ocr(pdf_path: str | Path, out: str | Path | None = None, dpi: int = 280) -> Path:
    pdf = Path(pdf_path)
    if not pdf.exists():
        raise FileNotFoundError(pdf)

    if out is None:
        out = pdf.with_suffix(".txt")
    else:
        out = Path(out)
        if out.suffix == "" or out.is_dir():
            out = out / f"{pdf.stem}.txt"
    out.parent.mkdir(parents=True, exist_ok=True)

    # 主路径：RapidOCR（GPU/DML）
    try:
        from rapidocr import RapidOCR

        engine = RapidOCR(params={"EngineConfig.onnxruntime.use_dml": True})
        print("→ 使用 RapidOCR (GPU/DML)", flush=True)
        n_ocr, parts = _ocr_rapid(pdf, out, dpi, engine)
        lines = [ln.rstrip() for ln in "\n".join(parts).splitlines()]
        out.write_text("\n".join(lines).strip(), encoding="utf-8")
        print(f"  [完成] OCR 页数: {n_ocr}", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"→ RapidOCR 不可用（{e}），回退 Tesseract (CPU)", flush=True)
        _ocr_tesseract_fallback(pdf, out, dpi)
    return out


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    dpi = int(sys.argv[3]) if len(sys.argv) > 3 else 280
    t0 = time.time()
    result = convert_pdf_ocr(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None, dpi)
    print(f"OK → {result}（用时 {(time.time()-t0)/60:.1f} 分钟）")