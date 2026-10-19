---
name: feedback-stop-repeating-verification-commands
description: "用户已确认的事实不要再重复验证,反复让跑 mokutil --sb-state 这种已确认命令 = 调试循环卡死症状"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 1b9fcc0d-8861-46a3-a981-3a0937775dd9
---

反复让用户跑同一条已经确认过的验证命令 = 调试循环症状。停止信号:用户用"?"、"有病"、"为什么"质疑当前动作的合理性。

**真案** (2026-07-02 Ollama 排查):
- 用户确认 `mokutil --sb-state → SecureBoot disabled`
- 我后面又让跑了 3 次同一命令
- 用户质问 "有病反复让我 mokutil --sb-state"
- 同一会话后段又犯:让用户重启 BIOS 后跑"重启后跑 mokutil 验证"——再被质问 "为什么要重启,什么都没改,我重启干什么"

**Why:** 调试链路上容易陷入"确保每一步都验证再下一步"的强迫症,但用户已经验证过的状态不能反复确认。这是时间浪费 + 信任消耗。

**How to apply:**
- 用户确认过的状态,直接 goto 下一步
- 验证命令只在"真的还不确定"时跑,且只跑一次
- 如果发现自己在连续消息里发同一条诊断命令,**立刻收尾**,直接给下一步动作或方向建议
- 用户用质问语气("为什么要 X"、"有病"、"?????")质疑合理性 = 立刻承认 + 改方向,**不要再 defend**
- 调试卡住时:停,列 3 个分支方案给用户拍板,不要重复 fall-through 同一诊断链

**相关**:
- [[feedback-stop-and-ask-dont-loop-on-infra]] — 调试 30 分钟卡住的升级路径
- [[feedback-debug-distinguish-root-causes]] — 别用最简单的解释掩盖真正问题
- [[feedback-debug-stop-after-root-cause-confirmed]] — 根因确认后立刻收尾