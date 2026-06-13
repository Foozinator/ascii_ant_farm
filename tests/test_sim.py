"""Sim engine: tick semantics and JSON serialization round-trips."""

from __future__ import annotations

from contract import Effect, EffectType
from sim import default_state, from_json, load, save, tick, to_json


def test_tick_is_pure_and_advances():
    s = default_state()
    s2 = tick(s, [])
    assert s2.turn == s.turn + 1
    assert s2.food < s.food          # the step consumes food
    assert s.turn == 0               # original state left untouched


def test_feed_effect_sets_food_then_step_consumes():
    s = default_state()
    s2 = tick(s, [Effect(type=EffectType.FEED, target="food", magnitude=9)])
    assert s2.food == 8.5            # set to 9, then 0.5 consumed


def test_event_log_trims_to_max():
    s = default_state()
    for _ in range(30):
        s = tick(s, [])
    assert len(s.event_log) <= 10


def test_json_string_round_trip():
    s = tick(default_state(), [Effect(type=EffectType.LIGHT, target="power", magnitude=80)])
    assert from_json(to_json(s)) == s


def test_save_load_round_trip(tmp_path):
    s = default_state()
    path = tmp_path / "save.json"
    save(s, path)
    assert load(path) == s
