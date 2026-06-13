"""Prompt construction for the Ollama backend.

Pure string-building from the read-only :class:`~llm.views.StateView` plus the
persona cards. No model calls, no ``sim`` imports — easy to eyeball and test.
"""

from __future__ import annotations

from llm.personas import PersonaCard
from llm.views import StateView

PARSE_SYSTEM = """\
You are the interpreter for ASCII Ant Farm, a small terminal ant-colony toy. The \
player types free-form gestures or remarks aimed at the colony. Translate the \
player's intent into structured game effects.

Respond with a single JSON object matching the required schema (an EffectEnvelope):
  - "prose": one short sentence, neutral narrator voice, acknowledging what the \
player did. No preamble, no reasoning, no JSON talk.
  - "effects": a list of zero or more effects. Each effect has:
      type: one of "feed", "light", "metric", "gesture".
      target: for "gesture", the room or area touched ("offices", "nursery", \
"pantry", or "colony"); for "feed"/"light" the stock name ("food"/"power"); for \
"metric" the metric name.
      magnitude: a number. gesture = a mood nudge in [-0.2, 0.2] (disturbing the \
ants is negative, soothing is positive); feed = 0..9; light = 0..100; metric = 0.

Most remarks map to a single "gesture" effect. Only emit "feed", "light", or \
"metric" if the player clearly asks to set that knob. If nothing actionable is \
implied, return an empty effects list but still acknowledge it in prose.\
"""

DIGEST_SYSTEM = """\
You are the colony's narrator for ASCII Ant Farm. After each step you report what \
the colony is doing, in the VOICES of the named residents. Stay in character: \
match each resident's given voice sample in tone, vocabulary, and attitude.

Respond with a single JSON object matching the required schema (a ColonyReport):
  - "prose": 2 to 4 vivid, present-tense sentences of narration that let the \
residents' personalities show. React to what happened this step and to the \
colony's condition. No preamble, no meta commentary, no JSON talk.
  - "flags": a short list of soft, aggregate signals as lowercase tags (e.g. \
"content", "restless", "hungry", "anxious"). Omit if nothing stands out.
  - "mood_deltas": optional small per-resident mood hints keyed by resident id.

Flat, generic narration is a failure. Be specific and characterful.\
"""


def state_digest(state: StateView) -> str:
    """A compact, human-readable snapshot of the colony for the prompt."""
    lines = [
        f"Turn {state.turn}.",
        f"Food stock: {state.food:.1f} of 9.  Power: {state.power:.0f} of 100.",
        f"Player is watching the '{state.metric}' metric.",
        "Residents:",
    ]
    for r in state.residents:
        lines.append(f"  - {r.id}: {r.archetype}, mood {r.mood:.2f}")
    return "\n".join(lines)


def build_parse_messages(state: StateView, sentence: str) -> list[dict[str, str]]:
    user = (
        f"Current colony:\n{state_digest(state)}\n\n"
        f'The player makes this gesture or remark: "{sentence.strip()}"\n\n'
        "Translate it into an EffectEnvelope."
    )
    return [
        {"role": "system", "content": PARSE_SYSTEM},
        {"role": "user", "content": user},
    ]


def _persona_block(voiced: list[tuple[object, PersonaCard]]) -> str:
    blocks = []
    for resident, card in voiced:
        traits = f" {card.traits}" if card.traits else ""
        blocks.append(
            f'{resident.id} - "{card.name}" ({card.role or card.id}), '
            f"mood {resident.mood:.2f}.{traits}\n"
            f'  Their voice sounds like: "{card.voice_sample}"'
        )
    return "\n".join(blocks)


def build_digest_messages(
    state: StateView,
    new_events: list[str],
    voiced: list[tuple[object, PersonaCard]],
) -> list[dict[str, str]]:
    events = (
        "\n".join(f"- {e}" for e in new_events)
        if new_events
        else "- (a quiet, uneventful step)"
    )
    personas = (
        _persona_block(voiced)
        if voiced
        else "(no named residents; use a generic worker voice)"
    )
    user = (
        f"Current colony:\n{state_digest(state)}\n\n"
        f"What happened this step:\n{events}\n\n"
        f"Voice these residents, staying true to each one:\n{personas}\n\n"
        "Write the ColonyReport now."
    )
    return [
        {"role": "system", "content": DIGEST_SYSTEM},
        {"role": "user", "content": user},
    ]
