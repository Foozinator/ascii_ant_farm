"""Required test (b): the envelope-validation fallback at the seam.

The stub parser always returns valid data, but the drop-effects-keep-prose
fallback must exist for when the (real) model returns something malformed. These
tests exercise it directly and through a full turn with a deliberately bad parser.
"""

from __future__ import annotations

from contract import ColonyReport, EffectType
from router import (
    FALLBACK_PROSE,
    FALLBACK_REPORT_PROSE,
    take_turn,
    validate_envelope,
    validate_report,
)
from sim import default_state


def test_valid_envelope_passes_through():
    raw = {
        "prose": "the colony hums",
        "effects": [{"type": "gesture", "target": "offices", "magnitude": -0.1}],
    }
    effects, prose = validate_envelope(raw)
    assert prose == "the colony hums"
    assert len(effects) == 1
    assert effects[0].type is EffectType.GESTURE


def test_invalid_effect_drops_effects_but_keeps_prose():
    raw = {
        "prose": "kept as flavor",
        "effects": [{"type": "NOT_A_REAL_TYPE", "target": "x", "magnitude": 1.0}],
    }
    effects, prose = validate_envelope(raw)
    assert effects == []              # effects dropped on validation failure
    assert prose == "kept as flavor"  # prose salvaged


def test_malformed_envelope_without_prose_uses_fallback():
    raw = {"effects": "not even a list"}  # no prose, bad effects
    effects, prose = validate_envelope(raw)
    assert effects == []
    assert prose == FALLBACK_PROSE


def test_full_turn_fallback_drops_effects_keeps_prose_and_still_ticks():
    """Integration: a bad parser shouldn't break the turn — it degrades."""
    state = default_state()
    moods_before = [r.mood for r in state.residents]

    def bad_parse(sentence, st):
        # prose present, but the effect carries an invalid type
        return {
            "prose": "you wave at the glass",
            "effects": [{"type": "bogus", "target": "offices", "magnitude": -0.5}],
        }

    new_state, result = take_turn(state, "wave at the glass", parse=bad_parse)

    assert result.path == "gesture"
    assert result.envelope_dropped is True
    assert result.effects == []                      # gesture effect dropped
    assert result.prose == "you wave at the glass"   # prose kept
    assert new_state.turn == state.turn + 1          # the sim still advanced
    # The dropped gesture would have lowered moods; instead only positive natural
    # drift applied, so every mood went UP — proof the bad effect never landed.
    moods_after = [r.mood for r in new_state.residents]
    assert all(a > b for a, b in zip(moods_after, moods_before))
    # A valid report still comes back out the other side.
    assert isinstance(result.report, ColonyReport)


def test_validate_report_falls_back_on_garbage():
    report = validate_report({"mood_deltas": "not a dict"})
    assert isinstance(report, ColonyReport)
    assert report.prose == FALLBACK_REPORT_PROSE
