"""/api/account/{profile,avatar,email,password,deletion} Pydantic schemas"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from .account_service import PASSWORD_MIN_LENGTH


class ProfileUpdate(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=50, description="昵称, 1-50 字符, trim 后校验")


class AccountOutExtended(BaseModel):
    """比 auth_account_router.AccountOut 多 3 字段: avatar_url, is_pending_deletion, deletion_expires_at"""

    id: int = Field(..., description="Account 主键")
    email: str = Field(..., description="账号邮箱")
    display_name: str | None = Field(None, description="显示名, 可空")
    role: str = Field(..., description="角色名")
    is_admin: bool = Field(..., description="派生: role in ('admin', 'super_admin')")
    avatar_url: str | None = Field(None, description="头像 URL (s3:// 或 local://)")
    is_pending_deletion: bool = Field(False, description="True = 处于注销宽限期 (7 天)")
    deletion_expires_at: datetime | None = Field(None, description="注销到期时间, pending=True 时填")


class EmailChangeRequest(BaseModel):
    new_email: EmailStr = Field(..., max_length=254, description="新邮箱, 格式合法, 不跟现有 email (排除自己) 重复")
    current_password: str = Field(..., min_length=1, description="当前密码 (二次确认, 防止 session 失窃)")


class EmailVerifyRequest(BaseModel):
    token: str = Field(..., min_length=1, description="request_email_change 返的 token, 7 天内有效")


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(..., min_length=1, description="当前密码 (二次确认, 防止 session 失窃后改密码)")
    new_password: str = Field(
        ...,
        min_length=PASSWORD_MIN_LENGTH,
        description=f"新密码 ≥ {PASSWORD_MIN_LENGTH} 字符 (env PASSWORD_MIN_LENGTH 控制)",
    )
    confirm: str = Field(
        ...,
        min_length=PASSWORD_MIN_LENGTH,
        description=f"新密码确认 (必须跟 new_password 字面相同, ≥ {PASSWORD_MIN_LENGTH} 字符)",
    )


class DeletionRequest(BaseModel):
    current_password: str = Field(..., min_length=1, description="当前密码 (二次确认)")
    confirm_text: str = Field(..., description="必须字面等于 '我要注销' (防误操作)")


class DeletionCancel(BaseModel):
    current_password: str = Field(..., min_length=1, description="当前密码 (二次确认)")
