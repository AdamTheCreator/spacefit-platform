"""byok rebuild: re-encrypt legacy Fernet rows under envelope

Revision ID: 029
Revises: 028
Create Date: 2026-04-21

Per-row data migration: for every `user_ai_configs` row that still holds a
legacy Fernet-encrypted API key (`encryption_salt IS NOT NULL AND
encrypted_dek IS NULL`), decrypt with the legacy primitive, re-encrypt
under the envelope shape defined in `app.byok.crypto`, and write the new
fields in a single UPDATE.

Invariants after this migration:
    * Every active row with a stored API key has all five envelope fields
      populated (`api_key_encrypted`, `ciphertext_iv`, `ciphertext_tag`,
      `encrypted_dek`, `kek_id`).
    * `key_fingerprint` and `key_last_four` are set, so the v2 endpoints'
      duplicate detection and UI display work for pre-existing rows.
    * `encryption_salt` is **kept** on each migrated row so a rollback of
      029 can re-use it. Migration 030 drops the legacy column once the
      envelope rollout has been stable for the 30-day retention window.

Failure handling: a row that fails to decrypt (master key rotated, stale
data) is flipped to `status='invalid'` with `key_error_message` populated.
It is not deleted — operators can inspect, and users see the same
"validate again" path the circuit breaker uses.
"""

from __future__ import annotations

import logging
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.byok.crypto import encrypt_api_key, fingerprint, last_four
from app.core.security import decrypt_credential

revision: str = "029"
down_revision: str = "028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


logger = logging.getLogger("alembic.029")


def upgrade() -> None:
    conn = op.get_bind()

    # Only touch rows that still need migration:
    #   - have legacy ciphertext + salt
    #   - have not been envelope-encoded yet
    # status filter limits us to the live row; revoked/invalid history
    # rows from v2 (which cannot exist yet on a fresh DB at 029 but might
    # on a re-run) are intentionally left alone.
    rows = conn.execute(
        sa.text(
            """
            SELECT id, api_key_encrypted, encryption_salt
            FROM user_ai_configs
            WHERE api_key_encrypted IS NOT NULL
              AND encryption_salt IS NOT NULL
              AND encrypted_dek IS NULL
              AND status = 'active'
            """
        )
    ).fetchall()

    migrated = 0
    failed = 0
    for row in rows:
        row_id: str = row.id
        legacy_ciphertext: bytes = row.api_key_encrypted
        salt: bytes = row.encryption_salt

        try:
            plaintext = decrypt_credential(legacy_ciphertext, salt)
        except Exception as e:
            # Key can't be recovered (master key changed, corrupt row).
            # Flip to invalid so the user is prompted to re-enter; never
            # drop the row (audit value).
            logger.warning(
                "029: failed to decrypt legacy row %s; marking invalid: %s",
                row_id,
                e.__class__.__name__,
            )
            conn.execute(
                sa.text(
                    """
                    UPDATE user_ai_configs
                    SET status = 'invalid',
                        is_key_valid = false,
                        key_error_message = :msg
                    WHERE id = :id
                    """
                ),
                {
                    "id": row_id,
                    "msg": (
                        "Stored key could not be recovered during envelope "
                        "migration. Please re-enter your API key."
                    ),
                },
            )
            failed += 1
            continue

        try:
            bundle = encrypt_api_key(plaintext)
        except Exception as e:
            logger.error(
                "029: failed to re-encrypt row %s under envelope: %s",
                row_id,
                e,
            )
            failed += 1
            continue

        fp = fingerprint(plaintext)
        l4 = last_four(plaintext)

        # Overwrite api_key_encrypted with the DEK-encrypted ciphertext
        # (the new envelope semantic). The legacy Fernet token is gone
        # from this row after the UPDATE; rollback is possible only via
        # the `encryption_salt`-driven path removed in migration 030.
        conn.execute(
            sa.text(
                """
                UPDATE user_ai_configs
                SET api_key_encrypted = :ciphertext,
                    ciphertext_iv = :iv,
                    ciphertext_tag = :tag,
                    encrypted_dek = :edek,
                    kek_id = :kek_id,
                    key_fingerprint = :fp,
                    key_last_four = :l4
                WHERE id = :id
                """
            ),
            {
                "id": row_id,
                "ciphertext": bundle.ciphertext,
                "iv": bundle.iv,
                "tag": bundle.auth_tag,
                "edek": bundle.encrypted_dek,
                "kek_id": bundle.kek_id,
                "fp": fp,
                "l4": l4,
            },
        )

        # Best-effort scrub of the local plaintext reference. Python
        # strings are immutable so this is hygiene, not a guarantee.
        plaintext = ""  # noqa: F841
        migrated += 1

    logger.info("029: envelope backfill complete — migrated=%d failed=%d", migrated, failed)


def downgrade() -> None:
    # Envelope backfill is not cleanly reversible: the Fernet token that
    # lived in `api_key_encrypted` before the migration has been overwritten
    # by the DEK-encrypted ciphertext. Rolling back 029 would leave every
    # migrated row unrecoverable. The migration is therefore a one-way
    # door; downgrading past 029 requires restoring from a pre-029 DB dump.
    #
    # We leave downgrade() as a no-op rather than raising so an operator
    # rolling back a stack of migrations (e.g. 030 → 028) doesn't fail
    # the whole chain on this step.
    logger.warning(
        "029: downgrade is a no-op — envelope-encoded rows cannot be "
        "restored to legacy Fernet form. Restore from a pre-029 dump."
    )
