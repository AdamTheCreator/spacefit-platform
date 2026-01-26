"""
Connector Platform.

A generic, manifest-driven platform for executing data-retrieval tasks
against third-party sources.  New connectors are onboarded by adding a
manifest (YAML/JSON) and optionally a workflow definition — no changes
to orchestration code required.

Quick start:

    from app.connectors import ConnectorPlatform

    platform = ConnectorPlatform()
    platform.load_connectors("connector_manifests")

    response = await platform.execute(TaskRequest(
        capability="visitor_traffic",
        tenant_id="user-123",
        params={"address": "123 Main St"},
    ))
"""

from app.connectors.interface import BaseConnector
from app.connectors.registry import ConnectorRegistry
from app.connectors.router import ConnectorRouter
from app.connectors.schemas import (
    ConnectorManifest,
    ConnectorResponse,
    TaskRequest,
)
from app.connectors.platform import ConnectorPlatform

__all__ = [
    "BaseConnector",
    "ConnectorManifest",
    "ConnectorPlatform",
    "ConnectorRegistry",
    "ConnectorResponse",
    "ConnectorRouter",
    "TaskRequest",
]
