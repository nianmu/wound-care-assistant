"""Embedding 封装：OpenAI 兼容接口统一调用（硅基流动 Qwen3-Embedding-8B 等）。"""
from __future__ import annotations

from typing import Sequence

from openai import OpenAI

from app.config import get_registry, get_settings


class Embedder:
    """按 models.yaml 中的 embedding 模型配置创建客户端。"""

    def __init__(self, model_id: str | None = None) -> None:
        registry = get_registry()
        self.model_id = model_id or get_settings().embedding_model_id
        conf = registry.embedding_model(self.model_id)
        self.model_name = conf["model"]
        self.dimensions = int(conf.get("dimensions", 1024))
        self._client = OpenAI(base_url=conf["base_url"], api_key=conf["api_key"])

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        """批量向量化。可能拆批（单请求上限 2048 条）。"""
        result: list[list[float]] = []
        batch_size = 100
        for i in range(0, len(texts), batch_size):
            batch = list(texts[i : i + batch_size])
            resp = self._client.embeddings.create(
                model=self.model_name,
                input=batch,
                dimensions=self.dimensions,
            )
            # OpenAI 兼容接口按请求内顺序返回
            ordered = sorted(resp.data, key=lambda e: e.index)
            result.extend([e.embedding for e in ordered])
        return result

    def embed_query(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]