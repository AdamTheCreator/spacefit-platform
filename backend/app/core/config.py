from pydantic import Field, model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Space Goose"
    debug: bool = Field(default=False)
    api_prefix: str = "/api/v1"

    # CORS — list of explicit origins the API accepts XHR/fetch from.
    # Localhost entries are for local dev; production hosts are for the
    # deployed SPA and any vanity domain. Render preview deployments are
    # covered by ``cors_origin_regex`` below rather than enumerated here.
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
        "https://spacegoose.ai",
        "https://www.spacegoose.ai",
        "https://app.spacegoose.ai",
        "https://spacegoose.onrender.com",
    ]
    # Regex-based origin check for Render's per-PR preview URLs
    cors_origin_regex: str = r"^https://spacegoose-pr-\d+\.onrender\.com$"

    # WebSocket
    ws_heartbeat_interval: int = 30

    # Database (SQLite for dev, PostgreSQL for production)
    database_url: str = Field(
        default="sqlite+aiosqlite:///./spacegoose.db"
    )

    @model_validator(mode="after")
    def _normalize_database_url(self) -> "Settings":
        # Render provides postgresql:// — rewrite to postgresql+asyncpg://
        url = self.database_url
        if url.startswith("postgresql://"):
            self.database_url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgres://"):
            self.database_url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        return self
    # SQLAlchemy async engine pool sizing. The old defaults (5 / 10) were
    # too small for production; under moderate concurrency + a slow
    # wake-from-sleep on Render Free Postgres, requests queued for a
    # connection and timed out. db_pool_timeout is the max seconds a
    # request will wait for a connection before failing fast (vs the
    # SQLAlchemy default of 30s, which is long enough to look like a
    # server hang to the client).
    db_pool_size: int = Field(default=20)
    db_max_overflow: int = Field(default=20)
    db_pool_timeout: int = Field(default=10)

    # JWT Authentication
    secret_key: str = Field(default="development-secret-key-change-in-production")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # Encryption (for storing credentials)
    encryption_master_key: str = Field(
        default="development-encryption-key-32bytes!"
    )

    # BYOK envelope encryption.
    # Active KEK id; must appear in the KEK registry below (or fall back to
    # encryption_master_key when id is 'v1' and no override is set). Rotate
    # by adding a new BYOK_KEK_<id> env var, flipping this pointer, and
    # running the re-wrap job.
    byok_kek_primary_id: str = Field(default="v1")
    # Additional KEK secrets, looked up by id. These are intentionally left
    # empty by default so production must set them explicitly. The reserved
    # id 'v1' falls back to encryption_master_key if byok_kek_v1 is empty,
    # preserving backwards compatibility during the 028/029 migration.
    byok_kek_v1: str = Field(default="")
    byok_kek_v2: str = Field(default="")
    byok_kek_v3: str = Field(default="")
    # Plaintext-key TTL cache (per credential id). Capped at 60s by the
    # crypto module regardless of what's configured here. Set to 0 to
    # disable caching entirely (each chat turn pays a KDF + decrypt cost).
    byok_decrypt_cache_ttl_seconds: int = Field(default=60)
    # Max in-flight requests per credential (separate from, and finer-grained
    # than, the per-client llm_max_concurrency limit).
    byok_per_key_max_concurrency: int = Field(default=10)
    # Credential-submission rate limit: `byok_submission_rate_limit` requests
    # per `byok_submission_window_seconds` per user. Protects `PUT /ai-config`
    # and `POST /ai-config/validate-key` from brute-force key probing.
    byok_submission_rate_limit: int = Field(default=5)
    byok_submission_window_seconds: int = Field(default=60)
    # After this many consecutive `credential_invalid` responses from a
    # provider, the gateway flips the credential to `status=invalid` and
    # forces the user to revalidate.
    byok_invalid_circuit_breaker_threshold: int = Field(default=5)
    # Feature flag for the rebuild. When False the repo-original endpoints
    # and resolution path are used unchanged, enabling instant rollback.
    byok_rebuild_enabled: bool = Field(default=False)

    # OAuth
    google_client_id: str = Field(default="")
    google_client_secret: str = Field(default="")
    google_redirect_uri: str = Field(
        default="http://localhost:8000/api/v1/auth/google/callback"
    )

    # Frontend URL (for OAuth redirects)
    frontend_url: str = Field(default="http://localhost:5174")

    # Gmail API Settings (for outreach campaigns - satisfies PRD G5)
    gmail_redirect_uri: str = Field(
        default="http://localhost:8000/api/v1/auth/gmail/callback"
    )

    # Anthropic AI
    anthropic_api_key: str = Field(default="")
    anthropic_model: str = Field(default="claude-3-haiku-20240307")

    # LLM Routing / Provider Abstraction
    # - LLM_PROVIDER=anthropic (default) uses ANTHROPIC_API_KEY and ANTHROPIC_MODEL
    # - LLM_PROVIDER=openai_compatible uses OPENAI_API_KEY and OPENAI_BASE_URL
    llm_provider: str = Field(default="anthropic")
    llm_vision_provider: str = Field(default="")  # Optional override for vision tasks
    llm_model: str = Field(default="")  # Optional override for provider default model
    llm_vision_model: str = Field(default="")  # Optional override for vision model
    llm_timeout_seconds: float = Field(default=120.0)
    llm_max_retries: int = Field(default=2)
    llm_max_concurrency: int = Field(default=4)
    llm_tool_result_max_chars: int = Field(default=12000)

    # Specialist routing (Phase 3)
    enable_specialist_routing: bool = Field(default=True)

    # Guardrails
    guardrail_max_message_chars: int = Field(default=8000)
    guardrail_rate_limit_messages: int = Field(default=30)
    guardrail_rate_limit_window_seconds: int = Field(default=60)
    guardrail_tool_recursion_max_depth: int = Field(default=3)
    guardrail_classifier_model: str = Field(default="claude-3-haiku-20240307")
    guardrail_free_monthly_token_budget: int = Field(default=500_000)
    guardrail_pro_monthly_token_budget: int = Field(default=-1)

    # Google Gemini (free-tier chat default)
    google_gemini_api_key: str = Field(default="")
    google_gemini_model: str = Field(default="gemini-2.0-flash")
    google_gemini_base_url: str = Field(
        default="https://generativelanguage.googleapis.com/v1beta/openai"
    )

    # OpenAI-compatible settings (optional)
    openai_api_key: str = Field(default="")
    openai_base_url: str = Field(default="https://api.openai.com/v1")

    # Census Bureau API
    census_api_key: str = Field(default="")

    # Google Places API
    google_places_api_key: str = Field(default="")

    # Placer.ai API
    placer_api_key: str = Field(default="")
    placer_api_url: str = Field(default="https://api.placer.ai/v1")

    # Email/SMTP Settings (for outreach campaigns)
    smtp_host: str = Field(default="")  # e.g., "smtp.gmail.com" or "smtp.sendgrid.net"
    smtp_port: int = Field(default=587)
    smtp_username: str = Field(default="")
    smtp_password: str = Field(default="")
    smtp_use_tls: bool = Field(default=True)
    smtp_from_email: str = Field(default="")  # Default sender email
    smtp_from_name: str = Field(default="Space Goose")

    # File Upload
    upload_dir: str = Field(default="./uploads")
    max_upload_size_mb: int = Field(default=50)

    # Browser Automation
    browser_headless: bool = Field(default=True)
    browser_sessions_dir: str = Field(default="./browser_sessions")
    browser_timeout_seconds: int = Field(default=60)
    browser_session_max_age_hours: int = Field(default=24)

    # Resend Email (transactional emails)
    resend_api_key: str = Field(default="")
    resend_from_email: str = Field(default="noreply@spacegoose.ai")
    resend_from_name: str = Field(default="Space Goose")

    # ATTOM Data API (title/owner lookup)
    attom_api_key: str = Field(default="")

    # Gmail Monitoring
    gmail_monitor_interval_minutes: int = Field(default=5)
    gmail_monitor_max_emails_per_check: int = Field(default=20)

    # Stripe Payments
    stripe_secret_key: str = Field(default="")
    stripe_publishable_key: str = Field(default="")
    stripe_webhook_secret: str = Field(default="")
    stripe_individual_price_id: str = Field(default="")
    stripe_enterprise_price_id: str = Field(default="")

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
