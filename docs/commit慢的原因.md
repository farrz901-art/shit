根据测量数据，以下是完整分析：

---

## `git commit` 慢的原因分析

### 基线对比

|方式|耗时|倍数|
|---|---|---|
|`git commit -n`（跳过 hooks）|**0.14s**|1×|
|`git commit`（完整 hooks）|**27.4s**|**~200×**|

所以慢的不是 git 本身，是 pre-commit 和 commit-msg **hooks**。

---

### 各步骤精确耗时（后端 1 个文件的场景）

|步骤|耗时|瓶颈？|
|---|---|---|
|ruff check --fix|0.15s|✅ 快|
|ruff format|0.14s|✅ 快|
|**pytest --picked**|**0.8~3.2s**|⚠️|
|**pyright**|**4.3~12s**|🔴 **主瓶颈**|
|lint-staged 调度开销|~0.3s|✅|
|commit-msg (grep)|~0.05s|✅|
|**合计**|**~~8~~27s**||

---

### 🔴 根因 1：pyright — 最大的瓶颈（占 70-80% 时间）

```
pyright tests/conftest.py   # 单文件 → 4~12 秒！
```

- pyright 是一个**原生 Windows .exe** (PE 格式 ~46KB)，每次冷启动都要加载并初始化整个类型推断引擎
- 即使只检查 1 个文件，它仍需扫描整个 `PYTHONPATH`、解析所有第三方 stubs（`types-*` 包）、构建符号表
- `.venv/.cache/pyright/` 缓存过期或第一次运行时会**显著更慢**（12-27s），缓存 warm 后加速到 ~4-7s
- 在 Windows 上，`uv run --no-sync` 启动 pyright 比直接 .exe 慢一丁点，但瓶颈在 pyright 本身而非 uv

### ⚠️ 根因 2：pytest --picked — 次瓶颈（占 3-12% 时间）

```
./.venv/Scripts/python.exe -m pytest --picked --tb=short -q
```

- Windows 上 Python 解释器启动很慢，即便 "no tests ran" 也要 **~0.8s** 加载 CPython 运行时
- `pytest --picked` 需要扫描全量文件列表来挑选变更关联的测试，如果在 monorepo 中，这一步骤可能需要在查找后重新计算依赖关系
- 如果涉及测试导入第三方库，启动时间进一步膨胀

### 🔴 根因 3：前后端都在改时会更慢

当前只改了 Python 文件，如果一次 commit 同时改后端和前端：

- **oxlint --fix + --deny-warnings**：~1-3s
- **oxfmt**：~0.5s
- **vitest related --run**：~30-90s（看旧注释说被删过，但又回来了）
- **tsc --noEmit**：~10-30s

此时 commit 可能轻松 **>2 分钟**。

---

### 为什么 warm vs cold 差 3 倍？

|缓存项|cold → warm 加速|
|---|---|
|pyright `.cache`|12s → 4s（3×）|
|pyright 类型 stub 加载|首次需解析所有包|
|pytest import 缓存|.pyc 编译过就快|
|ruff 也有 `.ruff_cache`|影响较小|

---

### 优化建议

**立竿见影（风险低）：**

1. **`git commit --no-verify` 变成 alias**：日常小改跳过 hook
2. **pyright 加缓存持久化**：确保 `.venv/.cache/pyright` 不丢失
3. **pytest --picked 改成有条件触发**：只当实际有测试关联文件改动时才跑（当前 0 个测试也空转 0.8s）

**中等风险：**

4. **增加 pyright 增量模式**：`pyright --watch` 后台驻守，hook 里只查 diff
5. **用预启动 daemon 加速**（看 pyright 是否支持 `--background` / watch 模式）

**高风险（需要改 hook 逻辑）：**

6. **lint-staged 并行化**：将后端、前端、pyright 的步骤异步并发跑（而非串行走 lint-staged）
7. **如果只能改 frontend/pyright 文件，不跑后端的 pytest --picked**

要帮你实施某个优化方案吗？