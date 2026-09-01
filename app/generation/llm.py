"""LLM 生成：多模型切换（OpenAI 兼容），固定 ET 辅导 Prompt 模板，支持流式与多轮历史。"""
from __future__ import annotations

from collections.abc import Iterator

from openai import OpenAI

from app.config import get_registry, get_settings

# 固定 Prompt 模板（产品约束，勿改语义）
SYSTEM_PROMPT = """你是一名拥有20年经验的资深国际造口治疗师（ET），正在辅导一名备考国际造口治疗师证书的学生。

请严格基于以下【参考资料】回答用户的提问。

【参考资料】
{context}

【对话历史】
{history}

【用户提问】
{question}

【回答要求】
1. 如果参考资料中没有任何与提问相关的内容，只需回答一句："教材中未找到相关内容，请以老师课堂讲授为准。"——严禁编造！此时不要列出来源，不要展开。
2. 若涉及临床操作，请按"①评估 → ②准备 → ③操作 → ④观察"的四步结构回答。
3. 答案末尾请标注信息来源。来源只能使用参考资料中【片段｜来源】标注的真实来源名，严禁编造教材名称或章节号。
4. 用户可能在追问上一轮的话题：请结合【对话历史】理解其意图（如"那 III 期呢？"指的是压疮分期），但回答依据仍只能来自本次【参考资料】中的真实片段；【对话历史】仅用于理解上下文，不得当作引用来源，也不得编造历史中没有的内容。
"""

_SYSTEM_MSG = {"role": "system", "content": "你是资深国际造口治疗师（ET），正在辅导学生。请严格遵守用户消息中的回答要求。"}

# 送入模型的最近对话轮数 / 历史总字符上限（防 prompt 膨胀）
HISTORY_MAX_TURNS = 6
HISTORY_MAX_CHARS = 2000


def _build_context(hits) -> str:
    """检索片段 → Prompt 上下文（带真实来源标签，禁止模型编造书名）。"""
    ctx_parts = []
    for i, (doc, _score) in enumerate(hits):
        src = doc.metadata.get("source", "未知来源")
        page = doc.metadata.get("page")
        src_label = f"{src}（第{page}页）" if page is not None else src
        ctx_parts.append(f"[片段{i+1}｜来源：{src_label}]\n{doc.page_content}")
    return "\n\n".join(ctx_parts)


def _build_history(history: list[dict] | None) -> str:
    """对话历史 → Prompt 段落。空历史返回"（无）"。"""
    if not history:
        return "（无）"
    lines: list[str] = []
    total = 0
    for h in history[-HISTORY_MAX_TURNS:]:
        role = h.get("role")
        content = (h.get("content") or "").strip()
        if not content or role not in ("user", "assistant"):
            continue
        if len(content) > 500:
            content = content[:500] + "…"
        lines.append(f"{'用户' if role == 'user' else '助教'}：{content}")
        total += len(content)
        if total >= HISTORY_MAX_CHARS:
            break
    return "\n".join(lines) or "（无）"


class LLMClient:
    """按 models.yaml 中的 chat 模型配置创建客户端，一套代码通吃多厂商。"""

    def __init__(self, model_id: str | None = None) -> None:
        registry = get_registry()
        self.model_id = model_id or get_settings().default_model
        conf = registry.chat_model(self.model_id)
        self.model_name = conf["model"]
        self.display_name = conf["name"]
        self._client = OpenAI(base_url=conf["base_url"], api_key=conf["api_key"])

    def _messages(self, question: str, hits, history: list[dict] | None = None, temperature: float = 0.3) -> list[dict]:
        context_text = _build_context(hits)
        user_message = SYSTEM_PROMPT.format(
            context=context_text,
            history=_build_history(history),
            question=question,
        )
        return [_SYSTEM_MSG, {"role": "user", "content": user_message}]

    def generate(self, question: str, hits, history: list[dict] | None = None, temperature: float = 0.3) -> str:
        """非流式：返回完整回答。history 为 [{role, content}, ...] 的最近对话。"""
        resp = self._client.chat.completions.create(
            model=self.model_name,
            messages=self._messages(question, hits, history, temperature),
            temperature=temperature,
        )
        return resp.choices[0].message.content or ""

    def generate_stream(self, question: str, hits, history: list[dict] | None = None, temperature: float = 0.3) -> Iterator[str]:
        """流式：逐段 yield 生成的文本增量。history 为 [{role, content}, ...] 的最近对话。"""
        stream = self._client.chat.completions.create(
            model=self.model_name,
            messages=self._messages(question, hits, history, temperature),
            temperature=temperature,
            stream=True,
        )
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content