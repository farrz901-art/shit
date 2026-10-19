// /output 专属 layout smoke 测试:
// 1) 透传 children
// 2) 提供 QueryClient context (子组件 useQuery 能正常返回数据, 不抛 "No QueryClient set")
// 3) 同一 layout 实例下 QueryClient 单例 (re-render 不丢 cache)
import { act, screen, waitFor } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { describe, expect, it } from "vitest";
import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import OutputLayout from "./layout";

const ZERO = 0;
const ONE = 1;
const MIN_RENDERS = 3;
const FIRST_INDEX = 0;

const getStableLabel = (current: unknown, first: unknown): string => {
  if (current === first) {
    return "stable";
  }
  return "new";
};

// 哨兵组件: 在 layout 包裹下, 调 useQuery 拿 queryClient.
// 如果 layout 没真正提供 QueryClientProvider, 这里会抛 "No QueryClient set".
const QueryProbe = ({ signal }: { signal: { client: unknown; observed: unknown[] } }) => {
  const qc = useQueryClient();
  const { data } = useQuery({
    enabled: true,
    queryFn: () => Promise.resolve("smoke-value"),
    queryKey: ["smoke", "key"],
  });
  // 把拿到的 queryClient 暴露给测试断言; 多次 render 拿到的应是同一实例.
  signal.client = qc;
  useEffect(() => {
    signal.observed.push(qc);
  }, [qc, signal]);
  return <div data-testid="probe-data">{data ?? "pending"}</div>;
};

describe("OutputLayout (B 档 RQ Provider)", () => {
  it("透传 children 渲染", () => {
    render(
      <OutputLayout>
        <span data-testid="child">child-content</span>
      </OutputLayout>,
    );
    expect(screen.getByTestId("child")).toHaveTextContent("child-content");
  });

  it("包了 QueryClientProvider → 子组件 useQuery 能正常返回数据", async () => {
    const signal: { client: unknown; observed: unknown[] } = { client: null, observed: [] };
    render(
      <OutputLayout>
        <QueryProbe signal={signal} />
      </OutputLayout>,
    );
    await waitFor(() => {
      expect(screen.getByTestId("probe-data")).toHaveTextContent("smoke-value");
    });
    // 哨兵拿到非 null queryClient 才是 context 真正生效的证据
    expect(signal.client).not.toBeNull();
  });

  const RerenderingProbe = ({ signal }: { signal: { client: unknown; observed: unknown[] } }) => {
    const qc = useQueryClient();
    const [, setN] = useState(ZERO);
    if (signal.client === null) {
      signal.client = qc;
    }
    signal.observed.push(qc);
    return (
      <div data-testid="probe-stable">
        <button type="button" onClick={() => setN((x) => x + ONE)} data-testid="force-rerender">
          rerender
        </button>
        <span>{getStableLabel(qc, signal.client)}</span>
      </div>
    );
  };

  it("同一 layout 实例多次 render 共享同一个 QueryClient 单例 (useState 工厂)", async () => {
    // 模拟同一 layout 组件被多次 render (e.g. parent state 变化).
    // 如果 QueryClient 是 useState 工厂创建的, 整个 layout 生命周期内应是同一实例.
    // 策略: 让 Probe 自己 setState 触发 re-render, 每次 render 拿到的 queryClient
    // 都跟第一次相同, 证明 layout 内的 QueryClient 实例没被重建.
    const signal: { client: unknown; observed: unknown[] } = { client: null, observed: [] };
    render(
      <OutputLayout>
        <RerenderingProbe signal={signal} />
      </OutputLayout>,
    );
    // 触发 2 次 re-render, 每次都 await act 避免异步警告
    const btn = screen.getByTestId("force-rerender");
    await act(async () => {
      btn.click();
    });
    await act(async () => {
      btn.click();
    });
    // 至少 3 次 render (初次 + 2 次 click)
    expect(signal.observed.length).toBeGreaterThanOrEqual(MIN_RENDERS);
    // 所有 render 拿到的 queryClient 都是同一引用
    const first = signal.observed[FIRST_INDEX];
    for (const qc of signal.observed) {
      expect(qc).toBe(first);
    }
    expect(screen.getByText("stable")).toBeInTheDocument();
  });
});
