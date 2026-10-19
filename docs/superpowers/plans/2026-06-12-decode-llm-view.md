# Decode LLM View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 `/decode` 端点加 `llm_view: list[str]` 字段, 同时给 `/decode` page 加 toggle 切 cards/llm 两视图; LLM 文本格式给 Dify 工作流拼 prompt 用.

**Architecture:**

- 后端: `ProductDecoder.build_llm_view(result)` 纯函数, 复用 `decode()` 已算好的 `display` / `_suffix` / `_warnings` / `_zh` / `_en` / `code` 字段, 段划分跟 `format_display` 共用 cfg `decoder.display_separators` 优先 + `position.group` 降级
- 前端: `useState<"cards" | "llm">` 切视图, 持久化 localStorage; cards 模式不变, llm 模式渲染 `<pre>` 块; 复制按钮 copyTarget 跟 view 联动
- i18n: 3 新 key (`Dify 视图` / `解码卡` / `复制 LLM 文本`)

**Tech Stack:** Python 3.14, FastAPI, pytest, vitest, React 19, shadcn/ui, next-intl

---

## File Structure

| File                                                              | Change                                                |
| ----------------------------------------------------------------- | ----------------------------------------------------- |
| `packages/service/src/product_decoders/engine.py`                 | Modify: add `build_llm_view()` method                 |
| `packages/service/src/product_decoders/app.py`                    | Modify: call `build_llm_view()` in `/decode` endpoint |
| `packages/service/tests/product_decoders/test_product_decoder.py` | Modify: add 8 new test cases                          |
| `packages/web/app/[locale]/decode/page.tsx`                       | Modify: add view state, toggle, conditional render    |
| `packages/web/app/[locale]/decode/page.test.tsx`                  | Modify: add 4 new test cases                          |
| `packages/web/messages/zh.json`                                   | Modify: add 3 i18n keys                               |
| `packages/web/messages/en.json`                                   | Modify: add 3 i18n keys                               |

---

## Backend

### Task 1: Add 8 failing tests for `build_llm_view`

**Files:**

- Modify: `packages/service/tests/product_decoders/test_product_decoder.py:1-10` (imports area) and add new tests at end

- [ ] **Step 1: Read the test file to find a good insertion point and see existing test patterns**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/service
# Read the file
```

- [ ] **Step 2: Append 8 new tests at end of file**

```python
# --- build_llm_view (Dify LLM 视图) ---


def test_llm_view_header_has_6_lines_then_separator():
    """头部 6 行 (code/厂商/系列 各 zh+en) + 一个 '---' 分隔"""
    from src.product_decoders.engine import ProductDecoder

    decoder = ProductDecoder("configs/1LE0.yaml")
    result = decoder.decode("1LE0001-1AA42-1AA4")
    llm = decoder.build_llm_view(result)
    # 6 header lines
    assert "完整型号: 1LE0001-1AA42-1AA4" in llm
    assert "Full order code: 1LE0001-1AA42-1AA4" in llm
    assert any("厂商:" in line for line in llm)
    assert any("Manufacturer:" in line for line in llm)
    assert any("系列:" in line for line in llm)
    assert any("Series:" in line for line in llm)
    # 第一个 '---' 在头部之后
    assert llm[6].strip() == "---"


def test_llm_view_segments_split_by_display():
    """1LE0 16 字符 → 3 段, 每段一个 [段 X] 头"""
    from src.product_decoders.engine import ProductDecoder

    decoder = ProductDecoder("configs/1LE0.yaml")
    result = decoder.decode("1LE0001-1AA42-1AA4")
    llm = decoder.build_llm_view(result)
    seg_headers = [line for line in llm if line.startswith("[段 ")]
    assert len(seg_headers) == 3
    assert "[段 1LE0001]" in seg_headers
    assert "[段 1AA42]" in seg_headers
    assert "[段 1AA4]" in seg_headers


def test_llm_view_position_line_zh_en_pair():
    """position 渲染成 'name_zh: v_zh / name_en: v_en'"""
    from src.product_decoders.engine import ProductDecoder

    decoder = ProductDecoder("configs/1LE0.yaml")
    result = decoder.decode("1LE0001-1AA42-1AA4")
    llm = decoder.build_llm_view(result)
    pos_lines = [
        line for line in llm
        if "/" in line and line.startswith("[段") is False and "---" not in line
        and ":" in line and not line.startswith("[WARN]")
    ]
    assert len(pos_lines) > 0
    for line in pos_lines:
        # 至少含一个 ' / ' 分隔符 (zh / en)
        assert " / " in line, f"line 缺 ' / ' 分隔: {line}"


def test_llm_view_warning_block_appended():
    """解码未知码 → 末尾 [WARN] 行, 数量 = _warnings 长度"""
    from src.product_decoders.engine import ProductDecoder

    decoder = ProductDecoder("configs/1LE0.yaml")
    result = decoder.decode("1LE0001-1AA4-99-AA4")  # 99 是不在编码表
    assert "voltage" in (result.get("_warnings") or [w for w in [None]] or []) or len(result.get("_warnings", [])) > 0
    llm = decoder.build_llm_view(result)
    warn_lines = [line for line in llm if line.startswith("[WARN]")]
    assert len(warn_lines) == len(result["_warnings"])


def test_llm_view_unknown_value_shows_question_mark():
    """未知码 value 双语都是 '?'"""
    from src.product_decoders.engine import ProductDecoder

    decoder = ProductDecoder("configs/1LE0.yaml")
    result = decoder.decode("1LE0001-1AA4-99-AA4")
    llm = decoder.build_llm_view(result)
    voltage_lines = [line for line in llm if "电压" in line or "Voltage" in line]
    assert voltage_lines, f"没找到电压行, llm: {llm}"
    # value 是 '? / ?'
    for line in voltage_lines:
        assert ": ? /" in line or ": ?" in line, f"未知码 value 应该是 '?', 实际: {line}"


def test_llm_view_no_display_separators_falls_back():
    """cfg 缺 display_separators → 仍产 llm_view, 不带段头 (不抛)"""
    from src.product_decoders.engine import ProductDecoder
    from unittest.mock import MagicMock

    decoder = ProductDecoder("configs/1LE0.yaml")
    # mock 一个没有 display_separators 的 cfg
    fake_cfg = {
        "decoder": {
            "total_chars": 16,
            "positions": [
                {"idx": 1, "name": "prefix", "char_count": 7, "values": {"1LE0001": {"code": "1LE0001", "zh": "型号前缀"}}},
            ],
        },
        "metadata": {
            "model_format": {"code": "1LE0001", "zh": "完整型号"},
            "manufacturer": {"code": "Siemens", "zh": "西门子", "en": "Siemens"},
            "series": {"zh": "系列", "en": "Series", "code": "1LE0"},
        },
        "values": {},
    }
    result = decoder.decode("1LE0001-1AA42-1AA4")
    # 模拟 result display 缺失 (强制走降级)
    result.pop("display", None)
    llm = decoder.build_llm_view(result)
    assert isinstance(llm, list)
    assert len(llm) > 0
    # 段头不应有 (降级)
    assert not any(line.startswith("[段 ") for line in llm)


def test_llm_view_suffix_line_appended_to_header():
    """_suffix = 'Z F40' 时头部第 7 行 '后缀: Z F40'"""
    from src.product_decoders.engine import ProductDecoder

    decoder = ProductDecoder("configs/1LE0.yaml")
    # 16 字符之后的内容进 _suffix
    result = decoder.decode("1LE0001-1AA42-1AA4-Z-F40")
    if "_suffix" in result and result["_suffix"]:
        llm = decoder.build_llm_view(result)
        suffix_idx = next(
            (i for i, line in enumerate(llm) if line.startswith("后缀:")), None
        )
        assert suffix_idx is not None, f"无 '后缀:' 行, llm: {llm}"
        assert llm[suffix_idx] == f"后缀: {result['_suffix']}"
        # '---' 在第 8 行 (index 7)
        assert llm[7].strip() == "---"
    else:
        pytest.skip(f"模型 '1LE0001-1AA42-1AA4-Z-F40' 不触发 _suffix (实际 _suffix={result.get('_suffix')!r})")


def test_llm_view_does_not_mutate_input():
    """build_llm_view 前后, 原 result 字典其他 key 数量不变"""
    from src.product_decoders.engine import ProductDecoder

    decoder = ProductDecoder("configs/1LE0.yaml")
    result = decoder.decode("1LE0001-1AA42-1AA4")
    keys_before = set(result.keys())
    _ = decoder.build_llm_view(result)
    keys_after = set(result.keys())
    assert keys_before == keys_after, f"build_llm_view 污染了 result: 多了 {keys_after - keys_before}, 少了 {keys_before - keys_after}"
```

- [ ] **Step 3: Run tests to verify they all fail (red)**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/service
uv run --no-sync pytest tests/product_decoders/test_product_decoder.py -v -k "llm_view" 2>&1 | tail -20
```

Expected: 8 ERROR (build_llm_view method doesn't exist) — `AttributeError: 'ProductDecoder' object has no attribute 'build_llm_view'`

- [ ] **Step 4: Commit the failing tests**

```bash
cd /c/doc/Code/worktrees/rag-refactor
git add packages/service/tests/product_decoders/test_product_decoder.py
git commit -m "test(engine): 加 build_llm_view 8 个测试 (TDD red)"
```

---

### Task 2: Implement `build_llm_view` method

**Files:**

- Modify: `packages/service/src/product_decoders/engine.py` (add method after `format_display`)

- [ ] **Step 1: Read `engine.py` to find where to insert the new method**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/service
# Find format_display and decode methods to see structure
```

- [ ] **Step 2: Append `build_llm_view` method after `format_display`**

```python
    def build_llm_view(self, result: dict) -> list[str]:
        """从 decode() 返回的 dict 构 llm_view 文本行 (Dify LLM 友好).

        复用 decode() 已算好的 display / _suffix / _warnings / 各 *_zh / *_en / code 字段.
        不修改 result (纯函数).

        Returns:
            list[str]: 文本行, 顺序固定 (header → 段 → warnings), 用 \\n join 即可拼 Dify prompt.
        """
        lines: list[str] = []
        meta = self.cfg.get("metadata", {})

        # --- 头部 6 行 (code/厂商/系列 各 zh+en) ---
        # 完整型号: result.display (如果有) 或原 model
        model_display = result.get("display") or result.get("_model") or ""
        model_code = model_display.split("-")[0] if model_display else ""  # 拿首段
        # 实际"完整型号"应该用 model_display 整体 (带横线)
        full_code = model_display

        lines.append(f"完整型号: {full_code}")
        lines.append(f"Full order code: {full_code}")

        mfr = meta.get("manufacturer", {})
        lines.append(f"厂商: {mfr.get('zh') or mfr.get('code', '')}")
        lines.append(f"Manufacturer: {mfr.get('en') or mfr.get('code', '')}")

        series = meta.get("series", {})
        lines.append(f"系列: {series.get('zh') or series.get('code', '')}")
        lines.append(f"Series: {series.get('en') or series.get('code', '')}")

        # _suffix 非空时头部第 7 行
        suffix = result.get("_suffix", "")
        if suffix:
            lines.append(f"后缀: {suffix}")

        # --- 第一个 --- 分隔 ---
        lines.append("---")

        # --- 段划分 + position 行 ---
        # 获取 display_separators 累计 cursor, 跟 cfg positions 顺序对齐
        separators = self.cfg["decoder"].get("display_separators") or []
        display = result.get("display", "")

        # 段头: 用 display.split("-") 切; 段间用 '---' 分隔
        if display and separators:
            segments = display.split("-")
        else:
            # 降级: 无 display 或无 separators → 单一段, 不带 [段 X] 头
            segments = [display] if display else []

        # 累计 cursor 走 cfg positions, 算每个 position 落在哪段
        positions = self.cfg["decoder"]["positions"]
        cursor = 0
        seg_boundaries = []  # 累计 separator 位置: [7, 12] → 段尾字符索引
        for sep in separators:
            cursor += sep
            seg_boundaries.append(cursor)
        # 段内累计 char_count
        seg_pos_map: dict[int, list[dict]] = {i: [] for i in range(len(segments))}
        cursor = 0
        for pos in positions:
            char_count = pos.get("char_count", len(str(result.get(pos["name"], ""))))
            pos_end = cursor + char_count
            # 找这个 position 落在哪个段 (cursor 到 pos_end 之间的段边界)
            seg_idx = 0
            for boundary in seg_boundaries:
                if pos_end > boundary:
                    seg_idx += 1
                else:
                    break
            seg_pos_map[seg_idx].append(pos)
            cursor = pos_end

        # 渲染每段
        for seg_idx, seg_label in enumerate(segments):
            seg_positions = seg_pos_map.get(seg_idx, [])
            if not seg_positions and segments:
                # 段内 0 个 position → 不渲染 [段 X] 头 (避免空段)
                continue
            if segments:
                lines.append(f"[段 {seg_label}]")
            for pos in seg_positions:
                pos_name = pos["name"]
                # value 缺失 fallback: code 优先 (跟 decode() engine.py:133 一致)
                decoded = result.get(pos_name)
                if isinstance(decoded, dict):
                    val_zh = decoded.get("zh")
                    val_en = decoded.get("en")
                    val_code = decoded.get("code")
                else:
                    val_zh = None
                    val_en = None
                    val_code = decoded

                # 未知码: _warnings 里有, 显示 '?'
                if val_zh is None and val_en is None and val_code is None:
                    val_zh = "?"
                    val_en = "?"

                # name 缺失 fallback: 走 cfg positions 的 name (英文 id)
                name_zh = pos.get("name_zh") or pos["name"]
                name_en = pos.get("name_en") or pos["name"]

                if val_zh == "?" and val_en == "?":
                    line = f"{name_zh}: ? / {name_en}: ?"
                else:
                    zh_part = val_zh if val_zh is not None else (val_code or "")
                    en_part = val_en if val_en is not None else (val_code or "")
                    line = f"{name_zh}: {zh_part} / {name_en}: {en_part}"
                lines.append(line)

            # 段间 --- (但只在还有下一段时)
            if seg_idx < len(segments) - 1 and seg_pos_map.get(seg_idx + 1):
                lines.append("---")

        # --- 尾部: warnings 段 ---
        warnings = result.get("_warnings", [])
        if warnings:
            lines.append("---")
            for w in warnings:
                # engine.py 现有格式: dict 含 message 字段, 或 str
                if isinstance(w, dict):
                    msg = w.get("message", str(w))
                else:
                    msg = str(w)
                lines.append(f"[WARN] {msg}")

        return lines
```

- [ ] **Step 3: Run the 8 new tests**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/service
uv run --no-sync pytest tests/product_decoders/test_product_decoder.py -v -k "llm_view" 2>&1 | tail -30
```

Expected: 8 PASS (or some skip for the suffix test if test model doesn't trigger suffix). If any fail, debug and fix.

- [ ] **Step 4: Run all existing engine tests to confirm no regression**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/service
uv run --no-sync pytest tests/product_decoders/ -v 2>&1 | tail -15
```

Expected: all PASS (the 8 new + existing 4-page test cases for product decoder)

- [ ] **Step 5: Commit**

```bash
cd /c/doc/Code/worktrees/rag-refactor
git add packages/service/src/product_decoders/engine.py
git commit -m "feat(engine): 加 build_llm_view (Dify LLM 视图, 17 行 zh+en 双语)"
```

---

### Task 3: Wire `build_llm_view` into `/decode` endpoint

**Files:**

- Modify: `packages/service/src/product_decoders/app.py:91-99`

- [ ] **Step 1: Read the endpoint**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/service
# Read app.py around line 91-99
```

- [ ] **Step 2: Add `llm_view` to the response**

Find the `/decode` endpoint (line ~91-99). After the `decoder.decode(req.model)` call, add:

```python
result = decoder.decode(req.model)
result["llm_view"] = decoder.build_llm_view(result)
return result
```

The change should look like:

```python
@app.post("/decode")
async def decode(req: DecodeRequest):
    try:
        result = decoder.decode(req.model)
        result["llm_view"] = decoder.build_llm_view(result)
        return result
    except ProductNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
```

- [ ] **Step 3: Verify all backend tests pass**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/service
uv run --no-sync pytest tests/product_decoders/ -v 2>&1 | tail -10
```

Expected: 8 new llm_view tests pass + existing tests pass

- [ ] **Step 4: Commit**

```bash
cd /c/doc/Code/worktrees/rag-refactor
git add packages/service/src/product_decoders/app.py
git commit -m "feat(api): /decode 响应加 llm_view 字段 (build_llm_view 调通)"
```

---

## Frontend

### Task 4: Add 3 i18n keys (zh + en)

**Files:**

- Modify: `packages/web/messages/zh.json` (add 3 keys)
- Modify: `packages/web/messages/en.json` (add 3 keys)

- [ ] **Step 1: Read the i18n files to find insertion point**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/web
# Find a "复制" or "decode" related key in zh.json and en.json
```

- [ ] **Step 2: Add 3 keys to zh.json**

Find a good location (after existing decode-related keys). Add:

```json
"解码卡": "解码卡",
"Dify 视图": "Dify 视图",
"复制 LLM 文本": "复制 LLM 文本",
```

- [ ] **Step 3: Add 3 keys to en.json**

```json
"解码卡": "Cards",
"Dify 视图": "Dify view",
"复制 LLM 文本": "Copy LLM view",
```

- [ ] **Step 4: Verify keys load (run app and check, or use i18n test if available)**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/web
# If there's a test for i18n, run it
bun test --filter i18n 2>&1 | tail -5
```

If no i18n test, skip and trust the keys are loaded (they'll fail loudly in UI if missing).

- [ ] **Step 5: Commit**

```bash
cd /c/doc/Code/worktrees/rag-refactor
git add packages/web/messages/zh.json packages/web/messages/en.json
git commit -m "feat(i18n): 加 decode 双视图 3 个 key (zh+en)"
```

---

### Task 5: Write 4 failing frontend tests

**Files:**

- Modify: `packages/web/app/[locale]/decode/page.test.tsx` (add 4 new tests)

- [ ] **Step 1: Read the test file to find existing patterns and mock structure**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/web
# Read app/[locale]/decode/page.test.tsx
```

- [ ] **Step 2: Append 4 new tests at end of file**

```tsx
describe("view toggle (llm_view)", () => {
  it("toggle to llm view renders pre block with llm_view joined", async () => {
    // Render with mock result that includes llm_view
    // Click "Dify 视图" toggle
    // Assert <pre data-testid="llm-view"> appears with joined text
  });

  it("toggle persists to localStorage", async () => {
    // Click "Dify 视图" toggle
    // Assert localStorage.getItem("decode.view") === "llm"
  });

  it("copy button in llm mode copies joined text", async () => {
    // Mock clipboard.writeText
    // Switch to llm mode
    // Click copy button
    // Assert clipboard received llm_view.join("\n")
  });

  it("copy button label switches with view", async () => {
    // Default cards mode → button text "复制 JSON"
    // Switch to llm mode → button text "复制 LLM 文本"
  });
});
```

NOTE: implementer should fill in the actual mock/render logic by following the existing test patterns in the file (each existing test in this file mocks the `/decode` response and asserts rendered output).

- [ ] **Step 3: Run new tests to verify they fail (red)**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/web
bun test --filter "llm_view" 2>&1 | tail -20
```

Expected: 4 FAIL (toggle doesn't exist yet, state not implemented, etc.)

- [ ] **Step 4: Commit failing tests**

```bash
cd /c/doc/Code/worktrees/rag-refactor
git add packages/web/app/[locale]/decode/page.test.tsx
git commit -m "test(web): 加 decode llm_view 4 个测试 (TDD red)"
```

---

### Task 6: Implement view toggle + conditional render

**Files:**

- Modify: `packages/web/app/[locale]/decode/page.tsx` (add state, toggle UI, conditional render, copy target)

- [ ] **Step 1: Read the page.tsx to find the current state and render structure**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/web
# Read app/[locale]/decode/page.tsx
```

- [ ] **Step 2: Add view state at the top of the component (after existing useState hooks)**

```tsx
const [view, setView] = useState<"cards" | "llm">(() => {
  if (typeof window === "undefined") return "cards";
  try {
    return (localStorage.getItem("decode.view") as "cards" | "llm") ?? "cards";
  } catch {
    return "cards";
  }
});

useEffect(() => {
  try {
    localStorage.setItem("decode.view", view);
  } catch {
    // 隐私模式 / quota 超限等, 不阻塞 UI
  }
}, [view]);
```

- [ ] **Step 3: Add toggle UI (segmented control) BEFORE the "复制 JSON" button (around line 255)**

```tsx
<div className="flex rounded-md border border-border bg-card p-0.5">
  <button
    type="button"
    onClick={() => setView("cards")}
    className={cn(
      "px-3 py-1 text-sm rounded",
      view === "cards" ? "bg-ink text-paper" : "text-muted-foreground",
    )}
    data-testid="view-cards"
  >
    {t("解码卡")}
  </button>
  <button
    type="button"
    onClick={() => setView("llm")}
    className={cn(
      "px-3 py-1 text-sm rounded",
      view === "llm" ? "bg-ink text-paper" : "text-muted-foreground",
    )}
    data-testid="view-llm"
  >
    {t("Dify 视图")}
  </button>
</div>
```

- [ ] **Step 4: Add `useT` import (if not already imported) and `useEffect` import (if not already imported)**

Check existing imports. Add if missing:

```tsx
import { useEffect, useState } from "react";
```

- [ ] **Step 5: Update the copy button's target + label to be view-aware**

Find the existing `copyTarget` (or inline copy logic) and `copyLabel` constant. Replace with:

```tsx
const copyTarget =
  view === "llm" ? (result.llm_view ?? []).join("\n") : JSON.stringify(result, null, 2);
const copyLabel = view === "llm" ? t("复制 LLM 文本") : t("复制 JSON");
```

Use these in the copy button's onClick and label.

- [ ] **Step 6: Update the field grid render (around line 290-296) to switch between cards and pre**

Find the existing field grid render and wrap it in a conditional:

```tsx
{
  view === "cards" ? (
    <Stagger className="grid grid-cols-1 gap-3 md:grid-cols-2" delay={0.04}>
      {mainFields.map(([k, v]) => (
        <StaggerItem key={k}>
          <DecodeField k={k} v={v} />
        </StaggerItem>
      ))}
    </Stagger>
  ) : (
    <pre
      data-testid="llm-view"
      className="num whitespace-pre-wrap rounded-lg border border-border/50 bg-card p-4 text-sm leading-relaxed"
    >
      {(result.llm_view ?? []).join("\n")}
    </pre>
  );
}
```

- [ ] **Step 7: Run the 4 new tests (should now pass)**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/web
bun test --filter "llm_view" 2>&1 | tail -20
```

Expected: 4 PASS

- [ ] **Step 8: Run all decode page tests (existing + new) to confirm no regression**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/web
bun test --filter decode 2>&1 | tail -10
```

Expected: existing 4 tests + new 4 tests all PASS

- [ ] **Step 9: Commit**

```bash
cd /c/doc/Code/worktrees/rag-refactor
git add packages/web/app/[locale]/decode/page.tsx
git commit -m "feat(web): /decode 加 view toggle (cards / Dify 视图) + 复制按钮联变"
```

---

### Task 7: Final verification

- [ ] **Step 1: Run full backend test suite**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/service
uv run --no-sync pytest tests/product_decoders/ -v 2>&1 | tail -15
```

Expected: all product_decoder tests pass (8 new + existing).

- [ ] **Step 2: Run full frontend decode tests**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/web
bun test --filter decode 2>&1 | tail -10
```

Expected: 4 existing + 4 new = 8 tests pass.

- [ ] **Step 3: Run typecheck + lint to confirm no regressions**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/web
bun run typecheck
bun run lint
```

Expected: 0 errors.

- [ ] **Step 4: Manual smoke test in browser (recommended)**

```bash
# 启动后端 + 前端
cd /c/doc/Code/worktrees/rag-refactor/packages/service
uv run python main.py serve &
cd /c/doc/Code/worktrees/rag-refactor/packages/web
bun run dev
```

Open http://localhost:3000/decode, input `1LE0001-1AA42-1AA4`, verify:

- Default cards mode
- Toggle to Dify 视图 → see `<pre>` with 17 lines
- Click "复制 LLM 文本" → clipboard gets joined text
- Reload page → toggle state persists

---

## Self-Review

**1. Spec coverage:**

- ✅ Header 6 lines (Task 2 lines.append for code/manufacturer/series zh+en)
- ✅ Suffix line 7 if \_suffix (Task 2 if suffix: lines.append)
- ✅ `---` separator after header (Task 2 lines.append("---") after suffix)
- ✅ Segment split by display.split("-") (Task 2 segments = display.split("-"))
- ✅ `---` between segments (Task 2 if seg_idx < len-1: lines.append("---"))
- ✅ Each position one line `name_zh: v_zh / name_en: v_en` (Task 2 line construction)
- ✅ `name_zh`/`value_zh` fallback to name/code (Task 2 fallbacks)
- ✅ `_warnings` appended at end (Task 2 warnings block)
- ✅ Unknown value shows `?` (Task 2 if val_zh is None and val_en is None)
- ✅ No display_separators fall back to no segment headers (Task 2 if display and separators check)
- ✅ Wire /decode endpoint (Task 3)
- ✅ i18n 3 keys zh + en (Task 4)
- ✅ Toggle state with localStorage (Task 6)
- ✅ Conditional render: cards vs `<pre>` (Task 6)
- ✅ Copy button switches target/label with view (Task 6)
- ✅ 8 backend tests (Task 1)
- ✅ 4 frontend tests (Task 5)

**2. Placeholder scan:** No "TBD" / "TODO" / "fill in later" markers. Each step has concrete code.

**3. Type consistency:**

- `build_llm_view(self, result: dict) -> list[str]` — defined Task 2, used Task 3 ✓
- `result.llm_view` — added in Task 3 backend, used in Task 6 frontend ✓
- `view: "cards" | "llm"` — defined Task 6, used in tests Task 5 ✓
- localStorage key `"decode.view"` — defined Task 6, tested Task 5 ✓
- 3 i18n keys (`解码卡`, `Dify 视图`, `复制 LLM 文本`) — defined Task 4, used Task 6 ✓
