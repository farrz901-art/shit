// 轻量 logger 测试 (2026-06-23)
// Validate: 时间戳格式 / 级别前缀 / meta 序列化 / debug 开关 / prod 模式无 ANSI
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { log } from "./log";

// HH:MM:SS.mmm; 不锚定行首 (dev 模式有 ANSI 颜色码前缀 \x1b[36m)
const TIME_PATTERN = /\d{2}:\d{2}:\d{2}\.\d{3}/;
const ANSI_ESCAPE = "\x1b[";
const FIRST_CALL = 0;
const FIRST_ARG = 0;
const ONCE = 1;
const SAMPLE_ID = 42;

type Spy = ReturnType<typeof vi.spyOn>;

// 抽出 spy 装拆: 把 3 let + beforeEach + afterEach 5 个语句合并成 1 个 const
// (oxlint max-statements ≤ 10, 顶层 describe 7 个 it 已经吃满, spy 必须挪出去)
const setupConsoleSpies = (): { logSpy: () => Spy; warnSpy: () => Spy; errorSpy: () => Spy } => {
  let logSpy: Spy = vi.fn() as unknown as Spy;
  let warnSpy: Spy = vi.fn() as unknown as Spy;
  let errorSpy: Spy = vi.fn() as unknown as Spy;
  beforeEach(() => {
    logSpy = vi.spyOn(console, "log").mockImplementation(() => undefined);
    warnSpy = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    errorSpy = vi.spyOn(console, "error").mockImplementation(() => undefined);
  });
  afterEach(() => {
    logSpy.mockRestore();
    warnSpy.mockRestore();
    errorSpy.mockRestore();
    vi.unstubAllEnvs();
  });
  return { errorSpy: () => errorSpy, logSpy: () => logSpy, warnSpy: () => warnSpy };
};

describe("log facade", () => {
  const spies = setupConsoleSpies();

  it("info 带时间戳 + 级别前缀", () => {
    log.info("hello");
    const out = spies.logSpy().mock.calls[FIRST_CALL]?.[FIRST_ARG] as string;
    expect(out).toMatch(TIME_PATTERN);
    expect(out).toContain("INFO");
    expect(out).toContain("hello");
  });

  it("meta 序列化为 JSON 后缀", () => {
    log.info("user login", { id: SAMPLE_ID, role: "admin" });
    const out = spies.logSpy().mock.calls[FIRST_CALL]?.[FIRST_ARG] as string;
    expect(out).toContain('"id":42');
    expect(out).toContain('"role":"admin"');
  });

  it("warn → console.warn, error → console.error", () => {
    log.warn("warning message");
    log.error("error message");
    expect(spies.warnSpy()).toHaveBeenCalledTimes(ONCE);
    expect(spies.errorSpy()).toHaveBeenCalledTimes(ONCE);
    expect(spies.warnSpy().mock.calls[FIRST_CALL]?.[FIRST_ARG]).toMatch(TIME_PATTERN);
    expect(spies.errorSpy().mock.calls[FIRST_CALL]?.[FIRST_ARG]).toContain("error message");
  });

  it("debug 在非 production 默认打印", () => {
    // Vitest 默认 NODE_ENV=test (不是 "production"), 所以 debug 不被关
    log.debug("debug msg");
    expect(spies.logSpy()).toHaveBeenCalled();
  });

  it("debug 在 production 模式被关掉", () => {
    vi.stubEnv("NODE_ENV", "production");
    spies.logSpy().mockClear();
    log.debug("debug msg");
    expect(spies.logSpy()).not.toHaveBeenCalled();
  });

  it("production 模式无 ANSI 颜色码 (容器日志兼容性)", () => {
    vi.stubEnv("NODE_ENV", "production");
    spies.logSpy().mockClear();
    log.info("plain");
    const out = spies.logSpy().mock.calls[FIRST_CALL]?.[FIRST_ARG] as string;
    expect(out).not.toContain(ANSI_ESCAPE);
    expect(out).toContain("INFO");
  });

  it("非 production 模式带 ANSI 颜色码 (终端可读性)", () => {
    vi.stubEnv("NODE_ENV", "development");
    spies.logSpy().mockClear();
    log.info("colorful");
    const out = spies.logSpy().mock.calls[FIRST_CALL]?.[FIRST_ARG] as string;
    expect(out).toContain(ANSI_ESCAPE);
  });
});
