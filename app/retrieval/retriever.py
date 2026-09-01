"""ChromaDB 检索封装：本地持久化，显式传向量（不触发默认 embedding 下载）。

进程内单例：避免每个请求重新打开 PersistentClient / 重建 HNSW 索引（冷启动
慢 + 内存浪费）。所有 Chroma 访问通过模块级锁串行化，多线程安全。
"""
from __future__ import annotations

import threading
from pathlib import Path

import chromadb
from langchain_core.documents import Document

from app.config import get_settings
from app.retrieval.embedder import Embedder

# Collection 命名与持久化目录
COLLECTION_NAME = "wound_care_kb"

_store: "VectorStore | None" = None
_store_lock = threading.Lock()


def get_store() -> "VectorStore":
    """进程级单例（线程安全）。"""
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                _store = VectorStore()
    return _store


class VectorStore:
    def __init__(self, embedding: Embedder | None = None, collection: str = COLLECTION_NAME) -> None:
        self.embedding = embedding or Embedder()
        self.collection = collection
        persist = Path(get_settings().chroma_persist_dir)
        persist.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(persist))
        # 仅传 metadata，强制后续 add 时显式给 embeddings，避免 chroma 默认模型下载
        self._col = self._client.get_or_create_collection(
            name=collection,
            metadata={"hnsw:space": "cosine"},
        )
        # 所有公开方法在 _lock 下执行（Chroma PersistentClient 非线程安全）
        self._lock = threading.Lock()

    # ---- 索引 ----
    def add_documents(self, docs: list[Document]) -> int:
        if not docs:
            return 0
        texts = [d.page_content for d in docs]
        vectors = self.embedding.embed_texts(texts)
        ids = []
        metadatas = []
        for i, d in enumerate(docs):
            doc_id = d.metadata.get("doc_id") or d.metadata.get("chunk_id")
            if not doc_id:
                continue
            ids.append(doc_id)
            meta = dict(d.metadata)
            meta.pop("doc_id", None)
            meta.pop("chunk_id", None)
            metadatas.append(meta)
        if not ids:
            raise ValueError("切片缺少 doc_id/chunk_id 元数据，无法入库")
        with self._lock:
            self._col.add(ids=ids, embeddings=vectors, documents=texts, metadatas=metadatas)
        return len(ids)

    # ---- 检索 ----
    def similarity_search(self, query: str, k: int = 5) -> list[tuple[Document, float]]:
        q_vec = self.embedding.embed_query(query)
        with self._lock:
            res = self._col.query(query_embeddings=[q_vec], n_results=k, include=["documents", "metadatas", "distances"])
        docs: list[tuple[Document, float]] = []
        for i in range(len(res["ids"][0])):
            meta = res["metadatas"][0][i] or {}
            doc = Document(page_content=res["documents"][0][i], metadata=meta)
            dist = res["distances"][0][i]
            # cosine 距离 → 相似度（1 - distance），并钳位到 [0,1]
            score = max(0.0, min(1.0, 1.0 - dist))
            docs.append((doc, score))
        return docs

    # ---- 管理 ----
    def count(self) -> int:
        with self._lock:
            return self._col.count()

    def sources(self) -> list[str]:
        """已索引的来源列表（distinct source 元数据）。"""
        with self._lock:
            res = self._col.get(include=["metadatas"])
        srcs = {m.get("source", "unknown") for m in res["metadatas"]}
        return sorted(srcs)

    def delete_source(self, source: str) -> int:
        with self._lock:
            res = self._col.get(where={"source": source}, include=[])  # include=[] 只取 ids
            ids = res["ids"]
            if ids:
                self._col.delete(ids=ids)
        return len(ids)

    def get_source_chunks(self, source: str, limit: int = 500) -> list[dict]:
        """按来源取全部切片（文档详情页用），按页码/序号排序。

        返回 [{id, page, content, chunk_index}]。
        """
        with self._lock:
            res = self._col.get(
                where={"source": source},
                include=["documents", "metadatas"],
                limit=limit,
            )
        chunks: list[dict] = []
        for i, doc_id in enumerate(res["ids"]):
            meta = res["metadatas"][i] or {}
            chunks.append({
                "id": doc_id,
                "page": meta.get("page"),
                "chunk_index": meta.get("chunk_index"),
                "content": res["documents"][i],
            })
        # 排序：有 page 按 page，否则按 chunk_index
        chunks.sort(key=lambda c: (c["page"] is None, c["page"] or 0, c["chunk_index"] or 0))
        return chunks

    def reset(self) -> None:
        with self._lock:
            self._client.delete_collection(self.collection)
            self._col = self._client.get_or_create_collection(
                name=self.collection,
                metadata={"hnsw:space": "cosine"},
            )