# 前端页面详解

> 每个页面的职责、入口、关键交互。页面路径均相对 `frontend/src/pages/`。

## 1. chat/chat.vue — 智能问答（tabBar 首页）

- **自定义导航栏**：左侧标题"造口护理学习助手"，右侧 ⚙️（`openMenu`）
- **⚙️ 菜单**（uni.showActionSheet）：📤 上传文档 → upload；🤖 切换对话模型 → settings；🧹 清空对话
- **对话列表**：`scroll-view`（内部滚动，`flex:1;min-height:0`），`scroll-into-view` 自动滚底
  - user 消息：纯文本；assistant 消息：`rich-text :nodes="m.html"`（md 渲染）+ 底部 📚 来源标签（source + pages）
- **流式发送**：`askQuestionStream`（fetch + ReadableStream）→ `onDelta` 增量拼 `content` 并重渲染 `html` → `onSources` 填来源 → `onDone`/`onError`
- **多轮追问**：发送前 `buildHistory()` 取最近 12 条 user/assistant 文本作为 `history` 随请求发送（不含当前句）——后端结合历史理解"那 III 期呢？"这类追问；每次回答的 📚 来源标签仍是**独立检索**结果
- **停止**：`AbortController`（streaming 时按钮变"停止"）
- 模型/TopK 每次发送前从 localStorage 读（`wc_model_id`/`wc_top_k`），onShow 刷新缓存

## 2. exam/exam.vue — 模拟测验主页

- **出题设置卡**：题型 4 选（混合/单选/多选/案例）+ 题量 4 档（3/5/10/15）
- **四大模式入口**：
  - 🎯 练一练 → `startPractice(false)`：AI 出题 → 跳 quiz，即时判分
  - 📄 模拟考试 → `startPractice(true)`：出题 → quiz（计时，每题 90s）
  - 📕 错题本 → wrong 页（角标显示待巩固数）
  - 📊 学习报告 → stats 页
- `startPractice(isExam)`：`generateQuestions` → `getApp().globalData.examQuestions` 存题 → `navigateTo quiz?mode=&timeout=`（模拟考 timeout = 题数×90）

## 3. exam/quiz.vue — 答题

- 状态：`questions`（来自 globalData）+ `answers[]`（每题 `{选项index: true}`）
- 交互：
  - 单选：点击选项替换；多选：点击切换（页面提示"选择2~3个"）
  - 顶栏：进度 `i/n`、计时器（exam 模式）、答题卡按钮
  - 答题卡抽屉：格子显示已答（绿色）与当前（红框），点击跳题
- **交卷**：`submit()` 组装 `[["B"],["B","C"],…]`（A/B/C/D 字母）→ 未答弹确认 → `submitAnswers` → `globalData.examResult` → 跳 result
- **超时**：计时归零自动交卷（isTimeout 跳过未答确认）
- 计时器 onUnload 清理（防泄漏）

## 4. exam/result.vue — 成绩单

- 顶部成绩卡：分数/答对数 + 等级文案（scoreClass: excellent≥90 / good≥70 / needs-work）
- 逐题回顾：题干 + 选项（**绿色=正确答案，红色=你错选**）+ 你的答案/正确答案 + 解析 + 来源页码
- `onLoad` 读 `globalData.examResult` 后**置 null**（消费即清，防旧成绩残留）；无数据给空对象兜底（防崩溃）
- 底部：再练一组（redirectTo exam）/ 返回主页（switchTab exam）

## 5. exam/wrong.vue — 错题本

- `getWrongBook()` 拉错题（含 wrong_count）
- 每题：题型标签 / 错次数 / 题干 / 选项（高亮正确答案）/ 解析 / 来源 / **"已掌握，移出"**按钮
- 移出实现：用正确答案重答一次（`submitAnswers([题],[answer])` → 触发 grader 的 mark_resolved）

## 6. exam/stats.vue — 学习报告

- 总体正确率大卡（overall_accuracy + total_answered）
- ⚠️ 薄弱主题卡：`stats.weak_topics`（条目 + 进度条）
- 各主题正确率条形图（by_topic）
- 最近做题记录（attempts 前 8，mode 标签 + 时间 + 分数）

## 7. docs/docs.vue — 文档管理（tabBar）

- 汇总：总切片数 + 教材数
- 教材列表：📘 名 + `›`，点击 → `navigateTo doc-detail?source=encodeURIComponent(name)`
- 删除入口已移到详情页（本页不再有删除按钮）

## 8. doc-detail/doc-detail.vue — 文档详情

- 顶部：📘 文档名 + 切片数 + **删除文档**按钮（确认弹窗 → DELETE → navigateBack）
- 切片列表：`scroll-view` 内部滚动；每条 #序号 + 页码标签 + 内容（默认折叠 max-height）+ "展开全文 ▼/收起 ▲"
- `onLoad` 里 `setNavigationBarTitle` 截断长书名

## 9. upload/upload.vue — 上传教材

- 说明卡（服务器只收 txt/md，PDF/EPUB 先转换）
- 选择文件（`uni.chooseFile`，extension: txt/md）→ 上传 → 显示切片数 + 知识库总量
- 提示：已上传会覆盖同名再增量加入

## 10. settings/settings.vue — 学习设置

- **对话模型**：从 `/api/models` 拉 chat_models，单选（radio 样式），显示 name + model
- **Top-K**：4 档单选（3/5/7/10）
- 保存：写入 localStorage（`wc_model_id`/`wc_top_k`）→ toast → navigateBack

## 跨页数据约定

| 键 | 写入方 | 读取方 | 生命周期 |
| :-- | :-- | :-- | :-- |
| `wc_model_id` / `wc_top_k` | settings | chat 发送时 | 持久（localStorage） |
| `globalData.examQuestions` | exam | quiz | 单次会话 |
| `globalData.examResult` | quiz(doSubmit) | result（读后置 null） | 单次会话 |