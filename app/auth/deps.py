"""FastAPI 依赖：从 Authorization: Bearer 头解析当前用户。"""
from __future__ import annotations

from fastapi import Depends, Header, HTTPException

from app.auth.security import decode_token
from app.exam import store


def get_current_user(authorization: str | None = Header(default=None)) -> dict:
    """校验 Bearer token → 返回 {id, username, display_name, is_admin}；失败抛 401。"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "未登录，请先登录")
    payload = decode_token(authorization[7:].strip())
    if not payload:
        raise HTTPException(401, "登录已过期，请重新登录")
    try:
        uid = int(payload["sub"])
    except (KeyError, ValueError):
        raise HTTPException(401, "登录凭证无效")
    user = store.get_user_by_id(uid)
    if not user:
        raise HTTPException(401, "用户不存在")
    return user


def get_current_admin(user: dict = Depends(get_current_user)) -> dict:
    """管理员专属：is_admin=1 才放行，否则 403（高危操作：上传/删除教材）。"""
    if not user.get("is_admin"):
        raise HTTPException(403, "仅系统管理员可执行此操作")
    return user