<template>
	<view class="quiz-page">
		<!-- 顶栏：进度 + 计时 + 答题卡 -->
		<view class="quiz-top">
			<text class="progress">{{ idx + 1 }}/{{ questions.length }}</text>
			<text class="timer" v-if="mode === 'exam'">⏱ {{ mm }}:{{ ss }}</text>
			<text class="card-btn" @click="showCard = !showCard">答题卡</text>
		</view>

		<!-- 题目卡 -->
		<view class="question-card">
			<view class="q-tags">
				<text class="q-tag">{{ typeLabel }}</text>
				<text class="q-tag topic" v-if="current.topic">{{ current.topic }}</text>
				<text class="q-source" v-if="current.source">📖 {{ shortSource }}<template v-if="current.page"> 第{{ current.page }}页</template></text>
			</view>
			<text class="q-text">{{ current.question }}</text>

			<view class="options">
				<view
					v-for="(opt, oi) in current.options"
					:key="oi"
					class="opt"
					:class="{ picked: isPicked(oi) }"
					@click="toggle(oi)"
				>
					<text class="opt-key">{{ keyOf(oi) }}</text>
					<text class="opt-text">{{ opt }}</text>
				</view>
			</view>
			<text class="q-hint" v-if="current.qtype === 'multi'">📌 多选题：选择 2~3 个正确选项</text>
		</view>

		<!-- 答题卡抽屉 -->
		<view class="card-drawer" v-if="showCard">
			<view class="card-grid">
				<view v-for="(q, qi) in questions" :key="qi" class="card-cell" :class="{ answered: isAnswered(qi), current: qi === idx }" @click="goTo(qi)">
					{{ qi + 1 }}
				</view>
			</view>
		</view>

		<!-- 底部导航 -->
		<view class="quiz-bottom">
			<button class="nav-btn" v-if="idx > 0" @click="prev">上一题</button>
			<button class="nav-btn next" v-if="idx < questions.length - 1" @click="next">下一题</button>
			<button class="nav-btn submit" v-else @click="submit">交卷</button>
		</view>
	</view>
</template>

<script>
import { submitAnswers } from '../../utils/api.js'

const KEY = ['A', 'B', 'C', 'D']

export default {
  data() {
    return {
      questions: [],
      mode: 'practice',
      idx: 0,
      answers: [],        // [{0:true,1:false,...}] 或 {idx: [oi...]}
      showCard: false,
      timeLeft: 0,
      timer: null,
      mm: '00',
      ss: '00',
    }
  },
  computed: {
    current() { return this.questions[this.idx] || {} },
    typeLabel() {
      const m = { single: '单选', multi: '多选', case: '案例分析' }
      return m[this.current.qtype] || '单选'
    },
    shortSource() {
      const s = this.current.source || ''
      return s.length > 16 ? s.slice(0, 16) + '…' : s
    },
  },
  onLoad(options) {
    this.mode = options.mode || 'practice'
    this.questions = (getApp().globalData.examQuestions || []).map(q => ({ ...q, _ans: {} }))
    this.answers = this.questions.map(() => ({}))
    if (!this.questions.length) {
      uni.showToast({ title: '没有题目，请返回重试', icon: 'none' })
      setTimeout(() => uni.navigateBack(), 800)
      return
    }
    const timeout = parseInt(options.timeout || '0', 10)
    if (this.mode === 'exam' && timeout > 0) {
      this.timeLeft = timeout
      this.timer = setInterval(() => this.tick(), 1000)
      this.updateTimer()
    }
  },
  onUnload() {
    if (this.timer) clearInterval(this.timer)
  },
  methods: {
    keyOf(i) { return KEY[i] || '' },
    isPicked(oi) { return !!(this.answers[this.idx] && this.answers[this.idx][oi]) },
    isAnswered(qi) { return !!this.answers[qi] && Object.keys(this.answers[qi]).length > 0 },
    toggle(oi) {
      const a = this.answers[this.idx]
      if (this.current.qtype === 'multi') {
        a[oi] = !a[oi]
      } else {
        Object.keys(a).forEach(k => delete a[k])
        a[oi] = true
      }
    },
    goTo(i) { this.idx = i; this.showCard = false },
    prev() { if (this.idx > 0) this.idx-- },
    next() { if (this.idx < this.questions.length - 1) this.idx++ },
    tick() {
      if (this.timeLeft <= 0) {
        clearInterval(this.timer)
        this.submit(true)
        return
      }
      this.timeLeft--
      this.updateTimer()
    },
    updateTimer() {
      this.mm = String(Math.floor(this.timeLeft / 60)).padStart(2, '0')
      this.ss = String(this.timeLeft % 60).padStart(2, '0')
    },
    submit(isTimeout) {
      // 组装答案
      const finalAnswers = this.questions.map((q, i) => {
        const picked = Object.keys(this.answers[i] || {}).filter(k => this.answers[i][k]).map(Number)
        return picked.map(oi => KEY[oi])
      })
      const unanswered = finalAnswers.filter(a => !a.length).length
      if (!isTimeout && unanswered > 0) {
        uni.showModal({
          title: '还有未答题目',
          content: `还有 ${unanswered} 题未作答，确定交卷吗？`,
          confirmColor: '#0E7C7B',
          success: (res) => { if (res.confirm) this.doSubmit(finalAnswers) },
        })
        return
      }
      this.doSubmit(finalAnswers)
    },
    doSubmit(finalAnswers) {
      uni.showLoading({ title: '判分中…' })
      submitAnswers(this.questions, finalAnswers, this.mode, '')
        .then((res) => {
          getApp().globalData.examResult = res
          uni.navigateTo({ url: '/pages/exam/result' })
        })
        .catch((err) => {
          uni.showToast({ title: (err && err.data && err.data.detail) || '判分失败', icon: 'none' })
        })
        .finally(() => uni.hideLoading())
    },
  },
}
</script>

<style scoped>
.quiz-page { box-sizing: border-box; display: flex; flex-direction: column; height: calc(100vh - var(--window-top) - var(--window-bottom)); background: #F5F6FA; }
.quiz-top { display: flex; align-items: center; justify-content: space-between; padding: 20rpx 24rpx; background: #FFFFFF; border-bottom: 1rpx solid #EEE; }
.progress { font-size: 28rpx; color: #333; font-weight: 700; }
.timer { font-size: 28rpx; color: #C45656; font-weight: 700; }
.card-btn { font-size: 26rpx; color: #0E7C7B; }

.question-card { margin: 24rpx; background: #FFFFFF; border-radius: 20rpx; padding: 28rpx; box-shadow: 0 2rpx 8rpx rgba(0,0,0,0.04); }
.q-tags { display: flex; align-items: center; gap: 12rpx; flex-wrap: wrap; margin-bottom: 16rpx; }
.q-tag { font-size: 22rpx; color: #0E7C7B; background: #EAF4F4; border-radius: 8rpx; padding: 4rpx 14rpx; }
.q-tag.topic { color: #8A6D1D; background: #FBF3DD; }
.q-source { font-size: 22rpx; color: #B0B6C0; }
.q-text { display: block; font-size: 30rpx; color: #333; line-height: 1.7; margin-bottom: 24rpx; }
.options { display: flex; flex-direction: column; gap: 16rpx; }
.opt { display: flex; align-items: flex-start; gap: 16rpx; padding: 20rpx; border: 2rpx solid #E5E8EC; border-radius: 14rpx; }
.opt.picked { border-color: #0E7C7B; background: #F0F8F7; }
.opt-key { flex-shrink: 0; width: 48rpx; height: 48rpx; border-radius: 50%; background: #F0F0F0; color: #666; text-align: center; line-height: 48rpx; font-size: 26rpx; font-weight: 700; }
.opt.picked .opt-key { background: #0E7C7B; color: #FFF; }
.opt-text { font-size: 28rpx; color: #333; line-height: 1.6; }
.q-hint { display: block; font-size: 24rpx; color: #C45656; margin-top: 20rpx; }

.card-drawer { margin: 0 24rpx 16rpx; background: #FFFFFF; border-radius: 16rpx; padding: 20rpx; }
.card-grid { display: flex; flex-wrap: wrap; gap: 14rpx; }
.card-cell { width: 64rpx; height: 64rpx; border-radius: 10rpx; background: #F5F6FA; color: #666; text-align: center; line-height: 64rpx; font-size: 26rpx; }
.card-cell.answered { background: #0E7C7B; color: #FFF; }
.card-cell.current { border: 3rpx solid #C45656; }

.quiz-bottom { display: flex; gap: 16rpx; padding: 16rpx 24rpx; background: #FFFFFF; border-top: 1rpx solid #EEE; margin-top: auto; }
.nav-btn { flex: 1; font-size: 28rpx; border-radius: 14rpx; background: #F0F0F0; color: #333; line-height: 76rpx; height: 76rpx; }
.nav-btn.next, .nav-btn.submit { background: #0E7C7B; color: #FFF; }
</style>