"""W21 -- THE CORE OF THE CORE-PLUS-SLEEVE BOOK: one trend bet across the whole universe.

WHAT THE DESK HAS, AND WHAT IT DOES NOT. It has tactical sleeves: a gold scalp at M5, a session
breakout, an overnight gap decay -- each one a narrow, fast, session-shaped claim on one or two
instruments. What it does not have is the thing every multi-asset book is built around first: a
SLOW, WIDE, DIVERSIFIED TREND CORE. Managed futures has run on it for forty years because it is
the one premium that is cross-sectionally wide, mechanically simple, and NOT correlated with a
scalper's edge -- which is exactly what makes it the right ADDITIONAL bet here.

    core   = time-series momentum x cross-sectional momentum, vol-scaled, across every
             hypothesis-lane instrument the desk holds bars for
    sleeve = the tactical, session-shaped claims that already exist

THIS ORGAN MEASURES THE CORE AND DONATES IT. IT TAKES NOTHING FROM THE SLEEVES. There is no cap,
no shrink, no veto and no reallocation here: not one line of this file can reduce an existing
sleeve's size. The desk's standing order is that a Tier-1 book means MORE independent positive-
E[log W] bets inside the same heat, never a smaller book, and a trend core is the textbook case of
an independent one -- its correlation to the scalp sleeves is measured here and published, not
assumed.

FOUR MEASUREMENTS, AND THE FOURTH IS THE POINT.

1. TIME-SERIES MOMENTUM AT SEVERAL SPEEDS. sign(log P_t - log P_{t-L}) for L in 21, 63, 126, 252
   trading days. One speed is a coin flip about which trend you meant; the vote across speeds is
   the actual claim, and `agreement` (how many speeds agree) is published per instrument because
   it is what the family being donated (`multi_speed_trend`) actually trades.

2. CROSS-SECTIONAL MOMENTUM. Within an asset class, the 126-day return RANKED: long the top
   third, short the bottom third. Time-series momentum is a bet on the direction of a market;
   cross-sectional momentum is a bet on the SPREAD between markets, and the two are different
   enough that both are measured and their agreement is reported.

3. VOLATILITY SCALING, AND IT IS A SCALING, NOT A CAP. w_i = target_vol / realised_vol_i. A book
   that holds one lot of gold and one lot of EURCHF is not holding two bets; it is holding gold.
   The scaler is TWO-SIDED by construction -- it raises a quiet instrument's size exactly as much
   as it lowers a noisy one's -- so it adds risk to the book as readily as it removes it. The only
   guard is a numerical floor on the volatility estimate, which exists so a division does not
   explode on a stale series, and it is reported when it binds.

4. THE CORRELATION STRUCTURE, SO THE CORE READS AS ONE BET RATHER THAN N. The per-instrument
   strategy returns are correlated and the PARTICIPATION RATIO of that matrix's spectrum
   (`libs.risk.fx_exposure.effective_rank`) says how many independent directions the core really
   spans. Forty vol-scaled trend legs that all lean on the dollar are ONE bet with forty tickets,
   and `n_effective / n_legs` is the number that says so. The core's own aggregate return series
   is then what E[log W] is measured on -- mu - sigma^2/2 on the aggregate, never the sum of the
   legs' individual growth rates, which would count the same bet forty times.

TWO LANES, ENFORCED AT THE DOOR. Single-name equities ARE measured here -- their trend statistics
are published like everything else, because measurement is not a hypothesis -- and NOT ONE of them
is donated or admitted to the core's legs. `research.universe_policy.may_hypothesise` is the only
thing that decides, an unclassified symbol is refused (absence is not permission), and the refusal
count rides on the report.

NO PRIVILEGED PATH TO CAPITAL. The core is donated through the same proposer contract as any
miner's cell, reaches the same ten gates, and gets its forward clock the same way. Its
specification is published in the exact `shadow_spec` shape the forward enrolment reader consumes
(symbol, family, side, selector, condition, is_universe, hunt) plus the certified `params`, so
nothing downstream has to infer a parameterisation from a display name. If it does not clear the
gauntlet it does not trade, and this file has no opinion about that.

    python desks/mt5/research/trend_core.py [--once] [--budget-s 600] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

UNIVERSE = DESK / "data" / "universe" / "universe.json"
SLEEVES = DESK / "data" / "sleeves.json"
REPORT = DESK / "reports" / "TREND_CORE.json"

SOURCE = "trend_core"
FAMILY = "multi_speed_trend"

#: Trading-day lookbacks. Four speeds, a quarter apart in log time: a month, a quarter, a half
#: year, a year. One speed is an opinion about which trend you meant; the vote is the claim.
SPEEDS: tuple[int, ...] = (21, 63, 126, 252)
#: The speed the cross-sectional rank is taken on -- the middle of the range, so the ranking is
#: not a restatement of the fastest or the slowest vote.
CS_SPEED = 126
#: Days of daily returns the volatility estimate uses.
VOL_WINDOW = 63
#: Annualised volatility every leg is scaled to. It is a UNIT, not a limit: the leg's own size is
#: target/realised, which is above 1.0 for every instrument quieter than this and below it for
#: every instrument noisier, and the book's heat is the allocator's decision, not this file's.
TARGET_VOL = 0.10
TRADING_DAYS = 252
#: Daily observations a leg needs before it is measured at all. 252 + the slowest lookback: a
#: leg that cannot see a year past its own slowest speed has not measured that speed once.
MIN_DAYS = max(SPEEDS) + 252
#: Speeds that must agree before the leg is IN the core. 0.6 of four speeds is three of them,
#: which is the family's own default and what the donated parameterisation carries.
MIN_AGREEMENT = 0.6
#: Legs published and, separately, donated. The core is ONE bet; donating forty tickets for it
#: would spend the family-wise error budget forty times over for one mechanism.
MAX_LEGS = 120
MAX_DONATIONS = 12
#: The volatility floor is a NUMERICAL guard, not a risk limit: a stale or degenerate series can
#: produce a near-zero sigma and w = target/sigma would then explode. Expressed as a fraction of
#: the instrument's own median volatility, so it is scale-free and binds almost never -- and when
#: it binds it is counted in the report.
VOL_FLOOR_FRAC = 0.1
#: What ONE instrument costs this organ once its frame is closed: the daily closes, the daily
#: strategy returns and the leg dict. Generous at 64 KB, and it is the quantity that is actually
#: retained rather than the transient frame.
RETAINED_BYTES = 64 * 1024

RULE = ("a vol-scaled multi-speed trend core across the whole hypothesis-lane universe, measured "
        "as ONE bet through the participation ratio of its own legs' correlation matrix")
STANDING = ("ADDITIVE ONLY: this organ measures and donates a new independent bet. It never "
            "caps, shrinks, vetoes or reallocates an existing sleeve, and contains no mechanism "
            "that could")
UNMEASURED = "UNMEASURED"


# --------------------------------------------------------------------------------- plumbing
def _now() -> datetime:
    return datetime.now(tz=UTC)


def _f(value: Any) -> float | None:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return None


def _atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, "utf-8")
    os.replace(tmp, path)


def max_symbols(default: int = 60) -> int:
    """How many instruments one pass may hold at once, DERIVED from the box it runs on.

    THE H1 FRAME IS TRANSIENT; WHAT IS RETAINED IS TINY. Each instrument's frame is read, reduced
    to a daily series and released, so the standing cost per instrument is the daily closes, the
    strategy returns and the leg dict -- tens of kilobytes, not the megabytes the frame occupied
    while it was open. Sizing the cap off the frame is what made the first pass here read 41 of
    251 instruments on a box with 4 GB free: a floor sized for the wrong quantity.

    25% of measured free physical memory at RETAINED_BYTES a symbol, floored at `default` so an
    unreadable counter changes nothing. The trading box and the build box differ by an order of
    magnitude and a constant sized for either is wrong on the other -- that mistake is already
    written down in this repo, twice.
    """
    try:
        import psutil  # type: ignore[import-untyped]
    except Exception:                                    # pragma: no cover - optional dependency
        return default
    try:
        free = int(psutil.virtual_memory().available)
    except Exception:                                    # pragma: no cover - counter unreadable
        return default
    return max(default, int(free * 0.25 / RETAINED_BYTES))


# --------------------------------------------------------------------------------- the inputs
def universe_rows() -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """The MT5 registry, and the accounting of it. An absent registry measures nothing."""
    doc = _read_json(UNIVERSE)
    if not isinstance(doc, dict) or not doc:
        return {}, {"status": "absent", "path": str(UNIVERSE),
                    "why": "no universe registry; routing is by asset class from MetaTrader's "
                           "own registry and there is nothing here to route"}
    rows = {str(k): v for k, v in doc.items() if isinstance(v, dict)}
    return rows, {"status": "present", "path": str(UNIVERSE), "n": len(rows)}


def _lane(symbol: str) -> bool | None:
    """True when this instrument may carry a statistical hypothesis; None when unreadable.

    None is NOT permission -- an unclassifiable symbol is named in the report and admitted by
    nothing. Only the registry may put an instrument in the discovery lane.
    """
    try:
        from research.universe_policy import may_hypothesise
    except Exception:                                    # pragma: no cover - import-context only
        return None
    try:
        return bool(may_hypothesise(symbol))
    except Exception:                                    # pragma: no cover - policy is pure json
        return None


def _asset_class(symbol: str, row: dict[str, Any]) -> str:
    klass = str(row.get("asset_class") or "").strip().lower()
    if klass:
        return klass
    try:
        from research.universe_policy import asset_class_of
        return str(asset_class_of(symbol) or "unclassified")
    except Exception:                                    # pragma: no cover - import-context only
        return "unclassified"


def bars(symbol: str) -> Any:
    """The desk's H1 frame for `symbol`, through the shared proposer helper. A seam for tests."""
    try:
        from research.proposer_common import bars as _bars
    except Exception:                                    # pragma: no cover - import-context only
        return None
    return _bars(symbol)


def daily_closes(frame: Any) -> np.ndarray | None:
    """One close per UTC calendar day, in order. None when the frame cannot yield a series.

    DAILY, NOT HOURLY, and the reason is not convenience. A 252-'bar' lookback on H1 is ten days;
    the premium being measured is a MONTHS-long one, and measuring it on the wrong clock measures
    a different thing that happens to share a number.
    """
    if frame is None:
        return None
    try:
        import pandas as pd
        if "close" not in getattr(frame, "columns", []):
            return None
        index = pd.DatetimeIndex(pd.to_datetime(frame.index, utc=True, errors="coerce"))
        series = pd.Series(np.asarray(frame["close"], dtype=float), index=index)
        series = series[~series.index.isna()].sort_index()
        daily = series.groupby(series.index.normalize()).last()
    except Exception:                                    # pragma: no cover - pandas is required
        return None
    values = np.asarray(daily.to_numpy(), dtype=float)
    values = values[np.isfinite(values) & (values > 0)]
    return values if values.size else None


# ----------------------------------------------------------------------------- the mechanism
def ts_momentum(closes: np.ndarray, speeds: tuple[int, ...] = SPEEDS) -> dict[str, Any]:
    """The vote across speeds, on the LAST observation, plus each speed's own log return."""
    log_close = np.log(closes)
    votes: dict[str, float] = {}
    for speed in speeds:
        if closes.size <= speed:
            continue
        votes[f"r{speed}"] = float(log_close[-1] - log_close[-1 - speed])
    if not votes:
        return {"n_speeds": 0, "vote": 0.0, "agreement": 0.0, "signals": {}, "side": 0}
    signs = [1.0 if v > 0 else (-1.0 if v < 0 else 0.0) for v in votes.values()]
    vote = float(np.mean(signs))
    return {"n_speeds": len(votes), "vote": round(vote, 4),
            "agreement": round(abs(vote), 4),
            "signals": {k: round(v, 6) for k, v in votes.items()},
            "side": 1 if vote > 0 else (-1 if vote < 0 else 0)}


def realised_vol(closes: np.ndarray, window: int = VOL_WINDOW) -> tuple[float | None, bool]:
    """Annualised volatility of daily log returns, and whether the numerical floor bound.

    The floor is a fraction of the instrument's OWN long-run volatility, so it is scale-free and
    cannot quietly become a risk limit: it only ever catches a degenerate estimate.
    """
    if closes.size < window + 2:
        return None, False
    returns = np.diff(np.log(closes))
    recent = returns[-window:]
    sigma = float(np.std(recent, ddof=1)) * math.sqrt(TRADING_DAYS)
    longrun = float(np.std(returns, ddof=1)) * math.sqrt(TRADING_DAYS)
    if not math.isfinite(sigma) or not math.isfinite(longrun) or longrun <= 0:
        return None, False
    floor = VOL_FLOOR_FRAC * longrun
    return (max(sigma, floor), sigma < floor)


def vol_scale(vol: float, target: float = TARGET_VOL) -> float:
    """w = target / realised. Above 1 for anything quieter than target, below 1 for anything
    noisier: a two-sided normaliser, never a cap. It is the whole reason a book of forty
    instruments is forty bets instead of one bet on whichever is loudest this quarter."""
    return float(target / vol) if vol > 0 else 0.0


def strategy_returns(closes: np.ndarray, side_series: np.ndarray) -> np.ndarray:
    """Daily returns of holding `side_series[t-1]` through day t. Signals are LAGGED by one day:
    a position taken on the close that produced the signal is a position taken on information
    the market had not yet printed."""
    returns = np.diff(np.log(closes))
    held = side_series[:-1]
    n = min(returns.size, held.size)
    return returns[-n:] * held[-n:] if n else np.asarray([], dtype=float)


def side_path(closes: np.ndarray, speeds: tuple[int, ...] = SPEEDS,
              min_agreement: float = MIN_AGREEMENT) -> np.ndarray:
    """The side the core would have held on every day, from that day's own information only."""
    log_close = np.log(closes)
    out = np.zeros(closes.size, dtype=float)
    for t in range(max(speeds), closes.size):
        signs = [1.0 if log_close[t] > log_close[t - s] else
                 (-1.0 if log_close[t] < log_close[t - s] else 0.0) for s in speeds]
        vote = float(np.mean(signs))
        out[t] = (1.0 if vote > 0 else -1.0) if abs(vote) >= min_agreement else 0.0
    return out


def cross_sectional(legs: list[dict[str, Any]]) -> dict[str, Any]:
    """Rank within asset class on the CS_SPEED return: long the top third, short the bottom.

    A class with fewer than three members has no terciles and gets NO cross-sectional signal --
    a two-member "top third" is the same instrument twice under a fancier name.
    """
    by_class: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for leg in legs:
        value = _f(leg.get("ts", {}).get("signals", {}).get(f"r{CS_SPEED}"))
        if value is not None:
            by_class[str(leg["asset_class"])].append(leg)
    assigned, skipped = 0, {}
    for klass, members in by_class.items():
        if len(members) < 3:
            skipped[klass] = len(members)
            for leg in members:
                leg["cs_side"] = 0
                leg["cs_why"] = "fewer than three members in this class: no terciles exist"
            continue
        members.sort(key=lambda m: float(m["ts"]["signals"][f"r{CS_SPEED}"]))
        cut = max(1, len(members) // 3)
        for i, leg in enumerate(members):
            leg["cs_side"] = -1 if i < cut else (1 if i >= len(members) - cut else 0)
            leg["cs_rank"] = round((i + 0.5) / len(members), 4)
            leg["cs_why"] = f"rank {i + 1}/{len(members)} in {klass} on {CS_SPEED}d return"
            assigned += 1 if leg["cs_side"] else 0
    return {"classes": {k: len(v) for k, v in sorted(by_class.items())},
            "assigned": assigned, "skipped_thin_classes": skipped, "speed_days": CS_SPEED}


def correlation_structure(names: list[str], series: list[np.ndarray]) -> dict[str, Any]:
    """How many independent directions the core spans, and the aggregate it therefore is.

    `effective_rank` is the participation ratio of the singular spectrum -- continuous in the
    angle between legs, so crowding is visible while it is forming rather than at a tolerance
    step. Forty legs at rank_eff 3 is three bets with forty tickets, and that is the number that
    decides whether this core is a diversifier or a leveraged dollar view.
    """
    if not series:
        return {"status": UNMEASURED, "why": "no leg produced a return series"}
    width = min(int(s.size) for s in series)
    if width < VOL_WINDOW:
        return {"status": UNMEASURED, "n_legs": len(series), "overlap_days": width,
                "why": f"only {width} overlapping day(s) across the legs; a correlation on that "
                       f"is noise wearing a number"}
    matrix = np.vstack([np.asarray(s[-width:], dtype=float) for s in series])
    if not np.all(np.isfinite(matrix)):
        return {"status": UNMEASURED, "why": "a leg's return series carries a non-finite entry"}
    sd = matrix.std(axis=1, ddof=1)
    live = sd > 0
    matrix, kept = matrix[live], [n for n, ok in zip(names, live, strict=False) if ok]
    if matrix.shape[0] < 2:
        return {"status": UNMEASURED, "n_legs": int(matrix.shape[0]),
                "why": "fewer than two legs with a non-degenerate return series"}
    corr = np.corrcoef(matrix)
    # STANDARDISED ROWS, AND THIS IS NOT COSMETIC. The participation ratio is computed on the
    # singular spectrum, so a matrix of raw returns is dominated by whichever leg is loudest:
    # six genuinely uncorrelated legs of unequal volatility read as ~1 effective direction, which
    # is a statement about scale and not about crowding. Centring and dividing each row by its own
    # sd makes the spectrum the CORRELATION structure's -- which is the thing being measured, and
    # the thing the vol scaling has already equalised in the book itself.
    centred = matrix - matrix.mean(axis=1, keepdims=True)
    standard = centred / matrix.std(axis=1, ddof=1)[:, None]
    try:
        from libs.risk.fx_exposure import effective_rank
        rank_eff = float(effective_rank(standard))
        how = "libs.risk.fx_exposure.effective_rank (participation ratio of the spectrum)"
    except Exception:                                    # pragma: no cover - import-context only
        eigenvalues = np.linalg.eigvalsh(corr)
        weights = np.clip(eigenvalues, 0.0, None)
        total = float(weights.sum())
        rank_eff = float(total * total / float(np.square(weights).sum())) if total > 0 else 0.0
        how = "local participation ratio of the correlation spectrum (fx_exposure unavailable)"
    off = corr[np.triu_indices_from(corr, k=1)]
    return {"status": "present", "n_legs": len(kept), "overlap_days": int(width),
            "effective_rank": round(rank_eff, 3),
            "independence": round(rank_eff / len(kept), 4) if kept else None,
            "mean_abs_correlation": round(float(np.mean(np.abs(off))), 4),
            "max_correlation": round(float(np.max(off)), 4) if off.size else None,
            "how": how,
            "reads_as": (f"{round(rank_eff, 2)} independent direction(s) across {len(kept)} legs "
                         f"-- the core is ONE bet to the extent this number is near 1")}


def log_growth(returns: np.ndarray) -> dict[str, Any]:
    """E[log W] per year on a daily return series: mu - sigma^2/2, annualised, with its sigma.

    MEASURED ON THE AGGREGATE, never summed across legs. Summing the legs' growth rates counts
    a correlated book once per ticket, which is exactly the error the participation ratio above
    exists to make visible.
    """
    if returns.size < VOL_WINDOW:
        return {"status": UNMEASURED, "n_days": int(returns.size),
                "why": f"{returns.size} day(s) is below the {VOL_WINDOW}-day floor"}
    mu = float(np.mean(returns)) * TRADING_DAYS
    sigma = float(np.std(returns, ddof=1)) * math.sqrt(TRADING_DAYS)
    if not math.isfinite(mu) or not math.isfinite(sigma):
        return {"status": UNMEASURED, "why": "non-finite moments"}
    return {"status": "present", "n_days": int(returns.size),
            "mu_annual": round(mu, 5), "sigma_annual": round(sigma, 5),
            "e_log_w": round(mu - 0.5 * sigma * sigma, 5),
            "sharpe": round(mu / sigma, 4) if sigma > 0 else None,
            "note": "arithmetic drift minus half the variance, on the CORE's own aggregate"}


# --------------------------------------------------------------------------------- the sleeves
def sleeve_roster() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """The tactical sleeves the core sits BESIDE. Read only: nothing here writes or resizes one."""
    doc = _read_json(SLEEVES)
    rows = doc.get("sleeves") if isinstance(doc, dict) else None
    if not isinstance(rows, list):
        return [], {"status": "absent", "path": str(SLEEVES),
                    "why": "no sleeve roster; the core's independence from the existing book is "
                           "UNMEASURED, which is a verdict and not an all-clear"}
    out: list[dict[str, Any]] = [
        {"name": str(r.get("name") or ""), "symbol": str(r.get("symbol") or ""),
         "family": str(r.get("family") or ""), "status": str(r.get("status") or ""),
         "risk_frac": _f(r.get("risk_frac"))}
        for r in rows if isinstance(r, dict)]
    live = sum(1 for r in out if str(r["status"]).upper() == "LIVE")
    return out, {"status": "present", "path": str(SLEEVES), "n": len(out), "live": live}


def beside_sleeves(core_returns: np.ndarray, legs: list[dict[str, Any]],
                   sleeves: list[dict[str, Any]]) -> dict[str, Any]:
    """The core's overlap with the existing book, measured where it can be and named where not.

    THE SLEEVES' OWN REALISED RETURN SERIES IS NOT ON THIS TREE, so the true sleeve-to-core
    correlation is UNMEASURED and says so. What IS measurable is the core's correlation to the
    UNDERLYING each sleeve trades, which is an UPPER BOUND on how much they can share: a scalp on
    gold cannot be more correlated to a trend core than gold's own trend leg is. Reported as the
    bound it is, never as the correlation itself.
    """
    if core_returns.size < VOL_WINDOW or not sleeves:
        return {"status": UNMEASURED,
                "why": ("no core series" if core_returns.size < VOL_WINDOW
                        else "no sleeve roster to compare against")}
    by_symbol = {str(leg["symbol"]): leg for leg in legs}
    bounds = []
    for sleeve in sleeves:
        leg = by_symbol.get(sleeve["symbol"])
        series = None if leg is None else leg.get("_returns")
        if series is None or np.asarray(series).size < VOL_WINDOW:
            bounds.append({"sleeve": sleeve["name"], "symbol": sleeve["symbol"],
                           "bound": None, "status": UNMEASURED,
                           "why": "the core holds no measured leg on this sleeve's instrument"})
            continue
        arr = np.asarray(series, dtype=float)
        width = min(arr.size, core_returns.size)
        if width < VOL_WINDOW:
            bounds.append({"sleeve": sleeve["name"], "symbol": sleeve["symbol"],
                           "bound": None, "status": UNMEASURED, "why": "thin overlap"})
            continue
        a, b = arr[-width:], core_returns[-width:]
        if float(np.std(a)) <= 0 or float(np.std(b)) <= 0:
            bounds.append({"sleeve": sleeve["name"], "symbol": sleeve["symbol"],
                           "bound": None, "status": UNMEASURED, "why": "degenerate series"})
            continue
        bounds.append({"sleeve": sleeve["name"], "symbol": sleeve["symbol"],
                       "bound": round(float(np.corrcoef(a, b)[0, 1]), 4), "status": "bound",
                       "why": "correlation of the core to THIS SLEEVE'S INSTRUMENT leg -- an "
                              "upper bound on the sleeve-to-core overlap, not the overlap"})
    measured = [r["bound"] for r in bounds if r["bound"] is not None]
    return {"status": "present" if measured else UNMEASURED, "bounds": bounds,
            "max_bound": (round(sorted((float(v) for v in measured),
                                       key=lambda x: -abs(x))[0], 4) if measured else None),
            "sleeve_returns": UNMEASURED,
            "why": ("the sleeves' own realised return series is not published on this tree; the "
                    "bound is what is measurable and it is labelled as a bound")}


# --------------------------------------------------------------------------------- the spec
def core_params() -> dict[str, Any]:
    """`mt5desk.family_multi_speed_trend` parameters ONLY -- the family's own vocabulary."""
    return {"speeds": list(SPEEDS), "vol_window": VOL_WINDOW,
            "hold_days": 5, "min_agreement": MIN_AGREEMENT, "crisis_only": False,
            "atr_n": 20, "stop_atr": 2.5, "rr": 2.0}


def shadow_spec(symbol: str) -> dict[str, Any]:
    """The spec shape `shadow_admission.authorized_runs` / `shadow_forward` consume, exactly.

    `side` IS A DECLARATION THE READER REQUIRES, NOT A CONSTRAINT THIS FAMILY OBEYS.
    `multi_speed_trend` votes long or short per bar from its own speeds, so the direction is
    internal to the family; the enrolment reader refuses a spec whose `side` is neither LONG nor
    SHORT, and it is recorded as LONG with `direction_from` naming the vote, so an auditor reading
    the certificate sees which it was rather than inferring a long-only publisher.
    """
    return {"symbol": symbol, "family": FAMILY, "side": "LONG", "selector": "all_day",
            "condition": "ANY", "is_universe": True, "hunt": SOURCE,
            "direction_from": "family_vote_across_speeds",
            "params": core_params()}


def _registered(family: str) -> bool:
    try:
        from mt5desk.families_orthogonal import ORTHOGONAL_FAMILIES
    except Exception:                                    # pragma: no cover - import-context only
        return False
    return family in ORTHOGONAL_FAMILIES


def donation_rows(legs: list[dict[str, Any]], limit: int,
                  structure: dict[str, Any]) -> tuple[list[dict[str, Any]],
                                                      list[dict[str, Any]]]:
    """(candidates, refusals). The core's strongest-agreement legs, in the normal contract.

    The two-lane mandate is enforced HERE and only here: a leg that was measured above may still
    be refused at this door, and every refusal is counted with its reason.
    """
    refused: list[dict[str, Any]] = []
    if legs and not _registered(FAMILY):
        return [], [{"symbol": leg["symbol"],
                     "why": f"{FAMILY} is not in ORTHOGONAL_FAMILIES on this tree"}
                    for leg in legs[:5]]
    out: list[dict[str, Any]] = []
    ranked = sorted(legs, key=lambda leg: (-float(leg["ts"]["agreement"]),
                                           -abs(float(leg.get("weight") or 0.0)),
                                           str(leg["symbol"])))
    for leg in ranked:
        if len(out) >= max(int(limit), 0):
            break
        allowed = _lane(str(leg["symbol"]))
        if allowed is not True:
            refused.append({"symbol": leg["symbol"], "asset_class": leg["asset_class"],
                            "why": ("the two-lane mandate: this instrument is traded on news, "
                                    "reports and earnings reaction and is never hunted for a "
                                    "statistical hypothesis"
                                    if allowed is False else
                                    "universe policy unreadable here; absence is not permission")})
            continue
        spec = shadow_spec(str(leg["symbol"]))
        out.append({"source": SOURCE, "kind": "hypothesis", "symbol": leg["symbol"],
                    "symbols": [leg["symbol"]], "family": FAMILY, "params": core_params(),
                    "url": "", "shadow_spec": spec,
                    "title": f"trend core leg {leg['symbol']} "
                             f"({leg['asset_class']})"[:120],
                    "mechanism": (
                        f"multi-speed trend across {SPEEDS} trading days, vol-scaled to "
                        f"{TARGET_VOL:.0%} annualised. This leg: {leg['ts']['n_speeds']} speeds, "
                        f"agreement {leg['ts']['agreement']}, realised vol "
                        f"{leg['vol_annual']}, weight {leg['weight']}, cross-sectional rank "
                        f"{leg.get('cs_rank')}. It is ONE LEG OF A CORE whose measured "
                        f"independence is {structure.get('effective_rank')} effective "
                        f"direction(s) over {structure.get('n_legs')} legs -- the core is the "
                        f"bet, the leg is how it is expressed here")[:400],
                    "evidence": {"agreement": leg["ts"]["agreement"],
                                 "vote": leg["ts"]["vote"], "n_speeds": leg["ts"]["n_speeds"],
                                 "vol_annual": leg["vol_annual"], "weight": leg["weight"],
                                 "cs_side": leg.get("cs_side"), "cs_rank": leg.get("cs_rank"),
                                 "leg_e_log_w": (leg.get("growth") or {}).get("e_log_w"),
                                 "core_effective_rank": structure.get("effective_rank"),
                                 "asset_class": leg["asset_class"],
                                 "screen": RULE}})
    return out, refused


def _donate(candidates: list[dict[str, Any]], tests_run: int) -> Any:
    """The seam. One import, one call, so a test can watch what leaves without a live intake."""
    from research.proposer_common import donate
    return donate(SOURCE, candidates, tests_run)


# --------------------------------------------------------------------------------- the organ
def build(*, budget_s: float = 600.0, max_donations: int = MAX_DONATIONS,
          apply: bool = True, now: datetime | None = None,
          symbols: list[str] | None = None) -> dict[str, Any]:
    """Measure the core and return the payload. Touches disk only through `main`."""
    started = time.monotonic()
    now = now or _now()
    rows, universe_status = universe_rows()
    names = sorted(symbols if symbols is not None else rows)
    cap = max_symbols()
    legs: list[dict[str, Any]] = []
    skipped: dict[str, int] = defaultdict(int)
    measured_only: list[dict[str, Any]] = []
    stopped = False
    reached = 0
    for symbol in names:
        if time.monotonic() - started > budget_s or reached >= cap:
            stopped = True
            break
        reached += 1
        closes = daily_closes(bars(symbol))  # type: np.ndarray | None
        if closes is None or closes.size < MIN_DAYS:
            skipped["no_or_thin_series"] += 1
            continue
        vol, floored = realised_vol(closes)
        if vol is None:
            skipped["no_volatility"] += 1
            continue
        ts = ts_momentum(closes)
        if ts["n_speeds"] < len(SPEEDS):
            skipped["not_every_speed_seen"] += 1
            continue
        path = side_path(closes)
        returns = strategy_returns(closes, path)
        leg: dict[str, Any] = {
            "symbol": symbol, "asset_class": _asset_class(symbol, rows.get(symbol) or {}),
            "lane_may_hypothesise": _lane(symbol), "n_days": int(closes.size),
            "ts": ts, "vol_annual": round(vol, 5), "vol_floor_bound": bool(floored),
            "weight": round(vol_scale(vol) * float(ts["side"]), 4),
            "growth": log_growth(returns), "_returns": returns}
        if leg["lane_may_hypothesise"] is not True:
            # MEASURED, and that is all. The two-lane mandate says a single-name equity's edge is
            # sought in the event lane; measuring its trend costs the trial budget nothing and
            # tells the desk what it is passing on, which is the difference between a decision
            # and a blind spot.
            measured_only.append({k: v for k, v in leg.items() if k != "_returns"})
            continue
        legs.append(leg)
    cs = cross_sectional(legs)
    admitted = [leg for leg in legs if abs(float(leg["ts"]["agreement"])) >= MIN_AGREEMENT]
    structure = correlation_structure([str(leg["symbol"]) for leg in admitted],
                                      [np.asarray(leg["_returns"]) for leg in admitted])
    if admitted:
        width = min(int(np.asarray(leg["_returns"]).size) for leg in admitted)
        stacked = np.vstack([np.asarray(leg["_returns"])[-width:] * abs(float(leg["weight"]))
                             for leg in admitted]) if width else np.zeros((1, 0))
        gross = sum(abs(float(leg["weight"])) for leg in admitted) or 1.0
        core = np.asarray(stacked.sum(axis=0) / gross, dtype=float)
    else:
        core = np.asarray([], dtype=float)
    growth = log_growth(core)
    sleeves, sleeve_status = sleeve_roster()
    overlap = beside_sleeves(core, admitted, sleeves)
    cands, refusals = donation_rows(admitted, max_donations, structure)
    donated_to = _donate(cands, len(legs) + len(measured_only)) if (apply and cands) else None
    status = "present" if admitted else UNMEASURED
    why = "" if admitted else (
        universe_status.get("why")
        or f"{reached} instrument(s) read and none produced {MIN_DAYS} daily closes with every "
           f"speed seen and {MIN_AGREEMENT:.0%} of speeds agreeing; the core is UNMEASURED, "
           f"which is a verdict and not an empty book")
    report = {
        "at": now.isoformat(timespec="seconds"), "source": SOURCE, "status": status, "why": why,
        "rule": RULE, "standing_order": STANDING,
        "elapsed_s": round(time.monotonic() - started, 2), "budget_s": budget_s,
        "universe": universe_status,
        "scan": {"named": len(names), "reached": reached, "cap": cap,
                 "stopped_on_budget_or_cap": stopped, "skipped": dict(skipped),
                 "measured_not_hypothesised": len(measured_only),
                 "why_measured_only": ("single-name equities and unclassified instruments are "
                                       "MEASURED here and hypothesised by nothing (two-lane "
                                       "mandate); absence of a class is not permission")},
        "spec": {"family": FAMILY, "params": core_params(), "speeds": list(SPEEDS),
                 "target_vol": TARGET_VOL, "min_agreement": MIN_AGREEMENT,
                 "example": shadow_spec(str(admitted[0]["symbol"])) if admitted else None,
                 "shape": ("the shadow_spec shape the forward enrolment reader consumes: "
                           "symbol, family, side, selector, condition, is_universe, hunt, plus "
                           "the certified params")},
        "cross_sectional": cs,
        "structure": structure,
        "core_growth": growth,
        "n_legs_measured": len(legs), "n_legs_admitted": len(admitted),
        "legs": [{k: v for k, v in leg.items() if k != "_returns"} for leg in admitted[:MAX_LEGS]],
        "measured_only": measured_only[:MAX_LEGS],
        "by_class": {klass: sum(1 for leg in admitted if leg["asset_class"] == klass)
                     for klass in sorted({str(leg["asset_class"]) for leg in admitted})},
        "vol_floor_bound": sum(1 for leg in admitted if leg["vol_floor_bound"]),
        "sleeves": {**sleeve_status, "roster": sleeves[:40]},
        "beside_sleeves": overlap,
        "donated": {"n": len(cands) if donated_to else 0,
                    "path": str(donated_to) if donated_to else None,
                    "symbols": [c["symbol"] for c in cands],
                    "n_candidates": len(cands),
                    "refused": refusals[:20], "n_refused": len(refusals),
                    "status": ("donated" if donated_to else
                               "nothing admitted, or the donation door refused every row"),
                    "rule": "the core reaches the ten gates through the normal proposer "
                            "contract; it has no privileged path to capital and no exemption"},
    }
    return {"report": report, "core_returns": core}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="the trend-following core of the book")
    ap.add_argument("--once", action="store_true", help="one pass (the only mode there is)")
    ap.add_argument("--budget-s", type=float, default=600.0, help="wall-clock budget")
    ap.add_argument("--max-donations", type=int, default=MAX_DONATIONS)
    ap.add_argument("--dry-run", action="store_true", help="measure and print; write nothing")
    a = ap.parse_args(argv)
    built = build(budget_s=a.budget_s, max_donations=a.max_donations, apply=not a.dry_run)
    rep = built["report"]
    st, growth = rep["structure"], rep["core_growth"]
    print(f"trend_core at={rep['at']} status={rep['status']} elapsed={rep['elapsed_s']}s")
    print(f"  scan       {rep['scan']['reached']}/{rep['scan']['named']} instrument(s), cap "
          f"{rep['scan']['cap']}; skipped {rep['scan']['skipped']}")
    print(f"  legs       measured {rep['n_legs_measured']}, admitted {rep['n_legs_admitted']}, "
          f"measured-not-hypothesised {rep['scan']['measured_not_hypothesised']}")
    print("  classes    " + ("  ".join(f"{k}:{v}" for k, v in rep["by_class"].items()) or "none"))
    print(f"  structure  {st.get('status')}: rank_eff={st.get('effective_rank')} over "
          f"{st.get('n_legs')} legs, independence={st.get('independence')}, "
          f"mean|rho|={st.get('mean_abs_correlation')}")
    print(f"  growth     {growth.get('status')}: E[log W]={growth.get('e_log_w')}/yr "
          f"(mu={growth.get('mu_annual')}, sigma={growth.get('sigma_annual')}) over "
          f"{growth.get('n_days')} day(s)")
    print(f"  sleeves    {rep['sleeves'].get('status')} n={rep['sleeves'].get('n')}; overlap "
          f"{rep['beside_sleeves'].get('status')} max_bound="
          f"{rep['beside_sleeves'].get('max_bound')}")
    verb = "would donate" if a.dry_run else "donated"
    print(f"  {verb:<10} {rep['donated']['n_candidates'] if a.dry_run else rep['donated']['n']} "
          f"({rep['donated']['status']}); {rep['donated']['n_refused']} refused")
    print(f"  rule       {RULE}")
    print(f"  standing   {STANDING}")
    if a.dry_run:
        print(f"  --dry-run: nothing written, nothing donated; would have written {REPORT.name}")
        return 0
    _atomic(REPORT, json.dumps(rep, indent=1, default=str))
    print(f"  -> {REPORT}")
    return 0


if __name__ == "__main__":                                       # pragma: no cover - CLI
    raise SystemExit(main())
