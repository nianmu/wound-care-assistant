# 后端模块 — 总览

> FastAPI 后端位于 `app/`。本文给出模块地图、文件职责与修改入口；细节见各子文档。

## 目录地图

| 文件/目录 | 职责 | 详见 |
| :-- | :-- | :-- |
| `main.py` | 应用入口：lifespan（加载配置）、CORS、/health、路由挂载 | 本页下方 |
| `config.py` | Settings（env）+ ModelRegistry（models.yaml），全局单例 | [config.md](config.md) |
| `ingestion/loader.py` | 读 txt/md，解析 `@@PAGE:N@@` 页码标记 → Document(page) | [ingestion.md](ingestion.md) |
| `ingestion/chunker.py` | 500/50 中文切片 | [ingestion.md](ingestion.md) |
| `retrieval/embedder.py` | Embedding API 封装（Qwen3-Embedding-8B，1024 维） | [retrieval.md](retrieval.md) |
| `retrieval/retriever.py` | Chroma 持久化集合、检索、按来源增删查 | [retrieval.md](retrieval.md) |
| `generation/llm.py` | 多模型 LLM、ET Prompt 模板、流式生成 | [generation.md](generation.md) |
| `routers/api.py` | /api/*：问答、上传、文档、模型列表 | [api.md](api.md) |
| `exam/engine.py` | AI 出题引擎（三道闸） | [exam.md](exam.md) |
| `exam/grader.py` | 判分 + 错题/统计落库 | [exam.md](exam.md) |
| `exam/store.py` | sqlite 存储（题目/成绩/错题/统计） | [exam.md](exam.md) |
| `exam/router.py` | /api/exam/* HTTP 层 | [api.md](api.md) |
| `utils/` | 工具函数（预留） | — |

## main.py 说明

```python
# 启动时（lifespan）：
app.state.settings = get_settings()      # 读 .env
app.state.registry = get_registry()      # 解析 models.yaml

# 路由挂载：
app.include_router(api_router)           # /api/*
app.include_router(exam_router)          # /api/exam/*

# /health：返回状态 + 模型清单（不含任何 Key）——注意用 chat_model_info/embedding_model_info
# （不带 Key 的只读方法，避免健康检查因缺 Key 而 500）
```

## 模块依赖方向（单向，避免循环）

```
routers */ exam/router  →  业务模块（ingestion/retrieval/generation/exam.*）
                           ↓
config.py（最底层，被所有模块依赖）
```

`config.get_settings() / get_registry()` 是全局单例（模块级缓存），所有模块通过它拿配置。

## 修改入口速查

| 想改什么 | 改哪里 |
| :-- | :-- |
| API Key / 模型 / 检索参数 | `.env` + `config.py`（无需改代码，重启后端） |
| 加 LLM 模型 | `models.yaml` + `.env` 加 Key |
| 切片大小/重叠 | `ingestion/chunker.py`（CHUNK_SIZE/OVERLAP） |
| 相关性阈值 | `.env` 的 RELEVANCE_THRESHOLD |
| ET Prompt / 流式 | `generation/llm.py` |
| 出题规则/题型 | `exam/engine.py` |
| 判分规则 | `exam/grader.py` |
| 新增 API | `routers/` 或 `exam/router.py` 加路由，main.py 挂载 |

## 测试

```bash
.\.venv\Scripts\python.exe -m pytest tests/ -v
```

- `test_health.py`：/health + 模型注册表缺 Key 报错
- `test_ingestion.py`：切片边界、页码标记解析、存拒绝 PDF
- `test_pages.py`：loader 页码解析（多页/无标记/多行）
- `test_exam.py`：sqlite 存储 CRUD、判分规则、错题流（自动用临时库隔离）