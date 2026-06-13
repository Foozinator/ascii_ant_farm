"""The deterministic simulation core.

Public surface — import these rather than reaching into submodules:

* :func:`default_state`, :func:`tick`, :func:`save`, :func:`load`
* :class:`GameState`, :class:`Resident`, :class:`CellType`, ``CELL_GLYPHS``

``sim`` owns all state and never imports ``llm`` or ``ui``.
"""

from sim.engine import default_state, from_json, load, save, tick, to_json
from sim.state import CELL_GLYPHS, CellType, GameState, Resident

__all__ = [
    "default_state",
    "tick",
    "save",
    "load",
    "to_json",
    "from_json",
    "GameState",
    "Resident",
    "CellType",
    "CELL_GLYPHS",
]
