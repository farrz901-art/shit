---
name: project-rag-shim-audit-2026-06-08
description: "RAG 项目当前 shim 代码清单 (5 HIGH + 6 MEDIUM) —— 改这些位置前先按 [[feedback-no-shim-no-minimal-changes]] 清理"
metadata: 
  node_type: memory
  type: project
  originSessionId: 15ad1bed-e505-4a41-9d65-4ac51a5a15c0
---

# RAG 项目 shim 审计清单 (2026-06-08)

审计触发: 用户 2026-06-08 升级 no-shim 原则为硬规则, 要求自查项目内 shim.

---

## HIGH (5) —— 应该清理

### 1. `process_pdfs()` 旧 API 包装
- 位置: `src/rag/ingest/pipeline.py:231-244`
- 形态: 注释"兼容旧 API", 函数体只调 `process_documents`
- 清理: 直接删函数, 让调用方改用 `process_documents`

### 2. `classify_pdfs()` 旧 API 包装
- 位置: `src/rag/ingest/converters/__init__.py:18-20`
- 形态: docstring "保留旧 API, 向后兼容", 函数体只调 `classify_files`
- 清理: 删函数

### 3. `process_pdfs` / `classify_pdfs` 在包入口被当公共 API 导出
- 位置: `src/rag/ingest/__init__.py:17, 26, 32`
- 形态: `__all__` 含 `"process_pdfs"` 标注 "兼容包装"
- 清理: 跟 1+2 一起删, `__all__` 同步清

### 4. 顶包 `rag/__init__.py` 同步导出旧 API
- 位置: `src/rag/__init__.py:17, 19, 73, 74`
- 形态: `from .ingest import (... process_pdfs, ... classify_pdfs, ...)`
- 清理: 跟 1+2+3 一起删, 外部依赖面归零

### 5. `_read_file_with_fallback` 跨文件重复实现
- 位置 A: `src/rag/common/prompt_loader.py:32-38`
- 位置 B: `src/rag/common/document_loader.py:42-50`
- 形态: 完全相同的编码回退循环 (utf-8/gbk/gb2312/latin-1)
- 清理: 抽到 `src/rag/common/text_io.py` 公共函数, 删两处副本

---

## MEDIUM (6) —— 需判断, 倾向清

### 6. `process_documents` `file_paths=None` 静默退化成从 input_dir glob PDF
- 位置: `src/rag/ingest/pipeline.py:144, 153-155`
- 形态: 注释 "兼容旧调用", `file_paths is None` → 自动 glob
- 判断: 单元入口 `process_files` 总是显式传 `file_paths`, 这条兜底只服务旧调用方
- 清理建议: 删兜底, 强制传参

### 7. `process_cad_files` 接受 `str` 自动 glob
- 位置: `src/rag/ingest/pipeline.py:259, 267-273`
- 形态: docstring "传 str 视作目录 (兼容旧 API)"
- 判断: 单个 dxf 文件 vs 目录的 str 歧义, 当前调用方都传 list
- 清理建议: 删 str 隐式转换, 类型签名收紧到 `list[str] | None`

### 8. `get_cad_config()` 段缺失静默返回空字符串
- 位置: `src/rag/ingest/config.py:72-89`
- 形态: docstring "兼容早期只有 [paths] 段的 config.toml"
- 判断: 对照 `get_paths()` 段缺失直接 raise KeyError, 这里不一致
- 清理建议: 跟 `get_paths()` 对齐, 段缺失 raise

### 9. `get_archive_config()` 段缺失用魔法默认值
- 位置: `src/rag/ingest/config.py:92-110`
- 形态: `max_total_size=1 << 30`, `max_file_count=10_000` 硬编码兜底
- 判断: 未来改 zip-bomb 阈值时用户感知不到
- 清理建议: 段缺失 raise, 或至少 INFO 日志

### 10. `_read_oda_path_from_env_or_config()` `except (FileNotFoundError, KeyError)` 兜底吃所有配置错
- 位置: `src/rag/ingest/converters/cad.py:46-66`
- 形态: 注释 "兼容旧 config", `except (FileNotFoundError, KeyError): return ""`
- 判断: 吃掉了 config.toml 语法错等多种错
- 清理建议: 让配置错透传, 不要静默兜底

### 11. `classify_files` `getattr(conv, "skip_can_handle", False)` 旁路特性
- 位置: `src/rag/ingest/converters/__init__.py:40-45`
- 形态: 通过属性偷塞行为, 只 `EzdxfConverter` 标了 True
- 判断: 不是基类抽象, 是 CAD 一个子类的旁路
- 清理建议: 在基类 `Converter` 加抽象 `can_handle` 默认实现或 `priority` 字段

---

## 不算 shim (LOW) —— 已确认必要, 保留

- llama-index 节点/响应 duck typing (`document_loader`, `chunker`, `query_engine` 多处 hasattr)
- 第三方可选依赖 (tqdm) `try/except ImportError` (batch_utils.py:48-50)
- 第三方属性可能不存在 (`getattr(entity.dxf, "annotation_handle", None)` cad.py:398)
- DIMENSION 测量值兜底 (cad.py:381-383)
- mineru 容器输出路径兜底查找 (mineru.py:199-206)
- langfuse/psycopg2 客户端方法的 None 守卫

---

**Why:** 跟 [[feedback-no-shim-no-minimal-changes]] 配对, 这次升级为硬规则后, 需要一份"具体哪里是 shim"的可定位清单, 才能彻底清完.

**How to apply:**
- 改上述文件前, 先按条目把 shim 删了
- 删完跑 `pytest tests/` 确认无回归
- 全部清完后, 这条 project memory 可以废弃
