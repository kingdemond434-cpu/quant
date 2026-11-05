"""The formula rule in the replication spec book: an independent numpy reading of the expression
grammar and the family's entry/exit text. Checked here AGAINST the original (the grammar's
`evaluate` and `family_formula`), which only this test may import -- the lane itself never does
(`FORBIDDEN_IMPORTS`)."""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK / "research"), str(DESK), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import replication_civilization as rc  # noqa: E402

#: One expression per operator class the 582 held certificates use (FORWARD_ENROLMENT
#: 2026-11-04), plus every other operator the grammar defines.
EXPRS = [
    "spread",
    ["max", ["mean", "spread", 8], 48],
    ["neg", ["decay", ["delta", "spread", 5], 12]],
    ["zscore", ["ts_backfill", ["trade_when", "range", "spread"], 24], 24],
    ["abs", ["std", "ret", 24]],
    ["sum", ["delay", "body", 3], 12],
    ["ts_rank", "spread", 48],
    ["scale", ["sub", "close", ["mean", "close", 24]], 24],
    ["div", "vol", "spread"],
    ["bars_since_max", "high", 24],
    ["bars_since_min", "low", 12],
    ["mul", "flow", ["sign", "body"]],
    ["add", "activity", ["min", "atr", 12]],
    ["max2", "range", ["min2", "body", "ret"]],
    ["atr_norm", ["delta", "close", 3], 24],
    ["corr", "ret", ["delay", "ret", 1], 24],
    ["cov", "range", "spread", 24],
    ["residual", "ret", ["delay", "ret", 1], 48],
    ["group_rank", "ret", "spread", 24],
    ["group_zscore", "body", "range", 24],
]


def _frame(n: int = 4000, seed: int = 11) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    t = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    c = 1.3 + np.cumsum(rng.normal(0, 0.001, n))
    o = np.r_[c[0], c[:-1]] + rng.normal(0, 2e-4, n)
    h = np.maximum(o, c) + np.abs(rng.normal(0, 5e-4, n))
    lo = np.minimum(o, c) - np.abs(rng.normal(0, 5e-4, n))
    sp = rng.integers(5, 40, n).astype(float)          # a spread that moves every bar
    tv = rng.integers(50, 900, n).astype(float)
    return pd.DataFrame({"open": o, "high": h, "low": lo, "close": c, "spread": sp,
                         "tick_volume": tv}, index=t)


def _bars(df: pd.DataFrame) -> rc.Bars:
    return rc.bars_from_arrays(df.index.as_unit("ns").asi8, df["open"].to_numpy(),
                               df["high"].to_numpy(), df["low"].to_numpy(),
                               df["close"].to_numpy(), df["spread"].to_numpy(),
                               df["tick_volume"].to_numpy())


@pytest.mark.parametrize("expr", EXPRS, ids=lambda e: json.dumps(e)[:40])
def test_each_operator_reads_what_the_grammar_computes(expr) -> None:
    from libs.research import alpha_grammar as ag
    df = _frame()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ref = ag.evaluate(expr, ag.terminal_frames(df, raw=df, atr_n=20)).to_numpy(float)
    ours = rc._fx_eval(expr, rc._fx_terminals(_bars(df), 20), len(df))
    assert np.array_equal(np.isnan(ref), np.isnan(ours))
    fin = ~np.isnan(ref)
    scale = max(1e-12, float(np.max(np.abs(ref[fin])))) if fin.any() else 1.0
    assert float(np.max(np.abs(ref[fin] - ours[fin]), initial=0.0)) <= 1e-7 * scale


@pytest.mark.parametrize("side_mode", ["follow", "fade"])
def test_the_rule_emits_the_familys_signals(side_mode) -> None:
    from mt5desk.family_formula import family_formula
    df = _frame()
    p = {"norm": 240, "entry_z": 1.5, "hold_bars": 8, "atr_n": 20, "stop_atr": 2.0, "rr": 1.5,
         "side_mode": side_mode}
    for expr in EXPRS[:8]:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            ref = family_formula(df, expr=expr, **p)
        ours = rc._build_formula(_bars(df), {**p, "expr": expr})
        a = [(int(s.time.value), s.side, round(s.stop, 9), round(s.target, 9)) for s in ref]
        b = [(o.t_ns, o.side, round(o.stop, 9), round(o.target, 9)) for o in ours]
        assert a == b, expr


def test_a_constant_window_reads_zero_not_a_rounding_residue() -> None:
    x = np.r_[np.arange(30, dtype=float), np.full(40, 7.0)]
    z = rc._fx_z(x, 24)
    assert np.all(z[-10:] == 0.0)
    assert rc._fx_std(x, 24)[-1] == 0.0 and rc._fx_mean(x, 24)[-1] == 7.0


def test_a_rendered_call_parses_back_and_a_driver_stands_aside() -> None:
    assert rc._fx_parse("max(mean(spread, 8), 48)") == ["max", ["mean", "spread", 8], 48]
    df = _frame()
    p = {"norm": 240, "entry_z": 1.5, "hold_bars": 8, "atr_n": 20, "stop_atr": 2.0, "rr": 1.5,
         "side_mode": "follow"}
    b = _bars(df)
    assert rc._build_formula(b, {**p, "expr": "max(mean(spread, 8), 48)"}) == \
        rc._build_formula(b, {**p, "expr": ["max", ["mean", "spread", 8], 48]})
    assert rc._build_formula(b, {**p, "expr": ["mean", "usd", 8]}) == []      # driver
    assert rc._build_formula(b, {**p, "expr": ["xrank", "close"]}) == []      # panel op
    no_spread = rc.Bars(b.t, b.o, b.h, b.low, b.c, b.minutes)
    assert rc._build_formula(no_spread, {**p, "expr": "spread"}) == []        # absent column


def test_resolve_spec_carries_every_formula_parameter() -> None:
    params = {"expr": ["mean", "spread", 8], "norm": 120, "entry_z": 2.0, "side_mode": "fade",
              "hold_bars": 24, "atr_n": 14, "stop_atr": 1.5, "rr": 2.0, "timeframe": "M15"}
    p, why = rc.resolve_spec("formula", params, "asia", "LONG")
    assert why == "ok" and p is not None
    assert {k: p[k] for k in params if k != "timeframe"} == {k: v for k, v in params.items()
                                                            if k != "timeframe"}
    assert p["_side"] == 1 and p["_session"] is None     # no session param: every hour


def test_load_bars_carries_spread_and_tick_volume(tmp_path: Path) -> None:
    df = _frame(400).rename_axis("time")
    df.to_parquet(tmp_path / "TESTFX_H1.parquet")
    b = rc.load_bars("TESTFX", "H1", universe=tmp_path)
    assert b is not None and b.spread is not None and b.volume is not None
    assert np.array_equal(b.spread, df["spread"].to_numpy())


def test_a_certificate_judged_before_its_rule_existed_is_rejudged_ahead(tmp_path: Path,
                                                                         monkeypatch) -> None:
    seen: list[str] = []

    def fake(row, *, meta, bars):
        seen.append(row["certificate"])
        return {"lane": "certificate", "key": row["certificate"],
                "certificate": row["certificate"], "verdict": rc.UNMEASURED, "why": []}

    monkeypatch.setattr(rc, "replicate_certificate", fake)
    monkeypatch.setattr(rc, "certificate_fp", lambda r: "fp")
    certs = [{"certificate": k, "shadow_spec": {"symbol": "TESTFX", "family": fam}}
             for k, fam in (("A", "carry"), ("B", "formula"), ("C", "formula"),
                            ("D", "no_such_family"))]
    book = {k: {"verdict": rc.UNMEASURED, "fp": "fp",
                "sharpe_metric_version": rc.SHARPE_METRIC_VERSION,
                "why": [f"no written specification in the spec book for family {fam!r}"]}
            for k, fam in (("B", "formula"), ("C", "formula"), ("D", "no_such_family"))}
    book["A"] = {"verdict": rc.REPLICATED, "fp": "fp",
                 "sharpe_metric_version": rc.SHARPE_METRIC_VERSION, "why": []}
    (tmp_path / rc.VERDICTS_NAME).write_text(json.dumps({"certificates": book}), "utf-8")
    doc = rc.build(certificates=certs, forward=[], universe_meta={},
                   bars_loader=lambda *_: None, cursor_path=tmp_path / "cursor.json",
                   dry_run=True, max_per_pass=2)
    assert seen[:2] == ["B", "C"] and "D" not in seen[:2]
    assert doc["verdict_book"]["no_rule_backlog"] == 2


def test_the_backlogs_extra_slots_are_never_taken_by_moved_fingerprints(tmp_path: Path,
                                                                         monkeypatch) -> None:
    seen: list[str] = []

    def fake(row, *, meta, bars):
        seen.append(row["certificate"])
        return {"lane": "certificate", "key": row["certificate"],
                "certificate": row["certificate"], "verdict": rc.UNMEASURED, "why": []}

    monkeypatch.setattr(rc, "replicate_certificate", fake)
    monkeypatch.setattr(rc, "certificate_fp", lambda r: "fp")
    moved = [f"M{i}" for i in range(10)]           # no book entry: pending, ahead of the backlog
    backlog = ["B0", "B1", "B2"]
    certs = [{"certificate": k, "shadow_spec": {"symbol": "TESTFX", "family": "formula"}}
             for k in moved + backlog]
    book = {k: {"verdict": rc.UNMEASURED, "fp": "fp",
                "sharpe_metric_version": rc.SHARPE_METRIC_VERSION,
                "why": ["no written specification in the spec book for family 'formula'"]}
            for k in backlog}
    (tmp_path / rc.VERDICTS_NAME).write_text(json.dumps({"certificates": book}), "utf-8")
    rc.build(certificates=certs, forward=[], universe_meta={}, bars_loader=lambda *_: None,
             cursor_path=tmp_path / "cursor.json", dry_run=True, max_per_pass=4)
    assert seen == ["M0", "M1", *backlog]         # the lane's share, then the backlog's extra
