"""FastAPI 应用入口。"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.router import router as auth_router
from app.config import get_registry, get_settings
from app.exam.router import router as exam_router
from app.routers.api import router as api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时校验配置与模型注册表可加载（不校验 Key 是否有效，仅在调用时惰性报错）
    settings = get_settings()
    if not settings.jwt_secret:
        raise RuntimeError("缺少 JWT_SECRET：账户体系需要它签发登录凭证（生成: openssl rand -hex 32）")
    app.state.settings = settings
    app.state.registry = get_registry()

    # 系统管理员引导：.env 配置了 ADMIN_PASSWORD 且库里尚无 admin 时自动创建（is_admin=1）。
    # 未配置 → 跳过（health/正常运行不受影响，仅上传/删除保持受保护）。
    if settings.admin_password:
        from app.auth.security import hash_password
        from app.exam import store
        admin = store.ensure_admin(hash_password(settings.admin_password))
        print(f"[auth] 管理员就绪: {admin['username']} (id={admin['id']})")
    yield


app = FastAPI(
    title="造口伤口失禁护理 AI 学习助手",
    description="基于教材的 RAG 精准问答（FastAPI + Chroma + 多模型）",
    version="0.1.0",
    lifespan=lifespan,
)

# 前端（uni-app H5 / 开发期 Vite）跨域放开；生产环境由 Nginx 同域反代。
# allow_credentials 必须为 False：它与 allow_origins=["*"] 不能同时生效
# （浏览器会拒绝通配源上的凭据请求）。本应用用 Authorization: Bearer 头
# 携带登录态，而非 Cookie，因此不需要 credentials。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    """健康检查：返回服务状态、已配置模型清单（不含任何 Key）。"""
    registry = get_registry()
    return {
        "status": "ok",
        "service": "wound-care-assistant",
        "models": {
            "chat": [
                {"id": mid, "name": registry.chat_model_info(mid)["name"]}
                for mid in registry.chat_model_ids()
            ],
            "embedding": [
                {"id": eid, "name": registry.embedding_model_info(eid)["name"]}
                for eid in registry.embedding_model_ids()
            ],
        },
        "default_model": get_settings().default_model,
        "default_embedding": get_settings().embedding_model_id,
        "top_k": get_settings().default_top_k,
    }


# 业务路由
app.include_router(api_router)
app.include_router(auth_router)
app.include_router(exam_router)