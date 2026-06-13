"""Backend selection and lifecycle.

``LLM_BACKEND`` (read via :func:`llm.config.load_config`) decides which backend is
active. The active backend is cached and rebuilt automatically whenever the
effective config changes, so flipping an env var between turns takes effect
without a restart. Tests can install an explicit override with :func:`set_backend`.
"""

from __future__ import annotations

from llm.backends import Backend, OllamaBackend, StubBackend
from llm.config import LLMConfig, load_config

# Cache of the env-derived backend, keyed by the config it was built from.
_cached: Backend | None = None
_cached_config: LLMConfig | None = None

# An explicit override always wins over the env-derived cache (for tests/DI).
_override: Backend | None = None


def build_backend(config: LLMConfig) -> Backend:
    """Construct the backend named by ``config`` (does not touch the cache)."""
    if config.backend == "ollama":
        return OllamaBackend(config)
    return StubBackend(config)


def get_backend() -> Backend:
    """Return the active backend, rebuilding it if the config changed."""
    global _cached, _cached_config
    if _override is not None:
        return _override
    config = load_config()
    if _cached is None or config != _cached_config:
        _cached = build_backend(config)
        _cached_config = config
    return _cached


def set_backend(backend: Backend | None) -> None:
    """Install an explicit override backend (pass ``None`` to clear it)."""
    global _override
    _override = backend


def reset_backend() -> None:
    """Clear the override and the cache; the next call re-reads the env."""
    global _cached, _cached_config, _override
    _cached = None
    _cached_config = None
    _override = None


def describe_backend() -> str:
    """A one-line, config-only description of the selected backend (no network)."""
    cfg = load_config()
    if cfg.backend == "ollama":
        return f"ollama · model={cfg.model} · {cfg.base_url}"
    return "stub (offline, no model calls)"


def _model_names(resp: object) -> list[str]:
    """Extract model name strings from an ollama list() response, defensively."""
    models = getattr(resp, "models", None)
    if models is None and isinstance(resp, dict):
        models = resp.get("models", [])
    names: list[str] = []
    for m in models or []:
        name = getattr(m, "model", None) or getattr(m, "name", None)
        if name is None and isinstance(m, dict):
            name = m.get("model") or m.get("name")
        if name:
            names.append(name)
    return names


def check_backend() -> tuple[bool, str]:
    """Return ``(ok, message)`` describing whether the active backend is usable.

    The stub is always ok. For ollama this makes a cheap ``list()`` call to
    confirm the server is reachable and the configured model is installed — it
    does NOT load the model. Never raises; failures come back as ``ok=False``
    with an explanatory message.
    """
    cfg = load_config()
    if cfg.backend != "ollama":
        return True, "engine: stub (offline, no model calls)"
    try:
        import ollama

        client = ollama.Client(host=cfg.base_url)
        resp = client.list()
    except Exception as exc:  # unreachable server, missing package, etc.
        return False, (
            f"engine: ollama UNREACHABLE at {cfg.base_url} ({exc!r}); "
            "parses/digests will fall back to safe flavor"
        )
    names = _model_names(resp)
    base = cfg.model.split(":")[0]
    if names and cfg.model not in names and not any(n.split(":")[0] == base for n in names):
        return False, (
            f"engine: ollama reachable at {cfg.base_url}, but model '{cfg.model}' "
            f"is NOT installed (have: {', '.join(names) or 'none'})"
        )
    return True, f"engine: ollama OK at {cfg.base_url} (model '{cfg.model}')"
