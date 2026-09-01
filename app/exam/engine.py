"""出题引擎：基于教材知识库，AI 自动生成题目（三道闸防错题）。

生成阶段并行调用 LLM（ThreadPoolExecutor，与核数匹配），10 题从串行 ~60s
降到 ~20s；GIL 下 OpenAI 客户端线程安全，可共享同一 LLMClient。
"""
from __future__ import annotations

import hashlib
import json
import random
from concurrent.futures import ThreadPoolExecutor

from app.config import get_settings
from app.generation.llm import LLMClient
from app.retrieval.retriever import get_store
from app.exam import store

# 题型映射（Prompt 用）
QTYPE_LABEL = {
    "single": "单选题（4 个选项，仅 1 个正确答案）",
    "multi": "多选题（4 个选项，2~3 个正确答案）",
    "case": "临床情景案例分析题（给出具体病例情景后提问，4 个选项，仅 1 个正确答案）",
}

# 置信度阈值：低于此值题目不入库
CONFIDENCE_THRESHOLD = 0.7

DEFAULT_MIX = {"single": 6, "multi": 2, "case": 2}  # 模拟考试默认配比（每 10 题）

# LLM 生成并发数：调用为网络等待型（~95% 时间在等 API 返回），5 路并发
# 在 2 核服务器上不会形成 CPU 竞争，10 题由 4 波次降到 2 波次
GENERATE_WORKERS = 5


def _scope_key(source: str | None, topic: str | None, qtypes: list[str]) -> str:
    raw = f"{source or '*'}|{topic or '*'}|{','.join(sorted(qtypes))}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _build_exam_prompt(qtype: str, excerpt: str, source: str, page: int | None) -> str:
    """单题生成 Prompt。答案必须出自 excerpt，并输出 JSON。"""
    return f"""你是国际造口治疗师（ET）考试命题专家。请根据下面的【教材原文】出一道考题。

【教材原文】（来源：{source}{f'，第{page}页' if page else ''}）
{excerpt}

【题目要求】
- 题型：{QTYPE_LABEL[qtype]}
- 题干要贴合临床实际；案例题需先描述一个具体病例场景（患者情况、造口/伤口/失禁状态），再提问
- 4 个选项用 A/B/C/D 标注；干扰项要专业且似是而非，不能一眼看出错误
- 正确答案必须能在【教材原文】中找到明确依据

【输出格式】严格输出 JSON，不要多余文字：
{{
  "question": "题干（案例题含病例描述）",
  "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
  "answer": ["B"],
  "explanation": "解析，说明为什么选此项，引用教材原文要点",
  "topic": "主题标签（如：压疮分期/造口用品/失禁分类/肠道准备等，3~8个字）",
  "confidence": 0.0
}}
confidence 是 0~1 的实数，代表你对"答案有教材依据、题目无歧义"的把握。"""


def generate_questions(
    count: int = 5,
    qtype: str | None = None,          # single|multi|case|None(混合)
    source: str | None = None,         # 指定教材
    topic: str | None = None,          # 主题标签
    reuse_cached: bool = True,
) -> dict:
    """出题主流程。返回 {questions, generated, reused, skipped}。

    三道闸：
      1) 有据可依：检索真实教材切片，Prompt 硬约束
      2) 置信度自检：confidence < 阈值丢弃
      3) 缓存复用：同范围复用已出题目
    """
    settings = get_settings()
    store_inst = get_store()
    if store_inst.count() == 0:
        return {"error": "知识库为空：请先在「文档管理」上传教材。", "questions": []}

    # 题型配比
    qtypes = [qtype] if qtype else _expand_mix(DEFAULT_MIX, count)

    rng = random.Random()  # 局部实例，保证并发安全

    # 1) 读缓存（同范围已出的题优先复用）
    scope = _scope_key(source, topic, qtypes)
    cached = store.get_questions_by_scope(scope) if reuse_cached else []
    reuse_limit = min(len(cached), count)
    selected = rng.sample(cached, reuse_limit) if reuse_limit else []
    store.touch_questions([q["id"] for q in selected])
    need = count - len(selected)
    if need <= 0:
        questions = selected
        random.shuffle(questions)
        return {
            "questions": questions,
            "generated": 0,
            "reused": len(selected),
            "skipped": 0,
        }

    # 2) 检索种子段落（按范围过滤 + 随机），并按 (来源,页码) 去重：
    #    同一来源页只出一题（与旧逻辑一致），去重前置到并行生成之前
    seed_docs = _fetch_seed_docs(store_inst, source, topic, max(need * 4, 6))
    seen_keys: set[tuple] = set()
    unique_docs: list = []
    for doc in seed_docs:
        src = doc.metadata.get("source", "未知来源")
        page = doc.metadata.get("page")
        if page is not None:
            key = (src, page)
        else:
            key = (src, hashlib.md5(doc.page_content[:200].encode("utf-8")).hexdigest())
        if key in seen_keys:
            continue
        seen_keys.add(key)
        unique_docs.append(doc)

    # 3) 并行生成（每道题一次独立 LLM 调用，相互无依赖），置信度闸
    llm = LLMClient()
    tasks = [
        (qtypes[i % len(qtypes)] if len(qtypes) > 1 else qtypes[0], doc.page_content,
         doc.metadata.get("source", "未知来源"), doc.metadata.get("page"))
        for i, doc in enumerate(unique_docs)
    ]
    # 只需 need 题：给少量冗余吸收"跳过/低置信度"，避免缓存命中多时仍整批生成
    tasks = tasks[: min(len(tasks), need + 4)]
    raw_results = _generate_many(llm, tasks)

    generated: list[dict] = []
    skipped = 0
    for q, (qtype, _excerpt, src, page) in zip(raw_results, tasks):
        if len(generated) >= need:
            break
        if not q:
            skipped += 1
            continue
        if (q.get("confidence") or 0) < CONFIDENCE_THRESHOLD:
            skipped += 1
            continue
        q["source"] = src
        q["page"] = page
        q["qtype"] = qtype
        qid = store.cache_question(scope, q)
        q["id"] = qid
        generated.append(q)

    questions = selected + generated
    random.shuffle(questions)
    return {
        "questions": questions,
        "generated": len(generated),
        "reused": len(selected),
        "skipped": skipped,
    }


def _generate_many(llm: LLMClient, tasks: list[tuple]) -> list[dict | None]:
    """并行调用 LLM 逐题生成，按任务顺序返回（失败返回 None，不中断整体）。"""
    results: list[dict | None] = [None] * len(tasks)
    with ThreadPoolExecutor(max_workers=GENERATE_WORKERS) as ex:
        futures = [
            ex.submit(_generate_one, llm, qtype, excerpt, src, page)
            for qtype, excerpt, src, page in tasks
        ]
        for i, f in enumerate(futures):
            try:
                results[i] = f.result()
            except Exception:  # noqa: BLE001 - 单题失败记 skipped，不拖垮整场考试
                results[i] = None
    return results


def _expand_mix(mix: dict, count: int) -> list[str]:
    """按配比展开题型列表（如 count=5 → [single,single,single,multi,case]）。"""
    total_ratio = sum(mix.values())
    result: list[str] = []
    for qt, ratio in mix.items():
        n = round(count * ratio / total_ratio)
        result.extend([qt] * n)
    # 修正舍入误差
    while len(result) < count:
        result.append("single")
    while len(result) > count:
        result.pop()
    return result


def _fetch_seed_docs(store_inst, source: str | None, topic: str | None, n: int) -> list:
    """按范围取种子段落：topic 优先检索；否则多来源均匀随机采样。"""
    if topic:
        try:
            hits = store_inst.similarity_search(topic, k=n * 2)
            docs = [d for d, s in hits]
            if source:
                docs = [d for d in docs if d.metadata.get("source") == source]
            if docs:
                return docs[:n]
        except Exception:
            pass
    # 随机采样：用宽泛检索拿一批段落后，按来源轮转分散
    try:
        hits = store_inst.similarity_search("造口 伤口 失禁 护理 评估 处理", k=max(n * 6, 12))
        docs = [d for d, s in hits]
    except Exception:
        docs = []
    if source:
        docs = [d for d in docs if d.metadata.get("source") == source]
    # 各来源轮转取，保证覆盖面
    by_source: dict[str, list] = {}
    for d in docs:
        by_source.setdefault(d.metadata.get("source", "unknown"), []).append(d)
    pooled: list = []
    keys = list(by_source.keys())
    random.shuffle(keys)
    while len(pooled) < n and by_source:
        for k in list(by_source.keys()):
            if by_source[k]:
                pooled.append(by_source[k].pop(0))
            if not by_source[k]:
                del by_source[k]
            if len(pooled) >= n:
                break
    return pooled[:n] or docs[:n]


def _generate_one(llm: LLMClient, qtype: str, excerpt: str, source: str, page: int | None) -> dict | None:
    prompt = _build_exam_prompt(qtype, excerpt, source, page)
    raw = llm._client.chat.completions.create(
        model=llm.model_name,
        messages=[
            {"role": "system", "content": "你是国际造口治疗师（ET）考试命题专家，严格按用户要求输出 JSON。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
    )
    text = (raw.choices[0].message.content or "").strip()
    # 提取 JSON（模型可能包在 ```json 里）
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    q = json.loads(text)
    # 基础校验
    if not q.get("question") or not q.get("options") or not q.get("answer"):
        return None
    if len(q.get("options", [])) != 4:
        return None
    q["confidence"] = float(q.get("confidence", 0) or 0)
    return q


def list_topics() -> list[str]:
    """已出题目的主题列表（章节练习选择用）。"""
    return _topics_from_db()


def _topics_from_db() -> list[str]:
    with store.get_conn() as conn:
        rows = conn.execute("SELECT DISTINCT topic FROM exam_questions WHERE topic IS NOT NULL AND topic!=''").fetchall()
    return sorted({r["topic"] for r in rows})