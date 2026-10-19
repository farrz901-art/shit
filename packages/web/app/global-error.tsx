"use client";
/**
 * 根 layout 崩溃兜底组件: 自带 <html>+<body>, 不依赖任何 layout context
 *
 * @param error - 捕获的错误对象
 * @param reset - 重置函数, 点击"重试"触发重新渲染
 * @returns JSX 元素
 * @client-bff
 */
export default function GlobalError({ error, reset }: { error: Error; reset: () => void }) {
  return (
    <html lang="zh">
      <body
        style={{
          display: "grid",
          fontFamily: "sans-serif",
          minHeight: "100vh",
          placeItems: "center",
        }}
      >
        <div style={{ maxWidth: 420, padding: 32, textAlign: "center" }}>
          <h1 style={{ fontSize: 24, fontWeight: 600, marginBottom: 12 }}>出错了</h1>
          <p style={{ color: "#666", fontSize: 14, marginBottom: 24 }}>
            {error.message || "应用遇到意外错误"}
          </p>
          <button
            onClick={reset}
            style={{
              background: "#111",
              border: "none",
              borderRadius: 8,
              color: "#fff",
              cursor: "pointer",
              fontSize: 14,
              padding: "10px 24px",
            }}
          >
            重试
          </button>
        </div>
      </body>
    </html>
  );
}
