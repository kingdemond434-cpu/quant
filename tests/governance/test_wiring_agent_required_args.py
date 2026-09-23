"""The wiring agent must not schedule a script it cannot invoke.

THE DEFECT (measured 2026-08-29). `scripts/run_wiring_agent.py` proves an AUTO-WIRE candidate is
SAFE five ways -- it has a main(), imports no money path, cannot spend, is not a server, writes
only under data/ and web/. It never asked whether the script can RUN with the command line the
agent writes, which is always argument-free. `scripts/vault_search.py` takes a required
positional query, was auto-wired as `.venv/bin/python scripts/vault_search.py >> <log>`, and
every scheduled run since exited 2 on an argparse usage message.

A row that can only ever fail is worse than an unwired script: it consumes a slot on a 4GB box,
writes a log nobody can act on, and counts as coverage in every organ that measures wiring. It is
L1.49's "a gate that never ran is a claim the desk cannot cash" wearing a cron schedule.

ONE-WAY BY CONSTRUCTION: this check can only ever move a script from AUTO-WIRE to PROPOSE. There
is no input that turns a PROPOSE into an AUTO-WIRE, so it cannot loosen the agent.
"""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

_ROOT = Path(__file__).resolve().parents[2]


def _load() -> ModuleType:
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    spec = importlib.util.spec_from_file_location(
        "run_wiring_agent", _ROOT / "scripts" / "run_wiring_agent.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def mod() -> ModuleType:
    return _load()


def _req(mod: ModuleType, body: str) -> list[str]:
    return mod._required_positionals(ast.parse(body))


def test_the_live_case_is_caught(mod: ModuleType) -> None:
    """vault_search.py's own signature, verbatim in shape."""
    assert _req(mod, "ap.add_argument('query', nargs='+')") == ["query"]


def test_a_bare_positional_is_required(mod: ModuleType) -> None:
    assert _req(mod, "ap.add_argument('path')") == ["path"]


def test_flags_are_not_required(mod: ModuleType) -> None:
    assert _req(mod, "ap.add_argument('--json', action='store_true')") == []


def test_a_positional_with_a_default_is_optional(mod: ModuleType) -> None:
    assert _req(mod, "ap.add_argument('report', default='coverage.json')") == []


@pytest.mark.parametrize("nargs", ["?", "*"])
def test_optional_nargs_is_not_required(mod: ModuleType, nargs: str) -> None:
    assert _req(mod, f"ap.add_argument('extra', nargs={nargs!r})") == []


def test_nargs_plus_is_still_required(mod: ModuleType) -> None:
    """`+` means one-or-more, so an argument-free invocation still fails."""
    assert _req(mod, "ap.add_argument('words', nargs='+')") == ["words"]


def test_a_non_literal_name_is_not_guessed_at(mod: ModuleType) -> None:
    """Only argparse's own vocabulary is read; a computed name earns no verdict either way."""
    assert _req(mod, "ap.add_argument(NAME)") == []


def test_the_real_wiring_agent_now_refuses_vault_search(mod: ModuleType) -> None:
    """End to end against the actual script that shipped the broken row."""
    decision, reason, _ = mod.classify("scripts/vault_search.py")
    assert decision == "PROPOSE"
    assert "positional" in reason
