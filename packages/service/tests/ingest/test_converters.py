"""Converter 转换器单元测试"""

import os
import shutil
import tempfile
from pathlib import Path

import pytest

from src.ingest.pdf_processing.analyzers.pdf import PDFInfo
from src.ingest.pdf_processing.converters import (
    CONVERTERS,
    Converter,
    KreuzbergConverter,
    MineruConverter,
    classify_files,
    get_converter,
)
from src.ingest.pdf_processing.converters.cad import EzdxfConverter

# 真 PDF 测试样本 (2026-06-29) 改用 tests/fixtures/ 已入库样本, 不再依赖 pdfs/ 软链
_FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


class TestConverterBase:
    """Converter 基类测试"""

    def test_base_can_handle_returns_false(self):
        """基类can_handle默认返回False"""
        info = PDFInfo()
        assert Converter.can_handle(info) is False

    def test_base_convert_raises(self):
        """基类convert应抛出NotImplementedError"""
        converter = Converter()
        with pytest.raises(NotImplementedError):
            converter.convert("test.pdf", "out.md")

    def test_convert_batch_returns_dict(self):
        """测试批量转换返回字典"""
        converter = Converter()
        with tempfile.TemporaryDirectory() as tmpdir:
            results = converter.convert_batch([], tmpdir)
            assert isinstance(results, dict)
            assert len(results) == 0


class TestKreuzbergConverter:
    """KreuzbergConverter 测试"""

    def setup_method(self):
        self.converter = KreuzbergConverter()
        self.info_simple = PDFInfo(has_text=True, is_simple=True)
        self.info_complex = PDFInfo(has_text=False, is_simple=False)

    def test_name(self):
        """测试名称"""
        assert self.converter.name == "kreuzberg"

    def test_can_handle_simple_text(self):
        """简单含文字PDF可以处理"""
        assert self.converter.can_handle(self.info_simple) is True

    def test_cannot_handle_complex(self):
        """复杂PDF不能处理"""
        assert self.converter.can_handle(self.info_complex) is False

    def test_cannot_handle_no_text(self):
        """无文字PDF不能处理"""
        info = PDFInfo(has_text=False, is_simple=True)
        assert self.converter.can_handle(info) is False

    def test_convert_batch_real_pdf(self, tmp_path):
        """真实端到端：用 kreuzberg 批量接口处理一个真 PDF，必须返回 dict 且内容非空

        回归测试：之前用了 async 版 batch_extract_files（coroutine），导致
        'coroutine' object is not iterable + RuntimeWarning: coroutine ... was never awaited。
        修复后必须用 batch_extract_files_sync（同签名同返回类型），本测试通过即证明修好。
        """
        real_pdf = str(_FIXTURES_DIR / "easy_pdf_test.pdf")

        # 复制到独立临时目录（避免污染源）
        pdf_copy = tmp_path / "rag.pdf"
        shutil.copy(real_pdf, pdf_copy)

        # 产品代码假定 output_dir 已存在（与 main.py 调用方一致）
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        converter = KreuzbergConverter()
        results = converter.convert_batch([str(pdf_copy)], str(out_dir))

        assert isinstance(results, dict)
        assert str(pdf_copy) in results
        content = results[str(pdf_copy)]
        assert content, "kreuzberg 批量接口应产出非空内容（修复前返回 [ERROR] 串）"
        assert not content.startswith("[ERROR]"), f"kreuzberg 批量接口不应报错，实际错误: {content!r}"

    def test_convert_batch_auto_creates_output_dir(self, tmp_path):
        """convert_batch 应自动创建不存在的 output_dir（与 MineruConverter 行为对齐）

        修复前：output_dir 不存在会 FileNotFoundError，调用方必须先 mkdir。
        修复后：自动 makedirs(exist_ok=True)，调用方无需关心。
        """
        real_pdf = str(_FIXTURES_DIR / "easy_pdf_test.pdf")

        pdf_copy = tmp_path / "README.pdf"
        shutil.copy(real_pdf, pdf_copy)

        # 关键：不预先 mkdir
        out_dir = tmp_path / "deep" / "nested" / "out"
        assert not out_dir.exists(), "测试前提：output_dir 必须不存在"

        converter = KreuzbergConverter()
        results = converter.convert_batch([str(pdf_copy)], str(out_dir))

        # 返回值结构正确
        assert str(pdf_copy) in results
        assert results[str(pdf_copy)], "应有非空内容"

        # output_dir 已被自动创建
        assert out_dir.exists(), "convert_batch 应自动创建 output_dir"
        assert out_dir.is_dir()
        # 文件也写到了正确位置（子目录布局：<out>/<stem>/<stem>.md）
        assert (out_dir / "README" / "README.md").exists()

    def test_convert_batch_writes_to_stem_subdir(self, tmp_path):
        """输出改为 <output>/<stem>/<stem>.md（跟 mineru 对齐）"""
        # 用 kreuzberg 直接产一个 markdown
        real_pdf = str(_FIXTURES_DIR / "easy_pdf_test.pdf")

        pdf_copy = tmp_path / "sample.pdf"
        shutil.copy(real_pdf, pdf_copy)

        converter = KreuzbergConverter()
        out = tmp_path / "out"
        converter.convert_batch([str(pdf_copy)], str(out))

        # 期望: <out>/sample/sample.md
        expected = out / "sample" / "sample.md"
        assert expected.exists(), f"输出应在子目录: {expected}"


class TestMineruConverter:
    """MineruConverter 测试"""

    def setup_method(self):
        self.converter = MineruConverter()

    def test_name(self):
        """测试名称"""
        assert self.converter.name == "mineru"

    def test_can_handle_complex(self):
        """复杂PDF用mineru处理"""
        info = PDFInfo(is_simple=False)
        assert self.converter.can_handle(info) is True

    def test_can_handle_simple(self):
        """简单PDF也接收：实际路由由 CONVERTERS 顺序 + extensions 决定

        简单含文字的 PDF 会先被 KreuzbergConverter 截走
        （顺序在 CONVERTERS 前 + can_handle=is_simple and has_text），
        这里的 can_handle 只决定"mineru 有没有能力吃"，答案始终 True。
        """
        info = PDFInfo(is_simple=True)
        assert self.converter.can_handle(info) is True

    def test_can_handle_accepts_all_pdfinfo(self):
        """mineru.can_handle 对任何 PDFInfo 都返回 True

        合同：路由决策 = extensions（哪个 converter 收这个扩展名）
                          + can_handle（这个 converter 能不能吃）。
        简单/复杂 PDF 的分流已由 CONVERTERS 顺序 + KreuzbergConverter.can_handle 处理，
        mineru 自身不重复拒绝。
        """
        # 简单含文字：典型 kreuzberg 场景
        info_a = PDFInfo(has_text=True, is_simple=True)
        # 简单无文字：扫描件 PDF
        info_b = PDFInfo(has_text=False, is_simple=True)
        # 复杂 PDF：mineru 原本的当家场景
        info_c = PDFInfo(has_text=False, is_simple=False)
        # 复杂但有文字（双层 PDF）
        info_d = PDFInfo(has_text=True, is_simple=False)
        for info in (info_a, info_b, info_c, info_d):
            assert self.converter.can_handle(info) is True, f"mineru 应接受所有 PDFInfo，但 {info!r} 被拒"

    def test_convert_batch_empty(self):
        """空列表批量处理"""
        with tempfile.TemporaryDirectory() as tmpdir:
            results = self.converter.convert_batch([], tmpdir)
            assert results == {}

    def test_resolve_md_path_matches_mineru_output_layout(self):
        """验证路径解析匹配mineru实际输出布局

        mineru实际输出结构（已用真实容器验证）:
            <output_dir>/<pdf_stem>/<method>/<pdf_stem>.md
        注意：嵌套目录是 **PDF 文件名（stem）**，不是输入目录名。
        """
        with tempfile.TemporaryDirectory() as input_dir, tempfile.TemporaryDirectory() as output_dir:
            pdf_path = os.path.join(input_dir, "demo.pdf")
            Path(pdf_path).write_bytes(b"%PDF-1.4\n%EOF\n")

            method = "auto"
            expected = os.path.join(
                os.path.abspath(output_dir),
                "demo",  # PDF stem
                method,
                "demo.md",
            )
            actual = MineruConverter.resolve_md_path(pdf_path, output_dir, method=method)
            assert actual == expected, f"mineru 实际输出路径应为 {expected}，但代码解析得到 {actual}"


# 真实端到端测试：跑真实 mineru 容器处理真实 PDF，验证能产出并读到 markdown
# 默认跳过：每个PDF数十秒到数分钟，处理18个太慢。
# 开启方式：RUN_SLOW_TESTS=1 pytest


@pytest.mark.skipif(
    not os.environ.get("RUN_SLOW_TESTS"),
    reason="真实端到端测试较慢，设 RUN_SLOW_TESTS=1 开启",
)
class TestMineruEndToEnd:
    """真实端到端测试：跑真实 mineru 容器 + 真实 PDF"""

    def test_container_sees_host_gpu(self):
        """验证 convert_batch 调用时 GPU 真的被透传到容器

        之前 bug: 没传 device_requests → 容器内 torch.cuda.is_available() = False
                  即使主机有 RTX 4060，mineru 也用不了 GPU。
        修复后: 透传 GPU → 容器内应该能看到 GPU。

        这个测试用代码里同样的 Docker API 调用方式启动一个临时容器，
        在容器内跑 torch 检查 cuda 可用性。
        """
        import docker
        from docker.types import DeviceRequest

        client = docker.from_env()
        try:
            output = client.containers.run(
                "mineru:latest",
                ["/usr/bin/python3", "-c", "import torch; print('CUDA_AVAILABLE=' + str(torch.cuda.is_available()))"],
                device_requests=[DeviceRequest(count=-1, capabilities=[["gpu"]])],
                remove=True,
            )
            text = output.decode("utf-8")
            assert "CUDA_AVAILABLE=True" in text, (
                f"容器内 torch.cuda.is_available() 应该为 True（修复 GPU 透传后），但容器输出: {text!r}"
            )
        finally:
            client.close()

    def test_real_mineru_generates_and_reads_markdown(self, tmp_path):
        """跑真实 mineru 容器处理真实 PDF，验证能产出并读到 markdown

        不使用任何 mock。修复前：返回空串（路径错了）。
        修复后：返回真实 markdown 内容。
        """
        # 用真实的 PDF（来自项目 pdfs/ 目录）
        real_pdf = str(_FIXTURES_DIR / "easy_pdf_test.pdf")

        # 复制到独立临时输入目录（避免污染源）
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        pdf_path = input_dir / "sample.pdf"
        shutil.copy(real_pdf, pdf_path)

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        converter = MineruConverter()
        results = converter.convert_batch([str(pdf_path)], str(output_dir))

        # 验证：1) 返回了结果；2) 内容非空；3) 真实文件存在于 mineru 实际输出位置
        assert str(pdf_path) in results
        content = results[str(pdf_path)]
        assert content, "mineru 容器跑完应该产出非空内容（修复前返回空串）"

        # 双重确认：文件确实在 mineru 实际输出布局中存在
        expected_path = MineruConverter.resolve_md_path(str(pdf_path), str(output_dir), method="auto")
        assert os.path.exists(expected_path), f"mineru 输出文件不存在: {expected_path}"

    def test_mineru_does_not_process_pdfs_outside_its_batch(self, tmp_path):
        """验证 mineru 不会越界处理本批之外的 PDF

        修复前 bug: convert_batch 把整个 pdf_dir 挂到 /app/input，
        mineru 命令是扫描整目录，结果 kreuzberg 那批 PDF 也被跑了一遍，
        output_dir 出现不该有的 auto/ 目录 + _layout.pdf / _model.json / _content_list.json。

        修复后: convert_batch 用临时目录隔离，只把本批 PDF 放进容器视野。
        """
        real_pdf = str(_FIXTURES_DIR / "easy_pdf_test.pdf")

        # 模拟用户场景：input_dir 里有 2 张 PDF（实际是同一张的两份拷贝）
        # 其中一张会"分给" mineru（convert_batch 收的），
        # 另一张不传（代表 kreuzberg 那批）—— 必须不能被 mineru 看到。
        shared_input_dir = tmp_path / "input"
        shared_input_dir.mkdir()
        mineru_pdf = shared_input_dir / "to_mineru.pdf"
        kreuzberg_pdf = shared_input_dir / "to_kreuzberg.pdf"
        shutil.copy(real_pdf, mineru_pdf)
        shutil.copy(real_pdf, kreuzberg_pdf)

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        converter = MineruConverter()
        # 只传 mineru_pdf，不传 kreuzberg_pdf
        results = converter.convert_batch([str(mineru_pdf)], str(output_dir))

        # 1. mineru 应该有结果
        assert str(mineru_pdf) in results
        assert results[str(mineru_pdf)], "mineru 处理本批 PDF 应该产出内容"

        # 2. 关键断言：kreuzberg_pdf 的 auto 目录不能出现在 output_dir
        # （这才是修复要保护的不变量 —— kreuzberg 的 PDF 不能被 mineru 越界处理）
        kreuzberg_auto_dir = output_dir / kreuzberg_pdf.stem / "auto"
        assert not kreuzberg_auto_dir.exists(), (
            f"mineru 越界处理了 kreuzberg 的 PDF: {kreuzberg_auto_dir} 不应存在。\n"
            f"  output_dir 实际内容: {list(output_dir.iterdir())}"
        )


class TestGetConverter:
    """get_converter 测试"""

    def test_get_kreuzberg(self):
        converter = get_converter("kreuzberg")
        assert isinstance(converter, KreuzbergConverter)

    def test_get_mineru(self):
        converter = get_converter("mineru")
        assert isinstance(converter, MineruConverter)

    def test_get_invalid_raises(self):
        """无效名称应抛出KeyError"""
        with pytest.raises(KeyError):
            get_converter("nonexistent")


class TestConvertersRegistry:
    """CONVERTERS 注册表测试"""

    def test_all_converters_registered(self):
        """所有转换器已注册"""
        assert "kreuzberg" in CONVERTERS
        assert "mineru" in CONVERTERS

    def test_registry_values_are_classes(self):
        """注册表的值是类"""
        for _name, cls in CONVERTERS.items():
            assert isinstance(cls, type)
            assert issubclass(cls, Converter)


class TestConverterExtensions:
    """Converter.extensions 声明机制"""

    def test_kreuzberg_declares_only_pdf(self):
        """kreuzberg 只处理简单 PDF（其他格式走 mineru / 不支持）"""
        exts = KreuzbergConverter.extensions
        assert exts == [".pdf"]

    def test_mineru_declares_pdf_images_and_office(self):
        """mineru 吃 PDF + 图片 + Office OOXML（mineru --help + 真容器验证）

        Office 区分：
        - .docx / .pptx / .xlsx 是 OOXML 新格式，mineru 容器支持
        - .xls (BIFF8 旧格式) 不在 mineru --help 支持列表
        """
        exts = MineruConverter.extensions
        # PDF
        assert ".pdf" in exts
        # 图片
        for ext in [".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff"]:
            assert ext in exts, f"mineru 应支持 {ext}"
        # Office OOXML（mineru --help 明确支持 pdf, image, docx, pptx, xlsx）
        assert ".docx" in exts
        assert ".pptx" in exts
        assert ".xlsx" in exts  # 2026-06-02 真容器验证：.xlsx 产出 <table> markdown
        # .xls (BIFF8 旧格式) 不支持：实测 docker run 报 "No supported documents found"
        assert ".xls" not in exts
        # HTML/EML/EPUB 不支持（to-do.md 未要求）
        assert ".html" not in exts
        assert ".eml" not in exts
        assert ".epub" not in exts


class TestClassifyFiles:
    """classify_files 按 converter 声明的 extensions 过滤分发"""

    def test_pdf_goes_to_kreuzberg_when_simple(self):
        """简单 PDF → kreuzberg"""
        infos = {"a.pdf": PDFInfo(has_text=True, is_simple=True)}
        result = classify_files(infos, list(CONVERTERS.values()))
        assert "a.pdf" in result["kreuzberg"]
        assert "a.pdf" not in result["mineru"]

    def test_pdf_goes_to_mineru_when_complex(self):
        """复杂 PDF → mineru"""
        infos = {"a.pdf": PDFInfo(has_text=False, is_simple=False)}
        result = classify_files(infos, list(CONVERTERS.values()))
        assert "a.pdf" in result["mineru"]
        assert "a.pdf" not in result["kreuzberg"]

    def test_png_routes_to_mineru(self):
        """.png 走 mineru（kreuzberg 现在只 PDF）
        用 is_simple=False 触发 mineru.can_handle；扩展名匹配也确保 .png 只走 mineru。
        """
        infos = {"a.png": PDFInfo(has_text=False, is_simple=False)}
        result = classify_files(infos, list(CONVERTERS.values()))
        assert "a.png" in result["mineru"]
        assert "a.png" not in result["kreuzberg"]

    def test_png_routes_to_mineru_with_simple_pdfinfo(self):
        """回归测试：.png 即便 is_simple=True 也必须进 mineru

        修复前 bug: MineruConverter.can_handle = `not info.is_simple`，
        .png 走 PDFAnalyzer 默认值 is_simple=True → can_handle 返回 False
        → .png 不分给任何 converter → 进 unknown 桶打 [WARN] 跳过。
        修复后: mineru.can_handle 始终 True，扩展名匹配决定走向，.png 安全到 mineru。
        """
        infos = {"a.png": PDFInfo(has_text=True, is_simple=True)}  # PDFAnalyzer 对非 PDF 的默认值
        result = classify_files(infos, list(CONVERTERS.values()))
        assert "a.png" in result["mineru"], ".png 必须路由到 mineru，但实际被忽略——can_handle 把简单 PDFInfo 拒了？"
        assert "a.png" not in result["kreuzberg"]

    def test_docx_routes_to_mineru(self):
        """.docx 走 mineru（mineru 验证支持）
        用 is_simple=False 触发 mineru.can_handle；扩展名匹配也确保 .docx 只走 mineru。
        """
        infos = {"a.docx": PDFInfo(has_text=True, is_simple=False)}
        result = classify_files(infos, list(CONVERTERS.values()))
        assert "a.docx" in result["mineru"]
        assert "a.docx" not in result["kreuzberg"]

    def test_xyz_not_classified(self):
        """未注册扩展名返回空 grouped（任何 converter 都不分）"""
        infos = {"a.xyz": PDFInfo(has_text=True, is_simple=True)}
        result = classify_files(infos, list(CONVERTERS.values()))
        # 所有 converter 都不分
        for name in CONVERTERS:
            assert "a.xyz" not in result[name]

    def test_dxf_goes_to_ezdxf(self):
        """.dxf 走 EzdxfConverter（在 CONVERTERS 里也注册一份方便统一调用）"""
        infos = {"a.dxf": PDFInfo()}  # ezdxf 不走 can_handle
        # 把 EzdxfConverter 加到 converters list 里
        converters = list(CONVERTERS.values()) + [EzdxfConverter]
        result = classify_files(infos, converters)
        assert "a.dxf" in result["ezdxf"]

    def test_classify_simple_pdfs(self):
        """简单PDF分到kreuzberg（classify_pdfs shim 已删，直接用 classify_files）"""
        infos = {"a.pdf": PDFInfo(has_text=True, is_simple=True)}
        result = classify_files(infos, list(CONVERTERS.values()))
        assert len(result["kreuzberg"]) == 1
        assert len(result["mineru"]) == 0

    def test_classify_complex_pdfs(self):
        """复杂PDF分到mineru"""
        infos = {"a.pdf": PDFInfo(has_text=False, is_simple=False)}
        result = classify_files(infos, list(CONVERTERS.values()))
        assert len(result["kreuzberg"]) == 0
        assert len(result["mineru"]) == 1

    def test_classify_mixed(self):
        """混合PDF分类"""
        infos = {
            "a.pdf": PDFInfo(has_text=True, is_simple=True),
            "b.pdf": PDFInfo(has_text=False, is_simple=False),
            "c.pdf": PDFInfo(has_text=True, is_simple=True),
        }
        result = classify_files(infos, list(CONVERTERS.values()))
        assert len(result["kreuzberg"]) == 2
        assert len(result["mineru"]) == 1

    def test_classify_empty(self):
        """空输入"""
        result = classify_files({}, list(CONVERTERS.values()))
        assert all(len(paths) == 0 for paths in result.values())


class TestMineruParseFailedFiles:
    """MineruConverter._parse_failed_files —— 从 mineru stderr 解析失败的文件 stem（仅日志诊断用）"""

    def test_parse_failed_files_single(self):
        """单个 task 失败：解析出对应 stem"""
        stderr = (
            "INFO some startup line\n"
            "Error: 1 task(s) failed while processing documents:\n"
            "- task#1 (1LE1): All connection attempts failed\n"
        )
        assert MineruConverter._parse_failed_files(stderr) == {"1LE1"}

    def test_parse_failed_files_multiple(self):
        """多个 task 失败：全部 stem 都拿到"""
        stderr = (
            "Error: 2 task(s) failed while processing documents:\n"
            "- task#1 (1LE1): All connection attempts failed\n"
            "- task#3 (complex_pdf_test): some other error\n"
        )
        assert MineruConverter._parse_failed_files(stderr) == {"1LE1", "complex_pdf_test"}

    def test_parse_failed_files_no_match(self):
        """stderr 不含 task# 行（镜像缺失场景）→ 空集合"""
        stderr = "docker: Error response from daemon: pull access denied"
        assert MineruConverter._parse_failed_files(stderr) == set()

    def test_parse_failed_files_chinese_stem(self):
        """中文文件名 stem 能解析"""
        stderr = "- task#3 (定制服务器05-26): All connection attempts failed\n"
        assert MineruConverter._parse_failed_files(stderr) == {"定制服务器05-26"}


class TestEzdxfCanHandleAlwaysTrue:
    """EzdxfConverter 走 ezdxf 自己的解析逻辑, 不分析 PDFInfo, can_handle 总返 True

    旧设计用 Converter 基类的 skip_can_handle flag 偷塞行为; 新设计直接 override can_handle。
    """

    def test_can_handle_returns_true_for_any_pdfinfo(self):
        from src.ingest.pdf_processing.converters.cad import EzdxfConverter

        for info in [
            PDFInfo(has_text=True, is_simple=True),
            PDFInfo(has_text=False, is_simple=False),
            PDFInfo(),
        ]:
            assert EzdxfConverter().can_handle(info) is True, (
                f"EzdxfConverter 应接受任何 PDFInfo（不分析 PDFInfo），但 {info!r} 被拒"
            )
