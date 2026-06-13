"""The two LLM backends behind the same interface.

* :class:`StubBackend` — deterministic, offline, no model. Behaves like the
  walking-skeleton stubs so CI, the sim agent, and offline runs never need a
  live model.
* :class:`OllamaBackend` — the first real version. Talks to Ollama via the
  official client at a configurable host, constrains generation to the contract's
  JSON schema (derived from the Pydantic models), and validates the result.

Both implement :class:`Backend`; ``LLM_BACKEND`` selects which one is active
(see :mod:`llm.runtime`). Neither imports ``sim`` — state is read through the
structural :class:`~llm.views.StateView`.

Fallback discipline (both methods, both backends): a malformed/empty/erroring
model response degrades to a SAFE value (empty effects with prose preserved, or a
generic report) and NEVER raises into the turn loop.
"""

from __future__ import annotations

import json
from typing import Any, Protocol, runtime_checkable

from pydantic import ValidationError

from contract import ColonyReport, Effect, EffectEnvelope, EffectType
from llm.config import LLMConfig
from llm.personas import PersonaCard, get_catalog
from llm.prompts import build_digest_messages, build_parse_messages
from llm.views import StateView

# Narration used when a digest can't be produced or salvaged.
GENERIC_DIGEST_PROSE = (
    "The colony goes about its work in the dark — unremarkable, and alive."
)


@runtime_checkable
class Backend(Protocol):
    """The interface both backends satisfy and the turn loop depends on."""

    def parse(self, sentence: str, state: StateView) -> EffectEnvelope: ...

    def digest(self, state: StateView, new_events: list[str]) -> ColonyReport: ...


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #

def _select_voiced(
    state: StateView, voices: int
) -> list[tuple[Any, PersonaCard]]:
    """Pair the first ``voices`` residents with their persona cards.

    "Who speaks" is intentionally just the first N residents handed to us —
    distribution-based selection is sim-side logic and is NOT done here.
    """
    catalog = get_catalog()
    chosen = list(state.residents)[: max(0, voices)]
    return [(r, catalog.card_for(r.archetype)) for r in chosen]


def _salvage_prose(content: str) -> str:
    """Best-effort: pull a "prose" string out of partially-valid JSON."""
    try:
        data = json.loads(content)
    except (ValueError, TypeError):
        return ""
    if isinstance(data, dict):
        prose = data.get("prose")
        if isinstance(prose, str):
            return prose
    return ""


def coerce_envelope(content: str) -> EffectEnvelope:
    """Validate model output into an EffectEnvelope; degrade safely on failure.

    On a clean parse, the full envelope. On a validation failure, the effects are
    dropped but any salvageable prose is preserved. On non-JSON/empty, an empty
    envelope. Never raises.
    """
    if not content or not content.strip():
        return EffectEnvelope()
    try:
        return EffectEnvelope.model_validate_json(content)
    except ValidationError:
        return EffectEnvelope(prose=_salvage_prose(content))


def coerce_report(content: str) -> ColonyReport:
    """Validate model output into a ColonyReport; degrade safely on failure."""
    if not content or not content.strip():
        return ColonyReport(prose=GENERIC_DIGEST_PROSE)
    try:
        return ColonyReport.model_validate_json(content)
    except ValidationError:
        salvaged = _salvage_prose(content)
        return ColonyReport(prose=salvaged or GENERIC_DIGEST_PROSE)


# --------------------------------------------------------------------------- #
# Stub backend (offline, deterministic)
# --------------------------------------------------------------------------- #

# Keyword buckets the stub uses to fake interpretation, mirroring the skeleton.
_HARSH = ("tap", "bang", "knock", "shake", "flood", "poke", "rattle")
_KIND = ("calm", "soothe", "sing", "warm", "praise", "comfort")
_ROOM_WORDS = ("offices", "nursery", "pantry")


def _guess_target(sentence: str) -> str:
    low = sentence.lower()
    for room in _ROOM_WORDS:
        if room in low or room.rstrip("s") in low:
            return room
    return "colony"


def _guess_magnitude(sentence: str) -> float:
    low = sentence.lower()
    if any(w in low for w in _HARSH):
        return -0.10
    if any(w in low for w in _KIND):
        return 0.08
    return -0.03


class StubBackend:
    """Canned, deterministic backend — the skeleton behavior, kept selectable."""

    def __init__(self, config: LLMConfig | None = None) -> None:
        self._config = config or LLMConfig()

    def parse(self, sentence: str, state: StateView) -> EffectEnvelope:
        del state  # unused by the stub; part of the real signature
        target = _guess_target(sentence)
        magnitude = _guess_magnitude(sentence)
        prose = f"You {sentence.strip().rstrip('.')}. The colony registers it."
        return EffectEnvelope(
            prose=prose,
            effects=[Effect(type=EffectType.GESTURE, target=target, magnitude=magnitude)],
        )

    def digest(self, state: StateView, new_events: list[str]) -> ColonyReport:
        flags: list[str] = []
        if state.food < 2.0:
            flags.append("hunger")
        if state.power < 10.0:
            flags.append("brownout")

        # TODO(coordination): mood_deltas here are canned placeholders, not
        # derived from the sim's tick — exactly the contradiction flagged for the
        # real path. Agreed direction: mood numbers come from sim.tick; the model
        # owns prose (+ soft flags). Move mood_deltas sim-side.
        base = -0.05 if flags else 0.02
        mood_deltas = {r.id: round(base, 3) for r in state.residents}

        headline = "; ".join(new_events) if new_events else "A quiet shift passes."
        prose = f"[Colony digest - turn {state.turn}] {headline} The ants carry on."
        return ColonyReport(prose=prose, mood_deltas=mood_deltas, flags=flags)


# --------------------------------------------------------------------------- #
# Ollama backend (the first real version)
# --------------------------------------------------------------------------- #

def _extract_content(response: Any) -> str:
    """Pull message content from an ollama response (object OR dict, robustly)."""
    message = getattr(response, "message", None)
    if message is None and isinstance(response, dict):
        message = response.get("message")
    if message is None:
        return ""
    content = getattr(message, "content", None)
    if content is None and isinstance(message, dict):
        content = message.get("content")
    return content or ""


class OllamaBackend:
    """Real backend: schema-constrained generation via the Ollama client.

    The ``ollama`` package is imported lazily (only when a default client is
    needed) so importing this module — and selecting this backend — never
    requires the package to be installed. Tests inject a fake client instead.
    """

    def __init__(self, config: LLMConfig, client: Any | None = None) -> None:
        self._config = config
        self._client = client

    @property
    def client(self) -> Any:
        if self._client is None:
            import ollama  # lazy: only needed for a live call

            self._client = ollama.Client(host=self._config.base_url)
        return self._client

    def _chat(self, messages: list[dict[str, str]], schema: dict, temperature: float) -> str:
        # `format=<json schema>` constrains generation to a valid object — this is
        # what stops reasoning/preamble leaks and out-of-enum values at the source.
        response = self.client.chat(
            model=self._config.model,
            messages=messages,
            format=schema,
            options={"temperature": temperature},
        )
        return _extract_content(response)

    def parse(self, sentence: str, state: StateView) -> EffectEnvelope:
        schema = EffectEnvelope.model_json_schema()
        messages = build_parse_messages(state, sentence)
        try:
            content = self._chat(messages, schema, self._config.parse_temperature)
        except Exception:  # connection/runtime errors must not reach the turn loop
            return EffectEnvelope()
        return coerce_envelope(content)

    def digest(self, state: StateView, new_events: list[str]) -> ColonyReport:
        voiced = _select_voiced(state, self._config.digest_voices)
        schema = ColonyReport.model_json_schema()
        messages = build_digest_messages(state, new_events, voiced)
        try:
            content = self._chat(messages, schema, self._config.digest_temperature)
        except Exception:
            return ColonyReport(prose=GENERIC_DIGEST_PROSE)
        # TODO(coordination): the model currently fills mood_deltas (model-invented
        # and able to contradict the deterministic tick). Agreed direction: mood
        # numbers should come from sim.tick and the model should own prose + soft
        # flags only. Stop trusting model mood_deltas once the sim populates them.
        return coerce_report(content)
