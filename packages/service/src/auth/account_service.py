"""账号系统业务逻辑: 密码 hash, 登录, invite, reset"""

from __future__ import annotations

import os
import secrets

import bcrypt

# --- 密码 ---

PASSWORD_MIN_LENGTH = int(os.getenv("PASSWORD_MIN_LENGTH", "8"))
BCRYPT_ROUNDS = int(os.getenv("PASSWORD_BCRYPT_ROUNDS", "12"))


def hash_password(plain: str) -> str:
    """bcrypt hash (12 rounds 默认), 入库前必过"""
    if len(plain) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"password must be at least {PASSWORD_MIN_LENGTH} characters")
    salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    return bcrypt.hashpw(plain.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """bcrypt verify. 错密码/坏 hash → False (不抛)"""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError, TypeError:
        return False


# --- Token 生成 (invite / reset) ---


def generate_token() -> str:
    """32 字节 hex token (64 字符)"""
    return secrets.token_hex(32)
