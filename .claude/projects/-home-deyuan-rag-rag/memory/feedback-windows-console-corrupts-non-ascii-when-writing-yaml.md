---
name: feedback-windows-console-corrupts-non-ascii-when-writing-yaml
description: "Windows bash 下写 YAML/JSON 时, 全角字符 (△、※、…) 被控制台 code page 吞掉, 变成 ASCII 替代 (D, *, ...). 用 Python 直接写 bytes 才能保住, 但要先跟用户确认是不是有意为之"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 2b43cdde-9008-4f4a-8f71-df2d2a112bb2
---

# Windows 控制台编码吞掉全角字符

**症状**：在 Windows 11 + PowerShell / Git Bash 下用 `Write` 工具或 `>` / `cat <<EOF` 写含**全角字符**（`△` `※` `…` `—` 等）到 YAML / JSON / 任意文本文件，**写完后再读发现字符被替换成 ASCII 替代**：
- `△` (U+25B3) → `D` (单字节)
- `※` (U+203B) → `*`
- `…` (U+2026) → `...`
- `—` (U+2014) → `--`
- 中文 / 日文等也会被 mojibake

**根因**：Windows console 默认 code page 是 437 / 936 (GBK)，**不是 UTF-8**。`Write` 工具如果走 console 路径输出，UTF-8 字节流经过 console code page 转换就坏掉了。

**重现链**（2026-06-04 在 `configs/.../1le0_low_voltage.yaml`）：
1. 我用 `Write` 写 YAML，里面有 `code: "220△/380Y/50"`
2. 写完后 `grep` 看到的是 `code: "220D/380Y/50"`（D 替换了 △）
3. 我以为这是 bug，**自作主张**把 YAML 改回 △
4. **用户纠正**：`VD` 是用户**手动选**的电压 code 表示（避开 △ 的编码坑），不是 bug
5. 我又把 △ 改回 `VD/VY`，对齐用户的真实选择

**关键教训**：
- 看到 "看起来不对的字符" 不要立即当成 bug 修——**先跟用户确认**是不是有意为之
- 用户为了解决一个问题会做出非显而易见的"hack"（如把 △ 换 VD 是为了避开 console 编码），自动 revert 这种 hack 会让用户重新踩坑
- 如果测试失败 assertion 说 "实际 X 期望 Y"：先看 X 是不是用户手动改的（git log / git blame），再决定改测试还是改 X

**解决方案**（按推荐顺序）：
1. **直接用 `Write` 工具写完整内容**——它用 file I/O，UTF-8 安全
2. **用 `python -c "..."` 或 `python <<'EOF'` heredoc 写文件**——Python 文件 I/O 是 UTF-8，绕过 console 转码
3. **绝对不要**用 `bash echo`、`cat <<EOF`、`printf` 等依赖 console 转码的命令构造含全角字符的内容
4. **写完后用 hexdump 验证**：
   ```bash
   python -c "
   with open('file.yaml', 'rb') as f:
       print(f.read().hex())
   "
   # △ 应该是 e296b3, 不是 44 (D 的 ASCII)
   ```

**How to apply**：
- 写含 `△` `※` `…` `—` 的 YAML/Markdown 配置文件：用 `Write` 工具或 `python <<'EOF'`
- 跑 git pre-commit 后中文/全角字符被破坏：先怀疑 console 编码，不怀疑 lint
- 调试测试时 assertion 失败说 "实际值跟期望值不同"：**先 git blame 确认 "实际值" 是不是用户手动改的**，再决定修哪边
- 看到非 ASCII 字符的 "非标准" 替换：先问用户是不是 hack，不要自作主张 revert

**Related**: [[feedback-record-errors-and-lessons]]（每次犯错都要存）
