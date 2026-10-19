# 审核系统使用文档

## 给提交者

提交后跳到 `/submissions` "我提交的" tab 看自己提交的状态:

- **待审** (黄色 badge): 等待 admin 批准
- **已批 + 已写入** (绿色 badge): 成功写入知识库
- **已批 + 写库失败** (红色 badge): admin 会重试, 不需操作, 可展开看错误
- **被拒** (红色 badge): 展开看拒绝原因 (预设 6 类 + 补充), 修正后重新提交

## 给 admin

进 `/submissions` 切 "全部待审" tab:

1. 展开行看完整内容 (qa / triple / batch / optimize)
2. 1 键批准 (立即触发 BackgroundTask 写入 Dify/Neo4j)
3. 拒绝: 选预设原因 (重复内容 / 质量问题 / 信息不完整 / 分类错误 / 格式问题 / 其他), 选 "其他" 时补充说明
4. 失败项 1 键重试

## 状态字段

每个审核项有 2 个独立状态:

- `review_status`: `pending` / `approved` / `rejected` (admin 决定的, 3 状态)
- `apply_status`: `none` / `applied` / `failed` (系统写入结果, 3 状态)

终态组合: `(approved, applied)` 成功 / `(rejected, none)` 拒绝 / 其他都是中间态可重试或观察。
