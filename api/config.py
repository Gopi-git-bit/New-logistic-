"""Zippy Logistics — Central Configuration Validation.

Fails fast at startup when REQUIRED server-side production variables are missing.
Optional integrations disable their feature instead of crashing.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class Settings:
    """Validated application settings. Reads from environment."""

    # === CRITICAL (missing = startup failure) ===
    database_url: str = ""
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_jwt_secret: str = ""
    postgres_password: str = ""

    # === Razorpay (critical for payments) ===
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""

    # === Odoo (critical for ERP) ===
    odoo_url: str = ""
    odoo_db: str = "odoo18"
    odoo_user: str = "zippy-integration"
    odoo_api_key: str = ""

    # === Paperclip (critical for governance) ===
    paperclip_url: str = ""
    paperclip_api_key: str = ""

    # === Hermes (critical for execution) ===
    hermes_api_url: str = ""
    hermes_api_key: str = ""

    # === Application ===
    app_env: str = "development"
    app_base_url: str = "http://localhost:3000"
    api_base_url: str = "http://localhost:8000"
    log_level: str = "info"

    # === Public-safe (browser allowed) ===
    next_public_supabase_url: str = ""
    next_public_supabase_anon_key: str = ""

    # === Optional integrations (missing = feature disabled) ===
    langfuse_host: str = "https://us.cloud.langfuse.com"
    langfuse_public_key: Optional[str] = None
    langfuse_secret_key: Optional[str] = None

    honcho_api_url: Optional[str] = None
    honcho_api_key: Optional[str] = None

    openrouter_api_key: Optional[str] = None
    deepseek_api_key: Optional[str] = None
    model_planning: str = "deepseek-v4-pro"
    model_fast: str = "deepseek-v4-flash"

    composio_api_key: Optional[str] = None
    composio_mcp_url: Optional[str] = None
    tinyfish_api_key: Optional[str] = None
    tinyfish_api_url: Optional[str] = None
    tinyfish_tool_name: str = "tinyfish.start_task"

    mapbox_access_token: Optional[str] = None

    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from: Optional[str] = None

    sms_api_url: Optional[str] = None
    sms_api_key: Optional[str] = None

    whatsapp_api_url: Optional[str] = None
    whatsapp_api_token: Optional[str] = None

    ocr_provider: str = "tesseract"
    ocr_api_key: Optional[str] = None

    redis_url: str = "redis://localhost:6379/0"

    max_tool_calls_per_tick: int = 20
    governance_usd_inr_rate: float = 82.50
    governance_approval_timeout_hours: int = 72
    agent_daily_budget_usd: float = 50.00

    # === Derived ===
    is_production: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "is_production", self.app_env == "production")


def _require(key: str, default: str = "") -> str:
    """Get required env var. Returns empty string if missing."""
    return os.environ.get(key, default)


def _optional(key: str) -> Optional[str]:
    """Get optional env var. Returns None if missing."""
    return os.environ.get(key) or None


def load_settings() -> Settings:
    """Load and validate settings from environment."""
    return Settings(
        # Critical
        database_url=_require("DATABASE_URL"),
        supabase_url=_require("SUPABASE_URL"),
        supabase_service_role_key=_require("SUPABASE_SERVICE_ROLE_KEY"),
        supabase_jwt_secret=_require("SUPABASE_JWT_SECRET"),
        postgres_password=_require("POSTGRES_PASSWORD"),
        # Razorpay
        razorpay_key_id=_require("RAZORPAY_KEY_ID"),
        razorpay_key_secret=_require("RAZORPAY_KEY_SECRET"),
        razorpay_webhook_secret=_require("RAZORPAY_WEBHOOK_SECRET"),
        # Odoo
        odoo_url=_require("ODOO_URL"),
        odoo_db=_require("ODOO_DB", "odoo18"),
        odoo_user=_require("ODOO_USER", "zippy-integration"),
        odoo_api_key=_require("ODOO_API_KEY"),
        # Paperclip
        paperclip_url=_require("PAPERCLIP_URL"),
        paperclip_api_key=_require("PAPERCLIP_API_KEY"),
        # Hermes
        hermes_api_url=_require("HERMES_API_URL"),
        hermes_api_key=_require("HERMES_API_KEY"),
        # Application
        app_env=_require("APP_ENV", "development"),
        app_base_url=_require("APP_BASE_URL", "http://localhost:3000"),
        api_base_url=_require("API_BASE_URL", "http://localhost:8000"),
        log_level=_require("LOG_LEVEL", "info"),
        # Public-safe
        next_public_supabase_url=_require("NEXT_PUBLIC_SUPABASE_URL"),
        next_public_supabase_anon_key=_require("NEXT_PUBLIC_SUPABASE_ANON_KEY"),
        # Optional
        langfuse_host=_require("LANGFUSE_HOST", "https://us.cloud.langfuse.com"),
        langfuse_public_key=_optional("LANGFUSE_PUBLIC_KEY"),
        langfuse_secret_key=_optional("LANGFUSE_SECRET_KEY"),
        honcho_api_url=_optional("HONCHO_API_URL"),
        honcho_api_key=_optional("HONCHO_API_KEY"),
        openrouter_api_key=_optional("OPENROUTER_API_KEY"),
        deepseek_api_key=_optional("DEEPSEEK_API_KEY"),
        model_planning=_require("MODEL_PLANNING", "deepseek-v4-pro"),
        model_fast=_require("MODEL_FAST", "deepseek-v4-flash"),
        composio_api_key=_optional("COMPOSIO_API_KEY"),
        composio_mcp_url=_optional("COMPOSIO_MCP_URL"),
        tinyfish_api_key=_optional("TINYFISH_API_KEY"),
        tinyfish_api_url=_optional("TINYFISH_API_URL"),
        tinyfish_tool_name=_require("TINYFISH_TOOL_NAME", "tinyfish.start_task"),
        mapbox_access_token=_optional("MAPBOX_ACCESS_TOKEN"),
        smtp_host=_optional("SMTP_HOST"),
        smtp_port=int(_require("SMTP_PORT", "587")),
        smtp_user=_optional("SMTP_USER"),
        smtp_password=_optional("SMTP_PASSWORD"),
        smtp_from=_optional("SMTP_FROM"),
        sms_api_url=_optional("SMS_API_URL"),
        sms_api_key=_optional("SMS_API_KEY"),
        whatsapp_api_url=_optional("WHATSAPP_API_URL"),
        whatsapp_api_token=_optional("WHATSAPP_API_TOKEN"),
        ocr_provider=_require("OCR_PROVIDER", "tesseract"),
        ocr_api_key=_optional("OCR_API_KEY"),
        redis_url=_require("REDIS_URL", "redis://localhost:6379/0"),
        max_tool_calls_per_tick=int(_require("MAX_TOOL_CALLS_PER_TICK", "20")),
        governance_usd_inr_rate=float(_require("GOVERNANCE_USD_INR_RATE", "82.50")),
        governance_approval_timeout_hours=int(_require("GOVERNANCE_APPROVAL_TIMEOUT_HOURS", "72")),
        agent_daily_budget_usd=float(_require("AGENT_DAILY_BUDGET_USD", "50.00")),
    )


def validate_required(settings: Settings) -> list[str]:
    """Return list of missing required fields. Empty = all good."""
    missing = []
    if not settings.database_url:
        missing.append("DATABASE_URL")
    if not settings.supabase_url:
        missing.append("SUPABASE_URL")
    if not settings.supabase_service_role_key:
        missing.append("SUPABASE_SERVICE_ROLE_KEY")
    if not settings.supabase_jwt_secret:
        missing.append("SUPABASE_JWT_SECRET")
    if not settings.postgres_password:
        missing.append("POSTGRES_PASSWORD")
    if not settings.razorpay_key_id:
        missing.append("RAZORPAY_KEY_ID")
    if not settings.razorpay_key_secret:
        missing.append("RAZORPAY_KEY_SECRET")
    if not settings.razorpay_webhook_secret:
        missing.append("RAZORPAY_WEBHOOK_SECRET")
    if not settings.odoo_url:
        missing.append("ODOO_URL")
    if not settings.odoo_api_key:
        missing.append("ODOO_API_KEY")
    if not settings.paperclip_url:
        missing.append("PAPERCLIP_URL")
    if not settings.paperclip_api_key:
        missing.append("PAPERCLIP_API_KEY")
    if not settings.hermes_api_url:
        missing.append("HERMES_API_URL")
    if not settings.hermes_api_key:
        missing.append("HERMES_API_KEY")
    return missing


def validate_production_security(settings: Settings) -> list[str]:
    """Check for dangerous defaults in production."""
    warnings = []
    if settings.is_production:
        if settings.postgres_password in ("postgres", "changeme", "password", "admin", "secret", "test"):
            warnings.append("POSTGRES_PASSWORD is weak/default — MUST change for production")
        if "localhost" in settings.odoo_url:
            warnings.append("ODOO_URL points to localhost — likely wrong for production")
        if settings.odoo_user == "admin":
            warnings.append("ODOO_USER is 'admin' — use dedicated integration account")
        if settings.composio_api_key and not settings.composio_mcp_url:
            warnings.append("COMPOSIO_API_KEY is set but COMPOSIO_MCP_URL is missing")
        if settings.tinyfish_api_key and not (
            settings.tinyfish_api_url or settings.composio_mcp_url
        ):
            warnings.append(
                "TINYFISH_API_KEY is set but neither TINYFISH_API_URL nor "
                "COMPOSIO_MCP_URL is configured"
            )
    return warnings


if __name__ == "__main__":
    settings = load_settings()
    missing = validate_required(settings)
    warnings = validate_production_security(settings)

    if missing:
        print(f"FATAL: Missing required environment variables: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    if warnings:
        for w in warnings:
            print(f"WARNING: {w}", file=sys.stderr)

    print("Configuration validated successfully.")
