"""文字型 PDF → UTF-8 txt 转换（在开发机运行，勿部署到服务器）。

带页码标记输出：每页文本前插入 @@PAGE:N@@ 行，服务器解析后可在回答中
定位原文页码。

用法:
    python tools/convert_pdf.py 输入.pdf [输出目录或路径]

说明:
    - 文字型 PDF 直接用 PyMuPDF 提取文本
    - 扫描版 PDF（无文字层）请用 convert_pdf_ocr.py（需 Tesseract）
"""
from __future__ import annotations

import sys
from pathlib import Path

PAGE_MARK = "@@PAGE:{}@@"


def convert_pdf(pdf_path: str | Path, out: str | Path | None = None) -> Path:
    import fitz  # PyMuPDF

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

    doc = fitz.open(pdf)
    parts = []
    for page in doc:
        parts.append(PAGE_MARK.format(page.number + 1))
        parts.append(page.get_text("text"))
    doc.close()

    # 去除空白过多的空行，保留段落
    raw = "\n".join(parts)
    lines = [ln.rstrip() for ln in raw.splitlines()]
    text = "\n".join(lines).strip()
    out.write_text(text, encoding="utf-8")
    return out


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    result = convert_pdf(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    print(f"OK → {result}")