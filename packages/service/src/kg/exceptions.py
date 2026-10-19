"""知识图谱模块异常类型"""


class KgError(RuntimeError):
    """知识图谱相关错误的基类"""


class DuplicateNodeError(KgError):
    """MERGE 命中已存在节点且 caller 要求 CREATE-only"""


class InvalidTripleError(KgError):
    """三元组结构不合法 (缺字段 / 类型不匹配 / 关系不存在)"""


class SchemaError(KgError):
    """yaml schema 加载或校验失败"""


class TaskNotFoundError(KgError):
    """task_id 在 TaskStore 里查不到"""
