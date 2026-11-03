"""THE SECOND IMPLEMENTATION (item 15, 2026-09-29).

Two properties make `libs/validation/independent_replica.py` worth anything: it must NOT reach the
desk's own code (else it is the first implementation twice), and on bars where the desk's code is
right it must agree with it trade for trade (else its disagreements are noise). Both are pinned
here, plus the verifier's refusal to count UNSUPPORTED or UNMEASURED as agreement.
"""
from __future__ import annotations

import ast
import dataclasses
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(DESK / "research"), str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import families, families_orthogonal  # noqa: E402
from mt5desk.engine import Costs, run_backtest  # noqa: E402

from libs.validation import independent_replica as rep  # noqa: E402

META = {"contract_size": 100000.0, "tick_size": 1e-5, "tick_value": 1.0,
        "median_spread_pts": 12.0, "swap_long": -4.0, "swap_short": 1.5, "swap_mode": 1}


def test_the_replica_imports_nothing_from_the_desk() -> None:
    tree = ast.parse((ROOT / "libs" / "validation" / "independent_replica.py").read_text("utf-8"))
    banned = ("mt5desk", "research", "scripts", "desks", "blind_reviewer", "edge_search",
              "libs.validation.replay2")
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        for n in names:
            assert not any(n == b or n.startswith(b + ".") for b in banned), n


def _bars(n: int = 3000, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    idx = idx[idx.dayofweek < 5]
    r = rng.normal(0.0, 0.0012, len(idx))
    # overnight gaps on each day's first bar, so the gap family has something to fade
    first = np.r_[True, idx.date[1:] != idx.date[:-1]]
    r[first] += rng.normal(0.0, 0.004, first.sum())
    close = 1.1 * np.exp(np.cumsum(r))
    openp = np.r_[close[0], close[:-1]] * np.exp(np.where(first, r * 0.8, 0.0))
    wig = np.abs(rng.normal(0.0, 0.0008, len(idx)))
    return pd.DataFrame({"open": openp, "close": close,
                         "high": np.maximum(openp, close) * (1 + wig),
                         "low": np.minimum(openp, close) * (1 - wig)}, index=idx)


def _orig_rows(df: pd.DataFrame, sigs: list) -> list[dict]:
    out = []
    for t in run_backtest(df, sigs, Costs.from_symbol(META)).trades:
        unit = abs(t.entry - t.stop)
        g = t.side * (t.exit - t.entry) / unit
        out.append({"entry_time": t.entry_time, "side": t.side, "gross_r": g,
                    "cost_r": g - t.r_multiple, "r": t.r_multiple})
    return out


@pytest.mark.parametrize(("family", "orig", "params"), [
    ("overnight_gap_decay", families_orthogonal.family_overnight_gap_decay, {}),
    ("session_range_breakout", families.family_session_range_breakout,
     {"rr": 1.5, "wait_bars": 12}),
    ("discovered", families_orthogonal.family_discovered,
     {"feature": "dd_12", "band": [0.75, 0.9], "horizon": 3, "side": -1}),
])
def test_on_honest_bars_the_two_implementations_agree_trade_for_trade(family, orig,
                                                                       params) -> None:
    df = _bars()
    families_orthogonal._PRIM_CACHE.clear()
    a = _orig_rows(df, list(orig(df, **params)))
    sigs, why = rep.signals_for(family, df, params)
    assert sigs is not None, why
    b = [dataclasses.asdict(f) for f in rep.simulate(df, sigs, META)]
    cmp = rep.compare(a, b)
    assert len(a) > 10, "the fixture must actually trade"
    assert cmp["agree"], cmp


def test_a_planted_engine_difference_is_a_disagreement_that_names_the_trade() -> None:
    df = _bars()
    sigs, _ = rep.signals_for("overnight_gap_decay", df, {})
    a = [dataclasses.asdict(f) for f in rep.simulate(df, sigs, META)]
    b = [dict(x) for x in a]
    b[3]["r"] += 0.01
    del b[5]
    cmp = rep.compare(a, b)
    assert not cmp["agree"] and cmp["n_r_disagree"] == 1 and cmp["n_only_original"] == 1


def test_unsupported_specs_are_refused_by_name_never_guessed() -> None:
    df = _bars(400)
    assert rep.signals_for("carry", df, {})[0] is None
    s, why = rep.signals_for("session_range_breakout", df, {"midpoint_filter": "prev_day"})
    assert s is None and "midpoint_filter" in why
    s, why = rep.signals_for("discovered", df, {"feature": "ext_resid_EURGBP_z",
                                                "band": [0.9, 1.0]})
    assert s is None and "price-native" in why


def test_the_contract_costs_match_the_engines_cost_model() -> None:
    c = Costs.from_symbol(META)
    assert rep.round_trip_price(META) == pytest.approx(c.per_oz_roundtrip() / c.contract_oz)
    assert rep.swap_price_per_night(META) == pytest.approx(c.financing(1.0) / c.contract_oz)


def test_the_verifier_never_counts_unsupported_as_agreement(monkeypatch) -> None:
    import independent_verifier as iv
    row = iv.verify_one("x", {"shadow_spec": {"symbol": "CHFNOK", "family": "carry",
                                              "params": {}}}, {})
    assert row["verdict"] == iv.UNSUPPORTED
    canon = {"a": {}, "b": {}, "c": {}}
    sleeves = {"sleeves": [{"status": "LIVE", "certificate": {"cell": "c"}},
                           {"status": "RETIRED", "certificate": {"cell": "a"}}]}
    order, promoted = iv.certificate_order(canon, sleeves)
    assert order[0] == "c" and promoted == {"c"}
