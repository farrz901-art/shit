// JSON 解析: 校验 items 数组, 错误行收集
import { z } from "zod";

const ItemSchema = z.object({
  payload: z.record(z.string(), z.unknown()),
  target: z.enum(["dify", "neo4j"]),
  type: z.string(),
});

const JsonSchema = z.object({
  items: z.array(ItemSchema),
});

/**
 * 解析 JSON 文本, 校验 items 数组格式
 * @param text  JSON 字符串
 * @returns     包含 items 和 errors 的解析结果
 *
 * 调用边界:
 *   @shared  前后端通用 (纯函数)
 */
export const parseJsonText = (
  text: string,
): {
  items: z.infer<typeof ItemSchema>[];
  errors: string[];
} => {
  let data: unknown = null;
  try {
    data = JSON.parse(text);
  } catch (error) {
    return { errors: [`JSON 解析失败: ${String(error)}`], items: [] };
  }
  const result = JsonSchema.safeParse(data);
  if (!result.success) {
    return {
      errors: result.error.issues.map((issue) => `${issue.path.join(".")}: ${issue.message}`),
      items: [],
    };
  }
  return { errors: [], items: result.data.items };
};
