"""Required test (a): the deterministic grammar gate and its routing.

Covers that knob commands match and build the right effect, that near-misses
fall through, and crucially that the knob path NEVER touches the llm parser
while a free sentence does.
"""

from __future__ import annotations

import pytest

from contract import Effect, EffectType
from router import match_grammar, take_turn
from sim import default_state


def test_feed_matches_and_builds_effect():
    assert match_grammar("feed 5") == Effect(
        type=EffectType.FEED, target="food", magnitude=5.0
    )


def test_light_matches_and_builds_effect():
    eff = match_grammar("light 80")
    assert eff is not None
    assert eff.type is EffectType.LIGHT
    assert eff.magnitude == 80.0


def test_metric_matches_and_builds_effect():
    eff = match_grammar("metric mood")
    assert eff is not None
    assert eff.type is EffectType.METRIC
    assert eff.target == "mood"


def test_grammar_trims_and_is_case_insensitive():
    assert match_grammar("  FEED 3  ") is not None


@pytest.mark.parametrize(
    "text",
    [
        "feed 12",                          # not a single 0-9 digit
        "light 250",                        # over 100
        "metric",                           # missing argument
        "tap the glass over the offices",   # a free sentence
        "",                                 # empty
    ],
)
def test_grammar_misses_fall_through(text):
    assert match_grammar(text) is None


def test_knob_path_does_not_call_the_parser():
    """The headline of the success criterion: `feed 5` skips the stub parser."""
    state = default_state()

    def exploding_parse(sentence, st):  # must never run on the knob path
        raise AssertionError("llm.parse must not be called on the knob path")

    new_state, result = take_turn(state, "feed 5", parse=exploding_parse)

    assert result.path == "knob"
    assert new_state.food == 4.5  # set to 5, then 0.5 consumed by the step
    assert new_state.turn == state.turn + 1
    # The digest still runs on the knob path, so a report comes back.
    assert result.report.prose


def test_gesture_path_calls_the_parser_once():
    state = default_state()
    seen: list[str] = []

    def spy_parse(sentence, st):
        import llm

        seen.append(sentence)
        return llm.parse(sentence, st)

    new_state, result = take_turn(
        state, "tap the glass over the offices", parse=spy_parse
    )

    assert result.path == "gesture"
    assert seen == ["tap the glass over the offices"]
    assert new_state.turn == state.turn + 1
    assert result.effects  # the stub produced a gesture effect that survived
