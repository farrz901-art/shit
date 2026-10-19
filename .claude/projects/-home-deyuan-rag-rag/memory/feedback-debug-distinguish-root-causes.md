---
name: feedback-debug-distinguish-root-causes
description: 调试时不要把相似症状的不同根因混为一谈，要分情况列清楚再判断
metadata: 
  node_type: memory
  type: feedback
  originSessionId: d5923208-4647-4dd0-9acb-40426948d1ee
---

**错误：** 在 [[project-mineru-docker-integration]] 调试中，mineru 报"CUDA not available"——这是个症状。可能的根因至少有两个：

1. **主机真没 GPU**（环境问题，无法解决）
2. **容器没拿到 GPU 设备请求**（代码 bug，可以修）

我直接下结论"无 GPU 时 exit 1"，掩盖了是哪一个根因，导致给的修复（固定 pipeline backend）只是绕过症状，没修根因。

**为什么犯这个错：**
- 调试时只看了症状（错误信息），没看证据（主机有没有 GPU / 容器能不能看到 GPU）
- "无 GPU"是更简单的解释，我偷懒选了简单的
- 没意识到这是个**多根因问题**——同一个症状背后有不同修法

**教训：**
- 看到症状时，**先**列出所有可能的根因（环境/配置/代码/网络/权限）
- 收集证据**逐一排除**或确认，而不是直接选最简单的那个
- 用户报告"我有 X 硬件但 Y 报错"时，**特别**要怀疑是不是代码没正确利用 X
- 给的修复要对应**根因**，不是症状；写测试时也要测根因
- 跨参考：[[feedback-docker-gpu-needs-device-requests]] 是这个教训的来源案例
