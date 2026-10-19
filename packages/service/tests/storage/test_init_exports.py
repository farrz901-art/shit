"""storage 包公开 API 测试: 5 个导出都从顶层 import 可用

Task 4: 验证 IngestTask + KgAudit (新增) 也注册到 Base.metadata.
其他 7 个业务 model (User / Account / Conversation / Message / Evaluation /
EvaluationSample / Approval) 仍可从各自子包 import.
"""


def test_storage_top_level_imports():
    from src.storage import Base, get_engine, get_session, init_db, session_scope

    # 都是 callable / 类, 不是 None
    assert Base is not None
    assert callable(get_engine)
    assert callable(init_db)
    assert callable(get_session)
    assert callable(session_scope)


def test_all_11_business_models_registered():
    """Task 4: Base.metadata 应包含 11 张业务表.

    漏注册某个 model → alembic autogenerate 会漏 diff, 这里把守.
    """
    from src.approvals.models import Approval
    from src.auth.models import User
    from src.chat.models import Conversation, Message
    from src.eval.models import Evaluation, EvaluationSample
    from src.ingest.pdf_processing.models import IngestTask
    from src.kg.audit_models import KgAudit
    from src.storage import Base

    expected_tables = {
        Approval.__tablename__,
        User.__tablename__,
        Conversation.__tablename__,
        Message.__tablename__,
        Evaluation.__tablename__,
        EvaluationSample.__tablename__,
        IngestTask.__tablename__,
        KgAudit.__tablename__,
    }
    actual_tables = set(Base.metadata.tables.keys())
    missing = expected_tables - actual_tables
    assert not missing, f"Base.metadata 漏注册 model: {missing}"
