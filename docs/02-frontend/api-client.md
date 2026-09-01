# 前端 API 封装与数据流

> `frontend/src/utils/api.js` 是前端访问后端的唯一通道。本文列出每个函数、参数、返回与调用方。

## 1. api.js 函数清单

| 函数 | 方法/路径 | 参数 | 返回 | 调用方 |
| :-- | :-- | :-- | :-- | :-- |
| `getModels()` | GET /api/models | — | `{default, chat_models[], embedding}` | chat, settings |
| `askQuestion()` | POST /api/ask | (question, modelId, topK, history) | `{answer, sources, model, top_k_used}` | （预留，未用） |
| `askQuestionStream()` | POST /api/ask/stream | (question, modelId, topK, history, callbacks) | — (SSE 回调) | chat |
| `uploadFile(filePath, name)` | POST /api/upload | multipart `file` | `{statusCode, data}` | upload |
| `getDocuments()` | GET /api/documents | — | `{sources, total_chunks}` | docs, exam |
| `getDocumentChunks(source)` | GET /api/documents/{source}/chunks | source（自动 encodeURIComponent） | `{source, total, chunks}` | doc-detail |
| `deleteDocument(source)` | DELETE /api/documents/{source} | source | `{deleted_chunks, source}` | doc-detail |
| `generateQuestions(opts)` | POST /api/exam/generate | `{count, qtype, source, topic, reuse_cached}`，**timeout 180s** | `{questions, generated, reused, skipped}` | exam |
| `submitAnswers(questions, answers, mode, topic)` | POST /api/exam/submit | 数组 | `{attempt_id, total, correct, score, details}` | quiz, wrong |
| `getWrongBook()` | GET /api/exam/wrong-book | — | `{total, questions}` | exam, wrong |
| `getStats()` | GET /api/exam/stats | — | `{overall_accuracy, by_topic, weak_topics, attempts}` | stats |
| `getExamTopics()` | GET /api/exam/topics | — | `{topics}` | （预留，章节练习） |

## 2. askQuestionStream — SSE 流式（重点）

```js
askQuestionStream(question, modelId, topK, history, {
  onDelta(text),      // 每次增量文本
  onSources(sources, model),
  onDone(),
  onError(msg),
}) → { cancel() }     // 停止（AbortController.abort）
```

- `history`：最近对话 `[{role: 'user'|'assistant', content}]`，随请求发后端（多轮追问用）。chat 页用 `buildHistory()` 从本地消息列表取最近 12 条拼装，**不含当前这句**；后端用它接地检索 + 注入 LLM Prompt，引用仍每次独立
- 无历史（首问）传 `[]` 即可

实现（H5 端）：
1. `fetch('/api/ask/stream')` + `AbortController`
2. `resp.body.getReader()` + `TextDecoder` 读流
3. 按 `\n\n` 切 SSE 帧，取 `data:` 后的 JSON，分发给回调
4. 返回 `cancel()` 供"停止"按钮中断

> 注：小程序端 fetch 流式支持有限——未来编译小程序时需换方案（如分包轮询或 webview 内实现）。

## 3. 错误处理约定

- `uni.request` 成功但后端返回错误码时，`err.data.detail` 携带后端错误信息
- 各页面 catch 里统一取 `(err && err.data && err.data.detail) || '…'` 提示用户
- 出题（generate）调用可能慢 → timeout 已设 180s，UI 用 `uni.showLoading('AI 出题中…')`

## 4. 数据流速查

```
问答:   chat ──askQuestionStream──▶ /api/ask/stream ──▶ LLM(流式) ──▶ onDelta/onSources
出题:   exam ──generateQuestions──▶ /api/exam/generate ──▶ 题目 → globalData → quiz
判分:   quiz ──submitAnswers──▶ /api/exam/submit ──▶ result(globalData.examResult)
错题:   wrong ──getWrongBook──▶ /api/exam/wrong-book
报告:   stats ──getStats──▶ /api/exam/stats
文档:   docs ──getDocuments──▶ /api/documents → doc-detail ──getDocumentChunks──▶ /{source}/chunks
上传:   upload ──uploadFile──▶ /api/upload
设置:   settings ──getModels──▶ /api/models → localStorage
```

## 5. 修改注意

- 后端加 API → 同步在 api.js 加函数（命名/参数/返回结构化）
- 中文参数（source 等）一律 `encodeURIComponent`（路径参数）
- 跨域：开发期 Vite 代理；生产期 Nginx 同域（无需 CORS）