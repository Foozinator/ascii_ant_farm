"""Read the character catalog as plain DATA for the detail panel.

The catalog (``characters.json`` at the repo root) is the canonical card source
shared by content and, eventually, the language model. The UI reads it directly
as JSON — it does **not** import :mod:`llm`. Residents carry a catalog id in
their ``archetype`` tag (the generator seeds them from these ids); we match on
that and fall back gracefully when an id isn't in the catalog (e.g. the default
8x10 colony uses free tags like ``forager`` that have no card).

(The catalog wants to live in a shared content path both ``ui`` and ``llm`` can
read, rather than next to code — a nudge toward that refactor, not done here.)
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

# Repo root / characters.json — ui/ sits one level down from the root.
_CATALOG_PATH = Path(__file__).resolve().parent.parent / "characters.json"


@lru_cache(maxsize=1)
def load_catalog() -> dict[str, dict]:
    """Return ``{catalog_id: card}``; empty dict if the file is missing/bad."""
    try:
        data = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    characters = data.get("characters", [])
    return {c["id"]: c for c in characters if isinstance(c, dict) and "id" in c}


def card_for(catalog_id: str | None) -> dict | None:
    """Look up one card by catalog id, or ``None`` if absent."""
    if not catalog_id:
        return None
    return load_catalog().get(catalog_id)
