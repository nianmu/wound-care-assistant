# Embedding 与向量检索 — retrieval/

> 职责：向量化（硅基流动 Qwen3-Embedding-8B）与 Chroma 增删查。前端的一切"找哪里"都走这里。

## 1. embedder.py — Embedding API 封装

```python
class Embedder:
    def __init__(self, model_id=None)  # 默认 settings.embedding_model_id
        # 从 ModelRegistry 拿: model_name, dimensions(1024), api_key, base_url
        # 创建 OpenAI 客户端（OpenAI 兼容）

    embed_texts(texts) -> list[list[float]]   # 批量，100条/批，按 index 排序
    embed_query(text)  -> list[float]         # 单条（= embed_texts([text])[0]）
```

- 通过 `openai` SDK 调 `/embeddings`（`model` + `dimensions=1024`）
- 硅基流动模型名：`Qwen/Qwen3-Embedding-8B`
- 维度固定 1024（换模型需同维度，见 [config.md](config.md)）

## 2. retriever.py — Chroma 持久化

### 进程级单例

- 业务代码**必须**用 `get_store()` 取单例，**不要** `VectorStore()` 每个请求新建：
  每次 new 都会重新打开 PersistentClient / 重建 HNSW 索引，冷启动慢且浪费内存
- 单例内部所有 Chroma 访问过 `self._lock`（PersistentClient 非线程安全），读写串行化

### 集合

- 集合名：`wound_care_kb`
- 空间：`cosine`（`metadata={"hnsw:space": "cosine"}`）
- 持久化：`CHROMA_PERSIST_DIR`（默认 `./chroma_db`）
- **显式传向量**：add 时给 `embeddings=`，绝不触发 Chroma 默认 embedding（防下载模型到本机/服务器）

### 核心方法

| 方法 | 说明 |
| :-- | :-- |
| `get_store()` | 进程级单例入口（线程安全） |
| `add_documents(docs)` | 向量化 + 入库；要求切片带 `doc_id` 或 `chunk_id` 元数据 |
| `similarity_search(query, k)` | 返回 `[(Document, score)]`；**score = 1 - cosine_distance**，钳位 [0,1] |
| `count()` | 总数 |
| `sources()` | 已索引来源名（去重） |
| `delete_source(source)` | 删某教材全部切片（`where={"source": ...}`） |
| `get_source_chunks(source, limit)` | 文档详情页用：按来源取切片，按 page/序号排序 |
| `reset()` | 删集合重建（换 embedding 后全量重建用） |

### 检索返回结构

```python
hits = [(Document, score), ...]  # score=1 最相关；cosine distance 0→score 1
# Document.page_content = 原文切片
# Document.metadata: {source, page?, file_path, chunk_id, chunk_index}
```

### 排序

`get_source_chunks` 排序键：`(page is None, page or 0, chunk_index or 0)`——有页码的按页码，无页码的按序号，保证详情页阅读顺序。

## 3. 数据在 Chroma 的形态

```
id: "伤口护理学#42"           → chunk_id（来源#序号，上传时生成）
document: 切片原文
metadata: {source: "伤口护理学", page: 12, chunk_index: 42, file_path: ...}
embedding: 1024 维 float 数组
```

## 4. 修改指南

| 想改什么 | 位置 |
| :-- | :-- |
| 检索距离度量 | `retriever.py` 的 `metadata={"hnsw:space": ...}`（注：改度量需重建索引） |
| 批量大小 | `embedder.py` batch_size（100） |
| 排序键 | `retriever.py get_source_chunks` |

## 5. 故障排查

| 现象 | 原因 | 处理 |
| :-- | :-- | :-- |
| 问答总说"未找到" | 阈值过滤太严 / 知识库空 | 查 `RELEVANCE_THRESHOLD`，先确认 `store.count()` |
| 上传后 count 不变 | 重复上传覆盖逻辑（delete_source 再 add） | 对照 /api/documents 返回 |
| 换 embedding 后检索错乱 | 维度不一致 + 旧索引 | 重建索引 |