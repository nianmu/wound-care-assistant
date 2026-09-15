/**
 * 后端 API 封装（H5 开发期走 Vite 代理 /api → 127.0.0.1:8000；
 * 生产期 Nginx 同域反代 /api → 后端）
 *
 * 账户体系（B 模式）：考试类接口需要登录，请求自动带 Authorization:
 * Bearer <JWT>；401 时清登录态并引导去登录页。问答类不强制登录。
 */

const BASE = '/api'

const KEY_TOKEN = 'wc_token'
const KEY_USER = 'wc_user'

// ===== 登录态工具 =====

export function getToken() {
  return uni.getStorageSync(KEY_TOKEN) || ''
}

export function getUser() {
  return uni.getStorageSync(KEY_USER) || null
}

export function setAuth(token, user) {
  uni.setStorageSync(KEY_TOKEN, token)
  uni.setStorageSync(KEY_USER, user)
}

export function clearAuth() {
  uni.removeStorageSync(KEY_TOKEN)
  uni.removeStorageSync(KEY_USER)
}

function isLoginPage() {
  const pages = getCurrentPages()
  const cur = pages[pages.length - 1]
  return cur && cur.route === 'pages/auth/login'
}

function redirectLogin() {
  if (isLoginPage()) return
  uni.showToast({ title: '请先登录', icon: 'none' })
  setTimeout(() => uni.navigateTo({ url: '/pages/auth/login' }), 500)
}

/**
 * 统一请求：自动带 Bearer；auth=true 时 401 → 清登录态跳登录页。
 * resolve(res.data)；业务错误/reject({data})（含 detail）。
 */
function request({ url, method = 'GET', data, auth = false, timeout = 30000 }) {
  return new Promise((resolve, reject) => {
    const token = getToken()
    const header = { 'Content-Type': 'application/json' }
    if (token) header.Authorization = `Bearer ${token}`
    if (auth && !token) {
      redirectLogin()
      reject({ data: { detail: '未登录' } })
      return
    }
    uni.request({
      url, method, data, header, timeout,
      success: (res) => {
        if (res.statusCode === 401 && auth) {
          clearAuth()
          redirectLogin()
          reject({ data: res.data })
        } else if (res.statusCode >= 400) {
          reject({ data: res.data })
        } else {
          resolve(res.data)
        }
      },
      fail: (err) => reject(err),
    })
  })
}

// ===== 认证 =====

export function register(username, password, displayName, inviteCode) {
  return request({
    url: `${BASE}/auth/register`, method: 'POST',
    data: { username, password, display_name: displayName || undefined, invite_code: inviteCode || '' },
  })
}

export function login(username, password) {
  return request({
    url: `${BASE}/auth/login`, method: 'POST',
    data: { username, password },
  })
}

export function getMe() {
  return request({ url: `${BASE}/auth/me`, auth: true })
}

// ===== 问答 =====

export function getModels() {
  return request({ url: `${BASE}/models` })
}

export function askQuestion(question, modelId, topK, history, auth = false) {
  return request({
    url: `${BASE}/ask`, method: 'POST',
    data: { question, model_id: modelId, top_k: topK, history: history || [] },
    auth, timeout: 120000,
  })
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
      const headers = { 'Content-Type': 'application/json' }
      const token = getToken()
      if (token) headers.Authorization = `Bearer ${token}`
      const resp = await fetch(`${BASE}/ask/stream`, {
        method: 'POST',
        headers,
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

// ===== 文档 =====

export function uploadFile(filePath, name) {
  return new Promise((resolve, reject) => {
    const header = {}
    const token = getToken()
    if (token) header.Authorization = `Bearer ${token}`
    uni.uploadFile({
      url: `${BASE}/upload`,
      filePath,
      name: 'file',
      header,
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
  return request({ url: `${BASE}/documents` })
}

export function getDocumentChunks(source) {
  return request({ url: `${BASE}/documents/${encodeURIComponent(source)}/chunks` })
}

export function deleteDocument(source) {
  return request({
    url: `${BASE}/documents/${encodeURIComponent(source)}`,
    method: 'DELETE',
    auth: true,          // 高危操作：需登录，且仅管理员（403 由后端拦截）
  })
}

// ===== 考试模块（需登录，auth=true） =====

export function generateQuestions(opts) {
  return request({
    url: `${BASE}/exam/generate`,
    method: 'POST',
    data: opts,
    auth: true,
    timeout: 180000,   // AI 出题可能较慢
  })
}

export function submitAnswers(questions, answers, mode, topic) {
  return request({
    url: `${BASE}/exam/submit`,
    method: 'POST',
    data: { questions, answers, mode, topic },
    auth: true,
    timeout: 30000,
  })
}

export function getWrongBook() {
  return request({ url: `${BASE}/exam/wrong-book`, auth: true })
}

export function getStats() {
  return request({ url: `${BASE}/exam/stats`, auth: true })
}

export function getExamTopics() {
  return request({ url: `${BASE}/exam/topics`, auth: true })
}