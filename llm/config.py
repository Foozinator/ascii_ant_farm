"""Runtime configuration for the llm backends — entirely env-driven.

Nothing about the model is hardcoded at a call site: everything routes through
:func:`load_config`, which reads the environment with sane fallbacks. Ollama may
run on another machine, so ``OLLAMA_BASE_URL`` is always overridable.

Environment variables:
  - ``LLM_BACKEND``            "ollama" | "stub"   (default "stub")
  - ``OLLAMA_BASE_URL``        Ollama host URL     (default http://localhost:11434)
  - ``OLLAMA_MODEL``           model tag           (default the installed Gemma E4B)
  - ``LLM_PARSE_TEMPERATURE``  parse sampling temp (default 0.3 — interpretation)
  - ``LLM_DIGEST_TEMPERATURE`` digest sampling temp(default 0.8 — voice)
  - ``LLM_DIGEST_VOICES``      residents to voice  (default 3)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

DEFAULT_BACKEND = "stub"
DEFAULT_BASE_URL = "http://localhost:11434"
# The Gemma E4B-class model installed on this machine (`ollama list`). Override
# with OLLAMA_MODEL for any other deployment.
DEFAULT_MODEL = "gemma4:e4b"
DEFAULT_PARSE_TEMPERATURE = 0.3
DEFAULT_DIGEST_TEMPERATURE = 0.8
DEFAULT_DIGEST_VOICES = 3

_VALID_BACKENDS = ("stub", "ollama")


@dataclass(frozen=True)
class LLMConfig:
    """An immutable snapshot of the llm configuration.

    Frozen so it doubles as a cache key — the runtime rebuilds the active backend
    whenever ``load_config()`` returns a value that differs from the cached one.
    """

    backend: str = DEFAULT_BACKEND
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    parse_temperature: float = DEFAULT_PARSE_TEMPERATURE
    digest_temperature: float = DEFAULT_DIGEST_TEMPERATURE
    digest_voices: int = DEFAULT_DIGEST_VOICES


def _get_str(env: Mapping[str, str], key: str, default: str) -> str:
    value = env.get(key)
    if value is None:
        return default
    value = value.strip()
    return value or default


def _get_float(env: Mapping[str, str], key: str, default: float) -> float:
    raw = env.get(key)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _get_int(env: Mapping[str, str], key: str, default: int) -> int:
    raw = env.get(key)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def load_config(env: Mapping[str, str] | None = None) -> LLMConfig:
    """Build an :class:`LLMConfig` from the environment (defaults if unset)."""
    env = os.environ if env is None else env

    backend = _get_str(env, "LLM_BACKEND", DEFAULT_BACKEND).lower()
    if backend not in _VALID_BACKENDS:
        backend = DEFAULT_BACKEND

    return LLMConfig(
        backend=backend,
        base_url=_get_str(env, "OLLAMA_BASE_URL", DEFAULT_BASE_URL),
        model=_get_str(env, "OLLAMA_MODEL", DEFAULT_MODEL),
        parse_temperature=_get_float(env, "LLM_PARSE_TEMPERATURE", DEFAULT_PARSE_TEMPERATURE),
        digest_temperature=_get_float(env, "LLM_DIGEST_TEMPERATURE", DEFAULT_DIGEST_TEMPERATURE),
        digest_voices=_get_int(env, "LLM_DIGEST_VOICES", DEFAULT_DIGEST_VOICES),
    )
