"""Formula certificates that read unrecorded bar inputs hold no capital on their stored verdict.

Auditor, measured on the box 2026-11-10 18:08Z: 5,702 of 5,757 `formula` certificates read the
spread or tick columns, and on AUDSGD the certified edge disappears when the unrecorded (zero)
bars are treated as missing. pf_allocation.json funded GBPMXN_formula_asia 2.16% and
USDMXN_formula_asia 4.76% on such certificates.

Pinned here:
  * ONE shared test, the Judge's (`shadow_admission.formula_input_unmeasured`): the allocator
    asks it and carries no copy of the rule; with the test absent or raising it fails closed
    (every formula certificate held), and only the `formula` family is ever asked;
  * a held certificate is not priced, the cell stays open for a certificate that stands, a cell
    left with none loses its column, and a book held from the last pass is cleared of it;
  * LIVE and STANDBY formula rows on held evidence are published as zeros, so the gateway
    sends no order instead of sizing them at the base ramp;
  * the report counts and names the exclusions, with the paper fractions removed and where the
    freed heat went, and missed_growth publishes it.
"""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import missed_growth as MG  # noqa: E402
from research import pf_allocator as pa  # noqa: E402
from research import shadow_admission as SA  # noqa: E402

SPREAD = {"expr": ["neg", ["delta", "spread", 5]], "rr": 1.5}
CLEAN = {"expr": ["zscore", "ret", 24], "rr": 1.5}
K_BAD = "external.GBPMXN.formula.p=449c3280438f8a09"
K_OK = "external.GBPMXN.formula.p=00000000000clean"
K_USD = "external.USDMXN.formula.p=f5b697dc3ae02496"


def _judge(name: str, row: dict) -> str | None:
    """A stand-in for the Judge's shared test, on the row shape the allocator hands it."""
    expr = json.dumps((row.get("shadow_spec") or {}).get("params", {}).get("expr"))
    return "reads spread; not re-gated" if '"spread"' in expr else None


def test_one_shared_test_and_it_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    ask = pa.formula_evidence_unmeasured
    # only the formula family is ever asked
    monkeypatch.setattr(SA, "formula_input_unmeasured", lambda n, r: "would hold", raising=False)
    assert ask("k", "EURUSD", "carry", "asia", SPREAD) is None
    monkeypatch.setattr(SA, "formula_input_unmeasured", _judge, raising=False)
    assert ask(K_BAD, "GBPMXN", "formula", "asia", SPREAD) == "reads spread; not re-gated"
    assert ask(K_OK, "GBPMXN", "formula", "asia", CLEAN) is None
    # the Judge's switch off (QUANT_FORMULA_INPUT_HOLD=0) enrols them here too; on, they hold
    monkeypatch.setattr(SA, "formula_input_hold_enforced", lambda: False, raising=False)
    assert ask(K_BAD, "GBPMXN", "formula", "asia", SPREAD) is None
    monkeypatch.setattr(SA, "formula_input_hold_enforced", lambda: True, raising=False)
    assert ask(K_BAD, "GBPMXN", "formula", "asia", SPREAD) == "reads spread; not re-gated"
    # the Judge's test raising, or not on this tree at all: held, and the reason says why
    monkeypatch.setattr(SA, "formula_input_unmeasured",
                        lambda n, r: (_ for _ in ()).throw(ValueError("bad row")), raising=False)
    assert "fail closed" in (ask(K_OK, "GBPMXN", "formula", "asia", CLEAN) or "")
    monkeypatch.delattr(SA, "formula_input_unmeasured", raising=False)
    assert "not on this tree" in (ask(K_OK, "GBPMXN", "formula", "asia", CLEAN) or "")
    # no copy of the rule lives in the allocator
    src = (_DESK / "research" / "pf_allocator.py").read_text(encoding="utf-8")
    assert '"spread"' not in src and "UNRECORDED_BAR_TERMINALS" not in src


def _fake_gauntlet(calls: list) -> types.ModuleType:
    eg = types.ModuleType("external_gauntlet")

    def build_cell(sym, fam, params, meta):
        calls.append((sym, fam, params))
        return {"df": params, "sigs": [1], "costs": 0}

    def daily_series(df, sigs, costs):
        return pd.Series([0.1, -0.05, 0.2], index=pd.date_range("2026-01-01", periods=3))

    eg.build_cell, eg.daily_series = build_cell, daily_series
    return eg


def _desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, calls: list, roster: list) -> None:
    for d in ("data/universe", "reports"):
        (tmp_path / d).mkdir(parents=True)
    (tmp_path / "data" / "universe" / "universe.json").write_text("{}", "utf-8")
    (tmp_path / "data" / "sleeves.json").write_text(json.dumps({"sleeves": roster}), "utf-8")

    def cert(sym: str, params: dict) -> dict:
        return {"cell": f"{sym}.formula", "gated_at": "2026-09-01T00:00:00+00:00",
                "shadow_spec": {"symbol": sym, "selector": "asia", "family": "formula",
                                "params": params}}
    survivors = tmp_path / "survivors.json"
    survivors.write_text(json.dumps({"survivors": {
        K_BAD: cert("GBPMXN", SPREAD), K_OK: cert("GBPMXN", CLEAN),
        K_USD: cert("USDMXN", SPREAD)}}), "utf-8")
    import research.portfolio_gap as pg
    monkeypatch.setattr(pg, "SURVIVORS", survivors)
    monkeypatch.setattr(pa, "BASE", tmp_path)
    monkeypatch.setattr(pa, "_rostered_certificates", lambda sp: ({}, {}, {}))
    monkeypatch.setitem(sys.modules, "external_gauntlet", _fake_gauntlet(calls))
    monkeypatch.setattr(SA, "formula_input_unmeasured", _judge, raising=False)


def test_a_held_certificate_is_not_priced_and_the_cell_takes_one_that_stands(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list = []
    roster = [
        {"name": "usdmxn_formula_asia_p_f5b6", "status": "LIVE", "symbol": "USDMXN",
         "family": "formula", "selector": "asia", "certificate": {"cell": K_USD}},
        {"name": "gbpmxn_formula_asia_p_449c", "status": "STANDBY", "symbol": "GBPMXN",
         "family": "formula", "selector": "asia", "certificate": {"cell": K_BAD}},
        {"name": "gbpmxn_formula_asia_p_clean", "status": "LIVE", "symbol": "GBPMXN",
         "family": "formula", "selector": "asia", "certificate": {"cell": K_OK}},
        {"name": "usdmxn_formula_asia_retired", "status": "RETIRED", "symbol": "USDMXN",
         "family": "formula", "selector": "asia", "certificate": {"cell": K_USD}},
    ]
    _desk(tmp_path, monkeypatch, calls, roster)
    out, acct = pa.certified_evidence()
    # GBPMXN is priced on its certificate that stands; USDMXN has none and gets no column
    assert set(out) == {"GBPMXN_formula_asia"}
    assert [c[2] for c in calls] == [CLEAN], "the spread-reading certificates were never replayed"
    assert set(acct["evidence_unmeasured"]) == {K_BAD, K_USD}
    assert acct["evidence_unmeasured_cells"] == ["USDMXN_formula_asia"]
    # the LIVE row on the held USDMXN cell and the STANDBY row on the held certificate are
    # zeros for the gateway; the row on the certificate that stands and the RETIRED row are not
    assert set(acct["evidence_unmeasured_rows"]) == {"usdmxn_formula_asia_p_f5b6",
                                                     "gbpmxn_formula_asia_p_449c"}


def test_the_report_names_the_paper_fractions_removed_and_where_the_heat_went() -> None:
    acct = {"evidence_unmeasured": {K_BAD: {"cell": "GBPMXN_formula_asia", "why": "x"},
                                    K_USD: {"cell": "USDMXN_formula_asia", "why": "x"}},
            "evidence_unmeasured_cells": ["GBPMXN_formula_asia", "USDMXN_formula_asia"],
            "evidence_unmeasured_rows": {}}
    prev = {"GBPMXN_formula_asia": 0.02162, "USDMXN_formula_asia": 0.04759, "gold_asia": 0.10}
    funded = {"gold_asia": 0.13, "NZDCHF_clock_transition_asia": 0.03921}
    rep = pa.unmeasured_evidence_report(acct, prev, funded)
    assert rep["status"] == "HELD" and rep["n_certificates"] == 2 and rep["n_cells"] == 2
    assert rep["paper_fractions_removed"] == {"GBPMXN_formula_asia": 0.02162,
                                              "USDMXN_formula_asia": 0.04759}
    assert rep["freed_heat"] == pytest.approx(0.06921)
    assert rep["refilled_into"] == {"NZDCHF_clock_transition_asia": 0.03921, "gold_asia": 0.03}
    assert rep["book_total"] == pytest.approx(sum(prev.values()))        # the book is no smaller
    line = MG.evidence_unmeasured_line({"evidence_unmeasured": rep})
    assert line["verdict"] == MG.UNMEASURED and line["freed_heat"] == pytest.approx(0.06921)
    assert line["refilled_into"] and "earn side" in line["why"] and "cost side" in line["why"]
    assert MG.evidence_unmeasured_line({"evidence_unmeasured": pa.unmeasured_evidence_report(
        {}, prev, funded)})["verdict"] == MG.NOT_BINDING
    assert MG.evidence_unmeasured_line({})["verdict"] == MG.UNMEASURED


def test_the_pass_drops_the_cell_clears_a_held_book_and_publishes_the_zeros() -> None:
    src = (_DESK / "research" / "pf_allocator.py").read_text(encoding="utf-8")
    run_src = src[src.index("def run(mode"):]
    assert "daily = daily.drop(columns=_unm_cols)" in run_src
    assert (run_src.index("daily = daily.drop(columns=_unm_cols)")
            < run_src.index("daily = align(align(daily, certified), scalp)"))
    assert "ts_zero = ts_zero | lp_zero | _unm_cells" in run_src
    assert '**(cert_acct.get("evidence_unmeasured_rows") or {})})' in run_src
    assert ('"evidence_unmeasured": unmeasured_evidence_report(cert_acct, prev_book, funded),'
            in run_src)
    mg = (_DESK / "research" / "missed_growth.py").read_text(encoding="utf-8")
    assert '"formula_evidence_unmeasured": evidence_unmeasured_line(' in mg
