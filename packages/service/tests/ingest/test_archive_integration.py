"""process_files 与 ArchiveHandler 集成测试"""

import zipfile
from pathlib import Path

from src.ingest import process_files

SAMPLE_MD = "tests/fixtures/test_doc.md"


class TestProcessFilesArchiveIntegration:
    def test_zip_in_input_extracts_and_routes(self, tmp_path):
        """含 zip 的 input_dir → 自动解压 + 走 4 桶路由"""
        in_dir = tmp_path / "input"
        in_dir.mkdir()
        # 造一个含 .md 的 zip
        zip_path = in_dir / "test.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.write(SAMPLE_MD, "nested_doc.md")

        results = process_files(str(in_dir), str(tmp_path / "output"))
        assert results is not None
        # 解压出的 .md 应被 passthrough 桶处理
        assert results["passthrough"] is not None
        assert any("nested_doc" in p["file"] for p in results["passthrough"]["processed"])

    def test_mixed_zip_and_plain_files(self, tmp_path):
        """input_dir 同时有 zip + 普通 md"""
        in_dir = tmp_path / "input"
        in_dir.mkdir()
        (in_dir / "plain.md").write_text("# plain")

        zip_path = in_dir / "archive.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("inside.md", "# inside")

        results = process_files(str(in_dir), str(tmp_path / "output"))
        assert results is not None
        assert results["passthrough"] is not None
        # 两个 .md 都被处理（一个 plain + 一个解压出的）
        assert len(results["passthrough"]["processed"]) == 2

    def test_unsupported_archive_warns_and_continues(self, tmp_path, caplog):
        """.rar 格式打 WARN 跳过，不阻断其他文件"""
        in_dir = tmp_path / "input"
        in_dir.mkdir()
        (in_dir / "x.rar").write_bytes(b"fake rar")
        (in_dir / "plain.md").write_text("# ok")

        process_files(str(in_dir), str(tmp_path / "output"))
        # loguru 经 PropagateHandler 到 stdlib, caplog 抓 warning 文案
        assert ".rar" in caplog.text

    def test_cleans_temp_after_completion(self, tmp_path):
        """process_files 结束后不会新增 rag_ingest_ 前缀临时目录

        修复前：检查 tempfile.gettempdir() 里所有 rag_ingest_ 前缀目录，依赖系统 tempdir 干净状态
                → flaky（历史进程崩溃残留就会让测试失败）
        修复后：snapshot 跑前已有 rag_ingest_ 集合，跑后再 snapshot，比差集
                → 只关心本次调用是否泄漏，忽略历史残留
        """
        import tempfile

        in_dir = tmp_path / "input"
        in_dir.mkdir()
        (in_dir / "x.md").write_text("# x")

        # 跑前：snapshot 系统 tempdir 里的 rag_ingest_ 前缀目录
        before = {p.resolve() for p in Path(tempfile.gettempdir()).iterdir() if p.name.startswith("rag_ingest_")}

        process_files(str(in_dir), str(tmp_path / "output"))

        # 跑后：再 snapshot，比较差集
        after = {p.resolve() for p in Path(tempfile.gettempdir()).iterdir() if p.name.startswith("rag_ingest_")}
        new_leaks = after - before
        assert new_leaks == set(), f"本次调用泄漏了 temp 目录: {new_leaks}"
