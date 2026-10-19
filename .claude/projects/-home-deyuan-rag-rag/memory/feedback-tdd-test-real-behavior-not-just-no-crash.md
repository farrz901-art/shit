---
name: feedback-tdd-test-real-behavior-not-just-no-crash
description: "TDD 不能只测\"不崩\", 要测真行为 (尤其是 CLI/集成路径, 跟 mock 真实场景)"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 2b43cdde-9008-4f4a-8f71-df2d2a112bb2
---

# TDD: 测真行为, 不只测"不崩"

**问题模式**: 我 TDD 写测试时, 只测"代码不抛错" (e.g. `returncode == 0`, `ModuleNotFoundError not in stderr`), 漏了"真行为" (e.g. `check` 读 .env, 连 Neo4j, 打 APOC 版本).

**用户两次纠错**:
1. (Task 12 提交后) `python scripts/neo4j_import.py --help` 能跑, 但 `check` 报 `ModuleNotFoundError`. 我的回归测试只覆盖了 `--help`, 没真测 `check`.
2. (Bug fix #1 提交后) `python scripts/neo4j_import.py check` 报 `缺环境变量`. 我的 `test_neo4j_client_missing_env_raises` 只测了缺 env 报错, 没测有 env 真的跑通.

**根因**:
- TDD 的诱惑是"测错误路径容易, 测成功路径难" (要造真实数据, 真实连接)
- 我倾向写"防御性测试" (防错), 不写"行为性测试" (验真)
- pytest 通过 ≠ 脚本能跑, 尤其 CLI 工具
- 单元 mock 通过 ≠ 集成端到端通

**关键教训**:
- 每个测试前问: "用户真用这个功能时, 实际命令是什么? 实际输入是什么?"
- 对 CLI 工具, 至少 1 个测试 = subprocess 跑 `python script.py <子命令> <真实参数>`, 看 stdout 是否包含期望的输出
- 集成测试不要都 mock, 至少 1 个端到端 (这次没补, 改成 user-report-driven)
- "成功路径测试" 跟 "失败路径测试" 同样重要, 不是二选一

**解决方案** (按推荐顺序):
1. **写测试前先口述用户场景**: "用户会跑 X 命令, 输入 Y, 期望看到 Z 输出"
2. **每条测试都问: 这是 mock 的成功, 还是真实的成功?** Mock 通过 ≠ 真行为通过
3. **对 CLI/集成代码, 默认带 1 个 subprocess 真跑测试** (e.g. `test_script_runs_with_dotenv`)
4. **失败 → 修 → 提交前, 必须手动跑一次真命令**, 不只看测试绿
5. **"用户报告后才补测试" 是被动反应**, 应该主动在 TDD 阶段就覆盖真实路径

**How to apply**:
- 写 CLI 工具的测试: 至少 1 个 `subprocess.run([sys.executable, "script.py", ...])` 测真命令
- 写集成测试: 不只测 mock, 至少 1 个用真实数据 (e.g. 真 yaml, 真 .env)
- 写完测试, 提交前: 自己手动跑一次真命令, 确认跟测试期望一致
- 接到用户报告 bug: 不仅修, 还要加"覆盖真实场景"的回归测试, 防再犯

**Related**: [[project-scripts-syspath-injection]] (这个 bug 也是 TDD 没真测暴露的), [[feedback-no-mock-for-external-systems]] (mock 不能替代真测)
