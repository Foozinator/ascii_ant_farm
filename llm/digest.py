"""``digest`` — state + new events in, a :class:`ColonyReport` out. STUBBED.

This is the narration AI interface. After the sim ticks, the router calls this
to turn the turn's events into prose the player reads, plus a structured payload
(per-resident mood deltas and flags) the UI can act on.

The real implementation will prompt a local Ollama model. The skeleton returns a
canned report assembled deterministically from the state snapshot and the new
events — enough to prove the report flows out to the UI. Signature is the
contract: ``digest(state, new_events) -> ColonyReport``.

Imports only :mod:`contract` and :mod:`llm.views`; never ``sim``.
"""

from __future__ import annotations

from contract import ColonyReport
from llm.views import StateView

_HUNGER_BELOW = 2.0
_BROWNOUT_BELOW = 10.0


def digest(state: StateView, new_events: list[str]) -> ColonyReport:
    """Summarize the latest tick into a :class:`ColonyReport` (stub).

    Always returns a valid report; the router re-validates it at the seam.
    """
    flags: list[str] = []
    if state.food < _HUNGER_BELOW:
        flags.append("hunger")
    if state.power < _BROWNOUT_BELOW:
        flags.append("brownout")

    # Canned heuristic deltas: the narration's read on how moods moved. With a
    # real model these would be reasoned per ant; here one fixed value per ant
    # keeps it deterministic.
    base = -0.05 if flags else 0.02
    mood_deltas = {r.id: round(base, 3) for r in state.residents}

    headline = "; ".join(new_events) if new_events else "A quiet shift passes."
    prose = f"[Colony digest - turn {state.turn}] {headline} The ants carry on."

    return ColonyReport(prose=prose, mood_deltas=mood_deltas, flags=flags)
