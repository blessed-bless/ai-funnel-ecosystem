from aifunnel.ai.base import AIProvider
from aifunnel.ai.mock import MockAIProvider
from aifunnel.ai.openai_compat import OpenAICompatProvider
from aifunnel.config import Settings, get_settings


def build_ai(settings: Settings | None = None) -> AIProvider:
    cfg = settings or get_settings()
    if cfg.ai_provider == "openai_compat" and cfg.ai_api_key:
        return OpenAICompatProvider(cfg)
    return MockAIProvider()
