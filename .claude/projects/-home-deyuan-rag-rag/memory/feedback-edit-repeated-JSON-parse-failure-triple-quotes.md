---
name: feedback-edit-repeated-json-parse-failure-triple-quotes
description: Edit/Write 对含 Python 三重引号的代码反复 JSON 解析失败时，应换方案而非重试
metadata: 
  node_type: memory
  type: feedback
  originSessionId: b7519910-797a-4626-b12b-7081b672f030
---

# Edit/Write 工具频繁 JSON 解析失败时的应对

**问题**: 2026-06-23 修改 `cache.py` 的 `_subscriber` 函数时，Edit/Write/PowerShell/Bash 工具连续失败上百次，全部报 `InputValidationError: could not be parsed as JSON`。

**根因**: 工具接口用 JSON 传输参数。Python 代码含三重引号 `"""` + 中文 + 特殊字符（`→`、`{}`、`'` 等）时，这些字符在 JSON 字符串里需要转义。多重转义（JSON â→Python →实际字符）极易出错，且每次失败都要重新输入全部内容。我不停重试相同方法，没有及时切方案。

**正确做法**:
1. **第一步**: 用 Write 工具写一个简单的 Python 脚本文件到磁盘（脚本本身不包含三重引号，纯 ASCII）
2. **第二步**: 用 Bash 工具运行该脚本（脚本内容通过文件系统传递，不经过 JSON）
3. 如果 Write 也失败 → 用 PowerShell `Set-Content` + `@''@` 单引号 here-string 写入
4. 如果还不能写文件 → 用 `python -c` 一行命令直接创建小文件

用这个方法（先写 fix_subscriber.py → 再 run）一次就成功了。问题是 `while True:` 缩进没处理好，再迭代修复脚本即可，不需要重新输入所有内容。

**Why**: JSON 传输含特殊字符的代码注定脆弱。文件系统没有这个限制。先写文件再运行是绕过 JSON 解析瓶颈的最短路径。

**How to apply**: 以后遇到 Edit/Write 连续 2 次以上 JSON 解析失败，立刻换"先写 Python 脚本→再运行"方案，不要重复试。