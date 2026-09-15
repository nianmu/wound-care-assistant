"""知识库来源名清理（一次性迁移脚本）。

背景：教材 txt 直接沿用了 z-library 的下载文件名（含作者串、站点后缀），
该名称会写进 LLM Prompt 与前端引用标签。

本脚本只改「元数据名称」，不重新向量化、不重新上传：
  1. 备份 chroma_db / data/exam.db
  2. 重命名 data/raw 下的教材文件（txt 及其转换源 pdf/epub）
  3. 改写 Chroma 里 source 与 file_path 元数据
  4. 改写 SQLite exam_questions.source（历史缓存题）

默认 dry-run，加 --apply 才真正执行。
"""
from __future__ import annotations

import shutil
import sqlite3
import sys
from pathlib import Path

import chromadb

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
ARCHIVE = RAW / "_archive"
STAMP = "2026-09-15"
COLLECTION = "wound_care_kb"

OLD_A = "伤口造口失禁常见皮肤问题护理方案 (彭飞等主编) (z-library.sk, 1lib.sk, z-lib.sk)"
OLD_B = "失禁护理学 (丁炎明著, Yanming Ding, 丁炎明主编, 丁炎明) (z-library.sk, 1lib.sk, z-lib.sk)"

# 来源名映射（Chroma / SQLite 通用）
SOURCE_MAP = {
    OLD_A: "伤口造口失禁常见皮肤问题护理方案",
    OLD_B: "失禁护理学",
}

# 文件重命名：(源文件名, 目标文件名)
FILE_RENAMES = [
    (f"{OLD_A}.txt", "伤口造口失禁常见皮肤问题护理方案.txt"),
    (f"{OLD_B}.txt", "失禁护理学.txt"),
    (f"{OLD_B}.pdf", "失禁护理学.pdf"),
    (f"{OLD_A}.epub", "伤口造口失禁常见皮肤问题护理方案.epub"),
    (
        "伤口护理学 (丁炎明著, 丁炎明主编, 丁炎明) (z-library.sk, 1lib.sk, z-lib.sk).pdf",
        "伤口护理学.pdf",
    ),
    (
        "伤口造口失禁患者个案护理 (张惠芹，黄漫容，郑美春主编, 张惠芹,黄漫容,郑美春主编, 张惠芹, 黄漫容, 郑美春) (z-library.sk, 1lib.sk, z-lib.sk).pdf",
        "伤口造口失禁患者个案护理.pdf",
    ),
]

# 内容逐字相同的重复 txt，先归档腾出目标名
DUP_TO_ARCHIVE = ("失禁护理学.txt", "失禁护理学 (旧转换·内容与长名版逐字相同).txt")

APPLY = "--apply" in sys.argv


def head(t: str) -> None:
    print()
    print("=" * 74)
    print(t)
    print("=" * 74)


# ---------- 0. 现状 ----------
head("0. 迁移前现状")
client = chromadb.PersistentClient(path=str(ROOT / "chroma_db"))
col = client.get_collection(COLLECTION)
print("Chroma 切片总数 :", col.count())

before = col.get(include=["metadatas"])
from collections import Counter

cnt = Counter(m.get("source", "?") for m in before["metadatas"])
for s, n in sorted(cnt.items()):
    mark = "  <- 待改名" if s in SOURCE_MAP else ""
    print(f"   {n:>5}  {s}{mark}")
print()
print("file_path 字段示例 :", before["metadatas"][0].get("file_path"))
print("元数据字段集合     :", sorted(before["metadatas"][0].keys()))

db = ROOT / "data" / "exam.db"
con = sqlite3.connect(db)
rows = con.execute("SELECT DISTINCT source FROM exam_questions WHERE source IS NOT NULL").fetchall()
print()
print("exam_questions 里的 source :", [r[0] for r in rows])

# ---------- 1. 备份 ----------
head("1. 备份")
bak_chroma = ROOT / f"chroma_db.bak-{STAMP}"
bak_db = db.with_name(f"exam.db.bak-{STAMP}")
if APPLY:
    if bak_chroma.exists():
        print("已存在，跳过 :", bak_chroma.name)
    else:
        shutil.copytree(ROOT / "chroma_db", bak_chroma)
        print("已备份 chroma_db ->", bak_chroma.name)
    if bak_db.exists():
        print("已存在，跳过 :", bak_db.name)
    else:
        shutil.copy2(db, bak_db)
        print("已备份 exam.db   ->", bak_db.name)
else:
    print("[dry-run] 将备份 chroma_db ->", bak_chroma.name)
    print("[dry-run] 将备份 exam.db   ->", bak_db.name)

# ---------- 2. 文件重命名 ----------
head("2. data/raw 文件重命名")
plan: list[tuple[Path, Path]] = []
if (RAW / DUP_TO_ARCHIVE[0]).exists():
    plan.append((RAW / DUP_TO_ARCHIVE[0], ARCHIVE / DUP_TO_ARCHIVE[1]))
for src_name, dst_name in FILE_RENAMES:
    s, d = RAW / src_name, RAW / dst_name
    if s.exists():
        plan.append((s, d))
    elif d.exists():
        print(f"   已就位，跳过 : {dst_name}")
    else:
        print(f"   !! 源文件缺失 : {src_name}")

for s, d in plan:
    exists = "目标已存在!" if d.exists() else ""
    print(f"   {s.relative_to(ROOT)}")
    print(f"     -> {d.relative_to(ROOT)}  {exists}")

# ---------- 3. Chroma 元数据 ----------
head("3. Chroma 元数据改写")
for old, new in SOURCE_MAP.items():
    ids = [i for i, m in zip(before["ids"], before["metadatas"]) if m.get("source") == old]
    print(f"   {old[:46]}...")
    print(f"     -> {new}   影响 {len(ids)} 个切片")

# ---------- 4. SQLite ----------
head("4. SQLite exam_questions.source 改写")
for old, new in SOURCE_MAP.items():
    n = con.execute("SELECT COUNT(*) FROM exam_questions WHERE source=?", (old,)).fetchone()[0]
    print(f"   {old[:46]}...  -> {new}   影响 {n} 行")

# ---------- 执行 ----------
if not APPLY:
    head("DRY-RUN 结束（未做任何改动）")
    print("确认无误后加 --apply 执行。")
    sys.exit(0)

head("执行")

ARCHIVE.mkdir(parents=True, exist_ok=True)
for s, d in plan:
    if d.exists():
        print("跳过（目标已存在）:", d.name)
        continue
    s.rename(d)
    print("重命名 :", s.name, "->", d.name)

for old, new in SOURCE_MAP.items():
    res = col.get(where={"source": old}, include=["metadatas"])
    ids, metas = res["ids"], res["metadatas"]
    new_metas = []
    for m in metas:
        m = dict(m)
        m["source"] = new
        fp = m.get("file_path")
        if fp:
            p = Path(fp)
            candidate = RAW / f"{new}{p.suffix}"
            if candidate.exists():
                m["file_path"] = str(candidate)
        new_metas.append(m)
    if ids:
        col.update(ids=ids, metadatas=new_metas)
        print(f"Chroma 改写 {len(ids)} 个切片 : {old[:38]}... -> {new}")

for old, new in SOURCE_MAP.items():
    cur = con.execute("UPDATE exam_questions SET source=? WHERE source=?", (new, old))
    print(f"SQLite 改写 {cur.rowcount} 行 : {new}")
con.commit()
con.close()

head("迁移后校验")
col2 = client.get_collection(COLLECTION)
after = col2.get(include=["metadatas"])
print("Chroma 切片总数 :", col2.count(), "(迁移前", col.count(), ")")
cnt2 = Counter(m.get("source", "?") for m in after["metadatas"])
for s, n in sorted(cnt2.items()):
    print(f"   {n:>5}  {s}")
