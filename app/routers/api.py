"""业务 API：/api/upload /api/ask /api/ask/stream /api/documents。"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.auth.deps import get_current_admin
from app.config import get_registry, get_settings
from app.generation.llm import LLMClient
from app.ingestion.chunker import split_documents
from app.ingestion.loader import SUPPORTED, load_document
from app.retrieval.retriever import get_store

router = APIRouter(prefix="/api")


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    model_id: str | None = None  # 不传则用默认模型
    top_k: int | None = Field(default=None, ge=1, le=20)  # 默认取配置值 5
    history: list[dict] = []  # 最近对话 [{role: user|assistant, content}]，用于多轮追问


def _validate_model(model_id: str) -> None:
    """校验模型存在且 Key 已配置；失败抛 HTTPException。"""
    registry = get_registry()
    if model_id not in registry.chat_model_ids():
        raise HTTPException(404, f"未知模型 {model_id}，可选: {registry.chat_model_ids()}")
    try:
        registry.chat_model(model_id)
    except RuntimeError as e:
        raise HTTPException(500, f"模型 {model_id} 未配置可用 Key：{e}")


def _grounded_query(question: str, history: list[dict]) -> str:
    """检索用查询：有历史时把最近的用户问题拼进来，使"那 III 期呢？"这类追问
    能命中上一轮主题；无历史则原样返回。每次回答的检索/引用仍相互独立。"""
    if not history:
        return question
    for h in reversed(history):
        if h.get("role") == "user" and (h.get("content") or "").strip():
            prev = h["content"].strip()[:300]
            return f"{prev} {question}" if prev and prev != question else question
    return question


def _retrieve(req: AskRequest, model_id: str) -> list | None:
    """检索 Top-K 并过滤低相关片段。返回 None 表示应走空知识库提示。"""
    store = get_store()
    if store.count() == 0:
        return None
    k = req.top_k or get_settings().default_top_k
    hits = store.similarity_search(_grounded_query(req.question, req.history), k=k)
    threshold = get_settings().relevance_threshold
    hits = [(doc, score) for doc, score in hits if score >= threshold]
    return hits or None


def _empty_answer(model_id: str) -> dict:
    """知识库为空 / 无有效命中时的统一兜底。"""
    return {
        "answer": "教材中未找到相关内容，请以老师课堂讲授为准。",
        "sources": [],
        "model": model_id,
    }


def _build_answer(model_id: str, llm: LLMClient, question: str, hits: list, answer: str) -> dict:
    """组装回答 + 引用来源（带页码）。"""
    sources = _source_labels(hits)
    return {
        "answer": answer,
        "sources": sources,
        "model": llm.display_name,
        "top_k_used": len(hits),
    }


def _source_labels(hits: list) -> list[dict]:
    """来源列表（去重），每个含 source 名称与页码数组，供前端定位原文。"""
    merged: dict[str, set] = {}
    for doc, _score in hits:
        src = doc.metadata.get("source", "未知来源")
        merged.setdefault(src, set())
        if doc.metadata.get("page") is not None:
            merged[src].add(int(doc.metadata["page"]))
    return [
        {"source": s, "pages": sorted(pages)}
        for s, pages in sorted(merged.items())
    ]


def _ingest(dest: Path, source_label: str) -> int:
    """加载→切片→入库（同步、阻塞，由调用方放入线程池执行）。"""
    docs = load_document(dest, source_label=source_label)
    chunks = split_documents(docs)
    # 为每个 chunk 生成稳定 ID（来源+序号）
    for i, c in enumerate(chunks):
        c.metadata["chunk_id"] = f"{source_label}#{i}"
    store = get_store()
    store.delete_source(source_label)
    return store.add_documents(chunks)


@router.post("/upload")
async def upload_file(file: UploadFile = File(...), _admin: dict = Depends(get_current_admin)):
    """接收教材（txt/md）→ 切片 → 向量化 → 入库。返回 chunk 数与来源名。

    ⚠️ 高危操作：仅系统管理员（is_admin=1）可上传，非管理员 403。
    服务器不做 PDF/EPUB 解析（保持 2C2G 轻量）；PDF/EPUB 请在开发机
    用 tools/ 转换（见 tools/README.md）后上传 txt。
    """
    settings = get_settings()
    # 1. 校验扩展名：服务器只收纯文本
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED:
        guidance = {
            ".pdf": "请在开发机运行 python tools/convert_pdf.py 或 convert_pdf_ocr.py 转成 txt 后上传",
            ".epub": "请在开发机运行 python tools/convert_epub.py 转成 txt 后上传",
        }
        hint = guidance.get(suffix, "请先用 tools/ 转换脚本转成 UTF-8 txt")
        raise HTTPException(400, f"{suffix} 不在服务器支持范围（{sorted(SUPPORTED)}）。{hint}")

    # 2. 落盘到 data/raw/
    raw_dir = settings.raw_dir
    raw_dir.mkdir(parents=True, exist_ok=True)
    dest = raw_dir / (file.filename or f"upload{suffix}")
    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(400, "文件不是 UTF-8 编码，请转换后再上传")
    dest.write_text(text, encoding="utf-8")

    # 3-4. 加载+切片+向量化+入库（阻塞 + 网络，放线程池，避免卡事件循环）
    source_label = dest.stem
    try:
        n = await asyncio.to_thread(_ingest, dest, source_label)
    except ValueError as e:
        dest.unlink(missing_ok=True)
        raise HTTPException(400, str(e))

    return {"status": "success", "chunk_count": n, "source": source_label, "total_in_kb": get_store().count()}


@router.get("/documents")
async def list_documents():
    """已索引来源 + 总量。"""
    store = get_store()
    return {"sources": store.sources(), "total_chunks": store.count()}


@router.post("/ask")
async def ask(req: AskRequest):
    """RAG 问答（非流式）：检索 Top-K → 拼接 Prompt（含对话历史）→ 指定模型生成 → 返回答案+引用。"""
    model_id = req.model_id or get_settings().default_model
    _validate_model(model_id)

    hits = await asyncio.to_thread(_retrieve, req, model_id)
    if hits is None:
        return _empty_answer(model_id)

    llm = LLMClient(model_id)
    answer = await asyncio.to_thread(llm.generate, req.question, hits, req.history)
    return _build_answer(model_id, llm, req.question, hits, answer)


@router.post("/ask/stream")
async def ask_stream(req: AskRequest):
    """RAG 问答（SSE 流式）：逐字返回 answer 增量，结尾附 sources/model。

    事件格式（text/event-stream）：
      data: {"type":"delta","text":"..."}     # 增量文本（前端逐字渲染）
      data: {"type":"sources","sources":[...]} # 引用来源（含页码）
      data: {"type":"done"}                    # 结束
    """
    model_id = req.model_id or get_settings().default_model
    _validate_model(model_id)

    hits = await asyncio.to_thread(_retrieve, req, model_id)
    if hits is None:
        empty = _empty_answer(model_id)
        return StreamingResponse(
            _sse([{"type": "delta", "text": empty["answer"]}, {"type": "done"}]),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    llm = LLMClient(model_id)

    def gen():
        try:
            for piece in llm.generate_stream(req.question, hits, req.history):
                yield _sse_event({"type": "delta", "text": piece})
            yield _sse_event({"type": "sources", "sources": _source_labels(hits), "model": llm.display_name})
            yield _sse_event({"type": "done"})
        except Exception as e:  # noqa: BLE001 - 流式中途异常也需端给前端
            yield _sse_event({"type": "error", "message": f"生成中断：{e}"})

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _sse_event(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


def _sse(items: list[dict]) -> object:
    for it in items:
        yield _sse_event(it)


@router.get("/models")
async def list_models():
    """可用 LLM 列表（供前端下拉切换，不含 Key）。"""
    registry = get_registry()
    return {
        "default": get_settings().default_model,
        "chat_models": [registry.chat_model_info(mid) for mid in registry.chat_model_ids()],
        "embedding": registry.embedding_model_info(get_settings().embedding_model_id),
    }


@router.get("/documents/{source}/chunks")
async def get_document_chunks(source: str):
    """某个来源的全部切片（文档详情页用），按页码/序号排序。"""
    store = get_store()
    chunks = store.get_source_chunks(source)
    return {"source": source, "total": len(chunks), "chunks": chunks}


@router.delete("/documents/{source}")
async def delete_document(source: str, _admin: dict = Depends(get_current_admin)):
    """删除某个来源的全部切片（含 data/raw 原始文件，匹配任意扩展名）。

    ⚠️ 高危操作：仅系统管理员（is_admin=1）可删除，非管理员 403。
    """
    store = get_store()
    n = store.delete_source(source)
    raw_dir = get_settings().raw_dir
    for raw_file in raw_dir.glob(f"{source}.*"):
        raw_file.unlink(missing_ok=True)
    return {"deleted_chunks": n, "source": source}