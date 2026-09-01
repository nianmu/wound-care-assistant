<template>
	<view class="detail-page">
		<!-- 顶部操作区：返回已由导航栏提供；文档名 + 删除 -->
		<view class="header">
			<view class="header-main">
				<text class="doc-icon">📘</text>
				<view class="doc-title-wrap">
					<text class="doc-title">{{ source }}</text>
					<text class="doc-meta" v-if="loaded">{{ total }} 个切片</text>
				</view>
			</view>
			<button class="del-btn" :disabled="deleting" @click="confirmDelete">删除文档</button>
		</view>

		<!-- 切片列表 -->
		<scroll-view scroll-y class="chunk-list">
			<view class="chunk" v-for="(c, i) in chunks" :key="c.id">
				<view class="chunk-bar">
					<text class="chunk-no">#{{ i + 1 }}</text>
					<text class="chunk-page" v-if="c.page">第 {{ c.page }} 页</text>
					<text class="chunk-page" v-else>（无页码）</text>
				</view>
				<view class="chunk-content" :class="{ expanded: c.expanded }">
					<text class="chunk-text">{{ c.content }}</text>
				</view>
				<text class="expand-btn" @click="toggle(i)">
					{{ c.expanded ? '收起 ▲' : '展开全文 ▼' }}
				</text>
			</view>
			<view class="empty" v-if="loaded && !chunks.length">
				<text class="empty-text">该文档暂无切片</text>
			</view>
		</scroll-view>
	</view>
</template>

<script>
import { getDocumentChunks, deleteDocument } from '../../utils/api.js'

export default {
  data() {
    return {
      source: '',
      chunks: [],
      total: 0,
      loaded: false,
      deleting: false,
    }
  },
  onLoad(options) {
    this.source = decodeURIComponent(options.source || '')
    uni.setNavigationBarTitle({ title: this.source.length > 12 ? this.source.slice(0, 12) + '…' : this.source })
    this.load()
  },
  methods: {
    load() {
      getDocumentChunks(this.source).then((data) => {
        this.chunks = (data.chunks || []).map(c => ({ ...c, expanded: false }))
        this.total = data.total || 0
      }).catch(() => {
        uni.showToast({ title: '加载切片失败', icon: 'none' })
      }).finally(() => { this.loaded = true })
    },
    toggle(i) {
      this.chunks[i].expanded = !this.chunks[i].expanded
    },
    confirmDelete() {
      uni.showModal({
        title: '删除文档',
        content: `确定删除「${this.source}」吗？将移除其全部 ${this.total} 个切片。`,
        confirmColor: '#C45656',
        success: (res) => {
          if (res.confirm) this.doDelete()
        },
      })
    },
    doDelete() {
      this.deleting = true
      deleteDocument(this.source).then((data) => {
        uni.showToast({ title: `已删除 ${data.deleted_chunks} 个切片`, icon: 'success' })
        setTimeout(() => uni.navigateBack(), 600)
      }).catch(() => {
        uni.showToast({ title: '删除失败', icon: 'none' })
      }).finally(() => { this.deleting = false })
    },
  },
}
</script>

<style scoped>
/* box-sizing 防 padding 撑破高度 */
.detail-page { box-sizing: border-box; display: flex; flex-direction: column; height: calc(100vh - var(--window-top) - var(--window-bottom)); background: #F5F6FA; }
.header { display: flex; align-items: center; justify-content: space-between; padding: 24rpx; background: #FFFFFF; border-bottom: 1rpx solid #EEE; }
.header-main { display: flex; align-items: center; gap: 16rpx; max-width: 70%; }
.doc-icon { font-size: 40rpx; }
.doc-title-wrap { display: flex; flex-direction: column; min-width: 0; }
.doc-title { font-size: 28rpx; font-weight: 700; color: #333; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.doc-meta { font-size: 24rpx; color: #8A8F99; margin-top: 4rpx; }
.del-btn { background: #FDECEC; color: #C45656; font-size: 26rpx; border-radius: 12rpx; padding: 0 28rpx; line-height: 64rpx; }
.del-btn[disabled] { opacity: 0.5; }

.chunk-list { flex: 1; min-height: 0; padding: 20rpx 24rpx; overflow: hidden; box-sizing: border-box; }
.chunk { background: #FFFFFF; border-radius: 16rpx; padding: 20rpx 24rpx; margin-bottom: 20rpx; box-shadow: 0 2rpx 8rpx rgba(0,0,0,0.04); }
.chunk-bar { display: flex; align-items: center; gap: 16rpx; margin-bottom: 12rpx; }
.chunk-no { font-size: 24rpx; color: #FFFFFF; background: #0E7C7B; border-radius: 8rpx; padding: 4rpx 14rpx; }
.chunk-page { font-size: 24rpx; color: #8A8F99; }
.chunk-content { max-height: 200rpx; overflow: hidden; }
.chunk-content.expanded { max-height: none; }
.chunk-text { font-size: 26rpx; color: #444; line-height: 1.7; white-space: pre-wrap; }
.expand-btn { display: inline-block; margin-top: 12rpx; font-size: 24rpx; color: #0E7C7B; }
.empty { display: flex; justify-content: center; padding: 100rpx 0; }
.empty-text { font-size: 26rpx; color: #B0B6C0; }
</style>