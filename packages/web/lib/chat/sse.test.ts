// 字符串流切块器测试 (2026-07-01 简化版)
// 字节→文本由上游 TextDecoderStream 处理, 本层只做 \n\n 切分
import { describe, expect, it } from "vitest";
import { parseSseBlocks } from "./sse";

const ABORT_DELAY_MS = 10;

const makeStream = (text: string): ReadableStream<string> =>
  new ReadableStream<string>({
    start(ctrl) {
      ctrl.enqueue(text);
      ctrl.close();
    },
  });

const makeMultiStream = (chunks: string[]): ReadableStream<string> =>
  new ReadableStream<string>({
    start(ctrl) {
      for (const chunk of chunks) {
        ctrl.enqueue(chunk);
      }
      ctrl.close();
    },
  });

const collect = async <TItem>(asyncIterable: AsyncIterable<TItem>): Promise<TItem[]> => {
  const out: TItem[] = [];
  for await (const val of asyncIterable) {
    out.push(val);
  }
  return out;
};

describe("parseSseBlocks", () => {
  it("单块完整到达 → yield 一次", async () => {
    const stream = makeStream('event: message\ndata: {"x":1}\n\n');
    const blocks = await collect(parseSseBlocks(stream, new AbortController().signal));
    expect(blocks).toEqual(['event: message\ndata: {"x":1}']);
  });

  it(String.raw`多块按 \n\n 切分`, async () => {
    const stream = makeStream("data: a\n\ndata: b\n\ndata: c\n\n");
    const blocks = await collect(parseSseBlocks(stream, new AbortController().signal));
    expect(blocks).toEqual(["data: a", "data: b", "data: c"]);
  });

  it("跨 chunk 切分不丢不重 (上游分块边界模拟)", async () => {
    // 字符串层切块边界: 一段 buffer 切碎分多次 enqueue
    const stream = makeMultiStream(["data: hel", "lo\n\n"]);
    const blocks = await collect(parseSseBlocks(stream, new AbortController().signal));
    expect(blocks).toEqual(["data: hello"]);
  });

  it("signal.aborted → 抛 AbortError", async () => {
    const ac = new AbortController();
    const never = new ReadableStream<string>({
      start() {
        /* Never closes */
      },
    });
    ac.abort();
    await expect(async () => {
      for await (const ignoredValue of parseSseBlocks(never, ac.signal)) {
        void ignoredValue;
      }
    }).rejects.toThrow(/aborted/);
  });

  it("iteration 阻塞中触发 abort → 立即抛 AbortError (cancel reader)", async () => {
    // 模拟"流永远不结束 + 用户中途 stop"的场景:
    // 旧 ChatShell 靠 ac.signal.addEventListener("abort", () => reader.cancel())
    // 打断阻塞 read(), parseSseBlocks 必须自带这个行为, 否则 ChatShell 点 stop 卡死
    const ac = new AbortController();
    const never = new ReadableStream<string>({
      start() {
        /* Never closes */
      },
    });
    setTimeout(() => ac.abort(), ABORT_DELAY_MS);
    await expect(async () => {
      for await (const ignoredValue of parseSseBlocks(never, ac.signal)) {
        void ignoredValue;
      }
    }).rejects.toThrow(/aborted/);
  });
});
