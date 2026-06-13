"""Pytest session setup: keep the suite offline and deterministic.

The LLM tests must never reach a live Ollama — even when a developer's shell, a
VS Code ``.env``, or a launch config selects the ``ollama`` backend. We pin
``LLM_BACKEND=stub`` for the whole test session here. Individual tests still
override it with ``monkeypatch`` where needed; those paths use injected fake
clients and never touch the network.
"""

import os

# Runs at conftest import, before any test is collected — so the default backend
# during tests is always the offline stub, regardless of the ambient environment.
os.environ["LLM_BACKEND"] = "stub"
