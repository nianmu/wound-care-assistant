"""EPUB → UTF-8 txt 转换（开发机运行）。轻量实现：解压 EPUB(zip) 提取 HTML 纯文本。

带页码标记输出：每个 HTML 内容块前插入 @@PAGE:N@@（EPUB 无物理页码，
按内容顺序编号，定位到块级别）。

用法:
    python tools/convert_epub.py 输入.epub [输出目录或路径]
"""
from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

from bs4 import BeautifulSoup

PAGE_MARK = "@@PAGE:{}@@"


def convert_epub(epub_path: str | Path, out: str | Path | None = None) -> Path:
    epub = Path(epub_path)
    if not epub.exists():
        raise FileNotFoundError(epub)

    if out is None:
        out = epub.with_suffix(".txt")
    else:
        out = Path(out)
        if out.suffix == "" or out.is_dir():
            out = out / f"{epub.stem}.txt"
    out.parent.mkdir(parents=True, exist_ok=True)

    texts: list[str] = []
    with zipfile.ZipFile(epub) as z:
        # 只处理 XHTML/HTML 文件
        html_names = sorted(
            n for n in z.namelist()
            if n.lower().endswith((".xhtml", ".html", ".htm"))
            and not n.startswith(("META-INF", "mimetype"))
        )
        for idx, name in enumerate(html_names):
            texts.append(PAGE_MARK.format(idx + 1))
            soup = BeautifulSoup(z.read(name), "lxml")
            for tag in soup(["script", "style"]):
                tag.decompose()
            texts.append(soup.get_text("\n", strip=True))

    text = "\n\n".join(texts)
    text = re.sub(r"\n{3,}", "\n\n", text)
    out.write_text(text, encoding="utf-8")
    return out


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    result = convert_epub(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    print(f"OK → {result}")