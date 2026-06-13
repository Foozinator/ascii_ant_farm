"""Headless walking-skeleton demo — proves the pipe without a terminal.

Runs the two canonical inputs from the success criterion through the *real*
turn router and prints what happens at each stage:

* ``feed 5`` takes the deterministic knob path (the stub parser is NOT called).
* ``tap the glass over the offices`` misses the grammar and is routed through
  the stub parser, validated at the seam, applied, and digested.

Then it round-trips the colony through JSON to prove serialization.

Run with ``python demo.py`` or ``python main.py --demo``.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from contract import EffectEnvelope
from router import take_turn
from sim import GameState, default_state, load, save
from ui.render import render_grid, render_status


class ParseSpy:
    """Wraps the real stub parser and counts how often it's called."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, sentence: str, state: GameState) -> EffectEnvelope:
        import llm

        self.calls += 1
        return llm.parse(sentence, state)


def _banner(title: str) -> None:
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def _show_colony(state: GameState) -> None:
    print(render_grid(state))
    print()
    print(render_status(state))


def run_demo() -> None:
    import llm

    _banner("ASCII Ant Farm - walking skeleton demo")
    print(llm.check_backend()[1])  # which engine is active (and reachable?)
    state = default_state()
    print("\nInitial colony:\n")
    _show_colony(state)

    # ---- Turn 1: knob path -------------------------------------------------
    _banner("Turn 1 (knob path):  input = 'feed 5'")
    spy = ParseSpy()
    food_before = state.food
    state, result = take_turn(state, "feed 5", parse=spy)
    print(f"routed via      : {result.path}")
    print(f"stub parser hits: {spy.calls}   <-- 0 proves the knob path skips the parser")
    print(f"applied effects : {result.effects}")
    print(f"food            : {food_before:.1f} -> {state.food:.1f}")
    print(f"report          : {result.report.prose}")
    print()
    print(render_grid(state))

    # ---- Turn 2: gesture path ---------------------------------------------
    _banner("Turn 2 (gesture path):  input = 'tap the glass over the offices'")
    spy = ParseSpy()
    state, result = take_turn(state, "tap the glass over the offices", parse=spy)
    print(f"routed via      : {result.path}")
    print(f"stub parser hits: {spy.calls}   <-- 1 proves the sentence went through the parser")
    print(f"applied effects : {result.effects}")
    print(f"prose           : {result.prose}")
    print(f"report          : {result.report.prose}")
    print(f"mood deltas     : {result.report.mood_deltas}")
    print(f"flags           : {result.report.flags}")
    print()
    _show_colony(state)

    # ---- Save / load round-trip -------------------------------------------
    _banner("Save / load round-trip (proves JSON serialization)")
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "demo_save.json"
        save(state, path)
        reloaded = load(path)
        print(f"saved to        : {path.name}")
        print(f"states equal    : {reloaded == state}")

    print("\nDemo complete - one full turn flows end to end through the seam.\n")


if __name__ == "__main__":
    run_demo()
