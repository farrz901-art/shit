// 文件上传 → Dify createDocumentByText (v1 演示, 读 text)
// 实际 multipart 走 by_file; 后续 PR 升级
import { type NextRequest, NextResponse } from "next/server";
import { DifyDatasets } from "@/lib/api/dify-datasets";

/**
 * 文件上传至 Dify BFF: POST /api/knowledge/documents/upload
 * @param req - 请求对象 (含 multipart form)
 * @returns Response
 * @client-bff
 */
export const POST = async (req: NextRequest) => {
  const form = await req.formData();
  const datasetId = form.get("dataset_id") as string | null;
  const file = form.get("file") as File | null;
  if (!datasetId || !file) {
    return NextResponse.json({ error: "dataset_id / file 必填" }, { status: 400 });
  }
  try {
    const text = await file.text();
    const doc = await DifyDatasets.createDocumentByText(datasetId, file.name, text, "high_quality");
    return NextResponse.json({ doc });
  } catch (error) {
    return NextResponse.json({ error: String(error) }, { status: 502 });
  }
};
