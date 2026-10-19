"""cad_oda DWG 读取包装测试 (ARCH-004 改造: config.toml 路径删了, 全 env)"""

import pytest

from src.ingest.pdf_processing.converters.cad import (
    OdaNotInstalledError,
    _read_oda_path_from_env_or_config,
    read_cad_with_oda,
)


def test_missing_dwg_file_raises_filenotfound(tmp_path):
    """DWG 文件本身不存在时, read_cad_with_oda 必须抛 FileNotFoundError"""
    nonexistent = tmp_path / "nonexistent.dwg"
    with pytest.raises(FileNotFoundError):
        read_cad_with_oda(str(nonexistent))


class TestOdaPathPriority:
    """_read_oda_path_from_env_or_config 优先级: env > defaults ("")"""

    def test_env_wins_over_default(self, monkeypatch):
        """env 配了 -> 用 env, 不走 defaults 空串"""
        monkeypatch.setenv("ODA_WIN_PATH", "D:/from-env")
        result = _read_oda_path_from_env_or_config("ODA_WIN_PATH", "oda_win_path")
        assert result == "D:/from-env"

        monkeypatch.setenv("ODA_UNIX_PATH", "/from-env")
        result = _read_oda_path_from_env_or_config("ODA_UNIX_PATH", "oda_unix_path")
        assert result == "/from-env"

    def test_falls_back_to_default_when_env_unset(self, monkeypatch):
        """env 没设 -> 走 defaults 空串 (ARCH-004: 不再退到 config.toml)"""
        monkeypatch.delenv("ODA_WIN_PATH", raising=False)
        result = _read_oda_path_from_env_or_config("ODA_WIN_PATH", "oda_win_path")
        assert result == ""

    def test_strips_whitespace(self, monkeypatch):
        """env 值带前后空格要去掉"""
        monkeypatch.setenv("ODA_WIN_PATH", "  D:/with-spaces  ")
        result = _read_oda_path_from_env_or_config("ODA_WIN_PATH", "oda_win_path")
        assert result == "D:/with-spaces"


class TestReadCadWithOda:
    """read_cad_with_oda 行为测试 (装 ODA 跑真路径)

    (2026-06-29) 用户: ODA 已装 + env 已配, 删 skipif, 跑真 ODA 路径.
    之前 test_dwg_raises_friendly_error_when_oda_missing 是装 ODA 之前的占位, 永远 skip, 改语义.
    """

    def test_dwg_does_not_raise_oda_not_installed_when_installed(self, tmp_path):
        """装了 ODA 时, read_cad_with_oda 不应抛 OdaNotInstalledError

        真 fake DWG 内容不完整, ODA 可能转失败抛 RuntimeError, 这是预期的.
        关键是 OdaNotInstalledError 永不抛 (本机装了 ODA).

        (2026-07-08) 沙箱没装 ODA 时直接 skip, 不让 pytest fail 卡住默认 CI 跑.
        顺手修 except 语法 bug (原 `except RuntimeError, Exception:` 是 Python 2 写法).
        """
        from ezdxf.addons import odafc

        if not odafc.is_installed():
            pytest.skip("沙箱无 ODA File Converter, 装 ODA + 配 ODA_WIN_PATH/ODA_UNIX_PATH 后才跑")

        fake_dwg = tmp_path / "fake.dwg"
        fake_dwg.write_bytes(b"AC1032\x00" * 10)

        try:
            read_cad_with_oda(str(fake_dwg))
        except OdaNotInstalledError as e:
            pytest.fail(f"装了 ODA 不应抛 OdaNotInstalledError, 实际: {e}")
        except RuntimeError:
            # fake DWG 内容不完整, ODA 转失败是预期的 (e.g. invalid file format)
            pass
