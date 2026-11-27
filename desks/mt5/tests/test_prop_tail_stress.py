"""prop_tail_stress (IDEA_QUEUE row 13): replay arithmetic, scenario magnitudes, verdicts."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_ROOT), str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import prop_tail_stress as pts  # noqa: E402

SPEC = {"buy_stop": {"price": 110.0, "sl": 100.0, "tp": 130.0},
        "sell_stop": {"price": 90.0, "sl": 100.0, "tp": 70.0}}


def _day(rows: list[tuple[int, float, float, float, float]]) -> pd.DataFrame:
    idx = pd.DatetimeIndex([pd.Timestamp("2026-01-05", tz="UTC") + pd.Timedelta(hours=h)
                            for h, *_ in rows])
    return pd.DataFrame([r[1:] for r in rows], index=idx,
                        columns=["open", "high", "low", "close"])


def _synthetic_bars(days: int = 40, seed: int = 0, start: str = "2026-01-05") -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start, periods=days * 24, freq="h", tz="UTC")
    idx = idx[idx.dayofweek < 5]
    close = 2000 + np.cumsum(rng.normal(0, 3, len(idx)))
    op = np.r_[close[0], close[:-1]]
    hi = np.maximum(op, close) + rng.uniform(0, 3, len(idx))
    lo = np.minimum(op, close) - rng.uniform(0, 3, len(idx))
    return pd.DataFrame({"open": op, "high": hi, "low": lo, "close": close}, index=idx)


def test_e8_constants_parsed_not_imported():
    acct = pts.e8_account()
    assert acct.start == 100_000.0
    assert acct.daily_limit == pytest.approx(2_500.0)
    assert acct.max_room == pytest.approx(10_000.0)
    assert "prop.e8_guard" not in sys.modules


def test_parse_constants_ignores_non_numeric(tmp_path):
    f = tmp_path / "m.py"
    f.write_text("A = 1.5\nB: float = 2\nC = 'x'\nD = foo()\n", encoding="utf-8")
    assert pts.parse_constants(f, ("A", "B", "C", "D")) == {"A": 1.5, "B": 2.0}


def test_fusion_unreadable_state_is_none_not_a_default(tmp_path):
    assert pts.fusion_account(state=tmp_path / "missing.json") is None


def test_fusion_measured_floor_and_rail(tmp_path):
    st = tmp_path / "s.json"
    st.write_text(json.dumps({"equity": 484.83, "updated_at": "x"}), encoding="utf-8")
    a = pts.fusion_account(state=st)
    assert a is not None
    # The rail's own constants, read the way the module reads them: the floor moves with the
    # deadman file (it was 300 when this test was written, 10 on 2026-11-14), the arithmetic not.
    rail = pts.parse_constants(pts.FUSION_DEADMAN_SRC, ("EQUITY_FLOOR_EUR", "DAILY_LOSS_PCT"))
    assert set(rail) == {"EQUITY_FLOOR_EUR", "DAILY_LOSS_PCT"}
    assert a.max_room == pytest.approx(484.83 - rail["EQUITY_FLOOR_EUR"])
    assert a.daily_limit == pytest.approx(484.83 * rail["DAILY_LOSS_PCT"])
    assert a.state_basis.startswith("MEASURED")
    pub = pts.published_account(a)
    assert pub["max_room_frac_of_start"] == pytest.approx(
        (484.83 - rail["EQUITY_FLOOR_EUR"]) / 484.83, abs=1e-5)
    assert "484.83" not in json.dumps(pub)


def test_published_stress_carries_no_money_amount():
    xau = _synthetic_bars(60)
    fx = _synthetic_bars(60, seed=1) / 2000.0
    accts = {"E8": pts.e8_account(), "FTMO": pts.ftmo_account(),
             "Fusion": pts.Account("Fusion", "EUR", 484.83, 48.483, 474.83, "MEASURED x")}
    doc = pts.stress(xau=xau, audchf=fx, eurchf=fx, eurusd=fx, accounts=accts, legs=2)
    blob = json.dumps(doc, default=str)
    for amount in ("100000", "2500.0", "10000.0", "484.83", "474.83", "48.483", '"loss"'):
        assert amount not in blob, amount
    v = doc["scenarios"]["snb_2015_fill_near_close"]["accounts"]["E8"]
    assert v["loss_frac_of_start"] * 100 == pytest.approx(
        v["pct_of_daily_limit"] * 0.025, rel=0.01)


def test_long_gap_through_stop_fills_at_open():
    day = _day([(7, 105, 111, 104, 110), (8, 95, 96, 94, 95)])
    legs = pts.replay_day(day, SPEC, oco=True, slip=5.0)
    assert len(legs) == 1 and legs[0]["why"] == "stop"
    assert legs[0]["exit"] == 95                      # the open, not sl - slip
    assert legs[0]["r"] == pytest.approx(-1.5)


def test_intrabar_stop_charges_slip():
    day = _day([(7, 105, 111, 104, 110), (8, 109, 109, 99, 101)])
    legs = pts.replay_day(day, SPEC, oco=True, slip=5.0)
    assert legs[0]["exit"] == 95.0
    assert legs[0]["r"] == pytest.approx(-1.5)


def test_oco_fills_one_leg_and_oco_fail_fills_both():
    day = _day([(7, 100, 111, 89, 100), (8, 100, 100, 100, 100), (19, 100, 100, 100, 100)])
    one = pts.replay_day(day, SPEC, oco=True)
    both = pts.replay_day(day, SPEC, oco=False)
    assert len(one) == 1
    assert len(both) == 2
    assert all(x["why"] == "stop" for x in both)     # whipsaw: both stopped in the bar
    assert sum(x["r"] for x in both) == pytest.approx(-2.0)


def test_target_and_force_close():
    day = _day([(7, 105, 111, 104, 110), (8, 110, 131, 109, 130)])
    assert pts.replay_day(day, SPEC)[0]["why"] == "target"
    day2 = _day([(7, 105, 111, 104, 110), (8, 110, 112, 108, 111), (19, 115, 116, 114, 115)])
    leg = pts.replay_day(day2, SPEC)[0]
    assert leg["why"] == "force_close" and leg["exit"] == 115


def test_mae_records_floating_loss_on_a_winner():
    day = _day([(7, 105, 111, 104, 110), (8, 110, 112, 102, 111), (9, 111, 131, 110, 130)])
    leg = pts.replay_day(day, SPEC)[0]
    assert leg["why"] == "target"
    assert leg["mae_r"] == pytest.approx(-0.8)


def test_no_entry_after_session_end():
    day = _day([(13, 105, 111, 104, 110)])
    assert pts.replay_day(day, SPEC) == []


def test_leg_loss_and_verdicts():
    acct = pts.Account("X", "USD", 100_000, 2_500, 10_000, "ASSUMED")
    assert pts.leg_loss(60, 30, 600) == pytest.approx(1200)
    assert pts.leg_loss(-5, 30, 600) == 0.0
    assert pts.verdict(2_000, acct)["verdict_vs_full_room"] == "SURVIVES_FULL_ROOM"
    assert pts.verdict(2_500, acct)["verdict_vs_full_room"] == "BREACH_DAILY"
    assert pts.verdict(10_000, acct)["verdict_vs_full_room"] == "BREACH_MAX"
    # an assumed state never claims a verdict against current room
    assert pts.verdict(10, acct)["verdict_vs_current_room"] == pts.UNMEASURED


def test_weekend_gap_and_flash_magnitudes():
    b = _synthetic_bars(20)
    i = b.index.get_indexer([b.index[b.index.dayofweek == 0][24]])[0]   # 2nd Monday 00:00
    b.iloc[i, b.columns.get_loc("open")] = b["close"].iloc[i - 1] * 1.05
    b.iloc[i, b.columns.get_loc("high")] = max(b["high"].iloc[i], b["open"].iloc[i])
    w = pts.weekend_gap_pct(b)
    assert w["pct"] == pytest.approx(0.05)
    f = pts.flash_crash_atr_mult(b)
    assert f["atr_mult"] > 0 and f["n_bars"] > 0


def test_weekend_gap_without_weekends_is_unmeasured():
    b = _synthetic_bars(3)
    b = b[b.index.dayofweek < 4]
    b = b[b.index < b.index[0] + pd.Timedelta(days=3)]
    assert pts.weekend_gap_pct(b)["pct"] == pts.UNMEASURED


def test_stress_end_to_end_synthetic():
    xau = _synthetic_bars(60)
    fx = _synthetic_bars(60, seed=1) / 2000.0
    accts = {"E8": pts.e8_account(), "FTMO": pts.ftmo_account(), "Fusion": None}
    doc = pts.stress(xau=xau, audchf=fx, eurchf=fx, eurusd=fx, accounts=accts, legs=2)
    for scen in doc["scenarios"].values():
        assert scen["accounts"]["Fusion"] == pts.UNMEASURED
        for name in ("E8", "FTMO"):
            v = scen["accounts"][name]
            assert v["verdict_vs_full_room"] in {"SURVIVES_FULL_ROOM", "BREACH_DAILY",
                                                 "BREACH_MAX"}
            assert v["verdict_vs_current_room"] == pts.UNMEASURED
    # a percent gap the size of SNB's close-level fill breaches every prop floor
    assert doc["scenarios"]["snb_2015_fill_near_close"]["accounts"]["E8"][
        "verdict_vs_full_room"] == "BREACH_MAX"
    assert "sim_v3" in doc["inputs"]["slip_basis"]


def test_no_order_path_or_account_identity_in_source():
    src = (_DESK / "research" / "prop_tail_stress.py").read_text(encoding="utf-8")
    for bad in ("order_send", "e8_executor", "tradelocker", "place_order", "login"):
        assert bad not in src.lower().replace("login_withheld", "")
