"""Watch mode: advance N ticks and animate them in the terminal.

``run_watch(state, n)`` ticks the sim N times (no player input) and prints
each frame at ``fps`` frames per second. ``--headless`` suppresses animation
and prints a one-line summary — useful as a quick balance-test harness.

This module imports ``sim`` and ``ui.render`` but never imports ``llm``; the
watch loop is entirely deterministic.
"""

from __future__ import annotations

import time

from sim import GameState, tick
from ui.render import render_grid, render_status


def _clear() -> None:
    print("\033[2J\033[H", end="", flush=True)


def run_watch(
    state: GameState,
    n_ticks: int,
    *,
    headless: bool = False,
    fps: float = 5.0,
) -> GameState:
    """Advance ``n_ticks`` ticks and animate (or run silently in headless mode).

    Returns the final state so callers can inspect it (e.g. in tests).
    Handles ``KeyboardInterrupt`` gracefully so Ctrl-C stops the animation.
    """
    if headless:
        for _ in range(n_ticks):
            state = tick(state, [])
        residents = state.residents
        mood_mean = sum(r.mood for r in residents) / max(1, len(residents))
        print(
            f"turn={state.turn} food={state.food:.1f} "
            f"power={state.power:.1f} mood_mean={mood_mean:.2f}"
        )
        return state

    delay = 1.0 / max(0.1, fps)
    try:
        for frame in range(n_ticks):
            state = tick(state, [])
            _clear()
            print(f"  ASCII Ant Farm  |  watch {frame + 1}/{n_ticks}  |  Ctrl-C to stop\n")
            print(render_grid(state))
            print()
            print(render_status(state))
            if state.last_events:
                print()
                for ev in state.last_events[-3:]:
                    print(f"  {ev}")
            time.sleep(delay)
    except KeyboardInterrupt:
        print("\n\nStopped.")

    return state
