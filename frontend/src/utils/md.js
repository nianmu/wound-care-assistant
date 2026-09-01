/**
 * 轻量 markdown → HTML 转换（聊天回答渲染用，跨端 rich-text 兼容）。
 *
 * 安全策略：先转义所有 HTML，再解析 markdown 标记，绝不透传原始 HTML。
 * 覆盖聊天场景常见语法：标题、加粗、斜体、行内代码、代码块、
 * 无序/有序列表、引用、链接、换行。
 */

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

/** 行内语法：**bold** *italic* `code` [text](url) */
function inline(md) {
  let s = escapeHtml(md)
  // 行内代码（先保护，避免内部标记被二次解析）
  const codes = []
  s = s.replace(/`([^`]+)`/g, (m, code) => {
    codes.push(code)
    return `\u0000${codes.length - 1}\u0000`
  })
  // 链接 [text](url)
  s = s.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (m, text, url) => {
    const safeUrl = /^https?:\/\//i.test(url) ? url : '#'
    return `<a href="${escapeHtml(safeUrl)}">${escapeHtml(text)}</a>`
  })
  // 加粗
  s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  // 斜体（粗体之后，避免误伤）
  s = s.replace(/(^|[^*])\*([^*\n]+)\*(?!\*)/g, '$1<em>$2</em>')
  // 还原行内代码
  s = s.replace(/\u0000(\d+)\u0000/g, (m, i) => `<code>${escapeHtml(codes[+i])}</code>`)
  return s
}

/**
 * 整段 markdown → HTML 字符串（rich-text nodes 直接可用）。
 */
export function mdToHtml(md) {
  if (!md) return ''
  const lines = String(md).split('\n')
  const html = []
  let inCode = false
  let codeBuf = []
  let listType = '' // '' | 'ul' | 'ol'

  const closeList = () => {
    if (listType) { html.push(`</${listType}>`); listType = '' }
  }
  const flushCode = () => {
    if (inCode) {
      html.push(`<pre><code>${escapeHtml(codeBuf.join('\n'))}</code></pre>`)
      codeBuf = []
      inCode = false
    }
  }
  const emitLine = (tag, content) => html.push(`<${tag}>${content}</${tag}>`)

  for (const raw of lines) {
    const line = raw.trimEnd()
    // 代码块围栏
    if (/^```/.test(line)) {
      if (inCode) { flushCode() } else { closeList(); flushCode(); inCode = true }
      continue
    }
    if (inCode) { codeBuf.push(line); continue }

    // 空行
    if (!line.trim()) { closeList(); continue }

    // 标题
    const h = line.match(/^(#{1,6})\s+(.+)$/)
    if (h) { closeList(); emitLine(`h${h[1].length}`, inline(h[2])); continue }

    // 无序列表
    const ul = line.match(/^[-*+]\s+(.+)$/)
    if (ul) {
      if (listType !== 'ul') { closeList(); html.push('<ul>'); listType = 'ul' }
      html.push(`<li>${inline(ul[1])}</li>`)
      continue
    }
    // 有序列表
    const ol = line.match(/^\d+[.)]\s+(.+)$/)
    if (ol) {
      if (listType !== 'ol') { closeList(); html.push('<ol>'); listType = 'ol' }
      html.push(`<li>${inline(ol[1])}</li>`)
      continue
    }

    // 引用
    const q = line.match(/^>\s?(.+)$/)
    if (q) { closeList(); emitLine('blockquote', inline(q[1])); continue }

    // 普通段落
    closeList()
    if (!line.trim()) continue
    if (html.length === 0) {
      html.push(`<p>${inline(line)}</p>`)
    } else {
      // 连续普通行合并进同一段落（保留换行）
      const last = html[html.length - 1]
      if (last.startsWith('<p>')) {
        html[html.length - 1] = last.slice(0, -4) + '<br/>' + inline(line) + '</p>'
      } else {
        html.push(`<p>${inline(line)}</p>`)
      }
    }
  }
  closeList()
  flushCode()
  return html.join('')
}

/**
 * 纯文本（用户消息、标题等）：只转义，不做任何标记解析。
 */
export function plain(s) {
  return escapeHtml(s)
}