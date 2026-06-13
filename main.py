"""Entry point for ASCII Ant Farm.

Usage
-----
python main.py                        launch the Textual TUI (default 8x10 layout)
python main.py --size 40x20 --seed 7  generate a large tank, then open TUI
python main.py --seed 7               regenerate the default 8x10 with a seed
python main.py --watch 20             animate 20 ticks in the terminal
python main.py --watch 20 --headless  run 20 ticks silently, print one-line summary
python main.py --demo                 headless walking-skeleton demo
"""

from __future__ import annotations

import sys


def _parse_size(s: str) -> tuple[int, int]:
    """Parse 'WxH' → (width, height). Raises ValueError on bad input."""
    parts = s.lower().split("x")
    if len(parts) != 2:
        raise ValueError(f"--size must be WxH, got {s!r}")
    return int(parts[0]), int(parts[1])


def main(argv: list[str] | None = None) -> None:
    import argparse

    argv = sys.argv[1:] if argv is None else argv

    parser = argparse.ArgumentParser(prog="ascii-ant-farm", add_help=True)
    parser.add_argument("--demo", action="store_true", help="run headless walking-skeleton demo")
    parser.add_argument("--size", default="8x10", metavar="WxH", help="grid size (default 8x10)")
    parser.add_argument("--seed", type=int, default=None, metavar="N", help="RNG seed for procedural generation")
    parser.add_argument("--watch", type=int, default=None, metavar="N", help="animate N ticks in the terminal")
    parser.add_argument("--headless", action="store_true", help="suppress animation, print one-line summary (use with --watch)")
    parser.add_argument("--fps", type=float, default=5.0, metavar="F", help="animation speed in frames per second (default 5)")
    args = parser.parse_args(argv)

    if args.demo:
        from demo import run_demo
        run_demo()
        return

    # Build initial state: use the procedural generator when --seed or non-default --size.
    width, height = _parse_size(args.size)
    use_generator = args.seed is not None or (width, height) != (8, 10)

    if use_generator:
        from sim import generate
        seed = args.seed if args.seed is not None else 0
        state = generate(width, height, seed)
    else:
        from sim import default_state
        state = default_state()

    if args.watch is not None:
        from ui.watch import run_watch
        run_watch(state, args.watch, headless=args.headless, fps=args.fps)
        return

    from ui.app import AntFarmApp
    AntFarmApp(state=state).run()


if __name__ == "__main__":
    main()
