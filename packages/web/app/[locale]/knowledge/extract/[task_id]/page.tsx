// 抽取进度页 RSC entry (2026-07-01 markdown extract KG PR4 v3)
// (2026-07-03) Next 16: params 是 Promise, 必须 await, 否则 client 拿 undefined → fetch /tasks/undefined.
// 拆 RSC entry 后, 这里只负责 await params, 业务逻辑在 _components/task-progress-client.tsx.
import { TaskProgressClient } from "./_components/task-progress-client";

/**
 * 抽取进度页路由参数
 * @property params - 路由参数 (含 task_id)
 */
interface PageProps {
  params: Promise<{ task_id: string }>;
}

/**
 * TaskProgressPage - 抽取进度页 RSC 入口
 * @param props.params - 路由参数 Promise
 * @server-only
 */
export default async function TaskProgressPage({ params }: PageProps) {
  const { task_id } = await params;
  return <TaskProgressClient taskId={task_id} />;
}
