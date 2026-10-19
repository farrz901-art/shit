# Pydantic 教程

> 📅 创建日期：2026-06-25
> 📁 项目代码引用：本教程以 `c:/doc/Code/rag` 仓库当前代码为准，所有引用标注 `file_path:line_number`
> 🏷️ 类别：L-语言/框架
> 🎯 读者：中高级 Python 工程师

---

## 目录

- [一、是什么 & 适用场景](#一是什么--适用场景)
- [二、安装 & 开发环境](#二安装--开发环境)
- [三、基础语法 & 类型系统](#三基础语法--类型系统)
- [四、核心概念](#四核心概念)
- [五、常用命令 & 工具链](#五常用命令--工具链)
- [六、项目集成点](#六项目集成点)
- [七、项目代码示例](#七项目代码示例)
- [八、项目没用到的能力 / 进阶方向](#八项目没用到的能力--进阶方向)
- [九、最佳实践 & 常见坑](#九最佳实践--常见坑)

---

## 一、是什么 & 适用场景

Pydantic 是 Python 生态最流行的数据验证库，2.0 版本（2023 年发布）用 Rust 重写核心，性能提升 5-50 倍。它用 Python 类型注解定义 schema，自动做数据验证 + 序列化 + 文档生成，是 FastAPI 的核心依赖。

**同类对比：**

| 库 | 定位 | 本项目选择理由 |
|------|------|----------------|
| **Pydantic v2** | 数据验证 + 序列化 | 本项目**主力**（`pydantic[email]>=2.13.4`） |
| **dataclass** | Python 标准数据类 | 轻量但无验证 |
| **attrs** | 类 dataclass | 第三方，跟 Pydantic 类似 |
| **marshmallow** | 老牌序列化 | 性能弱 |
| **msgspec** | 高性能序列化 | 新项目，生态小 |

**Pydantic 解决的核心问题**：
- **数据验证**：用类型注解自动验证
- **序列化**：`model_dump()` / `model_dump_json()`
- **反序列化**：`model_validate(dict)` / `model_validate_json(str)`
- **类型安全**：schema 即类型，IDE / mypy 全支持
- **OpenAPI 集成**：FastAPI 直接用 Pydantic 模型生成 API 文档

---

## 二、安装 & 开发环境

### 2.1 安装

```bash
# 项目已装 (pyproject.toml:39)
"pydantic[email]>=2.13.4",  # [email] 加 EmailStr 验证
```

### 2.2 版本

- Pydantic v2.13.4（项目锁版本）
- 完全重写核心（Rust），跟 v1 不兼容

### 2.3 健康检查

```python
from pydantic import __version__
print(__version__)  # 2.13.4
```

---

## 三、基础语法 & 类型系统

### 3.1 基本模型

```python
from pydantic import BaseModel, Field

class User(BaseModel):
    id: int
    name: str = Field(..., min_length=1, max_length=50)
    email: str
    age: int = Field(default=18, ge=0, le=150)

# 自动验证
user = User(id=1, name="Alice", email="alice@x.com")
# User(id=1, name='Alice', email='alice@x.com', age=18)

# 验证失败抛 ValidationError
try:
    User(id=1, name="", email="not-email")
except ValidationError as e:
    print(e.errors())
```

### 3.2 字段类型

```python
from typing import Optional, List, Dict, Tuple
from pydantic import BaseModel, EmailStr, HttpUrl, AnyUrl, Field
from datetime import datetime
from enum import Enum

class Role(str, Enum):
    USER = "user"
    ADMIN = "admin"

class User(BaseModel):
    name: str
    email: EmailStr                              # 邮箱验证
    website: HttpUrl                             # URL 验证
    role: Role = Role.USER                       # 枚举
    tags: List[str] = []                         # 列表
    metadata: Dict[str, str] = {}                # 字典
    birth: Optional[datetime] = None             # 可选
    score: float = Field(ge=0.0, le=100.0)      # 范围
    password: str = Field(min_length=8)          # 长度
```

### 3.3 嵌套模型

```python
class Address(BaseModel):
    street: str
    city: str

class Person(BaseModel):
    name: str
    addresses: List[Address]

person = Person(name="Alice", addresses=[{"street": "123 Main", "city": "SF"}])
# 自动嵌套验证
```

### 3.4 验证器

```python
from pydantic import field_validator, model_validator

class User(BaseModel):
    name: str
    password: str
    confirm: str

    @field_validator("name")
    @classmethod
    def name_no_admin(cls, v):
        if v.lower() == "admin":
            raise ValueError("'admin' is reserved")
        return v

    @model_validator(mode="after")
    def passwords_match(self):
        if self.password != self.confirm:
            raise ValueError("Passwords don't match")
        return self
```

### 3.5 序列化

```python
user = User(id=1, name="Alice", email="a@x.com")

# Python dict
user.model_dump()      # {'id': 1, 'name': 'Alice', 'email': 'a@x.com', ...}

# JSON str
user.model_dump_json()  # '{"id":1,"name":"Alice",...}'

# 排除字段
user.model_dump(exclude={"password"})
user.model_dump(include={"id", "name"})

# alias 模式（用于 API 兼容 snake_case ↔ camelCase）
class CamelModel(BaseModel):
    user_id: int = Field(alias="userId")

    model_config = ConfigDict(populate_by_name=True)

m = CamelModel.model_validate({"userId": 1})  # 用 alias 输入
m.model_dump(by_alias=True)  # {"userId": 1}
```

### 3.6 ConfigDict 配置

```python
from pydantic import BaseModel, ConfigDict

class Strict(BaseModel):
    model_config = ConfigDict(
        extra="forbid",        # 禁止额外字段
        frozen=True,           # 实例不可变
        str_strip_whitespace=True,
        str_to_lower=True,
        validate_assignment=True,
    )
```

### 3.7 反序列化

```python
# 从 dict
User.model_validate({"id": 1, "name": "Alice", "email": "a@x.com"})

# 从 JSON str
User.model_validate_json('{"id":1,"name":"Alice","email":"a@x.com"}')

# 部分字段（缺字段允许）
User.model_validate({"id": 1}, partial=True)
```

### 3.8 Field 参数

```python
class User(BaseModel):
    name: str = Field(
        ...,                              # ... = 必填
        description="用户姓名",
        examples=["Alice", "Bob"],
        min_length=1,
        max_length=50,
    )
    age: int = Field(default=18, ge=0, le=150, description="年龄")
    tags: List[str] = Field(default_factory=list)  # 默认空列表（可变默认值陷阱）
```

---

## 四、核心概念

### 4.1 BaseModel

所有 Pydantic 模型的基类。定义 schema + 验证逻辑 + 序列化方法。

### 4.2 Field（字段）

字段定义，类型 + 验证规则 + 默认值 + 文档。

### 4.3 Validator（验证器）

- `@field_validator`：单字段验证
- `@model_validator(mode="before")`：验证前预处理
- `@model_validator(mode="after")`：跨字段验证

### 4.4 TypeAdapter（类型适配器）

把任意类型包装成 Pydantic 风格：

```python
from pydantic import TypeAdapter

# 不需要 BaseModel
email_validator = TypeAdapter(EmailStr)
email_validator.validate_python("a@x.com")  # 'a@x.com'
email_validator.validate_python("not-email")  # ValidationError
```

### 4.5 Generic Model

```python
from pydantic import BaseModel
from typing import Generic, TypeVar

T = TypeVar("T")

class Response(BaseModel, Generic[T]):
    code: int
    data: T
    msg: str = ""

Response[User](code=0, data=user)  # 类型自动推断
```

---

## 五、常用命令 & 工具链

Pydantic 不需要单独命令。配合：

```bash
uv run pytest             # 测试
uv run pyright            # 类型检查
uv run ruff check --fix   # Lint
```

### Python REPL 测试

```bash
uv run python -c "from pydantic import BaseModel; class U(BaseModel): id:int; print(U(id=1))"
```

---

## 六、项目集成点

### 6.1 项目**主力**数据验证 + FastAPI

`pyproject.toml:39`：

```toml
"pydantic[email]>=2.13.4",
```

### 6.2 FastAPI 集成

Pydantic 模型是 FastAPI Request / Response 的官方类型：

```python
from fastapi import FastAPI
from pydantic import BaseModel

class CreateUserReq(BaseModel):
    email: str
    password: str

class UserResp(BaseModel):
    id: int
    email: str

app = FastAPI()

@app.post("/users", response_model=UserResp)
async def create_user(req: CreateUserReq):  # 自动验证请求体
    user = svc.create_user(req.email, req.password)
    return UserResp(id=user.id, email=user.email)  # 序列化响应
```

### 6.3 项目中 Pydantic 模型分布

- `src/middleware/auth.py:58-84` — `CurrentUser`
- `src/auth/` — Account / AccountSettings / 登录请求响应
- `src/chat/` — Conversation / Message / ChatRequest / ChatResponse
- `src/ingest/` — 文件上传 + 处理请求
- `src/eval/` — 评估 CSV 上传 + 评估结果
- `src/common/` — 共享 Schema
- 几乎所有 `router.py` 都有大量 Pydantic model

### 6.4 业务 enum 走 lookup

项目 `service/CLAUDE.md` 强制：**业务 enum 不用 Pydantic `Enum` 字段**，全部走 lookup 字典。

```python
# ❌ 错：硬编 enum
class ApprovalReview(BaseModel):
    status: Literal["pending", "approved", "rejected"]

# ✅ 对：业务 enum 走 lookup（详见 python/lookup.md）
class ApprovalReview(BaseModel):
    status: str  # 来自字典，不写死
```

唯一例外是 LLM 框架强制的 enum（如 OpenAI role）。

---

## 七、项目代码示例

### 7.1 项目 CurrentUser

`src/middleware/auth.py:58-84`：

```python
from pydantic import BaseModel, Field, EmailStr
from typing import Optional

class CurrentUser(BaseModel):
    id: int
    public_token: str = Field(..., min_length=32, max_length=64)
    role: str = "user"
    is_account: bool = False
    account_id: Optional[int] = None
    email: Optional[EmailStr] = None
    display_name: Optional[str] = None
    is_active: bool = True
    avatar_url: Optional[str] = None
    is_pending_deletion: bool = False

    @property
    def is_admin(self) -> bool:
        return self.role in ("admin", "super_admin")
```

### 7.2 项目请求 / 响应模型

```python
# src/chat/router.py:25
from pydantic import BaseModel, Field
from typing import Optional

class CreateConversationReq(BaseModel):
    title: Optional[str] = Field(default=None, max_length=200, description="对话标题")

class ConversationResp(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    messages: list["MessageResp"] = []

class MessageResp(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime

@router.post("/conversations", response_model=ConversationResp)
async def create_conv(req: CreateConversationReq, user: CurrentUser = Depends(...)):
    conv = svc.create_conversation(user_id=user.id, title=req.title)
    return ConversationResp(...)
```

### 7.3 Field description 进 OpenAPI

```python
from pydantic import BaseModel, Field

class DecodeRequest(BaseModel):
    order_code: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="产品订货号 (e.g. 'AB-1234-CD')",
        examples=["AB-1234-CD"],
    )
```

效果：FastAPI 自动渲染到 Swagger UI。

### 7.4 自定义验证器

```python
from pydantic import BaseModel, field_validator, model_validator

class PasswordChangeReq(BaseModel):
    old_password: str = Field(min_length=8)
    new_password: str = Field(min_length=8)
    confirm: str = Field(min_length=8)

    @field_validator("new_password")
    @classmethod
    def password_complexity(cls, v):
        if not any(c.isupper() for c in v):
            raise ValueError("must contain uppercase")
        if not any(c.isdigit() for c in v):
            raise ValueError("must contain digit")
        return v

    @model_validator(mode="after")
    def passwords_match(self):
        if self.new_password != self.confirm:
            raise ValueError("confirm doesn't match new_password")
        return self
```

### 7.5 SQLAlchemy ↔ Pydantic 互转

```python
from src.db.models.auth import User as UserORM
from pydantic import BaseModel

class UserResp(BaseModel):
    id: int
    email: str
    display_name: str

    @classmethod
    def from_orm(cls, u: UserORM) -> "UserResp":
        return cls(id=u.id, email=u.email, display_name=u.display_name)

# ORM → Pydantic
user_orm = session.get(User, 1)
user_resp = UserResp.from_orm(user_orm)

# Pydantic → dict（写库）
user_dict = user_resp.model_dump()
```

### 7.6 JSON Schema（OpenAPI）

```python
from src.auth.account_settings_router import AccountUpdateReq

schema = AccountUpdateReq.model_json_schema()
# 输出 OpenAPI 兼容 JSON Schema
# FastAPI 内部用这个生成 /openapi.json
```

### 7.7 测试断言

```python
import pytest
from pydantic import ValidationError
from src.middleware.auth import CurrentUser

def test_current_user_validation():
    # 合法
    u = CurrentUser(id=1, public_token="abc123" * 5)
    assert u.is_admin is False

    # 非法（短 token）
    with pytest.raises(ValidationError):
        CurrentUser(id=1, public_token="short")
```

---

## 八、项目没用到的能力 / 进阶方向

以下 Pydantic 2 能力项目当前未充分使用（**待评估**）：

| 能力 | 用途 | 集成建议 |
|------|------|----------|
| **TypeAdapter** | 验证非 BaseModel 类型 | 简单场景避免建 model |
| **Discriminated Union** | 多态事件 | SSE / WebSocket |
| **Generic[T]** | 泛型响应 | `Response[T]` 包装 |
| **Functional Validator** | 函数式 validator | 简单字段 |
| **Computed Field** | 计算字段（`@computed_field`）| 全名 = first + last |
| **Custom Types** | 自定义标量 | 业务 enum 字典化 |
| **JSON Schema Generation** | 自定义 OpenAPI | 暴露给前端 codegen |
| **Strict Mode** | `extra="forbid"` | API 严格性 |
| **Alias Generator** | `to_camel` 自动转换 | snake_case ↔ camelCase |

**建议关注**：Alias Generator 让后端 snake_case Pydantic 模型自动生成 camelCase OpenAPI schema，前端 fetch 自动转换。

---

## 九、最佳实践 & 常见坑

### 项目风格指南（项目 CLAUDE.md 强制）

1. **Pydantic model 加 `Field(description=...)`**：字段说明进 OpenAPI
2. **每个 router 加 docstring**：FastAPI 渲染成接口说明
3. **`@router.post(..., response_model=..., summary="...")`**：summary 是接口标题
4. **业务 enum 走 lookup**：不要用 Pydantic `Enum` / `Literal`
5. **4xx 抛 `HTTPException`**：5xx 让全局 handler 接
6. **永远不返 stacktrace 给前端**

### 最佳实践

1. **不要硬编默认值**：

```python
# ❌ 错：可变默认值陷阱
class Bad(BaseModel):
    tags: List[str] = []  # 所有实例共享同一个 list

# ✅ 对
tags: List[str] = Field(default_factory=list)
```

2. **TypeAdapter 替代简单校验**：

```python
from pydantic import TypeAdapter, EmailStr

email_check = TypeAdapter(EmailStr)
email_check.validate_python("a@x.com")  # 不需要建 BaseModel
```

3. **Optional → None**：

```python
from typing import Optional

name: Optional[str] = None  # str | None
# vs
name: str | None = None  # 3.10+
```

4. **配置 ConfigDict**：

```python
from pydantic import ConfigDict

class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
```

5. **嵌套模型用 TypeAdapter 复用**：

```python
AddressSchema = TypeAdapter(Address)

class Person(BaseModel):
    addresses: list[Address]

# 单独验证
addr = AddressSchema.validate_python({"street": "...", "city": "..."})
```

### 常见坑

1. **Pydantic v1 → v2 breaking**：项目用 v2，但很多老教程是 v1

```python
# ❌ v1
user.dict()          # ❌
user.json()          # ❌
class Config:        # ❌
    ...

# ✅ v2
user.model_dump()
user.model_dump_json()
model_config = ConfigDict(...)
```

2. **`Optional` vs 必填 + 默认值**：

```python
# ❌ 错：name: str = None  # str | None 但 Pydantic 不验证
# ✅ 对
name: Optional[str] = None  # 显式 Optional
```

3. **`email` 验证失败**：

```bash
# ❌ 错：写 email 字段但用 str 类型
email: str  # 接受任意字符串

# ✅ 对：EmailStr 类型
email: EmailStr  # Pydantic 验证邮箱格式
# 需装 pydantic[email]
```

4. **`field_validator` 必须 `@classmethod`**：

```python
@field_validator("name")
@classmethod
def check(cls, v):  # cls 不是 self
    ...
```

5. **递归模型用 `from __future__ import annotations`**：

```python
from __future__ import annotations

class Tree(BaseModel):
    children: list[Tree] = []  # 前向引用
```

6. **FastAPI Pydantic model 报错格式**：

```python
# 422 Unprocessable Entity
{
  "detail": [
    {"loc": ["body", "email"], "msg": "value is not a valid email address", "type": "value_error.email"}
  ]
}
```

7. **`model_dump()` 默认不 dump 嵌套字段为 dict**：

```python
class A(BaseModel):
    class B(BaseModel):
        x: int
    b: B

a = A(b={"x": 1})
a.model_dump()  # {"b": {"x": 1}}  # 默认递归 dump

# 自定义序列化
a.model_dump(mode="json")  # 序列化为 JSON 兼容类型
```

8. **测试**：

```python
# 验证失败用 pytest.raises
with pytest.raises(ValidationError) as exc_info:
    User(name="")
assert "name" in str(exc_info.value)
```

### Pydantic 性能

- v2 比 v1 快 5-50x（Rust 核心）
- 大模型（100+ 字段）`model_dump()` 慢，可考虑 `model_dump_json()` 直接
- 验证路径尽量短：`Field(...)` 内置 > `@field_validator`
- `validate_assignment=True` 会大幅拖慢每次赋值，生产慎用

---

## 📚 参考

- [Pydantic 官方文档](https://docs.pydantic.dev/latest/)
- [Pydantic v2 迁移指南](https://docs.pydantic.dev/latest/migration/)
- [Pydantic + FastAPI](https://fastapi.tiangolo.com/tutorial/body/)
- [Pydantic 性能优化](https://docs.pydantic.dev/latest/concepts/performance/)
- [Pydantic GitHub](https://github.com/pydantic/pydantic)
- [项目 service/CLAUDE.md §测试规范](../../packages/service/CLAUDE.md)

---

**状态：** ✅ 已完成

**最后更新：** 2026-06-25