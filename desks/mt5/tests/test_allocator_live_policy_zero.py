"""The Fusion book funds only what the principal's live policy lets the Fusion account trade.

Hourly pass P63 (2026-11-05): the dynamic book put 30% heat on seven cells outside
data/live_sleeve_policy.json; the gateway could size none of them and the join read BROKEN.
`live_policy_zero` binds those columns to 0 through the exchange-zero path, which refills their
heat across the columns that can trade.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import live_policy as lp  # noqa: E402

from research import pf_allocator as pa  # noqa: E402


@pytest.fixture
def policy(tmp_path, monkeypatch):
    pol = tmp_path / "live_sleeve_policy.json"
    pol.write_text(json.dumps({
        "by": "test", "live_symbols": ["XAUUSD", "USDJPY", "EURZAR"],
        "banned_timeframes": {"XAUUSD": ["M15"]}, "banned_families": ["discovered"],
        "live_sleeves": {"EURZAR": ["eurzar_carry_asia_p_8339"]}}), "utf-8")
    monkeypatch.setattr(lp, "POLICY_FILE", pol)
    data = tmp_path / "data"
    data.mkdir()
    (data / "sleeves.json").write_text(json.dumps({"sleeves": [
        {"name": "eurzar_carry_asia_p_8339", "symbol": "EURZAR", "family": "carry",
         "selector": "asia", "status": "RETIRED"},
        {"name": "xau_m5_anti_momentum_ny", "symbol": "XAUUSD", "family": "anti_momentum",
         "exec": "scalp_market", "timeframe": "M5", "status": "STANDBY"}]}), "utf-8")
    monkeypatch.setattr(pa, "BASE", tmp_path)
    return tmp_path


def test_columns_the_fusion_account_may_not_trade_are_zeroed(policy) -> None:
    names = ["NZDCHF_clock_transition_asia", "CHFDKK_cross_asset_residual_asia",
             "gold_asia", "gold_london_am", "xau_m15_anti_breakout", "xau_m5_anti_momentum_ny",
             "USDJPY_session_range_breakout_asia", "USDJPY_discovered_asia",
             "EURZAR_carry_asia", "EURZAR_formula_asia"]
    zero, meta = pa.live_policy_zero(names)
    assert zero == {"NZDCHF_clock_transition_asia", "CHFDKK_cross_asset_residual_asia",
                    "xau_m15_anti_breakout", "USDJPY_discovered_asia", "EURZAR_formula_asia",
                    "xau_m5_anti_momentum_ny"}
    assert meta["status"] == "MEASURED" and meta["n_zeroed"] == 6
    # #748 MF1: a column that resolves to a roster row is judged by live_policy.refuse on it,
    # so the stood-down scalp_market lane is zeroed; EURZAR_carry_asia joins its allowlisted row
    assert "scalp_market" in meta["zeroed"]["xau_m5_anti_momentum_ny"]
    assert "EURZAR_carry_asia" not in zero and meta["n_resolved_to_rows"] == 2
    assert "outside the live sleeve universe" in meta["zeroed"]["NZDCHF_clock_transition_asia"]
    assert "M15" in meta["zeroed"]["xau_m15_anti_breakout"]
    assert "allowlisted" in meta["zeroed"]["EURZAR_formula_asia"]


def test_the_zero_reaches_every_solve_and_the_published_artifact() -> None:
    src = (_DESK / "research" / "pf_allocator.py").read_text(encoding="utf-8")
    run_src = src[src.index("def run(mode"):]
    i = run_src.index("lp_zero, live_policy_meta = live_policy_zero(")
    j = run_src.index("ts_zero = ts_zero | lp_zero")
    k = run_src.index("def _psb(")
    assert i < j < k
    assert '"live_policy": live_policy_meta,' in run_src


def test_the_name_parser_keeps_multi_token_selectors_and_selectorless_families() -> None:
    assert pa._column_identity("GBPJPY_session_range_breakout_london_am") == (
        "GBPJPY", "session_range_breakout", "")
    assert pa._column_identity("EURZAR_relative_value") == ("EURZAR", "relative_value", "")
    assert pa._column_identity("xau_m15_anti_breakout") == ("XAUUSD", "anti_breakout", "M15")
    assert pa._column_identity("gold_afternoon") == ("XAUUSD", "", "")


def test_the_fallback_is_re_solved_on_the_admissible_columns() -> None:
    import numpy as np

    from libs.portfolio.robust_elog import SleeveEvidence
    rng = np.random.default_rng(1)
    ev = [SleeveEvidence(n, rng.normal(0.001, 0.01, 200)) for n in ("a", "b", "c")]
    fb = pa.fallback_on_admissible("equal_weight", ev, frozenset({"c"}), 0.2)
    assert fb is not None and set(fb) == {"a", "b"}
    assert abs(sum(fb.values()) - 0.2) < 1e-9 and abs(fb["a"] - fb["b"]) < 1e-12
    iv = pa.fallback_on_admissible("inverse_vol", ev, frozenset({"c"}), 0.2)
    assert iv is not None and "c" not in iv
    assert pa.fallback_on_admissible("multiperiod", ev, frozenset({"c"}), 0.2) is None
    # a challenger whose rebuild raises is named, never read as "needs the worlds"
    import libs.portfolio.challengers as ch
    why: dict[str, str] = {}
    orig = ch.all_books
    try:
        ch.all_books = lambda *_a, **_k: (_ for _ in ()).throw(ValueError("bad cov"))
        assert pa.fallback_on_admissible("hrp", ev, frozenset({"c"}), 0.2, why) is None
    finally:
        ch.all_books = orig
    assert why["fallback"] == "all_books failed: ValueError: bad cov"
    src = (_DESK / "research" / "pf_allocator.py").read_text(encoding="utf-8")
    assert "fallback_on_admissible(best, ev, ts_zero" in src
