"use client";
/**
 * 首次访问触发鉴权 bootstrap — 没 cookie 时 POST /api/auth/anon 拿匿名 token
 * 装在 root layout 顶层, useEffect 跑一次, 不阻塞渲染
 * @param props.serverSession RSC 层是否已识别到登录 session
 * @returns null
 * @client-bff
 */
// (2026-06-16) 砍 localStorage 路径: anon 后端 Set-Cookie 已自动写到浏览器, 不再
// 同步写 localStorage.
// (2026-06-18) 加 rag_was_logged_in localStorage 标记防止 anon 覆盖真账号:
//   登录成功 → cookie + localStorage 标记都存在
//   Cookie 过期/被清但标记还在 → 不再自动调 anon, 用户必须走显式登录页
//   显式 logout → cookie + localStorage 标记一起清
import { createAnonToken } from "@/lib/api/auth";
import { useEffect } from "react";
import { LS_KEY_WAS_LOGGED_IN } from "@/const";

/** 静默获取匿名 token */
const fetchAnonTokenSilently = async () => {
  try {
    await createAnonToken();
  } catch {
    // 静默: 网络/超时不影响首屏渲染, 下次访问重试
  }
};

interface AuthBootstrapProps {
  /** RSC 层是否已识别到登录 session (由 layout fetchLayoutUser 传入) */
  serverSession?: boolean;
}

/**
 * 首次访问 / 刷新页面时确保有 cookie:
 * 1. serverSession=true → 跳过 (服务端已通过 HttpOnly cookie 识别到登录用户)
 * 2. serverSession=false, 但有 localStorage rag_was_logged_in → 不调 anon (真账号标记还在)
 * 3. 都没 → 首次访问 / 已登出, POST anon 拿临时 token
 *
 * 不阻塞渲染: 网络错误静默.
 */
export const AuthBootstrap = ({ serverSession = false }: AuthBootstrapProps) => {
  useEffect(() => {
    if (typeof document === "undefined") {
      return;
    }

    // 服务端已确认有 session → 不调 anon (避免 HttpOnly cookie 被覆盖)
    if (serverSession) {
      return;
    }

    // 没 cookie 但有 rag_was_logged_in 标记 → 真账号 session 丢了, 等用户主动登录
    try {
      if (localStorage.getItem(LS_KEY_WAS_LOGGED_IN)) {
        return;
      }
    } catch {
      // LocalStorage 不可用时放行到 anon (兜底)
    }

    // 没 cookie, 没 localStorage 标记 → 首次访问 / 已登出 → anon
    fetchAnonTokenSilently();
  }, []);

  return null;
};
