# CAD 转 markdown 使用文档

本项目 RAG 流水线第一阶段支持把 CAD 文件（DWG/DXF）转成 markdown，附带 SVG 矢量图作为视觉上下文。

## 快速开始

```bash
# 1. 把 CAD 文件放到输入目录
# 默认从 config.toml [paths].input_dir 读
cp my_drawing.dxf pdf-test/

# 2. 跑主入口
python main.py
# 自动按扩展名分流：.pdf 走 PDF 流水线，.dxf/.dwg 走 CAD 流水线

# 3. 看产物
ls pdf-test/output/cad/my_drawing/
#   Model.svg           # modelspace 渲染图
#   Layout1.svg         # paperspace（如有）
#   my_drawing.md       # 文字流 + SVG 引用
```

> 💡 其它格式（.png / .docx / .html / .eml 等）走 Document 流水线，由 kreuzberg / mineru 处理。详见 [README.md](../../README.md)。

## 目录结构

每个 CAD 文件在 output_dir 下产出一个子目录：

```
<output_dir>/
└── <cad_stem>/
    ├── <cad_stem>_Model.svg        # modelspace 渲染
    ├── <cad_stem>_Layout1.svg      # paperspace（每个 layout 一张）
    ├── <cad_stem>.md               # 文字 + SVG 引用 + 图层分组
    └── <cad_stem>_entities.json    # 全部文字实体结构化数据
```

## markdown 输出样例

```markdown
# my_drawing

> 来源：my_drawing.dxf | 格式：DXF | DXF 版本：AC1032 | 图层：12 | 文字实体：47

## 渲染图

![my_drawing_Model](my_drawing_Model.svg)

## 文字内容（按图层分组）

### 图层：0
- **TEXT** `(10.00, 20.00)`: 标题文字
- **MTEXT** `(50.00, 30.00)`: 多行
文字内容
- **DIMENSION** `(0.00, 0.00)`: 100.000

### 图层：DIMENSIONS
- **DIMENSION** `(123.45, 67.89)`: 30.000
- **DIMENSION** `(456.78, 90.12)`: 45.000

### 图层：TITLE_BLOCK
- **ATTRIB** `DRAWING_NO` `(50.00, 0.00)`: DWG-001
- **ATTRIB** `DESIGNER` `(80.00, 0.00)`: 李工
```

## 已知限制

### 1. DWG 版本天花板 R2018

ezdxf + ODA File Converter 只支持 DWG R2018（AC1032）及更早版本。**AutoCAD 2019+ 出的 DWG 读不了**，会直接报错。

**对策**：
- 用户的 CAD 软件能导出 DXF 的话用 DXF（更省事）
- 必须用 DWG 的，确保出图软件版本 ≤ AutoCAD 2018

### 2. DWG 需要 ODA File Converter

DWG 是 Autodesk 的二进制格式，ezdxf 不直接读。需要装 ODA File Converter（[opendesign.com](https://www.opendesign.com/guestfiles/oda_file_converter) 免费下载，80MB+ GUI 程序）。

**安装**：
- Windows：装完后 ODAFileConverter.exe 在 `C:\Program Files\ODA\ODAFileConverter\`（或自定义路径）
- macOS/Linux：装完后把 ODAFileConverter 加到 PATH，或写到 `config.toml` 的 `[cad].oda_path`

**Linux 额外注意**：ODA File Converter 启动弹 GUI，要装 `xvfb` 抑制：
```bash
sudo apt install xvfb
xvfb-run -a ODAFileConverter ...
```

未装 ODA 时，本项目会抛 `OdaNotInstalledError` 并指引下载，不会让 ezdxf 抛谜语般的 `UnsupportedVersion`。

### 3. TABLE 实体不支持

ezdxf 1.4.4 官方 entities 索引**没有 TABLE**。CAD 图里的标题栏、明细表如果是 TABLE 做的，会丢失表格内容。

**当前对策**：`EzdxfConverter` 遇到 TABLE 打 warning log 跳过，不阻塞其他实体。后续扩展可以：自己用 ezdxf 解析组码（DXF group codes 100/70/...),或者上 OCR。

### 4. MULTILEADER 部分支持

ezdxf 1.4.x 之前对 MULTILEADER 解析是 partial。本项目渲染时用 `filter_func` 跳过 MULTILEADER（避免 frontend 炸），文字提取时容错。

### 5. 3D 实体渲不了

`ezdxf.addons.drawing` 只投影到 xy 平面，3D 实体（`3DSOLID` / `REGION` / `SURFACE` / `BODY` / `MESH`）不进 SVG。`CADAnalyzer` 会把这类文件标为"复杂"。

### 6. 中文 MTEXT 字体回退

如果系统没装 DXF 里指定的字体，中文 MTEXT 渲出来是豆腐块。

**临时解决**：在 `EzdxfConverter` 里指定字体：
```python
from ezdxf.addons.drawing.properties import Configuration, LayoutProperties
config = Configuration(
    default_layout_properties=LayoutProperties(font_name="SimSun")
)
```

（当前版本未实现此配置入口，需要时改 `cad_converter.py` 的 `_render_svgs` 方法。）

### 7. 文字与几何分离

markdown 是文字流，视觉信息只在 SVG 里。下游 RAG 切片时要知道：
- 文字按图层分组，**位置坐标 `(x, y)` 保留**但与 SVG 不直接对应
- 想要图文关联检索，需要用多模态 embedding（文本 + SVG 截图一起 encode）

## 调试技巧

### 跑通但 SVG 是空的

1. 检查 DXF 是不是 R2018 之前的版本：`ezdxf.readfile` 不抛错但 layout 是空的
2. 检查 layout 是不是只有 paperspace：modelspace 没东西但 `Layout1` 有
3. 跑 `python -c "import ezdxf; doc = ezdxf.readfile('xxx.dxf'); print([(n, len(list(doc.layouts.get(n)))) for n in doc.layouts.names()])"` 看每个 layout 的实体数

### 中文乱码

1. 看 SVG 里 `<text>` 标签的 `font-family`
2. 浏览器装对应字体（SimSun / SimHei / 思源黑体等）
3. 或在代码里 `Configuration(font_name=...)` 强制字体

### DWG 报 "Unknown or unsupported DWG version"

1. 先看 DWG 是哪版：ODA File Converter GUI 打开文件 → 标题栏会显示
2. 如果 > R2018，唯一办法是源文件转 DXF
3. 如果 ≤ R2018 还报这个错，可能是 ODA 没装好 / PATH 找不到

## 内部 API

如果要在自己的脚本里用：

```python
from src.rag_ingest.cad_converter import EzdxfConverter

converter = EzdxfConverter()
result = converter.convert("drawing.dxf", "./out")
# result = {
#     "svg_files": ["/abs/path/to/drawing_Model.svg"],
#     "markdown_path": "/abs/path/to/drawing/drawing.md",
#     "content": "# drawing\n\n> ...",
# }
```

```python
from src.rag_ingest.cad_analyzer import CADAnalyzer

analyzer = CADAnalyzer()
info = analyzer.analyze("drawing.dxf")
# info.entity_count, info.text_entity_count, info.is_simple, info.reasons
```

```python
from src.rag_ingest.cad_oda import read_cad_with_oda, OdaNotInstalledError

try:
    doc = read_cad_with_oda("drawing.dwg", audit=True)
except OdaNotInstalledError as e:
    print(f"请装 ODA: {e}")
```

## 参考

- [cad-ezdxf-best-practices.md](cad-ezdxf-best-practices.md) —— ezdxf 调研沉淀（API 踩坑记录）
- [mineru-output-for-rag.md](mineru-output-for-rag.md) —— PDF 流水线产物取舍（参考设计风格）
