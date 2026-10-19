"""pipeline.py 单元测试 — process_path 的 output_dir kwarg"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from src.ingest.pdf_processing import pipeline


def test_process_path_forwards_output_dir_to_process_files(tmp_path: Path):
    """process_path(path, output_dir=...) → process_files(input_dir=path, output_dir=output_dir)"""
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.pdf").write_bytes(b"%PDF-1.4 fake")

    target = tmp_path / "custom_output"
    with patch.object(
        pipeline, "process_files", return_value={"document": None, "cad": None, "passthrough": None}
    ) as m:
        pipeline.process_path(str(src), output_dir=str(target))

    m.assert_called_once_with(input_dir=str(src), output_dir=str(target))


def test_process_path_no_output_dir_uses_none(tmp_path: Path):
    """不传 output_dir → process_files(input_dir=path) (config fallback)"""
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.pdf").write_bytes(b"%PDF-1.4 fake")

    with patch.object(
        pipeline, "process_files", return_value={"document": None, "cad": None, "passthrough": None}
    ) as m:
        pipeline.process_path(str(src))

    m.assert_called_once_with(input_dir=str(src))


def test_process_single_file_forwards_output_dir(tmp_path: Path):
    """单文件路径也支持 output_dir"""
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    target = tmp_path / "custom_output"

    with patch.object(pipeline, "process_documents", return_value={"processed": [], "errors": []}) as m:
        pipeline.process_path(str(pdf), output_dir=str(target))

    m.assert_called_once_with([str(pdf)], str(target))
