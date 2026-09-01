# LLM 生成 — generation/

> 职责：调用多模型 LLM（OpenAI 兼容），按 ET Prompt 模板生成回答，支持流式。

## 1. llm.py — LLMClient

```python
class LLMClient:
    def __init__(self, model_id=None)
        # 默认 settings.default_model 的 models.yaml id
        # 从 ModelRegistry 拿: model_name, api_key, base_url, display_name
        # 创建 OpenAI 客户端

    generate(question, hits, history=None, temperature=0.3) -> str        # 非流式
    generate_stream(question, hits, history=None, temperature=0.3) -> Iterator[str]  # 流式逐段
```

- `hits` 是 `[(Document, score)]`（来自 retriever），**片段携带真实来源+页码**
- `history` 是 `[{role: user|assistant, content}]` 的最近对话，支持多轮追问；经 `_build_history` 注入 Prompt（最多 6 轮、单条 500 字、总 2000 字）
- 所有厂商走 OpenAI 兼容 `/chat/completions`；`stream=True` 时逐 chunk yield content

## 2. ET Prompt 模板（产品约束）

`SYSTEM_PROMPT`（在 llm.py 顶部，**改语义前慎重**）：

```
你是一名拥有20年经验的资深国际造口治疗师（ET），正在辅导学生。

请严格基于【参考资料】回答。回答要求：
1. 参考资料无相关内容 → 只答："教材中未找到相关内容，请以老师课堂讲授为准。"——严禁编造！不要列来源不要展开。
2. 涉及临床操作 → 按"①评估 → ②准备 → ③操作 → ④观察"四步结构回答。
3. 答案末尾标注信息来源——只能用参考资料中【片段｜来源】的真实来源名，严禁编造书名/章节。
4. 用户可能追问上一轮话题（如"那 III 期呢？"）：结合【对话历史】理解意图，但回答依据仍只能来自本次【参考资料】；历史仅用于理解上下文，不得当作引用来源。
```

模板含三段：`{context}`（本次检索片段）、`{history}`（对话历史，空为"（无）"）、`{question}`（当前问题）。

**Prompt 构造**（`_build_context`）：

```
[片段1｜来源：伤口护理学（第12页）]
（检索到的原文）
[片段2｜来源：失禁护理学（第3页）]
（原文）
```

- 片段带来源标签 → 模型"有据可依"且**不能编书名**（曾出现模型自编《国际造口治疗师培训教材》的幻觉，已通过此设计修复）
- system 层再叠一条身份约束（双保险）

## 3. 流式（SSE）

- `generate_stream` 逐 chunk yield 文本增量
- 路由层（api.py `/ask/stream`）包装为 `text/event-stream`：
  - `data: {"type":"delta","text":"..."}` 增量
  - `data: {"type":"sources","sources":[...]}` 来源（含页码）
  - `data: {"type":"done"}` / `{"type":"error"}`
- 前端 fetch + ReadableStream 逐字渲染（打字机效果），带"停止"按钮（AbortController）

## 4. 多模型切换

- `/api/ask` 请求体 `model_id` 字段 → `LLMClient(model_id)`
- 前端「学习设置」页选择 → localStorage（`wc_model_id`）→ 每次发送时读取
- 未知模型 / 缺 Key：路由层先 `_validate_model`（404/500 明确报错）

## 5. 修改指南

| 想改什么 | 位置 |
| :-- | :-- |
| Agent 身份/Prompt 约束 | `llm.py` SYSTEM_PROMPT |
| 温度 | 路由层 temperature 参数（默认 0.3） |
| 流式粒度/事件格式 | `generate_stream` + api.py `/ask/stream`（前后端需同步改） |

## 6. 故障排查

| 现象 | 原因 | 处理 |
| :-- | :-- | :-- |
| 回答 500 "模型未配置可用 Key" | 选中的模型没配 Key | 换默认模型或补 Key |
| 回答编造来源 | Prompt 版本旧 / 片段未带来源 | 确认 llm.py 用最新模板 |
| 流式中断 | 网络/超时 | 前端有 error 事件兜底提示 |