"""切片与加载器单元测试（纯本地，不依赖任何 API Key）。"""
import os

os.environ.setdefault("DEEPSEEK_API_KEY", "sk-test")
os.environ.setdefault("SILICONFLOW_API_KEY", "sk-test")
# 测试使用独立的临时向量库目录
os.environ.setdefault("CHROMA_PERSIST_DIR", "./.test_chroma")

from langchain_core.documents import Document  # noqa: E402

from app.ingestion.chunker import make_splitter, split_documents  # noqa: E402
from app.ingestion.loader import load_document  # noqa: E402


def test_chunker_respects_size_and_overlap():
    splitter = make_splitter(chunk_size=100, chunk_overlap=20)
    text = "回肠造口护理。" * 50  # 250 字符
    chunks = splitter.split_text(text)
    assert len(chunks) >= 3
    assert all(len(c) <= 100 for c in chunks)


def test_chunker_breaks_at_chinese_boundaries():
    splitter = make_splitter(chunk_size=60, chunk_overlap=0)
    text = "第一段叙述造口评估。第二段叙述皮肤护理。第三段叙述更换频率。"
    chunks = splitter.split_text(text)
    # 不出现把句子拦腰截断成残句的情况
    assert all("。" not in c[:-1] or c.endswith("。") for c in chunks)


def test_split_documents_adds_metadata(tmp_path):
    doc = Document(page_content="伤口护理的评估要点。", metadata={"source": "伤口护理学"})
    chunks = split_documents([doc])
    assert chunks
    assert all("chunk_index" in c.metadata for c in chunks)


def test_txt_loader(tmp_path):
    f = tmp_path / "造口护理学.txt"
    f.write_text("尿液性皮炎的处理原则。", encoding="utf-8")
    docs = load_document(f, source_label="造口护理学")
    assert len(docs) == 1
    assert docs[0].metadata["source"] == "造口护理学"
    assert "尿液性皮炎" in docs[0].page_content


def test_txt_loader_rejects_pdf(tmp_path):
    """服务器不解析 PDF，应明确拒绝。"""
    import pytest

    from app.ingestion.loader import load_document

    # 模拟一个 PDF 文件内容（即使是有效 PDF 也应被拒绝——解析在开发机做）
    bad = tmp_path / "教材.pdf"
    bad.write_bytes(b"%PDF-1.4 fake")
    with pytest.raises(ValueError):
        load_document(bad)