from functools import lru_cache
from pathlib import Path

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
    database_url: str = f"sqlite+aiosqlite:///{(DATA_DIR / 'aifunnel.db').as_posix()}"
    api_host: str = "0.0.0.0"
    api_port: int = 8080
    api_public_url: str = "http://127.0.0.1:8080"
    crm_api_token: str = "dev-crm-token-change-me"

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

    funnel_default_source: str = "direct"


@lru_cache
def get_settings() -> Settings:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return Settings()
