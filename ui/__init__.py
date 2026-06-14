"""The Textual terminal UI.

A thin shell over the seam: it renders :class:`~sim.GameState` and forwards
every player input to :func:`router.take_turn`. Inspection (selection + detail
panel) is layered on top and stays UI-local — it never touches the sim. Public
surface:

* :class:`AntFarmApp` — the Textual app
* :func:`render_grid`, :func:`render_status` — pure render helpers
* :func:`render_stats`, :func:`render_detail` — the app's stats/detail panels
"""

from ui.app import AntFarmApp
from ui.render import render_detail, render_grid, render_stats, render_status

__all__ = [
    "AntFarmApp",
    "render_grid",
    "render_status",
    "render_stats",
    "render_detail",
]
