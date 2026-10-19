// ApiError / NetworkError 单测
import { HTTP_NOT_FOUND } from "@/const";
import { describe, expect, it } from "vitest";
import { ApiError, NetworkError, getErrorMessage } from "./errors";

describe("ApiError", () => {
  it("保存 status + message, name=ApiError", () => {
    const err = new ApiError(HTTP_NOT_FOUND, "Not Found");
    expect(err.status).toBe(HTTP_NOT_FOUND);
    expect(err.message).toBe("Not Found");
    expect(err.name).toBe("ApiError");
    expect(err).toBeInstanceOf(Error);
  });
});

describe("NetworkError", () => {
  it("保存 message, name=NetworkError", () => {
    const err = new NetworkError("网络断开");
    expect(err.message).toBe("网络断开");
    expect(err.name).toBe("NetworkError");
    expect(err).toBeInstanceOf(Error);
  });
});

describe("getErrorMessage", () => {
  it("ApiError 取 .message", () => {
    expect(getErrorMessage(new ApiError(HTTP_NOT_FOUND, "not found"))).toBe("not found");
  });
  it("NetworkError 取 .message", () => {
    expect(getErrorMessage(new NetworkError("fetch failed"))).toBe("fetch failed");
  });
  it("普通 Error 取 .message", () => {
    expect(getErrorMessage(new Error("x"))).toBe("x");
  });
  it("字符串转 String()", () => {
    expect(getErrorMessage("raw string")).toBe("raw string");
  });
  it("null 转 'null'", () => {
    expect(getErrorMessage(null)).toBe("null");
  });
});
