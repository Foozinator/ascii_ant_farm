"""Tests for the procedural generator: determinism, connectivity, watch mode."""

from __future__ import annotations

from collections import deque

from sim import from_json, tick, to_json
from sim.generator import generate
from sim.state import CellType


# --------------------------------------------------------------------------- #
# Determinism
# --------------------------------------------------------------------------- #

def test_same_seed_same_tank():
    a = generate(40, 20, seed=7)
    b = generate(40, 20, seed=7)
    assert a == b


def test_different_seeds_differ():
    a = generate(40, 20, seed=7)
    b = generate(40, 20, seed=99)
    assert a.grid != b.grid


def test_default_size_with_seed_is_deterministic():
    a = generate(8, 10, seed=1)
    b = generate(8, 10, seed=1)
    assert a == b


# --------------------------------------------------------------------------- #
# Connectivity: every non-DIRT cell reachable from every other
# --------------------------------------------------------------------------- #

def _non_dirt_cells(state) -> set[tuple[int, int]]:
    return {
        (r, c)
        for r, row in enumerate(state.grid)
        for c, cell in enumerate(row)
        if cell is not CellType.DIRT
    }


def _reachable_from(start: tuple[int, int], non_dirt: set[tuple[int, int]]) -> set[tuple[int, int]]:
    visited: set[tuple[int, int]] = set()
    q: deque[tuple[int, int]] = deque([start])
    while q:
        r, c = q.popleft()
        if (r, c) in visited:
            continue
        visited.add((r, c))
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nb = (r + dr, c + dc)
            if nb in non_dirt and nb not in visited:
                q.append(nb)
    return visited


def test_connectivity_large():
    state = generate(40, 20, seed=42)
    non_dirt = _non_dirt_cells(state)
    assert non_dirt, "generated tank has no open cells"
    start = next(iter(non_dirt))
    assert _reachable_from(start, non_dirt) == non_dirt


def test_connectivity_small():
    state = generate(16, 12, seed=5)
    non_dirt = _non_dirt_cells(state)
    assert non_dirt
    start = next(iter(non_dirt))
    assert _reachable_from(start, non_dirt) == non_dirt


def test_connectivity_default_size():
    state = generate(8, 10, seed=3)
    non_dirt = _non_dirt_cells(state)
    assert non_dirt
    start = next(iter(non_dirt))
    assert _reachable_from(start, non_dirt) == non_dirt


# --------------------------------------------------------------------------- #
# Rooms and residents
# --------------------------------------------------------------------------- #

def test_rooms_are_populated():
    state = generate(40, 20, seed=7)
    assert len(state.rooms) >= 5


def test_residents_have_positions():
    state = generate(40, 20, seed=7)
    assert state.residents
    for r in state.residents:
        assert r.row is not None
        assert r.col is not None
        assert r.room_id != ""


def test_resident_positions_are_inside_rooms():
    state = generate(20, 14, seed=11)
    room_cells = {
        (cell[0], cell[1])
        for room in state.rooms
        for cell in room.cells
    }
    for r in state.residents:
        assert (r.row, r.col) in room_cells, (
            f"{r.id} at ({r.row},{r.col}) is not inside any room"
        )


# --------------------------------------------------------------------------- #
# watch N: advances exactly N ticks, state stays serializable
# --------------------------------------------------------------------------- #

def test_watch_advances_n_ticks():
    state = generate(20, 12, seed=2)
    assert state.turn == 0
    n = 20
    for _ in range(n):
        state = tick(state, [])
    assert state.turn == n


def test_watch_state_serializes():
    state = generate(20, 12, seed=2)
    for _ in range(10):
        state = tick(state, [])
    assert from_json(to_json(state)) == state


def test_headless_watch_output(capsys):
    from ui.watch import run_watch
    state = generate(16, 10, seed=1)
    run_watch(state, 5, headless=True)
    out = capsys.readouterr().out
    assert "turn=5" in out
    assert "food=" in out
    assert "mood_mean=" in out


# --------------------------------------------------------------------------- #
# Existing 8x10 tests still pass (tick purity, no positions required)
# --------------------------------------------------------------------------- #

def test_existing_default_state_still_works():
    from sim import default_state
    from contract import Effect, EffectType

    s = default_state()
    s2 = tick(s, [Effect(type=EffectType.FEED, target="food", magnitude=9)])
    assert s2.food == 8.5
    assert s.turn == 0        # original untouched
    assert s2.turn == 1
