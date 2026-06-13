"""Pure rendering helpers — :class:`~sim.GameState` to display strings.

Kept separate from the Textual app so the rendering logic has no UI-framework
dependency and can be unit-tested directly. These functions only *read* state.
"""

from __future__ import annotations

from sim import CELL_GLYPHS, GameState

_MOOD_BAR_WIDTH = 10


def render_grid(state: GameState) -> str:
    """Render the colony grid as a block of ASCII glyphs, one row per line."""
    return "\n".join(
        "".join(CELL_GLYPHS[cell] for cell in row) for row in state.grid
    )


def _mood_bar(mood: float) -> str:
    filled = round(max(0.0, min(1.0, mood)) * _MOOD_BAR_WIDTH)
    return "#" * filled + "-" * (_MOOD_BAR_WIDTH - filled)


def render_status(state: GameState) -> str:
    """Render stocks, the selected metric, and the resident roster."""
    lines = [
        f"turn   : {state.turn}",
        f"food   : {state.food:5.1f} / 9",
        f"power  : {state.power:5.1f} / 100",
        f"metric : {state.metric}",
        "",
        "residents:",
    ]
    for r in state.residents:
        lines.append(
            f"  {r.id}  [{_mood_bar(r.mood)}] {r.mood:4.2f}  {r.archetype}"
        )
    lines += [
        "",
        "legend: # dirt  . tunnel  O offices  N nursery  P pantry",
    ]
    return "\n".join(lines)
