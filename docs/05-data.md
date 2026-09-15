# 数据存储设计

> 三类持久化：向量库（Chroma）、关系库（SQLite）、文件（txt 教材）。均随项目目录，备份 = 拷贝这些目录。

## 1. 存储地图

| 存储 | 位置 | 内容 | 特点 |
| :-- | :-- | :-- | :-- |
| ChromaDB | `chroma_db/` | 教材切片向量 + 原文 + 元数据（source/page） | 检索专用，可重建 |
| SQLite | `data/exam.db` | 题目/成绩/错题/统计 | 零依赖，Python 内置 |
| 文件 | `data/raw/*.txt` | 原始教材（带 @@PAGE:N@@ 标记） | 可重新上传重建索引 |
| 配置 | `.env`, `models.yaml` | Key 与模型 | 不入库 |

**备份/迁移**：打包 `chroma_db/` + `data/`（含 exam.db）+ `.env` 即可完整搬家。若只搬 `data/raw/*.txt`，可在新环境重新上传重建索引（embedding 会重调 API）。

## 2. ChromaDB（向量库）

- 集合：`wound_care_kb`，度量 cosine，持久化目录 `CHROMA_PERSIST_DIR`（默认 ./chroma_db）
- 显式传 `embeddings=` 入库（不触发默认 embedding 下载）
- 切片元数据：`{source, page?, file_path, chunk_id, chunk_index}`
- `id` 约定：`来源#序号`（上传时生成），重复上传先删旧再插 = 天然幂等更新

### 重建索引场景

1. 换 embedding 模型（维度变化）
2. 本地 chroma_db 损坏/误删
3. 想全库重切（改切片参数后）

做法：停后端 → 删 `chroma_db/` → 启后端 → 重新上传全部教材。

## 3. SQLite — data/exam.db

schema（`app/exam/store.py` 自动建表；`_migrate_schema` 幂等补列/重建，旧库自动升级）：

```sql
users            -- 用户（账户体系 B 模式，2026-09-01 引入）
  id, username(UNIQUE), password_hash(bcrypt), display_name,
  is_admin(0普通/1系统管理员), created_at
  -- 系统管理员（admin）由启动时 ADMIN_PASSWORD 引导创建，唯一

exam_questions   -- 题目缓存（公共，AI 出题 + 缓存复用）
  id, scope_key, qtype, topic, source, page, question,
  options(JSON), answer(JSON), explanation, confidence,
  used_count, created_at
  -- 索引: scope_key（同范围复用查询）

exam_attempts    -- 做题记录/成绩（按用户）
  id, mode(practice|exam|chapter), topic, total, correct,
  score, detail(JSON 逐题), created_at, user_id

wrong_book       -- 错题本（按用户）
  id, question_id(FK→exam_questions), user_answer(JSON),
  wrong_count, last_wrong_at, resolved(0待巩固/1已掌握), user_id
  -- 索引: (user_id, resolved)

question_stats   -- 题目统计（按用户，复合主键）
  question_id, user_id, attempts, correct
  -- PRIMARY KEY (question_id, user_id)
  -- 旧表(单列 PK)会在首个连接时自动重建为复合主键（数据保留）
```

- `user_id=0` = 未归属历史数据；**首个用户注册时 `migrate_legacy_to_user` 一次性接管**（UPDATE 三表）
- 索引：`idx_wrong_user(user_id,resolved)`、`idx_stats_user(user_id)`、`idx_attempts_user(user_id)`

### 关键查询（store.py）

| 函数 | 说明 |
| :-- | :-- |
| `get_questions_by_scope(scope_key)` | 同范围缓存题（公共） |
| `user_count / create_user / get_user_by_*` | 用户 CRUD（账户体系） |
| `migrate_legacy_to_user(uid)` | 首个用户注册时接管 user_id=0 历史数据 |
| `save_attempt(..., user_id)` | 记录成绩（按用户），返回 attempt_id |
| `add_wrong / mark_wrong_resolved(..., user_id)` | 错题增/清（按用户） |
| `get_wrong_questions(user_id)` | 待巩固错题（JOIN 题目，按用户） |
| `record_answer / topic_stats(user_id)` | 统计 + 按主题聚合正确率（按用户） |

### 数据流

```
出题: generate → 逐题 cache_question(scope_key) → 前端拿题
判分: submit → grade() → record_answer + add_wrong(+1) / mark_resolved + save_attempt
报表: stats → topic_stats(JOIN topic) + attempts(最近20)
```

### 维护

- 清空错题本：`UPDATE wrong_book SET resolved=1` 或删表重建（schema 自动建）
- 清空题库（想重新出题）：删除 `exam_questions` 表行，scope_key 缓存随之失效

## 4. 文件（data/）

```
data/
├── raw/            # 教材 txt（带页码标记）；上传 API 落盘于此
│   └── 伤口护理学.txt
└── exam.db         # SQLite（运行时生成）
```

> `.gitignore`：data/raw/* 忽略（保留 .gitkeep），chroma_db/ 与 exam.db 忽略——**生产环境这些是运行时数据，不入版本库**。

## 5. 数据一致性提醒

- `data/raw/*.txt` 与 Chroma 切片**非强绑定**：删向量不删文件仍会残留 data/raw 文件；`DELETE /documents/{source}` 会同时清理（按 source 前缀匹配所有后缀）
- 换 embedding 需重建索引（见上）——此时 data/raw 保留，只需删 chroma_db 重传
- 考试统计与题库：只增不改（除了错题 resolved 状态），审计友好