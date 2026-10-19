"""ProductDecoder 测试用例

真实 Siemens 1LE0 16 字符型号: 1LE0001-1AA42-1AA4
3 段 display (按 display_separators=[7, 12]): 1LE0001 / 1AA42 / 1AA4
YAML value 全部 {code, zh, en} dict 形式
支持容错: 型号带后缀 (如 -Z F40) 自动截取前 16 字符
"""

from pathlib import Path

import pytest

from src.core.app_factory import create_app
from src.product_decoders import ConfigLoader, ProductDecoder

# 仓库根 = tests/product_decoders/ 的 parent.parent.parent
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIGS_DIR = REPO_ROOT / "configs" / "product_decoders"


def make_decoder() -> ProductDecoder:
    """构造一个 ProductDecoder, 用绝对路径指向新的 configs 目录"""
    loader = ConfigLoader(config_dir=str(CONFIGS_DIR))
    return ProductDecoder(loader)


# ---------- T1: 完整解码 ----------
def test_decode_siemens_1le0_full():
    """16 字符型号完整解码, 验证所有 code 字段和 display 字段 (真实厂商写法 3 段)"""
    decoder = make_decoder()
    result = decoder.decode("1LE0001-1AA42-1AA4")

    assert result["series"] == "siemens_1le0_low_voltage"
    assert result["manufacturer"] == "Siemens"
    assert result["prefix"] == "1LE000"
    # efficiency_grade: 唯一值是 "1" (EFF3), 主值取 code; _zh 是完整中文
    assert result["efficiency_grade"] == "EFF3"
    assert "高效" in result["efficiency_grade_zh"]
    # frame_size: 1A -> code=100
    assert result["frame_size"] == 100
    assert result["frame_size_raw"] == "1A"
    # poles: A -> code=2
    assert result["poles"] == 2
    assert result["poles_raw"] == "A"
    # frame_length: 4 -> code=L
    assert result["frame_length"] == "L"
    # voltage: 21 -> code="220VD/380VY/50" (用户手动选 VD/VY 表示, 避开 △ 的 console 编码坑)
    assert result["voltage"] == "220VD/380VY/50"
    # mounting: A -> code="IM B3"
    assert result["mounting"] == "IM B3"
    # winding_protection: A -> code="NONE"
    assert result["winding_protection"] == "NONE"
    # box_location: 4 -> code="TOP"
    assert result["box_location"] == "TOP"
    # display: 真实厂商 3 段写法 (display_separators=[7, 12])
    assert result["display"] == "1LE0001-1AA42-1AA4"


# ---------- T2: 未知 enum value ----------
def test_decode_with_unknown_value():
    """电压位 99 未知 -> 进 _warnings, HTTP 200, voltage 字段是 raw '99'"""
    decoder = make_decoder()
    result = decoder.decode("1LE0001-1AA4-99-AA4")

    assert "_warnings" in result
    assert any(w.get("name") == "voltage" for w in result["_warnings"])
    assert result["voltage_raw"] == "99"


# ---------- T3: 未知系列 ----------
def test_unknown_series():
    """完全无匹配前缀 -> ValueError"""
    decoder = make_decoder()
    with pytest.raises(ValueError, match="无法识别"):
        decoder.decode("XYZ12345678901234")


# ---------- T4: 长度错误 ----------
def test_length_error():
    """太短的型号 -> ValueError"""
    decoder = make_decoder()
    with pytest.raises(ValueError, match="长度"):
        decoder.decode("1LE0001-1A")


# ---------- T5: 列出所有系列 ----------
def test_list_series():
    """至少 1 个系列"""
    decoder = make_decoder()
    series_list = decoder.list_series()
    assert len(series_list) >= 1
    siemens = next(s for s in series_list if s["series"] == "siemens_1le0_low_voltage")
    assert siemens["manufacturer"] == "Siemens"
    assert siemens["prefix"] == "1LE000"


# ---------- T6: 输入标准化 ----------
def test_normalization_3_forms():
    """不同书写方式解析出相同 frame_size"""
    decoder = make_decoder()
    r1 = decoder.decode("1le0001-1aa42-1aa4")
    r2 = decoder.decode("1LE00011AA421AA4")
    r3 = decoder.decode("  1LE0001 1AA42 1AA4  ")
    assert r1["frame_size"] == r2["frame_size"] == r3["frame_size"] == 100


# ---------- T7: format_display 走 display_separators (优先) ----------
def test_format_display_with_separators():
    """传入 separators=[7, 12] -> 按 separator 位置插横线, 真实厂商 3 段写法"""
    positions = []  # 走 separators 路径时 positions 无关
    result = ProductDecoder.format_display("1LE00011AA421AA4", positions, separators=[7, 12])
    assert result == "1LE0001-1AA42-1AA4"


# ---------- T8: format_display 降级走 group 字段 ----------
def test_format_display_with_group():
    """无 separators, positions 含 group 1-4 -> 按 group 边界插横线 (4 段)"""
    positions = [
        {"char_count": 6, "group": 1},
        {"char_count": 1, "group": 1},
        {"char_count": 2, "group": 2},
        {"char_count": 1, "group": 2},
        {"char_count": 1, "group": 2},
        {"char_count": 2, "group": 3},
        {"char_count": 1, "group": 4},
        {"char_count": 1, "group": 4},
        {"char_count": 1, "group": 4},
    ]
    result = ProductDecoder.format_display("1LE00011AA421AA4", positions)
    assert result == "1LE0001-1AA4-21-AA4"


# ---------- T9: format_display 无 separators 无 group (彻底降级) ----------
def test_format_display_no_separators_no_group():
    """无 separators 且 positions 缺 group -> 不插横线, 直接返回 normalized"""
    positions = [
        {"char_count": 6},
        {"char_count": 1},
        {"char_count": 2},
        {"char_count": 1},
        {"char_count": 1},
        {"char_count": 2},
        {"char_count": 1},
        {"char_count": 1},
        {"char_count": 1},
    ]
    result = ProductDecoder.format_display("1LE00011AA421AA4", positions)
    assert result == "1LE00011AA421AA4"


# ---------- T10: create_app 在任意 CWD 下能找到 configs ----------
def test_create_app_loads_configs_from_any_cwd(tmp_path, monkeypatch):
    """切到临时目录后调 create_app() 不能因为相对路径失败"""
    monkeypatch.chdir(tmp_path)
    app = create_app()  # 不抛异常 = 通过
    assert app is not None
    from fastapi.testclient import TestClient

    client = TestClient(app)
    resp = client.get("/product-decoder/health")
    assert resp.status_code == 200
    assert resp.json()["series_count"] >= 1


# ---------- T11: 每个 enum 位都出 _zh / _en ----------
def test_every_enum_position_emits_zh_en():
    """Bug #3 回归: 解析 1LE0001-1AA42-1AA4, 所有 enum 位的 _zh / _en 都非空"""
    decoder = make_decoder()
    result = decoder.decode("1LE0001-1AA42-1AA4")

    for field in [
        "efficiency_grade",
        "frame_size",
        "poles",
        "frame_length",
        "voltage",
        "mounting",
        "winding_protection",
        "box_location",
    ]:
        assert f"{field}_zh" in result, f"缺 {field}_zh 字段"
        assert f"{field}_en" in result, f"缺 {field}_en 字段"
        assert result[f"{field}_zh"], f"{field}_zh 是空字符串"
        assert result[f"{field}_en"], f"{field}_en 是空字符串"


# ---------- T12: 型号带后缀容错 ----------
def test_decode_with_suffix():
    """型号带 -Z F40 后缀 -> 截取前 16 字符, 后缀进 _suffix, display 用真实写法"""
    decoder = make_decoder()
    result = decoder.decode("1LE0001-1AA42-1AA4-Z F40")

    # 主体解析正确
    assert result["series"] == "siemens_1le0_low_voltage"
    assert result["frame_size"] == 100
    assert result["display"] == "1LE0001-1AA42-1AA4"
    # normalized 字段也被截到 16 字符
    assert result["normalized"] == "1LE00011AA421AA4"
    # 后缀进 _suffix
    assert result["_suffix"] == "ZF40"


# --- build_llm_view (Dify LLM 视图) ---


def test_llm_view_header_has_6_lines_then_separator():
    """头部 6 行 (code/厂商/系列 各 zh+en) + 一个 '---' 分隔"""
    decoder = make_decoder()
    result = decoder.decode("1LE0001-1AA42-1AA4")
    llm = decoder.build_llm_view(result)
    # 6 header lines (assert 真值, 不只 key 存在 — 防 厂商/系列 空值回归)
    assert "完整型号: 1LE0001-1AA42-1AA4" in llm
    assert "Full order code: 1LE0001-1AA42-1AA4" in llm
    # 厂商: cfg.manufacturer = "Siemens" (顶层字符串, 非 metadata.manufacturer 字典)
    assert "厂商: Siemens" in llm
    assert "Manufacturer: Siemens" in llm
    # 系列: cfg.series_name_zh/_en 顶层字符串
    assert "系列: 西门子低压系列三相异步电动机" in llm
    assert "Series: Siemens 1LE0 Low-voltage Motor Series" in llm
    # 第一个 '---' 在头部之后
    assert llm[6].strip() == "---"


def test_llm_view_segments_split_by_display():
    """1LE0 16 字符 → 3 段, 每段一个 [段 X] 头"""
    decoder = make_decoder()
    result = decoder.decode("1LE0001-1AA42-1AA4")
    llm = decoder.build_llm_view(result)
    seg_headers = [line for line in llm if line.startswith("[段 ")]
    assert len(seg_headers) == 3
    assert "[段 1LE0001]" in seg_headers
    assert "[段 1AA42]" in seg_headers
    assert "[段 1AA4]" in seg_headers


def test_llm_view_position_line_zh_en_pair():
    """position 渲染成 'name_zh: v_zh / name_en: v_en'"""
    decoder = make_decoder()
    result = decoder.decode("1LE0001-1AA42-1AA4")
    llm = decoder.build_llm_view(result)
    pos_lines = [
        line
        for line in llm
        if "/" in line
        and line.startswith("[段") is False
        and "---" not in line
        and ":" in line
        and not line.startswith("[WARN]")
    ]
    assert len(pos_lines) > 0
    for line in pos_lines:
        # 至少含一个 ' / ' 分隔符 (zh / en)
        assert " / " in line, f"line 缺 ' / ' 分隔: {line}"


def test_llm_view_warning_block_appended():
    """解码未知码 → 末尾 [WARN] 行, 数量 = _warnings 长度"""
    decoder = make_decoder()
    result = decoder.decode("1LE0001-1AA4-99-AA4")  # 99 是不在编码表
    assert len(result.get("_warnings", [])) > 0
    llm = decoder.build_llm_view(result)
    warn_lines = [line for line in llm if line.startswith("[WARN]")]
    assert len(warn_lines) == len(result["_warnings"])


def test_llm_view_unknown_value_shows_question_mark():
    """未知码 value 双语都是 '?'"""
    decoder = make_decoder()
    result = decoder.decode("1LE0001-1AA4-99-AA4")
    llm = decoder.build_llm_view(result)
    voltage_lines = [line for line in llm if "电压" in line or "Voltage" in line]
    assert voltage_lines, f"没找到电压行, llm: {llm}"
    # value 是 '? / ?'
    for line in voltage_lines:
        assert ": ? /" in line or ": ?" in line, f"未知码 value 应该是 '?', 实际: {line}"


def test_llm_view_no_display_separators_falls_back():
    """cfg 缺 display_separators → 仍产 llm_view, 不带段头 (不抛)"""
    decoder = make_decoder()
    result = decoder.decode("1LE0001-1AA42-1AA4")
    # 模拟 result display 缺失 (强制走降级)
    result.pop("display", None)
    llm = decoder.build_llm_view(result)
    assert isinstance(llm, list)
    assert len(llm) > 0
    # 段头不应有 (降级)
    assert not any(line.startswith("[段 ") for line in llm)


def test_llm_view_suffix_line_appended_to_header():
    """_suffix 非空时头部第 7 行 '后缀: <suffix>'"""
    decoder = make_decoder()
    # 16 字符之后的内容进 _suffix ('ZF40', 跟 raw model '1LE0001-1AA42-1AA4-Z F40' 标准化一致)
    result = decoder.decode("1LE0001-1AA42-1AA4-Z F40")
    # (2026-06-29) 之前 if/else + else: pytest.skip 是 dead branch (实际 _suffix 命中),
    # 改 assert 直接, 跟其他 test 一致
    assert result.get("_suffix"), f"期望 _suffix 非空, 实际 {result!r}"
    llm = decoder.build_llm_view(result)
    suffix_idx = next((i for i, line in enumerate(llm) if line.startswith("后缀:")), None)
    assert suffix_idx is not None, f"无 '后缀:' 行, llm: {llm}"
    assert llm[suffix_idx] == f"后缀: {result['_suffix']}"
    # '---' 在第 8 行 (index 7)
    assert llm[7].strip() == "---"


def test_llm_view_does_not_mutate_input():
    """build_llm_view 前后, 原 result 字典其他 key 数量不变"""
    decoder = make_decoder()
    result = decoder.decode("1LE0001-1AA42-1AA4")
    keys_before = set(result.keys())
    _ = decoder.build_llm_view(result)
    keys_after = set(result.keys())
    assert keys_before == keys_after, (
        f"build_llm_view 污染了 result: 多了 {keys_after - keys_before}, 少了 {keys_before - keys_after}"
    )
