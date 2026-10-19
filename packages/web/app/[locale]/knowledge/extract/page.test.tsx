// 列表页 RSC entry 守门测试 (2026-07-03)
// 验证: page.tsx 渲染 <TasksListClient />, 不 throw
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("server-only", () => ({}));

describe("ExtractTasksPage (RSC entry)", () => {
  afterEach(() => vi.restoreAllMocks());

  it("渲染 <TasksListClient /> 桩, 不抛", async () => {
    // mock list 容器避免所有子组件依赖
    // oxlint-disable-next-line arrow-body-style -- JSX 在 mock factory 内需要 block
    vi.mock("./_components/tasks-list-client", () => ({
      default: () => <div data-testid="tasks-list-client-stub">stub</div>,
    }));

    const mod = await import("./page");
    const page = mod.default;
    const element = page();

    // render 不 throw 即为通过
    expect(element).toBeTruthy();
  });
});
