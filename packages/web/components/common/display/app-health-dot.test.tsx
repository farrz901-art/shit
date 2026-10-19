// HealthDot 测试 (Task 27, 2026-06-12 redesign, 2026-06-15 改用 BreathingDot)
// 模式: useSWR → useQuery, HealthDot 内部已经自包 QueryClientProvider.
// Mock healthApi.fetchDifyHealth, 测 ok / not-ok 两种状态的颜色.
// 改用 BreathingDot 后, testid 容器是外层 span (relative flex), color class 落到内层 dot 上
// 所以断言改成查 root.innerHTML 是否包含目标 bg-status-* 类
import { describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { HealthDot } from "./app-health-dot";

vi.mock("@/lib/api/health", () => ({
  fetchDifyHealth: vi.fn(),
}));

import { fetchDifyHealth } from "@/lib/api/health";

describe("HealthDot", () => {
  it("监控时显示绿色 dot (bg-status-success)", async () => {
    vi.mocked(fetchDifyHealth).mockResolvedValue({ ok: true });
    render(<HealthDot />);
    const dot = await screen.findByTestId("health-dot");
    // 等待 useQuery 拿到 mock 数据, isLoading 变 false → 颜色从 muted 切到 success
    // BreathingDot 双层结构: 外层容器 + 内层 ping + 内层实心 dot, 都查 innerHTML
    await waitFor(() => {
      expect(dot.innerHTML).toContain("bg-status-success");
    });
  });

  it("不可达时显示红色 dot (bg-status-error)", async () => {
    vi.mocked(fetchDifyHealth).mockResolvedValue({ ok: false });
    render(<HealthDot />);
    const dot = await screen.findByTestId("health-dot");
    await waitFor(() => {
      expect(dot.innerHTML).toContain("bg-status-error");
    });
  });
});
