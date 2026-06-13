"""Structural views of the state that ``llm`` is allowed to read.

The language-model side receives a state object across the seam but must not
import ``sim`` — that would couple the two isolated halves. Instead it describes
the *shape* it depends on as :class:`typing.Protocol` types. Any object with
these attributes satisfies them structurally, so ``sim.GameState`` works at
runtime without ``llm`` ever importing it.

These are read-only views: the stubs (and the eventual real model) only ever
read state to produce envelopes/reports — they never mutate it.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class ResidentView(Protocol):
    id: str
    mood: float
    archetype: str


@runtime_checkable
class StateView(Protocol):
    food: float
    power: float
    turn: int
    metric: str
    residents: list[ResidentView]
