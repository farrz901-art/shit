"use server";
// 账号系统 Server Actions (login / logout)
// 跟其他 _actions/*.ts 同模板 (看 _actions/knowledge.ts 风格)
// (2026-06-14) 改走 apiFetch(): 统一错误归一 (ApiError/NetworkError), 不再手写 JSON + try/catch
// (2026-06-16) 加 serverAuthHeaders: server caller 显式注 cookie token, 跨域到 FastAPI
// (2026-06-17) loginAction 成功走 server-side redirect() 而非 client router.push/refresh:
//  原因 1: 标准 Next.js 15 post-auth 模式, 浏览器拿 Set-Cookie 跟 303 一起, 不依赖 React 客户端 follow
//  原因 2: 跟 useActionState 一起用最自然 — server action 抛 NEXT_REDIRECT, useActionState 自动 follow
//  原因 3: 真账号 UserMenu 显示依赖 layout 重跑 (Next.js 默认行为, 但 server-side redirect 更显式)
//  注意: "App Router layout 不被 router.refresh 重跑" 是错误分析 — router.refresh() 实际会重跑 layout,
//         之前观察到 UserMenu 不更新真因是 layout apiFetch 漏传 headers, 不是 layout 共享问题.
import { ApiError, NetworkError } from "@/lib/api/errors";
import { createUser, resetPassword } from "@/lib/api/users";
import { redeemInvite } from "@/lib/api/invites";
import { actionError, actionErrorWithFallback } from "@/lib/actions-utils";
import { forgotPassword, login, logout, resetUserPassword } from "@/lib/api/account";
import { cookies } from "next/headers";
import { getLocale } from "next-intl/server";
import { redirect } from "@/i18n/navigation";
import { revalidatePath } from "next/cache";
import { serverAuthHeaders } from "@/lib/api/auth.server";
import {
  COOKIE_USER_TOKEN,
  HOURS_PER_DAY,
  HTTP_UNAUTHORIZED,
  MIN_PASSWORD_LENGTH,
  MINUTES_PER_HOUR,
  SECONDS_PER_MINUTE,
} from "@/const";

// --- 常量 (2026-06-25 const-cleanup: 6 个删, 改 import @/const) ---
const COOKIE_EXPIRY_DAYS = 7;
const COOKIE_MAX_AGE = COOKIE_EXPIRY_DAYS * HOURS_PER_DAY * MINUTES_PER_HOUR * SECONDS_PER_MINUTE; // 7 天

/**
 * 登录表单提交结果
 * @property ok 是否登录成功
 * @property error 错误消息 (成功时为 null)
 */
export interface LoginState {
  ok: boolean;
  error: string | null;
}

/**
 * 从 FormData 中提取登录凭证
 * @param formData 登录表单数据
 * @returns 分离出的 email + password + next, 或含错误信息的 LoginState
 */
const getLoginCredentials = (
  formData: FormData,
): { email: string; password: string; next: string } | LoginState => {
  const email = String(formData.get("email") ?? "").trim();
  const password = String(formData.get("password") ?? "");
  const next = String(formData.get("next") ?? "/");
  if (!email || !password) {
    return { error: "请填邮箱和密码", ok: false };
  }
  return { email, next, password };
};

/**
 * 调用后端登录 API，统一错误处理
 * @param email 邮箱
 * @param password 密码
 * @returns 登录成功返回 token，失败返回带错误信息的 LoginState
 */
const loginApiCall = async (
  email: string,
  password: string,
): Promise<{ token: string } | LoginState> => {
  try {
    return await login({ email, password }, await serverAuthHeaders());
  } catch (error) {
    if (error instanceof ApiError) {
      if (error.status === HTTP_UNAUTHORIZED) {
        return { error: "邮箱或密码错", ok: false };
      }
      return { error: `登录失败: ${error.message}`, ok: false };
    }
    if (error instanceof NetworkError) {
      return { error: "无法连接服务器", ok: false };
    }
    return { error: "登录失败", ok: false };
  }
};

/**
 * 将用户 token 写入 httpOnly cookie (7天有效期)
 * @param token 用户认证 token
 */
const setLoginCookie = async (token: string): Promise<void> => {
  const cookieStore = await cookies();
  cookieStore.set({
    httpOnly: true,
    maxAge: COOKIE_MAX_AGE,
    name: COOKIE_USER_TOKEN,
    path: "/",
    sameSite: "lax",
    value: token,
  });
};

/** 登录
 * @param _prev 前一次状态
 * @param formData 表单数据 (email, password, next)
 * @returns LoginState
 * @server-only
 */
export const loginAction = async (_prev: LoginState, formData: FormData): Promise<LoginState> => {
  const creds = getLoginCredentials(formData);
  if ("error" in creds) {
    return creds;
  }

  const loginResult = await loginApiCall(creds.email, creds.password);
  if ("error" in loginResult) {
    return loginResult;
  }

  // 成功: set cookie + server-side redirect
  await setLoginCookie(loginResult.token);
  revalidatePath("/", "layout");
  // Redirect({ href, locale }) throws NEXT_REDIRECT, code after 不执行; useActionState 跟 Next.js 客户端会处理.
  // 4.x API: 收 { href, locale } 对象, locale 必填 (从当前 request locale 拿, 保持用户在 /zh 或 /en)
  redirect({ href: creds.next, locale: await getLocale() });
  // 不可达: redirect() 永远 throws. 写兜底让 TS 满意 (return type 不含 undefined)
  throw new Error("unreachable: redirect should have thrown");
};

// (2026-06-14) React 19 useActionState: forgotPasswordAction
/**
 * 忘记密码请求结果
 * @property ok 是否成功
 * @property error 错误消息 (成功时为 null)
 * @property resetUrl 重置密码链接 (成功时返回)
 */
export interface ForgotPasswordState {
  ok: boolean;
  error: string | null;
  resetUrl: string | null;
}

/** 发送忘记密码邮件
 * @param _prev 前一次状态
 * @param formData 表单数据 (email)
 * @returns ForgotPasswordState
 * @server-only
 */
export const forgotPasswordAction = async (
  _prev: ForgotPasswordState,
  formData: FormData,
): Promise<ForgotPasswordState> => {
  const email = String(formData.get("email") ?? "").trim();
  if (!email) {
    return { error: "请填邮箱", ok: false, resetUrl: null };
  }
  try {
    const result = await forgotPassword(email, await serverAuthHeaders());
    return { error: null, ok: true, resetUrl: result.reset_url ?? null };
  } catch {
    // 安全: 不暴露邮箱是否存在, 统一返回成功
    return { error: null, ok: true, resetUrl: null };
  }
};

// (2026-06-14) React 19 useActionState: resetPasswordAction
/**
 * 重置密码操作结果
 * @property ok 是否成功
 * @property error 错误消息 (成功时为 null)
 */
export interface ResetPasswordState {
  ok: boolean;
  error: string | null;
}

// --- Reset password 辅助 ---
/**
 * 验证重置密码表单输入
 * @param formData 表单数据 (token, password, confirm)
 * @returns 验证通过返回 token + password，失败返回 ResetPasswordState 错误
 */
const validateResetPasswordInput = (
  formData: FormData,
): { token: string; password: string } | ResetPasswordState => {
  const token = String(formData.get("token") ?? "");
  const password = String(formData.get("password") ?? "");
  const confirm = String(formData.get("confirm") ?? "");
  if (!token) {
    return { error: "链接无效", ok: false };
  }
  if (password.length < MIN_PASSWORD_LENGTH) {
    return { error: "密码至少 8 位", ok: false };
  }
  if (password !== confirm) {
    return { error: "两次密码不一致", ok: false };
  }
  return { password, token };
};

/** 重置密码 (通过邮件 token)
 * @param _prev 前一次状态
 * @param formData 表单数据 (token, password, confirm)
 * @returns ResetPasswordState
 * @server-only
 */
export const resetPasswordAction = async (
  _prev: ResetPasswordState,
  formData: FormData,
): Promise<ResetPasswordState> => {
  const validated = validateResetPasswordInput(formData);
  if ("error" in validated) {
    return validated;
  }
  const { token, password } = validated;
  try {
    await resetUserPassword({ token, password }, await serverAuthHeaders());
    return { error: null, ok: true };
  } catch (error) {
    if (error instanceof ApiError) {
      return actionError(error);
    }
    return { error: "重置失败", ok: false };
  }
};

// (2026-06-14) React 19 useActionState: acceptInviteAction
/**
 * 接受邀请操作结果
 * @property ok 是否成功
 * @property error 错误消息 (成功时为 null)
 */
export interface AcceptInviteState {
  ok: boolean;
  error: string | null;
}

// --- Accept invite 辅助 ---
/**
 * 从 FormData 提取接受邀请的字段
 * @param formData 邀请表单数据
 * @returns 分离出的 token + displayName + password + confirm
 */
const getAcceptInviteFields = (
  formData: FormData,
): {
  confirm: string;
  displayName: string;
  password: string;
  token: string;
} => ({
  confirm: String(formData.get("confirm") ?? ""),
  displayName: String(formData.get("displayName") ?? "").trim(),
  password: String(formData.get("password") ?? ""),
  token: String(formData.get("token") ?? ""),
});

/** 验证接受邀请的表单输入 (token/displayName/password/confirm)
 * @param formData - 邀请表单数据
 * @returns 验证通过返回 token + displayName + password, 失败返回 AcceptInviteState 错误
 */
const validateAcceptInviteInput = (
  formData: FormData,
): { token: string; displayName: string; password: string } | AcceptInviteState => {
  const { confirm, displayName, password, token } = getAcceptInviteFields(formData);
  if (!token) {
    return { error: "邀请链接无效", ok: false };
  }
  if (!displayName) {
    return { error: "请填显示名称", ok: false };
  }
  if (password.length < MIN_PASSWORD_LENGTH) {
    return { error: "密码至少 8 位", ok: false };
  }
  if (password !== confirm) {
    return { error: "两次密码不一致", ok: false };
  }
  return { displayName, password, token };
};

/**
 * 调用后端兑换邀请 API
 * @param token 邀请 token
 * @param displayName 用户显示名
 * @param password 用户密码
 * @returns 成功返回认证 token，失败返回 AcceptInviteState 错误
 */
const acceptInviteApiCall = async (
  token: string,
  displayName: string,
  password: string,
): Promise<{ token: string } | AcceptInviteState> => {
  try {
    const result = await redeemInvite(
      token,
      { display_name: displayName, password },
      await serverAuthHeaders(),
    );
    return { token: result.token };
  } catch (error) {
    if (error instanceof ApiError) {
      return actionError(error);
    }
    return { error: "兑换失败", ok: false };
  }
};

// eslint-disable-next-line max-statements -- redirect 兜底 throw 多 1 行, 拆函数反而割裂阅读
/** 接受邀请并注册
 * @param _prev 前一次状态
 * @param formData 表单数据 (token, displayName, password, confirm)
 * @returns AcceptInviteState
 * @server-only
 */
export const acceptInviteAction = async (
  _prev: AcceptInviteState,
  formData: FormData,
): Promise<AcceptInviteState> => {
  const validated = validateAcceptInviteInput(formData);
  if ("error" in validated) {
    return validated;
  }
  const { token, displayName, password } = validated;
  const result = await acceptInviteApiCall(token, displayName, password);
  if ("error" in result) {
    return result;
  }
  // (2026-06-24) 兑换成功: 跟 loginAction 同款 server-side redirect 模式.
  // 原因 1: 后端 redeem 通过 response.set_cookie 种 cookie, server action fetch
  //         **不会**把上游 Set-Cookie 透传给浏览器 → 必须 server action 内显式 cookies().set().
  // 原因 2: 老代码用 next/navigation 的 router.push("/") 不带 locale → intlMiddleware 307,
  //         加上 React 19 useActionState 的 isPending 跟 transition 绑死, navigation 没结束前
  //         按钮永远显示"兑换中…", 用户感觉卡住 (真实 bug, 兑换实际已经成功).
  // 原因 3: 跟 loginAction 一致, 一处改一处用, 不留两套模式.
  await setLoginCookie(result.token);
  revalidatePath("/", "layout");
  redirect({ href: "/", locale: await getLocale() });
  throw new Error("unreachable: redirect should have thrown");
};

// (2026-06-14) React 19 useActionState: resetPasswordAdminAction
/**
 * 管理员重置密码操作结果
 * @property ok 是否成功
 * @property error 错误消息
 * @property tempPassword 临时密码 (重置后生成)
 */
export interface ResetPasswordAdminState {
  ok: boolean;
  error: string | null;
  tempPassword: string | null;
}

/** 管理员重设用户密码
 * @param _prev 前一次状态
 * @param formData 表单数据 (userId)
 * @returns ResetPasswordAdminState
 * @server-only
 */
export const resetPasswordAdminAction = async (
  _prev: ResetPasswordAdminState,
  formData: FormData,
): Promise<ResetPasswordAdminState> => {
  const userId = Number(formData.get("userId"));
  if (!userId) {
    return { error: "用户 ID 无效", ok: false, tempPassword: null };
  }
  try {
    const result = await resetPassword(userId, await serverAuthHeaders());
    return { error: null, ok: true, tempPassword: result.temp_password };
  } catch (error) {
    if (error instanceof ApiError) {
      return { ...actionErrorWithFallback(error, "重设失败"), tempPassword: null };
    }
    return { error: "重设失败", ok: false, tempPassword: null };
  }
};

// (2026-06-14) React 19 useActionState: createInviteAction
/**
 * 创建邀请操作结果
 * @property ok 是否成功
 * @property error 错误消息
 * @property inviteUrl 邀请链接 (成功时返回)
 */
export interface CreateInviteState {
  ok: boolean;
  error: string | null;
  inviteUrl: string | null;
}

/** 创建邀请 (管理员)
 * @param _prev 前一次状态
 * @param formData 表单数据 (email, isAdmin)
 * @returns CreateInviteState
 * @server-only
 */
export const createInviteAction = async (
  _prev: CreateInviteState,
  formData: FormData,
): Promise<CreateInviteState> => {
  const email = String(formData.get("email") ?? "").trim();
  const isAdmin = formData.get("isAdmin") === "on";
  if (!email) {
    return { error: "请填邮箱", inviteUrl: null, ok: false };
  }
  try {
    const result = await createUser(
      { email, role: isAdmin ? "admin" : undefined },
      await serverAuthHeaders(),
    );
    return { error: null, inviteUrl: result.invite_url, ok: true };
  } catch (error) {
    if (error instanceof ApiError) {
      return { error: error.message, inviteUrl: null, ok: false };
    }
    return { error: "创建失败", inviteUrl: null, ok: false };
  }
};

/** 登出: 调用后端登出 API 并清除本地 cookie
 * @throws ApiError / NetworkError (静默吞掉, 不影响本地 cookie 清理)
 * @server-only
 */
export const logoutAction = async (): Promise<void> => {
  try {
    await logout(await serverAuthHeaders());
  } catch {
    // Logout 失败不影响本地 cookie 清理
  }
  const cookieStore = await cookies();
  cookieStore.delete(COOKIE_USER_TOKEN);
  revalidatePath("/", "layout");
};
