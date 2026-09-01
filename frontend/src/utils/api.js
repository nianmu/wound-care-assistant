/**
 * 后端 API 封装（H5 开发期走 Vite 代理 /api → 127.0.0.1:8000；
 * 生产期 Nginx 同域反代 /api → 后端）
 */

const BASE = '/api'

export function getModels() {
  return uni.request({
    url: `${BASE}/models`,
    method: 'GET',
  }).then(res => res.data)
}

export function askQuestion(question, modelId, topK, history) {
  return uni.request({
    url: `${BASE}/ask`,
    method: 'POST',
    data: { question, model_id: modelId, top_k: topK, history: history || [] },
  }).then(res => res.data)
}

/**
 * SSE 流式问答。history 为最近对话 [{role: 'user'|'assistant', content}]，
 * 用于多轮追问（后端会结合历史理解提问意图，引用仍每次独立检索）。
 * onDelta(text) / onSources(sources, model) / onDone() / onError(msg)。
 * 返回一个 cancel() 用于中断请求（H5 端 fetch + ReadableStream）。
 */
export function askQuestionStream(question, modelId, topK, history, { onDelta, onSources, onDone, onError }) {
  let controller = null
  const start = async () => {
    controller = new AbortController()
    try {
      const resp = await fetch(`${BASE}/ask/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, model_id: modelId, top_k: topK, history: history || [] }),
        signal: controller.signal,
      })
      if (!resp.ok || !resp.body) {
        onError && onError(`请求失败（${resp.status}）`)
        return
      }
      const reader = resp.body.getReader()
      const decoder = new TextDecoder('utf-8')
      let buffer = ''
      for (;;) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        // SSE 帧以空行分隔：data: {...}\n\n
        let idx
        while ((idx = buffer.indexOf('\n\n')) >= 0) {
          const frame = buffer.slice(0, idx)
          buffer = buffer.slice(idx + 2)
          if (!frame.startsWith('data:')) continue
          let obj
          try { obj = JSON.parse(frame.slice(5).trim()) } catch (e) { continue }
          if (obj.type === 'delta') onDelta && onDelta(obj.text || '')
          else if (obj.type === 'sources') onSources && onSources(obj.sources || [], obj.model)
          else if (obj.type === 'done') { onDone && onDone(); return }
          else if (obj.type === 'error') onError && onError(obj.message)
        }
      }
    } catch (e) {
      if (e.name !== 'AbortError') onError && onError(e.message || '网络错误')
    }
  }
  start()
  return { cancel: () => controller && controller.abort() }
}

export function uploadFile(filePath, name) {
  return new Promise((resolve, reject) => {
    uni.uploadFile({
      url: `${BASE}/upload`,
      filePath,
      name: 'file',
      success: (res) => {
        try {
          resolve({ statusCode: res.statusCode, data: JSON.parse(res.data) })
        } catch (e) {
          reject(new Error('响应解析失败: ' + res.data))
        }
      },
      fail: (err) => reject(err),
    })
  })
}

export function getDocuments() {
  return uni.request({
    url: `${BASE}/documents`,
    method: 'GET',
  }).then(res => res.data)
}

export function getDocumentChunks(source) {
  return uni.request({
    url: `${BASE}/documents/${encodeURIComponent(source)}/chunks`,
    method: 'GET',
  }).then(res => res.data)
}

export function deleteDocument(source) {
  return uni.request({
    url: `${BASE}/documents/${encodeURIComponent(source)}`,
    method: 'DELETE',
  }).then(res => res.data)
}

// ===== 考试模块 =====

export function generateQuestions(opts) {
  return uni.request({
    url: `${BASE}/exam/generate`,
    method: 'POST',
    data: opts,
    timeout: 180000,   // AI 出题可能较慢
  }).then(res => res.data)
}

export function submitAnswers(questions, answers, mode, topic) {
  return uni.request({
    url: `${BASE}/exam/submit`,
    method: 'POST',
    data: { questions, answers, mode, topic },
    timeout: 30000,
  }).then(res => res.data)
}

export function getWrongBook() {
  return uni.request({
    url: `${BASE}/exam/wrong-book`,
    method: 'GET',
  }).then(res => res.data)
}

export function getStats() {
  return uni.request({
    url: `${BASE}/exam/stats`,
    method: 'GET',
  }).then(res => res.data)
}

export function getExamTopics() {
  return uni.request({
    url: `${BASE}/exam/topics`,
    method: 'GET',
  }).then(res => res.data)
}