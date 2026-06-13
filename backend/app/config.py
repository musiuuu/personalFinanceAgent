"""Environment-driven configuration. No secrets in code."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///finance.db"

    anthropic_api_key: str = ""
    llm_cheap_model: str = "claude-haiku-4-5-20251001"
    llm_smart_model: str = "claude-sonnet-4-6"

    # LangSmith tracing (optional, env-gated)
    langchain_tracing_v2: bool = False
    langchain_api_key: str = ""
    langchain_project: str = "finance-agent"

    # Engine defaults
    safety_buffer_minor: int = 50_000_00  # 50,000 PKR in paisa
    forecast_lookback_months: int = 3
    anomaly_mad_k: float = 3.5

    # Ingestion
    pdf_text_min_chars_per_page: int = 200

    # Deployment / demo
    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    seed_on_startup: bool = False
    seed_data_dir: str = "../sample_data"
    frontend_dist: str = ""

    @property
    def llm_enabled(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
