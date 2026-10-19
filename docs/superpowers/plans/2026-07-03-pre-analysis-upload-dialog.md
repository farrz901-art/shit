# PreAnalysisUploadDialog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `admin/pre-analysis/` 列表页的大块 FileDropzone 改为"按钮 + 弹框"两步式上传流,1 个新弹框组件 (`pre-analysis-upload-dialog.tsx`),1 个共享文件大小格式化工具 (`lib/format.ts`),不改其他 4 个 FileDropzone 调用点。

**Architecture:** 触发按钮 (`<Button variant="default" size="lg"> + UploadCloud`) 触发 `AppDialog` 弹框,弹框内嵌 `<FileDropzone>` 选文件 → 选完后切到文件信息卡 (文件名 + `fmtSize` + 旁边"清空"按钮) → 点"开始上传"调 `preAnalysisUpload` → 成功 `toast.success` + 500ms 后关弹框 + 跳详情页 → 失败弹框保留 + error slot 红字。`isUploading` 期间 onOpenChange 守卫拒绝关弹框。

**Tech Stack:** React 19 + TypeScript + shadcn `<AppDialog>` + `<FileDropzone>` + sonner `toast` + `vi.useFakeTimers` + `IntlWrapper` test util。

---

## File Structure

**新增 (5)**:
- `packages/web/lib/format.ts` — 共享 `fmtSize` 工具
- `packages/web/lib/format.test.ts` — fmtSize 单元测试
- `packages/web/app/[locale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.tsx` — 弹框组件
- `packages/web/app/[locale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.test.tsx` — 弹框 4 个 test
- `packages/web/app/[locale]/admin/pre-analysis/_components/admin-pre-analysis-client.test.tsx` — 列表 1 个 test

**修改 (3)**:
- `packages/web/app/[locale]/admin/pre-analysis/_components/admin-pre-analysis-client.tsx` — FileDropzone → Button + 弹框
- `packages/web/app/[locale]/output/new/page.tsx` — 删 inline `fmtSize`,改 import `@/lib/format`
- `packages/web/messages/zh.json` + `en.json` — 新增 6 个 key (取消/开始上传/上传中/清空/上传成功/选择 PDF 上传)

**不修改**: 其他 4 个 FileDropzone 调用点 (`output/new` 仅删 fmtSize; `knowledge/documents/import`, `knowledge/extract`, `evaluate/new` 0 改动)。

---

## Task 1: 抽共享 `lib/format.ts` + 单元测试

**Files:**
- Create: `packages/web/lib/format.ts`
- Create: `packages/web/lib/format.test.ts`
- Modify: `packages/web/app/[locale]/output/new/page.tsx:18,26-34`

- [ ] **Step 1: 写 `lib/format.test.ts` 失败测试**

```typescript
// packages/web/lib/format.test.ts
import { describe, expect, it } from "vitest";
import { fmtSize } from "./format";

describe("fmtSize", () => {
  it("< 1KB 显示 B", () => {
    expect(fmtSize(0)).toBe("0 B");
    expect(fmtSize(512)).toBe("512 B");
  });

  it("< 1MB 显示 KB (1 位小数)", () => {
    expect(fmtSize(1024)).toBe("1.0 KB");
    expect(fmtSize(15 * 1024)).toBe("15.0 KB");
  });

  it(">= 1MB 显示 MB (1 位小数)", () => {
    expect(fmtSize(1024 * 1024)).toBe("1.0 MB");
    expect(fmtSize(12.3 * 1024 * 1024)).toBe("12.3 MB");
    expect(fmtSize(100 * 1024 * 1024)).toBe("100.0 MB");
  });
});
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd packages/web && bun run test lib/format.test.ts`
Expected: FAIL — "Cannot find module './format'"

- [ ] **Step 3: 写 `lib/format.ts` 实现**

```typescript
// packages/web/lib/format.ts
import { ONE, ONE_KB } from "@/const";

/**
 * 字节数 → 人类可读文件大小 (B / KB / MB).
 * 1 位小数 (跟 output/new/page.tsx:26 行为完全一致).
 *
 * @param val 字节数
 * @returns 形如 "0 B" / "15.0 KB" / "12.3 MB"
 */
export const fmtSize = (val: number): string => {
  if (val < ONE_KB) {
    return `${val} B`;
  }
  if (val < ONE_KB * ONE_KB) {
    return `${(val / ONE_KB).toFixed(ONE)} KB`;
  }
  return `${(val / ONE_KB / ONE_KB).toFixed(ONE)} MB`;
};
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd packages/web && bun run test lib/format.test.ts`
Expected: 3 passed

- [ ] **Step 5: 改 `output/new/page.tsx` 删 inline `fmtSize`**

Edit `packages/web/app/[locale]/output/new/page.tsx`:
- 删除 line 26-34 (`const fmtSize = ...` block)
- 改 line 18 import: 删 `ONE, ONE_KB, ZERO` 不变,新增 `import { fmtSize } from "@/lib/format";`

改完:
```typescript
// line 18-19 替换
import { ZERO } from "@/const";
import { fmtSize } from "@/lib/format";
```

- [ ] **Step 6: 跑 output/new 测试验回归**

Run: `cd packages/web && bun run test app/[locale]/output/new/page.test.tsx`
Expected: 全部 existing passed (0 regression)

- [ ] **Step 7: 跑 lint + typecheck**

Run: `cd packages/web && bun run lint && bun run typecheck`
Expected: 0 error

- [ ] **Step 8: Commit**

```bash
git add packages/web/lib/format.ts packages/web/lib/format.test.ts packages/web/app/[locale]/output/new/page.tsx
git commit -m "refactor(web): extract fmtSize to lib/format for reuse"
```

---

## Task 2: 加 6 个 i18n key (zh + en)

**Files:**
- Modify: `packages/web/messages/zh.json:439 附近`
- Modify: `packages/web/messages/en.json:439 附近`

- [ ] **Step 1: 查现有 zh.json line 439 位置**

Run: `cd packages/web && grep -n "上传 PDF" messages/zh.json`
Expected: `439:  "上传 PDF": "上传 PDF",`

- [ ] **Step 2: 在 zh.json line 439 之后加 6 个 key**

Edit `packages/web/messages/zh.json`:
```json
  "上传 PDF": "上传 PDF",
  "选择 PDF 上传": "选择 1 个 PDF 文件 (≤100MB), 后台跑预分析",
  "取消": "取消",
  "开始上传": "开始上传",
  "上传中…": "上传中…",
  "清空": "清空",
  "上传成功": "上传成功",
```

> ⚠️ zh value 用 `…` (U+2026 1 字符), 不要 `...` (3 dot)

- [ ] **Step 3: 在 en.json line 439 之后加 6 个 key**

Edit `packages/web/messages/en.json`:
```json
  "上传 PDF": "Upload PDF",
  "选择 PDF 上传": "Select 1 PDF file (≤100MB), pre-analysis runs in background",
  "取消": "Cancel",
  "开始上传": "Start Upload",
  "上传中…": "Uploading...",
  "清空": "Clear",
  "上传成功": "Upload successful",
```

- [ ] **Step 4: 跑 i18n 自检**

Run: `cd packages/web && bun run test messages/__tests__/i18n.test.ts`
Expected: 6 passed (key 集合完全一致 + value=key identity)

- [ ] **Step 5: Commit**

```bash
git add packages/web/messages/zh.json packages/web/messages/en.json
git commit -m "i18n(web): add pre-analysis upload dialog keys"
```

---

## Task 3: 写 `pre-analysis-upload-dialog.tsx` 4 个失败测试

**Files:**
- Create: `packages/web/app/[locale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.test.tsx`

- [ ] **Step 1: 写测试文件**

```typescript
// packages/web/app/[locale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.test.tsx
"use client";

// pre-analysis 上传弹框 4 个独立测试 (mode 1 mock)
// mock sonner toast + preAnalysisUpload + react-dropzone 内部 click
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { IntlWrapper } from "@/lib/test-utils/intl-wrapper";
import { PreAnalysisUploadDialog } from "./pre-analysis-upload-dialog";

const toastSuccessMock = vi.fn();
const preAnalysisUploadMock = vi.fn();

vi.mock("sonner", () => ({
  toast: { success: (...args: unknown[]) => toastSuccessMock(...args) },
}));

vi.mock("@/lib/api/pre-analysis", () => ({
  preAnalysisUpload: (...args: unknown[]) => preAnalysisUploadMock(...args),
}));

afterEach(() => {
  vi.restoreAllMocks();
  toastSuccessMock.mockReset();
  preAnalysisUploadMock.mockReset();
});

const renderDialog = (
  props: Partial<React.ComponentProps<typeof PreAnalysisUploadDialog>> = {},
): ReturnType<typeof render> => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <IntlWrapper locale="zh">
        <PreAnalysisUploadDialog
          onOpenChange={vi.fn()}
          onSuccess={vi.fn()}
          open={true}
          {...props}
        />
      </IntlWrapper>
    </QueryClientProvider>,
  );
};

const FAKE_FILE_SIZE_BYTES = 1024 * 1024;
const makeFakePdf = (name: string): File =>
  new File([new Uint8Array(FAKE_FILE_SIZE_BYTES)], name, { type: "application/pdf" });

// oxlint-disable-next-line max-statements -- 4 个 test 描述块, 不拆分
describe("PreAnalysisUploadDialog", () => {
  it("open=true 渲染 title + FileDropzone + 取消/开始按钮 (开始 disabled)", () => {
    renderDialog();
    // AppDialog title
    expect(screen.getByText("上传 PDF")).toBeInTheDocument();
    // FileDropzone 默认 title
    expect(screen.getByText(/拖文件到这/)).toBeInTheDocument();
    // footer 按钮
    expect(screen.getByRole("button", { name: "取消" })).toBeInTheDocument();
    const startBtn = screen.getByRole("button", { name: "开始上传" });
    expect(startBtn).toBeInTheDocument();
    expect(startBtn).toBeDisabled();
  });

  it("选文件 → 文件信息 + fmtSize 渲染 + 清空按钮 + 开始上传 enabled", () => {
    renderDialog();
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [makeFakePdf("test.pdf")] } });
    // 文件名 + fmtSize (1.0 MB)
    expect(screen.getByText("test.pdf")).toBeInTheDocument();
    expect(screen.getByText("1.0 MB")).toBeInTheDocument();
    // 清空按钮
    expect(screen.getByRole("button", { name: "清空" })).toBeInTheDocument();
    // 开始上传 enabled
    expect(screen.getByRole("button", { name: "开始上传" })).not.toBeDisabled();
  });

  it("点开始上传 → preAnalysisUpload 调 + toast.success + 500ms 后 onSuccess + onOpenChange(false)", async () => {
    vi.useFakeTimers();
    const onOpenChange = vi.fn();
    const onSuccess = vi.fn();
    preAnalysisUploadMock.mockResolvedValue({
      task_id: "pa-new-1",
      state: "pending",
      pdf_filename: "test.pdf",
    });
    renderDialog({ onOpenChange, onSuccess });
    fireEvent.change(document.querySelector('input[type="file"]') as HTMLInputElement, {
      target: { files: [makeFakePdf("test.pdf")] },
    });
    fireEvent.click(screen.getByRole("button", { name: "开始上传" }));
    // 立刻调 preAnalysisUpload, toast.success 已触发
    await waitFor(() => {
      expect(preAnalysisUploadMock).toHaveBeenCalledTimes(1);
      expect(toastSuccessMock).toHaveBeenCalledWith("上传成功");
    });
    // 500ms 还没到, callback 还没触发
    expect(onSuccess).not.toHaveBeenCalled();
    expect(onOpenChange).not.toHaveBeenCalled();
    // 推进 500ms
    vi.advanceTimersByTime(500);
    expect(onSuccess).toHaveBeenCalledWith("pa-new-1");
    expect(onOpenChange).toHaveBeenCalledWith(false);
    vi.useRealTimers();
  });

  it("preAnalysisUpload 抛错 → uploadError 设置 + 弹框不关 + error slot 展示", async () => {
    const onOpenChange = vi.fn();
    preAnalysisUploadMock.mockRejectedValue(new Error("PDF > 100MB"));
    renderDialog({ onOpenChange });
    fireEvent.change(document.querySelector('input[type="file"]') as HTMLInputElement, {
      target: { files: [makeFakePdf("test.pdf")] },
    });
    fireEvent.click(screen.getByRole("button", { name: "开始上传" }));
    await waitFor(() => {
      expect(screen.getByText("PDF > 100MB")).toBeInTheDocument();
    });
    // 弹框不关
    expect(onOpenChange).not.toHaveBeenCalled();
    // toast 不调
    expect(toastSuccessMock).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: 跑测试确认全部失败**

Run: `cd packages/web && bun run test app/[locale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.test.tsx`
Expected: 4 failed — "Cannot find module './pre-analysis-upload-dialog'"

- [ ] **Step 3: Commit (red)**

```bash
git add packages/web/app/[locale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.test.tsx
git commit -m "test(web): add failing tests for pre-analysis upload dialog"
```

---

## Task 4: 写 `pre-analysis-upload-dialog.tsx` 实现 (green)

**Files:**
- Create: `packages/web/app/[locale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.tsx`

- [ ] **Step 1: 写实现**

```tsx
// packages/web/app/[locale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.tsx
"use client";
// pre-analysis 上传弹框 (2026-07-03) — 替列表页 FileDropzone
// 3 段式: 选文件 → 文件信息+清空 → 上传 (成功 toast + 500ms 关弹框跳详情页, 失败保留弹框)

import { useState } from "react";
import { FileText, UploadCloud, X } from "lucide-react";
import { toast } from "sonner";
import { useTranslations } from "next-intl";

import { AppDialog } from "@/components/common/dialog/app-dialog";
import { FileDropzone } from "@/components/common/input/app-file-dropzone";
import { Button } from "@/components/ui/button";
import { fmtSize } from "@/lib/format";
import { preAnalysisUpload } from "@/lib/api/pre-analysis";

const DIALOG_CLOSE_DELAY_MS = 500;
const PDF_MAX_SIZE_MB = 100;

export interface PreAnalysisUploadDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** 上传成功回调, 父组件负责 router.push 到详情页 */
  onSuccess: (taskId: string) => void;
}

export const PreAnalysisUploadDialog = ({
  open,
  onOpenChange,
  onSuccess,
}: PreAnalysisUploadDialogProps) => {
  const translate = useTranslations();
  const [pickedFile, setPickedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // 守卫: 上传中拒绝关弹框
  const handleOpenChange = (nextOpen: boolean) => {
    if (!nextOpen && isUploading) {
      return;
    }
    if (!nextOpen) {
      // 关弹框时清状态, 下次打开干净
      setPickedFile(null);
      setUploadError(null);
    }
    onOpenChange(nextOpen);
  };

  const handleClear = (): void => {
    setPickedFile(null);
    setUploadError(null);
  };

  const handleUpload = async (): Promise<void> => {
    if (!pickedFile || isUploading) {
      return;
    }
    setIsUploading(true);
    setUploadError(null);
    try {
      const result = await preAnalysisUpload(pickedFile);
      toast.success(translate("上传成功"));
      setTimeout(() => {
        onOpenChange(false);
        onSuccess(result.task_id);
      }, DIALOG_CLOSE_DELAY_MS);
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : String(error));
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <AppDialog
      open={open}
      onOpenChange={handleOpenChange}
      title={translate("上传 PDF")}
      description={translate("选择 PDF 上传")}
      icon={<UploadCloud className="h-5 w-5" />}
      maxWidth="md"
      error={uploadError}
      errorTestid="upload-dialog-error"
      footer={
        <>
          <Button
            variant="outline"
            onClick={() => handleOpenChange(false)}
            disabled={isUploading}
          >
            {translate("取消")}
          </Button>
          <Button
            onClick={handleUpload}
            disabled={!pickedFile || isUploading}
            data-testid="upload-dialog-start"
          >
            {isUploading ? translate("上传中…") : translate("开始上传")}
          </Button>
        </>
      }
    >
      {pickedFile === null ? (
        <FileDropzone
          onFile={setPickedFile}
          accept=".pdf"
          maxSizeMB={PDF_MAX_SIZE_MB}
          title={translate("点击上传按钮开始")}
        />
      ) : (
        <div
          data-testid="upload-dialog-file-info"
          className="flex items-center justify-between gap-3 rounded-lg border border-border/60 bg-card/40 p-4"
        >
          <div className="flex min-w-0 items-center gap-3">
            <FileText className="h-5 w-5 shrink-0 text-muted-foreground" />
            <div className="min-w-0">
              <div className="truncate text-sm font-medium text-foreground">
                {pickedFile.name}
              </div>
              <div className="text-xs text-muted-foreground">
                {fmtSize(pickedFile.size)}
              </div>
            </div>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleClear}
            disabled={isUploading}
            data-testid="upload-dialog-clear"
          >
            <X className="mr-1 h-4 w-4" />
            {translate("清空")}
          </Button>
        </div>
      )}
    </AppDialog>
  );
};
```

- [ ] **Step 2: 跑弹框 4 个测试确认全绿**

Run: `cd packages/web && bun run test app/[locale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.test.tsx`
Expected: 4 passed

- [ ] **Step 3: 跑 i18n 自检 + 全 pre-analysis test**

Run: `cd packages/web && bun run test messages/__tests__/i18n.test.ts app/[locale]/admin/pre-analysis/`
Expected: i18n 6 passed + pre-analysis 弹框 4 passed + 现有 page 3 passed

- [ ] **Step 4: 跑 lint + typecheck**

Run: `cd packages/web && bun run lint && bun run typecheck`
Expected: 0 error

- [ ] **Step 5: Commit (green)**

```bash
git add packages/web/app/[locale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.tsx
git commit -m "feat(web): add pre-analysis upload dialog component"
```

---

## Task 5: 改 `admin-pre-analysis-client.tsx` 用按钮 + 弹框

**Files:**
- Modify: `packages/web/app/[locale]/admin/pre-analysis/_components/admin-pre-analysis-client.tsx`

- [ ] **Step 1: 改 import + 删 FileDropzone**

把 `FileDropzone` import 换成 `PreAnalysisUploadDialog` + 加 `Button` + `UploadCloud` icon:

```typescript
// 删:
import { FileDropzone } from "@/components/common/input/app-file-dropzone";
// 改:
import { Button } from "@/components/ui/button";
import { UploadCloud } from "lucide-react";
import { useState } from "react";
import { PreAnalysisUploadDialog } from "./pre-analysis-upload-dialog";
```

- [ ] **Step 2: 加 `isDialogOpen` state + 改组件主体**

```typescript
export const AdminPreAnalysisClient = (): React.ReactElement => {
  const translate = useTranslations();
  const router = useRouter();
  const [isDialogOpen, setIsDialogOpen] = useState(false);

  const { data, error, isLoading } = useQuery({...});  // 保持

  const handleUpload = async (file: File): Promise<void> => {
    const result = await preAnalysisUpload(file);
    router.push(`/admin/pre-analysis/${result.task_id}`);
  };
  // ↑ handleUpload 现在不再被 FileDropzone 直接调, 删掉或保留都行.
  //   弹框自己调 preAnalysisUpload, onSuccess 跳路由.
  //   删 handleUpload 避免 lint 报 unused.
```

- [ ] **Step 3: 替换 JSX (FileDropzone → Button + Dialog)**

```tsx
  return (
    <div className="space-y-6 p-6">
      <PageHero eyebrow="admin" title={translate("PDF 预分析")} />
      <div className="flex justify-end">
        <Button
          variant="default"
          size="lg"
          onClick={() => setIsDialogOpen(true)}
          data-testid="pre-analysis-upload-trigger"
        >
          <UploadCloud className="mr-2 h-4 w-4" />
          {translate("上传 PDF")}
        </Button>
      </div>
      {error ? (
        <ErrorBanner description={String(error)} variant="destructive" />
      ) : (
        <DataTable ... />  // 保持
      )}
      <PreAnalysisUploadDialog
        open={isDialogOpen}
        onOpenChange={setIsDialogOpen}
        onSuccess={(taskId) => {
          setIsDialogOpen(false);
          router.push(`/admin/pre-analysis/${taskId}`);
        }}
      />
    </div>
  );
};
```

- [ ] **Step 4: 跑 page 现有测试看是否回归**

Run: `cd packages/web && bun run test app/[locale]/admin/pre-analysis/page.test.tsx`
Expected: 现有 3 test:
- "renders DataTable with tasks" — 应仍绿 (DataTable 0 改动)
- "renders upload button" — 仍绿 (触发按钮文字也含"上传 PDF")
- "shows empty state when no tasks" — 仍绿

- [ ] **Step 5: Commit**

```bash
git add packages/web/app/[locale]/admin/pre-analysis/_components/admin-pre-analysis-client.tsx
git commit -m "feat(web): replace pre-analysis FileDropzone with upload button + dialog"
```

---

## Task 6: 写 `admin-pre-analysis-client.test.tsx` 1 个新测试 (弹框联动)

**Files:**
- Create: `packages/web/app/[locale]/admin/pre-analysis/_components/admin-pre-analysis-client.test.tsx`

- [ ] **Step 1: 写测试文件**

```typescript
// packages/web/app/[locale]/admin/pre-analysis/_components/admin-pre-analysis-client.test.tsx
"use client";

// 验证: 1) 默认弹框关闭 2) 点触发按钮弹框打开
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { IntlWrapper } from "@/lib/test-utils/intl-wrapper";
import { AdminPreAnalysisClient } from "./admin-pre-analysis-client";

afterEach(() => {
  vi.restoreAllMocks();
});

const renderWithProviders = (): ReturnType<typeof render> => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <IntlWrapper locale="zh">
        <AdminPreAnalysisClient />
      </IntlWrapper>
    </QueryClientProvider>,
  );
};

describe("AdminPreAnalysisClient (button + dialog)", () => {
  it("默认弹框关闭, 点触发按钮后弹框打开", () => {
    globalThis.fetch = vi.fn(async () =>
      Response.json({ tasks: [] }, { status: 200 }),
    ) as unknown as typeof fetch;

    renderWithProviders();
    // 默认 FileDropzone 不应渲染 (改成按钮了)
    expect(screen.queryByText(/拖文件到这/)).not.toBeInTheDocument();
    // 触发按钮存在
    const trigger = screen.getByTestId("pre-analysis-upload-trigger");
    expect(trigger).toBeInTheDocument();
    // 弹框标题未显示 (AppDialog open=false 不渲染 children)
    expect(screen.queryByText("选择 PDF 上传")).not.toBeInTheDocument();
    // 点按钮
    fireEvent.click(trigger);
    // 弹框描述出现
    expect(screen.getByText("选择 PDF 上传")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: 跑测试确认通过**

Run: `cd packages/web && bun run test app/[locale]/admin/pre-analysis/_components/admin-pre-analysis-client.test.tsx`
Expected: 1 passed

- [ ] **Step 3: 跑所有 pre-analysis 相关 test 确认 0 回归**

Run: `cd packages/web && bun run test app/[locale]/admin/pre-analysis/ messages/__tests__/i18n.test.ts`
Expected: 全部 passed:
- 弹框 4
- client 1
- page 3 (现有)
- i18n 6

- [ ] **Step 4: Commit**

```bash
git add packages/web/app/[locale]/admin/pre-analysis/_components/admin-pre-analysis-client.test.tsx
git commit -m "test(web): add button+dialog integration test for pre-analysis list"
```

---

## Task 7: 全套验证 + format

**Files:** 0 改动,只跑命令

- [ ] **Step 1: 跑全套 typecheck + lint**

Run: `cd packages/web && bun run typecheck && bun run lint`
Expected: 0 error

- [ ] **Step 2: 跑 format:check**

Run: `cd packages/web && bun run format:check`
Expected: 0 files need formatting. 如果有 fail, 跑 `bun run format` 自动修

- [ ] **Step 3: 跑全套 vitest (719 + 新 8 = 727)**

Run: `cd packages/web && bun run test`
Expected: 全部 passed, 0 new fail

- [ ] **Step 4: 手动 smoke test**

启动 dev server:
```bash
# terminal 1
cd packages/service && uv run python main.py

# terminal 2
cd packages/web && bun run dev
```

浏览器走查 (项目 [run skill](superpowers:run) 模式):
- 访问 `http://localhost:3000/zh/admin/pre-analysis`
- 列表页: 拖拽区消失, 右上角"上传 PDF" 按钮 ✅
- 点按钮 → 弹框, 内含 FileDropzone + 取消/开始上传 ✅
- 选 .pdf → 文件信息 + "1.0 MB" + 清空 + 开始上传 enabled ✅
- 选 >100MB / .txt → FileDropzone 内红字, pickedFile 不更新 ✅
- 点开始上传 → toast "上传成功" → 500ms 后关弹框 → 跳详情页 ✅
- (模拟失败) 关后端再上传 → 弹框保留 + error 红字 ✅

- [ ] **Step 5: git status 检查**

Run: `cd packages/web && git status`
Expected: 0 uncommitted 改动 (Task 1-6 全已 commit)

- [ ] **Step 6: 完成**

按 [feedback-cleanup-worktree-after-merge](feedback-cleanup-worktree-after-merge.md),如果用了 worktree 跑 `git worktree remove`.

按 [superpowers:finishing-a-development-branch](superpowers:finishing-a-development-branch) 决定 merge/PR 方式.
