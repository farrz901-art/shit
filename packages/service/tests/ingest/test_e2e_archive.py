"""压缩包端到端测试（gated by RUN_SLOW_TESTS=1）"""

import os
import shutil

import pytest

from src.ingest import process_files

SAMPLE_ARCHIVE = "tests/fixtures/sample_archive.zip"


@pytest.mark.skipif(
    not os.path.exists(SAMPLE_ARCHIVE),
    reason=f"fixture 不存在: {SAMPLE_ARCHIVE}",
)
@pytest.mark.skipif(
    not os.environ.get("RUN_SLOW_TESTS"),
    reason="需要 RUN_SLOW_TESTS=1 才跑慢测试",
)
class TestE2EArchive:
    def test_e2e_zip_with_md_files(self, tmp_path):
        """真实 zip → 真跑 process_files → 断言输出结构"""
        in_dir = tmp_path / "input"
        in_dir.mkdir()
        shutil.copy(SAMPLE_ARCHIVE, in_dir / "archive.zip")

        results = process_files(str(in_dir), str(tmp_path / "output"))
        assert results is not None
        # 两个 .md 都在 passthrough 桶
        assert results["passthrough"] is not None
        files = [p["file"] for p in results["passthrough"]["processed"]]
        assert "README.md" in files
        assert "notes.md" in files

        # 验证输出落盘
        assert (tmp_path / "output" / "README" / "README.md").exists()
        assert (tmp_path / "output" / "notes" / "notes.md").exists()
