"""
Secret management for the Connector Platform.

Wraps the existing app.core.security encryption and provides a clean
interface for connectors to retrieve decrypted credentials without ever
seeing the raw ciphertext.

INVARIANTS:
- Secrets are NEVER logged.
- Secrets are NEVER included in telemetry or error details.
- Secrets exist in memory only for the duration of a connector execution.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decrypt_credential
from app.db.models.credential import SiteCredential

logger = logging.getLogger("connectors.secrets")


class SecretManager:
    """
    Retrieves and decrypts credentials for connector use.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_credentials(
        self,
        credential_id: str,
        tenant_id: str,
    ) -> dict[str, Any]:
        """
        Load and decrypt a SiteCredential.

        Returns a dict with keys:
            - username
            - password
            - additional_config (dict, may be empty)
            - site_name
            - credential_id

        Raises ValueError if not found or not owned by tenant.
        """
        stmt = select(SiteCredential).where(
            SiteCredential.id == credential_id,
            SiteCredential.user_id == tenant_id,
        )
        result = await self._db.execute(stmt)
        cred = result.scalar_one_or_none()

        if cred is None:
            raise ValueError(
                f"Credential {credential_id} not found for tenant {tenant_id}"
            )

        username = ""
        password = ""
        additional: dict[str, Any] = {}

        if cred.username_encrypted:
            username = decrypt_credential(cred.username_encrypted)
        if cred.password_encrypted:
            password = decrypt_credential(cred.password_encrypted)
        if cred.additional_config_encrypted:
            import json
            raw = decrypt_credential(cred.additional_config_encrypted)
            try:
                additional = json.loads(raw)
            except Exception:
                additional = {}

        return {
            "username": username,
            "password": password,
            "additional_config": additional,
            "site_name": cred.site_name,
            "credential_id": cred.id,
        }

    async def get_api_key(
        self,
        credential_id: str,
        tenant_id: str,
    ) -> str:
        """
        Shortcut to retrieve just the password field (used for API-key
        based connectors where the API key is stored as the password).
        """
        creds = await self.get_credentials(credential_id, tenant_id)
        return creds["password"]

    async def get_credentials_by_site(
        self,
        site_name: str,
        tenant_id: str,
    ) -> dict[str, Any] | None:
        """
        Look up credentials by site_name instead of credential_id.
        Returns None if not found.
        """
        stmt = select(SiteCredential).where(
            SiteCredential.site_name == site_name,
            SiteCredential.user_id == tenant_id,
        )
        result = await self._db.execute(stmt)
        cred = result.scalar_one_or_none()
        if cred is None:
            return None
        return await self.get_credentials(cred.id, tenant_id)
