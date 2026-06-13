# ASCII Ant Farm

*An AI-augmented ant farm simulation in a retro terminal.*

Tend a living colony rendered entirely in your terminal. Drop food, adjust the
conditions, tap on the glass — then watch what the colony does about it. A local
language model drives the colony's behavior, so it develops in ways the
simulation alone never scripted. Equal parts toy, sandbox, and quiet experiment
in what happens when you tend a small world.

Runs entirely on your own machine. No cloud, no accounts, no telemetry.

## Status

Early and experimental — a hobby project, built in the open. Expect rough edges
and missing pieces; the foundations are still going in.

## Requirements

- Python 3.12+
- [Textual](https://textual.textualize.io/) for the terminal interface
- A local [Ollama](https://ollama.com/) model to drive the colony

## Running

This is currently a **walking skeleton**: one complete turn flows end to end
through the real architecture, with the AI parts stubbed (canned responses, no
model calls). It proves the pipe and locks the module boundaries before any game
content goes in.

Setup with [uv](https://docs.astral.sh/uv/) (recommended):

```bash
uv venv
uv pip install -e ".[dev]"

uv run python main.py          # launch the Textual TUI
uv run python main.py --demo   # headless walking-skeleton demo (no terminal UI)
uv run pytest                  # run the tests
```

Or with a plain venv:

```bash
python -m venv .venv
. .venv/Scripts/activate       # Windows;  use .venv/bin/activate on macOS/Linux
pip install -e ".[dev]"
python main.py                 # or: python main.py --demo
pytest
```

Inside the TUI, type into the input line at the bottom:

- `feed 5`, `light 80`, `metric mood` — **knob commands**: a deterministic
  grammar builds an effect directly; the parser is never called.
- any free sentence, e.g. *tap the glass over the offices* — the **gesture
  path**: routed through the (stubbed) parser, validated, applied, and digested.

`Ctrl+S` saves the colony to JSON, `Ctrl+O` reloads it, `Ctrl+Q` quits.

## Architecture

Three modules stay strictly isolated, meeting only at a shared contract — so each
side can be built independently against the stub of the other.

```text
contract.py        the seam: Effect, EffectEnvelope, ColonyReport (Pydantic)
                   imported by both sides; imports neither

sim/               deterministic core — owns ALL state (grid, stocks, residents,
                   event log, metric). tick(state, effects) -> state + JSON
                   save/load.  MUST NOT import llm/.

llm/               the two AI interfaces, both STUBBED:
                     parse(sentence, state)  -> EffectEnvelope
                     digest(state, events)   -> ColonyReport
                   depends only on contract.py (reads state via a structural
                   Protocol); never imports sim/.

router.py          the composition root: the command-grammar gate + the turn
                   loop. The only module that touches all three sides.

ui/                the Textual app: grid panel, log/report panel, input line.
```

The turn loop (`router.take_turn`): player text → grammar gate (knob path builds
an `Effect` directly) or, on a miss, `llm.parse` (gesture path) → **validate the
envelope at the seam** (on failure, drop the effects but keep the prose as flavor)
→ `sim.tick` → `llm.digest` → validate the report → UI re-renders.

`tests/test_isolation.py` enforces the boundaries automatically; `test_router.py`
covers grammar-gate routing and `test_validation.py` covers the validation fallback.

## License

This project is **source-available, not open source**: free to use and modify
for non-commercial purposes, with attribution.

- **Code** is under the
  [PolyForm Noncommercial License 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0/).
  It isn't in GitHub's license picker, so the full text lives in
  [`LICENSE`](./LICENSE).
- **Creative content** — characters, narrative, and other assets — is under
  [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/).

Non-commercial use is welcome. **For any commercial use, please get in touch
first** — open an issue or reach the owner ([@Foozinator](https://github.com/Foozinator)).
Happy to talk.
