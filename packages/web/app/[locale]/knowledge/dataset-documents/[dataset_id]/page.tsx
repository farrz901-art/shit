// RSC: server 端拉 datasets 列表 + QA 文档列表, 传 Promise 给 DatasetDocumentsTable (use(promise) 模式).
// (2026-06-14) 改: 去 Promise.all + await, 传两个 Promise + Suspense fallback
// (2026-06-15) fetchDatasets 改走 rscGet: 自动解 Dify { data, has_more, total, limit, page } 包装,
//   跟 sibling /knowledge/datasets/page.tsx 对齐. 直 apiFetch 会被 Dify 包装坑成 datasets.find is not a function.
// (2026-06-23) 迁移: PageGuard + getMyPermissions → GuardPage
import { fetchDatasets, type QAListResponse } from "@/lib/api/knowledge";
import { DataTableSkeleton } from "@/components/common/table/data-table-skeleton";
import { DatasetDocumentsTable } from "./_components/dataset-documents-table";
import { DifyDatasets } from "@/lib/api/dify-datasets";
import { GuardPage } from "@/components/auth/guard-page";
import { Suspense } from "react";
import { ZERO } from "@/const/index";

/** dynamic - 强制 dynamic 渲染, 走 cookie 每次请求取最新
 * @server-only
 */
export const dynamic = "force-dynamic";

// 从文档内容中提取 Q&A
/** extractQAFromContent - 从文档内容中提取 question 和 answer
 * @param content 文档内容
 * @returns 提取的 question 和 answer
 * @shared
 */
const extractQAFromContent = (content: string): { answer: string; question: string } => {
  const qMatch = content.match(/^Q:\s*(?<question>.+?)(?:\n|$)/);
  const aMatch = content.match(/^A:\s*(?<answer>.+?)(?:\n|$)/m);
  return {
    answer: aMatch?.groups?.answer ?? "",
    question: qMatch?.groups?.question ?? "",
  };
};

// 提取单个 QA 文档的解析逻辑（减少 fetchQADocuments 的语句数）
/** parseQADocument - 解析单个 QA 文档, 提取 question + answer
 * @param datasetId 数据集 ID
 * @param doc 文档对象 (含 id, indexing_status, name)
 * @returns 解析后的 QA 条目
 * @server-only
 */
const parseQADocument = async (
  datasetId: string,
  doc: { id: string; indexing_status: string; name: string },
) => {
  let question = "";
  let answer = "";
  try {
    const segments = await DifyDatasets.listSegments(datasetId, doc.id);
    const seg = segments.data?.[ZERO];
    if (seg?.content) {
      const { answer: extractedAnswer, question: extractedQuestion } = extractQAFromContent(
        seg.content,
      );
      question = extractedQuestion;
      answer = extractedAnswer;
    }
  } catch {
    /* Ignore */
  }
  return {
    answer,
    id: doc.id,
    indexing_status: doc.indexing_status,
    name: doc.name,
    question,
  };
};

/** fetchQADocuments - 获取指定数据集的 QA 文档列表
 * @param datasetId 数据集 ID
 * @returns QA 文档列表响应
 * @server-only
 */
const fetchQADocuments = async (datasetId: string): Promise<QAListResponse> => {
  const out = await DifyDatasets.listDocuments(datasetId);
  const qaDocs = out.data.filter((doc) => doc.name.startsWith("qa-"));

  const items = await Promise.all(qaDocs.map(async (doc) => parseQADocument(datasetId, doc)));

  return { items };
};

/** DatasetDocumentsPage - 数据集文档列表 RSC 页面, 并行 fetch 数据集和 QA 文档
 * @param params 路由参数 (含 dataset_id)
 * @server-only
 */
export default async function DatasetDocumentsPage({
  params,
}: {
  params: Promise<{ dataset_id: string }>;
}) {
  const { dataset_id } = await params;

  // 两个 fetch 同时启动, 不 await — Suspense 边界控制 loading
  const datasetsPromise = fetchDatasets();
  const qaPromise = fetchQADocuments(dataset_id);

  return (
    <GuardPage pageKey="knowledge">
      <Suspense fallback={<DataTableSkeleton columns={4} rows={8} />}>
        <DatasetDocumentsTable
          datasetId={dataset_id}
          datasetsPromise={datasetsPromise}
          qaPromise={qaPromise}
        />
      </Suspense>
    </GuardPage>
  );
}
