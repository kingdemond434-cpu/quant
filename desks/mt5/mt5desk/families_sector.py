"""THE SEMICONDUCTOR SECTOR BOOK: one leg per cell, ranked within the semis peer class.

WHY A SECTOR BOOK WHEN THE EQUITY CLASS BOOK ALREADY RANKS EVERY SHARE CFD. The `equity` class
(`families_cross_sectional`) ranks NVIDIA against Coca-Cola: its spread is mostly the sector
factor, which the class book then bets on without meaning to. A sector book ranks a semis name
against semis names only, so the common sector move is demeaned out of every leg and what is left
is the idiosyncratic, within-industry spread -- the construction the Asian sector desks (Korean
semis books, measured as MISSING in reports/asia_quant_gap_2026-09-30.md row 10) run.

MEMBERS, FROM THE REGISTRY, NEVER FAKED. `research.universe_policy.SECTOR_BOOKS["semis"]` declares
the issuers (NVIDIA, AMD, Intel, Micron, TSMC, Qualcomm, Broadcom, Texas Instruments, Applied
Materials) and the broker spellings each may carry; `sector_resolution` resolves them against the
broker registry on every read and reports any that are absent.

THE ISSUERS ARE RANKED AGAINST THEIR EQUITY PEERS, AND ONLY AGAINST THEM (principal's ruling,
2026-09-30). USDKRW (the Korea leg, read inverted as the won in dollars: Samsung and SK Hynix make
memory the largest line in Korea's exports) and JPN225 (the Japanese equipment leg) are TRADABLE
PROXY LEGS AND CONDITIONERS, never the ranking benchmark: they are left out of every issuer's
cross-section (`families_cross_sectional.class_panel`), and a proxy cell never ranks itself among
the issuers either. It trades the ISSUERS' aggregate view instead -- the sign of the book's mean
score on that date (its own causal leader-basket prediction for the catch-up family) -- so the
book carries its Korean and Japanese exposure without a currency or an index ever setting the bar
a share is judged against.

EVERY SCORE IS VOLATILITY-SCALED, in units of the member's own trailing daily volatility, so the
issuers' ranks are not dominated by the most volatile names and the proxy's aggregate is a mean of
comparable quantities.

THE FAMILIES AND THEIR PRIORS (written before any data was looked at):

  semis_sector_momentum    Industry-relative momentum: information about a sector's winners
      diffuses slowly (Moskowitz & Grinblatt 1999 industry momentum; Hou 2007 intra-industry
      diffusion). Long the members whose vol-scaled return ranks top of the book.
  semis_sector_reversal    Short-horizon intra-industry reversal: a member pushed to an extreme
      of its industry by one flow over days reverts as that inventory is laid off (Lehmann 1990;
      Da, Liu & Schaumburg 2014: within-industry reversal survives where the raw one does not).
  semis_sector_value       Price furthest below its own one-to-two-year level, relative to the
      industry, in its own volatility units (AMP 2013 value, read within industry).
  semis_leader_catchup     Lead-lag against the SOXX-like leaders: the cap-weighted leaders
      (NVIDIA, Broadcom, TSMC) are the screen the sector watches; smaller members and the Korean
      leg reprice the leaders' move a day late (Hou 2007; Cohen & Frazzini 2008). A causal lagged
      beta on the leader basket (ex-self) predicts which members have not caught up.

NO LOOKAHEAD, BY CONSTRUCTION -- the panel is `families_cross_sectional.class_panel`, which reads
every peer as of the decision bar's stamp and drops a stale peer rather than carrying it forward;
every window is trailing and the signal enters at the next bar's open.
"""
from __future__ import annotations

import math
from collections.abc import Callable

import numpy as np
import pandas as pd
from mt5desk import families_cross_sectional as xs
from mt5desk.families import Signal

#: The sector book these families rank within (research.universe_policy.SECTOR_BOOKS).
BOOK = "semis"

#: Members that must be present on a day before the book has a cross-section. The declared book is
#: nine issuers and one proxy, so five is a real cross-section and a missing file or two does not
#: silence it.
MIN_MEMBERS = xs.MIN_MEMBERS

#: The grid is the trial count this module charges; written here and nowhere else.
PARAM_GRID: dict[str, dict[str, list]] = {
    "semis_sector_momentum": {"lookback_d": [20, 60, 120], "hold_d": [5, 20]},
    "semis_sector_reversal": {"lookback_d": [1, 3, 5], "hold_d": [1, 3]},
    "semis_sector_value": {"anchor_d": [250, 500], "hold_d": [10, 20]},
    "semis_leader_catchup": {"leaders": ["mega", "book"], "window_d": [120, 250],
                             "hold_d": [1, 2]},
}


def _leaders(panel: dict) -> list[int]:
    """Column indices of the SOXX-like leader basket in `panel` (from the registry resolution)."""
    try:
        names = {s.upper() for s in xs._policy().sector_resolution(BOOK)["leaders"]}
    except Exception:
        names = set()
    return [i for i, m in enumerate(panel["members"]) if m.upper() in names]


def _vol(r: np.ndarray, rows: int = 60) -> np.ndarray:
    """Trailing per-member daily-return volatility, read strictly before the row."""
    return xs._rolling(xs._shift(r, 1), rows, "std")


def _prepare(df: pd.DataFrame, symbol: str, decision_hour: int, max_stale_h: float):
    return xs._prepare(df, symbol, decision_hour, max_stale_h, klass=BOOK)


def _sides(score: np.ndarray, panel: dict, quantile: float) -> np.ndarray:
    """+1 / -1 / 0 per decision row.

    An ISSUER is ranked within the issuers (the panel carries no proxy column for it). A PROXY leg
    is never ranked: it takes the sign of the issuers' mean score on the row, and only when at
    least MIN_MEMBERS issuers are scored and its own price is known."""
    if not panel.get("proxy"):
        return xs._rank_sides(score, panel["own"], quantile)
    issuers = np.delete(score, panel["own"], axis=1)
    mean, _ = xs._row_mean_std(issuers, min_n=MIN_MEMBERS)
    own_ok = np.isfinite(panel["logv"][:, panel["own"]])
    side = np.zeros(score.shape[0], dtype="int64")
    ok = own_ok & np.isfinite(mean)
    side[ok & (mean > 0)] = 1
    side[ok & (mean < 0)] = -1
    return side


def family_semis_sector_momentum(
    df: pd.DataFrame, *, symbol: str = "", lookback_d: int = 60, hold_d: int = 20,
    quantile: float = 1 / 3, decision_hour: int = 22, max_stale_h: float = 12.0,
    stop_sd: float = 3.0, rr: float = 2.0,
) -> list[Signal]:
    """Long while `symbol`'s vol-scaled `lookback_d`-day return ranks in the top `quantile` of
    the semis book, short while it ranks in the bottom."""
    if not xs._valid_common(quantile, hold_d, stop_sd, rr) or int(lookback_d) < 1:
        return []
    got = _prepare(df, symbol, decision_hour, max_stale_h)
    if got is None:
        return []
    d, panel = got
    lv = panel["logv"]
    ret = lv - xs._shift(lv, int(lookback_d))
    with np.errstate(divide="ignore", invalid="ignore"):
        score = ret / (_vol(xs._returns(lv)) * math.sqrt(int(lookback_d)))
    side = _sides(score, panel, quantile)
    return xs._signals(d, panel, side, hold_d=hold_d, stop_sd=stop_sd, rr=rr,
                       tag=f"semis_momentum:{lookback_d}")


def family_semis_sector_reversal(
    df: pd.DataFrame, *, symbol: str = "", lookback_d: int = 3, hold_d: int = 3,
    quantile: float = 1 / 3, decision_hour: int = 22, max_stale_h: float = 12.0,
    stop_sd: float = 3.0, rr: float = 2.0,
) -> list[Signal]:
    """Long while `symbol`'s vol-scaled `lookback_d`-day return ranks in the BOTTOM `quantile` of
    the semis book, short while in the top."""
    if not xs._valid_common(quantile, hold_d, stop_sd, rr) or int(lookback_d) < 1:
        return []
    got = _prepare(df, symbol, decision_hour, max_stale_h)
    if got is None:
        return []
    d, panel = got
    lv = panel["logv"]
    ret = lv - xs._shift(lv, int(lookback_d))
    with np.errstate(divide="ignore", invalid="ignore"):
        score = ret / (_vol(xs._returns(lv)) * math.sqrt(int(lookback_d)))
    side = _sides(-score, panel, quantile)
    return xs._signals(d, panel, side, hold_d=hold_d, stop_sd=stop_sd, rr=rr,
                       tag=f"semis_reversal:{lookback_d}")


def family_semis_sector_value(
    df: pd.DataFrame, *, symbol: str = "", anchor_d: int = 250, hold_d: int = 20,
    quantile: float = 1 / 3, decision_hour: int = 22, max_stale_h: float = 12.0,
    stop_sd: float = 3.0, rr: float = 2.0,
) -> list[Signal]:
    """Long while `symbol` is among the semis members furthest BELOW their own `anchor_d`-day
    level (in that level's own dispersion), short while among the furthest above."""
    if not xs._valid_common(quantile, hold_d, stop_sd, rr) or int(anchor_d) < 20:
        return []
    got = _prepare(df, symbol, decision_hour, max_stale_h)
    if got is None:
        return []
    d, panel = got
    lv = panel["logv"]
    prior = xs._shift(lv, 1)
    mu = xs._rolling(prior, int(anchor_d), "mean")
    sd = xs._rolling(prior, int(anchor_d), "std")
    with np.errstate(divide="ignore", invalid="ignore"):
        z = np.where(sd > 0, (lv - mu) / sd, np.nan)
    side = _sides(-z, panel, quantile)
    return xs._signals(d, panel, side, hold_d=hold_d, stop_sd=stop_sd, rr=rr,
                       tag=f"semis_value:{anchor_d}")


def family_semis_leader_catchup(
    df: pd.DataFrame, *, symbol: str = "", leaders: str = "mega", window_d: int = 250,
    hold_d: int = 1, quantile: float = 1 / 3, decision_hour: int = 22,
    max_stale_h: float = 12.0, stop_sd: float = 3.0, rr: float = 2.0,
) -> list[Signal]:
    """Each member's next-day return predicted from the LEADER basket's return today (ex-self)
    through a causal lagged beta over `window_d` days; the prediction is vol-scaled and ranked.
    Long while `symbol`'s is positive and in the book's top `quantile`, short while negative and
    in the bottom. `leaders="mega"` is the SOXX-like leader basket (NVIDIA, Broadcom, TSMC as the
    registry resolves them); `"book"` is the whole book ex-self."""
    if (not xs._valid_common(quantile, hold_d, stop_sd, rr) or int(window_d) < 40
            or leaders not in ("mega", "book")):
        return []
    got = _prepare(df, symbol, decision_hour, max_stale_h)
    if got is None:
        return []
    d, panel = got
    r = xs._returns(panel["logv"])
    if leaders == "mega":
        cols = _leaders(panel)
        if len(cols) < 2:
            return []
        is_lead = np.zeros(r.shape[1], dtype=bool)
        is_lead[cols] = True
        valid = np.isfinite(r) & is_lead[None, :]
        vals = np.where(valid, r, 0.0)
        s = vals.sum(axis=1, keepdims=True)
        n = valid.sum(axis=1, keepdims=True)
        nn = n - valid                                  # the basket EX-SELF for a leader
        with np.errstate(divide="ignore", invalid="ignore"):
            x = np.where(nn >= 1, (s - vals) / np.maximum(nn, 1), np.nan)
    elif panel.get("proxy"):
        # the proxy's "book" is the issuers' mean; each issuer's is the issuers ex-self. The
        # proxy's own return never enters an issuer's basket.
        iss = np.delete(r, panel["own"], axis=1)
        own_x, _ = xs._row_mean_std(iss, min_n=1)
        x = np.insert(xs._ew_ex_self(iss), panel["own"], own_x, axis=1)
    else:
        x = xs._ew_ex_self(r)
    x_lag = xs._shift(x, 1)
    both = np.isfinite(r) & np.isfinite(x_lag)
    num = xs._rolling(np.where(both, r * x_lag, np.nan), int(window_d), "sum", 0.5)
    den = xs._rolling(np.where(both, x_lag * x_lag, np.nan), int(window_d), "sum", 0.5)
    with np.errstate(divide="ignore", invalid="ignore"):
        b = np.where(den > 0, num / den, np.nan)
        pred = b * x / _vol(r)
    own_pred = pred[:, panel["own"]]
    if panel.get("proxy"):
        # a proxy leg is never ranked among the issuers: it trades the sign of its OWN causal
        # prediction from the leader basket (a conditioner on the leaders, not a rank)
        side = np.zeros(pred.shape[0], dtype="int64")
        side[np.isfinite(own_pred) & (own_pred > 0)] = 1
        side[np.isfinite(own_pred) & (own_pred < 0)] = -1
        return xs._signals(d, panel, side, hold_d=hold_d, stop_sd=stop_sd, rr=rr,
                           tag=f"semis_leader_catchup:{leaders}:{window_d}")
    side = xs._rank_sides(pred, panel["own"], quantile)
    side[(side > 0) & ~(own_pred > 0)] = 0
    side[(side < 0) & ~(own_pred < 0)] = 0
    return xs._signals(d, panel, side, hold_d=hold_d, stop_sd=stop_sd, rr=rr,
                       tag=f"semis_leader_catchup:{leaders}:{window_d}")


SECTOR_FAMILIES: dict[str, Callable[..., list[Signal]]] = {
    "semis_sector_momentum": family_semis_sector_momentum,
    "semis_sector_reversal": family_semis_sector_reversal,
    "semis_sector_value": family_semis_sector_value,
    "semis_leader_catchup": family_semis_leader_catchup,
}

#: The classes each family is enumerated over by `research/cross_sectional_breadth`.
FAMILY_CLASSES: dict[str, tuple[str, ...]] = dict.fromkeys(SECTOR_FAMILIES, (BOOK,))

TARGETS: dict[str, dict[str, str]] = {
    "semis_sector_momentum": {
        "cluster": "cross_sectional_equity",
        "prior": "industry-relative momentum: slow intra-industry diffusion (Moskowitz & "
                 "Grinblatt 1999; Hou 2007)"},
    "semis_sector_reversal": {
        "cluster": "cross_sectional_equity",
        "prior": "within-industry short-horizon reversal: the price of immediacy (Lehmann 1990; "
                 "Da, Liu & Schaumburg 2014)"},
    "semis_sector_value": {
        "cluster": "cross_sectional_equity",
        "prior": "reversion to a long-run level ranked within industry (AMP 2013 value)"},
    "semis_leader_catchup": {
        "cluster": "cross_asset_lead_lag",
        "prior": "followers and the Korean leg reprice the SOXX-like leaders' move with a lag "
                 "(Hou 2007; Cohen & Frazzini 2008)"},
}
