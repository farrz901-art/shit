"""d81_dummy.pdf 程序生成 (5 页 PDF, 含 1 表格 + 4 关键词段) - mode 2 集成测用

生成 PDF 写入 tests/ingest/fixtures/d81_dummy.pdf, 5 页:
- 第 1 页: 章 1 通用技术指导 (含 "注意" 关键词)
- 第 2 页: 章 1.1 (含 "必须" 关键词)
- 第 3 页: 章 2 1LE1 选型 (含 1 个 4 列 4 行表格 + "不能" 关键词)
- 第 4 页: 章 2.1 (无关键词, 无表格)
- 第 5 页: 章 2.2 (含 "禁止" 关键词)

Windows 上需要 CJK 字体 (默认 Helvetica 不含中文字形, pymupdf insert_text 会渲染成 '·').
"""

from __future__ import annotations

import os
from pathlib import Path

import pymupdf

# Windows 中文字体路径 (兜底: 不存在就用默认 font)
_CJK_FONT_CANDIDATES = [
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/simsun.ttc",
]


def _cjk_font_path() -> str | None:
    """返回第一个存在的 CJK 字体路径, 没有则返 None (用默认 font, 中文字符会变成 '·')."""
    for p in _CJK_FONT_CANDIDATES:
        if os.path.exists(p):
            return p
    return None


def build_d81_dummy(out_path: Path) -> None:
    doc = pymupdf.open()
    font_path = _cjk_font_path()
    # 第 1 页: 章 1 通用技术指导 + "注意"
    p1 = doc.new_page()
    if font_path:
        p1.insert_font(fontname="CJK", fontfile=font_path)
    p1.insert_text(
        (50, 50),
        "第1章 通用技术指导\n\n注意: 本设备在海拔超过 1000 米以上地区使用时, 必须考虑降容运行以确保安全.",
        fontsize=14,
        fontname="CJK" if font_path else "helv",
    )
    # 第 2 页: 章 1.1 + "必须"
    p2 = doc.new_page()
    if font_path:
        p2.insert_font(fontname="CJK", fontfile=font_path)
    p2.insert_text(
        (50, 50),
        "1.1 国际能效等级\n\n依据 IEC 标准, 所有电机必须配置接地端子以满足绝缘要求.",
        fontsize=14,
        fontname="CJK" if font_path else "helv",
    )
    # 第 3 页: 章 2 1LE1 选型 + 1 表格 + "不能"
    p3 = doc.new_page()
    if font_path:
        p3.insert_font(fontname="CJK", fontfile=font_path)
    p3.insert_text((50, 50), "第2章 1LE1 选型", fontsize=14, fontname="CJK" if font_path else "helv")
    p3.insert_text(
        (50, 80),
        "重要提示: 不能将 1LE1 系列电机与 1LA4 系列电机混用在同一控制回路.",
        fontsize=12,
        fontname="CJK" if font_path else "helv",
    )
    # 画 4 列 4 行表格
    table_x = 50
    table_y = 120
    col_w = 100
    row_h = 30
    for row_idx in range(4):
        for col_idx in range(4):
            x = table_x + col_idx * col_w
            y = table_y + row_idx * row_h
            p3.draw_rect(pymupdf.Rect(x, y, x + col_w, y + row_h))
            p3.insert_text(
                (x + 5, y + 18),
                f"R{row_idx}C{col_idx}",
                fontsize=10,
                fontname="CJK" if font_path else "helv",
            )
    # 第 4 页: 章 2.1
    p4 = doc.new_page()
    if font_path:
        p4.insert_font(fontname="CJK", fontfile=font_path)
    p4.insert_text((50, 50), "2.1 选型参数", fontsize=14, fontname="CJK" if font_path else "helv")
    # 第 5 页: 章 2.2 + "禁止"
    p5 = doc.new_page()
    if font_path:
        p5.insert_font(fontname="CJK", fontfile=font_path)
    p5.insert_text(
        (50, 50),
        "2.2 应用限制\n\n严格禁止在海拔 5000 米以上的高原地区使用本型号电机, 以避免绝缘击穿风险.",
        fontsize=14,
        fontname="CJK" if font_path else "helv",
    )
    doc.save(str(out_path))
    doc.close()


if __name__ == "__main__":
    out = Path(__file__).parent / "d81_dummy.pdf"
    build_d81_dummy(out)
    print(f"Generated {out} ({out.stat().st_size} bytes)")
