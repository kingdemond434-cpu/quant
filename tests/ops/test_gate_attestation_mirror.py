"""The attestation's state classification must BE the canonical one, not a copy of it.

WHY THIS TEST EXISTS. `scripts/gate_attestation.py` kept its own copy of the state-path lists so
it could run on a bare checkout where `libs` is not importable. The copy drifted: measured
2026-11-14 it carried 2 of `release.py:STATE_FILES`' 11 entries, so nine canonical state paths
were counted as dirty CODE and `data/gate_attestation.json` reported `tree_clean: false,
dirty_paths: 6` on every run of a box whose only non-prefix changes were ledgers. The one field a
consumer needing a hard guarantee must require was therefore permanently unusable.

`release.py` states the law the copy broke -- "a mirror that can drift is not a mirror" -- and
this is the third time that file's own comments record this bug-class. So the script now IMPORTS
the canonical lists and keeps its literals only as the bare-checkout fallback; these tests pin the
fallback equal to the canonical lists, so the next drift fails the suite instead of the
attestation.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from libs.ops import release

ROOT = Path(__file__).resolve().parents[2]


def _module() -> Any:
    path = ROOT / "scripts" / "gate_attestation.py"
    spec = importlib.util.spec_from_file_location("gate_attestation_mirror", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_live_classification_is_the_canonical_one() -> None:
    module = _module()
    assert module._STATE_PREFIXES is release.STATE_PREFIXES
    assert module._STATE_FILES is release.STATE_FILES


def test_the_bare_checkout_fallback_cannot_drift_from_the_canonical_lists() -> None:
    module = _module()
    assert tuple(module._FALLBACK_STATE_PREFIXES) == tuple(release.STATE_PREFIXES)
    assert frozenset(module._FALLBACK_STATE_FILES) == frozenset(release.STATE_FILES)


def test_the_box_standing_dirty_set_is_state_not_code() -> None:
    """The six paths that held `tree_clean` false, named: five moat registries and the journal.

    Every one is written by an organ and read by organs; none is importable (`git ls-files
    backups` returns no `.py`). A classification that calls them CODE says the code under test is
    unknown because the desk's own ledgers moved.
    """
    module = _module()
    for rel in (
        "backups/moat/forward_registry",
        "backups/moat/graveyard",
        "backups/moat/manifest.json",
        "backups/moat/shadow_state",
        "backups/moat/universal_canon",
        "context/decision_journal.jsonl",
    ):
        assert module._is_state(rel), rel
        assert release.is_state_path(rel), rel


def test_the_moat_tree_is_state_without_disarming_the_code_fence() -> None:
    """`backups/` is state; the directories that hold code are not swept in with it."""
    assert release.is_state_path("backups/moat/shadow_ledgers/ledger_XAUUSD_asia.json")
    assert not release.is_state_path("desks/mt5/mt5desk/gateway.py")
    assert not release.is_state_path("libs/ops/release.py")
    assert not release.is_state_path("scripts/gate_attestation.py")
