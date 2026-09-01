<template>
	<view class="stats-page">
		<!-- 总体 -->
		<view class="overall">
			<view class="overall-main">
				<text class="overall-score">{{ stats.overall_accuracy || 0 }}</text>
				<text class="overall-unit">% 总体正确率</text>
			</view>
			<text class="overall-sub">共作答 {{ stats.total_answered || 0 }} 题</text>
		</view>

		<!-- 薄弱点提示 -->
		<view class="weak" v-if="stats.weak_topics && stats.weak_topics.length">
			<text class="weak-title">⚠️ 需要加强的主题</text>
			<view class="weak-item" v-for="w in stats.weak_topics" :key="w.topic">
				<view class="weak-info">
					<text class="weak-name">{{ w.topic }}</text>
					<text class="weak-detail">{{ w.correct }}/{{ w.attempts }} 题 · {{ w.accuracy }}%</text>
				</view>
				<view class="weak-bar"><view class="weak-bar-fill" :style="{ width: w.accuracy + '%' }"></view></view>
			</view>
		</view>

		<!-- 主题分布 -->
		<view class="section" v-if="stats.by_topic && stats.by_topic.length">
			<text class="section-title">📊 各主题正确率</text>
			<view class="topic-row" v-for="t in stats.by_topic" :key="t.topic">
				<view class="topic-info">
					<text class="topic-name">{{ t.topic }}</text>
					<text class="topic-detail">{{ t.correct }}/{{ t.attempts }} 题</text>
				</view>
				<view class="topic-bar"><view class="topic-bar-fill" :style="{ width: t.accuracy + '%' }"></view></view>
				<text class="topic-pct">{{ t.accuracy }}%</text>
			</view>
		</view>

		<!-- 最近记录 -->
		<view class="section" v-if="stats.attempts && stats.attempts.length">
			<text class="section-title">🕐 最近做题记录</text>
			<view class="attempt-row" v-for="a in stats.attempts.slice(0, 8)" :key="a.id">
				<view class="attempt-info">
					<text class="attempt-mode">{{ modeLabel(a.mode) }}</text>
					<text class="attempt-time">{{ a.created_at.slice(5, 16) }}</text>
				</view>
				<text class="attempt-score" :class="{ good: a.score >= 70 }">{{ a.score }}分（{{ a.correct }}/{{ a.total }}）</text>
			</view>
		</view>

		<view class="empty" v-if="loaded && !stats.total_answered">
			<text class="empty-icon">📈</text>
			<text class="empty-text">还没有做题记录，去「练一练」开始吧</text>
		</view>
	</view>
</template>

<script>
import { getStats } from '../../utils/api.js'

export default {
  data() {
    return { stats: {}, loaded: false }
  },
  onShow() {
    getStats().then((d) => { this.stats = d || {} })
      .catch(() => uni.showToast({ title: '加载失败', icon: 'none' }))
      .finally(() => { this.loaded = true })
  },
  methods: {
    modeLabel(m) { return { practice: '练习', exam: '模拟考', chapter: '章节' }[m] || m },
  },
}
</script>

<style scoped>
.stats-page { box-sizing: border-box; padding: 24rpx; background: #F5F6FA; min-height: calc(100vh - var(--window-top) - var(--window-bottom)); }
.overall { display: flex; flex-direction: column; align-items: center; padding: 40rpx 24rpx; background: linear-gradient(135deg, #0E7C7B, #14A99A); border-radius: 24rpx; margin-bottom: 24rpx; color: #FFF; }
.overall-main { display: flex; align-items: baseline; gap: 8rpx; }
.overall-score { font-size: 100rpx; font-weight: 800; }
.overall-unit { font-size: 28rpx; }
.overall-sub { font-size: 26rpx; opacity: 0.9; margin-top: 8rpx; }

.weak { background: #FFF7F0; border-radius: 20rpx; padding: 24rpx; margin-bottom: 24rpx; border: 2rpx solid #F0D9C0; }
.weak-title { display: block; font-size: 28rpx; font-weight: 700; color: #C45656; margin-bottom: 16rpx; }
.weak-item { margin-bottom: 16rpx; }
.weak-info { display: flex; justify-content: space-between; margin-bottom: 8rpx; }
.weak-name { font-size: 28rpx; color: #333; }
.weak-detail { font-size: 24rpx; color: #C45656; }
.weak-bar { height: 16rpx; background: #F0E0D0; border-radius: 8rpx; overflow: hidden; }
.weak-bar-fill { height: 100%; background: #C45656; border-radius: 8rpx; }

.section { background: #FFFFFF; border-radius: 20rpx; padding: 24rpx; margin-bottom: 24rpx; }
.section-title { display: block; font-size: 30rpx; font-weight: 700; color: #333; margin-bottom: 20rpx; }
.topic-row { display: flex; align-items: center; gap: 16rpx; margin-bottom: 16rpx; }
.topic-info { width: 200rpx; flex-shrink: 0; }
.topic-name { display: block; font-size: 26rpx; color: #333; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.topic-detail { display: block; font-size: 22rpx; color: #8A8F99; }
.topic-bar { flex: 1; height: 18rpx; background: #F0F0F0; border-radius: 9rpx; overflow: hidden; }
.topic-bar-fill { height: 100%; background: #0E7C7B; border-radius: 9rpx; }
.topic-pct { width: 90rpx; text-align: right; font-size: 26rpx; color: #333; font-weight: 700; }

.attempt-row { display: flex; justify-content: space-between; align-items: center; padding: 16rpx 0; border-bottom: 1rpx solid #F4F4F4; }
.attempt-info { display: flex; flex-direction: column; }
.attempt-mode { font-size: 26rpx; color: #333; }
.attempt-time { font-size: 22rpx; color: #B0B6C0; }
.attempt-score { font-size: 28rpx; color: #C45656; font-weight: 700; }
.attempt-score.good { color: #0E7C7B; }

.empty { display: flex; flex-direction: column; align-items: center; padding: 100rpx 0; gap: 16rpx; }
.empty-icon { font-size: 72rpx; }
.empty-text { font-size: 26rpx; color: #B0B6C0; }
</style>