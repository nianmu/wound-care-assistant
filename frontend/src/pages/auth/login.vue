<template>
	<view class="auth-page">
		<view class="auth-card">
			<view class="app-badge">🩺</view>
			<text class="app-title">造口护理学习助手</text>

			<!-- 登录 / 注册 切换 -->
			<view class="tabs">
				<view class="tab" :class="{ active: mode === 'login' }" @click="mode = 'login'">登录</view>
				<view class="tab" :class="{ active: mode === 'register' }" @click="mode = 'register'">注册</view>
			</view>

			<view class="form">
				<view class="field">
					<text class="label">用户名</text>
					<input class="input" v-model="username" placeholder="3~32 位小写字母/数字/下划线" />
				</view>
				<view class="field" v-if="mode === 'register'">
					<text class="label">昵称（选填）</text>
					<input class="input" v-model="displayName" placeholder="如：妈妈 / 小明" maxlength="20" />
				</view>
				<view class="field" v-if="mode === 'register'">
					<text class="label">邀请码</text>
					<input class="input" v-model="inviteCode" placeholder="向家人索取注册邀请码" maxlength="64" />
				</view>
				<view class="field">
					<text class="label">密码</text>
					<input class="input" v-model="password" password placeholder="至少 8 位，含字母和数字" />
				</view>
				<view class="hint" v-if="mode === 'register'">首个注册的账号会自动接管现有的历史成绩与错题。</view>
			</view>

			<button class="submit-btn" :disabled="submitting" @click="submit">{{ mode === 'login' ? '登 录' : '注册并登录' }}</button>
		</view>
	</view>
</template>

<script>
import { login, register, setAuth } from '../../utils/api.js'

export default {
  data() {
    return {
      mode: 'login',
      username: '',
      password: '',
      displayName: '',
      inviteCode: '',
      submitting: false,
    }
  },
  methods: {
    submit() {
      const username = (this.username || '').trim()
      const password = this.password || ''
      if (!username || !password) {
        uni.showToast({ title: '请输入用户名和密码', icon: 'none' })
        return
      }
      if (this.mode === 'register' && password.length < 8) {
        uni.showToast({ title: '密码至少 8 位', icon: 'none' })
        return
      }
      if (this.mode === 'register' && !(this.inviteCode || '').trim()) {
        uni.showToast({ title: '请输入注册邀请码', icon: 'none' })
        return
      }
      this.submitting = true
      const p = this.mode === 'register'
        ? register(username, password, this.displayName, this.inviteCode)
        : login(username, password)
      p.then((data) => {
        setAuth(data.token, data.user)
        uni.showToast({ title: this.mode === 'register' ? '注册成功，已登录' : '登录成功', icon: 'success' })
        setTimeout(() => this.back(), 600)
      }).catch((err) => {
        const detail = (err && err.data && err.data.detail) || '操作失败'
        uni.showToast({ title: detail, icon: 'none' })
      }).finally(() => { this.submitting = false })
    },
    back() {
      const pages = getCurrentPages()
      if (pages.length > 1) {
        uni.navigateBack()
      } else {
        uni.switchTab({ url: '/pages/exam/exam' })
      }
    },
  },
}
</script>

<style scoped>
.auth-page {
	min-height: 100vh;
	background: #F5F6FA;
	display: flex;
	justify-content: center;
	padding: 80rpx 40rpx;
	box-sizing: border-box;
}
.auth-card {
	background: #FFFFFF;
	border-radius: 24rpx;
	padding: 48rpx 40rpx;
	width: 100%;
	max-width: 640rpx;
	align-self: flex-start;
}
.app-badge { font-size: 64rpx; text-align: center; display: block; }
.app-title { display: block; text-align: center; font-size: 32rpx; font-weight: 700; color: #0E7C7B; margin: 12rpx 0 32rpx; }
.tabs { display: flex; border-bottom: 2rpx solid #EEF0F3; margin-bottom: 28rpx; }
.tab { flex: 1; text-align: center; font-size: 30rpx; color: #8A8F99; padding-bottom: 16rpx; }
.tab.active { color: #0E7C7B; font-weight: 700; border-bottom: 4rpx solid #0E7C7B; }
.field { margin-bottom: 20rpx; }
.label { display: block; font-size: 26rpx; color: #8A8F99; margin-bottom: 8rpx; }
.input { height: 84rpx; background: #F5F6FA; border-radius: 14rpx; padding: 0 24rpx; font-size: 28rpx; }
.hint { font-size: 24rpx; color: #B0B6C0; margin-bottom: 8rpx; }
.submit-btn { margin-top: 28rpx; background: #0E7C7B; color: #FFF; font-size: 30rpx; border-radius: 40rpx; height: 88rpx; line-height: 88rpx; }
.submit-btn[disabled] { opacity: 0.6; }
</style>