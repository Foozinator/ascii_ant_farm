"""The turn router — the composition root that wires the seam end to end.

This is the only module that imports all three sides (``sim``, ``llm``, and the
``contract``); ``sim`` and ``llm`` stay isolated from each other and meet only
here. The UI calls :func:`take_turn` once per player input and renders whatever
comes back. Keeping the orchestration here (not in the Textual app) means the
whole turn loop is testable without a terminal.

The turn loop, exactly as wired:

1. The player's raw text arrives.
2. :func:`match_grammar` — the deterministic command gate. If the text matches a
   fixed knob grammar (``feed <0-9>``, ``light <0-100>``, ``metric <name>``) we
   build the :class:`Effect` directly. The llm parser is **not** called.
3. On a grammar miss, the sentence goes to ``llm.parse`` (stubbed).
4. :func:`validate_envelope` re-validates the returned envelope at the seam. On
   failure the effects are **dropped** but the prose is kept as flavor text.
5. ``sim.tick`` applies the validated effects and advances one step.
6. ``llm.digest`` (stubbed) returns a report, re-validated by
   :func:`validate_report` the same way.
7. The UI re-renders and appends the report.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

from pydantic import ValidationError

import llm
from contract import ColonyReport, Effect, EffectEnvelope, EffectType
from sim import GameState, tick

# Shown when a parsed envelope fails validation and carried no salvageable prose.
FALLBACK_PROSE = "(The colony stirs, but the gesture doesn't quite translate.)"

# Shown when a digest fails validation entirely.
FALLBACK_REPORT_PROSE = "(The colony's report came back garbled.)"


# --------------------------------------------------------------------------- #
# Step 2: the deterministic command grammar (the knob gate)
# --------------------------------------------------------------------------- #

def _build_feed(m: re.Match[str]) -> Effect:
    return Effect(type=EffectType.FEED, target="food", magnitude=float(m.group(1)))


def _build_light(m: re.Match[str]) -> Effect:
    return Effect(type=EffectType.LIGHT, target="power", magnitude=float(m.group(1)))


def _build_metric(m: re.Match[str]) -> Effect:
    return Effect(type=EffectType.METRIC, target=m.group(1).lower(), magnitude=0.0)


# Ordered (pattern, builder) pairs. Patterns are anchored and case-insensitive.
# `feed` takes a single digit 0-9; `light` takes 0-100; `metric` takes a word.
_GRAMMAR: list[tuple[re.Pattern[str], Callable[[re.Match[str]], Effect]]] = [
    (re.compile(r"^feed\s+([0-9])$", re.IGNORECASE), _build_feed),
    (re.compile(r"^light\s+(100|[0-9]{1,2})$", re.IGNORECASE), _build_light),
    (re.compile(r"^metric\s+([A-Za-z_]+)$", re.IGNORECASE), _build_metric),
]


def match_grammar(text: str) -> Effect | None:
    """Return a knob :class:`Effect` if ``text`` matches the grammar, else None.

    A ``None`` result is the signal to fall through to the llm parse path. This
    function is pure and side-effect free — it never touches the model.
    """
    text = text.strip()
    for pattern, builder in _GRAMMAR:
        match = pattern.match(text)
        if match is not None:
            return builder(match)
    return None


# --------------------------------------------------------------------------- #
# Step 4 & 6: seam validation with graceful fallback
# --------------------------------------------------------------------------- #

def _salvage_prose(raw: object, fallback: str) -> str:
    """Pull a usable prose string off a payload that failed validation."""
    candidate: object = None
    if isinstance(raw, dict):
        candidate = raw.get("prose")
    else:
        candidate = getattr(raw, "prose", None)
    return candidate if isinstance(candidate, str) and candidate else fallback


def validate_envelope(raw: object) -> tuple[list[Effect], str]:
    """Validate an inbound envelope; return ``(effects, prose)``.

    On success, the validated effects and prose. On a validation failure the
    effects are dropped (returned empty) but the prose is salvaged if present so
    the player still gets flavor text. This is the fallback the spec requires —
    exercised by the tests even though the stub always returns valid data.
    """
    try:
        envelope = EffectEnvelope.model_validate(raw)
    except ValidationError:
        return [], _salvage_prose(raw, FALLBACK_PROSE)
    return list(envelope.effects), envelope.prose


def validate_report(raw: object) -> ColonyReport:
    """Validate an outbound digest; on failure return a minimal valid report."""
    try:
        return ColonyReport.model_validate(raw)
    except ValidationError:
        return ColonyReport(prose=_salvage_prose(raw, FALLBACK_REPORT_PROSE))


# --------------------------------------------------------------------------- #
# The turn
# --------------------------------------------------------------------------- #

@dataclass
class TurnResult:
    """Everything the UI needs to render the outcome of one turn."""

    path: str                       # "knob" or "gesture"
    prose: str                      # player-intent flavor ("" on the knob path)
    report: ColonyReport            # the colony's narrated response
    effects: list[Effect] = field(default_factory=list)  # what was applied
    envelope_dropped: bool = False  # True if validation dropped parsed effects


def take_turn(
    state: GameState,
    text: str,
    *,
    parse: Callable[[str, GameState], object] = llm.parse,
    digest: Callable[[GameState, list[str]], object] = llm.digest,
) -> tuple[GameState, TurnResult]:
    """Run one full turn and return ``(new_state, result)``.

    ``parse`` and ``digest`` are injectable so tests can substitute spies or
    fakes; by default they are the real (stubbed) llm interfaces.
    """
    text = text.strip()

    knob = match_grammar(text)
    if knob is not None:
        # Knob path: deterministic, instant. The llm parser is never called.
        effects: list[Effect] = [knob]
        prose = ""
        path = "knob"
        dropped = False
    else:
        # Gesture path: cross the seam to the parser, then validate.
        raw_envelope = parse(text, state)
        effects, prose = validate_envelope(raw_envelope)
        path = "gesture"
        # We dropped effects iff the raw payload meant to carry some but none survived.
        dropped = not effects and _intended_effects(raw_envelope)

    new_state = tick(state, effects)

    raw_report = digest(new_state, new_state.last_events)
    report = validate_report(raw_report)

    result = TurnResult(
        path=path,
        prose=prose,
        report=report,
        effects=effects,
        envelope_dropped=dropped,
    )
    return new_state, result


def _intended_effects(raw: object) -> bool:
    """Best-effort: did the raw envelope try to carry effects at all?"""
    if isinstance(raw, dict):
        eff = raw.get("effects")
    else:
        eff = getattr(raw, "effects", None)
    return bool(eff)
