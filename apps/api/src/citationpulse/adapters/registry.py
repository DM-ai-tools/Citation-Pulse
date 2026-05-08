from __future__ import annotations

from citationpulse.adapters.anthropic_adapter import AnthropicClaudeAdapter
from citationpulse.adapters.base import BaseEngineAdapter
from citationpulse.adapters.gemini_adapter import GeminiAdapter
from citationpulse.adapters.openai_adapter import OpenAIChatGPTAdapter
from citationpulse.adapters.perplexity_adapter import PerplexityAdapter
from citationpulse.models.domain import GOOGLE_AIO_ENABLED, EngineType

# Deprecated browser adapter support remains behind the feature flag below for
# backward compatibility only.
if GOOGLE_AIO_ENABLED:
    from citationpulse.adapters.google_aio import GoogleAIOAdapter
else:  # pragma: no cover - feature flag
    GoogleAIOAdapter = None  # type: ignore[assignment, misc]


def build_adapter(engine: EngineType) -> BaseEngineAdapter:
    if engine == EngineType.CHATGPT:
        return OpenAIChatGPTAdapter()
    if engine == EngineType.CLAUDE:
        return AnthropicClaudeAdapter()
    if engine == EngineType.GEMINI:
        return GeminiAdapter()
    if engine == EngineType.PERPLEXITY:
        return PerplexityAdapter()
    if engine == EngineType.GOOGLE_AIO:
        if not GOOGLE_AIO_ENABLED or GoogleAIOAdapter is None:
            raise ValueError(
                "GOOGLE_AIO is disabled: set GOOGLE_AIO_ENABLED=True in "
                "models/domain.py and configure PLAYWRIGHT_PROXY_SERVER first."
            )
        return GoogleAIOAdapter()
    raise ValueError(engine)
