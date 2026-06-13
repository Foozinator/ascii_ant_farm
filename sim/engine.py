"""The deterministic engine: build a colony, advance it one tick, save/load it.

``tick(state, effects) -> state`` is the only way state changes. It applies the
validated effects handed in across the contract seam, then advances the world by
one step (consumption + mood drift). It is pure: it copies the incoming state
and returns a new one, so callers can keep the previous value if they want.

This module imports the contract (to read :class:`Effect`) but never imports
``llm`` — the simulation must not know the language model exists.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from contract import Effect, EffectType
from sim.state import (
    GameState,
    Resident,
    default_grid,
)

# How many history entries to keep in event_log (the "last ~10 events").
EVENT_LOG_MAX = 10

# Per-tick world step constants. Small and fixed — this is a skeleton, not a
# balanced economy, but the drift proves a tick genuinely advances time.
_FOOD_PER_TICK = 0.5
_POWER_PER_TICK = 1.0
_MOOD_UP = 0.02
_MOOD_DOWN = 0.05
_FOOD_HUNGRY_BELOW = 2.0
_POWER_BROWNOUT_BELOW = 10.0


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


# Possible wander deltas; (0,0) appears twice so residents stay ~1/3 of ticks.
_WANDER_DELTAS = [(-1, 0), (1, 0), (0, -1), (0, 1), (0, 0), (0, 0)]


def _wander_offset(resident_id: str, turn: int) -> tuple[int, int]:
    """Deterministic wander delta derived from resident id and current turn."""
    digest = hashlib.md5(f"{resident_id}:{turn}".encode()).digest()
    h = int.from_bytes(digest[:4], "little")
    return _WANDER_DELTAS[h % len(_WANDER_DELTAS)]


def default_state() -> GameState:
    """A fresh colony: the default 8x10 grid and a small starting cast."""
    return GameState(
        width=8,
        depth=10,
        grid=default_grid(),
        food=3.0,
        power=50.0,
        residents=[
            Resident(id="ant-01", mood=0.60, archetype="forager"),
            Resident(id="ant-02", mood=0.50, archetype="nurse"),
            Resident(id="ant-03", mood=0.45, archetype="drone"),
            Resident(id="ant-04", mood=0.70, archetype="queen"),
        ],
        event_log=["The colony wakes. Four ants stir in the dark."],
        metric="mood",
        turn=0,
    )


def _apply_effect(state: GameState, eff: Effect, events: list[str]) -> None:
    """Mutate ``state`` for a single validated effect, logging what happened."""
    if eff.type is EffectType.FEED:
        state.food = _clamp(eff.magnitude, 0.0, 9.0)
        events.append(f"Feed dial set to {state.food:.0f}.")
    elif eff.type is EffectType.LIGHT:
        state.power = _clamp(eff.magnitude, 0.0, 100.0)
        events.append(f"Lights set to {state.power:.0f}%.")
    elif eff.type is EffectType.METRIC:
        state.metric = eff.target
        events.append(f"Now watching the '{eff.target}' metric.")
    elif eff.type is EffectType.GESTURE:
        # Open-ended nudge: shift every ant's mood by the magnitude. The target
        # (a room/colony tag) is descriptive here; a richer sim would scope the
        # nudge to residents in that room.
        for r in state.residents:
            r.mood = _clamp(r.mood + eff.magnitude, 0.0, 1.0)
        verb = "soothes" if eff.magnitude >= 0 else "rattles"
        events.append(
            f"A gesture toward '{eff.target}' {verb} the colony "
            f"({eff.magnitude:+.2f} mood)."
        )


def _advance_step(state: GameState, events: list[str]) -> None:
    """Advance the world one step: consume stocks, drift moods, wander residents."""
    state.food = max(0.0, state.food - _FOOD_PER_TICK)
    state.power = max(0.0, state.power - _POWER_PER_TICK)

    hungry = state.food < _FOOD_HUNGRY_BELOW
    dark = state.power < _POWER_BROWNOUT_BELOW
    drift = -_MOOD_DOWN if (hungry or dark) else _MOOD_UP
    for r in state.residents:
        r.mood = _clamp(r.mood + drift, 0.0, 1.0)

    if hungry:
        events.append("Stores run low; the ants are getting hungry.")
    if dark:
        events.append("The lights gutter; a brownout sets in.")

    # Wander: drift residents within their room's floor cells.
    if state.rooms:
        valid_cells: dict[str, set[tuple[int, int]]] = {
            room.id: {(cell[0], cell[1]) for cell in room.cells}
            for room in state.rooms
        }
        for r in state.residents:
            if r.row is None or r.col is None or not r.room_id:
                continue
            floor = valid_cells.get(r.room_id)
            if not floor:
                continue
            dr, dc = _wander_offset(r.id, state.turn)
            nr, nc = r.row + dr, r.col + dc
            if (nr, nc) in floor:
                r.row, r.col = nr, nc


def tick(state: GameState, effects: list[Effect]) -> GameState:
    """Apply ``effects`` and advance the colony one step. Returns a new state.

    The input is not mutated. ``effects`` must already be validated
    :class:`Effect` instances (the router enforces this at the seam).
    """
    state = state.model_copy(deep=True)

    events: list[str] = []
    for eff in effects:
        _apply_effect(state, eff, events)

    _advance_step(state, events)

    state.turn += 1

    # last_events = just this turn's events (fed to the digest); event_log is the
    # rolling history (shown by the UI), trimmed to the most recent entries.
    state.last_events = events
    state.event_log = (state.event_log + events)[-EVENT_LOG_MAX:]
    return state


def save(state: GameState, path: str | Path) -> None:
    """Serialize the entire colony to a JSON file."""
    Path(path).write_text(state.model_dump_json(indent=2), encoding="utf-8")


def load(path: str | Path) -> GameState:
    """Reconstruct a colony from a JSON file written by :func:`save`."""
    return GameState.model_validate_json(Path(path).read_text(encoding="utf-8"))


def to_json(state: GameState) -> str:
    """Serialize to a JSON string (used by tests / round-trip checks)."""
    return state.model_dump_json()


def from_json(data: str) -> GameState:
    """Inverse of :func:`to_json`."""
    return GameState.model_validate_json(data)
