# 后端配置 — config.py / .env / models.yaml

> 配置文件是整个系统的"开关"。改配置 = 改 `.env` 或 `models.yaml`，然后重启后端即可，无需改代码。

## 1. 配置读取架构

```
.env（环境变量）            models.yaml（模型注册表）
    │                            │
    └──► config.py               │
         ├─ Settings（dataclass）│
         └─ ModelRegistry ◄──────┘
              └─ 全局单例 get_settings() / get_registry()
```

- `.env` 通过 `python-dotenv` 在模块导入时加载（`load_dotenv(BASE_DIR / ".env")`）
- `models.yaml` 位于项目根，存模型**元数据**（如何调用）；**API Key 一律不落文件**，从环境变量读

## 2. Settings 全部字段（.env）

| 环境变量 | 默认值 | 说明 |
| :-- | :-- | :-- |
| `DEFAULT_MODEL` | `deepseek-chat` | 默认 LLM 的 models.yaml id |
| `EMBEDDING_MODEL_ID` | `qwen3-embedding-8b` | 默认 embedding 模型的 id |
| `CHROMA_PERSIST_DIR` | `./chroma_db` | 向量库持久化目录 |
| `DEFAULT_TOP_K` | `5` | 问答检索片段数 |
| `RELEVANCE_THRESHOLD` | `0.35` | 相关度阈值（低于此不送 LLM） |
| （数据目录 `data_dir`/`raw_dir`/`processed_dir` 固定推导，不配置） | | |

**.env 示例结构**（Key 用占位）：

```ini
# 大模型（默认走硅基流动）
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.siliconflow.cn/v1
DEFAULT_MODEL=deepseek-chat

# 其他模型可选
# DASHSCOPE_API_KEY=...  # 通义
# ZHIPU_API_KEY=...      # 智谱
# MOONSHOT_API_KEY=...   # Kimi

# Embedding（硅基流动）
SILICONFLOW_API_KEY=sk-xxx
SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1
EMBEDDING_MODEL=Qwen/Qwen3-Embedding-8B
EMBEDDING_MODEL_ID=qwen3-embedding-8b
EMBEDDING_DIMENSIONS=1024

# 检索
DEFAULT_TOP_K=5
RELEVANCE_THRESHOLD=0.35
```

> ⚠️ `EMBEDDING_MODEL`（模型名）仅在调用 API 时用；`EMBEDDING_MODEL_ID` 是 models.yaml 里的条目 id，`ModelRegistry.embedding_model()` 会用它查注册表。两者分开：代码以 id 查表，id→模型名的映射在 models.yaml。

## 3. 模型注册表 models.yaml

```yaml
chat_models:
  - id: deepseek-chat          # 内部 id（代码/前端引用它）
    name: DeepSeek V3.2（硅基流动）  # 展示名
    base_url: https://api.siliconflow.cn/v1
    model: deepseek-ai/DeepSeek-V3.2  # 厂商侧模型名
    api_key_env: DEEPSEEK_API_KEY     # 从哪个环境变量读 Key

embedding_models:
  - id: qwen3-embedding-8b
    name: 硅基流动 Qwen3-Embedding-8B (1024维)
    base_url: https://api.siliconflow.cn/v1
    model: Qwen/Qwen3-Embedding-8B
    api_key_env: SILICONFLOW_API_KEY
    dimensions: 1024
```

### 加一个新 LLM 模型（零代码改动）

1. `models.yaml` 的 `chat_models` 加一个条目（id/name/base_url/model/api_key_env）
2. `.env` 加对应的 `XXX_API_KEY`
3. 重启后端 → 前端「学习设置」页自动出现新模型

> 注意：所有厂商必须提供 **OpenAI 兼容** `/chat/completions` 接口（DeepSeek/硅基流动/通义/智谱/Kimi 都兼容）。Embedding 同理需兼容 `/embeddings`。

### 换 Embedding 模型的约束

- **维度必须一致**（当前 1024）：不同维度会导致旧索引（chroma_db）全部失效，需重建索引（重新上传教材）。
- 切换流程：改 `.env` 的 `EMBEDDING_MODEL_ID` + `EMBEDDING_MODEL` → 重启 → 删 `chroma_db/` → 重新上传全部教材。

## 4. ModelRegistry 关键方法

| 方法 | 返回 | 备注 |
| :-- | :-- | :-- |
| `chat_model_ids()` | 全部 chat 模型 id | /api/models 用 |
| `chat_model(id)` | `{..., api_key}` | **解析 Key**，缺 Key 抛 RuntimeError |
| `chat_model_info(id)` | `{id,name,model}` 无 Key | /health、前端列表用，缺 Key 不报错 |
| `embedding_model(id)` | `{..., api_key, dimensions}` | 同上解析 Key |
| `embedding_model_info(id)` | 无 Key 版本 | 同上 |

> 为什么分 `chat_model`（带 Key）和 `chat_model_info`（不带 Key）？`/health` 和前端模型列表在**缺 Key 时也不能 500**——只展示信息，调用时才校验 Key。业务代码（LLMClient/Embedder）用带 Key 的方法，拿 Key 失败会抛"缺少环境变量 xxx"明确报错。

## 5. 常见故障

| 现象 | 原因 | 处理 |
| :-- | :-- | :-- |
| 切换某模型报 500 "未配置可用 Key" | 该模型 api_key_env 在 .env 缺失 | 补 Key 或换模型 |
| /health 报"缺少环境变量" | 误用带 Key 的方法 | 用 `*_info` 方法 |
| 换 embedding 后问答错乱 | 维度不一致旧索引 | 重建索引（见上） |
| `.env` 改了不生效 | 需重启后端（模块单例缓存） | 重启 uvicorn |