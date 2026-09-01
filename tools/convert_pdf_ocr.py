"""扫描版 PDF → UTF-8 txt 转换（OCR，开发机运行，需 Tesseract 中文包）。

带页码标记输出：每页文本前插入 @@PAGE:N@@ 行，服务器解析后可在回答中
定位原文页码。

前置要求（Windows）:
    choco install tesseract            # 或手动安装 https://github.com/UB-Mannheim/tesseract/wiki
    # 并在安装时勾选中文(简体)语言包；或安装后放置 chi_sim.traineddata 到 tessdata 目录

用法:
    python tools/convert_pdf_ocr.py 扫描版.pdf [输出目录或路径] [dpi=300]

说明:
    - 先尝试提取文字层；无文字层的页面自动走 OCR
    - 用 PyMuPDF 渲染页面 → 交给 tesseract 识别
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PAGE_MARK = "@@PAGE:{}@@"


def _page_has_text(page) -> bool:
    return bool(page.get_text("text").strip())


def _find_tesseract() -> str:
    """定位 tesseract：优先 PATH，其次探测常见 Windows 安装路径（不依赖 PATH 刷新）。"""
    exe = shutil.which("tesseract")
    if exe:
        return exe
    candidates = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",  # choco / UB-Mannheim 默认
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        r"D:\environment\Tesseract-OCR\tesseract.exe",
        r"D:\Program Files\Tesseract-OCR\tesseract.exe",
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    raise RuntimeError(
        "未找到 tesseract，请先安装（安装后若提示找不到，可设置环境变量 TESSERACT_CMD 指向 tesseract.exe）"
    )


def _ocr_image(img_path: Path, lang: str = "chi_sim+eng") -> str:
    tesseract = os.getenv("TESSERACT_CMD") or _find_tesseract()
    # --psm 3 = 全自动页面分割（中文书籍排版优于 psm 6 的固定块）
    proc = subprocess.run(
        [tesseract, str(img_path), "stdout", "-l", lang, "--psm", "3", "--dpi", "280"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if proc.returncode != 0:
        raise RuntimeError(f"tesseract 失败: {proc.stderr}")
    return proc.stdout


def convert_pdf_ocr(pdf_path: str | Path, out: str | Path | None = None, dpi: int = 300) -> Path:
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
    parts: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for i, page in enumerate(doc):
            parts.append(PAGE_MARK.format(i + 1))
            if _page_has_text(page):
                parts.append(page.get_text("text"))
                continue
            pix = page.get_pixmap(dpi=dpi)
            img = tmp / f"p{i:04d}.png"
            pix.save(img)
            parts.append(_ocr_image(img))
            print(f"[OCR] 第 {i + 1}/{len(doc)} 页完成", flush=True)
    doc.close()

    lines = [ln.rstrip() for ln in "\n".join(parts).splitlines()]
    out.write_text("\n".join(lines).strip(), encoding="utf-8")
    return out


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    dpi = int(sys.argv[3]) if len(sys.argv) > 3 else 300
    result = convert_pdf_ocr(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None, dpi)
    print(f"OK → {result}")