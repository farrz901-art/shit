# Spec/Plan 分批写入文件的经验

写入大型 spec/plan 文件时，由于工具参数 JSON 解析对特殊字符（`\`、`"`、`{`、`}`、`(`, `)` 等）敏感，已多次写文件失败。

## 验证过的工作方法

1. **写 Python 脚本到磁盘 → 执行**：用 Write 写 Python 脚本（纯 ASCII 无复杂转义），然后 `python script.py` 执行。脚本内用 list of lines + `str.join("\n")` 构建 Markdown 内容，避免直接在三引号字符串内包含 `\` 等特殊字符
2. **PowerShell Add-Content 逐行**：每行一个 `Add-Content -Path $path -Value $line`，最稳定但慢。单引号字符串避免变量展开。注意 `[` / `]` / `{` / `}` 在 PowerShell 中的特殊含义
3. **避免**：直接在 Write/Edit/Bash/PowerShell 工具的参数中嵌入大段含特殊字符的内容——JSON 解析会失败

## 反模式

- ❌ 在 Write 内容中放包含 `\n`、`\"`、`\` 的 Python 三引号字符串——JSON 解析器吃掉反斜杠
- ❌ 在 PowerShell `@()` 数组中放含 `{`、`(` 的项——ParseError
- ❌ 把大型 spec/plan 一次性通过 Write 写入——超长内容遇到任何特殊字符立刻失败

**Why:** 我花了大量时间在文件写入工具的 JSON 解析问题上，经常需要把同一段内容用 3-4 种不同方式尝试。`Write` 工具一旦内容含特殊字符（绝大多数 Markdown + 代码块都含），就通不过 JSON 解析。**PowerShell Add-Content 逐行 + Python 脚本**是可靠路径。
**How to apply:** 写大文件先想能否用 PowerShell `Add-Content` 逐行写，或用 Python 脚本中转。不要在工具调用的 JSON 参数里放含特殊字符的内容。Write 只适合写纯 Python 脚本（无复杂转义），不适合写含代码块的 Markdown。
