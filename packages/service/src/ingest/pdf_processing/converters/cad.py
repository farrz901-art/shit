"""CAD 转换器 - DWG/DXF → SVG + markdown

每个 CAD 文件产出一个子目录：
    <cad_output_dir>/<cad_stem>/
    ├── Model.svg            # modelspace 渲染
    ├── Layout1.svg          # paperspace（如有）
    ├── <cad_stem>.md        # 文字流 + SVG 引用
    └── <cad_stem>_entities.json  # 全部文字实体结构化数据

支持的输入：.dxf（原生）、.dwg（需要 ODA File Converter）

ODA File Converter 路径配置 (优先级 高→低):
    1. env var: ODA_WIN_PATH / ODA_UNIX_PATH
    2. config.toml: [cad].oda_win_path / oda_unix_path (兼容旧 config)
    3. defaults.py: DEFAULT_ODA_WIN_PATH = "" (走 ezdxf 系统默认)

机器特定路径(本机装哪)绝不应该进 git, 推荐放 .env。

已知限制：
- DWG 版本天花板 R2018（AC1032）
- TABLE 实体暂不支持（ezdxf 1.4.4 entities 索引无 TABLE）
- MULTILEADER 部分支持（解析 partial，要容错）
- 3D 实体（ACIS）渲不了
- 中文 MTEXT 字体回退需指定 Configuration(font_name=...)
"""

import os
import platform
import re
from dataclasses import dataclass
from pathlib import Path

import ezdxf

# 新版 ezdxf: Frontend / RenderContext 已迁出 drawing/__init__, 改从子模块导入
from ezdxf.addons.drawing.frontend import Frontend  # pyright: ignore[reportPrivateImportUsage]
from ezdxf.addons.drawing.layout import Page
from ezdxf.addons.drawing.properties import RenderContext  # pyright: ignore[reportPrivateImportUsage]
from ezdxf.addons.drawing.svg import SVGBackend
from loguru import logger

from ....common import defaults
from .base import Converter

# ============================================================================
# ODA 相关（从 cad_oda.py 移入）
# ============================================================================


def _read_oda_path_from_env_or_config(key_env: str, key_config: str) -> str:
    """从 env 读 ODA 路径 (ARCH-004: 不再退到 config.toml)

    优先级: env (ODA_WIN_PATH) > defaults ("")
    空字符串 = 让 ezdxf 走系统默认路径

    key_config 参数保留是 API 兼容 (测试用), 业务走 settings.cad_config.
    """
    # env 没设时, 兜底值从 defaults 拿 (避免 os.getenv(..., "") 这种字面量)
    fallback = defaults.DEFAULT_ODA_WIN_PATH if key_env == "ODA_WIN_PATH" else defaults.DEFAULT_ODA_UNIX_PATH
    return os.getenv(key_env, fallback).strip()


def _apply_oda_path_from_config():
    """把 ODA 路径写到 ezdxf.options (供 odafc 读)

    优先级: env (ODA_WIN_PATH/ODA_UNIX_PATH) > config ([cad].oda_*) > defaults ("")
    空 = 保留 ezdxf 默认:
      Windows: C:\\Program Files\\ODA\\ODAFileConverter\\ODAFileConverter.exe
      Linux/macOS: 查系统 PATH (which ODAFileConverter)

    容错: 用户在 env / config 里可能写"目录"(E:\\ODAFileConverter 27.1.0),
    本函数自动识别并补 .exe 后缀。已带可执行后缀的就原样用。

    这是个幂等操作: 重复调用不会出错, 但每次都会重新 set 一次。
    模块导入时自动调一次; 之后用户改 env / config 重新 import 才能生效。
    """
    win_path = _read_oda_path_from_env_or_config("ODA_WIN_PATH", "oda_win_path")
    if win_path:
        resolved = _resolve_oda_exec_path(win_path, platform="win")
        if resolved:
            ezdxf.options.set("odafc-addon", "win_exec_path", resolved)  # pyright: ignore[reportPrivateImportUsage]  # ezdxf.options 是单例, stub 不暴露
    unix_path = _read_oda_path_from_env_or_config("ODA_UNIX_PATH", "oda_unix_path")
    if unix_path:
        resolved = _resolve_oda_exec_path(unix_path, platform="unix")
        if resolved:
            ezdxf.options.set("odafc-addon", "unix_exec_path", resolved)  # pyright: ignore[reportPrivateImportUsage]


def _resolve_oda_exec_path(user_path: str, platform: str) -> str:
    """容错：把用户填的 ODA 路径解析成 ezdxf 期望的"可执行文件绝对路径"

    接受三种写法：
      1. 完整文件路径（已带 .exe / ODAFileConverter）  → 原样返回
      2. 目录路径（不带可执行文件名）                    → 自动拼 ODAFileConverter(.exe)
      3. 路径在磁盘上不存在                             → 仍返回拼好的路径，让 is_installed() 抛 False
                                                        （友好错误是 read_cad_with_oda 负责）

    Args:
        user_path: 从 env / config 读出的原始路径字符串
        platform: "win" / "unix"，决定可执行文件名和后缀
    """
    p = Path(user_path)

    # 已带可执行后缀 / 名字？直接返回
    # Windows: .exe 后缀
    # Linux/macOS: 文件名就是 ODAFileConverter（无后缀）
    if platform == "win":
        # 大小写不敏感匹配 .exe 结尾
        if re.search(r"\.exe$", p.name, re.IGNORECASE):
            return str(p)
        # 目录场景：补 \ODAFileConverter.exe
        return str(p / "ODAFileConverter.exe")
    else:
        # unix 平台：文件名就叫 ODAFileConverter
        if p.name == "ODAFileConverter":
            return str(p)
        return str(p / "ODAFileConverter")


# 模块导入时一次性把 config 里的 ODA 路径写进 ezdxf.options。
_apply_oda_path_from_config()


def read_cad_with_oda(dwg_path: str | Path, audit: bool = True):
    """用 ODA File Converter 把 DWG 转成 DXF，再用 ezdxf 读

    Args:
        dwg_path: .dwg 文件路径
        audit: 是否让 ODA 先审计文件（更安全但更慢）

    Returns:
        ezdxf Drawing 对象

    Raises:
        FileNotFoundError: dwg_path 不存在
        OdaNotInstalledError: ODA File Converter 没装（友好错误信息）
        RuntimeError: ODA 转 DXF 失败
    """
    dwg_path = Path(dwg_path).resolve()
    if not dwg_path.exists():
        raise FileNotFoundError(f"DWG 文件不存在: {dwg_path}")

    # 关键：先检查 ODA 是否装了，没装抛友好错误（不要让 ezdxf 抛 UnsupportedVersion 那种谜语）
    # 重依赖 lazy: ezdxf 启动慢, ODA 检查只在 DWG 路径需要
    from ezdxf.addons import odafc  # noqa: E402

    if not odafc.is_installed():
        raise OdaNotInstalledError(
            "ODA File Converter 未安装，无法读取 DWG 文件。\n"
            f"  要读的 DWG: {dwg_path}\n"
            f"  当前系统: {platform.system()}\n"
            "  下载地址: https://www.opendesign.com/guestfiles/oda_file_converter\n"
            "  安装后把 ODAFileConverter.exe (Windows) 或 ODAFileConverter (macOS/Linux) "
            "所在路径写进 config.toml [cad].oda_win_path / oda_unix_path，或加到系统 PATH。\n"
            "  注意：ezdxf + ODA 组合只支持 DWG R2018 及更早版本（AC1032 及以下），"
            "AutoCAD 2019+ 出的 DWG 读不了。"
        )

    try:
        return odafc.readfile(str(dwg_path), audit=audit)
    except Exception as e:
        raise RuntimeError(
            f"ODA 转 DXF 失败: {dwg_path}\n"
            f"  原始错误: {type(e).__name__}: {e}\n"
            "  可能原因：DWG 版本过新（>R2018）、文件损坏、ODA 配置错误。"
        ) from e


class OdaNotInstalledError(RuntimeError):
    """ODA File Converter 未安装时抛"""

    pass


# ============================================================================
# EzdxfConverter
# ============================================================================


@dataclass
class CadConvertResult:
    """单文件转换结果"""

    svg_files: list[str]  # 渲染出的 SVG 绝对路径列表
    markdown_path: str  # 落盘的 .md 绝对路径
    content: str  # markdown 文本（跟 markdown_path 内容一致）


class EzdxfConverter(Converter):
    """ezdxf 转换器 - DWG/DXF → SVG + markdown

    用法:
        converter = EzdxfConverter()
        result = converter.convert("drawing.dxf", "./out")
    """

    name: str = "ezdxf"
    extensions = [".dxf", ".dwg"]

    @staticmethod
    def can_handle(info) -> bool:
        """不分析 PDFInfo（ezdxf 走自己的解析逻辑），任意 info 都接受"""
        return True

    def __init__(self, audit_dwg: bool = True):
        """初始化

        Args:
            audit_dwg: 读 DWG 时是否先让 ODA 审计（更安全但更慢）。
                       DXF 路径忽略此参数。
        """
        self.audit_dwg = audit_dwg

    def convert(  # pyright: ignore[reportIncompatibleMethodOverride]  # CAD 走自己的参数命名 (cad_path/output_dir) + dict 返回 (含 svg_files)
        self, cad_path: str | Path, output_dir: str | Path
    ) -> dict:
        """转换单个 CAD 文件

        Args:
            cad_path:  .dxf 或 .dwg 文件绝对/相对路径
            output_dir: 输出根目录（会在其下创建 <stem>/ 子目录）

        Returns:
            dict 含 svg_files / markdown_path / content

        Raises:
            FileNotFoundError: cad_path 不存在
            ValueError: 扩展名不是 .dwg/.dxf
        """
        cad_path = Path(cad_path).resolve()
        if not cad_path.exists():
            raise FileNotFoundError(f"CAD 文件不存在: {cad_path}")

        ext = cad_path.suffix.lower()
        if ext not in (".dxf", ".dwg"):
            raise ValueError(f"不支持的 CAD 扩展名: {ext}（只支持 .dxf / .dwg）")

        output_dir = Path(output_dir).resolve()
        # 模仿 KreuzbergConverter 行为：自动建 output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        # 每个 CAD 文件一个子目录
        stem = cad_path.stem
        work_dir = output_dir / stem
        work_dir.mkdir(parents=True, exist_ok=True)

        # 1. 读
        doc = self._read(cad_path, ext)

        # 2. 渲染 SVG
        svg_files = self._render_svgs(doc, work_dir, stem)

        # 3. 提取文字 + 生成 markdown
        text_records = self._extract_text(doc)
        content = self._text_to_markdown(text_records, doc, svg_files, cad_path)

        # 4. 落盘 markdown
        md_path = work_dir / f"{stem}.md"
        md_path.write_text(content, encoding="utf-8")

        return {
            "svg_files": [str(p) for p in svg_files],
            "markdown_path": str(md_path),
            "content": content,
        }

    def _read(self, cad_path: Path, ext: str):
        """读 CAD 文件。.dwg 走 ODA 转换，.dxf 走原生 ezdxf。"""
        if ext == ".dxf":
            return ezdxf.readfile(str(cad_path))  # pyright: ignore[reportPrivateImportUsage]  # ezdxf 没在 __all__ 暴露但确实存在
        # DWG 路径：先调 ODA 转 DXF 再读
        return read_cad_with_oda(str(cad_path), audit=self.audit_dwg)

    def _render_svgs(self, doc, work_dir: Path, stem: str) -> list[Path]:
        """按 layout 渲染 SVG 矢量图

        已知 ezdxf 1.4.4 bug：某些 R2018 DIMENSION 在 frontend 内部展开时会
        访问 self.dxf.text_midpoint.z 而该属性为 None，导致 AttributeError。
        解决：渲染时用 filter_func 跳过 DIMENSION，文字仍通过 _extract_text 进 markdown。
        """
        svg_paths: list[Path] = []

        # 跳过 ezdxf 1.4.4 渲染时有 bug 的实体类型
        SKIP_ON_RENDER = {"DIMENSION", "MULTILEADER", "ACAD_PROXY_ENTITY"}

        def _filter(entity):
            return entity.dxftype() not in SKIP_ON_RENDER

        for layout_name in doc.layouts.names():
            layout = doc.layouts.get(layout_name)
            ctx = RenderContext(doc)
            backend = SVGBackend()
            try:
                # paperspace 用 page from layout；modelspace 自己算 bbox
                if layout_name == "Model":
                    page = self._page_from_modelspace(layout)
                else:
                    page = Page.from_dxf_layout(layout)
                Frontend(ctx, backend).draw_layout(layout, finalize=True, filter_func=_filter)
                svg_str = backend.get_string(page)
            except Exception as e:
                # 单个 layout 渲染失败不阻塞其他
                logger.warning("布局 {} 渲染失败: {}", layout_name, e)
                continue

            svg_file = work_dir / f"{stem}_{layout_name}.svg"
            svg_file.write_text(svg_str, encoding="utf-8")
            svg_paths.append(svg_file)

        return svg_paths

    def _page_from_modelspace(self, layout):
        """给 modelspace 构造一个 Page：用安全实体的 bbox 算尺寸"""
        # 算 bbox 时跳过 DIMENSION（它的 text_midpoint.z 在 ezdxf 1.4.4 有 bug）
        safe_entities = list(layout.query("LINE TEXT MTEXT CIRCLE ARC LWPOLYLINE POLYLINE"))
        if safe_entities:
            # ezdxf 拆 bbox 模块 (旧版) → ezdxf.bbox (新版), 但新版需用 boundingbox
            # 重依赖 lazy: ezdxf.bbox 仅在 safe_entities 命中时需要
            from ezdxf.bbox import extents  # noqa: E402

            bbox = extents(safe_entities)
            w = bbox.size.x if bbox.size.x > 0 else 100
            h = bbox.size.y if bbox.size.y > 0 else 100
        else:
            w, h = 100, 100
        return Page(w, h)

    def _extract_text(self, doc) -> list[dict]:
        """遍历所有 layout 提取含文字的实体

        返回的每条记录: {layout, layer, type, text, insert_xy, handle, tag?}
        - text: 解析后的纯文本（MTEXT 已去格式码，DIMENSION 兜底用 measurement）
        - insert_xy: (x, y) 插入点（OCS/WCS 视具体实体）
        - handle: DXF handle，调试用
        - tag: 仅 ATTRIB 有
        """
        records: list[dict] = []
        for layout_name in doc.layouts.names():
            layout = doc.layouts.get(layout_name)
            for entity in layout:
                t = entity.dxftype()
                try:
                    if t == "TEXT":
                        records.append(self._record_text(entity, layout_name, t))
                    elif t == "MTEXT":
                        records.append(self._record_mtext(entity, layout_name, t))
                    elif t == "DIMENSION":
                        rec = self._record_dimension(entity, layout_name, t)
                        if rec:
                            records.append(rec)
                    elif t == "LEADER":
                        rec = self._record_leader(entity, layout_name, t, doc)
                        if rec:
                            records.append(rec)
                    elif t == "TOLERANCE":
                        records.append(self._record_tolerance(entity, layout_name, t))
                    elif t == "INSERT":
                        records.extend(self._record_insert_attribs(entity, layout_name))
                    elif t == "TABLE":
                        # ezdxf 1.4.4 不支持 TABLE 实体解析，跳过但记日志
                        logger.warning("TABLE 实体暂不支持解析（layout={}）", layout_name)
                except Exception as e:
                    logger.warning("{} 实体提取失败: {}", t, e)
        return records

    def _record_text(self, entity, layout_name: str, t: str) -> dict:
        return {
            "layout": layout_name,
            "layer": entity.dxf.layer,
            "type": t,
            "text": entity.plain_text(),
            "insert_xy": self._xy(entity.dxf.insert),
            "handle": entity.dxf.handle,
        }

    def _record_mtext(self, entity, layout_name: str, t: str) -> dict:
        return {
            "layout": layout_name,
            "layer": entity.dxf.layer,
            "type": t,
            "text": entity.plain_text(),
            "insert_xy": self._xy(entity.dxf.insert),
            "handle": entity.dxf.handle,
        }

    def _record_dimension(self, entity, layout_name: str, t: str):
        text = entity.dxf.text
        if text in ("", "<>"):
            # 兜底用测量值
            try:
                text = f"{entity.get_measurement():.3f}"
            except Exception:
                text = "<unmeasurable>"
        elif text == " ":
            # 用户显式抑制了文字
            return None
        return {
            "layout": layout_name,
            "layer": entity.dxf.layer,
            "type": t,
            "text": text,
            "insert_xy": self._xy(entity.dxf.insert),
            "handle": entity.dxf.handle,
        }

    def _record_leader(self, entity, layout_name: str, t: str, doc):
        # LEADER 文字存在 annotation_handle 指向的实体里
        handle = getattr(entity.dxf, "annotation_handle", None)
        if not handle or handle not in doc.entitydb:
            return None
        target = doc.entitydb[handle]
        if target.dxftype() != "MTEXT":
            return None
        return {
            "layout": layout_name,
            "layer": entity.dxf.layer,
            "type": t,
            "text": target.plain_text(),
            "insert_xy": self._xy(entity.dxf.insert),
            "handle": entity.dxf.handle,
        }

    def _record_tolerance(self, entity, layout_name: str, t: str) -> dict:
        return {
            "layout": layout_name,
            "layer": entity.dxf.layer,
            "type": t,
            "text": entity.dxf.text,
            "insert_xy": self._xy(entity.dxf.insert),
            "handle": entity.dxf.handle,
        }

    def _record_insert_attribs(self, entity, layout_name: str) -> list[dict]:
        recs = []
        try:
            attribs = list(entity.attribs)
        except Exception:
            return recs
        for a in attribs:
            try:
                recs.append(
                    {
                        "layout": layout_name,
                        "layer": a.dxf.layer,
                        "type": "ATTRIB",
                        "text": a.dxf.text,
                        "insert_xy": self._xy(entity.dxf.insert),
                        "handle": a.dxf.handle,
                        "tag": a.dxf.tag,
                    }
                )
            except Exception as e:
                logger.warning("ATTRIB 提取失败: {}", e)
        return recs

    def _xy(self, point) -> tuple[float, float]:
        """从 Vec3/Vec2 提取 (x, y)，缺失则返回 (0.0, 0.0)"""
        if point is None:
            return (0.0, 0.0)
        try:
            return (float(point[0]), float(point[1]))
        except Exception:
            return (0.0, 0.0)

    def _text_to_markdown(
        self,
        records: list[dict],
        doc,
        svg_files: list[Path],
        cad_path: Path,
    ) -> str:
        """生成 markdown：标题 + 渲染图 + 按图层分组的文字"""
        stem = cad_path.stem
        layer_count = len(list(doc.layers))
        dxf_version = doc.dxfversion

        lines: list[str] = [f"# {stem}", ""]
        # 元信息
        ext = cad_path.suffix.upper().lstrip(".")
        lines.append(
            f"> 来源：{cad_path.name} | 格式：{ext} | DXF 版本：{dxf_version} | 图层：{layer_count} | 文字实体：{len(records)}"
        )
        lines.append("")

        # 渲染图引用
        if svg_files:
            lines.append("## 渲染图")
            lines.append("")
            for svg in svg_files:
                # 用相对路径（相对于 markdown 所在目录）
                rel = svg.name
                lines.append(f"![{svg.stem}]({rel})")
            lines.append("")

        # 按图层分组
        by_layer: dict[str, list[dict]] = {}
        for r in records:
            by_layer.setdefault(r["layer"], []).append(r)

        if by_layer:
            lines.append("## 文字内容（按图层分组）")
            lines.append("")
            for layer_name in sorted(by_layer):
                lines.append(f"### 图层：{layer_name}")
                lines.append("")
                for r in by_layer[layer_name]:
                    coord = f"({r['insert_xy'][0]:.2f}, {r['insert_xy'][1]:.2f})"
                    tag_part = f" `{r['tag']}`" if "tag" in r else ""
                    lines.append(f"- **{r['type']}**{tag_part} `{coord}`: {r['text']}")
                lines.append("")

        return "\n".join(lines)
