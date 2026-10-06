"""The breadth-law row round (audit 2026-10-06): near-duplicate rules, the four-term duplicate tax,
the per-producer duplicate budget, breadth-constrained mode, the empty clusters, the research-only
champion cap, the producer book context and the per-row coverage table."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for p in (str(DESK / "research"), str(DESK), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import breadth_debt as bd  # noqa: E402
import breadth_law_coverage as blc  # noqa: E402
import certificate_saturation as cs  # noqa: E402
import near_duplicate as nd  # noqa: E402
import producer_breadth as pbr  # noqa: E402

PAIRS = ("EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDCAD", "USDCHF", "USDJPY")


def _spec(sym: str, fam: str = "session_range_breakout", tf: str = "H1", **params: object) -> dict:
    return {"symbol": sym, "family": fam, "params": {"timeframe": tf, **params},
            "selector": "london", "source": "miner_x"}


CERT = {**_spec("EURUSD", rr=2.0, wait_bars=4, stop=1.0), "key": "EURUSD.srb"}


# ------------------------------------------------------------------ near-duplicate rules
@pytest.mark.parametrize(("cand", "rule"), [
    ({**_spec("EURUSD", rr=2.0, wait_bars=4, stop=1.0), "source": "kimi"}, "renamed_source"),
    (_spec("GBPUSD", rr=2.0, wait_bars=4, stop=1.0), "symbol"),
    (_spec("EURUSD", rr=2.0, wait_bars=4, stop=1.2), "small_stop"),
    (_spec("EURUSD", rr=2.1, wait_bars=4, stop=1.0), "small_param"),
    (_spec("EURUSD", tf="H4", rr=2.0, wait_bars=4, stop=1.0), "minor_tf_shift"),
])
def test_each_near_duplicate_rule_fires_on_its_twin(cand: dict, rule: str) -> None:
    assert nd.rule_between(cand, CERT) == rule
    idx = nd.Index([CERT])
    hit = nd.near_duplicate(cand, idx)
    assert hit is not None and hit[0] == rule


def test_equivalent_indicator_and_genuine_difference() -> None:
    a = _spec("EURUSD", fam="trend_ma_cross", indicator="sma", fast=10, slow=50)
    b = _spec("EURUSD", fam="trend_ma_cross", indicator="ema", fast=10, slow=50)
    assert nd.rule_between(b, a) == "equivalent_indicator"
    far = _spec("EURUSD", rr=4.0, wait_bars=12, stop=3.0)
    assert nd.rule_between(far, CERT) is None
    assert nd.rule_between(_spec("EURUSD", tf="D1", rr=2.0, wait_bars=4, stop=1.0), CERT) is None


def test_evidence_overturns_a_near_duplicate_rule() -> None:
    idx = nd.Index([CERT])
    twin = _spec("GBPUSD", rr=2.0, wait_bars=4, stop=1.0)
    assert nd.near_duplicate(twin, idx) is not None
    measured = {**twin, "measured_independence": {"n": 120, "rho_upper": 0.2}}
    assert nd.near_duplicate(measured, idx) is None
    thin = {**twin, "measured_independence": {"n": 10, "rho_upper": 0.0}}
    assert nd.near_duplicate(thin, idx) is not None, "a tiny sample never buys independence"
    assert nd.near_duplicate({**twin, "breadth_exception": "G"}, idx) is None


def test_structural_key_publishes_every_component_and_unknown_matches_only_unknown() -> None:
    ax = cs.axes_of("EURUSD", "session_range_breakout", {"rr": 2.0}, session="london",
                    timeframe="H1")
    key = nd.structural_key(ax)
    assert len(key) == len(nd.STRUCTURAL_KEY) == 11
    assert key[0] != "UNKNOWN" and key[1] != "UNKNOWN"
    assert nd.structural_key({}) == ("UNKNOWN",) * 11


# ------------------------------------------------------------------ the duplicate tax
def test_duplicate_tax_has_four_terms_each_monotone_and_a_floor() -> None:
    base, f = cs.duplicate_tax(1.0)
    assert base == pytest.approx(cs.DUPLICATE_TAX_CREDIT)
    assert f == {"density": pytest.approx(cs.DUPLICATE_TAX_CREDIT), "rate": 1.0,
                 "trials": 1.0, "yield": 1.0}
    dense, _ = cs.duplicate_tax(1.0, local_count=8.0)
    rated, _ = cs.duplicate_tax(1.0, duplicate_rate=0.8)
    tried, _ = cs.duplicate_tax(1.0, trials_spent=300.0)
    fallen, _ = cs.duplicate_tax(1.0, yield_ratio=0.3)
    for v in (dense, rated, tried, fallen):
        assert v < base
    worst, _ = cs.duplicate_tax(1.0, local_count=1e9, duplicate_rate=1.0, trials_spent=1e9,
                                yield_ratio=0.0)
    assert worst == cs.DUPLICATE_TAX_FLOOR > 0.0


def _sat() -> dict:
    sv = {}
    for i in range(140):
        sym = PAIRS[i % 7]
        sv[f"c{i}"] = {"sym": sym, "cell": f"{sym}.srb", "gated_at": "2026-09-01T00:00:00+00:00",
                       "gates": {"walk_forward": {"oos_sharpe": 0.2}},
                       "shadow_spec": {"symbol": sym, "selector": "london",
                                       "family": "session_range_breakout", "condition": None,
                                       "params": {"rr": 1 + (i // 7) % 10 * 0.25,
                                                  "wait_bars": 4 + (i // 70)}}}
    return cs.build(canon={"survivors": sv}, shadow={}, sleeves={}, judged={}, coupling_tab={},
                    residual={}, forward_daily={}, book={}, previous={}, loader=lambda s: None)


@pytest.fixture(scope="module")
def sat() -> dict:
    return _sat()


def _rows() -> list[dict]:
    rows = []
    for i in range(40):
        rows.append({"_cell": f"d{i}", "family": "session_range_breakout",
                     "symbol": PAIRS[i % 7], "params": {"rr": 1.0, "wait_bars": 4},
                     "selector": "london", "source": "miner_x"})
    for i in range(10):
        rows.append({"_cell": f"n{i}", "family": "session_range_breakout",
                     "symbol": ("XAUUSD", "US500")[i % 2], "params": {"rr": 9 + i},
                     "selector": "asia", "source": "miner_y"})
    return rows


def test_stamp_taxes_near_duplicates_never_drops_and_publishes_the_tax(
        sat: dict, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(cs, "FEEDBACK", tmp_path / "BREADTH_FEEDBACK.json")
    rows = _rows()
    ev = cs.stamp(rows, sat, debt={})
    assert ev["status"] == cs.MEASURED and ev["rows"] == len(rows) == 50
    assert all("_sat" in r for r in rows), "every row stamped, none removed"
    assert sum(ev["near_duplicates_by_rule"].values()) > 0
    assert ev["duplicate_tax"]["rows_taxed"] > 0
    assert set(ev["duplicate_tax"]["mean_factor"]) == {"density", "rate", "trials", "yield"}
    taxed = [r["_sat"] for r in rows if r["_dup"]]
    assert taxed and max(taxed) <= cs.DUPLICATE_TAX_CREDIT + 1e-9
    assert min(taxed) >= cs.DUPLICATE_TAX_FLOOR


def test_a_producers_published_duplicate_rate_deepens_its_tax(sat: dict, tmp_path: Path,
                                                              monkeypatch) -> None:
    fb = tmp_path / "BREADTH_FEEDBACK.json"
    monkeypatch.setattr(cs, "FEEDBACK", fb)
    a = _rows()
    cs.stamp(a, sat, debt={})
    fb.write_text(json.dumps({"producers": {"miner_x": {"duplicate_share": 1.0}}}), "utf-8")
    b = _rows()
    cs.stamp(b, sat, debt={})
    da = [r["_sat"] for r in a if r["_dup"]]
    db = [r["_sat"] for r in b if r["_dup"]]
    assert sum(db) < sum(da)


# ------------------------------------------------------------------ breadth-constrained mode
def test_mode_on_off_unmeasured_follows_its_documented_trigger() -> None:
    slope_up = {"slope": {"status": "MEASURED", "per_hour": 0.5}, "next_target": 20}
    flat = {"slope": {"status": "MEASURED", "per_hour": 0.0}, "next_target": 20}
    diluted = {"n_certificates": 100, "n_effective_certificates": 5}
    healthy = {"n_certificates": 10, "n_effective_certificates": 8}
    assert bd.mode(diluted, slope_up, "MEASURED")["fired"] == ["certificate_dilution"]
    assert bd.mode(healthy, flat, "MEASURED")["fired"] == ["stalled_ladder"]
    assert bd.mode(healthy, slope_up, "MEASURED")["mode"] == "OFF"
    assert bd.mode(healthy, {}, "MEASURED")["mode"] == bd.UNMEASURED, "OFF needs both readings"
    assert bd.mode(diluted, slope_up, "UNMEASURED")["mode"] == bd.UNMEASURED
    assert "dilution" in bd.mode(healthy, slope_up, "MEASURED")["trigger"]


def test_mode_boost_reaches_every_priority_level_only_while_on() -> None:
    debt = {"breadth_constrained_mode": "ON", "priority_targets": {
        "empty_payer_clusters": ["carry_rollover"], "empty_information_sources": ["options"],
        "low_occupancy_mechanisms": ["fx_fixing_flow"],
        "unrepresented_asset_factor_exposures": ["OIL"],
        "unrepresented_session_clocks": ["asia"], "unrepresented_horizons": ["swing"]}}
    hits = ("carry_rollover/price/forex/USD/london|intraday|day",
            "trend_persistence/options/forex/USD/london|intraday|day",
            "fx_fixing_flow/price/forex/USD/london|intraday|day",
            "trend_persistence/price/energy/OIL/london|intraday|day",
            "trend_persistence/price/forex/USD/asia|intraday|day",
            "trend_persistence/price/forex/USD/london|intraday|swing")
    for c in hits:
        assert bd.boost_for(c, debt) == bd.MODE_BOOST, c
    assert bd.boost_for("trend_persistence/price/forex/USD/london|intraday|day", debt) == 1.0
    assert bd.boost_for(hits[0], {**debt, "breadth_constrained_mode": "OFF"}) == 1.0
    assert bd.boost_for(hits[0], {}) == 1.0


def test_stamp_boosts_target_rows_while_on_and_never_a_duplicate(sat: dict, tmp_path: Path,
                                                                  monkeypatch) -> None:
    monkeypatch.setattr(cs, "FEEDBACK", tmp_path / "BREADTH_FEEDBACK.json")
    rows = _rows()
    clusters = set()
    sc = cs.Scorer(sat)
    for r in rows:
        clusters.add(sc.score_row(r)["cluster"])
    l1s = sorted({c.split("/")[0] for c in clusters})
    debt = {"breadth_constrained_mode": "ON",
            "priority_targets": {"low_occupancy_mechanisms": l1s}}
    on = _rows()
    ev = cs.stamp(on, sat, debt=debt)
    off = _rows()
    cs.stamp(off, sat, debt={})
    assert ev["breadth_constrained_mode"] == "ON" and ev["mode_boosted_rows"] > 0
    for a, b in zip(on, off, strict=True):
        if a["_dup"]:
            assert a["_sat"] == b["_sat"], "a duplicate is never boosted"
        else:
            assert a["_sat"] >= b["_sat"]


def test_breadth_debt_names_empty_clusters_with_bounty_and_bids(sat: dict) -> None:
    empties = [k for k, v in sat["empty_cluster_priors"].items()
               if int(v.get("certificates") or 0) == 0]
    assert empties
    debts = [d for d in sat["breadth_debts"] if d.get("alpha_cluster") in empties]
    assert debts, "an empty cluster carries at least one breadth debt"
    d0 = debts[0]
    bounty = {"bounties": [{"bounty_id": f"bounty:breadth_debt:{d0['missing_cluster']}"[:160],
                            "targets": ["dept_x"]}]}
    auction = {"bids": {"dept_x": {"bid": 3.5}}}
    doc = bd.build(sat=sat, ladder={}, bounty=bounty, auction=auction, lane_factors={"OIL"})
    assert doc["breadth_constrained_mode"] in ("ON", "OFF", bd.UNMEASURED)
    row = next(e for e in doc["empty_clusters"] if e["cluster"] == d0["alpha_cluster"])
    assert row["bounties_posted"] == 1 and row["auction_bids"] == {"dept_x": 3.5}
    assert row["expected_delta_k_eff"] >= 0.0 and row["breadth_debts"] >= 1
    assert row["mission"].startswith("NOT BUILT HERE")
    tg = doc["priority_targets"]
    assert tg["unrepresented_asset_factor_exposures"] == ["OIL"]
    for k in ("empty_payer_clusters", "empty_information_sources", "low_occupancy_mechanisms",
              "unrepresented_regimes", "unrepresented_horizons",
              "unrepresented_session_clocks"):
        assert isinstance(tg[k], list)
    assert doc["k_eff"]["stress_k_eff"] is None or isinstance(doc["k_eff"]["stress_k_eff"], float)


def test_breadth_debt_round_trips_and_a_stale_file_reads_empty(sat: dict, tmp_path: Path) -> None:
    p = bd.publish(bd.build(sat=sat, ladder={}, bounty={}, auction={}, lane_factors=None),
                   tmp_path / "BREADTH_DEBT.json")
    assert bd.load(p)["status"] == "MEASURED"
    assert bd.load(p, max_age_h=-1.0) == {}


# ------------------------------------------------------------------ champion cap, research-only
def test_champion_cap_counts_breadth_only_and_refuses_the_capital_side(sat: dict) -> None:
    cap = sat["champion_cap"]
    assert "REFUSED_BY_GROWTH_GOVERNANCE" in cap["capital_side"]
    head = sat["certificates"]
    assert head["n_certificates_credited"] <= head["n_certificates"]
    assert head["n_certificates"] == 140, "the nominal count is never capped"


# ------------------------------------------------------------------ producer context + budget
def test_producer_brief_carries_the_whole_book_context(sat: dict, monkeypatch) -> None:
    monkeypatch.setattr(cs, "_debt_brief", lambda: {"mode": "OFF"})
    brief = cs.producer_brief("miner", doc=sat, feedback={})
    ctx = brief["book_context"]
    for k in ("forward_sleeves", "promoted_live_sleeves", "economic_mechanism_clusters",
              "information_source_clusters", "factor_exposures", "temporal_session_clusters",
              "realised_return_clusters", "recent_survivor_yield", "effective_trials_spent",
              "stress_k_eff_book", "tail_k_eff_book"):
        assert k in ctx, k
    assert ctx["realised_return_clusters"] == cs.UNMEASURED
    assert ctx["information_source_clusters"][0]["certificates"] > 0
    assert brief["breadth_constrained_mode"] == {"mode": "OFF"}


def test_feedback_publishes_each_producers_duplicate_budget(sat: dict, tmp_path: Path,
                                                            monkeypatch) -> None:
    fb = tmp_path / "BREADTH_FEEDBACK.json"
    monkeypatch.setattr(cs, "FEEDBACK", fb)
    monkeypatch.setattr(cs, "load", lambda *a, **k: (sat, "fresh"))
    ev = cs.stamp(_rows(), sat, debt={})
    cs.write_feedback(ev, path=fb)
    doc = json.loads(fb.read_text("utf-8"))
    mx = doc["producers"]["miner_x"]
    assert mx["duplicate_budget"]["max_duplicate_share"] == cs.DUPLICATE_BUDGET_SHARE
    blk = pbr.duplicate_block("miner_x", [], doc)
    assert blk["status"] == "MEASURED" and blk["duplicate_candidates"] > 0
    assert blk["over_budget"] is True
    assert pbr.duplicate_block("nobody", [], doc)["status"] == pbr.UNMEASURED


# ------------------------------------------------------------------ the coverage table
def test_coverage_table_resolves_anchors_and_downgrades_a_dead_one(tmp_path: Path,
                                                                    monkeypatch) -> None:
    (tmp_path / "m.py").write_text("x = 1\ndef alive():\n    pass\n", "utf-8")
    rows = {"rows": [
        {"id": "BREADTH-9001", "section": "S §1", "requirement": "r", "audit_state": "ABSENT"},
        {"id": "BREADTH-9002", "section": "S §1", "requirement": "r", "audit_state": "ABSENT"},
        {"id": "BREADTH-9003", "section": "S §2", "requirement": "r", "audit_state": "SCHEDULED",
         "audit_module": ["m.py:1"]},
        {"id": "BREADTH-9004", "section": "S §2", "requirement": "r", "audit_state": "CODED",
         "audit_module": ["m.py:1"]},
    ]}
    rp = tmp_path / "rows.json"
    rp.write_text(json.dumps(rows), "utf-8")
    monkeypatch.setattr(blc, "CLASSIFICATION", (
        ("9001", blc.COVERED, ("m.py::^def alive",), ""),
        ("9002", blc.COVERED, ("m.py::^def gone",), ""),
    ))
    doc = blc.build(rows_path=rp, root=tmp_path)
    by = {r["id"]: r for r in doc["rows"]}
    assert by["BREADTH-9001"]["status"] == blc.COVERED
    assert by["BREADTH-9001"]["where"] == ["m.py:2"]
    assert by["BREADTH-9002"]["status"] == blc.PARTIAL and by["BREADTH-9002"]["downgraded"]
    assert by["BREADTH-9003"]["status"] == blc.COVERED
    assert by["BREADTH-9004"]["status"] == blc.PARTIAL
    assert doc["downgraded"] == ["BREADTH-9002"]
    p = blc.publish(doc, tmp_path / "BREADTH_LAW_COVERAGE.json")
    assert json.loads(p.read_text("utf-8"))["n_rows"] == 4


def test_the_real_table_covers_all_635_rows_with_no_dead_anchor() -> None:
    doc = blc.build()
    assert doc["status"] == "MEASURED" and doc["n_rows"] == 635
    assert sum(doc["counts"].values()) == 635
    assert doc["downgraded"] == [], doc["downgraded"]
    for r in doc["rows"]:
        if r["status"] in (blc.COVERED, blc.COVERED_SHADOW):
            assert r["where"], r["id"]
    assert doc["counts"][blc.COVERED_SHADOW] >= 1


def test_every_classified_anchor_resolves_in_this_tree() -> None:
    dead = [(spec, a) for spec, status, anchors, _ in blc.CLASSIFICATION
            for a in anchors if blc.resolve(a) is None]
    assert dead == []


def test_alpha_breadth_pass_writes_debt_and_coverage_beside_the_map(tmp_path: Path,
                                                                     monkeypatch) -> None:
    import alpha_breadth as ab
    monkeypatch.setattr(ab, "OUT", tmp_path / "EFFECTIVE_BREADTH.json")
    monkeypatch.setattr(bd, "_lane_factors", lambda: None)
    out = ab.breadth_debt_pass(_sat())
    assert (tmp_path / "BREADTH_DEBT.json").exists()
    assert (tmp_path / "BREADTH_LAW_COVERAGE.json").exists()
    assert out["breadth_constrained_mode"] in ("ON", "OFF", "UNMEASURED")
