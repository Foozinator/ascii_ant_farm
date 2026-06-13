"""``parse`` — natural language in, an :class:`EffectEnvelope` out. STUBBED.

This is the gesture-path AI interface. When a player types a free sentence that
the deterministic command grammar doesn't recognize, the router hands it here.

The real implementation will prompt a local Ollama model to translate the
sentence into structured effects. For the walking skeleton it returns a *canned
but valid* envelope, derived with a few keyword heuristics so the demo feels
alive — no model, no network. The signature is the contract the real version
must satisfy: ``parse(sentence, state) -> EffectEnvelope``.

Imports only :mod:`contract` and :mod:`llm.views`; never ``sim``.
"""

from __future__ import annotations

from contract import Effect, EffectEnvelope, EffectType
from llm.views import StateView

# Room words the stub recognizes, so "...over the offices" targets the offices.
_ROOM_WORDS = ("offices", "nursery", "pantry")

# Crude sentiment buckets that decide which way a gesture nudges mood.
_HARSH = ("tap", "bang", "knock", "shake", "flood", "poke", "rattle")
_KIND = ("calm", "soothe", "sing", "warm", "praise", "comfort")


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


def parse(sentence: str, state: StateView) -> EffectEnvelope:
    """Translate a free sentence into an :class:`EffectEnvelope` (stub).

    ``state`` is accepted (and typed) to match the real interface — a model
    would condition on the current colony — but the stub does not need it.
    Always returns a valid envelope; the router still re-validates it at the seam.
    """
    del state  # unused by the stub; part of the real signature.

    target = _guess_target(sentence)
    magnitude = _guess_magnitude(sentence)
    prose = f"You {sentence.strip().rstrip('.')}. The colony registers it."
    return EffectEnvelope(
        prose=prose,
        effects=[Effect(type=EffectType.GESTURE, target=target, magnitude=magnitude)],
    )
