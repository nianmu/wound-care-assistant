<template>
	<view class="chat-page">
		<!-- 自定义导航栏：左上角设置图标 -->
		<view class="nav-bar" :style="{ paddingTop: statusBarHeight + 'px' }">
			<view class="nav-inner">
				<view class="nav-left">
					<text class="app-title">造口护理学习助手</text>
				</view>
				<view class="nav-right">
					<text class="settings-icon" @click="openMenu">⚙️</text>
				</view>
			</view>
		</view>

		<!-- 对话列表：仅此区域内部滚动 -->
		<scroll-view scroll-y class="msg-list" :scroll-into-view="scrollInto">
			<view class="msg-inner">
				<view class="msg-row" v-for="(m, i) in messages" :key="i" :id="'msg-' + i">
					<view class="msg user" v-if="m.role === 'user'">
						<text>{{ m.content }}</text>
					</view>
					<view class="msg assistant" v-else>
						<rich-text class="msg-text" :nodes="m.html"></rich-text>
						<view class="sources" v-if="m.sources && m.sources.length">
							<text class="sources-label">📚 定位原文：</text>
							<view class="source-tags">
								<text class="source-tag" v-for="(s, si) in m.sources" :key="si">
									{{ s.source }}{{ s.pages && s.pages.length ? `·第${s.pages.join('、')}页` : '' }}
								</text>
							</view>
						</view>
					</view>
				</view>
				<view class="msg-row" v-if="loading">
					<view class="msg assistant">
						<text class="thinking" v-if="!streaming">正在检索教材并思考…</text>
						<text class="thinking" v-else>⏳ 生成中…（可点「停止」）</text>
					</view>
				</view>
			</view>
		</scroll-view>

		<!-- 输入区 -->
		<view class="input-bar">
			<input class="input" v-model="question" placeholder="输入问题，如：回肠造口渗漏怎么办？" confirm-type="send" @confirm="send" />
			<button class="send-btn" v-if="!streaming" :disabled="loading || !question.trim()" @click="send">发送</button>
			<button class="stop-btn" v-else @click="stop">停止</button>
		</view>
	</view>
</template>

<script>
import { getModels, askQuestionStream } from '../../utils/api.js'
import { mdToHtml as renderMd } from '../../utils/md.js'

const KEY_MODEL = 'wc_model_id'
const KEY_TOPK = 'wc_top_k'

export default {
  data() {
    return {
      statusBarHeight: 20,
      question: '',
      messages: [],
      loading: false,
      streaming: false,
      streamAbort: null,
      scrollInto: '',
      modelId: '',
      topK: 5,
    }
  },
  onLoad() {
    try {
      const info = uni.getSystemInfoSync()
      this.statusBarHeight = info.statusBarHeight || 20
    } catch (e) { /* ignore */ }
    this.modelId = uni.getStorageSync(KEY_MODEL) || ''
    this.topK = uni.getStorageSync(KEY_TOPK) || 5
    // 没有默认时拉取后端默认模型
    if (!this.modelId) {
      getModels().then((data) => {
        this.modelId = data.default || (data.chat_models && data.chat_models[0] && data.chat_models[0].id) || ''
      }).catch(() => {})
    }
  },
  // 从设置页/上传页返回时刷新本地缓存（用户可能刚改过模型参数）
  onShow() {
    const m = uni.getStorageSync(KEY_MODEL)
    if (m) this.modelId = m
    const k = uni.getStorageSync(KEY_TOPK)
    if (k) this.topK = k
  },
  methods: {
    openMenu() {
      uni.showActionSheet({
        itemList: ['📤 上传文档', '🤖 切换对话模型', '🧹 清空对话'],
        success: (res) => {
          if (res.tapIndex === 0) {
            uni.navigateTo({ url: '/pages/upload/upload' })
          } else if (res.tapIndex === 1) {
            uni.navigateTo({ url: '/pages/settings/settings' })
          } else if (res.tapIndex === 2) {
            this.clearHistory()
          }
        },
      })
    },
    clearHistory() {
      this.messages = []
    },
    buildHistory() {
      // 取最近若干条完整的 user/assistant 文本（不含当前这句）作为多轮上下文
      const items = []
      const msgs = this.messages
      for (let i = msgs.length - 1; i >= 0 && items.length < 12; i--) {
        const m = msgs[i]
        const content = (m.content || '').trim()
        if ((m.role === 'user' || m.role === 'assistant') && content) {
          items.unshift({ role: m.role, content })
        }
      }
      return items
    },
    send() {
      const q = this.question.trim()
      if (!q || this.loading) return
      // 先取历史（不含当前这句），随请求发给后端支持多轮追问
      const history = this.buildHistory()
      this.messages.push({ role: 'user', content: q })
      this.question = ''
      this.loading = true
      this.scrollToBottom()
      // 预热一个空的 assistant 消息，流式增量往里填（html 为预渲染的 markdown）
      const idx = this.messages.length
      this.messages.push({ role: 'assistant', content: '', html: '', sources: null })
      this.streaming = true

      // 每次发送前重新读设置（用户可能刚改过）；storage 为空则用已刷新的 modelId
      const modelId = uni.getStorageSync(KEY_MODEL) || this.modelId
      const topK = uni.getStorageSync(KEY_TOPK) || this.topK

      this.streamAbort = askQuestionStream(q, modelId, topK, history, {
        onDelta: (text) => {
          const m = this.messages[idx]
          m.content += text
          m.html = renderMd(m.content)
          this.scrollToBottom()
        },
        onSources: (sources, model) => {
          this.messages[idx].sources = sources
          this.messages[idx].model = model
        },
        onDone: () => {
          this.finishStream()
          if (!this.messages[idx].content.trim()) {
            this.messages[idx].content = '（未返回内容）'
            this.messages[idx].html = renderMd(this.messages[idx].content)
          }
        },
        onError: (msg) => {
          this.finishStream()
          if (!this.messages[idx].content) {
            this.messages[idx].content = `⚠️ ${msg || '请求失败'}`
            this.messages[idx].html = renderMd(this.messages[idx].content)
          }
        },
      })
    },
    stop() {
      if (this.streamAbort) {
        try { this.streamAbort.cancel() } catch (e) { /* ignore */ }
      }
      this.finishStream()
    },
    finishStream() {
      this.streaming = false
      this.loading = false
      this.streamAbort = null
      this.scrollToBottom()
    },
    scrollToBottom() {
      this.$nextTick(() => {
        this.scrollInto = 'msg-' + (this.messages.length - 1)
      })
    },
  },
}
</script>

<style scoped>
/* 自定义导航栏高度 = 状态栏 + 44px 内容区 */
.chat-page { display: flex; flex-direction: column; height: calc(100vh - var(--window-bottom)); background: #F5F6FA; overflow: hidden; }
.nav-bar { background: #0E7C7B; }
.nav-inner { display: flex; align-items: center; justify-content: space-between; height: 44px; padding: 0 24rpx; }
.app-title { color: #FFFFFF; font-size: 32rpx; font-weight: 700; }
.settings-icon { font-size: 40rpx; color: #FFFFFF; padding: 8rpx 8rpx 8rpx 24rpx; }

/* 消息区：flex 子项必须 min-height:0 才能正确收缩出滚动区域 */
.msg-list { flex: 1; min-height: 0; overflow: hidden; }
.msg-inner { padding: 20rpx 24rpx; }
.msg-row { margin-bottom: 20rpx; }
.msg { max-width: 85%; padding: 18rpx 24rpx; border-radius: 16rpx; font-size: 28rpx; line-height: 1.6; word-break: break-word; }
.msg.user { background: #0E7C7B; color: #FFFFFF; margin-left: auto; }
.msg.assistant { background: #FFFFFF; color: #333; box-shadow: 0 2rpx 8rpx rgba(0,0,0,0.04); }
.msg-text { white-space: pre-wrap; }
/* rich-text 内部标签排版 */
.msg-text p { margin: 0 0 8rpx 0; line-height: 1.6; }
.msg-text h1, .msg-text h2, .msg-text h3, .msg-text h4 { font-weight: 700; margin: 12rpx 0 8rpx 0; line-height: 1.5; }
.msg-text h1 { font-size: 34rpx; } .msg-text h2 { font-size: 32rpx; } .msg-text h3 { font-size: 30rpx; } .msg-text h4 { font-size: 28rpx; }
.msg-text ul, .msg-text ol { margin: 8rpx 0; padding-left: 32rpx; }
.msg-text li { margin: 4rpx 0; line-height: 1.6; }
.msg-text strong { font-weight: 700; }
.msg-text em { font-style: italic; }
.msg-text blockquote { border-left: 4rpx solid #0E7C7B; padding-left: 16rpx; color: #666; margin: 8rpx 0; }
.msg-text code { background: #F0F0F0; border-radius: 6rpx; padding: 0 8rpx; font-size: 24rpx; color: #C45656; }
.msg-text pre { background: #2D2D2D; color: #EEE; border-radius: 10rpx; padding: 16rpx; margin: 8rpx 0; overflow-x: auto; }
.msg-text pre code { background: transparent; color: inherit; padding: 0; }
.msg-text a { color: #0E7C7B; text-decoration: underline; }
.sources { margin-top: 12rpx; padding-top: 12rpx; border-top: 1rpx solid #EEE; }
.sources-label { font-size: 24rpx; color: #8A8F99; }
.source-tags { margin-top: 8rpx; display: flex; flex-wrap: wrap; gap: 12rpx; }
.source-tag { font-size: 24rpx; color: #0E7C7B; background: #EAF4F4; padding: 4rpx 16rpx; border-radius: 8rpx; }
.thinking { color: #8A8F99; font-size: 26rpx; }
.input-bar { display: flex; align-items: center; gap: 16rpx; padding: 16rpx 24rpx; background: #FFFFFF; border-top: 1rpx solid #EEE; }
.input { flex: 1; height: 72rpx; background: #F5F6FA; border-radius: 36rpx; padding: 0 28rpx; font-size: 28rpx; }
.send-btn { background: #0E7C7B; color: #FFFFFF; font-size: 28rpx; border-radius: 36rpx; padding: 0 40rpx; line-height: 72rpx; height: 72rpx; }
.send-btn[disabled] { opacity: 0.5; }
.stop-btn { background: #C45656; color: #FFFFFF; font-size: 28rpx; border-radius: 36rpx; padding: 0 40rpx; line-height: 72rpx; height: 72rpx; }
</style>