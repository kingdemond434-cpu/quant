"""Hypothesis families: breadth in independent families, duplicates re-aimed and never deleted."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import hypothesis_families as hf  # noqa: E402
from research import judge_coverage as jc  # noqa: E402

MECH = "Dealers hedging short gamma into the close push price toward the strike; it reverts."


def _row(sym: str, fam: str = "range_reversion", tf: str = "H1", day: str = "2026-10-01",
         **params: object) -> dict:
    return {"symbol": sym, "family": fam, "params": {"timeframe": tf, **params},
            "first_seen": f"{day}T00:00:00+00:00", "mechanism_note": MECH,
            "producer": "miner_candidates.json"}


CL = {"EURUSD": "EURUSD", "GBPUSD": "EURUSD", "USDJPY": "USDJPY", "XAUUSD": "XAUUSD"}


def test_threshold_variants_collapse_to_one_rule_and_comoving_symbols_to_one_family() -> None:
    rows = [_row("EURUSD", lookback=20), _row("EURUSD", lookback=40),
            _row("GBPUSD", lookback=20), _row("USDJPY", lookback=20)]
    doc = hf.census(rows, CL, detail=100)
    assert doc["raw_cells"] == 4
    assert doc["l1_rules"] == 3            # EURUSD rule, GBPUSD rule, USDJPY rule
    assert doc["l2_families"] == 2         # {EURUSD, GBPUSD} co-move -> one family; USDJPY
    assert doc["duplicate_share_l2"] == 0.5
    assert doc["k_eff_readings"]["families_upper_bound"] == 2
    assert doc["k_eff"] == round(16 / (9 + 1), 3)   # inverse Simpson of cells 3 and 1


def test_an_unmeasured_symbol_is_its_own_cluster() -> None:
    rows = [_row("EURUSD"), _row("AUDNZD")]
    assert hf.census(rows, {}, detail=10)["l2_families"] == 2


def test_label_only_mechanism_is_flagged_and_counted_never_discarded() -> None:
    a = _row("EURUSD")
    b = {**_row("USDJPY", fam="jump"), "mechanism_note": "volatility_shock"}
    doc = hf.census([a, b], CL, detail=10)
    assert doc["raw_cells"] == 2
    assert doc["mechanism"]["missing_families"] == 1
    assert doc["mechanism"]["label_only_families"] == 1
    flags = {r["key"].split("|")[0]: r["mechanism_flag"] for r in doc["families"]}
    assert flags == {"range_reversion": None, "jump": "LABEL_ONLY"}
    good = next(r for r in doc["families"] if r["key"].startswith("range_reversion"))
    assert good["mechanism"].startswith("Dealers hedging short gamma")


def test_daily_metric_counts_new_independent_cells_and_families_net_of_duplicates() -> None:
    rows = [_row("EURUSD", day="2026-10-01"), _row("USDJPY", day="2026-10-01"),
            _row("EURUSD", day="2026-10-02", lookback=99),   # NEAR: same rule, mined before
            _row("GBPUSD", day="2026-10-02"),                # new rule, same family as EURUSD
            _row("XAUUSD", day="2026-10-02")]                # new rule, new family
    d = {x["day"]: x for x in hf.daily(rows, CL)["days"]}
    assert d["2026-10-01"] == {"day": "2026-10-01", "raw_cells": 2, "new_independent_cells": 2,
                               "new_independent_families": 2, "reaimed_cells": 0,
                               "duplicate_share": 0.0}
    assert d["2026-10-02"]["raw_cells"] == 3
    assert d["2026-10-02"]["new_independent_cells"] == 2
    assert d["2026-10-02"]["new_independent_families"] == 1
    assert d["2026-10-02"]["duplicate_share"] == round(1 - 2 / 3, 4)


def test_reaim_keeps_every_duplicate_and_adds_a_child_on_empty_lawful_ground() -> None:
    bank = [_row("EURUSD"), _row("USDJPY", fam="carry"), _row("XAUUSD")]
    dup = _row("EURUSD", lookback=55)          # NEAR the banked EURUSD rule
    rows = [*bank, dup]
    fresh = {hf.identity(dup)}
    children, rep = hf.reaim(rows, fresh, set(), clusters=CL, lawful=lambda s, f: True)
    assert rep["by_status"]["NEAR"] == 1
    assert rep["mint_conservation"]["removed"] == 0
    assert dup in rows and dup["dup_status"] == "NEAR"
    # range_reversion runs on EURUSD and XAUUSD; EURUSD's cluster holds the rule, XAUUSD does
    # too -> no empty target. Add GBPUSD (same cluster as EURUSD) and AUDNZD (empty).
    bank2 = [*bank, _row("AUDNZD", lookback=1)]
    bank2[-1]["params"]["session"] = "asia"      # a different rule on AUDNZD
    rows2 = [*bank2, dup]
    children, rep = hf.reaim(rows2, fresh, set(), clusters=CL, lawful=lambda s, f: True)
    assert [c["symbol"] for c in children] == ["AUDNZD"]
    assert children[0]["params"] == dup["params"]
    assert children[0]["reaimed_from"]["parent_identity"] == hf.identity(dup)
    assert rep["reaimed"] == 1


def test_reaim_respects_the_lane_order_and_happens_once_per_parent() -> None:
    bank = [_row("EURUSD"), _row("AUDNZD", session="asia")]
    dup = _row("EURUSD", lookback=7)
    rows = [*bank, dup]
    fresh = {hf.identity(dup)}
    none, rep = hf.reaim(rows, fresh, set(), clusters=CL, lawful=lambda s, f: s != "AUDNZD")
    assert none == [] and rep["no_lawful_empty_target"] == 1
    kids, _ = hf.reaim(rows, fresh, set(), clusters=CL, lawful=lambda s, f: True)
    assert len(kids) == 1
    again, rep2 = hf.reaim(rows + kids, set(), {hf.identity(dup)}, clusters=CL,
                           lawful=lambda s, f: True)
    assert again == [] and rep2["already_reaimed_parents"] == 1
    assert rep2["by_status"]["EXACT"] == 1


def test_inheritance_is_only_where_statistically_honest() -> None:
    rep, twin = _row("EURUSD", lookback=20), _row("EURUSD", lookback=20)
    sib = _row("GBPUSD", lookback=30)
    assert hf.inheritable({"passed": True}, rep, twin, CL)            # exact twin: anything
    assert not hf.inheritable({"passed": True}, rep, sib, CL)         # a PASS never
    assert hf.inheritable({"terminal_gate": "economic_prior"}, rep, sib, CL)
    assert not hf.inheritable({"terminal_gate": "deflated_sharpe"}, rep, sib, CL)
    assert not hf.inheritable({"terminal_gate": "symbol_eligibility"}, rep, sib, CL)
    assert not hf.inheritable({"terminal_gate": "economic_prior"}, rep, _row("USDJPY"), CL)


def test_family_split_marks_first_claim_and_coverage_order_reads_it() -> None:
    old, new = _row("EURUSD", day="2026-09-01"), _row("GBPUSD", day="2026-10-01")
    other = _row("USDJPY", day="2026-10-05")
    rows = [new, other, old]
    out = hf.family_split(rows, None, CL)
    assert out["family_representatives"] == 2 and out["family_members"] == 1
    assert (old["_famdup"], new["_famdup"], other["_famdup"]) == (0, 1, 0)
    ordered = jc.coverage_order(rows, {"range_reversion": 3}, None)
    assert ordered.index(other) < ordered.index(new)
    legacy = jc.coverage_order(rows, {"range_reversion": 3}, None, use_families=False)
    assert len(legacy) == len(ordered) == 3


def test_symbol_clusters_are_leader_clusters_on_daily_correlation() -> None:
    idx = pd.date_range("2024-01-01", periods=400, freq="D")
    rng = np.random.default_rng(7)
    base = pd.Series(rng.normal(size=400), index=idx)
    series = {"AAA": base, "BBB": base * 0.9 + pd.Series(rng.normal(size=400), index=idx) * 0.1,
              "CCC": pd.Series(rng.normal(size=400), index=idx)}
    doc = hf.derive_clusters(["CCC", "AAA", "BBB", "ZZZ"], series.get)
    assert doc["cluster_of"] == {"AAA": "AAA", "BBB": "AAA", "CCC": "CCC", "ZZZ": "ZZZ"}
    assert doc["unmeasured"] == ["ZZZ"]


def test_returns_merge_groups_correlated_families_only() -> None:
    k = [f"2026-01-{i:02d}" for i in range(1, 31)]
    a = {s: float(i % 5) for i, s in enumerate(k)}
    b = {s: float(i % 5) * 2 + 0.01 for i, s in enumerate(k)}
    c = {s: float((i * 7) % 11) for i, s in enumerate(k)}
    g = hf.returns_merge({"fa": a, "fb": b, "fc": c})
    assert g["fb"] == "fa" and g["fc"] == "fc"


def test_apply_never_removes_a_row_and_publishes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(hf, "CLUSTERS", tmp_path / "clusters.json")
    monkeypatch.setattr(hf, "REAIM_LEDGER", tmp_path / "reaim.jsonl")
    monkeypatch.setattr(hf, "_daily", lambda s, u: None)
    rows = [_row("EURUSD"), _row("EURUSD", lookback=3)]
    out, block = hf.apply(rows, fresh={hf.identity(rows[1])}, reproposed=set(),
                          report_path=tmp_path / "HF.json")
    assert len(out) >= len(rows) and all(r in out for r in rows)
    assert block["raw_cells"] == len(out)
    assert block["intake"]["by_status"]["NEAR"] == 1
    assert (tmp_path / "HF.json").exists()
    assert hf._RULE_CACHE is None


def test_detail_budget_is_derived_and_floored() -> None:
    assert hf.detail_budget(10) == 10
    assert hf.detail_budget(0) == 0
    assert hf.detail_budget(10**9) >= 2000
