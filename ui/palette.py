"""Colour palette and terminal-capability detection for the renderer.

The palette builds a visual *hierarchy by weight* so the excavated colony reads
as the figure and the sand recedes into the ground:

* **Sand** (``#``) — dim, low-contrast gray. It is most of the tank and must
  recede; it is never left bright.
* **Tunnels** (``.``) — a quiet neutral, one step above sand, so the carved
  network is legible without competing.
* **Rooms** (``O``/``N``/``P``) — distinct categorical *hues*, kept muted and
  desaturated. The hues are drawn from the Okabe–Ito colourblind-safe set
  (blue / amber / green) so they never rely on a red-vs-green distinction.
* **Residents** — the loudest element. Coloured on a perceptually-ordered
  gradient (viridis) by the *currently active metric*, saturated and bold so
  they pop against the muted rooms and dim sand.

Degrades gracefully. We detect the terminal's colour support once:

* ``truecolor`` / ``256``  → the full muted hex palette and a smooth gradient.
* ``standard`` / ``windows`` (16 colours) → a curated named palette whose room
  hues (blue/amber/green) and resident hues (magenta/cyan/white) stay mutually
  distinguishable instead of collapsing under nearest-colour downsampling.
* no colour → plain text; residents stay **bold** so they still read as figure.
"""

from __future__ import annotations

from rich.console import Console
from rich.style import Style

from sim import CellType

# Detect once. 'truecolor' | '256' | 'standard' | 'windows' | None.
# In a real interactive terminal (how the TUI and watch mode are run) this
# reports the true capability; when stdout is piped it reports None and we fall
# back to plain text, which is what captured output wants anyway.
COLOR_SYSTEM: str | None = Console().color_system
_RICH = COLOR_SYSTEM in ("truecolor", "256")
_BASIC = COLOR_SYSTEM in ("standard", "windows")


def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, v))


# --------------------------------------------------------------------------- #
# Substrate + room styles, per capability tier
# --------------------------------------------------------------------------- #

# Truecolor/256: muted hex. Sand recedes; tunnel a step above; rooms are
# desaturated Okabe–Ito hues (blue / amber / bluish-green).
_RICH_CELL: dict[CellType, Style] = {
    CellType.DIRT: Style(color="#454545"),     # sand — dim gray, recedes
    CellType.TUNNEL: Style(color="#7d7d7d"),   # quiet neutral, a step above
    CellType.OFFICES: Style(color="#3d6d94"),  # muted blue
    CellType.NURSERY: Style(color="#a87a2c"),  # muted amber
    CellType.PANTRY: Style(color="#3f8a72"),   # muted bluish-green
}

# 16-colour fallback: named ANSI chosen so the categories stay distinct.
# Rooms use blue/yellow/green; residents (below) use magenta/cyan/white — the
# two sets are disjoint so nothing collapses together.
_BASIC_CELL: dict[CellType, Style] = {
    CellType.DIRT: Style(color="bright_black"),       # the conventional gray
    CellType.TUNNEL: Style(color="white", dim=True),  # a dim step above sand
    CellType.OFFICES: Style(color="blue"),
    CellType.NURSERY: Style(color="yellow"),
    CellType.PANTRY: Style(color="green"),
}

_PLAIN = Style()


def cell_style(cell: CellType) -> Style:
    """Style for a substrate/room glyph, honouring the detected colour tier."""
    if _RICH:
        return _RICH_CELL.get(cell, _PLAIN)
    if _BASIC:
        return _BASIC_CELL.get(cell, _PLAIN)
    return _PLAIN


# --------------------------------------------------------------------------- #
# Resident gradient — the loudest element, keyed to a 0..1 metric value
# --------------------------------------------------------------------------- #

# Viridis anchor stops (perceptually uniform, colourblind-safe). Interpolated
# for truecolor; bucketed for 16-colour terminals.
_VIRIDIS: list[tuple[float, tuple[int, int, int]]] = [
    (0.00, (68, 1, 84)),     # deep violet  (low)
    (0.25, (59, 82, 139)),   # indigo
    (0.50, (33, 145, 140)),  # teal
    (0.75, (94, 201, 98)),   # green
    (1.00, (253, 231, 37)),  # bright yellow (high)
]


def _lerp(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))  # type: ignore[return-value]


def _viridis_hex(value: float) -> str:
    value = _clamp01(value)
    for i in range(len(_VIRIDIS) - 1):
        v0, c0 = _VIRIDIS[i]
        v1, c1 = _VIRIDIS[i + 1]
        if value <= v1:
            t = 0.0 if v1 == v0 else (value - v0) / (v1 - v0)
            r, g, b = _lerp(c0, c1, t)
            return f"#{r:02x}{g:02x}{b:02x}"
    r, g, b = _VIRIDIS[-1][1]
    return f"#{r:02x}{g:02x}{b:02x}"


# 16-colour resident buckets: loud, bold, and disjoint from the room hues.
_BASIC_RESIDENT = ["bright_magenta", "bright_cyan", "bright_white"]


def resident_style(value: float) -> Style:
    """Style for a resident glyph, coloured by the active metric value (0..1)."""
    value = _clamp01(value)
    if _RICH:
        return Style(color=_viridis_hex(value), bold=True)
    if _BASIC:
        idx = 0 if value < 0.34 else 1 if value < 0.67 else 2
        return Style(color=_BASIC_RESIDENT[idx], bold=True)
    # No colour: bold still lifts residents off the substrate.
    return Style(bold=True)


# --------------------------------------------------------------------------- #
# Metric → per-resident value. Not hard-coded to mood: changing state.metric
# recolours the colony.
# --------------------------------------------------------------------------- #

def metric_value(state, resident) -> float:
    """Map the colony's active metric to a 0..1 value for one resident.

    ``mood`` is per-resident, so residents differentiate individually. The
    colony-wide stocks (``food``/``power``) shift every resident together — they
    still *recolour* when the metric changes, which is the point. Unknown
    metrics fall back to mood.
    """
    metric = (state.metric or "mood").lower()
    if metric == "food":
        return _clamp01(state.food / 9.0)
    if metric == "power":
        return _clamp01(state.power / 100.0)
    return _clamp01(resident.mood)
