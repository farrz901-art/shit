// Retriever 自测: 用问题调 Dify retrieve, 返 top N
import { type NextRequest, NextResponse } from "next/server";
import { DifyDatasets } from "@/lib/api/dify-datasets";
import { THREE } from "@/const";

/**
 * Retriever 自测 BFF: POST /api/knowledge/qa/retrieve
 * @param req - 请求对象
 * @returns Response
 * @client-bff
 */
export const POST = async (req: NextRequest) => {
  const {
    dataset_id,
    question,
    top_k = THREE,
  } = (await req.json()) as {
    dataset_id: string;
    question: string;
    top_k?: number;
  };
  if (!dataset_id || !question) {
    return NextResponse.json({ error: "dataset_id / question 必填" }, { status: 400 });
  }
  try {
    const out = await DifyDatasets.retrieve(dataset_id, question, top_k);
    return NextResponse.json(out);
  } catch (error) {
    return NextResponse.json({ error: String(error) }, { status: 502 });
  }
};
