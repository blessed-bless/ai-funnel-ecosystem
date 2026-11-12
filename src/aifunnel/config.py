from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "AI Funnel Ecosystem"
    app_env: str = "development"
    log_level: str = "INFO"
    database_url: str = f"sqlite+aiosqlite:///{(DATA_DIR / 'aifunnel.db').as_posix()}"
    api_host: str = "0.0.0.0"
    api_port: int = 8080
    api_public_url: str = "http://127.0.0.1:8080"
    crm_api_token: str = Field(default="dev-crm-token-change-me", min_length=8)
    cors_origins: str = "http://127.0.0.1:8080,http://localhost:8080"

    jwt_secret: str = Field(default="dev-jwt-secret-change-me-please-32b", min_length=32)
    jwt_expire_minutes: int = 720
    admin_username: str = "admin"
    admin_password: str = "admin-change-me"

    rate_limit_per_minute: int = 60
    chat_rate_limit_per_minute: int = 20

    telegram_bot_token: str = ""
    telegram_bot_username: str = ""
    telegram_manager_url: str = "https://t.me/"

    ai_provider: str = "mock"
    ai_api_key: str = ""
    ai_base_url: str = "https://api.openai.com/v1"
    ai_model: str = "gpt-4o-mini"
    ai_system_prompt: str = (
        "Ты консультант агентства автоматизации. Помогаешь квалифицировать лид: "
        "задача, бюджетный ориентир, контакт. Отвечай кратко по-русски. "
        "Не выдумывай цены и договоры."
    )
    ai_max_retries: int = 3
    ai_circuit_failures: int = 5
    ai_circuit_recovery_seconds: float = 45.0
    ai_fallback_reply: str = (
        "Сейчас модель недоступна. Оставь телефон и кратко задачу — "
        "менеджер свяжется вручную."
    )

    funnel_default_source: str = "direct"
    ready_require_db: bool = True

    @field_validator("app_env")
    @classmethod
    def _normalize_env(cls, value: str) -> str:
        return value.strip().lower() or "development"

    @property
    def cors_origin_list(self) -> list[str]:
        return [part.strip() for part in self.cors_origins.split(",") if part.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env in {"prod", "production"}


@lru_cache
def get_settings() -> Settings:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    settings = Settings()
    if settings.is_production and settings.crm_api_token.startswith("dev-"):
        raise RuntimeError("В production нельзя оставлять дефолтный CRM_API_TOKEN")
    if settings.is_production and settings.jwt_secret.startswith("dev-"):
        raise RuntimeError("В production нельзя оставлять дефолтный JWT_SECRET")
    if settings.is_production and settings.admin_password in {"admin-change-me", "admin", "password"}:
        raise RuntimeError("В production задай нормальный ADMIN_PASSWORD")
    return settings
