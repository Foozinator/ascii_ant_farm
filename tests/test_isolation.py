"""Architectural guard: the three modules stay isolated.

The spec makes isolation a hard constraint:
* ``sim`` must not import ``llm`` (the deterministic core can't know the model exists)
* ``llm`` must not import ``sim`` (the model side talks only through the contract)

This scans each package's source with the AST (no importing required) and asserts
the forbidden top-level imports are absent — so a future agent building one side
against the stubbed other can't accidentally couple them.
"""

from __future__ import annotations

import ast
import pathlib

_ROOT = pathlib.Path(__file__).resolve().parent.parent


def _top_level_imports(package: str) -> set[str]:
    found: set[str] = set()
    for py in (_ROOT / package).rglob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    found.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                found.add(node.module.split(".")[0])
    return found


def test_sim_does_not_import_llm():
    assert "llm" not in _top_level_imports("sim")


def test_sim_does_not_import_ui():
    assert "ui" not in _top_level_imports("sim")


def test_llm_does_not_import_sim():
    assert "sim" not in _top_level_imports("llm")


def test_llm_does_not_import_ui():
    assert "ui" not in _top_level_imports("llm")
