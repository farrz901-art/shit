---
name: feedback-no-emoji-use-lucide-icons
description: 项目中禁止使用 emoji，必须用 Lucide React 图标替代
metadata: 
  node_type: memory
  type: feedback
  originSessionId: eec4f205-4669-4734-b77f-77c2e0b18e11
---

项目中禁止使用 emoji 字符（📝📄🔗📦📥💾👋 等），必须用 Lucide React 图标替代。

**原因**：
- Emoji 在不同操作系统/浏览器渲染不一致
- 不支持无障碍访问（屏幕阅读器读不出）
- 样式无法控制（颜色/大小/动画）

**How to apply**:
- 安装：`bunx shadcn@latest add lucide-react`
- 使用：`import { IconName } from "lucide-react"` 然后 `<IconName className="h-4 w-4" />`
- 常用图标对照：
  - 📝 → `<MessageSquare />` (写消息)
  - 📄 → `<FileText />` (文件)
  - 🔗 → `<Network />` (网络/关系)
  - 📦 → `<Package />` (包/批量)
  - 📥 → `<Download />` (下载)
  - 💾 → `<Save />` (保存)
  - 👋 → `<Sparkles />` (招呼/欢迎)
  - ✕ → `<X />` (关闭/删除)
  - ▾ → `<ChevronDown />` (展开)
