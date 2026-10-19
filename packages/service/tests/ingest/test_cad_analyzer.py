"""CAD 分析器单元测试"""

from pathlib import Path

from src.ingest.pdf_processing.analyzers.cad import CADAnalyzer, CADInfo

SAMPLE_DXF = "tests/fixtures/sample.dxf"


class TestCADInfo:
    """CADInfo 数据类测试"""

    def test_default_values(self):
        info = CADInfo()
        assert info.file_path == ""
        assert info.file_format == ""
        assert info.dxf_version == ""
        assert info.entity_count == 0
        assert info.text_entity_count == 0
        assert info.layer_count == 0
        assert info.layout_count == 0
        assert info.has_3d_solids is False
        assert info.has_tables is False
        assert info.is_simple is True
        assert info.reasons == []


class TestCADAnalyzer:
    """CADAnalyzer 真跑 fixture 的端到端测试"""

    def setup_method(self):
        self.analyzer = CADAnalyzer()

    def test_analyze_returns_cad_info(self):
        info = self.analyzer.analyze(SAMPLE_DXF)
        assert isinstance(info, CADInfo)
        # file_path 内部 resolve 成绝对路径，比较文件名 + 父目录名
        p = Path(info.file_path)
        assert p.name == Path(SAMPLE_DXF).name
        assert p.parent.name == Path(SAMPLE_DXF).parent.name
        assert info.file_format == "DXF"
        assert info.dxf_version != ""
        assert info.entity_count >= 1
        assert info.text_entity_count >= 1
        assert info.layer_count >= 1
        assert info.layout_count >= 1

    def test_analyze_counts_text_entities_correctly(self):
        """fixture 里有 1 TEXT + 1 MTEXT + 1 DIMENSION，text_entity_count 应为 3"""
        info = self.analyzer.analyze(SAMPLE_DXF)
        assert info.text_entity_count == 3, f"应有 3 个文字实体（TEXT+MTEXT+DIMENSION），实际 {info.text_entity_count}"

    def test_analyze_simple_dxf_is_simple(self):
        """fixture 是简单 DXF，is_simple=True 且 reasons 为空"""
        info = self.analyzer.analyze(SAMPLE_DXF)
        assert info.is_simple is True
        assert info.reasons == []
