"""账户体系：bcrypt 密码哈希 + JWT 签发/校验。"""
from __future__ import annotations

import time

import bcrypt
import jwt

from app.config import get_settings

_BCRYPT_ROUNDS = 12


def hash_password(password: str) -> str:
    """密码 → bcrypt 哈希（随机盐，12 轮）。"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """校验密码；哈希畸形时返回 False 而非抛异常。"""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_token(user_id: int, username: str) -> str:
    """签发 HS256 JWT（含过期时间，默认 7 天，可配 JWT_EXPIRES_DAYS）。"""
    settings = get_settings()
    now = int(time.time())
    payload = {
        "sub": str(user_id),
        "name": username,
        "iat": now,
        "exp": now + settings.jwt_expires_days * 86400,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> dict | None:
    """解析并校验 JWT；无效/过期/密钥不符返回 None。"""
    try:
        return jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        return None