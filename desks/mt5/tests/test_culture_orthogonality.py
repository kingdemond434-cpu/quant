"""Cross-culture orthogonality: does a different culture produce a different edge?

research/culture_orthogonality.py pairs survivors that share a mechanism and differ in culture,
measures them on live + forward daily R over the SAME dates, and calls each pair DIVERGE,
SAME_EDGE or UNMEASURED. Consumers: docket_keff counts a merge group once; pf_allocator relabels
the mechanism cap's families (merge -> one family, proven divergence -> its own) without moving
the total heat; the occupancy_map leg runs it hourly.
"""
from __future__ import annotations

import contextlib
import inspect
import json
import math
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import culture_orthogonality as co  # noqa: E402

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)


def _days(n: int, start: date = date(2026, 6, 1)) -> list[str]:
    return [(start + timedelta(days=i)).isoformat() for i in range(n)]


def _series(n: int, seed: int, days: list[str] | None = None) -> dict[str, float]:
    rng = np.random.default_rng(seed)
    return dict(zip(days or _days(n), rng.standard_normal(n).tolist(), strict=True))


# ------------------------------------------------------------------------------ the pair test
def test_independent_series_diverge() -> None:
    m = co.measure_pair(_series(80, 1), _series(80, 2))
    assert m["verdict"] == co.DIVERGE
    assert m["overlap_days"] == 80 and m["co_active_days"] == 80
    assert abs(m["rho"]) < co.SAME_EDGE_RHO


def test_one_edge_under_two_names_is_same_edge() -> None:
    a = _series(80, 3)
    noise = _series(80, 4)
    b = {d: v + 0.3 * noise[d] for d, v in a.items()}
    m = co.measure_pair(a, b)
    assert m["verdict"] == co.SAME_EDGE
    assert m["rho"] > 0.9
    assert m["co_loss_lift"] > 1.5 and m["dd_jaccard"] > 0.5


def test_too_few_overlap_days_is_unmeasured_never_a_verdict() -> None:
    short = co.measure_pair(_series(20, 5), _series(20, 6))
    assert short["verdict"] == co.UNMEASURED and short["overlap_days"] == 20
    # A long common window with the sleeves never trading on the same day is also unmeasured.
    days = _days(90)
    a = {d: 1.0 if i % 3 else -1.0 for i, d in enumerate(days) if i % 2 == 0}
    b = {d: 1.0 if i % 5 else -1.0 for i, d in enumerate(days) if i % 2 == 1}
    apart = co.measure_pair(a, b)
    assert apart["verdict"] == co.UNMEASURED and apart["co_active_days"] == 0
    # Windows that do not overlap at all.
    late = _series(60, 7, _days(60, date(2026, 9, 1)))
    assert co.measure_pair(_series(60, 8), late)["verdict"] == co.UNMEASURED
    assert co.measure_pair({}, _series(60, 9))["verdict"] == co.UNMEASURED


def test_merge_groups_are_components_of_the_same_edge_graph() -> None:
    pairs = [{"a": "x", "b": "y", "verdict": co.SAME_EDGE},
             {"a": "y", "b": "z", "verdict": co.SAME_EDGE},
             {"a": "p", "b": "q", "verdict": co.DIVERGE},
             {"a": "p", "b": "r", "verdict": co.UNMEASURED}]
    groups = co.merge_groups(pairs)
    assert [g["members"] for g in groups] == [["x", "y", "z"]]
    k = co.keff_merged(["x", "y", "z", "p", "q", "r"], groups)
    assert k == {"nominal": 6, "merged": 4, "collapsed": 2}


# ------------------------------------------------------------------------------ culture
def test_culture_is_declared_then_derived_then_unmeasured() -> None:
    idx = {"seat": {"boj_timeseries": "JP"}, "host": {"www.7hcn.com": "CN"}}
    assert co.row_culture({"source_culture": "KR/ko"}, idx)[:2] == ("KR", "declared")
    assert co.row_culture({"contributing_sources": ["asia:boj_timeseries"]}, idx)[:2] == \
        ("JP", "derived")
    assert co.row_culture({"source_url": "https://www.7hcn.com/a"}, idx)[0] == "CN"
    assert co.row_culture({"source_url": "https://www.cbr.ru/x"}, idx)[0] == "RU"
    assert co.row_culture({"source_url": "https://www.b3.com.br/x"}, idx)[0] == "BR"
    assert co.row_culture({"source_url": "https://sa.gov.sa/x"}, idx)[0] == "ARABIC"
    assert co.row_culture({"source_title": "東京時間の逆張り"}, idx)[0] == "JP"
    assert co.row_culture({"source_url": "https://www.myfxbook.com/x"}, idx)[:2] == \
        (None, co.UNMEASURED)


# ------------------------------------------------------------------------------ the whole test
def _world() -> dict[str, Any]:
    """Four certified survivors of ONE mechanism (session_range_breakout): JP and CN trade one
    edge under two names, KR trades an independent one, and one has no provenance at all."""
    fam = "session_range_breakout"
    canon = {"survivors": {}}
    docket = []
    specs = [("USDJPY", {"rr": 1.5, "wait_bars": 12}, {"source_culture": "JP/ja"}),
             ("EURJPY", {"rr": 1.5, "wait_bars": 12},
              {"contributing_sources": ["asia:cfets_fixing"]}),
             ("KRWUSD", {"rr": 2.0, "wait_bars": 12},
              {"source_url": "https://ecos.bok.or.kr/api", "participant_structure": "retail_heavy",
               "failure_mode_hypothesis": "KRX retail fade", "crowding_prior": "low"}),
             ("GBPJPY", {"rr": 1.5, "wait_bars": 12}, {})]
    for sym, params, prov in specs:
        key = f"external.{sym}.{fam}.rr={params['rr']}_wb={params['wait_bars']}"
        canon["survivors"][key] = {"cell": key, "sym": sym, "shadow_spec": {
            "symbol": sym, "family": fam, "selector": "asia", "params": params}}
        docket.append({"symbol": sym, "family": fam, "params": params, **prov})
    base = _series(90, 11)
    noise = _series(90, 12)
    fwd = {
        co.norm(f"external.USDJPY.{fam}.rr=1.5_wb=12"): base,
        co.norm(f"external.EURJPY.{fam}.rr=1.5_wb=12"): {d: v + 0.2 * noise[d]
                                                         for d, v in base.items()},
        co.norm(f"external.KRWUSD.{fam}.rr=2.0_wb=12"): _series(90, 13),
        co.norm(f"external.GBPJPY.{fam}.rr=1.5_wb=12"): _series(90, 14),
    }
    idx = {"seat": {"cfets_fixing": "CN"}, "host": {}}
    return {"canon": canon, "docket": docket, "fwd": fwd, "idx": idx, "sleeves": {"sleeves": []},
            "shadow": {}, "live": {}}


def _doc(**over: Any) -> dict[str, Any]:
    w = _world()
    kw = {"canon": w["canon"], "sleeves": w["sleeves"], "shadow": w["shadow"],
          "docket": w["docket"], "fwd": w["fwd"], "live": w["live"], "idx": w["idx"],
          "cell_index": {}, "now": NOW}
    kw.update(over)
    return co.build(**kw)


def test_build_pairs_cross_culture_survivors_and_publishes_merge_groups() -> None:
    doc = _doc()
    by = {s["symbol"]: s for s in doc["survivors"]}
    assert by["USDJPY"]["culture"] == "JP" and by["USDJPY"]["culture_source"] == "declared"
    assert by["EURJPY"]["culture"] == "CN" and by["EURJPY"]["culture_source"] == "derived"
    assert by["KRWUSD"]["culture"] == "KR"
    assert by["KRWUSD"]["participant_structure"] == "retail_heavy"
    assert by["KRWUSD"]["crowding_prior"] == "low"
    assert by["GBPJPY"]["culture"] == co.UNMEASURED
    # Only culture-bearing survivors of one mechanism pair: JP-CN, JP-KR, CN-KR.
    assert doc["pair_counts"] == {"total": 3, co.DIVERGE: 2, co.SAME_EDGE: 1, co.UNMEASURED: 0}
    [group] = doc["merge_groups"]
    assert group["cultures"] == ["CN", "JP"]
    assert doc["k_eff_survivors"] == {"nominal": 4, "merged": 3, "collapsed": 1}
    assert doc["per_culture"]["KR"]["independent_edges_proven"] == 1
    assert doc["per_culture"]["JP"]["edges_shared_with_another_culture"] == 1
    assert by["KRWUSD"]["label"]["family"] == "session_range_breakout@KR"
    assert by["USDJPY"]["label"] == by["EURJPY"]["label"]
    assert doc["status"] == "MEASURED"
    assert datetime.fromisoformat(doc["at"]) == NOW


def test_short_history_stays_unmeasured_and_merges_nothing() -> None:
    w = _world()
    short = {k: dict(list(v.items())[:12]) for k, v in w["fwd"].items()}
    doc = _doc(fwd=short)
    assert doc["pair_counts"][co.UNMEASURED] == 3
    assert doc["merge_groups"] == [] and doc["status"] == co.UNMEASURED
    assert all("label" not in s for s in doc["survivors"])


def test_cell_culture_index_overrides_derivation() -> None:
    cid = "EURJPY.session_range_breakout.rr=1.5_wb=12"
    doc = _doc(cell_index={cid: {"source_culture": "RU/ru", "participant_structure":
                                 "policy_driven", "crowding_prior": "high"}})
    s = next(x for x in doc["survivors"] if x["symbol"] == "EURJPY")
    assert s["culture"] == "RU" and s["culture_source"] == "declared"
    assert s["participant_structure"] == "policy_driven" and s["crowding_prior"] == "high"


def test_crowding_prior_survival_uses_wilson_and_needs_n() -> None:
    idx = {f"L{i}": {"crowding_prior": "low"} for i in range(60)}
    idx.update({f"H{i}": {"crowding_prior": "high"} for i in range(60)})
    judged = set(idx)
    certified = {f"L{i}" for i in range(30)} | {"H0"}
    out = co.crowding_survival(idx, judged, certified)
    assert out["verdict"] == "LOW_SURVIVES_MORE"
    lo, hi = out["by_crowding_prior"]["low"]["wilson_95"]
    assert lo < 0.5 < hi
    small = co.crowding_survival({"a": {"crowding_prior": "low"}}, {"a"}, {"a"})
    assert small["verdict"] == co.UNMEASURED
    assert co.crowding_survival(idx, None, certified)["status"] == co.UNMEASURED
    lo2, hi2 = co.wilson(0, 10)
    assert lo2 == 0.0 and 0 < hi2 < 1


def test_live_ledger_names_are_truncated_prefixes(tmp_path: Path) -> None:
    ledger = tmp_path / "live.jsonl"
    rows = [{"sleeve": "eurchf_discovered_asia_p_16", "time": "2026-09-07T17:00:00+00:00",
             "r_multiple": 0.0, "pl_quote": 10.0, "risk_quote": -20.0},
            {"sleeve": "[tp 1.23]", "time": "2026-09-07T17:00:00+00:00", "r_multiple": 1.0}]
    ledger.write_text("\n".join(json.dumps(r) for r in rows), "utf-8")
    fwd, live = co.load_series(tmp_path, ledger)
    assert fwd == {} and list(live) == ["eurchf_discovered_asia_p_16"]
    s = {"names": ["eurchf_discovered_asia_p_16bd35526c7f3515"]}
    ser, src = co.survivor_series(s, fwd, live)
    assert src == "live" and ser == {"2026-09-07": 0.5}


def test_load_refuses_a_stale_artifact(tmp_path: Path) -> None:
    p = tmp_path / "c.json"
    co.write({"at": (NOW - timedelta(hours=10)).isoformat()}, p)
    assert co.load(p, now=NOW)[0] is None
    co.write({"at": NOW.isoformat()}, p)
    assert co.load(p, now=NOW)[0] is not None


# ------------------------------------------------------------------------------ consumers
def test_docket_keff_counts_a_merge_group_once() -> None:
    from research import docket_keff as dk
    doc = _doc()
    rows = [{"family": "session_range_breakout", "symbol": "USDJPY"},
            {"family": "session_range_breakout", "symbol": "KRWUSD"}]
    out = dk.score(rows, read_artifacts=False, loader=lambda s: None, culture=doc)
    assert out["culture"]["survivors_nominal"] == 4
    assert out["culture"]["survivors_k_merged"] == 3
    gid = doc["merge_groups"][0]["group_id"]
    assert out["_terms"]["session_range_breakout|USDJPY"]["culture_merge_group"] == gid
    assert out["_terms"]["session_range_breakout|KRWUSD"]["culture_merge_group"] is None
    none = dk.score([dict(r) for r in rows], read_artifacts=False, loader=lambda s: None)
    assert none["culture"]["status"] == co.UNMEASURED


def test_allocator_labels_join_on_symbol_family_selector() -> None:
    doc = _doc()
    labels = co.allocator_labels(doc, [
        ("USDJPY_session_range_breakout_asia", "USDJPY", "session_range_breakout", "asia"),
        ("EURJPY_session_range_breakout_asia", "EURJPY", "session_range_breakout", "asia"),
        ("KRWUSD_session_range_breakout_asia", "KRWUSD", "session_range_breakout", "asia"),
        ("GBPJPY_session_range_breakout_asia", "GBPJPY", "session_range_breakout", "asia")])
    fams = {k: v["family"] for k, v in labels.items()}
    assert fams["USDJPY_session_range_breakout_asia"] == \
        fams["EURJPY_session_range_breakout_asia"]
    assert fams["USDJPY_session_range_breakout_asia"].startswith("culture_merge:")
    assert fams["KRWUSD_session_range_breakout_asia"] == "session_range_breakout@KR"
    assert "GBPJPY_session_range_breakout_asia" not in labels


def test_allocator_relabel_is_heat_neutral() -> None:
    """The cap's families change; the resolved total the book holds does not."""
    pa = pytest.importorskip("research.pf_allocator")
    from research.heat_policy import enforce_family_cap

    from libs.portfolio.robust_elog import SleeveEvidence, WorldConfig, optimise, sample_worlds

    rng = np.random.default_rng(0)

    def sl(name: str, sym: str, mu: float) -> SleeveEvidence:
        r = (rng.standard_normal(500) + mu) * (rng.random(500) < 0.3)
        return SleeveEvidence(name=name, daily_r=r, symbol=sym,
                              family="session_range_breakout", forward_days=60,
                              mechanism="session_range_breakout asia")

    ev = [sl("USDJPY_session_range_breakout_asia", "USDJPY", 0.3),
          sl("EURJPY_session_range_breakout_asia", "EURJPY", 0.25),
          sl("KRWUSD_session_range_breakout_asia", "KRWUSD", 0.2),
          SleeveEvidence(name="XAUUSD_carry_asia", daily_r=rng.standard_normal(500) * 0.3 + 0.05,
                         symbol="XAUUSD", family="carry", forward_days=60, mechanism="carry")]
    target = 0.20
    cfg = WorldConfig(seed=0, n_worlds=48, n_rows=96)

    def solve(evs: list[Any], family_of: dict[str, str]) -> float:
        worlds = sample_worlds(evs, cfg)
        book = optimise(evs, hard_cap=0.30, target=target, cfg=cfg, worlds=worlds,
                        max_per_sleeve=0.2, iterations=60)
        ub = dict.fromkeys(family_of, 0.2)
        capped = enforce_family_cap(book.heat, family_of, book.total_heat)
        tight = {k: min(ub[k], capped.get(k, math.inf)) for k in ub}
        with contextlib.suppress(ValueError):
            book = optimise(evs, hard_cap=0.30, target=target, cfg=cfg, worlds=worlds,
                            max_per_sleeve=tight, warm_start=book.heat, iterations=60)
        book, _ = pa.fill_floor(book, evs, target, ub, family_of, cfg=cfg, worlds=worlds)
        return float(sum(book.heat.values()))

    before = solve(list(ev), {e.name: e.family for e in ev})
    relabelled = list(ev)
    family_of, meta = pa.apply_culture_labels(relabelled, _doc())
    assert meta["merged"] == 2 and meta["split"] == 1
    assert family_of["KRWUSD_session_range_breakout_asia"] == "session_range_breakout@KR"
    assert [e.name for e in relabelled] == [e.name for e in ev]
    assert all(np.array_equal(a.daily_r, b.daily_r) for a, b in zip(ev, relabelled, strict=True))
    assert relabelled[0].mechanism == relabelled[1].mechanism != ev[0].mechanism
    after = solve(relabelled, family_of)
    assert before == pytest.approx(target, abs=1e-6)
    assert after == pytest.approx(target, abs=1e-6)
    # An artifact with nothing measured relabels nothing.
    same, none = pa.apply_culture_labels(list(ev), {"status": co.UNMEASURED, "survivors": []})
    assert none["relabelled"] == {} and same == {e.name: e.family for e in ev}


def test_allocator_run_uses_the_culture_families_and_publishes_them() -> None:
    pa = pytest.importorskip("research.pf_allocator")
    src = inspect.getsource(pa.run)
    assert "culture_family, culture_meta = apply_culture_labels(ev)" in src
    assert "family_of = {e.name: culture_family.get(e.name, e.family) for e in ev}" in src
    assert '"culture_labels": culture_meta' in src


def test_the_occupancy_leg_runs_the_culture_pass() -> None:
    from research import occupancy_map as om
    src = inspect.getsource(om.main)
    assert "culture_pass(docket, dry_run=a.dry_run)" in src
    out = om.culture_pass([], dry_run=True)
    assert out["status"] in ("MEASURED", co.UNMEASURED)
    assert out["report"].endswith("CULTURE_ORTHOGONALITY.json")
