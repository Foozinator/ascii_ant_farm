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

from rich.style import Style
from rich.text import Text

from sim import CELL_GLYPHS, CellType, GameState
from ui.catalog import card_for
from ui.inspect import Selection, occupants, resident_by_id, room_by_id
from ui.palette import cell_style, metric_value, resident_style

_MOOD_BAR_WIDTH = 10

# Selection/cursor overlays applied on top of a glyph's base style.
_HIGHLIGHT = Style(reverse=True)            # a selected cell (room or resident)
_CURSOR = Style(reverse=True, bold=True)    # where the grid cursor sits


def render_grid(
    state: GameState,
    *,
    cursor: tuple[int, int] | None = None,
    highlight: set[tuple[int, int]] | None = None,
) -> Text:
    """Render the colony grid with residents overlaid, each glyph styled.

    Sand recedes, tunnels read quietly, rooms carry muted categorical hues, and
    residents are the loud figure on top — coloured by the active metric.

    ``highlight`` cells are drawn reversed (the current selection); ``cursor``
    is drawn reversed + bold so the inspection cursor is visible even over sand.
    Both default off, so non-interactive callers (watch mode, the demo) get the
    plain coloured grid unchanged.
    """
    highlight = highlight or set()

    # Position → (glyph, style) for placed residents. First resident at a cell
    # wins; glyph is the uppercase initial of the archetype, coloured by metric.
    resident_at: dict[tuple[int, int], tuple[str, Style]] = {}
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
            else:
                glyph, style = CELL_GLYPHS[cell], cell_style(cell)
            if (ri, ci) in highlight:
                style = style + _HIGHLIGHT
            if cursor is not None and cursor == (ri, ci):
                style = style + _CURSOR
            text.append(glyph, style)
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
    _append_legend(t)
    return t


def _append_legend(t: Text) -> None:
    """Append a one-line key of cell hues plus the resident swatch."""
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


def render_stats(state: GameState) -> Text:
    """Stocks, turn, and the active metric — the roster lives in the list now.

    This is the interactive app's compact stats box; :func:`render_status` keeps
    the full roster for watch mode and the demo.
    """
    t = Text(no_wrap=True)
    t.append(f"turn   : {state.turn}\n")
    t.append(f"food   : {state.food:5.1f} / 9\n")
    t.append(f"power  : {state.power:5.1f} / 100\n")
    t.append(f"metric : {state.metric}  ", Style(bold=True))
    t.append("(press m to cycle)\n", Style(dim=True))
    t.append("\n")
    _append_legend(t)
    return t


def render_detail(state: GameState, selection: Selection | None) -> Text:
    """Detail-on-demand for the current selection — names live HERE, not the grid.

    Room → function, placeholder name, and occupants.
    Resident → catalog card (display name + archetype), the active-metric value,
    and position. Falls back gracefully when a resident has no catalog card.
    """
    t = Text(no_wrap=True)
    if selection is None:
        t.append("Nothing selected.\n\n", Style(bold=True))
        t.append("Arrow-keys move the cursor over the tank;\n", Style(dim=True))
        t.append("click a cell or roster row to inspect it.\n", Style(dim=True))
        t.append("Tab to the input line to type a command.", Style(dim=True))
        return t

    if selection.kind == "resident":
        return _render_resident_detail(state, selection.id, t)
    return _render_room_detail(state, selection.id, t)


def _render_resident_detail(state: GameState, rid: str, t: Text) -> Text:
    r = resident_by_id(state, rid)
    if r is None:
        t.append("(resident no longer present)", Style(dim=True))
        return t

    card = card_for(r.archetype)
    name = card["name"] if card else r.id
    archetype = card["archetype"] if card else r.archetype

    t.append(f"{name}\n", resident_style(metric_value(state, r)))
    t.append(f"{archetype}\n", Style(italic=True))
    if card and card.get("satire"):
        t.append(f"{card['satire']}\n", Style(dim=True))
    t.append("\n")
    t.append(f"{state.metric:<6}: ", Style(bold=True))
    t.append(f"{metric_value(state, r):.2f}\n")
    t.append(f"mood  : {r.mood:.2f}\n")
    pos = f"({r.row}, {r.col})" if r.row is not None else "unplaced"
    t.append(f"at    : {pos}\n")
    t.append(f"room  : {r.room_id or '—'}\n")
    if not card:
        t.append("\n(no catalog card for this tag)", Style(dim=True))
    return t


def _render_room_detail(state: GameState, room_id: str, t: Text) -> Text:
    room = room_by_id(state, room_id)
    if room is None:
        t.append("(room no longer present)", Style(dim=True))
        return t

    t.append(f"{room.id}\n", Style(bold=True))
    t.append("function: ", Style(bold=True))
    t.append(f"{room.room_type.value}\n", cell_style(room.room_type))
    # The costume-naming layer isn't built yet — show a placeholder, not a name.
    t.append("name    : ", Style(bold=True))
    t.append("(unnamed)\n", Style(dim=True))
    here = occupants(state, room.id)
    t.append(f"\noccupants ({len(here)}):\n", Style(bold=True))
    if not here:
        t.append("  (empty)\n", Style(dim=True))
    for r in here:
        t.append("  ")
        t.append(r.id, resident_style(metric_value(state, r)))
        t.append(f"  {r.archetype}\n")
    return t
