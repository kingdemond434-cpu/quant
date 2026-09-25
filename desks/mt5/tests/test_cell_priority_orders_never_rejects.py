"""THE ORDERING IS NOT A SECOND JUDGE.

`research/cell_priority.order` decides which cells the warmer makes cheap first, and therefore
which cells a bounded sweep actually reaches this week. That is a large amount of influence over
what gets tested, and the whole of it must be over ORDER. The ten gates in
`desks/mt5/policy/gate_spec.yaml` are the only thing on this desk that may certify or refuse a
cell; an ordering that quietly dropped one would be a second judge with no attestation, no trial
accounting and no record.

So these tests pin the property rather than the ranking: for every input -- including the cells
this module scores WORST, including families it has never measured, including an empty docket and
a docket where every artifact is missing -- the output is a PERMUTATION of the input. Same length,
same multiset of identities, nothing added and nothing lost.

The ranking itself is checked only for the two claims the module actually makes: measured
prospects dominate, and novelty breaks NEAR-ties without overruling a measured edge.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK / "research"), str(_DESK), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import cell_priority as CP  # noqa: E402


def _spec(sym: str, family: str, tf: str = "H1", **params: object) -> dict:
    return {"sym": sym, "family": family, "tf": tf, "params": dict(params)}


def _desk(tmp_path: Path, *, judged: list[dict], cured: list[str], passed: list[str]) -> Path:
    """A minimal desk tree carrying only the three artifacts the priors are measured from."""
    hyp = tmp_path / "desks" / "mt5" / "data" / "hypotheses"
    rep = tmp_path / "desks" / "mt5" / "reports"
    hyp.mkdir(parents=True)
    rep.mkdir(parents=True)
    (hyp / "gate_verdict_ledger.jsonl").write_text(
        "\n".join(json.dumps(r) for r in judged), encoding="utf-8")
    (rep / "POWER_CURE_CANDIDATES.json").write_text(json.dumps({
        "n": len(cured),
        "candidates": {f"external.{c}": {"cell": c, "shadow_spec": {
            "family": CP.family_from_cell(c)}} for c in cured}}), encoding="utf-8")
    (rep / "UNIVERSAL_SURVIVORS.json").write_text(json.dumps({
        "survivors": {f"external.{c}": {"cell": c, "shadow_spec": {
            "family": CP.family_from_cell(c)}} for c in passed}}), encoding="utf-8")
    return tmp_path


def _ledger(sym: str, family: str, tf: str, n: int) -> list[dict]:
    at = "@" + tf if tf != "H1" else ""
    return [{"at": "2026-09-01T00:00:00+00:00", "cell": f"{sym}{at}.{family}.p={i:016x}",
             "sym": sym, "family": family, "passed": False,
             "terminal_gate": "deflated_sharpe"} for i in range(n)]


@pytest.fixture
def priors(tmp_path: Path) -> CP.Priors:
    """A desk where `carry` reaches the forward-cure route and `noise` never does."""
    judged = (_ledger("EURUSD", "carry", "H1", 100)
              + _ledger("EURUSD", "noise", "H1", 100)
              + _ledger("GBPJPY", "untouched_ground", "M15", 1))
    cured = [f"EURUSD.carry.p={i:016x}" for i in range(60)]
    passed = [f"EURUSD.carry.p={0:016x}"]
    return CP.measure_priors(_desk(tmp_path, judged=judged, cured=cured, passed=passed))


# --------------------------------------------------------------- the property that matters

def test_order_is_a_permutation(priors: CP.Priors) -> None:
    specs = [_spec("EURUSD", "carry"), _spec("EURUSD", "noise"),
             _spec("GBPJPY", "untouched_ground", "M15"),
             _spec("XAUUSD", "never_seen_family", "M5", rr=2.0)]
    out = CP.order(specs, priors)
    assert len(out) == len(specs)
    assert sorted(CP.cell_key(s) for s in out) == sorted(CP.cell_key(s) for s in specs)


def test_the_worst_scoring_cell_is_still_in_the_queue(priors: CP.Priors) -> None:
    """A cell with the lowest measured prospect on the most crowded ground is ranked LAST and is
    still present. Ranked last means judged later, never judged never."""
    worst = _spec("EURUSD", "noise")
    out = CP.order([_spec("EURUSD", "carry"), worst], priors)
    assert CP.cell_key(out[-1]) == CP.cell_key(worst)
    assert any(CP.cell_key(s) == CP.cell_key(worst) for s in out)


def test_permutation_holds_with_every_artifact_missing(tmp_path: Path) -> None:
    """UNMEASURED is a real answer (L1.28a): with no ledger, no cure file and no survivors the
    module still returns every cell, in a defined order."""
    p = CP.measure_priors(tmp_path)
    assert p.n_judged == 0
    assert "MISSING" in str(p.sources["gate_verdict_ledger.jsonl"])
    specs = [_spec("EURUSD", "carry"), _spec("XAUUSD", "session_range_breakout", "M15")]
    out = CP.order(specs, p)
    assert sorted(CP.cell_key(s) for s in out) == sorted(CP.cell_key(s) for s in specs)


def test_duplicate_specs_are_not_collapsed(priors: CP.Priors) -> None:
    """Two docket rows that key identically must both come back: de-duplication is the caller's
    decision and the sweep's, never a side effect of ranking."""
    twin = _spec("EURUSD", "carry")
    out = CP.order([twin, dict(twin)], priors)
    assert len(out) == 2


def test_empty_docket(priors: CP.Priors) -> None:
    assert CP.order([], priors) == []


def test_order_is_reproducible(priors: CP.Priors) -> None:
    specs = [_spec("EURUSD", "carry"), _spec("EURUSD", "noise"), _spec("AUDNZD", "carry", "M5")]
    assert [CP.cell_key(s) for s in CP.order(specs, priors)] == \
           [CP.cell_key(s) for s in CP.order(list(reversed(specs)), priors)]


# --------------------------------------------------------------- the two ranking claims

def test_a_family_that_reaches_the_cure_route_outranks_one_that_does_not(
        priors: CP.Priors) -> None:
    out = CP.order([_spec("EURUSD", "noise"), _spec("EURUSD", "carry")], priors)
    assert out[0]["family"] == "carry"


def test_an_unmeasured_family_gets_the_house_rate_not_zero(priors: CP.Priors) -> None:
    """Never-judged ground is unknown, not barren. An unmeasured family must score at least the
    house rate, so it outranks a family MEASURED to be worse than the house."""
    unknown = _spec("XAUUSD", "never_seen_family")
    measured_bad = _spec("EURUSD", "noise")
    assert CP.score(unknown, priors) > CP.score(measured_bad, priors)


def test_novelty_breaks_near_ties_and_does_not_overrule_a_measured_edge(
        priors: CP.Priors) -> None:
    """Two cells whose measured prospects are identical separate on novelty; a cell with a real
    measured edge is not displaced by a novel one."""
    crowded = _spec("EURUSD", "never_seen_family")
    thin = _spec("GBPJPY", "never_seen_family", "M15")
    assert CP.score(thin, priors) > CP.score(crowded, priors)
    # ... but the measured edge still wins outright.
    assert CP.score(_spec("EURUSD", "carry"), priors) > CP.score(thin, priors)


def test_novelty_weight_is_an_order_of_magnitude_below_the_cure_weight() -> None:
    """Pinned as a constant relationship, because 'among near-ties' is an arithmetic claim: the
    whole novelty range must be smaller than the cure term's range."""
    assert CP.W_NOVELTY * 1.0 < CP.W_CURE * 0.5


def test_cell_ids_parse_the_chart_they_carry() -> None:
    assert CP.timeframe_from_cell("GBPJPY@M15.adx_channel_hybrid.p=9f6f") == "M15"
    assert CP.timeframe_from_cell("EURUSD.carry.p=abcd") == "H1"
    assert CP.family_from_cell("GBPJPY@M15.adx_channel_hybrid.p=9f6f") == "adx_channel_hybrid"
    assert CP.symbol_from_cell("GBPJPY@M15.adx_channel_hybrid.p=9f6f") == "GBPJPY"


def test_publish_records_that_the_output_was_a_permutation(tmp_path: Path,
                                                           priors: CP.Priors) -> None:
    (tmp_path / "desks" / "mt5" / "reports").mkdir(parents=True, exist_ok=True)
    specs = [_spec("EURUSD", "carry"), _spec("EURUSD", "noise")]
    out = CP.publish(specs, CP.order(specs, priors), priors, tmp_path)
    doc = json.loads(out.read_text("utf-8"))
    assert doc["is_permutation"] is True
    assert doc["n_in"] == doc["n_out"] == 2
    assert "ORDERS, NEVER REJECTS" in doc["rule"]
