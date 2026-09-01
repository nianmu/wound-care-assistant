"""文档加载：服务器端只接收 .txt/.md 纯文本。

PDF/EPUB 一律在开发机用 tools/ 转换（见 tools/README.md），
解析重活不放在 2C2G 服务器上。

页码标记：转换脚本在每页文本前插入 @@PAGE:N@@ 行，此处解析后写入
每个 Document 的 metadata['page']，检索时可定位原文页码。
"""
from __future__ import annotations

import re
from pathlib import Path

from langchain_core.documents import Document

# 支持的类型（服务器只收纯文本）
SUPPORTED = {".txt", ".md"}

# 页码标记：@@PAGE:12@@（tools/ 转换脚本输出）
PAGE_MARK_RE = re.compile(r"^@@PAGE:(\d+)@@\s*$", re.MULTILINE)

# 原始空文档标记：@@EMPTY@@（保留为噪音，不参与检索）
EMPTY_MARK_RE = re.compile(r"^@@EMPTY@@\s*$", re.MULTILINE)


def _parse_pages(text: str) -> list[tuple[int | None, str]]:
    """按页码标记把文本切成 [(page, content), ...]。

    无任何标记时返回单段 (None, 全文)，兼容无页码的旧 txt。
    """
    positions = list(PAGE_MARK_RE.finditer(text))
    if not positions:
        return [(None, text)]
    segments: list[tuple[int | None, str]] = []
    for i, m in enumerate(positions):
        page = int(m.group(1))
        end = positions[i + 1].start() if i + 1 < len(positions) else len(text)
        # 标记行之后、下一标记之前的内容
        content = text[m.end() : end].strip("\n")
        # 去掉内容里可能残留的标记行（非行首情况）
        content = PAGE_MARK_RE.sub("", content).strip()
        if content.strip():
            segments.append((page, content))
    return segments


def load_document(path: Path, source_label: str | None = None) -> list[Document]:
    """加载单个纯文本文件为 LangChain Document 列表（每个分页一段，带页码）。"""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED:
        raise ValueError(f"不支持的类型 {suffix}（服务器仅接收 {sorted(SUPPORTED)}）")
    text = path.read_text(encoding="utf-8")
    label = source_label or path.stem
    docs: list[Document] = []
    for page, content in _parse_pages(text):
        content = content.strip()
        if not content:
            continue
        meta = {"source": label, "file_path": str(path)}
        if page is not None:
            meta["page"] = page
        docs.append(Document(page_content=content, metadata=meta))
    return docs


def load_txt_files(directory: Path) -> list[Document]:
    """批量加载 data/raw/ 下的所有 txt/md。"""
    docs: list[Document] = []
    for p in sorted(directory.iterdir()):
        if p.suffix.lower() in SUPPORTED:
            docs.extend(load_document(p, source_label=p.stem))
    return docs