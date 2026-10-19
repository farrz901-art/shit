"""fix(pre-analysis): stage CHECK 约束白名单加 prepare_input (2026-07-09)

2026-07-03 创建 ck_pre_analysis_task_stages_stage 时白名单是 5 个历史 stage
(load_config / extract_chapters / extract_tables / extract_flagged / write_outputs)。

2026-07-09 一次重构 (commit 68670162 附近) 把 stage 1 从 load_config 改成
prepare_input, 抽到 src/ingest/pre_analysis/prepare_input.py, 但没更新 CHECK 约束。

结果: 任何新 pre_analysis task 跑 stage 1 mark_stage_started 就炸
  psycopg.errors.CheckViolation: new row for relation "pre_analysis_task_stages"
  violates check constraint "ck_pre_analysis_task_stages_stage"
  DETAIL: ... stage='prepare_input' ...

修法: drop 旧约束, 重建包含 prepare_input (其他 4 个 stage 名不变, load_config
下掉, 代码里已不再 emit 它)。
"""

from __future__ import annotations

from alembic import op

revision = "20260709_000000"
down_revision = "20260706_000000"  # pre_analysis_task_config
branch_labels = None
depends_on = None


# 单一事实源: 跟 src/ingest/pre_analysis/ 下 5 个 stage 模块的 STAGE_NAME 字面值保持一致。
# 改了 stage 名必须同时改这俩 list, 否则 CHECK 约束会炸。
_STAGES_V2 = (
    "prepare_input",
    "extract_chapters",
    "extract_tables",
    "extract_flagged",
    "write_outputs",
)

# 旧白名单, downgrade 还原用。load_config 是 2026-07-09 重构前的 stage 1。
_STAGES_V1 = (
    "load_config",
    "extract_chapters",
    "extract_tables",
    "extract_flagged",
    "write_outputs",
)


def upgrade() -> None:
    """重命名历史 load_config 行 → prepare_input, drop 旧 CHECK 约束, 重建新白名单.

    顺序很关键:
      1. drop 旧 CHECK 约束 (为了能 UPDATE stage='load_config' → 'prepare_input',
         同时为下一步重建做准备)
      2. UPDATE 旧 load_config 行 (同一业务, 2026-07-09 重构只是改名, 行为不变)
      3. 重建新 CHECK 约束 (含 prepare_input, 不含 load_config)
    """
    op.drop_constraint(
        "ck_pre_analysis_task_stages_stage",
        "pre_analysis_task_stages",
        type_="check",
    )
    op.execute("UPDATE pre_analysis_task_stages SET stage = 'prepare_input' WHERE stage = 'load_config'")
    op.create_check_constraint(
        "ck_pre_analysis_task_stages_stage",
        "pre_analysis_task_stages",
        f"stage IN {tuple(_STAGES_V2)!r}",
    )


def downgrade() -> None:
    """downgrade 还原: prepare_input → load_config 改名, 重建旧白名单.

    ⚠️ 注意: 跑 downgrade 前必须先清空 prepare_input 行 (除了从 load_config 改名来的
    那些), 否则新 CHECK 约束 drop 之后跑 UPDATE 没问题, 但如果有更新引入的
    prepare_input 行, 反向 UPDATE 后会重新违反旧白名单 (这里白名单其实也含
    'load_config', 跟 prepare_input 互斥, 所以下面 UPDATE 一次过)。
    """
    op.drop_constraint(
        "ck_pre_analysis_task_stages_stage",
        "pre_analysis_task_stages",
        type_="check",
    )
    op.execute("UPDATE pre_analysis_task_stages SET stage = 'load_config' WHERE stage = 'prepare_input'")
    op.create_check_constraint(
        "ck_pre_analysis_task_stages_stage",
        "pre_analysis_task_stages",
        f"stage IN {tuple(_STAGES_V1)!r}",
    )
