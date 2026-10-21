"""LLM Adapter package for MediFlow."""

from agent.llm.adapter import (
    FALLBACKS,
    PRIMARY,
    LLMResult,
    complete,
    modelos_disponibles,
)
from agent.llm.phoenix import (
    get_phoenix_url,
    init_phoenix,
    is_phoenix_running,
    phoenix_session,
    shutdown_phoenix,
)

__all__ = [
    "complete",
    "LLMResult",
    "PRIMARY",
    "FALLBACKS",
    "modelos_disponibles",
    "init_phoenix",
    "shutdown_phoenix",
    "phoenix_session",
    "is_phoenix_running",
    "get_phoenix_url",
]