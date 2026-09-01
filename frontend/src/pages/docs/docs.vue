<template>
	<view class="docs-page">
		<view class="summary" v-if="loaded">
			<text class="summary-num">{{ totalChunks }}</text>
			<text class="summary-label">个切片 / {{ sources.length }} 本教材</text>
		</view>

		<view class="doc-list" v-if="sources.length">
			<view class="doc-item" v-for="s in sources" :key="s" @click="openDetail(s)">
				<view class="doc-info">
					<text class="doc-icon">📘</text>
					<text class="doc-name">{{ s }}</text>
				</view>
				<text class="arrow">›</text>
			</view>
		</view>

		<view class="empty" v-if="loaded && !sources.length">
			<text class="empty-icon">🗂️</text>
			<text class="empty-text">知识库为空，请先到「上传」页添加教材</text>
		</view>

		<view class="empty" v-if="!loaded">
			<text class="empty-text">加载中…</text>
		</view>
	</view>
</template>

<script>
import { getDocuments } from '../../utils/api.js'

export default {
  data() {
    return {
      sources: [],
      totalChunks: 0,
      loaded: false,
    }
  },
  onShow() {
    this.refresh()
  },
  methods: {
    refresh() {
      getDocuments().then((data) => {
        this.sources = data.sources || []
        this.totalChunks = data.total_chunks || 0
      }).catch(() => {
        uni.showToast({ title: '无法连接后端服务', icon: 'none' })
      }).finally(() => { this.loaded = true })
    },
    openDetail(source) {
      // navigateTo 新页面（详情页）：删除操作在详情页顶部
      uni.navigateTo({
        url: `/pages/doc-detail/doc-detail?source=${encodeURIComponent(source)}`,
      })
    },
  },
}
</script>

<style scoped>
/* box-sizing: border-box 防止 padding 撑破 calc 高度导致无内容也出现滚动条 */
.docs-page { box-sizing: border-box; padding: 24rpx; background: #F5F6FA; min-height: calc(100vh - var(--window-top) - var(--window-bottom)); }
.summary { display: flex; align-items: baseline; gap: 12rpx; padding: 24rpx 8rpx; }
.summary-num { font-size: 56rpx; font-weight: 800; color: #0E7C7B; }
.summary-label { font-size: 26rpx; color: #8A8F99; }
.doc-list { background: #FFFFFF; border-radius: 20rpx; overflow: hidden; }
.doc-item { display: flex; align-items: center; justify-content: space-between; padding: 26rpx 28rpx; border-bottom: 1rpx solid #F0F0F0; }
.doc-info { display: flex; align-items: center; gap: 16rpx; max-width: 85%; }
.doc-icon { font-size: 36rpx; }
.doc-name { font-size: 28rpx; color: #333; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.arrow { font-size: 40rpx; color: #B0B6C0; }
.empty { display: flex; flex-direction: column; align-items: center; padding: 120rpx 0; gap: 20rpx; }
.empty-icon { font-size: 72rpx; }
.empty-text { font-size: 26rpx; color: #B0B6C0; }
</style>