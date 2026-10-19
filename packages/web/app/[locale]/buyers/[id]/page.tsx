"use client";
// 客户画像详情页 (2026-06-22 buyer-profile spec)
// ProfileCard + ChangeTimeline + 操作按钮 (归档 / 编辑备注)
// (2026-06-24) 真拉 useFieldConfigs + useProfileChanges, 之前硬塞 []
//   导致 ProfileCard 永远走"暂无字段配置" 分支, ChangeTimeline 永远空.

import { ChangeTimeline } from "./_components/change-timeline";
import { ProfileCard } from "./_components/profile-card";
import { ErrorBanner } from "@/components/common/feedback/app-error-banner";
import { AppConfirm } from "@/components/common/confirm/app-confirm";
import { Button } from "@/components/ui/button";
import { LoadingSkeleton } from "@/components/common/button/app-loading-skeleton";
import { Archive } from "lucide-react";
import { useTranslations } from "next-intl";
import { use } from "react";
import { useToggle } from "react-use";
import { PageHeader } from "@/components/common/navigation/app-page-header";
import { useRouter, type useRouter as useRouterType } from "@/i18n/navigation";
import type {
  BuyerProfile,
  ChangeLog,
  ProfileFieldConfig,
} from "@/app/[locale]/buyers/_lib/buyer-profile/types";
import {
  useArchiveProfile,
  useBuyerProfile,
  useFieldConfigs,
  useProfileChanges,
  useUpdateProfile,
} from "@/app/[locale]/buyers/_lib/buyer-profile/hooks";

interface BuyerDetailPageProps {
  params: Promise<{ id: string }>;
}

const useBuyerDetailState = (id: string) => {
  const translate = useTranslations();
  const router = useRouter();
  const [showArchiveConfirm, toggleshowArchiveConfirm] = useToggle(false);
  const profileResult = useBuyerProfile(id);
  const fieldConfigsResult = useFieldConfigs();
  const changesResult = useProfileChanges(id);
  const updateProfile = useUpdateProfile();
  const archiveProfile = useArchiveProfile();

  return {
    translate,
    router,
    showArchiveConfirm,
    toggleshowArchiveConfirm,
    profileResult,
    fieldConfigsResult,
    changesResult,
    updateProfile,
    archiveProfile,
  };
};

const BuyerDetailPage = ({ params }: BuyerDetailPageProps) => {
  const { id } = use(params);
  const {
    translate,
    router,
    showArchiveConfirm,
    toggleshowArchiveConfirm,
    profileResult,
    fieldConfigsResult,
    changesResult,
    updateProfile,
    archiveProfile,
  } = useBuyerDetailState(id);

  if (profileResult.isLoading) {
    return <LoadingSkeleton />;
  }
  if (profileResult.error || !profileResult.data) {
    return (
      <div className="p-6">
        <ErrorBanner description={translate("买家不存在")} variant="destructive" />
      </div>
    );
  }

  return (
    <BuyerDetailContent
      id={id}
      profile={profileResult.data}
      configs={fieldConfigsResult.data ?? []}
      changes={changesResult.data ?? []}
      changesLoading={changesResult.isLoading}
      updateProfile={updateProfile}
      archiveProfile={archiveProfile}
      router={router}
      translate={translate}
      showArchiveConfirm={showArchiveConfirm}
      setShowArchiveConfirm={toggleshowArchiveConfirm}
    />
  );
};

// TanStack Query mutation 通用类型: 用 ReturnType 取 hook 真实返回类型, 替代之前的 any
// (2026-07-08 lint-ignores.md §4.2 FC-01)

const BuyerDetailContent = ({
  id,
  profile,
  configs,
  changes,
  changesLoading,
  updateProfile,
  archiveProfile,
  router,
  translate,
  showArchiveConfirm,
  setShowArchiveConfirm,
}: {
  id: string;
  profile: BuyerProfile;
  configs: ProfileFieldConfig[];
  changes: ChangeLog[];
  changesLoading: boolean;
  updateProfile: ReturnType<typeof useUpdateProfile>;
  archiveProfile: ReturnType<typeof useArchiveProfile>;
  router: ReturnType<typeof useRouterType>;
  translate: (key: string) => string;
  showArchiveConfirm: boolean;
  setShowArchiveConfirm: (nextValue?: boolean) => void;
}) => (
  <div className="space-y-6">
    <PageHeader backHref="/buyers" title={translate("买家详情")} />
    <ProfileCard
      configs={configs}
      onUpdate={(fieldCode, val) =>
        updateProfile.mutate({ id, profile_data: { [fieldCode]: val } })
      }
      profile={profile}
    />
    <div className="flex gap-2">
      <Button
        disabled={profile.status === "archived"}
        onClick={() => setShowArchiveConfirm(true)}
        size="sm"
        variant="outline"
      >
        <Archive className="mr-1 h-4 w-4" />
        {translate("归档")}
      </Button>
      <AppConfirm
        confirmText={translate("确认归档")}
        description={translate("归档后买家将不再活跃列表显示")}
        onConfirm={() => {
          archiveProfile.mutate(id, {
            onSuccess: () => {
              router.push("/buyers");
            },
          });
          setShowArchiveConfirm(false);
        }}
        onOpenChange={(open: boolean) => {
          if (!open) {
            setShowArchiveConfirm(false);
          }
        }}
        open={showArchiveConfirm}
        title={translate("确认归档?")}
        variant="destructive"
      />
    </div>
    <ChangeTimeline changes={changes} loading={changesLoading} />
  </div>
);

export default BuyerDetailPage;
