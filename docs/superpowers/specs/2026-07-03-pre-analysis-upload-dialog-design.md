# PreAnalysisUploadDialog 弹框组件设计 (2026-07-03)

> **Status**: draft → implementation pending
> **Owner**: frontend
> **Scope**: 1 个新弹框组件 + pre-analysis 列表按钮改造, **不抽通用 UploadButton**

## 背景

`packages/web/app/[locale]/admin/pre-analysis/` 页当前用 `<FileDropzone>` 做大块拖拽区 (2026-07-02 PR5)。
super_admin 上传 1 个 PDF 触发预分析, **大块拖拽区视觉过重**——admin 后台单文件场景更适合"按钮 → 弹框 → 选 → 确认"两步式。

5 个 FileDropzone 调用点里 4 个 (`output/new` / `knowledge/documents/import` / `knowledge/extract` / `evaluate/new`) 都是批量/大块场景, **保留拖拽区**。只有 `pre-analysis` 单文件 + admin 场景适合弹框, **不抽通用 UploadButton** (YAGNI, 1 个调用点不算重复)。

## 方案

**触发按钮 + AppDialog + FileDropzone 三段式**, **弹框拆独立文件** (项目 "复合 Radix 必抽 AppXxx" 规约 + "单文件 ≤300 行" + kebab-case `*-dialog.tsx` 命名)。

**用户决策** (2026-07-03 头脑风暴):
1. 弹框内仍用 FileDropzone 大块拖拽区 (不改视觉)
2. 触发按钮保持 `flex justify-end` 右上角位置
3. API 错误时保留 file 选择, 弹框内提供"清空"操作
4. 文件大小显示复用 `lib/format.ts` 共享 `fmtSize` (从 `output/new/page.tsx:26` 抽出)
5. "清空" 按钮放文件信息旁边, 不放 footer
6. 上传成功后 `toast.success("上传成功")` + `setTimeout(500ms)` 关闭弹框 + 跳详情页

## 架构

```
app/[locale]/admin/pre-analysis/
├── _components/
│   ├── admin-pre-analysis-client.tsx           (改: 加按钮 + 弹框状态)
│   ├── admin-pre-analysis-client.test.tsx      (新: 按钮/弹框联动 test)
│   ├── pre-analysis-upload-dialog.tsx          (新: 弹框组件)
│   └── pre-analysis-upload-dialog.test.tsx     (新: 弹框独立 test)
```

**PreAnalysisUploadDialog 内部**:
- Props: `open` + `onOpenChange` + `onSuccess(taskId: string)`
- 内部 state:
  - `isUploading: boolean` (提交中 disable 弹框交互)
  - `uploadError: string | null` (API 错误 → 传给 AppDialog `error` slot)
  - `pickedFile: File | null` (用户选的文件, 弹框内显示 + "清空" 重选)
- 视觉 (3 段式):
  - `<AppDialog>` 标题 "上传 PDF" + 描述
  - body:
    - `pickedFile === null` → `<FileDropzone onFile={setPickedFile}>`
    - `pickedFile !== null` → 文件信息卡 (文件名 + `fmtSize(pickedFile.size)`) + 旁边"清空" Button
  - footer: `[取消]` `[开始上传]` (后者 pickedFile 存在时 enabled)
  - error slot: API 错误展示
- 流程 (handleUpload):
  - `setIsUploading(true)` + `setUploadError(null)`
  - `try { const result = await preAnalysisUpload(pickedFile); toast.success("上传成功"); setTimeout(500ms, () => { onOpenChange(false); onSuccess(result.task_id); }); } catch (e) { setUploadError(e.message); }`
  - `finally setIsUploading(false)`
- 守卫: `onOpenChange` 在 isUploading=true 时拒绝 (0 改动弹框)

**AdminPreAnalysisClient 改动**:
- 新 state: `isDialogOpen: boolean`
- 右上角 `<FileDropzone>` 替换为 `<Button variant="default" size="lg"> + <UploadCloud> + 文字` + 点击 `setIsDialogOpen(true)`
- 弹框: `<PreAnalysisUploadDialog open onOpenChange onSuccess={(id) => router.push(...)}>`

## 改动文件清单 (6 个)

| 文件 | 类型 | 改动量 |
|---|---|---|
| `lib/format.ts` | 新增 | ~15 行 (抽 fmtSize 共享) |
| `app/[locale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.tsx` | 新增 | ~150 行 |
| `app/[locale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.test.tsx` | 新增 | ~120 行 (4 test) |
| `app/[locale]/admin/pre-analysis/_components/admin-pre-analysis-client.tsx` | 改 | -20 行 +50 行 (净 +30) |
| `app/[locale]/admin/pre-analysis/_components/admin-pre-analysis-client.test.tsx` | 新增 | ~50 行 (1 test) |
| `messages/{zh,en}.json` | 改 2 文件 | 各 6 个 key |
| `app/[locale]/output/new/page.tsx` | 改 | 删 inline fmtSize, 改 import lib/format |

## API

```typescript
// pre-analysis-upload-dialog.tsx
export interface PreAnalysisUploadDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** 父组件负责 router.push 到详情页 */
  onSuccess: (taskId: string) => void;
}
```

## i18n 自检 (2026-07-03)

项目已有 `packages/web/messages/__tests__/i18n.test.ts` 6 个 test, **自动跑** (husky pre-commit → vitest 触发):
- `zh.json` 所有 value 跟 key 一致 (identity)
- `en.json` 覆盖 `zh.json` 所有 key (防漏翻译)
- `zh.json` / `en.json` **key 集合完全一致** (双边孤儿都报)
- `zh.json` / `en.json` key 都是非空字符串

**改动时 3 步必须做**:
1. 改 UI 加新 `t("...")` 字符串前, **先**在 `zh.json` 加 (key=中文, value=同中文 identity)
2. 同步在 `en.json` 加同 key 英文翻译
3. 改完跑 `bun run test messages/__tests__/i18n.test.ts` 单文件验证 6 个 test 全绿 (项目 "单次定位" 规约, 不跑全量)

**7 个 key (新增到 zh.json + en.json)**:
- 触发按钮: `上传 PDF` / `Upload PDF`
- 弹框标题: `上传 PDF` / `Upload PDF` (复用, 不另开 key)
- 弹框描述: `选择 PDF 上传` / `Select PDF to upload`
- 取消: `取消` / `Cancel`
- 开始上传: `开始上传` / `Start Upload`
- 上传中: `上传中…` / `Uploading...`
- 清空: `清空` / `Clear`
- 上传成功 (toast): `上传成功` / `Upload successful`

> ⚠️ zh value 用 `…` (U+2026 1 字符) 不要 `...` (3 dot), 跟项目"省略号统一"规约一致.

**commit 前必查**:
- `git diff messages/zh.json messages/en.json` 看新增 key
- `bun run test messages/__tests__/i18n.test.ts` 单跑验证

## i18n (7 key × 2 lang = 14)

| key | zh | en |
|---|---|---|
| `上传 PDF` | 上传 PDF | Upload PDF |
| `选择 PDF 上传` | 选择 1 个 PDF 文件 (≤100MB), 后台跑预分析 | Select 1 PDF (≤100MB), runs pre-analysis in background |
| `取消` | 取消 | Cancel |
| `开始上传` | 开始上传 | Start Upload |
| `上传中…` | 上传中… | Uploading... |
| `清空` | 清空 | Clear |
| `上传成功` | 上传成功 | Upload successful |

## 测试 (5 个, 按 TDD red-green-refactor)

**PreAnalysisUploadDialog 4 个** (弹框独立):
1. 打开状态渲染 title + FileDropzone + 取消/开始按钮 (开始 disabled)
2. 选文件 → FileDropzone 切换成文件名 + 大小 + "清空" 按钮 + "开始上传" enabled
3. 点 "开始上传" → 调 preAnalysisUpload + 成功后 toast.success + setTimeout(500ms) 后 onSuccess(taskId) + 弹框 onOpenChange(false) (用 `vi.useFakeTimers`)
4. preAnalysisUpload 抛错 → uploadError 设置 + 弹框不关 + error slot 展示

**AdminPreAnalysisClient 1 个**:
1. 默认渲染触发按钮 (不上传状态, 弹框关闭) + 点按钮弹框打开

## 风险

| 风险 | 缓解 |
|---|---|
| 弹框内 `isUploading` 期间用户关弹框 → race condition | `onOpenChange` 在 isUploading 时强制不关 (拒绝) |
| FileDropzone 拒绝行为 (大小/类型) → 弹框内红字 + 不进 pickedFile | FileDropzone 内部已处理 fileRejections, 弹框不接 |
| preAnalysisUpload mock 不还原 | vitest mock 用 `vi.mock(import("..."), async (importOriginal) => ({...await importOriginal()}))` 模式 |

## 验收

- [ ] pre-analysis 列表: 拖拽区消失, 右上角"上传 PDF" 按钮
- [ ] 点按钮弹 AppDialog, 内含 FileDropzone + 取消/开始上传
- [ ] 选 .pdf → 文件名 + 大小 + 清空 按钮, "开始上传" enabled
- [ ] 选 >100MB / .txt → FileDropzone 内红字, pickedFile 不更新
- [ ] 点 "开始上传" → preAnalysisUpload 调用 + toast.success("上传成功") + 500ms 后关弹框 + 跳详情页
- [ ] preAnalysisUpload 抛错 → 弹框不关 + error slot 红字 + 文件选择保留
- [ ] isUploading 期间点遮罩/X/取消 → 弹框不关
- [ ] i18n 自检: `bun run test messages/__tests__/i18n.test.ts` 6 个 test 全绿 (zh 跟 en 7 key 完全一致, value 跟 key identity / 英文翻译)
- [ ] `bun run typecheck` 0 error
- [ ] `bun run lint` 0 error
- [ ] 5 个新 test 全绿, 0 现有 test 回归

## 实施步骤 (writing-plans 阶段展开)

1. 写 `pre-analysis-upload-dialog.test.tsx` (4 test, 先 red)
2. 写 `pre-analysis-upload-dialog.tsx` 实现 (green)
3. 写 `admin-pre-analysis-client.test.tsx` (1 test, red)
4. 改 `admin-pre-analysis-client.tsx` (按钮 + 弹框状态)
5. 改 `messages/{zh,en}.json` (6 key)
6. 跑全套: typecheck + lint + test + format:check
7. commit (按项目规约: `feat:` 前缀, 拆 2-3 个 commit: 测试红 → 实现绿 → i18n + refactor)
