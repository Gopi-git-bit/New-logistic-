"""Agent config from environment (M3)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    max_tool_calls_per_tick: int = 20
    claim_batch_size: int = 5
    tick_interval_seconds: float = 15.0

    # Deterministic governance conversion (PRD D-13); human-reviewed quarterly.
    governance_usd_inr_rate: float = 82.50

    # Optional Langfuse (trace ingest only when keys present)
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str = "https://us.cloud.langfuse.com"

    # Supabase access for the kernel (service role required for RPCs)
    supabase_url: str | None = None
    supabase_service_role_key: str | None = None

    # Odoo 18 CE system of record
    odoo_url: str | None = None
    odoo_db: str = "odoo18"
    odoo_user: str = "admin"
    odoo_api_key: str | None = None


def get_settings() -> "WorkerSettings":
    return WorkerSettings()  # cached by caller if hot-path profiling matters later
