"""The breadth gap round (2026-10-06): behavioural overlap, the projected future book, capacity
terms, the brief reaching every producer and seat, and the per-cluster cap run in shadow."""
from __future__ import annotations

import copy
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for p in (str(DESK / "research"), str(DESK), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import breadth_capacity as bcap  # noqa: E402
import breadth_law_coverage as blc  # noqa: E402
import certificate_saturation as cs  # noqa: E402
import cluster_cap_shadow as ccs  # noqa: E402
import stream_overlap as so  # noqa: E402

PAIRS = ("EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDCAD", "USDCHF", "USDJPY")


def _days(n: int) -> list[str]:
    t0 = datetime(2025, 1, 1, tzinfo=UTC)
    return [(t0 + timedelta(days=i)).date().isoformat() for i in range(n)]


def _series(vals: np.ndarray, days: list[str]) -> dict[str, float]:
    return {d: float(v) for d, v in zip(days, vals, strict=True)}


# ------------------------------------------------------------------ behavioural overlap
def test_independent_streams_never_link_and_every_term_is_a_lower_bound() -> None:
    rng = np.random.default_rng(1)
    d = _days(250)
    worst = 0.0
    for _ in range(15):
        a, b = _series(rng.normal(size=250), d), _series(rng.normal(size=250), d)
        o = so.pair_overlap(a, b, events=set(d[::5]), regimes=so.regime_labels([a, b]))
        assert o["status"] == so.MEASURED
        worst = max(worst, float(o["overlap_score"]))
    assert worst < so.OVERLAP_INDEPENDENT


def test_shared_crashes_and_drawdowns_link_a_pair_whose_rho_is_modest() -> None:
    rng = np.random.default_rng(2)
    d = _days(300)
    common = np.where(rng.random(300) < 0.08, -4.0, 0.0)       # shared crash days
    a = rng.normal(size=300) * 0.5 + common
    b = rng.normal(size=300) * 0.5 + common
    o = so.pair_overlap(_series(a, d), _series(b, d))
    assert o["co_crash"] is not None and o["co_crash"] >= so.OVERLAP_LINK
    assert o["overlap_score"] >= so.OVERLAP_LINK


def test_signal_overlap_reads_shared_trading_days_and_floors_say_unmeasured() -> None:
    rng = np.random.default_rng(3)
    d = _days(200)
    on = rng.random(200) < 0.3
    a = np.where(on, rng.normal(size=200), 0.0)
    b = np.where(on, rng.normal(size=200), 0.0)
    o = so.pair_overlap(_series(a, d), _series(b, d))
    assert o["signal"] is not None and o["signal"] > so.OVERLAP_LINK
    short = so.pair_overlap(_series(a[:20], d[:20]), _series(b[:20], d[:20]))
    assert short["status"] == so.UNMEASURED and short["overlap_score"] is None
    assert o["event"] is None and "calendar" in o["why"]["event"]


def test_lead_lag_is_found_at_its_lag() -> None:
    rng = np.random.default_rng(4)
    d = _days(300)
    x = rng.normal(size=301)
    a, b = x[1:], x[:-1] + 0.1 * rng.normal(size=300)        # b leads a by one day
    o = so.pair_overlap(_series(a, d), _series(b, d))
    assert o["lead_lag"] > so.OVERLAP_LINK and abs(o["lead_lag_k"]) == 1


def test_overlap_links_pairs_in_forward_dependence_and_denies_exception_f() -> None:
    rng = np.random.default_rng(5)
    d = _days(250)
    common = np.where(rng.random(250) < 0.08, -4.0, 0.0)
    daily = {"EURUSD_session_range_breakout_london": _series(rng.normal(size=250) + common, d),
             "GBPUSD_session_range_breakout_london": _series(rng.normal(size=250) + common, d)}
    dep = cs.forward_dependence(daily)
    p = dep["pairs"][0]
    assert p["overlap_score"] is not None and p["overlap_score"] >= so.OVERLAP_LINK
    assert p["state"] == "DEPENDENT" and p["dependence"] >= p["overlap_score"]
    assert dep["overlap_by_identity"], "the stream's worst overlap is keyed for the scorer"


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


def test_measured_overlap_caps_novelty_and_blocks_f(sat: dict) -> None:
    sc = cs.Scorer(sat)
    row = {"family": "carry", "symbol": "XAUUSD", "params": {"hold_days": 5},
           "selector": "asia", "measured_independence": {"n": 200, "rho_upper": 0.1}}
    free = sc.score_row(row)
    assert "F" in free["exceptions"]
    hit = sc.score_row({**row, "measured_overlap": {"overlap_score": 0.8}})
    assert "F" not in hit["exceptions"]
    assert hit["measured_overlap"] == 0.8
    assert hit["breadth_value"] <= max(cs.DUPLICATE_TAX_FLOOR, 0.2) + 1e-9
    assert hit["breadth_value"] < free["breadth_value"]


# ------------------------------------------------------------------ the projected future book
def _rows(n: int = 40) -> list[dict]:
    return [{"_cell": f"r{i}", "family": "session_range_breakout", "symbol": PAIRS[i % 7],
             "params": {"rr": 9.0 + i, "wait_bars": 2}, "selector": "asia", "source": "miner_z",
             "premortem": {"p_survivor": 0.4}} for i in range(n)]


def test_future_book_marginal_is_published_and_no_larger_than_todays(sat: dict, tmp_path: Path,
                                                                     monkeypatch) -> None:
    monkeypatch.setattr(cs, "FEEDBACK", tmp_path / "BREADTH_FEEDBACK.json")
    ev = cs.stamp(_rows(), sat, debt={})
    fut = ev["future_book"]
    assert fut["status"] == cs.MEASURED and fut["rows"] == 40
    assert fut["n_future"] == pytest.approx(fut["n_book"] + 40 * 0.4)
    assert fut["k_eff_future"] >= fut["k_eff_book"]
    p = ev["producers"]["miner_z"]
    assert p["expected_delta_k_eff_future_book"] is not None
    assert p["expected_delta_k_eff_future_book"] <= p["expected_delta_k_eff"] + 1e-12


# ------------------------------------------------------------------ capacity terms
def test_capacity_terms_each_bite_and_the_product_is_floored() -> None:
    uni = {"AAA": {"asset_class": "Forex", "median_spread_pts": 10.0, "min_volume": 0.01,
                   "volume_step": 0.01, "swap_long": -1.0, "swap_short": -1.0},
           "BBB": {"asset_class": "Forex", "median_spread_pts": 40.0, "min_volume": 0.1,
                   "volume_step": 0.01, "swap_long": 1.0, "swap_short": -1.0},
           "CCC": {"asset_class": "Forex", "median_spread_pts": 10.0}}
    cap = {"rows": [{"status": "MEASURED", "symbol": "BBB", "headroom_multiple": 4.0}],
           "ceiling_status": "UNMEASURED"}
    ctx = bcap.Context(universe=uni, capacity=cap)
    a = bcap.terms("AAA", {"timeframe": "H1", "horizon": "swing"}, ctx)
    b = bcap.terms("BBB", {"timeframe": "M5", "horizon": "intraday"}, ctx)
    z = bcap.terms("ZZZ", {"timeframe": "H1", "horizon": "intraday"}, ctx)
    assert a["terms"]["capital_efficiency"] == bcap.NEGATIVE_CARRY
    assert b["terms"]["capacity"] == pytest.approx(0.25)
    assert b["terms"]["broker_constraints"] == bcap.COARSE_LOT
    assert b["terms"]["liquidity"] < a["terms"]["liquidity"] <= 1.0
    assert b["terms"]["turnover"] < a["terms"]["turnover"]
    assert z["terms"]["broker_constraints"] == bcap.UNROUTED
    assert a["terms"]["market_impact"] is None and "market_impact" in a["unmeasured"]
    assert b["factor"] >= bcap.CAPACITY_FLOOR
    assert set(a["terms"]) == set(bcap.TERMS)


def test_capacity_scales_the_breadth_value_and_is_published(sat: dict, tmp_path: Path,
                                                             monkeypatch) -> None:
    monkeypatch.setattr(cs, "FEEDBACK", tmp_path / "BREADTH_FEEDBACK.json")
    sc = cs.Scorer(sat)
    row = {"family": "carry", "symbol": "XAUUSD", "params": {"hold_days": 5}, "selector": "asia"}
    s = sc.score_row(row)
    assert 0.0 < s["capacity_factor"] <= 1.0
    assert set(s["capacity_terms"]) == set(bcap.TERMS)
    ev = cs.stamp(_rows(10), sat, debt={})
    assert "terms_measured" in ev["capacity"]


# ------------------------------------------------------------------ the brief everywhere
def test_briefs_publish_read_back_and_go_stale(sat: dict, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(cs, "_debt_brief", lambda: {"mode": "ON", "empty_clusters": ["x"]})
    fb = {"producers": {"miner_z": {"rows": 10, "duplicate_share": 0.5, "state": "OK"}}}
    p = cs.publish_briefs(doc=sat, feedback=fb, path=tmp_path / "PRODUCER_BRIEFS.json")
    assert p is not None
    b = cs.brief_for("miner_z", path=p)
    assert b["own_recent_output"]["miner_z"]["duplicate_share"] == 0.5
    assert "book_context" in b and "desk_owns" in b
    lines = cs.brief_lines("miner_z", path=p)
    assert any("saturated" in ln for ln in lines) and any("your recent output" in ln
                                                          for ln in lines)
    assert cs.brief_for("miner_z", path=p, now=datetime.now(tz=UTC) + timedelta(hours=7)) == {}
    assert cs.brief_for("x", path=tmp_path / "absent.json") == {}


def test_every_producer_leg_is_handed_the_brief() -> None:
    import hourly_cycle as hc
    env = hc._brief_env("deep_forest")
    assert env["QUANT_PRODUCER_NAME"] == "deep_forest"
    assert env["QUANT_PRODUCER_BRIEF"].endswith("PRODUCER_BRIEFS.json")
    assert env["QUANT_PRODUCER_BRIEF_STATUS"] in ("MEASURED", "UNMEASURED")


def test_every_proposer_seat_prompt_carries_the_brief(sat: dict, tmp_path: Path,
                                                      monkeypatch) -> None:
    from libs.research import proposer_seat as ps
    monkeypatch.setattr(cs, "_debt_brief", lambda: {"mode": "OFF"})
    path = cs.publish_briefs(doc=sat, feedback={}, path=tmp_path / "PRODUCER_BRIEFS.json")
    monkeypatch.setattr(ps, "BREADTH_BRIEFS", path)
    import certificate_saturation as cs2
    monkeypatch.setattr(cs2, "_debt_brief", lambda: {"mode": "OFF"})
    seen: list[str] = []
    monkeypatch.setattr(ps, "enabled", lambda: True)
    monkeypatch.setattr(ps, "_ask", lambda role, prompt, timeout: (seen.append(prompt) or "",
                                                                  "m", None))
    organ = next(iter(ps.ORGANS))
    ps.propose(organ, role="generation", task="t", grammar="{}", n=1)
    assert seen and "breadth: desk holds" in seen[0]
    assert ps.breadth_context(organ, path=tmp_path / "absent.json") == []


# ------------------------------------------------------------------ the per-cluster cap, shadow
def _book(n: int) -> dict:
    return {"sleeves": [
        {"name": f"s{i}", "symbol": PAIRS[i % 7], "family": "session_range_breakout",
         "selector": "london", "status": "LIVE", "risk_frac": 0.004,
         "promoted_at": f"2026-09-{1 + i:02d}T00:00:00+00:00",
         "admission": {"delta_elogw_per_day": (1e-4 if i % 2 else None)}}
        for i in range(n)] + [{"name": "standby", "symbol": "EURUSD", "status": "STANDBY",
                               "family": "session_range_breakout", "selector": "london"}]}


def test_shadow_cap_counts_match_a_synthetic_book_and_never_change_a_promotion(
        sat: dict, tmp_path: Path) -> None:
    book = _book(9)
    before = copy.deepcopy(book)
    by: dict[str, list[str]] = {}
    for r in ccs.live_rows(book):
        by.setdefault(ccs.cluster_of(r), []).append(r["name"])
    cap = 1 + cs.CHALLENGERS
    expect = sum(max(0, len(v) - cap) for k, v in by.items()
                 if (sat["clusters"].get(k) or {}).get("state") == "SATURATED")
    doc = ccs.build(sat=sat, sleeves=book)
    assert doc["status"] == "MEASURED" and doc["enforced"] is False
    assert doc["n_live"] == 9 and doc["n_would_block"] == expect
    assert expect > 0, "the synthetic book saturates its cluster"
    assert book == before, "the shadow never changes a promotion"
    blocked = [b["sleeve"] for b in doc["would_block"]]
    names_by_order = [r["name"] for r in sorted(ccs.live_rows(book),
                                                key=lambda r: r["promoted_at"])]
    assert all(names_by_order.index(n) >= cap for n in blocked), "the latest promotions block"
    mg = doc["missed_growth"]
    assert mg["lines"] == expect and mg["measured"] + mg["unmeasured"] == expect
    for b in doc["would_block"]:
        line = b["missed_growth"]
        assert line["rail"] == ccs.RAIL and set(line) >= {"day", "rail", "value", "at"}
        if line["status"] == "MEASURED":
            assert line["value"] == pytest.approx(-1e-4)
        else:
            assert line["value"] is None and line["undeployed_risk_frac"] == 0.004
    assert "AUTOMATIC PROMOTION" in doc["reason"] and "Rule 1" in doc["reason"]
    p = ccs.publish(doc, tmp_path / "CLUSTER_CAP_SHADOW.json")
    ccs.publish(doc, p)
    ledger = (tmp_path / ccs.LEDGER.name).read_text("utf-8").splitlines()
    assert len(ledger) == expect, "one ledger line per blocked promotion per day"


def test_shadow_reads_the_promoter_file_read_only(sat: dict, tmp_path: Path,
                                                  monkeypatch) -> None:
    f = tmp_path / "sleeves.json"
    f.write_text(json.dumps(_book(6)), "utf-8")
    raw = f.read_bytes()
    monkeypatch.setattr(ccs, "SLEEVES", f)
    doc = ccs.build(sat=sat)
    assert doc["status"] == "MEASURED" and f.read_bytes() == raw


def test_coverage_has_the_shadow_state_and_names_other_owners(tmp_path: Path,
                                                              monkeypatch) -> None:
    assert blc.COVERED_SHADOW in blc.STATUSES
    doc = blc.build()
    r326 = next(r for r in doc["rows"] if r["id"] == "BREADTH-0326")
    assert r326["status"] == blc.COVERED_SHADOW and r326["where"]
    assert "Rule 1" in r326["note"] and "automatic promotion" in r326["note"]
    rows = {"rows": [{"id": "BREADTH-9001", "section": "S §1", "requirement": "r",
                      "audit_state": "ABSENT", "owner_thread": "Other thread"}]}
    rp = tmp_path / "rows.json"
    rp.write_text(json.dumps(rows), "utf-8")
    monkeypatch.setattr(blc, "CLASSIFICATION", ())
    one = blc.build(rows_path=rp, root=tmp_path)["rows"][0]
    assert one["status"] == blc.PARTIAL and one["raw_status"] == blc.MISSING
    assert "owned by Other thread" in one["note"]


def test_alpha_breadth_pass_publishes_briefs_and_the_shadow(sat: dict, tmp_path: Path,
                                                            monkeypatch) -> None:
    import alpha_breadth as ab
    monkeypatch.setattr(ab, "OUT", tmp_path / "EFFECTIVE_BREADTH.json")
    out = ab.breadth_debt_pass(sat)
    assert (tmp_path / "PRODUCER_BRIEFS.json").exists()
    assert (tmp_path / "CLUSTER_CAP_SHADOW.json").exists()
    assert out["cluster_cap_shadow"]["status"] in ("MEASURED", "UNMEASURED")
