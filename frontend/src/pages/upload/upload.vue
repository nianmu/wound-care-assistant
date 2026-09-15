<template>
	<view class="upload-page">
		<!-- 管理员专属：非管理员显示提示并隐藏上传控件 -->
		<view class="card intro">
			<text class="card-title">📖 上传教材（.txt）</text>
			<text class="card-desc">服务器只收纯文本，PDF / EPUB 请先在电脑上用一键转换工具转成 txt（见 tools/README.md）。</text>
		</view>

		<view class="no-auth" v-if="!isAdmin">
			<text class="no-auth-text">🔒 上传教材属于高危操作，仅系统管理员（admin）可执行。</text>
		</view>

		<view class="card" v-if="isAdmin">
			<button class="pick-btn" @click="pickFile">选择文件</button>
			<view class="file-info" v-if="fileName">
				<text class="file-name">{{ fileName }}</text>
				<text class="file-size">{{ fileSize }}</text>
			</view>
			<button class="upload-btn" :disabled="!fileName || uploading" @click="doUpload">
				{{ uploading ? '正在上传并索引…' : '上传并建立索引' }}
			</button>
			<view class="result" v-if="result">
				<text class="result-ok">✅ 上传成功：{{ result.chunk_count }} 个切片已入库</text>
				<text class="result-sub">知识库当前共 {{ result.total_in_kb }} 个切片</text>
			</view>
		</view>

		<view class="tip">
			<text class="tip-text">💡 已上传的教材会先覆盖同名文档，再增量加入知识库。</text>
		</view>
	</view>
</template>

<script>
import { uploadFile, getUser } from '../../utils/api.js'

export default {
  data() {
    return {
      filePath: '',
      fileName: '',
      fileSize: '',
      uploading: false,
      result: null,
      isAdmin: false,
    }
  },
  onShow() {
    const user = getUser()
    this.isAdmin = !!(user && user.is_admin)
  },
  methods: {
    pickFile() {
      uni.chooseFile({
        count: 1,
        extension: ['txt', 'md'],
        success: (res) => {
          const f = res.tempFiles && res.tempFiles[0]
          if (f) {
            this.filePath = f.path
            this.fileName = f.name || this.filePath.split('/').pop()
            this.fileSize = f.size ? (f.size / 1024).toFixed(1) + ' KB' : ''
            this.result = null
          }
        },
        fail: () => {},
      })
    },
    doUpload() {
      if (!this.filePath || this.uploading) return
      this.uploading = true
      this.result = null
      uploadFile(this.filePath, this.fileName)
        .then(({ statusCode, data }) => {
          if (statusCode === 200) {
            this.result = data
            uni.showToast({ title: '上传成功', icon: 'success' })
          } else {
            uni.showToast({ title: data.detail || '上传失败', icon: 'none' })
          }
        })
        .catch((err) => {
          uni.showToast({ title: err.message || '上传失败', icon: 'none' })
        })
        .finally(() => { this.uploading = false })
    },
  },
}
</script>

<style scoped>
/* 高度 = 视口 - 顶部导航栏 - 底部 tabBar；border-box 防 padding 撑破 */
.upload-page { box-sizing: border-box; padding: 24rpx; background: #F5F6FA; min-height: calc(100vh - var(--window-top) - var(--window-bottom)); }
.card { background: #FFFFFF; border-radius: 20rpx; padding: 28rpx; margin-bottom: 24rpx; box-shadow: 0 2rpx 8rpx rgba(0,0,0,0.04); }
.intro {}
.card-title { display: block; font-size: 32rpx; font-weight: 700; color: #333; margin-bottom: 12rpx; }
.card-desc { display: block; font-size: 26rpx; color: #8A8F99; line-height: 1.7; }
.no-auth { background: #FFF7E6; border: 2rpx solid #FFE0A3; border-radius: 16rpx; padding: 24rpx; margin-bottom: 24rpx; }
.no-auth-text { font-size: 26rpx; color: #B7791F; line-height: 1.6; }
.pick-btn { background: #EAF4F4; color: #0E7C7B; font-size: 28rpx; border-radius: 14rpx; }
.file-info { display: flex; justify-content: space-between; align-items: center; margin: 20rpx 0; }
.file-name { font-size: 28rpx; color: #333; max-width: 70%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.file-size { font-size: 24rpx; color: #8A8F99; }
.upload-btn { background: #0E7C7B; color: #FFFFFF; font-size: 28rpx; border-radius: 14rpx; }
.upload-btn[disabled] { opacity: 0.5; }
.result { margin-top: 24rpx; padding: 20rpx; background: #F0F8F7; border-radius: 12rpx; }
.result-ok { display: block; font-size: 28rpx; color: #0E7C7B; font-weight: 600; }
.result-sub { display: block; font-size: 24rpx; color: #8A8F99; margin-top: 8rpx; }
.tip { padding: 8rpx 8rpx; }
.tip-text { font-size: 24rpx; color: #B0B6C0; }
</style>