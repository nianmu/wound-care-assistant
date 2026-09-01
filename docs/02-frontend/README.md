# 前端模块 — 总览

> uni-app (Vue 3 + Vite) 位于 `frontend/`。一套代码可编译 H5 / 微信小程序 / App。当前以 **H5 端**为主验证。

## 页面地图（pages.json）

| 页面 | 路径 | tabBar | 说明 |
| :-- | :-- | :-- | :-- |
| 智能问答 | pages/chat/chat | ✅ | 自定义导航栏（设置⚙️入口）+ 流式对话 |
| 模拟测验 | pages/exam/exam | ✅ | 测验主页：出题设置 + 四大模式入口 |
| 文档管理 | pages/docs/docs | ✅ | 教材列表（点进详情） |
| 上传教材 | pages/upload/upload | — | 从问答页 ⚙️ 进入，上传 txt |
| 学习设置 | pages/settings/settings | — | 模型单选 + Top-K（localStorage） |
| 文档详情 | pages/doc-detail/doc-detail | — | 切片列表 + 顶部删除 |
| 答题 | pages/exam/quiz | — | 做题（单选/多选/案例 + 计时 + 答题卡） |
| 成绩单 | pages/exam/result | — | 得分 + 逐题解析回顾 |
| 错题本 | pages/exam/wrong | — | 错题 + 已掌握移出 |
| 学习报告 | pages/exam/stats | — | 正确率统计 + 薄弱主题 |

> tabBar 固定 3 项：问答 / 测验 / 文档。**新增 tabBar 页受数量限制**；非 tabBar 页用 `uni.navigateTo` 跳转。

## 运行

```bash
cd frontend
npm install            # 首次
npm run dev:h5         # 开发（热更新）→ http://localhost:5173
npm run build:h5       # 生产构建 → dist/build/h5/（Nginx 托管）
npm run build:mp-weixin  # 小程序（后续多端可用）
```

- 开发期 vite.config.js 代理 `/api` → `http://127.0.0.1:8000`
- 生产期 Nginx 托管静态 + 反代 /api（见 [04-deployment.md](../04-deployment.md)）

## 目录结构

```
frontend/
├── src/
│   ├── pages/          # 页面（见上表）
│   ├── utils/
│   │   ├── api.js      # 全部后端 API 封装
│   │   └── md.js       # 轻量 markdown→HTML（rich-text 渲染，防 XSS）
│   ├── pages.json      # 路由注册 + tabBar
│   ├── manifest.json   # uni-app 应用配置
│   ├── App.vue         # 全局
│   └── main.js         # 入口（createSSRApp）
├── vite.config.js      # Vite + uni 插件 + dev 代理
└── index.html
```

## 关键技术点

1. **自定义导航栏**（chat 页）：`pages.json` 设 `navigationStyle: "custom"`，页面内自绘（状态栏高度 `uni.getSystemInfoSync().statusBarHeight` + 标题 + ⚙️）。这是给左上角放设置按钮的方案（默认导航栏小程序端不能加按钮）。
2. **localStorage 跨页设置**：`wc_model_id` / `wc_top_k`（settings 页写入，quiz/chat 发送时读取；chat 页 onShow 刷新，保障从设置页返回即时生效）。
3. **跨页数据**：`getApp().globalData` 传递出题结果（examQuestions）与成绩（examResult，**读取即消费清空**防误显）。
4. **markdown 渲染**：LLM 输出 markdown → `md.js mdToHtml()`（先转义再解析，防 XSS）→ rich-text 展示。模板只引用数据属性（`m.html`），**不要**在模板里直接调导入函数（uni 编译器绑定 `_ctx.xxx` 有坑）。
5. **CSS 高度**：页面高度用 `calc(100vh - var(--window-top) - var(--window-bottom))` + `box-sizing: border-box`，扣除导航栏/tabBar，防无内容也出滚动条。消息区用 `flex:1; min-height:0` + 内部 scroll-view 做局部滚动。

## 修改指南

| 想改什么 | 位置 |
| :-- | :-- |
| 加页面 | pages/ 新目录 + pages.json 注册 → **重启 dev server** |
| 改 API 调用 | utils/api.js |
| 改 markdown 渲染规则 | utils/md.js |
| 改 tabBar | pages.json tabBar.list（数量固定） |
| 改模型选择存储键 | pages/settings/settings.vue（KEY_MODEL/KEY_TOPK）与 chat.vue 一致 |

> ⚠️ uni-app 编译器的坑：改 `pages.json` / 新增页面 / `.vue` 里加 methods 后，**有时 HMR 不完整**——遇到"方法不存在"或页面未更新，先重启 dev server（npm run dev:h5）。