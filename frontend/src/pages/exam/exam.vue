<template>
	<view class="exam-page">
		<!-- 当前用户条（账户体系）：未登录可点去登录，登录后显示昵称并可退出 -->
		<view class="user-bar" @click="goUser">
			<text class="user-info">{{ user ? ('👤 ' + user.display_name) : '未登录 · 点此登录/注册' }}</text>
			<text v-if="user" class="logout" @click.stop="logout">退出</text>
			<text v-else class="logout">›</text>
		</view>

		<!-- 题目配置 -->
		<view class="card">
			<text class="card-title">📝 出题设置</text>
			<view class="config-row">
				<text class="config-label">题型</text>
				<view class="seg">
					<view v-for="t in qtypeOptions" :key="t.id" class="seg-item" :class="{ active: qtype === t.id }" @click="qtype = t.id">
						{{ t.label }}
					</view>
				</view>
			</view>
			<view class="config-row">
				<text class="config-label">题量</text>
				<view class="seg">
					<view v-for="n in countOptions" :key="n" class="seg-item" :class="{ active: count === n }" @click="count = n">{{ n }}</view>
				</view>
			</view>
		</view>

		<!-- 模式入口 -->
		<view class="mode-list">
			<view class="mode-item" @click="startPractice(false)">
				<view class="mode-icon">🎯</view>
				<view class="mode-info">
					<text class="mode-name">练一练</text>
					<text class="mode-desc">自由刷题，提交后即时看对错和解析</text>
				</view>
				<text class="mode-arrow">›</text>
			</view>
			<view class="mode-item" @click="startPractice(true)">
				<view class="mode-icon">📄</view>
				<view class="mode-info">
					<text class="mode-name">模拟考试</text>
					<text class="mode-desc">计时答题，交卷统一判分出成绩</text>
				</view>
				<text class="mode-arrow">›</text>
			</view>
			<view class="mode-item" @click="goWrong">
				<view class="mode-icon">📕</view>
				<view class="mode-info">
					<text class="mode-name">错题本</text>
					<text class="mode-desc">回顾做错的题，反复重练</text>
				</view>
				<text class="mode-badge" v-if="wrongCount">{{ wrongCount }}</text>
				<text class="mode-arrow">›</text>
			</view>
			<view class="mode-item" @click="goStats">
				<view class="mode-icon">📊</view>
				<view class="mode-info">
					<text class="mode-name">学习报告</text>
					<text class="mode-desc">各板块正确率与薄弱点</text>
				</view>
				<text class="mode-arrow">›</text>
			</view>
		</view>
	</view>
</template>

<script>
import { generateQuestions, getWrongBook, getToken, getUser, clearAuth } from '../../utils/api.js'

export default {
  data() {
    return {
      qtypeOptions: [
        { id: 'mix', label: '混合' },
        { id: 'single', label: '单选' },
        { id: 'multi', label: '多选' },
        { id: 'case', label: '案例' },
      ],
      qtype: 'mix',
      countOptions: [3, 5, 10, 15],
      count: 5,
      wrongCount: 0,
      user: null,
    }
  },
  onShow() {
    this.user = getToken() ? getUser() : null
    if (this.user) this.loadWrongCount()
  },
  methods: {
    loadWrongCount() {
      getWrongBook().then((d) => { this.wrongCount = d.total || 0 }).catch(() => {})
    },
    goUser() {
      if (!this.user) uni.navigateTo({ url: '/pages/auth/login' })
    },
    logout() {
      uni.showModal({
        title: '退出登录',
        content: '退出后此设备将回到未登录状态。',
        confirmText: '退出',
        confirmColor: '#C45656',
        success: (r) => {
          if (r.confirm) {
            clearAuth()
            this.user = null
            this.wrongCount = 0
            uni.navigateTo({ url: '/pages/auth/login' })
          }
        },
      })
    },
    startPractice(isExam) {
      uni.showLoading({ title: 'AI 出题中…' })
      const qtype = this.qtype === 'mix' ? null : this.qtype
      generateQuestions({ count: this.count, qtype })
        .then((data) => {
          if (!data.questions || !data.questions.length) {
            uni.showToast({ title: '出题失败，请重试', icon: 'none' })
            return
          }
          const mode = isExam ? 'exam' : 'practice'
          const total = data.questions.length
          const timeout = isExam ? Math.max(60, total * 90) : 0  // 每题 90 秒
          uni.navigateTo({
            url: `/pages/exam/quiz?mode=${mode}&timeout=${timeout}`,
            success: () => {
              // 通过事件总线传递题目（简单方案：存全局）
              getApp().globalData.examQuestions = data.questions
            },
          })
        })
        .catch((err) => {
          uni.showToast({ title: (err && err.data && err.data.detail) || '出题失败', icon: 'none' })
        })
        .finally(() => uni.hideLoading())
    },
    goWrong() {
      uni.navigateTo({ url: '/pages/exam/wrong' })
    },
    goStats() {
      uni.navigateTo({ url: '/pages/exam/stats' })
    },
  },
}
</script>

<style scoped>
.exam-page { box-sizing: border-box; padding: 24rpx; background: #F5F6FA; min-height: calc(100vh - var(--window-top) - var(--window-bottom)); }
.user-bar { display: flex; align-items: center; justify-content: space-between; background: #FFFFFF; border-radius: 16rpx; padding: 16rpx 24rpx; margin-bottom: 20rpx; }
.user-info { font-size: 26rpx; color: #333; }
.logout { font-size: 26rpx; color: #C45656; font-weight: 600; }
.card { background: #FFFFFF; border-radius: 20rpx; padding: 24rpx; margin-bottom: 24rpx; }
.card-title { display: block; font-size: 30rpx; font-weight: 700; color: #333; margin-bottom: 20rpx; }
.config-row { display: flex; align-items: center; margin-bottom: 16rpx; }
.config-label { font-size: 26rpx; color: #8A8F99; width: 90rpx; }
.seg { display: flex; gap: 12rpx; flex-wrap: wrap; }
.seg-item { font-size: 26rpx; color: #333; background: #F5F6FA; border-radius: 10rpx; padding: 10rpx 24rpx; }
.seg-item.active { background: #0E7C7B; color: #FFFFFF; font-weight: 700; }
.mode-list { background: #FFFFFF; border-radius: 20rpx; overflow: hidden; }
.mode-item { display: flex; align-items: center; padding: 28rpx; border-bottom: 1rpx solid #F0F0F0; }
.mode-icon { font-size: 44rpx; margin-right: 20rpx; }
.mode-info { flex: 1; display: flex; flex-direction: column; min-width: 0; }
.mode-name { font-size: 30rpx; color: #333; font-weight: 600; }
.mode-desc { font-size: 24rpx; color: #8A8F99; margin-top: 4rpx; }
.mode-arrow { font-size: 40rpx; color: #B0B6C0; }
.mode-badge { background: #C45656; color: #FFF; border-radius: 100rpx; font-size: 22rpx; padding: 4rpx 16rpx; margin-right: 8rpx; min-width: 36rpx; text-align: center; }
</style>