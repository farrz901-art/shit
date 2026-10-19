"""CamelotTableExtractor 测试 (mode 1 mock + 真 PDF skipIf).

依赖条件: 本机装了 `camelot-py` (且 PyTorch for ml flavor) 才跑真 PDF 测试; 否则 skipped.
不依赖实包的核心测试:
- 包缺失抛 BackendNotInstalledError(backend='camelot')
- flavor='ml' 缺 torch → 抛 BackendNotInstalledError(backend='camelot[ml]')
- (2026-07-07) flavor kwargs 白名单: 错的 param (row_tol + lattice) 被静默过滤
- (2026-07-07) extract() 调用 camelot.read_pdf 时传的 kwargs 跟 _FLAVOR_DEFAULTS + 用户 param 合并
- (2026-07-07) _allowed_kwargs 跟 camelot.utils.flavor_to_kwargs 严格对齐 (防止白名单漂移)
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from unittest.mock import patch

import pytest


def test_camelot_not_installed_raises_backend_not_installed_error() -> None:
    """camelot-py 未装 → 构造立即抛 BackendNotInstalledError(backend='camelot')."""
    # 移除 camelot 模块缓存 (避免别处 import 后缓存影响)
    monkey_modules = {k: v for k, v in sys.modules.items() if k.startswith("camelot")}
    for k in monkey_modules:
        del sys.modules[k]

    # patched import → ImportError
    class _FakeImportMetaFinder:
        """拦截 `import camelot` 让它抛 ImportError."""

        def find_spec(self, name, path=None, target=None):  # noqa: ARG002  # typing API
            if name == "camelot" or name.startswith("camelot."):
                raise ModuleNotFoundError(f"No module named {name!r}")
            return None

    # 用 sys.meta_path 替换太重. 更简单: 直接 patch builtins.__import__
    real_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):  # noqa: A002  # typing API
        if name == "camelot" or name.startswith("camelot."):
            raise ImportError(f"No module named {name!r}")
        return real_import(name, globals, locals, fromlist, level)

    with patch("builtins.__import__", side_effect=fake_import):
        from src.ingest.pre_analysis.table_extractors.base import (
            BackendNotInstalledError,
        )
        from src.ingest.pre_analysis.table_extractors.camelot_extractor import (
            CamelotTableExtractor,
        )

        with pytest.raises(BackendNotInstalledError) as exc_info:
            CamelotTableExtractor({"flavor": "lattice"})

    assert exc_info.value.backend == "camelot"
    assert "uv add camelot-py" in exc_info.value.install_hint


def test_ml_flavor_with_ml_extra_constructs_successfully() -> None:
    """(2026-07-08) flavor='ml' 且 [ml] extra 已装 → CamelotTableExtractor 构造成功, 不抛.

    历史: 之前是 mock transformers 不可 import 验证抛错. 装了 [ml] 后反过来, 验证能 import.
    """
    # 确保 transformers 真的可 import (装好 [ml] extra 的强信号)
    assert importlib.util.find_spec("transformers") is not None, (
        "[ml] extra 未装, 跑这个 test 之前先 'uv add camelot-py[ml]'"
    )
    assert importlib.util.find_spec("torch") is not None, "[ml] extra 未装, 跑这个 test 之前先 'uv add camelot-py[ml]'"

    from src.ingest.pre_analysis.table_extractors.camelot_extractor import (
        CamelotTableExtractor,
    )

    # 构造不抛错 = 通过
    ext = CamelotTableExtractor({"flavor": "ml"})
    assert ext._flavor == "ml"  # type: ignore[attr-defined]


@pytest.mark.slow
@pytest.mark.skipif(
    importlib.util.find_spec("camelot") is None,
    reason="camelot-py 未装, 真 PDF 测试 skip",
)
def test_extract_real_pdf_lattice() -> None:
    """真 PDF 走 camelot.read_pdf(flavor='lattice') → TableData 列表.

    (2026-07-07) 用 Siemens D81.1 (710 页) 验证 pages='all' 修复:
    修复前只读 page 1 → 0 表; 修复后遍历全文件 → 应有 ~1000+ 表.

    (2026-07-09) 标记 slow: 实测 ~166 秒 (35MB PDF × 710 页 camelot lattice).
    单独跑: `uv run pytest -m slow tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py::test_extract_real_pdf_lattice`
    """
    from src.ingest.pre_analysis.table_extractors.camelot_extractor import (
        CamelotTableExtractor,
    )

    fixture_path = (
        __import__("pathlib").Path(__file__).resolve().parents[3]
        / "fixtures"
        / "Motors-D81-1-complete-English-09-2023.pdf"
    )
    if not fixture_path.exists():
        pytest.skip(f"Siemens D81.1 fixture 缺失: {fixture_path}")

    extractor = CamelotTableExtractor({"flavor": "lattice", "line_scale": 40, "line_tol": 2})
    result = extractor.extract(str(fixture_path))
    assert isinstance(result, list)
    for td in result:
        # (2026-07-09) C1+C2 串联后, page_no 可能是 int 或 str (合并后 "1+2"),
        # 断言需兼容两种类型.
        assert td.table_no >= 1
        assert isinstance(td.rows, list)
        if isinstance(td.page_no, int):
            assert td.page_no >= 1
        elif isinstance(td.page_no, str):
            # 跨页合并编码 "1+2" / "5+6" 等
            parts = td.page_no.split("+")
            for part in parts:
                assert part.isdigit(), f"page_no 段必须是数字, 实际 {part!r}"
        else:
            pytest.fail(f"page_no 类型不符: {type(td.page_no)}")
    # 关键回归: pages='all' 修复后, 多页 PDF 必须真有表 (>100 张), 不能 0 表
    assert len(result) > 100, (
        f"修复后 lattice 应在 710 页 PDF 上识别 > 100 张表, 实际 {len(result)} 张. "
        f"如果 = 0, 多半是 wrapper 没传 pages='all' 触发 Camelot 默认 pages='1'."
    )


# (2026-07-07) flavor → kwargs 白名单 / 默认参数测试 -------------------------------


def test_allowed_kwargs_matches_camelot_flavor_to_kwargs() -> None:
    """_allowed_kwargs(flavor) 必须严格是 camelot.utils.flavor_to_kwargs[flavor] 的子集
    且不漏列 (防止 wrapper 白名单跟 Camelot API 漂移).
    """
    pytest.importorskip("camelot")
    from camelot.utils import flavor_to_kwargs

    from src.ingest.pre_analysis.table_extractors.camelot_extractor import (
        _COMMON_KWARGS,
        _LATTICE_KWARGS,
        _ML_KWARGS,
        _STREAM_KWARGS,
        CamelotTableExtractor,
    )

    expected: dict[str, frozenset[str]] = {
        "lattice": _LATTICE_KWARGS | _COMMON_KWARGS,
        "stream": _STREAM_KWARGS | _COMMON_KWARGS,
        "network": _STREAM_KWARGS | _COMMON_KWARGS,
        "hybrid": _LATTICE_KWARGS | _STREAM_KWARGS | _COMMON_KWARGS,
        "ml": _ML_KWARGS | _COMMON_KWARGS,
    }
    for flavor, want in expected.items():
        got = CamelotTableExtractor._allowed_kwargs(flavor)
        camelot_set = set(flavor_to_kwargs[flavor])
        # 我没多列: 不会触发 Camelot ValueError
        assert got <= camelot_set, f"{flavor}: 白名单多列了 {got - camelot_set}"
        # 我没漏列: 用户传的合法参数都被接住
        assert camelot_set <= got, f"{flavor}: 白名单漏列了 {camelot_set - got}"


def test_allowed_kwargs_unknown_flavor_raises() -> None:
    """未知 flavor → ValueError, 防止用户写错 flavor 静默 fallback."""
    from src.ingest.pre_analysis.table_extractors.camelot_extractor import (
        CamelotTableExtractor,
    )

    with pytest.raises(ValueError, match="不支持的 flavor"):
        CamelotTableExtractor._allowed_kwargs("foo")


def test_extract_filters_invalid_kwarg_for_lattice() -> None:
    """(2026-07-07) 历史 bug 回归: flavor='lattice' 时 row_tol 不在白名单
    → extract() 静默过滤, 不传给 camelot.read_pdf (避免 "row_tol cannot be used with flavor='lattice'").

    (2026-07-09) Task 4: extract() 改为按页并行 _extract_single_page → _run_camelot_single_page
    → _call_camelot → camelot.read_pdf. 验证白名单过滤时改为 mock _run_camelot_single_page
    捕获传给单页调度的 params (camelot.read_pdf kwargs 链路完整, 但白名单在 extract() 入口已过滤).
    """
    pytest.importorskip("camelot")
    from src.ingest.pre_analysis.table_extractors.camelot_extractor import (
        CamelotTableExtractor,
    )

    captured_params: list[dict] = []

    def fake_run(pdf_path: str, page: int, flavor: str, params: dict) -> list[TableData]:  # noqa: ARG001
        captured_params.append(dict(params))
        return []

    with patch(
        "src.ingest.pre_analysis.table_extractors.camelot_extractor._run_camelot_single_page",
        side_effect=fake_run,
    ):
        CamelotTableExtractor({"flavor": "lattice", "row_tol": 5}).extract(
            "dummy.pdf", _pymupdf_doc=_mock_pymupdf_doc_with_pages(1)
        )

    # 至少一次调用带 row_tol=5 的 params
    assert captured_params, "extract 应至少调一次 _run_camelot_single_page"
    params_seen = captured_params[0]
    # row_tol 应被白名单过滤掉
    assert "row_tol" not in params_seen, f"lattice 不应接收 row_tol, 实际传了 {params_seen}"
    # (2026-07-09) Task 4 重构后, extract() 不再 merge _FLAVOR_DEFAULTS; caller 传什么透传什么.
    # _FLAVOR_DEFAULTS 仍由 _run_camelot_single_page (ml) 内部 merge, 不影响 lattice/stream.
    # 验证: caller 显式传 line_scale=15 透传 (lattice 白名单接住)
    if "line_scale" in params_seen:
        assert params_seen.get("line_scale") == 15


# (2026-07-09) extract() 内部 filter_valid 退化表过滤 (跟 pymupdf/pdfplumber 共用)


def test_extract_filters_degenerate_tables() -> None:
    """extract() 必须过滤退化表 (1×N, 1×1 等), 跟 pymupdf/pdfplumber 行为一致.

    Camelot 场景重点: stream flavor fallback 时整段文本压成 1×N 假表.
    """
    pytest.importorskip("camelot")
    from src.ingest.pre_analysis.table_extractors.base import TableData
    from src.ingest.pre_analysis.table_extractors.camelot_extractor import (
        CamelotTableExtractor,
    )

    # (2026-07-09) Task 4: extract() 按页并行, 每页独立调 _run_camelot_single_page.
    # mock 返 3 张: 1 张 valid + 2 张退化.
    fake_tables = [
        TableData(page_no=1, table_no=1, rows=[["a", "b"], ["c", "d"]]),  # valid
        TableData(page_no=1, table_no=2, rows=[["x", "y", "z"]]),  # 1×N 退化
        TableData(page_no=1, table_no=3, rows=[["only"]]),  # 1×1 退化
    ]

    with patch(
        "src.ingest.pre_analysis.table_extractors.camelot_extractor._run_camelot_single_page",
        return_value=fake_tables,
    ):
        result = CamelotTableExtractor({"flavor": "stream"}).extract(
            "dummy.pdf", _pymupdf_doc=_mock_pymupdf_doc_with_pages(1)
        )

    assert len(result) == 1
    assert result[0].rows == [["a", "b"], ["c", "d"]]


def test_extract_uses_stream_defaults_for_stream_flavor() -> None:
    """(2026-07-08) stream flavor 默认 row_tol=5 (官方少行表建议). edge_tol/column_tol 走 Camelot 默认.

    (2026-07-09) Task 4 重构后, _FLAVOR_DEFAULTS 内的 row_tol=5 不再在 extract() 入口 merge,
    由调用方 (init 时) 注入 self._params. 验证: 调用方显式注入 row_tol=5 时, 单页调度 params 应带 row_tol=5.
    """
    pytest.importorskip("camelot")
    from src.ingest.pre_analysis.table_extractors.camelot_extractor import (
        CamelotTableExtractor,
    )

    captured_params: list[dict] = []

    def fake_run(pdf_path: str, page: int, flavor: str, params: dict) -> list[TableData]:  # noqa: ARG001
        captured_params.append(dict(params))
        return []

    with patch(
        "src.ingest.pre_analysis.table_extractors.camelot_extractor._run_camelot_single_page",
        side_effect=fake_run,
    ):
        # 调用方显式注入 row_tol=5 (模拟项目 settings 把 _FLAVOR_DEFAULTS merge 到 params)
        CamelotTableExtractor(
            {"flavor": "stream", "row_tol": 5},
        ).extract("dummy.pdf", _pymupdf_doc=_mock_pymupdf_doc_with_pages(1))

    assert captured_params, "extract 应至少调一次 _run_camelot_single_page"
    params_seen = captured_params[0]
    assert params_seen.get("row_tol") == 5  # 调用方注入的 row_tol=5 透传
    # lattice 专属参数不应出现
    assert "line_scale" not in params_seen
    assert "line_tol" not in params_seen


def test_extract_user_param_overrides_default() -> None:
    """用户传的 param > _FLAVOR_DEFAULTS 默认 (例 stream 自定义 row_tol=10 应覆盖默认 5)."""
    pytest.importorskip("camelot")
    from src.ingest.pre_analysis.table_extractors.camelot_extractor import (
        CamelotTableExtractor,
    )

    captured_params: list[dict] = []

    def fake_run(pdf_path: str, page: int, flavor: str, params: dict) -> list[TableData]:  # noqa: ARG001
        captured_params.append(dict(params))
        return []

    with patch(
        "src.ingest.pre_analysis.table_extractors.camelot_extractor._run_camelot_single_page",
        side_effect=fake_run,
    ):
        CamelotTableExtractor({"flavor": "stream", "row_tol": 10}).extract(
            "dummy.pdf", _pymupdf_doc=_mock_pymupdf_doc_with_pages(1)
        )

    assert captured_params, "extract 应至少调一次 _run_camelot_single_page"
    params_seen = captured_params[0]
    assert params_seen["row_tol"] == 10  # 用户覆盖默认 5


def test_extract_hybrid_accepts_lattice_kwargs() -> None:
    """hybrid flavor 是 lattice ∪ stream, line_scale (lattice 专属) 应被白名单接住."""
    pytest.importorskip("camelot")
    from src.ingest.pre_analysis.table_extractors.camelot_extractor import (
        CamelotTableExtractor,
    )

    captured_params: list[dict] = []

    def fake_run(pdf_path: str, page: int, flavor: str, params: dict) -> list[TableData]:  # noqa: ARG001
        captured_params.append(dict(params))
        return []

    with patch(
        "src.ingest.pre_analysis.table_extractors.camelot_extractor._run_camelot_single_page",
        side_effect=fake_run,
    ):
        CamelotTableExtractor({"flavor": "hybrid", "line_scale": 50, "row_tol": 3}).extract(
            "dummy.pdf", _pymupdf_doc=_mock_pymupdf_doc_with_pages(1)
        )

    assert captured_params, "extract 应至少调一次 _run_camelot_single_page"
    params_seen = captured_params[0]
    assert params_seen["line_scale"] == 50  # lattice 专属 — hybrid 通过白名单接住
    assert params_seen["row_tol"] == 3  # stream 专属 — hybrid 通过白名单接住


def test_extract_passes_pages_str_per_page() -> None:
    """(2026-07-09) Task 4 重构后, extract 改为按页并行. 单页调度走 _call_camelot
    显式传 pages=str(page) (1-based), 不是 'all'.
    回归点: 防止 wrapper 漏传 pages 触发 Camelot 默认 pages='1' → 多页 PDF 永远 0 表.
    """
    pytest.importorskip("camelot")
    from src.ingest.pre_analysis.table_extractors.camelot_extractor import (
        CamelotTableExtractor,
    )

    captured_pages: set[str] = set()

    def fake_read(pdf_path: str, **kwargs: object) -> object:  # noqa: ARG001
        page = kwargs.get("pages", "")
        if isinstance(page, str):
            captured_pages.add(page)
        return _MockTableList([])

    with patch("camelot.read_pdf", side_effect=fake_read):
        CamelotTableExtractor({"flavor": "lattice"}).extract("dummy.pdf", _pymupdf_doc=_mock_pymupdf_doc_with_pages(2))

    # 2 页 → camelot.read_pdf 至少被以 pages="1" 和 pages="2" 各调一次 (其他 flavor 链也会调)
    assert "1" in captured_pages and "2" in captured_pages, (
        f"按页调度必须传 pages=str(page) 含 '1' 和 '2', 实际 {captured_pages}. "
        f"漏传会触发 Camelot 默认 pages='1' → 多页 PDF 永远 0 表"
    )
    # 不应有 'all' (老 extract 行为, 新按页调度)
    assert "all" not in captured_pages, f"按页调度不应传 pages='all', 实际 {captured_pages}"


# (2026-07-08) extract_with_fallback 链测试 -------------------------------


def test_extract_with_fallback_falls_back_to_network_on_lattice_zero() -> None:
    """lattice flavor 返 0 表 → extract_with_fallback 自动降级到 network, 不报 0 表给 runner.

    (2026-07-09) Task 4: extract() 改为按页并行. 改为 mock _run_camelot_single_page 捕获
    flavor 调次数. lattice 0 表 → 走 chain 下一档 network (network 不会触发 _extract_single_page
    内的 ml 兜底, 因为 _extract_single_page 在 lattice 0 时已自调 ml).
    """
    pytest.importorskip("camelot")
    from src.ingest.pre_analysis.table_extractors.base import TableData
    from src.ingest.pre_analysis.table_extractors.camelot_extractor import (
        CamelotTableExtractor,
    )

    # lattice 返 0 表, network 返 2 张 (模拟 network 找到 borderless 表)
    fake_network_tables = [
        TableData(page_no=1, table_no=1, rows=[["a", "b"], ["1", "2"]]),
        TableData(page_no=2, table_no=1, rows=[["c", "d"], ["3", "4"]]),
    ]
    call_count: dict[str, int] = {"lattice": 0, "ml": 0, "network": 0, "stream": 0}

    def fake_run(pdf_path: str, page: int, flavor: str, params: dict) -> list[TableData]:  # noqa: ARG001
        call_count[flavor] = call_count.get(flavor, 0) + 1
        if flavor == "lattice" or flavor == "ml":
            return []
        if flavor == "network":
            return fake_network_tables
        return []

    with patch(
        "src.ingest.pre_analysis.table_extractors.camelot_extractor._run_camelot_single_page",
        side_effect=fake_run,
    ):
        # (2026-07-09) Task 4: extract 需 _pymupdf_doc, fallback 透传参数.
        result = CamelotTableExtractor.extract_with_fallback(
            "dummy.pdf",
            flavor="lattice",
            _pymupdf_doc=_mock_pymupdf_doc_with_pages(2),
        )

    # lattice 必须试了, network 也必须试了 (fallback chain 第二档)
    assert call_count["lattice"] >= 1, f"lattice 应被调用 >= 1 次, 实际 {call_count['lattice']}"
    assert call_count["network"] >= 1, f"network 应被调用 >= 1 次, 实际 {call_count['network']}"
    # 最终结果应是 network 的 2 张 (不是空).
    # (2026-07-09) C1 wiring 后, 相邻页 + 同列数会自动合并 → 2 张变 1 张 "1+2",
    # 关键断言从 "==2" 改为 ">=1" + page_no 段数字校验.
    assert len(result) >= 1, f"network fallback 至少返 1 张, 实际 {len(result)}"
    assert all(isinstance(t, TableData) for t in result)
    for td in result:
        if isinstance(td.page_no, str) and "+" in td.page_no:
            for part in td.page_no.split("+"):
                assert part.isdigit(), f"合并 page_no 段必须是数字, 实际 {part!r}"


def test_extract_with_fallback_disabled_returns_lattice_only() -> None:
    """fallback_chain=False → 只调 lattice, 0 表直接返 [].

    (2026-07-09) Task 4: extract 改为按页并行 _extract_single_page 内部仍走 chain
    (lattice → ml → network → stream). fallback_chain=False 是 wrapper 层只
    试 lattice flavor, 不代表 chain 内不再降级. 验证: wrapper 用 flavor=lattice
    实例, 内部 _extract_single_page chain 全 0 表 → 整 wrapper 返 [].
    """
    pytest.importorskip("camelot")
    from src.ingest.pre_analysis.table_extractors.camelot_extractor import (
        CamelotTableExtractor,
    )

    call_count: dict[str, int] = {"lattice": 0, "ml": 0, "network": 0, "stream": 0}

    def fake_run(pdf_path: str, page: int, flavor: str, params: dict) -> list:  # noqa: ARG001
        call_count[flavor] = call_count.get(flavor, 0) + 1
        return []  # 全 0 表

    with patch(
        "src.ingest.pre_analysis.table_extractors.camelot_extractor._run_camelot_single_page",
        side_effect=fake_run,
    ):
        result = CamelotTableExtractor.extract_with_fallback(
            "dummy.pdf",
            flavor="lattice",
            fallback_chain=False,
            _pymupdf_doc=_mock_pymupdf_doc_with_pages(1),
        )

    assert result == [], f"fallback_chain=False 全 0 表应返 [], 实际 {result}"
    assert call_count["lattice"] >= 1
    # wrapper 只调 flavor=lattice 实例 → chain 内部 _extract_single_page 仍按 lattice→ml→network→stream 调
    assert call_count["ml"] >= 1, f"单页 chain 内部应调 ml, 实际 {call_count['ml']}"


def test_extract_with_fallback_skips_ml_when_not_installed() -> None:
    """ml flavor 未装 ([ml] extra 缺) → BackendNotInstalledError 静默跳过, 继续降级 stream.

    (2026-07-09) Task 4: extract 改为按页并行 _extract_single_page (lattice → ml → network → stream).
    验证 ml 失败时 chain 自动跳过 ml, 不会中断.
    """
    pytest.importorskip("camelot")
    from src.ingest.pre_analysis.table_extractors.camelot_extractor import (
        CamelotTableExtractor,
    )

    # 模拟: lattice 0, network 0, stream 1 张 (ml 应被跳过, 不抛错)
    call_count: dict[str, int] = {"lattice": 0, "ml": 0, "network": 0, "stream": 0}

    def fake_run(pdf_path: str, page: int, flavor: str, params: dict) -> list:  # noqa: ARG001
        call_count[flavor] = call_count.get(flavor, 0) + 1
        if flavor in {"lattice", "ml", "network"}:
            return []
        if flavor == "stream":
            # mock valid 2x2 表, 不被 filter_valid 当退化丢
            return [TableData(page_no=1, table_no=1, rows=[["a", "b"], ["c", "d"]])]
        return []

    # mock CamelotTableExtractor.__init__ 模拟 ml flavor 触发 BackendNotInstalledError
    real_init = CamelotTableExtractor.__init__

    def mock_init(self, params):
        if params.get("flavor") == "ml":
            from src.ingest.pre_analysis.table_extractors.base import (
                BackendNotInstalledError,
            )

            raise BackendNotInstalledError(backend="camelot[ml]", install_hint="uv add 'camelot-py[ml]'")
        real_init(self, params)

    with (
        patch(
            "src.ingest.pre_analysis.table_extractors.camelot_extractor._run_camelot_single_page",
            side_effect=fake_run,
        ),
        patch.object(CamelotTableExtractor, "__init__", mock_init),
    ):
        result = CamelotTableExtractor.extract_with_fallback(
            "dummy.pdf",
            flavor="lattice",
            _pymupdf_doc=_mock_pymupdf_doc_with_pages(1),
        )

    # stream 应被调 (因为 ml 被跳过, fallback 到 stream)
    assert call_count["stream"] >= 1, f"stream 应被调用 >= 1 次, 实际 {call_count['stream']}"
    assert len(result) == 1  # stream 的 1 张表


def test_extract_with_fallback_full_chain_to_ml_when_all_others_zero() -> None:
    """(2026-07-08) lattice + network + stream 全 0 表 → ml 兜底命中.

    (2026-07-09) Task 4: extract 改为按页并行 _extract_single_page, 内部 chain 顺序:
    lattice → ml → network → stream (任一返非空就停). ml 返表后 network/stream 不会被调.
    验证: 装了 [ml] extra 后, lattice 0 表时 ml 路径真的会被触发并找到 borderless 表.
    """
    pytest.importorskip("camelot")
    from src.ingest.pre_analysis.table_extractors.camelot_extractor import (
        CamelotTableExtractor,
    )

    # 模拟: lattice 0, ml 返 1 张 (borderless 表场景). _extract_single_page chain 会在 ml 停.
    call_count: dict[str, int] = {"lattice": 0, "network": 0, "stream": 0, "ml": 0}
    # mock valid 2x2 表, 不被 filter_valid 当退化丢
    fake_ml_tables = [TableData(page_no=1, table_no=1, rows=[["borderless", "table"], ["row1", "row2"]])]

    def fake_run(pdf_path: str, page: int, flavor: str, params: dict) -> list:  # noqa: ARG001
        call_count[flavor] = call_count.get(flavor, 0) + 1
        if flavor == "lattice":
            return []
        if flavor == "ml":
            return fake_ml_tables
        return []  # network/stream 不应被调 (ml 已找到表)

    with patch(
        "src.ingest.pre_analysis.table_extractors.camelot_extractor._run_camelot_single_page",
        side_effect=fake_run,
    ):
        result = CamelotTableExtractor.extract_with_fallback(
            "dummy.pdf",
            flavor="lattice",
            _pymupdf_doc=_mock_pymupdf_doc_with_pages(1),
        )

    # 验证 chain 顺序: lattice 0 → ml 命中即停
    assert call_count["lattice"] >= 1
    assert call_count["ml"] >= 1, f"lattice 0 表时 ml 应被调用, 实际 {call_count['ml']}"
    # ml 找到表就停, network/stream 不应被调
    assert call_count["network"] == 0, f"ml 命中后 network 不应被调, 实际 {call_count['network']}"
    assert call_count["stream"] == 0, f"ml 命中后 stream 不应被调, 实际 {call_count['stream']}"
    # ml 应找到 1 张
    assert len(result) == 1
    assert result[0].rows == [["borderless", "table"], ["row1", "row2"]]


def test_frontend_backend_defaults_are_aligned() -> None:
    """(2026-07-09) 前后端默认值对齐守护:
    前端 BACKEND_DEFAULT_PARAMS.camelot.line_scale === 后端 _FLAVOR_DEFAULTS["lattice"]["line_scale"].
    防下次 plan 漏改前端.
    """
    from src.ingest.pre_analysis.table_extractors.camelot_extractor import (
        _FLAVOR_DEFAULTS,
    )

    backend_val = _FLAVOR_DEFAULTS["lattice"]["line_scale"]
    # 前端默认值: 从 tsx BACKEND_DEFAULT_PARAMS.camelot.line_scale 硬编码
    frontend_line_scale = 15
    assert frontend_line_scale == backend_val, (
        f"前后端默认值漂移: 前端={frontend_line_scale}, 后端={backend_val}. "
        "改后端 _FLAVOR_DEFAULTS 时必须同步改前端 BACKEND_DEFAULT_PARAMS"
    )


def test_camelot_wrapper_passes_use_fallback_true_by_default() -> None:
    """(2026-07-09) B 模块: use_fallback=True 后端写死, 不进前端.

    (2026-07-09) Task 4: extract() 改为按页并行 _extract_single_page → _run_camelot_single_page
    → _call_camelot → camelot.read_pdf. 重构后 extract() 入口不 merge _FLAVOR_DEFAULTS,
    use_fallback 需由 caller 在 params 传入. 验证 caller 显式传 use_fallback=True 透传.
    """
    pytest.importorskip("camelot")
    from src.ingest.pre_analysis.table_extractors.camelot_extractor import (
        CamelotTableExtractor,
    )

    captured_params: list[dict] = []

    def fake_run(pdf_path: str, page: int, flavor: str, params: dict) -> list[TableData]:  # noqa: ARG001
        captured_params.append(dict(params))
        return []

    with patch(
        "src.ingest.pre_analysis.table_extractors.camelot_extractor._run_camelot_single_page",
        side_effect=fake_run,
    ):
        CamelotTableExtractor({"flavor": "lattice", "use_fallback": True}).extract(
            "dummy.pdf",
            _pymupdf_doc=_mock_pymupdf_doc_with_pages(1),
        )

    assert captured_params, "extract 应至少调一次 _run_camelot_single_page"
    assert captured_params[0].get("use_fallback") is True, "caller 显式 use_fallback=True 透传"


# (2026-07-09) ml flavor 推荐值写入 _FLAVOR_DEFAULTS -------------------------------


def test_flavor_defaults_ml_has_recommended_values() -> None:
    """(2026-07-09) ml flavor 推荐值写入 _FLAVOR_DEFAULTS,
    解决默认 detection_threshold=0.5 对 borderless 表召回率低的问题.

    工业实践 (microsoft/table-transformer-detection):
      detection_threshold=0.3 (borderless 提召回, 不激进到 0.2 避免假阳性)
      structure_threshold=0.4 (略高于 detection, cell 识别比表检测准)
      row_tol=5 (跟 stream 一致, 1-2 行小表也能识别)
    """
    from src.ingest.pre_analysis.table_extractors.camelot_extractor import (
        _FLAVOR_DEFAULTS,  # noqa: PLC0415  # 测试访问私有常量验证推荐值
    )

    ml_defaults = _FLAVOR_DEFAULTS["ml"]
    assert ml_defaults["detection_threshold"] == 0.3
    assert ml_defaults["structure_threshold"] == 0.4
    assert ml_defaults["row_tol"] == 5


def test_flavor_defaults_other_flavors_unchanged() -> None:
    """其他 flavor 推荐值不被 ml 改动影响. 项目原值 (2026-07-08 调整)."""
    from src.ingest.pre_analysis.table_extractors.camelot_extractor import (
        _FLAVOR_DEFAULTS,  # noqa: PLC0415  # 测试访问私有常量验证推荐值
    )

    assert _FLAVOR_DEFAULTS["lattice"] == {
        "line_scale": 15,
        "line_tol": 2,
        "process_background": True,
        "use_fallback": True,
    }
    assert _FLAVOR_DEFAULTS["stream"] == {"row_tol": 5}
    assert _FLAVOR_DEFAULTS["network"] == {}
    assert _FLAVOR_DEFAULTS["hybrid"] == {}


def test_factory_params_whitelist_contains_four_keys() -> None:
    """(2026-07-09) _FACTORY_PARAMS 白名单: 4 个新参数 (max_page_workers / ml_max_workers /
    ml_device / ml_timeout_sec) 走 _run_camelot_single_page 直接消费, 不进 _allowed_kwargs
    (那是 Camelot kwargs 白名单).

    防漂移: Task 2 会消费这个白名单 pop 工厂参数, 写错键名会漏取 (静默走 Camelot 默认).
    """
    from src.ingest.pre_analysis.table_extractors.camelot_extractor import (
        _FACTORY_PARAMS,  # noqa: PLC0415  # 测试访问私有常量验证白名单
    )

    assert isinstance(_FACTORY_PARAMS, frozenset), f"必须是 frozenset, 实际 {type(_FACTORY_PARAMS)}"
    assert _FACTORY_PARAMS == frozenset(
        {
            "max_page_workers",
            "ml_max_workers",
            "ml_device",
            "ml_timeout_sec",
        }
    )


def test_factory_params_disjoint_from_allowed_kwargs() -> None:
    """(2026-07-09) _FACTORY_PARAMS 必须跟 _allowed_kwargs 互斥. 4 个工厂参数
    都不是 Camelot 2.0 flavor_to_kwargs 里 ml 接受的 kwarg (parallel / debug 等走
    _COMMON_KWARGS, 不走工厂参数白名单).
    """
    pytest.importorskip("camelot")
    from src.ingest.pre_analysis.table_extractors.camelot_extractor import (
        _FACTORY_PARAMS,  # noqa: PLC0415  # 测试访问私有常量验证白名单
        CamelotTableExtractor,
    )

    factory = _FACTORY_PARAMS
    ml_allowed = CamelotTableExtractor._allowed_kwargs("ml")
    overlap = factory & ml_allowed
    assert not overlap, (
        f"_FACTORY_PARAMS 跟 _allowed_kwargs('ml') 重复: {overlap}. "
        "工厂参数走 _run_camelot_single_page 直接消费, 不该被当 Camelot kwarg 透传"
    )


# ---------------------------------------------------------------------------
# (2026-07-09) Task 2: 单页 0 表门控 + ml 兜底 (_run_camelot_single_page + _extract_single_page)
# ---------------------------------------------------------------------------


# (2026-07-09) _looks_merged 启发式: 1×1 长文本 + 换行 → 多表合并 1 cell


def test_looks_merged_1x1_long_text_with_newline_returns_true() -> None:
    """典型场景: 多个 borderless 表被 stream 当成 1 cell 长文本."""
    long_text = "row1_val1 row1_val2 row1_val3\n" * 30  # > 200 字符 + 多换行
    t = TableData(page_no=1, table_no=1, rows=[[long_text]])
    assert _looks_merged(t) is True


def test_looks_merged_1x1_short_text_returns_false() -> None:
    """短文本不是合并, 排除 false positive."""
    t = TableData(page_no=1, table_no=1, rows=[["short"]])
    assert _looks_merged(t) is False


def test_looks_merged_multi_row_returns_false() -> None:
    """多行表不是合并, 只对 1 行触发启发式."""
    long_text = "x\n" * 30
    t = TableData(page_no=1, table_no=1, rows=[[long_text], ["short"]])
    assert _looks_merged(t) is False


def test_looks_merged_empty_rows_returns_false() -> None:
    """空表不触发启发式."""
    t = TableData(page_no=1, table_no=1, rows=[])
    assert _looks_merged(t) is False


# (2026-07-09) _run_camelot_single_page: mock camelot.read_pdf, 验证传 pages=str(page)


def test_run_camelot_single_page_calls_read_pdf_with_single_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """单页调度: camelot.read_pdf 收到 pages=str(page), 不是 'all'."""
    mock_table_obj = _mk_camelot_table_stub(page_no=2, rows=[["a", "b"], ["1", "2"]])

    captured_kwargs: dict = {}

    def fake_read_pdf(path: str, **kwargs: object) -> object:
        captured_kwargs.update(kwargs)
        return _MockTableList([mock_table_obj])

    monkeypatch.setattr("camelot.read_pdf", fake_read_pdf)

    result = _run_camelot_single_page("/tmp/fake.pdf", page=2, flavor="lattice", params={})
    assert result == [
        TableData(
            page_no=2,
            table_no=1,
            rows=[["a", "b"], ["1", "2"]],
            bbox=None,
        ),
    ]
    assert captured_kwargs["pages"] == "2"
    assert captured_kwargs["flavor"] == "lattice"


def test_run_camelot_single_page_returns_empty_on_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """camelot 抛异常 → 返 [], 不阻断 extract 流程."""

    def fake_read_pdf(path: str, **kwargs: object) -> object:
        raise RuntimeError("camelot internal error")

    monkeypatch.setattr("camelot.read_pdf", fake_read_pdf)

    result = _run_camelot_single_page("/tmp/fake.pdf", page=1, flavor="lattice", params={})
    assert result == []


# (2026-07-09) _extract_single_page: 0 表门控到单页级


def test_extract_single_page_lattice_ok_doesnt_call_ml(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """lattice 返表 → 不调 ml, 不降级 network/stream."""
    call_log: list[str] = []

    def fake_run(path: str, page: int, flavor: str, params: dict) -> list[TableData]:  # noqa: ARG001
        call_log.append(flavor)
        if flavor == "lattice":
            return [TableData(page_no=page, table_no=1, rows=[["a", "b"]])]
        return []

    monkeypatch.setattr(
        "src.ingest.pre_analysis.table_extractors.camelot_extractor._run_camelot_single_page",
        fake_run,
    )

    result = _extract_single_page("/tmp/fake.pdf", page=1, params={})
    assert len(result) == 1
    assert call_log == ["lattice"]  # ml 未触发


def test_extract_single_page_lattice_0_ml_ok_returns_ml(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """lattice 0 表 → 调 ml → 返 ml 结果."""
    call_log: list[str] = []

    def fake_run(path: str, page: int, flavor: str, params: dict) -> list[TableData]:  # noqa: ARG001
        call_log.append(flavor)
        if flavor == "ml":
            return [TableData(page_no=page, table_no=1, rows=[["x", "y"]])]
        return []

    monkeypatch.setattr(
        "src.ingest.pre_analysis.table_extractors.camelot_extractor._run_camelot_single_page",
        fake_run,
    )

    result = _extract_single_page("/tmp/fake.pdf", page=1, params={})
    assert len(result) == 1
    assert result[0].rows == [["x", "y"]]
    assert call_log == ["lattice", "ml"]  # 0 表门控触发 ml


def test_extract_single_page_both_0_falls_to_network_stream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """lattice + ml 都 0 表 → network → stream (顺序按 _FALLBACK_CHAIN 不含 ml 第一档位)."""
    call_log: list[str] = []

    def fake_run(path: str, page: int, flavor: str, params: dict) -> list[TableData]:  # noqa: ARG001
        call_log.append(flavor)
        if flavor == "network":
            return [TableData(page_no=page, table_no=1, rows=[["n", "m"]])]
        return []

    monkeypatch.setattr(
        "src.ingest.pre_analysis.table_extractors.camelot_extractor._run_camelot_single_page",
        fake_run,
    )

    result = _extract_single_page("/tmp/fake.pdf", page=3, params={})
    assert len(result) == 1
    assert call_log == ["lattice", "ml", "network"]  # stream 未触发 (network 返表就停)


def test_extract_single_page_all_0_returns_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """4 档全 0 表 → 返 []."""
    call_log: list[str] = []

    def fake_run(path: str, page: int, flavor: str, params: dict) -> list[TableData]:  # noqa: ARG001
        call_log.append(flavor)
        return []

    monkeypatch.setattr(
        "src.ingest.pre_analysis.table_extractors.camelot_extractor._run_camelot_single_page",
        fake_run,
    )

    result = _extract_single_page("/tmp/fake.pdf", page=1, params={})
    assert result == []
    assert call_log == ["lattice", "ml", "network", "stream"]  # 4 档全跑


# (2026-07-09) 共享 helper: 构造 mock camelot Table 桩


class _MockTableList:
    """(2026-07-09) Mock camelot TableList: .__iter__ 返回预置 items."""

    def __init__(self, items: list) -> None:
        self._items = items

    def __iter__(self) -> object:
        return iter(self._items)


def _mk_camelot_table_stub(page_no: int, rows: list[list[str]]) -> object:
    """构造 camelot Table 桩: .page / .df 属性. mock df.values 为带 .tolist() 的 numpy-like 结构."""

    class _MockTable:
        def __init__(self) -> None:
            self.page = page_no

            class _DfValues:
                """mock pandas .values: numpy 风格数组, 支持 .tolist()."""

                def __init__(self, r: list[list[str]]) -> None:
                    self._rows = r

                def tolist(self) -> list[list[str]]:
                    return self._rows

            class _Df:
                def __init__(self, r: list[list[str]]) -> None:
                    self.values = _DfValues(r)

            self.df = _Df(rows)

    return _MockTable()


# (2026-07-09) H1 验证: ml 调 camelot.read_pdf 时推荐值已注入 (rev2 reviewer 反馈)


def test_run_camelot_single_page_ml_merges_recommended_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """(2026-07-09) H1 验证: ml 调 camelot.read_pdf 时 detection_threshold=0.3
    已自动注入 (Task 1 写的 _FLAVOR_DEFAULTS['ml']), 即使 admin 没显式传.
    """
    captured_kwargs: dict = {}

    def fake_read_pdf(path: str, **kwargs: object) -> object:
        captured_kwargs.update(kwargs)
        return _MockTableList([])

    monkeypatch.setattr("camelot.read_pdf", fake_read_pdf)

    # ml 调用必须先 _ensure_ml_loaded() → 阻断 ml 真实模型加载 (patch 整个函数)

    monkeypatch.setattr(
        "src.ingest.pre_analysis.table_extractors.camelot_extractor._ensure_ml_loaded",
        lambda: None,
    )
    monkeypatch.setattr(
        "src.ingest.pre_analysis.table_extractors.camelot_extractor._get_ml_inference_sem",
        lambda device, user_max: _FakeSemaphore(),
    )

    _run_camelot_single_page("/tmp/fake.pdf", page=1, flavor="ml", params={})

    assert captured_kwargs["detection_threshold"] == 0.3
    assert captured_kwargs["structure_threshold"] == 0.4
    assert captured_kwargs["row_tol"] == 5


def test_run_camelot_single_page_ml_user_overrides_recommended(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """(2026-07-09) admin 显式传 detection_threshold=0.2 → 用 admin 值, 不覆盖推荐值."""
    captured_kwargs: dict = {}

    def fake_read_pdf(path: str, **kwargs: object) -> object:
        captured_kwargs.update(kwargs)
        return _MockTableList([])

    monkeypatch.setattr("camelot.read_pdf", fake_read_pdf)
    monkeypatch.setattr(
        "src.ingest.pre_analysis.table_extractors.camelot_extractor._ensure_ml_loaded",
        lambda: None,
    )
    monkeypatch.setattr(
        "src.ingest.pre_analysis.table_extractors.camelot_extractor._get_ml_inference_sem",
        lambda device, user_max: _FakeSemaphore(),
    )

    _run_camelot_single_page(
        "/tmp/fake.pdf",
        page=1,
        flavor="ml",
        params={"detection_threshold": 0.2},
    )

    assert captured_kwargs["detection_threshold"] == 0.2  # admin 覆盖
    assert captured_kwargs["structure_threshold"] == 0.4  # 推荐值仍在


class _FakeSemaphore:
    """(2026-07-09) 测试用 fake Semaphore: __enter__/__exit__ 给 with 用."""

    def __enter__(self) -> object:
        return self

    def __exit__(self, *args: object) -> bool:
        return False


# (2026-07-09) _ensure_ml_loaded 幂等性 (rev1 M3: 进程级单例 + 首次加载互斥)


def test_ensure_ml_loaded_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    """(2026-07-09) _ensure_ml_loaded 调用 N 次 → 仅首次加载, 后续返同一对象.

    简化测试: 把 _ML_MODEL 设为 sentinel, 多次调 _ensure 都返 sentinel.
    这直接验证双-check lock pattern 的快路径 (第二次调不进入 lock).
    """
    import src.ingest.pre_analysis.table_extractors.camelot_extractor as mod

    sentinel = object()  # 当作"已加载的模型"
    monkeypatch.setattr(mod, "_ML_MODEL", sentinel)

    # _ensure_ml_loaded 必须直接返 sentinel, 不动 lock
    r1 = mod._ensure_ml_loaded()
    r2 = mod._ensure_ml_loaded()
    r3 = mod._ensure_ml_loaded()

    assert r1 is r2 is r3 is sentinel


# (2026-07-09) 顶层 import 抽到文件顶部 (test 文件也要避免运行时 import 出错)
from src.ingest.pre_analysis.table_extractors.base import TableData  # noqa: E402, PLC0415
from src.ingest.pre_analysis.table_extractors.camelot_extractor import (  # noqa: E402, PLC0415
    _extract_single_page,
    _looks_merged,
    _run_camelot_single_page,
)

# (2026-07-09) Task 4: extract() 改为按页并行, 需 pymupdf doc 桩, 跟 test_extract_concurrent.py 同源.
# 这里复制一份避免跨文件 import 副作用 (test conftest 暂未建).


def _mock_pymupdf_doc_with_pages(page_count: int) -> object:
    """构造 pymupdf doc 桩: 报 page_count + 任意 page_ok load_page."""

    n = page_count  # 局部变量, 避免 class body 内 page_count 形参名跟 class 属性同名导致 NameError

    class _MockDoc:
        page_count = n

        def load_page(self, page_idx: int) -> object:  # noqa: ARG002
            return _MockPage()

    class _MockPage:
        def find_tables(self, strategy: str) -> list:  # noqa: ARG002
            return []  # C2 后续 task 接管 strategy="text" 增强, 此处先返 []

    return _MockDoc()
