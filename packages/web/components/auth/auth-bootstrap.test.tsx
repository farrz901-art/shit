import { beforeEach, describe, expect, it, vi } from "vitest";
import { waitFor } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { AuthBootstrap } from "./auth-bootstrap";

// Mock createAnonToken (隔离网络)
vi.mock("@/lib/api/auth", () => ({
  createAnonToken: vi.fn(),
}));

import { createAnonToken } from "@/lib/api/auth";

const mockedCreateAnonToken = vi.mocked(createAnonToken);

beforeEach(() => {
  mockedCreateAnonToken.mockReset();
  // 清 cookie: document.cookie 没法真清, 但能 set 过期
  document.cookie = "rag_user_token=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/";
  // 清 localStorage (jsdom 实现的)
  localStorage.clear();
});

describe("AuthBootstrap", () => {
  it("serverSession=true → 跳过 anon 调用", async () => {
    render(<AuthBootstrap serverSession />);
    // eslint-disable-next-line no-magic-numbers -- 10ms 等 useEffect 异步执行
    await new Promise((resolve) => setTimeout(resolve, 10));
    expect(mockedCreateAnonToken).not.toHaveBeenCalled();
  });

  it("无 cookie 无 localStorage → 首次访问, 调 createAnonToken", async () => {
    render(<AuthBootstrap />);
    await waitFor(() => {
      expect(mockedCreateAnonToken).toHaveBeenCalled();
    });
  });

  it("无 cookie 但有 localStorage rag_was_logged_in → 真账号丢失, 不调 anon", async () => {
    localStorage.setItem("rag_was_logged_in", "1");
    render(<AuthBootstrap />);
    // eslint-disable-next-line no-magic-numbers -- 10ms 等 useEffect 异步执行
    await new Promise((resolve) => setTimeout(resolve, 10));
    expect(mockedCreateAnonToken).not.toHaveBeenCalled();
  });

  it("POST /api/auth/anon 抛错时静默, 不抛", async () => {
    mockedCreateAnonToken.mockRejectedValue(new Error("network"));
    expect(() => render(<AuthBootstrap />)).not.toThrow();
    await waitFor(() => {
      expect(mockedCreateAnonToken).toHaveBeenCalled();
    });
  });

  it("返回 null, 不渲染任何 DOM (effect-only 组件)", () => {
    const { container } = render(<AuthBootstrap />);
    expect(container.firstChild).toBeNull();
  });
});
