"""``digest`` — state + new events in, a :class:`ColonyReport` out.

The narration AI interface. After the sim ticks, the router calls this to turn
the turn's events into in-character prose (plus soft flags). This module is a thin
facade: it delegates to the active backend (stub or Ollama) selected by
``LLM_BACKEND``. The signature is the stable contract:
``digest(state, new_events) -> ColonyReport``.

Imports only :mod:`contract`, :mod:`llm.runtime`, and :mod:`llm.views`; never ``sim``.
"""

from __future__ import annotations

from contract import ColonyReport
from llm.runtime import get_backend
from llm.views import StateView


def digest(state: StateView, new_events: list[str]) -> ColonyReport:
    """Summarize the latest tick into a :class:`ColonyReport`.

    Routed to the active backend. Always returns a valid report (backends degrade
    malformed/empty/erroring model output to a safe value rather than raising).
    """
    return get_backend().digest(state, new_events)
