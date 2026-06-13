"""The (stubbed) language-model side of the game.

Two interfaces, both currently canned:

* :func:`parse` — free sentence -> :class:`contract.EffectEnvelope`
* :func:`digest` — state + new events -> :class:`contract.ColonyReport`

Real Ollama calls will live behind these exact signatures. This package depends
only on :mod:`contract` and its own :mod:`llm.views`; it never imports ``sim``.
"""

from llm.digest import digest
from llm.parser import parse
from llm.views import ResidentView, StateView

__all__ = ["parse", "digest", "StateView", "ResidentView"]
