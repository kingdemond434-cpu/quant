"""The nine closed-loop organs (Tier-1 B14-B25), on synthetic ground.

    cd desks/mt5 && python -m pytest tests/test_closed_loop_organs.py -q

Everything here runs off-box: synthetic registries, ledgers and chains under tmp_path, no
network, no tracked file written. WHAT MUST NOT REGRESS:

  1. B14 a source the collector never read is priced above a redundant one, and `fetch_order`
     never DROPS an id it has no price for
  2. B15 a trending series reads a trend-follower pressure with the trend's sign, and a symbol
     with no posterior still produces a conditioning row rather than nothing
  3. B17 a destroyer's view is a strict subset of the signals, fitness rewards a NOVEL kill
     above a duplicate one, and reproduction keeps the population size fixed
  4. B18 every corpus case names a registered probe, and the bench's verdict is REGRESSED as
     soon as one case is
  5. B19 a Merkle root moves when any leaf moves, and an edited chain row fails verification
  6. B20 a later start is refused, an earlier one accepted, and a new identity opens a new clock
     while the old one is kept
  7. B22 the intent->deal join measures a signed shortfall, and an unmeasured pool returns None
     rather than a zero cost
  8. B23 `chart_order` ranks measured charts first and keeps unmeasured ones
  9. B25 the ordering tournament scores on recorded seconds, and `ordering_kill_rates` is empty
     unless the measured policy actually won
 10. every new leg is declared in `libs.research.layers.LEG_LAYER` and wired in `hourly_cycle`
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research.layers import LEG_LAYER  # noqa: E402
from research import actor_pressure as ap  # noqa: E402
from research import clock_ledger as cl  # noqa: E402
from research import counterfactual_timeframes as ctf  # noqa: E402
from research import destroyer_pool as dp  # noqa: E402
from research import evidence_chain as ec  # noqa: E402
from research import meta_rnd as mr  # noqa: E402
from research import quantbench as qb  # noqa: E402
from research import shortfall_model as sm  # noqa: E402
from research import source_evig as se  # noqa: E402

NEW_LEGS = ("source_evig", "actor_pressure", "destroyer_pool", "quantbench", "evidence_chain",
            "clock_ledger", "shortfall_model", "counterfactual_timeframes", "meta_rnd")


# ----------------------------------------------------------------- B14 source EVIG
def test_evig_prefers_the_unread_source_over_the_redundant_one() -> None:
    sources = [
        {"id": "read_often", "targets": ["XAUUSD"], "cadence": "daily",
         "pit": {"publication_lag_days": 0}},
        {"id": "never_read", "targets": ["USDCNH"], "cadence": "daily",
         "pit": {"publication_lag_days": 0}},
        {"id": "duplicate", "targets": ["XAUUSD"], "cadence": "daily",
         "pit": {"publication_lag_days": 0}},
    ]
    state = {"read_often": {"last_status": "COLLECTED"}}
    rows = se.price(sources, state, {"XAUUSD": 1.0, "USDCNH": 1.0})
    rank = {r["id"]: r["rank"] for r in rows}
    assert rank["never_read"] < rank["duplicate"], "a novel target must outrank a covered one"
    assert next(r for r in rows if r["id"] == "duplicate")["novelty"] == 0.0
    assert next(r for r in rows if r["id"] == "never_read")["never_collected"] is True


def test_fetch_order_never_drops_an_unpriced_id(tmp_path: Path, monkeypatch) -> None:
    doc = {"rows": [{"id": "b", "rank": 0}, {"id": "a", "rank": 1}]}
    out = tmp_path / "SOURCE_EVIG.json"
    out.write_text(json.dumps(doc), encoding="utf-8")
    monkeypatch.setattr(se, "OUT", out)
    assert se.fetch_order(["a", "b", "unknown"]) == ["b", "a", "unknown"]
    monkeypatch.setattr(se, "OUT", tmp_path / "missing.json")
    assert se.fetch_order(["a", "b"]) == ["a", "b"], "no artifact leaves the order untouched"


# ----------------------------------------------------------------- B15 actor pressure
def test_trend_follower_reads_the_trend_sign() -> None:
    up = [100.0 * (1.0 + 0.001) ** i for i in range(400)]
    row = ap._trend_follower(up)
    assert row["status"] == "MEASURED"
    assert row["pressure"] > 0, "a rising series is trend-follower buying pressure"
    down = list(reversed(up))
    assert ap._trend_follower(down)["pressure"] < 0


def test_hints_for_publishes_rows_the_state_vector_can_merge(tmp_path: Path, monkeypatch) -> None:
    doc = {"by_symbol": {"XAUUSD": {"status": "MEASURED", "net_pressure": 0.4,
                                    "dominant_actor": "trend_follower",
                                    "crowded_with": ["trend_follower"], "crowded_against": [],
                                    "actors": {"trend_follower": {"status": "MEASURED",
                                                                  "pressure": 0.4,
                                                                  "crowding": 0.2,
                                                                  "basis": "test"}}}}}
    out = tmp_path / "ACTOR_PRESSURE.json"
    out.write_text(json.dumps(doc), encoding="utf-8")
    monkeypatch.setattr(ap, "OUT", out)
    hints = ap.hints_for(["XAUUSD", "EURUSD"])
    assert "EURUSD" not in hints, "a symbol with no measured row contributes nothing"
    nodes = [r["node"] for r in hints["XAUUSD"]]
    assert "actor:trend_follower" in nodes and "actor:net" in nodes
    assert all("weight" in r and r["source"] == "actor_pressure" for r in hints["XAUUSD"])


# ----------------------------------------------------------------- B17 destroyers
def test_a_view_is_a_subset_of_the_signals() -> None:
    signals = list(range(100))
    view = dp._view(signals, {"block_frac": 0.5, "block_len": 10}, seed=7)
    assert set(view) <= set(signals)
    assert 30 <= len(view) <= 70
    assert view == sorted(view), "blocks are kept in time order"


def test_a_novel_kill_outscores_a_duplicate_kill_and_the_population_is_fixed() -> None:
    report = {"per_certificate": {
        "cert_survived": {"status": "SURVIVED", "tests_run": ["cost_surface"], "kills": [],
                          "evolved": {"kills": ["d000"], "results": {
                              "d000": {"verdict": "FAIL", "seconds": 1.0},
                              "d001": {"verdict": "PASS", "seconds": 1.0}}}},
        "cert_killed": {"status": "KILLED", "tests_run": ["cost_surface"],
                        "kills": ["cost_surface"],
                        "evolved": {"kills": ["d001"], "results": {
                            "d001": {"verdict": "FAIL", "seconds": 1.0}}}},
    }}
    pool = dp.seed_pool()
    scored = dp.score(report, pool)
    assert scored["fitness"]["d000"]["novel_kills"] == 1
    assert scored["fitness"]["d001"]["novel_kills"] == 0
    assert scored["fitness"]["d000"]["fitness"] > scored["fitness"]["d001"]["fitness"]
    assert scored["prey"]["cert_survived"]["generations"] == 1
    before = len(pool["genomes"])
    ev = dp.reproduce(pool, scored["fitness"])
    assert len(pool["genomes"]) == min(before, dp.POP_SIZE)
    assert ev["n_offspring"] >= 1 and ev["generation"] == 1
    assert all(g["id"] for g in pool["genomes"])


# ----------------------------------------------------------------- B18 quantbench
def test_every_corpus_case_names_a_registered_probe() -> None:
    rows = qb.cases()
    assert rows, "the shipped corpus must hold cases"
    unknown = [r["id"] for r in rows if str(r.get("check")) not in qb.CHECKS]
    assert unknown == [], f"corpus cases with no probe: {unknown}"


def test_one_regressed_case_is_the_whole_benchs_verdict(tmp_path: Path, monkeypatch) -> None:
    corpus = tmp_path / "corpus.jsonl"
    corpus.write_text(json.dumps({"id": "T1", "check": "always_fails", "expect": {}}) + "\n",
                      encoding="utf-8")
    monkeypatch.setitem(qb.CHECKS, "always_fails", lambda _e: {"verdict": "REGRESSED",
                                                               "why": "synthetic"})
    doc = qb.build(path=corpus)
    assert doc["status"] == "REGRESSED" and doc["regressed"] == ["T1"]


def test_an_unregistered_probe_is_unmeasured_never_a_pass(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus.jsonl"
    corpus.write_text(json.dumps({"id": "T2", "check": "nope"}) + "\n", encoding="utf-8")
    doc = qb.build(path=corpus)
    assert doc["counts"] == {"UNMEASURED": 1} and doc["status"] == "OK"


# ----------------------------------------------------------------- B19 evidence chain
def test_a_moved_leaf_moves_the_root() -> None:
    rec = {"shadow_spec": {"symbol": "XAUUSD", "family": "f", "params": {"a": 1}},
           "gates": {"g1": {"passed": True}}, "days": 20}
    policy = {"version": "v1", "gates": ["g1"]}
    a = ec.manifest("c1", rec, policy)
    b = ec.manifest("c1", {**rec, "gates": {"g1": {"passed": False}}}, policy)
    assert a["merkle_root"] != b["merkle_root"]
    assert ec.manifest("c1", rec, policy)["merkle_root"] == a["merkle_root"], "hash is stable"


def test_an_edited_chain_row_fails_verification(tmp_path: Path, monkeypatch) -> None:
    chain = tmp_path / "chain.jsonl"
    monkeypatch.setattr(ec, "CERTS", tmp_path / "certs.json")
    monkeypatch.setattr(ec, "CANON", tmp_path / "canon.json")
    (tmp_path / "certs.json").write_text(json.dumps({
        "survivors": {"c1": {"shadow_spec": {"symbol": "XAUUSD", "family": "f", "params": {}},
                             "gates": {"g1": {"passed": True}}, "days": 20}},
        "gate_policy": {"version": "v1"}}), encoding="utf-8")
    doc = ec.build(chain_path=chain)
    assert doc["n_appended"] == 1 and doc["chain"]["verdict"] == "INTACT"
    rows = ec.read_chain(chain)
    rows[0]["merkle_root"] = "0" * 64
    chain.write_text(json.dumps(rows[0]) + "\n", encoding="utf-8")
    assert ec.verify(ec.read_chain(chain))["verdict"] == "BROKEN"


# ----------------------------------------------------------------- B20 immutable clocks
def test_a_later_start_is_refused_and_an_earlier_one_accepted(tmp_path: Path) -> None:
    led = tmp_path / "ledger.json"
    first = cl.stamp("k", "id-a", "2026-01-01T00:00:00+00:00", path=led)
    assert first["opened_new_clock"] is True
    later = cl.stamp("k", "id-a", "2026-02-01T00:00:00+00:00", path=led)
    assert later["start"] == first["start"] and later["refused"] is True
    earlier = cl.stamp("k", "id-a", "2025-12-01T00:00:00+00:00", path=led)
    assert earlier["start"] < first["start"] and earlier["refused"] is False
    assert cl.start_for("k", "id-a", path=led) == earlier["start"]


def test_a_new_identity_opens_a_new_clock_and_keeps_the_old(tmp_path: Path) -> None:
    led = tmp_path / "ledger.json"
    cl.stamp("k", "id-a", "2026-01-01T00:00:00+00:00", path=led)
    fresh = cl.stamp("k", "id-b", "2026-03-01T00:00:00+00:00", path=led)
    assert fresh["opened_new_clock"] is True and fresh["supersedes"]
    doc = json.loads(led.read_text(encoding="utf-8"))
    kept = [r for r in doc["clocks"].values() if r.get("closed")]
    assert len(kept) == 1 and kept[0]["start"] == "2026-01-01T00:00:00+00:00"


def test_an_empty_identity_adopts_the_existing_clock(tmp_path: Path) -> None:
    led = tmp_path / "ledger.json"
    cl.stamp("k", "", "2026-01-01T00:00:00+00:00", path=led)
    adopted = cl.stamp("k", "id-a", "2026-05-01T00:00:00+00:00", path=led)
    assert adopted["opened_new_clock"] is False
    assert adopted["start"] == "2026-01-01T00:00:00+00:00"


# ----------------------------------------------------------------- B22 shortfall
def test_the_ticket_join_measures_a_signed_shortfall() -> None:
    intents = [{"ticket": 1, "symbol": "XAUUSD", "side": "buy", "intended": 100.0, "lot": 0.1,
                "time": "2026-09-01T10:00:00+00:00"},
               {"ticket": 2, "symbol": "XAUUSD", "side": "sell", "intended": 100.0, "lot": 0.1,
                "time": "2026-09-01T10:00:00+00:00"}]
    deals = [{"entry_order": 1, "entry_price": 100.1, "symbol": "XAUUSD"},
             {"order": 2, "entry_price": 100.1, "symbol": "XAUUSD"}]
    fills = sm.join(intents, deals)
    assert len(fills) == 2
    buy = next(f for f in fills if f["ticket"] == 1)
    sell = next(f for f in fills if f["ticket"] == 2)
    assert buy["shortfall_frac"] == pytest.approx(0.001, rel=1e-6), "paying up is positive"
    assert sell["shortfall_frac"] == pytest.approx(-0.001, rel=1e-6), "selling higher is a gain"


def test_an_unmeasured_pool_returns_none_not_a_zero_cost() -> None:
    doc = {"model": {"pooled": {"n": 1, "mean": 0.01, "verdict": "UNMEASURED", "min_pool": 8},
                     "cells": {}}}
    mu, why = sm.expected_shortfall("XAUUSD", 10, 0.1, "market", doc=doc)
    assert mu is None and "floor" in why


def test_a_thin_cell_is_shrunk_toward_the_pool() -> None:
    fills = [{"symbol": "XAUUSD", "session": "london", "size_bucket": "xs<=0.05",
              "order_type": "market", "shortfall_frac": 0.01}]
    fills += [{"symbol": "EURUSD", "session": "asia", "size_bucket": "xs<=0.05",
               "order_type": "market", "shortfall_frac": 0.0} for _ in range(9)]
    model = sm.fit(fills)
    cell = model["cells"]["XAUUSD|london|xs<=0.05|market"]
    assert cell["verdict"] == "UNMEASURED" and cell["n"] == 1
    assert abs(cell["shrunk_mean"]) < 0.01, "one fill is mostly the pooled number"


# ----------------------------------------------------------------- B23 timeframes
def test_chart_order_puts_measured_charts_first(tmp_path: Path, monkeypatch) -> None:
    out = tmp_path / "CTF.json"
    out.write_text(json.dumps({"per_chart": {
        "M5": {"verdict": "MEASURED", "mean": 0.2},
        "M15": {"verdict": "MEASURED", "mean": -0.1},
        "M30": {"verdict": "UNMEASURED", "mean": None}}}), encoding="utf-8")
    monkeypatch.setattr(ctf, "OUT", out)
    assert ctf.chart_order("XAUUSD", ["M15", "M30", "M5"]) == ["M5", "M15", "M30"]
    monkeypatch.setattr(ctf, "OUT", tmp_path / "missing.json")
    assert ctf.chart_order("XAUUSD", ["M15", "M5"]) == ["M15", "M5"]


# ----------------------------------------------------------------- B25 meta R&D
def test_the_ordering_tournament_scores_on_recorded_seconds() -> None:
    rows = [{"cert_id": f"c{i}", "premortem_class": "COST_DEATH",
             "results": {"cost_surface": {"verdict": "FAIL", "seconds": 0.5},
                         "placebo_battery": {"verdict": "PASS", "seconds": 20.0},
                         "truncation": {"verdict": "PASS", "seconds": 2.0}}}
            for i in range(6)]
    out = mr.replay_orderings(rows, {"COST_DEATH": 0.9})
    assert set(out) == set(mr.POLICIES)
    assert all(r["verdict"] == "MEASURED" for r in out.values())
    assert out["premortem_first"]["mean_seconds_to_verdict"] == pytest.approx(0.5)
    assert out["premortem_first"]["n_killed"] == 6


def test_ordering_kill_rates_is_empty_unless_the_measured_policy_won(tmp_path: Path,
                                                                    monkeypatch) -> None:
    out = tmp_path / "META_RND.json"
    out.write_text(json.dumps({"ordering": {"applied_policy": "catalogue_prior",
                                            "measured_kill_rates": {"LEAKAGE": 0.4}}}),
                   encoding="utf-8")
    monkeypatch.setattr(mr, "OUT", out)
    assert mr.ordering_kill_rates() == {}
    out.write_text(json.dumps({"ordering": {"applied_policy": "measured_kill_rates",
                                            "measured_kill_rates": {"LEAKAGE": 0.4}}}),
                   encoding="utf-8")
    assert mr.ordering_kill_rates() == {"LEAKAGE": 0.4}


def test_the_threshold_subject_is_measured_and_never_applied() -> None:
    block = mr.threshold_variants()
    assert block["applied"] is False
    assert "REFUSED IN BOTH DIRECTIONS" in block["why_not_applied"]


# ----------------------------------------------------------------- wiring (LAWS 7)
@pytest.mark.parametrize("leg", NEW_LEGS)
def test_every_new_leg_is_declared_and_wired(leg: str) -> None:
    assert leg in LEG_LAYER, f"{leg} has no layer: opportunity_cost cannot attribute its hour"
    src = (_DESK / "research" / "hourly_cycle.py").read_text(encoding="utf-8", errors="replace")
    assert f'_costed("{leg}"' in src, f"{leg} has no leg in the hourly cycle"
    assert f'"{leg}":' in src, f"{leg} is missing from the cycle's results dict"
