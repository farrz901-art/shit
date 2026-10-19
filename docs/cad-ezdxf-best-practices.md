# ezdxf 调研沉淀

本项目用 [ezdxf 1.4.4](https://ezdxf.mozman.at/docs/) 实现 DWG/DXF → SVG + markdown。本篇记录调研中的关键发现和踩过的坑。

## 1. 库选型：为什么用 ezdxf

- **MIT 协议**（商用友好）
- 维护活跃（1.4.x 是当前 stable）
- 有完整的 drawing add-on（frontend/backend 解耦，方便换输出格式）
- 有 ODA File Converter 桥接支持 DWG
- 唯一硬伤：DWG 版本天花板 R2018

## 2. DXF vs DWG：API 一致，入口不同

一旦文件被 ezdxf 加载（无论来自 DXF 还是 DWG→DXF 转换），返回的都是同一个 `Drawing` 对象，API 完全一致：

```python
# DXF 路径：原生支持，零依赖
doc = ezdxf.readfile("file.dxf")

# DWG 路径：需要 ODA
from ezdxf.addons import odafc
doc = odafc.readfile("file.dwg", audit=True)
```

**DWG 版本支持矩阵**（ezdxf + ODA File Converter 8.3dll 23.9）：

| DWG 版本 | AC 代码 | 支持 |
|---|---|---|
| R12 - R2018 | AC1009 - AC1032 | ✅ |
| R2019 - R2024 | AC1033+ | ❌ 读不了 |

## 3. ezdxf 1.4.4 不支持的实体（实测）

调研时确认的 **不解析 / 部分解析** 实体：

| 实体 | 状态 | 影响 |
|---|---|---|
| `TABLE` | ❌ 官方 entities 索引**无 TABLE** | 标题栏、明细表丢失 |
| `MULTILEADER` | ⚠️ 1.4.x 解析 partial | 部分引线文字丢失 |
| `ACAD_PROXY_ENTITY` | ⚠️ 需要代理对象支持 | 复杂代理图元丢失 |
| `3DSOLID` / `REGION` / `SURFACE` / `BODY` / `MESH` | ⚠️ drawing 不支持渲染 | 3D 实体不进 SVG |

**本项目对策**：
- `TABLE` / `MULTILEADER` / `ACAD_PROXY_ENTITY`：渲染时用 `filter_func` 跳过（`ezdxf` drawing 遇到会炸）
- 文字提取时用 try/except 包裹，单实体失败不阻塞其他
- TABLE 在 markdown 里打 warning log（"暂不支持解析"）

## 4. ezdxf 1.4.4 实际踩坑

### 4.1 DIMENSION 渲染时 `text_midpoint.z` 是 None

**问题**：在 `Frontend.draw_layout()` 内部展开 DIMENSION 实体时，访问 `self.dxf.text_midpoint.z` 报 `AttributeError: 'NoneType' object has no attribute 'z'`。

**原因**：某些 R2018 DXF 头部没声明 `text_midpoint`，ezdxf 展开虚拟实体时不补默认值。

**解决**：渲染时 `filter_func` 跳过 DIMENSION。文字仍通过 `_extract_text` 进 markdown（用 `get_measurement()` 兜底）。

### 4.2 `Page(0, 0)` 传错

`Page.__init__(width, height, ...)`，width/height 是毫米单位浮点数。传 `(0, 0)` 会被 `get_string()` 当成空 box 拒绝（"empty bounding box"）。

**解决**：先用 `ezdxf.bbox.extents(safe_entities)` 算 layout 的 bbox，再 `Page(w, h)`。其中 `safe_entities` 要排除 DIMENSION（4.1 同款 bug）。

### 4.3 `draw_layout` 不接 `page` 参数

早期写 `Frontend.draw_layout(layout, page=page, finalize=True)` —— 报 `unexpected keyword argument 'page'`。

**解决**：`draw_layout` 只接 layout / finalize / filter_func / layout_properties。`page` 概念属于 backend，传给 `backend.get_string(page)`：

```python
Frontend(ctx, backend).draw_layout(layout, finalize=True)
svg_str = backend.get_string(page)
```

## 5. Backend 选择：SVG vs matplotlib

| Backend | 输出 | 额外依赖 | 推荐 |
|---|---|---|---|
| `SVGBackend` | SVG | **无** | ✅ 本项目用 |
| `MatplotlibBackend` | PNG/PDF/SVG | matplotlib（重） | 临时需要 PNG 时 |
| `PyMuPdfBackend` | PDF/PNG | pymupdf（已依赖） | 临时需要 PDF 时 |
| `PyQtBackend` | 交互式 | PySide6 | 不适合流水线 |

**为什么 SVG**：
- 零额外依赖（不要装 `ezdxf[draw]`，那会拉 matplotlib 整套）
- 矢量图无限缩放、文本可被检索
- 适合 RAG 多模态场景

## 6. 文字提取要点

### 6.1 MTEXT 必用 `plain_text()`

```python
# ❌ 错误：dxf.text 是含格式码的原始字符串
text = entity.dxf.text  # "\\PLine1\\PLine2"

# ✅ 正确：plain_text() 是去格式码的纯文本
text = entity.plain_text()  # "Line1\nLine2"
```

`plain_text(fast=True)` 默认走 fast 模式，对新 CAD 输出准确；旧 CAD 用 `fast=False` 但慢。

### 6.2 DIMENSION 的 text 字段含义

| `dxf.text` 值 | 含义 | 处理 |
|---|---|---|
| `""` 或 `"<>"` | 显示测量值 | 用 `get_measurement()` 兜底 |
| `" "`（一个空格） | 用户显式抑制文字 | 跳过 |
| 其它 | 用户自定义字面量 | 原样保留 |

### 6.3 LEADER 文字在另一实体

LEADER 自身**不含文字**，文字存为另一个 MTEXT 实体，通过 `dxf.annotation_handle` 链接：

```python
leader.dxf.annotation_handle  # 硬引用 handle
target = doc.entitydb[handle]  # 拿到目标 MTEXT
text = target.plain_text()
```

## 7. ODA File Converter 部署

DWG 路径必须装 ODA File Converter：

- **下载**：<https://www.opendesign.com/guestfiles/oda_file_converter>（免费）
- **平台**：Windows / macOS / Linux 全有
- **配置**：`ezdxf.addons.odafc` 通过 `odafc.options` 找 ODA 路径
  - 默认查找系统 PATH
  - 也可显式设 `odafc.options.win_exec_path` / `unix_exec_path`
- **Linux 注意**：ODA File Converter 启动时弹 GUI，需要 `xvfb-run` 抑制

**本项目对策**：[`cad_oda.py`](../src/rag_ingest/cad_oda.py) 封装调用，未装 ODA 时抛 `OdaNotInstalledError` 并指引下载。

## 8. 文档来源

- ezdxf 文档首页：<https://ezdxf.mozman.at/docs/>
- Drawing / Export add-on：<https://ezdxf.mozman.at/docs/addons/drawing.html>
- ODA File Converter add-on：<https://ezdxf.mozman.at/docs/addons/odafc.html>
- DXF Entities 索引：<https://ezdxf.mozman.at/docs/dxfentities/index.html>
- Text 实体：<https://ezdxf.mozman.at/docs/dxfentities/text.html>
- MText 实体：<https://ezdxf.mozman.at/docs/dxfentities/mtext.html>
- Dimension 实体：<https://ezdxf.mozman.at/docs/dxfentities/dimension.html>
- Leader 实体：<https://ezdxf.mozman.at/docs/dxfentities/leader.html>
- Attrib 实体：<https://ezdxf.mozman.at/docs/blocks/attrib.html>
- ODA File Converter 官网：<https://www.opendesign.com/guestfiles/oda_file_converter>
- GitHub 仓库：<https://github.com/mozman/ezdxf>
