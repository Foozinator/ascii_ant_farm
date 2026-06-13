"""Entry point for ASCII Ant Farm.

* ``python main.py``        — launch the Textual TUI
* ``python main.py --demo`` — run the headless walking-skeleton demo
"""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv

    if "--demo" in argv:
        from demo import run_demo

        run_demo()
        return

    from ui.app import AntFarmApp

    AntFarmApp().run()


if __name__ == "__main__":
    main()
