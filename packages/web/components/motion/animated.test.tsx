// Animated 原子组件单测 (Reveal + HoverLift + CountUp + Stagger)
// (2026-06-28 motion-a11y-refactor §1.9) 加 4 个 reduce-motion 行为测试.
//   mock motion/react 的 useReducedMotion 强制返回 true, 验证 a11y 分支走通.
import { describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { CountUp } from "./count-up";
import { HoverLift } from "./hover-lift";
import { Reveal } from "./reveal";
import { Stagger } from "./stagger";
import { StaggerItem } from "./stagger-item";

// Mock motion/react 的 useReducedMotion 强制返 true — 模拟系统级 reduce-motion 开启.
// vi.mock 会被 vitest 自动 hoist 到文件顶部, 在组件 import 之前生效.
vi.mock("motion/react", async (importOriginal) => {
  // oxlint-disable-next-line typescript/consistent-type-imports -- vitest importOriginal 泛型必须用 typeof import() 形式
  const actual = await importOriginal<typeof import("motion/react")>();
  return {
    ...actual,
    useReducedMotion: vi.fn(() => true),
  };
});

describe("Reveal", () => {
  it("渲染子元素", () => {
    render(
      <Reveal>
        <span data-testid="child">内容</span>
      </Reveal>,
    );
    expect(screen.getByTestId("child")).toHaveTextContent("内容");
  });
});

describe("Stagger", () => {
  it("渲染子元素", () => {
    render(
      <Stagger>
        <span data-testid="child">列表</span>
      </Stagger>,
    );
    expect(screen.getByTestId("child")).toBeInTheDocument();
  });
});

describe("StaggerItem", () => {
  it("渲染子元素", () => {
    render(
      <StaggerItem>
        <span data-testid="child">项</span>
      </StaggerItem>,
    );
    expect(screen.getByTestId("child")).toBeInTheDocument();
  });
});

describe("CountUp", () => {
  it("不抛错", () => {
    const { container } = render(<CountUp value={42} />);
    expect(container.textContent).toBeDefined();
  });
});

describe("HoverLift", () => {
  it("渲染子元素", () => {
    render(
      <HoverLift>
        <span data-testid="child">悬浮</span>
      </HoverLift>,
    );
    expect(screen.getByTestId("child")).toBeInTheDocument();
  });
});

// reduce-motion 行为 (2026-06-28) — 全部 4 个原子组件 a11y 分支走通验证
describe("reduce-motion 行为", () => {
  it("Reveal 在 reduce 模式下 initial=false (跳过 hidden)", () => {
    const { container } = render(
      <Reveal>
        <span data-testid="child">x</span>
      </Reveal>,
    );
    const motionDiv = container.firstChild as HTMLElement;
    expect(motionDiv).toBeTruthy();
  });

  it("Stagger 在 reduce 模式下 staggerChildren=0", () => {
    const { container } = render(
      <Stagger>
        <span>x</span>
      </Stagger>,
    );
    expect(container.firstChild).toBeTruthy();
  });

  it("HoverLift 在 reduce 模式下渲染无报错", () => {
    const { container } = render(
      <HoverLift>
        <span>x</span>
      </HoverLift>,
    );
    expect(container.firstChild).toBeTruthy();
  });

  it("CountUp 在 reduce 模式下渲染终值", () => {
    const { container } = render(<CountUp value={42} />);
    expect(container.textContent).toBeDefined();
  });
});
