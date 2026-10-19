// VoiceRecorder 组件单测 (mock MediaRecorder)
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { VoiceRecorder } from "./voice-recorder";

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => key,
  NextIntlClientProvider: ({ children }: { children: React.ReactNode }) => children,
}));
vi.mock("sonner", () => ({ toast: { error: vi.fn() } }));

// Stub MediaRecorder
class MockMediaRecorder {
  state = "inactive";
  ondataavailable: ((event: any) => void) | null = null;
  onstop: (() => void) | null = null;
  start() {
    this.state = "recording";
  }
  stop() {
    this.state = "inactive";
    this.onstop?.();
  }
  static isTypeSupported(_type: string) {
    return true;
  }
}
vi.stubGlobal("MediaRecorder", MockMediaRecorder);

describe("VoiceRecorder", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });
  afterEach(() => vi.unstubAllGlobals());

  it("渲染按钮", () => {
    render(<VoiceRecorder onRecorded={vi.fn()} />);
    expect(screen.getByTestId("voice-recorder")).toBeInTheDocument();
  });
});
