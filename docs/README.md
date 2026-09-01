# 造口伤口失禁护理 AI 学习助手 — 项目文档

> 面向国际造口治疗师（ET）考试备考的 RAG 学习应用（FastAPI + uni-app + ChromaDB）。
> 本文档体系用于**维护与交接**：任何新人（人或 AI）按此索引即可理解全貌并上手修改。

## 快速导航

| 文档 | 内容 | 适合场景 |
| :-- | :-- | :-- |
| [架构总览](architecture.md) | 系统整体设计、数据流、模块边界 | 第一次接触项目 |
| [后端模块](01-backend/README.md) | 后端目录地图、各模块职责 | 改后端代码前 |
| [前端模块](02-frontend/README.md) | uni-app 页面地图、交互流 | 改前端代码前 |
| [文档转换工具](03-tools.md) | PDF/EPUB/OCR 转 txt | 上传新教材前 |
| [部署运维](04-deployment.md) | 阿里云上线、日常管理 | 部署/故障排查 |
| [数据存储](05-data.md) | Chroma/sqlite/文件布局 | 理解持久化、备份 |
| [术语表](glossary.md) | 关键概念速查 | 快速回顾术语 |

## 项目速览

```
wound-care-assistant/
├── app/                # FastAPI 后端（RAG + 考试模块）
│   ├── main.py         # 入口：路由挂载 + /health
│   ├── config.py       # 环境变量 + 模型注册表 models.yaml
│   ├── ingestion/      # 文档加载 + 切片（500/50 中文）
│   ├── retrieval/      # Embedding(硅基流动) + Chroma 检索
│   ├── generation/     # 多模型 LLM（DeepSeek 默认）+ ET Prompt
│   ├── routers/        # 问答/上传/文档 API
│   ├── exam/           # 模拟测验：出题引擎/判分/sqlite 存储
│   └── utils/
├── frontend/           # uni-app (Vue3)：问答/上传/文档/测验
│   └── src/pages/      # chat, upload, docs, doc-detail, settings, exam/*
├── tools/              # 开发机文档转换（PDF/EPUB/OCR）
├── deploy/             # nginx / supervisor / 部署脚本
├── docs/               # 本文档体系
├── data/               # 教材 txt + exam.db（运行时）
├── chroma_db/          # 向量库持久化（运行时）
├── models.yaml         # 模型注册表（多模型切换，key 从 .env 读）
├── .env                # API Key 等（不入库）
└── requirements*.txt
```

## 核心思路（3 句话）

1. **RAG 问答**：教材先在开发机转 txt → 服务器切片向量化入 Chroma → 提问时检索 Top-K 片段拼 Prompt → 多模型 LLM 生成"有据可依"的回答（禁编造）。
2. **模拟测验**：复用同一检索链路，AI 按教材自动出题（单选/多选/案例），三道闸防错题（有据可依/置信度自检/缓存复用），作答后错题入错题本、成绩进统计。
3. **轻量部署**：2C2G 服务器只跑 Python 单进程（Uvicorn）+ 静态前端（Nginx），解析重活（PDF/OCR）全在开发机。

## 运行状态速查

- 后端：`python -m uvicorn app.main:app --port 8000`（健康检查 `/health`）
- 前端（开发）：`cd frontend && npm run dev:h5` → http://localhost:5173
- 测试：`pytest tests/ -v`（当前 14 个用例）

## 常用命令

```bash
# 后端启动 / 重启
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 全量测试
.\.venv\Scripts\python.exe -m pytest tests/ -q

# 前端开发 / 构建
cd frontend && npm run dev:h5        # 开发（热更新）
cd frontend && npm run build:h5      # 生产构建 → dist/build/h5/

# 教材转换（把 PDF/EPUB 拖到 tools/convert_dragdrop.bat）
python tools/convert_pdf_gpu.py 教材.pdf   # GPU OCR（RapidOCR）
python tools/convert_pdf.py 教材.pdf        # 文字版 PDF
```

## 修改指南（维护者必读）

- **改配置**（模型/Key/切片参数）：见 [01-backend/config.md](01-backend/config.md)，改 `.env` 或 `models.yaml` 后重启后端。
- **加新模型**：`models.yaml` 加条目 + `.env` 加 Key，零代码改动（见 config.md）。
- **改出题 Prompt / 判分规则**：见 [01-backend/exam.md](01-backend/exam.md)。
- **加前端页面**：`frontend/src/pages/` 新目录 + `pages.json` 注册（tabBar 页需处理 3 项限制）。
- **注意**：uni-app 改 `pages.json` 或新增页面后，需**重启 dev server** 生效；`.vue` 内 methods 若未生效也先重启（uni 编译器偶发不热更新方法注入）。

## 文档维护约定

- 本文档体系与代码同步维护；改了代码结构、API、配置项后，请同步更新对应文档。
- 新功能先写 `docs/specs/YYYY-MM-DD-xxx-design.md` 设计，再实现，最后把设计归档进对应模块文档。