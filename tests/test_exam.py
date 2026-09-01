"""考试模块单元测试：存储 + 判分（不调用外部 API）。"""
import os
import shutil

os.environ.setdefault("DEEPSEEK_API_KEY", "sk-test")
os.environ.setdefault("SILICONFLOW_API_KEY", "sk-test")
os.environ.setdefault("CHROMA_PERSIST_DIR", "./.test_chroma")
os.environ.setdefault("DATA_DIR", "./.test_data")

from pathlib import Path

import pytest

from app.exam import store


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    """每个测试用独立临时 sqlite 文件，避免用例间数据共享。"""
    db_file = tmp_path / "exam.db"
    monkeypatch.setattr(store, "_db_path", lambda: db_file)
    yield
    shutil.rmtree(tmp_path, ignore_errors=True)


from app.exam.grader import grade  # noqa: E402


def test_cache_and_get_question():
    qid = store.cache_question("scope-a", {
        "qtype": "single", "topic": "压疮分期", "source": "伤口护理学", "page": 12,
        "question": "压力性损伤2期的特征？", "options": ["A. 红斑", "B. 水疱", "C. 溃疡", "D. 坏疽"],
        "answer": ["B"], "explanation": "教材原文：2期为部分皮层缺损伴水疱", "confidence": 0.9,
    })
    cached = store.get_questions_by_scope("scope-a")
    assert len(cached) == 1
    assert cached[0]["id"] == qid
    assert cached[0]["topic"] == "压疮分期"
    assert cached[0]["answer"] == ["B"]


def test_grade_single_and_multi():
    q1 = {"id": 1, "answer": ["B"], "explanation": "正确", "source": "x", "topic": "t"}
    q2 = {"id": 2, "answer": ["A", "C"], "explanation": "多选", "source": "y", "topic": "t"}
    result = grade([q1, q2], [["B"], ["A", "C"]], mode="practice", topic="t")
    assert result["correct"] == 2
    assert result["score"] == 100

    # 多选少选算错
    result2 = grade([q1, q2], [["B"], ["A"]], mode="practice")
    assert result2["correct"] == 1
    assert result2["details"][1]["correct"] is False


def test_wrong_book_flow():
    qid = store.cache_question("scope-err", {
        "qtype": "single", "topic": "造口用品", "source": "造口护理学", "page": 5,
        "question": "回肠造口宜用哪种底盘？", "options": ["A. 平面", "B. 凸面", "C. 无", "D. 不确定"],
        "answer": ["B"], "explanation": "教材", "confidence": 0.8,
    })
    grade([{"id": qid, "answer": ["B"], "explanation": "x"}], [["A"]])
    wrongs = store.get_wrong_questions()
    assert any(w["id"] == qid for w in wrongs)
    assert wrongs[0]["wrong_count"] >= 1
    # 答对后标记解决
    store.mark_wrong_resolved(qid)
    assert all(w["id"] != qid for w in store.get_wrong_questions())


def test_topic_stats_aggregation():
    stats = store.topic_stats()
    assert isinstance(stats, list)