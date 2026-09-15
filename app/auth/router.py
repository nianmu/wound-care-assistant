"""账户体系 API：/api/auth/register /login /me。"""
from __future__ import annotations

import re
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.auth.deps import get_current_user
from app.auth.security import create_token, hash_password, verify_password
from app.config import get_settings
from app.exam import store

router = APIRouter(prefix="/api/auth")

_USERNAME_RE = re.compile(r"^[a-z0-9_]{3,32}$")

# 登录限速（进程级，单 worker 够用）：key → (失败次数, 锁定截止时间戳)
_FAIL_COUNT: dict[str, tuple[int, float]] = {}
MAX_FAILS = 5
LOCK_SECONDS = 300


class RegisterRequest(BaseModel):
    # 长度规则在端点内统一校验（返回 400）；字段层只做基本边界防超长
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=64)
    display_name: str | None = Field(default=None, max_length=20)
    invite_code: str | None = Field(default=None, max_length=64)  # 注册邀请码（防外人随意注册）


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=32)
    password: str = Field(min_length=1, max_length=64)


def _public_user(u: dict) -> dict:
    """去敏：绝不返回任何哈希字段。is_admin 供前端显示/隐藏管理操作。"""
    return {
        "id": u["id"],
        "username": u["username"],
        "display_name": u.get("display_name"),
        "is_admin": bool(u.get("is_admin")),
    }


def _validate_password(password: str) -> None:
    if len(password) < 8:
        raise HTTPException(400, "密码至少 8 位")
    if not (any(c.isalpha() for c in password) and any(c.isdigit() for c in password)):
        raise HTTPException(400, "密码需同时包含字母和数字")


def _check_lock(key: str) -> None:
    entry = _FAIL_COUNT.get(key)
    if entry and entry[1] > time.time():
        remain = int((entry[1] - time.time()) / 60) + 1
        raise HTTPException(429, f"尝试次数过多，请 {remain} 分钟后再试")


def _record_fail(key: str) -> None:
    count, _until = _FAIL_COUNT.get(key, (0, 0.0))
    if count + 1 >= MAX_FAILS:
        _FAIL_COUNT[key] = (0, time.time() + LOCK_SECONDS)
    else:
        _FAIL_COUNT[key] = (count + 1, 0.0)


def _clear_fails(*keys: str) -> None:
    for k in keys:
        _FAIL_COUNT.pop(k, None)


@router.post("/register")
async def register(req: RegisterRequest, request: Request):
    """注册即登录。首个用户自动成为"主人"，接管历史（user_id=0）数据。

    注册门槛（防外人随意注册）：`REGISTER_INVITE_CODE` 未配置 = 禁止注册；
    配置了则必须提交匹配的邀请码，否则 403。
    """
    # 邀请码闸（在一切校验之前）
    expected = get_settings().register_invite_code
    if not expected:
        raise HTTPException(403, "暂未开放注册，请联系管理员")
    if not req.invite_code or req.invite_code.strip() != expected:
        raise HTTPException(403, "注册邀请码错误")

    username = req.username.strip().lower()
    if not _USERNAME_RE.match(username):
        raise HTTPException(400, "用户名需 3~32 位小写字母/数字/下划线")
    _validate_password(req.password)
    if store.get_user_by_username(username):
        raise HTTPException(400, "用户名已存在")

    display_name = (req.display_name or "").strip() or username
    # "首个用户"按普通用户计：系统管理员（is_admin=1）自动引导创建，不算首个用户
    is_first = store.normal_user_count() == 0
    try:
        uid = store.create_user(username, hash_password(req.password), display_name)
    except ValueError as e:
        raise HTTPException(400, str(e))

    migrated = store.migrate_legacy_to_user(uid) if is_first else None
    user = store.get_user_by_id(uid)
    return {
        "token": create_token(uid, username),
        "user": _public_user(user),
        "migrated": migrated,
        "is_first": is_first,
    }


@router.post("/login")
async def login(req: LoginRequest, request: Request):
    """登录：失败 5 次（按用户名+IP）锁定 5 分钟。"""
    username = req.username.strip().lower()
    key_u, key_i = f"u:{username}", f"ip:{request.client.host}"
    _check_lock(key_u)
    _check_lock(key_i)

    user = store.get_user_by_username(username)
    if not user or not verify_password(req.password, user["password_hash"]):
        _record_fail(key_u)
        _record_fail(key_i)
        raise HTTPException(401, "用户名或密码错误")

    _clear_fails(key_u, key_i)
    return {
        "token": create_token(user["id"], user["username"]),
        "user": _public_user(user),
    }


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    """当前登录用户（token 校验）；用于前端启动时确认登录态。"""
    return {"user": _public_user(user)}