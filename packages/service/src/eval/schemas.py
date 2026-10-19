"""eval 模块 Pydantic schemas 和异常类"""


class EvaluatorError(Exception):
    """eval 执行失败, 非 None 信号.

    原代码中 evaluator 静默吞错返 None, 调用方无法区分"评估成功得 0 分"和"评估炸了".
    改用此异常主动抛, 上层统一处理成 EvalResult(status="error", ...).
    """

    pass
