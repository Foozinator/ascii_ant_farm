"""Inspection layer: selection, detail panel, catalog, hotkeys, command palette.

Pure helpers are tested directly; the wired-up widget behaviour (focus zones,
roster/grid selection, `m`, the typed line) is exercised through Textual's
headless pilot. Selection is UI-local throughout — the sim is never mutated by
looking.
"""

from __future__ import annotations

import asyncio

import ui.palette as palette
from sim.generator import generate
from ui.app import AntFarmApp, TankGrid
from ui.catalog import card_for
from ui.inspect import (
    Selection,
    highlight_cells,
    next_metric,
    resident_at,
    room_at,
    selection_at,
)
from ui.palette import metric_value, resident_style
from ui.render import render_detail


def _run(coro):
    """Run an async pilot test body without a pytest-asyncio plugin."""
    asyncio.run(coro)


def _first_placed_resident(state):
    return next(r for r in state.residents if r.row is not None)


def _empty_room_cell(state):
    """A room floor cell with no resident on it (so it selects the room)."""
    occupied = {(r.row, r.col) for r in state.residents if r.row is not None}
    for room in state.rooms:
        for cell in room.cells:
            if (cell[0], cell[1]) not in occupied:
                return room, cell[0], cell[1]
    raise AssertionError("no empty room cell found")


# --------------------------------------------------------------------------- #
# Catalog (read as data, not via llm)
# --------------------------------------------------------------------------- #

def test_catalog_lookup_and_graceful_fallback():
    assert card_for("bryce_hustle")["name"] == "Bryce"
    assert card_for("not_a_real_id") is None
    assert card_for(None) is None
    # The default 8x10 colony uses free tags with no card — must not raise.
    assert card_for("forager") is None


# --------------------------------------------------------------------------- #
# Selection (pure)
# --------------------------------------------------------------------------- #

def test_selection_at_resident_beats_room():
    state = generate(24, 14, seed=5)
    r = _first_placed_resident(state)
    sel = selection_at(state, r.row, r.col)
    assert sel == Selection("resident", r.id)
    assert resident_at(state, r.row, r.col).id == r.id


def test_selection_at_empty_room_cell_selects_room():
    state = generate(24, 14, seed=5)
    room, row, col = _empty_room_cell(state)
    sel = selection_at(state, row, col)
    assert sel == Selection("room", room.id)
    assert room_at(state, row, col).id == room.id


def test_highlight_cells_for_room_is_whole_floor():
    state = generate(24, 14, seed=5)
    room = state.rooms[0]
    cells = highlight_cells(state, Selection("room", room.id))
    assert cells == {(c[0], c[1]) for c in room.cells}


# --------------------------------------------------------------------------- #
# Detail panel (pure) — names live HERE
# --------------------------------------------------------------------------- #

def test_detail_resident_shows_card_metric_and_position():
    state = generate(24, 14, seed=5)
    r = _first_placed_resident(state)
    card = card_for(r.archetype)
    assert card is not None  # generated residents carry catalog ids

    text = str(render_detail(state, Selection("resident", r.id)))
    assert card["name"] in text            # display name
    assert card["archetype"] in text       # archetype line
    assert state.metric in text            # active-metric label
    assert f"({r.row}, {r.col})" in text   # position


def test_detail_room_shows_function_and_occupants():
    state = generate(24, 14, seed=5)
    # Pick a room that actually has occupants.
    room = next(
        rm for rm in state.rooms
        if any(res.room_id == rm.id for res in state.residents)
    )
    text = str(render_detail(state, Selection("room", room.id)))
    assert room.room_type.value in text                       # function
    assert "(unnamed)" in text                                # placeholder name
    for res in state.residents:
        if res.room_id == room.id:
            assert res.id in text                             # occupants


def test_detail_none_is_a_hint():
    state = generate(24, 14, seed=5)
    text = str(render_detail(state, None)).lower()
    assert "nothing selected" in text


# --------------------------------------------------------------------------- #
# Metric cycling + recolour (pure)
# --------------------------------------------------------------------------- #

def test_next_metric_cycles():
    assert next_metric("mood") == "food"
    assert next_metric("food") == "power"
    assert next_metric("power") == "mood"
    assert next_metric("weird") == "mood"


def test_metric_change_recolours_residents():
    state = generate(24, 14, seed=5)
    r = _first_placed_resident(state)
    r.mood = 0.95
    state.food = 0.0  # so the food metric maps to the low end of the gradient

    # Force the truecolor tier so the gradient is exercised (pytest stdout is a
    # pipe, which the palette detects as no-colour).
    saved = (palette._RICH, palette._BASIC)
    palette._RICH, palette._BASIC = True, False
    try:
        state.metric = "mood"
        hot = resident_style(metric_value(state, r))
        state.metric = "food"
        cold = resident_style(metric_value(state, r))
    finally:
        palette._RICH, palette._BASIC = saved

    assert hot != cold  # switching the active metric recolours the resident


# --------------------------------------------------------------------------- #
# Command palette — every command is registered & discoverable
# --------------------------------------------------------------------------- #

def test_command_palette_lists_registered_commands():
    app = AntFarmApp(state=generate(20, 12, seed=1))
    titles = [c.title.lower() for c in app.colony_commands()]
    for needed in ("feed", "light", "metric", "watch", "save", "load", "quit"):
        assert any(needed in t for t in titles), f"missing command: {needed}"
    # inspect/selection actions are registered too
    assert any("next resident" in t for t in titles)
    assert any("focus tank" in t for t in titles)


# --------------------------------------------------------------------------- #
# Wired behaviour (Textual headless pilot)
# --------------------------------------------------------------------------- #

def test_opens_focused_on_the_tank():
    async def body():
        app = AntFarmApp(state=generate(20, 12, seed=3))
        async with app.run_test():
            assert isinstance(app.focused, TankGrid)
    _run(body())


def test_select_resident_via_roster_updates_detail():
    async def body():
        state = generate(20, 12, seed=3)
        app = AntFarmApp(state=state)
        async with app.run_test() as pilot:
            ol = app.query_one("#residents")
            ol.highlighted = 0  # arrow/click would do the same
            await pilot.pause()
            rid = state.residents[0].id
            assert app.selection == Selection("resident", rid)
            detail = str(render_detail(app.state, app.selection))
            card = card_for(state.residents[0].archetype)
            assert card["name"] in detail
    _run(body())


def test_select_resident_via_grid_cursor_updates_detail():
    async def body():
        state = generate(20, 12, seed=3)
        app = AntFarmApp(state=state)
        async with app.run_test() as pilot:
            r = _first_placed_resident(state)
            app.select_cell(r.row, r.col)  # the grid cursor / click path
            await pilot.pause()
            assert app.selection == Selection("resident", r.id)
            assert app.cursor == (r.row, r.col)
            detail = str(render_detail(app.state, app.selection))
            assert card_for(r.archetype)["name"] in detail
    _run(body())


def test_select_room_via_grid_cursor_updates_detail():
    async def body():
        state = generate(20, 12, seed=3)
        app = AntFarmApp(state=state)
        async with app.run_test() as pilot:
            room, row, col = _empty_room_cell(state)
            app.select_cell(row, col)
            await pilot.pause()
            assert app.selection == Selection("room", room.id)
            detail = str(render_detail(app.state, app.selection))
            assert room.room_type.value in detail
    _run(body())


def test_arrow_moves_cursor_in_looking_mode():
    async def body():
        app = AntFarmApp(state=generate(20, 12, seed=3))
        async with app.run_test() as pilot:
            before = app.cursor
            await pilot.press("down")
            assert app.cursor != before
            assert app.cursor[0] == before[0] + 1
    _run(body())


def test_m_cycles_metric_without_ticking():
    async def body():
        app = AntFarmApp(state=generate(20, 12, seed=3))
        async with app.run_test() as pilot:
            turn0, metric0 = app.state.turn, app.state.metric
            await pilot.press("m")
            assert app.state.metric == next_metric(metric0)
            assert app.state.turn == turn0  # looking does not advance the sim
    _run(body())


def test_typed_knob_and_gesture_still_work():
    async def body():
        app = AntFarmApp(state=generate(20, 12, seed=3))
        async with app.run_test() as pilot:
            inp = app.query_one("#cmd")
            app.set_focus(inp)
            await pilot.pause()

            inp.value = "feed 5"
            await pilot.press("enter")
            await pilot.pause()
            assert app.state.food == 4.5   # set to 5, then the tick consumes 0.5
            assert app.state.turn == 1

            turn1 = app.state.turn
            inp.value = "tap the glass over the offices"
            await pilot.press("enter")
            await pilot.pause()
            assert app.state.turn == turn1 + 1  # gesture routed + ticked
    _run(body())
