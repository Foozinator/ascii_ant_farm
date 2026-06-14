"""Pure rendering helpers — :class:`~sim.GameState` to coloured renderables.

Kept separate from the Textual app so the rendering logic has no UI-framework
dependency and can be unit-tested directly. These functions only *read* state.

They return Rich :class:`~rich.text.Text`, which:

* renders with colour in the Textual TUI and in watch mode (via a Rich Console),
* downsamples automatically to the terminal's real colour capability, and
* degrades to plain text under ``str()`` — so ``print()`` and tests still get a
  clean ASCII grid with no escape codes.

Colour choices (the visual hierarchy) live in :mod:`ui.palette`.
"""

from __future__ import annotations

from rich.text import Text

from sim import CELL_GLYPHS, CellType, GameState
from ui.palette import cell_style, metric_value, resident_style

_MOOD_BAR_WIDTH = 10


def render_grid(state: GameState) -> Text:
    """Render the colony grid with residents overlaid, each glyph styled.

    Sand recedes, tunnels read quietly, rooms carry muted categorical hues, and
    residents are the loud figure on top — coloured by the active metric.
    """
    # Position → (glyph, style) for placed residents. First resident at a cell
    # wins; glyph is the uppercase initial of the archetype, coloured by metric.
    resident_at: dict[tuple[int, int], tuple[str, object]] = {}
    for r in state.residents:
        if r.row is not None and r.col is not None:
            key = (r.row, r.col)
            if key not in resident_at:
                glyph = r.archetype[0].upper() if r.archetype else "@"
                resident_at[key] = (glyph, resident_style(metric_value(state, r)))

    text = Text(no_wrap=True)
    for ri, row in enumerate(state.grid):
        if ri:
            text.append("\n")
        for ci, cell in enumerate(row):
            hit = resident_at.get((ri, ci))
            if hit is not None:
                glyph, style = hit
                text.append(glyph, style)
            else:
                text.append(CELL_GLYPHS[cell], cell_style(cell))
    return text


def _mood_bar(mood: float) -> str:
    filled = round(max(0.0, min(1.0, mood)) * _MOOD_BAR_WIDTH)
    return "#" * filled + "-" * (_MOOD_BAR_WIDTH - filled)


def render_status(state: GameState) -> Text:
    """Render stocks, the selected metric, and the resident roster.

    Each resident's id is tinted with the same metric colour it carries in the
    grid, so the roster reads as a key to the tank. The legend shows a live
    swatch of every cell hue.
    """
    t = Text(no_wrap=True)
    t.append(f"turn   : {state.turn}\n")
    t.append(f"food   : {state.food:5.1f} / 9\n")
    t.append(f"power  : {state.power:5.1f} / 100\n")
    t.append(f"metric : {state.metric}\n")
    t.append("\n")
    t.append("residents:\n")
    for r in state.residents:
        t.append("  ")
        t.append(r.id, resident_style(metric_value(state, r)))
        t.append(f"  [{_mood_bar(r.mood)}] {r.mood:4.2f}  {r.archetype}\n")

    t.append("\n")
    t.append("legend: ")
    for glyph, cell, label in (
        ("#", CellType.DIRT, " dirt  "),
        (".", CellType.TUNNEL, " tunnel  "),
        ("O", CellType.OFFICES, " offices  "),
        ("N", CellType.NURSERY, " nursery  "),
        ("P", CellType.PANTRY, " pantry  "),
    ):
        t.append(glyph, cell_style(cell))
        t.append(label)
    # A bright swatch for the resident layer, keyed high on the gradient.
    t.append("@", resident_style(0.9))
    t.append("=resident")
    return t
