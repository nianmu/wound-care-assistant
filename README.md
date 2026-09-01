# 造口伤口失禁护理 AI 学习助手

面向国际造口治疗师（ET）考试备考的 RAG 精准问答应用：
基于教材文档，检索增强生成，答案必须出自教材、禁止编造。

> ✅ **当前状态（2026-08-31）**：后端全链路 + 前端 H5 已开发完成并端到端实测通过。
> **下一步**：把真实教材（PDF/EPUB → txt）用 `tools/` 转换后上传，即可日常使用。

## 技术栈

| 层 | 选型 |
| :-- | :-- |
| 后端 | FastAPI + LangChain(TextLoader/切片) + ChromaDB（本地持久化） |
| Embedding | 硅基流动 Qwen3-Embedding-8B（API，1024 维，OpenAI 兼容） |
| LLM | DeepSeek V3.2 默认（硅基流动），多模型可切换（通义/GLM/Kimi，见 `models.yaml`） |
| 前端 | uni-app (Vue 3) → 编译 H5 / 微信小程序 / App |
| 部署 | Nginx 托管前端静态产物 + 反代 `/api`；Supervisor 守护 Uvicorn |

## 快速开始（开发机）

```bash
# 0. 环境准备
#    本机已装 Python 3.12 venv + 依赖（用 uv，缓存目录在工作区 .uv-cache/）
#    如需重建：
#      $env:UV_CACHE_DIR="E:\dsh Files\.uv-cache"; $env:UV_PYTHON_INSTALL_DIR="E:\dsh Files\.uv-python"
#      uv venv --python 3.12 .venv && uv pip install -r requirements-dev.txt

# 1. 配置密钥（已就绪，.env 有真实 Key）
#    copy .env.example .env   # 填入 DEEPSEEK_API_KEY / SILICONFLOW_API_KEY

# 2. 启动后端
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
# 健康检查: http://127.0.0.1:8000/health

# 3. 启动前端（H5 dev，自动代理 /api 到 :8000）
cd frontend && npm run dev:h5
# 浏览器打开: http://localhost:5173/

# 4. 测试
pytest tests/ -v
```

## 使用流程

1. **上传教材**：前端「上传」页选 .txt（或 `POST /api/upload`）；PDF/EPUB 先转换（`tools/`，见 `tools/README.md`）
2. **智能问答**：前端「问答」页输入问题，可切换模型 / Top-K
3. **文档管理**：前端「文档」页查看 / 删除已索引教材

## 目录结构

```
wound-care-assistant/
├── app/
│   ├── main.py            # FastAPI 入口 + /health
│   ├── config.py          # 环境变量 + 模型注册表(models.yaml)
│   ├── ingestion/         # 文档加载 + 切片(500/50)
│   ├── retrieval/         # Embedding 封装 + Chroma 检索
│   ├── generation/        # LLM 多模型调用 + ET Prompt 模板
│   ├── routers/           # /upload /ask /documents /models
│   └── utils/
├── frontend/              # uni-app (Vue 3)：问答/上传/文档三页
├── tools/                 # PDF/EPUB → txt 转换脚本（开发机）
├── deploy/                # nginx / supervisor / deploy.sh / DEPLOY.md
├── data/raw/              # 教材 txt
├── chroma_db/             # 向量库持久化（自动生成）
├── models.yaml            # 模型注册表（多模型切换）
├── .env                   # API Key 等（不入库）
└── requirements*.txt
```

## 使用流程

1. **上传教材**：前端「上传」页选 .txt（或 `POST /api/upload`）；PDF/EPUB 先转换（`tools/`，见 `tools/README.md`）
2. **智能问答**：前端「问答」页输入问题，可切换模型 / Top-K
3. **文档管理**：前端「文档」页查看 / 删除已索引教材

## API 一览

| 方法 | 路径 | 说明 |
| :-- | :-- | :-- |
| GET | `/health` | 健康检查 + 模型清单（不含 Key） |
| GET | `/api/models` | 可用 LLM / 当前 Embedding |
| POST | `/api/upload` | 上传 .txt 教材（multipart `file`）→ 切片入库 |
| POST | `/api/ask` | 问答 `{question, model_id?, top_k?}` |
| GET | `/api/documents` | 已索引来源 + chunk 总数 |
| DELETE | `/api/documents/{source}` | 删除某教材全部切片 |

## 多模型切换

- LLM：`models.yaml` 的 `chat_models` 预置 4 家，`/api/ask` 传 `model_id` 切换；前端下拉选择；新增模型只需加配置条目 + `.env` 加 Key，零代码改动
- Embedding：换模型需**同维度**（当前 1024），否则旧索引失效需重建
- 相关性阈值：`RELEVANCE_THRESHOLD`（默认 0.35）——低于此相似度的检索片段不送入 LLM，防编造
- API Key 一律从环境变量读取，不落配置文件、不外泄

## 部署（阿里云 2C2G）

见 `deploy/DEPLOY.md`：Nginx 托管前端 + 反代，Supervisor 守护后端，2G Swap。

## 免责声明

本应用仅用于学习备考辅助，不构成医疗建议；涉及临床判断的内容以教材与老师讲授为准。