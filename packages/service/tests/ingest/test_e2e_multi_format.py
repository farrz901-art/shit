"""混合格式端到端测试

造一个 input_dir 装 .pdf + .md + .dxf + .xyz
跑 process_files，验证产物
"""

import os
import shutil

import pytest

from src.ingest.pdf_processing.pipeline import process_files

SAMPLE_PDF = "tests/fixtures/easy_pdf_test.pdf"  # (2026-06-29) 改用 fixtures 已入库 PDF, 不再依赖 pdfs/ 软链
SAMPLE_DXF = "tests/fixtures/sample.dxf"
SAMPLE_MD = "tests/fixtures/test_doc.md"


@pytest.mark.skipif(
    not os.environ.get("RUN_SLOW_TESTS"),
    reason="端到端慢测试（跑真实 kreuzberg），设 RUN_SLOW_TESTS=1 开启",
)
class TestMultiFormatEndToEnd:
    def test_mixed_input_routes_to_correct_pipelines(self, tmp_path, capsys):
        """混合 PDF + MD + DXF + 未知格式 → 4 桶分流"""
        in_dir = tmp_path / "input"
        in_dir.mkdir()
        shutil.copy(SAMPLE_PDF, in_dir / "doc.pdf")
        shutil.copy(SAMPLE_MD, in_dir / "readme.md")
        shutil.copy(SAMPLE_DXF, in_dir / "drawing.dxf")
        (in_dir / "weird.xyz").write_text("garbage")

        results = process_files(str(in_dir), str(tmp_path / "output"))
        assert results is not None

        # PDF → Document 流水线
        assert results["document"] is not None
        assert any(r["file"] == "doc.pdf" for r in results["document"]["processed"])
        # MD → passthrough
        assert results["passthrough"] is not None
        assert any(r["file"] == "readme.md" for r in results["passthrough"]["processed"])
        # DXF → CAD
        assert results["cad"] is not None
        assert any(r["file"] == "drawing.dxf" for r in results["cad"]["processed"])

        # 未知格式 [WARN]
        captured = capsys.readouterr()
        assert "[WARN]" in captured.out
        assert "weird.xyz" in captured.out

        # 验证子目录布局
        out = tmp_path / "output"
        assert (out / "doc" / "doc.md").exists()
        assert (out / "readme" / "readme.md").exists()
        assert (out / "drawing" / "drawing.md").exists()
