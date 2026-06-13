"""The language-model side of the game — now with a real backend.

Two interfaces, unchanged in signature:

* :func:`parse` — free sentence -> :class:`contract.EffectEnvelope`
* :func:`digest` — state + new events -> :class:`contract.ColonyReport`

Both route through a selectable backend (``LLM_BACKEND``):

* ``stub``   — deterministic, offline, no model (default; what CI and the sim
  agent use).
* ``ollama`` — the real version: schema-constrained generation via the official
  Ollama client at a configurable host.

This package depends only on :mod:`contract` and its own modules; it never
imports ``sim``. State is read through the structural :class:`StateView`.
"""

from llm.backends import Backend, OllamaBackend, StubBackend
from llm.config import LLMConfig, load_config
from llm.digest import digest
from llm.parser import parse
from llm.personas import PersonaCard, PersonaCatalog, get_catalog, load_catalog
from llm.runtime import (
    build_backend,
    check_backend,
    describe_backend,
    get_backend,
    reset_backend,
    set_backend,
)
from llm.views import ResidentView, StateView

__all__ = [
    # interfaces
    "parse",
    "digest",
    # config
    "LLMConfig",
    "load_config",
    # backends & selection
    "Backend",
    "StubBackend",
    "OllamaBackend",
    "build_backend",
    "get_backend",
    "set_backend",
    "reset_backend",
    "describe_backend",
    "check_backend",
    # personas
    "PersonaCard",
    "PersonaCatalog",
    "get_catalog",
    "load_catalog",
    # state views
    "StateView",
    "ResidentView",
]
