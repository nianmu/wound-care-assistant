"""文本切片：500 字符/块、50 重叠，按中文自然边界切分。"""
from __future__ import annotations

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
# 中文优先按段落/句号/逗号断句，保证语义完整
SEPARATORS = ["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""]


def make_splitter(
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=SEPARATORS,
        length_function=len,
    )


def split_documents(docs: list[Document]) -> list[Document]:
    """切片并补齐元数据（chunk 序号 / 来源 / 全文定位标记）。"""
    splitter = make_splitter()
    chunks = splitter.split_documents(docs)
    for i, c in enumerate(chunks):
        c.metadata.setdefault("chunk_index", i)
    return chunks