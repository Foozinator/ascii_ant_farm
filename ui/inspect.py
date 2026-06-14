"""Selection model and pure inspection helpers — the 'looking' substrate.

Selection is a **view concern**: it lives only in UI state and never touches the
sim or the save file. Everything here is a pure read over a
:class:`~sim.GameState` so it can be unit-tested without a running app.

A selection is a room, a resident, or nothing. The grid cursor and the resident
list both produce selections through :func:`selection_at` /
:func:`Selection`; the detail panel and grid highlight consume them.

This is intentionally the groundwork for the deferred focus/attention mechanic,
but it implements **inspection only** — no unobserved-regions-run-blind here.
"""

from __future__ import annotations

from dataclasses import dataclass

# The metrics the `m` hotkey cycles through. ``mood`` is per-resident; ``food``
# and ``power`` are colony-wide. Matches the colouring in :mod:`ui.palette`.
METRICS: tuple[str, ...] = ("mood", "food", "power")


@dataclass(frozen=True)
class Selection:
    """A UI-local selection. ``kind`` is ``"room"`` or ``"resident"``."""

    kind: str
    id: str


def next_metric(current: str) -> str:
    """The next metric after ``current`` in the cycle (wraps)."""
    cur = (current or "mood").lower()
    if cur in METRICS:
        return METRICS[(METRICS.index(cur) + 1) % len(METRICS)]
    return METRICS[0]


# --------------------------------------------------------------------------- #
# Read-only lookups over state
# --------------------------------------------------------------------------- #

def resident_by_id(state, rid: str):
    for r in state.residents:
        if r.id == rid:
            return r
    return None


def room_by_id(state, room_id: str):
    for room in state.rooms:
        if room.id == room_id:
            return room
    return None


def resident_at(state, row: int, col: int):
    """The first placed resident standing on ``(row, col)``, or ``None``."""
    for r in state.residents:
        if r.row == row and r.col == col:
            return r
    return None


def room_at(state, row: int, col: int):
    """The room whose floor includes ``(row, col)``, or ``None``."""
    for room in state.rooms:
        for cell in room.cells:
            if cell[0] == row and cell[1] == col:
                return room
    return None


def selection_at(state, row: int, col: int) -> Selection | None:
    """What the grid cursor selects at ``(row, col)``.

    A resident under the cursor wins over the room it stands in; an empty room
    cell selects the room; sand/tunnel with nothing on it selects nothing.
    """
    r = resident_at(state, row, col)
    if r is not None:
        return Selection("resident", r.id)
    room = room_at(state, row, col)
    if room is not None:
        return Selection("room", room.id)
    return None


def occupants(state, room_id: str) -> list:
    """Residents whose ``room_id`` is this room, in roster order."""
    return [r for r in state.residents if r.room_id == room_id]


def highlight_cells(state, selection: Selection | None) -> set[tuple[int, int]]:
    """Grid cells to highlight for ``selection`` (a resident cell or a room)."""
    if selection is None:
        return set()
    if selection.kind == "resident":
        r = resident_by_id(state, selection.id)
        if r is not None and r.row is not None and r.col is not None:
            return {(r.row, r.col)}
        return set()
    room = room_by_id(state, selection.id)
    if room is not None:
        return {(c[0], c[1]) for c in room.cells}
    return set()
