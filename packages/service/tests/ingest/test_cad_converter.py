"""CAD converter 单元测试"""

import shutil
from pathlib import Path

import pytest

# 关键 import 顺序：先 import converters.cad（会执行 _apply_oda_path_from_config 把 config 路径 set 进 ezdxf），
# 再 import odafc.is_installed() 才能拿到 config 配的 ODA 路径下的真实结果。
from src.ingest.pdf_processing.converters import (
    cad as cad_oda,  # noqa: F401  # pyright: ignore[reportUnusedImport]  # 副作用导入
)
from src.ingest.pdf_processing.converters.cad import EzdxfConverter

SAMPLE_DXF = "tests/fixtures/sample.dxf"


class TestEzdxfConverter:
    """EzdxfConverter 端到端测试（DXF 路径）"""

    def setup_method(self):
        self.converter = EzdxfConverter()

    def test_name(self):
        """converter name 必须是 'ezdxf'"""
        assert self.converter.name == "ezdxf"

    def test_convert_dxf_produces_svg_and_md(self, tmp_path):
        """真实端到端：sample.dxf → 至少 1 个 SVG + 1 个 .md

        跑通：证明 EzdxfConverter 能读 DXF、渲染 SVG、产出 markdown。
        """
        # 复制到独立 tmp 避免污染源 fixture
        cad_copy = tmp_path / "sample.dxf"
        shutil.copy(SAMPLE_DXF, cad_copy)

        result = self.converter.convert(str(cad_copy), str(tmp_path))

        assert "svg_files" in result, "返回值必须含 svg_files 键"
        assert "markdown_path" in result, "返回值必须含 markdown_path 键"
        assert "content" in result, "返回值必须含 content 键（markdown 文本）"

        # SVG
        assert len(result["svg_files"]) >= 1, "至少应有 1 个 SVG（Model 视图）"
        for svg in result["svg_files"]:
            assert Path(svg).exists()
            assert Path(svg).suffix == ".svg"
            # SVG 文件头
            head = Path(svg).read_text(encoding="utf-8")[:200]
            assert "<svg" in head, f"SVG 文件头缺失 <svg> 标签: {head[:100]}"

        # markdown
        md_path = Path(result["markdown_path"])
        assert md_path.exists()
        md = md_path.read_text(encoding="utf-8")
        assert md.startswith("#"), "markdown 应以 # 标题开头"
        assert "Model" in md or "svg" in md.lower(), "markdown 应包含 SVG 引用"

        # 运行时返回的 content 必须跟磁盘上写的一致
        assert result["content"] == md

    def test_convert_creates_output_dir_if_missing(self, tmp_path):
        """output_dir 不存在时自动创建（跟 KreuzbergConverter 行为对齐）"""
        cad_copy = tmp_path / "sample.dxf"
        shutil.copy(SAMPLE_DXF, cad_copy)

        out_dir = tmp_path / "deep" / "nested" / "out"
        assert not out_dir.exists()

        self.converter.convert(str(cad_copy), str(out_dir))

        assert out_dir.exists()
        assert out_dir.is_dir()

    def test_extract_text_finds_all_known_entity_types(self, tmp_path):
        """_extract_text 必须正确处理 TEXT/MTEXT/DIMENSION 三种类型

        覆盖用户原代码的两个 bug：
        1. MTEXT 不该用 entity.dxf.text（拿到 "\\PLine2..." 含格式码）
           必须用 entity.plain_text() → "Line1\\nLine2\\nLine3"
        2. DIMENSION 文字 "<>" 必须兜底成测量值
        """
        import ezdxf

        doc = ezdxf.readfile(SAMPLE_DXF)  # pyright: ignore[reportPrivateImportUsage]  # ezdxf 没在 stub 暴露但运行时可用
        records = self.converter._extract_text(doc)

        by_type = {}
        for r in records:
            by_type.setdefault(r["type"], []).append(r)

        # TEXT 实体
        assert "TEXT" in by_type, "TEXT 实体未被识别"
        text_rec = by_type["TEXT"][0]
        assert text_rec["text"] == "Hello CAD"
        assert text_rec["layer"] == "0"
        assert text_rec["insert_xy"] == (10.0, 20.0)

        # MTEXT 实体：plain_text() 必须把 \P 换成换行
        assert "MTEXT" in by_type, "MTEXT 实体未被识别"
        mtext_rec = by_type["MTEXT"][0]
        assert "\n" in mtext_rec["text"], f"MTEXT 应该有换行（plain_text 去 \\P），实际: {mtext_rec['text']!r}"
        assert "Line1" in mtext_rec["text"]
        assert "Line3" in mtext_rec["text"]

        # DIMENSION 实体："<>" 必须兜底成测量值
        assert "DIMENSION" in by_type, "DIMENSION 实体未被识别"
        dim_rec = by_type["DIMENSION"][0]
        assert dim_rec["text"] != "<>", "DIMENSION text='<>' 必须是测量值兜底，不是字符串 '<>'"
        # 测量值是 100（fixture 里 p1=(0,60) p2=(100,60) 距离 100）
        assert "100" in dim_rec["text"], f"DIMENSION 测量值应为 100，实际: {dim_rec['text']!r}"

    def test_extract_text_handles_garbage_entity_gracefully(self, tmp_path):
        """遇到 ezdxf 解析失败的实体不应让 _extract_text 整体崩溃

        通过 patch _record_text 让其抛异常，模拟单个实体解析失败，
        验证 _extract_text 整体容错、不抛出。
        """
        import ezdxf

        doc = ezdxf.readfile(SAMPLE_DXF)  # pyright: ignore[reportPrivateImportUsage]  # ezdxf 没在 stub 暴露但运行时可用

        # 直接调 _extract_text 验证 try/except 包裹能容错：
        # 我们 patch _record_text 让它内部抛，模拟单实体解析失败
        try:
            from src.ingest.pdf_processing.converters import cad

            original_method = cad.EzdxfConverter._record_text

            def boom(self, *a, **kw):
                raise RuntimeError("simulated")

            cad.EzdxfConverter._record_text = boom
            try:
                records = self.converter._extract_text(doc)
                # _record_text 抛异常时被外层 try/except 兜住，
                # TEXT/MTEXT/DIMENSION 都不会进 records，但仍不会崩
                assert isinstance(records, list)
            finally:
                cad.EzdxfConverter._record_text = original_method
        finally:
            pass

    def test_convert_dwg_runs_with_real_oda_when_installed(self, tmp_path):
        """装了 ODA 时, convert 收到 .dwg 走真 ODA 转换 (不抛 OdaNotInstalledError)

        (2026-06-29) 用户: ODA 已装且 env 已配, 跑真 ODA 路径, 不应再走'未装 ODA 抛友好错'的占位 test.
        之前 test_convert_dwg_raises_oda_not_installed 是装 ODA 之前的占位, 永远 skip, 删.

        (2026-07-08) 沙箱没装 ODA 时直接 skip, 不让 pytest fail 卡住默认 CI 跑.
        """
        from ezdxf.addons import odafc

        if not odafc.is_installed():
            pytest.skip("沙箱无 ODA File Converter, 装 ODA + 配 ODA_WIN_PATH/ODA_UNIX_PATH 后才跑")

        from src.ingest.pdf_processing.converters.cad import OdaNotInstalledError

        # 用 ODA 能解析的最小 DWG header (AC1032 = R2018)
        fake_dwg = tmp_path / "drawing.dwg"
        fake_dwg.write_bytes(b"AC1032\x00" * 10)

        # 装 ODA 跑真 ODA, 不会抛 OdaNotInstalledError (但 fake 内容可能 ODA 转失败, 那时 RuntimeError 是 ok 的)
        try:
            self.converter.convert(str(fake_dwg), str(tmp_path / "out"))
        except OdaNotInstalledError as e:
            pytest.fail(f"装了 ODA 不应抛 OdaNotInstalledError, 实际: {e}")
        except RuntimeError:
            # fake DWG 内容不完整, ODA 转换失败是预期的 (e.g. invalid file format)
            pass


class TestEzdxfExtensions:
    """EzdxfConverter.extensions 声明"""

    def test_ezdxf_declares_dxf_and_dwg(self):
        from src.ingest.pdf_processing.converters.cad import EzdxfConverter

        exts = EzdxfConverter.extensions
        assert ".dxf" in exts
        assert ".dwg" in exts


class TestOdaPathConfigErrorPropagation:
    """_read_oda_path_from_env_or_config 段缺失走默认空字符串

    MEDIUM shim 清理 (2026-06-08): #5
    修复前: except (FileNotFoundError, KeyError): return "" 显式兜底吃错
    修复后: 删 try/except 显式兜底, 让 get_cad_config() 段缺失走默认空 (合理)
    """

    def test_returns_empty_when_env_unset(self, monkeypatch):
        """env 缺 -> return "" (ARCH-004: config.toml 路径已删, 纯 env-only)"""
        from src.ingest.pdf_processing.converters.cad import _read_oda_path_from_env_or_config

        monkeypatch.delenv("ODA_WIN_PATH", raising=False)
        monkeypatch.delenv("ODA_UNIX_PATH", raising=False)

        result = _read_oda_path_from_env_or_config(
            key_env="ODA_WIN_PATH",
            key_config="oda_win_path",
        )
        assert result == "", f"env 缺应返回空字符串，实际: {result!r}"
