"""LLM module tests — fully offline (no live Ollama required).

The real backend is exercised with a *fake* Ollama client injected into
``OllamaBackend``; the rest goes through the deterministic stub. Together these
cover config, persona mapping, backend selection, the happy path, and — most
importantly — that malformed/empty/erroring responses degrade to safe values
without raising into the turn loop.
"""

from __future__ import annotations

import json

import pytest

import llm
from contract import ColonyReport, Effect, EffectEnvelope, EffectType
from llm.backends import GENERIC_DIGEST_PROSE, OllamaBackend, StubBackend
from llm.config import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    LLMConfig,
    load_config,
)
from llm.personas import load_catalog


# --------------------------------------------------------------------------- #
# Fakes & fixtures
# --------------------------------------------------------------------------- #

class FakeResident:
    def __init__(self, id, mood=0.5, archetype="forager"):
        self.id = id
        self.mood = mood
        self.archetype = archetype


class FakeState:
    """A minimal StateView-compatible object (no sim import needed)."""

    def __init__(self):
        self.food = 4.0
        self.power = 50.0
        self.turn = 7
        self.metric = "mood"
        self.residents = [
            FakeResident("ant-01", 0.6, "forager"),
            FakeResident("ant-02", 0.5, "nurse"),
            FakeResident("ant-03", 0.4, "drone"),
            FakeResident("ant-04", 0.7, "queen"),
        ]


class FakeClient:
    """Stands in for ollama.Client. Records calls; returns canned content."""

    def __init__(self, content="", raises=None):
        self.content = content
        self.raises = raises
        self.calls = []

    def chat(self, model, messages, format=None, options=None):
        self.calls.append(
            {"model": model, "messages": messages, "format": format, "options": options}
        )
        if self.raises is not None:
            raise self.raises
        return {"message": {"content": self.content}}


@pytest.fixture
def state():
    return FakeState()


@pytest.fixture
def ollama_config():
    return LLMConfig(backend="ollama", base_url="http://testhost:11434", model="test-model")


@pytest.fixture(autouse=True)
def _clean_backend():
    """Ensure backend selection state never leaks between tests."""
    llm.reset_backend()
    yield
    llm.reset_backend()


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #

def test_config_defaults_when_env_unset(monkeypatch):
    for key in ("LLM_BACKEND", "OLLAMA_BASE_URL", "OLLAMA_MODEL"):
        monkeypatch.delenv(key, raising=False)
    cfg = load_config()
    assert cfg.backend == "stub"
    assert cfg.base_url == DEFAULT_BASE_URL
    assert cfg.model == DEFAULT_MODEL


def test_config_reads_env_overrides(monkeypatch):
    monkeypatch.setenv("LLM_BACKEND", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://192.168.1.50:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "some-model:latest")
    monkeypatch.setenv("LLM_DIGEST_VOICES", "2")
    cfg = load_config()
    assert cfg.backend == "ollama"
    assert cfg.base_url == "http://192.168.1.50:11434"
    assert cfg.model == "some-model:latest"
    assert cfg.digest_voices == 2


def test_config_bad_backend_falls_back_to_stub(monkeypatch):
    monkeypatch.setenv("LLM_BACKEND", "gpt9000")
    assert load_config().backend == "stub"


# --------------------------------------------------------------------------- #
# Personas
# --------------------------------------------------------------------------- #

def test_persona_catalog_maps_known_and_defaults_unknown():
    catalog = load_catalog()  # the bundled character_seeds.json
    # Known archetype tags resolve to their own cards...
    assert catalog.card_for("forager").id == "forager"
    assert catalog.card_for("QUEEN").id == "queen"  # case-insensitive
    # ...and an unmatched tag falls back to the neutral default card.
    fallback = catalog.card_for("astronaut")
    assert fallback.id == catalog.default.id
    assert fallback.voice_sample  # default still carries a usable voice


# --------------------------------------------------------------------------- #
# Backend selection
# --------------------------------------------------------------------------- #

def test_get_backend_respects_env(monkeypatch):
    monkeypatch.setenv("LLM_BACKEND", "ollama")
    llm.reset_backend()
    assert isinstance(llm.get_backend(), OllamaBackend)

    monkeypatch.setenv("LLM_BACKEND", "stub")
    assert isinstance(llm.get_backend(), StubBackend)  # rebuilds on config change


def test_set_backend_override_wins(state):
    sentinel = StubBackend()
    llm.set_backend(sentinel)
    assert llm.get_backend() is sentinel


# --------------------------------------------------------------------------- #
# Stub backend (offline parity with the skeleton)
# --------------------------------------------------------------------------- #

def test_stub_parse_maps_known_sentence_to_valid_envelope(state):
    """Required: parse maps a known sentence to a valid EffectEnvelope shape."""
    env = StubBackend().parse("tap the glass over the offices", state)
    assert isinstance(env, EffectEnvelope)
    assert len(env.effects) == 1
    eff = env.effects[0]
    assert eff.type is EffectType.GESTURE
    assert eff.target == "offices"
    assert env.prose


def test_stub_digest_returns_report_with_prose(state):
    report = StubBackend().digest(state, ["something happened"])
    assert isinstance(report, ColonyReport)
    assert report.prose


# --------------------------------------------------------------------------- #
# Ollama backend — happy path (fake client returns valid JSON)
# --------------------------------------------------------------------------- #

def test_ollama_parse_valid_response(state, ollama_config):
    valid = EffectEnvelope(
        prose="You rap on the glass; the ants flinch.",
        effects=[Effect(type=EffectType.GESTURE, target="offices", magnitude=-0.1)],
    ).model_dump_json()
    client = FakeClient(content=valid)
    backend = OllamaBackend(ollama_config, client=client)

    env = backend.parse("tap the glass over the offices", state)

    assert isinstance(env, EffectEnvelope)
    assert env.effects[0].type is EffectType.GESTURE
    assert env.effects[0].target == "offices"
    # generation was constrained to the EffectEnvelope schema, low temperature
    call = client.calls[0]
    assert call["model"] == "test-model"
    assert call["format"] == EffectEnvelope.model_json_schema()
    assert call["options"]["temperature"] == ollama_config.parse_temperature


def test_ollama_digest_valid_response(state, ollama_config):
    valid = ColonyReport(
        prose="Rust grumbles about the noise while Vela shushes the brood.",
        flags=["restless"],
    ).model_dump_json()
    client = FakeClient(content=valid)
    backend = OllamaBackend(ollama_config, client=client)

    report = backend.digest(state, ["A gesture rattles the colony."])

    assert isinstance(report, ColonyReport)
    assert "Rust" in report.prose
    assert report.flags == ["restless"]
    call = client.calls[0]
    assert call["format"] == ColonyReport.model_json_schema()
    assert call["options"]["temperature"] == ollama_config.digest_temperature


# --------------------------------------------------------------------------- #
# Ollama backend — fallback discipline (REQUIRED)
# --------------------------------------------------------------------------- #

def test_ollama_parse_malformed_degrades_to_safe_envelope(state, ollama_config):
    """Required: a malformed response degrades to a safe envelope, no raise."""
    backend = OllamaBackend(ollama_config, client=FakeClient(content="not json at all {{"))
    env = backend.parse("wave hello", state)
    assert isinstance(env, EffectEnvelope)
    assert env.effects == []  # nothing applied


def test_ollama_parse_empty_response_degrades(state, ollama_config):
    backend = OllamaBackend(ollama_config, client=FakeClient(content=""))
    env = backend.parse("wave hello", state)
    assert env.effects == []


def test_ollama_parse_salvages_prose_when_effects_invalid(state, ollama_config):
    raw = json.dumps(
        {"prose": "kept as flavor", "effects": [{"type": "bogus", "target": "x", "magnitude": 1.0}]}
    )
    backend = OllamaBackend(ollama_config, client=FakeClient(content=raw))
    env = backend.parse("do a thing", state)
    assert env.effects == []                 # invalid effect dropped
    assert env.prose == "kept as flavor"     # prose preserved


def test_ollama_parse_connection_error_degrades(state, ollama_config):
    backend = OllamaBackend(
        ollama_config, client=FakeClient(raises=ConnectionError("ollama down"))
    )
    env = backend.parse("anything", state)   # must NOT raise
    assert isinstance(env, EffectEnvelope)
    assert env.effects == []


def test_ollama_digest_malformed_degrades_to_safe_report(state, ollama_config):
    backend = OllamaBackend(ollama_config, client=FakeClient(content="???"))
    report = backend.digest(state, ["x"])
    assert isinstance(report, ColonyReport)
    assert report.prose == GENERIC_DIGEST_PROSE
    assert report.mood_deltas == {}
    assert report.flags == []


def test_ollama_digest_connection_error_degrades(state, ollama_config):
    backend = OllamaBackend(
        ollama_config, client=FakeClient(raises=TimeoutError("no route"))
    )
    report = backend.digest(state, ["x"])    # must NOT raise
    assert report.prose == GENERIC_DIGEST_PROSE


def test_ollama_backend_does_not_import_ollama_without_a_call(ollama_config):
    """Selecting/constructing the ollama backend never needs the package."""
    backend = OllamaBackend(ollama_config, client=FakeClient(content="{}"))
    # A call with an injected client must not touch the real `ollama` module.
    backend.parse("hi", FakeState())  # no ImportError, no network
