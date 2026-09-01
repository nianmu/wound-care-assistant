# 文档加载与切片 — ingestion/

> 职责：把 txt 教材变成"带页码元数据的切片"。**PDF/EPUB 解析不在这里**（在开发机 tools/，见 [03-tools.md](../03-tools.md)）。

## 1. loader.py — 读取 txt 并解析页码

### 页码标记规范（跨模块约定）

开发机转换脚本（tools/）在**每一页文本前**插入一行：

```
@@PAGE:1@@
（第1页内容）
@@PAGE:2@@
（第2页内容）
```

`loader.py` 用正则 `^@@PAGE:(\d+)@@` 切分，每页生成一个 `Document`，`metadata["page"]=N`。

| 情况 | 行为 |
| :-- | :-- |
| 有页码标记 | 按页切分，每 Document 带 `page` |
| 无标记（旧 txt） | 整体一个 Document，**无 page** 字段（兼容） |

### 关键函数

```python
load_document(path, source_label=None) -> list[Document]
# 校验后缀（.txt/.md，拒绝其他）→ 读 UTF-8 → 按页码切分
# 每个 Document: page_content + metadata{source, file_path[, page]}

load_txt_files(directory)  # 批量，按文件名排序
```

### 为什么服务器拒绝 PDF？

设计决策：**解析重活不放在 2C2G 服务器**。服务器只收纯文本，PDF/EPUB 在开发机（有 GPU/OCR 工具）转成带页码标记的 txt 再上传。`/api/upload` 对 .pdf/.epub 返回明确指引。

## 2. chunker.py — 文本切片

```python
CHUNK_SIZE = 500      # 每块最大字符数
CHUNK_OVERLAP = 50    # 块间重叠（保持语义连贯）
SEPARATORS = ["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""]
```

- 基于 LangChain `RecursiveCharacterTextSplitter`
- **中文优先断句**：段落 → 句号/叹号/问号/分号/逗号 → 空格 → 字符
- `split_documents(docs)` 追加 `chunk_index` 元数据
- （loader 已按页切，chunker 在页内再切 500 字块 → 每个 chunk 继承该页的 page）

### 切片为什么 500 字？

- 语义完整（中文段落/句群）
- 检索精度与上下文窗口平衡
- 检索时 Top-K=5 拼接 ≈ 2500 字，LLM 上下文充足

## 3. 数据流

```
data/raw/教材.txt（带 @@PAGE:N@@）
  → load_document → [Document(page=1, content=第1页…), Document(page=2, …)]
  → split_documents → [[chunk500, chunk450](page1), [chunk500](page2), …]
  → VectorStore.add_documents（见 retrieval.md）
```

## 4. 修改指南

| 想改什么 | 位置 |
| :-- | :-- |
| 切片大小/重叠 | `chunker.py` CHUNK_SIZE / CHUNK_OVERLAP |
| 中文分隔符 | `chunker.py` SEPARATORS |
| 页码标记格式 | 需**同步改** tools 转换脚本 + `loader.py` PAGE_MARK_RE |
| 支持新文本格式 | `loader.py` SUPPORTED + load_document 分支 |

> ⚠️ 页码标记是**跨模块协议**：改格式必须同时改 tools/（生成端）、loader.py（消费端）、现有教材需重新转换上传。