"""WIRING IS A RATCHET NOW, BECAUSE A HAND-RUN GREP FINDS A DEFECT CLASS EXACTLY ONCE.

A one-off shell loop found three unwired modules on 2026-08-03: libs/data/wallet_graph.py,
libs/portfolio/capacity_allocation.py, and earlier the whole ICT detector family, which shipped
with full test suites and no caller. Tests passing is not reachability -- a module with 20 green
tests and no importer produces as much E[log W] as not having been written.

These tests pin the mechanical version, and the two bugs that made its first drafts useless.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scripts.max_audit as M  # noqa: E402


def _defects(fn) -> list:
    d: list = []
    fn(d)
    return d


# ------------------------------------------------------------------- unwired check

def test_the_unwired_check_resolves_absolute_imports() -> None:
    """THE BUG THAT INVERTED IT. The first version discarded `self_name` from the GLOBAL import
    set, so processing libs/alpha/card.py erased the record that another file had imported it --
    every module deleted its own inbound edges and 241 of 244 modules reported as orphans. A check
    that loud is ignored on sight."""
    d = _defects(M.check_unwired_modules)
    if d:
        n = int(d[0][1].split()[0])
        assert n < 30, f"{n} orphans -- the import walker is broken again, not the codebase"


def test_a_package_is_reachable_through_its_submodules() -> None:
    """Importing libs.alpha.card loads libs.alpha on the way. Counting package roots as orphans
    put 20 phantom entries in the list and buried the real ones."""
    d = _defects(M.check_unwired_modules)
    names = d[0][1] if d else ""
    for pkg in ("libs.alpha,", "libs.core,", "libs.costs,"):
        assert pkg not in names, f"package root {pkg} reported as unwired"


def test_the_modules_wired_this_session_are_no_longer_orphans() -> None:
    d = _defects(M.check_unwired_modules)
    names = d[0][1] if d else ""
    for m in ("wallet_graph", "capacity_allocation", "book_walk", "alert_ledger"):
        assert m not in names, f"{m} is still unwired"


def test_live_connectors_are_exempt_with_an_argument() -> None:
    """Wiring an order path on a desk with zero validated alphas is strictly worse than leaving it
    unreachable. This is the one exemption that could lose money if granted casually."""
    assert "libs.execution.binance_live" in M._UNWIRED_EXEMPT
    src = (ROOT / "scripts/max_audit.py").read_text("utf-8")
    assert "DORMANT UNTIL GATE-0" in src, "every exemption must be argued in writing"


# ------------------------------------------------------------- asymmetry ratchet

def test_the_asymmetry_ratchet_exists_and_is_registered() -> None:
    """Promised, then not delivered for a full session. A ledger nothing audits is a report."""
    assert any(name == "asymmetry-ratchet" for name, _ in M.CHECKS)
    assert any(name == "data-decay" for name, _ in M.CHECKS)


def test_a_stale_asymmetry_claim_raises_a_defect(tmp_path, monkeypatch) -> None:
    """An unchecked claim is 'not measured' read as 'measured and fine', pointed at the one asset
    that supposedly justifies the enterprise."""
    art = tmp_path / "asymmetry_ledger.json"
    art.write_text(json.dumps({"realised_asymmetry_total": 1.0,
                               "stale_claims": ["wallet_entity_graph"]}), "utf-8")
    monkeypatch.setattr(M, "ROOT", tmp_path.parent)
    monkeypatch.setattr(M, "ASYM_RECORD", tmp_path / "rec.json")
    # Point the check at our fixture by placing it where it looks.
    (tmp_path.parent / "data").mkdir(exist_ok=True)
    (tmp_path.parent / "data" / "asymmetry_ledger.json").write_text(art.read_text(), "utf-8")
    d = _defects(M.check_asymmetry_ratchet)
    assert any(x[0] == "asymmetry-claim-stale" for x in d)


def test_realised_asymmetry_is_a_ratchet_not_a_gauge(tmp_path, monkeypatch) -> None:
    """Weight x depth only grows. A fall is a source demoted, a depth regressed, or a claim
    expired -- §39(4) applied to the axis that decides edge."""
    monkeypatch.setattr(M, "ROOT", tmp_path)
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "asymmetry_ledger.json").write_text(
        json.dumps({"realised_asymmetry_total": 1.0, "stale_claims": []}), "utf-8")
    rec = tmp_path / "rec.json"
    rec.write_text(json.dumps({"best_realised": 5.0}), "utf-8")
    monkeypatch.setattr(M, "ASYM_RECORD", rec)
    d = _defects(M.check_asymmetry_ratchet)
    assert any(x[0] == "asymmetry-realised-fell" for x in d)


# ------------------------------------------------------------------- the callers

@pytest.mark.parametrize("script", ["scripts/resolve_wallets.py", "scripts/run_allocation.py"])
def test_the_new_callers_run_and_report_absent_input_honestly(script: str) -> None:
    """Both refuse to synthesise: entity labels and allocations are consumed as ground truth, and
    one derived from a generator would name noise or size real capital against imaginary
    correlations."""
    r = subprocess.run([sys.executable, str(ROOT / script)], cwd=ROOT,
                       capture_output=True, text=True, timeout=300, check=False)
    assert r.returncode == 0, r.stderr
    assert "NO " in r.stdout


def test_allocation_gives_zero_weight_to_unmeasured_capacity(tmp_path) -> None:
    """A strategy with no measured capacity is NOT assumed unlimited -- that is how an
    unexecutable book gets built."""
    import pandas as pd
    p = tmp_path / "s.csv"
    pd.DataFrame({"a": [0.01, -0.01] * 60, "b": [0.02, -0.015] * 60}).to_csv(p, index=False)
    r = subprocess.run([sys.executable, str(ROOT / "scripts/run_allocation.py"),
                        "--streams", str(p)], cwd=ROOT, capture_output=True,
                       text=True, timeout=300, check=False)
    assert r.returncode == 0, r.stderr
    assert "NO MEASURED CAPACITY" in r.stdout
    rep = json.loads((ROOT / "data/allocation.json").read_text("utf-8"))
    assert rep["gross"] == 0.0
    assert rep["unallocated"] == pytest.approx(1.0)


def test_the_orphan_detector_can_still_SEE_an_orphan(tmp_path) -> None:
    """A CLEAN RESULT AND A BROKEN WALKER LOOK IDENTICAL, AND ONLY ONE IS GOOD NEWS.

    The test above asserts the orphan COUNT is small -- which it also is when the walker returns
    early, walks nothing and reports nothing. That is the failure mode this desk keeps finding in
    itself: a detector broken in the QUIET direction, whose silence reads as health. Today's sweep
    for tests that can pass while asserting nothing found exactly this one.

    So: plant a real orphan under libs/, confirm the check names it, and remove it. The positive
    control is the only thing that distinguishes "nothing is unwired" from "nothing is looking".
    """
    orphan = Path("libs") / "_orphan_probe_do_not_import.py"
    assert not orphan.exists(), "a previous run leaked its probe -- delete it"
    orphan.write_text('"""Planted by a test. Nothing imports this, on purpose."""\n'
                      "X = 1\n", "utf-8")
    try:
        d = _defects(M.check_unwired_modules)
        named = " ".join(msg for _, msg in d)
        assert d, "the check found NO orphan while one was sitting in libs/ -- it is not looking"
        assert "_orphan_probe_do_not_import" in named, (
            f"the walker ran but missed a planted orphan: {named[:300]}")
    finally:
        orphan.unlink(missing_ok=True)


def test_a_wiring_fix_cannot_be_one_link_short() -> None:
    """THE HOLE IN THE ORPHAN CHECK, AND I FELL INTO IT THREE TIMES IN ONE SESSION.

    A libs module counts as wired the moment ANY file imports it -- including a scripts/ entrypoint
    that nothing ever runs. So the honest fix for an orphan ("write it a caller") can be satisfied
    by a file that is itself an orphan: the check goes green and the module is exactly as
    unreachable as before. cluster_weak_signals.py, resolve_wallets.py and
    run_ict_cross_sectional.py were each written to wire a library module, and nothing ran any of
    them. A wiring fix one link short still reports success, which is worse than no fix at all.

    Deliberately narrow: it audits only scripts that are LOAD-BEARING for the orphan check -- the
    sole importer of some libs module. Not every script needs a caller, and a check that demanded
    one would emit 69 defects nobody could act on, which is the crying-wolf failure this file
    names in three other places.
    """
    d = _defects(M.check_unwired_modules)
    dead = [msg for key, msg in d if key == "unwired-caller"]
    assert not dead, dead[0][:400]


def test_the_dead_caller_check_can_still_SEE_a_dead_caller(tmp_path) -> None:
    """Same argument as the orphan probe above: a clean result and a check that stopped looking
    are indistinguishable, and only one is good news."""
    probe = Path("libs") / "_deadlink_probe.py"
    caller = Path("scripts") / "_deadlink_probe_caller.py"
    assert not probe.exists() and not caller.exists(), "a previous run leaked its probe"
    probe.write_text('"""Planted by a test."""\nY = 2\n', "utf-8")
    caller.write_text('"""Planted caller. NOTHING invokes this file, on purpose."""\n'
                      "from libs._deadlink_probe import Y\n\nprint(Y)\n", "utf-8")
    try:
        d = _defects(M.check_unwired_modules)
        named = " ".join(msg for key, msg in d if key == "unwired-caller")
        assert named, "the check found no dead link while one was planted -- it is not looking"
        assert "_deadlink_probe_caller" in named, f"the sweep ran but missed it: {named[:300]}"
    finally:
        probe.unlink(missing_ok=True)
        caller.unlink(missing_ok=True)
