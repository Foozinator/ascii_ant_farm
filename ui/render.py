"""Pure rendering helpers — :class:`~sim.GameState` to display strings.

Kept separate from the Textual app so the rendering logic has no UI-framework
dependency and can be unit-tested directly. These functions only *read* state.
"""

from __future__ import annotations

from sim import CELL_GLYPHS, GameState

_MOOD_BAR_WIDTH = 10


def render_grid(state: GameState) -> str:
    """Render the colony grid as ASCII glyphs with residents overlaid."""
    # Build a position → glyph map for placed residents.
    # First resident at each cell wins; glyph is the uppercase initial of the archetype.
    resident_at: dict[tuple[int, int], str] = {}
    for r in state.residents:
        if r.row is not None and r.col is not None:
            key = (r.row, r.col)
            if key not in resident_at:
                glyph = r.archetype[0].upper() if r.archetype else "@"
                resident_at[key] = glyph

    lines: list[str] = []
    for ri, row in enumerate(state.grid):
        chars: list[str] = []
        for ci, cell in enumerate(row):
            g = resident_at.get((ri, ci))
            chars.append(g if g is not None else CELL_GLYPHS[cell])
        lines.append("".join(chars))
    return "\n".join(lines)


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
        "legend: # dirt  . tunnel  O offices  N nursery  P pantry  letter=resident",
    ]
    return "\n".join(lines)
