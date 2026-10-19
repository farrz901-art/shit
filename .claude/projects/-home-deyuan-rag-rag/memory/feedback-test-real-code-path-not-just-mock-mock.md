---
name: feedback-test-real-code-path-not-just-mock-mock
description: "dep 替换 / 包切换后必须测真实代码路径, 不能依赖 mock 单元测试当验证"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 298dc759-254d-43ee-a841-71ccb0b25682
---

依赖包替换 (e.g. pynvml → nvidia-ml-py) 后, **单元测试可能完全 mock 掉了被替换的入口**, 跑绿不等于新包实际能用. 必须额外写一个走真实代码路径的 smoke test, 覆盖 import + 关键函数调用.

**Why:** 2026-06-15 用户严正纠错: "你只改了包, 甚至没改代码, 这是严重失误". 当时情况:
- 把 pynvml PyPI shim 换成 nvidia-ml-py 官方包
- 跑 pytest 10/10 全绿
- 实际 `tests/health/test_checks.py::test_check_system_returns_cpu_mem_gpu` mock 的是 `_sample_gpu` 函数本身, 完全没走 `import pynvml` → `nvmlInit` → `DeviceGetCount` 的真实代码
- 如果新包 API 不兼容 (比如函数名变了, bytes 解码行为变了), 单测 10/10 也能绿, 但生产 health endpoint 拿不到 GPU 数据
- 用户教训: 改包/换包后必须确认"被替换的代码真的被运行过"

**How to apply:**
- dep 替换 / 包名切换 / 重大升级 (minor+ 版本跳) 后, 写一个 `test_<dep>_smoke.py` 走真实 import + 真实函数调用, 不能只靠 mock 测试
- smoke test 必须包含: (1) 真 import 无警告; (2) 关键函数 hasattr 存在; (3) 真实端到端调用 (或 mock 整个第三方模块保留 API 形状); (4) 优雅降级路径 (无 GPU/驱动时返 [] 不抛)
- 本项目已修: `packages/service/tests/health/test_nvidia_ml_py_smoke.py` 3 个 case, 涵盖 mock-pynvml 跑 _sample_gpu 真代码 / 真模块 import / 真无驱动的优雅降级
- 原则同 `feedback-must-test-both-ends` 和 `feedback-no-mock-for-external-systems`
