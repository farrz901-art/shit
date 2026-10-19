"""create log tables (app_logs, error_logs, audit_logs)

Revision ID: 20260617_001000
Revises: 20260617_000000
Create Date: 2026-06-17 00:00:00.000000
"""

from __future__ import annotations

from alembic import op

revision = "20260617_001000"
down_revision = "20260617_000000"  # RBAC migration, latest before this
branch_labels = None
depends_on = None


def upgrade() -> None:
    # app_logs
    op.execute("""
        CREATE TABLE app_logs (
            id          BIGSERIAL,
            ts          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            level       TEXT NOT NULL CHECK (level IN ('DEBUG','INFO','WARNING','ERROR','CRITICAL')),
            logger      TEXT NOT NULL,
            message     TEXT NOT NULL,
            request_id  UUID,
            user_id     BIGINT,
            trace_id    CHAR(32),
            context     JSONB NOT NULL DEFAULT '{}'::jsonb
        ) PARTITION BY RANGE (ts);
    """)
    op.execute("CREATE TABLE app_logs_2026_06 PARTITION OF app_logs FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');")
    op.execute("CREATE TABLE app_logs_2026_07 PARTITION OF app_logs FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');")
    op.execute("CREATE INDEX idx_app_logs_ts_brin ON app_logs USING BRIN (ts);")
    op.execute("CREATE INDEX idx_app_logs_user_ts ON app_logs (user_id, ts DESC);")
    op.execute("CREATE INDEX idx_app_logs_context_gin ON app_logs USING GIN (context);")
    op.execute("CREATE INDEX idx_app_logs_errors ON app_logs (ts DESC) WHERE level IN ('ERROR', 'CRITICAL');")

    # error_logs
    op.execute("""
        CREATE TABLE error_logs (
            id              BIGSERIAL,
            ts              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            level           TEXT NOT NULL,
            exception_type  TEXT NOT NULL,
            exception_msg   TEXT NOT NULL,
            stacktrace      TEXT,
            request_id      UUID,
            user_id         BIGINT,
            path            TEXT,
            method          TEXT,
            status_code     INT,
            context         JSONB NOT NULL DEFAULT '{}'::jsonb
        ) PARTITION BY RANGE (ts);
    """)
    op.execute(
        "CREATE TABLE error_logs_2026_06 PARTITION OF error_logs FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');"
    )
    op.execute(
        "CREATE TABLE error_logs_2026_07 PARTITION OF error_logs FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');"
    )
    op.execute("CREATE INDEX idx_error_logs_ts_brin ON error_logs USING BRIN (ts);")
    op.execute("CREATE INDEX idx_error_logs_user_ts ON error_logs (user_id, ts DESC);")
    op.execute("CREATE INDEX idx_error_logs_exception_type ON error_logs (exception_type);")

    # audit_logs
    op.execute("""
        CREATE TABLE audit_logs (
            id          BIGSERIAL,
            ts          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            actor_id    BIGINT NOT NULL,
            actor_type  TEXT NOT NULL DEFAULT 'user',
            action      TEXT NOT NULL,
            target_type TEXT NOT NULL,
            target_id   TEXT NOT NULL,
            ip          INET,
            user_agent  TEXT,
            request_id  UUID,
            result      TEXT NOT NULL DEFAULT 'success',
            before      JSONB,
            after       JSONB,
            metadata    JSONB NOT NULL DEFAULT '{}'::jsonb
        ) PARTITION BY RANGE (ts);
    """)
    op.execute(
        "CREATE TABLE audit_logs_2026_06 PARTITION OF audit_logs FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');"
    )
    op.execute(
        "CREATE TABLE audit_logs_2026_07 PARTITION OF audit_logs FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');"
    )
    op.execute("CREATE INDEX idx_audit_logs_ts_brin ON audit_logs USING BRIN (ts);")
    op.execute("CREATE INDEX idx_audit_logs_actor_ts ON audit_logs (actor_id, ts DESC);")
    op.execute("CREATE INDEX idx_audit_logs_action_ts ON audit_logs (action, ts DESC);")
    op.execute("CREATE INDEX idx_audit_logs_target ON audit_logs (target_type, target_id);")
    op.execute("CREATE INDEX idx_audit_logs_metadata_gin ON audit_logs USING GIN (metadata);")

    # immutable trigger for audit_logs
    op.execute("""
        CREATE OR REPLACE FUNCTION reject_audit_modify() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_logs is append-only (no UPDATE/DELETE allowed)';
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER audit_logs_no_update BEFORE UPDATE ON audit_logs
            FOR EACH ROW EXECUTE FUNCTION reject_audit_modify();
    """)
    op.execute("""
        CREATE TRIGGER audit_logs_no_delete BEFORE DELETE ON audit_logs
            FOR EACH ROW EXECUTE FUNCTION reject_audit_modify();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_logs_no_delete ON audit_logs;")
    op.execute("DROP TRIGGER IF EXISTS audit_logs_no_update ON audit_logs;")
    op.execute("DROP FUNCTION IF EXISTS reject_audit_modify();")
    op.execute("DROP TABLE IF EXISTS audit_logs CASCADE;")
    op.execute("DROP TABLE IF EXISTS error_logs CASCADE;")
    op.execute("DROP TABLE IF EXISTS app_logs CASCADE;")
