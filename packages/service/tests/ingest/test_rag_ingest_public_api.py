"""smoke test: public API 可从 src.ingest 顶层 import

防止 README 文档化的 import 路径因 __init__.py 漏 re-export 而 ImportError。
"""


def test_process_files_importable():
    from src.ingest import process_files

    assert callable(process_files)


def test_process_documents_importable():
    from src.ingest import process_documents

    assert callable(process_documents)


def test_process_cad_files_importable():
    from src.ingest import process_cad_files

    assert callable(process_cad_files)


def test_process_passthrough_importable():
    from src.ingest import process_passthrough

    assert callable(process_passthrough)
