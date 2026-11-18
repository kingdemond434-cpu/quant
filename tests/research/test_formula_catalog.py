"""The published libraries: the catalogue's census, and at least ten formulas per library
evaluated against an INDEPENDENT reference -- plain Python loops over the bar list, written from
the publication's definitions, sharing no code with `formula_ops`. The published text of each is
pinned too, so a transcription change cannot pass by changing both sides."""
from __future__ import annotations

import math
from collections.abc import Callable

import numpy as np
import pandas as pd
import pytest

from libs.research import formula_catalog as fc
from libs.research import formula_ops as fo

N = 160
NAN = float("nan")


def _bars(seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, N)))
    opn = close * np.exp(rng.normal(0, 0.003, N))
    high = np.maximum(opn, close) * np.exp(np.abs(rng.normal(0, 0.003, N)))
    low = np.minimum(opn, close) * np.exp(-np.abs(rng.normal(0, 0.003, N)))
    vol = rng.integers(50, 500, N).astype(float)
    idx = pd.date_range("2024-01-01", periods=N, freq="h", tz="UTC")
    return pd.DataFrame({"open": opn, "high": high, "low": low, "close": close,
                         "tick_volume": vol}, index=idx)


BARS = {"S1": _bars(1), "S2": _bars(2), "S3": _bars(3), "S4": _bars(4)}
FIELDS = fo.panel_from_bars(BARS, None)
OP, H, L, C, V = (BARS["S1"][k].tolist() for k in ("open", "high", "low", "close",
                                                   "tick_volume"))


def _cmp(got: pd.Series, want: list[float]) -> None:
    g = got.to_numpy(dtype=float)
    w = np.asarray(want, dtype=float)
    assert np.array_equal(np.isnan(g), np.isnan(w)), "absent bars differ"
    ok = ~np.isnan(w)
    assert ok.sum() > N // 3
    np.testing.assert_allclose(g[ok], w[ok], rtol=1e-9, atol=1e-12)


# ---------------------------------------------------------------- reference helpers (loops)
def delay(x: list[float], n: int) -> list[float]:
    return [NAN] * n + x[:-n] if n else list(x)


def win(x: list[float], i: int, n: int, full: bool) -> list[float] | None:
    lo = i - n + 1
    if lo < 0:
        if full:
            return None
        lo = 0
    w = x[lo:i + 1]
    if full and any(math.isnan(v) for v in w):
        return None
    return w


def roll(x: list[float], n: int, fn: Callable[[list[float]], float], full: bool = True
         ) -> list[float]:
    out = []
    for i in range(len(x)):
        w = win(x, i, n, full)
        if not full and w is not None:
            w = [v for v in w if not math.isnan(v)]
        out.append(NAN if not w else fn(w))
    return out


def mean(w: list[float]) -> float:
    return sum(w) / len(w)


def sstd(w: list[float]) -> float:
    if len(w) < 2:
        return NAN
    m = mean(w)
    return math.sqrt(sum((v - m) ** 2 for v in w) / (len(w) - 1))


def ew(op: Callable[[float, float], float], a: list[float], b: list[float]) -> list[float]:
    return [NAN if (math.isnan(x) or math.isnan(y)) else op(x, y) for x, y in zip(a, b,
                                                                                    strict=True)]


def div(a: list[float], b: list[float]) -> list[float]:
    return [NAN if (math.isnan(x) or math.isnan(y) or y == 0) else x / y
            for x, y in zip(a, b, strict=True)]


def scal(a: list[float], k: float) -> list[float]:
    return [v * k for v in a]


def sma(x: list[float], n: int, m: int) -> list[float]:
    out, y = [], NAN
    for v in x:
        if math.isnan(v):
            out.append(y)
            continue
        y = v if math.isnan(y) else (v * m + y * (n - m)) / n
        out.append(y)
    return out


def lowday(x: list[float], n: int) -> list[float]:
    def fn(w: list[float]) -> float:
        return float(n - 1 - w.index(min(w)))
    return roll(x, n, fn)


def highday(x: list[float], n: int) -> list[float]:
    def fn(w: list[float]) -> float:
        return float(n - 1 - w.index(max(w)))
    return roll(x, n, fn)


def slope(w: list[float]) -> float:
    if len(w) < 2:
        return NAN
    xs = list(range(1, len(w) + 1))
    xm, ym = mean(xs), mean(w)
    return (sum((a - xm) * (b - ym) for a, b in zip(xs, w, strict=True))
            / sum((a - xm) ** 2 for a in xs))


def lin_quantile(w: list[float], q: float) -> float:
    s = sorted(w)
    pos = q * (len(s) - 1)
    lo = math.floor(pos)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


# ---------------------------------------------------------------- the census
def test_census_counts_per_library() -> None:
    c = fc.census()
    assert (c["gtja191"]["published"], c["gtja191"]["testable"]) == (191, 140)
    assert (c["alpha158"]["published"], c["alpha158"]["testable"]) == (158, 157)
    assert (c["alpha360"]["published"], c["alpha360"]["testable"]) == (360, 300)
    assert c["gtja191"]["nontestable_by_reason"]["MALFORMED:text"] == 7
    assert c["gtja191"]["nontestable_by_reason"]["MISSING_FIELD:vwap"] == 36
    assert c["gtja191"]["cross_sectional"] == 30
    assert c["alpha158"]["cross_sectional"] == c["alpha360"]["cross_sectional"] == 0


def test_every_testable_formula_evaluates_on_ohlc_and_tick_volume() -> None:
    for lib in fc.libraries():
        for f in fc.by_library(lib):
            if f.status != "TESTABLE":
                assert f.why_not()
                continue
            out = fc.evaluate(f.key, FIELDS)
            assert list(out.columns) == list(BARS), f.key
            assert f.volume_proxy == ("tick" if "volume" in f.fields() else None), f.key


def test_volume_reads_are_marked_tick_proxies() -> None:
    assert fc.get("alpha158_VMA5").volume_proxy == "tick"
    assert fc.get("alpha158_KMID").volume_proxy is None


# ---------------------------------------------------------------- GTJA-191, eleven + one panel
GTJA_REF: dict[str, tuple[str, Callable[[], list[float]]]] = {
    "014": ("CLOSE-DELAY(CLOSE,5)", lambda: ew(lambda a, b: a - b, C, delay(C, 5))),
    "018": ("CLOSE/DELAY(CLOSE,5)", lambda: div(C, delay(C, 5))),
    "020": ("(CLOSE-DELAY(CLOSE,6))/DELAY(CLOSE,6)*100",
            lambda: scal(div(ew(lambda a, b: a - b, C, delay(C, 6)), delay(C, 6)), 100)),
    "024": ("SMA(CLOSE-DELAY(CLOSE,5),5,1)",
            lambda: sma(ew(lambda a, b: a - b, C, delay(C, 5)), 5, 1)),
    "031": ("(CLOSE-MEAN(CLOSE,12))/MEAN(CLOSE,12)*100",
            lambda: scal(div(ew(lambda a, b: a - b, C, roll(C, 12, mean)), roll(C, 12, mean)),
                         100)),
    "034": ("MEAN(CLOSE,12)/CLOSE", lambda: div(roll(C, 12, mean), C)),
    "046": ("(MEAN(CLOSE,3)+MEAN(CLOSE,6)+MEAN(CLOSE,12)+MEAN(CLOSE,24))/(4*CLOSE)",
            lambda: div([a + b + c + d for a, b, c, d in zip(
                roll(C, 3, mean), roll(C, 6, mean), roll(C, 12, mean), roll(C, 24, mean),
                strict=True)], scal(C, 4))),
    "053": ("COUNT(CLOSE>DELAY(CLOSE,1),12)/12*100",
            lambda: scal(roll([NAN if math.isnan(p) else float(c > p)
                               for c, p in zip(C, delay(C, 1), strict=True)], 12, sum),
                         100 / 12)),
    "065": ("MEAN(CLOSE,6)/CLOSE", lambda: div(roll(C, 6, mean), C)),
    "071": ("(CLOSE-MEAN(CLOSE,24))/MEAN(CLOSE,24)*100",
            lambda: scal(div(ew(lambda a, b: a - b, C, roll(C, 24, mean)), roll(C, 24, mean)),
                         100)),
    "088": ("(CLOSE-DELAY(CLOSE,20))/DELAY(CLOSE,20)*100",
            lambda: scal(div(ew(lambda a, b: a - b, C, delay(C, 20)), delay(C, 20)), 100)),
    "103": ("((20-LOWDAY(LOW,20))/20)*100",
            lambda: [NAN if math.isnan(v) else (20 - v) / 20 * 100 for v in lowday(L, 20)]),
    "133": ("((20-HIGHDAY(HIGH,20))/20)*100-((20-LOWDAY(LOW,20))/20)*100",
            lambda: [NAN if math.isnan(a) else (20 - a) / 20 * 100 - (20 - b) / 20 * 100
                     for a, b in zip(highday(H, 20), lowday(L, 20), strict=True)]),
}


@pytest.mark.parametrize("fid", sorted(GTJA_REF))
def test_gtja_formula_matches_reference(fid: str) -> None:
    text, ref = GTJA_REF[fid]
    f = fc.get(f"gtja191_alpha{fid}")
    assert f is not None and f.status == "TESTABLE"
    assert f.text.replace(" ", "") == text.replace(" ", "")
    _cmp(fc.evaluate(f.key, FIELDS)["S1"], ref())


def test_gtja_cross_sectional_rank_matches_reference() -> None:
    f = fc.get("gtja191_alpha185")
    assert f is not None and f.needs_panel
    assert f.text.replace(" ", "") == "RANK((-1*((1-(OPEN/CLOSE))^2)))"
    out = fc.evaluate(f.key, FIELDS)
    for t in range(N):
        vals = {s: -((1 - b["open"].iloc[t] / b["close"].iloc[t]) ** 2) for s, b in BARS.items()}
        for s, v in vals.items():
            less = sum(1 for u in vals.values() if u < v)
            eq = sum(1 for u in vals.values() if u == v)
            assert out[s].iloc[t] == pytest.approx((less + (eq + 1) / 2) / len(vals))


# ---------------------------------------------------------------- Alpha158, twelve
A158_REF: dict[str, tuple[str, Callable[[], list[float]]]] = {
    "KMID": ("($close-$open)/$open", lambda: div(ew(lambda a, b: a - b, C, OP), OP)),
    "KLEN": ("($high-$low)/$open", lambda: div(ew(lambda a, b: a - b, H, L), OP)),
    "KUP": ("($high-Greater($open, $close))/$open",
            lambda: div(ew(lambda h, m: h - m, H, ew(max, OP, C)), OP)),
    "KSFT": ("(2*$close-$high-$low)/$open",
             lambda: div([2 * c - h - lo for c, h, lo in zip(C, H, L, strict=True)], OP)),
    "OPEN0": ("$open/$close", lambda: div(OP, C)),
    "ROC5": ("Ref($close, 5)/$close", lambda: div(delay(C, 5), C)),
    "MA5": ("Mean($close, 5)/$close", lambda: div(roll(C, 5, mean, full=False), C)),
    "STD5": ("Std($close, 5)/$close", lambda: div(roll(C, 5, sstd, full=False), C)),
    "MAX5": ("Max($high, 5)/$close", lambda: div(roll(H, 5, max, full=False), C)),
    "QTLU5": ("Quantile($close, 5, 0.8)/$close",
              lambda: div(roll(C, 5, lambda w: lin_quantile(w, 0.8), full=False), C)),
    "RSV5": ("($close-Min($low, 5))/(Max($high, 5)-Min($low, 5)+1e-12)",
             lambda: [(c - lo) / (hi - lo + 1e-12) for c, lo, hi in zip(
                 C, roll(L, 5, min, full=False), roll(H, 5, max, full=False), strict=True)]),
    "VMA5": ("Mean($volume, 5)/($volume+1e-12)",
             lambda: [m / (v + 1e-12) for m, v in zip(roll(V, 5, mean, full=False), V,
                                                      strict=True)]),
    "BETA5": ("Slope($close, 5)/$close", lambda: div(roll(C, 5, slope, full=False), C)),
    "IMAX5": ("IdxMax($high, 5)/5",
              lambda: roll(H, 5, lambda w: (w.index(max(w)) + 1) / 5, full=False)),
}


@pytest.mark.parametrize("fid", sorted(A158_REF))
def test_alpha158_formula_matches_reference(fid: str) -> None:
    text, ref = A158_REF[fid]
    f = fc.get(f"alpha158_{fid}")
    assert f is not None and f.status == "TESTABLE"
    assert f.text == text
    _cmp(fc.evaluate(f.key, FIELDS)["S1"], ref())


# ---------------------------------------------------------------- Alpha360, ten
A360_REF: dict[str, tuple[str, Callable[[], list[float]]]] = {
    "CLOSE0": ("$close/$close", lambda: div(C, C)),
    "CLOSE1": ("Ref($close, 1)/$close", lambda: div(delay(C, 1), C)),
    "CLOSE59": ("Ref($close, 59)/$close", lambda: div(delay(C, 59), C)),
    "OPEN0": ("$open/$close", lambda: div(OP, C)),
    "OPEN30": ("Ref($open, 30)/$close", lambda: div(delay(OP, 30), C)),
    "HIGH3": ("Ref($high, 3)/$close", lambda: div(delay(H, 3), C)),
    "HIGH59": ("Ref($high, 59)/$close", lambda: div(delay(H, 59), C)),
    "LOW0": ("$low/$close", lambda: div(L, C)),
    "LOW10": ("Ref($low, 10)/$close", lambda: div(delay(L, 10), C)),
    "VOLUME5": ("Ref($volume, 5)/($volume+1e-12)",
                lambda: [NAN if math.isnan(a) else a / (v + 1e-12)
                         for a, v in zip(delay(V, 5), V, strict=True)]),
}


@pytest.mark.parametrize("fid", sorted(A360_REF))
def test_alpha360_formula_matches_reference(fid: str) -> None:
    text, ref = A360_REF[fid]
    f = fc.get(f"alpha360_{fid}")
    assert f is not None and f.status == "TESTABLE"
    assert f.text == text
    _cmp(fc.evaluate(f.key, FIELDS)["S1"], ref())
