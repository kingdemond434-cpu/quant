"""UNKNOWN verdicts: the share is read on the cells that reached the judge, every one is named,
and the two causes that sat upstream of the judge are fixed where they are minted.

Measured 2026-09-30: the desktop read 9.55% UNKNOWN (2,814 of 29,466 report rows) while the gate
ledger read 43% over 7 days (53,460 of 124,342). Same numerator class; the report's denominator
carried 20,247 NOT_RUN rows that never reached a gate. These tests pin the judged-only basis, the
named causes, and the two source fixes (peer/driver/factor inputs in `discovery_compiler`, the
`formula` provenance key and rendered expression in `family_formula`).
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import discovery_compiler as dc  # noqa: E402
from research import judge_coverage as jc  # noqa: E402
from research import transformation_miners as TM  # noqa: E402

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)


def _gates(tmp_path: Path, verdicts: list[dict]) -> Path:
    p = tmp_path / "universal_gates_external.json"
    p.write_text(json.dumps({"verdicts": verdicts}), "utf-8")
    return p


def _unknown(cell: str, days: int = 0, **extra: object) -> dict:
    return {"cell": cell, "sym": "XAUUSD", "family": extra.pop("family", "f"), "days": days,
            "passed": False, "unmeasured": True,
            "stages": {"observations": {"passed": False, "days": days, "why": "x"}}, **extra}


# ------------------------------------------------------------------ the denominator
def test_unknown_share_divides_by_the_judged_cells_not_by_every_report_row(tmp_path) -> None:
    """2 UNKNOWN of 4 judged is 50%, however many NOT_RUN rows the sweep also wrote."""
    rows = [_unknown("a.f.p=1"), _unknown("b.f.p=2", days=12),
            {"cell": "c.f.p=3", "sym": "XAUUSD", "family": "f", "passed": False,
             "terminal_gate": "cpcv"},
            {"cell": "d.f.p=4", "sym": "XAUUSD", "family": "f", "passed": True,
             "terminal_gate": "PASSED"}]
    rows += [{"cell": f"n.f.p={i}", "sym": "XAUUSD", "family": "f", "passed": None,
              "downstream_status": "NOT_RUN_BUILD_FAILED"} for i in range(16)]
    doc = jc.unknown_breakdown(_gates(tmp_path, rows))
    assert doc["judged_verdicts"] == 4 and doc["not_run_rows"] == 16
    assert doc["unknown_share"] == 0.5
    assert doc["unknown_share_of_all_rows"] == 0.1, "the old ratio is kept, by name"
    assert doc["unknown_share_basis"] == jc.UNKNOWN_SHARE_BASIS


def test_a_sweep_that_judged_nothing_reads_unmeasured_not_zero(tmp_path) -> None:
    rows = [{"cell": "n.f.p=1", "sym": "X", "family": "f", "passed": None,
             "downstream_status": "NOT_RUN_DATA_MISSING"}]
    assert jc.unknown_breakdown(_gates(tmp_path, rows))["unknown_share"] is None


def test_the_ledger_window_publishes_the_same_class_over_seven_days(tmp_path) -> None:
    at = (NOW - timedelta(days=2)).isoformat()
    rows = ([{"at": at, "cell": f"u{i}", "family": "f", "passed": False,
              "terminal_gate": "UNKNOWN"} for i in range(43)]
            + [{"at": at, "cell": f"r{i}", "family": "f", "passed": False,
                "terminal_gate": "cpcv"} for i in range(57)]
            + [{"at": at, "cell": f"n{i}", "family": "f",
                "downstream_status": "NOT_RUN_X"} for i in range(500)])
    ledger = tmp_path / "gate_verdict_ledger.jsonl"
    ledger.write_text("".join(json.dumps(r) + "\n" for r in rows), "utf-8")
    r = jc.sustained_rate(ledger, now=NOW)
    assert r["unknown_counts"]["7d"] == 43 and r["counts"]["7d"] == 100
    assert r["unknown_share_7d"] == 0.43 and r["unknown_share_24h"] is None


# ------------------------------------------------------------------ every UNKNOWN is named
def test_no_unknown_is_left_without_a_named_reason(tmp_path) -> None:
    """Whatever the writer declares or omits, every UNKNOWN row leaves with a non-empty reason."""
    rows = [_unknown("a.f.p=1"), _unknown("b.f.p=2", days=30),
            _unknown("c.f.p=3", unknown_reason="series_exception", series_error="KeyError: x"),
            _unknown("d.f.p=4", unknown_reason="lockbox_consumed_history", days=0),
            _unknown("e.relative_value.p=5", family="relative_value", params={"session": "ny"}),
            _unknown("f.relative_value.p=6", family="relative_value",
                     params={"peer_symbol": "XAGUSD"}),
            _unknown("g.f.p=7", unknown_reason="some_new_cause_nobody_wrote_yet")]
    named = jc.name_unknowns(_gates(tmp_path, rows))
    assert set(named) == {r["cell"] for r in rows}
    assert all(str(n.get("reason") or "") and str(n.get("route") or "")
               for n in named.values())
    assert named["c.f.p=3"]["reason"] == "series_exception"
    assert named["d.f.p=4"]["reason"] == "lockbox_consumed_history"
    assert named["e.relative_value.p=5"]["reason"] == "missing_identity_input"
    assert named["f.relative_value.p=6"]["reason"] != "missing_identity_input"
    assert named["g.f.p=7"].get("detail") == "some_new_cause_nobody_wrote_yet"


def test_the_cells_own_chart_decides_whether_its_bars_exist(tmp_path, monkeypatch) -> None:
    """An M15 cell with no M15 file is missing bars, not a spec that never fires on H1."""
    monkeypatch.setattr(jc, "_bar_bytes", lambda sym, tf="H1": 0 if tf == "M15" else 5_000)
    named = jc.name_unknowns(_gates(tmp_path, [_unknown("XAUUSD@M15.f.p=1")]))
    assert named["XAUUSD@M15.f.p=1"]["reason"] == "missing_bars"
    assert named["XAUUSD@M15.f.p=1"]["tf"] == "M15"


def test_a_series_exception_retries_on_the_build_failure_clock(monkeypatch) -> None:
    monkeypatch.setattr(jc, "_bar_bytes", lambda sym, tf="H1": 1_000)
    row = {"reason": "series_exception", "sym": "XAUUSD", "tf": "H1", "bar_bytes": 1_000,
           "parked_at": (NOW - timedelta(days=jc.BUILD_FAILED_RETRY_DAYS + 1)).isoformat()}
    assert jc.readmit_due(row, now=NOW)


# ------------------------------------------------------------------ source fix 1: inputs
def _ctx() -> TM.Context:
    return TM.Context(
        instruments={"forex": ["EURUSD", "GBPUSD", "EURJPY", "USDJPY"],
                     "commodities": ["XAUUSD", "XAGUSD"], "indices": ["US500"]},
        families=frozenset({"relative_value", "correlation_regime", "lead_lag",
                            "cross_asset_residual", "pca_residual", "asia_momentum"}),
        defaults={}, bars_available=lambda s, c: not (s == "EURJPY" and c == "M15"),
        lane_ok=lambda s: True)


META = {s: {"asset_class": c, "bars": b} for s, c, b in (
    ("EURUSD", "Forex", 50_000), ("GBPUSD", "Forex", 49_000), ("EURJPY", "Forex", 48_000),
    ("USDJPY", "Forex", 47_000), ("XAUUSD", "Metals", 46_000), ("XAGUSD", "Metals", 45_000),
    ("US500", "Indices", 44_000))}


def _child(family: str, symbol: str = "EURUSD", chart: str = "H1", **params: object) -> dict:
    return {"family": family, "symbol": symbol, "chart": chart, "params": dict(params),
            "content_hash": "0" * 32}


def test_a_peer_family_is_given_its_peer_on_its_own_chart() -> None:
    out = dc.complete_inputs(_child("relative_value"), _ctx(), META)
    assert out["params"]["peer_symbol"] == "EURJPY", "shares the distinguishing EUR leg"
    assert out["input_completed"] == "peer_symbol"
    assert out["content_hash"] != "0" * 32, "a new input is a new cell identity"
    m15 = dc.complete_inputs(_child("correlation_regime", chart="M15"), _ctx(), META)
    assert m15["params"]["peer_symbol"] != "EURJPY", "no M15 bars for EURJPY: never its peer"


def test_lead_lag_gets_a_driver_and_the_residual_families_a_basket() -> None:
    ll = dc.complete_inputs(_child("lead_lag", symbol="XAGUSD"), _ctx(), META)
    assert ll["params"]["driver_symbol"] not in ("", None, "XAGUSD")
    for fam in ("cross_asset_residual", "pca_residual"):
        out = dc.complete_inputs(_child(fam), _ctx(), META)
        basket = out["params"]["factor_symbols"]
        assert "EURUSD" not in basket and len(basket) >= 4
        assert {"XAUUSD", "US500"} <= set(basket) or {"XAGUSD", "US500"} <= set(basket), \
            "the basket spans the asset classes"


def test_a_named_input_and_a_price_only_family_are_left_exactly_as_written() -> None:
    named = _child("relative_value", peer_symbol="GBPUSD")
    assert dc.complete_inputs(named, _ctx(), META) is named
    plain = _child("asia_momentum")
    assert dc.complete_inputs(plain, _ctx(), META) is plain


def test_no_candidate_instrument_leaves_the_child_unchanged_never_refused() -> None:
    ctx = _ctx()
    ctx.bars_available = lambda s, c: False
    child = _child("relative_value")
    assert dc.complete_inputs(child, ctx, META) is child


def test_the_two_input_maps_agree() -> None:
    expected = {**dc.PEER_KEY_BY_FAMILY, **dict.fromkeys(dc.FACTOR_FAMILIES, "factor_symbols"),
                **{f: keys[0] for f, keys in dc.LEG_FAMILIES.items()}}
    assert expected == jc.REQUIRED_INPUT_KEY


# ------------------------------------------------------------------ source fix 2: formula
def _bars(n: int = 1_500) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    close = 1.1 + np.cumsum(rng.normal(0, 0.001, n))
    idx = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    opn = np.r_[close[0], close[:-1]]
    return pd.DataFrame({"open": opn, "high": close + 0.0008, "low": close - 0.0008,
                         "close": close, "tick_volume": 100, "spread": 10}, index=idx)


def test_formula_accepts_its_provenance_key_and_its_rendered_tree() -> None:
    """The census rows carry `population` and the tree as a string: both built nothing before."""
    from mt5desk.family_formula import family_formula

    from libs.research.alpha_grammar import to_str

    tree = ["zscore", ["sub", "close", "open"], 24]
    df = _bars()
    as_list = family_formula(df, expr=tree, norm=120, entry_z=1.0)
    as_text = family_formula(df, expr=to_str(tree), norm=120, entry_z=1.0, population="gp")
    assert as_list, "the fixture must fire for the comparison to mean anything"
    assert [(s.time, s.side) for s in as_text] == [(s.time, s.side) for s in as_list]
    assert family_formula(df, expr="not(a valid", norm=120) == []



def test_a_short_history_after_the_cut_is_named_not_never_fires(tmp_path) -> None:
    """T5 names a cell that traded only after the lockbox cut; it is not a spec that never fires."""
    rows = [_unknown("d.f.p=9", unknown_reason="short_history_after_cut", days=0)]
    named = jc.name_unknowns(_gates(tmp_path, rows))
    assert named["d.f.p=9"]["reason"] == "short_history_after_cut"
