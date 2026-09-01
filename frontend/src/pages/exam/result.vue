<template>
	<view class="result-page">
		<!-- 成绩概览 -->
		<view class="hero" :class="scoreClass">
			<text class="score">{{ result.score }}</text>
			<text class="score-unit">分</text>
			<text class="hero-sub">答对 {{ result.correct }}/{{ result.total }} 题</text>
			<view class="hero-rank">
				<text class="rank-text">{{ rankText }}</text>
			</view>
		</view>

		<!-- 逐题回顾 -->
		<view class="review">
			<view class="review-item" v-for="(d, i) in result.details" :key="i">
				<view class="review-head">
					<text class="review-no">第 {{ i + 1 }} 题</text>
					<text class="review-mark" :class="d.correct ? 'ok' : 'bad'">{{ d.correct ? '✓ 正确' : '✗ 错误' }}</text>
				</view>
				<text class="review-q">{{ d.question }}</text>
				<view class="review-opts">
					<view
						v-for="(opt, oi) in (d.options || [])" :key="oi"
						class="review-opt"
						:class="{
							std: (d.answer || []).includes(keyOf(oi)),
							userWrong: !d.correct && (d.user_answer || []).includes(keyOf(oi)) && !(d.answer || []).includes(keyOf(oi)),
						}"
					>
						<text class="review-opt-key">{{ keyOf(oi) }}</text>
						<text class="review-opt-text">{{ opt }}</text>
					</view>
				</view>
				<view class="review-ans">
					<text class="review-ans-label">✅ 正确答案：{{ (d.answer || []).join('、') }}</text>
					<text class="review-ans-label" v-if="!d.correct">✏️ 你的答案：{{ (d.user_answer || []).length ? (d.user_answer || []).join('、') : '未作答' }}</text>
				</view>
				<view class="review-explain" v-if="d.explanation">
					<text class="review-explain-label">📖 解析</text>
					<text class="review-explain-text">{{ d.explanation }}</text>
					<text class="review-explain-src" v-if="d.source">来源：{{ d.source }}{{ d.page ? ` 第${d.page}页` : '' }}</text>
				</view>
			</view>
		</view>

		<view class="bottom-bar">
			<button class="again-btn" @click="again">再练一组</button>
			<button class="home-btn" @click="goHome">返回主页</button>
		</view>
	</view>
</template>

<script>
const KEY = ['A', 'B', 'C', 'D']

export default {
  data() {
    return { result: null }
  },
  computed: {
    scoreClass() {
      const s = this.result ? this.result.score : 0
      if (s >= 90) return 'excellent'
      if (s >= 70) return 'good'
      return 'needs-work'
    },
    rankText() {
      const s = this.result ? this.result.score : 0
      if (s >= 90) return '优秀！冲刺满分 🏆'
      if (s >= 70) return '良好，继续巩固 💪'
      if (s >= 60) return '及格边缘，建议看解析复习 📖'
      return '基础薄弱，建议回到问答页深入学习 🔁'
    },
  },
  onLoad() {
    const r = getApp().globalData.examResult
    // 读取后即消费，防止下次误显示旧成绩
    getApp().globalData.examResult = null
    // 无成绩时渲染空明细（防 undefined 崩溃）
    this.result = r || { score: 0, correct: 0, total: 0, details: [] }
  },
  methods: {
    keyOf(i) { return ['A', 'B', 'C', 'D'][i] || '' },
    again() {
      uni.redirectTo({ url: '/pages/exam/exam' })
    },
    goHome() {
      uni.switchTab({ url: '/pages/exam/exam' })
    },
  },
}
</script>

<style scoped>
.result-page { box-sizing: border-box; padding: 24rpx; background: #F5F6FA; min-height: calc(100vh - var(--window-top) - var(--window-bottom)); }
.hero { display: flex; flex-direction: column; align-items: center; padding: 50rpx 24rpx; border-radius: 24rpx; margin-bottom: 24rpx; color: #FFF; }
.hero.excellent { background: linear-gradient(135deg, #0E7C7B, #14A99A); }
.hero.good { background: linear-gradient(135deg, #2D6CDF, #4D9FFF); }
.hero.needs-work { background: linear-gradient(135deg, #C45656, #E07B7B); }
.score { font-size: 110rpx; font-weight: 800; line-height: 1.1; }
.score-unit { font-size: 30rpx; margin-left: 8rpx; }
.hero-sub { font-size: 26rpx; opacity: 0.9; margin-top: 8rpx; }
.hero-rank { margin-top: 16rpx; background: rgba(255,255,255,0.2); border-radius: 100rpx; padding: 10rpx 30rpx; }
.rank-text { font-size: 26rpx; }

.review { display: flex; flex-direction: column; gap: 20rpx; }
.review-item { background: #FFFFFF; border-radius: 20rpx; padding: 24rpx; }
.review-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12rpx; }
.review-no { font-size: 26rpx; color: #8A8F99; }
.review-mark { font-size: 26rpx; font-weight: 700; }
.review-mark.ok { color: #0E7C7B; }
.review-mark.bad { color: #C45656; }
.review-q { display: block; font-size: 28rpx; color: #333; line-height: 1.7; margin-bottom: 16rpx; }
.review-opts { display: flex; flex-direction: column; gap: 10rpx; margin-bottom: 14rpx; }
.review-opt { display: flex; gap: 12rpx; padding: 12rpx 16rpx; border-radius: 10rpx; border: 2rpx solid #EEE; font-size: 26rpx; color: #555; line-height: 1.5; }
.review-opt.std { border-color: #0E7C7B; background: #F0F8F7; }
.review-opt.userWrong { border-color: #C45656; background: #FDECEC; }
.review-opt-key { flex-shrink: 0; font-weight: 700; color: #333; }
.review-ans { display: flex; flex-direction: column; gap: 6rpx; margin-bottom: 12rpx; }
.review-ans-label { font-size: 26rpx; color: #333; }
.review-explain { background: #FAFAFA; border-radius: 12rpx; padding: 16rpx; }
.review-explain-label { display: block; font-size: 24rpx; color: #0E7C7B; font-weight: 700; margin-bottom: 8rpx; }
.review-explain-text { display: block; font-size: 26rpx; color: #444; line-height: 1.7; }
.review-explain-src { display: block; font-size: 22rpx; color: #B0B6C0; margin-top: 8rpx; }

.bottom-bar { display: flex; gap: 16rpx; margin-top: 24rpx; padding-bottom: 30rpx; }
.again-btn { flex: 1; background: #0E7C7B; color: #FFF; font-size: 28rpx; border-radius: 14rpx; }
.home-btn { flex: 1; background: #F0F0F0; color: #333; font-size: 28rpx; border-radius: 14rpx; }
</style>