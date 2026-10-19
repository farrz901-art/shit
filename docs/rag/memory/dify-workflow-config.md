# Dify Chatflow 工作流配置: 接入长期记忆

> **作用**: 让 Dify Chatflow 在跟用户对话时, 自动接收前端 dify.ts 注入的 `memory_context` (含相关历史记忆), 并拼到 LLM 的 System Prompt 里.

**前提**: 长期记忆 FastAPI 端点 `/api/memory/search` 已经返回相关记忆 (项目本地后端跑在 :8000), 前端 `withMemoryHooks` 装饰器已自动把 `inputs.memory_context` 字段塞进 Dify 请求.

**作用域**: 每个 Dify Chatflow 应用都要配一次 (用同一份模板).

---

## 步骤

### 1. 打开应用编排页

Dify 控制台 → 你的 Chatflow 应用 → "编排" 标签.

### 2. 配置"开始"节点的输入变量

点 "开始" 节点 → 右侧 "输入变量" 区域:

- 如果列表里**已经有** `memory_context` 字段 (类型 String): 把"必填"改为**否** (让它可空, 不传也不报错).
- 如果**没有**: 手动添加 → 字段名 `memory_context`, 类型 `String`, 必填 `否`.

> **为什么要"必填=否"**: 用户首轮对话没历史记忆时, 前端不调 search / search 返空, `memory_context` 会是空串. Dify 必填会让首轮 422.

### 3. 改 LLM 节点的 System Prompt

点 LLM 节点 → "SYSTEM" 提示词模板 → 末尾追加:

```
{{#memory_context}}
用户历史记忆:
{{memory_context}}
{{/memory_context}}
```

#### 模板语法说明

- `{{#var}}...{{/var}}` 是 Dify 的**条件块**: 变量**非空**才渲染中间的内容; 变量为空时整块消失.
- 用户首轮没记忆时 `memory_context=""`, 整块不渲染, 提示词保持原状, 无副作用.
- 用户有记忆时, 块渲染成 "用户历史记忆:\n<记忆内容>", 拼到 SYSTEM 末尾, LLM 能看到.

#### 示例效果

有记忆时 LLM 看到的 SYSTEM 末尾:
```
你是一个乐于助人的助手.

用户历史记忆:
- 用户叫张三
- 用户住北京
```

没记忆时 (首轮):
```
你是一个乐于助人的助手.
```

### 4. 保存 + 发布

点右上角 "发布" → 确认.

### 5. 验证 (手动测试)

1. 在前端 dev 界面开新对话
2. 发 "我叫张三, 住北京"
3. 等流结束
4. 开新对话 (Dify 端: 同账号新 conversation)
5. 发 "我叫什么名字, 住哪"
6. 期待: LLM 答 "你叫张三, 住北京" (用了 memory_context 里的事实)

如果没成功:
- 检查 Dify 工作流 SYSTEM 模板是否正确 (注意 `{{#` 和 `{{/` 是条件块, 不是普通变量引用)
- 检查 "开始" 节点的 `memory_context` 是否设了"必填=否"
- 浏览器 devtools 看 `/api/chat/messages` 请求 body 是否含 `inputs.memory_context`
- 后端日志看 `grep memory` 是否有 `search failed` / `add failed` warning

---

## 可选: 改 LLM 抽取模型

事实抽取 (mem0.add 的 LLM 调用) 默认用 `MEM0_LLM_MODEL=gpt-4o-mini`. 想省钱可在 `.env.local` 改:

```bash
MEM0_LLM_MODEL=gpt-4o-mini          # 默认, 便宜
# 或
MEM0_LLM_MODEL=gpt-3.5-turbo         # 更便宜, 抽取质量略降
```

不需要改 Dify 端. 只改后端 .env, 重启 service 即生效.

---

## 常见问题

**Q: 多个 Chatflow 应用都要配?**
A: 是. 每个 Chatflow 都要走 Step 1-4 一次. 建议把这文档链接加到 Dify 应用描述里, 提醒维护者.

**Q: memory_context 注入到 LLM 的哪个位置?**
A: 拼到 SYSTEM Prompt 末尾, 在 USER 消息之前. LLM 视为"系统级背景信息", 不会跟用户当前问题混淆.

**Q: 记忆里出现错误信息怎么办?**
A: 用户在对话中纠正即可. mem0 的 `infer=True` 模式下, 重新 add 同一 user_id 的对话时, LLM 会自动判断新事实跟旧记忆冲突, 触发 UPDATE/DELETE. 不需要用户手动清记忆.
