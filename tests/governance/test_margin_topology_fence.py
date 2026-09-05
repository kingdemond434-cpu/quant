"""L1.64 fence -- a margin construction nobody chose is a ceiling nobody measured.

These tests fail if the fence's wiring is removed. The ones that matter most pin the refusals:
INHERITED must fail the fence (that is the state it was built to expose), a stale terms table
must not mint MEASURED alternatives, and a molded paper book must never price the clamp in
dollars.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
_SRC = ROOT / "scripts/check_margin_topology.py"

# THE SUBJECT IS PARKED, NOT RETIRED, AND THAT DISTINCTION IS WHY THIS FILE STILL EXISTS.
#
# `scripts/check_margin_topology.py` imports `libs.portfolio.margin_topology`, which was deleted in
# 1657d5f7 during the crypto-exchange purge, so the fence can no longer import and its cron rows
# are parked in ops/crontab.manifest. But the manifest says in as many words that this is NOT a
# universe retirement and that the rows are a RESTORATION CANDIDATE: margin construction -- whether
# a book is INHERITED from the venue's leverage or chosen against measured alternatives -- is an
# MT5-relevant risk concept, and L1.64 has no other scheduled enforcement point.
#
# So the SPEC is kept executable rather than deleted. The skip is CONDITIONAL on the file's absence,
# which means restoring the module re-arms all seven assertions automatically -- nobody has to
# remember this file exists. A deleted spec would have to be rewritten from scratch to restore a
# law the desk still holds, and it would be rewritten from memory of what the fence used to refuse.
if not _SRC.exists():                                                  # pragma: no cover
    pytest.skip(
        "L1.64 PARKED 2026-09-05: scripts/check_margin_topology.py cannot import because "
        "libs.portfolio.margin_topology was deleted in 1657d5f7. This is a RESTORATION CANDIDATE, "
        "not a retirement -- ops/crontab.manifest carries the parked rows and the reason. Restore "
        "the module and every assertion below arms again with no edit here.",
        allow_module_level=True)


def _load(monkeypatch: pytest.MonkeyPatch, root: Path) -> Any:
    """Import the fence with every artifact path pointed at a temporary tree."""
    spec = importlib.util.spec_from_file_location("check_margin_topology_under_test", _SRC)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    (root / "data").mkdir(exist_ok=True)
    (root / "web").mkdir(exist_ok=True)
    monkeypatch.setattr(mod, "_OUT", root / "data/margin_topology.json")
    monkeypatch.setattr(mod, "_TERMS", root / "data/margin_topology_terms.json")
    monkeypatch.setattr(mod, "_DECISION", root / "data/margin_topology_decision.json")
    monkeypatch.setattr(mod, "_NAV", root / "data/nav_attestation.jsonl")
    monkeypatch.setattr(mod, "_PLAN", root / "web/capital_plan.json")
    return mod


def _terms(**kw: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "as_of": datetime.now(UTC).isoformat(),
        "usdtm_perp_bases": ["BTC", "ETH", "SOL", "XRP"],
        "coinm_perp_bases": ["BTC", "ETH"],
        "multi_assets_collateral": {"BTC": 0.95, "ETH": 0.95},
        "pm_npe": 1.62, "pm_min_equity_usd": 10_000.0, "pm_source": "dated read",
    }
    base.update(kw)
    return base


def _write(p: Path, doc: Any) -> None:
    p.write_text(json.dumps(doc), "utf-8")


def test_a_bare_tree_reports_inherited_never_ok(monkeypatch, tmp_path):
    """THE FAILING STATE THIS FENCE WAS BUILT FOR. No decision row, no terms, no NAV -- the
    book still runs a construction nobody chose, and the fence must say so from the executor's
    own constants alone, with zero network reads."""
    mod = _load(monkeypatch, tmp_path)
    rep = mod.build()
    assert rep["status"] == "INHERITED"
    assert rep["n_constructions"] == 5
    assert rep["n_measured"] == 1  # only the inherited construction stands without terms
    assert "INHERITED" not in mod._PASSING
    assert "UNMEASURED" not in mod._PASSING
    # the artifact must have been produced with its provenance beside the numbers (L1.55)
    assert rep["provenance"], "no inputs declared -- L1.55 requires the block"


def test_decided_against_measured_alternatives_passes(monkeypatch, tmp_path):
    mod = _load(monkeypatch, tmp_path)
    _write(tmp_path / "data/margin_topology_terms.json", _terms())
    _write(tmp_path / "data/margin_topology_decision.json",
           {"construction": "split_spot_usdtm", "decided_at": "2026-08-19",
            "decided_by": "principal", "equity_at_decision_usd": 17_000.0,
            "evidence": "data/margin_topology.json"})
    rep = mod.build()
    assert rep["status"] == "DECIDED"
    assert rep["status"] in mod._PASSING


def test_a_stale_terms_table_must_not_mint_measured_alternatives(monkeypatch, tmp_path):
    """L1.44 degrade direction: a three-week-old collateral table is not evidence about
    today's venue. The alternatives fall back to UNMEASURED; they never run on the stale read."""
    mod = _load(monkeypatch, tmp_path)
    old = (datetime.now(UTC) - timedelta(days=40)).isoformat()
    _write(tmp_path / "data/margin_topology_terms.json", _terms(as_of=old))
    rep = mod.build()
    assert rep["n_measured"] == 1
    rows = {r["key"]: r for r in rep["constructions"]}
    assert rows["coinm_inverse_1x"]["status"] == "UNMEASURED"


def test_paper_book_refuses_dollar_pricing_but_publishes_rates(monkeypatch, tmp_path):
    """L1.51: the NAV attestation is a molded/simulated curve pre-Gate-0. Dollar costs from a
    simulated denominator are refused; per-$10k rates stay published."""
    mod = _load(monkeypatch, tmp_path)
    _write(tmp_path / "data/margin_topology_terms.json", _terms())
    nav = {"ts": datetime.now(UTC).isoformat(), "equity_marked": 17_323.61,
           "mode": "PAPER (testnet) -- pre-Gate-0", "_note": "molded_curve_usd is a MOLDED..."}
    (tmp_path / "data/nav_attestation.jsonl").write_text(json.dumps(nav) + "\n", "utf-8")
    rep = mod.build()
    assert "MOLDED-PAPER" in rep["equity_basis"]
    for alt in rep["uplift"]["alternatives"]:
        assert alt["usd_per_day_if_validated"] is None
        assert alt["per_10k_usd_per_day_if_validated"] is not None


def test_diverged_decision_fails(monkeypatch, tmp_path):
    mod = _load(monkeypatch, tmp_path)
    _write(tmp_path / "data/margin_topology_terms.json", _terms())
    _write(tmp_path / "data/margin_topology_decision.json",
           {"construction": "coinm_inverse_1x", "decided_at": "2026-08-19",
            "decided_by": "principal"})
    rep = mod.build()
    assert rep["status"] == "DIVERGED"
    assert rep["status"] not in mod._PASSING


def test_fence_exit_is_wired_with_a_scanned_denominator():
    """L1.57: the exit site must declare how many constructions the verdict covers, and the
    passing set must be exactly {DECIDED} -- INHERITED passing would weld this fence open."""
    src = _SRC.read_text("utf-8")
    assert "fence_exit(" in src and "scanned=rep[\"n_constructions\"]" in src
    assert 'frozenset({"DECIDED"})' in src
    assert "_law_guard()" in src  # L1.42: no exempt entry points


def test_main_writes_the_artifact_and_fails_on_inherited(monkeypatch, tmp_path):
    """A failing fence that writes no artifact strands its own repair: the decision row is
    written FROM data/margin_topology.json, so the report must exist precisely when INHERITED."""
    mod = _load(monkeypatch, tmp_path)
    monkeypatch.setattr(mod, "_law_guard", lambda: None)
    monkeypatch.setattr(sys, "argv", ["check_margin_topology.py"])
    rc = mod.main()
    assert rc == 2, "INHERITED must fail loud at the exit code cron actually reads"
    assert json.loads(mod._OUT.read_text("utf-8"))["status"] == "INHERITED"
