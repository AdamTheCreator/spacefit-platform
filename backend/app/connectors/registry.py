"""
Connector Registry.

Discovers and loads connector manifests from YAML/JSON files, validates
them, instantiates the connector class, and provides lookup APIs for the
router and sub-agents.
"""

from __future__ import annotations

import importlib
import logging
from pathlib import Path
from typing import Any

import yaml

from app.connectors.interface import BaseConnector
from app.connectors.schemas.errors import ConnectorError, ErrorCode, ErrorSeverity
from app.connectors.schemas.manifest import ConnectorManifest, ExecutionMode

logger = logging.getLogger("connectors.registry")


class ConnectorRegistry:
    """
    Singleton registry that holds all known connectors keyed by
    connector_id.
    """

    _instance: ConnectorRegistry | None = None

    def __init__(self) -> None:
        self._manifests: dict[str, ConnectorManifest] = {}
        self._classes: dict[str, type[BaseConnector]] = {}

    # ------------------------------------------------------------------
    # Singleton access
    # ------------------------------------------------------------------

    @classmethod
    def get_instance(cls) -> ConnectorRegistry:
        if cls._instance is None:
            cls._instance = ConnectorRegistry()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton (useful for tests)."""
        cls._instance = None

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load_directory(self, directory: str | Path) -> int:
        """
        Scan *directory* for manifest.yaml / manifest.json files and
        register each connector found.

        Returns the number of connectors successfully loaded.
        """
        directory = Path(directory)
        if not directory.is_dir():
            logger.warning("Manifest directory does not exist: %s", directory)
            return 0

        loaded = 0
        for child in sorted(directory.iterdir()):
            if child.is_dir():
                # Look for manifest.yaml or manifest.json inside
                for suffix in ("yaml", "yml", "json"):
                    manifest_file = child / f"manifest.{suffix}"
                    if manifest_file.exists():
                        try:
                            self.load_manifest(manifest_file)
                            loaded += 1
                        except Exception:
                            logger.exception(
                                "Failed to load manifest: %s", manifest_file
                            )
                        break
            elif child.suffix in (".yaml", ".yml", ".json"):
                try:
                    self.load_manifest(child)
                    loaded += 1
                except Exception:
                    logger.exception("Failed to load manifest: %s", child)

        logger.info(
            "ConnectorRegistry loaded %d connector(s) from %s", loaded, directory
        )
        return loaded

    def load_manifest(self, path: str | Path) -> ConnectorManifest:
        """Load and register a single manifest file."""
        path = Path(path)
        raw = self._read_file(path)
        manifest = ConnectorManifest(**raw)
        self.register(manifest)
        logger.info("Registered connector: %s (v%s)", manifest.connector_id, manifest.version)
        return manifest

    def register(self, manifest: ConnectorManifest) -> None:
        """Register a manifest and resolve its connector class."""
        connector_cls = self._resolve_class(manifest.module)
        self._manifests[manifest.connector_id] = manifest
        self._classes[manifest.connector_id] = connector_cls

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get_manifest(self, connector_id: str) -> ConnectorManifest:
        if connector_id not in self._manifests:
            raise ConnectorError(
                code=ErrorCode.PLATFORM_CONNECTOR_NOT_FOUND,
                message=f"Connector '{connector_id}' is not registered.",
                severity=ErrorSeverity.PERMANENT,
            )
        return self._manifests[connector_id]

    def create_connector(self, connector_id: str) -> BaseConnector:
        """Instantiate and return a new connector instance."""
        manifest = self.get_manifest(connector_id)
        cls = self._classes[connector_id]
        return cls(manifest)

    def list_connectors(self) -> list[ConnectorManifest]:
        return list(self._manifests.values())

    def find_by_capability(self, capability: str) -> list[ConnectorManifest]:
        """Return manifests whose capabilities include *capability*."""
        return [
            m for m in self._manifests.values()
            if capability in m.capabilities
        ]

    def find_by_mode(self, mode: ExecutionMode) -> list[ConnectorManifest]:
        return [
            m for m in self._manifests.values()
            if mode in m.execution_modes
        ]

    @property
    def connector_ids(self) -> list[str]:
        return list(self._manifests.keys())

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _read_file(path: Path) -> dict[str, Any]:
        text = path.read_text(encoding="utf-8")
        if path.suffix in (".yaml", ".yml"):
            return yaml.safe_load(text)
        else:
            import json
            return json.loads(text)

    @staticmethod
    def _resolve_class(dotted_path: str) -> type[BaseConnector]:
        """Import a class from a dotted Python path."""
        module_path, _, class_name = dotted_path.rpartition(".")
        if not module_path:
            raise ConnectorError(
                code=ErrorCode.PLATFORM_CONFIG_INVALID,
                message=f"Invalid module path: {dotted_path}",
                severity=ErrorSeverity.PERMANENT,
            )
        try:
            module = importlib.import_module(module_path)
            cls = getattr(module, class_name)
        except (ImportError, AttributeError) as exc:
            raise ConnectorError(
                code=ErrorCode.PLATFORM_CONFIG_INVALID,
                message=f"Cannot import connector class '{dotted_path}': {exc}",
                severity=ErrorSeverity.PERMANENT,
            ) from exc
        if not (isinstance(cls, type) and issubclass(cls, BaseConnector)):
            raise ConnectorError(
                code=ErrorCode.PLATFORM_CONFIG_INVALID,
                message=f"'{dotted_path}' is not a BaseConnector subclass.",
                severity=ErrorSeverity.PERMANENT,
            )
        return cls
