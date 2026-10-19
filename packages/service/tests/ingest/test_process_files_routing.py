"""process_files 路由测试 + passthrough / documents 子流程测试"""

import shutil

from src.ingest.pdf_processing.pipeline import process_files, process_passthrough

SAMPLE_PDF = "tests/fixtures/easy_pdf_test.pdf"
SAMPLE_DXF = "tests/fixtures/sample.dxf"
SAMPLE_MD = "tests/fixtures/test_doc.md"


class TestProcessPassthrough:
    """process_passthrough 行为测试"""

    def test_passthrough_copies_md_files(self, tmp_path):
        """传 2 个 .md 路径 → 都被复制到 <output>/<stem>/<stem>.md"""
        src_dir = tmp_path / "input"
        src_dir.mkdir()
        shutil.copy(SAMPLE_MD, src_dir / "doc1.md")
        shutil.copy(SAMPLE_MD, src_dir / "doc2.md")

        result = process_passthrough(
            [str(src_dir / "doc1.md"), str(src_dir / "doc2.md")],
            str(tmp_path / "output"),
        )

        assert len(result["processed"]) == 2
        assert (tmp_path / "output" / "doc1" / "doc1.md").exists()
        assert (tmp_path / "output" / "doc2" / "doc2.md").exists()

    def test_passthrough_empty_returns_empty(self, tmp_path):
        """空列表 → 返回空结构，不报错"""
        result = process_passthrough([], str(tmp_path / "output"))
        assert result == {"processed": [], "errors": []}


class TestProcessFilesRouting:
    """process_files 4 桶路由"""

    def test_routes_pdf_to_document_pipeline(self, tmp_path):
        """.pdf 走 Document 流水线"""
        in_dir = tmp_path / "input"
        in_dir.mkdir()
        shutil.copy(SAMPLE_PDF, in_dir / "test.pdf")

        results = process_files(str(in_dir), str(tmp_path / "output"))
        assert results is not None
        assert results["document"] is not None
        assert len(results["document"]["processed"]) == 1
        # 输出在子目录
        assert (tmp_path / "output" / "test" / "test.md").exists()

    def test_routes_dxf_to_cad_pipeline(self, tmp_path):
        """.dxf 走 CAD 流水线"""
        in_dir = tmp_path / "input"
        in_dir.mkdir()
        shutil.copy(SAMPLE_DXF, in_dir / "drawing.dxf")

        results = process_files(str(in_dir), str(tmp_path / "output"))
        assert results is not None
        assert results["cad"] is not None
        assert len(results["cad"]["processed"]) == 1
        assert (tmp_path / "output" / "drawing" / "drawing.md").exists()

    def test_routes_md_to_passthrough(self, tmp_path):
        """.md 走 passthrough 流水线"""
        in_dir = tmp_path / "input"
        in_dir.mkdir()
        shutil.copy(SAMPLE_MD, in_dir / "doc.md")

        results = process_files(str(in_dir), str(tmp_path / "output"))
        assert results is not None
        assert results["passthrough"] is not None
        assert len(results["passthrough"]["processed"]) == 1
        assert (tmp_path / "output" / "doc" / "doc.md").exists()

    def test_warns_unknown_format(self, tmp_path, caplog):
        """未支持格式打 WARN 跳过 (loguru → caplog)"""
        in_dir = tmp_path / "input"
        in_dir.mkdir()
        (in_dir / "weird.xyz").write_text("garbage")

        process_files(str(in_dir), str(tmp_path / "output"))
        assert "weird.xyz" in caplog.text

    def test_recursive_scan(self, tmp_path):
        """递归扫子目录"""
        in_dir = tmp_path / "input"
        in_dir.mkdir()
        sub = in_dir / "subdir"
        sub.mkdir()
        shutil.copy(SAMPLE_PDF, sub / "nested.pdf")

        results = process_files(str(in_dir), str(tmp_path / "output"))
        assert results is not None
        # 嵌套文件被处理
        assert results["document"] is not None
        assert len(results["document"]["processed"]) == 1
        assert (tmp_path / "output" / "nested" / "nested.md").exists()
