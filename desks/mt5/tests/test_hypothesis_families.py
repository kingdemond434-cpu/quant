"""Hypothesis families: breadth in independent families, duplicates re-aimed and never deleted."""

from __future__ import annotations

import json
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


def NOBLOCK(spec: dict) -> bool:
    return False


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


def test_categorical_params_are_structure_and_thresholds_still_collapse() -> None:
    """exit_operated on base_family=breakout and base_family=carry are two rules, not a duplicate;
    a nested numeric threshold (base_params.lookback) still collapses; a re-aim keeps the
    categorical part, so the L2 family key moves only the instrument."""
    a = _row("EURUSD", "exit_operated", base_family="breakout", exit_on_anchor_flip=True,
             base_params={"lookback": 20, "mode": "close"}, rr="1.5")
    b = _row("EURUSD", "exit_operated", base_family="carry", exit_on_anchor_flip=True,
             base_params={"lookback": 20, "mode": "close"}, rr="1.5")
    c = _row("EURUSD", "exit_operated", base_family="breakout", exit_on_anchor_flip=False,
             base_params={"lookback": 20, "mode": "close"}, rr="1.5")
    a2 = _row("EURUSD", "exit_operated", base_family="breakout", exit_on_anchor_flip=True,
              base_params={"lookback": 60, "mode": "close"}, rr="2.5")
    assert len({hf.rule_key(r) for r in (a, b, c)}) == 3
    assert hf.rule_key(a) == hf.rule_key(a2)
    # the structural cell itself is untouched (judge_coverage ordering reads it as before)
    assert jc.structural_cell(a) == jc.structural_cell(b)
    assert hf.rule_key(a).startswith(jc.structural_cell(a) + "|")
    # a row with no categorical params keeps judge_coverage's key exactly
    plain = _row("EURUSD", lookback=20)
    assert hf.rule_key(plain) == jc.structural_cell(plain)
    assert hf.categorical_suffix(plain) == ""
    g = _row("GBPUSD", "exit_operated", base_family="breakout", exit_on_anchor_flip=True,
             base_params={"lookback": 20, "mode": "close"}, rr="1.5")
    assert hf.family_key(a, CL) == hf.family_key(g, CL) != hf.family_key(b, CL)
    doc = hf.census([a, b, c, a2], CL, detail=100)
    assert doc["l1_rules"] == 3


def test_provenance_params_are_not_structure_and_expr_literals_collapse() -> None:
    """The audit's must-fix: one executable rule from two populations (or two genome narratives)
    is ONE L1 rule; a formula whose expression differs only by numeric literals is one too."""
    a = _row("EURUSD", "formula", expr="decay(sum(div(open,open),240),8)", population="zoo")
    b = _row("EURUSD", "formula", expr="decay(sum(div(open,open),120),5)", population="bayesian",
             mechanism_genome={"driver": "flow"}, crossed_slot="driver", claim_id="c-17")
    c = _row("EURUSD", "formula", expr="decay(sum(div(close,open),240),8)", population="zoo")
    assert hf.rule_key(a) == hf.rule_key(b)
    assert hf.rule_key(a) != hf.rule_key(c)
    # an identifier's digits are not a threshold, and input_source is read by the engine
    assert hf.categorical_suffix(_row("EURUSD", "x", base_family="ma20")) != hf.categorical_suffix(
        _row("EURUSD", "x", base_family="ma50"))
    assert hf.categorical_suffix(_row("EURUSD", "x", input_source="cot")) != ""


def _family_kwargs() -> set[str]:
    import importlib
    import inspect
    import pkgutil

    import mt5desk
    from mt5desk import families

    fns: list[object] = [e["func"] for e in families.FAMILY_REGISTRY.values()]
    for m in pkgutil.iter_modules(mt5desk.__path__):
        try:
            mod = importlib.import_module(f"mt5desk.{m.name}")
        except Exception:
            continue        # a box-only module (gateway: MetaTrader5) defines no family
        fns += [v for k, v in vars(mod).items() if k.startswith("family") and callable(v)
                and getattr(v, "__module__", "") == mod.__name__]
    try:
        from mt5desk.executables import hunt16_families
        fns += list(hunt16_families().values())
    except Exception:
        pass
    out: set[str] = set()
    for fn in fns:
        try:
            sig = inspect.signature(fn)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        out |= {p.name for p in sig.parameters.values()
                if p.kind in (p.KEYWORD_ONLY, p.POSITIONAL_OR_KEYWORD)}
    return out


def test_no_family_kwarg_is_ever_treated_as_provenance() -> None:
    """A later family that grows a `title` or `reason` kwarg fails here instead of silently
    collapsing its distinct rules into one L1 cell (audit 2026-10-28: `label`, `source`)."""
    kwargs = _family_kwargs()
    assert len(kwargs) > 100                       # the families were actually reached
    dropped = {k for k in kwargs if not hf._structural_param(k) and k not in hf._AXIS_PARAMS}
    assert dropped <= hf._DISCARDED_KWARGS, sorted(dropped)
    src = (Path(hf.__file__).resolve().parents[1] / "mt5desk" / "family_formula.py").read_text(
        encoding="utf-8")
    assert "del population" in src                 # the one exception is still discarded
    assert hf.categorical_suffix(_row("EURUSD", "clock_transition", label="tokyo_open")) != \
        hf.categorical_suffix(_row("EURUSD", "clock_transition", label="comex_settle"))


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
    children, rep = hf.reaim(rows, fresh, set(), clusters=CL, lawful=lambda s, f: True,
                             blocked=NOBLOCK, done=set())
    assert rep["by_status"]["NEAR"] == 1
    assert rep["mint_conservation"]["removed"] == 0
    assert dup in rows and dup["dup_status"] == "NEAR"
    # range_reversion runs on EURUSD and XAUUSD; EURUSD's cluster holds the rule, XAUUSD does
    # too -> no empty target. Add GBPUSD (same cluster as EURUSD) and AUDNZD (empty).
    bank2 = [*bank, _row("AUDNZD", lookback=1)]
    bank2[-1]["params"]["session"] = "asia"      # a different rule on AUDNZD
    rows2 = [*bank2, dup]
    children, rep = hf.reaim(rows2, fresh, set(), clusters=CL, lawful=lambda s, f: True,
                             blocked=NOBLOCK, done=set())
    assert [c["symbol"] for c in children] == ["AUDNZD"]
    assert children[0]["params"] == dup["params"]
    assert children[0]["reaimed_from"]["parent_identity"] == hf.identity(dup)
    assert rep["reaimed"] == 1


def test_reaim_respects_the_lane_order_and_happens_once_per_parent() -> None:
    bank = [_row("EURUSD"), _row("AUDNZD", session="asia")]
    dup = _row("EURUSD", lookback=7)
    rows = [*bank, dup]
    fresh = {hf.identity(dup)}
    none, rep = hf.reaim(rows, fresh, set(), clusters=CL, lawful=lambda s, f: s != "AUDNZD",
                         blocked=NOBLOCK, done=set())
    assert none == [] and rep["no_lawful_empty_target"] == 1
    kids, _ = hf.reaim(rows, fresh, set(), clusters=CL, lawful=lambda s, f: True,
                       blocked=NOBLOCK, done=set())
    assert len(kids) == 1
    # the ledger, not the docket, remembers: even with the child GONE from the rows (filtered
    # by order_docket), a parent the ledger names is never re-aimed again
    again, rep2 = hf.reaim(list(rows), set(), {hf.identity(dup)}, clusters=CL,
                           lawful=lambda s, f: True, blocked=NOBLOCK,
                           done={hf.identity(dup)})
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
    assert doc["cluster_of"] == {"AAA": "AAA", "BBB": "AAA", "CCC": "CCC", "ZZZ": "?ZZZ"}
    assert doc["unmeasured"] == ["ZZZ"]
    # the budget is WORK, not wall-clock: identical on any machine, any load
    capped = hf.derive_clusters(["CCC", "AAA", "BBB"], series.get, max_loads=2)
    assert capped["cluster_of"] == {"AAA": "AAA", "BBB": "AAA", "CCC": "?CCC"}
    assert capped["work"]["loads"] == 2


def test_returns_merge_groups_correlated_families_only() -> None:
    k = [f"2026-01-{i:02d}" for i in range(1, 31)]
    a = {s: float(i % 5) for i, s in enumerate(k)}
    b = {s: float(i % 5) * 2 + 0.01 for i, s in enumerate(k)}
    c = {s: float((i * 7) % 11) for i, s in enumerate(k)}
    g = hf.returns_merge({"fa": a, "fb": b, "fc": c})
    assert g["fb"] == "fa" and g["fc"] == "fc"


def test_apply_writes_nothing_until_commit_then_report_then_ledger(tmp_path: Path,
                                                                   monkeypatch) -> None:
    monkeypatch.setattr(hf, "_daily", lambda s, u: None)
    monkeypatch.setattr(hf, "_lawful", lambda: (lambda s, f: True))
    monkeypatch.setattr(hf, "_unrunnable", lambda: NOBLOCK)
    rows = [_row("EURUSD"), _row("XAUUSD", session="asia"), _row("EURUSD", lookback=3)]
    out, block, pending = hf.apply(rows, fresh={hf.identity(rows[2])}, reproposed=set(),
                                   report_path=tmp_path / "HF.json", hyp_dir=tmp_path)
    assert pending is not None and all(r in out for r in rows)
    assert block["raw_cells"] == len(out) == 4 and block["intake"]["reaimed"] == 1
    assert not (tmp_path / "HF.json").exists() and not (tmp_path / "reaim_ledger.jsonl").exists()
    got = pending.commit(out)
    assert got == {"children": 1, "durable": 1, "report_written": True, "ledger_lines": 1,
                   "why": None}
    assert (tmp_path / "HF.json").exists()
    assert hf.reaimed_parents(tmp_path / "reaim_ledger.jsonl") == {hf.identity(rows[2])}
    assert hf._RULE_CACHE is None


def _two_passes(tmp_path: Path, monkeypatch, *, written_first: bool, blocked: bool,
                commit_first: bool) -> tuple[int, int]:
    """Pass 1 then pass 2 of the merge's re-aim; returns (children pass 1, children pass 2)."""
    monkeypatch.setattr(hf, "_daily", lambda s, u: None)
    monkeypatch.setattr(hf, "_lawful", lambda: (lambda s, f: True))
    bank = [_row("EURUSD"), _row("XAUUSD", session="asia")]
    dup = _row("EURUSD", lookback=3)
    monkeypatch.setattr(hf, "_unrunnable", lambda: NOBLOCK)
    out1, _, p1 = hf.apply([*bank, dup], fresh={hf.identity(dup)}, reproposed=set(),
                           report_path=tmp_path / "HF.json", hyp_dir=tmp_path)
    kids1 = [r for r in out1 if r.get("reaimed_from")]
    # what the docket writer actually wrote: order_docket may have filtered the child out
    written = out1 if written_first else [r for r in out1 if not r.get("reaimed_from")]
    if commit_first:
        assert p1 is not None
        p1.commit(written)
    # pass 2: the producer re-emits the same duplicate (EXACT); the bank is what was written
    bank2 = [dict(r) for r in written]
    if blocked:
        # the child's target is now in the judge's unrunnable bank
        monkeypatch.setattr(hf, "_unrunnable", lambda: (lambda sp: sp["symbol"] == "XAUUSD"))
    out2, _, _ = hf.apply(bank2, fresh=set(), reproposed={hf.identity(dup)},
                          report_path=tmp_path / "HF.json", hyp_dir=tmp_path)
    return len(kids1), sum(1 for r in out2 if r.get("reaimed_from")) - sum(
        1 for r in bank2 if r.get("reaimed_from"))


def test_probe_p2_a_second_pass_remints_nothing_after_the_child_was_filtered(
        tmp_path: Path, monkeypatch) -> None:
    # child minted, durable and ledgered, then filtered out of the docket by a later pass
    n1, n2 = _two_passes(tmp_path, monkeypatch, written_first=True, blocked=False,
                         commit_first=True)
    assert (n1, n2) == (1, 0)
    bank = json.loads(json.dumps([_row("EURUSD"), _row("XAUUSD", session="asia")]))
    dup = _row("EURUSD", lookback=3)
    out3, block3, _ = hf.apply([*bank, dup], fresh=set(), reproposed={hf.identity(dup)},
                               report_path=tmp_path / "HF.json", hyp_dir=tmp_path)
    assert not any(r.get("reaimed_from") for r in out3)        # child NOT in rows, ledger wins
    assert block3["intake"]["reaimed"] == 0


def test_probe_p2_an_unrunnable_target_is_never_minted(tmp_path: Path, monkeypatch) -> None:
    # pass 1's child was filtered (unrunnable) before it was written: no ledger line; pass 2
    # sees the bank and skips the target instead of re-minting it every hour
    n1, n2 = _two_passes(tmp_path, monkeypatch, written_first=False, blocked=True,
                         commit_first=True)
    assert (n1, n2) == (1, 0)
    assert not (tmp_path / "reaim_ledger.jsonl").exists()


def test_crash_after_the_docket_write_before_the_ledger_mints_nothing_twice(
        tmp_path: Path, monkeypatch) -> None:
    # the child reached the docket, then the process died before commit: no ledger line.
    n1, n2 = _two_passes(tmp_path, monkeypatch, written_first=True, blocked=False,
                         commit_first=False)
    assert (n1, n2) == (1, 0)      # pass 2 reads the child's parent out of the docket


def test_crash_before_the_docket_write_leaves_no_ledger_claim(tmp_path: Path,
                                                             monkeypatch) -> None:
    n1, n2 = _two_passes(tmp_path, monkeypatch, written_first=False, blocked=False,
                         commit_first=False)
    assert (n1, n2) == (1, 1)      # the child never existed; minting it once now is correct
    assert not (tmp_path / "reaim_ledger.jsonl").exists()


def test_a_failed_report_write_never_leaves_the_ledger_claiming_children(
        tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(hf, "_daily", lambda s, u: None)
    monkeypatch.setattr(hf, "_lawful", lambda: (lambda s, f: True))
    monkeypatch.setattr(hf, "_unrunnable", lambda: NOBLOCK)
    rows = [_row("EURUSD"), _row("XAUUSD", session="asia"), _row("EURUSD", lookback=3)]
    out, _, pending = hf.apply(rows, fresh={hf.identity(rows[2])}, reproposed=set(),
                               report_path=tmp_path / "HF.json", hyp_dir=tmp_path)
    monkeypatch.setattr(hf, "write", lambda doc, path=None: False)
    assert pending is not None
    got = pending.commit(out)
    assert got["report_written"] is False and got["ledger_lines"] == 0
    assert not (tmp_path / "reaim_ledger.jsonl").exists()


def test_atomic_write_replaces_a_read_only_destination(tmp_path: Path) -> None:
    import os
    import stat
    p = tmp_path / "R.json"
    p.write_text("old", "utf-8")
    os.chmod(p, stat.S_IREAD)
    assert hf._atomic_write(p, "new") is True
    assert p.read_text("utf-8") == "new"
    assert not list(tmp_path.glob(".R.json.*.tmp"))


def test_the_lane_law_fails_closed(monkeypatch) -> None:
    monkeypatch.setattr(hf, "_lawful", lambda: None)
    bank = [_row("EURUSD"), _row("XAUUSD", session="asia")]
    dup = _row("EURUSD", lookback=3)
    kids, rep = hf.reaim([*bank, dup], {hf.identity(dup)}, set(), clusters=CL,
                         blocked=NOBLOCK, done=set())
    assert kids == [] and rep["fail_closed"] == ["lane law (universe_policy) unavailable"]
    assert rep["by_status"]["NEAR"] == 1                    # the check still ran and counted


def test_a_child_claims_no_source_agreement_it_does_not_have() -> None:
    bank = [_row("EURUSD"), _row("XAUUSD", session="asia")]
    dup = {**_row("EURUSD", lookback=3), "n_independent_sources": 4,
           "contributing_sources": ["a", "b", "c", "d"], "contested": True}
    kids, _ = hf.reaim([*bank, dup], {hf.identity(dup)}, set(), clusters=CL,
                       lawful=lambda s, f: True,
                             blocked=NOBLOCK, done=set())
    assert kids[0]["n_independent_sources"] == 0 and kids[0]["contributing_sources"] == []
    assert "contested" not in kids[0]
    assert kids[0]["reaimed_from"]["parent_n_independent_sources"] == 4


def test_an_unmeasured_instrument_does_not_outrank_a_measured_family() -> None:
    cl = {"EURUSD": "EURUSD", "GBPUSD": "EURUSD", "AUDNZD": "?AUDNZD"}
    first = _row("EURUSD", day="2026-09-01")
    nobars = _row("AUDNZD", day="2026-10-01")                 # same rule shape, no bars
    nobars_new_rule = _row("AUDNZD", day="2026-10-02", session="asia")
    rows = [nobars, nobars_new_rule, first]
    out = hf.family_split(rows, None, cl)
    assert (first["_famdup"], nobars["_famdup"], nobars_new_rule["_famdup"]) == (0, 1, 0)
    assert out["rows_on_unmeasured_instruments"] == 2
    # the breadth COUNT still gives the unmeasured instrument its own family
    assert hf.census([first, nobars], cl, detail=10)["l2_families"] == 2


def test_the_report_is_capped_and_summarises_the_rest() -> None:
    rows = [_row("EURUSD", fam=f"fam{i}") for i in range(2100)]
    doc = hf.census(rows, CL)
    assert doc["families_published"] == hf.DETAIL_FAMILIES == 2000
    assert doc["families_summarised"] == 100
    assert sum(b["families"] for b in doc["family_size_bands"].values()) == 2100


def test_detail_budget_is_derived_and_floored() -> None:
    assert hf.detail_budget(10) == 10
    assert hf.detail_budget(0) == 0
    assert hf.detail_budget(10**9) >= 2000


def _tree_state() -> dict[str, float]:
    """mtime of every file under the desk's data/ and reports/ (the dirs a merge can touch)."""
    out: dict[str, float] = {}
    for d in (_DESK / "data", _DESK / "reports"):
        for p in d.rglob("*"):
            if p.is_file():
                out[str(p)] = p.stat().st_mtime
    return out


def test_the_docket_writer_runs_the_census_and_reaims_every_hour(monkeypatch, tmp_path) -> None:
    from research import merge_hypotheses as mh
    hyp = tmp_path / "hypotheses"
    hyp.mkdir()
    target = hyp / "external_survivors.json"
    banked = [_row("EURUSD", fam="session_range_breakout", session="asia"),
              _row("XAUUSD", fam="session_range_breakout", session="london")]
    target.write_text(json.dumps(banked), "utf-8")
    fresh = {"hypotheses": [_row("EURUSD", fam="session_range_breakout", session="asia",
                                 range_hours=5)]}
    (hyp / "miner_candidates.json").write_text(json.dumps(fresh), "utf-8")
    monkeypatch.setattr(mh, "HYP", hyp)
    monkeypatch.setattr(mh, "TARGET", target)
    monkeypatch.setattr(mh, "tradeable_universe", lambda: {})
    monkeypatch.setattr(mh, "_pipeline_started_at", lambda: None)
    # EVERY PATH IN tmp_path (audit of 8628268b6): no desk file may be written by this test.
    monkeypatch.setattr(mh, "_ack", lambda path: None)
    monkeypatch.setattr(mh, "_lease", lambda path: None)
    from libs.research import claim_selection as cs
    monkeypatch.setattr(cs, "LEDGER", hyp / "claim_families.json")
    # order_docket owns JUDGE_COVERAGE.json, the ratchet and the bank; stand it in, and FILTER
    # nothing here (the filtered case is the P2 tests above)
    monkeypatch.setattr(jc, "order_docket", lambda rows, **k: (rows, {}))
    monkeypatch.setattr(hf, "_daily", lambda s, u: None)
    monkeypatch.setattr(hf, "_lawful", lambda: (lambda s, f: True))
    monkeypatch.setattr(hf, "_unrunnable", lambda: NOBLOCK)
    before = _tree_state()
    assert mh.main() == 0
    assert _tree_state() == before, "the end-to-end merge test wrote a desk file"
    rows = json.loads(target.read_text("utf-8"))
    report = json.loads((hyp / "merge_report.json").read_text("utf-8"))
    fam = report["hypothesis_families"]
    assert fam["intake"]["by_status"]["NEAR"] == 1, fam
    assert fam["intake"]["reaimed"] == 1
    assert len(rows) == 4                    # 2 banked + 1 fresh duplicate KEPT + 1 re-aimed
    kid = next(r for r in rows if r.get("reaimed_from"))
    assert kid["symbol"] == "XAUUSD" and kid["params"]["range_hours"] == 5
    assert (hyp / "HYPOTHESIS_FAMILIES.json").exists()
    assert (hyp / "reaim_ledger.jsonl").read_text("utf-8").count("\n") == 1
    assert report["hypothesis_families"]["commit"]["ledger_lines"] == 1
    cycle = (_DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '"merge_hypotheses", "research/merge_hypotheses.py"' in cycle


# ---- v1.2 (audit of 7753bbf95): the docket is the ledger's twin; several targets per pass ----
TARGETS = ("AUDUSD", "NZDUSD", "USDCAD", "USDCHF", "XAGUSD", "XAUUSD")


def _wide(monkeypatch, blocked=NOBLOCK) -> tuple[list[dict], list[dict]]:
    monkeypatch.setattr(hf, "_daily", lambda s, u: None)
    monkeypatch.setattr(hf, "_lawful", lambda: (lambda s, f: True))
    monkeypatch.setattr(hf, "_unrunnable", lambda: blocked)
    bank = [_row("EURUSD"), *(_row(t, session="asia") for t in TARGETS)]
    dups = [_row("EURUSD", lookback=n) for n in (3, 5, 7)]
    return bank, dups


def _pass(rows: list[dict], fresh: set, reproposed: set, tmp_path: Path):
    return hf.apply([dict(r) for r in rows], fresh=fresh, reproposed=reproposed,
                    report_path=tmp_path / "HF.json", hyp_dir=tmp_path)


def _kids(rows: list[dict]) -> list[dict]:
    return [r for r in rows if r.get("reaimed_from")]


def test_crash_after_the_docket_write_with_many_targets_gives_no_parent_a_second_child(
        tmp_path: Path, monkeypatch) -> None:
    bank, dups = _wide(monkeypatch)
    ids = {hf.identity(d) for d in dups}
    out1, _, p1 = _pass([*bank, *dups], ids, set(), tmp_path)
    assert len(_kids(out1)) == 3 and p1 is not None
    # docket written, then the process died: NO commit, no ledger line
    assert not (tmp_path / "reaim_ledger.jsonl").exists()
    out2, _, _ = _pass(out1, set(), ids, tmp_path)
    assert len(_kids(out2)) == 3                       # the same three, nothing new
    per_parent = [k["reaimed_from"]["parent_identity"] for k in _kids(out2)]
    assert sorted(per_parent) == sorted(ids)
    out3, _, _ = _pass(out2, set(), ids, tmp_path)     # and a third pass: still nothing
    assert len(_kids(out3)) == 3


def test_a_failed_report_write_with_many_targets_gives_no_parent_a_second_child(
        tmp_path: Path, monkeypatch) -> None:
    bank, dups = _wide(monkeypatch)
    ids = {hf.identity(d) for d in dups}
    out1, _, p1 = _pass([*bank, *dups], ids, set(), tmp_path)
    monkeypatch.setattr(hf, "write", lambda doc, path=None: False)
    assert p1 is not None and p1.commit(out1)["ledger_lines"] == 0
    for _ in range(2):
        out1, _, p = _pass(out1, set(), ids, tmp_path)
        assert p is not None and p.commit(out1)["ledger_lines"] == 0
    assert len(_kids(out1)) == 3


def test_commit_matches_durable_children_by_identity_not_object(tmp_path: Path,
                                                               monkeypatch) -> None:
    # probe P2d: the docket writer wrote COPIES of the rows; the children are still durable
    bank, dups = _wide(monkeypatch)
    ids = {hf.identity(d) for d in dups}
    out1, _, p1 = _pass([*bank, *dups], ids, set(), tmp_path)
    copied = json.loads(json.dumps(out1, default=str))
    assert p1 is not None
    got = p1.commit(copied)
    assert got["durable"] == 3 and got["ledger_lines"] == 3
    # and a child the writer dropped is not claimed
    _, _, p2 = _pass([*bank, *dups], ids, set(), tmp_path / "b")
    assert p2 is not None
    assert p2.commit([r for r in copied if not r.get("reaimed_from")])["ledger_lines"] == 0


def test_the_unrunnable_bank_is_asked_about_the_child_row_with_its_row_level_timeframe(
        tmp_path: Path, monkeypatch) -> None:
    seen: list[dict] = []

    def block(spec: dict) -> bool:
        seen.append(spec)
        # the bank holds the M15 cell on AUDUSD, identifiable only by the ROW-level timeframe
        return spec["symbol"] == "AUDUSD" and spec.get("timeframe") == "M15"
    bank, dups = _wide(monkeypatch, blocked=block)
    dup = dict(dups[0], timeframe="M15")
    out, _, _ = _pass([*bank, dup], {hf.identity(dup)}, set(), tmp_path)
    kids = _kids(out)
    assert len(kids) == 1 and kids[0]["symbol"] != "AUDUSD"
    assert kids[0]["timeframe"] == "M15"
    assert seen and all(s.get("timeframe") == "M15" for s in seen)
    from research import frontier_identity as fi
    # the spec the bank saw for the chosen target keys exactly as the child row will
    asked = next(s for s in seen if s["symbol"] == kids[0]["symbol"])
    assert fi.docket_cell_id(asked) == fi.docket_cell_id(kids[0])
