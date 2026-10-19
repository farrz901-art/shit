# Alembic 教程

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

Alembic 是 SQLAlchemy 团队出品的数据库 schema 迁移工具。它通过 Python 脚本（不是 SQL 文件）记录每次 schema 变更，能自动生成 diff、回滚到任意版本，是 Python 生态事实标准的迁移工具。

**同类对比：**

| 工具 | 定位 | 本项目选择理由 |
|------|------|----------------|
| **Alembic** | SQLAlchemy 官方迁移 | 本项目**主力**，跟 SQLAlchemy 2.0 集成 |
| **Django Migrations** | Django ORM 绑定 | 项目不用 Django |
| **yoyo-migrations** | 轻量级 SQL 迁移 | 生态小 |
| **sqlx / Flyway** | Java 生态迁移 | 不跨语言 |
| **手写 SQL** | 简单项目 | 没有版本控制 / 回滚 |

**Alembic 解决的核心问题**：
- **版本控制**：每次 schema 变更是一个可回滚的"版本"
- **自动生成**：从 ORM model diff 自动生成迁移脚本
- **多环境同步**：dev / staging / prod 拉同一套脚本，顺序一致
- **零停机迁移**：支持在线 / 离线 / 事务模式

---

## 二、安装 & 开发环境

### 2.1 安装

```bash
# 项目已装 (pyproject.toml:1)
"alembic>=1.18.4",  # SQLAlchemy 数据库 schema 迁移工具
```

### 2.2 项目配置

```
packages/service/
├── alembic.ini          # Alembic 主配置
├── alembic/
│   ├── env.py           # 启动脚本（连接 DB + 加载 model metadata）
│   ├── script.py.mako   # 迁移脚本模板
│   └── versions/        # 所有迁移文件
│       ├── 2026_01_15_initial.py
│       ├── 2026_02_10_add_lookup.py
│       └── ...
```

### 2.3 alembic.ini 关键配置

```ini
[alembic]
script_location = alembic
prepend_sys_path = .
version_path_separator = os

# 异步模式（项目用 asyncpg）
[post_write_hooks]
# ...

sqlalchemy.url =  # 留空，env.py 里动态设置
```

### 2.4 env.py 关键配置

`alembic/env.py`（项目风格）：

```python
import asyncio
from logging.config import fileConfig
from alembic import context
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy import pool
from src.db.base import Base
from src.db.models import auth, chat, approvals, permissions, lookups  # 全部 import
from src.common.db_url import get_rag_db_url

config = context.config
config.set_main_option("sqlalchemy.url", get_rag_db_url())

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def run_migrations_offline() -> None:
    """离线模式：生成 SQL 脚本而不连接 DB"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url, target_metadata=target_metadata,
        literal_binds=True, dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()

async def run_async_migrations() -> None:
    """异步模式（项目用）"""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.", poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()

def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

---

## 三、基础语法 & 类型系统

### 3.1 迁移文件结构

`alembic/versions/2026_05_15_add_avatar_url.py`：

```python
"""add avatar_url to users

Revision ID: 1a2b3c4d5e6f
Revises: 9z8y7x6w5v4u
Create Date: 2026-05-15 10:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "1a2b3c4d5e6f"
down_revision: Union[str, None] = "9z8y7x6w5v4u"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column("users", sa.Column("avatar_url", sa.String(255), nullable=True))

def downgrade() -> None:
    op.drop_column("users", "avatar_url")
```

### 3.2 常用 op 操作

```python
# 列
op.add_column("users", sa.Column("avatar_url", sa.String(255)))
op.drop_column("users", "avatar_url")
op.alter_column("users", "display_name", new_column_name="name")
op.alter_column("users", "is_active", type_=sa.Boolean(), nullable=False, default=True)

# 索引
op.create_index("ix_users_email", "users", ["email"], unique=True)
op.drop_index("ix_users_email", "table_name="users")

# 约束
op.create_unique_constraint("uq_users_email", "users", ["email"])
op.create_foreign_key("fk_posts_user", "posts", "users", ["user_id"], ["id"])
op.create_check_constraint("ck_users_age", "users", "age >= 0")

# 表
op.create_table("audit_log", sa.Column("id", sa.Integer, primary_key=True), ...)
op.drop_table("audit_log")
op.rename_table("users", "accounts")

# 枚举
op.execute("CREATE TYPE user_role AS ENUM ('user', 'admin', 'super_admin')")
op.execute("ALTER TABLE users ALTER COLUMN role TYPE user_role USING role::user_role")
op.execute("DROP TYPE user_role")

# JSONB
op.add_column("approvals", sa.Column("payload", postgresql.JSONB(), nullable=True))
```

### 3.3 升级 / 回滚

```bash
uv run alembic upgrade head          # 升到最新
uv run alembic upgrade +1           # 升 1 个版本
uv run alembic upgrade 1a2b3c4d5e6f # 升到指定版本
uv run alembic downgrade -1          # 降 1 个
uv run alembic downgrade base        # 回到最初
```

---

## 四、核心概念

### 4.1 Revision（版本）

每个迁移是一个 "revision"，有唯一 ID（默认 12 字符 hash）。多个 revision 用 `down_revision` 链接成链。

```
base → 9z8y7x → 1a2b3c → 2b3c4d → head
```

### 4.2 Autogenerate（自动生成）

`alembic revision --autogenerate` 对比 `Base.metadata` 和当前 DB schema，自动生成 `upgrade()` / `downgrade()`。

**autogenerate 检测到的变更**：

- 新增 / 删除表
- 新增 / 删除 / 修改列（类型 / nullable / default）
- 新增 / 删除索引
- 新增 / 删除外键

**autogenerate 漏掉的变更**（要手写）：

- enum 增删
- 视图 / 触发器 / 存储过程
- 表 / 列重命名（autogenerate 看成 drop + add）
- 复杂 CHECK 约束

### 4.3 离线模式

```bash
uv run alembic upgrade head --sql > migration.sql
```

生成 SQL 脚本而不连接数据库（生产环境 DBA 审计用）。

### 4.4 事务管理

每个 migration 默认在事务里执行，失败自动 rollback。

```python
def upgrade():
    op.execute("CREATE EXTENSION vector")  # 单独事务
    op.add_column("docs", sa.Column("embedding", postgresql.ARRAY(sa.Float)))
```

---

## 五、常用命令 & 工具链

```bash
cd packages/service

# 当前版本
uv run alembic current

# 历史
uv run alembic history --verbose

# 自动生成
uv run alembic revision --autogenerate -m "add avatar_url to users"

# 空迁移（手写）
uv run alembic revision -m "custom data migration"

# 升级
uv run alembic upgrade head
uv run alembic upgrade +2

# 降级
uv run alembic downgrade -1
uv run alembic downgrade base

# 强制 stamp（不跑迁移，只标记版本）
uv run alembic stamp head
uv run alembic stamp 1a2b3c4d5e6f

# 离线生成 SQL
uv run alembic upgrade head --sql > /tmp/migration.sql

# 查看 SQL（不执行）
uv run alembic upgrade head --sql | head
```

---

## 六、项目集成点

### 6.1 项目**强制** 使用 Alembic

`packages/service/pyproject.toml:1`：

```toml
"alembic>=1.18.4", # SQLAlchemy 数据库 schema 迁移工具, 管理 src/storage/migrations/versions/*.py
```

### 6.2 迁移位置

`packages/service/alembic/versions/`

### 6.3 项目使用流程

1. 改 `src/db/models/*.py` 加列
2. `uv run alembic revision --autogenerate -m "xxx"`
3. 检查生成的 `alembic/versions/xxx.py`，手写补全 autogen 漏掉的部分（enum / 索引 / 数据迁移）
4. **必须写 downgrade**（项目 `service/CLAUDE.md` 强制：alembic 迁移可回滚）
5. 本地 `uv run alembic upgrade head` 验证
6. CI 跑测试 + 集成测试
7. PR 合并

### 6.4 已有迁移示例

```bash
ls packages/service/alembic/versions/
# 2026_01_15_initial_schema.py
# 2026_02_10_add_lookup_tables.py
# 2026_03_05_add_audit_log.py
# 2026_04_20_add_user_avatar.py
# ...
```

### 6.5 与 FastAPI lifespan 集成

项目 lifespan 不直接调 alembic（独立命令），但部署流程中：

```bash
# 部署脚本
uv run alembic upgrade head
uv run python main.py
```

---

## 七、项目代码示例

### 7.1 新增列（典型）

```bash
uv run alembic revision --autogenerate -m "add avatar_url to users"
```

生成的 `alembic/versions/2026_05_15_xxx.py`：

```python
"""add avatar_url to users

Revision ID: 1a2b3c4d5e6f
Revises: 9z8y7x6w5v4u
Create Date: 2026-05-15 10:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision = "1a2b3c4d5e6f"
down_revision = "9z8y7x6w5v4u"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("users", sa.Column("avatar_url", sa.String(255), nullable=True))

def downgrade() -> None:
    op.drop_column("users", "avatar_url")
```

### 7.2 业务 enum 走 lookup（项目核心约定）

```python
# alembic/versions/2026_02_10_add_lookup_tables.py
def upgrade():
    # 字典表（替代硬编 enum）
    op.create_table(
        "dictionaries",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("code", sa.String(50), unique=True, nullable=False),
        sa.Column("label_zh", sa.String(100), nullable=False),
        sa.Column("label_en", sa.String(100)),
        sa.Column("is_readonly", sa.Boolean, default=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_table(
        "dictionary_items",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("dictionary_id", sa.Integer, sa.ForeignKey("dictionaries.id", ondelete="CASCADE")),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("label_zh", sa.String(100), nullable=False),
        sa.Column("label_en", sa.String(100)),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("deprecated_at", sa.DateTime),
        sa.UniqueConstraint("dictionary_id", "code", name="uq_dict_item_code"),
    )

def downgrade():
    op.drop_table("dictionary_items")
    op.drop_table("dictionaries")
```

### 7.3 数据迁移（手写）

```python
# alembic/versions/2026_06_15_migrate_status_to_lookup.py
"""migrate hardcoded approval_status to lookup dictionary"""

revision = "abc123def456"
down_revision = "xyz789uvw012"

def upgrade():
    # 1. 创建字典（前置）
    # 假设字典已经先 migration 进去了
    # 2. 把现有 status 字符串值映射到 lookup item ID
    conn = op.get_bind()

    # 查字典 item id
    pending_id = conn.execute(
        sa.text("SELECT id FROM dictionary_items WHERE dictionary_id = (SELECT id FROM dictionaries WHERE code='approval_status') AND code='pending'")
    ).scalar()

    # 更新原表的 status 列
    conn.execute(
        sa.text("UPDATE approval_reviews SET status_lookup_id = :pid WHERE status = 'pending'"),
        {"pid": pending_id},
    )

def downgrade():
    # 反向迁移
    pass  # 或手写还原
```

### 7.4 添加索引

```python
def upgrade():
    op.create_index("ix_users_email_lower", "users", [sa.text("lower(email)")], unique=True)

def downgrade():
    op.drop_index("ix_users_email_lower", "users")
```

### 7.5 pgvector 扩展

```python
# alembic/versions/2026_01_20_pgvector.py
def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "llamaindex_embeddings",
        sa.Column("id", sa.dialects.postgresql.UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("metadata", postgresql.JSONB),
        sa.Column("ref_doc_id", sa.dialects.postgresql.UUID),
        sa.Column("embedding", postgresql.ARRAY(sa.Float, dimensions=2)),  # vector(N) 见下方说明
    )

def downgrade():
    op.drop_table("llamaindex_embeddings")
    # 不 drop EXTENSION（其他业务可能用）
```

### 7.6 async env.py 完整示例

```python
import asyncio
from logging.config import fileConfig
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy import pool
from alembic import context
from src.db.base import Base
from src.db.models import auth, chat, approvals, permissions, lookups, audit_log  # 全部
from src.common.db_url import get_rag_db_url

config = context.config
config.set_main_option("sqlalchemy.url", get_rag_db_url())
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online():
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section), prefix="sqlalchemy.", poolclass=pool.NullPool,
    )
    async with connectable.connect() as conn:
        await conn.run_sync(lambda c: context.configure(connection=c, target_metadata=target_metadata) and None)
        async with conn.begin():
            await conn.run_sync(context.run_migrations)
    await connectable.dispose()

if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

---

## 八、项目没用到的能力 / 进阶方向

以下 Alembic 能力项目当前未使用（**待评估**）：

| 能力 | 用途 | 集成建议 |
|------|------|----------|
| **Branch Labels** | 多分支迁移（dev / prod schema 分叉） | 多团队独立迁移场景 |
| **Online Migration** | 大表无锁 ALTER | 千万级表场景 |
| **Multi-database** | 跨库迁移 | 多 DB 项目 |
| **Hook scripts** | 迁移前后跑脚本 | 数据修复 / 缓存失效 |
| **Compression** | pg_dump 压缩 | 大数据库 |
| **Compare Schema** | 对比两个 DB | 跨环境校验 |
| **Time-travel queries** | 任意时间点 schema 查询 | 历史回溯 |
| **Schema metadata 版本化** | 远端服务 schema 同步 | 微服务 |

**建议关注**：Online migration（`op.alter_column` 在大表上锁表），项目表小时无影响，> 1 亿行时必须用 `pg_repack` / `pg_repack` 工具。

---

## 九、最佳实践 & 常见坑

### 项目风格指南（项目 CLAUDE.md 强制）

1. **alembic 迁移必须可回滚**（写 `downgrade`）
2. **业务 enum 走 lookup**（不要新增 enum 列，先看 lookup 字典表）
3. **测试不连真 PG**（迁移不在单测跑，集成测试用 `tmp_pg_schema` 模式）

### 最佳实践

1. **autogenerate 后一定要 review**：

```python
# autogen 看到 column C 删了 + column D 加了
# 可能实际上你想 column C → D 重命名
# 必须手改：op.rename_column
```

2. **每个 migration 专注一件事**：

```python
# ✅ 一个 migration 改一张表的一个变更
"""add avatar_url to users"""

# ❌ 混着来
"""add avatar_url + drop users.created_at + add index"""
```

3. **复杂数据迁移分两步**：

```python
# 1. 先 schema（加列 nullable=True）
op.add_column("users", sa.Column("avatar_url", sa.String(255), nullable=True))

# 2. 后 data migration（独立文件，写实际数据 + 改 nullable=False）
```

4. **测试 downgrade**：

```bash
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head
```

5. **CI 校验**：

```yaml
# .github/workflows/ci.yml
- run: uv run alembic upgrade head
- run: uv run alembic downgrade base
- run: uv run alembic upgrade head
```

6. **stamp 而非 upgrade**：

```bash
# DB 已经是目标 schema，但 alembic_version 表丢了
uv run alembic stamp head
# 标记为最新版本，不跑 migration
```

### 常见坑

1. **env.py 漏 import model**：autogen 看不到新增表

```python
# 必须 import 全部 model（即使代码里不用）
from src.db.models import auth, chat, approvals, permissions, lookups
```

2. **autogen 漏 enum 变更**：手写 `op.execute("CREATE TYPE ...")` 或 `op.alter_column`

3. **表重命名 autogen 看成 drop + add**：手改 `op.rename_table`

4. **nullable 改了丢失数据**：

```python
# ❌ 错：直接 NOT NULL，老数据报错
op.alter_column("users", "email", nullable=False)

# ✅ 对：先 fill default，再 NOT NULL
op.execute("UPDATE users SET email = 'unknown@x.com' WHERE email IS NULL")
op.alter_column("users", "email", nullable=False)
```

5. **大表 ALTER TABLE 锁表**：

```python
# ❌ 错：千万行加 NOT NULL 锁 10+ 分钟
op.alter_column("users", "email", nullable=False)

# ✅ 对：分批
# PostgreSQL 12+ 加 NOT NULL DEFAULT 'x' 不会锁表
op.alter_column("users", "email", nullable=False, server_default="unknown@x.com")
```

6. **测试 mock 漏 `Base.metadata`**：

```python
# 测试时如果 mock 了 engine，alembic 升级会失败
# 项目测试**不要**跑真实 alembic 升级（`alembic` 模式 3 待评估）
```

7. **CI 跑 migration 没设置 DATABASE_URL**：env.py 里 `os.getenv("DATABASE_URL")` 缺失会失败

8. **autogen 时连接了错误的 DB**：env.py `get_rag_db_url()` 必须指向测试 / dev DB，不要指向 prod

9. **alembic 跟 model 双向漂移**：

```bash
# 经常跑
uv run alembic upgrade head  # 同步 DB 到最新
# 改 model，再
uv run alembic revision --autogenerate -m "..."
```

10. **JSONB 默认值**：

```python
# ✅ 对：default dict
op.add_column("approvals", sa.Column("payload", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")))
```

---

## 📚 参考

- [Alembic 官方文档](https://alembic.sqlalchemy.org/en/latest/)
- [Alembic Tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- [Autogenerate 文档](https://alembic.sqlalchemy.org/en/latest/autogenerate.html)
- [SQLAlchemy 2.0 文档](https://docs.sqlalchemy.org/en/20/)
- [PostgreSQL Online Migration](https://www.postgresql.org/docs/current/sql-altertable.html)
- [项目 service/CLAUDE.md §测试隔离 4 模式](../../packages/service/CLAUDE.md)

---

**状态：** ✅ 已完成

**最后更新：** 2026-06-25
