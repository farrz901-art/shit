# 2026-06-15 Smart App Control 拦截 PyMuPDF / kreuzberg 修复设计

## 背景

启动 RAG 服务时报错：

```
ImportError: DLL load failed while importing _mupdf: 应用程序控制策略已阻止此文件。
ModuleNotFoundError: No module named 'mupdf'
```

错误链路：main.py → src.product_decoders → src.ingest → src.ingest.analyzers.pdf → `import pymupdf` → `_mupdf.pyd` 加载失败 → pymupdf fallback 找 `mupdf` 模块失败。

## 根因

Windows **Smart App Control (SAC)** 在用户机器上处于 eval/enforced 状态，拦截所有"未在 Microsoft 信誉库中登记"的未签名大型 C 扩展 DLL：

| 文件 | 大小 | 签名状态 | SAC 拦截? |
| --- | --- | --- | --- |
| `pymupdf/_mupdf.pyd` | 12 MB | NotSigned | ❌ 拦截 (WinError 4551) |
| `pymupdf/mupdfcpp64.dll` | 25 MB | NotSigned | ✅ 不拦截 |
| `pymupdf/_extra.pyd` | 190 KB | NotSigned | ✅ 不拦截 |
| `kreuzberg/_internal_bindings.pyd` | 同上 | NotSigned | ❌ 拦截 |

`_mupdf.pyd` 和 `_internal_bindings.pyd` 同目录、同作者、同签名状态、但单独被 SAC 标记，说明 SAC 用 hash/heuristic 标识"PyPI 信誉不足"的大型二进制，而非基于签名判断。

注册表证据：

```
HKLM:\SYSTEM\CurrentControlSet\Control\CI\Policy
  VerifiedAndReputablePolicyState = 1  (eval)
  SAC_EnforcementReason           = 1  (强制开启)
  SAC_PreviousState               = 2  (曾 enforced)
```

SAC 一旦强制开启后会拦截所有 PyPI 上的大 C 扩展，**无法靠代码绕过**——所有同类库（pypdfium2、pdfplumber 等含 C 扩展的）都会被同样拦截。

## 目标

让 `uv run py .\main.py` 在用户 Windows 11 开发机上正常启动。零代码改动，零回归风险。

## 实施

### 步骤 1：关闭 Smart App Control（一次性）

- **方法**：GUI 手动
  1. 打开 Windows 设置
  2. 隐私和安全 → Windows 安全 → 应用和浏览器控制
  3. 找到 Smart App Control 设置
  4. 选 "关"
- **权限**：需要本地管理员
- **可逆性**：可在 GUI 中重新开启

### 步骤 2：验证（三步每步必须看到预期输出）

```powershell
# 在 packages/service 目录下

uv run python -c "import pymupdf; print(pymupdf.__version__)"
# 期望: 1.27.2.3

uv run python -c "import kreuzberg; print(kreuzberg.__version__)"
# 期望: 4.9.7

uv run py .\main.py
# 期望: uvicorn 启动监听端口，无 ImportError，无 WinError 4551
```

### 步骤 3：文档化

新建 `docs/dev-environment-setup.md`，包含：

1. **SAC 是什么**：Windows 11 引入的云端应用信誉检查，会拦截未在 Microsoft 信誉库登记的未签名二进制
2. **为什么必须关**：本项目依赖两个 PyPI 上的 C 扩展（pymupdf + kreuzberg），它们都被 SAC 标记为"未验证"
3. **怎么关**：步骤 1 的 GUI 路径
4. **怎么验证**：步骤 2 的三条命令
5. **故障排查**：
   - 如果 import 仍报 4551：检查 `HKLM:\SYSTEM\CurrentControlSet\Control\CI\Policy\VerifiedAndReputablePolicyState` 是否为 0；否则重启
   - 如果管理员权限不足：联系 IT 申请临时管理员或 IT 代关

不在 `docs/dev-environment-setup.md` 中加 SAC 关闭脚本，原因：
- GUI 一次性操作，脚本反而引入复杂度（需要管理员提权逻辑）
- PowerShell `Set-ItemProperty` 修改 `VerifiedAndReputablePolicyState` 不一定生效（SAC 强制 enabled 时）

## 边界（明确不做的）

- ❌ 不替换 pymupdf 为其他库：SAC 拦截所有大 C 扩展，换库不解决问题
- ❌ 不替换 kreuzberg 为其他库：同上
- ❌ 不在代码中加 lazy import / try-except 兜底：违反 `feedback-no-shim-no-minimal-changes`
- ❌ 不写 SAC 关闭脚本：见上
- ❌ 不修改 pyproject.toml 依赖列表：依赖本身正确，问题在系统层

## 影响范围

- **代码**：零改动
- **配置**：零改动
- **文档**：新增 1 个文件 `docs/dev-environment-setup.md`
- **系统**：用户机器 Smart App Control 由 enabled → disabled（一次性，可逆）
- **安全性**：SAC 关闭后，未知 PE 文件不再被预拦截；常规 Windows Defender 防病毒仍生效

## 后续监控

- 拉新机器 / 重装系统时，再次遇到类似 `_mupdf.pyd` 加载失败时，先检查 SAC 状态
- 如果项目未来引入新的 PyPI C 扩展（例如 tokenizers、onnxruntime），同样会被 SAC 拦截，需要在 README 强调

## 验证清单

- [ ] Smart App Control 已关闭（`VerifiedAndReputablePolicyState = 0`）
- [ ] `uv run python -c "import pymupdf"` 无 WinError 4551
- [ ] `uv run python -c "import kreuzberg"` 无 WinError 4551
- [ ] `uv run py .\main.py` 启动 uvicorn 成功
- [ ] `docs/dev-environment-setup.md` 已创建并被 main README 引用