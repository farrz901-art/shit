// SSE \n\n 切块器 (2026-07-01 简化版)
// 字节解码委托给上游 ReadableStream.pipeThrough(new TextDecoderStream())
// 只做 \n\n 切块, 不解析 JSON, 不做 data: 前缀剥离

const NOT_FOUND = -1;
const DELIMITER_LENGTH = 2;
const START_INDEX = 0;

/**
 * 解析 SSE \n\n 切块流, 生成纯文本块
 * @param stream  可读字符串流 (已通过 TextDecoderStream 解码)
 * @param signal  中止信号, 用于取消读取
 * @returns       异步生成 SSE 块字符串
 *
 * 调用边界:
 *   @shared  前后端通用 (纯函数)
 */
// eslint-disable-next-line max-statements -- 流解析核心逻辑, 拆分会破坏 reader/abort 生命周期
export const parseSseBlocks = async function* parseSseBlocks(
  stream: ReadableStream<string>,
  signal: AbortSignal,
): AsyncIterable<string> {
  const reader = stream.getReader();
  const onAbort = () => {
    reader.cancel().catch(() => {
      /* Ignore */
    });
  };
  signal.addEventListener("abort", onAbort, { once: true });
  let buffer = "";
  try {
    while (true) {
      if (signal.aborted) {
        await reader.cancel();
        throw new DOMException("aborted", "AbortError");
      }
      const { value, done } = await reader.read();
      if (done) {
        // 兜底: 阻塞 read() 被 abort 打断后可能直接返回 done, 仍要抛 AbortError
        if (signal.aborted) {
          throw new DOMException("aborted", "AbortError");
        }
        break;
      }
      buffer += value;
      let index = 0;
      while ((index = buffer.indexOf("\n\n")) !== NOT_FOUND) {
        const block = buffer.slice(START_INDEX, index);
        buffer = buffer.slice(index + DELIMITER_LENGTH);
        yield block;
      }
    }
  } finally {
    signal.removeEventListener("abort", onAbort);
    reader.releaseLock();
  }
};
