"""execution_feedback: per-sleeve execution cost in R on the initial risk, and priced proposals."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research"), str(DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import execution_feedback as ef  # noqa: E402


def _intent(t, px, sl, spread=0.0004, sleeve="s1", sym="EURUSD", hour=1):
    return {"ticket": t, "intended": px, "sl": sl, "side": "buy", "sleeve": sleeve,
            "symbol": sym, "spread_at_decision": spread, "latency_ms": 90.0,
            "time": f"2026-10-01T{hour:02d}:00:00+00:00"}


def _deal(t, fill, comm=-1.0, swap=-0.5, r=1.0):
    return {"entry_order": t, "position_id": t, "entry_price": fill, "fill_price": fill + 0.002,
            "side": 1, "contract_size": 100000.0, "volume": 0.1, "commission": comm,
            "swap": swap, "r_multiple": r, "symbol": "EURUSD"}


def test_costs_are_in_r_on_the_initial_risk() -> None:
    costs = ef.sleeve_costs([_intent(1, 1.1000, 1.0980), _intent(2, 1.1000, 1.0980)],
                            [_deal(1, 1.1002)])
    c = costs["s1"]
    assert c["fills"] == 1 and c["intents_sent"] == 2 and c["unfilled_brackets"] == 1
    assert c["costs_r"]["slip_r"]["mean"] == pytest.approx(0.1, rel=1e-3)
    assert c["costs_r"]["half_spread_r"]["mean"] == pytest.approx(0.1, rel=1e-3)
    # risk in money = 0.002 x 100000 x 0.1 = 20; commission 1.0 -> 0.05R, swap 0.5 -> 0.025R
    assert c["costs_r"]["commission_r"]["mean"] == pytest.approx(0.05, rel=1e-3)
    assert c["costs_r"]["swap_r"]["mean"] == pytest.approx(0.025, rel=1e-3)
    assert c["total_cost_r_mean"] == pytest.approx(0.275, rel=1e-3)


def test_a_tape_discovery_is_priced_on_its_own_instrument_and_session_only() -> None:
    costs = ef.sleeve_costs([_intent(1, 1.1000, 1.0980)], [_deal(1, 1.1002)])
    sess = costs["s1"]["sessions"][0]
    alpha = {"discoveries": [
        {"instrument": "EURUSD", "cell": f"spread=wide|velocity=fast|session={sess}",
         "effect": {"measure": "delayed_vs_immediate", "diff_bps": 2.0}, "ci": [0.5, 3.5],
         "n": 900, "suggested": "delayed_entry"},
        {"instrument": "GBPUSD", "cell": f"spread=wide|session={sess}",
         "effect": {"diff_bps": 9.0}, "ci": [1, 2], "n": 900, "suggested": "delayed_entry"}]}
    props = ef.proposals(costs, alpha, {})
    assert [p["symbol"] for p in props] == ["EURUSD"]
    p = props[0]
    # 2 bps of 1.1002 = 0.00022 over a 0.0020 stop = 0.11R a trade
    assert p["delta_r_per_trade"] == pytest.approx(0.110011, rel=1e-3)
    assert p["status"] == "SUPPORTED" and p["fraction_basis"] == "default_0.01"


def test_a_straddling_interval_is_never_supported() -> None:
    costs = ef.sleeve_costs([_intent(1, 1.1000, 1.0980)], [_deal(1, 1.1002)])
    alpha = {"discoveries": [{"instrument": "EURUSD", "cell": "spread=wide|session=all",
                              "effect": {"diff_bps": 2.0}, "ci": [-0.5, 3.5], "n": 900,
                              "suggested": "delayed_entry"}]}
    (p,) = ef.proposals(costs, alpha, {})
    assert p["status"] == "CANDIDATE"


def test_e8_is_named_unmeasured_and_the_leg_is_wired(tmp_path, monkeypatch) -> None:
    for name in ("INTENTS", "LEDGER", "E8_INTENTS", "EXECUTION_ALPHA", "SLEEVES"):
        monkeypatch.setattr(ef, name, tmp_path / f"{name}.missing")
    doc = ef.build()
    assert doc["accounts"]["e8"]["status"] == ef.UNMEASURED
    assert doc["tape_source"].startswith(ef.UNMEASURED)
    text = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_costed("execution_feedback"' in text
