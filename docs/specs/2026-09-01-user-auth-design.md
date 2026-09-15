# 用户账户体系设计（B 模式：用户名+密码+JWT）

- 日期：2026-09-01
- 状态：待评审
- 关联：[2026-08-31-exam-module-design.md](./2026-08-31-exam-module-design.md)（考试模块，本设计在其上增加用户维度）

## 1. 背景与目标

当前应用无账户体系：考试数据（成绩/错题/统计）全局共享，无法区分家人各自的学习进度。
目标：引入用户名+密码账户，按用户隔离个人学习数据，支持未来多设备同步。

非目标（本阶段不做）：
- 多设备跨端同步（依赖登录态天然支持，但对话历史持久化不在本设计内）
- 管理员/角色权限分级
- 微信/短信 OAuth（成本与复杂度过度）
- HTTPS 启用（域名 nianmu.top 备案中，过渡期暂用 IP+HTTP，备案通过后切换，见 §7）

## 2. 已确认决策

| 决策点 | 结论 |
| :-- | :-- |
| 认证模式 | 用户名+密码，bcrypt 哈希 + JWT（HS256） |
| 问答模块 | **不强制登录**（打开即可问，考试模块强制） |
| 存量数据 | 归第一个注册的用户（自动迁移，不丢历史） |
| 个人数据隔离表 | exam_attempts / wrong_book / question_stats |
| 公共数据不动 | exam_questions（题库缓存全局共享） |

## 3. 数据模型（sqlite，幂等迁移）

### 3.1 新表 users

```sql
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,   -- bcrypt(12 轮)
  display_name TEXT,
  created_at TEXT
);
```

- `username`：登录名，唯一；小写英文+数字+下划线，3~32 字符
- `display_name`：昵称（"妈妈"等），可空，1~20 字符，默认取 username

### 3.2 个人数据表加列（幂等 ALTER）

```sql
ALTER TABLE exam_attempts  ADD COLUMN user_id INTEGER NOT NULL DEFAULT 0;
ALTER TABLE wrong_book     ADD COLUMN user_id INTEGER NOT NULL DEFAULT 0;
ALTER TABLE question_stats ADD COLUMN user_id INTEGER NOT NULL DEFAULT 0;
```

- sqlite 的 ADD COLUMN 需探测列存在（`PRAGMA table_info`），缺失才执行 → 幂等
- `user_id=0` 表示"未归属历史数据"

### 3.3 存量数据归属（首个用户注册时执行一次）

首个用户注册成功后：
```sql
UPDATE exam_attempts  SET user_id = ? WHERE user_id = 0;
UPDATE wrong_book     SET user_id = ? WHERE user_id = 0;
UPDATE question_stats SET user_id = ? WHERE user_id = 0;
```
（`?` = 新用户 id；注册前先查 users 是否为空判断是否"首个"）

### 3.4 查询改造

- wrong_book / stats / question_stats 查询均加 `WHERE user_id = ?`
- 写入（record_answer / add_wrong / mark_resolved / save_attempt）均带 user_id
- exam_questions 不动

## 4. 认证实现

### 4.1 依赖

- `bcrypt`（密码哈希，cost=12）
- `pyjwt`（JWT，HS256）

### 4.2 配置（.env 新增）

```
JWT_SECRET=<64字节随机串>      # 生成: openssl rand -hex 32
JWT_EXPIRES_DAYS=7
```

- `JWT_SECRET` 缺失时启动即报错（防默认密钥上线）
- 服务器 .env chmod 600

### 4.3 Token 载荷与校验

```json
{ "sub": "12", "name": "妈妈", "exp": 1725206400, "iat": 1725120000 }
```

- `sub` = user id（字符串）；`exp` = 7 天后
- FastAPI 依赖 `get_current_user`：解析 Bearer token → 校验签名/过期 → 查库返回用户；失败 401

### 4.4 防爆破（登录限速）

- 内存计数（进程级，单 worker 够用）：key = `login:<username>` 与 `login:<ip>`
- 连续错 5 次 → 锁 5 分钟（429 + 提示"尝试过多，5 分钟后再试"）
- 成功登录清空计数

### 4.5 密码策略

- 长度 ≥ 8，至少含 1 字母 + 1 数字（前后端双校验）
- bcrypt 比较用 `checkpw`，恒时比较由库保证

## 5. API 设计

### 5.1 新增认证端点

| 方法 | 路径 | 请求 | 响应 | 说明 |
| :-- | :-- | :-- | :-- | :-- |
| POST | `/api/auth/register` | `{username, password, display_name?}` | `{token, user}` | 注册即登录；首个用户触发存量迁移 |
| POST | `/api/auth/login` | `{username, password}` | `{token, user}` | 限速保护 |
| GET | `/api/auth/me` | —（带 token） | `{user}` | 前端启动校验；401=未登录/过期 |

`user` 结构：`{"id": 1, "username": "mama", "display_name": "妈妈"}`（不含任何哈希）。

错误约定：
- 400：用户名已存在 / 密码不合规 / 用户名格式错
- 401：用户名或密码错误 / token 缺失或失效
- 429：限速锁定中

### 5.2 现有接口鉴权改造

| 接口 | 鉴权 | 说明 |
| :-- | :-- | :-- |
| /api/ask, /api/ask/stream | ❌ 不要求 | 问答保持低门槛 |
| /api/exam/generate | ✅ 要求登录 | 题库全局缓存，但统计使用方需身份 |
| /api/exam/submit | ✅ 要求登录 | 判分写入当前用户 |
| /api/exam/wrong-book, /api/exam/stats, /api/exam/topics | ✅ 要求登录 | 按 user_id 过滤 |
| /api/upload, /api/documents* | ❌ 不要求（保持现状） | 家庭管理员即本人 |

- 未带/无效 token 访问受保护接口 → 401（前端统一跳登录）

## 6. 前端改造

### 6.1 新页面 pages/auth/login.vue（登录+注册合一）

- 两个 tab：登录 / 注册
- 登录：username + password → 存 `wc_token`/`wc_user` → `uni.navigateBack()`
- 注册：username + password + 昵称（可选）→ 自动登录
- 校验：密码 ≥8 位含字母数字（前端提示）
- 登录失败 401 → 提示"用户名或密码错误"；429 → 提示锁定

### 6.2 pages.json

- 新增 `pages/auth/login`（navigationStyle custom？统一普通导航即可）
- tabBar 不变

### 6.3 api.js 改造

- 新增 `register()` / `login()` / `getMe()`
- 统一请求头：所有请求（uni.request / fetch / uploadFile）自动附 `Authorization: Bearer <wc_token>`
- 401 统一处理：清 token + 跳登录页（`uni.navigateTo auth/login`）——问答接口除外（不强制）

### 6.4 页面守门

- `exam` 页 onShow：无 `wc_token` → 引导：确认框"需要登录后使用（记录成绩/错题）"，去登录或留在本页提示
- `quiz/wrong/stats` 若遇 401 → 清 token 跳登录
- 设置页/聊天页不强制

### 6.5 localStorage 键

- `wc_token`：JWT
- `wc_user`：{id, username, display_name}

## 7. HTTPS 过渡方案（备案窗口期）

- 现状：公网 IP + HTTP 明文；B 模式密码经明文 → **家庭自用、数据价值低，接受过渡期风险**（已与用户确认）
- nginx 预留：`/etc/nginx/conf.d/wound-care-ssl.conf` 模板（443 ssl + HTTP→HTTPS 跳转 + 反代 /api）**先写好不启用**，随代码入库 deploy/
- 备案通过后切换步骤写入 `deploy/DEPLOY.md`：
  1. 阿里云申请免费证书（域名 nianmu.top）→ 下载 nginx 版 pem/key 上传服务器
  2. 启用 ssl conf → `nginx -t && reload`
  3. 验证 https://nianmu.top
- 切换后如需强制跳转，改 DNS 解析指向即可（域名解析在备案通过前保持不指向）

## 8. 测试清单

新增 `tests/`：
1. `test_auth.py`：
   - 注册成功 → 返回 token，user 无哈希字段
   - 重复用户名 → 400
   - 弱密码（<8 位 / 纯字母）→ 400
   - 登录成功/密码错误 401
   - 连续 5 次错密 → 429 锁定
   - /api/auth/me 带有效 token → 200；无/坏 token → 401
   - 首个用户注册触发存量迁移（预置 user_id=0 数据 → 归属新用户）
   - 第二个用户注册不触发迁移、不拿到第一个用户的数据
2. `test_exam.py` 扩展：
   - submit/wrong-book/stats 无 token → 401
   - 用户 A 与用户 B 错题本/统计互相隔离
3. 回归：既有 14 项全过

## 9. 受影响文件

后端：
- `app/config.py`（JWT_SECRET / JWT_EXPIRES_DAYS 配置）
- `app/auth/`（新）：`security.py`（bcrypt+JWT）、`deps.py`（get_current_user）、`router.py`（register/login/me）
- `app/exam/store.py`（users 表 + 三表加列 + 迁移 + 查询/写入按 user_id）
- `app/exam/engine.py`（无改动，做题/统计在 grader）
- `app/exam/grader.py`（record_answer/add_wrong/save_attempt 带 user_id）
- `app/exam/router.py`（全部端点要求登录 + 透传 user_id）
- `app/main.py`（挂 auth_router）
- `requirements.txt`（+bcrypt +pyjwt）

前端：
- `pages/auth/login.vue`（新）
- `pages.json`（+auth 页）
- `utils/api.js`（auth 函数 + 统一 Authorization + 401 处理）
- `pages/exam/exam.vue`（登录守门）
- `pages/exam/quiz.vue`、`result.vue`、`wrong.vue`、`stats.vue`（401 处理）

文档：`docs/01-backend/api.md`（新端点+鉴权表）、`docs/02-frontend/pages.md`/`api-client.md`、`docs/01-backend/config.md`、`docs/05-data.md`（users 表+user_id）、`deploy/DEPLOY.md`（HTTPS 切换）、`deploy/nginx-ssl.conf`（预留）

## 10. 验收标准

1. 浏览器注册 → 自动登录 → 考试页可出题/答题/看错题本
2. 第二个账号登录 → 错题本/统计与第一个完全隔离
3. 问答不登录也能用；考试模块未登录被引导登录
4. 存量数据（若有）归第一个账号，不丢
5. 14 项旧测试 + 新增测试全过
6. 本地部署验证后，按既有流程上传阿里云（HTTP 过渡），HTTPS 切备案通过后执行

## 11. 追加：注册邀请码（2026-09-01 实施时收紧）

- 需求：不让外人随意注册。方案：注册必须提交 `invite_code`，与 `REGISTER_INVITE_CODE`（.env）一致才放行。
- 安全默认：`REGISTER_INVITE_CODE` **为空 = 注册接口一律 403**（防止忘了配置导致开放）。
- 邀请码是弱秘密（家庭内部口头约定），仅作入门口槛；登录防爆破（5 次锁 5 分钟）不受影响。
- 现网邀请码：`95279527`（.env 可改，改后重启生效）。
- 涉及：`app/config.py`（新配置）、`app/auth/router.py`（register 校验）、`frontend/pages/auth/login.vue`（注册表单加邀请码输入）、`tests/test_auth.py`（+2 用例）。

## 12. 追加：系统管理员（2026-09-01 实施时收紧）

- 需求：文档上传/删除属高危操作，仅系统管理员可执行。
- 模型：users 表加 `is_admin`；管理员唯一（username=admin），由启动时 `ADMIN_PASSWORD`（.env）引导自动创建（`store.ensure_admin`，幂等）。
- 安全默认：`ADMIN_PASSWORD` **未配置 = 不创建管理员**（避免默认密码裸奔；上传/删除接口仍受保护但无人可用）。
- 权限：`/api/upload`、`DELETE /api/documents/{source}` 用 `get_current_admin`（未登录 401 / 非管理员 403）；文档查看保持开放。
- `is_first` 判定改按 `normal_user_count()`（排除管理员）——admin 存在不影响"首个注册家人接管历史数据"。
- 前端：`user.is_admin` 返回给前端（`_public_user`）；上传页非管理员隐藏控件并提示；详情页删除按钮仅管理员可见。
- 现网：ADMIN_PASSWORD 为用户指定口令；改密码 = 改 .env 后删除 admin 行重启（或将来加改密接口）。
- 涉及：`app/exam/store.py`（is_admin 列 + ensure_admin + normal_user_count）、`app/auth/deps.py`（get_current_admin）、`app/auth/router.py`（_public_user + is_first）、`app/routers/api.py`（upload/delete 加 Admin 依赖）、`app/main.py`（lifespan 引导）、`frontend`（upload.vue / doc-detail.vue / api.js）、`tests/test_auth.py`（+3 用例）。