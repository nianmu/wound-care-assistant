# 模拟测试出题模块 — 设计文档

> 日期：2026-08-31
> 状态：**已实施完成（T1-T6 全部落地并实测通过）**
> 关联：造口伤口失禁护理 AI 学习助手（RAG 问答应用）

## 一、目标

为备考国际造口治疗师（WCET 认证，笔试部分）的家人提供**基于教材的 AI 自动出题**：
- 题目必须出自教材知识库（复用现有 RAG 检索链路）
- 支持单选 / 多选 / 临床情景案例题
- 核心闭环：出题 → 答题 → 判分 → 错题收集 → 薄弱点分析

## 二、考试背景（调研结论）

来源：[中山大学造口治疗师学校](http://www.sysucc.org.cn/node/8883)、[WOCNCB 考试](https://www.wocncb.org/certification/wound-ostomy-continence/exam)

- 专业课程四大板块：**造口护理、伤口护理、失禁护理、专业发展**
- 教学强调案例分析法、情景模拟
- 证书 = 笔试（理论）+ 实操；本模块只覆盖**笔试刷题**

## 三、功能模块

```
tabBar 新增【测验】页
├─ 🎯 练一练：自由刷题（题型可按单选/多选/案例切换，即时判分）
├─ 📄 模拟考试：固定题量 + 计时 + 答题卡 + 交卷统一判分 + 成绩单
├─ 📚 章节练习：选教材 → 选主题标签 → 只出该主题的题
├─ 📕 错题本：错题自动收集（题目快照 + 解析 + 来源页码），支持重练
└─ 📊 学习报告：各板块正确率统计 → 薄弱主题 → 复习建议
```

### 题型配比（模拟考试默认）
单选：多选：案例 = 6 : 2 : 2（可配置）

### 判分策略
- 练一练 / 章节练习：**前端即时判分**（秒出对错 + 解析）
- 模拟考试：**交卷统一判分**（答题卡回顾）

## 四、AI 出题引擎（核心）

```
选范围(整库/教材/主题/题型/数量)
  → Chroma 采样种子段落(按主题过滤+随机+去重)
  → LLM 逐段生成题目(题干+选项+答案+解析+来源页码+主题标签)
  → 置信度自检(低分丢弃)
  → 题目缓存表(同范围复用，不重复出)
```

### 防错题三道闸
1. **有据可依**：每题绑定教材原文片段+页码，Prompt 硬约束答案须出自片段
2. **置信度自检**：生成后让模型输出 self_confidence(0-1)，低于阈值丢弃
3. **缓存复用**：出过的题入缓存表，同范围练习不重复

## 五、技术方案

| 层 | 方案 |
| :-- | :-- |
| 后端 API | `POST /api/exam/generate`、`POST /api/exam/submit`、`GET /api/wrong-book`、`GET /api/stats` |
| 出题 | 复用 LLMClient（多模型）+ ExamPrompt 模板（既有 4 步临床结构约束） |
| 检索 | 复用 VectorStore.similarity_search，增加按主题过滤器 |
| 存储 | **Python 内置 sqlite3**（零依赖）：`exam_questions`（题目缓存）、`exam_attempts`（考试成绩）、`wrong_book`（错题）、`question_stats`（题目正确率） |
| 前端 | uni-app 新页面：exam/exam（主页）、exam/quiz（做题）、exam/result（成绩）、exam/wrong（错题本）、exam/stats（报告） |

### 数据库 schema（sqlite3）

```sql
CREATE TABLE exam_questions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  scope_key TEXT,            -- 出题范围指纹（教材+主题+题型），用于复用
  qtype TEXT,                -- single | multi | case
  topic TEXT,                -- 主题标签（压疮分期/造口用品/失禁分类…）
  source TEXT,               -- 教材名
  page INTEGER,              -- 来源页码
  question TEXT,             -- 题干（含案例情景）
  options TEXT,              -- JSON 数组 ["A.xx","B.xx"...]
  answer TEXT,               -- JSON 数组 ["A"] 或 ["A","C"]
  explanation TEXT,          -- 解析
  confidence REAL,           -- 自检置信度
  used_count INTEGER DEFAULT 0,
  created_at TEXT
);

CREATE TABLE exam_attempts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  mode TEXT,                 -- practice | exam | chapter
  topic TEXT,
  total INTEGER, correct INTEGER,
  score REAL,                -- 0-100
  detail TEXT,               -- JSON: [{qid, user_answer, correct}]
  created_at TEXT
);

CREATE TABLE wrong_book (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  question_id INTEGER,
  user_answer TEXT,
  wrong_count INTEGER DEFAULT 1,
  last_wrong_at TEXT,
  resolved INTEGER DEFAULT 0   -- 重练答对置 1
);

CREATE TABLE question_stats (
  question_id INTEGER PRIMARY KEY,
  attempts INTEGER DEFAULT 0,
  correct INTEGER DEFAULT 0
);
```

## 六、实施里程碑

```
T1 出题引擎：/api/exam/generate（范围/题型/数量 + 三道闸 + sqlite 缓存）
T2 做题闭环：前端测验页 + 练习模式（即时判分）
T3 模拟考试：计时 + 答题卡 + 交卷成绩单
T4 错题本 + 章节练习
T5 学习报告
T6 回归验证 + 部署更新
```

## 七、错误处理与安全

- 知识库为空 / 检索不到种子段 → 明确提示"请先上传教材"
- LLM 生成失败 / 自检低分 → 跳过该段，继续下一段；数量不足则返回已生成部分并提示
- 题目内容来自教材，仅学习用途；答案以教材为准（同问答的免责声明）
- sqlite 文件放 data/exam.db，随项目备份

## 八、非目标（YAGNI）

- 不做实操考核模拟（那是临床环节）
- 不做用户多账号体系（单用户场景）
- 不做题目人工审核 UI（置信度自检 + 解析自带来源即可；如后续题质量有问题再评估）