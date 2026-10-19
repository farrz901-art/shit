# 解码页双视图 + Dify LLM 视图

**日期**: 2026-06-12
**状态**: 设计已批准, 待实施
**作者**: Claude (brainstorming with user)

## Context

`/decode` 页现在只展示"卡片网格"形式 (code / zh / en / raw 各一卡). 用户希望:

1. 页面上加一个 toggle 按钮切 2 种形式
2. 新形式是 **bilingual 文本行** (机座号:100mm 机座 / Frame size:100mm frame)
3. 后端一次返回 2 种数据结构 (现有 flat dict + 新 `llm_view`)
4. **新形式同时给 Dify LLM 读** — Dify prompt 节点直接 `{{decode.llm_view | join('\n')}}` 拼到上下文

**Why**: Dify 工作流下一步要把"型号解码"作为上下文塞给 LLM, 让 LLM 推理用户问的电机参数. 现有 flat dict 塞进 prompt 对 LLM 不友好 (一堆 `"frame_size_zh"` key 名噪声); 文本行 LLM 一眼读懂, 也方便 page 渲染.

## 目标

- 1 个后端接口 (`/decode`) 一次返回 2 种 view: **现有 flat dict (不变) + 新 `llm_view: list[str]`**
- 1 个 page (现有 `/decode`) 加 segmented control toggle, 切 cards / llm 两视图
- 1 个文本视图同时服务 Dify (机器读) + 人看 (UI 切到此模式展示 `<pre>` 块)
- 现有 flat dict schema **零破坏**, 现有 4 个 page.test.tsx 用例不需改

## 非目标

- 不重做现有 cards 视图 UI
- 不引入 Dify SDK / 调 Dify API (本期只产出 Dify 可消费的格式, 不联调)
- 不做 llm_view 格式的"配置化" (e.g. 用户选"只 zh 不要 en" / "按 group 头 vs 按 position 头") — 本期一种格式定死
- 不在 llm_view 里加超出 YAML 字段的"派生信息" (e.g. 不算"frame_size >= 100 算大机座" 之类的 LLM-friendly 摘要) — 只原样翻

## 数据形状

### 新增字段 (在 `/decode` 响应顶层, 现有字段一字不动)

```json
{
  // ... 现有 flat dict 全部保留 ...
  "llm_view": [
    "完整型号: 1LE0001-1AA42-1AA4",
    "Full order code: 1LE0001-1AA42-1AA4",
    "厂商: Siemens",
    "Manufacturer: Siemens",
    "系列: 西门子低压系列三相异步电动机",
    "Series: Siemens 1LE0 Low-voltage Motor Series",
    "---",
    "[段 1LE0001] 型号前缀: 1LE000 / Series prefix: 1LE000",
    "[段 1LE0001] 能效等级: 高效电动机, 中国能效等级 3 级 / High Efficiency, China Energy Efficiency Grade 3",
    "---",
    "[段 1AA42] 机座号: 100mm 机座 / Frame size: 100mm frame",
    "[段 1AA42] 极数: 2 极 / Number of poles: 2 poles",
    "[段 1AA42] 机座长度: 长机座 / Frame length: long",
    "---",
    "[段 1AA4] 安装方式: IM B3 卧式底脚安装 / IM B3",
    "[段 1AA4] 绕组保护: 无绕组保护 / without winding protection",
    "[段 1AA4] 接线盒位置: 置顶 / on top"
  ]
}
```

### 关键规则

| #   | 规则                                                                                        | 示例                                                                 |
| --- | ------------------------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| 1   | 头部 6 行永远存在: 完整型号 (zh+en) + 厂商 (zh+en) + 系列 (zh+en)                           | 顺序固定                                                             |
| 2   | `result._suffix` 非空时头部第 7 行加 `后缀: <suffix>` (zh 单语, 不出 en)                    | 例: `后缀: Z F40`                                                    |
| 3   | `---` 分隔: 头部后一个 + 段与段之间各一个                                                   | 1LE0 = 3 段 → 头部后 1 个 + 段间 2 个 = 3 个 `---`                   |
| 4   | 段头 `[段 <display_segment>]` 来自 `result.display.split('-')`                              | `1LE0001-1AA42-1AA4` → `["1LE0001", "1AA42", "1AA4"]`                |
| 4a  | position 分配到段: 用 cfg `decoder.positions` 的累计 cursor 落在段字符范围内                | `prefix` cursor=0 落段 `1LE0001`; `frame_size` cursor=7 落段 `1AA42` |
| 5   | 每 position 一行, 格式 `<name_zh>: <value_zh> / <name_en>: <value_en>`                      | `机座号: 100mm 机座 / Frame size: 100mm frame`                       |
| 6   | `name_zh` 缺失 → `name`; `value_zh` 缺失 → `result[pos_name]` (code 优先, 跟 decode() 一致) | 例: 某 position `name_zh`/`name_en` 都缺 → `name: code / name: code` |
| 7   | `_warnings` 非空时尾部追加 `---` + 每条一行 `[WARN] <message>` 走原文 (engine.py 当前格式)  | 原文: `值 '99' 不在已知编码表中`                                     |
| 8   | 未知值 value 双语都显示 `?` (不暴露 raw 码); 同一 position 在 `_warnings` 里有对应条目      | `[段 1AA4] 电压: ? / Voltage: ?` + `[WARN] 值 '99' 不在已知编码表中` |

### 段划分: 复用 `display_separators`

段字符用 `result.display` (engine.py:format_display 算出) 切 `-` 取段.

**降级**: 如果 YAML 没有 `display_separators` 也没 `position.group`, llm_view 退化为"无段头"模式, 所有 position 排在一个 `---` 后不带 `[段 X]` 头, 仅 `---` 分隔. 跟现有 format_display 的优先级一致 (避免引擎出现两条降级路径).

## 实施

### 后端 (Python)

**文件**: `packages/service/src/product_decoders/engine.py`

新增方法:

```python
def build_llm_view(self, result: dict) -> list[str]:
    """从 decode() 返回的 dict 构 llm_view.

    假设 result 是本 decoder 刚 decode() 出来的 (有 _suffix / _warnings / display).
    不修改 result (纯函数, 不污染调用方 dict).
    """
```

`/decode` endpoint 改 (packages/service/src/product_decoders/app.py:91-99):

```python
@app.post("/decode")
async def decode(req: DecodeRequest):
    try:
        result = decoder.decode(req.model)
        result["llm_view"] = decoder.build_llm_view(result)
        return result
    ...
```

### 测试 (TDD)

**后端** `packages/service/tests/product_decoders/test_product_decoder.py` 新增:

| Test                                              | 验什么                                                             |
| ------------------------------------------------- | ------------------------------------------------------------------ |
| `test_llm_view_header_has_6_lines_then_separator` | 头部 6 行 + 一个 `---`                                             |
| `test_llm_view_segments_split_by_display`         | 1LE0 16 字符 → 3 个 `[段 ...]` 头 (1LE0001 / 1AA42 / 1AA4)         |
| `test_llm_view_position_line_zh_en_pair`          | 至少 1 个 position 渲染成 `name_zh: v_zh / name_en: v_en`          |
| `test_llm_view_warning_block_appended`            | 解码未知码 → 末尾 `[WARN] ...` 行, 数量 = `_warnings` 长度         |
| `test_llm_view_unknown_value_shows_question_mark` | 未知码 value 双语 `?`                                              |
| `test_llm_view_no_display_separators_falls_back`  | mock 缺 display_separators 的 cfg → 仍产 llm_view, 不带段头 (不抛) |
| `test_llm_view_suffix_line_appended_to_header`    | `_suffix = "Z F40"` 时头部第 7 行 `后缀: Z F40`                    |
| `test_llm_view_does_not_mutate_input`             | 调完 `result["llm_view"]` 前后, 原 dict 其他 key 数量不变          |

**前端** `packages/web/app/[locale]/decode/page.test.tsx` 新增:

| Test                                              | 验什么                                                                   |
| ------------------------------------------------- | ------------------------------------------------------------------------ |
| `test_toggle_to_llm_view_renders_pre_block`       | mock 返回 `llm_view: ["a", "b"]`, 点 toggle → 出现 `<pre>` 含 `a\nb`     |
| `test_toggle_persists_to_localStorage`            | 切 llm → localStorage["decode.view"] = "llm"                             |
| `test_copy_button_in_llm_mode_copies_joined_text` | mock clipboard.writeText, 在 llm 模式点复制 → 收到 `llm_view.join("\n")` |
| `test_copy_button_label_switches_with_view`       | 卡片模式文本"复制 JSON" / llm 模式文本"复制 LLM 文本" (zh)               |

### 前端 (React)

**文件**: `packages/web/app/[locale]/decode/page.tsx`

新增:

```tsx
const [view, setView] = useState<"cards" | "llm">(() => {
  if (typeof window === "undefined") return "cards";
  return (localStorage.getItem("decode.view") as "cards" | "llm") ?? "cards";
});

useEffect(() => {
  localStorage.setItem("decode.view", view);
}, [view]);
```

头部 (line 255 区域) 加 segmented control (在 `复制 JSON` 按钮**左边**):

```tsx
<div className="flex rounded-md border border-border bg-card p-0.5">
  <button
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

字段网格区域 (line 290-296) 改为:

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

复制按钮 (line 255-286) 行为联变:

```tsx
const copyTarget =
  view === "llm" ? (result.llm_view ?? []).join("\n") : JSON.stringify(result, null, 2);
const copyLabel = view === "llm" ? t("复制 LLM 文本") : t("复制 JSON");
// onClick 用 copyTarget, 按钮文字用 copyLabel
```

**i18n key 加** (zh.json + en.json):

| zh              | en              |
| --------------- | --------------- |
| `Dify 视图`     | `Dify view`     |
| `解码卡`        | `Cards`         |
| `复制 LLM 文本` | `Copy LLM view` |

跟现有 `[WARN]` 这种技术性 label 不入 i18n 的做法保持一致, 警告行直接硬编码中文字符串在 backend.

## 错误处理矩阵

| 场景                                     | 表现                                                                      |
| ---------------------------------------- | ------------------------------------------------------------------------- |
| `result["llm_view"]` 不存在 (旧版本后端) | 前端 `(result.llm_view ?? []).join("\n")` → 空字符串 + `<pre>` 空块, 不崩 |
| `_warnings` 为空 / 不存在                | 不出 `[WARN]` 段, 不出尾部 `---`                                          |
| `_suffix` 为空 / 不存在                  | 不出 `后缀:` 行                                                           |
| `result.display` 缺 (走降级)             | 段头空, 行按 position 顺序排, 单 `---` 分隔                               |
| YAML 缺 `name_zh` / `name_en`            | engine.py 现有 decode() 已有 fallback 行为, build_llm_view 复用同样       |
| localStorage 不可用 (隐私模式)           | `try/catch` 包 setItem, 失败不阻塞 UI                                     |

## 安全 / 兼容

- **API 向后兼容**: `llm_view` 是新增字段, 现有字段 (含 `frame_size` / `_zh` / `_en` / `_raw` / `_suffix` / `_warnings`) 一字不动. 现有前端 / Dify workflow / E2E 测试都不会破
- **不写入 llm_view 之外的新字段** (e.g. 不加 `_llm_prompt_template` 等推测性字段)
- **不引入新依赖**

## 风险

| 风险                                                         | 缓解                                                                                                                                |
| ------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------- |
| YAML 字段缺 (e.g. 没 `name_en`) → 双语行残缺                 | name 缺失回退到 cfg `name` (英文 id), value 缺失回退到 `result[pos_name]` (code 优先, 跟 decode() engine.py:133 一致), 测试覆盖     |
| 段字符 vs position 顺序错位 (段内 position 乱)               | 按 `result._positions_ordered` 不存在, 用 cfg `decoder.positions` 顺序遍历, 跟 `result.display` 段切**独立**两路径, 段内按 cfg 顺序 |
| `display` 段切与 position 数量不匹配 (e.g. 段多 position 少) | 段遍历按 position 分配, 段内可能 0 个 position → 该段 `[段 X]` 头不出现 (避免空段)                                                  |
| Dify prompt 节点对换行敏感 (e.g. 表格解析)                   | llm_view 全用普通 `\n` 换行, 不混 `\r\n`; 测试断言 join 用 `\n`                                                                     |
| localStorage SSR 报错                                        | 初始 state 用 `typeof window === "undefined"` 守卫                                                                                  |
| toggle 切换丢失用户已复制的内容                              | 复制按钮有反馈动画 (现有 "已复制" 1.5s), 切视图不重置 result                                                                        |

## 验收

- [ ] `bun run test --filter decode` 全过 (现有 + 新 4 个前端用例)
- [ ] `uv run pytest packages/service/tests/product_decoders/test_product_decoder.py -v` 全过 (现有 + 新 8 个后端用例)
- [ ] 浏览器手动: 输入 `1LE0001-1AA42-1AA4` → 默认 cards 模式 → 切 Dify 视图 → 看到 17 行 (6 header + 1 sep + 1 seg1 head + 2 seg1 pos + 1 sep + 1 seg2 head + 3 seg2 pos + 1 sep + 1 seg3 head + 3 seg3 pos) 共 17 行
- [ ] 切 Dify 视图后点 "复制 LLM 文本" → 剪贴板拿到 join('\n') 的全文
- [ ] 切回 cards 模式 → "复制 JSON" 行为不变
- [ ] reload 页面 → 保留上次 view 选择 (localStorage)
- [ ] 未知码型号 (e.g. `1LE0001-1AA4-99-AA4`) → 切 Dify 视图 → 看到电压位 `?` + 末尾 `[WARN] 值 '99' 不在已知编码表中` (跟 engine.py:150 当前 message 原文一致)
- [ ] 不破现有 Dify 工作流 (Dify 现调 `/decode` 取字段不变, 多了 `llm_view` 字段不影响)
