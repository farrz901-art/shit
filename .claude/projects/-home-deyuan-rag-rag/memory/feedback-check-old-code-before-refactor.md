---
name: feedback-check-old-code-before-refactor
description: "重构/拆路由/改页面结构前必须先 git log 查老代码, 不能凭\"我记得\"动手; 用户两次因\"删除功能没补回\"严重纠错, 2026-06-10 是第二次"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 822e2447-09c4-4b8a-9808-d37453aff4b8
---

**每次重构/拆路由/改页面结构前, 必须先 git log 查老代码, 不能凭记忆动手.** 用户两次因"重构时删除功能没补回"严重纠错, 这是第二次.

**Why:** 2026-06-10 用户报告"你犯了严重失误":
- 拆 /document + /graph 路由时, /documents 入口文件被改错, 少回填 1 张录入卡 (本应是 2 张, 我只补了 1 张)
- /graph 页面下方的录入卡片也消失了
- 用户原话: "你犯了严重失误 1. 昨天重构知识库页面, 改成 /document 和 /graph 路由的时候, 把 /document 入口文件弄错了, 另外 /graph 页面下面的录入卡片也消失了, 检查一下"
- 用户追问: "/documents 页面原来有两个录入卡片, 现在只有一个卡片" / "/documents 页面下面的导入功能是原来的录入卡片的功能, 应该提取出来, 从卡片点击进入"

根因分析 (我自己的复盘):
1. **没查 git 老代码**: 我"修复"时凭"我以为老设计是 X"动手, 没 `git show 5703e18:web/app/knowledge/page.tsx` 确认. 实际老 Dify tab 是 2 张卡 (录 QA 对 + 传文档), 不是我以为的 1 张
2. **删了功能没全补回**: 上次拆 /document + /graph 路由时, 老 dashboard 里的 2 张卡变 0 张, 我"恢复"时只补了 /graph 的 2 张, 漏了 /documents 的 1 张 (应该是 2 张)
3. **没核对 "为什么"**: "传文档"在分路由后自环, 我下意识说"老设计也是 1 张卡"逃避, 真因是没去 git log 查
4. **复述用户指令不准**: 用户说"参考以前的老代码", 我听成"按我记得的改"而不是"git show 老代码"

**How to apply:**

```bash
# 重构前必跑 (改页面/拆路由/重命名任何 UI 结构)
git log --oneline --all -- <相关路径>  # 找老版本
git show <old_commit>:<path>           # 看老代码长什么样

# 拆路由时
git show <refactor_commit> --stat      # 看改动了哪些文件
git show <refactor_commit>:<old_path>  # 看老页面完整结构
```

**自检清单 (拆路由/重构页面结构时)**:
- [ ] 老页面有几个 EntryCard / StatCard / 子区块?  (用 git show 数)
- [ ] 每个区块在新路由哪个位置?  (写下来, 不要脑子里推)
- [ ] 老 href → 新 href 的映射表是否完整?  (易漏自环 href)
- [ ] 改完跑测试, 测试用例数 ≥ 老测试用例数?  (少 = 漏了功能)

**查接口/功能是否存在时**:
- `curl localhost:8000/openapi.json` 只反映**当前运行的 uvicorn** 加载了哪些路由
- 源码里定义了但没注册/没重启 = 运行时 404, 但代码存在
- **正确做法**: 先 `grep -rn "router\." src/` 查源码有没有定义, 再判断是"没写"还是"没注册/没重启"
- **禁止**: 只看 openapi.json 就下结论"后端没这个路由"

**沟通纪律**:
- 用户说"参考老代码" = 必须 git show, 不是"我记得"
- 用户说"仿老 X tab 结构" = 必须先找到老 tab 代码, 数清楚几个卡, 再动手
- 模糊时停下来问, 不要猜 — 见 [[feedback-clarify-ambiguous-instructions]]

**关联**:
- [[feedback-fix-root-cause-not-remove-feature]] — 这次也是变相"删功能", 老设计是"自环但用户能点", 我把整个拆了
- [[feedback-no-shim-no-minimal-changes]] — 这次没用 shim, 但用了"凭印象补卡"这种 minimal mental model 凑合
- [[feedback-clarify-ambiguous-instructions]] — 用户说"参考以前"我没追问"参考哪个 commit/哪个时间段"
