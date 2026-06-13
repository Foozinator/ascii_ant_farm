"""The Textual TUI: grid panel, log/report panel, and one input line.

Keyboard-only (no mouse needed). The app owns no game logic — every player
input goes straight to :func:`router.take_turn`, and the app only renders the
state and report that come back. That keeps the UI a thin shell over the seam.

Key bindings:
* Enter       — submit the command in the input line
* Ctrl+S      — save the colony to JSON
* Ctrl+O      — load the colony from JSON
* Ctrl+Q      — quit
"""

from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Input, RichLog, Static

from router import take_turn
from sim import GameState, default_state, load, save
from ui.render import render_grid, render_status

SAVE_PATH = Path("ant_farm_save.json")


class AntFarmApp(App[None]):
    """The ASCII Ant Farm terminal app."""

    TITLE = "ASCII Ant Farm"
    SUB_TITLE = "walking skeleton"

    CSS = """
    Screen { layout: vertical; }

    #panels { height: 1fr; }

    #grid {
        width: 24;
        border: round $accent;
        padding: 0 1;
        content-align: center middle;
    }

    #status {
        width: 38;
        border: round $secondary;
        padding: 0 1;
    }

    #log {
        width: 1fr;
        border: round $primary;
        padding: 0 1;
    }

    #cmd { dock: bottom; }
    """

    BINDINGS = [
        ("ctrl+s", "save", "Save"),
        ("ctrl+o", "load", "Load"),
        ("ctrl+q", "quit", "Quit"),
    ]

    def __init__(self, state: GameState | None = None) -> None:
        super().__init__()
        self.state: GameState = state if state is not None else default_state()

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="panels"):
            yield Static(id="grid")
            yield Static(id="status")
            with Vertical():
                yield RichLog(id="log", wrap=True, markup=True, highlight=False)
        yield Input(
            placeholder="feed 5  |  light 80  |  metric mood  |  or type a sentence…",
            id="cmd",
        )
        yield Footer()

    def on_mount(self) -> None:
        self._render()
        log = self.query_one("#log", RichLog)
        for event in self.state.event_log:
            log.write(event)
        self.query_one("#cmd", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        event.input.value = ""
        if not text:
            return

        self.state, result = take_turn(self.state, text)

        log = self.query_one("#log", RichLog)
        log.write(f"[b]> {text}[/b]  [dim]({result.path})[/dim]")
        if result.envelope_dropped:
            log.write("[yellow]· envelope failed validation — effects dropped[/yellow]")
        if result.prose:
            log.write(result.prose)
        log.write(f"[italic]{result.report.prose}[/italic]")
        if result.report.flags:
            log.write("[red]flags: " + ", ".join(result.report.flags) + "[/red]")

        self._render()

    def _render(self) -> None:
        self.query_one("#grid", Static).update(render_grid(self.state))
        self.query_one("#status", Static).update(render_status(self.state))

    def action_save(self) -> None:
        save(self.state, SAVE_PATH)
        self.query_one("#log", RichLog).write(f"[green]saved → {SAVE_PATH}[/green]")

    def action_load(self) -> None:
        log = self.query_one("#log", RichLog)
        if not SAVE_PATH.exists():
            log.write(f"[red]no save at {SAVE_PATH}[/red]")
            return
        self.state = load(SAVE_PATH)
        self._render()
        log.write(f"[green]loaded ← {SAVE_PATH}[/green]")
