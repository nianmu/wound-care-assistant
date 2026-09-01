"""loader 页码标记解析测试。"""
import pytest

from app.ingestion.loader import load_document


def test_parse_page_markers(tmp_path):
    f = tmp_path / "教材.txt"
    f.write_text(
        "@@PAGE:1@@\n第一页内容。\n\n@@PAGE:2@@\n第二页内容。\n\n@@PAGE:3@@\n第三页内容。\n",
        encoding="utf-8",
    )
    docs = load_document(f, source_label="护理学")
    assert len(docs) == 3
    assert [d.metadata["page"] for d in docs] == [1, 2, 3]
    assert docs[0].page_content == "第一页内容。"
    assert docs[2].page_content == "第三页内容。"


def test_no_markers_backward_compat(tmp_path):
    """无标记的旧 txt 仍可整体加载（无 page 字段）。"""
    f = tmp_path / "旧教材.txt"
    f.write_text("第一段。第二段。", encoding="utf-8")
    docs = load_document(f, source_label="旧教材")
    assert len(docs) == 1
    assert "page" not in docs[0].metadata


def test_page_with_multiline_content(tmp_path):
    """跨行页内容应完整保留。"""
    f = tmp_path / "多行.txt"
    f.write_text("@@PAGE:5@@\n第一行\n第二行\n第三行\n", encoding="utf-8")
    docs = load_document(f)
    assert docs[0].metadata["page"] == 5
    assert "第二行" in docs[0].page_content