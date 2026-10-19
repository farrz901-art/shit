"""base.py 测试: Base 是 DeclarativeBase 子类, metadata 可用"""

from src.storage.base import Base


def test_base_is_declarative_base():
    """Base 必须是 SQLAlchemy DeclarativeBase 子类, 2.0+ 写法"""
    from sqlalchemy.orm import DeclarativeBase

    assert issubclass(Base, DeclarativeBase)


def test_base_metadata_is_empty():
    """Base.metadata 是空 MetaData 容器, 可注册 model

    Task 6+ 后: 业务 model (User 等) 在 import 时注册, metadata 不为空
    本测试只验证 metadata 对象本身存在且可用, 不假设为空
    """
    assert Base.metadata is not None
    assert hasattr(Base.metadata, "tables")
    assert hasattr(Base.metadata, "create_all")
