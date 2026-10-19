# JSX 违规整改实施计划 (2026-06-29)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 整改 [JSX 违规审计报告 (2026-06-29)](../audits/2026-06-29-jsx-violations.md) 中发现的 25 项违规 — 5 个 P0 大文件拆分子组件 / hook、10 个 P1 IIFE-in-JSX 模式替换为命名函数、5 个 P2 杂项整理，达成项目"禁止 JSX 中写过多元语句和大数组" + "单文件 ≤ 300 行"规约的合规状态。

**Architecture:**
- **Phase 1 (P0)**: 5 个 > 300 行的文件拆 `_components/` 子组件或抽 `useXxx` hook，每个文件一个 task，独立 commit。任务顺序按依赖关系排：先拆 `composer-attachments`（hook 模式示范）→ `profile-fields`（参考 hook 模式）→ 其他 3 个
- **Phase 2 (P1)**: 10 项 IIFE-in-JSX / 嵌套三元 / switch-case 模式，统一用模块顶层命名函数 / Record lookup / 子组件替，按文件分组 commit
- **Phase 3 (P2)**: 5 项杂项整理（小文件、低严重度），单文件单 commit
- **每 task 都是原子 commit**：可独立 review/bisect/revert

**Tech Stack:** React 19 / TypeScript 8 / shadcn/ui / next-intl 4 / vitest + jsdom

**Source:** [JSX 违规审计报告](../audits/2026-06-29-jsx-violations.md)

---

## 关键约束（每个 task 必读）

1. **TDD 不是每 task 必跑** — 这次是"代码移动 + 重命名"型整改，原有测试覆盖的行为不应改变。Task 内只跑 lint + typecheck + 该文件已有测试，不需要为每个 task 新写测试
2. **禁止改业务逻辑** — 只移动 / 提取 / 重命名，不修改 JSX 表达式的结果或副作用
3. **禁止新增 shim/兼容代码** — 见项目 `feedback-no-shim-no-minimal-changes` 规约
4. **禁止删除原注释** — 见 `.claude/CLAUDE.md` §编码规范
5. **必须保持 import 字母排序** — oxlint sort-imports 规则
6. **commit 前必须跑**：format → lint fix → typecheck → 该文件测试 → commit
7. **commit message 前缀**：
   - `refactor(<scope>): 拆 _components/` （拆子组件）
   - `refactor(<scope>): 抽 useXxx hook` （抽 hook）
   - `refactor(<scope>): IIFE → 命名函数` （IIFE 替换）
   - `refactor(<scope>): 内联数组 → 模块级常量` （数组外提）
8. **复杂字符串不需要 i18n** — 现有文件用的硬编中文保留，不在本次整改范围

---

## 文件结构

### Phase 1 — P0 大文件拆分（5 个 task）

| Task | 文件 | 操作 | 目标行数 |
|---|---|---|---|
| 1 | `components/chat/composer-attachments.tsx` | 抽 `useComposerAttachments` hook + 拆 `<ImageSlot>` `<FileSlot>` `<VoiceSlot>` | 329 → < 100 |
| 2 | `app/[locale]/admin/profile-fields/page.tsx` | 抽 `<CreateFieldDialog>` `<EditFieldDialog>` + `useProfileFieldsHandlers` hook | 413 → < 200 |
| 3 | `app/[locale]/admin/users/_components/admin-users-table.tsx` | 抽 `getAdminLabel/getActiveLabel` helper + `useUserActions` hook | 387 → < 250 |
| 4 | `app/[locale]/buyers/page.tsx` | 抽 `FIELD_TYPE_RENDERERS` lookup + `useBuyersColumns` hook + 拆 `<BuyersToolbar>` | 377 → < 250 |
| 5 | `app/[locale]/knowledge/documents/import/_components/documents-import-form.tsx` | 拆 `<StepIndicator>` `<UploadStep>` `<ParseResultCard>` `<TemplateDownload>` | 347 → < 150 |

### Phase 2 — P1 IIFE-in-JSX 模式替换（7 个 task）

| Task | 文件 | 操作 |
|---|---|---|
| 6 | `components/ui/calendar.tsx` | 抽 `CALENDAR_CLASS_NAMES` `CALENDAR_COMPONENTS` 常量 + `getCaptionLabelClass` 纯函数 |
| 7 | `components/chat/message-bubble.tsx` | 替换两个 IIFE → 抽 `buildBubbleClass()` + `<AssistantBody>` 子组件 + `markdownComponents` 提到模块顶层 |
| 8 | `components/chat/memory-management-dialog.tsx` | `useMemoryFilter` 内 IIFE → `useMemo` |
| 9 | `components/user-menu.tsx` | 7 元素 items → `buildMenuItems()` 函数 + `useMemo` |
| 10 | `components/common/table/data-table.tsx` | `useReactTable` 28 行 inline config → `buildTableOptions()` 函数 |
| 11 | `components/common/table/data-table-body.tsx` | IIFE expanded row → `renderExpandedRow()` 命名函数 |
| 12 | `components/common/button/app-copy-button.tsx` | 单层 IIFE → 三元 |

### Phase 3 — P2 杂项整理（3 个 task）

| Task | 文件 | 操作 |
|---|---|---|
| 13 | `app/[locale]/output/[task_id]/_components/task-info.tsx` | `getStatusText` 4 个 if 分支 → `STATE_TEXT_BUILDERS` Record 查找 |
| 14 | `app/[locale]/evaluate/[id]/_components/run-detail-view.tsx` | 4 个 `<MetricBar>` 硬编 → `METRIC_DEFS` 数组 + map + 抽 `<RunActions>` 子组件 + `mapSampleForTable` 函数 |
| 15 | `app/[locale]/admin/dicts/_components/admin-dicts-client.tsx` (临界 290 行) | 审计判定无违规，但行数临界，需要预防性拆分至少 1 个 hook |

**总计**: 15 个 task，每个 task = 1 个 commit

---

## Phase 1 — P0 大文件拆分（5 task）

### Task 1: 拆 `composer-attachments.tsx` (329 → < 100 行)

**Files:**
- Create: `packages/web/components/chat/use-composer-attachments.ts` (新 hook 文件)
- Create: `packages/web/components/chat/image-slot.tsx` (新子组件)
- Create: `packages/web/components/chat/file-slot.tsx` (新子组件)
- Create: `packages/web/components/chat/voice-slot.tsx` (新子组件)
- Modify: `packages/web/components/chat/composer-attachments.tsx` (主组件化简)
- Modify: `packages/web/components/chat/composer-attachments.test.tsx` (如有测试，调整 mock)

**审计依据**: A-03 (ActivePanel if-else 链)、A-04 (主组件 91 行混逻辑)、C-05 (>300 行)

- [ ] **Step 1: 抽取 `useComposerAttachments` hook**

创建 `packages/web/components/chat/use-composer-attachments.ts`:

```typescript
/**
 * useComposerAttachments (2026-06-29)
 * 把 ComposerAttachments 主组件的 items state + upload/remove/toggle/close 4 个 handler 抽出来
 * 主组件只负责 UI 组合, hook 管所有状态变更 + 上传链 (presign → fallback multipart)
 * 上传链: doUpload (presign/finalize → multipart fallback)
 */
"use client";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import type { ChatFile } from "@/lib/chat/types";
import { apiFetch } from "@/lib/api/config";
import { log } from "@/lib/log";
import { uploadFile } from "@/lib/api/chat";

// 内部附件状态: 比 ChatFile 多个 status 字段
export interface AttachmentItem extends ChatFile {
  id: string;
  name: string;
  status: "uploading" | "done" | "error";
}

const RANDOM_ID_RADIX = 36;
const RANDOM_ID_START = 2;
const EMPTY_URI = "";

const inferType = (mime: string): ChatFile["type"] => {
  if (mime.startsWith("image/")) {
    return "image";
  }
  if (mime.startsWith("audio/")) {
    return "audio";
  }
  return "document";
};

const uploadFileViaPresign = async (
  file: File,
): Promise<{ uploadFileId: string; uri: string }> => {
  const { uri, put_url, mime } = await apiFetch<{
    uri: string;
    put_url: string | null;
    mime: string;
  }>("/api/chat/files/presign", {
    body: { mime: file.type, name: file.name, size: file.size },
    method: "POST",
  });
  if (!put_url) {
    throw new Error("presign 未返 PUT URL, 需要 fallback");
  }
  const putResp = await fetch(put_url, {
    body: file,
    headers: { "Content-Type": mime },
    method: "PUT",
  });
  if (!putResp.ok) {
    throw new Error(`PUT MinIO 失败: ${putResp.status}`);
  }
  const data = await apiFetch<{ uploadFileId: string; uri: string }>(
    "/api/chat/files/finalize",
    {
      body: { mime, name: file.name, uri },
      method: "POST",
    },
  );
  return { uploadFileId: data.uploadFileId, uri: data.uri };
};

const doUpload = async (
  file: File,
): Promise<{ uploadFileId: string; uri: string }> => {
  try {
    return await uploadFileViaPresign(file);
  } catch (error) {
    log.warn("presign/finalize 失败, fallback multipart", { error: String(error) });
    const out = await uploadFile(file);
    return { uploadFileId: out.uploadFileId, uri: out.uri ?? EMPTY_URI };
  }
};

export type Slot = "image" | "file" | "voice";

export const useComposerAttachments = (
  onAttachmentsChange: (files: ChatFile[]) => void,
) => {
  const [items, setItems] = useState<AttachmentItem[]>([]);
  const [activeSlot, setActiveSlot] = useState<Slot | null>(null);

  // 列表变更 → 提取 status=done 的项, 上抛给 Composer
  useEffect(() => {
    const done = items
      .filter((item) => item.status === "done")
      .map<ChatFile>(({ id: _id, name: _name, status: _s, ...rest }) => rest);
    onAttachmentsChange(done);
  }, [items, onAttachmentsChange]);

  const uploadAndAdd = useCallback(async (file: File): Promise<void> => {
    const tempId = `tmp-${Date.now()}-${Math.random().toString(RANDOM_ID_RADIX).slice(RANDOM_ID_START)}`;
    setItems((prev) => [
      ...prev,
      {
        id: tempId,
        name: file.name,
        status: "uploading",
        transferMethod: "local_file",
        type: inferType(file.type),
      },
    ]);
    try {
      const { uploadFileId, uri } = await doUpload(file);
      setItems((prev) =>
        prev.map((item) => {
          if (item.id === tempId) {
            return {
              ...item,
              id: uploadFileId,
              status: "done",
              uploadFileId,
              url: uri || item.url,
            };
          }
          return item;
        }),
      );
    } catch (error) {
      setItems((prev) =>
        prev.map((item) => {
          if (item.id === tempId) {
            return { ...item, status: "error" };
          }
          return item;
        }),
      );
      toast.error(`上传失败: ${(error as Error).message}`);
    }
  }, []);

  const removeItem = useCallback((id: string): void => {
    setItems((prev) => prev.filter((item) => item.id !== id));
  }, []);

  const toggleSlot = useCallback((slot: Slot) => {
    setActiveSlot((prev) => (prev === slot ? null : slot));
  }, []);

  const closeSlot = useCallback(() => {
    setActiveSlot(null);
  }, []);

  return { activeSlot, closeSlot, items, removeItem, toggleSlot, uploadAndAdd };
};
```

- [ ] **Step 2: 创建 3 个 slot 子组件**

创建 `packages/web/components/chat/image-slot.tsx`:

```typescript
"use client";
import { FileDropzone } from "@/components/common/input/app-file-dropzone";

const IMAGE_ACCEPT = "image/*";

export const ImageSlot = ({
  uploadAndAdd,
  closeSlot,
  title,
}: {
  uploadAndAdd: (file: File) => Promise<void>;
  closeSlot: () => void;
  title: string;
}) => (
  <FileDropzone
    accept={IMAGE_ACCEPT}
    onFile={(file: File) => {
      void uploadAndAdd(file);
      closeSlot();
    }}
    title={title}
  />
);
```

创建 `packages/web/components/chat/file-slot.tsx`:

```typescript
"use client";
import { FileDropzone } from "@/components/common/input/app-file-dropzone";

const FILE_ACCEPT = ".pdf,.docx,.xlsx,.txt,.md";

export const FileSlot = ({
  uploadAndAdd,
  closeSlot,
  title,
}: {
  uploadAndAdd: (file: File) => Promise<void>;
  closeSlot: () => void;
  title: string;
}) => (
  <FileDropzone
    accept={FILE_ACCEPT}
    onFile={(file: File) => {
      void uploadAndAdd(file);
      closeSlot();
    }}
    title={title}
  />
);
```

创建 `packages/web/components/chat/voice-slot.tsx`:

```typescript
"use client";
import { VoiceRecorder } from "./voice-recorder";

export const VoiceSlot = ({
  uploadAndAdd,
  closeSlot,
}: {
  uploadAndAdd: (file: File) => Promise<void>;
  closeSlot: () => void;
}) => (
  <VoiceRecorder
    onRecorded={async (blob, fileName) => {
      const file = new File([blob], fileName, { type: blob.type });
      await uploadAndAdd(file);
      closeSlot();
    }}
  />
);
```

- [ ] **Step 3: 化简 `composer-attachments.tsx` 主组件**

替换 `packages/web/components/chat/composer-attachments.tsx` 全部内容:

```typescript
/**
 * Composer 附件主组件 (2026-06-29 重构)
 * 3 个入口: 图片 / 文件 / 语音 (互斥)
 * 状态管理: useComposerAttachments hook (拆自本文件)
 * 子组件: ImageSlot / FileSlot / VoiceSlot (拆自原 ActivePanel if-else 链)
 * SlotButtons / ThumbnailList: 同文件内子组件
 */
"use client";
import { FileText, Image as ImageIcon, Loader2, Mic, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { ZERO } from "@/const";
import { FileSlot } from "./file-slot";
import { ImageSlot } from "./image-slot";
import { useComposerAttachments, type Slot } from "./use-composer-attachments";
import { VoiceSlot } from "./voice-slot";

export interface ComposerAttachmentsProps {
  /** 附件列表变更时回调, 把"已完成"的 ChatFile[] 传给父组件 */
  onAttachmentsChange: (files: import("@/lib/chat/types").ChatFile[]) => void;
}

const SlotButtons = ({
  toggleSlot,
  translation,
}: {
  toggleSlot: (slot: Slot) => void;
  translation: (key: string) => string;
}) => (
  <div className="flex items-center gap-1">
    <Button
      type="button"
      variant="ghost"
      size="icon"
      onClick={() => toggleSlot("image")}
      aria-label={translation("图片")}
      data-testid="composer-attach-image"
    >
      <ImageIcon className="h-4 w-4" />
    </Button>
    <Button
      type="button"
      variant="ghost"
      size="icon"
      onClick={() => toggleSlot("file")}
      aria-label={translation("文件")}
      data-testid="composer-attach-file"
    >
      <FileText className="h-4 w-4" />
    </Button>
    <Button
      type="button"
      variant="ghost"
      size="icon"
      onClick={() => toggleSlot("voice")}
      aria-label={translation("语音")}
      data-testid="composer-attach-voice"
    >
      <Mic className="h-4 w-4" />
    </Button>
  </div>
);

const ThumbnailList = ({
  items,
  removeItem,
}: {
  items: import("./use-composer-attachments").AttachmentItem[];
  removeItem: (id: string) => void;
}) => (
  <div className="flex flex-wrap gap-2" data-testid="composer-attachments-list">
    {items.map((item) => {
      const onClickRemove = () => removeItem(item.id);
      return (
        <div
          key={item.id}
          data-testid={`attachment-${item.id}`}
          data-attachment-uri={item.url ?? ""}
          className="flex items-center gap-2 rounded-md border bg-muted/50 px-2 py-1 text-xs"
        >
          {item.status === "uploading" && <Loader2 className="h-3 w-3 animate-spin" />}
          <span className="max-w-[160px] truncate">{item.name}</span>
          <button
            type="button"
            onClick={onClickRemove}
            data-testid={`attachment-remove-${item.id}`}
            aria-label="remove"
            className="text-muted-foreground hover:text-foreground"
          >
            <X className="h-3 w-3" />
          </button>
        </div>
      );
    })}
  </div>
);

export const ComposerAttachments = ({ onAttachmentsChange }: ComposerAttachmentsProps) => {
  const translation = useTranslations();
  const { activeSlot, closeSlot, items, removeItem, toggleSlot, uploadAndAdd } =
    useComposerAttachments(onAttachmentsChange);

  return (
    <div className="flex flex-col gap-2" data-testid="composer-attachments">
      <SlotButtons toggleSlot={toggleSlot} translation={translation} />
      {items.length > ZERO && <ThumbnailList items={items} removeItem={removeItem} />}
      {activeSlot === "image" && (
        <ImageSlot
          uploadAndAdd={uploadAndAdd}
          closeSlot={closeSlot}
          title={translation("图片")}
        />
      )}
      {activeSlot === "file" && (
        <FileSlot
          uploadAndAdd={uploadAndAdd}
          closeSlot={closeSlot}
          title={translation("文件")}
        />
      )}
      {activeSlot === "voice" && (
        <VoiceSlot uploadAndAdd={uploadAndAdd} closeSlot={closeSlot} />
      )}
    </div>
  );
};
```

- [ ] **Step 4: 跑 typecheck + lint + 测试**

```bash
cd c:/doc/Code/rag/packages/web
bun run typecheck
bun run lint
bun run test -- components/chat/composer-attachments.test.tsx
```

预期: 0 error, 0 lint warning, 测试全绿（行为不变）。

- [ ] **Step 5: 验证文件行数**

```bash
cd c:/doc/Code/rag/packages/web
wc -l components/chat/composer-attachments.tsx components/chat/use-composer-attachments.ts components/chat/image-slot.tsx components/chat/file-slot.tsx components/chat/voice-slot.tsx
```

预期:
- `composer-attachments.tsx` < 100 行
- 其他 4 个文件每个 < 150 行
- 总行数较原 329 行小幅增长（合理）

- [ ] **Step 6: Commit**

```bash
cd c:/doc/Code/rag
git add packages/web/components/chat/composer-attachments.tsx \
        packages/web/components/chat/use-composer-attachments.ts \
        packages/web/components/chat/image-slot.tsx \
        packages/web/components/chat/file-slot.tsx \
        packages/web/components/chat/voice-slot.tsx
git commit -m "refactor(chat): 拆 composer-attachments 为 hook + 3 slot 子组件 (329→<100 行)

- 抽 useComposerAttachments hook (含 items state + upload/remove/toggle/close)
- 拆 ActivePanel if-else 链为 ImageSlot/FileSlot/VoiceSlot 3 个子组件
- 主组件只负责 UI 组合

审计依据: A-03, A-04, C-05 (jsx-violations audit 2026-06-29)"
```

---

### Task 2: 拆 `profile-fields/page.tsx` (413 → < 200 行)

**Files:**
- Create: `packages/web/app/[locale]/admin/profile-fields/_components/create-field-dialog.tsx` (新 dialog)
- Create: `packages/web/app/[locale]/admin/profile-fields/_components/edit-field-dialog.tsx` (新 dialog)
- Create: `packages/web/app/[locale]/admin/profile-fields/_hooks/use-profile-fields-handlers.ts` (新 hook)
- Modify: `packages/web/app/[locale]/admin/profile-fields/page.tsx` (化简)
- Modify: `packages/web/app/[locale]/admin/profile-fields/page.test.tsx` (如有测试, 调整 mock)

**审计依据**: A-02, C-01 (>300 行 + 内联 5 handler + 2 个完整 AppDialog)

- [ ] **Step 1: 读取现状确认现有结构**

```bash
cd c:/doc/Code/rag/packages/web
ls app/[locale]/admin/profile-fields/
cat app/[locale]/admin/profile-fields/page.tsx | head -150
```

记录: `useFieldConfigs` / `useCreateFieldConfig` / `useUpdateFieldConfig` 是已存在的 hook（来自 `@/lib/api/profile-fields`），本 task 只拆本文件内的 5 个 handler + 2 个 dialog。

- [ ] **Step 2: 抽 `useProfileFieldsHandlers` hook**

创建 `packages/web/app/[locale]/admin/profile-fields/_hooks/use-profile-fields-handlers.ts`:

```typescript
/**
 * useProfileFieldsHandlers (2026-06-29)
 * 抽自 profile-fields/page.tsx 的 5 个 handler: handleCreate / handleEdit / handleEditSave / handleToggleActive / handleToggleConfirm
 * 主组件只管 UI state, hook 管所有 mutation + 错误处理
 */
"use client";
import { useState } from "react";
import { useCreateFieldConfig, useUpdateFieldConfig } from "@/lib/api/profile-fields";
import type { ProfileFieldConfig } from "@/lib/api/profile-fields/types";

export interface ProfileFieldsFormState {
  code: string;
  label: string;
  field_type: string;
  required: boolean;
  options: string[];
}

export const useProfileFieldsHandlers = (refetch: () => Promise<unknown>) => {
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [createForm, setCreateForm] = useState<ProfileFieldsFormState>({
    code: "",
    field_type: "text",
    label: "",
    options: [],
    required: false,
  });
  const [editTarget, setEditTarget] = useState<ProfileFieldConfig | null>(null);
  const [editForm, setEditForm] = useState<ProfileFieldsFormState>({
    code: "",
    field_type: "text",
    label: "",
    options: [],
    required: false,
  });
  const [toggleTarget, setToggleTarget] = useState<ProfileFieldConfig | null>(null);

  const createMutation = useCreateFieldConfig();
  const updateMutation = useUpdateFieldConfig();

  const handleCreate = async () => {
    try {
      await createMutation.mutateAsync(createForm);
      setCreateForm({ code: "", field_type: "text", label: "", options: [], required: false });
      await refetch();
    } catch (error) {
      setErrorMessage((error as Error).message);
    }
  };

  const handleEdit = (config: ProfileFieldConfig) => {
    setEditTarget(config);
    setEditForm({
      code: config.code,
      field_type: config.field_type,
      label: config.label,
      options: config.options ?? [],
      required: config.required,
    });
  };

  const handleEditSave = async () => {
    if (!editTarget) {
      return;
    }
    try {
      await updateMutation.mutateAsync({ ...editForm, id: editTarget.id });
      setEditTarget(null);
      await refetch();
    } catch (error) {
      setErrorMessage((error as Error).message);
    }
  };

  const handleToggleActive = (config: ProfileFieldConfig) => {
    setToggleTarget(config);
  };

  const handleToggleConfirm = async () => {
    if (!toggleTarget) {
      return;
    }
    try {
      await updateMutation.mutateAsync({
        ...toggleTarget,
        is_active: !toggleTarget.is_active,
      });
      setToggleTarget(null);
      await refetch();
    } catch (error) {
      setErrorMessage((error as Error).message);
    }
  };

  return {
    createForm,
    editForm,
    editTarget,
    errorMessage,
    handleCreate,
    handleEdit,
    handleEditSave,
    handleToggleActive,
    handleToggleConfirm,
    setCreateForm,
    setEditForm,
    setErrorMessage,
    toggleTarget,
  };
};
```

- [ ] **Step 3: 抽 `<CreateFieldDialog>` 子组件**

创建 `packages/web/app/[locale]/admin/profile-fields/_components/create-field-dialog.tsx`:

```typescript
"use client";
import { AppDialog } from "@/components/common/dialog/app-dialog";
import type { ProfileFieldsFormState } from "../_hooks/use-profile-fields-handlers";

const EMPTY_FORM: ProfileFieldsFormState = {
  code: "",
  field_type: "text",
  label: "",
  options: [],
  required: false,
};

export const CreateFieldDialog = ({
  open,
  onOpenChange,
  form,
  setForm,
  onSubmit,
  translation,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  form: ProfileFieldsFormState;
  setForm: (form: ProfileFieldsFormState) => void;
  onSubmit: () => Promise<void>;
  translation: (key: string) => string;
}) => (
  <AppDialog
    open={open}
    onOpenChange={onOpenChange}
    title={translation("新建画像字段")}
    onConfirm={onSubmit}
    confirmText={translation("创建")}
  >
    <div className="flex flex-col gap-3">
      {/* 字段输入: code/label/field_type/required/options */}
      <input
        type="text"
        value={form.code}
        onChange={(event) => setForm({ ...form, code: event.target.value })}
        placeholder={translation("字段代码")}
        className="border rounded px-3 py-2"
      />
      <input
        type="text"
        value={form.label}
        onChange={(event) => setForm({ ...form, label: event.target.value })}
        placeholder={translation("显示名称")}
        className="border rounded px-3 py-2"
      />
      <select
        value={form.field_type}
        onChange={(event) => setForm({ ...form, field_type: event.target.value })}
        className="border rounded px-3 py-2"
      >
        <option value="text">{translation("文本")}</option>
        <option value="number">{translation("数字")}</option>
        <option value="select">{translation("下拉选择")}</option>
        <option value="boolean">{translation("布尔")}</option>
      </select>
      <label className="flex items-center gap-2">
        <input
          type="checkbox"
          checked={form.required}
          onChange={(event) => setForm({ ...form, required: event.target.checked })}
        />
        {translation("必填")}
      </label>
    </div>
  </AppDialog>
);
```

- [ ] **Step 4: 抽 `<EditFieldDialog>` 子组件**

创建 `packages/web/app/[locale]/admin/profile-fields/_components/edit-field-dialog.tsx`:

```typescript
"use client";
import { AppDialog } from "@/components/common/dialog/app-dialog";
import type { ProfileFieldsFormState } from "../_hooks/use-profile-fields-handlers";

export const EditFieldDialog = ({
  open,
  onOpenChange,
  form,
  setForm,
  onSubmit,
  translation,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  form: ProfileFieldsFormState;
  setForm: (form: ProfileFieldsFormState) => void;
  onSubmit: () => Promise<void>;
  translation: (key: string) => string;
}) => (
  <AppDialog
    open={open}
    onOpenChange={onOpenChange}
    title={translation("编辑画像字段")}
    onConfirm={onSubmit}
    confirmText={translation("保存")}
  >
    <div className="flex flex-col gap-3">
      {/* 跟 CreateFieldDialog 字段一致, 但 code 字段 disabled */}
      <input
        type="text"
        value={form.code}
        disabled
        className="border rounded px-3 py-2 bg-muted"
      />
      <input
        type="text"
        value={form.label}
        onChange={(event) => setForm({ ...form, label: event.target.value })}
        placeholder={translation("显示名称")}
        className="border rounded px-3 py-2"
      />
      <select
        value={form.field_type}
        onChange={(event) => setForm({ ...form, field_type: event.target.value })}
        className="border rounded px-3 py-2"
      >
        <option value="text">{translation("文本")}</option>
        <option value="number">{translation("数字")}</option>
        <option value="select">{translation("下拉选择")}</option>
        <option value="boolean">{translation("布尔")}</option>
      </select>
      <label className="flex items-center gap-2">
        <input
          type="checkbox"
          checked={form.required}
          onChange={(event) => setForm({ ...form, required: event.target.checked })}
        />
        {translation("必填")}
      </label>
    </div>
  </AppDialog>
);
```

- [ ] **Step 5: 化简 page.tsx**

修改 `packages/web/app/[locale]/admin/profile-fields/page.tsx`:
- 删除 `useProfileFieldsHandlers` 5 个 handler 函数体（保持函数签名委托给 hook）
- 把 `<AppDialog>` 新增 + 编辑 2 个块替换为 `<CreateFieldDialog>` / `<EditFieldDialog>`
- 保留 DataTable + 列定义 + PageHero + 错误条

预期 page.tsx < 200 行。**重要**: 用 Edit 替换而非 Write 全文件，避免覆盖注释。

- [ ] **Step 6: 跑测试 + 验证**

```bash
cd c:/doc/Code/rag/packages/web
bun run typecheck
bun run lint
bun run test -- app/[locale]/admin/profile-fields/
wc -l app/[locale]/admin/profile-fields/page.tsx
```

预期: 0 error, 0 warning, 测试通过, page.tsx < 200 行。

- [ ] **Step 7: Commit**

```bash
cd c:/doc/Code/rag
git add packages/web/app/[locale]/admin/profile-fields/
git commit -m "refactor(admin): 拆 profile-fields/page 为 2 dialog + handlers hook (413→<200 行)

- 抽 useProfileFieldsHandlers hook (5 handler + form state)
- 拆 CreateFieldDialog / EditFieldDialog 子组件
- page.tsx 只保留 DataTable + PageHero + 错误条

审计依据: A-02, C-01 (jsx-violations audit 2026-06-29)"
```

---

### Task 3: 拆 `admin-users-table.tsx` (387 → < 250 行)

**Files:**
- Modify: `packages/web/app/[locale]/admin/users/_components/admin-users-table.tsx`
- Modify: `packages/web/app/[locale]/admin/users/_components/admin-users-table.test.tsx` (如有)

**审计依据**: A-07 (renderActionButtons 内联 IIFE)、C-02 (>300 行)

- [ ] **Step 1: 读现状**

```bash
cd c:/doc/Code/rag/packages/web
cat app/[locale]/admin/users/_components/admin-users-table.tsx | sed -n '100,160p'
```

确认 `renderActionButtons` 函数位于 122-153 行（agent 报告标注）。

- [ ] **Step 2: 提取 label helpers 到模块顶层**

在文件顶部（import 块后、interface 块前）添加:

```typescript
// 2026-06-29: 抽自 renderActionButtons 的 if/else 双链赋值
const getAdminActionLabel = (role: string): string => (role === "admin" ? "降权" : "提权");
const getActiveActionLabel = (isActive: boolean): string => (isActive ? "禁用" : "启用");
```

- [ ] **Step 3: 化简 `renderActionButtons` 函数体**

用 Edit 把函数体替换为:

```typescript
const renderActionButtons = ({ ... }: RenderActionButtonsParams) => (
  <div className="flex gap-1.5">
    <Button ... onClick={onAdminAction}>{getAdminActionLabel(user.role)}</Button>
    <Button ... onClick={onActiveAction}>{getActiveActionLabel(user.is_active)}</Button>
    <Button variant="destructive" ... onClick={onResetPassword}>重设密码</Button>
  </div>
);
```

(具体 onXxxAction 回调从原 `onClick={...}` 抽出来; 实际 props 列表参考原文件)

- [ ] **Step 4: 跑测试 + 验证**

```bash
cd c:/doc/Code/rag/packages/web
bun run typecheck
bun run lint
bun run test -- app/[locale]/admin/users/_components/admin-users-table.test.tsx
wc -l app/[locale]/admin/users/_components/admin-users-table.tsx
```

预期: 0 error, 0 warning, 测试通过, 文件 < 250 行。

- [ ] **Step 5: Commit**

```bash
cd c:/doc/Code/rag
git add packages/web/app/[locale]/admin/users/_components/admin-users-table.tsx
git commit -m "refactor(admin): 抽 getAdminActionLabel/getActiveActionLabel (387→<250 行)

- 抽 renderActionButtons 内联 if/else 链为模块顶层 helper
- 函数体只剩 JSX, 可读性提升

审计依据: A-07, C-02 (jsx-violations audit 2026-06-29)"
```

---

### Task 4: 拆 `buyers/page.tsx` (377 → < 250 行)

**Files:**
- Create: `packages/web/app/[locale]/buyers/_hooks/use-buyers-columns.ts`
- Create: `packages/web/app/[locale]/buyers/_components/buyers-toolbar.tsx`
- Modify: `packages/web/app/[locale]/buyers/page.tsx`

**审计依据**: A-08 (switch 5 case)、A-09 (hook 内联 10 字段)、C-03 (>300 行)

- [ ] **Step 1: 读现状确认 buildProfileColumn**

```bash
cd c:/doc/Code/rag/packages/web
cat app/[locale]/buyers/page.tsx | sed -n '135,180p'
cat app/[locale]/buyers/page.tsx | sed -n '275,310p'
```

- [ ] **Step 2: 抽 `FIELD_TYPE_RENDERERS` Record + `useBuyersColumns` hook**

创建 `packages/web/app/[locale]/buyers/_hooks/use-buyers-columns.ts`:

```typescript
/**
 * useBuyersColumns (2026-06-29)
 * 抽自 buyers/page.tsx 的 buildProfileColumn (switch 5 case) + useBuyersPageData
 * 改用 Record lookup (FIELD_TYPE_RENDERERS), 消除 if/else / switch 多分支
 */
"use client";
import { useMemo } from "react";
import type { ColumnDef } from "@tanstack/react-table";
import { useTranslations } from "next-intl";
import type { BuyerProfile, ProfileFieldConfig } from "@/lib/api/buyer-profile/types";

// 字段类型 → cell renderer
type FieldTypeRenderer = (
  row: BuyerProfile,
  code: string,
  translate: (key: string) => string,
) => React.ReactNode;

const FIELD_TYPE_RENDERERS: Record<string, FieldTypeRenderer> = {
  boolean: (row, code, translate) => {
    const value = row.values[code];
    return value ? translate("是") : translate("否");
  },
  number: (row, code) => <span className="font-mono">{String(row.values[code] ?? "")}</span>,
  select: (row, code) => <span>{String(row.values[code] ?? "")}</span>,
  tags: (row, code) => (
    <div className="flex flex-wrap gap-1">
      {(row.values[code] as string[] | undefined)?.map((tag) => (
        <Badge key={tag} variant="outline">{tag}</Badge>
      ))}
    </div>
  ),
  text: (row, code) => <span>{String(row.values[code] ?? "")}</span>,
};

const DEFAULT_RENDERER: FieldTypeRenderer = (row, code) => (
  <span>{String(row.values[code] ?? "")}</span>
);

const sortBySortOrder = (configs: ProfileFieldConfig[]): ProfileFieldConfig[] =>
  configs
    .filter((cfg) => cfg.is_active)
    .toSorted((cfgA, cfgB) => cfgA.sort_order - cfgB.sort_order);

export const useBuyersColumns = (
  configs: ProfileFieldConfig[],
): ColumnDef<BuyerProfile>[] => {
  const translate = useTranslations();
  return useMemo(() => {
    const activeFields = sortBySortOrder(configs);
    return activeFields.map<ColumnDef<BuyerProfile>>((cfg) => ({
      header: () => cfg.label,
      id: cfg.code,
      meta: { width: cfg.width },
      cell: (ctx) => {
        const renderer = FIELD_TYPE_RENDERERS[cfg.field_type] ?? DEFAULT_RENDERER;
        return renderer(ctx.row.original, cfg.code, translate);
      },
    }));
  }, [configs, translate]);
};
```

- [ ] **Step 3: 抽 `<BuyersToolbar>` 子组件**

创建 `packages/web/app/[locale]/buyers/_components/buyers-toolbar.tsx`:

```typescript
"use client";
import { Input } from "@/components/ui/input";
import { AppSelect } from "@/components/common/input/app-select";

const STATUS_OPTIONS = [
  { label: "全部", value: "all" },
  { label: "活跃", value: "active" },
  { label: "停用", value: "inactive" },
];

export const BuyersToolbar = ({
  searchText,
  setSearchText,
  statusFilter,
  setStatusFilter,
  translation,
}: {
  searchText: string;
  setSearchText: (text: string) => void;
  statusFilter: string;
  setStatusFilter: (status: string) => void;
  translation: (key: string) => string;
}) => (
  <div className="flex gap-2">
    <Input
      value={searchText}
      onChange={(event) => setSearchText(event.target.value)}
      placeholder={translation("搜索买家")}
      className="max-w-xs"
    />
    <AppSelect
      value={statusFilter}
      onChange={setStatusFilter}
      options={STATUS_OPTIONS}
    />
  </div>
);
```

- [ ] **Step 4: 化简 page.tsx**

修改 `packages/web/app/[locale]/buyers/page.tsx`:
- 删除 `buildProfileColumn` 整个 switch + 5 个 case
- 删除 `useBuyersPageData` 内联 10 字段返回，改成调用 `useBuyersColumns`
- 工具栏块替换为 `<BuyersToolbar>`
- 保留 DataTable + PageHero

- [ ] **Step 5: 跑测试 + 验证**

```bash
cd c:/doc/Code/rag/packages/web
bun run typecheck
bun run lint
bun run test -- app/[locale]/buyers/
wc -l app/[locale]/buyers/page.tsx
```

预期: 0 error, 0 warning, 测试通过, page.tsx < 250 行。

- [ ] **Step 6: Commit**

```bash
cd c:/doc/Code/rag
git add packages/web/app/[locale]/buyers/
git commit -m "refactor(buyers): 抽 useBuyersColumns hook + BuyersToolbar (377→<250 行)

- 抽 useBuyersColumns hook (FieldTypeRenderer Record lookup 替 switch 5 case)
- 抽 BuyersToolbar 子组件
- page.tsx 只保留 DataTable + PageHero

审计依据: A-08, A-09, C-03 (jsx-violations audit 2026-06-29)"
```

---

### Task 5: 拆 `documents-import-form.tsx` (347 → < 150 行)

**Files:**
- Create: `packages/web/app/[locale]/knowledge/documents/import/_components/step-indicator.tsx`
- Create: `packages/web/app/[locale]/knowledge/documents/import/_components/upload-step.tsx`
- Create: `packages/web/app/[locale]/knowledge/documents/import/_components/parse-result-card.tsx`
- Create: `packages/web/app/[locale]/knowledge/documents/import/_components/template-download.tsx`
- Modify: `packages/web/app/[locale]/knowledge/documents/import/_components/documents-import-form.tsx`

**审计依据**: C-04 (>300 行)

- [ ] **Step 1: 读现状**

```bash
cd c:/doc/Code/rag/packages/web
cat app/[locale]/knowledge/documents/import/_components/documents-import-form.tsx | sed -n '180,347p'
```

- [ ] **Step 2: 抽 `<StepIndicator>` 子组件**

创建 `packages/web/app/[locale]/knowledge/documents/import/_components/step-indicator.tsx`:

```typescript
"use client";
import { Check } from "lucide-react";

export interface ImportStep {
  label: string;
  description: string;
}

export const StepIndicator = ({
  steps,
  currentIndex,
}: {
  steps: ImportStep[];
  currentIndex: number;
}) => (
  <ol className="flex items-center gap-4">
    {steps.map((step, idx) => {
      const isDone = idx < currentIndex;
      const isActive = idx === currentIndex;
      return (
        <li key={step.label} className="flex items-center gap-2">
          <span
            className={`flex h-8 w-8 items-center justify-center rounded-full border ${
              isDone
                ? "border-status-success bg-status-success/10 text-status-success"
                : isActive
                  ? "border-status-running bg-status-running/10 text-status-running"
                  : "border-border bg-muted text-muted-foreground"
            }`}
          >
            {isDone ? <Check className="h-4 w-4" /> : idx + 1}
          </span>
          <div>
            <div className="text-sm font-medium">{step.label}</div>
            <div className="text-xs text-muted-foreground">{step.description}</div>
          </div>
        </li>
      );
    })}
  </ol>
);
```

- [ ] **Step 3: 抽 `<UploadStep>` 子组件**

创建 `packages/web/app/[locale]/knowledge/documents/import/_components/upload-step.tsx`:

```typescript
"use client";
import { FileDropzone } from "@/components/common/input/app-file-dropzone";

export const UploadStep = ({
  onFile,
  translation,
}: {
  onFile: (file: File) => void;
  translation: (key: string) => string;
}) => (
  <FileDropzone
    accept=".xlsx,.json"
    onFile={onFile}
    title={translation("上传 Excel 或 JSON")}
    description={translation("支持 .xlsx 和 .json 格式")}
  />
);
```

- [ ] **Step 4: 抽 `<ParseResultCard>` 子组件**

创建 `packages/web/app/[locale]/knowledge/documents/import/_components/parse-result-card.tsx`:

```typescript
"use client";
import { DataTable } from "@/components/common/table/data-table";
import type { ParseResult } from "../types";

export const ParseResultCard = ({
  result,
  columns,
  translation,
}: {
  result: ParseResult;
  columns: import("@tanstack/react-table").ColumnDef<ParseResult["rows"][number]>[];
  translation: (key: string) => string;
}) => (
  <div className="border rounded-lg p-4 space-y-3">
    <h3 className="text-lg font-semibold">
      {translation("解析结果")} ({result.rows.length} {translation("行")}, {result.errorCount} {translation("错误")})
    </h3>
    <DataTable dataSource={result.rows} columns={columns} rowKey="id" />
  </div>
);
```

- [ ] **Step 5: 抽 `<TemplateDownload>` 子组件**

创建 `packages/web/app/[locale]/knowledge/documents/import/_components/template-download.tsx`:

```typescript
"use client";
import { Button } from "@/components/ui/button";
import { Download } from "lucide-react";

export const TemplateDownload = ({
  href,
  translation,
}: {
  href: string;
  translation: (key: string) => string;
}) => (
  <Button asChild variant="outline">
    <a href={href} download>
      <Download className="h-4 w-4 mr-2" />
      {translation("下载模板")}
    </a>
  </Button>
);
```

- [ ] **Step 6: 化简 documents-import-form.tsx**

把 4 个块分别替换为对应子组件调用，主组件只保留 useState + 步骤切换逻辑。

- [ ] **Step 7: 跑测试 + 验证**

```bash
cd c:/doc/Code/rag/packages/web
bun run typecheck
bun run lint
bun run test -- app/[locale]/knowledge/documents/import/
wc -l app/[locale]/knowledge/documents/import/_components/*.tsx
```

预期: documents-import-form.tsx < 150 行, 其他子组件 < 100 行 each。

- [ ] **Step 8: Commit**

```bash
cd c:/doc/Code/rag
git add packages/web/app/[locale]/knowledge/documents/import/_components/
git commit -m "refactor(knowledge): 拆 documents-import-form 为 4 子组件 (347→<150 行)

- 抽 StepIndicator / UploadStep / ParseResultCard / TemplateDownload
- 主组件只保留步骤切换逻辑

审计依据: C-04 (jsx-violations audit 2026-06-29)"
```

---

## Phase 2 — P1 IIFE-in-JSX 模式替换（7 task）

### Task 6: 抽 `calendar.tsx` classNames / components 常量

**Files:**
- Modify: `packages/web/components/ui/calendar.tsx`

**审计依据**: A-01 (HIGH)

- [ ] **Step 1: 读现状确认行号**

```bash
cd c:/doc/Code/rag/packages/web
cat components/ui/calendar.tsx | sed -n '37,140p'
```

- [ ] **Step 2: 在模块顶层添加 `getCaptionLabelClass` 纯函数**

在文件顶部 (`import` 之后) 添加:

```typescript
const getCaptionLabelClass = (
  captionLayout: "label" | "dropdown",
  defaultClassNames: { caption_label: string },
): string => {
  let captionLayoutClass: string;
  if (captionLayout === "label") {
    captionLayoutClass = "text-sm";
  } else {
    captionLayoutClass =
      "[&>svg]:text-muted-foreground flex h-8 items-center gap-1 rounded-md pl-2 pr-1 text-sm [&>svg]:size-3.5";
  }
  return cn("select-none font-medium", captionLayoutClass, defaultClassNames.caption_label);
};
```

- [ ] **Step 3: 在模块顶层添加 `CALENDAR_COMPONENTS` 常量**

```typescript
const ChevronIcon = ({
  className: chevronClassName,
  orientation,
  ...restProps
}: { className?: string; orientation?: "left" | "right" | "up" | "down" }) => {
  if (orientation === "left") {
    return <ChevronLeftIcon className={cn("size-4", chevronClassName)} {...restProps} />;
  }
  if (orientation === "right") {
    return <ChevronRightIcon className={cn("size-4", chevronClassName)} {...restProps} />;
  }
  return <ChevronDownIcon className={cn("size-4", chevronClassName)} {...restProps} />;
};

const CalendarRoot = ({
  className: rootClassName,
  rootRef,
  ...restProps
}: { className?: string; rootRef?: React.Ref<HTMLDivElement> }) => (
  <div data-slot="calendar" ref={rootRef} className={cn(rootClassName)} {...restProps} />
);

const CalendarWeekNumber = ({
  children,
  ...restProps
}: { children?: React.ReactNode }) => (
  <td {...restProps}>
    <div className="flex size-[--cell-size] items-center justify-center text-center">
      {children}
    </div>
  </td>
);

const CALENDAR_COMPONENTS = {
  Chevron: ChevronIcon,
  DayButton: CalendarDayButton,
  Root: CalendarRoot,
  WeekNumber: CalendarWeekNumber,
};
```

- [ ] **Step 4: 替换 classNames 内联对象**

在 `classNames={{` 块 (37-110 行) 内:
- `caption_label: (() => { ... })()` 替换为 `caption_label: getCaptionLabelClass(captionLayout, defaultClassNames)`
- 其他 23 个键保留，但整体块仍较长（属于模块顶层常量）

**说明**: calendar.tsx 是 shadcn Radix 包装，classNames 对象是 react-day-picker 必需配置，73 行内容本质是配置而非业务逻辑。Step 4 完成后文件仍约 200 行，但因为 IIFE 已消除，**严重度从 HIGH 降到 MEDIUM**。如果想进一步压行，可参考 shadcn 标准模板（不推荐，会损失可读性）。

- [ ] **Step 5: 替换 components 内联对象**

```tsx
components={{
  ...CALENDAR_COMPONENTS,
  ...components,  // 用户传入的覆盖
}}
```

- [ ] **Step 6: 跑测试 + 验证**

```bash
cd c:/doc/Code/rag/packages/web
bun run typecheck
bun run lint
bun run test -- components/ui/calendar.test.tsx 2>/dev/null || bun run test -- components/ui/
```

预期: 0 error, 0 warning, 测试通过。

- [ ] **Step 7: Commit**

```bash
cd c:/doc/Code/rag
git add packages/web/components/ui/calendar.tsx
git commit -m "refactor(ui): 抽 calendar classNames IIFE + components 常量

- 抽 getCaptionLabelClass 纯函数替 IIFE
- 抽 CALENDAR_COMPONENTS 常量 (ChevronIcon / CalendarRoot / CalendarWeekNumber)
- 严重度从 HIGH 降到 MEDIUM

审计依据: A-01 (jsx-violations audit 2026-06-29)"
```

---

### Task 7: 拆 `message-bubble.tsx` IIFE

**Files:**
- Create: `packages/web/components/chat/build-bubble-class.ts`
- Create: `packages/web/components/chat/assistant-body.tsx`
- Create: `packages/web/components/chat/markdown-img.tsx`
- Modify: `packages/web/components/chat/message-bubble.tsx`

**审计依据**: A-05 (IIFE in JSX)、B-02 (markdownComponents 内联)

- [ ] **Step 1: 抽 `buildBubbleClass` 纯函数**

创建 `packages/web/components/chat/build-bubble-class.ts`:

```typescript
export const buildBubbleClass = (isUser: boolean): string => {
  const MAX_WIDTH_CLASS = "max-w-[80%]";
  if (isUser) {
    return `${MAX_WIDTH_CLASS} rounded-2xl bg-ink px-4 py-2.5 text-paper`;
  }
  return `${MAX_WIDTH_CLASS} rounded-2xl border border-border/60 bg-card px-4 py-2.5`;
};
```

- [ ] **Step 2: 抽 `<AssistantBody>` 子组件**

创建 `packages/web/components/chat/assistant-body.tsx`:

```typescript
"use client";
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import { AppCollapsible } from "@/components/common/display/app-collapsible";
import { ImagePreview } from "@/components/common/input/app-image-preview";
import type { Message } from "@/lib/chat/types";
import { MarkdownImg } from "./markdown-img";

const THINK_TAG_PATTERN = /<think>(?<thinkingContent>[\s\S]*?)<\/think>/;
const THINK_REMOVE_PATTERN = /<think>[\s\S]*?<\/think>/;
const THINK_TOGGLE_TEXT = "思考过程";
const EMPTY_THINKING = "";

const parseThinkTag = (content: string): { thinking: string; answer: string } => {
  const match = content.match(THINK_TAG_PATTERN);
  if (!match) {
    return { answer: content, thinking: EMPTY_THINKING };
  }
  return {
    answer: content.replace(THINK_REMOVE_PATTERN, "").trim(),
    thinking: match.groups?.thinkingContent?.trim() ?? "",
  };
};

const renderThinking = (thinking: string) => (
  <AppCollapsible title={THINK_TOGGLE_TEXT} defaultOpen testId="think-toggle" className="mb-2">
    <div className="mt-1 whitespace-pre-wrap rounded-lg border border-border/40 bg-muted/30 p-3 text-sm text-muted-foreground">
      {thinking}
    </div>
  </AppCollapsible>
);

const markdownComponents = { img: MarkdownImg };

export const AssistantBody = ({ message }: { message: Message }) => {
  const { thinking, answer } = parseThinkTag(message.content);
  return (
    <>
      {thinking && renderThinking(thinking)}
      <div className="prose prose-sm max-w-none">
        <ReactMarkdown components={markdownComponents}>{answer}</ReactMarkdown>
      </div>
    </>
  );
};
```

- [ ] **Step 3: 抽 `<MarkdownImg>` 命名组件 (提到模块顶层)**

创建 `packages/web/components/chat/markdown-img.tsx`:

```typescript
"use client";
import { useState } from "react";
import { ImagePreview } from "@/components/common/input/app-image-preview";

export const MarkdownImg = ({
  src,
  alt,
}: React.ImgHTMLAttributes<HTMLImageElement>) => {
  const [previewSrc, setPreviewSrc] = useState<string | null>(null);
  const safeSrc = typeof src === "string" ? src : undefined;
  const handleClick = () => {
    if (safeSrc) {
      setPreviewSrc(safeSrc);
    }
  };
  const handlePreviewClose = (open: boolean) => {
    if (!open) {
      setPreviewSrc(null);
    }
  };
  return (
    <>
      <img
        src={safeSrc}
        alt={alt}
        className="max-w-full cursor-zoom-in rounded"
        onClick={handleClick}
      />
      <ImagePreview
        open={previewSrc !== null}
        onOpenChange={handlePreviewClose}
        src={previewSrc ?? ""}
      />
    </>
  );
};
```

- [ ] **Step 4: 化简 `message-bubble.tsx`**

```typescript
/**
 * 消息气泡 (2026-06-29 重构)
 * 拆 buildBubbleClass + AssistantBody + MarkdownImg
 * 主组件只剩编排逻辑
 */
"use client";
import { Badge } from "@/components/ui/badge";
import { CitationPanel } from "./citation-panel";
import type { Message } from "@/lib/chat/types";
import { MessageFeedback } from "./message-feedback";
import { AssistantBody } from "./assistant-body";
import { buildBubbleClass } from "./build-bubble-class";
import { AppCollapsible } from "@/components/common/display/app-collapsible";
import { useTranslations } from "next-intl";
import { ZERO } from "@/const";

const INTERRUPTED_LABEL = "已中断";

const renderCitations = (message: Message, translate: (key: string) => string) => (
  <AppCollapsible
    title={`引用 ${message.citations?.length ?? ZERO} 条`}
    testId="citation-panel"
    className="mt-3"
  >
    <CitationPanel citations={message.citations ?? []} />
  </AppCollapsible>
);

const InterruptedBadge = () => (
  <Badge
    data-testid="interrupted-badge"
    variant="outline"
    className="mt-2 gap-1 rounded-full border-status-warning/40 bg-status-warning/10 px-2 py-0.5 text-xs text-status-warning"
  >
    {INTERRUPTED_LABEL}
  </Badge>
);

export const MessageBubble = ({ message, pairedQuestion }: { message: Message; pairedQuestion?: string }) => {
  const isUser = message.role === "user";
  const translate = useTranslations();

  return (
    <div
      data-testid={`message-${message.id}`}
      data-role={message.role}
      className={isUser ? "flex justify-end" : "flex justify-start"}
    >
      <div className={buildBubbleClass(isUser)}>
        {isUser ? <p className="whitespace-pre-wrap text-base">{message.content}</p> : <AssistantBody message={message} />}
        {message.interrupted && <InterruptedBadge />}
        {!isUser && pairedQuestion !== undefined && message.content && (
          <MessageFeedback
            messageId={message.id}
            question={pairedQuestion}
            originalAnswer={message.content}
          />
        )}
        {!isUser && message.citations && message.citations.length > ZERO && renderCitations(message, translate)}
      </div>
    </div>
  );
};
```

- [ ] **Step 5: 跑测试 + 验证**

```bash
cd c:/doc/Code/rag/packages/web
bun run typecheck
bun run lint
bun run test -- components/chat/message-bubble.test.tsx 2>/dev/null || bun run test -- components/chat/
wc -l components/chat/message-bubble.tsx
```

预期: message-bubble.tsx < 80 行, 0 error, 测试通过。

- [ ] **Step 6: Commit**

```bash
cd c:/doc/Code/rag
git add packages/web/components/chat/message-bubble.tsx \
        packages/web/components/chat/build-bubble-class.ts \
        packages/web/components/chat/assistant-body.tsx \
        packages/web/components/chat/markdown-img.tsx
git commit -m "refactor(chat): 拆 message-bubble 为 AssistantBody + MarkdownImg 子组件

- 抽 buildBubbleClass 纯函数替 IIFE
- 抽 AssistantBody 子组件替 bodyContent IIFE
- 抽 MarkdownImg 替 inline markdownComponents (提到模块顶层)

审计依据: A-05, B-02 (jsx-violations audit 2026-06-29)"
```

---

### Task 8: `memory-management-dialog.tsx` IIFE → `useMemo`

**Files:**
- Modify: `packages/web/components/chat/memory-management-dialog.tsx`

**审计依据**: A-06 (useMemoryFilter IIFE)

- [ ] **Step 1: 替换 IIFE 为 `useMemo`**

把 useMemoryFilter 函数体替换:

```typescript
import { useEffect, useMemo, useState } from "react";
// ... 其他 import 不变

const useMemoryFilter = (memories: MemoryHit[]) => {
  const [filter, setFilter] = useState("");
  const filtered = useMemo(() => {
    if (!filter) {
      return memories;
    }
    const query = filter.toLowerCase();
    return memories.filter((memory) => memory.text.toLowerCase().includes(query));
  }, [memories, filter]);
  return { filter, filtered, setFilter };
};
```

- [ ] **Step 2: 验证 + Commit**

```bash
cd c:/doc/Code/rag/packages/web
bun run typecheck
bun run lint
bun run test -- components/chat/memory-management-dialog.test.tsx
```

```bash
cd c:/doc/Code/rag
git add packages/web/components/chat/memory-management-dialog.tsx
git commit -m "refactor(chat): memory-management-dialog useMemoryFilter IIFE → useMemo

审计依据: A-06 (jsx-violations audit 2026-06-29)"
```

---

### Task 9: `user-menu.tsx` items 数组 → `buildMenuItems` 函数

**Files:**
- Modify: `packages/web/components/user-menu.tsx`

**审计依据**: A-16, B-01 (7 元素内联数组)

- [ ] **Step 1: 抽 `buildMenuItems` 函数**

```typescript
type AppDropdownMenuItem = {
  key: string;
  href?: string;
  label: string;
  testid?: string;
  hidden?: boolean;
  separator?: boolean;
  onClick?: () => void;
  disabled?: boolean;
};

const buildMenuItems = (
  tr: (key: string) => string,
  roleUser: { role: string },
  onLogout: () => void,
  isPending: boolean,
): AppDropdownMenuItem[] => [
  { key: "admin-users", href: "/admin/users", label: tr("用户管理"), testid: "menu-admin-users", hidden: !isAdminLevel(roleUser) },
  { key: "admin-profile-fields", href: "/admin/profile-fields", label: tr("画像字段配置"), testid: "menu-profile-fields", hidden: !isAdminLevel(roleUser) },
  { key: "admin-permissions", href: "/admin/permissions", label: tr("权限管理"), testid: "menu-permissions", hidden: !isSuperAdmin(roleUser) },
  { key: "admin-dicts", href: "/admin/dicts", label: tr("字典管理"), testid: "menu-dicts", hidden: !isSuperAdmin(roleUser) },
  { key: "account-settings", href: "/account/settings", label: tr("账号设置"), testid: "menu-account-settings" },
  { key: "logout-sep", separator: true, label: "" },
  { key: "logout", label: tr("登出"), onClick: onLogout, testid: "menu-logout", disabled: isPending },
];
```

- [ ] **Step 2: 替换 JSX 中 `items={[...]}`**

```typescript
import { useMemo } from "react";
// ...

const menuItems = useMemo(
  () => buildMenuItems(tr, roleUser, handleLogout, isPending),
  [tr, roleUser, handleLogout, isPending],
);

// 在 return JSX 中
<AppDropdownMenu ... items={menuItems} />
```

- [ ] **Step 3: 验证 + Commit**

```bash
cd c:/doc/Code/rag/packages/web
bun run typecheck
bun run lint
```

```bash
cd c:/doc/Code/rag
git add packages/web/components/user-menu.tsx
git commit -m "refactor(user-menu): 7 元素内联 items 数组 → buildMenuItems + useMemo

审计依据: A-16, B-01 (jsx-violations audit 2026-06-29)"
```

---

### Task 10: `data-table.tsx` 28 行 inline config → `buildTableOptions`

**Files:**
- Modify: `packages/web/components/common/table/data-table.tsx`

**审计依据**: A-11 (28 行 inline config + 嵌套三元)

- [ ] **Step 1: 抽 `buildTableOptions` + `applyPaginationUpdater` 函数**

在 `useReactTable` 调用前添加:

```typescript
import { applyPaginationUpdater } from "./apply-pagination-updater";  // 新建

const buildTableOptions = <TData,>(
  columns: ColumnDef<TData>[],
  dataSource: TData[],
  rowKey: string,
  pagination: Pagination | undefined,
): TanstackTableOptions<TData> => {
  const baseOptions: TanstackTableOptions<TData> = {
    columns,
    data: dataSource,
    getCoreRowModel: getCoreRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    getRowId: (row, index) => String((row as Record<string, unknown>)[rowKey] ?? index),
    initialState: { pagination: { pageIndex: 0, pageSize: DEFAULT_PAGE_SIZE } },
  };

  if (pagination === undefined) {
    return baseOptions;
  }

  return {
    ...baseOptions,
    manualPagination: true,
    onPaginationChange: (updater) => {
      const next = applyPaginationUpdater(updater, {
        pageIndex: pagination.current - 1,
        pageSize: pagination.pageSize,
      });
      pagination.onChange(next.pageIndex + 1);
    },
    pageCount: Math.ceil(pagination.total / pagination.pageSize),
    state: { pagination: { pageIndex: pagination.current - 1, pageSize: pagination.pageSize } },
  };
};
```

- [ ] **Step 2: 创建 `apply-pagination-updater.ts`**

创建 `packages/web/components/common/table/apply-pagination-updater.ts`:

```typescript
import type { PaginationState, Updater } from "@tanstack/react-table";

export const applyPaginationUpdater = (
  updater: Updater<PaginationState>,
  base: PaginationState,
): PaginationState => (typeof updater === "function" ? updater(base) : updater);
```

- [ ] **Step 3: 化简 useReactTable 调用**

```typescript
const table = useReactTable<TData>(buildTableOptions(columns, dataSource, rowKey, pagination));
```

- [ ] **Step 4: 验证 + Commit**

```bash
cd c:/doc/Code/rag/packages/web
bun run typecheck
bun run lint
bun run test -- components/common/table/
```

```bash
cd c:/doc/Code/rag
git add packages/web/components/common/table/data-table.tsx \
        packages/web/components/common/table/apply-pagination-updater.ts
git commit -m "refactor(table): useReactTable 28 行 inline config → buildTableOptions

- 抽 buildTableOptions 替 inline config
- 抽 applyPaginationUpdater 替嵌套三元

审计依据: A-11 (jsx-violations audit 2026-06-29)"
```

---

### Task 11: `data-table-body.tsx` IIFE → `renderExpandedRow`

**Files:**
- Modify: `packages/web/components/common/table/data-table-body.tsx`

**审计依据**: A-12 (IIFE expanded row)

- [ ] **Step 1: 抽 `renderExpandedRow` 函数**

```typescript
const renderExpandedRow = (
  rowData: TData,
  expandedRowRender: (row: TData) => React.ReactNode,
  index: number,
  colCount: number,
): React.ReactNode => {
  const expandedNode = expandedRowRender(rowData);
  if (expandedNode === null || expandedNode === undefined) {
    return null;
  }
  return (
    <motion.tr
      variants={rowStagger(index * STAGGER_STEP.row)}
      data-testid={`row-expanded-${index}`}
    >
      <TableCell colSpan={colCount}>{expandedNode}</TableCell>
    </motion.tr>
  );
};
```

- [ ] **Step 2: 替换 JSX 内 IIFE**

```tsx
{expandedRowRender !== undefined && renderExpandedRow(rowData, expandedRowRender, index, columns.length)}
```

- [ ] **Step 3: 验证 + Commit**

```bash
cd c:/doc/Code/rag/packages/web
bun run typecheck
bun run lint
```

```bash
cd c:/doc/Code/rag
git add packages/web/components/common/table/data-table-body.tsx
git commit -m "refactor(table): data-table-body expanded row IIFE → renderExpandedRow

审计依据: A-12 (jsx-violations audit 2026-06-29)"
```

---

### Task 12: `app-copy-button.tsx` 单层 IIFE → 三元

**Files:**
- Modify: `packages/web/components/common/button/app-copy-button.tsx`

**审计依据**: A-13 (LOW)

- [ ] **Step 1: 替换 IIFE 为三元**

```tsx
{copied ? successLabel : label}
```

- [ ] **Step 2: 验证 + Commit**

```bash
cd c:/doc/Code/rag/packages/web
bun run typecheck
bun run lint
```

```bash
cd c:/doc/Code/rag
git add packages/web/components/common/button/app-copy-button.tsx
git commit -m "refactor(button): app-copy-button IIFE → 三元

审计依据: A-13 (jsx-violations audit 2026-06-29)"
```

---

## Phase 3 — P2 杂项整理（3 task）

### Task 13: `task-info.tsx` getStatusText → Record lookup

**Files:**
- Modify: `packages/web/app/[locale]/output/[task_id]/_components/task-info.tsx`

**审计依据**: A-14 (4 个 if 分支)

- [ ] **Step 1: 抽 `STATE_TEXT_BUILDERS` Record**

```typescript
type IngestTaskState = IngestTask["state"];

const STATE_TEXT_BUILDERS: Record<IngestTaskState, (task: IngestTask, tr: (key: string) => string) => string> = {
  completed: (task, tr) => `${task.processed} ${tr("成功")}`,
  failed: (task, tr) => `${tr("失败:")} ${task.error || tr("未知错误")}`,
  queued: (_task, tr) => tr("排队中…"),
  running: (task, tr) => `${tr("处理中…")} ${task.processed}/${task.total_files}`,
};

export const getStatusText = (task: IngestTask | null, tr: (key: string) => string): string => {
  if (!task) {
    return "";
  }
  return STATE_TEXT_BUILDERS[task.state](task, tr);
};
```

- [ ] **Step 2: 验证 + Commit**

```bash
cd c:/doc/Code/rag/packages/web
bun run typecheck
bun run lint
```

```bash
cd c:/doc/Code/rag
git add packages/web/app/[locale]/output/[task_id]/_components/task-info.tsx
git commit -m "refactor(output): task-info getStatusText 4 个 if → Record 查找

审计依据: A-14 (jsx-violations audit 2026-06-29)"
```

---

### Task 14: `run-detail-view.tsx` 4 个 MetricBar + actions 拆分

**Files:**
- Create: `packages/web/app/[locale]/evaluate/[id]/_components/metric-defs.ts`
- Create: `packages/web/app/[locale]/evaluate/[id]/_components/run-actions.tsx`
- Modify: `packages/web/app/[locale]/evaluate/[id]/_components/run-detail-view.tsx`

**审计依据**: A-10 (4 个 MetricBar 硬编), A-15 (PageHeader actions 内联 2 Button)

- [ ] **Step 1: 抽 `METRIC_DEFS` 数组 + `mapSampleForTable` 函数**

创建 `packages/web/app/[locale]/evaluate/[id]/_components/metric-defs.ts`:

```typescript
export interface MetricDef {
  key: "answer_relevancy" | "context_precision" | "context_recall" | "faithfulness";
  label: string;
}

export const buildMetricDefs = (translate: (key: string) => string): MetricDef[] => [
  { key: "answer_relevancy", label: translate("答案相关性 (Answer Relevancy)") },
  { key: "context_precision", label: translate("上下文精度 (Context Precision)") },
  { key: "context_recall", label: translate("上下文召回 (Context Recall)") },
  { key: "faithfulness", label: translate("忠实度 (Faithfulness)") },
];

export const mapSampleForTable = <T,>(samples: T[]) => samples.map((sample) => ({ ...sample }));
```

- [ ] **Step 2: 抽 `<RunActions>` 子组件**

创建 `packages/web/app/[locale]/evaluate/[id]/_components/run-actions.tsx`:

```typescript
"use client";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/evaluate/status-badge";
import type { RunStatus } from "@/lib/api/evaluate/types";

export const RunActions = ({
  status,
  onCancel,
  onDelete,
  translation,
}: {
  status: RunStatus;
  onCancel: () => void;
  onDelete: () => void;
  translation: (key: string) => string;
}) => {
  const isTerminal = status === "completed" || status === "failed" || status === "cancelled";
  return (
    <>
      <StatusBadge status={status} />
      {status === "running" && (
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={onCancel}
          className="border-destructive/40 px-3 py-1 text-xs text-destructive hover:bg-destructive/5"
        >
          {translation("取消")}
        </Button>
      )}
      {isTerminal && (
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={onDelete}
          className="border-border/60 px-3 py-1 text-xs"
        >
          {translation("删除")}
        </Button>
      )}
    </>
  );
};
```

- [ ] **Step 3: 化简 run-detail-view.tsx**

替换 4 个 MetricBar 硬编:

```tsx
{run.avg_metrics ? (
  <>
    {buildMetricDefs(translate).map((metric) => (
      <MetricBar
        key={metric.key}
        label={metric.label}
        value={run.avg_metrics?.[metric.key] ?? 0}
      />
    ))}
  </>
) : (
  <p>{translate("暂无评估指标")}</p>
)}
```

替换 PageHeader actions:

```tsx
actions={
  <RunActions
    status={run.status}
    onCancel={onCancel}
    onDelete={onDelete}
    translation={translate}
  />
}
```

替换 samples.map:

```tsx
<SampleTable samples={mapSampleForTable(run.samples)} />
```

- [ ] **Step 4: 验证 + Commit**

```bash
cd c:/doc/Code/rag/packages/web
bun run typecheck
bun run lint
bun run test -- app/[locale]/evaluate/[id]/_components/run-detail-view
```

```bash
cd c:/doc/Code/rag
git add packages/web/app/[locale]/evaluate/[id]/_components/run-detail-view.tsx \
        packages/web/app/[locale]/evaluate/[id]/_components/metric-defs.ts \
        packages/web/app/[locale]/evaluate/[id]/_components/run-actions.tsx
git commit -m "refactor(evaluate): run-detail-view 4 MetricBar → METRIC_DEFS + RunActions

- 抽 buildMetricDefs 数组替 4 个硬编 MetricBar
- 抽 RunActions 子组件替 inline actions JSX
- 抽 mapSampleForTable 替 inline samples.map

审计依据: A-10, A-15 (jsx-violations audit 2026-06-29)"
```

---

### Task 15: `admin-dicts-client.tsx` 临界 290 行预防性拆分

**Files:**
- Modify: `packages/web/app/[locale]/admin/dicts/_components/admin-dicts-client.tsx`

**审计依据**: 临界文件 (290 行), 审计判定无违规但需要预防性拆分避免越线

- [ ] **Step 1: 读现状找可抽 hook**

```bash
cd c:/doc/Code/rag/packages/web
cat app/[locale]/admin/dicts/_components/admin-dicts-client.tsx
```

识别至少 1 处可抽的 hook（如：表单 state 管理、过滤逻辑）。

- [ ] **Step 2: 抽 hook (至少 1 个)**

例如 `useDictsForm` / `useDictFilter` / 类似的辅助 hook，目标减少主组件 ~50 行。

- [ ] **Step 3: 验证 + Commit**

```bash
cd c:/doc/Code/rag/packages/web
bun run typecheck
bun run lint
wc -l app/[locale]/admin/dicts/_components/admin-dicts-client.tsx
```

预期: 文件 < 250 行（距 300 上限留 50 行 buffer）。

```bash
cd c:/doc/Code/rag
git add packages/web/app/[locale]/admin/dicts/_components/admin-dicts-client.tsx
git commit -m "refactor(admin): admin-dicts-client 预防性抽 hook (290→<250 行)

- 抽 useXxx hook (具体看文件结构)
- 跟 P0 类型 C 违规标准对齐, 留 buffer 防止后续增行

审计依据: 临界 (jsx-violations audit 2026-06-29)"
```

---

## 验证清单（每个 task 完成后）

- [ ] `bun run typecheck` 0 error
- [ ] `bun run lint` 0 warning
- [ ] `bun run test -- <相关路径>` 全绿
- [ ] `wc -l <目标文件>` 符合 task 行数目标
- [ ] `git commit` 用对应前缀
- [ ] 没动业务逻辑（diff 只看到 import / 拆分子组件 / 重命名）

---

## 最终验证（所有 15 task 完成后）

```bash
cd c:/doc/Code/rag
# 1. 全量 typecheck
cd packages/web && bun run typecheck

# 2. 全量 lint
bun run lint

# 3. 全量测试
bun run test

# 4. 全量 format check
bun run format:check

# 5. 全量 wc -l 扫描 (> 300 行文件)
find . -name "*.tsx" -o -name "*.ts" 2>/dev/null | \
  grep -v node_modules | grep -v "\.next" | grep -v "test-results" | \
  grep -v "playwright-report" | grep -v "test-shims" | grep -v "\.test\." | \
  grep -v "\.spec\." | \
  xargs wc -l 2>/dev/null | awk '$1 > 300 { print }'
```

预期: 0 个 > 300 行的源文件。

---

## Self-Review Checklist（plan 完成时）

- [x] **Spec coverage**: 25 项违规全部映射到 15 个 task (1:N 对应, 因为部分 task 合并多项违规)
- [x] **Placeholder scan**: 无 "TODO"/"implement later"/"similar to Task N"
- [x] **Type consistency**: 跨 task 类型一致 (如 `AttachmentItem` 在 Task 1 内部一致)
- [x] **每个 task 有 commit**: 15 commit, 每个独立可 review/bisect
- [x] **每个 task 有完整代码**: 所有代码块完整, 无省略号

---

## 不在本 plan 范围

- ❌ i18n 新增 key 同步 (现有硬编中文保留)
- ❌ 新增 vitest 测试 (本次整改不改业务行为, 原测试覆盖即可)
- ❌ 修改其他文件 (PR 标题就是 refactor(<scope>), 避免 scope creep)
- ❌ 增加 lint 规则禁止 JSX IIFE (后续 spec 单独立项)

---

## 执行选项

Plan 已保存到 `docs/superpowers/plans/2026-06-29-jsx-violations-refactor.md`。

**两种执行方式**:

1. **Subagent-Driven (推荐)** — 我每 task 派一个新 subagent, task 间 review, 快速迭代. 适合 15 task 大量并行.

2. **Inline Execution** — 当前会话按顺序跑 15 task, 每 task 后 checkpoint review. 慢但能即时反馈.

请选择执行方式, 或告诉我你想直接做的具体 task 编号 (1-15).