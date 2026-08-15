"""Every playbook rule, on data built to make it fire -- and on data built to keep it silent.

THE FAILURE THIS EXISTS FOR. A detector that never fires is indistinguishable, in every report the
desk produces, from one that fired and found nothing: same empty list, same green tests, same
"wired" status. Ten inert rules would look exactly like ten working ones until the day somebody
asked why the discretionary sleeve had never journalled an intent.

So each rule gets two tests: a scenario CONSTRUCTED to satisfy its stated mechanism, where it must
produce a setup with the right direction, and a null scenario where it must stay quiet. A rule that
fires on both is a rule that fires on anything.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import pytest

from libs.discretionary import rules as R
from libs.discretionary import tape as T


def _frame(close: list[float] | np.ndarray, *, vol: list[float] | np.ndarray | None = None,
           spread: float = 0.002, freq: str = "D") -> pd.DataFrame:
    c = np.asarray(close, dtype="float64")
    v = np.full(len(c), 1000.0) if vol is None else np.asarray(vol, dtype="float64")
    return pd.DataFrame(
        {"open": c, "high": c * (1 + spread), "low": c * (1 - spread), "close": c, "volume": v},
        index=pd.date_range("2025-01-01", periods=len(c), freq=freq, tz="UTC"))


def _quiet(n: int = 400, seed: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return _frame(100 * np.cumprod(1 + rng.normal(0.0, 0.004, n)))


# ---------------------------------------------------------------- H1
def test_H1_FIRES_ON_A_TWICE_TESTED_LEVEL_WITH_AN_RSI_EXTREME() -> None:
    """Level touched repeatedly, then approached again on a strong rally -> fade short."""
    # the SAME level tested twice, then approached again on a rally that lifts RSI(14) past 70.
    # tight spread so the level's touches land inside the 0.3xATR tolerance rather than beside it
    seg = list(np.linspace(100, 108, 10)) + list(np.linspace(108, 100, 10))
    b = _frame([100.0] * 70 + seg + seg + list(np.linspace(100, 108, 20)), spread=0.0005)
    got = R.h1_structural_fade(b)
    assert got, "a repeatedly-tested level approached on an RSI extreme must produce a fade"
    assert got[0].direction == -1
    assert got[0].stop > got[0].entry_price, "a short's stop sits ABOVE entry"


def test_H1_IS_SILENT_WITHOUT_THE_RSI_EXTREME() -> None:
    """The level alone is not the hypothesis -- exhaustion is. Firing without it would make H1 a
    support/resistance rule, which is a different and much-tested claim."""
    assert not R.h1_structural_fade(_quiet())


# ---------------------------------------------------------------- H2
def test_H2_FIRES_ON_A_CHANNEL_BREAK_WITH_VOLUME() -> None:
    c = [100.0] * 50 + [100.5, 101.0, 106.0]
    v = [1000.0] * 50 + [1000.0, 1000.0, 5000.0]
    got = R.h2_volume_breakout(_frame(c, vol=v))
    assert got and got[0].direction == +1
    assert got[0].target > got[0].entry_price > got[0].stop


def test_H2_IS_SILENT_ON_THE_SAME_BREAK_WITHOUT_VOLUME() -> None:
    """THE PRE-REGISTERED ABLATION. H2 dies if volume adds nothing over the bare break, so the
    volume gate must be load-bearing -- identical prices, ordinary volume, no setup."""
    c = [100.0] * 50 + [100.5, 101.0, 106.0]
    assert not R.h2_volume_breakout(_frame(c, vol=[1000.0] * 53))


# ---------------------------------------------------------------- H6
def test_H6_FIRES_ON_A_SPRING_AND_NOT_ON_A_BREAKDOWN() -> None:
    """The RECOVERY is the signal. A break that stays broken is a trend and must not register."""
    rng = np.random.default_rng(1)
    base = list(100 + rng.normal(0, 0.3, 60))
    spring = _frame([*base, 96.0, 100.0])            # pierces the range low, closes back inside
    got = R.h6_wyckoff(spring)
    assert got and got[0].direction == +1 and "spring" in got[0].rule_id

    broken = _frame([*base, 96.0, 94.0])             # stays out: a trend, not a spring
    assert not R.h6_wyckoff(broken)


# ---------------------------------------------------------------- H7
def test_H7_FIRES_ONLY_WITH_THE_SLOPE_AND_NOT_AGAINST_IT() -> None:
    """The slope filter is a GATE. Fading a deviation against a trending VWAP is the losing half
    of this trade, and a rule that took both would be averaging a mechanism with its inverse."""
    up = [*np.linspace(100, 120, 60), 110.0]   # dip below a RISING vwap -> long
    got = R.h7_vwap_reversion(_frame(up))
    assert got and got[0].direction == +1

    down = [*np.linspace(120, 100, 60), 110.0]  # same dip shape, FALLING vwap -> silent
    assert not [s for s in R.h7_vwap_reversion(_frame(down)) if s.direction == +1]


# ---------------------------------------------------------------- H8
def test_H8_FIRES_ON_A_RETURN_TO_A_BASE_THAT_ACTUALLY_DEPARTED() -> None:
    rng = np.random.default_rng(5)
    pre = list(100 + rng.normal(0, 0.5, 55))
    base = [110.0, 110.1, 110.0]                     # tight base
    impulse = [125.0]                                # departure must be IMPULSIVE, not a drift
    back = list(np.linspace(125, 110.05, 20))        # return to the zone
    got = R.h8_supply_demand(_frame(pre + base + impulse + back))
    assert got and got[0].direction == +1 and "demand" in got[0].rule_id


def test_H8_IGNORES_A_BASE_WITH_NO_DEPARTURE() -> None:
    """A narrow range with nothing after it is quiet tape. Admitting those fills the book with
    every consolidation on the chart."""
    b = _frame([100.0] * 55 + [110.0, 110.1, 110.0] + [110.0] * 30)
    assert not R.h8_supply_demand(b)


# ---------------------------------------------------------------- H9
def test_H9_REFUSES_DAILY_BARS_RATHER_THAN_RETURNING_NOTHING() -> None:
    """An 'opening range' on daily candles is the day itself, which is not the hypothesis. It must
    decline, and the caller reports UNAVAILABLE -- silence here would read as 'no break today'."""
    assert not R.h9_opening_range(_frame([100.0] * 60, freq="D"))


def test_H9_FIRES_ON_INTRADAY_BARS_WITH_VOLUME() -> None:
    c = [100.0, 100.2, 100.1, 100.3] + [100.2] * 30 + [103.0]
    v = [1000.0] * 34 + [9000.0]
    b = _frame(c, vol=v, freq="h")
    got = R.h9_opening_range(b, session="utc_midnight")
    assert got and got[0].direction == +1


def test_H9_TESTS_EXACTLY_THE_THREE_REGISTERED_SESSIONS() -> None:
    """'session definitions (00:00 UTC, US open, Asia open) are pre-registered as the ONLY three
    tested'. A fourth is a new trial and must be counted as one."""
    assert set(R.SESSIONS_UTC) == {"utc_midnight", "asia_open", "us_open"}


# ---------------------------------------------------------------- H10
def test_H10_FIRES_ON_EXPANSION_OUT_OF_A_SQUEEZE_AND_TAKES_ITS_DIRECTION() -> None:
    """Direction comes from the EXPANSION, never the squeeze -- a compression is direction-free by
    construction, and picking a side before the break is where this family invents an edge."""
    rng = np.random.default_rng(9)
    # the squeeze must sit in the bottom decile of the 60-bar bandwidth window, and the 20-bar
    # rolling std at the break must be entirely quiet -- otherwise the "squeeze" still carries
    # loud bars and the rule is right to decline
    loud = list(100 + rng.normal(0, 4.0, 120))
    quiet = list(100 + rng.normal(0, 0.03, 25))
    up = _frame(loud + quiet + [112.0])
    got = R.h10_vol_compression(up)
    assert got and got[0].direction == +1

    down = _frame(loud + quiet + [88.0])
    got2 = R.h10_vol_compression(down)
    assert got2 and got2[0].direction == -1


# ---------------------------------------------------------------- H11
def test_H11_FIRES_AT_THE_BAND_AND_TARGETS_THE_MEAN() -> None:
    b = _frame([100.0] * 40 + [88.0])
    got = R.h11_band_fade(b)
    assert got and got[0].direction == +1
    assert got[0].target > got[0].entry_price, "a band fade targets the mean it deviated from"


# ---------------------------------------------------------------- H4 / H5, tape-fed
#
# THESE BUILD REAL PROFILES FROM SYNTHETIC PRINTS rather than stubbing the dataclass. The stub the
# first version used carried poc/vah/val/cvd and nothing else, which is exactly the shape that let
# a scalar CVD be compared against a DAILY candle extreme: the stub could not represent a window,
# so the window mismatch was unrepresentable in the test too.
_HOUR = 3_600_000


class _Prof:
    """A minimal profile double for the value-area geometry tests, which need no bars."""

    def __init__(self, poc: float, vah: float, val: float, last_price: float) -> None:
        self.poc, self.vah, self.val = poc, vah, val
        self.last_price, self.bars, self.cvd = last_price, (), 0.0


def _tape(bars: list[tuple[float, int, int]]) -> list[tuple[int, float, float, bool]]:
    """(price, n_buyer_aggressed, n_seller_aggressed) per hour -> aggTrade tuples.

    `m=True` means the BUYER was the maker, so the aggressor was a SELLER. Spelling the two counts
    out per bar is the whole point: delta is the only column here no candle source can supply, and
    a helper that derived it from price direction would be testing the folk method instead.
    """
    out: list[tuple[int, float, float, bool]] = []
    for h, (px, n_buy, n_sell) in enumerate(bars):
        t0 = h * _HOUR
        for j in range(n_buy + n_sell):
            out.append((t0 + j * 1000, float(px), 1.0, j >= n_buy))
    return out


def _profile(bars: list[tuple[float, int, int]]) -> Any:
    """A profile over `bars`. One extra hour is appended and then dropped by `tape_bars` as the
    in-progress bucket, so the window under test is exactly `bars`."""
    return T.volume_profile(_tape([*bars, (bars[-1][0], 1, 0)]))


def test_H4_FADES_A_PRINT_OUTSIDE_THE_VALUE_AREA_TOWARD_THE_POC() -> None:
    got = R.h4_auction_value(_Prof(poc=100.0, vah=105.0, val=95.0, last_price=112.0))
    assert got and got[0].direction == -1
    assert got[0].target == 100.0, "an unaccepted print reverts to where volume actually traded"


def test_H4_IS_SILENT_INSIDE_THE_VALUE_AREA() -> None:
    """Price inside the area is the auction doing what it should. That is not a signal."""
    assert not R.h4_auction_value(_Prof(poc=100.0, vah=105.0, val=95.0, last_price=101.0))


#: A base auction with real width: twenty hours oscillating across a few price bins, so the value
#: area is an interval rather than a single bin. A degenerate zero-width area is refused by H4 (a
#: stop half a width beyond the edge would be a zero-distance stop) and would test nothing here.
_BASE = [(100.0 + (i % 5) * 0.5, 20, 10) for i in range(20)]


def test_H4_READS_THE_TAPES_LAST_PRINT_NOT_A_CANDLE_CLOSE() -> None:
    """The profile is built from the last day of prints. Judging it against a DAILY bar's close
    asks whether a level up to twenty hours old sits outside an auction measured to the minute."""
    p = _profile([*_BASE, (130.0, 20, 10)])
    assert p is not None and p.last_price == pytest.approx(130.0)
    assert p.vah > p.val, "the value area must have width or H4 is right to decline"
    got = R.h4_auction_value(p)
    assert got and got[0].direction == -1 and got[0].entry_price == pytest.approx(130.0)
    assert got[0].target == pytest.approx(p.poc)


def test_H5_FADES_A_NEW_HIGH_THE_AGGRESSORS_DID_NOT_FUND() -> None:
    """THE STATEMENT OHLCV CANNOT MAKE. A new high carried by makers rather than aggressors is
    being sold into -- which is why this hypothesis waited for the tape."""
    rising = [(100.0 + i * 0.5, 20, 5) for i in range(20)]     # net-bought all the way up
    p = _profile([*rising, (115.0, 2, 40)])                    # new high, heavily seller-aggressed
    assert p is not None
    got = R.h5_cvd_divergence(p)
    assert got and got[0].direction == -1
    assert "not funded" in got[0].note


def test_H5_IS_SILENT_WHEN_FLOW_CONFIRMS_THE_MOVE() -> None:
    rising = [(100.0 + i * 0.5, 20, 5) for i in range(20)]
    p = _profile([*rising, (115.0, 40, 2)])                    # new high, aggressors funded it
    assert p is not None and not R.h5_cvd_divergence(p)


def test_H5_TESTS_A_DIVERGENCE_AND_NOT_THE_SIGN_OF_ONE_SCALAR() -> None:
    """THE DEFECT THE FIRST VERSION SHIPPED WITH. It fired on `cvd < 0` -- the sign of cumulative
    delta over the whole window. On a tape with any persistent imbalance that scalar holds one
    sign for days, so the rule was "new high while the day happens to be net-sold": constant in
    one regime, silent in the other, and in neither case the registered comparative claim.

    Here an early flush leaves the window's SCALAR deeply negative for the rest of the day, while
    over the ten bars that matter cumulative delta climbs with price and sets a new local high
    alongside it. A LEVEL test shorts this. A DIVERGENCE test must not, and that difference is
    the entire hypothesis."""
    flush = [(100.0, 5, 55) for _ in range(10)]                 # -50/bar: cum reaches -500
    recovery = [(101.0 + i, 25, 5) for i in range(10)]          # +20/bar: cum climbs to -300
    p = _profile([*flush, *recovery, (115.0, 35, 5)])           # new high, cum climbs to -270
    assert p is not None
    assert p.cvd < 0, "the scalar is negative -- a level test would short here"
    cum = p.cum_delta()
    assert cum[-1] > max(cum[-11:-1]), "cum delta set a new local high with price"
    assert not R.h5_cvd_divergence(p), "price and flow agree: there is no divergence to trade"


def test_PRICE_AND_FLOW_ARE_MEASURED_ON_ONE_GRID() -> None:
    """The seam this whole rewrite closes: both series come off `profile.bars`, and the scalar is
    trimmed to the same span, so no caller can hand H5 a ten-DAY extreme and one day of flow."""
    p = _profile(_BASE)
    assert p is not None
    assert len(p.cum_delta()) == len(p.bars) == len(_BASE)
    assert p.cum_delta()[-1] == pytest.approx(p.cvd, abs=1e-9), \
        "the scalar cvd IS the last cumulative point -- they can never describe different windows"


def test_A_STALE_TAPE_IS_REFUSED_NOT_FADED() -> None:
    """If a recorder unit stops, every number in the profile stays well-formed and describes an
    auction that has already ended. Only its AGE says so."""
    p = _profile([*_BASE, (130.0, 20, 10)])
    assert p is not None
    fresh_ms = p.last_ts + int(0.5 * _HOUR)
    stale_ms = p.last_ts + int((T.MAX_TAPE_AGE_H + 5) * _HOUR)
    assert R.detect_with_tape(p, now_ms=fresh_ms), "a fresh tape must produce the H4 fade"
    assert R.detect_with_tape(p, now_ms=stale_ms) == []
    assert p.age_h(stale_ms) > T.MAX_TAPE_AGE_H


def test_THE_TAPE_RULES_DECLINE_WITHOUT_A_PROFILE() -> None:
    """No tape must be reported as NO TAPE by the caller, not as no setups. A rule that returned
    silence for a missing input is indistinguishable from one that found nothing."""
    assert R.detect_with_tape(None) == []


# ---------------------------------------------------------------- family-level
def test_EVERY_READY_RULE_IS_CAPABLE_OF_FIRING() -> None:
    """THE ONE THAT WOULD CATCH TEN INERT DETECTORS. Each rule above has a constructed scenario
    proving it can produce a setup; this asserts the registry contains exactly those and nothing
    that has never been shown to fire."""
    assert set(R.READY) == {
        "H1_structural_fade", "H2_volume_breakout", "H6_wyckoff", "H7_vwap_reversion",
        "H8_supply_demand", "H9_opening_range", "H10_vol_compression", "H11_band_fade"}
    assert set(R.TAPE_RULES) == {"H4_auction_value", "H5_cvd_divergence"}


def test_NOTHING_REMAINS_BLOCKED_AND_THE_EMPTY_MAP_IS_THE_FINDING() -> None:
    """H4 and H5 were marked BLOCKED on recorder bringup on 2026-08-04. The recorders have been
    taping signed aggTrades since; the inputs arrived and the label did not change. Nobody
    re-reads a BLOCKED note to ask whether it is still true."""
    assert R.BLOCKED == {}


def test_ONE_BAD_DETECTOR_DOES_NOT_MUTE_THE_FAMILY(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """A crash in one rule reading as 'no setups today' would be a false claim about the other
    nine."""
    def _boom(_b: pd.DataFrame) -> list[R.Setup]:
        raise ValueError("bad frame")

    monkeypatch.setitem(R.READY, "H11_band_fade", _boom)
    R.detect(_frame([100.0] * 40 + [88.0]))          # must not raise


def test_THE_ADAPTER_ACCEPTS_EVERY_RULES_SETUP_NOT_JUST_H3S() -> None:
    """THE BUG THE FIRST LIVE RUN FOUND, and it got past twenty-one green tests.

    `_to_signal` read `sweep_i`/`shift_i`/`entry_i` straight off the ICT dataclass, because when it
    was written H3 was the only rule. Ten rules later, none of which has those fields, the first
    real invocation raised AttributeError -- and every test passed, because the detectors were
    tested and the order path was tested and the SEAM BETWEEN THEM was not.

    This exercises the seam with a Setup from each family.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location("run_disc_undertest",
                                                  "scripts/run_discretionary_live.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    for rule_id, direction in (("H1_structural_fade", -1), ("H6_wyckoff_spring", 1),
                               ("H11_band_fade", -1), ("H5_cvd_divergence", -1)):
        st = R.Setup(rule_id, direction, 100.0, 105.0, 95.0, 3, "note")
        sig = mod._to_signal(st, "BTCUSDT", st.rule_id)
        assert sig.rule_id == rule_id
        assert sig.side == ("BUY" if direction > 0 else "SELL")
        assert sig.entry_price == 100.0 and sig.stop_price == 105.0

    class _ICT:
        direction, entry_price, stop, target = 1, 100.0, 95.0, 110.0
        sweep_i, shift_i, entry_i = 1, 2, 3

    conv = mod._from_ict(_ICT())
    assert conv.rule_id == "H3_ict_sweep_shift"
    assert mod._to_signal(conv, "BTCUSDT", conv.rule_id).side == "BUY"
