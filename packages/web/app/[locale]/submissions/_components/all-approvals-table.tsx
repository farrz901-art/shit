"use client";
// AllApprovalsTable — "全部待审 (admin)" tab 内容, 仅 admin 渲染入口
// 复用 ApprovalRow (isAdmin=true), 切 review filter 用 RQ useQuery
// (2026-06-13) Task 19: 实装, 替 Task 16 stub
// (2026-06-14) 改走 apiFetch()

// (2026-06-15) 改用 AppTabs 替 shadcn Tabs 三件套, 1 行 options API
import { AppTabs } from "@/components/common/input/app-tabs";
import { fetchApprovalsByReview, type Approval } from "@/lib/api/approvals";
import { ApprovalRow } from "./approval-row";
import { DataEmpty } from "@/components/common/display/app-data-empty";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslations } from "next-intl";
import { ZERO } from "@/const";

/** 审核筛选类型 */
type ReviewFilter = "pending" | "approved" | "rejected";

/**
 * AllApprovalsTable - "全部待审 (admin)" 审核列表
 * @param props.initialData - 服务端预取的审批数据
 * @client-bff
 */
export const AllApprovalsTable = ({ initialData }: { initialData: Approval[] }) => {
  const translation = useTranslations("submissions");
  const [review, setReview] = useState<ReviewFilter>("pending");
  const { data = initialData } = useQuery({
    initialData,
    queryFn: () => fetchApprovalsByReview(review).catch(() => initialData),
    queryKey: ["approvals", "all", review],
  });

  if (data.length === ZERO) {
    return <DataEmpty title="暂无待审" />;
  }

  return (
    <div className="space-y-2">
      <AppTabs
        options={[
          { label: translation("filters.pending"), value: "pending" },
          { label: translation("filters.approved"), value: "approved" },
          { label: translation("filters.rejected"), value: "rejected" },
        ]}
        value={review}
        onChange={(value) => setReview(value as ReviewFilter)}
        dataTestid="all-review"
      />
      {data.map((approval) => (
        <ApprovalRow key={approval.id} approval={approval} isAdmin />
      ))}
    </div>
  );
};
