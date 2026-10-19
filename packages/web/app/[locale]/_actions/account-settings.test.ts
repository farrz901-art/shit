// Account Settings Server Action 单测
// 覆盖: 纯函数校验 + server action 成功/失败路径
import { describe, expect, it, vi } from "vitest";
import { HTTP_BAD_REQUEST, HTTP_UNPROCESSABLE_ENTITY } from "@/const";
import { ApiError, NetworkError } from "@/lib/api/errors";

vi.mock("@/lib/api/config", () => ({ apiFetch: vi.fn() }));
vi.mock("@/lib/api/auth.server", () => ({
  serverAuthHeaders: vi.fn().mockResolvedValue({ authorization: "Bearer tok" }),
}));
vi.mock("next/cache", () => ({ revalidatePath: vi.fn() }));

import {
  changePasswordAction,
  deleteAvatarAction,
  requestDeletionAction,
  updateProfileAction,
  uploadAvatarAction,
} from "./account-settings";

const PROFILE_INIT = { error: null, ok: false };
const AVATAR_INIT = { avatarUrl: null, error: null, ok: false };
const DELETION_INIT = { error: null, expiresAt: null, ok: false, restoreUrl: null };

describe("updateProfileAction", () => {
  it("displayName 太短返回校验错误", async () => {
    const fd = new FormData();
    fd.append("display_name", "");
    const result = await updateProfileAction(PROFILE_INIT, fd);
    expect(result.ok).toBe(false);
  });

  it("成功返 ok=true", async () => {
    const { apiFetch } = await import("@/lib/api/config");
    vi.mocked(apiFetch).mockResolvedValue(undefined);
    const fd = new FormData();
    fd.append("display_name", "新昵称");
    const result = await updateProfileAction(PROFILE_INIT, fd);
    expect(result.ok).toBe(true);
  });

  it("ApiError 返错误", async () => {
    const { apiFetch } = await import("@/lib/api/config");
    vi.mocked(apiFetch).mockRejectedValue(new ApiError(HTTP_BAD_REQUEST, "保存失败"));
    const fd = new FormData();
    fd.append("display_name", "新昵称");
    const result = await updateProfileAction(PROFILE_INIT, fd);
    expect(result.ok).toBe(false);
    expect(result.error).toBe("保存失败");
  });

  it("NetworkError 返网络错误", async () => {
    const { apiFetch } = await import("@/lib/api/config");
    vi.mocked(apiFetch).mockRejectedValue(new NetworkError("连接失败"));
    const fd = new FormData();
    fd.append("display_name", "新昵称");
    const result = await updateProfileAction(PROFILE_INIT, fd);
    expect(result.ok).toBe(false);
    expect(result.error).toContain("无法连接");
  });
});

describe("uploadAvatarAction", () => {
  it("空文件返回错误", async () => {
    const fd = new FormData();
    fd.append("file", new File([], ""));
    const result = await uploadAvatarAction(AVATAR_INIT, fd);
    expect(result.ok).toBe(false);
    expect(result.error).toBe("请选择文件");
  });

  it("文件类型不支持返回错误", async () => {
    const fd = new FormData();
    fd.append("file", new File(["x"], "test.gif", { type: "image/gif" }));
    const result = await uploadAvatarAction(AVATAR_INIT, fd);
    expect(result.ok).toBe(false);
    expect(result.error).toContain("仅支持");
  });

  it("成功返 avatarUrl", async () => {
    const { apiFetch } = await import("@/lib/api/config");
    vi.mocked(apiFetch).mockResolvedValue({ avatar_url: "https://example.com/av.jpg" });
    const fd = new FormData();
    fd.append("file", new File(["x"], "test.png", { type: "image/png" }));
    const result = await uploadAvatarAction(AVATAR_INIT, fd);
    expect(result.ok).toBe(true);
    expect(result.avatarUrl).toBe("https://example.com/av.jpg");
  });

  it("ApiError 422 返图片无效", async () => {
    const { apiFetch } = await import("@/lib/api/config");
    vi.mocked(apiFetch).mockRejectedValue(new ApiError(HTTP_UNPROCESSABLE_ENTITY, ""));
    const fd = new FormData();
    fd.append("file", new File(["x"], "test.png", { type: "image/png" }));
    const result = await uploadAvatarAction(AVATAR_INIT, fd);
    expect(result.ok).toBe(false);
    expect(result.error).toContain("2MB");
  });
});

describe("deleteAvatarAction", () => {
  it("成功返 ok=true", async () => {
    const { apiFetch } = await import("@/lib/api/config");
    vi.mocked(apiFetch).mockResolvedValue(undefined);
    const result = await deleteAvatarAction();
    expect(result.ok).toBe(true);
  });

  it("失败返错误", async () => {
    const { apiFetch } = await import("@/lib/api/config");
    vi.mocked(apiFetch).mockRejectedValue(new Error("网络错误"));
    const result = await deleteAvatarAction();
    expect(result.ok).toBe(false);
  });
});

describe("changePasswordAction", () => {
  it("密码太短返回校验错误", async () => {
    const fd = new FormData();
    fd.append("current_password", "old");
    fd.append("new_password", "短");
    fd.append("confirm", "短");
    const result = await changePasswordAction(PROFILE_INIT, fd);
    expect(result.ok).toBe(false);
    expect(result.error).toContain("8");
  });

  it("两次密码不一致返回错误", async () => {
    const fd = new FormData();
    fd.append("current_password", "old12345");
    fd.append("new_password", "new12345");
    fd.append("confirm", "new99999");
    const result = await changePasswordAction(PROFILE_INIT, fd);
    expect(result.ok).toBe(false);
    expect(result.error).toContain("不一致");
  });

  it("成功返 ok=true", async () => {
    const { apiFetch } = await import("@/lib/api/config");
    vi.mocked(apiFetch).mockResolvedValue(undefined);
    const fd = new FormData();
    fd.append("current_password", "old12345");
    fd.append("new_password", "new12345");
    fd.append("confirm", "new12345");
    const result = await changePasswordAction(PROFILE_INIT, fd);
    expect(result.ok).toBe(true);
  });

  it("ApiError 返错误消息", async () => {
    const { apiFetch } = await import("@/lib/api/config");
    vi.mocked(apiFetch).mockRejectedValue(new ApiError(HTTP_BAD_REQUEST, "当前密码错误"));
    const fd = new FormData();
    fd.append("current_password", "wrong");
    fd.append("new_password", "new12345");
    fd.append("confirm", "new12345");
    const result = await changePasswordAction(PROFILE_INIT, fd);
    expect(result.error).toBe("当前密码错误");
  });
});

describe("requestDeletionAction", () => {
  it("空密码返回错误", async () => {
    const fd = new FormData();
    fd.append("current_password", "");
    fd.append("confirm_text", "我要注销");
    const result = await requestDeletionAction(DELETION_INIT, fd);
    expect(result.ok).toBe(false);
  });

  it("确认文本不对返回错误", async () => {
    const fd = new FormData();
    fd.append("current_password", "pass12345");
    fd.append("confirm_text", "我不注销");
    const result = await requestDeletionAction(DELETION_INIT, fd);
    expect(result.ok).toBe(false);
  });

  it("成功返 restoreUrl", async () => {
    const { apiFetch } = await import("@/lib/api/config");
    vi.mocked(apiFetch).mockResolvedValue({
      restore_url: "https://example.com/restore",
      expires_at: "2026-07-01T00:00:00Z",
    });
    const fd = new FormData();
    fd.append("current_password", "pass12345");
    fd.append("confirm_text", "我要注销");
    const result = await requestDeletionAction(DELETION_INIT, fd);
    expect(result.ok).toBe(true);
    expect(result.restoreUrl).toBe("https://example.com/restore");
  });
});
