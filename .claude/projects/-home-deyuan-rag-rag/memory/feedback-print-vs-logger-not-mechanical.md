---
name: feedback-print-vs-logger-not-mechanical
description: "print → logger 改动必须先列适用/不适用清单, 不是无脑机械执行. fail-safe / CLI / tests 三类要保留"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 2b9d13fc-964f-41f4-8aba-b9c9b7e5b917
---

收到"把 print 改成 logger" 这类指令时, 不能机械执行, 必须先分 3 类列清单让用户拍板.

**3 类保留 print 的反例**:

1. **日志系统自身 fail-safe** (e.g. `src/core/logging.py` 里 `try: logger.sink 写库 except: print` 兑底)
   - Python logging 官方约束: "Never log from within a log handler"
   - 改 logger 会递归死循环

2. **CLI 脚本 / 人看输出** (e.g. `scripts/seed_admin.py`, `scripts/neo4j_import.py`)
   - 交互式输出, 改 logger 后走项目 `configure_logging` (PII scrub / DB sink / 级别过滤)
   - CLI 在 main.py 之外跑不接 configure_logging, loguru default 走 stderr
   - 改 logger 符号统一但实际效果一样, 反而增加代码噪音

3. **测试诊断 print** (e.g. `tests/health/test_nvidia_ml_py_smoke.py`)
   - pytest capture 默认捕获 stdout, `-s` 才显示
   - 改 logger 走项目 `configure_logging` 会污染测试输出 + 触发 PII scrub
   - 违反 [[feedback-test-must-be-100pct-mock-no-real-db]] 的测试隔离原则

**真正该改的**: 业务代码 `src/**` 里非 fail-safe 的 print (业务日志要结构化走 sink + 中文化).

**Why:** 2026-07-01 用户原话 "所有 print 改一下", 我没核对就开始动手, 给 `tests/health/test_nvidia_ml_py_smoke.py` 加 `from loguru import logger` 后被用户叫停, 要求先分析是不是最佳实践. 正确做法是先列 3 类反例让用户拍板.

**How to apply:** 收到 "把所有 X 改成 Y" 类指令时, 先扫描全项目, 按 "适用 / 反例" 分类列清单, 反例标"不适用理由", 用 AskUserQuestion 让用户选: 1) 保留反例 2) 全部机械改 3) 先问具体诉求. 不要默认派 subagent (太小), inline 核对 + 提问即可. 跟 [[feedback-clarify-ambiguous-instructions]] 配套使用.
