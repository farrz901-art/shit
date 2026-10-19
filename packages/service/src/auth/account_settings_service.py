"""账号设置业务逻辑: profile / avatar / email / password / deletion / purge

Phase 5 进度: 含 profile / avatar / email / password / deletion / purge.
"""

from __future__ import annotations

import io
import os
import secrets
from contextlib import nullcontext
from datetime import datetime, timedelta

from loguru import logger
from PIL import Image

from ..storage import get_object_store
from ..utils.timezone import HKT
from .account_models import Account, DeletionRestore, EmailChange
from .account_service import PASSWORD_MIN_LENGTH, generate_token, hash_password, verify_password
from .models import User

# --- 常量 (T2.1 只需 avatar 相关) ---
AVATAR_MAX_SIZE_MB = 2
AVATAR_OUTPUT_SIZE = 256
DELETION_GRACE_DAYS = int(os.getenv("DELETION_GRACE_DAYS", "7"))  # 注销宽限期 (T2.4 用)
EMAIL_CHANGE_EXPIRES_DAYS = int(os.getenv("EMAIL_CHANGE_EXPIRES_DAYS", "7"))  # 邮箱改 token 寿命
DELETION_RESTORE_EXPIRES_DAYS = int(os.getenv("DELETION_RESTORE_EXPIRES_DAYS", "7"))  # 注销撤销 token 寿命


# --- profile ---
def update_profile(session, account: Account, *, display_name: str) -> None:
    """改 display_name. 已 trim + 长度校验, 1-50 字符."""
    name = display_name.strip()
    if not 1 <= len(name) <= 50:
        raise ValueError(f"display_name must be 1-50 characters, got {len(name)}")
    account.display_name = name
    session.flush()


def delete_avatar(session, account: Account) -> None:
    """清空 avatar_url 字段, 不删 ObjectStore 文件 (保留历史 + 避免 race)."""
    account.avatar_url = None
    session.flush()


# --- avatar ---
def process_avatar_upload(file_bytes: bytes) -> bytes:
    """PIL 校验 + resize 256x256 + WebP 转码. 返转码后 bytes."""
    if len(file_bytes) > AVATAR_MAX_SIZE_MB * 1024 * 1024:
        raise ValueError(f"avatar too large: >{AVATAR_MAX_SIZE_MB}MB")
    try:
        img = Image.open(io.BytesIO(file_bytes))
        img.verify()  # 防 bomb, 验证后 img 不可用
        img = Image.open(io.BytesIO(file_bytes)).convert("RGBA")
    except (Image.UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError) as e:
        raise ValueError(f"invalid image: {e}") from e
    img = img.resize(
        (AVATAR_OUTPUT_SIZE, AVATAR_OUTPUT_SIZE), Image.Resampling.LANCZOS
    )  # Pillow 10+ Resampling enum; older stubs unknown
    buf = io.BytesIO()
    img.save(buf, "WEBP", quality=85)
    return buf.getvalue()


def _pick_avatar_uri(backend: str, account_id: int, content_hash: str) -> str:
    """按 backend 选 URI scheme + bucket/key. backend = 'local' | 'minio'."""
    key = f"avatars/{account_id}.{content_hash}.webp"
    if backend == "minio":
        bucket = os.getenv("OBJECT_STORE_S3_BUCKET", "rag-avatars")
        return f"s3://{bucket}/{key}"
    # local: 走 local://key
    return f"local://{key}"


def store_avatar(session, account: Account, file_bytes: bytes) -> str:
    """PIL 处理 + ObjectStore.put_bytes + 写 avatar_url. 返 URI.

    URI scheme 跟随当前 ObjectStore backend (OBJECT_STORE_BACKEND env):
    - backend=minio → s3://<bucket>/avatars/<id>.<hash>.webp
    - backend=local → local://avatars/<id>.<hash>.webp
    """
    webp = process_avatar_upload(file_bytes)
    store = get_object_store()
    backend = store.backend_name()  # 'local' / 'minio'
    content_hash = secrets.token_hex(8)  # 8 字节足够 (避覆盖, 防 race)
    uri = _pick_avatar_uri(backend, account.id, content_hash)
    store.put_bytes(uri, webp, mime="image/webp")
    account.avatar_url = uri
    session.flush()
    return uri


# --- email change ---
def request_email_change(session, account: Account, new_email: str, current_password: str) -> dict:
    """申请改邮箱. 校验 current_password, 检查 new_email 跟现有 email 不重复 (排除自己)."""
    if not verify_password(current_password, account.password_hash):
        raise ValueError("invalid current password")
    # 查重 (排除当前 account)
    existing = session.query(Account).filter(Account.email == new_email, Account.id != account.id).first()
    if existing is not None:
        raise ValueError("email already in use")
    # 创 EmailChange token
    token = generate_token()
    expires_at = datetime.now(HKT) + timedelta(days=EMAIL_CHANGE_EXPIRES_DAYS)
    session.add(
        EmailChange(
            account_id=account.id,
            new_email=new_email,
            token=token,
            expires_at=expires_at,
            created_at=datetime.now(HKT),
        )
    )
    session.flush()
    return {
        "new_email": new_email,
        "expires_at": expires_at,
        "verification_url": f"/verify-email?token={token}",  # dev: 返 URL; prod: 应发邮件
    }


def verify_email_change(session, token: str) -> dict:
    """验证 token → 切换 email + 标 used_at. 兼容 naive/aware datetime.

    CON-003 修复:
    - 加 SELECT ... FOR UPDATE 锁 email_change 行 + account 行, 防 TOCTOU.
    - 锁内二次校验 used_at, 另一请求先锁先改则抛 invalid.
    - account 行锁配合防并发改 email / 删 account.
    """
    # 锁 email_change 行, 阻塞等待其他并发事务释放
    change = session.query(EmailChange).filter_by(token=token).with_for_update().one_or_none()
    if change is None or change.used_at is not None:
        raise ValueError("invalid or used token")
    # 兼容 naive/aware
    if change.expires_at.tzinfo is None:
        expires_aware = change.expires_at.replace(tzinfo=HKT)
    else:
        expires_aware = change.expires_at.astimezone(HKT)
    if expires_aware < datetime.now(HKT):
        raise ValueError("token expired")
    # 二次校验 new_email 仍可用 (race)
    dup = session.query(Account).filter(Account.email == change.new_email, Account.id != change.account_id).first()
    if dup is not None:
        raise ValueError("email already in use")
    # 锁 account 行 (防并发修改 account.email 或删除)
    account = session.query(Account).filter(Account.id == change.account_id).with_for_update().one_or_none()
    if account is None:
        raise ValueError("account not found")
    account.email = change.new_email
    change.used_at = datetime.now(HKT)
    session.flush()
    return {"email": account.email}


# --- password ---
def change_password(session, account: Account, current_password: str, new_password: str, confirm: str) -> None:
    """改密码. 校验 current + new == confirm + new ≥ PASSWORD_MIN_LENGTH. 不踢出当前 session."""
    if not verify_password(current_password, account.password_hash):
        raise ValueError("invalid current password")
    if new_password != confirm:
        raise ValueError("passwords do not match")
    if len(new_password) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"password must be at least {PASSWORD_MIN_LENGTH} characters")
    account.password_hash = hash_password(new_password)
    session.flush()


# --- deletion ---
def request_deletion(session, account: Account, current_password: str, confirm_text: str) -> dict:
    """申请注销. 校验密码 + confirm_text 字面匹配. 立即 is_active=False, 创 restore token (7 天有效)."""
    if not verify_password(current_password, account.password_hash):
        raise ValueError("invalid current password")
    if confirm_text != "我要注销":
        raise ValueError("confirm text must be exactly '我要注销'")
    if account.is_pending_deletion:
        raise ValueError("account already pending deletion")
    now = datetime.now(HKT)
    account.is_active = False
    account.deletion_requested_at = now
    token = generate_token()
    expires_at = now + timedelta(days=DELETION_RESTORE_EXPIRES_DAYS)
    session.add(
        DeletionRestore(
            account_id=account.id,
            token=token,
            expires_at=expires_at,
            created_at=now,
        )
    )
    session.flush()
    return {
        "deletion_requested_at": now,
        "expires_at": expires_at,
        "restore_url": f"/account/restore?token={token}",
    }


def cancel_deletion(session, account: Account, current_password: str) -> None:
    """撤销注销. 校验密码 + 必须在 pending 状态. 重置 is_active=True, 标 DeletionRestore.used_at.

    CON-002 修复:
    - 加 SELECT ... FOR UPDATE 锁 account 行, 防止跟 purge_pending_deletions cron 并发:
      cron 已 SELECT 走待删列表 (但不持锁) → cancel 进来不加锁 → 双方都改 → 状态错乱.
    - 锁内重读 + 二次校验防 TOCTOU:
      * cron 持锁中跑完 + commit + 删 account → 我们 SELECT 锁后 one_or_none() 返 None → 拒绝 (race 被 cron 抢走).
      * 另一个 cancel 请求先持锁, 改完 commit → 我们 SELECT 锁后 is_pending_deletion=False → 拒绝 (幂等).
    - 锁内 batch 标 DeletionRestore.used_at, 保证原子 (cancel + cron 不能同时改 used_at).
    """
    if not account.is_pending_deletion:
        raise ValueError("account is not pending deletion")
    if not verify_password(current_password, account.password_hash):
        raise ValueError("invalid current password")

    # 锁住 account 行 (防 cron 同时跑 purge 决定删这行)
    # 注: 传入的 account 可能是过期 view, 必须 refresh + 加锁, 否则持锁无效
    locked_account = session.query(Account).filter(Account.id == account.id).with_for_update().one_or_none()
    if locked_account is None:
        # cron 已 DELETE 完这行 (race: 我们等锁 → cron 持锁 → commit → 释放 → 我们再查 → 没了)
        raise ValueError("account not found (concurrent deletion)")
    if not locked_account.is_pending_deletion:
        # 另一个 cancel 已抢锁改完 (幂等拒绝) / 状态被外部改了
        raise ValueError("account is not pending deletion")

    locked_account.is_active = True
    locked_account.deletion_requested_at = None
    # 锁内 batch 标 DeletionRestore.used_at (幂等: used_at IS NULL 的全部 mark now)
    for dr in session.query(DeletionRestore).filter_by(account_id=locked_account.id, used_at=None).all():
        dr.used_at = datetime.now(HKT)
    session.flush()


def get_deletion_status(account: Account) -> dict:
    """查当前注销状态. 不返 restore_token (防泄漏)."""
    if not account.is_pending_deletion or account.deletion_requested_at is None:
        return {"pending": False}
    requested_at = account.deletion_requested_at
    return {
        "pending": True,
        "deletion_requested_at": requested_at,
        "expires_at": requested_at + timedelta(days=DELETION_GRACE_DAYS),
    }


# --- purge (T5.1 APScheduler 每天 03:00 跑) ---
def purge_pending_deletions(session=None) -> int:
    """清理到期的 pending_deletion 账号. 接受可选 session (测试用). 返清理数.

    业务规则:
    - 筛选 deletion_requested_at 不为空 + 早于 (now - DELETION_GRACE_DAYS) 的 Account
    - 对每条记录: 关联 User 解绑 account_id + 重置 public_token + 匿名化 display_name (保留 user.id, 关联 chat/memory/share 不能丢)
    - 删 Account (CASCADE 自动删 EmailChange + DeletionRestore + PasswordReset)

    CON-002 修复:
    - 加 SELECT ... FOR UPDATE SKIP LOCKED 防跟 cancel_deletion 并发:
      cancel 持 account 行锁 → 跳过这行 → 不删 (用户已撤销).
      多个 cron 实例并发跑也安全 (PG SKIP LOCKED 跳过被锁行, 不会被两个 cron 同时处理).
    """
    cutoff = datetime.now(HKT) - timedelta(days=DELETION_GRACE_DAYS)
    owns_session = session is None
    if owns_session:
        # 生产路径: 自管 session (commit on success, rollback on exception)
        # 推迟副作用: session_scope 触发 src.storage 完整装载 (engine + ORM Base),
        # auth service 单元测试期不需要付出
        from ..storage.session import session_scope  # noqa: E402

        session_ctx = session_scope()
    else:
        # 测试路径: 用注入的 mock session, 避免开真实连接
        session_ctx = nullcontext(session)
    with session_ctx as s:
        victims = (
            s.query(Account)
            .filter(Account.deletion_requested_at.isnot(None))
            .filter(Account.deletion_requested_at < cutoff)
            .with_for_update(skip_locked=True)
            .all()
        )
        count = 0
        for account in victims:
            # 二次校验: 锁内确认 is_pending_deletion 仍为 True + is_active 仍 False
            # (防 cancel 在 cron 拉 SELECT 时改完行, 但 SELECT FOR UPDATE 锁住了, 不会;
            #  此处防御性 check, 让 cron 重跑时也不会被 cancel 干扰)
            if account.is_pending_deletion and not account.is_active:
                # 匿名化关联 User (CASCADE 删 EmailChange / DeletionRestore / PasswordReset 随 Account.delete 触发)
                _anonymize_user(s, account.id)
                s.delete(account)
                count += 1
        if count > 0:
            s.flush()
    if owns_session:
        logger.info("purge_pending_deletions 清理了 {} 个到期账号", count)
    return count


def _anonymize_user(session, account_id: int) -> None:
    """匿名化 User 行: 重置 public_token + display_name + 解绑 account_id.

    保留 user.id (关联 chat/memory/share 不能丢, 那些表是按 user_id 引用而非 account_id).
    """
    user = session.query(User).filter_by(account_id=account_id).first()
    if user is None:
        # 账号可能没有 user 关联 (老匿名账号场景), 静默返回
        return
    user.account_id = None  # 解绑, 避免 FK CASCADE 把 User 一起删
    user.public_token = secrets.token_hex(32)  # 重置, 旧 share link 失效
    user.display_name = f"已注销用户 #{user.id}"  # 匿名化
