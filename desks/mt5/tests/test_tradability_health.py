"""TRADABILITY_HEALTH: per-live-sleeve tradability, its verdict rule, its clock and its reader.

Every test builds its artifacts under tmp_path and passes the paths in; nothing reads or writes
the desk's real reports.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import layers  # noqa: E402
from research import hazard_engine as HZ  # noqa: E402
from research import tradability_health as TH  # noqa: E402

NOW = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)
STAMP = NOW.isoformat()


def _write(p: Path, doc: object) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc), encoding="utf-8")
    return p


def _roster(tmp: Path, *rows: dict) -> Path:
    return _write(tmp / "sleeves.json", {"sleeves": list(rows)})


def _paths(tmp: Path, **docs: object) -> dict[str, Path]:
    """Every source pointed into tmp; the ones not given simply do not exist."""
    keys = ("decay_live", "drift", "identity", "cost_truth", "execution_twin", "regime_router",
            "capacity", "capacity_frontier", "posterior")
    out = {k: tmp / f"{k}.json" for k in keys}
    for k, doc in docs.items():
        _write(out[k], doc)
    out["sleeves"] = tmp / "sleeves.json"
    return out


LIVE = {"name": "xau_a", "symbol": "XAUUSD", "family": "fam", "status": "LIVE"}


# ------------------------------------------------------------------------- paths stay pinned
def _declared(module_file: str, filename: str) -> bool:
    src = (DESK / "research" / module_file).read_text("utf-8")
    return re.search(rf'"reports"\s*/\s*"{re.escape(filename)}"', src) is not None


def test_mirrored_paths_are_the_organs_own():
    for module_file, path in (("posterior_alpha.py", TH.POSTERIOR),
                              ("regime_router.py", TH.REGIME_ROUTER),
                              ("capacity.py", TH.CAPACITY),
                              ("capacity_frontier.py", TH.CAPACITY_FRONTIER),
                              ("research_live_identity.py", TH.IDENTITY)):
        assert _declared(module_file, path.name), (module_file, path)
    assert _declared("cost_truth.py", "COST_TRUTH.json") or \
        'OUT = REPORTS / "COST_TRUTH.json"' in (DESK / "research" / "cost_truth.py").read_text()
    assert HZ.TRADABILITY == TH.OUT


def test_leg_is_on_the_clock_and_in_a_layer():
    src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_costed("tradability_health"' in src
    assert '"tradability_health": thl' in src
    assert layers.LEG_LAYER["tradability_health"] == "portfolio"


# --------------------------------------------------------------------------- absence is a verdict
def test_no_artifacts_reads_unmeasured_never_healthy(tmp_path):
    _roster(tmp_path, LIVE, {**LIVE, "name": "standby", "status": "STANDBY"})
    doc = TH.measure(NOW, _paths(tmp_path))
    assert doc["n_live"] == 1
    row = doc["sleeves"][0]
    assert row["verdict"] == TH.UNMEASURED
    for f in TH.FIELDS:
        assert row["fields"][f]["value"] == TH.UNMEASURED
        assert row["fields"][f]["why"]
    json.dumps(doc, allow_nan=False)


def test_unreadable_roster_is_unknown_not_empty(tmp_path):
    doc = TH.measure(NOW, _paths(tmp_path))
    assert doc["n_live"] is None and doc["status"] == TH.UNMEASURED and doc["roster_why"]


def test_stale_input_is_unmeasured_with_the_lease(tmp_path):
    _roster(tmp_path, LIVE)
    old = (NOW - timedelta(hours=10)).isoformat()
    doc = TH.measure(NOW, _paths(tmp_path, posterior={
        "at": old, "sleeves": [{"name": "xau_a", "n": 40, "p_positive": 0.95}]}))
    f = doc["sleeves"][0]["fields"]["recent_forward_posterior"]
    assert f["value"] == TH.UNMEASURED and "lease" in f["why"]


# ------------------------------------------------------------------------------- the readings
def test_fields_read_each_organ(tmp_path):
    _roster(tmp_path, LIVE)
    paths = _paths(
        tmp_path,
        posterior={"at": STAMP, "sleeves": [{"name": "xau_a", "n": 40, "p_positive": 0.93,
                                             "mu_mean": 0.2}]},
        identity={"generated_utc": STAMP, "rows": [{"name": "xau_a", "verdict": "MATCH"}]},
        cost_truth={"at": STAMP, "symbols": [{
            "symbol": "XAUUSD", "compare": {"charged_pts": 20.0, "reference_pts": 18.0},
            "quoted": {"tape": {"pooled": {"n": 500}}}}]},
        regime_router={"at": STAMP, "sleeves": [{
            "name": "xau_a", "n": 40, "current_bucket": "vol=high",
            "by_state": {"vol=high": {"n": 10}}, "p_alpha_positive_now": 0.8}]},
        capacity_frontier={"at": STAMP, "status": "OK",
                           "curves": [{"symbol": "XAUUSD", "family": "fam", "n_signals": 200,
                                       "dies_at_cost_multiple": 5.0, "status": "OK"}],
                           "spread_widening": {"by_symbol": {"XAUUSD": {
                               "status": "OK", "widening_multiple": 2.0}}}},
        drift={"generated_utc": STAMP, "per_symbol": {"XAUUSD": {
            "hazard_max": 0.5, "n_windows": 300, "per_stat": {}}}},
    )
    doc = TH.measure(NOW, paths)
    row = doc["sleeves"][0]
    f = row["fields"]
    assert f["recent_forward_posterior"]["value"] == 0.93
    assert f["recent_forward_posterior"]["pressure"] == 0.0
    assert f["parameter_drift"]["value"] == 0.0
    assert f["cost_drift"]["value"] == 0.9 and f["cost_drift"]["pressure"] == 0.0
    assert f["regime_occupancy"]["value"] == 0.25
    assert f["capacity_drift"]["value"] == 0.4
    assert f["feature_drift"]["value"] == 0.5 and f["feature_drift"]["pressure"] == 0.0
    assert f["execution_drift"]["value"] == TH.UNMEASURED
    for name in ("recent_forward_posterior", "cost_drift", "regime_occupancy"):
        assert f[name]["as_of"] and f[name]["source"].endswith(".json")
    assert row["verdict"] == TH.HEALTHY


def test_identity_mismatch_is_broken(tmp_path):
    _roster(tmp_path, LIVE)
    doc = TH.measure(NOW, _paths(tmp_path, identity={
        "generated_utc": STAMP,
        "rows": [{"name": "xau_a", "verdict": "MISMATCH", "fields": ["params"]}]}))
    row = doc["sleeves"][0]
    assert row["fields"]["parameter_drift"]["value"] == 1.0
    assert row["verdict"] == TH.BROKEN and doc["broken"] == ["xau_a"]


def test_promoter_flag_alone_can_only_degrade(tmp_path):
    _roster(tmp_path, {**LIVE, "certificate_drift": True})
    row = TH.measure(NOW, _paths(tmp_path))["sleeves"][0]
    assert row["verdict"] == TH.DEGRADING


# ------------------------------------------------------------------------------- the verdict rule
def _f(p: float | None) -> dict:
    return {"value": TH.UNMEASURED if p is None else 0.0, "pressure": p}


def test_verdict_rule():
    calm = {k: _f(None) for k in TH.FIELDS}
    assert TH.verdict_of(calm)[0] == TH.UNMEASURED
    three = {**calm, "cost_drift": _f(0.1), "feature_drift": _f(0.0),
             "recent_forward_posterior": _f(0.2)}
    assert TH.verdict_of(three)[0] == TH.HEALTHY
    no_posterior = {**calm, "cost_drift": _f(0.1), "feature_drift": _f(0.0),
                    "execution_drift": _f(0.2)}
    assert TH.verdict_of(no_posterior)[0] == TH.UNMEASURED
    assert TH.verdict_of({**three, "regime_occupancy": _f(1.0)})[0] == TH.DEGRADING
    assert TH.verdict_of({**three, "capacity_drift": _f(1.0)})[0] == TH.DEGRADING
    assert TH.verdict_of({**three, "recent_forward_posterior": _f(1.0)})[0] == TH.BROKEN
    assert TH.verdict_of({**calm, "execution_drift": _f(0.6)})[0] == TH.DEGRADING


# --------------------------------------------------------------------------- the reader wired
def _card(name: str, lane: str = "live", health: str = "GREEN", verdict: str | None = None
          ) -> dict:
    c = {"name": name, "lane": lane, "symbol": "XAUUSD", "family": "fam", "health": health,
         "k": 20, "p_die_k": 0.01, "trailing_t": 1.0, "n": 30, "mean_r": 0.1,
         "drawdown_r": -2.0, "basis": "x", "replacement_candidates": []}
    if verdict:
        c["tradability"] = {"verdict": verdict, "why": "parameter_drift"}
    return c


def test_hazard_engine_hunts_a_successor_for_degrading_tradability(tmp_path):
    q = tmp_path / "successor_queue.jsonl"
    cards = [_card("a", verdict="BROKEN"), _card("b", verdict="HEALTHY"),
             _card("c", lane="forward", verdict="BROKEN"), _card("d", verdict="DEGRADING")]
    rows = HZ.queue_successors(cards, STAMP, q)
    assert sorted(r["for"] for r in rows) == ["a", "d"]
    assert all(r["trigger"] == "tradability_health" for r in rows)
    assert HZ.queue_successors(cards, STAMP, q) == []          # deduped per day


def test_hazard_engine_reading_states(tmp_path):
    p = tmp_path / "TRADABILITY_HEALTH.json"
    assert HZ.tradability_reading(p, NOW)[1].startswith("absent")
    _write(p, {"generated_utc": (NOW - timedelta(hours=5)).isoformat(), "sleeves": []})
    assert HZ.tradability_reading(p, NOW)[1].startswith("stale")
    _write(p, {"generated_utc": STAMP,
               "sleeves": [{"name": "a", "verdict": "BROKEN", "why": "w"}]})
    got, state = HZ.tradability_reading(p, NOW)
    assert state == "present" and got["a"]["verdict"] == "BROKEN"
