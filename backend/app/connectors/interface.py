"""
Standard connector interface.

Every connector — API, browser, or hybrid — implements this single abstract
class.  The platform orchestrates connectors exclusively through these five
methods, guaranteeing a uniform lifecycle.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.connectors.schemas.manifest import ConnectorManifest
from app.connectors.schemas.task import TaskRequest
from app.connectors.schemas.response import ConnectorResponse


class BaseConnector(ABC):
    """
    The contract every connector must satisfy.

    Lifecycle:
        1. validate_config()  — called once at registration to verify manifest
        2. authenticate()     — called before execute() when credentials exist
        3. execute()          — the main work; returns a ConnectorResponse
        4. normalize()        — transforms raw output into the declared schema
        5. teardown()         — cleanup (close sessions, release resources)
    """

    def __init__(self, manifest: ConnectorManifest) -> None:
        self.manifest = manifest

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @abstractmethod
    async def validate_config(self) -> bool:
        """
        Validate that the connector's configuration (manifest, secrets,
        user inputs) is complete and well-formed.

        Returns True if valid, raises ConnectorError otherwise.
        """
        ...

    @abstractmethod
    async def authenticate(
        self,
        credentials: dict[str, Any],
        *,
        tenant_id: str,
    ) -> bool:
        """
        Perform authentication against the target system.

        *credentials* contains decrypted secrets keyed by SecretField.key.
        The implementation chooses the auth flow based on manifest.auth_type.

        Returns True on success, raises ConnectorError on failure.
        """
        ...

    @abstractmethod
    async def execute(self, request: TaskRequest) -> ConnectorResponse:
        """
        Execute the data-retrieval task described by *request* and return
        a fully populated ConnectorResponse envelope.

        Implementations may delegate to the WorkflowRunner for data-driven
        browser/API workflows, or contain bespoke logic.
        """
        ...

    @abstractmethod
    async def normalize(self, raw: Any) -> dict[str, Any] | list[Any]:
        """
        Transform raw output from the target system into the connector's
        declared output_schema.

        Called internally by execute() before populating
        ConnectorResponse.data.
        """
        ...

    async def teardown(self) -> None:
        """
        Release any resources held by this connector instance.
        Override if the connector opens long-lived connections, browser
        contexts, temp files, etc.
        """
        pass
