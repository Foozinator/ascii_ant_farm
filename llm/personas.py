"""Persona cards — the resident voices loaded from ``character_seeds.json``.

A :class:`PersonaCard` carries a ``voice_sample`` that the digest uses as a
few-shot anchor; in testing that field is what made the voices land. The catalog
maps a resident's ``archetype`` tag to a card by ``id`` and falls back to a
neutral default when there's no match.

This module is llm-internal — its card model is NOT part of ``contract.py`` and
must not leak across the seam. It imports nothing from ``sim``.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel

_SEEDS_PATH = Path(__file__).with_name("character_seeds.json")

# Used only if character_seeds.json is missing or corrupt — the digest must never
# crash for want of a persona.
_HARDCODED_DEFAULT = {
    "id": "default",
    "name": "Worker",
    "role": "worker",
    "traits": "An ordinary worker ant.",
    "voice_sample": "We dig, we carry, we carry on.",
}


class PersonaCard(BaseModel):
    """One resident voice. ``voice_sample`` anchors the model's tone."""

    id: str
    name: str
    role: str = ""
    traits: str = ""
    voice_sample: str = ""


class PersonaCatalog:
    """Lookup from archetype tag to :class:`PersonaCard`, with a default."""

    def __init__(self, cards: list[PersonaCard], default: PersonaCard) -> None:
        self._by_id = {card.id.lower(): card for card in cards}
        self._default = default

    def card_for(self, archetype: str) -> PersonaCard:
        """Return the card whose ``id`` matches ``archetype``, else the default.

        TODO(coordination): resident ``archetype`` tags (forager/nurse/drone/
        queen) are sim-side placeholders. Today the seeds file is keyed to match
        them, but the agreed direction is for residents to carry real per-character
        catalog ids and for this lookup to match on those. Until then, any
        unmatched tag degrades to the neutral default card.
        """
        return self._by_id.get((archetype or "").strip().lower(), self._default)

    @property
    def default(self) -> PersonaCard:
        return self._default

    def ids(self) -> list[str]:
        return list(self._by_id)


def load_catalog(path: str | Path | None = None) -> PersonaCatalog:
    """Load a :class:`PersonaCatalog` from a seeds JSON file (raises on error)."""
    seeds_path = Path(path) if path is not None else _SEEDS_PATH
    data = json.loads(seeds_path.read_text(encoding="utf-8"))
    cards = [PersonaCard(**raw) for raw in data.get("cards", [])]
    default_raw = data.get("default") or _HARDCODED_DEFAULT
    return PersonaCatalog(cards, PersonaCard(**default_raw))


@lru_cache(maxsize=1)
def get_catalog() -> PersonaCatalog:
    """Cached catalog from the bundled seeds; degrades safely if unreadable."""
    try:
        return load_catalog()
    except (OSError, ValueError) as exc:  # missing file or bad JSON/shape
        # Never let persona loading take down the turn loop.
        del exc
        return PersonaCatalog([], PersonaCard(**_HARDCODED_DEFAULT))
