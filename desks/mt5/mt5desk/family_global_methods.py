"""FOUR HYPOTHESIS-GENERATION METHODS FROM WORLD PRACTICE, AS EXECUTABLE FAMILIES (2026-11-25).

The generator map (`research/generator_coverage.py`) listed every way a quant shop or a solo
builder generates hypotheses and named the methods no code carried. These four are the ones
judged most likely to add INDEPENDENT positive E[log W] on the desk's own tradables (FX majors
and crosses, metals, energy, indices, crypto CFDs), each written down with its economic prior
BEFORE any data was looked at. The producer is `research/global_methods.py`; it mints cells for
these families through `family_donation.donate_per_family`, every cell an ordinary charged trial.

  cross_sectional_class_ltr        LEARNING-TO-RANK OVER THE CLASS PANEL (LambdaRank, the Numerai /
      WorldQuant / Chinese 机器学习选股 practice; Burges 2010 "From RankNet to LambdaRank to
      LambdaMART"; Poh, Lim, Zohren & Roberts 2021 "Building cross-sectional systematic strategies
      by learning to rank", which applies it to exactly this kind of futures/FX panel). The
      time-series rank learner (`ranked_linear`) learns which BARS of one symbol to trade; this
      learns which MEMBERS of a class to hold on a date. Features are the class's own published
      cross-sectional signals (momentum at five speeds, short reversal, long-run value, low vol,
      low beta), standardised within the row; the label is the member's realised forward
      `hold_d`-day return graded into quartiles; the weights are refit every `refit_d` days on the
      last `train_d` days whose labels were ALREADY REALISED at the refit date. Prior: the
      combination of documented cross-sectional premia is better ranked by a learner that weights
      them by their recent NDCG than by any one of them (Poh et al. 2021: Sharpe ~3x the
      hand-combined baseline). Payer: whoever pays each component premium.

  cross_sectional_class_hf_moment  高频因子 -- INTRADAY REALISED MOMENTS AGGREGATED TO DAILY, ranked
      within the class (the Chinese broker high-frequency factor series: Haitong 海通 "高频因子"
      and Founder 方正 realised-skew / downside-vol-share factors; Amaya, Christoffersen, Jacobs &
      Vasquez 2015 "Does realized skewness predict the cross-section of equity returns?";
      Fernandez-Perez, Frijns, Fuertes & Miffre 2018 "The skewness of commodity futures returns";
      Bollerslev, Li & Zhao 2020 signed jump variation; Bali, Cakici & Whitelaw 2011 MAX).
      measure="skew": long the class's most NEGATIVELY skewed members, short the most positive
      (investors overpay for lottery-like right tails). measure="signed_variation": long the
      members whose bad (downside) realised variance dominates, short good-variance dominance.
      measure="max_ret": long the members whose largest hourly return over the window is smallest
      (the MAX effect). Every moment is computed from the member's OWN H1 returns inside a
      trailing calendar window ending at the decision bar (weekend / session gaps over 4 h are not
      returns), oriented like the class panel (USDXXX inverted in fx_usd). Payer: the lottery buyer.

  value_area_rule                  MARKET PROFILE / VOLUME PROFILE VALUE AREA (Steidlmayer's CBOT
      Market Profile; Dalton, "Mind Over Markets"; the Russian 'объёмный профиль' / Volume Profile
      school that trades it systematically on FX and index futures). Each broker day's profile is
      built from the PRIOR day's bars -- TPO (time-at-price, bars only) or tick volume spread over
      each bar's range -- and its 70% value area [VAL, VAH] around the point of control.
      rule="eighty": the day opens outside yesterday's value area and then closes back inside it
      for `confirm_bars` bars -> trade toward the far edge (the "80% rule": the auction rejected
      the new price and returns to value). rule="acceptance": the day opens outside and the first
      `confirm_bars` bars all close outside on the same side -> follow (the auction accepted the
      new price; initiative flow). Prior: auction theory -- a market rotates inside accepted value
      and trends when it leaves it. Payer: the late reactive trader on the wrong side of the
      auction's verdict.

  volatility_breakout_kr           변동성 돌파 -- LARRY WILLIAMS' VOLATILITY BREAKOUT AS THE KOREAN
      RETAIL-QUANT SCHOOL TRADES IT (Williams, "Long-Term Secrets to Short-Term Trading"; 강환국
      "할 수 있다! 퀀트 투자" and the Korean algo-trading community's 노이즈 비율 refinement). Each
      broker day a resting stop sits at today's open + k x yesterday's range (long) or open - k x
      range (short); a fill is held to the day's end. k_mode="fixed" uses k = 0.5; k_mode="noise"
      uses k = the trailing 20-day mean NOISE RATIO 1 - |open - close| / (high - low): a choppy
      market needs a larger push before a breakout is believed. ma_filter="ma_score" trades only
      when today's open is above (long) / below (short) the average of the 3/5/10/20-day closes.
      Prior: an intraday range expansion beyond yesterday's noise is information arriving, and
      the trend that starts it persists into the close (Williams; the Korean school's measured
      KOSPI/crypto history). Payer: the range-reverting liquidity provider caught by the push.

NO LOOKAHEAD, BY CONSTRUCTION, AND PINNED BY A TEST THAT PERTURBS FUTURE BARS. The class panel is
read AS OF each decision bar's stamp with the same staleness rule as
`families_cross_sectional` (a stale peer is ABSENT that day, never carried forward); every
window is trailing; the rank learner is fitted only on rows whose label window closed at or
before the refit row; the profile is yesterday's. Entry is the next bar's open (`trigger=None`).

THE EXOTIC BAN (zuck, 2026-11-24). An exotic member (`universe_policy.is_exotic_symbol`) is NOT a
member of any class panel here -- not as a leg and not as a peer that shapes a rank -- and an
exotic `symbol` returns []. The producer never mints one.

HONEST LIMITS. A family returns [] (never a fallback) when: the symbol is empty, exotic, or has no
peer class; fewer than `families_cross_sectional.MIN_MEMBERS` non-exotic members are present on a
day (that day is skipped); the bars are too short for the trailing windows; the rank learner has
not yet had `min_train_d` realised rows.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd
from mt5desk import families_cross_sectional as xs
from mt5desk.families import Signal, _atr, _h1, bars_per_day

#: Returns across a gap longer than this are not intraday returns (weekend, session close).
MAX_GAP_H = 4.0

LTR_FEATURES: tuple[str, ...] = ("mom5", "mom20", "mom60", "mom120", "mom250_20", "rev1",
                                 "value250", "vol60", "beta60")
HF_MEASURES: tuple[str, ...] = ("skew", "signed_variation", "max_ret")
VA_RULES: tuple[str, ...] = ("eighty", "acceptance")
VA_PROFILES: tuple[str, ...] = ("tpo", "tick_volume")


# ------------------------------------------------------------------------------- the panel ---
def _is_exotic(symbol: str) -> bool:
    try:
        return bool(xs._policy().is_exotic_symbol(symbol))
    except Exception:
        return False


def class_members(klass: str) -> list[str]:
    """The NON-EXOTIC registry members of `klass`. Module-level so a test can substitute one."""
    return [s for s in xs.class_symbols(klass) if not _is_exotic(s)]


def load_series(symbol: str) -> tuple[np.ndarray, np.ndarray] | None:
    """(stamps ns, closes) of `symbol`'s H1 bars from the store. Module-level for tests."""
    return xs._load_series(symbol)


def clean_panel(d: pd.DataFrame, symbol: str, *, decision_hour: int = 22,
                max_stale_h: float = 12.0) -> dict | None:
    """`families_cross_sectional.class_panel` with exotics removed from the class, and each
    member's full H1 series kept (`series`) for the intraday-moment family.

    Same contract: rows are `symbol`'s own decision bars; a peer is read as of the bar's stamp
    and is ABSENT when its last bar is older than `max_stale_h` hours."""
    if not symbol or _is_exotic(symbol):
        return None
    klass = xs.class_of(symbol)
    if not klass:
        return None
    members = [s for s in class_members(klass) if s.upper() != symbol.upper()]
    pos, stamps = xs._decision_rows(d, decision_hour, max_stale_h)
    if pos.size == 0:
        return None
    stale_ns = float(max_stale_h) * 3_600_000_000_000
    cols: list[np.ndarray] = []
    names: list[str] = []
    series: list[tuple[np.ndarray, np.ndarray]] = []
    for peer in members:
        got = load_series(peer)
        if got is None:
            continue
        t, c = got
        j = np.searchsorted(t, stamps, side="right") - 1
        v = np.full(stamps.size, np.nan, dtype="float64")
        has = j >= 0
        jj = np.where(has, j, 0)
        fresh = has & ((stamps - t[jj]) <= stale_ns)
        v[fresh] = np.log(c[jj[fresh]].astype("float64")) * xs.orientation(peer, klass)
        if np.isfinite(v).sum() == 0:
            continue
        cols.append(v)
        names.append(peer)
        series.append((t, c.astype("float64")))
    if len(names) + 1 < xs.MIN_MEMBERS:
        return None
    own_close = d["close"].to_numpy(dtype="float64")[pos]
    with np.errstate(divide="ignore", invalid="ignore"):
        own = np.where(own_close > 0, np.log(own_close), np.nan) * xs.orientation(symbol, klass)
    own_series = (pd.DatetimeIndex(d.index).as_unit("ns").asi8.astype("int64"),
                  d["close"].to_numpy(dtype="float64"))
    return {"klass": klass, "members": [symbol, *names], "own": 0, "pos": pos,
            "stamps": stamps, "logv": np.column_stack([own, *cols]),
            "orient": xs.orientation(symbol, klass), "close": own_close,
            "series": [own_series, *series],
            "orients": [xs.orientation(s, klass) for s in [symbol, *names]]}


def _prepare(df: pd.DataFrame, symbol: str, decision_hour: int,
             max_stale_h: float) -> tuple[pd.DataFrame, dict] | None:
    if not symbol or df is None or len(df) == 0:
        return None
    d = _h1(df)
    if "close" not in d.columns:
        return None
    panel = clean_panel(d, symbol, decision_hour=decision_hour, max_stale_h=max_stale_h)
    return None if panel is None else (d, panel)


def _xs_center(m: np.ndarray) -> np.ndarray:
    """Per-row percentile rank minus its row mean; 0 where the entry is not finite."""
    r = pd.DataFrame(m).rank(axis=1, pct=True).to_numpy()
    valid = np.isfinite(r)
    n = valid.sum(axis=1, keepdims=True)
    s = np.where(valid, r, 0.0).sum(axis=1, keepdims=True)
    with np.errstate(divide="ignore", invalid="ignore"):
        mu = np.where(n > 0, s / np.maximum(n, 1), 0.0)
    return np.where(valid, r - mu, 0.0)


# ----------------------------------------------------------------------- learning to rank ---
def ltr_features(lv: np.ndarray) -> np.ndarray:
    """rows x members x features, each feature centred-ranked within the row (0 = absent)."""
    sh = xs._shift
    r = xs._returns(lv)
    prior = sh(lv, 1)
    mu = xs._rolling(prior, 250, "mean")
    sd = xs._rolling(prior, 250, "std")
    with np.errstate(divide="ignore", invalid="ignore"):
        value = np.where(sd > 0, -(lv - mu) / sd, np.nan)
    raw = [lv - sh(lv, 5), lv - sh(lv, 20), lv - sh(lv, 60), lv - sh(lv, 120),
           sh(lv, 20) - sh(lv, 250), -r, value, -xs._rolling(r, 60, "std"),
           -xs._beta(r, xs._ew_ex_self(r), 60)]
    return np.stack([_xs_center(f) for f in raw], axis=2)


def _grades(lab: np.ndarray) -> np.ndarray:
    """Within-row quartile grade 0..3 of the realised label, NaN where absent."""
    r = pd.DataFrame(lab).rank(axis=1, pct=True).to_numpy()
    return np.where(np.isfinite(r), np.floor(np.clip(r * 4.0 - 1e-9, 0.0, 3.0)), np.nan)


def lambdarank_fit(x: np.ndarray, g: np.ndarray, w0: np.ndarray | None = None, *,
                   iters: int = 25, lr: float = 2.0, l2: float = 1e-3) -> np.ndarray:
    """Linear LambdaRank: pairwise logistic loss on (better, worse) pairs within each row,
    each pair weighted by the |delta NDCG| of swapping the two at their CURRENT score positions
    (Burges 2010). x: rows x members x features; g: rows x members grades (NaN = no label)."""
    f = x.shape[2]
    w = np.zeros(f) if w0 is None else w0.astype(float).copy()
    valid = np.isfinite(g)
    gain = np.where(valid, 2.0 ** np.where(valid, g, 0.0) - 1.0, 0.0)
    pair = (gain[:, :, None] > gain[:, None, :]) & valid[:, :, None] & valid[:, None, :]
    n_pairs = int(pair.sum())
    if n_pairs == 0:
        return w
    srt = -np.sort(-np.where(valid, gain, 0.0), axis=1)
    disc_ideal = 1.0 / np.log2(np.arange(x.shape[1]) + 2.0)
    idcg = (srt * disc_ideal[None, :]).sum(axis=1)
    idcg = np.where(idcg > 0, idcg, 1.0)
    dgain = np.abs(gain[:, :, None] - gain[:, None, :])
    for _ in range(int(iters)):
        s = x @ w
        s_rank = np.where(valid, s, -np.inf)
        order = np.argsort(-s_rank, axis=1, kind="stable")
        pos = np.empty_like(order)
        np.put_along_axis(pos, order, np.arange(x.shape[1])[None, :].repeat(x.shape[0], 0), 1)
        disc = 1.0 / np.log2(pos + 2.0)
        dndcg = dgain * np.abs(disc[:, :, None] - disc[:, None, :]) / idcg[:, None, None]
        diff = np.clip(s[:, :, None] - s[:, None, :], -30.0, 30.0)
        lam = np.where(pair, dndcg / (1.0 + np.exp(diff)), 0.0)
        coef = lam.sum(axis=2) - lam.sum(axis=1)
        grad = -(coef[:, :, None] * x).sum(axis=(0, 1)) / n_pairs + l2 * w
        w = w - lr * grad
    return w


def ltr_scores(lv: np.ndarray, *, hold_d: int, train_d: int, refit_d: int,
               min_train_d: int) -> np.ndarray:
    """rows x members: the learned score of each member at each decision row, NaN before the
    first fit. The fit at row t reads labels lv[s + hold_d] - lv[s] only for s + hold_d <= t."""
    x = ltr_features(lv)
    h = int(hold_d)
    lab = np.full_like(lv, np.nan)
    if lv.shape[0] > h:
        lab[:-h] = lv[h:] - lv[:-h]
    g_all = _grades(lab)
    rows = lv.shape[0]
    out = np.full(lv.shape, np.nan)
    w: np.ndarray | None = None
    next_fit = 0
    for t in range(rows):
        if t >= next_fit:
            hi = t - h + 1                     # labels at rows < hi end at row <= t
            lo = max(0, hi - int(train_d))
            if hi - lo >= int(min_train_d):
                w = lambdarank_fit(x[lo:hi], g_all[lo:hi], w)
                next_fit = t + int(refit_d)
        if w is not None:
            s = x[t] @ w
            out[t] = np.where(np.isfinite(lv[t]), s, np.nan)
    return out


def family_cross_sectional_class_ltr(
    df: pd.DataFrame, *, symbol: str, hold_d: int = 5, train_d: int = 500, refit_d: int = 20,
    min_train_d: int = 120, quantile: float = 1 / 3, decision_hour: int = 22,
    max_stale_h: float = 12.0, stop_sd: float = 3.0, rr: float = 2.0,
) -> list[Signal]:
    """Long while `symbol`'s LambdaRank score (linear in the class's centred-ranked momentum,
    reversal, value, low-vol and low-beta signals, refit causally every `refit_d` days on the
    last `train_d` realised days) is in the top `quantile` of its class, short in the bottom."""
    if (not xs._valid_common(quantile, hold_d, stop_sd, rr) or int(train_d) < int(min_train_d)
            or int(min_train_d) < 20 or int(refit_d) < 1):
        return []
    got = _prepare(df, symbol, decision_hour, max_stale_h)
    if got is None:
        return []
    d, panel = got
    score = ltr_scores(panel["logv"], hold_d=int(hold_d), train_d=int(train_d),
                       refit_d=int(refit_d), min_train_d=int(min_train_d))
    side = xs._rank_sides(score, panel["own"], quantile)
    return xs._signals(d, panel, side, hold_d=hold_d, stop_sd=stop_sd, rr=rr,
                       tag=f"xs_ltr:{panel['klass']}:{hold_d}:{train_d}")


# ---------------------------------------------------------------- intraday realised moments ---
def realised_moment(series: tuple[np.ndarray, np.ndarray], stamps: np.ndarray, orient: int,
                    measure: str, window_d: int, min_n: int) -> np.ndarray:
    """One member's `measure` over its own H1 returns stamped in (stamp - window_d days, stamp],
    at each decision stamp. Returns across a gap > MAX_GAP_H are dropped. NaN when fewer than
    `min_n` returns fall in the window."""
    t, c = series
    out = np.full(stamps.size, np.nan)
    if t.size < 3:
        return out
    with np.errstate(divide="ignore", invalid="ignore"):
        r = np.diff(np.log(c)) * float(orient)
    rt = t[1:]
    ok = ((rt - t[:-1]) <= MAX_GAP_H * 3_600_000_000_000) & np.isfinite(r)
    r, rt = r[ok], rt[ok]
    if r.size < min_n:
        return out
    hi = np.searchsorted(rt, stamps, side="right")
    lo = np.searchsorted(rt, stamps - int(window_d) * 86_400_000_000_000, side="right")
    n = hi - lo
    good = n >= int(min_n)
    if measure == "max_ret":
        s = pd.Series(r, index=pd.DatetimeIndex(rt))
        mx = s.rolling(f"{int(window_d)}D", closed="right").max().to_numpy()
        idx = np.where(hi > 0, hi - 1, 0)
        out[good] = mx[idx[good]]
        return out

    def cs(v: np.ndarray) -> np.ndarray:
        return np.concatenate([[0.0], np.cumsum(v)])

    s2 = cs(r * r)
    win2 = s2[hi] - s2[lo]
    if measure == "skew":
        s3 = cs(r ** 3)
        win3 = s3[hi] - s3[lo]
        with np.errstate(divide="ignore", invalid="ignore"):
            val = np.sqrt(n) * win3 / win2 ** 1.5
    elif measure == "signed_variation":
        sp = cs(np.where(r > 0, r * r, 0.0))
        up = sp[hi] - sp[lo]
        with np.errstate(divide="ignore", invalid="ignore"):
            val = (up - (win2 - up)) / win2
    else:
        return out
    good &= win2 > 0
    out[good] = val[good]
    return out


def family_cross_sectional_class_hf_moment(
    df: pd.DataFrame, *, symbol: str, measure: str = "skew", window_d: int = 20,
    hold_d: int = 5, quantile: float = 1 / 3, decision_hour: int = 22,
    max_stale_h: float = 12.0, stop_sd: float = 3.0, rr: float = 2.0,
) -> list[Signal]:
    """Long while `symbol` is among its class's LOWEST `measure` (realised skew, signed realised
    variation, or largest hourly return) over the trailing `window_d` days of intraday returns,
    short while among the highest: the lottery-premium prior, ranked within the class."""
    if (not xs._valid_common(quantile, hold_d, stop_sd, rr) or measure not in HF_MEASURES
            or int(window_d) < 5):
        return []
    got = _prepare(df, symbol, decision_hour, max_stale_h)
    if got is None:
        return []
    d, panel = got
    min_n = 5 * int(window_d)
    m = np.column_stack([realised_moment(s, panel["stamps"], o, measure, int(window_d), min_n)
                         for s, o in zip(panel["series"], panel["orients"], strict=True)])
    m[~np.isfinite(panel["logv"])] = np.nan
    side = xs._rank_sides(-m, panel["own"], quantile)
    return xs._signals(d, panel, side, hold_d=hold_d, stop_sd=stop_sd, rr=rr,
                       tag=f"xs_hf_{measure}:{panel['klass']}:{window_d}")


# ------------------------------------------------------------------------ value-area rules ---
def value_area(lo: np.ndarray, hi: np.ndarray, vol: np.ndarray, *, bins: int = 30,
               va_pct: float = 0.7) -> tuple[float, float, float] | None:
    """(VAL, POC, VAH) of one session's bars: each bar's weight spread evenly over the bins its
    [low, high] covers; the value area grows from the point of control toward the heavier
    neighbour until it holds `va_pct` of the weight (Steidlmayer / Dalton)."""
    ok = np.isfinite(lo) & np.isfinite(hi) & np.isfinite(vol) & (hi >= lo) & (vol > 0)
    if ok.sum() < 3:
        return None
    lo, hi, vol = lo[ok], hi[ok], vol[ok]
    bottom, top = float(lo.min()), float(hi.max())
    if not top > bottom:
        return None
    edges = np.linspace(bottom, top, int(bins) + 1)
    a = np.clip(np.searchsorted(edges, lo, side="right") - 1, 0, bins - 1)
    b = np.clip(np.searchsorted(edges, hi, side="left") - 1, 0, bins - 1)
    b = np.maximum(a, b)
    prof = np.zeros(int(bins))
    span = (b - a + 1).astype(float)
    for k in range(lo.size):
        prof[a[k]:b[k] + 1] += vol[k] / span[k]
    poc = int(np.argmax(prof))
    lo_i = hi_i = poc
    held, total = prof[poc], prof.sum()
    while held < float(va_pct) * total and (lo_i > 0 or hi_i < bins - 1):
        down = prof[lo_i - 1] if lo_i > 0 else -1.0
        up = prof[hi_i + 1] if hi_i < bins - 1 else -1.0
        if up >= down:
            hi_i += 1
            held += up
        else:
            lo_i -= 1
            held += down
    return float(edges[lo_i]), float((edges[poc] + edges[poc + 1]) / 2), float(edges[hi_i + 1])


def family_value_area_rule(
    df: pd.DataFrame, *, rule: str = "eighty", profile: str = "tpo", confirm_bars: int = 1,
    va_pct: float = 0.7, bins: int = 30, entry_window_h: int = 8, atr_n: int = 20,
    stop_atr: float = 1.5, rr: float = 1.5, hold_bars: int = 12,
) -> list[Signal]:
    """Yesterday's value area against today's open. `eighty`: opened outside, closed back inside
    for `confirm_bars` bars within `entry_window_h` hours of the open -> trade to the far edge.
    `acceptance`: opened outside and the first `confirm_bars` bars closed outside on the same
    side -> follow, target `rr` x the ATR stop. At most one signal per broker day."""
    if (rule not in VA_RULES or profile not in VA_PROFILES or int(confirm_bars) < 1
            or not 0.3 <= float(va_pct) < 1.0 or int(bins) < 5 or int(hold_bars) < 1
            or stop_atr <= 0 or rr <= 0):
        return []
    if df is None or len(df) < 200:
        return []
    d = _h1(df)
    if not {"open", "high", "low", "close"} <= set(d.columns):
        return []
    if profile == "tick_volume":
        col = next((c for c in ("tick_volume", "volume", "real_volume") if c in d.columns), None)
        if col is None:
            return []
        vol = pd.to_numeric(d[col], errors="coerce").to_numpy(dtype=float)
    else:
        vol = np.ones(len(d))
    o, h = d["open"].to_numpy(float), d["high"].to_numpy(float)
    lo, c = d["low"].to_numpy(float), d["close"].to_numpy(float)
    atr = _atr(d, atr_n).to_numpy(dtype=float)
    idx = d.index
    day = idx.normalize().asi8
    starts = np.flatnonzero(np.r_[True, day[1:] != day[:-1]])
    ends = np.r_[starts[1:], len(d)]
    win_bars = max(1, int(round(int(entry_window_h) * bars_per_day(d) / 24.0)))
    k = int(confirm_bars)
    out: list[Signal] = []
    for n in range(1, starts.size):
        ps, pe = starts[n - 1], ends[n - 1]
        s0, e0 = starts[n], ends[n]
        va = value_area(lo[ps:pe], h[ps:pe], vol[ps:pe], bins=int(bins), va_pct=float(va_pct))
        if va is None:
            continue
        val, _poc, vah = va
        opn = o[s0]
        if val <= opn <= vah:
            continue
        above = opn > vah
        last = min(e0, s0 + win_bars) - 1
        for i in range(s0 + k - 1, last + 1):
            if i >= len(d) - 1:
                break
            seg = c[i - k + 1:i + 1]
            a = atr[i]
            if not (np.isfinite(a) and a > 0):
                continue
            px = c[i]
            if rule == "eighty":
                if not np.all((seg >= val) & (seg <= vah)):
                    continue
                side = -1 if above else 1
                target = val if above else vah
                if side * (target - px) <= 0:
                    break
                stop = px - side * stop_atr * a
            else:
                if i != s0 + k - 1:
                    break
                if not (np.all(seg > vah) if above else np.all(seg < val)):
                    break
                side = 1 if above else -1
                stop = px - side * stop_atr * a
                target = px + side * stop_atr * a * rr
            out.append(Signal(time=idx[i], side=side, stop=float(stop), target=float(target),
                              ttl_bars=int(hold_bars), tag=f"value_area:{rule}:{profile}",
                              trigger=None, wait_bars=1))
            break
    return out


def _daily(d: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, pd.DataFrame]:
    """(first bar of each broker day, end (exclusive) of each day, the day's OHLC table)."""
    day = d.index.normalize().asi8
    starts = np.flatnonzero(np.r_[True, day[1:] != day[:-1]])
    ends = np.r_[starts[1:], len(d)]
    hi = np.maximum.reduceat(d["high"].to_numpy(float), starts)
    lo = np.minimum.reduceat(d["low"].to_numpy(float), starts)
    o = d["open"].to_numpy(float)[starts]
    c = d["close"].to_numpy(float)[ends - 1]
    return starts, ends, pd.DataFrame({"open": o, "high": hi, "low": lo, "close": c})


VB_K_MODES: tuple[str, ...] = ("fixed", "noise")
VB_FILTERS: tuple[str, ...] = ("none", "ma_score")


def family_volatility_breakout_kr(
    df: pd.DataFrame, *, direction: str = "long", k_mode: str = "fixed", k: float = 0.5,
    noise_d: int = 20, ma_filter: str = "none", rr: float = 3.0,
) -> list[Signal]:
    """At each broker day's first bar, a resting stop at open +/- k x yesterday's range, alive to
    the day's last bar and held to it; the stop is the day's open (the breakout failed)."""
    if (direction not in ("long", "short") or k_mode not in VB_K_MODES
            or ma_filter not in VB_FILTERS or not 0.0 < float(k) < 3.0 or int(noise_d) < 2
            or rr <= 0):
        return []
    if df is None or len(df) < 200:
        return []
    d = _h1(df)
    if not {"open", "high", "low", "close"} <= set(d.columns):
        return []
    starts, ends, day = _daily(d)
    rng = (day["high"] - day["low"]).to_numpy(float)
    prev_rng = np.r_[np.nan, rng[:-1]]
    if k_mode == "noise":
        with np.errstate(divide="ignore", invalid="ignore"):
            noise = 1.0 - np.abs(day["open"] - day["close"]).to_numpy(float) / rng
        noise = np.where(np.isfinite(noise), noise, np.nan)
        kk = pd.Series(noise).rolling(int(noise_d), min_periods=int(noise_d)).mean().shift(1)
        kv = kk.to_numpy(float)
    else:
        kv = np.full(len(day), float(k))
    sign = 1 if direction == "long" else -1
    opn = day["open"].to_numpy(float)
    ok = np.isfinite(prev_rng) & (prev_rng > 0) & np.isfinite(kv) & (kv > 0)
    if ma_filter == "ma_score":
        closes = day["close"].shift(1)
        score = sum((opn > closes.rolling(n, min_periods=n).mean().to_numpy(float)).astype(int)
                    for n in (3, 5, 10, 20))
        warm = closes.rolling(20, min_periods=20).mean().notna().to_numpy()
        ok &= warm & ((score == 4) if sign > 0 else (score == 0))
    idx = d.index
    out: list[Signal] = []
    for n in np.flatnonzero(ok):
        s0, e0 = int(starts[n]), int(ends[n])
        if e0 - s0 < 3 or s0 >= len(d) - 1:
            continue
        level = opn[n] + sign * kv[n] * prev_rng[n]
        risk = abs(level - opn[n])
        out.append(Signal(time=idx[s0], side=sign, stop=float(opn[n]),
                          target=float(level + sign * rr * risk), ttl_bars=int(e0 - s0 - 1),
                          tag=f"vol_breakout_kr:{direction}:{k_mode}:{ma_filter}",
                          trigger=float(level), wait_bars=int(e0 - s0 - 1)))
    return out


GLOBAL_METHOD_FAMILIES: dict[str, Callable[..., list[Signal]]] = {
    "cross_sectional_class_ltr": family_cross_sectional_class_ltr,
    "cross_sectional_class_hf_moment": family_cross_sectional_class_hf_moment,
    "value_area_rule": family_value_area_rule,
    "volatility_breakout_kr": family_volatility_breakout_kr,
}

#: Swept params per family. The grid IS the trial count the producer charges, written here once.
PARAM_GRID: dict[str, dict[str, list[Any]]] = {
    "cross_sectional_class_ltr": {"hold_d": [5, 20], "train_d": [500, 1000]},
    "cross_sectional_class_hf_moment": {"measure": list(HF_MEASURES), "window_d": [20, 60],
                                        "hold_d": [5, 20]},
    "value_area_rule": {"rule": list(VA_RULES), "profile": list(VA_PROFILES),
                        "confirm_bars": [1, 2]},
    "volatility_breakout_kr": {"direction": ["long", "short"], "k_mode": list(VB_K_MODES),
                               "ma_filter": list(VB_FILTERS)},
}

#: Whether a family ranks a class (the producer then needs a peer class with enough members).
NEEDS_CLASS: dict[str, bool] = {"cross_sectional_class_ltr": True,
                                "cross_sectional_class_hf_moment": True,
                                "value_area_rule": False, "volatility_breakout_kr": False}

PRIORS: dict[str, str] = {
    "cross_sectional_class_ltr": (
        "LambdaRank over the class's documented cross-sectional premia (Burges 2010; Poh, Lim, "
        "Zohren & Roberts 2021 learning-to-rank on futures/FX)"),
    "cross_sectional_class_hf_moment": (
        "intraday realised moments ranked in the class: the lottery premium (Amaya et al. 2015; "
        "Fernandez-Perez et al. 2018 commodity skew; Bali et al. 2011 MAX; Haitong/Founder "
        "高频因子)"),
    "value_area_rule": (
        "auction theory on yesterday's value area: rejection returns to value (80% rule), "
        "acceptance trends (Steidlmayer; Dalton; the Russian volume-profile school)"),
    "volatility_breakout_kr": (
        "a range expansion beyond yesterday's noise is information arriving and persists into "
        "the close (Larry Williams; the Korean 변동성 돌파 school, 노이즈 비율 k)"),
}


def describe() -> dict[str, Any]:
    return {k: {"prior": PRIORS[k], "grid": PARAM_GRID[k], "needs_class": NEEDS_CLASS[k]}
            for k in GLOBAL_METHOD_FAMILIES}
