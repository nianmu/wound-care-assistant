"""判分与答题记录：判分、错题入库、题目统计。"""
from __future__ import annotations

from app.exam import store


def grade(
    questions: list[dict],
    answers: list[list[str]],
    mode: str = "practice",
    topic: str | None = None,
) -> dict:
    """判分。answers[i] 为第 i 题的作答（如 ["B"] 或 ["A","C"]）。

    - 单选/案例：完全匹配才对
    - 多选：与标准答案集合完全一致才对（多选/少选均错）
    返回结果含每题对错与解析，并落库：错题本 + 题目统计 + 答题记录。
    """
    assert len(questions) == len(answers), "题目与答案数量不匹配"
    correct_count = 0
    details = []
    for q, user_ans in zip(questions, answers):
        std = set(q["answer"])
        user = set(user_ans or [])
        is_correct = user == std
        if is_correct:
            correct_count += 1
        details.append({
            "question_id": q["id"],
            "qtype": q.get("qtype"),
            "topic": q.get("topic"),
            "question": q.get("question"),
            "options": q.get("options"),
            "answer": q["answer"],
            "user_answer": sorted(user),
            "correct": is_correct,
            "explanation": q.get("explanation", ""),
            "source": q.get("source"),
            "page": q.get("page"),
        })
        # 落库
        store.record_answer(q["id"], is_correct)
        if not is_correct:
            store.add_wrong(q["id"], sorted(user))
        else:
            store.mark_wrong_resolved(q["id"])

    total = len(questions)
    score = round(correct_count / total * 100) if total else 0
    attempt_id = store.save_attempt(
        mode=mode, topic=topic, total=total, correct=correct_count, score=score, detail=details
    )
    return {
        "attempt_id": attempt_id,
        "total": total,
        "correct": correct_count,
        "score": score,
        "details": details,
    }