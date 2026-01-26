# Connector Platform — Technical Design Document

## 1. Overview

The Connector Platform is a manifest-driven framework for executing data-retrieval
tasks against third-party sources. Sub-agents request data by **capability** (e.g.
`visitor_traffic`), and the platform selects, authenticates, executes, and normalizes
the response through the best available connector — without the agent knowing which
connector or execution mode was used.

**Key design principle:** New connectors are onboarded by adding a YAML manifest and
(optionally) a workflow file. No core orchestration code changes required.

## 2. Architecture

```
Sub-Agent
    │
    ▼
┌─────────────────────────────────────────────────┐
│              ConnectorPlatform                  │
│                (platform.py)                    │
│                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│  │  Router   │  │ Registry │  │ SecretManager│  │
│  │(router.py)│  │(registry)│  │ (secrets.py) │  │
│  └────┬─────┘  └────┬─────┘  └──────┬───────┘  │
│       │              │               │          │
│       ▼              ▼               ▼          │
│  ┌────────────────────────────────────────────┐ │
│  │            WorkflowRunner                  │ │
│  │         (workflow_runner.py)                │ │
│  │                                            │ │
│  │   ┌────────────┐    ┌────────────────┐     │ │
│  │   │ APIRunner   │    │ BrowserRunner  │     │ │
│  │   │ (httpx)     │    │ (Playwright)   │     │ │
│  │   └────────────┘    └────────────────┘     │ │
│  └────────────────────────────────────────────┘ │
│                                                 │
│  ┌────────────────┐  ┌───────────────────┐      │
│  │SecurityEnforcer│  │ConnectorTelemetry │      │
│  │ (security.py)  │  │  (telemetry.py)   │      │
│  └────────────────┘  └───────────────────┘      │
└─────────────────────────────────────────────────┘
    │
    ▼
ConnectorResponse (envelope)
```

## 3. Module Inventory

| Module | Responsibility |
|--------|---------------|
| `schemas/manifest.py` | ConnectorManifest Pydantic model. Loaded from YAML. |
| `schemas/task.py` | TaskRequest — what a sub-agent sends. |
| `schemas/response.py` | ConnectorResponse envelope — what comes back. |
| `schemas/errors.py` | Error codes, severity levels, catalog. |
| `interface.py` | BaseConnector abstract class (5-method contract). |
| `registry.py` | Discovers, loads, and indexes connector manifests. |
| `router.py` | Selects the best connector for a given capability + tenant. |
| `runner/steps.py` | Step type enum and WorkflowDefinition schema. |
| `runner/api_runner.py` | Executes HTTP workflow steps (httpx). |
| `runner/browser_runner.py` | Executes browser workflow steps (Playwright). |
| `runner/workflow_runner.py` | Orchestrates a full workflow, routing steps to API or browser runner. |
| `secrets.py` | Decrypts credentials from the existing SiteCredential model. |
| `security.py` | Domain allowlist, runtime/nav/content limits, secret redaction. |
| `telemetry.py` | Structured logging, trace_id, retry-with-backoff, MetricsStore. |
| `platform.py` | Top-level façade: route → auth → execute → normalize → respond. |

## 4. Data Flow

```
TaskRequest { capability: "visitor_traffic", tenant_id: "u-123", params: {address: "..."} }
        │
        ▼
   ConnectorRouter.select()
        │ finds: PlacerConnector (browser mode, score=62)
        ▼
   SecretManager.get_credentials(credential_id, tenant_id)
        │ returns decrypted { username, password }
        ▼
   PlacerConnector.authenticate(creds, tenant_id)
        │ verifies session exists (or raises AUTH_CAPTCHA_REQUIRED)
        ▼
   PlacerConnector.execute(request)
        │ loads workflow.yaml → WorkflowRunner.run()
        │   → BrowserRunner: open, wait, type, click, extract, snapshot, state_save
        ▼
   PlacerConnector.normalize(raw)
        │ structured dict matching output_schema
        ▼
   ConnectorResponse {
       status: "success",
       data: { property_name, visits, customer_profile },
       provenance: { pages_visited, steps_executed },
       metrics: { latency_ms, pages_visited, bytes_extracted },
       errors: []
   }
```

## 5. Connector Manifest Schema

Each connector declares the following in YAML:

- **connector_id** — unique slug
- **name, version, description** — identity
- **auth_type** — one of: `oauth`, `api_key`, `username_password`, `session_state`
- **execution_modes** — ordered list: `[api]`, `[browser]`, `[api, browser]`
- **allowed_domains** — strict URL allowlist for both HTTP and browser navigation
- **capabilities** — tags like `visitor_traffic`, `place_details`
- **rate_limit** — requests_per_minute, burst, cooldown
- **runtime_limits** — max seconds, max nav steps, max bytes
- **required_inputs** — user-facing parameters (address, date_range)
- **required_secrets** — API keys, passwords
- **output_schema** — JSON Schema reference (inline or external)
- **workflow_file** — optional YAML file defining data-driven steps
- **module** — Python dotted path to the connector class

## 6. Execution Modes

| Mode | Runner | Auth | Use When |
|------|--------|------|----------|
| API | APIRunner (httpx) | API key / OAuth | Official API exists |
| Hybrid | Both | Mixed | API + browser fallback |
| Browser | BrowserRunner (Playwright) | Session cookies | No API, CAPTCHA sites |

## 7. Routing Strategy

The router scores candidates on:
1. **Mode preference**: API (100) > hybrid (80) > browser (60)
2. **Rate limit headroom**: higher RPM = higher score
3. **Specialization**: fewer capabilities = slightly preferred (specialist)

Explicit `connector_id` in the request bypasses routing.

## 8. Security Model

- **Domain allowlist**: Every URL (HTTP and browser) is checked against the
  manifest's `allowed_domains`. Blocked attempts raise `SEC_DOMAIN_BLOCKED`.
- **Per-tenant isolation**: Browser sessions are keyed by `{tenant_id}_{connector_id}`.
  No session sharing across tenants.
- **Secrets**: Encrypted at rest (Fernet/AES-256). Decrypted only in-memory for
  the duration of a single execution. Never logged or included in telemetry.
- **Hard limits**: `max_runtime_seconds`, `max_navigation_steps`,
  `max_extracted_bytes` — enforced at every step boundary.
- **2FA / CAPTCHA**: Fail fast with `USER_ACTION_REQUIRED` status and
  `AUTH_CAPTCHA_REQUIRED` / `AUTH_2FA_REQUIRED` error code.

## 9. Error Taxonomy

Errors are grouped by prefix:

| Range | Category | Example |
|-------|----------|---------|
| E1xxx | Auth | `E1003 AUTH_CAPTCHA_REQUIRED` |
| E2xxx | Network (transient) | `E2001 NET_TIMEOUT` |
| E3xxx | Extraction | `E3001 EXTRACT_LAYOUT_CHANGED` |
| E4xxx | Security/policy | `E4001 SEC_DOMAIN_BLOCKED` |
| E5xxx | Platform | `E5002 PLATFORM_NO_CAPABLE_CONNECTOR` |

Each error carries a **severity** (`transient`, `permanent`, `user_action`)
and a **remediation** hint.

## 10. Observability

- **Structured logs**: Every event includes `connector_id`, `trace_id`, `task_id`.
- **Trace context**: `start_trace()` / `finish_trace()` bracket each execution.
- **MetricsStore**: In-process aggregation of success_rate, auth_failure_rate,
  median_latency, layout_change_rate per connector.
- **Retry with backoff**: `retry_with_backoff()` retries only transient errors
  with exponential delay (default: 3 attempts, 1s → 2s → 4s).
- **Debug artifacts**: On failure, `BrowserRunner.capture_failure_artifacts()`
  saves screenshots. Artifacts are returned in `ConnectorResponse.debug_artifacts`.

## 11. Integration with Existing Codebase

The platform reuses existing infrastructure:

| Existing Component | How It's Used |
|---|---|
| `BrowserManager` (singleton) | Browser context creation + session persistence |
| `SiteCredential` model | Credential storage and per-tenant ownership |
| `encrypt_credential` / `decrypt_credential` | Secret encryption at rest |
| FastAPI dependency injection | `get_db()` session for SecretManager |
| `browser_sessions/` directory | Session state file storage |

## 12. Future Extensibility

- **New connector**: Add a YAML manifest + connector class. No core changes.
- **New step types**: Add to `StepType` enum, implement handler in appropriate runner.
- **External workflow engine**: WorkflowRunner can be replaced with Temporal/Prefect.
- **Persistent metrics**: MetricsStore can be backed by Postgres or Prometheus.
- **Webhook callbacks**: Platform can be extended to emit webhooks on completion.
