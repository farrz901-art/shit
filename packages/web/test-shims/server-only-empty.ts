// Server-only 是 Next.js 的 marker module, 用于标记 RSC 代码不能在 client 端 import.
// 在 vitest 里把它 alias 成空模块, 让 RSC prefetch 工具的测试能跑.

// 加空 export 避免 unicorn/no-empty-file
export const emptyModule = true;
