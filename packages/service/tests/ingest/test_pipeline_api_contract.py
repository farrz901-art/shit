"""process_documents / process_cad_files API 契约测试

MEDIUM shim 清理 (2026-06-08):
1. process_documents 不再接受 file_paths=None 静默 glob 兜底
2. process_cad_files 不再接受 str 隐式目录 glob

调用方 process_files 总是传 list 显式文件, 收紧签名无破坏。
跟 [[feedback-no-shim-no-minimal-changes]] 配对。
"""

import pytest

from src.ingest.pdf_processing.pipeline import process_cad_files, process_documents

# ---------------------------------------------------------------------------
# MEDIUM #1: process_documents(file_paths=None) 不再静默 glob
# ---------------------------------------------------------------------------


def test_process_documents_rejects_none_file_paths(tmp_path):
    """file_paths=None 不再静默从 input_dir glob（清掉兜底）"""
    with pytest.raises((TypeError, ValueError)):
        process_documents(file_paths=None, output_dir=str(tmp_path))  # type: ignore[arg-type]  # 故意传 None 测试拒绝


def test_process_documents_with_empty_list_returns_empty_results(tmp_path):
    """传空 list 应直接返回空结果，不再从 input_dir glob"""
    result = process_documents(file_paths=[], output_dir=str(tmp_path))
    assert result == {"processed": [], "errors": []}


# ---------------------------------------------------------------------------
# MEDIUM #2: process_cad_files(file_paths=str) 不再隐式 glob
# ---------------------------------------------------------------------------


def test_process_cad_files_no_longer_glob_str_dir(tmp_path, caplog):
    """file_paths 传 str 不再隐式 glob（Python 不抛 TypeError, 但业务行为变了）

    修复前: str 视作目录路径, 自动 glob *.dxf/*.dwg
    修复后: str 被 list() 当作 iter 取每个字符当 path, 找不到文件就报 CAD 文件不存在
            (无静默 glob, 调用方必须显式传 list[str])
    """
    # 准备一个含 1 个真实 DXF 的目录
    cad_dir = tmp_path / "cad_dir"
    cad_dir.mkdir()
    fake_dxf = cad_dir / "sample.dxf"
    fake_dxf.write_bytes(b"0\n")  # 最小 DXF 文件头, ezdxf 不会真解析成功

    out_dir = tmp_path / "out"
    out_dir.mkdir()

    # 关键: 传 str 目录路径, 修复前会自动 glob 出 sample.dxf
    # 修复后: str 被 list() 拆字符, 找不到这些字符路径的 CAD 文件
    process_cad_files(file_paths=str(cad_dir), output_dir=str(out_dir))  # type: ignore[arg-type]  # 故意传 str 测试拒绝

    # loguru → caplog, 断言文案在 log records 而不是 stdout
    log_text = caplog.text
    # 修复前会看到 "扫描到 1 个 CAD 文件" (glob 出 sample.dxf)
    # 修复后会看到大量 "CAD 文件不存在" 错误 (字符路径找不到)
    assert "扫描到 1 个 CAD 文件" not in log_text, f"传 str 不应再隐式 glob 出 1 个文件, 实际 log: {log_text!r}"
    assert "CAD 文件不存在" in log_text, f"传 str 应按字符路径逐一找不到, 实际 log: {log_text!r}"


def test_process_cad_files_with_empty_list_returns_empty_results(tmp_path):
    """传空 list 应直接返回空结果"""
    result = process_cad_files(file_paths=[], output_dir=str(tmp_path))
    assert result == {"processed": [], "errors": []}
