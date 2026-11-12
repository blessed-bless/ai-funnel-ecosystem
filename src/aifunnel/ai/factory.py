from aifunnel.ai.base import AIProvider
from aifunnel.ai.mock import MockAIProvider
from aifunnel.ai.openai_compat import OpenAICompatProvider
from aifunnel.ai.resilient import ResilientAIProvider
from aifunnel.config import Settings, get_settings

_shared_resilient: ResilientAIProvider | None = None


def build_ai(settings: Settings | None = None) -> AIProvider:
    global _shared_resilient
    cfg = settings or get_settings()
    if cfg.ai_provider == "openai_compat" and cfg.ai_api_key:
        inner: AIProvider = OpenAICompatProvider(cfg)
    else:
        inner = MockAIProvider()
    if _shared_resilient is None or _shared_resilient._inner.__class__ is not inner.__class__:
        _shared_resilient = ResilientAIProvider(inner, cfg)
    return _shared_resilient


def reset_ai_singleton() -> None:
    global _shared_resilient
    _shared_resilient = None
