# 架构总览

> 目标读者：第一次接触项目的人。看完本文应能回答"系统有哪些部分、数据怎么流动、为什么这么设计"。

## 1. 系统定位

面向**国际造口治疗师（WCET）认证备考**的单用户学习应用，核心能力：

- **RAG 精准问答**：基于教材（txt）回答，禁止编造，可定位原文页码
- **模拟测验**：AI 按教材自动出题（单选/多选/案例分析），错题收集、学习报告
- 部署环境：阿里云 **2C2G** 轻量服务器 → 一切解析重活不放在服务器

## 2. 技术栈

| 层 | 选型 | 说明 |
| :-- | :-- | :-- |
| 后端 | FastAPI + Uvicorn（单 worker） | 轻量 ASGI，自动文档 |
| 向量化 | 硅基流动 `Qwen/Qwen3-Embedding-8B`（API，1024 维） | OpenAI 兼容，`text-embedding` 接口 |
| 向量库 | ChromaDB（本地持久化，`chroma_db/`） | cosine 距离，显式传向量 |
| LLM | 多模型（`models.yaml` 注册表，默认 DeepSeek V3.2 @ 硅基流动） | OpenAI 兼容 chat 接口 |
| 文本切分 | LangChain `RecursiveCharacterTextSplitter` | 500 字符/块、50 重叠、中文分隔符 |
| 前端 | uni-app (Vue 3) + Vite | 编译 H5 / 小程序 / App |
| 存储 | SQLite（Python 内置）+ Chroma + 文件 | 见 [05-data.md](05-data.md) |
| 文档解析 | 开发机 PyMuPDF / RapidOCR(GPU) / Tesseract(兜底) | 见 [03-tools.md](03-tools.md) |

## 3. 两大核心链路

### 3.1 RAG 问答链路

```
【索引阶段】（上传教材时，一次性）
  txt 教材 → loader 解析(@@PAGE:N@@ 页码标记) → chunker 切片(500/50)
    → Embedder 向量化(硅基流动,1024维) → Chroma 持久化(带 source/page 元数据)

【问答阶段】（每次提问）
  用户问题 → Embedder 向量化 → Chroma similarity_search(Top-K=5)
    → 相关性阈值过滤(RELEVANCE_THRESHOLD=0.35，低分不送 LLM 防编造)
    → 拼接 ET Prompt(带真实来源+页码) → LLM 生成(流式/非流式)
    → 返回 {answer, sources:[{source, pages}], model, top_k_used}
```

关键设计：**切片元数据携带 source（教材名）与 page（页码）**，既用于检索过滤，也让回答可"定位原文"。转换脚本在每页文本前插入 `@@PAGE:N@@` 行（详见 ingestion 文档）。

### 3.2 模拟测验链路

```
选范围(题型/题量/教材/主题) → generate_questions()
  → _fetch_seed_docs: Chroma 检索种子段落(主题优先/多源轮转)
  → LLM 逐段出题(题干+4选项+答案+解析+主题标签+置信度)
  → 三道闸：①答案必须出自片段 ②confidence<0.7 丢弃 ③同范围缓存复用
  → 题目入 sqlite exam_questions(scope_key 复用)

用户作答 → submit → grader.grade()
  → 单选/案例：完全匹配；多选：集合完全一致(多选少选均错)
  → 落库：exam_attempts(成绩) + wrong_book(错题) + question_stats(统计)
```

## 4. 模块边界

```
                ┌──────────────────────────────────────┐
                │             前端 uni-app             │
                │  chat / docs / upload / settings     │
                │  exam(主页/做题/成绩/错题/报告)        │
                └───────────────┬──────────────────────┘
                                │ HTTP (JSON / SSE 流式)
                ┌───────────────▼──────────────────────┐
                │            FastAPI (app/)            │
                │  routers/api.py  ── 问答/上传/文档     │
                │  exam/router.py  ── 出题/判分/统计     │
                │  config.py ── .env + models.yaml      │
                ├────────┬────────┬────────┬───────────┤
                │ingestion│retrieval│generation│  exam/ │
                │ loader │ embedder│  llm    │ engine  │
                │ chunker│ retriever│  (Prompt)│ grader │
                └────────┴────────┴────────┴── store ──┤
                        │        │        │       │     │
              data/raw/*.txt  chroma_db/  OpenAI API  data/exam.db
```

| 模块 | 职责 | 不负责 |
| :-- | :-- | :-- |
| `ingestion/` | 读 txt（含页码标记）、切片 | PDF/EPUB 解析（在开发机 tools/） |
| `retrieval/` | Embedding 调用、Chroma 增删查 | Prompt 构造 |
| `generation/` | 多模型 LLM 调用、ET Prompt 模板、流式 | 检索逻辑 |
| `routers/api.py` | 问答/上传/文档/模型的 HTTP 层 | 域逻辑（在对应模块） |
| `exam/` | 出题引擎/判分/错题/统计，sqlite 存储 | 前端交互 |
| `config.py` | 配置与模型注册表（全局单例） | 业务逻辑 |

## 5. 关键设计决策（为什么这么做）

| 决策 | 原因 |
| :-- | :-- |
| 服务器只收 txt，PDF/EPUB 在开发机转 | 2C2G 跑不动解析/OCR；开发机有 NVIDIA GPU（OCR 29 分钟跑 3 本书） |
| Embedding 和 LLM 全走 API | 服务器零本地模型负担，模型可随时换 |
| 显式传向量给 Chroma | 避免 Chroma 默认 embedding 下载模型到 C 盘/服务器 |
| 相关性阈值 0.35 | 低分片段不送 LLM，防止"拿无关内容编造" |
| 检索片段带真实来源+页码进 Prompt | 回答必须标注真实来源，禁止模型编书名（曾出现幻觉书名） |
| 三道闸防错题 | AI 出题质量不可完全信任：有据可依+置信度+缓存 |
| 题库 sqlite 缓存（scope_key） | 同范围练习不重复出题，且复用已生成题目（0.7s 出 5 题） |
| 单数据库文件 data/exam.db | 零依赖（Python 内置 sqlite3），随项目备份 |

## 6. 数据流图（一次完整交互）

```
用户: "回肠造口渗漏怎么办？"
  → POST /api/ask
  → config.get_registry() 校验模型 + Key
  → VectorStore.similarity_search → hits(带source/page)
  → 阈值过滤 → LLMClient.generate_stream (SSE)
  → 前端逐字渲染 + 底部来源标签(含页码)
```

```
用户: 测验页 → 练一练(5题)
  → POST /api/exam/generate {count:5}
  → 检索种子段 → LLM 出题 → 缓存 → 前端答题页
  → POST /api/exam/submit → 判分 → 错题本/统计 → 成绩单页
```

## 7. 扩展点（未来改动入口）

- **加教材**：tools 转换 → 上传，无需改代码
- **加模型**：models.yaml + .env（见 config.md）
- **加题型**：exam/engine.py `QTYPE_LABEL` + Prompt 模板 + grader 判分逻辑
- **加页面**：frontend pages/ + pages.json
- **题库人工审核**：exam_questions 表已存全部题目，可加审核 UI
- **多端发布**：`npm run build:mp-weixin`（小程序）等，需 DCloud 账号