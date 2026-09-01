<template>
	<view class="wrong-page">
		<view class="summary" v-if="loaded">
			<text class="summary-num">{{ questions.length }}</text>
			<text class="summary-label">道错题待巩固</text>
		</view>

		<view class="wrong-list" v-if="questions.length">
			<view class="wrong-item" v-for="(q, i) in questions" :key="q.id">
				<view class="wrong-head">
					<text class="wrong-no">#{{ i + 1 }}</text>
					<text class="wrong-tag">{{ typeLabel(q.qtype) }}</text>
					<text class="wrong-count" v-if="q.wrong_count > 1">错 {{ q.wrong_count }} 次</text>
				</view>
				<text class="wrong-q">{{ q.question }}</text>
				<view class="wrong-opts">
					<view v-for="(opt, oi) in (q.options || [])" :key="oi" class="wrong-opt" :class="{ std: (q.answer || []).includes(keyOf(oi)) }">
						<text class="wrong-opt-key">{{ keyOf(oi) }}</text>
						<text class="wrong-opt-text">{{ opt }}</text>
					</view>
				</view>
				<view class="wrong-ans">
					<text class="wrong-ans-label">✅ 正确答案：{{ q.answer.join('、') }}</text>
				</view>
				<view class="wrong-explain" v-if="q.explanation">
					<text class="wrong-explain-label">📖 解析</text>
					<text class="wrong-explain-text">{{ q.explanation }}</text>
					<text class="wrong-explain-src" v-if="q.source">来源：{{ q.source }}{{ q.page ? ` 第${q.page}页` : '' }}</text>
				</view>
				<view class="wrong-actions">
					<button class="relearn-btn" @click="relearn(q)">已掌握，移出</button>
				</view>
			</view>
		</view>

		<view class="empty" v-if="loaded && !questions.length">
			<text class="empty-icon">🎉</text>
			<text class="empty-text">错题本为空，继续保持！</text>
		</view>
		<view class="empty" v-if="!loaded">
			<text class="empty-text">加载中…</text>
		</view>
	</view>
</template>

<script>
import { getWrongBook } from '../../utils/api.js'

const KEY = ['A', 'B', 'C', 'D']

export default {
  data() {
    return { questions: [], loaded: false }
  },
  onShow() { this.refresh() },
  methods: {
    keyOf(i) { return ['A', 'B', 'C', 'D'][i] || '' },
    refresh() {
      getWrongBook().then((d) => {
        this.questions = d.questions || []
      }).catch(() => {
        uni.showToast({ title: '加载失败', icon: 'none' })
      }).finally(() => { this.loaded = true })
    },
    typeLabel(t) { return { single: '单选', multi: '多选', case: '案例' }[t] || '题' },
    relearn(q) {
      // 移出错题本：直接调错题标记接口（复用 submit 的答对路径：用正确答案重答一次）
      uni.showLoading({ title: '处理中…' })
      import('../../utils/api.js').then(({ submitAnswers }) => {
        submitAnswers([q], [q.answer], 'practice', '')
          .then(() => {
            uni.showToast({ title: '已移出', icon: 'success' })
            this.refresh()
          })
          .catch(() => uni.showToast({ title: '操作失败', icon: 'none' }))
          .finally(() => uni.hideLoading())
      })
    },
  },
}
</script>

<style scoped>
.wrong-page { box-sizing: border-box; padding: 24rpx; background: #F5F6FA; min-height: calc(100vh - var(--window-top) - var(--window-bottom)); }
.summary { display: flex; align-items: baseline; gap: 12rpx; padding: 10rpx 8rpx 20rpx; }
.summary-num { font-size: 56rpx; font-weight: 800; color: #C45656; }
.summary-label { font-size: 26rpx; color: #8A8F99; }
.wrong-list { display: flex; flex-direction: column; gap: 20rpx; }
.wrong-item { background: #FFFFFF; border-radius: 20rpx; padding: 24rpx; }
.wrong-head { display: flex; align-items: center; gap: 12rpx; margin-bottom: 12rpx; }
.wrong-no { font-size: 24rpx; color: #FFF; background: #C45656; border-radius: 8rpx; padding: 4rpx 12rpx; }
.wrong-tag { font-size: 22rpx; color: #0E7C7B; background: #EAF4F4; border-radius: 8rpx; padding: 4rpx 14rpx; }
.wrong-count { font-size: 22rpx; color: #C45656; }
.wrong-q { display: block; font-size: 28rpx; color: #333; line-height: 1.7; margin-bottom: 16rpx; }
.wrong-opts { display: flex; flex-direction: column; gap: 10rpx; margin-bottom: 14rpx; }
.wrong-opt { display: flex; gap: 12rpx; padding: 12rpx 16rpx; border-radius: 10rpx; border: 2rpx solid #EEE; font-size: 26rpx; color: #555; }
.wrong-opt.std { border-color: #0E7C7B; background: #F0F8F7; }
.wrong-opt-key { flex-shrink: 0; font-weight: 700; color: #333; }
.wrong-ans-label { font-size: 26rpx; color: #0E7C7B; font-weight: 600; }
.wrong-explain { background: #FAFAFA; border-radius: 12rpx; padding: 16rpx; margin-top: 12rpx; }
.wrong-explain-label { display: block; font-size: 24rpx; color: #0E7C7B; font-weight: 700; margin-bottom: 8rpx; }
.wrong-explain-text { display: block; font-size: 26rpx; color: #444; line-height: 1.7; }
.wrong-explain-src { display: block; font-size: 22rpx; color: #B0B6C0; margin-top: 8rpx; }
.wrong-actions { margin-top: 16rpx; display: flex; justify-content: flex-end; }
.relearn-btn { background: #F0F8F7; color: #0E7C7B; font-size: 24rpx; border-radius: 10rpx; padding: 0 24rpx; line-height: 56rpx; }
.empty { display: flex; flex-direction: column; align-items: center; padding: 120rpx 0; gap: 20rpx; }
.empty-icon { font-size: 72rpx; }
.empty-text { font-size: 26rpx; color: #B0B6C0; }
</style>