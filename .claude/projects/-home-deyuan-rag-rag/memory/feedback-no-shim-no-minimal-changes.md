---
name: feedback-no-shim-no-minimal-changes
description: "严禁写 shim / 兼容代码 / 兜底包装 —— 新项目零技术债原则"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 312b3b8d-ff70-492c-b82a-f9c6dba4f2c7
---

# 严禁 shim 代码

用户 2026-06-05 提出原则: "新项目不要前期就弄一堆历史包袱和技术债"
用户 2026-06-08 升级为硬规则: **"记住严禁以后出现shim代码"**

**禁止出现**（看到就直接删/拒绝实现）：
1. **API 兼容层** —— `def old_api(): return new_api(...)`, 函数体只调新 API
2. **属性兜底** —— `getattr(x, "method", None)` 当成"协议位"塞行为（duck typing 检查**必要**的除外）
3. **try/except 兜底** —— 捕 `ImportError` / `AttributeError` / `Exception` 后走替代实现
4. **配置静默回退** —— 段缺失时用魔法默认值, 不报错不告警
5. **重复实现** —— 同一功能在两个文件有几乎一样的实现（如 `_read_file_with_fallback`）
6. **deprecated warning** —— `DeprecationWarning` 提示老 API
7. **旁路属性** —— `skip_can_handle` 这种基类外加的 flag 偷塞行为
8. **package re-export 旧符号** —— `from .x import old_api` 让外部能继续用

**不算 shim, 可以保留**（必要多态/防御, 不要误删）：
- 必要 duck typing：llama-index 节点/响应对象有 `.text` / `.response` / `.source_nodes` / `.metadata` 中任一个（项目混用 LIDocument 和 TextNode）
- 必要 None 守卫：`getattr(entity.dxf, "annotation_handle", None)` 第三方对象属性可能不存在
- 必要可选依赖处理：`try: import tqdm; except ImportError`
- 必要环境变量回退：env 没设时从 `defaults.py` 拿项目自己的默认值（**不**是"段缺失时静默兜底"）
- 业务级兜底（如 mineru `_find_md_in_subdirs` 路径不固定）

**How to apply:**
- 写新代码前先问: "这个兼容层是真必要, 还是我在凑合?" —— 凑合的就删
- 改完任何代码, 用下面这些 grep 自查:
  - `legacy|compat|backward|shim|deprecat|旧的|兼容|兜底|旧 API|old_`
  - `getattr\(.*,\s*(None|"")` （属性兜底）
  - `try:\s*$` + `except (ImportError|AttributeError|Exception)` 多行模式
  - `cfg\.get\("段名",\s*\{\}\)` 段缺失静默回退
- 见 [[project-rag-shim-audit-2026-06-08]] 记录了项目里现有 shim 清单（5 HIGH + 6 MEDIUM）, 改这些位置前先清掉
- 跟 [[feedback-check-pyproject-deps-match-actual-imports]] 一起, 都是"现在就做对"的态度
- 跟 [[feedback-tdd-test-real-behavior-not-just-no-crash]] 配对: refactor 完跑测试验证

**两个反模式 (2026-06-08 清理 shim 时栽的跟头, 用户两次纠错):**

1. **过度设计**: 删 shim 不要为"业务**不会发生**的边界"加 try/except 分支. 例子:
   - `get_cad_config` 原来用 `.get(..., "")` 简单一条线. 我改成"段缺失 → 返空 / 段有但缺键 → raise"三段式
   - 业务现实: 用户**要么不写 [cad] 段**（走 env）**要么两个键都写**. "段有但缺键"几乎不发生
   - 为不会发生的边界加分支 = 把简单事复杂化, **违反 YAGNI**
   - 正确做法: 保留原版简单逻辑, 不细分这两种情况

2. **加反射测试 (testing absence)**: 删 shim 不应**新增**测试, 应该**保持不变**或**减少**.
   - 反例: 写 `test_process_pdfs_NOT_importable_*` 测 "shim 已删" = 测**不存在的属性**, anti-pattern
   - 删 shim 后用 `grep` 验证就行, **不要**为"删了"写测试
   - 真行为测试保留: 测新 API 签名, 测业务行为变化 (如 `process_cad_files` 不再 glob str 目录)
   - 删 shim 净效应: **测试数应该减少** (删旧 shim 测试 + 0 新增反射), 不应该增加
   - 用户原话: "明明没有增加功能, 为什么 test 代码增加这么多"

**Why:** 用户做架构选择时显式拒绝"最小改动"凑合方案, 选了"一次到位"方案. 这次 (2026-06-08 mineru 容器清理) 我留了 `raise ContainerError` 假装是 docker 异常, 被用户抓包, 升级为硬规则.
