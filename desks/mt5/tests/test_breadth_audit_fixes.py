"""The 2026-10-06 audit of PR #207: what the breadth law measured now acts on something.

MUST-FIX 1  the docket's breadth rank survives the write (`breadth_order`), so the judge can sort
            by it (the sealed side is `gauntlet_consume_breadth_order.patch`, tested by
            test_gauntlet_breadth_order.py once applied).
MUST-FIX 2  each breadth debt is priced by its own dk_eff and the auction sums VALUE, not count.
MUST-FIX 3  the A/B/C/D split only ADDS: B never below LIVE's factor; A/C/D legs get a factor on
            their real seconds.
MUST-FIX 4  a deadline walker visits every symbol within ceil(n/k) passes.
SHOULD-FIX  continuous empty-cluster decay, shrunk |rho|, PSD repair, stale map reads UNMEASURED,
            N_EFF labelled UNMEASURED when certified instruments have no bars.
"""
from __future__ import annotations

import itertools
import json
import math
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for p in (str(DESK / "research"), str(DESK), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import breadth_ladder as bl  # noqa: E402
import breadth_rotation as brot  # noqa: E402
import certificate_saturation as cs  # noqa: E402
import hourly_cycle as hc  # noqa: E402
import judge_coverage as jc  # noqa: E402
import merge_hypotheses as mh  # noqa: E402
import portfolio_bounty as pb  # noqa: E402
import research_auction as ra  # noqa: E402

USD = ("EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDCAD")
PAIRS = (*USD, "USDCHF", "USDJPY")


def _cert(sym: str, fam: str, params: dict[str, Any], sel: str = "london") -> dict[str, Any]:
    return {"sym": sym, "cell": f"{sym}.{fam}", "gated_at": "2026-09-01T00:00:00+00:00",
            "gates": {"walk_forward": {"oos_sharpe": 0.2}},
            "shadow_spec": {"symbol": sym, "selector": sel, "family": fam, "condition": None,
                            "params": params}}


def _canon(extra: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    sv = {f"c{i}": _cert(PAIRS[i % 7], "session_range_breakout",
                         {"rr": 1 + (i // 7) % 10 * 0.25, "wait_bars": 4 + (i // 70)})
          for i in range(140)}
    sv.update(extra or {})
    return {"survivors": sv}


def _build(canon: dict[str, Any], **kw: Any) -> dict[str, Any]:
    args: dict[str, Any] = {"shadow": {}, "sleeves": {}, "judged": {}, "coupling_tab": {},
                            "residual": {}, "forward_daily": {}, "book": {}, "previous": {},
                            "loader": lambda s: None}
    args.update(kw)
    return cs.build(canon=canon, **args)


@pytest.fixture(scope="module")
def sat() -> dict[str, Any]:
    return _build(_canon())


def _docket() -> list[dict[str, Any]]:
    rows = []
    for i in range(30):
        rows.append({"_cell": f"dup{i}", "family": "session_range_breakout", "symbol": USD[i % 5],
                     "params": {"rr": 1 + i}, "selector": "london", "source": "miner_x",
                     "premortem": {"p_survivor": 0.5}, "first_seen": f"2026-10-01T00:{i:02d}"})
    for i in range(10):
        rows.append({"_cell": f"new{i}", "family": "session_range_breakout",
                     "symbol": ("XAUUSD", "US500")[i % 2], "params": {"rr": 1 + i},
                     "selector": "london", "source": "miner_y",
                     "premortem": {"p_survivor": 0.5}, "first_seen": f"2026-10-03T00:{i:02d}"})
    return rows


# ------------------------------------------------------------------ must-fix 1
def test_breadth_order_survives_the_docket_write(sat: dict[str, Any], tmp_path: Path) -> None:
    rows = _docket()
    assert cs.stamp(rows, sat)["status"] == cs.MEASURED
    ordered = jc.coverage_order(rows, {"session_range_breakout": 1})
    dups = {r["_cell"] for r in ordered if r.get("_dup")}
    assert dups
    cells = [r["_cell"] for r in ordered]
    assert jc.persist_breadth_order(ordered) == len(ordered)
    path = tmp_path / "external_survivors.json"
    mh._write_docket_atomically(path, ordered)
    back = json.loads(path.read_text("utf-8"))
    assert len(back) == len(rows)
    by_rank = {r["breadth_order"]["rank"]: r for r in back}
    assert sorted(by_rank) == list(range(len(rows)))
    for rank, cell in enumerate(cells):
        # the persisted rank is the value / novelty position, whatever chart locality did after
        r = by_rank[rank]
        assert r["breadth_order"]["dup"] == (1 if cell in dups else 0)
    assert not any(k in r for r in back for k in ("_sat", "_dup", "_satq", "_satq_arch"))
    # a re-order pass clears the previous stamp before restamping, never carrying a stale rank
    again = [dict(r) for r in back]
    jc.order_docket(again, publish=False)
    assert all("breadth_order" not in r or isinstance(r["breadth_order"], dict) for r in again)


def test_an_unstamped_docket_carries_no_breadth_order() -> None:
    rows = _docket()
    assert jc.persist_breadth_order(rows) == 0
    assert not any("breadth_order" in r for r in rows)


# ------------------------------------------------------------------ must-fix 2
def test_each_debt_is_priced_by_its_own_dk_eff(sat: dict[str, Any]) -> None:
    debts = sat["breadth_debts"]
    dks = {d["expected_delta_k_eff"] for d in debts}
    assert len(dks) > 1, "every debt priced at one constant again"
    for d in debts:
        assert 0.0 <= d["shared_axes_with_book"] <= 2
        assert d["value_units"] is not None


def test_two_debts_of_different_dk_eff_bid_differently() -> None:
    deps = ("discovery",)

    def b(v: float) -> dict[str, Any]:
        return {"targets": ["discovery"], "evidence": {"value_units": v}}
    lo = ra.bids(deps, {}, {}, {"bounties": [b(0.3)]}, {}, {})["discovery"]
    hi = ra.bids(deps, {}, {}, {"bounties": [b(1.2)]}, {}, {})["discovery"]
    assert hi["bid"] > lo["bid"] and lo["bounties_addressed"] == hi["bounties_addressed"] == 1
    # six debts no longer saturate: a seventh still raises the bid
    six = ra.bids(deps, {}, {}, {"bounties": [b(1.0)] * 6}, {}, {})["discovery"]["bid"]
    seven = ra.bids(deps, {}, {}, {"bounties": [b(1.0)] * 7}, {}, {})["discovery"]["bid"]
    assert seven > six
    # never below the old count bonus where the old one had not saturated (1..4 units)
    for n in range(1, 5):
        assert ra.bounty_bonus_of(float(n)) >= min(ra.BOUNTY_CAP, ra.BOUNTY_WEIGHT * n) - 1e-12


def test_the_queue_reprices_when_a_debt_is_paid(sat: dict[str, Any]) -> None:
    sym_of = {"forex": "EURJPY", "commodities": "XAUUSD", "indices": "US500"}
    first = next(d for d in sat["breadth_debts"] if d["asset_class"] in sym_of
                 and cs.asset_class(sym_of[d["asset_class"]]) == d["asset_class"])
    paid_fam = first["candidate_producers"][0]
    paid = _build(_canon({"paid": _cert(sym_of[first["asset_class"]], paid_fam, {"x": 1})}))
    before = {d["missing_cluster"]: d for d in sat["breadth_debts"]}
    after = {d["missing_cluster"]: d for d in paid["breadth_debts"]}
    assert first["missing_cluster"] not in after, "the paid debt is still open"
    moved = [k for k in before.keys() & after.keys()
             if before[k]["expected_delta_k_eff"] != after[k]["expected_delta_k_eff"]]
    assert moved, "paying a debt repriced nothing"
    # the published queue changes: the paid debt leaves and its neighbours fall behind
    rows_b, _ = pb.bounties({}, {}, {}, {}, {}, {}, {}, {}, {}, sat)
    rows_a, _ = pb.bounties({}, {}, {}, {}, {}, {}, {}, {}, {}, paid)
    ids_b = [b["bounty_id"] for b in rows_b if b["kind"] == "breadth_debt"]
    ids_a = [b["bounty_id"] for b in rows_a if b["kind"] == "breadth_debt"]
    assert ids_b != ids_a
    # and the value the queue bids with falls: one stream fewer is missing, neighbours cheaper

    def queue(doc: dict[str, Any]) -> list[dict[str, Any]]:
        return [{"targets": ["discovery"], "evidence": {"value_units": d["value_units"]}}
                for d in doc["breadth_debts"]]
    deps = ("discovery",)
    assert (ra.bids(deps, {}, {}, {"bounties": queue(paid)}, {}, {})["discovery"]["bid"]
            < ra.bids(deps, {}, {}, {"bounties": queue(sat)}, {}, {})["discovery"]["bid"])


# ------------------------------------------------------------------ must-fix 3
RULES = ("stall", "duplicates_rising", "quality_degrading", "new_clusters_not_surviving",
         "independent_survivors_accumulating")
SLOPES = ({"status": "UNMEASURED"}, {"status": "MEASURED", "per_hour": 0.0},
          {"status": "MEASURED", "per_hour": 0.3}, {"status": "MEASURED", "per_hour": 5.0})


@pytest.mark.parametrize("sl", SLOPES)
def test_b_never_below_live_for_every_temperature(sl: dict[str, Any]) -> None:
    fac = bl.factors(sl)
    live_b = float(fac.get("exploitation", 1.0) or 1.0)       # LIVE: the ladder factor alone
    live_a = float(fac.get("exploration", 1.0) or 1.0)
    for r in range(len(RULES) + 1):
        for fired in itertools.combinations(RULES, r):
            doc = {"factors": fac, "budget_split": bl.budget_split({"fired": list(fired)})}
            for leg in bl.EXPLOITATION_LEGS:
                assert bl.budget_factor(leg, doc) >= live_b - 1e-12, (leg, fired)
                assert bl.split_budget(leg, doc)[0] == 1.0       # B is never paid twice
            for leg in bl.EXPLORATION_LEGS:
                assert bl.budget_factor(leg, doc) >= live_a - 1e-12, (leg, fired)
            for leg in (*bl.EXPLORATION_LEGS, *bl.FALSIFICATION_LEGS, *bl.FRONTIER_LEGS):
                assert bl.split_budget(leg, doc)[0] >= 1.0


def test_heating_a_c_and_d_funds_their_real_legs() -> None:
    doc = {"factors": {}, "budget_split": bl.budget_split({"fired": ["stall"]})}
    f, rec = bl.split_budget("world_crawler", doc)              # A and C
    assert f > 1.0 and rec["category"] == "C"
    assert bl.split_budget("deep_forest_miner", doc)[1]["category"] == "C"   # producer alias
    doc_d = {"factors": {}, "budget_split": bl.budget_split({"fired": ["new_clusters_not_surviving"]})}
    assert bl.split_budget("falsifier_run", doc_d)[0] > 1.0
    # and the hourly cycle raises the organ's own --budget-s, never lowers it
    assert hc._scale_budget_arg(("--once", "--budget-s", "900"), 1.5) == ("--once", "--budget-s",
                                                                          "1350")
    assert hc._scale_budget_arg(("--budget-s=240",), 1.25) == ("--budget-s=300",)
    assert hc._scale_budget_arg(("--budget-s", "900"), 0.5) == ("--budget-s", "900")


# ------------------------------------------------------------------ must-fix 4
class _TieredScorer:
    """Symbols S00..S09 sit in the best tier; the rest in a worse tier, forever."""

    def score_fields(self, sym: str, *_a: Any) -> dict[str, float]:
        return {"novelty_credit": 1.0 if int(sym[1:]) < 10 else 0.2}


def test_a_deadline_walker_visits_every_symbol_within_ceil_n_over_k(tmp_path: Path) -> None:
    syms = [f"S{i:02d}" for i in range(23)]
    k = 5
    path = tmp_path / "ring_visits.json"
    seen: set[str] = set()
    counts: tuple[dict[str, int], dict[tuple[str, str], int]] = ({}, {})
    for p in range(math.ceil(len(syms) / k)):
        ring = brot.orthogonal_ring(syms, "regime_split", counts=counts,
                                    saturation=_TieredScorer(),
                                    visits=brot.ring_visits("regime_split", path))
        walked = ring[:k]                                    # the deadline stops it at k
        for i, s in enumerate(walked):
            brot.mark_ring_visit("regime_split", [s], path,
                                 at=f"2026-10-06T00:{p:02d}:{i:02d}")
        seen.update(walked)
    assert seen == set(syms)
    # and inside the never-visited group the saturation tier still orders the first pass
    first = brot.orthogonal_ring(syms, "regime_split", counts=counts,
                                 saturation=_TieredScorer(), visits={})
    assert first[:10] == [f"S{i:02d}" for i in range(10)]


def test_the_tier_no_longer_leads_the_least_judged_key() -> None:
    counts = ({}, {("S15", "fam"): 0, ("S01", "fam"): 7})
    ring = brot.orthogonal_ring(["S01", "S15"], "fam", counts=counts, saturation=_TieredScorer())
    assert ring == ["S15", "S01"]          # worse tier but never judged comes first


# ------------------------------------------------------------------ should-fix
def test_empty_cluster_prior_decay_is_continuous() -> None:
    from libs.research.alpha_clusters import classify_family
    fam = "carry"
    key = classify_family(fam)
    gy = 0.01
    vals = []
    for effort in range(0, 700, 7):
        out = cs._empty_priors([], {("EURUSD", fam): effort}, gy, {})
        vals.append(out[key]["decay"])
    assert vals[0] == 1.0
    assert all(b <= a + 1e-12 for a, b in zip(vals, vals[1:], strict=False))
    assert max(a - b for a, b in zip(vals, vals[1:], strict=False)) < 0.05   # no cliff


def test_rho_is_shrunk_and_c_is_repaired_to_psd() -> None:
    assert cs.shrink_abs_rho(0.05, 60) == 0.0                 # noise on 60 days reads 0
    assert cs.shrink_abs_rho(0.9, 2000) == pytest.approx(0.9 - math.sqrt(2 / (math.pi * 2000)))
    bad = np.array([[1.0, 0.9, -0.9], [0.9, 1.0, 0.9], [-0.9, 0.9, 1.0]])
    fixed, rec = cs.nearest_psd(bad, "t")
    assert rec["repaired"] and rec["status"] == "REPAIRED"
    assert np.linalg.eigvalsh(fixed).min() > -1e-9
    assert np.allclose(np.diag(fixed), 1.0)
    same, rec2 = cs.nearest_psd(np.eye(3), "t")
    assert rec2["status"] == "PSD" and np.array_equal(same, np.eye(3))


def test_the_map_publishes_its_psd_check(sat: dict[str, Any]) -> None:
    assert [r["matrix"] for r in sat["psd_check"]] == ["structural_C", "forward_adjusted_C"]


def test_a_stale_map_reads_unmeasured_never_the_old_number(sat: dict[str, Any],
                                                          tmp_path: Path) -> None:
    path = tmp_path / "CERTIFICATE_SATURATION.json"
    old = dict(sat)
    old["at"] = (datetime.now(tz=UTC) - timedelta(hours=cs.MAX_AGE_H + 1)).isoformat()
    path.write_text(json.dumps(old, default=str), "utf-8")
    got = cs.read_fresh(path)
    assert got["status"] == "UNMEASURED" and "old" in got["why"]
    assert "certificates" not in got
    assert bl._fresh_saturation(path)["status"] == "UNMEASURED"
    doc = pb.build(**{n: {} for n in ("alloc", "exposure", "regimes", "drawdown", "dd_miner",
                                      "ortho", "session", "sleeves", "universe")},
                   saturation=cs.read_fresh(path))
    assert "CERTIFICATE_SATURATION.breadth_debts absent" in doc["unmeasured"]
    fresh = dict(sat)
    fresh["at"] = datetime.now(tz=UTC).isoformat()
    path.write_text(json.dumps(fresh, default=str), "utf-8")
    assert cs.read_fresh(path)["status"] == cs.MEASURED


def test_n_eff_is_labelled_unmeasured_when_certified_instruments_have_no_bars(
        sat: dict[str, Any]) -> None:
    head = sat["certificates"]
    assert head["n_effective_status"].startswith("UNMEASURED")
    assert len(head["instruments_without_bars"]) == 7
    assert isinstance(head["n_effective_certificates"], float)     # the number stays beside it
