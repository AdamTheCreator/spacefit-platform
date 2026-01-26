"""
Workflow step definitions.

Steps are the atomic units of a data-driven workflow.  They are declared
in YAML workflow files and interpreted by the APIRunner or BrowserRunner.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class StepType(str, Enum):
    # --- Browser steps ---
    OPEN = "open"                     # Navigate to URL
    SNAPSHOT = "snapshot"             # Capture page screenshot / accessibility tree
    CLICK = "click"                   # Click element by ref / selector
    TYPE = "type"                     # Type text into element
    WAIT = "wait"                     # Wait for URL, selector, or networkidle
    EXTRACT = "extract"              # Extract text or structured data
    DOWNLOAD = "download"            # Download a file
    STATE_SAVE = "state_save"        # Persist browser session
    STATE_LOAD = "state_load"        # Load persisted session
    SCROLL = "scroll"                # Scroll page or element

    # --- API steps ---
    HTTP_REQUEST = "http_request"    # Make an HTTP call
    PARSE_JSON = "parse_json"        # Parse JSON response body
    PAGINATE = "paginate"            # Follow pagination links/tokens

    # --- Control flow ---
    CONDITION = "condition"          # If/else branching
    LOOP = "loop"                    # Iterate over items
    SET_VAR = "set_var"              # Set a context variable
    LOG = "log"                      # Emit a log message


class WorkflowStep(BaseModel):
    """A single step in a workflow."""

    step_type: StepType
    description: str = ""

    # Shared parameters (interpreted per step_type)
    url: str | None = None
    selector: str | None = None
    ref: str | None = None          # Accessibility-tree ref
    value: str | None = None        # Text to type, variable to set, etc.
    headers: dict[str, str] = Field(default_factory=dict)
    body: dict[str, Any] | None = None
    method: str = "GET"             # For HTTP_REQUEST
    timeout_ms: int = 30_000

    # Extraction
    extract_type: str | None = None  # "text", "structured", "table", "json"
    extract_selector: str | None = None
    output_key: str | None = None   # Key to store extracted value in context

    # Control flow
    condition: str | None = None     # Python expression evaluated against context
    loop_over: str | None = None     # Context variable to iterate
    loop_as: str | None = None       # Variable name for current item
    sub_steps: list[WorkflowStep] | None = None

    # Wait
    wait_for: str | None = None      # "url:<pattern>", "selector:<sel>", "networkidle"

    # Misc
    save_artifact: bool = False      # Save screenshot/response as debug artifact


class WorkflowDefinition(BaseModel):
    """
    A complete data-driven workflow.  Referenced by a connector manifest
    via workflow_file or embedded inline.
    """

    name: str
    description: str = ""
    steps: list[WorkflowStep]
    variables: dict[str, Any] = Field(
        default_factory=dict,
        description="Default context variables available to steps",
    )
