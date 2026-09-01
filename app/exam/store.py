"""考试模块 SQLite 存储（Python 内置 sqlite3，零依赖）。

表：
- exam_questions   题目缓存（scope_key 复用）
- exam_attempts    做题记录/考试成绩
- wrong_book       错题本
- question_stats   题目统计（正确率）
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from app.config import get_settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS exam_questions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  scope_key TEXT,
  qtype TEXT,
  topic TEXT,
  source TEXT,
  page INTEGER,
  question TEXT,
  options TEXT,
  answer TEXT,
  explanation TEXT,
  confidence REAL,
  used_count INTEGER DEFAULT 0,
  created_at TEXT
);
CREATE TABLE IF NOT EXISTS exam_attempts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  mode TEXT,
  topic TEXT,
  total INTEGER,
  correct INTEGER,
  score REAL,
  detail TEXT,
  created_at TEXT
);
CREATE TABLE IF NOT EXISTS wrong_book (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  question_id INTEGER,
  user_answer TEXT,
  wrong_count INTEGER DEFAULT 1,
  last_wrong_at TEXT,
  resolved INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS question_stats (
  question_id INTEGER PRIMARY KEY,
  attempts INTEGER DEFAULT 0,
  correct INTEGER DEFAULT 0
);
"""

_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_exam_scope ON exam_questions(scope_key);
CREATE INDEX IF NOT EXISTS idx_wrong_resolved ON wrong_book(resolved);
"""


def _db_path() -> Path:
    d = get_settings().data_dir
    d.mkdir(parents=True, exist_ok=True)
    return d / "exam.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    conn.executescript(_INDEXES)
    return conn


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


# ---------- 题目缓存 ----------

def cache_question(scope_key: str, q: dict) -> int:
    """缓存一道题，返回 id。"""
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO exam_questions
               (scope_key, qtype, topic, source, page, question, options, answer,
                explanation, confidence, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                scope_key, q.get("qtype"), q.get("topic"), q.get("source"), q.get("page"),
                q.get("question"), json.dumps(q.get("options", []), ensure_ascii=False),
                json.dumps(q.get("answer", []), ensure_ascii=False),
                q.get("explanation", ""), q.get("confidence", 0.0), _now(),
            ),
        )
        return cur.lastrowid


def get_questions_by_scope(scope_key: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM exam_questions WHERE scope_key=? ORDER BY id", (scope_key,)
        ).fetchall()
    return [_row_to_q(r) for r in rows]


def bump_used_count(qid: int) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE exam_questions SET used_count = used_count + 1 WHERE id=?", (qid,))


def touch_questions(qids: list[int]) -> None:
    if not qids:
        return
    with get_conn() as conn:
        conn.executemany(
            "UPDATE exam_questions SET used_count = used_count + 1 WHERE id=?", [(i,) for i in qids]
        )


def _row_to_q(r: sqlite3.Row) -> dict:
    return {
        "id": r["id"],
        "qtype": r["qtype"],
        "topic": r["topic"],
        "source": r["source"],
        "page": r["page"],
        "question": r["question"],
        "options": json.loads(r["options"]),
        "answer": json.loads(r["answer"]),
        "explanation": r["explanation"],
        "confidence": r["confidence"],
    }


# ---------- 答题记录 ----------

def save_attempt(mode: str, topic: str, total: int, correct: int, score: float, detail: list) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO exam_attempts (mode, topic, total, correct, score, detail, created_at) VALUES (?,?,?,?,?,?,?)",
            (mode, topic, total, correct, score, json.dumps(detail, ensure_ascii=False), _now()),
        )
        return cur.lastrowid


def get_attempts(limit: int = 50) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM exam_attempts ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


# ---------- 错题本 ----------

def add_wrong(question_id: int, user_answer: list) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO wrong_book (question_id, user_answer, wrong_count, last_wrong_at, resolved)
               VALUES (?,?,1,?,0)
               ON CONFLICT DO NOTHING""",
            (question_id, json.dumps(user_answer, ensure_ascii=False), _now()),
        )
        # 若已存在且未解决则计数+1
        conn.execute(
            """UPDATE wrong_book SET wrong_count = wrong_count + 1, last_wrong_at = ?
               WHERE question_id=? AND resolved=0""",
            (_now(), question_id),
        )


def mark_wrong_resolved(question_id: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE wrong_book SET resolved=1 WHERE question_id=? AND resolved=0", (question_id,)
        )


def get_wrong_questions(include_resolved: bool = False) -> list[dict]:
    """错题列表（带题目内容）。"""
    cond = "" if include_resolved else "WHERE w.resolved=0"
    with get_conn() as conn:
        rows = conn.execute(
            f"""SELECT q.*, w.wrong_count, w.last_wrong_at, w.user_answer, w.resolved
                FROM wrong_book w JOIN exam_questions q ON q.id = w.question_id
                {cond} ORDER BY w.last_wrong_at DESC"""
        ).fetchall()
    return [_row_to_q(r) | {"wrong_count": r["wrong_count"], "resolved": r["resolved"]} for r in rows]


def get_wrong_question_ids() -> list[int]:
    with get_conn() as conn:
        rows = conn.execute("SELECT question_id FROM wrong_book WHERE resolved=0").fetchall()
    return [r["question_id"] for r in rows]


# ---------- 题目统计 ----------

def record_answer(question_id: int, is_correct: bool) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO question_stats (question_id, attempts, correct) VALUES (?,1,?)
               ON CONFLICT(question_id) DO UPDATE SET
                 attempts = attempts + 1,
                 correct = correct + ?""",
            (question_id, 1 if is_correct else 0, 1 if is_correct else 0),
        )


def topic_stats() -> list[dict]:
    """按主题的做题统计（学习报告用）。"""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT q.topic,
                      SUM(s.attempts) AS attempts,
                      SUM(s.correct)  AS correct
               FROM question_stats s JOIN exam_questions q ON q.id = s.question_id
               GROUP BY q.topic ORDER BY attempts DESC"""
        ).fetchall()
    result = []
    for r in rows:
        attempts = r["attempts"] or 0
        result.append({
            "topic": r["topic"],
            "attempts": attempts,
            "correct": r["correct"] or 0,
            "accuracy": round((r["correct"] or 0) / attempts * 100) if attempts else 0,
        })
    return result