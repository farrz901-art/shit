"""scripts/neo4j_import.py 单元测试

测试策略: 单元 + Mock, 不连真实 Neo4j. 真实端到端留给用户手动跑 import 验证.

测试数据用 _make_yaml_text() 生成最小版 1le0 yaml (8 个 enum position + 1 example),
通过 tmp_config_dir fixture 落到临时目录, 用项目内的 ConfigLoader + ProductDecoder 加载.
"""

import argparse
from pathlib import Path

import pytest

from src.product_decoders import ConfigLoader, ProductDecoder

# ---------- 测试 fixture ----------


def _make_yaml_text() -> str:
    """返回最小 1le0 yaml 字符串 (8 enum position + 1 example)

    example "1LE0001-1AA42-1AA4" 是 16 字符, 跟 total_chars=16 匹配.
    8 个 enum position 的 values 各含 1 个 key, 刚好覆盖 example 的 8 段编码.
    """
    return """\
series: test_1le0
manufacturer: TestBrand
series_name_zh: 测试系列
series_name_en: Test Series
version: "1.0"
source_doc: test fixture

router:
  prefix: "1LE000"
  pattern: "^1LE000"
  priority: 100

decoder:
  type: "positional"
  total_chars: 16
  display_separators: [7, 12]
  positions:
    - idx: 1
      name: prefix
      name_zh: 型号前缀
      name_en: Series prefix
      char_count: 6
      type: fixed
      value: "1LE000"
    - idx: 7
      name: efficiency_grade
      name_zh: 能效等级
      name_en: Efficiency grade
      char_count: 1
      type: enum
      values:
        "1": {code: "EFF3", zh: "高效", en: "High Efficiency"}
    - idx: 8
      name: frame_size
      name_zh: 机座号
      name_en: Frame size
      char_count: 2
      type: enum
      unit: mm
      values:
        "1A": {code: 100, zh: "100mm 机座", en: "100mm frame"}
    - idx: 10
      name: poles
      name_zh: 极数
      name_en: Number of poles
      char_count: 1
      type: enum
      values:
        A: {code: 2, zh: "2 极", en: "2 poles"}
    - idx: 11
      name: frame_length
      name_zh: 机座长度
      name_en: Frame length
      char_count: 1
      type: enum
      values:
        "4": {code: "L", zh: "长机座", en: "long"}
    - idx: 12
      name: voltage
      name_zh: 电压
      name_en: Voltage
      char_count: 2
      type: enum
      values:
        "21": {code: "220V/380V/50", zh: "220V/380V 50Hz", en: "220V/380V 50Hz"}
    - idx: 14
      name: mounting
      name_zh: 安装方式
      name_en: Mounting
      char_count: 1
      type: enum
      values:
        A: {code: "IM B3", zh: "IM B3 卧式", en: "IM B3"}
    - idx: 15
      name: winding_protection
      name_zh: 绕组保护
      name_en: Winding protection
      char_count: 1
      type: enum
      values:
        A: {code: "NONE", zh: "无", en: "none"}
    - idx: 16
      name: box_location
      name_zh: 接线盒位置
      name_en: Box location
      char_count: 1
      type: enum
      values:
        "4": {code: "TOP", zh: "置顶", en: "on top"}

examples:
  - raw: "1LE0001-1AA42-1AA4"
    description: "测试示例: 机座 100, 2 极, 长机座"
"""


@pytest.fixture
def tmp_config_dir(tmp_path):
    """创建临时 config 目录, 写入测试 yaml, 返回 (config_dir, loader, decoder)"""
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    yaml_path = config_dir / "test.yaml"
    yaml_path.write_text(_make_yaml_text(), encoding="utf-8")
    loader = ConfigLoader(config_dir=str(config_dir))
    decoder = ProductDecoder(loader)
    return config_dir, loader, decoder


# ---------- Group 1a: load_yamls ----------


def test_load_yamls_finds_yaml_files(tmp_config_dir):
    """临时目录有 1 个 yaml, load_yamls 加载它, 返回 1 个 dict"""
    from scripts.neo4j_import import load_yamls

    config_dir, _, _ = tmp_config_dir
    yamls = load_yamls(config_dir)
    assert len(yamls) == 1
    assert yamls[0]["series"] == "test_1le0"


def test_load_yamls_empty_dir(tmp_path):
    """空目录 → 空 list, 不抛"""
    from scripts.neo4j_import import load_yamls

    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    yamls = load_yamls(empty_dir)
    assert yamls == []


# ---------- Group 1b-d: yaml_to_graph_data 节点 (产品系列/技术参数/参数值) ----------


def test_yaml_to_nodes_series_count(tmp_config_dir):
    """1 个 yaml → 1 个产品系列节点"""
    from scripts.neo4j_import import load_yamls, yaml_to_graph_data

    config_dir, _, decoder = tmp_config_dir
    yamls = load_yamls(config_dir)
    data = yaml_to_graph_data(yamls, decoder)
    series_nodes = [n for n in data["nodes"] if "产品系列" in n["labels"]]
    assert len(series_nodes) == 1


def test_yaml_to_nodes_series_uses_name_zh_and_props(tmp_config_dir):
    """产品系列.name 是 series_name_zh, props 含 series_id"""
    from scripts.neo4j_import import load_yamls, yaml_to_graph_data

    config_dir, _, decoder = tmp_config_dir
    yamls = load_yamls(config_dir)
    data = yaml_to_graph_data(yamls, decoder)
    series_node = next(n for n in data["nodes"] if "产品系列" in n["labels"])
    assert series_node["name"] == "测试系列"
    assert series_node["props"]["series_id"] == "test_1le0"
    assert series_node["props"]["manufacturer"] == "TestBrand"


def test_yaml_to_nodes_param_count(tmp_config_dir):
    """8 个 enum position → 8 个技术参数节点"""
    from scripts.neo4j_import import load_yamls, yaml_to_graph_data

    config_dir, _, decoder = tmp_config_dir
    yamls = load_yamls(config_dir)
    data = yaml_to_graph_data(yamls, decoder)
    param_nodes = [n for n in data["nodes"] if "技术参数" in n["labels"]]
    assert len(param_nodes) == 8


def test_yaml_to_nodes_param_uses_name_zh(tmp_config_dir):
    """技术参数.name 是 name_zh"""
    from scripts.neo4j_import import load_yamls, yaml_to_graph_data

    config_dir, _, decoder = tmp_config_dir
    yamls = load_yamls(config_dir)
    data = yaml_to_graph_data(yamls, decoder)
    names = {n["name"] for n in data["nodes"] if "技术参数" in n["labels"]}
    assert "机座号" in names
    assert "极数" in names
    assert "电压" in names


def test_yaml_to_nodes_value_count(tmp_config_dir):
    """8 个 enum position 各 1 value → 去重后 5 个唯一 参数值节点 (raw key 跨 position 重复时合并)

    raw 重复: 'A' (poles/mounting/winding_protection) + '4' (frame_length/box_location) = 3 重复
    实际唯一: 1, 1A, A, 4, 21 = 5 个
    """
    from scripts.neo4j_import import load_yamls, yaml_to_graph_data

    config_dir, _, decoder = tmp_config_dir
    yamls = load_yamls(config_dir)
    data = yaml_to_graph_data(yamls, decoder)
    value_nodes = [n for n in data["nodes"] if "参数值" in n["labels"]]
    assert len(value_nodes) == 5
    names = {n["name"] for n in value_nodes}
    assert names == {"1", "1A", "A", "4", "21"}


def test_yaml_to_nodes_value_preserves_code(tmp_config_dir):
    """参数值.code 来自 values[i].code"""
    from scripts.neo4j_import import load_yamls, yaml_to_graph_data

    config_dir, _, decoder = tmp_config_dir
    yamls = load_yamls(config_dir)
    data = yaml_to_graph_data(yamls, decoder)
    v_1a = next(n for n in data["nodes"] if n["name"] == "1A")
    assert v_1a["props"]["code"] == 100
    assert v_1a["props"]["zh"] == "100mm 机座"


# ---------- Group 1e-h: yaml_to_graph_data 产品型号 + 4 类关系 ----------


def test_yaml_to_nodes_model_count(tmp_config_dir):
    """1 个 example → 1 个产品型号节点"""
    from scripts.neo4j_import import load_yamls, yaml_to_graph_data

    config_dir, _, decoder = tmp_config_dir
    yamls = load_yamls(config_dir)
    data = yaml_to_graph_data(yamls, decoder)
    model_nodes = [n for n in data["nodes"] if "产品型号" in n["labels"]]
    assert len(model_nodes) == 1


def test_yaml_to_nodes_model_uses_examples_raw(tmp_config_dir):
    """产品型号.name 是 examples[].raw"""
    from scripts.neo4j_import import load_yamls, yaml_to_graph_data

    config_dir, _, decoder = tmp_config_dir
    yamls = load_yamls(config_dir)
    data = yaml_to_graph_data(yamls, decoder)
    model_node = next(n for n in data["nodes"] if "产品型号" in n["labels"])
    assert model_node["name"] == "1LE0001-1AA42-1AA4"
    assert "测试示例" in model_node["props"]["description"]


def test_yaml_to_rels_belongsto_count(tmp_config_dir):
    """1 个 example × 1 series → 1 条 属于"""
    from scripts.neo4j_import import load_yamls, yaml_to_graph_data

    config_dir, _, decoder = tmp_config_dir
    yamls = load_yamls(config_dir)
    data = yaml_to_graph_data(yamls, decoder)
    belongs = [r for r in data["rels"] if r["type"] == "属于"]
    assert len(belongs) == 1
    assert belongs[0]["srcName"] == "1LE0001-1AA42-1AA4"
    assert belongs[0]["tgtName"] == "测试系列"


def test_yaml_to_rels_has_param_count(tmp_config_dir):
    """1 个 example × 8 enum pos → 8 条 具有参数"""
    from scripts.neo4j_import import load_yamls, yaml_to_graph_data

    config_dir, _, decoder = tmp_config_dir
    yamls = load_yamls(config_dir)
    data = yaml_to_graph_data(yamls, decoder)
    has_param = [r for r in data["rels"] if r["type"] == "具有参数"]
    assert len(has_param) == 8


def test_yaml_to_rels_param_value_and_param_of_counts(tmp_config_dir):
    """decode 出来 8 个 (param, value) 配对 → 8 参数值 + 8 参数对应"""
    from scripts.neo4j_import import load_yamls, yaml_to_graph_data

    config_dir, _, decoder = tmp_config_dir
    yamls = load_yamls(config_dir)
    data = yaml_to_graph_data(yamls, decoder)
    param_val = [r for r in data["rels"] if r["type"] == "参数值"]
    param_of = [r for r in data["rels"] if r["type"] == "参数对应"]
    assert len(param_val) == 8
    assert len(param_of) == 8


def test_yaml_decode_failure_skips_example(tmp_config_dir, capsys):
    """examples 里加一个无法解码的型号 → 跳过, 不阻塞其他"""
    from scripts.neo4j_import import load_yamls, yaml_to_graph_data

    config_dir, _, decoder = tmp_config_dir
    yamls = load_yamls(config_dir)
    # 加一个坏 example
    yamls[0]["examples"].append(
        {
            "raw": "BAD-MODEL-XXXXXXXX",
            "description": "故意坏",
        }
    )
    data = yaml_to_graph_data(yamls, decoder)
    # 只该有 1 个产品型号 (好的那个)
    model_nodes = [n for n in data["nodes"] if "产品型号" in n["labels"]]
    assert len(model_nodes) == 1
    # 警告应打印到 stderr (符合 Unix 惯例, 跟错误流分开)
    captured = capsys.readouterr()
    assert "BAD-MODEL-XXXXXXXX" in captured.err


# ---------- Group 3: build_cypher ----------


def test_build_cypher_contains_apoc_merge_node():
    """cypher 必须含 apoc.merge.node + UNWIND $nodes"""
    from scripts.neo4j_import import build_cypher

    cypher, _ = build_cypher(
        [{"labels": ["产品系列"], "name": "X", "props": {}}],
        [],
    )
    assert "apoc.merge.node" in cypher
    assert "UNWIND $nodes" in cypher


def test_build_cypher_contains_apoc_merge_relationship():
    """cypher 必须含 apoc.merge.relationship + UNWIND $rels"""
    from scripts.neo4j_import import build_cypher

    cypher, _ = build_cypher(
        [],
        [{"srcName": "A", "tgtName": "B", "type": "具有参数", "props": {}}],
    )
    assert "apoc.merge.relationship" in cypher
    assert "UNWIND $rels" in cypher


def test_build_cypher_params_separated():
    """$nodes 和 $rels 必须在 params 分开"""
    from scripts.neo4j_import import build_cypher

    nodes = [{"labels": ["产品系列"], "name": "X", "props": {"k": "v"}}]
    rels = [{"srcName": "X", "tgtName": "Y", "type": "属于", "props": {}}]
    _, params = build_cypher(nodes, rels)
    assert "nodes" in params
    assert "rels" in params
    assert params["nodes"] == nodes
    assert params["rels"] == rels


# ---------- Group 4: 表格渲染 ----------


def test_format_props_empty_shows_无():
    """空 dict → '无'"""
    from scripts.neo4j_import import format_props

    assert format_props({}) == "无"


def test_format_props_dict_shows_kv():
    """{k:v} → 'k: v, k: v'"""
    from scripts.neo4j_import import format_props

    assert format_props({"code": 100, "zh": "100mm 机座"}) == "code: 100, zh: 100mm 机座"


def test_render_node_table_chinese_ok():
    """tabulate 输出含中文不抛 UnicodeEncodeError"""
    from scripts.neo4j_import import render_node_table

    nodes = [
        {"name": "测试系列", "labels": ["产品系列"], "props": {"description": "..."}},
        {"name": "机座号", "labels": ["技术参数"], "props": {}},
        {"name": "1A", "labels": ["参数值"], "props": {"code": 100, "zh": "100mm 机座"}},
    ]
    out = render_node_table(nodes)
    assert "测试系列" in out
    assert "机座号" in out
    assert "code: 100" in out


def test_render_node_table_no_props_shows_无():
    """空 props 显示 '无'"""
    from scripts.neo4j_import import render_node_table

    out = render_node_table([{"name": "X", "labels": ["技术参数"], "props": {}}])
    assert "无" in out


def test_render_rel_table_format():
    """关系表格式正确"""
    from scripts.neo4j_import import render_rel_table

    rels = [{"srcName": "型号A", "tgtName": "系列B", "type": "属于", "props": {}}]
    out = render_rel_table(rels)
    assert "型号A" in out
    assert "系列B" in out
    assert "属于" in out


# ---------- Group 5a: Neo4jClient 基础 ----------


def test_neo4j_client_constructs_with_all_env(monkeypatch):
    """4 个 env 都设 → 构造成功"""
    from scripts.neo4j_import import Neo4jClient

    monkeypatch.setenv("NEO4J_URI", "neo4j+s://x")
    monkeypatch.setenv("NEO4J_USER", "neo4j")
    monkeypatch.setenv("NEO4J_PASSWORD", "pw")
    monkeypatch.setenv("NEO4J_DATABASE", "neo4j")
    # 不真连, 传 mock driver
    client = Neo4jClient(uri="neo4j+s://x", user="neo4j", password="pw", database="neo4j", driver=None)
    assert client.uri == "neo4j+s://x"
    assert client.user == "neo4j"
    assert client.password == "pw"
    assert client.database == "neo4j"


def test_neo4j_client_missing_env_raises(monkeypatch):
    """缺 NEO4J_PASSWORD → RuntimeError 提示具体哪个变量"""
    from scripts.neo4j_import import Neo4jClient

    monkeypatch.setenv("NEO4J_URI", "neo4j+s://x")
    monkeypatch.setenv("NEO4J_USER", "neo4j")
    monkeypatch.delenv("NEO4J_PASSWORD", raising=False)
    monkeypatch.setenv("NEO4J_DATABASE", "neo4j")
    with pytest.raises(RuntimeError, match="NEO4J_PASSWORD"):
        Neo4jClient.from_env()


# ---------- Group 2: dedup_against_neo4j ----------


def test_dedup_filters_existing_param(tmp_config_dir):
    """Neo4j 已有 '机座号' → 该节点被剔除 (rel 端点在 known space, 但 src 端点 new, 所以 (新型号→机座号) 保留)"""
    from scripts.neo4j_import import dedup_against_neo4j, load_yamls, yaml_to_graph_data

    config_dir, _, decoder = tmp_config_dir
    data = yaml_to_graph_data(load_yamls(config_dir), decoder)

    class MockClient:
        def existing_node_names(self, label):
            return {"机座号"} if label == "技术参数" else set()

    new_nodes, new_rels = dedup_against_neo4j(data, MockClient())
    names = {n["name"] for n in new_nodes}
    assert "机座号" not in names  # 节点被剔除
    # 但 新型号 → 机座号 的 rel 保留 (因为 src 端点是 new, 至少一端 new 就保留)
    rel_targets_with_model = [(r["tgtName"], r["type"]) for r in new_rels if r["srcName"] == "1LE0001-1AA42-1AA4"]
    assert ("机座号", "具有参数") in rel_targets_with_model  # 这条 rel 保留


def test_dedup_keeps_rels_from_new_model_to_existing_value(tmp_config_dir):
    """Bug 修复: 新型号 → 已存在的 value (如 'A' 已在 Neo4j), rel 必须保留

    场景: 1LE0001-1AA42-1AA4 的 winding_protection 是 'A', 但 'A' 已在 Neo4j
    (从其他系列的 poles). 修复前: dedup 把 (1LE0001→A) 丢了. 修复后保留.
    """
    from scripts.neo4j_import import dedup_against_neo4j, load_yamls, yaml_to_graph_data

    config_dir, _, decoder = tmp_config_dir
    data = yaml_to_graph_data(load_yamls(config_dir), decoder)

    class MockClient:
        def existing_node_names(self, label):
            return {"A"} if label == "参数值" else set()  # "A" 已在 Neo4j

    _new_nodes, new_rels = dedup_against_neo4j(data, MockClient())
    # 1LE0001-1AA42-1AA4 → A 的 rel 保留 (src 端点是 new)
    rels_model_to_A = [r for r in new_rels if r["srcName"] == "1LE0001-1AA42-1AA4" and r["tgtName"] == "A"]
    assert len(rels_model_to_A) >= 1, (
        f"期望保留 (1LE0001 → A) rel, 实际 rels: {[(r['srcName'], r['tgtName']) for r in new_rels if r['srcName'] == '1LE0001-1AA42-1AA4']}"
    )
    # A → 绕组保护 (A 是 existing, 绕组保护 是 new, src 端点 existing, tgt 是 new)
    # 按新规则: 至少一端 new, 保留
    rels_A_to_param = [r for r in new_rels if r["srcName"] == "A"]
    assert any(r["tgtName"] == "绕组保护" for r in rels_A_to_param), f"期望保留 (A → 绕组保护), 实际: {rels_A_to_param}"


def test_dedup_empty_existing_returns_all(tmp_config_dir):
    """Neo4j 空 → 全部算 new"""
    from scripts.neo4j_import import dedup_against_neo4j, load_yamls, yaml_to_graph_data

    config_dir, _, decoder = tmp_config_dir
    data = yaml_to_graph_data(load_yamls(config_dir), decoder)

    class MockClient:
        def existing_node_names(self, label):
            return set()

    new_nodes, new_rels = dedup_against_neo4j(data, MockClient())
    assert len(new_nodes) == len(data["nodes"])
    assert len(new_rels) == len(data["rels"])


def test_dedup_dedupes_node_names(tmp_config_dir):
    """Python 端已去重过的节点 → dedup 后还是去重的 (不爆重复)"""
    from scripts.neo4j_import import dedup_against_neo4j, load_yamls, yaml_to_graph_data

    config_dir, _, decoder = tmp_config_dir
    data = yaml_to_graph_data(load_yamls(config_dir), decoder)

    class MockClient:
        def existing_node_names(self, label):
            return set()

    new_nodes, _ = dedup_against_neo4j(data, MockClient())
    names = [n["name"] for n in new_nodes]
    assert len(names) == len(set(names))  # 节点 name 都唯一


# ---------- Group 5b: cmd_check ----------


def test_cmd_check_prints_counts(capsys):
    """check 子命令打 4 个 label 节点数, 不写库"""
    from scripts.neo4j_import import cmd_check

    class MockClient:
        # cmd_check 打印 uri 和 database, 所以 MockClient 也得有这俩属性
        uri = "neo4j+s://x"
        database = "neo4j"

        def check_apoc(self):
            return "5.20.0"

        def count_nodes_by_label(self, label):
            return {"产品系列": 0, "产品型号": 0, "技术参数": 0, "参数值": 0}.get(label, 0)

    args = argparse.Namespace()  # cmd_check 不读 args, 但要传
    rc = cmd_check(args, client=MockClient())
    out = capsys.readouterr().out
    assert "APOC 可用" in out
    assert "产品系列" in out
    assert "产品型号" in out
    assert "技术参数" in out
    assert "参数值" in out
    assert rc == 0


# ---------- Group 5c: cmd_import ----------


def test_cmd_import_user_says_no_exits_0(capsys, tmp_config_dir, monkeypatch):
    """用户输入 N → exit 0, 不调 run_cypher"""
    from scripts.neo4j_import import cmd_import

    config_dir, _, _ = tmp_config_dir

    class MockClient:
        def check_apoc(self):
            return "5.20.0"

        def existing_node_names(self, label):
            return set()  # Neo4j 空

        def run_cypher(self, cypher, params):
            raise AssertionError("不应调用 run_cypher, 用户说 N 了")

    monkeypatch.setattr("builtins.input", lambda _: "n")
    args = argparse.Namespace(config_dir=config_dir)
    rc = cmd_import(args, client=MockClient())
    out = capsys.readouterr().out
    assert "已取消" in out
    assert rc == 0


def test_cmd_import_user_says_yes_writes(capsys, tmp_config_dir, monkeypatch):
    """用户输入 y → 调 run_cypher 1 次"""
    from scripts.neo4j_import import cmd_import

    config_dir, _, _ = tmp_config_dir

    written = []

    class MockClient:
        def check_apoc(self):
            return "5.20.0"

        def existing_node_names(self, label):
            return set()

        def run_cypher(self, cypher, params):
            written.append((cypher, params))

    monkeypatch.setattr("builtins.input", lambda _: "y")
    args = argparse.Namespace(config_dir=config_dir)
    rc = cmd_import(args, client=MockClient())
    out = capsys.readouterr().out
    assert rc == 0
    assert len(written) == 1
    assert "已写入" in out


# ---------- Group 5d: main argparse ----------


def test_main_check_subcommand(monkeypatch, capsys):
    """main 派发到 cmd_check"""
    from scripts.neo4j_import import main

    class MockClient:
        uri = "neo4j+s://x"
        database = "neo4j"

        def check_apoc(self):
            return "5.20.0"

        def count_nodes_by_label(self, label):
            return 0

    monkeypatch.setattr("scripts.neo4j_import.Neo4jClient.from_env", classmethod(lambda cls: MockClient()))
    monkeypatch.setattr("sys.argv", ["neo4j_import.py", "check"])
    rc = main()
    out = capsys.readouterr().out
    assert "APOC 可用" in out
    assert rc == 0


def test_main_import_subcommand_user_no(monkeypatch, tmp_config_dir, capsys):
    """main 派发到 cmd_import, 用户说 N → exit 0"""
    from scripts.neo4j_import import main

    config_dir, _, _ = tmp_config_dir  # 解包 (config_dir, loader, decoder), 拿真正的 Path

    class MockClient:
        def check_apoc(self):
            return "5.20.0"

        def existing_node_names(self, label):
            return set()

    monkeypatch.setattr("scripts.neo4j_import.Neo4jClient.from_env", classmethod(lambda cls: MockClient()))
    monkeypatch.setattr("sys.argv", ["neo4j_import.py", "import", "--config-dir", str(config_dir)])
    monkeypatch.setattr("builtins.input", lambda _: "n")
    rc = main()
    out = capsys.readouterr().out
    assert "已取消" in out
    assert rc == 0


# ---------- Group 5e: 脚本可独立运行 (不依赖 pytest 的 pythonpath) ----------


def test_script_runs_without_module_not_found_error(tmp_path):
    """脚本 `python scripts/neo4j_import.py --help` 必须能跑, 不报 ModuleNotFoundError.

    Bug 修复: 之前 scripts/ 下的脚本 import src.* 失败, 因为 Python 把 scripts/ 加到 sys.path
    而非仓库根. 修复: 脚本顶部 sys.path 注入 _REPO_ROOT. 这个测试用 subprocess 模拟
    `python script.py` 的真实运行, 不走 pytest 的 pythonpath 注入.
    """
    import subprocess
    import sys as _sys

    repo_root = Path(__file__).resolve().parent.parent.parent
    script_path = repo_root / "scripts" / "neo4j_import.py"
    # 用系统 python 跑 (不是 pytest), 验 ModuleNotFoundError 不复现
    # encoding="utf-8" 因为脚本 stdout 改成了 utf-8 (Windows 防乱码)
    result = subprocess.run(
        [_sys.executable, str(script_path), "--help"],
        capture_output=True,
        text=True,
        encoding="utf-8",  # 关键: 跟脚本 stdout 一致
        cwd=str(repo_root),  # 在仓库根跑, 跟 README 推荐用法一致
    )
    # exit 0 (--help 成功)
    assert result.returncode == 0, f"stderr: {result.stderr}"
    # 没有 ModuleNotFoundError
    assert "ModuleNotFoundError" not in result.stderr
    # 输出含子命令
    assert "check" in result.stdout
    assert "import" in result.stdout


def test_check_subcommand_reads_dotenv(tmp_path, monkeypatch):
    """`check` 子命令自动从 .env 读 NEO4J_* (不再报 缺环境变量).

    场景: 用户在仓库根写 .env (NEO4J_URI=... 等), 直接 `python scripts/neo4j_import.py check`
    应能读到 .env 走到 connect 阶段 (不报 RuntimeError 缺环境变量).
    """
    import subprocess
    import sys as _sys

    repo_root = Path(__file__).resolve().parent.parent.parent
    script_path = repo_root / "scripts" / "neo4j_import.py"
    # 写 .env (CWD = repo_root 时, dotenv 默认找它)
    env_file = repo_root / ".env"
    env_content = "NEO4J_URI=bolt://fake-host:7687\nNEO4J_USER=neo4j\nNEO4J_PASSWORD=fake-pw\nNEO4J_DATABASE=neo4j\n"
    env_file.write_text(env_content, encoding="utf-8")
    # 强制清空外部 NEO4J_* env (monkeypatch.delenv), 验 .env 能填上
    for k in ("NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD", "NEO4J_DATABASE"):
        monkeypatch.delenv(k, raising=False)

    try:
        result = subprocess.run(
            [_sys.executable, str(script_path), "check"],
            capture_output=True,
            text=True,
            encoding="utf-8",  # 关键: 跟脚本 stdout 一致
            cwd=str(repo_root),  # 关键: CWD = repo_root, dotenv 找 .env
            env={},  # 空 env, 强制从 .env 读
        )
        # 不应报 "缺环境变量" (说明 .env 成功被读)
        combined = result.stdout + result.stderr
        assert "缺环境变量" not in combined, f"未读 .env:\nstdout={result.stdout}\nstderr={result.stderr}"
        # 应该报别的错 (connect 失败, 因为 fake-host 不存在) 或成功
        # 两种都 OK, 关键是 .env 被读了
    finally:
        env_file.unlink(missing_ok=True)


# ---------- Group 5f: URI scheme 转换 (neo4j 6.x ssl_context 限制) ----------


def test_normalize_uri_for_ssl_context_strips_encryption():
    """neo4j+s:// / bolt+s:// → neo4j:// / bolt:// (让 ssl_context 生效)

    neo4j 6.x driver: ssl_context 参数只能配明文 scheme.
    neo4j+s:// 走系统 trust store, Windows Python 默认 ssl 不含 Aura CA,
    会报 'self-signed certificate in certificate chain'. 脚本内部转成明文
    scheme + ssl_context=certifi 解决.
    """
    from scripts.neo4j_import import _normalize_uri_for_ssl_context

    # 加密 → 明文 (保 scheme 族)
    assert _normalize_uri_for_ssl_context("neo4j+s://host:7687") == "neo4j://host:7687"
    assert _normalize_uri_for_ssl_context("bolt+s://host:7687") == "bolt://host:7687"
    assert _normalize_uri_for_ssl_context("neo4j+ssc://host") == "neo4j://host"
    assert _normalize_uri_for_ssl_context("bolt+ssc://host") == "bolt://host"
    # 已是无加密 → 原样
    assert _normalize_uri_for_ssl_context("neo4j://host:7687") == "neo4j://host:7687"
    assert _normalize_uri_for_ssl_context("bolt://host") == "bolt://host"


# ---------- Group 5g: Windows console UTF-8 输出 (中文不乱码) ----------


def test_script_stdout_handles_chinese_without_mojibake():
    """脚本在 Windows console 输出中文不应乱码 (reconfigure stdout utf-8 + SetConsoleOutputCP 65001).

    Bug: Windows console 默认 code page 437/936, UTF-8 中文被吞成 mojibake (如 "实体清单" → "��ʵ���嵥").
    修复: 脚本顶部 sys.stdout.reconfigure(encoding="utf-8") + ctypes SetConsoleOutputCP(65001).
    """
    import subprocess
    import sys as _sys

    repo_root = Path(__file__).resolve().parent.parent.parent
    script_path = repo_root / "scripts" / "neo4j_import.py"
    # 跑 --help, 截 stdout 字节, 验证能 UTF-8 decode (没乱码)
    result = subprocess.run(
        [_sys.executable, str(script_path), "--help"],
        capture_output=True,
        cwd=str(repo_root),
    )
    # stdout 应能用 UTF-8 解码 (Python subprocess 默认 capture 字节, 这里 try decode)
    raw = result.stdout
    try:
        text: str = raw.decode("utf-8")
    except UnicodeDecodeError as e:
        pytest.fail(f"stdout 不能 UTF-8 解码 (reconfigure utf-8 没生效): {e}")
    # 至少含中文字符 (help 文本里 "知识图谱" 等)
    assert "知识图谱" in text, f"stdout 不含中文, 拿到: {text[:200]!r}"
