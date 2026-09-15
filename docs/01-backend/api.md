# API 参考 — 全部端点

> 前缀：业务 API = `/api`，考试 API = `/api/exam`。所有接口返回 JSON（`/ask/stream` 除外，见下）。
> 前端封装见 [02-frontend/api-client.md](../02-frontend/api-client.md)。

## 1. 基础

| 方法 | 路径 | 说明 |
| :-- | :-- | :-- |
| GET | `/health` | 健康检查 + 模型清单（不含 Key）+ 默认模型/TopK |

```json
// GET /health
{
  "status": "ok",
  "service": "wound-care-assistant",
  "models": { "chat": [{"id","name"}…], "embedding": [{"id","name"}] },
  "default_model": "deepseek-chat",
  "default_embedding": "qwen3-embedding-8b",
  "top_k": 5
}
```

## 2. 文档与索引

### POST /api/upload — 上传教材并索引

- multipart/form-data，字段名 `file`
- **只接受 .txt / .md**（UTF-8）；PDF/EPUB 返回 400 并提示先用 tools/ 转换
- 流程：落盘 data/raw/ → 加载(解析页码标记) → 切片 → 向量化 → 入库（覆盖同名：先删旧再插）
- 加载/切片/向量化全程在**线程池**执行（`asyncio.to_thread`），大书上传不阻塞其它接口

```json
// 200
{ "status": "success", "chunk_count": 959, "source": "伤口护理学", "total_in_kb": 2832 }
// 400
{ "detail": ".pdf 不在服务器支持范围（['.md', '.txt']）。请在开发机运行 python tools/convert_pdf.py 或 convert_pdf_ocr.py 转成 txt 后上传" }
```

### GET /api/documents — 已索引来源

```json
{ "sources": ["伤口护理学", "失禁护理学", …], "total_chunks": 2832 }
```

### GET /api/documents/{source}/chunks — 文档切片（详情页）

- source 需 URL 编码（中文！前端 `encodeURIComponent`）
- 按 (page, chunk_index) 排序

```json
{ "source": "伤口护理学", "total": 959, "chunks": [ { "id","page","chunk_index","content" }, … ] }
```

### DELETE /api/documents/{source} — 删除文档

- 删向量 + 删 data/raw/ 下所有同名文件（任意后缀）

```json
{ "deleted_chunks": 959, "source": "伤口护理学" }
```

## 3. 账户体系（B 模式：用户名+密码+JWT）

> 设计详见 [specs/2026-09-01-user-auth-design.md](../specs/2026-09-01-user-auth-design.md)。
> 考试模块全部端点要求登录（`Authorization: Bearer <JWT>`）；问答/文档类不强制。

### POST /api/auth/register — 注册（注册即登录，需邀请码）

```json
// 请求
{ "username": "mama", "password": "abc12345", "display_name": "妈妈", "invite_code": "95279527" }
// 200
{
  "token": "eyJ...",
  "user": { "id": 1, "username": "mama", "display_name": "妈妈" },
  "migrated": { "exam_attempts": 13, "wrong_book": 18, "question_stats": 10 },
  "is_first": true
}
// 403（邀请码错误 / 未配置邀请码=未开放注册）
{ "detail": "注册邀请码错误" }
```

- 用户名：3~32 位小写字母/数字/下划线（大写自动转小写）
- 密码：≥8 位，含字母+数字；`user` **永不返回哈希字段**
- **必须携带 `invite_code`**：与 `REGISTER_INVITE_CODE` 一致才放行；该配置为空时一律 403（防外人随意注册）
- `is_first=true` 时自动接管历史（user_id=0）数据，`migrated` 为迁移计数

### POST /api/auth/login — 登录

```json
{ "username": "mama", "password": "abc12345" }
// 200 → { "token", "user" }
// 401 → 用户名或密码错误；429 → 尝试次数过多（同用户名/IP 错 5 次锁 5 分钟）
```

### GET /api/auth/me — 当前用户

- 带 token → `{ "user": {...} }`；无/过期 → 401

### 鉴权矩阵（受保护接口）

| 接口 | 鉴权 | 隔离维度 |
| :-- | :-- | :-- |
| /api/exam/generate /submit /wrong-book /stats /topics | ✅ 必须登录 | submit 按 user_id 落库；wrong-book/stats 按 user_id 过滤 |
| **/api/upload**（上传教材） | ✅ **仅管理员**（is_admin=1） | 非管理员 403 |
| **DELETE /api/documents/{source}**（删除教材） | ✅ **仅管理员**（is_admin=1） | 非管理员 403 |
| /api/ask, /api/ask/stream | ❌ 不强制 | — |
| GET /api/documents, /api/documents/{source}/chunks | ❌ 不强制（查看开放） | — |
| /api/auth/* | 注册/登录开放；/me 需登录 | — |

> 管理员：系统启动时由 `ADMIN_PASSWORD`（.env）引导创建 `admin`（is_admin=1），唯一管理员。
> `is_first` 判定按普通用户计，管理员的存在不影响“首个注册家人接管历史数据”。

## 4. 问答

### POST /api/ask — 非流式问答

请求：

```json
{
  "question": "回肠造口渗漏怎么办？",
  "model_id": "deepseek-chat",
  "top_k": 5,
  "history": [ { "role": "user", "content": "上一轮问题" }, { "role": "assistant", "content": "上一轮回答" } ]
}
```

- `model_id` 可选（默认 DEFAULT_MODEL）；`top_k` 可选 1~20（默认 5）；`history` 可选（最近对话，支持**多轮追问**）
- **多轮语义**：检索用"当前问题 + 最近一个用户问题"接地（`_grounded_query`），使"那 III 期呢？"这类追问能命中上一轮主题；历史同时注入 LLM Prompt（`_build_history`，最多 6 轮/2000 字）
- **引用始终独立**：每次回答都是独立检索 Top-K → 独立返回本次 `sources`，不与历史共用/复用引用
- 流程：校验模型 → 检索 → 阈值过滤(0.35) → LLM 生成
- **性能**：检索（含 embedding 网络调用）与 LLM 生成均在 `asyncio.to_thread` 线程池执行，不阻塞事件循环，其它接口不受影响

```json
// 200
{
  "answer": "根据教材…（四步结构）…信息来源：伤口护理学（第12页）",
  "sources": [ { "source": "伤口护理学", "pages": [12, 15] } ],
  "model": "DeepSeek V3.2（硅基流动）",
  "top_k_used": 3
}
// 知识库空 / 无命中
{ "answer": "教材中未找到相关内容，请以老师课堂讲授为准。/ 知识库为空…", "sources": [], "model": "…" }
```

### POST /api/ask/stream — 流式问答（SSE）

请求同 /api/ask（含 `history`）。响应 `text/event-stream`（前端按 `data: {json}\n\n` 帧解析）：

```
data: {"type":"delta","text":"根据"}
data: {"type":"delta","text":"教材"}
data: {"type":"sources","sources":[{"source":"伤口护理学","pages":[12]}],"model":"DeepSeek V3.2（硅基流动）"}
data: {"type":"done"}
// 异常: {"type":"error","message":"…"}
```

### GET /api/models — 模型列表

```json
{
  "default": "deepseek-chat",
  "chat_models": [ {"id","name","model"} ],   // 不含 Key
  "embedding": { "id","name","model","dimensions" }
}
```

## 5. 模拟测验

### POST /api/exam/generate — AI 出题

请求：

```json
{ "count": 5, "qtype": "single", "source": "伤口护理学", "topic": "压疮分期", "reuse_cached": true }
```

- `count` 1~20；`qtype` single|multi|case|省略(混合 6:2:2)；`source`/`topic` 可选；`reuse_cached` 默认 true
- 响应含 `generated`(新出)/`reused`(缓存)/`skipped`(丢弃)
- **性能**：生成阶段线程池并行调 LLM（`GENERATE_WORKERS=3`），且整个生成在 `asyncio.to_thread` 中执行——既快又不阻塞其它接口（修复前 10 题串行会卡死整个事件循环）

```json
{
  "questions": [
    {
      "id": 42, "qtype": "case", "topic": "复杂伤口处理",
      "source": "伤口造口失禁患者个案护理", "page": 138,
      "question": "患者，女性，45岁…（病例描述+提问）",
      "options": ["A. …", "B. …", "C. …", "D. …"],
      "answer": ["C"],            // 单选["C"] / 多选["B","C"]
      "explanation": "根据教材原文…",
      "confidence": 0.95
    }
  ],
  "generated": 5, "reused": 0, "skipped": 0
}
// 知识库空：400 {detail:"知识库为空：请先在「文档管理」上传教材。"}
```

### POST /api/exam/submit — 判分

```json
{
  "questions": [ {题对象, 同 generate 返回} ],
  "answers": [["C"], ["B","C"]],
  "mode": "practice",     // practice | exam | chapter
  "topic": "压疮分期"      // 可选
}
```

```json
// 200
{
  "attempt_id": 8, "total": 2, "correct": 1, "score": 50,
  "details": [
    { "question_id", "qtype", "topic", "question", "options", "answer",
      "user_answer", "correct", "explanation", "source", "page" }
  ]
}
```

判分规则：单选/案例=完全匹配；**多选=集合完全一致**（多选/少选都算错）。错题自动入 wrong_book（resolved=0），答对自动 resolve；每答一题更新 question_stats。

### GET /api/exam/wrong-book?include_resolved=false — 错题本

```json
{ "total": 8, "questions": [ {同 generate 题对象 + wrong_count, resolved, last_wrong_at} ] }
```

### GET /api/exam/stats — 学习报告

```json
{
  "overall_accuracy": 62,
  "total_answered": 45,
  "by_topic": [ { "topic": "压疮分期", "attempts": 12, "correct": 9, "accuracy": 75 }, … ],
  "weak_topics": [ ≤3 个, attempts>=3, 按 accuracy 升序 ],
  "attempts": [ 最近20条记录 {mode,topic,total,correct,score,created_at,detail} ]
}
```

### GET /api/exam/topics — 主题列表（章节练习选择用）

```json
{ "topics": ["压疮分期", "造口用品", "失禁分类", …] }
```

## 6. 状态码约定

| 码 | 场景 |
| :-- | :-- |
| 200 | 成功 |
| 400 | 参数错误 / 格式不支持 / 知识库空 / 用户名重复或不合规 / 题目与答案数量不匹配 |
| 401 | 未登录 / 登录过期 / 用户名或密码错误 |
| 403 | 注册邀请码错误 / 未开放注册 |
| 404 | 未知模型 / 未知来源 |
| 429 | 登录尝试过多被临时锁定 |
| 500 | 模型 Key 缺失 / 生成中断等服务器异常（frontend 会显示 detail） |

## 7. 修改 API 后

1. 更新本文档
2. 同步前端 `frontend/src/utils/api.js` 对应函数
3. 跑 `pytest tests/`（test_health 覆盖路由加载）