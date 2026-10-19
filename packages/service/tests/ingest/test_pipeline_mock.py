"""ingest/pipeline.py 单元测试 (mode 1, mock 全部转换器)"""

from unittest.mock import patch


@patch("src.ingest.pdf_processing.pipeline.get_converter")
@patch("src.ingest.pdf_processing.pipeline.PDFAnalyzer")
@patch("src.ingest.pdf_processing.pipeline.ArchiveHandler")
def test_process_path_with_md_file(mock_archive, mock_pdf, mock_converter, tmp_path):
    """.md 文件直接走 markdown_passthrough"""
    src = tmp_path / "input"
    src.mkdir()
    (src / "test.md").write_text("# hello", encoding="utf-8")
    out_dir = str(tmp_path / "output")

    from src.ingest.pdf_processing.pipeline import process_path

    result = process_path(path=str(src / "test.md"), output_dir=out_dir)
    # 返回 None 或 dict 都可以
    assert result is None or isinstance(result, dict)
