"""The Textual terminal UI.

A thin shell over the seam: it renders :class:`~sim.GameState` and forwards
every player input to :func:`router.take_turn`. Public surface:

* :class:`AntFarmApp` — the Textual app
* :func:`render_grid`, :func:`render_status` — pure render helpers
"""

from ui.app import AntFarmApp
from ui.render import render_grid, render_status

__all__ = ["AntFarmApp", "render_grid", "render_status"]
