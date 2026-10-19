// 知识图谱任务列表页 RSC entry (2026-07-03)
// 列表 + tab 切换 + 弹框创建 + 重跑. 启动页 (原 page.tsx) 已删, 改为 _components/extract-create-dialog.tsx 弹框.
import TasksListClient from "./_components/tasks-list-client";

/**
 * ExtractTasksPage - 知识图谱任务列表页 RSC entry
 * @server-only
 */
export default function ExtractTasksPage() {
  return <TasksListClient />;
}
