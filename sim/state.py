"""The simulation's data model — every piece of mutable game state.

``sim`` owns *all* state. The UI and the language model only ever see snapshots
of these types; they never hold their own copies. Everything here is a Pydantic
model so the whole world serializes to JSON for free (see ``sim.engine.save`` /
``sim.engine.load``).

This module deliberately imports nothing from ``llm`` or ``ui`` — the simulation
is the deterministic core and must stay buildable in isolation.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class CellType(str, Enum):
    """What a single grid cell is.

    ``DIRT`` and ``TUNNEL`` are the substrate; the remaining values are room
    types. ``GESTURE`` effects target rooms by these names (lowercased).
    """

    DIRT = "dirt"
    TUNNEL = "tunnel"
    NURSERY = "nursery"
    OFFICES = "offices"
    PANTRY = "pantry"


# How each cell type renders in the ASCII grid. One char each, so the grid stays
# a clean rectangle. The UI reads this; nothing in the sim depends on glyphs.
CELL_GLYPHS: dict[CellType, str] = {
    CellType.DIRT: "#",
    CellType.TUNNEL: ".",
    CellType.NURSERY: "N",
    CellType.OFFICES: "O",
    CellType.PANTRY: "P",
}

# Reverse map, used only to author the default layout from a picture-string.
_GLYPH_TO_CELL: dict[str, CellType] = {g: c for c, g in CELL_GLYPHS.items()}


class Room(BaseModel):
    """A connected floor region carved from dirt."""

    id: str
    room_type: CellType
    cells: list[list[int]]  # [[row, col], ...] floor positions


class Resident(BaseModel):
    """One ant. ``mood`` is a 0..1 float; ``archetype`` is a free tag."""

    id: str
    mood: float = 0.5
    archetype: str = "worker"
    row: int | None = None  # grid position; None = not placed
    col: int | None = None
    room_id: str = ""  # which room they inhabit


class GameState(BaseModel):
    """The entire colony at one instant.

    Sizes are not constrained — ``width``/``depth`` default to 8x10 but a loaded
    save can be any rectangle, so the renderer reads the grid's real dimensions
    rather than assuming the defaults.
    """

    width: int = 8
    depth: int = 10
    # grid[row][col]; row 0 is the surface, increasing row goes deeper.
    grid: list[list[CellType]]

    # Stocks. food is kept on a 0..9 scale (matches the ``feed`` knob), power on
    # 0..100 (matches the ``light`` knob).
    food: float = 3.0
    power: float = 50.0

    residents: list[Resident] = Field(default_factory=list)
    rooms: list[Room] = Field(default_factory=list)

    # Rolling history the UI shows; trimmed to the last few entries by the engine.
    event_log: list[str] = Field(default_factory=list)

    # The subset of events produced by the most recent tick. This is what gets
    # handed to ``llm.digest`` as ``new_events`` — keeping it on the state is how
    # we feed the digest while honoring tick's fixed ``(state, effects) -> state``
    # signature. It is overwritten every tick, not accumulated.
    last_events: list[str] = Field(default_factory=list)

    # Which metric the player is currently watching (e.g. "mood", "food").
    metric: str = "mood"

    turn: int = 0


# Default colony: vertical tunnels down columns 1 and 6 connecting three rooms,
# carved out of surrounding dirt. Each row is exactly `width` glyphs wide.
_DEFAULT_LAYOUT: list[str] = [
    "........",  # 0  surface
    "#.####.#",  # 1
    "#.OOOO.#",  # 2  offices
    "#.#..#.#",  # 3
    "#.NNNN.#",  # 4  nursery
    "#.#..#.#",  # 5
    "#.PPPP.#",  # 6  pantry
    "#.####.#",  # 7
    "#......#",  # 8
    "########",  # 9  bedrock
]


def build_grid(layout: list[str]) -> list[list[CellType]]:
    """Turn a list of glyph-strings into a grid of :class:`CellType`."""
    return [[_GLYPH_TO_CELL[ch] for ch in row] for row in layout]


def default_grid() -> list[list[CellType]]:
    return build_grid(_DEFAULT_LAYOUT)
