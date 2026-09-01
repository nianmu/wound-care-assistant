# 术语表

> 项目内常用术语速查。首次阅读建议扫一遍。

## 概念

| 术语 | 含义 |
| :-- | :-- |
| **RAG** | 检索增强生成：先检索教材内容，再让 LLM 基于检索结果回答 |
| **ET** | Enterostomal Therapist，造口治疗师（本项目用户的目标证书） |
| **WCET** | World Council of Enterostomal Therapists，世界造口治疗师协会（认证机构） |
| **Chunk / 切片** | 教材被切成的 500 字片段，检索的最小单位 |
| **ChromaDB** | 本地嵌入式向量数据库（本项目存切片向量） |
| **Embedding / 向量** | 文本转成的数值向量（本项目 1024 维），用相似度找相关内容 |
| **Top-K** | 检索返回的片段数量（默认 5） |
| **置信度（confidence）** | AI 出题时自评的答案可靠程度（0~1，<0.7 丢弃） |

## 页码标记协议

| 符号 | 含义 | 位置 |
| :-- | :-- | :-- |
| `@@PAGE:N@@` | 第 N 页的起始标记 | txt 每页开头（tools 生成，loader 解析） |

跨模块约定：改格式需同步 tools/（生成）+ app/ingestion/loader.py（解析）。

## 配置项速查

| 配置 | 位置 | 默认 | 说明 |
| :-- | :-- | :-- | :-- |
| `DEEPSEEK_API_KEY` | .env | — | 硅基流动 Key（默认模型用） |
| `SILICONFLOW_API_KEY` | .env | — | Embedding Key |
| `DEFAULT_MODEL` | .env | `deepseek-chat` | 默认 chat 模型 id |
| `EMBEDDING_MODEL_ID` | .env | `qwen3-embedding-8b` | 默认 embedding id |
| `DEFAULT_TOP_K` | .env | 5 | 检索片段数 |
| `RELEVANCE_THRESHOLD` | .env | 0.35 | 相关度阈值（防编造） |
| `CHROMA_PERSIST_DIR` | .env | ./chroma_db | 向量库目录 |
| models.yaml | 根目录 | — | 模型注册表（id→模型名/地址/Keyenv） |

详见 [01-backend/config.md](01-backend/config.md)。

## 前端存储键

| 键 | 内容 |
| :-- | :-- |
| `wc_model_id` | 用户选择的模型 id（localStorage） |
| `wc_top_k` | 用户选择的 Top-K（localStorage） |
| `globalData.examQuestions` | 出题结果（会话内，quiz 读取） |
| `globalData.examResult` | 判分结果（会话内，result 读取并清空） |

## 测试

| 测试文件 | 覆盖 |
| :-- | :-- |
| tests/test_health.py | /health、模型注册表缺 Key 报错 |
| tests/test_ingestion.py | 切片边界、中文断句、页码解析、拒绝 PDF |
| tests/test_pages.py | loader 页码多页/无标记/多行 |
| tests/test_exam.py | 题目缓存、判分规则、错题流、统计 |