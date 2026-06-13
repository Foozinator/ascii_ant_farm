"""Entry point for ASCII Ant Farm.

* ``python main.py``        — launch the Textual TUI
* ``python main.py --demo`` — run the headless walking-skeleton demo

A local ``.env`` (if present) is loaded here so the VS Code ▶ Run button — which
does NOT apply ``python.envFile`` — still picks up the ``LLM_*`` / ``OLLAMA_*``
settings. Variables already set in the real environment (shell, launch.json) are
never overridden.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _load_dotenv(filename: str = ".env") -> None:
    """Minimal ``.env`` loader: ``KEY=VALUE`` lines, ``#`` comments.

    Intentionally does not override variables already present in the environment,
    so an explicit shell value or a launch.json ``env`` always wins.
    """
    path = Path(__file__).resolve().parent / filename
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv

    _load_dotenv()

    # Report which engine we're about to use (and whether it's actually reachable)
    # before the TUI takes over the screen.
    import llm

    _ok, message = llm.check_backend()
    print(f"[ascii-ant-farm] {message}", file=sys.stderr)

    if "--demo" in argv:
        from demo import run_demo

        run_demo()
        return

    from ui.app import AntFarmApp

    AntFarmApp(init_message=message).run()


if __name__ == "__main__":
    main()
