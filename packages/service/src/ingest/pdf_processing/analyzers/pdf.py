"""PDF 复杂度分析"""

from dataclasses import dataclass, field

import pymupdf


@dataclass
class PDFInfo:
    """PDF信息"""

    page_count: int = 0
    has_images: bool = False
    has_text: bool = False
    image_count: int = 0
    drawing_count: int = 0
    table_like_pages: int = 0
    is_simple: bool = True
    reasons: list[str] = field(default_factory=list)


class PDFAnalyzer:
    """PDF复杂度分析器"""

    def analyze(self, pdf_path: str) -> PDFInfo:
        """分析单个PDF复杂度"""
        doc = pymupdf.open(pdf_path)
        info = PDFInfo(page_count=len(doc))

        for page in doc:
            text: str = page.get_text()  # type: ignore[assignment]  # pymupdf 返 str, pyright 看不到
            if text.strip():
                info.has_text = True
            images = page.get_images()
            if images:
                info.has_images = True
                info.image_count += len(images)
            drawings = page.get_drawings()
            if drawings:
                info.drawing_count += len(drawings)
            if self._is_table_page(drawings):
                info.table_like_pages += 1

        self._evaluate(info)
        doc.close()
        return info

    def analyze_all(self, pdf_paths: list[str]) -> dict[str, PDFInfo]:
        """批量分析多个PDF，返回 {pdf_path: PDFInfo}"""
        return {path: self.analyze(path) for path in pdf_paths}

    def classify(self, infos: dict[str, PDFInfo]) -> tuple[list[str], list[str]]:
        """将PDF分类为简单和复杂两组"""
        simple, complex_ = [], []
        for path, info in infos.items():
            (simple if info.is_simple else complex_).append(path)
        return simple, complex_

    def _is_table_page(self, drawings: list) -> bool:
        if not drawings or len(drawings) < 20:
            return False
        h_lines = sum(1 for d in drawings if d.get("rect") and d["rect"].height < 5)
        v_lines = sum(1 for d in drawings if d.get("rect") and d["rect"].width < 5)
        return h_lines > 10 and v_lines > 10

    def _evaluate(self, info: PDFInfo):
        """评估PDF是否为简单PDF"""
        if not info.has_text:
            info.is_simple = False
            info.reasons.append("无文字内容（扫描件或图片型PDF）")
        elif info.table_like_pages > 0:
            info.is_simple = False
            info.reasons.append(f"含表格页面: {info.table_like_pages}页")
        elif info.drawing_count > 100:
            info.is_simple = False
            info.reasons.append(f"矢量图形过多: {info.drawing_count}个")
        elif info.image_count > 10:
            info.is_simple = False
            info.reasons.append(f"图片过多: {info.image_count}张")


def analyze_pdf_complexity(pdf_path: str) -> PDFInfo:
    """便捷函数：分析单个PDF复杂度"""
    return PDFAnalyzer().analyze(pdf_path)
