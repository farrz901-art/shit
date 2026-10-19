// 客户画像页面布局 (2026-06-22 buyer-profile spec)
// 简单布局: 只包 children, 无额外导航

/** 客户画像页面布局
 * @param children - 子页面内容
 * @returns 布局 JSX
 * @client-bff
 */
const BuyersLayout = ({ children }: { children: React.ReactNode }) => (
  <div className="min-h-screen">{children}</div>
);

export default BuyersLayout;
