---
name: feedback-lazy-import-avoid-auth-cycle
description: "src/middleware/auth.py 顶层**禁止** import src.auth.* 子模块 (Account / User), 必须在函数体内 lazy import. 根因: src/auth/__init__.py:3 eager-imports auth_account_router, 后者顶层 import middleware.auth → 循环"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 1dfcdecb-84bb-4149-9ad1-d1b332effa26
---

**src/middleware/auth.py 顶层禁止 import src.auth.* 子模块. Account / User 都必须在函数体内 lazy import.**

**Why:** 2026-06-14 web 端砍 x-admin-token 时, ingest/api.py 加 `from ..middleware.auth import CurrentUser, resolve_user`. 启动 uvicorn 报循环 import:

```
File "src/middleware/auth.py", line 14, in <module>
    from ..auth.account_models import Account
File "src/auth/__init__.py", line 3, in <module>
    from .auth_account_router import COOKIE_MAX_AGE, COOKIE_NAME, COOKIE_SECURE
File "src/auth/auth_account_router.py", line 12, in <module>
    from ..middleware.auth import CurrentUser, resolve_user
ImportError: cannot import name 'CurrentUser' from partially initialized module
```

**根因**:
1. `src/auth/__init__.py:3` eager-imports `auth_account_router` (re-export 常量给业务用)
2. `src/auth/auth_account_router.py:12` 顶层 `from ..middleware.auth import CurrentUser, resolve_user`
3. 任何 `src/auth/*` 子模块被 import → 触发 `__init__.py` → 触发 `auth_account_router` → 反向 import `middleware.auth` → 循环
4. **预先就有的隐患**, 之前 `middleware/auth.py` 顶层只 import `..auth.models.User` 也触发过, 之所以不爆, 是因为 `from ..auth.models import User` 这条路径**碰巧**某些情况下 Python 部分初始化的半成品模块**不**在第一次被立即用 — 但只要 ingest/api.py 真 import `resolve_user` 触发实际调用就爆

**修法**: `middleware/auth.py` 顶部**完全**不 import `src.auth.*` 任何子模块, 全部函数体内 lazy import:

```python
# middleware/auth.py 顶部
from ..storage.session import session_scope  # OK, 不在 src.auth.*

# 不要写:
# from ..auth.models import User
# from ..auth.account_models import Account

def _ensure_dev_user() -> None:
    from ..auth.models import User  # lazy
    ...

def resolve_user(request: Request) -> CurrentUser:
    ...
    from ..auth.models import User  # lazy
    with session_scope() as s:
        user = s.query(User).filter_by(public_token=user_token).first()
    ...

    from ..auth.account_models import Account  # lazy, 更里层
    with session_scope() as s:
        account = s.get(Account, user.account_id)
    ...
```

**How to apply:**
- 任何要 import `src.auth.*` 子模块的文件, 先**反向**检查: `src.auth.__init__.py` 是否 eager-imports 别的 module? 别的 module 是否 import 本文件?
- `src/auth/__init__.py:3` 这条 eager-import 是技术债, 长期修法是拆 `__init__.py` 不再 eager-import (业务直接 `from src.auth.auth_account_router import ...`), 但短期影响面大先不动
- 临时修法就是 lazy import 兜住

**反模式** (避免重蹈):
- ❌ `from ..auth.models import User` (顶层)
- ❌ `from ..auth.account_models import Account` (顶层)
- ❌ 任何 `from ..auth.<submodule> import ...` (顶层)
- ✅ 函数体内 lazy import
- ✅ TYPE_CHECKING 块下 import (只给 IDE 用, 运行时跳过)

**关联**:
- [[feedback-debug-search-before-loop]] — 循环 import 必先看错误链, 别瞎试位置
- [[feedback-no-shim-no-minimal-changes]] — lazy import 不是 shim, 是合理的 Python 模式
