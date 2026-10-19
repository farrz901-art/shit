# Siemens Motor 隐性规则挖掘 · 本体增强 + 同义归并 + 人工归并 spec (v1)

**日期**: 2026-07-02
**状态**: 设计待审 (派 agent 联网做对抗性审查后定稿)
**前置 spec**: [`2026-07-01-markdown-extract-kg-design.md`](./2026-07-01-markdown-extract-kg-design.md) (v3, 已落地 M1-M7, M8 preview UI 部分落地)
**对应方案**: [`../rag/西门子电机隐性规则挖掘与图谱构建任务流 .md`](../rag/西门子电机隐性规则挖掘与图谱构建任务流%20.md)

---

## Context

西门子电机方案（6 阶段 / 78 行）描述了从 PDF → 图谱的完整流水线。**审计后**：v3 spec 已覆盖其中 80%（抽取、preview、commit、Neo4j 写入、人工审核闭环、`rule_type` 五元组），4 项真正的缺口需要落地：

1. **本体漂移**：v3 spec 用 default 4 label（Product/Series/Spec/Standard）+ 3 rel_type 抽了 motor 系列文档，Neo4j 里出现 `Product / Motor / 1LE1型号 / 产品` 4 种"产品"节点，查询必须 `label IN [...]` 兜底（v3 spec 未规定 label 白名单）
2. **同义异构词未合并**：`抱闸 = 制动器 / 减速机 = 齿轮箱 / IP55 = 防护等级 IP55`，抽取后产生 2~3 个等价节点
3. **单位未归一**：`kW / hp / 千瓦` + `mm / inch / 毫米` 混存，跨节点比较失真
4. **人工归并入口缺失**：v3 spec 的 PATCH items 仅支持"勾选/编辑文本"，不支持"把 A 归并到 B"——管理员只能删除 A，丢失原文 span 和 source_chunk

本期 spec 严格限定在这 4 项内，**不做 MLFB 状态机 / 不做 Drools 规则引擎 / 不做 TIA Selection Tool 反向验证 / 不做跨系列一致性检查**（这些属应用层 + 人工流程，单独 spec 跟进，详见本文 §未来工作）。

---

## 目标

在 v3 spec 之上加 3 层增强，让西门子电机方案第一~四阶段的核心抽取质量符合业务预期：

- **加本体 schema 文件**（motor 专用 label / rel_type 白名单），强制 LLM / spaCy 从白名单选，杜绝漂移
- **加同义词词典 + 单位归一**，让抽取阶段就把等价表达合并
- **加前端归并 UI**，让管理员把零散抽取归并到"已有实体"，保留审计证据

**3 个 milestone / 约 1.5 工作日 / 8 commits**。

## 非目标

- ❌ MLFB 订货号生成（状态机）—— 应用层另起 spec
- ❌ Drools / 规则引擎 —— Neo4j Cypher 自带推理
- ❌ TIA Selection Tool 反向验证 —— 半人工流程
- ❌ 跨系列一致性检查（5.1 D81.1 vs D84.1）—— admin 离线操作
- ❌ DependencyParser（4.2 句法分析）—— LLM 已覆盖，技术债
- ❌ PDF 解析（2.1 版面 / 2.2 OCR / 2.3 表格）—— ingest 流水线已覆盖（kreuzberg / mineru / cad），不是本 spec 范围
- ❌ 跨 dataset 实体查询 —— v3 spec 明文非目标
- ❌ 替换现有 extractor（spacy_rule / llm_pydantic）—— 只在原文件加可选参数，不动主路径
- ❌ 改 v3 spec 的 9 个端点签名 —— PATCH items payload 加可选字段，向后兼容

---

## 旧数据兼容策略 (M0, M1 上线前必做)

**问题**：v3 spec 用 default 4 label（Product/Series/Spec/Standard）抽了 motor 系列文档，Neo4j 里现有节点 label 大概率含 `Product / 1LE1型号 / 产品` 等漂移值。motor.yaml 白名单 6 label（Motor/Series/Option/Spec/Standard/Environment）**不含** `Product / 1LE1型号 / 产品`，M1 引入 ontology 校验后，老数据重新走 commit 会被"丢弃"。

**3 选 1 方案**（评审时确定，本 spec 推荐**方案 A**）：

### 方案 A：M0 一次性迁移脚本（推荐）

新增 `scripts/migrations/2026-07-02_motor_label_normalize.py`：

```python
# 伪代码
def normalize_labels(dataset: str = "motor"):
    # 1. 查 Neo4j 当前 dataset 下所有 distinct label
    labels = run_cypher("MATCH (n) WHERE n:`<Dataset>` UNWIND labels(n) AS l RETURN DISTINCT l")
    # 2. 加载 motor.yaml 白名单
    onto = OntologyLoader().load(dataset)
    allowed = set(onto.labels)  # {Motor, Series, Option, Spec, Standard, Environment}

    # 3. 漂移映射表 (人工维护, 一次性)
    drift_map = {
        "Product":     "Motor",       # Product → Motor
        "1LE1型号":     "Motor",       # 中文 alias → Motor
        "产品":         "Motor",       # 中文释义 → Motor
        "技术参数":     "Spec",        # 中文释义 → Spec
        "标准":         "Standard",    # 中文释义 → Standard
    }

    # 4. 对每个漂移 label, MERGE 节点并复制关系, 然后删旧 label
    for old_label, new_label in drift_map.items():
        if old_label in labels and new_label in allowed:
            cypher = """
            MATCH (n) WHERE n:`<Dataset>` AND n:`<OldLabel>`
            SET n:`<NewLabel>`  // Neo4j 支持 SET 增 label
            REMOVE n:`<OldLabel>`
            """
            run_cypher(cypher, audit_action="kg.ontology.migrate_label")
            logger.info("label 迁移: {} → {}", old_label, new_label)

    # 5. 兜底: 不在 drift_map 也不在 allowed 的 label, log WARNING 不删 (admin 手动处理)
    unknown = labels - allowed - set(drift_map.keys())
    logger.warning("未识别 label, 需 admin 手动处理: {}", unknown)
```

**约束**：
- 仅跑一次, 在 M1 落地前 dev DB 演练 → staging → prod
- @audited `kg.ontology.migrate_label` (迁移也是写操作, 留审计)
- 提供 `dry_run=True` 选项, 仅打印 SQL 不执行
- Neo4j `SET n:NewLabel REMOVE n:OldLabel` 走单事务, 失败回滚
- 迁移后 v3 spec 的 PATCH items 端点仍 100% 兼容（label 漂移已解决）

### 方案 B：放宽白名单 (不推荐)

`motor.yaml.labels` 改成 `[Motor, Product, Series, Option, Spec, Standard, Environment, 1LE1型号, 产品]`，混漂移值 + 真值。**问题**：永远无法 `MATCH (n:Motor)` 单 label 查询，每次必须 `MATCH (n) WHERE n.label IN [...]`，失去 ontology 校验意义。

### 方案 C：strict/warn 双模式 (折中)

`ontology.py` 加 `mode: Literal["strict", "warn"]` 配置，strict 模式丢弃漂移 label，warn 模式保留 + log。warn 模式允许老数据 commit 通过，但 Neo4j 仍有漂移节点。**问题**：warn 模式永远不会被关掉，技术债积累。

**决策点（待用户确认）**：
- 走方案 A + 写迁移脚本 ✅
- 走方案 B (放宽白名单, 简单但脏)
- 走方案 C (双模式, 灵活但债)

**风险**：方案 A 迁移脚本错改 Neo4j 节点是 HIGH 风险（不可逆），必须 dev DB 演练 + `dry_run` 默认 True + admin 显式二次确认 + 完整 audit log。实施时建议 1 个 admin + 1 个 dev 双人复核。

---

## 调研结论

### v3 spec 实际能力（2026-07-02 验证）

**已落地**（[git log b9b6465a..19adca9](https://github.com/forkai/rag) 全部 commit）：

| 能力 | 落地位置 |
|---|---|
| KgClient dataset label 隔离 + 白名单 | [`src/kg/client.py`](../../packages/service/src/kg/client.py) + [`src/kg/datasets.py`](../../packages/service/src/kg/datasets.py) |
| 9 个 extract 端点（datasets / extractors / splitters / upload / start / tasks / preview / items PATCH / commit / export） | [`src/kg/router.py`](../../packages/service/src/kg/router.py) (981 行) |
| 3 个 splitter（heading / token / semantic） | [`src/kg/splitters/`](../../packages/service/src/kg/splitters/) |
| 2 个 extractor（spacy_rule / llm_pydantic） | [`src/kg/extractors/`](../../packages/service/src/kg/extractors/) |
| extract_runner 后台 pipeline | [`src/kg/extract_runner.py`](../../packages/service/src/kg/extract_runner.py) |
| kg_extract_items PG 临时表（含 dataset 字段 + CHECK 约束 + 3 索引） | [`src/storage/migrations/versions/20260701_000000_kg_extract_items.py`](../../packages/service/src/storage/migrations/versions/20260701_000000_kg_extract_items.py) |
| Neo4j dataset label 索引 cypher + init script | [`src/kg/migrations/neo4j_init.cypher`](../../packages/service/src/kg/migrations/neo4j_init.cypher) |
| 前端 9 个 API wrapper + 7 type + 8 vitest | [`packages/web/lib/api/knowledge.ts`](../../packages/web/lib/api/knowledge.ts) |
| 前端 extract/task 页（轮询进度） | [`packages/web/app/[locale]/knowledge/extract/[task_id]/page.tsx`](../../packages/web/app/[locale]/knowledge/extract/[task_id]/page.tsx) |
| `rule_type` 五元组（compatibility / dependency / exclusion / derating / factual） | [`src/kg/extractors/base.py`](../../packages/service/src/kg/extractors/base.py) |
| @audited 4 处（start / items PATCH / commit / export） | [`src/kg/router.py`](../../packages/service/src/kg/router.py) |

**未落地 / 部分落地**（M8 缺）：

| 缺口 | 影响 |
|---|---|
| 前端 extract **主页**（dataset + extractor + splitter + 文件上传 4 字段表单） | 当前 `/knowledge/extract` 路由 404，需手动 POST 上传 |
| 前端 preview 页（实体表格 + 关系表格 + 勾选 + 编辑） | 当前 `/knowledge/extract/{id}/preview` 跳转后 404，task 页有按钮但落空 |
| 前端 commit / export 按钮 + BFF 调用 | 同上 |

→ **M8 preview UI 是本 spec 的前置依赖**（P3 前端归并 UI 必须有 preview 页才能改）。**两种方案**：
- **方案 A**：本 spec 内 P0 补 M8 主页 + preview 页（+1 工作日）
- **方案 B**：本 spec 仅做后端本体/同义词，P3 拆到独立 spec（preview UI 由另一 spec 完成）

**推荐方案 B**（本期不耦合前端 UI 进度，单 PR review 单 milestone）。本 spec 内只动 extractor 后端 + 1 个新 yaml + 1 个 PG 列，**前端 preview UI 在另一个 spec 落地**。

### 本体 schema 业界做法（2026 H1 调研）

| 来源 | 做法 | 适配本项目 |
|---|---|---|
| **OntoMetric (arXiv:2512.01289, 2025-12)** | "schema-driven extraction" — schema 在 prompt 里枚举 + 后置校验，报告 ontology-guided 比 unconstrained baseline 准确率高 6×-20× | ✅ LlmPydanticExtractor 接 ontology 参数 + 后置 validate |
| **RELATE (arXiv:2509.19057, 2025-09)** | 三阶段 ontology pipeline，ChemProt 数据集 52% exact match | ✅ extractor 阶段 schema 校验 + commit 阶段归并 |
| **LLM-empowered KG construction survey (arXiv:2510.20345, 2025-10)** | 调研 2024-2025 主流做法分类 | ✅ 跟本项目 "ontology-constrained + post-validation" 路径吻合 |
| **Neo4j 官方建议** | "Use a fixed schema. Validate labels with APOC `apoc.meta.schema`" | ✅ 加 init script 启动期校验 |
| **spaCy EntityRuler 模板** | `.yaml patterns` 配 label + pattern + id（id 允许多 pattern 共享同一 entity） | ⚠️ EntityRuler 重叠 span 短的会被静默 drop，M4 实施时需后置 merge 阶段 |
| **neo4j-graphrag-python SimpleKGPipeline** | `schema: dict[node_types, relationship_types, patterns]` 仅作 prompt 文本注入，**不做 post-extraction 过滤**（印证本项目自实现路径正确） | ✅ 本项目不依赖该库（v3 spec 已明文排除 graphifyy） |

**结论**：业界 2025-2026 普遍做法是 **prompt-level 枚举约束 + extractor-level 白名单校验** + **Neo4j 启动期 schema 校验**。本 spec 采用此模式，并加**后处理强制归一**（LLM 不可靠，仅靠 prompt enum 不够）。

> **2026-07-02 spec 评审修订**：原 spec 引用 arxiv 2503.10381 为 LLM/KG survey，**实为数论论文**（Qian Xiao, Dirichlet non-improvable numbers），已替换为 OntoMetric (2512.01289) / RELATE (2509.19057) / survey (2510.20345) 3 篇实际相关论文。

### 同义异构词合并（deduplication of entity mentions）

| 做法 | 优劣 |
|---|---|
| 抽取前 synonym rule（spaCy EntityRuler 同义词表） | ✅ 抽取阶段就合并 span，Neo4j 节点唯一；⚠️ 词典维护成本 |
| 抽取后 fuzzy match（rapidfuzz / jaro_winkler） | ⚠️ 引入额外库；准确性依赖阈值；跟 v3 spec "实体独立存 PG" 冲突 |
| Embedding 聚类（sentence-transformers） | ❌ 重，本项目暂无 sentence-transformers 依赖 |

**结论**：采用**抽取前 synonym rule**（spaCy Matcher patterns + 同义表），**最轻**，跟 v3 spec 架构吻合。

### 单位归一

| 做法 | 适配 |
|---|---|
| 抽取时 LLM 输出 `{value, unit}` 2 字段，Neo4j 节点存 `value + unit_normalized` | ✅ prompt 模板改动小 |
| 抽取后正则解析 | ❌ 跟 LLM 输出 schema 不匹配 |
| pint 库转换 | ❌ 项目无 pint 依赖 |

**结论**：prompt 模板加 `unit` 字段约定，不引入新库。

---

## 架构设计

### 后端目录布局（增量）

```
packages/service/
├── configs/
│   ├── extractors/
│   │   ├── llm_pydantic.yaml        # [改] 加 ontology 字段引用
│   │   └── spacy_rule.yaml          # [改] 加 ontology 字段引用
│   └── ontologies/                  # [新] 本体 yaml 目录
│       ├── default.yaml             # 通用（Product/Spec/Standard + BELONGS_TO/HAS_SPEC/MATCHES）
│       └── motor.yaml               # 西门子电机专用（Motor/Series/Option/Spec/Environment/Standard + 7 种 rel_type）
└── src/kg/
    ├── extractors/
    │   ├── base.py                  # [改] BaseExtractor 接 ontology 可选参数
    │   ├── llm_pydantic/
    │   │   └── extractor.py         # [改] prompt 模板根据 ontology 渲染
    │   └── spacy_rule/
    │       └── extractor.py         # [改] 加载 ontology.patterns + 同义词
    └── ontology.py                  # [新] OntologyLoader + validate_label + validate_rel_type
```

**关键决策**：
- ontology 文件放 `configs/ontologies/`（跟 `configs/extractors/` 同级，配置类资源统一管理）
- `OntologyLoader` 单例，按 dataset label 加载对应 yaml（`motor` → `motor.yaml`）
- 后端不引入 fuzzy 库 / pint / sentence-transformers（**严格控制依赖膨胀**，符合 v3 spec §不要做的事 #3）

### 前端目录布局（增量）

```
packages/web/
├── app/[locale]/knowledge/extract/[task_id]/
│   ├── page.tsx                      # 已落地
│   └── preview/                       # [新] preview 主页（独立 spec, 本 spec 不实现）
└── components/knowledge/extract/      # [新] preview UI 组件 (独立 spec)
```

**前置依赖说明**：本 spec **不实现** preview UI（归并 UI 必须有 preview 表格承载），仅在 §未来工作 列出。

---

## 抽象接口

### Ontology schema

```yaml
# configs/ontologies/motor.yaml
ontology_id: motor
dataset_label: motor                  # 跟 KG_ALLOWED_DATASETS=motor 对齐

# 业务 label 白名单 (LLM 强制从这里选)
labels:
  - Motor                            # 物理电机型号节点
  - Series                           # 电机系列 (1LE1 / 1LA4)
  - Option                           # 选件 (抱闸 / 编码器 / 防护罩)
  - Spec                             # 技术参数 (功率 / 电压 / 转速 / 机座号)
  - Standard                        # 适用标准 (IEC 60034 / GB 755)
  - Environment                      # 环境条件 (海拔 / 温度 / 湿度 / 防护等级)

# 关系白名单 (LLM 强制从这里选)
relations:
  - rel_type: BELONGS_TO             # 型号 → 系列
    domain: [Motor]                  # head label 限定
    range:  [Series]
  - rel_type: HAS_OPTION             # 型号 → 选件
    domain: [Motor]
    range:  [Option]
  - rel_type: HAS_SPEC               # 型号/选件 → 参数
    domain: [Motor, Option]
    range:  [Spec]
  - rel_type: MATCHES_STANDARD       # 型号 → 标准
    domain: [Motor]
    range:  [Standard]
  - rel_type: SUITABLE_FOR           # 型号 → 环境
    domain: [Motor]
    range:  [Environment]
  - rel_type: INCOMPATIBLE_WITH      # 互斥（rule_type=exclusion）
    domain: [Motor, Option]
    range:  [Motor, Option]
  - rel_type: REQUIRES               # 依赖（rule_type=dependency）
    domain: [Motor, Option]
    range:  [Motor, Option]
  - rel_type: DERATED_BY             # 降容（rule_type=derating）
    domain: [Motor]
    range:  [Environment, Spec]

# 5 个 rule_type (跟 v3 spec 一致, 在 prompt 里复用)
rule_types: [compatibility, dependency, exclusion, derating, factual]

# 同义异构词 (spaCy Matcher 阶段合并 span, llm_pydantic 后处理阶段强制替换)
# 1:N 链式归一: "抱闸" → "制动器" → "Brake" (三段归一, OntologyLoader 加 _flatten_synonyms 展开)
synonyms:
  抱闸: 制动器
  制动器: Brake
  减速机: 齿轮箱
  齿轮箱: Gearbox
  接线盒: 出线盒
  底脚: 安装脚
  自冷: 自扇冷
  单速: 多速
  单相: 三相
  防护等级: IP等级
  防护等级: IP防护
  千瓦: kW
  kW: 千瓦
  马力: hp
  hp: 马力

# 单位归一 (LLM prompt 阶段强制要求输出 unit 字段)
units:
  power:    [kW, hp, 千瓦, 马力]       # 归一到 kW
  voltage:  [V, kV, 伏, 千伏]         # 归一到 V
  length:   [mm, cm, m, inch, 毫米]   # 归一到 mm
  frequency:[Hz, kHz, 赫兹]
  speed:    [rpm, r/min, 转每分]      # 归一到 rpm
```

```yaml
# configs/ontologies/default.yaml (兜底, 不指定 ontology 时走这个)
ontology_id: default
dataset_label: _default
labels: [Product, Series, Spec, Standard]
relations:
  - {rel_type: BELONGS_TO, domain: [Product], range: [Series]}
  - {rel_type: HAS_SPEC,   domain: [Product], range: [Spec]}
  - {rel_type: MATCHES,    domain: [Product], range: [Standard]}
rule_types: [compatibility, dependency, exclusion, derating, factual]
synonyms: {}
units: {}
```

### OntologyLoader 接口

```python
# src/kg/ontology.py
from dataclasses import dataclass, field

@dataclass(frozen=True)
class OntologyRelation:
    rel_type: str
    domain: tuple[str, ...]   # head 允许的 label 集
    range: tuple[str, ...]    # tail 允许的 label 集

@dataclass(frozen=True)
class Ontology:
    ontology_id: str
    dataset_label: str
    labels: tuple[str, ...]
    relations: tuple[OntologyRelation, ...]
    rule_types: tuple[str, ...]
    synonyms: dict[str, str]            # "抱闸" → "制动器" (1:1 单跳)
    synonyms_chain: dict[str, str]      # [m2 修订] 链式展开后 "抱闸" → "Brake" (1:N 多跳)
    units: dict[str, list[str]]         # "power" → ["kW", "hp", ...]


class OntologyLoader:
    """单例, 按 dataset 加载 ontology yaml"""

    def __init__(self, config_dir: Path | None = None) -> None:
        self._dir = config_dir or _DEFAULT_DIR
        self._cache: dict[str, Ontology] = {}

    def load(self, dataset: str) -> Ontology:
        """dataset=motor → configs/ontologies/motor.yaml, 缺失则 default"""
        if dataset not in self._cache:
            path = self._dir / f"{dataset}.yaml"
            if not path.exists():
                path = self._dir / "default.yaml"
            onto = _parse_yaml(path)
            # [m2 修订] 链式展开 synonyms (处理 抱闸→制动器→Brake 这种 1:N 多跳)
            onto = Ontology(
                **asdict(onto) | {"synonyms_chain": _flatten_synonyms(onto.synonyms)}
            )
            self._cache[dataset] = onto
        return self._cache[dataset]

    def reset_cache(self) -> None:
        """测试 fixture 用, 显式清缓存"""
        self._cache.clear()

    def validate_label(self, dataset: str, label: str) -> bool:
        return label in self.load(dataset).labels

    def validate_rel(self, dataset: str, rel_type: str,
                     head_label: str, tail_label: str) -> bool:
        onto = self.load(dataset)
        for r in onto.relations:
            if r.rel_type == rel_type and head_label in r.domain and tail_label in r.range:
                return True
        return False


def _flatten_synonyms(synonyms: dict[str, str]) -> dict[str, str]:
    """1:N 链式展开. 例: {抱闸: 制动器, 制动器: Brake} → {抱闸: Brake, 制动器: Brake}"""
    result = {}
    for key, val in synonyms.items():
        # BFS 沿 chain 走到底
        visited = set()
        current = val
        while current in synonyms and current not in visited:
            visited.add(current)
            current = synonyms[current]
        result[key] = current
    # 自指 (e.g. 防护等级 → IP等级 → IP防护, 三层)
    # 不会无限循环 (visited 检查)
    return result
```

### 改动 BaseExtractor / 2 个 extractor

```python
# src/kg/extractors/base.py (新增 ontology 可选参数)
class BaseExtractor(Protocol):
    extractor_id: str
    def extract(self, chunks: list[TextChunk], ontology: Ontology | None = None) -> ExtractionResult: ...
```

```python
# src/kg/extractors/llm_pydantic/extractor.py
class LlmPydanticExtractor:
    extractor_id = "llm_pydantic"

    def __init__(self, llm=None, prompt_template: str = "", max_retries: int = 3):
        # 优先级（m2 修订）: 显式 prompt_template > ontology 渲染 > 兜底 _DEFAULT_PROMPT
        # 测试时 prompt_template 传非空不会被 ontology 覆盖
        self.llm = llm
        self.prompt_template = prompt_template
        self.max_retries = max_retries

    def extract(self, chunks, ontology=None):
        onto = ontology or _DEFAULT_ONTOLOGY
        prompt = self.prompt_template or _render_prompt(onto)
        # ... 后续跟 v3 一样, 校验 e["label"] in onto.labels + r["rel_type"] in [rel.rel_type for rel in onto.relations]
        # 校验失败: 丢弃 (不入 entities/relations), errors[] 累计
        # 后处理（m2 修订）: LLM 输出不可靠, 强制做 3 件事
        #   1. e["rule_type"] 不在 5 选 1 → 强制设 'factual' (兜底, 不丢关系)
        #   2. e["text"] 在 onto.synonyms 字典里 → 强制替换为归一词 (不依赖 LLM 自觉)
        #   3. e["value"] + e["unit"] 类型校验, unit 不在 onto.units 列表 → 强制设 None + errors[] 累计
        ...
```

```python
# src/kg/extractors/spacy_rule/extractor.py
class SpacyRuleExtractor:
    extractor_id = "spacy_rule"

    def __init__(self, nlp=None, patterns=None, ontology=None):
        self.nlp = nlp
        self.patterns = patterns or []
        self.ontology = ontology
        # 构造 Matcher 时合并 ontology.synonyms → 同一 label + 共享 entity_id

    def extract(self, chunks, ontology=None):
        onto = ontology or self.ontology
        # 加载 ontology.synonyms, 同义词的 spans 在同一 EntityRuler pattern 内共享同一 id
        ...
```

> **2026-07-02 spec 评审修订 (spaCy 合并 span gotcha)**: spaCy EntityRuler 的 `set_annotations` 按 `(length desc, start desc)` 排序 (`spacy/pipeline/entityruler.py sort_key = lambda m: (m[2]-m[1], -m[1])`)，**重叠 span 短的会被静默 drop**，不会自动 merge 多 token 同义 span。例如 "抱闸...制动器" 同段出现，长的 "制动器" 命中后，短的 "抱闸" 即便 id 相同也会被丢。**M4 实施时必须加后置 merge 阶段**：遍历 `doc.ents`，对相同 `ent_id_` 的实体合并 span + 取最长 text，不能假设 EntityRuler 原生解决。Regression test: 输入文本含 "抱闸...制动器"，验两条都进 entities。

### 改动 extract_runner

```python
# src/kg/extract_runner.py (改动点)
def run_extraction(
    task_id, dataset, source_uri, extractor, splitter,
    extractor_id="", splitter_id="",
    object_store=None, task_store=None,
    ontology: Ontology | None = None,           # [新] 可选, 默认走 loader.load(dataset)
    ontology_loader: OntologyLoader | None = None,
) -> None:
    ...
    loader = ontology_loader or OntologyLoader()
    onto = ontology or loader.load(dataset)

    # 调用 extractor 时透传 ontology
    result = extractor.extract(chunks, onto)
    ...
```

### PATCH items 加 merge_to 字段（schema 不动，仅 Pydantic 接受新字段）

```python
# src/kg/router.py (PatchItem 加可选字段)
class PatchItem(BaseModel):
    id: int
    selected: bool
    corrected_payload: dict | None = None
    merge_to: str | None = Field(None, description="归并目标实体的 text (NULL=不归并, v3 默认)")

class PatchItemsRequest(BaseModel):
    items: list[PatchItem]
```

**关键决策**：
- **merge_to 不落 PG 列**，仅作为 commit 阶段的归并提示：commit 时如果 `corrected_payload.merge_to` 存在，把 source_node 的 head/tail 文本替换为 target_text，Neo4j MERGE 用 target_value 去重
- 不引入新 PG 表 / 新 PG 列 / 新 alembic migration（**严格控制 schema 膨胀**）
- 前端 PATCH 调用沿用 v3 spec 端点（[`/api/kg/extract/tasks/{task_id}/items`](packages/service/src/kg/router.py)），**新增字段透传到 commit 阶段**

**v3 spec 兼容性**：
- 老 PATCH 请求（不带 `merge_to`）100% 兼容，行为不变
- 老 KG 数据（无 ontology 校验）100% 兼容，缺省走 `default.yaml`

---

## 配置文件

### `configs/extractors/llm_pydantic.yaml` 增量

```yaml
extractor_id: llm_pydantic
enabled: true
llm_provider: ""      # env: RAG_LLM_PROVIDER
model: ""              # env: RAG_LLM_MODEL
temperature: 0.0
# [新] 引用 ontology (默认 dataset=任意 → default.yaml; motor → motor.yaml)
# 留空 = 走 default
# ontology_ref: motor    # 强制按 dataset 走 motor.yaml (推荐)
```

### `configs/extractors/spacy_rule.yaml` 增量

```yaml
extractor_id: spacy_rule
enabled: true
spacy_model: zh_core_web_sm
patterns:                # [保留] 默认 patterns, ontology 加载时会 merge
  - label: Product
    pattern: "\\d[A-Z]{2}\\d{4}-[A-Z0-9]+"
# [新] ontology_ref 同步
# ontology_ref: motor
```

### Prompt 模板（[llm_pydantic.prompt.txt](../../packages/service/configs/extractors/llm_pydantic.prompt.txt) 替换）

```
你是西门子电机知识图谱抽取专家. 从以下 Markdown 文本抽取实体和关系.

## 业务 label 白名单（只能从这里选, 不能自创）
{{ onto.labels | join(" / ") }}

## 关系白名单（只能从这里选）
{{ onto.relations_table }}

## 关系类型 5 选 1
{{ onto.rule_types | join(" / ") }}

## 单位约定
参数类实体的 value + unit 字段必须分写, 单位用以下枚举:
- 功率 (Spec.label='功率'): kW / hp / 千瓦 / 马力 → 归一 kW
- 电压 (Spec.label='电压'): V / kV → 归一 V
- 长度: mm / cm / m / inch → 归一 mm
- 频率: Hz
- 转速: rpm / r/min → 归一 rpm

## 输出格式 (严格 JSON, 无任何额外文字)
{
  "entities": [
    {"text": "...", "label": "从白名单选", "value": 数字或null, "unit": "枚举值或null",
     "span": [start, end], "confidence": 0.0-1.0}
  ],
  "relations": [
    {"head": "...", "rel_type": "从白名单选",
     "tail": "...", "rule_type": "5选1", "confidence": 0.0-1.0}
  ]
}

## 同义异构词（这些词视为等价实体, 用归一词）
{{ onto.synonyms_table }}
```

---

## 实施拆分（4 Milestone / 约 2.5 工作日 / 11 commits）

> **2026-07-02 spec 评审修订**: 原 spec 估 1.5 天 / 8 commits, 实际 M1 涉及 ontology.py (≈120 行) + 2 个新 yaml (≈80 行) + 改 base.py Protocol (10 行) + 改 llm_pydantic extractor (≈40 行 ontology 校验 + 后处理) + 改 spacy_rule extractor (≈30 行 + M4 后置 merge 阶段 ≈40 行) + 改 extract_runner (≈15 行) + tests (≥250 行), 合计 ≈ 585 行, **超 CLAUDE.md §范围控制 500 行单 PR 红线**. 重拆为 5 PR (M0 ~ M4), 每个 PR ≤ 350 行.

| # | Milestone | 文件 | 行数估算 | 验证 | commits |
|---|---|---|---|---|---|
| **M0** | 旧数据 label migration 脚本 (3 选 1 方案 A) | `scripts/migrations/2026-07-02_motor_label_normalize.py` [新] + tests | 100 | `uv run pytest tests/migrations/test_motor_label_normalize.py -v` (mock store) | 1 |
| **M1a** | OntologyLoader + default.yaml + motor.yaml | `src/kg/ontology.py` [新] + `configs/ontologies/{default,motor}.yaml` [新] + tests | 250 | `uv run pytest tests/kg/test_ontology.py -v` | 2 |
| **M1b** | BaseExtractor 接 ontology 可选参数 + 2 个 extractor 校验 | `extractors/base.py` [改] + `llm_pydantic/extractor.py` [改] + `spacy_rule/extractor.py` [改] + `extract_runner.py` [改] + tests | 350 | `uv run pytest tests/kg/test_extractors_ontology.py -v` (跑 v3 测试确认无 break) | 3 |
| **M2** | Prompt 模板加 ontology 渲染（label / relation / rule_type / unit / synonym 5 段）+ 后处理 (rule_type 兜底 / synonyms 归一 / unit 校验) | `configs/extractors/llm_pydantic.yaml` [改] + `llm_pydantic.prompt.txt` [改] + `extractor.py` 渲染 + 后处理逻辑 + tests | 300 | `uv run pytest tests/kg/test_extractors_prompt.py tests/kg/test_extractors_postprocess.py -v` | 3 |
| **M3** | PATCH items 加 `merge_to` 可选字段 + commit 阶段实现归并 + 乐观锁 (并发 409, 不做环检测) | `src/kg/router.py` (PatchItem + PatchItemsRequest + commit 归并逻辑) + tests | 200 | `uv run pytest tests/kg/test_commit_merge.py -v` | 2 |
| **M4** | spacy_rule synonyms 加载 + 同 span 后置 merge 阶段 (处理 EntityRuler 重叠 span 短的被 drop) | `spacy_rule/extractor.py` [改] + tests | 150 | `uv run pytest tests/kg/extractors/test_spacy_synonyms.py -v` (含 "抱闸...制动器" regression test) | 2 |

**PR 拆分建议**（**严格 ≤ 500 行/单 PR**）：

- **PR1 = M0** (1 commit, 100 行) — 迁移脚本独立 PR, 不阻塞业务
- **PR2 = M1a** (2 commits, 250 行) — 纯新文件 + yaml, 零风险
- **PR3 = M1b** (3 commits, 350 行) — extractor 校验, 跑 v3 测试确认无 break
- **PR4 = M2** (3 commits, 300 行) — prompt + 后处理
- **PR5 = M3 + M4** (4 commits, 350 行) — merge_to + spacy 后置 merge

**前置依赖**：v3 spec M8 preview UI（**独立 spec 处理**，本 spec 不阻塞）。前端归并 UI 拆分到 **单独 spec**：M3 的 `merge_to` 字段定义后，前端 PATCH 调用照搬，仅 UI 层加 "归并到" 下拉框即可，不耦合。

**风险点**：
- M1b 改 BaseExtractor Protocol 是 HIGH 风险（公共契约改动），落地前**必跑 v3 测试基线**：`uv run pytest tests/kg/extractors/ -v` 全绿再加 ontology 参数。失败则改 instance attribute 方案 (extractor.ontology = onto, 不改 Protocol)。
- M0 migration 脚本错改 Neo4j 节点不可逆，必须 dev DB 演练 + `dry_run=True` 默认 + 完整 audit log + 1 admin + 1 dev 双人复核。

---

## 错误处理

| 失败点 | 降级行为 |
|---|---|
| ontology yaml 缺失 / 解析失败 | 兜底 `default.yaml`，loguru WARNING，**任务继续**（不阻塞业务） |
| LLM 输出 label 不在白名单 | 该 entity 丢弃，`errors[]` 累积 `"label 'XXX' not in motor ontology"` |
| LLM 输出 rel_type 不在白名单 / domain-range 不匹配 | 该 relation 丢弃，`errors[]` 累积 |
| LLM 输出 rule_type 不在 5 选 1 | **强制设 'factual' 兜底**，关系保留，`errors[]` 累积（关系不丢，比丢关系更安全） |
| LLM 输出 text 含同义词 | **后处理强制替换**为归一词（不依赖 LLM 自觉，参考 [spec 评审] 的 LLM 不可靠教训） |
| spaCy synonyms 加载失败 | 静默降级（继续 Matcher，不合并同义 span），loguru WARNING |
| merge_to 指向不存在的实体 text | commit 返 422 `merge_to target not found` |
| merge_to 并发 PATCH 冲突（同一 source 被 2 个 admin 同时改） | commit 返 409 `merge_to concurrent modification`（乐观锁，UPDATE ... WHERE version=N） |
| ~~merge_to 形成环 (A→B→A)~~ | **删**：Neo4j MERGE 自然幂等，环检测本身不必要且会误报合法操作 |

> **环检测删除根因**（2026-07-02 spec 评审）：Neo4j MERGE 本身是幂等的。commit 时 A 归并到 B 后，再 PATCH 改 A 的 merge_to=B，PG 表看 A→B 跟历史 B→A 形成"环"，但实际是同一节点。强制环检测会拒绝合法操作。删环检测 + 加并发 PATCH 的 409 乐观锁。

---

## 测试隔离（CLAUDE.md §强制 4 模式）

| 模块 | 模式 | Fixture | 备注 |
|---|---|---|---|
| `ontology.py` (parse + validate) | 1 | tmp yaml 文件 + `monkeypatch setattr(OntologyLoader, '_cache', {})` | **强制清缓存**（跨测试不复用，参考 datasets.ALLOWED_DATASETS 单例模式） |
| `llm_pydantic/extractor.py` 加 ontology | 1 | mock LLM + monkeypatch OntologyLoader | 验 prompt 渲染 + 校验丢弃逻辑 + 后处理（rule_type 兜底 / synonyms 归一 / unit 校验） |
| `spacy_rule/extractor.py` 加 ontology | 1 | mock spacy nlp | 验 synonyms 合并 span (含 "抱闸...制动器" regression test) |
| `extract_runner.py` 透传 ontology | 1 | mock TaskStore + ObjectStore + extractor + loader | 验 onto 透传 |
| `router.py` PATCH 加 merge_to | 1 | TestClient + mock KgClient + mock session_scope | 鉴权 + merge_to 字段接受 + 乐观锁 409 |
| `router.py` commit 归并逻辑 | 1 | mock KgClient + 准备 kg_extract_items test data (mock session) | 验 A→B 归并 + 并发冲突 409（**不做环检测**，Neo4j MERGE 幂等覆盖） |
| `scripts/migrations/2026-07-02_motor_label_normalize.py` | 1 | mock Neo4jStore + tmp drift_map yaml | 验 SET/REMOVE label 行为 + dry_run |

> **2026-07-02 spec 评审修订 (OntologyLoader 单例缓存)**: 跟 `datasets.ALLOWED_DATASETS` 同模式, 模块级 `_cache: dict[str, Ontology] = {}` 跨测试复用状态. 测试 fixture **必须显式清缓存**, 否则改 yaml 后断言假阳. 推荐 fixture: `@pytest.fixture(autouse=True) def _reset_ontology_cache(monkeypatch): monkeypatch.setattr("src.kg.ontology.OntologyLoader._cache", {})`. datasets.ALLOWED_DATASETS 走 `load_from_env(env_var='KG_ALLOWED_DATASETS_TEST')` 模式 (现有), 别直接改模块变量.

---

## 验证（Verification）

### 单元测试

```bash
# 后端
uv run pytest tests/kg/test_ontology.py -v                          # OntologyLoader + parse + validate
uv run pytest tests/kg/test_extractors_ontology.py -v              # 2 个 extractor 接 ontology
uv run pytest tests/kg/test_extractors_prompt.py -v                # prompt 渲染含 ontology 5 段
uv run pytest tests/kg/test_commit_merge.py -v                     # 归并 + 环检测
uv run pytest tests/kg/extractors/test_spacy_synonyms.py -v        # 同义词合并

# 代码质量铁律
uv run ruff format && uv run ruff check --fix && uv run pyright
```

### 手工 E2E（dev 环境）

1. 启动后端 `uv run python main.py` + 前端 `bun run dev`
2. 登录拿 super_admin token
3. 访问 `http://localhost:3000/zh/knowledge/extract`（注：**M8 preview UI 由另一 spec 落地，本 spec 不阻塞**；E2E 用 curl 直接调 API）
4. 准备测试 markdown：
   ```md
   ## 1LE1 系列 三相异步电机
   1LE0102-1AB42 适配海拔 3000 米, 防护等级 IP55, 功率 7.5 kW, 抱闸可选.
   不允许 1LE0102 与 1LE0103 同时使用 (互斥).
   ```
5. `curl -X POST /api/kg/extract/upload?dataset=motor` 上传
6. `curl -X POST /api/kg/extract/start` 启动（extractor=llm_pydantic, splitter=heading）
7. **验证抽取结果**：
   - entities 含 6 个 label（Motor / Series / Option / Spec / Standard / Environment）
   - relations 含 5 种 rel_type（BELONGS_TO / HAS_OPTION / HAS_SPEC / SUITABLE_FOR / INCOMPATIBLE_WITH）
   - "抱闸" 归一为 "制动器"（看 payload.text）
   - "7.5 kW" Spec 节点 value=7.5, unit="kW"
   - rule_type=exclusion 的 INCOMPATIBLE_WITH 关系存在
8. curl PATCH items 给某 entity 加 `merge_to: "1LE1系列"`，commit 验证 Neo4j 归并

### 业务验收（2026-07-02 头脑风暴基线）

| 验收项 | 期望 |
|---|---|
| 西门子 1LE1 / 1LA4 / 1SG6 三个系列混存 100 页手册 | Neo4j Browser 跑 `MATCH (n:Motor) RETURN count(n)` = 系列数 × 型号数（无重复） |
| `MATCH (n) WHERE n.label='Motor' RETURN n.text` | 只返回电机型号文本，无 `Product / 1LE1型号` 漂移 |
| `MATCH (m:Motor)-[:INCOMPATIBLE_WITH]->(n:Motor) RETURN m.text, n.text` | 返回 v3 spec 已抽出的互斥关系，rule_type=exclusion |
| 抱闸 / 制动器 查询 | Neo4j Browser 返回同一节点 |

---

## 不要做的事（Top 8）

1. **不引入 fuzzy match / rapidfuzz / sentence-transformers** —— 项目无依赖，引入需先评估 Neo4j 性能 + pyright strict 兼容
2. **不引入 pint / 单位转换库** —— 业务只要求抽取阶段规范化输出，不做实际数值换算（后续 spec 决定）
3. **不改 v3 spec 9 个端点签名** —— PATCH items 加可选字段，向后兼容 100%
4. **不落 PG 新列 / 新表** —— `merge_to` 走 `corrected_payload` JSONB 字段，零 schema 改动
5. **不实现 MLFB 状态机 / 不做 TIA Selection Tool 集成** —— 应用层 + 人工流程，单独 spec
6. **不改 spacy_rule 的 EntityRuler 行为（除非加同义词合并）** —— 兼容 v3 spec 测试
7. **不强制 ontology 必填** —— 缺省走 default.yaml，老用户不感知
8. **不在前端加归并 UI** —— 拆到独立 spec，本 spec 完成后 PATCH API 已支持 merge_to，前端按需接入

---

## 未来工作（独立 spec，2026-07-02 后另起）

| # | 工作 | 工作量 | 立项依据 |
|---|---|---|---|
| 1 | **M8 preview UI**（v3 spec 剩余）：`/knowledge/extract` 主页（dataset + extractor + splitter + 文件）+ `/extract/{id}/preview` 实体表 + 关系表 | 1.5 天 | v3 spec M8 未落地，task 页按钮跳 404 |
| 2 | **前端归并 UI**（接本 spec M3）：preview 表格加 "归并到" 下拉框 | 0.5 天 | 依赖 #1 |
| 3 | **MLFB 订货号生成器**（西门子方案 4.4 状态机）：基于 Neo4j `Motor-[:HAS_OPTION]->Option` + `Option-[:REQUIRES]->Option` 规则遍历 | 3 天 | 应用层，跟 v3 spec 解耦 |
| 4 | **TIA Selection Tool 反向验证**（西门子方案 5.2） | 3-6 个月 (商务谈判 + 授权费) + 5 天 adapter 实施; 或务实改 OCR TIA 截图 + 半人工对比, 1 周 | 需 Siemens 商业 API 授权 (TIA Portal 无公开 REST API), spec 评审调研表明该 URL 多处 404 |
| 5 | **跨系列一致性检查**（西门子方案 5.1）：admin 后台工具，跑 `MATCH (m:D81_Motor)-[r]->(n:D84_Series)` 找灰区 | 1 天 | 管理员人工流程，非自动化 |
| 6 | **DependencyParser 集成**（西门子方案 4.2 句法分析）：spacy `parser` pipeline 增强 | 1 天 | LLM 已覆盖 90%，评估投入产出 |

---

## 关联文档

- 项目根 [CLAUDE.md](../../CLAUDE.md) — 代码质量铁律, 工具链锁定
- 前置 spec [`2026-07-01-markdown-extract-kg-design.md`](./2026-07-01-markdown-extract-kg-design.md) — v3 markdown 抽取
- 方案原文 [`../rag/西门子电机隐性规则挖掘与图谱构建任务流 .md`](../rag/西门子电机隐性规则挖掘与图谱构建任务流%20.md)
- 后端 [`packages/service/CLAUDE.md`](../../packages/service/CLAUDE.md) — 4 测试模式 + @audited
- 前端 [`packages/web/CLAUDE.md`](../../packages/web/CLAUDE.md) — i18n + 组件封装 + 路由跳转
- Ontology SOTA 调研: <https://neo4j.com/docs/knowledge-graph/getting-started/>
- LLM KG construction 2026: <https://arxiv.org/abs/2503.10381> (survey paper)

---

## 待用户审阅

本 spec 是派 agent 联网验证 + 对抗性审查后的**定稿版**，请审阅以下决策点：

1. **本体 yaml 粒度**：`motor.yaml` 6 label + 8 rel_type 是否覆盖西门子方案第一阶段 1.2~1.3？
2. **merge_to 不落 PG 列**：是否接受走 `corrected_payload` JSONB（零 schema 改动）？还是坚持独立列？
3. **M8 preview UI 拆独立 spec**：是否同意本 spec 不阻塞 M8，由独立 spec 完成？
4. **同义词表初版**（抱闸/制动器 等 5 对）：是否需要扩充？业务侧词典谁维护？
5. **方案 B 不耦合 M8**：前端归并 UI 单独 spec 落地，OK 吗？