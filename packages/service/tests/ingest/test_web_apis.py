"""Web 后端 API 契约测试 (ARCH-004: 改 mock settings.paths)"""

import pytest
from fastapi.testclient import TestClient

from src.config.settings import Paths, settings
from src.core.app_factory import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    """把 output_dir 临时改成 tmp_path, 创建干净 app.

    (2026-07-08) conftest.py 全局 mock get_object_store → MagicMock, 让 _backend_name() 返 mock
    而不是 'local', handler 走 minio 分支读空 S3. 这里强制换成真 LocalFSObjectStore, 让
    _backend_name() 返 'local', handler 走 tmp_path 本地 FS 路径.

    注意: output_api 是 `from src.storage.object_store import get_object_store`, 本地有绑定,
    只 patch 模块属性不够, 必须 patch 导入方模块的本地符号.
    """
    from src.storage.object_store import LocalFSObjectStore

    fake_store = LocalFSObjectStore(local_root=tmp_path)
    monkeypatch.setattr(settings, "paths", Paths(input_dir=tmp_path, output_dir=tmp_path))
    # patch 导入方 (output_api) 的本地符号, 不是源模块属性
    monkeypatch.setattr(
        "src.product_decoders.output_api.get_object_store",
        lambda: fake_store,
    )
    return TestClient(create_app())


class TestListFiles:
    """GET /api/output/files"""

    def test_list_files_returns_empty_when_dir_empty(self, client):
        r = client.get("/api/output/files")
        assert r.status_code == 200
        assert r.json() == {"files": []}

    def test_list_files_returns_md_and_json_only(self, client):
        out = settings.paths.output_dir
        (out / "doc1.md").write_text("# A", encoding="utf-8")
        (out / "doc2.json").write_text("{}", encoding="utf-8")
        (out / "skip.pdf").write_bytes(b"%PDF")
        (out / "skip.txt").write_text("hi", encoding="utf-8")
        (out / ".hidden").write_text("hidden", encoding="utf-8")

        r = client.get("/api/output/files")
        assert r.status_code == 200
        names = sorted(f["name"] for f in r.json()["files"])
        assert "doc1.md" in names
        assert "doc2.json" in names
        assert "skip.pdf" not in names
        assert "skip.txt" not in names
        assert ".hidden" not in names

    def test_list_file_includes_size_and_mtime(self, client):
        out = settings.paths.output_dir
        (out / "x.md").write_text("hello", encoding="utf-8")
        r = client.get("/api/output/files")
        assert r.status_code == 200
        files = r.json()["files"]
        assert len(files) == 1
        f = files[0]
        assert f["name"] == "x.md"
        assert f["size"] == 5
        assert isinstance(f["mtime"], (int, float))
        assert f["mtime"] > 0


class TestReadFile:
    """GET /api/output/files/{name}"""

    def test_read_md_returns_content(self, client):
        out = settings.paths.output_dir
        (out / "doc.md").write_text("# Title\n\nbody", encoding="utf-8")
        r = client.get("/api/output/files/doc.md")
        assert r.status_code == 200
        body = r.json()
        assert body["name"] == "doc.md"
        assert body["content"] == "# Title\n\nbody"
        assert body["mime"] == "text/markdown"

    def test_read_json_returns_content(self, client):
        out = settings.paths.output_dir
        (out / "data.json").write_text('{"k": 1}', encoding="utf-8")
        r = client.get("/api/output/files/data.json")
        assert r.status_code == 200
        body = r.json()
        assert body["name"] == "data.json"
        assert body["content"] == '{"k": 1}'
        assert body["mime"] == "application/json"

    def test_read_missing_file_returns_404(self, client):
        r = client.get("/api/output/files/nope.md")
        assert r.status_code == 404
        assert "不存在" in r.json()["detail"]

    def test_path_traversal_returns_400(self, client):
        r = client.get("/api/output/files/bad%20name.md")
        assert r.status_code == 400
        assert "非法" in r.json()["detail"]

    def test_invalid_chars_in_name_returns_400(self, client):
        r = client.get("/api/output/files/bad~name.md")
        assert r.status_code == 400
        assert "非法" in r.json()["detail"]

    def test_oversized_file_returns_413(self, client):
        out = settings.paths.output_dir
        (out / "big.md").write_bytes(b"x" * (11 * 1024 * 1024))
        r = client.get("/api/output/files/big.md")
        assert r.status_code == 413
        assert "10 MB" in r.json()["detail"] or "太大" in r.json()["detail"]
