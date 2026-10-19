---
name: feedback-dify-api-returns-data-wrapper
description: "Dify API 列表接口返回 { data: [...], has_more, total } 而非裸数组，类型定义要匹配"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: eec4f205-4669-4734-b77f-77c2e0b18e11
---

Dify API 的列表接口（如 `/datasets`）返回格式是 `{ data: T[], has_more: boolean, total: number }`，不是裸数组。`listDatasets` 等客户端方法必须提取 `.data` 后再返回。

**根因**：之前 `listDatasets` 标为 `Promise<Dataset[]>` 但实际返回 `{ data: Dataset[], ... }`，BFF 里 `difyDatasets.reduce(...)` 对对象调 `.reduce` 抛 TypeError，被 catch 静默吞掉 → dify 数据永远是 0。

**How to apply**: 新增 Dify 列表类 API 客户端时，先用 `curl` 看真实响应格式，类型定义和提取逻辑要匹配 `{ data: T[] }` 结构，不要假设是裸数组。
