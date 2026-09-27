"""The sweep's shape: exploration guaranteed across asset class x chart x family (2026-09-25).

Measured on the live docket before this module: the gauntlet's allocated order held FOUR
families in its first 1,500 cells, every family with no intraday row was judged zero times, and
~23,000 rows that no executor can run sat at the head of the never-judged queue every hour.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(DESK), str(DESK / "research"), str(DESK / "scripts"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import sweep_breadth as sb  # noqa: E402


def _chart(spec: dict) -> str:
    return str((spec.get("params") or {}).get("timeframe") or "H1").upper()


# --------------------------------------------------------------------------- the vocabulary
def test_buckets_split_what_the_registry_lumps():
    assert sb.research_bucket("EURUSD") == "fx_major"
    assert sb.research_bucket("EURGBP") == "fx_cross"
    assert sb.research_bucket("XAUUSD") == "gold"
    assert sb.research_bucket("XAGUSD") == "silver"
    assert sb.research_bucket("XPTUSD") == "metal"
    assert sb.research_bucket("US500") == "index"
    assert sb.research_bucket("UST10Y") == "bond"
    assert sb.research_bucket("XTIUSD") == "energy"
    assert sb.research_bucket("CORN") == "soft"
    assert sb.research_bucket("BTCUSD") == "crypto_cfd"
    assert sb.research_bucket("Apple") == "equity"
    # Absent from MetaTrader's registry: never classified from the text, hunted by nothing.
    assert sb.research_bucket("NOTREAL") == "unclassified"


def test_cell_ids_parse_in_every_shape_the_desk_writes():
    assert sb.parse_cell_id("EURUSD.carry.p=ab12") == ("EURUSD", "H1", "carry")
    assert sb.parse_cell_id("XAUUSD@M5.carry.p=ab12") == ("XAUUSD", "M5", "carry")
    assert sb.parse_cell_id("AAPL.24H.carry.p=ab12") == ("AAPL.24H", "H1", "carry")
    assert sb.parse_cell_id("EURUSD.session_range_breakout.rr=1.5_wb=12") == (
        "EURUSD", "H1", "session_range_breakout")
    assert sb.parse_cell_id("garbage") is None


def test_a_banned_familys_judgements_do_not_make_a_stratum_look_tested():
    ids = ["EURGBP.discovered.p=1", "EURGBP.discovered.p=2", "EURGBP.carry.p=3"]
    strata, fam = sb.judged_counts(ids, banned=lambda f: f == "discovered")
    assert strata[("fx_cross", "H1")] == 1
    assert fam[("fx_cross", "H1", "carry")] == 1


# ------------------------------------------------------------------------- executability
def test_decoration_keys_no_executor_applies_are_named():
    why = sb.unexecutable_reason("style_premia", {"style": "trend", "conditioner": "macro"})
    assert why and "conditioner" in why
    why = sb.unexecutable_reason("range_reversion", {"representation": "external_engine"})
    assert why and "representation" in why


def test_identity_keys_and_the_session_never_make_a_row_unexecutable():
    assert sb.unexecutable_reason("style_premia",
                                  {"style": "trend", "timeframe": "D1", "session": "asia"}) is None
    assert sb.unexecutable_reason("relative_value", {"peer_symbol": "NZDUSD"}) is None
    assert sb.unexecutable_reason("cross_sectional",
                                  {"peer_symbols": ["A", "B"], "horizon": 20}) is None
    assert sb.unexecutable_reason("exit_operated", {
        "timeframe": "H1", "base_family": "adx_channel_hybrid", "base_params": {},
        "expansion_mult": 1.25, "exit_on_anchor_flip": False}) is None
    assert sb.unexecutable_reason("htf_anchor_trend", {
        "timeframe": "H4", "anchor_mult": 3, "expansion_mult": 0.0,
        "exit_on_anchor_flip": False}) is None


def test_a_required_argument_nobody_supplies_is_named():
    why = sb.unexecutable_reason("calendar_month", {})
    assert why and "active_month" in why
    # `cot` is rebuilt for cot_positioning only; the legacy-frame families never receive it.
    assert sb.unexecutable_reason("cot_comm_follow", {}) is not None
    assert sb.unexecutable_reason("cot_positioning", {}) is None
    assert sb.unexecutable_reason("no_such_family_anywhere", {"x": 1}) is None


# ------------------------------------------------------------------------------ the shape
def _specs() -> list[dict]:
    """One heavily-exploited family on a tested stratum, two families on untested strata."""
    rows = [{"sym": "EURUSD", "family": "srb", "params": {}} for _ in range(400)]
    rows += [{"sym": "XAGUSD", "family": "trend", "params": {"timeframe": "D1"}}
             for _ in range(100)]
    rows += [{"sym": "UST10Y", "family": "tom", "params": {"timeframe": "H4"}}
             for _ in range(100)]
    return rows


def test_every_prefix_carries_the_exploration_share():
    specs = _specs()
    judged = [f"EURUSD.srb.p={i}" for i in range(2000)]      # fx_major|H1 is well tested
    order, rec = sb.shape(specs, list(specs), {"srb": 0.9, "trend": 0.05, "tom": 0.05},
                          judged, chart_of=_chart, exploration_share=0.5,
                          undertested_below=400, stratum_min=10, chunk=4)
    assert rec["n_undertested"] == 2
    for n in (40, 100, 200):
        head = order[:n]
        explored = sum(1 for s in head if s["sym"] != "EURUSD")
        assert explored >= 0.45 * n, (n, explored)
    # Exploitation still gets its half, and the yield leader leads it.
    assert sum(1 for s in order[:200] if s["family"] == "srb") >= 80


def test_the_shape_removes_nothing_the_allocator_kept_and_floors_untested_strata():
    specs = _specs()
    keep = specs[:400]                          # the trim kept only the exploited family
    order, rec = sb.shape(specs, keep, {"srb": 1.0}, [], chart_of=_chart,
                          exploration_share=0.5, undertested_below=400, stratum_min=10,
                          chunk=4)
    ids = {id(s) for s in order}
    assert all(id(k) in ids for k in keep), "a kept member was dropped"
    assert len(ids) == len(order), "a member was emitted twice"
    assert sum(1 for s in order if s["sym"] == "XAGUSD") == 10
    assert sum(1 for s in order if s["sym"] == "UST10Y") == 10
    assert rec["n_floor_added"] == 20


def test_family_blocks_no_longer_decide_what_the_hour_reaches():
    """The defect: keep was concatenated family by family, so the budget saw one family."""
    specs = [{"sym": f"S{i % 5}", "family": fam, "params": {}}
             for fam in ("a", "b", "c", "d") for i in range(200)]
    order, _ = sb.shape(specs, list(specs), dict.fromkeys("abcd", 0.25), [],
                        chart_of=_chart, exploration_share=0.0, chunk=4)
    assert {s["family"] for s in order[:32]} == {"a", "b", "c", "d"}


def test_equities_and_unclassified_symbols_are_never_explored():
    specs = [{"sym": "Apple", "family": "x", "params": {}} for _ in range(50)]
    specs += [{"sym": "NOTREAL", "family": "x", "params": {}} for _ in range(50)]
    _, rec = sb.shape(specs, [], {"x": 1.0}, [], chart_of=_chart, stratum_min=10)
    assert rec["n_undertested"] == 0 and rec["n_floor_added"] == 0


# -------------------------------------------------------------- wired into the gauntlet
def _gauntlet():
    spec = importlib.util.spec_from_file_location(
        "_gaunt_breadth", DESK / "scripts" / "external_gauntlet.py")
    assert spec and spec.loader
    g = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(g)
    return g


def test_allocate_by_yield_publishes_and_applies_the_shape(tmp_path, monkeypatch):
    g = _gauntlet()
    monkeypatch.setattr(g, "REPORTS", tmp_path)
    monkeypatch.setattr(g, "_family_yield", lambda root=None: {})
    monkeypatch.setattr(g, "_axis_yield", lambda root=None: {("H1", "-"): 1, ("D1", "-"): 1,
                                                            ("H4", "-"): 1})
    monkeypatch.setattr(g, "_seen_cells", lambda: {})
    specs = ([{"sym": "EURUSD", "family": "a", "params": {}} for _ in range(300)]
             + [{"sym": "XAGUSD", "family": "b", "params": {"timeframe": "D1"}}
                for _ in range(300)]
             + [{"sym": "CORN", "family": "c", "params": {"timeframe": "H4"}}
                for _ in range(300)])
    kept, _report = g.allocate_by_yield(specs)
    assert {s["family"] for s in kept[:24]} == {"a", "b", "c"}, (
        "the first builds of the hour must reach every family, not the first block")
    doc = json.loads((tmp_path / "RESEARCH_ALLOCATION.json").read_text("utf-8"))
    assert doc["breadth"]["n_undertested"] == 3
    assert "first_300" in doc["breadth"]["projection"]
