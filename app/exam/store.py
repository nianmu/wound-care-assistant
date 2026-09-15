"""考试模块 SQLite 存储（Python 内置 sqlite3，零依赖）+ 账户体系 users 表。

表：
- users            用户（账户体系，B 模式）
- exam_questions   题目缓存（公共，scope_key 复用）
- exam_attempts    做题记录/考试成绩（按 user_id 隔离）
- wrong_book       错题本（按 user_id 隔离）
- question_stats   题目统计（按 user_id 隔离）
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from app.config import get_settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  display_name TEXT,
  is_admin INTEGER NOT NULL DEFAULT 0,
  created_at TEXT
);
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
  question_id INTEGER NOT NULL,
  user_id INTEGER NOT NULL DEFAULT 0,
  attempts INTEGER DEFAULT 0,
  correct INTEGER DEFAULT 0,
  PRIMARY KEY (question_id, user_id)
);
"""

_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_exam_scope ON exam_questions(scope_key);
CREATE INDEX IF NOT EXISTS idx_wrong_user ON wrong_book(user_id, resolved);
CREATE INDEX IF NOT EXISTS idx_stats_user ON question_stats(user_id);
CREATE INDEX IF NOT EXISTS idx_attempts_user ON exam_attempts(user_id);
"""

# 需幂等补的列：个人数据表 user_id；users.is_admin（管理员标记）
_PERSONAL_COLUMNS = {
    "users": "is_admin",
    "exam_attempts": "user_id",
    "wrong_book": "user_id",
    "question_stats": "user_id",
}


def _db_path() -> Path:
    d = get_settings().data_dir
    d.mkdir(parents=True, exist_ok=True)
    return d / "exam.db"


def _migrate_schema(conn: sqlite3.Connection) -> None:
    """幂等补列/重建：个人数据表缺 user_id 时加上（存量行默认 0 = 未归属历史数据）。"""
    for table, col in _PERSONAL_COLUMNS.items():
        cols = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
        if col not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} INTEGER NOT NULL DEFAULT 0")

    # question_stats 旧表是单列主键 (question_id)，无法按 (question_id, user_id) 统计
    # → 检测到非复合主键时重建（幂等），数据带 user_id 迁入
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='question_stats'"
    ).fetchone()
    if row and "primary key (question_id, user_id)" not in (row["sql"] or "").lower():
        conn.execute("ALTER TABLE question_stats RENAME TO question_stats_old")
        conn.execute(
            """CREATE TABLE question_stats (
                 question_id INTEGER NOT NULL,
                 user_id INTEGER NOT NULL DEFAULT 0,
                 attempts INTEGER DEFAULT 0,
                 correct INTEGER DEFAULT 0,
                 PRIMARY KEY (question_id, user_id)
               )"""
        )
        conn.execute(
            """INSERT INTO question_stats (question_id, user_id, attempts, correct)
               SELECT question_id, user_id, attempts, correct FROM question_stats_old"""
        )
        conn.execute("DROP TABLE question_stats_old")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    _migrate_schema(conn)
    conn.executescript(_INDEXES)
    return conn


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


# ---------- 用户（账户体系） ----------

def user_count() -> int:
    """全部用户数（含管理员）。"""
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]


def normal_user_count() -> int:
    """普通用户数（不含管理员）——"首个注册用户接管历史"以普通用户计，
    管理员（系统引导创建）不影响家人成为首个用户。"""
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) AS n FROM users WHERE is_admin=0").fetchone()["n"]


def get_admin() -> dict | None:
    """现有管理员（is_admin=1）。"""
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE is_admin=1 LIMIT 1").fetchone()
    return dict(row) if row else None


def ensure_admin(password_hash: str, display_name: str = "系统管理员") -> dict:
    """引导创建唯一的系统管理员（username=admin，is_admin=1）。

    已存在管理员时不重复创建。返回管理员用户 dict。
    """
    existing = get_admin()
    if existing:
        return existing
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO users (username, password_hash, display_name, is_admin, created_at)
               VALUES ('admin', ?, ?, 1, ?)""",
            (password_hash, display_name, _now()),
        )
        uid = cur.lastrowid
    return get_user_by_id(uid)


def create_user(username: str, password_hash: str, display_name: str | None) -> int:
    """建用户，返回 id；用户名重复抛 ValueError。"""
    try:
        with get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO users (username, password_hash, display_name, created_at) VALUES (?,?,?,?)",
                (username, password_hash, display_name, _now()),
            )
            return cur.lastrowid
    except sqlite3.IntegrityError:
        raise ValueError("用户名已存在")


def get_user_by_id(uid: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    return dict(row) if row else None


def get_user_by_username(username: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    return dict(row) if row else None


def migrate_legacy_to_user(uid: int) -> dict:
    """首个用户注册时调用：把 user_id=0 的历史成绩/错题/统计归给该用户。

    返回迁移条数；重复调用无副作用（没有 user_id=0 的行可迁）。
    """
    with get_conn() as conn:
        counts = {}
        for table in ("exam_attempts", "wrong_book", "question_stats"):
            cur = conn.execute(f"UPDATE {table} SET user_id=? WHERE user_id=0", (uid,))
            counts[table] = cur.rowcount
    return counts


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


# ---------- 答题记录（按用户） ----------

def save_attempt(mode: str, topic: str, total: int, correct: int, score: float, detail: list, user_id: int) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO exam_attempts (mode, topic, total, correct, score, detail, created_at, user_id) VALUES (?,?,?,?,?,?,?,?)",
            (mode, topic, total, correct, score, json.dumps(detail, ensure_ascii=False), _now(), user_id),
        )
        return cur.lastrowid


def get_attempts(user_id: int, limit: int = 50) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM exam_attempts WHERE user_id=? ORDER BY id DESC LIMIT ?", (user_id, limit)
        ).fetchall()
    return [dict(r) for r in rows]


# ---------- 错题本（按用户） ----------

def add_wrong(question_id: int, user_answer: list, user_id: int) -> None:
    """记一次做错：插入一条错题记录 + 累计同题未解决记录的 wrong_count（按用户）。"""
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO wrong_book (question_id, user_answer, wrong_count, last_wrong_at, resolved, user_id)
               VALUES (?,?,1,?,0,?)""",
            (question_id, json.dumps(user_answer, ensure_ascii=False), _now(), user_id),
        )
        # 若已有同题未解决记录则计数+1（按用户，与原逻辑一致）
        conn.execute(
            """UPDATE wrong_book SET wrong_count = wrong_count + 1, last_wrong_at = ?
               WHERE question_id=? AND user_id=? AND resolved=0""",
            (_now(), question_id, user_id),
        )


def mark_wrong_resolved(question_id: int, user_id: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE wrong_book SET resolved=1 WHERE question_id=? AND user_id=? AND resolved=0", (question_id, user_id)
        )


def get_wrong_questions(user_id: int, include_resolved: bool = False) -> list[dict]:
    """错题列表（按用户，带题目内容）。"""
    cond = "WHERE w.resolved=0 AND w.user_id=?" if not include_resolved else "WHERE w.user_id=?"
    with get_conn() as conn:
        rows = conn.execute(
            f"""SELECT q.*, w.wrong_count, w.last_wrong_at, w.user_answer, w.resolved
                FROM wrong_book w JOIN exam_questions q ON q.id = w.question_id
                {cond} ORDER BY w.last_wrong_at DESC""",
            (user_id,) if not include_resolved else (user_id,),
        ).fetchall()
    return [_row_to_q(r) | {"wrong_count": r["wrong_count"], "resolved": r["resolved"]} for r in rows]


def get_wrong_question_ids(user_id: int) -> list[int]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT question_id FROM wrong_book WHERE user_id=? AND resolved=0", (user_id,)
        ).fetchall()
    return [r["question_id"] for r in rows]


# ---------- 题目统计（按用户） ----------

def record_answer(question_id: int, is_correct: bool, user_id: int) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO question_stats (question_id, attempts, correct, user_id) VALUES (?,1,?,?)
               ON CONFLICT(question_id, user_id) DO UPDATE SET
                 attempts = attempts + 1,
                 correct = correct + ?""",
            (question_id, 1 if is_correct else 0, user_id, 1 if is_correct else 0),
        )


def topic_stats(user_id: int) -> list[dict]:
    """按主题的做题统计（学习报告用，按用户）。"""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT q.topic,
                      SUM(s.attempts) AS attempts,
                      SUM(s.correct)  AS correct
               FROM question_stats s JOIN exam_questions q ON q.id = s.question_id
               WHERE s.user_id=?
               GROUP BY q.topic ORDER BY attempts DESC""",
            (user_id,),
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