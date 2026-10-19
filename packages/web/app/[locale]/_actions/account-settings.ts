"use server";
// 账号设置 Server Actions (7 个, 改 profile / email / password / deletion / avatar)
// 跟 _actions/account.ts (loginAction) 同模板: useActionState 签名 + apiFetch + 错误归一
// (2026-06-18) 跟后端 T2.1-T2.4 8 endpoint 对接: PATCH /profile, POST/DELETE /avatar,
//             PATCH /email, POST /email/verify, PATCH /password, GET/POST/DELETE /deletion

import { ApiError, NetworkError } from "@/lib/api/errors";
import { actionErrorWithFallback } from "@/lib/actions-utils";
import {
  updateProfile,
  uploadAvatar,
  deleteAvatar,
  changeEmail,
  changePassword,
  requestDeletion,
  cancelDeletion,
} from "@/lib/api/account";
import { revalidatePath } from "next/cache";
import { serverAuthHeaders } from "@/lib/api/auth.server";
import { HTTP_BAD_REQUEST, HTTP_UNPROCESSABLE_ENTITY, MIN_PASSWORD_LENGTH, ONE } from "@/const";

// ============================================================
// 常量定义 (2026-06-25 const-cleanup: HTTP 状态 + 密码长度改 import)
// ============================================================

const DISPLAY_NAME_MIN = ONE;
const DISPLAY_NAME_MAX = 50;
const AVATAR_MAX_BYTES = 2_097_152; // 2MB

// ============================================================
// Profile (T2.1: PATCH /api/account/profile)
// ============================================================

/** Profile 更新结果状态
 * @property ok - 是否成功
 * @property error - 错误信息, 成功时为 null
 */
export interface ProfileState {
  ok: boolean;
  error: string | null;
}

/** 处理 profile 更新过程中的错误
 * @param error - 捕获的异常 (ApiError / NetworkError / unknown)
 * @returns 归一化的 ProfileState
 */
const handleProfileError = (error: unknown): ProfileState => {
  if (error instanceof ApiError) {
    return actionErrorWithFallback(error, "保存失败");
  }
  if (error instanceof NetworkError) {
    return { error: "无法连接服务器", ok: false };
  }
  return { error: "保存失败", ok: false };
};

/** 更新 profile
 * @param _prev 前一次状态
 * @param formData 表单数据 (display_name)
 * @returns ProfileState
 * @server-only
 */
export const updateProfileAction = async (
  _prev: ProfileState,
  formData: FormData,
): Promise<ProfileState> => {
  const displayName = String(formData.get("display_name") ?? "").trim();
  if (displayName.length < DISPLAY_NAME_MIN || displayName.length > DISPLAY_NAME_MAX) {
    return { error: "昵称 1-50 字符", ok: false };
  }
  try {
    await updateProfile({ display_name: displayName }, await serverAuthHeaders());
    revalidatePath("/", "layout");
    return { error: null, ok: true };
  } catch (error) {
    return handleProfileError(error);
  }
};

// ============================================================
// Avatar (T2.1: POST/DELETE /api/account/avatar)
// ============================================================

/** Avatar 上传/删除操作结果状态
 * @property ok - 是否成功
 * @property error - 错误信息, 成功时为 null
 * @property avatarUrl - 更新后的头像 URL, 删除时为 null
 */
export interface AvatarState {
  ok: boolean;
  error: string | null;
  avatarUrl: string | null;
}

/** 验证上传的头像文件 (大小/格式)
 * @param file - 上传的文件对象
 * @returns 验证不通过时的错误信息, 通过则返回 null
 */
const validateAvatarFile = (file: File | null): string | null => {
  if (!file || !file.size) {
    return "请选择文件";
  }
  if (file.size > AVATAR_MAX_BYTES) {
    return "图片大于 2MB";
  }
  if (!["image/png", "image/jpeg", "image/webp"].includes(file.type)) {
    return "仅支持 PNG / JPG / WebP";
  }
  return null;
};

/** 处理头像上传过程中的错误
 * @param error - 捕获的异常 (ApiError / NetworkError / unknown)
 * @returns 归一化的 AvatarState
 */
const handleUploadError = (error: unknown): AvatarState => {
  if (error instanceof ApiError) {
    if (error.status === HTTP_UNPROCESSABLE_ENTITY) {
      return { avatarUrl: null, error: "图片无效或过大 (≤ 2MB)", ok: false };
    }
    return { ...actionErrorWithFallback(error, "上传失败"), avatarUrl: null };
  }
  if (error instanceof NetworkError) {
    return { avatarUrl: null, error: "无法连接后端", ok: false };
  }
  return { avatarUrl: null, error: "上传失败", ok: false };
};

/** 上传头像
 * @param _prev 前一次状态
 * @param formData 表单数据 (file)
 * @returns AvatarState
 * @server-only
 */
export const uploadAvatarAction = async (
  _prev: AvatarState,
  formData: FormData,
): Promise<AvatarState> => {
  const file = formData.get("file") as File | null;
  const validationError = validateAvatarFile(file);
  if (validationError) {
    return { avatarUrl: null, error: validationError, ok: false };
  }
  try {
    const result = await uploadAvatar(formData, await serverAuthHeaders());
    revalidatePath("/", "layout");
    return { avatarUrl: result.avatar_url, error: null, ok: true };
  } catch (error) {
    return handleUploadError(error);
  }
};

/** 删除头像
 * @returns AvatarState
 * @server-only
 */
export const deleteAvatarAction = async (): Promise<AvatarState> => {
  try {
    await deleteAvatar(await serverAuthHeaders());
    revalidatePath("/", "layout");
    return { avatarUrl: null, error: null, ok: true };
  } catch {
    return { avatarUrl: null, error: "删除失败", ok: false };
  }
};

// ============================================================
// Email (T2.2: PATCH /api/account/email + POST /email/verify)
// ============================================================

/** 邮箱变更结果状态
 * @property ok - 是否成功
 * @property error - 错误信息, 成功时为 null
 * @property verificationUrl - 验证链接, 需要后端发送验证邮件后返回
 */
export interface EmailState {
  ok: boolean;
  error: string | null;
  verificationUrl: string | null;
}

/** 处理邮箱变更过程中的错误
 * @param error - 捕获的异常 (ApiError / unknown)
 * @returns 归一化的 EmailState
 */
const handleEmailError = (error: unknown): EmailState => {
  if (error instanceof ApiError) {
    if (error.status === HTTP_BAD_REQUEST) {
      return { error: "当前密码错误或邮箱已被使用", ok: false, verificationUrl: null };
    }
    return { ...actionErrorWithFallback(error, "申请失败"), verificationUrl: null };
  }
  return { error: "申请失败", ok: false, verificationUrl: null };
};

/** 申请更换邮箱
 * @param _prev - 前一次操作状态
 * @param formData - 表单数据 (new_email / current_password)
 * @returns 包含 verificationUrl 的处理结果
 * @throws ApiError / NetworkError
 * @server-only
 */
export const requestEmailChangeAction = async (
  _prev: EmailState,
  formData: FormData,
): Promise<EmailState> => {
  const newEmail = String(formData.get("new_email") ?? "").trim();
  const currentPassword = String(formData.get("current_password") ?? "");
  if (!newEmail || !currentPassword) {
    return { error: "请填新邮箱和当前密码", ok: false, verificationUrl: null };
  }
  try {
    const result = await changeEmail(
      { current_password: currentPassword, new_email: newEmail },
      await serverAuthHeaders(),
    );
    return {
      error: null,
      ok: true,
      verificationUrl: result.verification_url,
    };
  } catch (error) {
    return handleEmailError(error);
  }
};

// ============================================================
// Password (T2.3: PATCH /api/account/password)
// ============================================================

/** 密码修改结果状态
 * @property ok - 是否成功
 * @property error - 错误信息, 成功时为 null
 */
export interface PasswordState {
  ok: boolean;
  error: string | null;
}

/** 验证密码表单必填字段和一致性
 * @param currentPassword - 当前密码
 * @param newPassword - 新密码
 * @param confirm - 确认新密码
 * @returns 校验不通过时的错误信息, 通过则返回 null
 */
const validatePasswords = (
  currentPassword: string,
  newPassword: string,
  confirm: string,
): string | null => {
  if (!currentPassword || !newPassword || !confirm) {
    return "请填完整";
  }
  if (newPassword.length < MIN_PASSWORD_LENGTH) {
    return "密码至少 8 位";
  }
  if (newPassword !== confirm) {
    return "两次密码不一致";
  }
  return null;
};

/** 处理密码修改过程中的错误
 * @param error - 捕获的异常 (ApiError / unknown)
 * @returns 归一化的 PasswordState
 */
const handlePasswordError = (error: unknown): PasswordState => {
  if (error instanceof ApiError) {
    return actionErrorWithFallback(error, "改密失败");
  }
  return { error: "改密失败", ok: false };
};

/** 修改密码
 * @param _prev - 前一次操作状态
 * @param formData - 表单数据 (current_password / new_password / confirm)
 * @returns 修改结果状态
 * @throws ApiError / NetworkError
 * @server-only
 */
export const changePasswordAction = async (
  _prev: PasswordState,
  formData: FormData,
): Promise<PasswordState> => {
  const currentPassword = String(formData.get("current_password") ?? "");
  const newPassword = String(formData.get("new_password") ?? "");
  const confirm = String(formData.get("confirm") ?? "");
  const validationError = validatePasswords(currentPassword, newPassword, confirm);
  if (validationError) {
    return { error: validationError, ok: false };
  }
  try {
    await changePassword(
      { confirm, current_password: currentPassword, new_password: newPassword },
      await serverAuthHeaders(),
    );
    return { error: null, ok: true };
  } catch (error) {
    return handlePasswordError(error);
  }
};

// ============================================================
// Deletion (T2.4: POST/DELETE /api/account/deletion)
// ============================================================

/** 账号注销申请结果状态
 * @property ok - 是否成功
 * @property error - 错误信息, 成功时为 null
 * @property restoreUrl - 撤销注销的链接
 * @property expiresAt - 注销生效时间 (ISO 字符串)
 */
export interface DeletionState {
  ok: boolean;
  error: string | null;
  restoreUrl: string | null;
  expiresAt: string | null;
}

/** 处理注销申请/撤销过程中的错误
 * @param error - 捕获的异常 (ApiError / unknown)
 * @returns 归一化的 DeletionState
 */
const handleDeletionError = (error: unknown): DeletionState => {
  if (error instanceof ApiError) {
    return {
      ...actionErrorWithFallback(error, "申请失败"),
      expiresAt: null,
      restoreUrl: null,
    };
  }
  return { error: "申请失败", expiresAt: null, ok: false, restoreUrl: null };
};

/** 申请注销账号
 * @param _prev - 前一次操作状态
 * @param formData - 表单数据 (current_password / confirm_text)
 * @returns 包含 restoreUrl 和 expiresAt 的处理结果
 * @throws ApiError / NetworkError
 * @server-only
 */
export const requestDeletionAction = async (
  _prev: DeletionState,
  formData: FormData,
): Promise<DeletionState> => {
  const currentPassword = String(formData.get("current_password") ?? "");
  const confirmText = String(formData.get("confirm_text") ?? "");
  if (!currentPassword) {
    return {
      error: "请输当前密码",
      expiresAt: null,
      ok: false,
      restoreUrl: null,
    };
  }
  if (confirmText !== "我要注销") {
    return {
      error: "请字面输入 '我要注销' 确认",
      expiresAt: null,
      ok: false,
      restoreUrl: null,
    };
  }
  try {
    const result = await requestDeletion(
      { confirm_text: confirmText, current_password: currentPassword },
      await serverAuthHeaders(),
    );
    return {
      error: null,
      expiresAt: result.expires_at,
      ok: true,
      restoreUrl: result.restore_url,
    };
  } catch (error) {
    return handleDeletionError(error);
  }
};

/** 撤销注销
 * @param _prev 前一次状态
 * @param formData 表单数据 (current_password)
 * @returns DeletionState
 * @server-only
 */
export const cancelDeletionAction = async (
  _prev: DeletionState,
  formData: FormData,
): Promise<DeletionState> => {
  const currentPassword = String(formData.get("current_password") ?? "");
  if (!currentPassword) {
    return {
      error: "请输当前密码",
      expiresAt: null,
      ok: false,
      restoreUrl: null,
    };
  }
  try {
    await cancelDeletion({ current_password: currentPassword }, await serverAuthHeaders());
    revalidatePath("/", "layout");
    return {
      error: null,
      expiresAt: null,
      ok: true,
      restoreUrl: null,
    };
  } catch (error) {
    if (error instanceof ApiError) {
      return {
        ...actionErrorWithFallback(error, "撤销失败"),
        expiresAt: null,
        restoreUrl: null,
      };
    }
    return { error: "撤销失败", expiresAt: null, ok: false, restoreUrl: null };
  }
};
