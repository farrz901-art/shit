# Markdown Extract KG — PR4: 前端 3 页面 + BFF + i18n (M8, v3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** 上传 Markdown → 后台抽取 → 进度 → 预览校对 → 3 出口 (Neo4j / JSONL / Cypher) 的前端完整链路。

**Scope (6 commits, ~6h):**
- Task 19: lib/api/knowledge.ts 加 8 个 wrapper + 7 个 type + 8 个 vitest test
- Task 20: 7 个 BFF route 透传 (cookie → x-user-token, dataset query param 透传)
- Task 21: i18n 同步 (zh.json + en.json 加 12 个 key)
- Task 22: knowledge-tabs.tsx 加 1 行 (TABS /knowledge/extract children)
- Task 23: 3 个前端页面 (extract / [task_id] / [task_id]/preview, 含 dataset 下拉框)
- Task 24: 1 个 Playwright 冒烟 spec + 收尾验证

**v3 关键**:
- 抽取页加 **dataset 下拉框** (从 `GET /api/kg/datasets` 拉白名单)
- 3 个页面 store + 透传 dataset 到 BFF
- BFF 透传 dataset query param
- i18n 加 `dataset` / `数据集` 等新 key

## 项目规约 (PR4 必须遵守)

1. **优先用项目封装组件**: AppSelect / FileDropzone / DataTable / TaskStatusBadge / ErrorBanner / PageHero / AppConfirm
2. **i18n 约定**: `t("中文 key")` 中文作 key, zh.json identity, en.json 翻译
3. **路由跳转必须用 `@/i18n/navigation` 的 useRouter** (禁止 next/navigation)
4. **JSX 不写行内 `onClick={() => {}}`**: 提取命名函数
5. **PR 收尾**: `bun run test && bun run typecheck && bun run lint`

## File Structure

### 修改
- `packages/web/lib/api/knowledge.ts` — 末尾追加 8 wrapper + 7 type
- `packages/web/lib/api/knowledge.test.ts` — 追加 8 vitest test
- `packages/web/components/knowledge/knowledge-tabs.tsx:18` — TABS children 加 `/knowledge/extract`
- `packages/web/messages/zh.json` — 加 12 个 key (含 `数据集` 等)
- `packages/web/messages/en.json` — 加翻译

### 新增
- `packages/web/app/api/kg/extract/upload/route.ts`
- `packages/web/app/api/kg/extract/start/route.ts`
- `packages/web/app/api/kg/extract/tasks/[task_id]/route.ts`
- `packages/web/app/api/kg/extract/tasks/[task_id]/preview/route.ts`
- `packages/web/app/api/kg/extract/tasks/[task_id]/items/route.ts`
- `packages/web/app/api/kg/extract/tasks/[task_id]/commit/route.ts`
- `packages/web/app/api/kg/extract/tasks/[task_id]/export/route.ts`
- `packages/web/app/[locale]/knowledge/extract/page.tsx` (~140 行, 含 dataset 下拉)
- `packages/web/app/[locale]/knowledge/extract/[task_id]/page.tsx` (~120 行)
- `packages/web/app/[locale]/knowledge/extract/[task_id]/preview/page.tsx` (~200 行)
- `packages/web/e2e/kg-extract.spec.ts` (~25 行, 含 dataset 选 motor)

---

## Task 19: lib/api/knowledge.ts 加 8 wrapper + 7 type + 8 vitest test

```typescript
// packages/web/lib/api/knowledge.ts (末尾追加)

export type DatasetInfo = { label: string };

export type ExtractorInfo = { id: string; available: boolean };

export type SplitterInfo = { id: string; chunk_size_range: [number, number] };

export type ExtractTaskState = {
  task_id: string;
  state: "queued" | "running" | "done" | "failed" | "partial";
  success: number;
  failed: number;
  errors: string[];
};

export type ExtractPreviewEntity = {
  id: number; text: string; label: string; selected: boolean;
  char_span: [number, number]; confidence: number; chunk_id: string;
};

export type ExtractPreviewRelation = {
  id: number; head: string; rel_type: string; tail: string;
  selected: boolean; rule_type: string; confidence: number; chunk_id: string;
};

export type ExtractPreview = {
  entities: ExtractPreviewEntity[];
  relations: ExtractPreviewRelation[];
};

export type PatchItemInput = { id: number; selected: boolean; corrected_payload: object | null };

export type ExtractUploadResult = { uri: string; file_id: string; dataset: string };


export const fetchDatasets = async (): Promise<DatasetInfo[]> => {
  const r = await apiFetch("/api/kg/datasets");
  if (!r.ok) throw new Error(`fetchDatasets 失败: ${r.status}`);
  return r.json();
};

export const fetchExtractors = async (): Promise<ExtractorInfo[]> => {
  const r = await apiFetch("/api/kg/extract/extractors");
  if (!r.ok) throw new Error(`fetchExtractors 失败: ${r.status}`);
  return r.json();
};

export const fetchSplitters = async (): Promise<SplitterInfo[]> => {
  const r = await apiFetch("/api/kg/extract/splitters");
  if (!r.ok) throw new Error(`fetchSplitters 失败: ${r.status}`);
  return r.json();
};

export const uploadExtractFile = async (
  file: File, dataset: string,
): Promise<ExtractUploadResult> => {
  const fd = new FormData();
  fd.append("file", file);
  const r = await apiFetch(`/api/kg/extract/upload?dataset=${encodeURIComponent(dataset)}`, {
    method: "POST", body: fd,
  });
  if (!r.ok) throw new Error(`uploadExtractFile 失败: ${r.status}`);
  return r.json();
};

export const startExtract = async (req: {
  uri: string; dataset: string; extractor: string; splitter: string;
}): Promise<{ task_id: string; state: string }> => {
  const r = await apiFetch("/api/kg/extract/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!r.ok) throw new Error(`startExtract 失败: ${r.status}`);
  return r.json();
};

export const fetchExtractTask = async (taskId: string): Promise<ExtractTaskState> => {
  const r = await apiFetch(`/api/kg/extract/tasks/${taskId}`);
  if (!r.ok) throw new Error(`fetchExtractTask 失败: ${r.status}`);
  return r.json();
};

export const fetchExtractPreview = async (taskId: string, dataset: string): Promise<ExtractPreview> => {
  const r = await apiFetch(
    `/api/kg/extract/tasks/${taskId}/preview?dataset=${encodeURIComponent(dataset)}`,
  );
  if (!r.ok) throw new Error(`fetchExtractPreview 失败: ${r.status}`);
  return r.json();
};

export const patchExtractItems = async (
  taskId: string, dataset: string, items: PatchItemInput[],
): Promise<{ updated: number }> => {
  const r = await apiFetch(
    `/api/kg/extract/tasks/${taskId}/items?dataset=${encodeURIComponent(dataset)}`,
    { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ items }) },
  );
  if (!r.ok) throw new Error(`patchExtractItems 失败: ${r.status}`);
  return r.json();
};

export const commitExtract = async (taskId: string, dataset: string): Promise<{
  success: number; failed: number; errors: string[];
}> => {
  const r = await apiFetch(
    `/api/kg/extract/tasks/${taskId}/commit?dataset=${encodeURIComponent(dataset)}`,
    { method: "POST" },
  );
  if (!r.ok) throw new Error(`commitExtract 失败: ${r.status}`);
  return r.json();
};

export const triggerExportDownload = async (
  taskId: string, dataset: string, format: "jsonl" | "cypher", filename: string,
): Promise<void> => {
  const r = await apiFetch(
    `/api/kg/extract/tasks/${taskId}/export?dataset=${encodeURIComponent(dataset)}&format=${format}`,
  );
  if (!r.ok) throw new Error(`export 失败: ${r.status}`);
  const blob = await r.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
};
```

8 个 vitest test (跟 v1 模式一致, mock fetch).

```bash
cd packages/web && bun run test lib/api/knowledge.test.ts -v
git add packages/web/lib/api/knowledge.ts packages/web/lib/api/knowledge.test.ts
git commit -m "feat(web): 8 个 kg extract API wrapper + 7 type + 1 datasets wrapper + 8 vitest test"
```

---

## Task 20: 7 个 BFF route 透传 (cookie → x-user-token)

跟 PR4 v1 一致, 每个 BFF 都透传 dataset query param。例:

```typescript
// packages/web/app/api/kg/extract/start/route.ts
import { type NextRequest } from "next/server";
import { cookies } from "next/headers";
import { COOKIE_USER_TOKEN, HEADER_X_USER_TOKEN, HEADER_CONTENT_TYPE } from "@/const";
import { serverFetch } from "@/lib/api/server-fetch";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export const POST = async (request: NextRequest): Promise<Response> => {
  const token = (await cookies()).get(COOKIE_USER_TOKEN)?.value;
  if (!token) return Response.json({ detail: "Unauthorized" }, { status: 401 });

  const body = await request.text();
  // 透传 url query params (dataset 在 body 里, 但其他 query 也得透)
  const url = `/api/kg/extract/start${request.nextUrl.search}`;
  const r = await serverFetch(url, {
    method: "POST",
    headers: {
      [HEADER_X_USER_TOKEN]: token,
      [HEADER_CONTENT_TYPE]: "application/json",
    },
    body,
  });
  return new Response(await r.text(), {
    status: r.status,
    headers: { "Content-Type": r.headers.get("Content-Type") ?? "application/json" },
  });
};
```

其他 6 个 BFF route 同模式, 把 `request.nextUrl.search` 拼到后端 URL。

```bash
cd packages/web && bun run typecheck
git add packages/web/app/api/kg/extract/
git commit -m "feat(web): 7 个 BFF route 透传 kg extract 端点 (cookie → x-user-token, dataset query 透传)"
```

---

## Task 21: i18n 同步

```json
// packages/web/messages/zh.json 末尾加
  "数据集": "数据集",
  "选择数据集": "选择数据集",
  "知识图谱抽取": "知识图谱抽取",
  "选择抽取器与切片器": "选择抽取器与切片器",
  "抽取器": "抽取器",
  "切片器": "切片器",
  "上传 Markdown 文件": "上传 Markdown 文件",
  "启动抽取": "启动抽取",
  "抽取进度": "抽取进度",
  "预览实体与关系": "预览实体与关系",
  "写 Neo4j": "写 Neo4j",
  "导出 JSONL": "导出 JSONL",
  "导出 Cypher": "导出 Cypher",
  "加载中…": "加载中…"

// packages/web/messages/en.json 末尾加
  "数据集": "Dataset",
  "选择数据集": "Choose dataset",
  "知识图谱抽取": "Knowledge Graph Extraction",
  "选择抽取器与切片器": "Choose extractor and splitter",
  "抽取器": "Extractor",
  "切片器": "Splitter",
  "上传 Markdown 文件": "Upload Markdown file",
  "启动抽取": "Start extraction",
  "抽取进度": "Extraction progress",
  "预览实体与关系": "Preview entities and relations",
  "写 Neo4j": "Write to Neo4j",
  "导出 JSONL": "Export JSONL",
  "导出 Cypher": "Export Cypher",
  "加载中…": "Loading..."
```

```bash
node -e "JSON.parse(require('fs').readFileSync('messages/zh.json')); JSON.parse(require('fs').readFileSync('messages/en.json')); console.log('OK')"
git add packages/web/messages/zh.json packages/web/messages/en.json
git commit -m "i18n(kg-extract): 加 13 个 key 含 dataset (zh identity, en 翻译, zh … / en ...)"
```

---

## Task 22: knowledge-tabs.tsx 加 1 行

```tsx
// packages/web/components/knowledge/knowledge-tabs.tsx:18
// TABS 数组的"知识图谱" tab children 加 "/knowledge/extract"
{
  children: [
    "/knowledge/graph",
    "/knowledge/triples",
    "/knowledge/batch",
    "/knowledge/nodes",
    "/knowledge/relations",
    "/knowledge/extract",  // 2026-07-01 v3
  ],
  href: "/knowledge/graph",
  label: "知识图谱",
},
```

```bash
cd packages/web && bun run test components/knowledge/knowledge-tabs.test.tsx -v
git add packages/web/components/knowledge/knowledge-tabs.tsx
git commit -m "feat(web): knowledge-tabs 加 /knowledge/extract children 1 行"
```

---

## Task 23: 3 个前端页面 (含 dataset 下拉)

### 23.1 extract 上传页 (~140 行, 加 dataset 下拉)

```tsx
// packages/web/app/[locale]/knowledge/extract/page.tsx
"use client";
import { useState, useTransition } from "react";
import { useRouter } from "@/i18n/navigation";
import { useTranslations } from "next-intl";
import { useQuery } from "@tanstack/react-query";
import { PageHero } from "@/components/common/navigation/app-page-hero";
import { FileDropzone } from "@/components/common/input/app-file-dropzone";
import { AppSelect } from "@/components/common/input/app-select";
import { Button } from "@/components/ui/button";
import { ErrorBanner } from "@/components/common/feedback/app-error-banner";
import { Form, FormField } from "@/components/common/form";
import {
  fetchDatasets, fetchExtractors, fetchSplitters,
  uploadExtractFile, startExtract,
} from "@/lib/api/knowledge";

const ExtractPage = () => {
  const tr = useTranslations();
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [file, setFile] = useState<File | null>(null);
  const [dataset, setDataset] = useState("motor");
  const [extractor, setExtractor] = useState("llm_pydantic");
  const [splitter, setSplitter] = useState("heading");
  const [error, setError] = useState<string | null>(null);

  const { data: datasets = [] } = useQuery({
    queryKey: ["kg", "datasets"],
    queryFn: fetchDatasets,
  });
  const { data: extractors = [] } = useQuery({
    queryKey: ["kg", "extractors"],
    queryFn: fetchExtractors,
  });
  const { data: splitters = [] } = useQuery({
    queryKey: ["kg", "splitters"],
    queryFn: fetchSplitters,
  });

  const onSubmit = async () => {
    if (!file) { setError(tr("请先选择文件")); return; }
    if (file.size > 5 * 1024 * 1024) { setError(tr("文件超过 5MB")); return; }
    startTransition(async () => {
      try {
        const { uri } = await uploadExtractFile(file, dataset);
        const { task_id } = await startExtract({ uri, dataset, extractor, splitter });
        router.push(`/knowledge/extract/${task_id}?dataset=${dataset}`);
      } catch (e) {
        setError(e instanceof Error ? e.message : tr("启动失败"));
      }
    });
  };

  return (
    <div className="space-y-6">
      <PageHero title={tr("知识图谱抽取")} description={tr("选择数据集与抽取器")} />
      {error && <ErrorBanner variant="destructive" title={tr("启动失败")} description={error} />}
      <Form onSubmit={onSubmit}>
        <FormField label={tr("数据集")}>
          <AppSelect
            value={dataset} onChange={setDataset}
            options={datasets.map((d) => ({ value: d.label, label: d.label }))}
          />
        </FormField>
        <FormField label={tr("抽取器")}>
          <AppSelect
            value={extractor} onChange={setExtractor}
            options={extractors.map((e) => ({ value: e.id, label: e.id }))}
          />
        </FormField>
        <FormField label={tr("切片器")}>
          <AppSelect
            value={splitter} onChange={setSplitter}
            options={splitters.map((s) => ({ value: s.id, label: s.id }))}
          />
        </FormField>
        <FormField label={tr("上传 Markdown 文件")}>
          <FileDropzone onFile={setFile} accept=".md,text/markdown" />
        </FormField>
        <Button type="submit" disabled={!file || isPending}>
          {isPending ? tr("加载中…") : tr("启动抽取")}
        </Button>
      </Form>
    </div>
  );
};

export default ExtractPage;
```

### 23.2 进度页 (~120 行, 从 URL 拿 dataset)

```tsx
// packages/web/app/[locale]/knowledge/extract/[task_id]/page.tsx
"use client";
/**
 * 抽取进度页
 *
 * 轮询 GET /tasks/{id}, 1s 间隔. dataset 从 URL ?dataset=motor 拿
 * 状态: queued → running → done/partial (可点击预览) / failed (显示错误)
 *
 * 复用项目封装:
 * - usePolling (项目 hooks)
 * - TaskStatusBadge (项目组件)
 * - Progress (shadcn)
 * - ErrorBanner (项目组件)
 * - PageHero
 */
import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "@/i18n/navigation";
import { useTranslations } from "next-intl";
import { PageHero } from "@/components/common/navigation/app-page-hero";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { TaskStatusBadge } from "@/components/common/display/app-task-status-badge";
import { ErrorBanner } from "@/components/common/feedback/app-error-banner";
import { THOUSAND, ZERO } from "@/const";
import { fetchExtractTask, type ExtractTaskState } from "@/lib/api/knowledge";
import { usePolling } from "@/lib/hooks";

const TaskProgressPage = ({
  params,
}: {
  params: { task_id: string };
}) => {
  const tr = useTranslations();
  const router = useRouter();
  const searchParams = useSearchParams();
  const dataset = searchParams.get("dataset") ?? "motor";
  const [task, setTask] = useState<ExtractTaskState | null>(null);
  const shouldPoll =
    task === null ||
    task.state === "queued" ||
    task.state === "running";

  usePolling(
    () => {
      void fetchExtractTask(params.task_id)
        .then((t) => setTask(t))
        .catch(() => {});
    },
    shouldPoll ? THOUSAND : null,
  );

  useEffect(() => {
    void fetchExtractTask(params.task_id)
      .then((t) => setTask(t))
      .catch(() => {});
  }, [params.task_id]);

  if (!task) {
    return (
      <div className="space-y-6">
        <PageHero title={tr("抽取进度")} description={tr("加载中…")} />
      </div>
    );
  }

  const isDone = task.state === "done" || task.state === "partial";
  const progressValue =
    task.success > ZERO
      ? Math.min(
          100,
          Math.round(
            (task.success /
              Math.max(task.success + task.failed, 1)) *
              100,
          ),
        )
      : ZERO;

  return (
    <div className="space-y-6">
      <PageHero
        title={tr("抽取进度")}
        description={`task_id: ${task.task_id} | dataset: ${dataset}`}
      />
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>{tr("状态")}</CardTitle>
          <TaskStatusBadge state={task.state} />
        </CardHeader>
        <CardContent className="space-y-4">
          <Progress value={progressValue} />
          <div className="text-sm text-muted-foreground">
            success: {task.success} | failed: {task.failed}
          </div>
          {task.errors.length > ZERO ? (
            <ErrorBanner
              variant="destructive"
              title="errors"
              description={task.errors.join("\n")}
            />
          ) : null}
          {isDone ? (
            <Button
              onClick={() =>
                router.push(
                  `/knowledge/extract/${task.task_id}/preview?dataset=${dataset}`,
                )
              }
            >
              {tr("预览实体与关系")}
            </Button>
          ) : null}
          {task.state === "failed" ? (
            <ErrorBanner
              variant="destructive"
              title="抽取失败"
              description="请检查后端日志"
            />
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
};

export default TaskProgressPage;
```

### 23.3 预览 + 3 出口页 (~200 行, dataset 从 URL 拿 + 透传到 BFF)

```tsx
// packages/web/app/[locale]/knowledge/extract/[task_id]/preview/page.tsx
"use client";
/**
 * 预览 + 3 出口页面
 *
 * dataset 从 URL ?dataset=motor 拿, 透传到 BFF (preview/commit/export/items PATCH)
 * 1. DataTable 渲染实体表 (text Input editable + label + checkbox + chunk_id)
 * 2. DataTable 渲染关系表 (head Input + rel_type + tail Input + rule_type + checkbox)
 * 3. 单行勾选/全选/取消全选 (handleToggle + handleToggleAll)
 * 4. 选中计数 + 按钮禁用态
 * 5. toast 成功/失败反馈
 * 6. 保存编辑 → patchExtractItems(taskId, dataset, items) + toast
 * 7. 写 Neo4j → AppConfirm destructive → commitExtract(taskId, dataset) + toast
 * 8. 导出 JSONL / Cypher → triggerExportDownload(taskId, dataset, format, filename) + toast
 */
import { useEffect, useMemo, useState, useTransition } from "react";
import { useSearchParams } from "@/i18n/navigation";
import { useTranslations } from "next-intl";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";

import { PageHero } from "@/components/common/navigation/app-page-hero";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { DataTable, type ColumnDef } from "@/components/common/table/data-table";
import { DataEmpty } from "@/components/common/display/app-data-empty";
import { AppConfirm } from "@/components/common/dialog/app-confirm";
import { ErrorBanner } from "@/components/common/feedback/app-error-banner";
import {
  fetchExtractPreview,
  patchExtractItems,
  commitExtract,
  triggerExportDownload,
  type ExtractPreviewEntity,
  type ExtractPreviewRelation,
  type PatchItemInput,
} from "@/lib/api/knowledge";

interface PreviewEditState {
  entities: Map<number, ExtractPreviewEntity>;
  relations: Map<number, ExtractPreviewRelation>;
}

const PreviewPage = ({ params }: { params: { task_id: string } }) => {
  const tr = useTranslations();
  const searchParams = useSearchParams();
  const dataset = searchParams.get("dataset") ?? "motor";
  const taskId = params.task_id;
  const [isPending, startTransition] = useTransition();
  const [commitOpen, setCommitOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editState, setEditState] = useState<PreviewEditState>({
    entities: new Map(),
    relations: new Map(),
  });

  const previewQuery = useQuery({
    queryKey: ["kg", "extract-preview", taskId, dataset],
    queryFn: () => fetchExtractPreview(taskId, dataset),
    enabled: Boolean(taskId),
  });

  useEffect(() => {
    if (!previewQuery.data) return;
    setEditState({
      entities: new Map(previewQuery.data.entities.map((e) => [e.id, { ...e }])),
      relations: new Map(previewQuery.data.relations.map((r) => [r.id, { ...r }])),
    });
  }, [previewQuery.data]);

  const selectedEntities = useMemo(
    () => [...editState.entities.values()].filter((e) => e.selected),
    [editState.entities],
  );
  const selectedRelations = useMemo(
    () => [...editState.relations.values()].filter((r) => r.selected),
    [editState.relations],
  );
  const totalSelected = selectedEntities.length + selectedRelations.length;
  const canCommit = totalSelected > 0 && !isPending;

  const handleToggle = (kind: "entity" | "relation", id: number, selected: boolean) => {
    setEditState((prev) => {
      const map = new Map(kind === "entity" ? prev.entities : prev.relations);
      const item = map.get(id);
      if (item) map.set(id, { ...item, selected });
      return {
        ...prev,
        [kind === "entity" ? "entities" : "relations"]: map,
      };
    });
  };

  const handleToggleAll = (kind: "entity" | "relation", selected: boolean) => {
    setEditState((prev) => {
      const map = new Map(kind === "entity" ? prev.entities : prev.relations);
      for (const [id, item] of map) {
        map.set(id, { ...item, selected });
      }
      return {
        ...prev,
        [kind === "entity" ? "entities" : "relations"]: map,
      };
    });
  };

  const handleEdit = (kind: "entity" | "relation", id: number, field: string, value: string) => {
    setEditState((prev) => {
      const map = new Map(kind === "entity" ? prev.entities : prev.relations);
      const item = map.get(id);
      if (item) map.set(id, { ...item, [field]: value });
      return {
        ...prev,
        [kind === "entity" ? "entities" : "relations"]: map,
      };
    });
  };

  const saveEdits = async () => {
    if (!previewQuery.data) return;
    const items: PatchItemInput[] = [];
    editState.entities.forEach((e) => {
      const original = previewQuery.data!.entities.find((o) => o.id === e.id);
      if (original && (original.text !== e.text || original.selected !== e.selected)) {
        items.push({
          id: e.id, selected: e.selected,
          corrected_payload: { text: e.text, label: e.label },
        });
      }
    });
    editState.relations.forEach((r) => {
      const original = previewQuery.data!.relations.find((o) => o.id === r.id);
      if (original && (original.head !== r.head || original.tail !== r.tail || original.selected !== r.selected)) {
        items.push({
          id: r.id, selected: r.selected,
          corrected_payload: { head: r.head, rel_type: r.rel_type, tail: r.tail, rule_type: r.rule_type },
        });
      }
    });
    if (items.length === 0) return;
    await patchExtractItems(taskId, dataset, items);
  };

  const handleCommit = async () => {
    setCommitOpen(false);
    startTransition(async () => {
      try {
        await saveEdits();
        const r = await commitExtract(taskId, dataset);
        if (r.failed > 0) {
          setError(`写入失败: ${r.errors.join(", ")}`);
          toast.error(tr("写 Neo4j 失败"));
        } else {
          toast.success(tr("已成功写入 Neo4j"));
        }
      } catch (e) {
        const msg = e instanceof Error ? e.message : tr("写 Neo4j 失败");
        setError(msg);
        toast.error(msg);
      }
    });
  };

  const handleExport = async (format: "jsonl" | "cypher") => {
    startTransition(async () => {
      try {
        await saveEdits();
        await triggerExportDownload(
          taskId, dataset, format, `kg-${dataset}-${taskId}.${format}`,
        );
        toast.success(tr("导出成功"));
      } catch (e) {
        const msg = e instanceof Error ? e.message : tr("导出失败");
        setError(msg);
        toast.error(msg);
      }
    });
  };

  const entityColumns: ColumnDef<ExtractPreviewEntity>[] = useMemo(
    () => [
      {
        id: "select",
        header: () => (
          <Checkbox
            checked={editState.entities.size > 0
              && [...editState.entities.values()].every((e) => e.selected)}
            onCheckedChange={(v) => handleToggleAll("entity", Boolean(v))}
          />
        ),
        cell: ({ row }) => (
          <Checkbox
            checked={row.original.selected}
            onCheckedChange={(v) => handleToggle("entity", row.original.id, Boolean(v))}
          />
        ),
      },
      { id: "text", header: tr("文本"), cell: ({ row }) => (
        <Input value={row.original.text} onChange={(e) => handleEdit("entity", row.original.id, "text", e.target.value)} />
      )},
      { id: "label", header: tr("类型"), cell: ({ row }) => row.original.label },
      { id: "chunk_id", header: "chunk_id", cell: ({ row }) => <code className="text-xs">{row.original.chunk_id}</code> },
    ],
    [tr, editState.entities, handleToggleAll, handleToggle, handleEdit],
  );

  const relationColumns: ColumnDef<ExtractPreviewRelation>[] = useMemo(
    () => [
      {
        id: "select",
        header: () => (
          <Checkbox
            checked={editState.relations.size > 0
              && [...editState.relations.values()].every((r) => r.selected)}
            onCheckedChange={(v) => handleToggleAll("relation", Boolean(v))}
          />
        ),
        cell: ({ row }) => (
          <Checkbox
            checked={row.original.selected}
            onCheckedChange={(v) => handleToggle("relation", row.original.id, Boolean(v))}
          />
        ),
      },
      { id: "head", header: tr("头"), cell: ({ row }) => (
        <Input value={row.original.head} onChange={(e) => handleEdit("relation", row.original.id, "head", e.target.value)} />
      )},
      { id: "rel_type", header: tr("关系"), cell: ({ row }) => row.original.rel_type },
      { id: "tail", header: tr("尾"), cell: ({ row }) => (
        <Input value={row.original.tail} onChange={(e) => handleEdit("relation", row.original.id, "tail", e.target.value)} />
      )},
      { id: "rule_type", header: tr("规则"), cell: ({ row }) => row.original.rule_type },
    ],
    [tr, editState.relations, handleToggleAll, handleToggle, handleEdit],
  );

  if (previewQuery.isLoading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-8 w-48 bg-muted rounded" />
        <div className="h-4 w-96 bg-muted rounded" />
        <div className="h-32 bg-muted rounded" />
        <div className="h-32 bg-muted rounded" />
      </div>
    );
  }

  const entities = [...editState.entities.values()];
  const relations = [...editState.relations.values()];
  const hasData = entities.length > 0 || relations.length > 0;

  if (!hasData) {
    return (
      <div className="space-y-6">
        <PageHero title={tr("预览实体与关系")} description={tr("暂无抽取结果")} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHero
        title={tr("预览实体与关系")}
        description={`task_id: ${taskId} | dataset: ${dataset} | 已选中 ${totalSelected} 项`}
      />

      {error ? <ErrorBanner variant="destructive" title={tr("导入失败")} description={error} /> : null}

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>实体 ({entities.length}) <span className="text-sm text-muted-foreground">已选 {selectedEntities.length}</span></CardTitle>
        </CardHeader>
        <CardContent>
          <DataTable
            dataSource={entities} columns={entityColumns} rowKey={(e) => e.id}
            emptyText={<DataEmpty title={tr("暂无实体")} />}
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>关系 ({relations.length}) <span className="text-sm text-muted-foreground">已选 {selectedRelations.length}</span></CardTitle>
        </CardHeader>
        <CardContent>
          <DataTable
            dataSource={relations} columns={relationColumns} rowKey={(r) => r.id}
            emptyText={<DataEmpty title={tr("暂无关系")} />}
          />
        </CardContent>
      </Card>

      <div className="flex flex-wrap gap-3">
        <Button onClick={() => startTransition(saveEdits)} variant="outline" disabled={isPending}>
          {tr("保存编辑")}
        </Button>
        <Button onClick={() => setCommitOpen(true)} disabled={!canCommit}>
          {tr("写 Neo4j")}
        </Button>
        <Button onClick={() => handleExport("jsonl")} variant="outline" disabled={!canCommit}>
          {tr("导出 JSONL")}
        </Button>
        <Button onClick={() => handleExport("cypher")} variant="outline" disabled={!canCommit}>
          {tr("导出 Cypher")}
        </Button>
      </div>

      <AppConfirm
        open={commitOpen}
        onOpenChange={setCommitOpen}
        title={tr("确认写 Neo4j")}
        description={tr(`写 ${dataset} dataset 操作不可撤销，选中的实体/关系会被合并到知识图谱。`)}
        onConfirm={handleCommit}
        confirmText={tr("写 Neo4j")}
        destructive
      />
    </div>
  );
};

export default PreviewPage;
```

```bash
cd packages/web && bun run typecheck && bun run lint && bun run test
git add packages/web/app/\[locale\]/knowledge/extract/
git commit -m "feat(web): 3 个 extract 页面 (dataset 下拉 + upload + progress + preview + 3 出口弹窗)"
```

---

## Task 24: 1 个 Playwright 冒烟 spec + 收尾验证

```typescript
// packages/web/e2e/kg-extract.spec.ts
import { test, expect } from "@playwright/test";

test.describe("知识图谱抽取", () => {
  test("用户上传 .md → 选 motor → 选 llm_pydantic + heading → 启动 → 看到进度页", async ({
    page,
  }) => {
    await page.goto("/zh/knowledge/extract");

    // 选 dataset = motor
    await page.getByLabel("数据集").click();
    await page.getByRole("option", { name: "motor" }).click();

    // 选 llm_pydantic
    await page.getByLabel("抽取器").click();
    await page.getByRole("option", { name: "llm_pydantic" }).click();

    // 选 heading
    await page.getByLabel("切片器").click();
    await page.getByRole("option", { name: "heading" }).click();

    // 上传 .md
    await page.locator("input[type=file]").setInputFiles({
      name: "test.md",
      mimeType: "text/markdown",
      buffer: Buffer.from("# H1\n\n1LE0001 兼容 230V"),
    });

    // 启动
    await page.getByRole("button", { name: "启动抽取" }).click();

    // 跳到进度页 (URL 含 ?dataset=motor)
    await expect(page).toHaveURL(/\/knowledge\/extract\/[a-f0-9]+\?dataset=motor/);

    // 看到 TaskStatusBadge
    await expect(page.getByTestId("task-status-badge")).toBeVisible({ timeout: 30000 });
  });
});
```

```bash
cd packages/service
uv run pytest -q && uv run ruff format && uv run ruff check --fix && uv run pyright
cd packages/web
bun run test && bun run typecheck && bun run lint
bun run test:e2e -- --grep "知识图谱.*抽取"
git add packages/web/e2e/kg-extract.spec.ts
git commit -m "test(e2e): kg extract 1 个冒烟 spec (dataset=motor + 上传 + 选 + 启动 + 进度)"
```

## PR4 收尾验证 checklist

- [ ] **dataset 透传**: 抽取页选 dataset → BFF 透传 → 后端校验白名单 → PG kg_extract_items.dataset = motor → commit 写 KgClient(dataset=motor)
- [ ] **i18n 同步**: zh.json + en.json 13 个 key 含 `数据集` / `Dataset`
- [ ] **7 个 BFF route**: FormData / JSON / blob 透传, query param 透传
- [ ] **3 个前端页面**: 完整代码 (upload: 140 行; progress: 120 行; preview: 200 行)
- [ ] **路由跳转**: 全部用 `@/i18n/navigation` useRouter
- [ ] **e2e 冒烟**: 1 个 Playwright spec 跑通