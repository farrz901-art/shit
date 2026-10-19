"use client";
// MySubmissionsList — "我提交的" tab 内容, 任何登录用户可见
// 复用 ApprovalRow (isAdmin=false), 用户视角只读, 切 filter 用 RQ useQuery
// (2026-06-13) Task 19: 实装, 替 Task 16 stub
// (2026-06-14) 改走 apiFetch()
import { AppTabs } from "@/components/common/input/app-tabs";
import { fetchMyApprovals, type Approval } from "@/lib/api/approvals";
import { ApprovalRow } from "./approval-row";
// (2026-06-15) 改用 AppTabs 替 shadcn Tabs 三件套, 1 行 options API
import { DataEmpty } from "@/components/common/display/app-data-empty";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslations } from "next-intl";
import { ZERO } from "@/const";

/** 筛选类型 */
type Filter = "all" | "pending" | "rejected" | "failed";

/**
 * MySubmissionsList - "我提交的" 审批列表
 * @param props.initialData - 服务端预取的审批数据
 * @client-bff
 */
export const MySubmissionsList = ({ initialData }: { initialData: Approval[] }) => {
  useTranslations("submissions");
  const [filter, setFilter] = useState<Filter>("all");
  const { data = initialData } = useQuery({
    initialData,
    queryFn: () => {
      // 仅在非 all 时发请求; all 走 initialData (RSC 预取)
      const params = new URLSearchParams();
      if (filter === "pending") {
        params.set("review", "pending");
      }
      if (filter === "rejected") {
        params.set("review", "rejected");
      }
      if (filter === "failed") {
        params.set("apply", "failed");
      }
      return fetchMyApprovals(params.toString()).catch(() => initialData);
    },
    queryKey: ["approvals", "me", filter],
  });

  if (data.length === ZERO) {
    return <DataEmpty title="暂无提交" />;
  }

  return (
    <div className="space-y-2">
      <AppTabs
        options={[
          { label: "全部", value: "all" },
          { label: "审批中", value: "pending" },
          { label: "拒绝", value: "rejected" },
          { label: "失败", value: "failed" },
        ]}
        value={filter}
        onChange={(val) => setFilter(val as Filter)}
        dataTestid="my-filter"
      />
      {data.map((item) => (
        <ApprovalRow key={item.id} approval={item} isAdmin={false} />
      ))}
    </div>
  );
};
