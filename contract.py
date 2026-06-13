"""The contract — the single seam between ``sim/`` and ``llm/``.

This module is the neutral ground both halves of the game talk through. ``sim/``
imports it to read effects in; ``llm/`` imports it to hand effects and reports
out. Nothing here imports ``sim`` or ``llm``, so neither side can reach across
the boundary except by speaking these types.

Two envelopes cross the seam, in opposite directions:

* :class:`EffectEnvelope` — produced by ``llm.parse`` (or built directly by the
  command router), consumed by ``sim.tick``. It carries flavor ``prose`` plus a
  list of concrete :class:`Effect` the simulation knows how to apply.
* :class:`ColonyReport` — produced by ``llm.digest``, consumed by the UI. It is
  pure narration: prose, per-resident mood deltas, and free-form flags.

Every value crossing the seam is re-validated against these Pydantic models at
the boundary (see ``router.validate_envelope`` / ``router.validate_report``), so
a malformed payload from either side is caught rather than corrupting state.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class EffectType(str, Enum):
    """The closed set of things an :class:`Effect` can ask the sim to do.

    Keeping this an enum is what lets validation reject a hallucinated effect
    type from the (eventually real) language model: anything outside this set
    fails :class:`EffectEnvelope` validation and is dropped at the seam.
    """

    FEED = "feed"        # set the food stock (knob: ``feed <0-9>``)
    LIGHT = "light"      # set the power/light stock (knob: ``light <0-100>``)
    METRIC = "metric"    # change the selected metric (knob: ``metric <name>``)
    GESTURE = "gesture"  # an open-ended nudge parsed from a free sentence


class Effect(BaseModel):
    """One concrete, sim-applicable action.

    ``target`` is interpreted per ``type`` (a stock name for FEED/LIGHT, a
    metric name for METRIC, a room/colony tag for GESTURE). ``magnitude`` is the
    scalar the sim applies; its meaning is likewise per-type.
    """

    type: EffectType
    target: str
    magnitude: float


class EffectEnvelope(BaseModel):
    """Player intent on its way *into* the simulation.

    Built either by the deterministic command router (knob path) or returned by
    ``llm.parse`` (gesture path). On a validation failure the router keeps
    :attr:`prose` as flavor text but drops the (untrusted) effects.
    """

    prose: str = ""
    effects: list[Effect] = Field(default_factory=list)


class ColonyReport(BaseModel):
    """The colony's narrated response on its way *out* to the UI.

    Produced by ``llm.digest``. :attr:`mood_deltas` maps ``resident_id`` to the
    mood change the narration attributes to them; :attr:`flags` are free-form
    tags (e.g. ``"hunger"``) the UI may surface.
    """

    prose: str = ""
    mood_deltas: dict[str, float] = Field(default_factory=dict)
    flags: list[str] = Field(default_factory=list)
