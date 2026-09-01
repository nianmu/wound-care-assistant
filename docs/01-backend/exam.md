# 出题引擎与判分 — exam/

> 职责：AI 根据教材自动出题（三道闸防错题）、判分、错题本、学习统计。SQLite 存储见 [05-data.md](../05-data.md)。

## 1. 模块文件

| 文件 | 职责 |
| :-- | :-- |
| `engine.py` | 出题引擎（generate_questions + Prompt 构造 + 种子选取） |
| `grader.py` | 判分（grade）+ 错题/统计落库 |
| `store.py` | sqlite 全部 CRUD |
| `router.py` | /api/exam/* HTTP 层 |

## 2. 出题流程（engine.py）

```
generate_questions(count, qtype, source, topic, reuse_cached)
  │ ① 校验知识库非空（空 → 返回 error）
  │ ② 决定题型列表：qtype 指定 → [qtype]*count；不指定 → DEFAULT_MIX 6:2:2 展开
  │ ③ 读缓存：scope_key = md5(source|topic|qtypes)，已出题优先复用（reuse_cached=true）
  │ ④ _fetch_seed_docs：种子段落 → 按 (source,page) 去重（去重前置到并行之前）
  │ ⑤ _generate_many：ThreadPoolExecutor(GENERATE_WORKERS=3) 并行 LLM 出题
  │ ⑥ 置信度闸 → 入库（只生成 need+4 个冗余任务，缓存命中多时不整批生成）
  └ 返回 {questions, generated, reused, skipped}
```

> **性能红线**：`generate_questions` 含多次 LLM 网络调用，路由层（router.py
> `/api/exam/generate`）必须用 `await asyncio.to_thread(...)` 调用——否则单
> worker 下整个事件循环被阻塞，其它接口（文档列表等）全部排队（曾在上线后复现）。

### scope_key 缓存

- `md5("源|主题|题型列表")` → 同范围反复出题时命中缓存，**0.7s 返回 5 题**
- 题库在 sqlite `exam_questions`，`used_count` 累计使用次数

### _fetch_seed_docs — 种子段落选取

- 指定 `topic`：用主题词 `similarity_search` 检索相关片段，source 过滤
- 未指定：宽泛检索一批 → **按来源轮转**（各教材分散取材，不集中在一本书相邻页）
- 去重：有页码按 `(source, page)`；**无页码**（旧教材）按 `(source, 内容前200字md5)`

### 三道闸（防错题核心）

| 闸 | 实现 | 失败处理 |
| :-- | :-- | :-- |
| ① 有据可依 | Prompt 硬约束：答案须出自片段；选项干扰项专业 | 判定不通过 → 放弃该段 |
| ② 置信度自检 | Prompt 要求模型输出 `confidence`(0~1)，`<0.7` 丢弃 | skipped++ |
| ③ 缓存复用 | 同 scope 优先用已出题 | 数量不足才生成新题 |

### 并行生成（_generate_many）

- 每道题一次独立 LLM 调用、相互无依赖 → `ThreadPoolExecutor(max_workers=GENERATE_WORKERS=5)` 并行（调用为网络等待型，5 路并发在 2 核服务器上无 CPU 竞争，10 题 2 波次）
- 单题失败/超时只记 `skipped`，不拖垮整场；GIL 下共享同一 LLMClient（OpenAI 客户端线程安全）
- 只提交 `need + 4` 个冗余任务：缓存命中多时（如复用 5/6 题）不会整批生成浪费 LLM 调用

### 出题 Prompt（_build_exam_prompt）

每段一道题，要求输出 **严格 JSON**：

```json
{ "question": "题干（案例题含病例场景描述）",
  "options": ["A. …", "B. …", "C. …", "D. …"],
  "answer": ["B"],
  "explanation": "解析，引用教材原文要点",
  "topic": "主题标签（3~8字）",
  "confidence": 0.9 }
```

- 生成后 `json.loads` 解析（兼容 ```json 包裹），校验：question/options(4个)/answer 齐全
- 温度 0.7（鼓励多样性）；输出后题库标签 topic 用于"章节练习"

### 题型定义

| qtype | 说明 | 判分 |
| :-- | :-- | :-- |
| single | 单选题，4 选 1 | 完全匹配 |
| multi | 多选题，2~3 正确 | **集合完全一致**（多选少选均错） |
| case | 临床情景案例分析，4 选 1 | 完全匹配 |
| （混合） | DEFAULT_MIX = {single:6, multi:2, case:2} | — |

## 3. 判分（grader.py）

```
grade(questions, answers, mode, topic)
  for 每题:
    std = set(answer), user = set(user_answer)
    correct = (user == std)
    details.append({…, correct, user_answer, explanation, source, page})
    store.record_answer(id, correct)          # 统计
    if not correct: store.add_wrong(id)        # 错题本
    else: store.mark_wrong_resolved(id)        # 清错
  save_attempt(...)  → 成绩记录
  return {attempt_id, total, correct, score, details}
  # score = round(correct/total*100)
```

## 4. 错题本语义

- 答错 → `wrong_book` 记录（未解决 resolved=0），重复错 wrong_count 累加
- 答对 → resolved=1（从"待巩固"消失）
- 前端错题本"已掌握，移出"= 用正确答案重答一次触发 resolve

## 5. 学习统计（store.py）

- `question_stats`：每题 attempts/correct（按题聚合）
- `topic_stats()`：按主题聚合正确率（JOIN exam_questions.topic）
- `weak_topics`：attempts>=3 的按正确率升序前 3（学习报告 ⚠️ 提示）

## 6. 修改指南

| 想改什么 | 位置 |
| :-- | :-- |
| 题型配比 | `engine.py` DEFAULT_MIX |
| 置信度阈值 | `engine.py` CONFIDENCE_THRESHOLD (0.7) |
| 出题 Prompt | `engine.py` _build_exam_prompt |
| 判分规则 | `grader.py` grade（多选集合比较处） |
| 新题型 | engine QTYPE_LABEL + Prompt + grader 分支 + 前端类型标签 |

## 7. 测试

`tests/test_exam.py` 覆盖：题目缓存/读取、单选多选判分、错题流（答错→收集→答对→移出）、统计聚合。存储层用临时库隔离（fixture monkeypatch `store._db_path`）。