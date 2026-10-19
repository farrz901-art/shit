# Neo4j 导入脚本设计

**日期**: 2026-06-04
**状态**: 设计已批准, 待实施

## Context

产品订货号解析服务 (`src/product_decoders/`) 的 YAML 配置 (`configs/product_decoders/`) 现在是"孤岛": 解析器能用, 但知识查询/聚合 (如"列出所有 Siemens 系列有哪些机座号") 需要人肉读 YAML。

知识图谱 (Neo4j) 是更好的查询介质:
- 跨系列聚合 (frame_size=100mm 的产品有哪些)
- 关系遍历 (这个系列符合哪些标准)
- 跟 Dify LLM 抽取的实体/关系合并 (后续)

本设计是**第一期**: 把现有 YAML 导入 Neo4j, 用脚本半自动完成 (查重 → 表格确认 → 写库)。后续 PDF 抽取的实体可同样用本脚本的 `import` 子命令并入。

## 目标

写一个 Python CLI 脚本, 把 `configs/product_decoders/**/*.yaml` 转换为 Neo4j 节点和关系, **经用户确认后** 写入在线 Neo4j 实例。

## 非目标

- **本期不导入 PDF 抽取的实体** (那是 Dify LLM 的活, 后续单独设计)
- **本期不实现图 schema 迁移 / 清理 / 备份** (只导入, 不删)
- **本期不实现双向同步** (只 YAML → Neo4j, 反向不回写)

## 数据来源

`configs/product_decoders/**/*.yaml`, 默认根目录 `configs/`, 可用 `--config-dir` 覆盖。

唯一现有 YAML: `configs/product_decoders/motor/siemens/1le0_low_voltage.yaml`
- 1 个系列
- 9 个 position (1 fixed + 8 enum)
- 59 个 enum value
- 1 个 example (1LE0001-1AA42-1AA4)
- 预期导入: 1 产品系列 + 1 产品型号 + 8 技术参数 + 59 参数值 = **69 节点**
- 预期关系: 1 `属于` + 8 `具有参数` + 8 `参数值` + 8 `参数对应` = **25 关系**

## 节点 / 关系 schema

**4 个 label, 4 个关系类型**。**所有 label/关系类型用中文**, 跟 Dify LLM 抽取 prompt 的术语对齐。

### 节点

| Label | name 来源 | props |
|---|---|---|
| `产品系列` | `YAML.series_name_zh` | `series_id` (原 series 字段, 唯一稳定 id), `manufacturer`, `series_name_zh`, `series_name_en`, `description` (从 name_zh + name_en 拼), `version`, `source_doc` |
| `产品型号` | `YAML.examples[].raw` (完整 16 位型号) | `description` (来自 examples[].description) |
| `技术参数` | `YAML.decoder.positions[].name_zh` (type=enum) | `name_zh`, `name_en`, `char_count` (int), `type` (`enum`/`fixed`/`passthrough`), `idx` (int), `unit` (有则附) |
| `参数值` | `YAML.decoder.positions[].values{}` 的 key (原始编码) | `code` (来自 `values[i].code`), `zh`, `en` |

**name 唯一性**: 4 个 label 内分别唯一 (跟 Dify prompt 期望的 join key 一致: 跨文档的"机座号"节点会合并)。`apoc.merge.node` 用 `name` 做 merge key。

**`产品系列` vs `产品型号` 区分** (用户强调):
- `产品系列` = 系列/家族, 标识是 prefix (YAML `router.prefix` = "1LE000" → 1LE0 系列)
- `产品型号` = 完整订货号 (16 位), 数据来源是 `YAML.examples[].raw` (本期不生成, 只读现有 examples)
- 两者不同, 不能合并

### 关系

| 关系类型 | 源 → 目标 | 数量 (1le0) | 用途 |
|---|---|---|---|
| `属于` | `产品型号` → `产品系列` | = 1 (1 example × 1 series) | "1LE0001-1AA42-1AA4 属于 1LE0 系列" |
| `具有参数` | `产品型号` → `技术参数` | = 8 (1 example × 8 enum pos) | "该型号有机座号/极数/电压... 这 8 个参数" |
| `参数值` | `产品型号` → `参数值` | = 8 (decode 出来的 8 个具体值) | "该型号的机座号取值 1A (=100mm)" |
| `参数对应` | `参数值` → `技术参数` | = 8 (跟上面 8 条配对) | "1A 这个值是机座号这个参数的值" |

**关键**: `具有参数` / `参数值` / `参数对应` 三条关系**只对 decode 出来的 (param, value) 配对创建**, 不对 59 个全 enum value 创建. 也就是说, 1le0 1 个 example 给出 8 个解码值, 所以这 3 类关系各 8 条, 跟 Dify 抽取例子 (1 个 1LE0003-0DA22-1 例子, 14 个值) 同构.

## 命名约定 (与 Dify LLM 抽取对齐)

| 维度 | 用什么 | 理由 |
|---|---|---|
| `产品系列.name` | `YAML.series_name_zh` | Dify prompt 要求"产品系列"用中文 + "系列"后缀, 跨文档可读 |
| `产品型号.name` | `YAML.examples[].raw` (16 位完整型号) | Dify prompt 要求"产品型号"保留原文 (订货号/型号代码) |
| `技术参数.name` | `YAML.name_zh` | Dify prompt 要求"技术参数"必须中文, 跨文档 join 简单 |
| `参数值.name` | values 字典的 key (原始编码) | Dify prompt 要求"参数值"保留原文 (含单位/特殊字符), 跟 ProductDecoder decode 输出对齐 |

`YAML.series` / `YAML.name` (英文) 存进 props, 不当 name, 避免双重主键。

## Cypher 模板

```cypher
UNWIND $nodes AS node
CALL apoc.merge.node(node.labels, {name: node.name}, node.props, {}) YIELD node AS n

UNWIND $rels AS rel
MATCH (a {name: rel.srcName})
MATCH (b {name: rel.tgtName})
CALL apoc.merge.relationship(a, rel.type, {}, rel.props, b) YIELD rel AS r

RETURN count(r) AS rels_written
```

`$nodes` 形状: `[{labels: ["产品系列"], name: "...", props: {...}}, ...]`
`$rels` 形状: `[{srcName: "...", tgtName: "...", type: "具有参数", props: {}}, ...]`

依赖 **APOC 插件**, 在线 Neo4j Aura 默认带, 启动时跑 `RETURN apoc.version()` 验证。

## CLI 设计

### `import` 子命令

```bash
uv run python scripts/neo4j_import.py import [--config-dir PATH]
```

执行流程:

1. `load_yamls(config_dir)` — 默认 `configs/`
2. `yaml_to_graph_data(yamls)` → `{nodes, rels}`
3. `Neo4jClient(...)` 构造, 缺 env 报 `RuntimeError`
4. `client.check_apoc()` 验证 APOC 可用
5. `client.existing_node_names(label)` 对 4 个 label 各查一次, 并集作 `existing`
6. `dedup_against_neo4j(data, client)` → `(new_nodes, new_rels)`, 端点不在 new_nodes 名空间里的 rel 也剔除
7. `render_node_table(new_nodes)` + `render_rel_table(new_rels)` (tabulate, 含中文)
8. `确认写入 Neo4j? [y/N]: ` — **强制交互, 无 --yes flag**
9. 用户输入 `y`/`Y` → `client.run_cypher(cypher, params)` → 打印结果
10. 其他输入 (含空回车) → 打印 `已取消`, exit 0

### `check` 子命令

```bash
uv run python scripts/neo4j_import.py check
```

执行流程:
1. 连 Neo4j + 验证 APOC
2. 打印: `[Neo4j 连接成功] uri=..., database=...` + `[APOC 可用] apoc.version()=...` + `[节点数] 产品系列: X, 产品型号: Y, 技术参数: A, 参数值: B`
3. 不写库, exit 0

## 模块布局 (单文件, 函数化拆分)

`scripts/neo4j_import.py` 不拆包 (YAGNI):

```python
# 数据层
def load_yamls(config_dir: Path) -> list[dict]: ...
def yaml_to_graph_data(yamls: list[dict], config_dir: Path) -> dict:
    """{nodes, rels}. 集成 ProductDecoder 解码 examples[].raw, 生成 4 类关系."""
    ...

# Neo4j 客户端
class Neo4jClient:
    def __init__(self, uri, user, password, database): ...
    def check_apoc(self) -> str: ...                       # 返回版本
    def existing_node_names(self, label: str) -> set[str]: ...
    def count_nodes_by_label(self, label: str) -> int: ...
    def run_cypher(self, query: str, params: dict) -> None: ...

# 去重
def dedup_against_neo4j(data: dict, client: Neo4jClient) -> tuple[list, list]: ...

# Cypher 生成
def build_cypher(nodes: list[dict], rels: list[dict]) -> tuple[str, dict]: ...

# 表格 (tabulate)
def render_node_table(nodes: list[dict]) -> str: ...
def render_rel_table(rels: list[dict]) -> str: ...
def format_props(props: dict) -> str: ...                  # {} → "无", {k:v} → "k: v, k: v"

# CLI (argparse subparsers)
def cmd_import(args): ...
def cmd_check(args): ...
def main(): ...
```

**ProductDecoder 集成关键点** (`yaml_to_graph_data` 内部):
1. 构造 `ProductDecoder(ConfigLoader(config_dir))` 一次
2. 对每个 `cfg.examples[].raw` 调 `decoder.decode(raw)`, 拿到 `{position_name: value, f"{position_name}_raw": raw_segment, ...}`
3. 对每个 enum position 用 `decoded[f"{pos['name']}_raw"]` 拿到该型号的具体 raw 值
4. 建 3 条关系: `(型号)-[具有参数]->(技术参数)` + `(型号)-[参数值]->(参数值)` + `(参数值)-[参数对应]->(技术参数)`
5. 解码失败 (ValueError) → **该 example 跳过, 不导入, 打印警告**, 不阻塞其他 yaml

## 环境变量

```
NEO4J_URI       # neo4j+s://xxx.databases.neo4j.io
NEO4J_USER      # neo4j
NEO4J_PASSWORD  # xxxxxxxx
NEO4J_DATABASE  # neo4j (默认)
```

文档放 `仓库根/.env.example` (git tracked, 含占位符)。`.env` 在 `.gitignore`。

## 依赖

- `neo4j>=5.x` (官方 Python driver) — 加到 `pyproject.toml` 的 `dependencies`
- `tabulate>=0.9` — 轻量表格库, 加到 `dependencies`
- `pyyaml` — 已在 (ProductDecoder 用了, 走 ProductDecoder.decode 集成)
- `src.product_decoders` — 项目内已有 (`ProductDecoder` + `ConfigLoader`), 脚本 `import` 它来解码 examples

## 表格格式

`tabulate(tabular_data, headers=..., tablefmt="simple")`, 输出含中文不乱码 (Python 3.14 + Windows + tabulate 默认 utf-8 输出到 stdout, 跟项目 `tests/rag_ingest/` 既有用法一致)。

**实体清单** (`headers=["序号", "实体名称", "实体类型", "属性"]`):
```
  序号  实体名称                       实体类型  属性
------  ----------------------------  ------  ---------------------------------------
  1     西门子低压系列三相异步电动机  产品系列  description: 西门子 1LE0 低压系列...
  2     机座号                        技术参数  无
  3     1A                            参数值  code: 100, zh: 100mm 机座
```

**关系清单** (`headers=["序号", "源实体", "关系类型", "目标实体", "属性"]`):
```
  序号  源实体  关系类型  目标实体  属性
------  ------  ------  ------  ----
  1     ...    具有参数  机座号  无
```

## 错误处理矩阵

| 场景 | 表现 |
|---|---|
| 缺 `NEO4J_*` env var | `RuntimeError: 缺环境变量 NEO4J_PASSWORD`, exit 1 |
| Neo4j 不可达 | `Neo4jClient` 构造时抛 `ServiceUnavailable`, 透传堆栈, exit 1 |
| APOC 不可用 | `RuntimeError: APOC 不可用`, exit 1 |
| YAML 解析失败 | `yaml.YAMLError` 透传, exit 1 |
| examples[].raw 解码失败 (跟 YAML 不匹配) | **该 example 跳过, 打印警告 `[SKIP] example "X" 无法解码`**, 不阻塞其他 yaml |
| 用户输入非 y/Y | `已取消`, exit 0 |
| Cypher 执行失败 | Neo4j driver 抛 `Neo4jError`, 透传堆栈, exit 1 |
| `--config-dir` 路径不存在 | `FileNotFoundError` 透传, exit 1 |

## 安全 / 幂等

- **APOC merge 天然幂等**: 重复跑 `import` 第二次只会 merge 不存在的新节点, 已有节点不动; 第二次跑完后 `existing` 已包含所有节点, `new_nodes` 为空
- **不删任何节点**: 无 `clear` 子命令, 误操作不会丢数据
- **凭证只走 env var**, 不进代码, 不进 git

## 测试设计

位置: `tests/scripts/test_neo4j_import.py` (单文件, ~200 行)

策略: **单元 + Mock, 不连真实 Neo4j**。理由:
- CI 跑得快 (不依赖外部服务)
- 测试可重复 (不污染线上数据)
- 真实端到端留给用户手动跑 `import` 验证

### 测试用例分组

**Group 1: YAML → graph data 转换** (纯函数, 无 mock, 集成 ProductDecoder)
- `test_yaml_to_nodes_series_count` — 1 个 yaml → 1 个产品系列节点
- `test_yaml_to_nodes_series_uses_name_zh` — name 是 `series_name_zh`, props 含 `series_id`
- `test_yaml_to_nodes_model_count` — 1le0 (1 example) → 1 个产品型号节点
- `test_yaml_to_nodes_model_uses_examples_raw` — name 是 `examples[].raw`
- `test_yaml_to_nodes_model_props_description` — props.description 是 examples[].description
- `test_yaml_to_nodes_param_count` — 1le0 → 8 个技术参数
- `test_yaml_to_nodes_param_uses_name_zh` — name 是 `name_zh`
- `test_yaml_to_nodes_value_count` — 1le0 → 59 个参数值
- `test_yaml_to_nodes_value_preserves_code` — `1A` 的 props.code == 100
- `test_yaml_to_rels_belongsto_count` — 1 条 `属于` (1 example × 1 series)
- `test_yaml_to_rels_has_param_count` — 8 条 `具有参数` (1 example × 8 enum pos)
- `test_yaml_to_rels_param_value_count` — 8 条 `参数值` (1 example decoded 8 个值)
- `test_yaml_to_rels_param_of_count` — 8 条 `参数对应` (跟 参数值 配对)
- `test_yaml_to_data_empty_dir` — 空目录 → 空数据, 不抛
- `test_yaml_decode_failure_skips_example` — examples 里一个错型号 → 跳过该 example, 不阻塞其他

**Group 2: 去重** (Mock `Neo4jClient.existing_node_names`)
- `test_dedup_filters_existing_param` — 已有"机座号" → 过滤掉 + 关联 3 条 rel (具有参数 + 参数值 + 参数对应) 也剔除
- `test_dedup_empty_existing_returns_all` — Neo4j 空 → 全部算 new

**Group 3: Cypher 生成** (纯函数)
- `test_build_cypher_contains_apoc_merge_node`
- `test_build_cypher_contains_apoc_merge_relationship`
- `test_build_cypher_params_separated` — `$nodes` 和 `$rels` 分开

**Group 4: 表格渲染** (验 tabulate 中文输出)
- `test_render_node_table_chinese_ok` — 含中文不抛 `UnicodeEncodeError`
- `test_render_node_table_no_props_shows_无` — 空 props → "无"
- `test_render_rel_table_format`

**Group 5: CLI 分派** (Mock client + capsys)
- `test_check_subcommand_prints_counts` — 打 4 个 label 节点数, 不写库
- `test_import_subcommand_user_says_no_exits_0` — 输 N → exit 0, 不调 `run_cypher`

**Group 6: 环境变量** (monkeypatch env)
- `test_missing_env_var_exits_1` — 缺 `NEO4J_PASSWORD` → `RuntimeError` + exit 1

预计 ~21 个测试, 跑 <1 秒。

## 实施步骤 (高层)

1. 加依赖 (`neo4j`, `tabulate`) 到 `pyproject.toml`
2. 创建 `.env.example` + 更新 `.gitignore`
3. 写 `scripts/neo4j_import.py` (TDD: 先 Group 1 测试, 再写实现)
4. 写 `tests/scripts/test_neo4j_import.py` (TDD)
5. 更新 `README.md` 加 "环境变量 / Neo4j 导入" 节
6. 端到端验证: 用真实 Neo4j Aura 实例跑一次 `import` + `check`

## 风险

| 风险 | 缓解 |
|---|---|
| APOC merge 对动态 label 的限制 (CYPHER 语法可能限制) | 已选 APOC merge 模板, 实测过类似用法 |
| tabulate 中文乱码 (Windows console 437/GBK) | 跟 `tests/rag_ingest/` 既有用法一致, 项目已有成功先例 |
| 真实 Neo4j 没有 APOC | `check_apoc()` 启动验证, 失败清晰报错 |
| YAML 字段缺失 (e.g. 缺 `name_zh`) | `KeyError` 透传, 用户加字段后重跑 |
| Dify LLM 后续抽取的中文术语跟现有 `name_zh` 不一致 | 后续单独设计 "ontology alignment" 子任务, 本期不解决 |

## 验收

- [ ] `uv run python scripts/neo4j_import.py check` 在真实 Neo4j 上打印连接成功 + APOC 可用 + 节点数 (初次应为 0/0/0/0)
- [ ] `uv run python scripts/neo4j_import.py import` 打印实体清单 (69 条: 1 系列 + 1 型号 + 8 参数 + 59 值) + 关系清单 (25 条: 1 属于 + 8 具有参数 + 8 参数值 + 8 参数对应) + 表格格式跟用户给的例子一致
- [ ] 用户输入 `y` 后写入, 再次 `check` 显示 1/1/8/59 节点
- [ ] 用户输入 `N` 后退出 0, Neo4j 数据不变
- [ ] `uv run pytest tests/scripts/test_neo4j_import.py -v` 全过 (~21 用例)
- [ ] 重复跑 `import` 第二次表格显示 "无新数据" 或为空
- [ ] 缺 `NEO4J_PASSWORD` 报清晰借误, exit 1
- [ ] 跨多 YAML 时 (未来加系列) `name` 相同的 技术参数 节点被 APOC merge 合并, 不重复
