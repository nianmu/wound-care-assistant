"""考试模块 API：/api/exam/generate /submit /wrong-book /stats。"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.exam import engine
from app.exam import store
from app.exam.grader import grade

router = APIRouter(prefix="/api/exam")


class GenerateRequest(BaseModel):
    count: int = Field(default=5, ge=1, le=20)
    qtype: str | None = None                 # single | multi | case | None(混合)
    source: str | None = None                # 教材名
    topic: str | None = None                 # 主题标签
    reuse_cached: bool = True


class SubmitRequest(BaseModel):
    questions: list = Field(min_length=1)
    answers: list = Field(min_length=1)      # [["B"], ["A","C"], ...]
    mode: str = "practice"                   # practice | exam | chapter
    topic: str | None = None


@router.post("/generate")
async def generate(req: GenerateRequest):
    """出题（三道闸：有据可依 / 置信度自检 / 缓存复用）。

    generate_questions 内含多次 LLM 网络调用（并行），必须放线程池执行，
    否则单 worker 下整个事件循环被阻塞，其它接口（文档列表等）全部排队。
    """
    if req.qtype and req.qtype not in ("single", "multi", "case"):
        raise HTTPException(400, "qtype 仅支持 single/multi/case")
    result = await asyncio.to_thread(
        engine.generate_questions,
        count=req.count,
        qtype=req.qtype,
        source=req.source,
        topic=req.topic,
        reuse_cached=req.reuse_cached,
    )
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/submit")
async def submit(req: SubmitRequest):
    """交卷判分：返回每题对错+解析，落库错题本/统计/记录。"""
    try:
        return grade(req.questions, req.answers, mode=req.mode, topic=req.topic)
    except AssertionError as e:
        raise HTTPException(400, str(e))


@router.get("/wrong-book")
async def wrong_book(include_resolved: bool = False):
    return {"total": len(store.get_wrong_questions(include_resolved)), "questions": store.get_wrong_questions(include_resolved)}


@router.get("/stats")
async def stats():
    attempts = store.get_attempts(limit=20)
    by_topic = store.topic_stats()
    total_answered = sum(t["attempts"] for t in by_topic)
    total_correct = sum(t["correct"] for t in by_topic)
    overall = round(total_correct / total_answered * 100) if total_answered else 0
    return {
        "overall_accuracy": overall,
        "total_answered": total_answered,
        "attempts": attempts,
        "by_topic": by_topic,
        "weak_topics": sorted([t for t in by_topic if t["attempts"] >= 3], key=lambda t: t["accuracy"])[:3],
    }


@router.get("/topics")
async def topics():
    return {"topics": engine.list_topics()}