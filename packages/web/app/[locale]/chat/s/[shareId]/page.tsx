// 公开 share 页 (RSC, 2026-06-16)
// 服务端 fetch share 数据 + 渲染只读视图; 无 header / composer / feedback.
// GET /api/chat/shares/{id} 是公开端点 (anon 可读), 无需鉴权.
import type { Metadata } from "next";

import { getShare } from "@/lib/api/chat-share";
import { SharedChatView } from "@/components/chat/shared-chat-view";

/** 公开分享页面 props
 * @property params - 路由参数 (locale + shareId)
 * @shared
 */
interface SharedChatPageProps {
  params: Promise<{ locale: string; shareId: string }>;
}

/** generateMetadata
 * @shared
 */
export const generateMetadata = async ({ params }: SharedChatPageProps): Promise<Metadata> => {
  await params; // 满足签名; metadata 不依赖 shareId 本身
  return {
    // (2026-06-16) 防搜索收录 share 内容
    robots: { follow: false, index: false },
  };
};

/** 公开分享聊天页面 (RSC, 无需鉴权)
 * @param params - 路由参数
 * @returns 分享聊天只读视图 JSX
 * @server-only
 */
export default async function SharedChatPage({ params }: SharedChatPageProps) {
  const { shareId } = await params;
  try {
    const data = await getShare(shareId);
    return (
      <>
        {/* (2026-06-16) 防御 noindex: layout 没显式声明, 此处双保险 */}
        <meta name="robots" content="noindex" />
        <SharedChatView
          shareId={data.share_id}
          title={data.title || "分享对话"}
          messages={data.messages}
          model={data.model}
          createdAt={data.created_at}
        />
      </>
    );
  } catch {
    // 404 / 失效链接 → 友好提示, 不抛错破坏 layout
    return <div className="py-12 text-center text-muted-foreground">分享链接无效或已过期</div>;
  }
}
