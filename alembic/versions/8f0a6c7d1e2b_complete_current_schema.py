"""complete current SQLAlchemy schema

Revision ID: 8f0a6c7d1e2b
Revises: 5ad3a2049a4a
Create Date: 2026-08-04

The original baseline predates the SSO, SCIM, incident, disaster recovery,
sector, and SIEM models. This revision brings a fresh Alembic database to the
same schema as aeon_db.Base.metadata.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "8f0a6c7d1e2b"
down_revision: str | Sequence[str] | None = "5ad3a2049a4a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "workspaces",
        sa.Column("theme_config", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )

    op.create_table(
        "sso_providers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("protocol", sa.String(length=10), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("attribute_mapping", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sso_providers_workspace_id", "sso_providers", ["workspace_id"])

    op.create_table(
        "scim_tokens",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scim_tokens_workspace_id", "scim_tokens", ["workspace_id"])
    op.create_index("ix_scim_tokens_token_hash", "scim_tokens", ["token_hash"])

    op.create_table(
        "workspace_security_configs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("pii_redaction_enabled", sa.Boolean(), nullable=False),
        sa.Column("phi_redaction_enabled", sa.Boolean(), nullable=False),
        sa.Column("data_region", sa.String(length=50), nullable=False),
        sa.Column("kms_key_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id"),
    )
    op.create_index(
        "ix_workspace_security_configs_workspace_id",
        "workspace_security_configs",
        ["workspace_id"],
        unique=True,
    )

    op.create_table(
        "anomalies",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("anomaly_type", sa.String(length=50), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("source_rule_id", sa.String(length=255), nullable=True),
        sa.Column("source_metric", sa.String(length=100), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("dismissed", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_anomalies_workspace_id", "anomalies", ["workspace_id"])

    op.create_table(
        "incident_runbooks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("triggers", sa.JSON(), nullable=False),
        sa.Column("actions", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_incident_runbooks_workspace_id", "incident_runbooks", ["workspace_id"])

    op.create_table(
        "incidents",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("root_cause_anomaly_id", sa.String(length=36), nullable=True),
        sa.Column("runbook_id", sa.String(length=36), nullable=True),
        sa.Column("assignee_user_id", sa.String(length=36), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["assignee_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["root_cause_anomaly_id"], ["anomalies.id"]),
        sa.ForeignKeyConstraint(["runbook_id"], ["incident_runbooks.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_incidents_workspace_id", "incidents", ["workspace_id"])

    op.create_table(
        "backup_policies",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("schedule", sa.String(length=50), nullable=False),
        sa.Column("retention_days", sa.Integer(), nullable=False),
        sa.Column("target", sa.String(length=50), nullable=False),
        sa.Column("target_config", sa.JSON(), nullable=False),
        sa.Column("encryption_enabled", sa.Boolean(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_backup_policies_workspace_id", "backup_policies", ["workspace_id"])

    op.create_table(
        "backup_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("policy_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("checksum", sa.String(length=255), nullable=True),
        sa.Column("storage_key", sa.String(length=1024), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["policy_id"], ["backup_policies.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_backup_jobs_workspace_id", "backup_jobs", ["workspace_id"])
    op.create_index("ix_backup_jobs_policy_id", "backup_jobs", ["policy_id"])

    op.create_table(
        "restore_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("backup_job_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["backup_job_id"], ["backup_jobs.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_restore_jobs_workspace_id", "restore_jobs", ["workspace_id"])
    op.create_index("ix_restore_jobs_backup_job_id", "restore_jobs", ["backup_job_id"])

    op.create_table(
        "dr_plans",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("rto_minutes", sa.Integer(), nullable=False),
        sa.Column("rpo_minutes", sa.Integer(), nullable=False),
        sa.Column("target_region", sa.String(length=50), nullable=False),
        sa.Column("failover_regions", sa.JSON(), nullable=False),
        sa.Column("contact_info", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("last_drill_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dr_plans_workspace_id", "dr_plans", ["workspace_id"])

    op.create_table(
        "dr_drills",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("plan_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("findings", sa.JSON(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["dr_plans.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dr_drills_workspace_id", "dr_drills", ["workspace_id"])
    op.create_index("ix_dr_drills_plan_id", "dr_drills", ["plan_id"])

    op.create_table(
        "identity_links",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("provider_id", sa.String(length=36), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["provider_id"], ["sso_providers.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_id", "external_id", name="uq_provider_external_id"),
    )
    op.create_index("ix_identity_links_user_id", "identity_links", ["user_id"])
    op.create_index("ix_identity_links_provider_id", "identity_links", ["provider_id"])
    op.create_index("ix_identity_links_external_id", "identity_links", ["external_id"])

    op.create_table(
        "siem_integrations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("endpoint_url", sa.String(length=2048), nullable=False),
        sa.Column("auth_type", sa.String(length=20), nullable=False),
        sa.Column("api_token_hash", sa.String(length=255), nullable=True),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("custom_headers", sa.JSON(), nullable=False),
        sa.Column("event_filters", sa.JSON(), nullable=False),
        sa.Column("log_level", sa.String(length=20), nullable=False),
        sa.Column("batch_size", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_siem_integrations_workspace_id", "siem_integrations", ["workspace_id"])

    op.create_table(
        "siem_export_logs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("integration_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("event_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("payload_size", sa.Integer(), nullable=True),
        sa.Column("response_text", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["integration_id"], ["siem_integrations.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("workspace_id", "integration_id", "event_type", "event_id"):
        op.create_index(f"ix_siem_export_logs_{column}", "siem_export_logs", [column])

    op.create_table(
        "sector_data",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("sector", sa.String(length=64), nullable=False),
        sa.Column("tool", sa.String(length=64), nullable=False),
        sa.Column("data_json", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "sector", "tool", name="uq_workspace_sector_tool"),
    )
    op.create_index("ix_sector_data_workspace_id", "sector_data", ["workspace_id"])
    op.create_index("ix_sector_data_sector", "sector_data", ["sector"])
    op.create_index("ix_sector_data_tool", "sector_data", ["tool"])


def downgrade() -> None:
    op.drop_index("ix_sector_data_tool", table_name="sector_data")
    op.drop_index("ix_sector_data_sector", table_name="sector_data")
    op.drop_index("ix_sector_data_workspace_id", table_name="sector_data")
    op.drop_table("sector_data")
    for column in ("event_id", "event_type", "integration_id", "workspace_id"):
        op.drop_index(f"ix_siem_export_logs_{column}", table_name="siem_export_logs")
    op.drop_table("siem_export_logs")
    op.drop_index("ix_siem_integrations_workspace_id", table_name="siem_integrations")
    op.drop_table("siem_integrations")
    op.drop_index("ix_identity_links_external_id", table_name="identity_links")
    op.drop_index("ix_identity_links_provider_id", table_name="identity_links")
    op.drop_index("ix_identity_links_user_id", table_name="identity_links")
    op.drop_table("identity_links")
    op.drop_index("ix_dr_drills_plan_id", table_name="dr_drills")
    op.drop_index("ix_dr_drills_workspace_id", table_name="dr_drills")
    op.drop_table("dr_drills")
    op.drop_index("ix_dr_plans_workspace_id", table_name="dr_plans")
    op.drop_table("dr_plans")
    op.drop_index("ix_restore_jobs_backup_job_id", table_name="restore_jobs")
    op.drop_index("ix_restore_jobs_workspace_id", table_name="restore_jobs")
    op.drop_table("restore_jobs")
    op.drop_index("ix_backup_jobs_policy_id", table_name="backup_jobs")
    op.drop_index("ix_backup_jobs_workspace_id", table_name="backup_jobs")
    op.drop_table("backup_jobs")
    op.drop_index("ix_backup_policies_workspace_id", table_name="backup_policies")
    op.drop_table("backup_policies")
    op.drop_index("ix_incidents_workspace_id", table_name="incidents")
    op.drop_table("incidents")
    op.drop_index("ix_incident_runbooks_workspace_id", table_name="incident_runbooks")
    op.drop_table("incident_runbooks")
    op.drop_index("ix_anomalies_workspace_id", table_name="anomalies")
    op.drop_table("anomalies")
    op.drop_index("ix_workspace_security_configs_workspace_id", table_name="workspace_security_configs")
    op.drop_table("workspace_security_configs")
    op.drop_index("ix_scim_tokens_token_hash", table_name="scim_tokens")
    op.drop_index("ix_scim_tokens_workspace_id", table_name="scim_tokens")
    op.drop_table("scim_tokens")
    op.drop_index("ix_sso_providers_workspace_id", table_name="sso_providers")
    op.drop_table("sso_providers")
    op.drop_column("workspaces", "theme_config")
