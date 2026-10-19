// RSC: /knowledge 根 → 自动跳 /knowledge/documents (2026-06-14, 用户要求)
// 不要 dashboard 那种"首页": KnowledgeDashboard (stat 卡 + 录入入口) 整页删, 直接用 documents 当首页.
// KnowledgeLayout 仍生效 (Tabs + ActiveSwitch 在子页共用), redirect 后 /knowledge/documents 继承 layout.
// (2026-06-23) 迁移: getMyPermissions + allowed.includes → getPermissions + can()
import { redirect } from "next/navigation";
import { getPermissions } from "@/lib/auth/permission";
import ForbiddenPage from "../forbidden";

/** knowledge 页面
 * @param props
 * @server-only
 */
export default async function KnowledgePage() {
  const perm = await getPermissions();
  if (!perm.can("knowledge")) {
    return <ForbiddenPage />;
  }
  redirect("/knowledge/documents");
}
