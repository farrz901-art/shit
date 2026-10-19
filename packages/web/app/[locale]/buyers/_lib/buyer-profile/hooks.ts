// 客户画像系统 TanStack Query hooks (2026-06-22 buyer-profile spec)
// 遵循项目 staleTime 默认 60_000, refetchOnWindowFocus 默认 false

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  listProfiles,
  getBuyerProfile,
  updateBuyerProfile,
  archiveProfile,
  getProfileChanges,
  listProfilesFieldConfigs,
  createFieldConfig,
  updateProfileFieldConfig,
  deleteFieldConfig,
} from "@/lib/api/buyer-profile";
import type {
  BuyerProfile,
  ProfileFieldConfig,
  ChangeLog,
  BuyerProfileListResponse,
} from "./types";

/** React Query staleTime 默认值 (60s) @shared */
const STALE_TIME_MS = 60_000;

/** 客户画像列表查询 hook
 * @param params - 查询参数
 * @returns 客户画像列表
 * @client-bff
 */
export const useBuyerProfiles = (params?: Record<string, string>) =>
  useQuery<BuyerProfileListResponse>({
    queryFn: () => listProfiles(params) as Promise<BuyerProfileListResponse>,
    queryKey: ["buyer-profiles", params],
    staleTime: STALE_TIME_MS,
  });

/** 单个客户画像详情查询 hook
 * @param id - 画像 ID
 * @returns 客户画像详情
 * @client-bff
 */
export const useBuyerProfile = (id: string) =>
  useQuery<BuyerProfile>({
    enabled: Boolean(id),
    queryFn: () => getBuyerProfile(id) as Promise<BuyerProfile>,
    queryKey: ["buyer-profile", id],
    staleTime: STALE_TIME_MS,
  });

/** 画像变更记录查询 hook
 * @param id - 画像 ID
 * @returns 变更日志列表
 * @client-bff
 */
export const useProfileChanges = (id: string) =>
  useQuery<ChangeLog[]>({
    enabled: Boolean(id),
    queryFn: () => getProfileChanges(id) as Promise<ChangeLog[]>,
    queryKey: ["buyer-profile-changes", id],
    staleTime: STALE_TIME_MS,
  });

/** 画像更新 mutation hook
 * @returns mutation 对象
 * @client-bff
 */
export const useUpdateProfile = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: string } & Record<string, unknown>) =>
      updateBuyerProfile(id, body),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["buyer-profiles"] });
      queryClient.invalidateQueries({ queryKey: ["buyer-profile", variables.id] });
    },
  });
};

/** 画像归档 mutation hook
 * @returns mutation 对象
 * @client-bff
 */
export const useArchiveProfile = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => archiveProfile(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["buyer-profiles"] });
    },
  });
};

/** 字段配置列表查询 hook
 * @returns 字段配置列表
 * @client-bff
 */
export const useFieldConfigs = () =>
  useQuery<ProfileFieldConfig[]>({
    queryFn: () => listProfilesFieldConfigs() as Promise<ProfileFieldConfig[]>,
    queryKey: ["profile-field-configs"],
    staleTime: STALE_TIME_MS,
  });

/** 创建字段配置 mutation hook
 * @returns mutation 对象
 * @client-bff
 */
export const useCreateFieldConfig = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => createFieldConfig(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["profile-field-configs"] });
    },
  });
};

/** 更新字段配置 mutation hook
 * @returns mutation 对象
 * @client-bff
 */
export const useUpdateFieldConfig = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ code, ...body }: { code: string } & Record<string, unknown>) =>
      updateProfileFieldConfig(code, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["profile-field-configs"] });
    },
  });
};

/** 删除字段配置 mutation hook
 * @returns mutation 对象
 * @client-bff
 */
export const useDeleteFieldConfig = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (code: string) => deleteFieldConfig(code),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["profile-field-configs"] });
    },
  });
};

export type { BuyerProfile, ProfileFieldConfig } from "./types";
