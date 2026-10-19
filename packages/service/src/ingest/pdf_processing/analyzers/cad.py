"""CAD 复杂度分析

跟 PDFAnalyzer 对应：分析 CAD 文件的复杂度，输出 CADInfo。
当前版本只用于诊断展示，后续要路由到不同 converter 时复用 CADInfo.is_simple。
"""

from dataclasses import dataclass, field
from pathlib import Path

import ezdxf

# 含文字的实体类型白名单（与 converters/cad.py._extract_text 保持一致）
TEXT_ENTITY_TYPES = ("TEXT", "MTEXT", "DIMENSION", "LEADER", "TOLERANCE", "ATTRIB")

# 3D 实体（ezdxf drawing 不支持渲染）
THREE_D_ENTITY_TYPES = ("3DSOLID", "REGION", "SURFACE", "BODY", "MESH")

# ezdxf 1.4.4 不支持的实体（解析不动）
UNSUPPORTED_ENTITY_TYPES = ("TABLE",)


@dataclass
class CADInfo:
    """CAD 文件分析结果"""

    file_path: str = ""
    file_format: str = ""  # "DXF" 或 "DWG"
    dxf_version: str = ""  # 例如 "AC1018" (R2018)
    entity_count: int = 0
    text_entity_count: int = 0
    layer_count: int = 0
    layout_count: int = 0
    has_3d_solids: bool = False
    has_tables: bool = False
    is_simple: bool = True
    reasons: list[str] = field(default_factory=list)


class CADAnalyzer:
    """CAD 文件复杂度分析器"""

    def analyze(self, cad_path: str | Path) -> CADInfo:
        """分析单个 CAD 文件"""
        cad_path = Path(cad_path).resolve()
        if not cad_path.exists():
            raise FileNotFoundError(f"CAD 文件不存在: {cad_path}")

        ext = cad_path.suffix.lower()
        if ext not in (".dxf", ".dwg"):
            raise ValueError(f"不支持的 CAD 扩展名: {ext}")

        # 读文件
        if ext == ".dxf":
            doc = ezdxf.readfile(str(cad_path))  # pyright: ignore[reportPrivateImportUsage]  # ezdxf 没在 __all__ 暴露但确实存在
        else:
            # DWG 路径：委托 cad_oda（未装 ODA 会抛友好错误）
            # 重依赖 lazy: ezdxf 启动慢, DWG 处理路径不常见
            from ..converters.cad import read_cad_with_oda  # noqa: E402

            doc = read_cad_with_oda(str(cad_path), audit=True)

        info = CADInfo(
            file_path=str(cad_path),
            file_format=ext.upper().lstrip("."),
            dxf_version=doc.dxfversion,
        )

        msp = doc.modelspace()
        info.entity_count = len(msp)
        info.layer_count = len(list(doc.layers))
        info.layout_count = len(doc.layouts.names())

        # 统计文字实体
        info.text_entity_count = sum(len(msp.query(t)) for t in TEXT_ENTITY_TYPES)

        # 检测 3D 实体
        for t in THREE_D_ENTITY_TYPES:
            if len(msp.query(t)) > 0:
                info.has_3d_solids = True
                break

        # 检测不支持的实体
        for t in UNSUPPORTED_ENTITY_TYPES:
            if len(msp.query(t)) > 0:
                info.has_tables = True
                break

        self._evaluate(info)
        return info

    def analyze_all(self, cad_paths: list[str]) -> dict[str, CADInfo]:
        """批量分析"""
        return {p: self.analyze(p) for p in cad_paths}

    def _evaluate(self, info: CADInfo):
        """评估 CAD 文件是否为简单可处理

        复杂度信号：
        - 含 3D 实体 → 复杂（ezdxf drawing 不支持渲染）
        - 含 TABLE → 复杂（ezdxf 1.4.4 解析不动）
        - layout 数过多 → 复杂（罕见但提示）
        """
        if info.has_3d_solids:
            info.is_simple = False
            info.reasons.append("含 3D 实体，ezdxf drawing 无法渲染")
        if info.has_tables:
            info.is_simple = False
            info.reasons.append("含 TABLE 实体，当前 ezdxf 1.4.4 解析不动")
        if info.layout_count > 5:
            info.is_simple = False
            info.reasons.append(f"layout 数过多: {info.layout_count}个")
