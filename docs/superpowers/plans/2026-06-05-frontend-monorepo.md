# Next.js 管理后台 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `web/` 子目录建 Next.js 15 + TypeScript + Tailwind v4 + shadcn/ui 只读管理后台，并加 2 个新后端只读 API（列 output/ 目录文件 + 读单个文件），用 CORS 接通。

**Architecture:** 单仓 + `web/` 子目录（不分 workspace）。后端 FastAPI 加 2 个只读路由（`output_api.py`），CORS 收窄到 `http://localhost:3000`。前端 Next.js 15 App Router，4 个页面（`/`、`/decode`、`/output`、`/output/[file]`），bun 装包，vitest 测组件。

**Tech Stack:**
- 后端增量：FastAPI 已有（不加新依赖）
- 前端：Next.js 15、React 19、TypeScript strict、Tailwind v4、shadcn/ui（复制进 `components/ui/`）、bun、vitest、react-markdown
- 通信：HTTP（fetch）+ CORS

---

## 文件结构

### 后端（Python）
- `src/product_decoders/output_api.py` — 新增，2 个新路由的 handler（避免 app.py 膨胀）
- `src/product_decoders/app.py` — 改：CORS 收窄 + `include_router(output_api.router)`
- `tests/test_web_apis.py` — 新增，2 个新 API 的契约测试

### 前端（TypeScript / TSX）
- `web/package.json`、`web/bun.lock` — bun 自动生成
- `web/tsconfig.json`、`web/next.config.ts`、`web/vitest.config.ts`、`web/vitest.setup.ts`
- `web/postcss.config.mjs`、`web/components.json`
- `web/.gitignore` — Next.js 标准产物
- `web/.oxlintrc.json` — oxlint 规则（Task 7.5）
- `web/.oxfmtrc.json` — oxformat 配置（Task 7.5）
- `web/lint-staged.config.js` — lint-staged 钩子（Task 7.5）
- `web/.husky/pre-commit` — husky 钩子（Task 7.5）
- `web/app/layout.tsx` — 根布局（顶部 nav）
- `web/app/page.tsx` — `/` 仪表盘
- `web/app/decode/page.tsx` — `/decode` 表单
- `web/app/output/page.tsx` — `/output` 文件列表
- `web/app/output/[file]/page.tsx` — `/output/<file>` 详情
- `web/app/globals.css` — Tailwind 入口
- `web/components/ui/*` — shadcn 组件（`button`、`input`、`card`、`table`、`badge`、`alert`）
- `web/lib/api.ts` — fetch 封装
- `web/lib/api.test.ts` — `api.ts` 单测
- `web/lib/utils.ts` — `cn()` 工具
- `web/app/decode/page.test.tsx` — decode 页测试
- `web/app/output/page.test.tsx` — output 列表页测试
- `web/CLAUDE.md` — 前端局部约定

### 项目根
- `.gitignore` — 追加 `web/node_modules/`、`web/.next/`、`web/out/`、`*.tsbuildinfo`、`next-env.d.ts`
- `README.md` — 追加"启动前端"小节

**注**：spec 写"根 CLAUDE.md 追加前端开发小节"，但当前仓库**没有根 CLAUDE.md**（CLAUDE.md 实际在 `.claude/CLAUDE.md`）。本计划**不**改 `.claude/CLAUDE.md`（避免越界改项目级配置），改用 README.md 的"启动前端"小节传递同样信息。如果用户后续想把前端约定写进 `.claude/CLAUDE.md`，可另起 spec。

---

## Task 1: 后端 `output_api.py` 红测试

**Files:**
- Create: `tests/test_web_apis.py`

- [ ] **Step 1: 写 2 个新 API 的契约测试**

```python
"""Web 后端 API 契约测试 (2026-06-05 frontend-monorepo)

新增 2 个只读 API:
- GET /api/output/files     列 output_dir 下的 .md / .json 文件
- GET /api/output/files/{name}  读单个文件
"""
import pytest
from fastapi.testclient import TestClient

from src.product_decoders.app import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    """把 output_dir 临时改成 tmp_path, 创建干净 app"""
    from src.rag.ingest.config import Paths
    fake_paths = Paths(input_dir=tmp_path, output_dir=tmp_path)
    monkeypatch.setattr("src.rag.ingest.config.get_paths", lambda: fake_paths)
    return TestClient(create_app())


class TestListFiles:
    """GET /api/output/files"""

    def test_list_files_returns_empty_when_dir_empty(self, client):
        """空目录 → files: []"""
        r = client.get("/api/output/files")
        assert r.status_code == 200
        assert r.json() == {"files": []}

    def test_list_files_returns_md_and_json_only(self, client):
        """只列 .md / .json, 过滤 .pdf / .txt / 隐藏文件"""
        from src.rag.ingest.config import get_paths
        out = get_paths().output_dir
        (out / "doc1.md").write_text("# A", encoding="utf-8")
        (out / "doc2.json").write_text("{}", encoding="utf-8")
        (out / "skip.pdf").write_bytes(b"%PDF")
        (out / "skip.txt").write_text("hi", encoding="utf-8")
        (out / ".hidden").write_text("hidden", encoding="utf-8")

        r = client.get("/api/output/files")
        assert r.status_code == 200
        names = sorted(f["name"] for f in r.json()["files"])
        assert "doc1.md" in names
        assert "doc2.json" in names
        assert "skip.pdf" not in names
        assert "skip.txt" not in names
        assert ".hidden" not in names

    def test_list_file_includes_size_and_mtime(self, client):
        """每个文件项含 name / size / mtime"""
        from src.rag.ingest.config import get_paths
        out = get_paths().output_dir
        (out / "x.md").write_text("hello", encoding="utf-8")
        r = client.get("/api/output/files")
        assert r.status_code == 200
        files = r.json()["files"]
        assert len(files) == 1
        f = files[0]
        assert f["name"] == "x.md"
        assert f["size"] == 5
        assert isinstance(f["mtime"], (int, float))
        assert f["mtime"] > 0


class TestReadFile:
    """GET /api/output/files/{name}"""

    def test_read_md_returns_content(self, client):
        """读 .md 返 name + content + mime=text/markdown"""
        from src.rag.ingest.config import get_paths
        out = get_paths().output_dir
        (out / "doc.md").write_text("# Title\n\nbody", encoding="utf-8")
        r = client.get("/api/output/files/doc.md")
        assert r.status_code == 200
        body = r.json()
        assert body["name"] == "doc.md"
        assert body["content"] == "# Title\n\nbody"
        assert body["mime"] == "text/markdown"

    def test_read_json_returns_content(self, client):
        """读 .json 返 mime=application/json"""
        from src.rag.ingest.config import get_paths
        out = get_paths().output_dir
        (out / "data.json").write_text('{"k": 1}', encoding="utf-8")
        r = client.get("/api/output/files/data.json")
        assert r.status_code == 200
        body = r.json()
        assert body["name"] == "data.json"
        assert body["content"] == '{"k": 1}'
        assert body["mime"] == "application/json"

    def test_read_missing_file_returns_404(self, client):
        """不存在文件 → 404"""
        r = client.get("/api/output/files/nope.md")
        assert r.status_code == 404
        assert "不存在" in r.json()["detail"]

    def test_path_traversal_returns_400(self, client):
        """`../` 越权 → 400"""
        r = client.get("/api/output/files/..%2F..%2Fetc%2Fpasswd")
        assert r.status_code == 400

    def test_invalid_chars_in_name_returns_400(self, client):
        """非法字符 → 400"""
        r = client.get("/api/output/files/bad%20name.md")
        assert r.status_code == 400
        # 也覆盖反斜杠
        r2 = client.get("/api/output/files/sub%2Ffile.md")
        assert r2.status_code == 400

    def test_oversized_file_returns_413(self, client):
        """超过 10 MB → 413"""
        from src.rag.ingest.config import get_paths
        out = get_paths().output_dir
        # 写 11 MB
        (out / "big.md").write_bytes(b"x" * (11 * 1024 * 1024))
        r = client.get("/api/output/files/big.md")
        assert r.status_code == 413
        assert "10 MB" in r.json()["detail"] or "太大" in r.json()["detail"]
```

- [ ] **Step 2: 跑测试确认 FAIL**

Run: `uv run pytest tests/test_web_apis.py -v`
Expected: 全部 FAIL（404 路由不存在）

---

## Task 2: 实现 `output_api.py` 路由

**Files:**
- Create: `src/product_decoders/output_api.py`

- [ ] **Step 1: 创建 output_api.py**

```python
"""管理后台只读 API: 列 output/ 目录文件 + 读单个文件

设计原则 (2026-06-05 frontend-monorepo):
- name 参数用 [a-zA-Z0-9._-]+ 字符集白名单, 防止路径越权
- 文件大小上限 10 MB, 防 OOM
- 解析后绝对路径必须 is_relative_to(output_dir), 兜底越权
"""
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException

from src.rag.ingest.config import get_paths


router = APIRouter(prefix="/api/output", tags=["output"])

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_EXTS = {".md", ".json"}
SAFE_NAME = re.compile(r"^[a-zA-Z0-9._-]+$")


@router.get("/files")
def list_files():
    """列 output_dir 下 .md / .json 文件（按 mtime 倒序）"""
    output_dir = get_paths().output_dir
    if not output_dir.exists():
        return {"files": []}

    items = []
    for p in sorted(output_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if not p.is_file():
            continue
        if p.suffix.lower() not in ALLOWED_EXTS:
            continue
        if p.name.startswith("."):
            continue
        st = p.stat()
        items.append({
            "name": p.name,
            "size": st.st_size,
            "mtime": st.st_mtime,
        })
    return {"files": items}


@router.get("/files/{name}")
def read_file(name: str):
    """读单个文件, 含 name 校验 + 大小校验 + 越权校验"""
    # 1. 字符白名单
    if not SAFE_NAME.match(name):
        raise HTTPException(status_code=400, detail=f"非法文件名: {name!r}")

    # 2. 解析绝对路径 + 越权校验
    output_dir = get_paths().output_dir.resolve()
    target = (output_dir / name).resolve()
    if not target.is_relative_to(output_dir):
        raise HTTPException(status_code=400, detail=f"路径越权: {name!r}")

    # 3. 存在性
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail=f"文件不存在: {name}")

    # 4. 大小校验
    size = target.stat().st_size
    if size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"文件太大: {size} 字节 (上限 {MAX_FILE_SIZE} 字节 / 10 MB)",
        )

    # 5. MIME 推断
    suffix = target.suffix.lower()
    mime = {
        ".md": "text/markdown",
        ".json": "application/json",
    }.get(suffix, "application/octet-stream")

    return {
        "name": name,
        "content": target.read_text(encoding="utf-8"),
        "mime": mime,
    }
```

- [ ] **Step 2: 跑测试确认 PASS**

Run: `uv run pytest tests/test_web_apis.py -v`
Expected: 全部 PASS

- [ ] **Step 3: 跑全量测试确认无回归**

Run: `uv run pytest tests/ -m "not slow" -q --ignore=tests/rag/ingest/test_analyzer.py`
Expected: 全过（321 + 新增 = 329）

- [ ] **Step 4: 提交**

```bash
git add src/product_decoders/output_api.py tests/test_web_apis.py
git commit -m "feat(api): 新增 output/ 目录只读 API (列文件 + 读文件)"
```

---

## Task 3: 收窄 CORS + 挂载新 router

**Files:**
- Modify: `src/product_decoders/app.py:52-57`

- [ ] **Step 1: 改 app.py 的 CORS 配置 + 挂新 router**

修改 `src/product_decoders/app.py`：

```python
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],  # dev only, 前端 Next.js
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    # 挂载管理后台只读 API
    from .output_api import router as output_router
    app.include_router(output_router)
```

- [ ] **Step 2: 跑测试确认无回归**

Run: `uv run pytest tests/test_web_apis.py tests/product_decoders/ -v`
Expected: 全过

- [ ] **Step 3: 验证 CORS 预检**

手测（可选）：
```bash
uv run python main.py &
curl -X OPTIONS http://localhost:8000/api/output/files \
  -H "Origin: http://localhost:3000" \
  -H "Access-Control-Request-Method: GET" -i
```

Expected: `Access-Control-Allow-Origin: http://localhost:3000` 头

- [ ] **Step 4: 提交**

```bash
git add src/product_decoders/app.py
git commit -m "feat(api): CORS 收窄到 localhost:3000 + 挂载 output_api"
```

---

## Task 4: 创建 `web/` 前端基础结构（无 Next.js 渲染）

**Files:**
- Create: `web/package.json`
- Create: `web/tsconfig.json`
- Create: `web/.gitignore`
- Create: `web/lib/utils.ts`

- [ ] **Step 1: 写 web/.gitignore**

```gitignore
# Next.js
.next/
out/
next-env.d.ts
*.tsbuildinfo

# Bun
node_modules/

# IDE
.vscode/
.idea/
```

- [ ] **Step 2: 写 web/package.json**

```json
{
  "name": "rag-web",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "test": "vitest run",
    "test:watch": "vitest",
    "typecheck": "tsgo --noEmit",
    "lint": "oxlint .",
    "lint:fix": "oxlint . --fix",
    "format": "oxformat .",
    "format:check": "oxformat . --check",
    "prepare": "husky"
  },
  "dependencies": {
    "next": "^15.0.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "react-markdown": "^9.0.0",
    "clsx": "^2.1.0",
    "tailwind-merge": "^2.5.0",
    "class-variance-authority": "^0.7.0",
    "lucide-react": "^0.460.0"
  },
  "devDependencies": {
    "@typescript/native-preview": "^7.0.0-dev.20260607.1",
    "@types/react": "^19.0.0",
    "@types/node": "^22.0.0",
    "tailwindcss": "^4.0.0",
    "@tailwindcss/postcss": "^4.0.0",
    "postcss": "^8.4.0",
    "vitest": "^2.1.0",
    "@testing-library/react": "^16.0.0",
    "@testing-library/jest-dom": "^6.5.0",
    "@vitejs/plugin-react": "^4.3.0",
    "jsdom": "^25.0.0",
    "oxlint": "^1.0.0",
    "oxformat": "^1.0.0",
    "husky": "^9.1.0",
    "lint-staged": "^15.0.0"
  }
}
```

- [ ] **Step 3: 写 web/tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["dom", "dom.iterable", "ES2022"],
    "allowJs": false,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

- [ ] **Step 4: 写 web/lib/utils.ts**

```typescript
// shadcn 要求的 cn() 工具: 合并 className
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
```

- [ ] **Step 5: 提交（不装包, 不渲染, 只脚手架）**

```bash
git add web/.gitignore web/package.json web/tsconfig.json web/lib/utils.ts
git commit -m "feat(web): 初始化 web/ 脚手架 (package.json, tsconfig, utils)"
```

**注**：本 task **不**运行 `bun install`（避免 600MB 依赖落盘 + 装包慢）。装包在 Task 5 一并跑。

---

## Task 5: Tailwind v4 + shadcn 基础配置

**Files:**
- Create: `web/postcss.config.mjs`
- Create: `web/components.json`
- Create: `web/app/globals.css`

**注**：Tailwind v4 不用 `tailwind.config.ts`，所有配置在 `globals.css` 用 `@theme` 块声明。

- [ ] **Step 1: 写 web/postcss.config.mjs**

```javascript
export default {
  plugins: { "@tailwindcss/postcss": {} },
};
```

- [ ] **Step 2: 写 web/components.json (shadcn config)**

```json
{
  "$schema": "https://ui.shadcn.com/schema.json",
  "style": "default",
  "rsc": true,
  "tsx": true,
  "tailwind": {
    "config": "",
    "css": "app/globals.css",
    "baseColor": "slate",
    "cssVariables": true
  },
  "aliases": {
    "components": "@/components",
    "utils": "@/lib/utils"
  }
}
```

- [ ] **Step 3: 写 web/app/globals.css (Tailwind v4 + CSS 变量)**

```css
@import "tailwindcss";

@theme inline {
  --color-background: hsl(var(--background));
  --color-foreground: hsl(var(--foreground));
  --color-border: hsl(var(--border));
  --color-primary: hsl(var(--primary));
  --color-primary-foreground: hsl(var(--primary-foreground));
  --color-muted: hsl(var(--muted));
  --color-muted-foreground: hsl(var(--muted-foreground));
  --color-destructive: hsl(var(--destructive));
  --color-destructive-foreground: hsl(var(--destructive-foreground));
}

:root {
  --background: 0 0% 100%;
  --foreground: 222.2 84% 4.9%;
  --border: 214.3 31.8% 91.4%;
  --primary: 222.2 47.4% 11.2%;
  --primary-foreground: 210 40% 98%;
  --muted: 210 40% 96.1%;
  --muted-foreground: 215.4 16.3% 46.9%;
  --destructive: 0 84.2% 60.2%;
  --destructive-foreground: 210 40% 98%;
}

.dark {
  --background: 222.2 84% 4.9%;
  --foreground: 210 40% 98%;
  --border: 217.2 32.6% 17.5%;
  --primary: 210 40% 98%;
  --primary-foreground: 222.2 47.4% 11.2%;
  --muted: 217.2 32.6% 17.5%;
  --muted-foreground: 215 20.2% 65.1%;
  --destructive: 0 62.8% 30.6%;
  --destructive-foreground: 210 40% 98%;
}
```

- [ ] **Step 4: 提交**

```bash
git add web/postcss.config.mjs web/components.json web/app/globals.css
git commit -m "feat(web): Tailwind v4 + shadcn 配置 (globals.css 含 CSS 变量)"
```

---

## Task 6: `lib/api.ts` 封装 + vitest 配置

**Files:**
- Create: `web/lib/api.ts`
- Create: `web/lib/api.test.ts`
- Create: `web/vitest.config.ts`

- [ ] **Step 1: 写 web/lib/api.ts (含 ApiError / NetworkError 分类)**

```typescript
// fetch 封装: 统一错误处理, 后端 HTTPException 抛 ApiError, 5xx/网络错 抛 NetworkError

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

export class NetworkError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "NetworkError";
  }
}

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const ctrl = new AbortController();
  const timeout = setTimeout(() => ctrl.abort(), 10_000);

  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, { ...init, signal: ctrl.signal });
  } catch (e) {
    throw new NetworkError(e instanceof Error ? e.message : String(e));
  } finally {
    clearTimeout(timeout);
  }

  if (!res.ok) {
    const detail = (await res.json().catch(() => ({}))).detail ?? res.statusText;
    throw new ApiError(res.status, String(detail));
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string; series_count: number }>("/health"),
  listSeries: () => request<Array<{ series: string; manufacturer: string; name: string; prefix: string }>>("/series"),
  decode: (model: string) =>
    request<Record<string, unknown>>("/decode", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model }),
    }),
  listOutputFiles: () =>
    request<{ files: Array<{ name: string; size: number; mtime: number }> }>("/api/output/files"),
  readOutputFile: (name: string) =>
    request<{ name: string; content: string; mime: string }>(`/api/output/files/${encodeURIComponent(name)}`),
};
```

- [ ] **Step 2: 写 web/lib/api.test.ts (Vitest) — 红测试**

```typescript
import { describe, it, expect, vi, beforeEach } from "vitest";
import { api, ApiError, NetworkError } from "./api";

describe("api wrapper", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("成功路径: 200 → 返回 json", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ status: "ok", series_count: 3 }),
    }));
    const r = await api.health();
    expect(r.status).toBe("ok");
    expect(r.series_count).toBe(3);
  });

  it("4xx → 抛 ApiError 带 status 和 detail", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      statusText: "Bad Request",
      json: async () => ({ detail: "非法文件名" }),
    }));
    await expect(api.readOutputFile("../etc/passwd")).rejects.toMatchObject({
      name: "ApiError",
      status: 400,
      message: "非法文件名",
    });
  });

  it("5xx → 抛 ApiError", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      statusText: "Internal Server Error",
      json: async () => ({ detail: "挂了" }),
    }));
    await expect(api.health()).rejects.toBeInstanceOf(ApiError);
  });

  it("fetch reject → 抛 NetworkError", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("ECONNREFUSED")));
    await expect(api.health()).rejects.toBeInstanceOf(NetworkError);
  });
});
```

- [ ] **Step 3: 写 web/vitest.config.ts**

```typescript
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
  },
});
```

- [ ] **Step 4: 写 web/vitest.setup.ts**

```typescript
import "@testing-library/jest-dom/vitest";
```

- [ ] **Step 5: 安装依赖 + 跑单测**

Run: `cd web && bun install`
Expected: 装包成功, `bun.lock` 自动生成

Run: `cd web && bun test`
Expected: 4 个测试 PASS

- [ ] **Step 6: 提交**

```bash
git add web/lib/api.ts web/lib/api.test.ts web/vitest.config.ts web/vitest.setup.ts web/bun.lock
git commit -m "feat(web): lib/api.ts fetch 封装 + ApiError/NetworkError + 4 个 vitest"
```

---

## Task 7: shadcn 组件复制进 `web/components/ui/`

**Files:**
- Create: `web/components/ui/button.tsx`
- Create: `web/components/ui/input.tsx`
- Create: `web/components/ui/card.tsx`
- Create: `web/components/ui/table.tsx`
- Create: `web/components/ui/badge.tsx`
- Create: `web/components/ui/alert.tsx`

- [ ] **Step 1: 用 shadcn CLI 复制组件**

Run: `cd web && bunx shadcn@latest add button input card table badge alert`
Expected: 6 个 .tsx 文件复制到 `web/components/ui/`, 全部用 `cn()` from `@/lib/utils`

**注**: 本 task 实际是"执行 CLI 复制"而不是手写代码。如果网络/CLI 不可用，手动复制 shadcn 官方源码（[ui.shadcn.com](https://ui.shadcn.com)），用 spec 里的 6 个组件即可。

- [ ] **Step 2: 验证导入路径**

Run: `cd web && bunx tsgo --noEmit`
Expected: 0 个错误（组件导入 `@/lib/utils` 解析成功）

- [ ] **Step 3: 提交**

```bash
git add web/components/ui/
git commit -m "feat(web): 6 个 shadcn 组件 (button/input/card/table/badge/alert)"
```

---

## Task 7.5: husky + lint-staged + oxlint/oxformat 配置

**Files:**
- Create: `web/.oxlintrc.json`
- Create: `web/.oxfmtrc.json`
- Create: `web/lint-staged.config.js`
- Create: `web/.husky/pre-commit`

- [ ] **Step 1: 写 web/.oxlintrc.json (oxlint 规则)**

```json
{
  "$schema": "https://oxc.rs/schema/oxlint.json",
  "categories": {
    "correctness": "error",
    "suspicious": "warn",
    "style": "warn"
  },
  "rules": {
    "no-unused-vars": "warn",
    "no-console": "off"
  },
  "ignore": ["node_modules", ".next", "out"]
}
```

- [ ] **Step 2: 写 web/.oxfmtrc.json (oxfmt 配置)**

```json
{
  "$schema": "https://oxc.rs/schema/oxfmt.json",
  "printWidth": 100,
  "singleQuote": false,
  "tabWidth": 2,
  "trailingComma": "all"
}
```

- [ ] **Step 3: 写 web/lint-staged.config.js**

```javascript
// lint-staged: 只对暂存的文件跑 lint + format, 不影响未暂存代码
export default {
  "*.{ts,tsx}": (stagedFiles) => {
    const files = stagedFiles.join(" ");
    return [
      `oxlint ${files} --fix`,
      `oxfmt ${files}`,
    ];
  },
  "*.{json,md}": (stagedFiles) => {
    const files = stagedFiles.join(" ");
    return [`oxfmt ${files}`];
  },
};
```

- [ ] **Step 4: 初始化 husky**

Run: `cd web && bunx husky init`
Expected: 创建 `web/.husky/pre-commit`（默认内容）+ 自动注册 `prepare` 脚本

- [ ] **Step 5: 改 web/.husky/pre-commit**

**Files:**
- Modify: `web/.husky/pre-commit` (覆盖 husky init 生成的内容)

```bash
#!/usr/bin/env sh
# 前端 pre-commit: lint-staged 跑 oxlint/oxformat, 然后全量 vitest + tsgo
# 后端走根 .pre-commit-config.yaml, 跟前端 husky 互不干扰

cd web

# 1. lint-staged (只对暂存文件)
bunx lint-staged

# 2. 全量 typecheck (拦截 TS 错)
bunx tsgo --noEmit

# 3. 全量单测 (拦截回归)
bun test --run

# 4. 格式检查 (拦截未格式化代码)
bun run format:check
```

- [ ] **Step 6: 让 husky pre-commit 可执行**

Run: `cd web && chmod +x .husky/pre-commit` (Windows 上 Git Bash 跑; PowerShell 用 `git update-index --chmod=+x web/.husky/pre-commit`)

- [ ] **Step 7: 手测 husky hook**

```bash
cd web
# 故意引入一个 TS 错
echo 'const x: number = "string";' > test-broken.ts
git add test-broken.ts
git -c user.name=test -c user.email=test@local commit -m "test husky"
```

Expected: pre-commit 跑 `tsgo --noEmit` 报错, commit 被拒绝

清理：
```bash
rm web/test-broken.ts
git reset HEAD web/test-broken.ts
```

- [ ] **Step 8: 提交**

```bash
git add web/.oxlintrc.json web/.oxfmtrc.json web/lint-staged.config.js web/.husky/
git commit -m "feat(web): husky pre-commit + oxlint + oxformat + lint-staged"
```

---

## Task 8: 4 个页面 (根布局 + 仪表盘 + decode + output 列表 + output 详情)

**Files:**
- Create: `web/app/layout.tsx`
- Create: `web/app/page.tsx`
- Create: `web/app/decode/page.tsx`
- Create: `web/app/output/page.tsx`
- Create: `web/app/output/[file]/page.tsx`
- Create: `web/next.config.ts`

- [ ] **Step 1: 写 web/next.config.ts**

```typescript
import type { NextConfig } from "next";

const config: NextConfig = {
  reactStrictMode: true,
};

export default config;
```

- [ ] **Step 2: 写 web/app/layout.tsx (根布局 + 顶部 nav)**

```tsx
import Link from "next/link";
import "./globals.css";
import { cn } from "@/lib/utils";

export const metadata = { title: "RAG 管理后台" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh">
      <body className={cn("min-h-screen bg-background text-foreground")}>
        <nav className="border-b">
          <div className="container mx-auto flex gap-6 px-4 py-3">
            <Link href="/" className="font-semibold">RAG</Link>
            <Link href="/decode">Decode</Link>
            <Link href="/output">Output</Link>
          </div>
        </nav>
        <main className="container mx-auto px-4 py-8">{children}</main>
      </body>
    </html>
  );
}
```

- [ ] **Step 3: 写 web/app/page.tsx (仪表盘)**

```tsx
"use client";
import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api, ApiError, NetworkError } from "@/lib/api";

export default function Dashboard() {
  const [status, setStatus] = useState<string>("加载中...");
  const [series, setSeries] = useState<Array<{ series: string; manufacturer: string; name: string }>>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const h = await api.health();
        setStatus(`服务在线 · 已注册 ${h.series_count} 个系列`);
        setSeries(await api.listSeries());
      } catch (e) {
        setErr(e instanceof ApiError || e instanceof NetworkError ? e.message : String(e));
      }
    })();
  }, []);

  if (err) return <div className="text-destructive">错误: {err}</div>;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader><CardTitle>健康状态</CardTitle></CardHeader>
        <CardContent>{status}</CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>已注册系列</CardTitle></CardHeader>
        <CardContent>
          <ul className="space-y-1">
            {series.map((s) => (
              <li key={s.series}>
                <span className="font-mono">{s.series}</span> · {s.manufacturer} · {s.name}
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
```

- [ ] **Step 4: 写 web/app/decode/page.tsx (decode 表单)**

```tsx
"use client";
import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableRow } from "@/components/ui/table";
import { api, ApiError, NetworkError } from "@/lib/api";

export default function DecodePage() {
  const [model, setModel] = useState("");
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const submit = async () => {
    setErr(null);
    setLoading(true);
    try {
      setResult(await api.decode(model));
    } catch (e) {
      setErr(e instanceof ApiError || e instanceof NetworkError ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader><CardTitle>产品订货号解码</CardTitle></CardHeader>
        <CardContent className="space-y-2">
          <Input
            placeholder="1LE0001-1AA42-1AA4"
            value={model}
            onChange={(e) => setModel(e.target.value)}
            disabled={loading}
          />
          <Button onClick={submit} disabled={loading || !model}>
            {loading ? "解码中..." : "解码"}
          </Button>
          {err && <p className="text-destructive text-sm">{err}</p>}
        </CardContent>
      </Card>
      {result && (
        <Card>
          <CardHeader><CardTitle>结果</CardTitle></CardHeader>
          <CardContent>
            <Table>
              <TableBody>
                {Object.entries(result).map(([k, v]) => (
                  <TableRow key={k}>
                    <TableCell className="font-mono text-xs">{k}</TableCell>
                    <TableCell className="text-xs">{JSON.stringify(v)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
```

- [ ] **Step 5: 写 web/app/output/page.tsx (output 列表)**

```tsx
"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { api, ApiError, NetworkError } from "@/lib/api";

export default function OutputList() {
  const [files, setFiles] = useState<Array<{ name: string; size: number; mtime: number }>>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const r = await api.listOutputFiles();
        setFiles(r.files);
      } catch (e) {
        setErr(e instanceof ApiError || e instanceof NetworkError ? e.message : String(e));
      }
    })();
  }, []);

  if (err) return <Alert variant="destructive"><AlertDescription>{err}</AlertDescription></Alert>;
  if (!files.length) return <p className="text-muted-foreground">output 目录为空, 跑一次 `uv run python main.py ingest` 再回来。</p>;

  return (
    <Card>
      <CardHeader><CardTitle>解析产物 (output/)</CardTitle></CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>文件名</TableHead>
              <TableHead>大小</TableHead>
              <TableHead>修改时间</TableHead>
              <TableHead>操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {files.map((f) => (
              <TableRow key={f.name}>
                <TableCell className="font-mono">{f.name}</TableCell>
                <TableCell><Badge variant="secondary">{(f.size / 1024).toFixed(1)} KB</Badge></TableCell>
                <TableCell className="text-xs text-muted-foreground">{new Date(f.mtime * 1000).toLocaleString("zh-CN")}</TableCell>
                <TableCell><Link href={`/output/${encodeURIComponent(f.name)}`} className="text-primary underline">查看</Link></TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 6: 写 web/app/output/[file]/page.tsx (markdown 详情)**

```tsx
"use client";
import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { api, ApiError, NetworkError } from "@/lib/api";

export default function OutputDetail({ params }: { params: Promise<{ file: string }> }) {
  const [name, setName] = useState<string>("");
  const [content, setContent] = useState<string>("");
  const [mime, setMime] = useState<string>("");
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      const { file } = await params;
      setName(file);
      try {
        const r = await api.readOutputFile(file);
        setContent(r.content);
        setMime(r.mime);
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) {
          setErr("文件已被删除或不存在");
        } else {
          setErr(e instanceof ApiError || e instanceof NetworkError ? e.message : String(e));
        }
      }
    })();
  }, [params]);

  if (err) return <Alert variant="destructive"><AlertDescription>{err}</AlertDescription></Alert>;

  return (
    <Card>
      <CardHeader><CardTitle className="font-mono">{name}</CardTitle></CardHeader>
      <CardContent>
        {mime === "text/markdown" ? (
          <article className="prose dark:prose-invert max-w-none">
            <ReactMarkdown>{content}</ReactMarkdown>
          </article>
        ) : (
          <pre className="overflow-x-auto rounded bg-muted p-4 text-xs">{content}</pre>
        )}
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 7: 跑 TypeScript 编译**

Run: `cd web && bunx tsgo --noEmit`
Expected: 0 个错误

- [ ] **Step 8: 提交**

```bash
git add web/next.config.ts web/app/
git commit -m "feat(web): 4 个页面 (layout/仪表盘/decode/output列表/output详情)"
```

---

## Task 9: 2 个页面测试 + `web/CLAUDE.md` + 根 `.gitignore` + README 追加

**Files:**
- Create: `web/app/decode/page.test.tsx`
- Create: `web/app/output/page.test.tsx`
- Create: `web/CLAUDE.md`
- Modify: `.gitignore` (追加 web/node_modules 等)
- Modify: `README.md` (追加"启动前端"小节)

- [ ] **Step 1: 写 web/app/decode/page.test.tsx**

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import DecodePage from "./page";
import { api } from "@/lib/api";

vi.mock("@/lib/api", () => ({ api: { decode: vi.fn() }, ApiError: class extends Error {}, NetworkError: class extends Error {} }));

describe("DecodePage", () => {
  beforeEach(() => vi.clearAllMocks());

  it("输入型号 + 提交 → 渲染结果表格", async () => {
    (api.decode as any).mockResolvedValue({ series: "siemens_1le0", raw_input: "1LE0001" });
    render(<DecodePage />);
    fireEvent.change(screen.getByPlaceholderText("1LE0001-1AA42-1AA4"), { target: { value: "1LE0001" } });
    fireEvent.click(screen.getByText("解码"));
    await waitFor(() => expect(screen.getByText("series")).toBeInTheDocument());
    expect(screen.getByText('"siemens_1le0"')).toBeInTheDocument();
  });

  it("decode 抛错 → 渲染错误信息", async () => {
    (api.decode as any).mockRejectedValue(new Error("挂了"));
    render(<DecodePage />);
    fireEvent.change(screen.getByPlaceholderText("1LE0001-1AA42-1AA4"), { target: { value: "x" } });
    fireEvent.click(screen.getByText("解码"));
    await waitFor(() => expect(screen.getByText("挂了")).toBeInTheDocument());
  });
});
```

- [ ] **Step 2: 写 web/app/output/page.test.tsx**

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import OutputList from "./page";
import { api } from "@/lib/api";

vi.mock("@/lib/api", () => ({ api: { listOutputFiles: vi.fn() }, ApiError: class extends Error {}, NetworkError: class extends Error {} }));

describe("OutputList", () => {
  beforeEach(() => vi.clearAllMocks());

  it("空目录 → 提示跑 ingest", async () => {
    (api.listOutputFiles as any).mockResolvedValue({ files: [] });
    render(<OutputList />);
    await waitFor(() => expect(screen.getByText(/output 目录为空/)).toBeInTheDocument());
  });

  it("有文件 → 渲染表格", async () => {
    (api.listOutputFiles as any).mockResolvedValue({
      files: [{ name: "doc.md", size: 1024, mtime: Date.now() / 1000 }],
    });
    render(<OutputList />);
    await waitFor(() => expect(screen.getByText("doc.md")).toBeInTheDocument());
  });

  it("API 抛错 → 渲染错误 Alert", async () => {
    (api.listOutputFiles as any).mockRejectedValue(new Error("连接拒绝"));
    render(<OutputList />);
    await waitFor(() => expect(screen.getByText("连接拒绝")).toBeInTheDocument());
  });
});
```

- [ ] **Step 3: 跑前端测试**

Run: `cd web && bun test`
Expected: 4 (api) + 2 (decode) + 3 (output) = 9 个测试 PASS

- [ ] **Step 4: 写 web/CLAUDE.md**

```markdown
# web/ 前端局部约定

## 包管理

- 用 `bun`（不用 npm/pnpm/yarn）
- 装包：`bun install`
- 装包后 `bun.lock` 自动生成, 入库

## 工具链 (替代 ESLint + Prettier + tsc)

- **类型检查**：`@typescript/native-preview` 的 `tsgo` 二进制 (10x 快于 tsc)
  ```bash
  bun run typecheck    # = tsgo --noEmit
  ```
- **Lint**：`oxlint` (Rust 写的, 极快)
  ```bash
  bun run lint         # 检查
  bun run lint:fix     # 自动修
  ```
- **Format**：`oxformat` (跟 Prettier 兼容)
  ```bash
  bun run format         # 写
  bun run format:check   # 只检查
  ```
- **Pre-commit**：`husky` + `lint-staged`
  ```bash
  .husky/pre-commit  # 跑 lint-staged → tsgo → vitest → format:check
  ```

## 跑测试

```bash
bun test              # 一次性跑全部
bun test:watch        # watch 模式
```

## 跑 dev server

```bash
bun run dev           # localhost:3000
```

**dev 模式要开两个终端**：
1. 后端：`uv run python main.py` (localhost:8000)
2. 前端：`cd web && bun run dev` (localhost:3000)

CORS 已在后端配好（`http://localhost:3000`）。

## 加 shadcn 组件

```bash
cd web && bunx shadcn@latest add <component-name>
```

组件复制到 `web/components/ui/`, 不装成 npm 依赖。

## TDD 流程

- 测试文件跟实现文件同目录, 后缀 `.test.ts` / `.test.tsx`
- 先红后绿, commit 用 `test:` / `feat:` 前缀
- **commit 前 husky 会自动跑 lint/typecheck/test**，不用手动跑全套

## 样式约定

- Tailwind v4 + shadcn/ui (Default + Slate)
- 不用 CSS modules, 不用 styled-components
- 组合类用 `cn()` from `@/lib/utils`
```

- [ ] **Step 5: 改根 .gitignore**

追加到现有 `.gitignore`：

```
# Next.js / web
web/node_modules/
web/.next/
web/out/
*.tsbuildinfo
next-env.d.ts
# 不用忽略 web/.husky/ (hooks 要入库)
```

- [ ] **Step 6: 改 README.md 加"启动前端"小节**

在 `## 文档` 小节**之前**插入：

```markdown
## 启动前端 (管理后台)

```bash
# 终端 1: 启后端
uv run python main.py

# 终端 2: 启前端 (cd web 装包, 再跑 dev)
cd web && bun install && bun run dev
```

打开 http://localhost:3000 看管理后台。

- 后端 FastAPI: 端口 8000
- 前端 Next.js: 端口 3000
- CORS 已配 (`http://localhost:3000`), 无需额外配置
```

- [ ] **Step 7: 跑全量验证**

Run (后端): `uv run pytest tests/ -m "not slow" -q --ignore=tests/rag/ingest/test_analyzer.py`
Expected: 329 passed (含 Task 1 的 12 个新测试)

Run (前端): `cd web && bun test`
Expected: 9 passed

Run (前端类型): `cd web && bunx tsc --noEmit`
Expected: 0 错误

- [ ] **Step 8: 提交**

```bash
git add web/app/decode/page.test.tsx web/app/output/page.test.tsx web/CLAUDE.md .gitignore README.md
git commit -m "docs+test: 前端 vitest 页面测试 + web/CLAUDE.md + 根 .gitignore + README"
```

---

## Task 10: 全量验证 + 手测

**Files:**
- (无代码改动)

- [ ] **Step 1: 后端全量回归**

Run: `uv run pytest tests/ -m "not slow" -q --ignore=tests/rag/ingest/test_analyzer.py`
Expected: 329 passed

- [ ] **Step 2: 前端全量测试**

Run: `cd web && bun test`
Expected: 9 passed

- [ ] **Step 3: 前端类型检查**

Run: `cd web && bunx tsgo --noEmit`
Expected: 0 错误

- [ ] **Step 3.5: 前端 lint + format**

Run: `cd web && bun run lint && bun run format:check`
Expected: 0 错

- [ ] **Step 3.6: husky hook 安装验证**

Run: `cd web && ls -la .husky/pre-commit && cat .husky/pre-commit | head -5`
Expected: 文件存在, 首行 `#!/usr/bin/env sh`

- [ ] **Step 4: ruff**

Run: `uv run ruff check .`
Expected: 14 个预存错误（master 就在的, 跟我无关）

- [ ] **Step 5: 手测后端 2 个新 API**

```bash
# 启后端
uv run python main.py &
sleep 3

# 测列文件 (output/ 目录是空的, 应该返 files: [])
curl http://localhost:8000/api/output/files

# 测读不存在文件
curl -i http://localhost:8000/api/output/files/nope.md

# 测越权
curl -i "http://localhost:8000/api/output/files/..%2Fetc%2Fpasswd"

# 写个测试文件再读
echo "# Title" > output/test.md
curl http://localhost:8000/api/output/files/test.md
```

Expected:
- 空目录 → `{"files": []}`
- nope.md → 404
- 越权 → 400
- 写后再读 → `{name, content, mime}`

- [ ] **Step 6: 验证 git log**

Run: `git log --oneline -10`
Expected: 看到本计划 9 个 feat/docs commits

---

## 总结

11 个 task，11 个 commit（后端 API + CORS + 4 个前端页面 + 9 个前端测试 + husky/oxlint/oxformat + 文档）。

实现完后：
- 后端：`uv run python main.py` 起服务，`/api/output/files` 和 `/api/output/files/{name}` 可用
- 前端：cd `web && bun install && bun run dev`，浏览器开 `http://localhost:3000`
- 工具链：
  - `bun run lint` → oxlint
  - `bun run format` → oxformat
  - `bun run typecheck` → tsgo (`@typescript/native-preview` 二进制)
  - `git commit` → husky pre-commit 跑 lint-staged + tsgo + vitest + format:check
- 测试：后端 329 passed，前端 9 passed
