"""byok rebuild: envelope columns, rotation/scope/governance, audit log

Revision ID: 028
Revises: 026
Create Date: 2026-04-21

Extends ``user_ai_configs`` to support:
- envelope encryption (encrypted_dek + kek_id + ciphertext_iv + ciphertext_tag
  alongside the existing api_key_encrypted, which becomes the DEK-encrypted
  ciphertext under the envelope model after migration 029 backfill)
- additive rotation (status column; partial unique index on active+rotating
  rows only, dropping the old one-row-per-user unique constraint)
- soft-delete on revoke (revoked_at, revoked_by)
- governance scope (scope JSON column: allowed/denied models, monthly caps)
- org-ready shape (scope_level, org_id nullable) for the future org rollout
- display helpers (key_fingerprint for dedupe, key_last_four for the UI)

Creates ``credential_audit_log`` (append-only, mirrors the shape of
``tool_call_log`` deliberately so existing operator tooling transfers).
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "028"
down_revision: str = "026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_names(table: str) -> set[str]:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    return {c["name"] for c in insp.get_columns(table)}


def _constraint_names(table: str) -> set[str]:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    names: set[str] = set()
    for uc in insp.get_unique_constraints(table):
        if uc.get("name"):
            names.add(uc["name"])
    return names


def _index_names(table: str) -> set[str]:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    return {idx["name"] for idx in insp.get_indexes(table) if idx.get("name")}


def upgrade() -> None:
    existing = _column_names("user_ai_configs")

    new_columns = [
        # Envelope-encryption fields. Nullable through the migration window;
        # 029 re-encrypts legacy rows. After 030 we can tighten to NOT NULL.
        ("ciphertext_iv", sa.Column("ciphertext_iv", sa.LargeBinary, nullable=True)),
        ("ciphertext_tag", sa.Column("ciphertext_tag", sa.LargeBinary, nullable=True)),
        ("encrypted_dek", sa.Column("encrypted_dek", sa.LargeBinary, nullable=True)),
        ("kek_id", sa.Column("kek_id", sa.String(50), nullable=True)),
        # Dedupe (sha256 of plaintext) + last-four for UI display.
        ("key_fingerprint", sa.Column("key_fingerprint", sa.String(64), nullable=True)),
        ("key_last_four", sa.Column("key_last_four", sa.String(8), nullable=True)),
        # Governance: JSON string with allowed_models, denied_models,
        # monthly_spend_cap_usd, monthly_request_cap. Kept as Text (not JSONB)
        # to match the prevailing style in this codebase (see tenant_categories,
        # specialist_models_json). Application-level parsing.
        (
            "scope",
            sa.Column("scope", sa.Text, nullable=False, server_default="{}"),
        ),
        # Rotation lifecycle: active | rotating | invalid | revoked.
        (
            "status",
            sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        ),
        # Org-ready. scope_level=user for all current rows; org_id stays null
        # until an organizations table exists.
        (
            "scope_level",
            sa.Column("scope_level", sa.String(10), nullable=False, server_default="user"),
        ),
        ("org_id", sa.Column("org_id", sa.String(36), nullable=True)),
        # Optional human label so users can tell rotated keys apart.
        ("label", sa.Column("label", sa.String(100), nullable=True)),
        # Usage + audit timestamps.
        ("last_used_at", sa.Column("last_used_at", sa.DateTime, nullable=True)),
        ("created_by", sa.Column("created_by", sa.String(36), nullable=True)),
        ("revoked_at", sa.Column("revoked_at", sa.DateTime, nullable=True)),
        ("revoked_by", sa.Column("revoked_by", sa.String(36), nullable=True)),
    ]
    for name, column in new_columns:
        if name not in existing:
            op.add_column("user_ai_configs", column)

    # Drop the one-row-per-user unique constraint. We want multiple rows per
    # user during rotation (one active + one rotating) and to retain revoked
    # rows for audit history. The partial unique index below enforces the
    # real invariant: at most one (user_id, provider) pair may be in
    # active|rotating status.
    for cname in _constraint_names("user_ai_configs"):
        if "user_id" in cname:
            op.drop_constraint(cname, "user_ai_configs", type_="unique")

    existing_indexes = _index_names("user_ai_configs")

    # Partial unique index (Postgres-only; the app is Postgres-only).
    if "ix_user_ai_configs_active_unique" not in existing_indexes:
        op.create_index(
            "ix_user_ai_configs_active_unique",
            "user_ai_configs",
            ["user_id", "provider"],
            unique=True,
            postgresql_where=sa.text("status IN ('active', 'rotating')"),
        )
    # Lookup helpers.
    if "ix_user_ai_configs_fingerprint" not in existing_indexes:
        op.create_index(
            "ix_user_ai_configs_fingerprint",
            "user_ai_configs",
            ["key_fingerprint"],
        )
    if "ix_user_ai_configs_user_status" not in existing_indexes:
        op.create_index(
            "ix_user_ai_configs_user_status",
            "user_ai_configs",
            ["user_id", "status"],
        )

    # Append-only audit log. Mirrors tool_call_log in shape so ops tooling
    # transfers. id is BigInteger because we expect this to accumulate.
    op.create_table(
        "credential_audit_log",
        sa.Column(
            "id",
            sa.BigInteger,
            sa.Identity(always=False),
            primary_key=True,
        ),
        # SET NULL so deleting a credential row doesn't orphan the audit
        # history; credential_fingerprint preserves the linkage after delete.
        sa.Column(
            "credential_id",
            sa.String(36),
            sa.ForeignKey("user_ai_configs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("credential_fingerprint", sa.String(64), nullable=True),
        # Subject: the owner of the credential.
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Actor: who performed the action. May differ from user_id (admin
        # revoking a user's key) or be NULL for system-initiated events
        # (auto-invalidation after repeated 401s).
        sa.Column(
            "actor_user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("provider", sa.String(30), nullable=True),
        sa.Column("request_id", sa.String(64), nullable=True),
        sa.Column("success", sa.Boolean, nullable=False),
        sa.Column("error_code", sa.String(50), nullable=True),
        # Called ``metadata_json`` rather than ``metadata`` — that name is
        # reserved by SQLAlchemy's declarative base.
        sa.Column("metadata_json", sa.Text, nullable=False, server_default="{}"),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_credential_audit_log_user_occurred",
        "credential_audit_log",
        ["user_id", sa.text("occurred_at DESC")],
    )
    op.create_index(
        "ix_credential_audit_log_credential_occurred",
        "credential_audit_log",
        ["credential_id", sa.text("occurred_at DESC")],
    )
    op.create_index(
        "ix_credential_audit_log_action",
        "credential_audit_log",
        ["action"],
    )


def downgrade() -> None:
    op.drop_index("ix_credential_audit_log_action", table_name="credential_audit_log")
    op.drop_index(
        "ix_credential_audit_log_credential_occurred",
        table_name="credential_audit_log",
    )
    op.drop_index(
        "ix_credential_audit_log_user_occurred",
        table_name="credential_audit_log",
    )
    op.drop_table("credential_audit_log")

    op.drop_index(
        "ix_user_ai_configs_user_status",
        table_name="user_ai_configs",
    )
    op.drop_index(
        "ix_user_ai_configs_fingerprint",
        table_name="user_ai_configs",
    )
    op.drop_index(
        "ix_user_ai_configs_active_unique",
        table_name="user_ai_configs",
    )

    # Recreate the old one-row-per-user unique constraint only if we can —
    # if rotation has produced more than one row per user this will fail,
    # which is deliberate: downgrade past this migration is irreversible
    # once rotation has happened.
    op.create_unique_constraint(
        "user_ai_configs_user_id_key",
        "user_ai_configs",
        ["user_id"],
    )

    for col in (
        "revoked_by",
        "revoked_at",
        "created_by",
        "last_used_at",
        "label",
        "org_id",
        "scope_level",
        "status",
        "scope",
        "key_last_four",
        "key_fingerprint",
        "kek_id",
        "encrypted_dek",
        "ciphertext_tag",
        "ciphertext_iv",
    ):
        op.drop_column("user_ai_configs", col)
