# Connector Platform — Developer Guide

## How to Add a New Connector

Adding a new connector requires **two files** (and optionally a third):

1. **Manifest** (`connector_manifests/<name>/manifest.yaml`)
2. **Connector class** (`app/connectors/examples/<name>/connector.py`)
3. **Workflow file** (optional, for data-driven browser/API steps)

### Step 1: Create the Manifest

Create `connector_manifests/my_connector/manifest.yaml`:

```yaml
connector_id: my_connector
name: My Data Source
version: "1.0.0"
description: Fetches data from My Data Source.

auth_type: api_key           # oauth | api_key | username_password | session_state
execution_modes: [api]       # api | hybrid | browser
allowed_domains:
  - api.mydatasource.com

capabilities:
  - my_data_type             # Tags that sub-agents use to find this connector

rate_limit:
  requests_per_minute: 30
  burst: 5
  cooldown_seconds: 2

runtime_limits:
  max_runtime_seconds: 60
  max_navigation_steps: 10
  max_extracted_bytes: 5000000

required_inputs:
  - key: query
    label: Search query
    type: string
    required: true

required_secrets:
  - key: api_key
    description: API key for My Data Source
    required: true

module: app.connectors.examples.my_connector.connector.MyConnector
```

### Step 2: Implement the Connector Class

Create `app/connectors/examples/my_connector/connector.py`:

```python
from typing import Any
from app.connectors.interface import BaseConnector
from app.connectors.schemas.manifest import ConnectorManifest
from app.connectors.schemas.task import TaskRequest
from app.connectors.schemas.response import ConnectorResponse, ResponseStatus, Metrics, Provenance
from app.connectors.schemas.errors import ConnectorError, ErrorCode, ErrorSeverity
import httpx
import time


class MyConnector(BaseConnector):
    def __init__(self, manifest: ConnectorManifest) -> None:
        super().__init__(manifest)
        self._api_key = ""

    async def validate_config(self) -> bool:
        # Verify manifest is well-formed
        return True

    async def authenticate(self, credentials: dict[str, Any], *, tenant_id: str) -> bool:
        self._api_key = credentials.get("api_key") or credentials.get("password", "")
        if not self._api_key:
            raise ConnectorError(
                code=ErrorCode.AUTH_MISSING_CREDENTIALS,
                message="No API key provided.",
                severity=ErrorSeverity.PERMANENT,
            )
        return True

    async def execute(self, request: TaskRequest) -> ConnectorResponse:
        t0 = time.monotonic()
        query = request.params.get("query", "")

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://api.mydatasource.com/search",
                params={"q": query},
                headers={"Authorization": f"Bearer {self._api_key}"},
            )

        raw = resp.json()
        data = await self.normalize(raw)
        elapsed = int((time.monotonic() - t0) * 1000)

        return ConnectorResponse(
            task_id=request.task_id,
            trace_id=request.trace_id,
            status=ResponseStatus.SUCCESS,
            data=data,
            metrics=Metrics(latency_ms=elapsed, api_calls_made=1),
            provenance=Provenance(
                source_connector=self.manifest.connector_id,
                execution_mode="api",
            ),
        )

    async def normalize(self, raw: Any) -> dict[str, Any]:
        # Transform API response into your declared output schema
        return {"results": raw.get("data", [])}

    async def teardown(self) -> None:
        self._api_key = ""
```

Don't forget the `__init__.py`:

```python
# app/connectors/examples/my_connector/__init__.py
```

### Step 3 (Optional): Data-Driven Workflow

For browser-based or complex multi-step connectors, add a workflow file:

```yaml
# connector_manifests/my_connector/workflow.yaml
name: my_workflow
description: Multi-step data extraction

variables:
  base_url: "https://app.mydatasource.com"

steps:
  - step_type: state_load
    description: Load saved session

  - step_type: open
    url: "{{base_url}}/dashboard"
    description: Navigate to dashboard

  - step_type: wait
    wait_for: networkidle
    timeout_ms: 10000

  - step_type: type
    selector: "#search-box"
    value: "{{query}}"
    description: Enter search query

  - step_type: click
    selector: "#search-button"
    description: Submit search

  - step_type: wait
    wait_for: "selector:.results-table"
    timeout_ms: 15000

  - step_type: extract
    extract_type: table
    extract_selector: ".results-table"
    output_key: _result
    description: Extract results table

  - step_type: state_save
    description: Persist session
```

Then reference it in your manifest:
```yaml
workflow_file: workflow.yaml
```

And update your connector to use `WorkflowRunner`:
```python
from app.connectors.runner.workflow_runner import WorkflowRunner

async def execute(self, request: TaskRequest) -> ConnectorResponse:
    workflow = WorkflowRunner.load_workflow("connector_manifests/my_connector/workflow.yaml")
    runner = WorkflowRunner(manifest=self.manifest, browser_runner=browser_runner)
    return await runner.run(request, workflow, initial_context=request.params)
```

### Step 4: Register and Test

The platform auto-discovers manifests at startup:

```python
from app.connectors import ConnectorPlatform

platform = ConnectorPlatform()
platform.load_connectors("connector_manifests")
```

---

## Available Workflow Step Types

### Browser Steps

| Step | Parameters | Description |
|------|-----------|-------------|
| `open` | `url` | Navigate to URL |
| `snapshot` | — | Screenshot + accessibility tree |
| `click` | `selector` or `ref` | Click element |
| `type` | `selector`, `value` | Fill input field |
| `wait` | `wait_for` (networkidle, url:pattern, selector:sel) | Wait for condition |
| `extract` | `extract_type` (text, structured, table, json), `extract_selector`, `output_key` | Extract data |
| `download` | `selector` | Download triggered by click |
| `scroll` | `value` (down, up, bottom) | Scroll page |
| `state_save` | — | Save browser session cookies |
| `state_load` | — | Signal to load saved session |

### API Steps

| Step | Parameters | Description |
|------|-----------|-------------|
| `http_request` | `url`, `method`, `headers`, `body`, `output_key` | Make HTTP call |
| `parse_json` | `value` (source key), `output_key` | Parse JSON string |
| `paginate` | `method`, `output_key` | Follow pagination |

### Control Flow Steps

| Step | Parameters | Description |
|------|-----------|-------------|
| `set_var` | `output_key`, `value` | Set context variable |
| `log` | `value` | Emit log message |
| `condition` | `condition`, `sub_steps` | If/else branch |
| `loop` | `loop_over`, `loop_as`, `sub_steps` | Iterate items |

### Variable Interpolation

Use `{{variable_name}}` in any string field. Variables come from:
- `workflow.variables` defaults
- `request.params`
- `output_key` from previous steps

---

## Response Envelope

Every execution returns:

```json
{
  "task_id": "abc123",
  "trace_id": "xyz789",
  "status": "success | failure | partial | user_action_required",
  "data": { ... },
  "provenance": {
    "source_connector": "google_places",
    "execution_mode": "api",
    "pages_visited": [],
    "workflow_steps_executed": 3
  },
  "metrics": {
    "latency_ms": 450,
    "pages_visited": 0,
    "bytes_extracted": 2048,
    "api_calls_made": 1,
    "retries": 0
  },
  "errors": [],
  "debug_artifacts": {}
}
```

---

## Error Handling

Connectors should raise `ConnectorError` with appropriate codes:

```python
from app.connectors.schemas.errors import ConnectorError, ErrorCode, ErrorSeverity

# Transient — platform will retry
raise ConnectorError(
    code=ErrorCode.NET_TIMEOUT,
    message="Request timed out",
    severity=ErrorSeverity.TRANSIENT,
)

# User action needed — platform surfaces to user
raise ConnectorError(
    code=ErrorCode.AUTH_CAPTCHA_REQUIRED,
    message="CAPTCHA detected",
    severity=ErrorSeverity.USER_ACTION,
    remediation="Complete manual login.",
)

# Permanent — no retry
raise ConnectorError(
    code=ErrorCode.EXTRACT_NO_DATA,
    message="No results found for query.",
    severity=ErrorSeverity.PERMANENT,
)
```

---

## Testing Checklist

When onboarding a new connector, verify:

- [ ] Manifest loads without validation errors
- [ ] `validate_config()` passes
- [ ] `authenticate()` succeeds with valid credentials
- [ ] `authenticate()` raises `AUTH_MISSING_CREDENTIALS` with empty creds
- [ ] `execute()` returns `ResponseStatus.SUCCESS` for valid input
- [ ] `execute()` returns `ResponseStatus.FAILURE` with proper error code for invalid input
- [ ] `normalize()` output matches the declared `output_schema`
- [ ] Domain allowlist blocks navigation to unlisted domains
- [ ] Runtime limits are enforced (timeout, nav steps, content size)
- [ ] Secrets are not present in logs or response
- [ ] `teardown()` releases all resources
- [ ] Response envelope contains populated provenance and metrics

### Sample Test Harness

```python
import pytest
from app.connectors import ConnectorPlatform, TaskRequest

@pytest.fixture
def platform():
    p = ConnectorPlatform()
    p.load_connectors("connector_manifests")
    return p

@pytest.mark.asyncio
async def test_google_places_success(platform):
    request = TaskRequest(
        capability="place_details",
        tenant_id="test-user",
        params={"query": "Empire State Building"},
        credential_id=None,  # Would need real cred for integration test
    )
    # For unit tests, mock httpx responses
    response = await platform.execute(request)
    assert response.status in ("success", "failure")
    assert response.task_id == request.task_id
    assert response.trace_id == request.trace_id

@pytest.mark.asyncio
async def test_connector_registry_loads():
    from app.connectors.registry import ConnectorRegistry
    registry = ConnectorRegistry()
    count = registry.load_directory("connector_manifests")
    assert count >= 2
    assert "google_places" in registry.connector_ids
    assert "placer" in registry.connector_ids

@pytest.mark.asyncio
async def test_router_selects_api_over_browser():
    from app.connectors.router import ConnectorRouter
    from app.connectors.registry import ConnectorRegistry

    registry = ConnectorRegistry()
    registry.load_directory("connector_manifests")
    router = ConnectorRouter(registry)

    request = TaskRequest(
        capability="place_details",
        tenant_id="test",
        params={},
    )
    candidate = router.select(request)
    assert candidate.mode.value == "api"

@pytest.mark.asyncio
async def test_domain_enforcement():
    from app.connectors.security import SecurityEnforcer
    from app.connectors.schemas.manifest import ConnectorManifest, ExecutionMode, AuthType

    manifest = ConnectorManifest(
        connector_id="test",
        name="Test",
        auth_type=AuthType.API_KEY,
        execution_modes=[ExecutionMode.API],
        allowed_domains=["example.com"],
        capabilities=["test"],
        module="app.connectors.interface.BaseConnector",  # placeholder
    )
    enforcer = SecurityEnforcer(manifest)

    enforcer.check_domain("https://example.com/api")  # should pass

    with pytest.raises(Exception):
        enforcer.check_domain("https://evil.com/steal")  # should fail

@pytest.mark.asyncio
async def test_error_taxonomy():
    from app.connectors.schemas.errors import ConnectorError, ErrorCode, ErrorSeverity

    exc = ConnectorError(
        code=ErrorCode.NET_TIMEOUT,
        message="timed out",
        severity=ErrorSeverity.TRANSIENT,
    )
    assert exc.retryable is True

    exc2 = ConnectorError(
        code=ErrorCode.AUTH_INVALID_CREDENTIALS,
        message="bad creds",
        severity=ErrorSeverity.PERMANENT,
    )
    assert exc2.retryable is False
```

---

## File Layout

```
backend/
├── connector_manifests/                  # ← Manifests live here
│   ├── google_places/
│   │   └── manifest.yaml
│   └── placer/
│       ├── manifest.yaml
│       └── workflow.yaml
├── app/connectors/                       # ← Platform code
│   ├── __init__.py
│   ├── platform.py                       # Top-level façade
│   ├── interface.py                      # BaseConnector ABC
│   ├── registry.py                       # Manifest loading + lookup
│   ├── router.py                         # Connector selection
│   ├── secrets.py                        # Credential decryption
│   ├── security.py                       # Allowlists + limits
│   ├── telemetry.py                      # Logging + metrics + retry
│   ├── schemas/
│   │   ├── manifest.py                   # ConnectorManifest
│   │   ├── task.py                       # TaskRequest
│   │   ├── response.py                   # ConnectorResponse
│   │   └── errors.py                     # ErrorCode taxonomy
│   ├── runner/
│   │   ├── steps.py                      # Step types + WorkflowDefinition
│   │   ├── api_runner.py                 # HTTP step executor
│   │   ├── browser_runner.py             # Playwright step executor
│   │   └── workflow_runner.py            # Orchestrator
│   └── examples/
│       ├── google_places/
│       │   └── connector.py              # API-mode example
│       └── placer/
│           └── connector.py              # Browser-mode example
└── CONNECTOR_PLATFORM_DESIGN.md
└── CONNECTOR_DEVELOPER_GUIDE.md
```
