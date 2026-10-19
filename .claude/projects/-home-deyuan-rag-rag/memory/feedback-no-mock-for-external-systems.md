---
name: feedback-no-mock-for-external-systems
description: "用户明确说\"不信 mock 测试\" — 涉及外部系统（Docker 容器、数据库、网络、文件系统真实行为）的 bug 修复必须用真实环境端到端跑通"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: d5923208-4647-4dd0-9acb-40426948d1ee
---

用户明确表态：**不信 mock 测试**。

**Why:** 在 [[project-mineru-docker-integration]] 调试中，我用 `unittest.mock` mock 掉 `docker.from_env` 写了测试，测试通过了就声称"修复成功"。但真实跑 `python main.py` 时，mineru 容器因为 VLM backend 没 GPU 直接 exit 1，加上嵌套目录名我猜错了，结果 markdown 一份都没生成。mock 测试通过了，真实系统全坏——用户原话"不要用 mock 测试，我不信 mock 测试"。

**How to apply:**
- 涉及外部系统的 bug 修复，**必须**真实端到端跑一次（真容器、真数据库、真 HTTP）
- mock 测试只适合验证纯函数/纯逻辑，**不**适合验证"代码调用了某个外部系统并且那个系统返回了预期结果"
- 写测试时如发现要 mock 大量外部依赖，应该考虑：是不是应该用真实环境（testcontainers、临时目录里的真实 DB 等）
- 测试通过 ≠ 修复成功。要看真实运行结果才算数
- 跨参考：[[project-mineru-docker-integration]] 是这个教训的来源案例
