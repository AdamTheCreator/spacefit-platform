from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    app_name: str = "SpaceFit AI"
    debug: bool = Field(default=False)
    api_prefix: str = "/api/v1"

    # CORS
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:5174", "http://localhost:3000"]

    # WebSocket
    ws_heartbeat_interval: int = 30

    # Database (SQLite for dev, PostgreSQL for production)
    database_url: str = Field(
        default="sqlite+aiosqlite:///./spacefit.db"
    )

    # JWT Authentication
    secret_key: str = Field(default="development-secret-key-change-in-production")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # Encryption (for storing credentials)
    encryption_master_key: str = Field(
        default="development-encryption-key-32bytes!"
    )

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
    llm_timeout_seconds: float = Field(default=60.0)
    llm_max_retries: int = Field(default=2)
    llm_max_concurrency: int = Field(default=4)
    llm_tool_result_max_chars: int = Field(default=12000)

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
    smtp_from_name: str = Field(default="SpaceFit")

    # File Upload
    upload_dir: str = Field(default="./uploads")
    max_upload_size_mb: int = Field(default=50)

    # Browser Automation
    browser_headless: bool = Field(default=True)
    browser_sessions_dir: str = Field(default="./browser_sessions")
    browser_timeout_seconds: int = Field(default=60)
    browser_session_max_age_hours: int = Field(default=24)

    # Stripe Payments
    stripe_secret_key: str = Field(default="")
    stripe_publishable_key: str = Field(default="")
    stripe_webhook_secret: str = Field(default="")
    stripe_pro_price_id: str = Field(default="")
    stripe_enterprise_price_id: str = Field(default="")

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
