"""Engine parallel wave grouping."""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.normpath(os.path.join(_HERE, "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from citationpulse.models.domain import EngineType  # noqa: E402
from citationpulse.tasks.geo import WAVE_1_ENGINES, WAVE_2_ENGINES, wave_for_engine  # noqa: E402


def test_wave_grouping():
    assert EngineType.CHATGPT.value in WAVE_1_ENGINES
    assert EngineType.PERPLEXITY.value in WAVE_1_ENGINES
    assert EngineType.CLAUDE.value in WAVE_2_ENGINES
    assert EngineType.GEMINI.value in WAVE_2_ENGINES
    assert wave_for_engine("chatgpt") == 1
    assert wave_for_engine("perplexity") == 1
    assert wave_for_engine("claude") == 2
    assert wave_for_engine("gemini") == 2
