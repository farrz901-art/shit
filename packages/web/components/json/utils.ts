/** JSON 序列化缩进空格数 */
export const JSON_INDENT_SPACES = 2;

/**
 * 安全序列化 JSON, 失败返回 null
 * 处理循环引用 / undefined 等 JSON.stringify 可能抛出的场景
 */
export const safeStringify = (data: unknown): string | null => {
  try {
    const result = JSON.stringify(data, null, JSON_INDENT_SPACES);
    // JSON.stringify 对 undefined / function / symbol 返回 undefined 而非抛错
    if (result === undefined) {
      return null;
    }
    return result;
  } catch {
    return null;
  }
};

/**
 * 统一 CSS 维度解析: 数字转 px, 字符串原样
 * @example resolveCssDimension(100) → "100px"
 * @example resolveCssDimension("500px") → "500px"
 */
export const resolveCssDimension = (val: string | number): string => {
  if (typeof val === "number") {
    return `${val}px`;
  }
  return val;
};
