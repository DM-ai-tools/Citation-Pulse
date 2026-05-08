from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol

from citationpulse.models.domain import EngineType


@dataclass
class RawCitation:
    url: str
    snippet: str | None = None
    position: int | None = None


@dataclass
class EngineResponse:
    answer_text: str
    citations: list[RawCitation]
    raw_payload_ref: str
    latency_ms: int
    cost_usd: Decimal | None = None


class EngineAdapter(Protocol):
    name: EngineType

    async def run(self, prompt: str, locale: str, run_ctx: dict[str, Any]) -> EngineResponse:
        ...


class BaseEngineAdapter(ABC):
    name: EngineType
    max_retries: int = 3

    def __init__(self, name: EngineType):
        self.name = name

    @abstractmethod
    async def run(self, prompt: str, locale: str, run_ctx: dict[str, Any]) -> EngineResponse:
        raise NotImplementedError
