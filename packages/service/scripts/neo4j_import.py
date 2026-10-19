"""YAML 配置 → Neo4j 知识图谱 导入脚本

子命令:
  import  把 configs/product_decoders/ 转成节点/关系, 查 Neo4j 去重, 表格确认, 写库
  check   验 Neo4j 连通 + APOC 可用, 打节点数

用法:
  uv run python scripts/neo4j_import.py check
  uv run python scripts/neo4j_import.py import
  uv run python scripts/neo4j_import.py import --config-dir /path/to/configs
"""

# ruff: noqa: E402  # 故意: 顶层 import 在 UTF-8 stdout reconfigure 之后 (Windows console)
import argparse
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

# 让 scripts/ 下的脚本能直接 `uv run python scripts/neo4j_import.py ...` 运行
# Python 默认把脚本所在目录加 sys.path, 所以 scripts/ 在 path, 但 src/ 不在.
# 跟仓库根的 main.py 不一样 (main.py 在根, 根在 path, src/ 作为子目录可找到).
# 这里显式把仓库根加 sys.path, 跟 pytest 行为一致 (pyproject.toml: pythonpath = ["src", "."]).
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Windows console 默认 code page 是 437/936, 写 UTF-8 中文会变 mojibake
# (例如 "实体清单" → "��ʵ���嵥"). 这里设 stdout 为 UTF-8, 并改 console code page 到 65001.
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # pyright: ignore[reportAttributeAccessIssue]  # Python 3.7+
        sys.stderr.reconfigure(encoding="utf-8")  # pyright: ignore[reportAttributeAccessIssue]
    except Exception:
        pass
    try:
        import ctypes

        ctypes.windll.kernel32.SetConsoleOutputCP(65001)  # 强制 console 显示 UTF-8
    except Exception:
        pass

import yaml

from src.product_decoders import ConfigLoader, ProductDecoder

if TYPE_CHECKING:
    pass  # noqa: F401


# ---------- 数据层 ----------


def load_yamls(config_dir: Path) -> list[dict]:
    """递归加载 config_dir 下所有 .yaml 文件, 返回 list[dict]"""
    config_dir = Path(config_dir)
    yamls: list[dict] = []
    for yaml_path in sorted(config_dir.rglob("*.yaml")):
        with open(yaml_path, encoding="utf-8") as f:
            yamls.append(yaml.safe_load(f))
    return yamls


# ---------- 暂未实现 (后续 task 填) ----------


def yaml_to_graph_data(yamls, decoder):
    """YAML 列表 + ProductDecoder → {nodes, rels}

    集成 ProductDecoder.decode() 解码 examples[].raw 生成 4 类关系.
    """
    nodes = []
    rels = []

    for cfg in yamls:
        # ---- 产品系列 节点 ----
        series_name = cfg.get("series_name_zh", cfg.get("series", ""))
        series_node = {
            "labels": ["产品系列"],
            "name": series_name,
            "props": {
                "series_id": cfg.get("series", ""),
                "manufacturer": cfg.get("manufacturer", ""),
                "series_name_zh": cfg.get("series_name_zh", ""),
                "series_name_en": cfg.get("series_name_en", ""),
                "description": f"{cfg.get('series_name_zh', '')} / {cfg.get('series_name_en', '')}".strip(" /"),
                "version": str(cfg.get("version", "")),
                "source_doc": cfg.get("source_doc", ""),
            },
        }
        nodes.append(series_node)

        # ---- 技术参数 节点 (只取 type=enum 的 position) ----
        enum_positions = []
        for pos in cfg.get("decoder", {}).get("positions", []):
            if pos.get("type") != "enum":
                continue
            enum_positions.append(pos)
            param_props = {
                "name_zh": pos.get("name_zh", ""),
                "name_en": pos.get("name_en", ""),
                "char_count": pos.get("char_count", 1),
                "type": pos.get("type", "enum"),
                "idx": pos.get("idx", 0),
            }
            if "unit" in pos:
                param_props["unit"] = pos["unit"]
            nodes.append(
                {
                    "labels": ["技术参数"],
                    "name": pos.get("name_zh", ""),
                    "props": param_props,
                }
            )

        # ---- 参数值 节点 ----
        for pos in enum_positions:
            for raw_key, decoded in pos.get("values", {}).items():
                if isinstance(decoded, dict):
                    value_props = {
                        "code": decoded.get("code"),
                        "zh": decoded.get("zh", ""),
                        "en": decoded.get("en", ""),
                    }
                else:
                    value_props = {"code": decoded}
                nodes.append(
                    {
                        "labels": ["参数值"],
                        "name": str(raw_key),
                        "props": value_props,
                    }
                )

        # ---- 产品型号 节点 + 4 类关系 (集成 ProductDecoder) ----
        for ex in cfg.get("examples", []):
            raw_model = ex.get("raw", "")
            if not raw_model:
                continue
            # 用 ProductDecoder 解码, 失败 → 整个 example 跳过 (不建 model 节点, 不建 属于 关系)
            try:
                decoded = decoder.decode(raw_model)
            except ValueError as e:
                print(f"[SKIP] example '{raw_model}' 无法解码: {e}", file=sys.stderr)
                continue
            # 产品型号 节点
            nodes.append(
                {
                    "labels": ["产品型号"],
                    "name": raw_model,
                    "props": {"description": ex.get("description", "")},
                }
            )
            # 属于 → 产品系列
            rels.append(
                {
                    "srcName": raw_model,
                    "tgtName": series_name,
                    "type": "属于",
                    "props": {},
                }
            )
            for pos in enum_positions:
                pos_name_en = pos["name"]  # decoder 用英文 key
                raw_value = decoded.get(f"{pos_name_en}_raw")
                if raw_value is None:
                    continue
                pos_name_zh = pos.get("name_zh", pos_name_en)
                # 具有参数 → 技术参数
                rels.append(
                    {
                        "srcName": raw_model,
                        "tgtName": pos_name_zh,
                        "type": "具有参数",
                        "props": {},
                    }
                )
                # 参数值 → 参数值
                rels.append(
                    {
                        "srcName": raw_model,
                        "tgtName": str(raw_value),
                        "type": "参数值",
                        "props": {},
                    }
                )
                # 参数对应 → 技术参数
                rels.append(
                    {
                        "srcName": str(raw_value),
                        "tgtName": pos_name_zh,
                        "type": "参数对应",
                        "props": {},
                    }
                )

    # 节点按 name 去重 (APOC merge 也是按 name, 先在 Python 端去重避免参数重复)
    seen = set()
    unique_nodes = []
    for n in nodes:
        if n["name"] in seen:
            continue
        seen.add(n["name"])
        unique_nodes.append(n)

    return {"nodes": unique_nodes, "rels": rels}


def dedup_against_neo4j(data, client):
    """查 Neo4j 已有节点, 过滤 new_nodes + 保留有效 rels

    Returns: (new_nodes, new_rels)

    关系过滤逻辑 (关键, 不要写错):
      - 端点必须在 (new ∪ existing) 里, 即已知的节点名空间
      - 端点都在 new 里: 当然要写
      - 一端 new 一端 existing: **要写** (例: 新型号 → 已存在的共享 value "A")
      - 两端都 existing: 不写 (旧 rel 已存在, apoc.merge 也会 idempotent 处理)
        注: 上一条"两端都 existing"是优化, 实际 apoc.merge 也安全, 可省去
    """
    # 收集 4 个 label 的已有 name 并集
    LABELS = ["产品系列", "产品型号", "技术参数", "参数值"]
    existing = set()
    for label in LABELS:
        existing |= client.existing_node_names(label)

    # 过滤节点: 不在 existing 里的 = 新节点
    new_nodes = [n for n in data["nodes"] if n["name"] not in existing]
    new_node_names = {n["name"] for n in new_nodes}
    # 已知节点名空间 = new ∪ existing (用于 rel 端点校验)
    known_names = new_node_names | existing

    # 过滤 rels: 端点都在已知名空间里 (至少一端是 new 的 rel 都保留)
    new_rels = [r for r in data["rels"] if r["srcName"] in known_names and r["tgtName"] in known_names]

    return new_nodes, new_rels


# ---------- Neo4j 客户端 ----------


class Neo4jClient:
    """封装 neo4j driver, 4 个 env var 缺一报借误

    构造用 Neo4jClient.from_env() 读环境变量; 测试可显式传 driver=None mock.
    """

    def __init__(self, uri, user, password, database, driver=None):
        self.uri = uri
        self.user = user
        self.password = password
        self.database = database
        self._driver = driver  # 真实环境用 self._connect() 构造

    @classmethod
    def from_env(cls):
        """从 NEO4J_* env var 构造, 缺一报 RuntimeError

        纯 env 读取, 不 load .env (那是 main() 一次性做的事).
        测试友好: 测试可以直接 monkeypatch delenv 制造 "缺 env" 场景.
        """
        required = ["NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD", "NEO4J_DATABASE"]
        missing = [k for k in required if not os.environ.get(k)]
        if missing:
            raise RuntimeError(f"缺环境变量: {', '.join(missing)}")
        return cls(
            uri=os.environ["NEO4J_URI"],
            user=os.environ["NEO4J_USER"],
            password=os.environ["NEO4J_PASSWORD"],
            database=os.environ["NEO4J_DATABASE"],
        )

    def _connect(self):
        """懒连接, 第一次用 driver 时才连

        neo4j 6.x driver 限制: ssl_context 只能配 bolt/neo4j scheme (明文),
        bolt+s/neo4j+s scheme 强制走系统 trust store, 改不了.

        Windows 上 Python 自带 ssl 不含 Aura 用的 DigiCert/Let's Encrypt CA,
        直接用 neo4j+s 会报 "self-signed certificate in certificate chain".

        解法: 脚本内部把 +s/+ssc 改写成无加密 scheme, 再传 ssl_context=certifi
        显式加 SSL + 自带 CA. 安全性等同 +s, 但跨平台可移植.
        """
        if self._driver is None:
            import ssl

            import certifi
            from neo4j import GraphDatabase

            conn_uri = _normalize_uri_for_ssl_context(self.uri)
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            self._driver = GraphDatabase.driver(
                conn_uri,
                auth=(self.user, self.password),
                ssl_context=ssl_context,
            )
        return self._driver

    def check_apoc(self):
        """验 APOC 可用, 返回版本号. 失败抛 RuntimeError"""
        driver = self._connect()
        with driver.session(database=self.database) as session:
            try:
                result = session.run("RETURN apoc.version() AS v").single()
            except Exception as e:
                raise RuntimeError(f"APOC 不可用: {e}") from e
        if result is None:
            raise RuntimeError("APOC 不可用: 查 apoc.version() 没结果")
        return result["v"]

    def existing_node_names(self, label):
        """查指定 label 下所有节点的 name"""
        driver = self._connect()
        with driver.session(database=self.database) as session:
            result = session.run("MATCH (n:$label) RETURN n.name AS name", label=label)
            return {r["name"] for r in result if r["name"] is not None}

    def count_nodes_by_label(self, label):
        """查指定 label 的节点数"""
        driver = self._connect()
        with driver.session(database=self.database) as session:
            result = session.run("MATCH (n:$label) RETURN count(n) AS c", label=label).single()
        if result is None:
            return 0
        return result["c"]

    def run_cypher(self, cypher, params):
        """执行 cypher, 失败透传 Neo4jError"""
        driver = self._connect()
        with driver.session(database=self.database) as session:
            session.run(cypher, **params)


def _normalize_uri_for_ssl_context(uri: str) -> str:
    """neo4j+s://X / bolt+s://X → neo4j://X / bolt://X (保 scheme 族)

    让 ssl_context 参数生效 (driver 6.x: ssl_context 只能配明文 scheme).
    无 +s/+ssc 的 URI 原样返回.
    """
    SCHEME_MAP = {
        "neo4j+s://": "neo4j://",
        "neo4j+ssc://": "neo4j://",
        "bolt+s://": "bolt://",
        "bolt+ssc://": "bolt://",
    }
    for old, new in SCHEME_MAP.items():
        if uri.startswith(old):
            return new + uri[len(old) :]
    return uri


def build_cypher(nodes, rels):
    """生成 apoc.merge.node + apoc.merge.relationship 的 cypher + params

    模板 (用户给定):
        UNWIND $nodes AS node
        CALL apoc.merge.node(node.labels, {name: node.name}, node.props, {}) YIELD node AS n
        UNWIND $rels AS rel
        MATCH (a {name: rel.srcName})
        MATCH (b {name: rel.tgtName})
        CALL apoc.merge.relationship(a, rel.type, {}, rel.props, b) YIELD rel AS r
        RETURN count(r) AS rels_written
    """
    cypher = """
UNWIND $nodes AS node
CALL apoc.merge.node(node.labels, {name: node.name}, node.props, {}) YIELD node AS n
WITH count(n) AS nodes_merged
UNWIND $rels AS rel
MATCH (a {name: rel.srcName})
MATCH (b {name: rel.tgtName})
CALL apoc.merge.relationship(a, rel.type, {}, rel.props, b) YIELD rel AS r
RETURN count(r) AS rels_written
""".strip()
    params = {"nodes": nodes, "rels": rels}
    return cypher, params


def format_props(props):
    """{} → '无', {k:v} → 'k: v, k: v' (跟用户给的例子一致)"""
    if not props:
        return "无"
    return ", ".join(f"{k}: {v}" for k, v in props.items())


def render_node_table(nodes):
    """渲染节点清单 (序号, 实体名称, 实体类型, 属性)"""
    from tabulate import tabulate

    rows = []
    for i, n in enumerate(nodes, 1):
        rows.append([i, n["name"], "/".join(n["labels"]), format_props(n.get("props", {}))])
    return tabulate(rows, headers=["序号", "实体名称", "实体类型", "属性"], tablefmt="simple")


def render_rel_table(rels):
    """渲染关系清单 (序号, 源实体, 关系类型, 目标实体, 属性)"""
    from tabulate import tabulate

    rows = []
    for i, r in enumerate(rels, 1):
        rows.append([i, r["srcName"], r["type"], r["tgtName"], format_props(r.get("props", {}))])
    return tabulate(rows, headers=["序号", "源实体", "关系类型", "目标实体", "属性"], tablefmt="simple")


def cmd_import(args, client=None):
    """import 子命令: load → decode → dedup → table → y/N → cypher"""
    if client is None:
        client = Neo4jClient.from_env()
    client.check_apoc()  # 验证

    # 1. load + decode
    loader = ConfigLoader(config_dir=str(args.config_dir))
    decoder = ProductDecoder(loader)
    yamls = load_yamls(args.config_dir)
    data = yaml_to_graph_data(yamls, decoder)

    # 2. dedup
    new_nodes, new_rels = dedup_against_neo4j(data, client)

    # 3. 表格
    if not new_nodes:
        print("无新数据 (Neo4j 已包含所有节点)")
        return 0
    print(f"\n=== 实体清单 (共 {len(new_nodes)} 条) ===")
    print(render_node_table(new_nodes))
    print(f"\n=== 关系清单 (共 {len(new_rels)} 条) ===")
    print(render_rel_table(new_rels))

    # 4. y/N
    ans = input("\n确认写入 Neo4j? [y/N]: ").strip().lower()
    if ans not in ("y", "Y"):
        print("已取消")
        return 0

    # 5. 写
    cypher, params = build_cypher(new_nodes, new_rels)
    client.run_cypher(cypher, params)
    print(f"已写入 {len(new_nodes)} 节点, {len(new_rels)} 关系")
    return 0


def cmd_check(args, client=None):
    """check 子命令: 连通 + APOC + 节点数"""
    if client is None:
        client = Neo4jClient.from_env()
    print(f"[Neo4j 连接成功] uri={client.uri}, database={client.database}")
    version = client.check_apoc()
    print(f"[APOC 可用] apoc.version()={version}")
    LABELS = ["产品系列", "产品型号", "技术参数", "参数值"]
    counts = {label: client.count_nodes_by_label(label) for label in LABELS}
    print("[节点数] " + ", ".join(f"{label}: {n}" for label, n in counts.items()))
    return 0


def main():
    """argparse 入口, 派发到 cmd_check 或 cmd_import

    启动时自动 load .env (找不到试 .env.example), 已有 env 不被覆盖.
    """
    # 自动 load .env (在 CWD 找, 找不到试 .env.example)
    # 放在 main() 而非 from_env() 是为了: from_env() 测试友好 (纯 env 读取)
    try:
        from dotenv import load_dotenv

        for env_path in (".env", ".env.example"):
            if os.path.isfile(env_path):
                load_dotenv(env_path, override=False)
    except ImportError:
        pass  # 容错, 缺 dotenv 时退到纯 env 模式

    parser = argparse.ArgumentParser(description="YAML 配置 → Neo4j 知识图谱导入")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # check 子命令
    subparsers.add_parser("check", help="验 Neo4j 连通 + APOC + 打节点数")

    # import 子命令
    sub_import = subparsers.add_parser("import", help="读 YAML, 查 Neo4j 去重, 表格确认, 写库")
    sub_import.add_argument(
        "--config-dir",
        type=Path,
        default=Path("configs/product_decoders"),
        help="YAML 配置目录 (默认: configs/product_decoders)",
    )

    args = parser.parse_args()

    if args.command == "check":
        return cmd_check(args)
    elif args.command == "import":
        return cmd_import(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
