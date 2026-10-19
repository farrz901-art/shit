---
name: feedback-check-pyproject-deps-match-actual-imports
description: 实施完成时必须核对 pyproject.toml dependencies 跟实际 import 匹配，避免幽灵依赖
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 5d26cefb-915c-4256-aa9f-e0d5a5f59c02
---

**问题**：14-task PR 实施完 master 合并后，发现 `cad_converter.py` 直接 `import ezdxf`，但 `pyproject.toml` 的 `dependencies` 列表**没**声明 `ezdxf`——ezdxf 是"幽灵依赖"（venv 里装着但 `uv tree` 看不到 Required-by）。

**踩坑时间**：2026-06-02，14-task PR 合并后用户质疑
**影响**：新环境 `uv sync` 不会装 ezdxf，git clone 后 `import ezdxf` 会 ImportError
**根因**：
- spec 写"改 pyproject.toml 加 ezdxf>=1.4.4"
- 实施时 14 task 全部跑完（14 个 commit），但**没**改 pyproject.toml
- ezdxf 之前 venv 里装着（可能是早期 `uv pip install ezdxf` 装的）
- 实施阶段的 80 测试 + 后续 109 测试都过，因为 venv 缓存没清

**正确做法（DRY check）**：
1. 实施完成后必须跑：扫描所有 `src/` 下的 import 跟 `pyproject.toml` dependencies 列表对比
2. 实现脚本（一次性）：
   ```bash
   # 提取 src/ 下的所有 third-party imports
   grep -rh "^import \|^from " src/ | grep -v "from \." | sort -u
   # 对比 pyproject.toml dependencies
   ```
3. spec 里有"改 pyproject.toml"的任务，**不能**漏
4. final code review 不该把"pyproject.toml 未动"标成 ✅（实际应该动）

**Why**：依赖管理的核心是**声明**——pyproject.toml 是"项目需要什么"的单一真相源。幽灵依赖在 dev 环境跑得通，但部署到 CI / 同事 clone / Docker 镜像时会全炸。

**How to apply**：
- 任何"包重命名 / 新 converter / 新功能"实施完成后，最后一步必须是**依赖对齐 check**
- 实施任务的 plan 里如果有"改 pyproject.toml"步骤，要 verify 真正改到了
- 提 PR 前跑 `uv sync --reinstall` 在干净环境验证
- final code review 应该 cross-check "所有 import 都对应 pyproject.toml 里 declared dep"

**关联**：
- 跟 [[feedback-record-errors-and-lessons]] 同源——犯错必记录
- 跟 [[feedback-verify-with-import-not-pip]] 互补——pip 看不到幽灵依赖，import 配合 `uv tree` 才能查
