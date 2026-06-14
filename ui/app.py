"""The Textual TUI: a tank you LOOK at and a command line you TYPE at.

Two focus zones embody "looking vs doing":

* the **tank** (the grid + the resident roster) — looking. Arrow keys drive a
  grid cursor, the roster navigates, ``m`` cycles the metric; typing does
  nothing here.
* the **command input** — doing. Normal text entry for gestures and knob
  commands, routed through :func:`router.take_turn` exactly as before.

Default focus is the tank, so the game opens ready to be explored. Tab cycles
focus (grid → roster → input → grid); Esc jumps straight back to the tank.

Selection (a room, a resident, or nothing) is **UI-local** — it never touches
the sim or the save file. The detail panel reads catalog cards (as data, via
:mod:`ui.catalog`) and the grid highlights the selection spatially.

Every command is registered with Textual's command palette (Ctrl+P) for
fuzzy-search discoverability.

Key bindings:
* Arrows  — move the grid cursor (when the tank is focused)
* m       — cycle the active metric (residents recolour)
* Tab     — move focus between tank zones and the input
* Esc     — focus the tank (look)
* Enter   — submit the command in the input line
* Ctrl+P  — command palette
* Ctrl+S / Ctrl+O / Ctrl+Q — save / load / quit
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from textual.app import App, ComposeResult, SystemCommand
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, OptionList, RichLog, Static
from textual.widgets.option_list import Option

from rich.text import Text

from router import take_turn
from sim import GameState, default_state, load, save, tick
from ui.inspect import (
    Selection,
    highlight_cells,
    next_metric,
    resident_by_id,
    selection_at,
)
from ui.palette import metric_value, resident_style
from ui.render import render_detail, render_grid, render_stats

SAVE_PATH = Path("ant_farm_save.json")


class TankGrid(Static, can_focus=True):
    """The grid panel — focusable so it can own the inspection cursor.

    It carries no logic of its own: arrow keys and clicks are forwarded to the
    app, which holds the cursor and selection. Keys other than the arrows (``m``,
    Tab, Esc) bubble up to the app's bindings.
    """

    _MOVES = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}

    def on_key(self, event) -> None:
        move = self._MOVES.get(event.key)
        if move is not None:
            event.stop()
            event.prevent_default()
            self.app.move_cursor(*move)  # type: ignore[attr-defined]

    def on_click(self, event) -> None:
        region = self.content_region
        row = event.screen_y - region.y
        col = event.screen_x - region.x
        self.focus()
        self.app.select_cell(row, col)  # type: ignore[attr-defined]


class AntFarmApp(App[None]):
    """The ASCII Ant Farm terminal app."""

    TITLE = "ASCII Ant Farm"
    SUB_TITLE = "look · type · inspect"

    CSS = """
    Screen { layout: vertical; }

    #panels { height: 1fr; }

    #grid {
        border: round $accent;
        padding: 0 1;
    }
    #grid:focus { border: round $warning; }

    #side { width: 38; }

    #stats {
        border: round $secondary;
        padding: 0 1;
        height: auto;
    }

    #residents {
        border: round $secondary;
        height: 1fr;
    }
    #residents:focus { border: round $warning; }

    #detail {
        border: round $success;
        padding: 0 1;
        height: auto;
        min-height: 9;
    }

    #log {
        width: 1fr;
        border: round $primary;
        padding: 0 1;
    }

    #cmd { dock: bottom; }
    """

    BINDINGS = [
        ("m", "cycle_metric", "Metric"),
        ("escape", "focus_tank", "Look"),
        ("ctrl+s", "save", "Save"),
        ("ctrl+o", "load", "Load"),
        ("ctrl+q", "quit", "Quit"),
    ]

    def __init__(self, state: GameState | None = None) -> None:
        super().__init__()
        self.state: GameState = state if state is not None else default_state()
        # View-local inspection state — never serialized into the colony.
        self.selection: Selection | None = None
        self.cursor: tuple[int, int] = self._default_cursor()
        self._mute_list = False  # suppress roster echo while syncing it

    # ------------------------------------------------------------------ #
    # Composition
    # ------------------------------------------------------------------ #

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="panels"):
            yield TankGrid(id="grid")
            with Vertical(id="side"):
                yield Static(id="stats")
                yield OptionList(id="residents")
                yield Static(id="detail")
            yield RichLog(id="log", wrap=True, markup=True, highlight=False)
        yield Input(
            placeholder="feed 5  |  light 80  |  metric mood  |  or type a sentence…",
            id="cmd",
        )
        yield Footer()

    def on_mount(self) -> None:
        self._size_panels()
        # Keep the log out of the Tab cycle: focus moves tank → roster → input.
        self.query_one("#log", RichLog).can_focus = False
        self._rebuild_residents()
        self._refresh_views()
        log = self.query_one("#log", RichLog)
        for event in self.state.event_log:
            log.write(event)
        log.write("[dim]Tank focused — arrow-keys to look, Tab to type, Ctrl+P for commands.[/dim]")
        # Default focus is the tank: open ready to explore, not to type.
        self.query_one("#grid", TankGrid).focus()

    def _default_cursor(self) -> tuple[int, int]:
        for r in self.state.residents:
            if r.row is not None and r.col is not None:
                return (r.row, r.col)
        return (self.state.depth // 2, self.state.width // 2)

    def _size_panels(self) -> None:
        # Grid box = grid chars + 2 padding + 2 border.
        self.query_one("#grid", TankGrid).styles.width = self.state.width + 4

    # ------------------------------------------------------------------ #
    # Command palette (Ctrl+P) — every command, fuzzy-searchable
    # ------------------------------------------------------------------ #

    def colony_commands(self) -> list[SystemCommand]:
        """The colony's palette commands. Exposed for discoverability + tests."""
        return [
            SystemCommand("Feed colony", "feed N — set the food stock (0–9)",
                          lambda: self._prefill("feed ")),
            SystemCommand("Set light", "light N — set the power level (0–100)",
                          lambda: self._prefill("light ")),
            SystemCommand("Set metric", "metric NAME — choose the watched metric",
                          lambda: self._prefill("metric ")),
            SystemCommand("Cycle metric", "Recolour residents by the next metric (m)",
                          self.action_cycle_metric),
            SystemCommand("Watch (advance ticks)", "Advance the colony 20 ticks, animated in place",
                          self.action_watch),
            SystemCommand("Select next resident", "Highlight the next resident in the roster",
                          self.action_select_next),
            SystemCommand("Select previous resident", "Highlight the previous resident",
                          self.action_select_prev),
            SystemCommand("Clear selection", "Deselect any room or resident",
                          self.action_clear_selection),
            SystemCommand("Focus tank (look)", "Move focus to the tank for inspection",
                          self.action_focus_tank),
            SystemCommand("Focus command line (type)", "Move focus to the input to type",
                          self.action_focus_input),
            SystemCommand("Save colony", "Write the colony to disk", self.action_save),
            SystemCommand("Load colony", "Read the colony back from disk", self.action_load),
            SystemCommand("Quit", "Exit ASCII Ant Farm", self.action_quit),
        ]

    def get_system_commands(self, screen: Screen) -> Iterable[SystemCommand]:
        yield from super().get_system_commands(screen)
        yield from self.colony_commands()

    # ------------------------------------------------------------------ #
    # Selection (UI-local)
    # ------------------------------------------------------------------ #

    def move_cursor(self, dr: int, dc: int) -> None:
        row = max(0, min(self.state.depth - 1, self.cursor[0] + dr))
        col = max(0, min(self.state.width - 1, self.cursor[1] + dc))
        self.cursor = (row, col)
        self.selection = selection_at(self.state, row, col)
        self._sync_list_to_selection()
        self._refresh_views()

    def select_cell(self, row: int, col: int) -> None:
        if 0 <= row < self.state.depth and 0 <= col < self.state.width:
            self.cursor = (row, col)
            self.selection = selection_at(self.state, row, col)
            self._sync_list_to_selection()
            self._refresh_views()

    def select_resident_id(self, rid: str) -> None:
        """Select a resident by id (from the roster). Moves the cursor to it."""
        r = resident_by_id(self.state, rid)
        self.selection = Selection("resident", rid) if r is not None else None
        if r is not None and r.row is not None and r.col is not None:
            self.cursor = (r.row, r.col)
        self._refresh_views()

    def _sync_list_to_selection(self) -> None:
        """Mirror a resident selection into the roster highlight (no echo)."""
        ol = self.query_one("#residents", OptionList)
        if self.selection is not None and self.selection.kind == "resident":
            idx = self._resident_index(self.selection.id)
            if idx is not None and ol.highlighted != idx:
                ol.highlighted = idx  # equality-guarded in the echo handler
        elif ol.highlighted is not None:
            self._mute_list = True
            ol.highlighted = None
            self._mute_list = False

    def _resident_index(self, rid: str) -> int | None:
        for i, r in enumerate(self.state.residents):
            if r.id == rid:
                return i
        return None

    # ------- roster (OptionList) events ------------------------------- #

    def on_option_list_option_highlighted(
        self, event: OptionList.OptionHighlighted
    ) -> None:
        self._roster_pick(event.option.id)

    def on_option_list_option_selected(
        self, event: OptionList.OptionSelected
    ) -> None:
        self._roster_pick(event.option.id)

    def _roster_pick(self, oid: str | None) -> None:
        if self._mute_list or oid is None:
            return
        if (
            self.selection is not None
            and self.selection.kind == "resident"
            and self.selection.id == oid
        ):
            return
        self.select_resident_id(oid)

    # ------------------------------------------------------------------ #
    # Hotkey / palette actions
    # ------------------------------------------------------------------ #

    def action_cycle_metric(self) -> None:
        # The active metric is a view selector; cycle it without ticking.
        self.state.metric = next_metric(self.state.metric)
        self._rebuild_residents()
        self._refresh_views()

    def action_focus_tank(self) -> None:
        self.query_one("#grid", TankGrid).focus()

    def action_focus_input(self) -> None:
        self.query_one("#cmd", Input).focus()

    def action_clear_selection(self) -> None:
        self.selection = None
        self._sync_list_to_selection()
        self._refresh_views()

    def action_select_next(self) -> None:
        self._step_roster(1)

    def action_select_prev(self) -> None:
        self._step_roster(-1)

    def _step_roster(self, delta: int) -> None:
        ol = self.query_one("#residents", OptionList)
        n = ol.option_count
        if not n:
            return
        cur = ol.highlighted if ol.highlighted is not None else (-1 if delta > 0 else 0)
        ol.highlighted = (cur + delta) % n  # fires the echo handler → selects

    def action_watch(self, n: int = 20) -> None:
        """Advance the colony N ticks, animated in place (no LLM, empty actions)."""
        if getattr(self, "_watching", False):
            return
        self._watching = True
        self._watch_left = n
        self._log(f"[green]watch {n} ticks…[/green]")
        self._watch_timer = self.set_interval(0.2, self._watch_step)

    def _watch_step(self) -> None:
        if self._watch_left <= 0:
            self._watching = False
            self._watch_timer.stop()
            self._log(f"[green]watch done → turn {self.state.turn}[/green]")
            return
        self.state = tick(self.state, [])
        self._watch_left -= 1
        self._after_state_change()

    # ------------------------------------------------------------------ #
    # Typed line (unchanged routing)
    # ------------------------------------------------------------------ #

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

        self._after_state_change()

    # ------------------------------------------------------------------ #
    # Save / load
    # ------------------------------------------------------------------ #

    def action_save(self) -> None:
        save(self.state, SAVE_PATH)
        self._log(f"[green]saved → {SAVE_PATH}[/green]")

    def action_load(self) -> None:
        if not SAVE_PATH.exists():
            self._log(f"[red]no save at {SAVE_PATH}[/red]")
            return
        self.state = load(SAVE_PATH)
        self.selection = None
        self.cursor = self._default_cursor()
        self._size_panels()
        self._rebuild_residents()
        self._refresh_views()
        self._log(f"[green]loaded ← {SAVE_PATH}[/green]")

    # ------------------------------------------------------------------ #
    # Rendering
    # ------------------------------------------------------------------ #

    def _after_state_change(self) -> None:
        """Resync views after the colony advanced (turn or watch tick)."""
        self._rebuild_residents()
        # Follow the selected resident as it wanders, so the highlight tracks it.
        if self.selection is not None and self.selection.kind == "resident":
            r = resident_by_id(self.state, self.selection.id)
            if r is not None and r.row is not None and r.col is not None:
                self.cursor = (r.row, r.col)
        self._refresh_views()

    def _refresh_views(self) -> None:
        hl = highlight_cells(self.state, self.selection)
        self.query_one("#grid", TankGrid).update(
            render_grid(self.state, cursor=self.cursor, highlight=hl)
        )
        self.query_one("#stats", Static).update(render_stats(self.state))
        self.query_one("#detail", Static).update(
            render_detail(self.state, self.selection)
        )

    def _rebuild_residents(self) -> None:
        ol = self.query_one("#residents", OptionList)
        self._mute_list = True
        ol.clear_options()
        for r in self.state.residents:
            ol.add_option(Option(self._roster_line(r), id=r.id))
        # Restore the highlight to the current selection (echo is equality-guarded).
        if self.selection is not None and self.selection.kind == "resident":
            idx = self._resident_index(self.selection.id)
            if idx is not None:
                ol.highlighted = idx
        self._mute_list = False

    def _roster_line(self, r) -> Text:
        line = Text(no_wrap=True)
        line.append(r.id, resident_style(metric_value(self.state, r)))
        line.append(f"  {r.archetype}")
        return line

    def _log(self, message: str) -> None:
        self.query_one("#log", RichLog).write(message)
