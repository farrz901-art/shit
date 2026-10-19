"""process_path 顶层入口测试

ingest 单文件支持 (2026-06-08):
- process_path 是单文件 / 单目录 / None 三路分发的入口
- 行为：单文件按扩展名路由到现有 process_documents/cad/passthrough
"""

from unittest.mock import patch


class TestProcessPathNone:
    """path=None → 走 config 默认目录"""

    def test_none_delegates_to_process_files_no_args(self):
        """path=None 时 process_path 调 process_files(output_dir=None) (output_dir 默认 None 透传)"""
        from src.ingest.pdf_processing.pipeline import process_path

        with patch("src.ingest.pdf_processing.pipeline.process_files") as mock_pf:
            process_path(None)
            mock_pf.assert_called_once_with(output_dir=None)

    def test_none_returns_process_files_result(self):
        """path=None 时返回值是 process_files 的返回值"""
        from src.ingest.pdf_processing.pipeline import process_path

        sentinel = {"document": [], "cad": [], "passthrough": []}
        with patch("src.ingest.pdf_processing.pipeline.process_files", return_value=sentinel):
            result = process_path(None)
            assert result is sentinel


class TestProcessPathDirectory:
    """path=目录 → 调 process_files(input_dir=...)"""

    def test_directory_delegates_to_process_files_with_input_dir(self, tmp_path):
        """目录路径 → process_files(input_dir=str(dir))"""
        from src.ingest.pdf_processing.pipeline import process_path

        with patch("src.ingest.pdf_processing.pipeline.process_files") as mock_pf:
            process_path(str(tmp_path))
            mock_pf.assert_called_once_with(input_dir=str(tmp_path))

    def test_zip_file_delegates_to_process_files_with_input_dir(self, tmp_path):
        """zip 文件路径 → 透传给 process_files(input_dir=...)（让 zip 解压逻辑接管）"""
        from src.ingest.pdf_processing.pipeline import process_path

        zip_path = tmp_path / "bundle.zip"
        zip_path.write_bytes(b"PK\x05\x06" + b"\x00" * 18)  # 最小 zip EOCD
        with patch("src.ingest.pdf_processing.pipeline.process_files") as mock_pf:
            process_path(str(zip_path))
            mock_pf.assert_called_once_with(input_dir=str(zip_path))


class TestProcessPathSingleFile:
    """path=单文件 → 按扩展名路由到对应 list[str] 入口"""

    def test_pdf_routes_to_process_documents(self, tmp_path):
        """.pdf → process_documents([file])"""
        from src.ingest.pdf_processing.pipeline import process_path

        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"%PDF-1.4\n")
        with patch("src.ingest.pdf_processing.pipeline.process_documents") as mock_pd:
            process_path(str(pdf))
            mock_pd.assert_called_once()
            args, _ = mock_pd.call_args
            assert args[0] == [str(pdf)]

    def test_dxf_routes_to_process_cad_files(self, tmp_path):
        """.dxf → process_cad_files([file])"""
        from src.ingest.pdf_processing.pipeline import process_path

        dxf = tmp_path / "drawing.dxf"
        dxf.write_bytes(b"0\n")
        with patch("src.ingest.pdf_processing.pipeline.process_cad_files") as mock_pc:
            process_path(str(dxf))
            mock_pc.assert_called_once()
            args, _ = mock_pc.call_args
            assert args[0] == [str(dxf)]

    def test_dwg_routes_to_process_cad_files(self, tmp_path):
        """.dwg → process_cad_files([file])（跟 .dxf 同路由）"""
        from src.ingest.pdf_processing.pipeline import process_path

        dwg = tmp_path / "drawing.dwg"
        dwg.write_bytes(b"AC1032\x00")
        with patch("src.ingest.pdf_processing.pipeline.process_cad_files") as mock_pc:
            process_path(str(dwg))
            mock_pc.assert_called_once()
            args, _ = mock_pc.call_args
            assert args[0] == [str(dwg)]

    def test_md_routes_to_process_passthrough(self, tmp_path):
        """.md → process_passthrough([file])"""
        from src.ingest.pdf_processing.pipeline import process_path

        md = tmp_path / "readme.md"
        md.write_text("# Title\n", encoding="utf-8")
        with patch("src.ingest.pdf_processing.pipeline.process_passthrough") as mock_pp:
            process_path(str(md))
            mock_pp.assert_called_once()
            args, _ = mock_pp.call_args
            assert args[0] == [str(md)]


class TestProcessPathErrors:
    """错误路径"""

    def test_missing_path_prints_error_returns_none(self, caplog):
        """不存在路径 → loguru WARN + 返回 None（跟 process_files 行为对齐）"""
        from src.ingest.pdf_processing.pipeline import process_path

        result = process_path("/nonexistent/path/to/file.pdf")
        assert result is None
        assert "路径不存在" in caplog.text

    def test_unknown_extension_prints_warning_returns_empty(self, tmp_path, caplog):
        """.xyz → loguru WARN 跳过，返回空 dict"""
        from src.ingest.pdf_processing.pipeline import process_path

        weird = tmp_path / "thing.xyz"
        weird.write_bytes(b"\x00")
        result = process_path(str(weird))
        assert "不支持的文件格式" in caplog.text
        assert ".xyz" in caplog.text
        assert result == {"document": [], "cad": [], "passthrough": []}
