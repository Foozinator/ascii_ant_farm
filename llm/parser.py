"""``parse`` — natural language in, an :class:`EffectEnvelope` out.

The gesture-path AI interface. The router hands a free sentence here when the
deterministic command grammar doesn't recognize it. This module is a thin facade:
it delegates to the active backend (stub or Ollama) selected by ``LLM_BACKEND``.
The signature is the stable contract the backends implement:
``parse(sentence, state) -> EffectEnvelope``.

Imports only :mod:`contract`, :mod:`llm.runtime`, and :mod:`llm.views`; never ``sim``.
"""

from __future__ import annotations

from contract import EffectEnvelope
from llm.runtime import get_backend
from llm.views import StateView


def parse(sentence: str, state: StateView) -> EffectEnvelope:
    """Translate a free sentence into an :class:`EffectEnvelope`.

    Routed to the active backend. Always returns a valid envelope (backends
    degrade malformed/empty/erroring model output to a safe value rather than
    raising); the router still re-validates at the seam.
    """
    return get_backend().parse(sentence, state)
