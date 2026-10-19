# Verifier Agent Prompt Template — oversize-files-audit v2

跟 `/full-stack-audit` Phase 3.2 verifier 模板 1:1 同结构。

每条 6 段 finding 派 1 个 verifier agent，默认反驳，找不到反例 → verified=true。

---

## 通用 frontmatter

```
你是 verifier，尝试反驳这条 finding (默认反驳):

finding 全文:
<paste 单文件 6 段 markdown，含路径 + 6 段内容>

文件: {file} (项目根: c:/doc/Code/rag/)
agent 派发时间: {ts}
verifier 编号: V{N} (主线程递增)

任务:
1. Read {file} 上下文 (前后 30 行)
2. 找出反例 / 错配 / 误判的证据:
   - 库替代段: 该库真的没装? (Read packages/web/package.json / components.json / packages/service/pyproject.toml)
   - 拆点提议: 行号对不对? 拆后预计减少 % 是否虚高?
   - 对象替 if: switch 是真存在? switch 不可被对象替 (case 复杂)?
   - 数组替循环: 循环里真有副作用? 不能改 .map()?
   - 纯函数化: 真的纯吗? 有没有闭包 / 全局变量?
3. 如果找不出反例 → verified=true，保留 finding
4. 如果找到反例 → verified=false，给具体 refuted_reason (≥ 2 句)

工具调用 ≤ 5 次，tokens ≤ 5k。最终回复必须是 JSON:
{"verified": bool, "confidence": "high|medium|low", "refuted_reason": "string|null"}
```

---

## Verifier 报告结构

主线程收集 verifier 返回 JSON 后，写回 finding 末尾：

```markdown
### `<相对路径>` (412 行)

**1. 拆分点**: ... (原文保留)
**2-6**: ... (原文保留)
**7. 骨架伪代码**: ... (原文保留)

**verified**: <bool>
**confidence**: <"high"|"medium"|"low">
**refuted_reason**: <string|null>  <!-- verified=true 时为 null -->
```

---

## 降级规则 (跟 /full-stack-audit §降级规则 一致)

| 情况 | 处理 |
|---|---|
| verifier 工具调用失败 / 超时 | 默认 verified=true, confidence=low |
| verifier 找不到反例 | verified=true |
| verifier 找到反例 | verified=false, refuted_reason ≥ 2 句 |
| verifier 返回不是合法 JSON | 默认 verified=true, confidence=low, 警告写到主报告 |

**绝不因 verifier 失败阻塞主报告**。

---

## 数量限制 (主线程派发前 assert)

```bash
# 估算 verifier 数量 = 文件数 × 6 段
EST=$((FILE_COUNT * 6))
if [ "$EST" -gt "$MAX_VERIFIER" ]; then
  echo "WARN: $EST > $MAX_VERIFIER, truncating"
  # 主线程从 a*.md 提取 finding, 按文件行数降序, 截到 N 条
fi
```

`--max-verifier N` 默认 60。42 文件 × 6 段 = 252 条 finding → 截到 60 条最关键的（行数最大）。

---

## Token 预算

- 每 verifier: ≤ 5k token
- 默认 60 verifier: ≤ 300k token
- 跟 /full-stack-audit 同量级, 不爆

---

## Verifier Prompt 派发示例 (主线程循环)

```bash
# 主线程读 3 份 a*.md, 提取 finding
python .claude/skills/oversize-files-audit/references/extract-findings.py \
  docs/audit/$DATE/oversize-files-audit/ \
  > docs/audit/$DATE/oversize-files-audit/.findings.json

# 按行数降序截到 N 条
python -c "
import json
findings = json.load(open('docs/audit/$DATE/oversize-files-audit/.findings.json'))
findings.sort(key=lambda f: -f['lines'])
findings = findings[:$MAX_VERIFIER]
json.dump(findings, open('docs/audit/$DATE/oversize-files-audit/.findings-trimmed.json', 'w'), ensure_ascii=False, indent=2)
print(f'Trimmed to {len(findings)} findings')
"

# 主线程遍历派 verifier (每个 background agent 跑 1 条)
for i, finding in enumerate(findings):
  # 派 Agent tool call with run_in_background: true
  # 把 finding 全文 + prompt 模板拼好
  # 收集 JSON 返回, 写回 finding 末尾
done
```

---

## Anti-pattern 防御

- ❌ verifier 找不到反例就 verified=false (跟 /full-stack-audit 反向) — **必须 verified=true**
- ❌ refuted_reason < 2 句 — 强制 ≥ 2 句, 短了拒绝接受
- ❌ refuted=true 直接删原段 — **保留原段 + 加 refuted 标记**
- ❌ verifier 全量跑 (252 条) — **必须按 --max-verifier 截断**
- ❌ verifier 失败静默跳过 — 默认 verified=true + confidence=low, 警告不阻塞