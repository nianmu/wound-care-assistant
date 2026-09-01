<template>
	<view class="settings-page">
		<!-- 对话模型 -->
		<view class="section">
			<text class="section-title">🤖 对话模型</text>
			<view class="radio-list">
				<view class="radio-item" v-for="m in models" :key="m.id" :class="{ active: modelId === m.id }" @click="selectModel(m.id)">
					<view class="radio-info">
						<text class="radio-name">{{ m.name }}</text>
						<text class="radio-model">{{ m.model }}</text>
					</view>
					<view class="radio-dot" :class="{ checked: modelId === m.id }"></view>
				</view>
			</view>
		</view>

		<!-- 检索参数 -->
		<view class="section">
			<text class="section-title">📚 检索数量 Top-K</text>
			<view class="topk-row">
				<view class="topk-opt" v-for="k in topKOptions" :key="k" :class="{ active: topK === k }" @click="selectTopK(k)">
					{{ k }}
				</view>
			</view>
			<text class="section-desc">数值越大，回答参考的教材片段越多，生成越慢</text>
		</view>

		<view class="save-bar">
			<button class="save-btn" @click="save">保存设置</button>
		</view>
	</view>
</template>

<script>
import { getModels } from '../../utils/api.js'

const KEY_MODEL = 'wc_model_id'
const KEY_TOPK = 'wc_top_k'

export default {
  data() {
    return {
      models: [],
      modelId: '',
      topKOptions: [3, 5, 7, 10],
      topK: 5,
      loaded: false,
    }
  },
  onLoad() {
    this.modelId = uni.getStorageSync(KEY_MODEL) || ''
    this.topK = uni.getStorageSync(KEY_TOPK) || 5
    this.loadModels()
  },
  methods: {
    loadModels() {
      getModels().then((data) => {
        const list = data.chat_models || []
        this.models = list
        if (!this.modelId || !list.some(m => m.id === this.modelId)) {
          this.modelId = data.default || (list[0] && list[0].id) || ''
        }
      }).catch(() => {
        uni.showToast({ title: '无法连接后端服务', icon: 'none' })
      }).finally(() => { this.loaded = true })
    },
    selectModel(id) { this.modelId = id },
    selectTopK(k) { this.topK = k },
    save() {
      if (this.modelId) {
        uni.setStorageSync(KEY_MODEL, this.modelId)
      }
      uni.setStorageSync(KEY_TOPK, this.topK)
      uni.showToast({ title: '已保存', icon: 'success' })
      setTimeout(() => uni.navigateBack(), 600)
    },
  },
}
</script>

<style scoped>
.settings-page { box-sizing: border-box; padding: 24rpx; background: #F5F6FA; min-height: calc(100vh - var(--window-top) - var(--window-bottom)); }
.section { background: #FFFFFF; border-radius: 20rpx; padding: 24rpx; margin-bottom: 24rpx; }
.section-title { display: block; font-size: 30rpx; font-weight: 700; color: #333; margin-bottom: 20rpx; }
.section-desc { display: block; font-size: 24rpx; color: #8A8F99; margin-top: 16rpx; }
.radio-list { display: flex; flex-direction: column; }
.radio-item { display: flex; align-items: center; justify-content: space-between; padding: 20rpx 8rpx; border-bottom: 1rpx solid #F4F4F4; }
.radio-item.active { background: #F0F8F7; border-radius: 12rpx; padding-left: 16rpx; padding-right: 16rpx; }
.radio-info { display: flex; flex-direction: column; min-width: 0; }
.radio-name { font-size: 28rpx; color: #333; }
.radio-model { font-size: 22rpx; color: #8A8F99; margin-top: 4rpx; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.radio-dot { width: 36rpx; height: 36rpx; border-radius: 50%; border: 3rpx solid #C8CDD4; box-sizing: border-box; }
.radio-dot.checked { border-color: #0E7C7B; border-width: 10rpx; }
.topk-row { display: flex; gap: 16rpx; }
.topk-opt { flex: 1; text-align: center; font-size: 28rpx; color: #333; background: #F5F6FA; border-radius: 12rpx; padding: 16rpx 0; }
.topk-opt.active { background: #0E7C7B; color: #FFFFFF; font-weight: 700; }
.save-bar { padding: 8rpx 0 30rpx; }
.save-btn { background: #0E7C7B; color: #FFFFFF; font-size: 30rpx; border-radius: 16rpx; }
</style>