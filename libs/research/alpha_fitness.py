"""What an alpha is WORTH TO THIS BOOK, term by term, with every term measured or named absent.

THE DEFECT THIS REPLACES. `alpha_evolution` scored a candidate as

    t x (0.5 + 0.5 x stability) - LAMBDA_CORR x relu(corr_survivors) x |t|
                                + LAMBDA_NOVEL x novelty - LAMBDA_CX x complexity

which is a standalone t with two haircuts. It cannot see growth (a t says nothing about what
heat the candidate earns), it cannot see the tail (a strategy that pays exactly when the book
bleeds scores the same as one that pays on quiet Tuesdays), it cannot see cost, capacity,
fragility, state breadth, or the trials spent finding it. Every one of those is a reason a
measured t does not become money, and the search was blind to all of them.

    Fitness = w1 dE[logW_P] + w2 OOS + w3 Novelty + w4 Tail + w5 StateBreadth + w6 Capacity
              - w7 Cost - w8 Fragility - w9 Complexity - w10 Multiplicity

WHAT MAKES THIS PORTFOLIO-AWARE RATHER THAN PORTFOLIO-FLAVOURED. `dE[logW_P]` is not a
correlation penalty standing in for growth: it is `libs.portfolio.robust_elog.marginal_delta_elog`
-- the SAME solver the allocator runs -- re-solving the book with and without the candidate and
reporting the difference in robust growth. A candidate that improves growth takes heat from
whatever it beats; one that does not is declined on the arithmetic. And `Tail` is
`E[R_i | R_P < q10]` on the book's OWN worst decile: the search's standing question becomes
"what makes money when the current portfolio loses", which is the only question whose answer
raises total safe heat rather than crowding it.

EVERY TERM IS MEASURED OR NAMED. An unmeasurable term is 0.0 AND its name is in `unmeasured` --
never a silent zero, never a guessed default. With no book on disk, `delta_elog` is 0.0 and the
report says "no book to measure against", so a fitness computed on an empty desk cannot be
mistaken for a fitness computed against a full one.

NOTHING HERE HAS AUTHORITY. This ranks candidates inside a search. The ten gates certify, the
allocator sizes, and a high fitness buys a trial and nothing else.
"""
from __future__ import annotations

import json
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
#: Where the current book is read from, best first. The allocator's own artifact is the truth;
#: `data/sleeves.json` is the older hand-maintained list; an empty book is the honest floor.
PF_ALLOCATION = DESK / "reports" / "pf_allocation.json"
SLEEVE_DAILY = DESK / "data" / "pf_allocator_cache" / "daily_r.parquet"
SLEEVES_JSON = ROOT / "data" / "sleeves.json"

#: The book's worst decile. The same 0.10 `tail_alpha_search` conditions on, and deliberately the
#: same number: two organs asking "what pays when the book bleeds" must mean the same days by it.
TAIL_Q = 0.10
#: Fewest book-days before a tail decile is a decile rather than a handful of anecdotes.
MIN_TAIL_DAYS = 40
#: Train/holdout split for the OOS term. The holdout is measured and never used to choose.
TRAIN_FRAC = 0.70
MIN_OBS = 30
#: State buckets and the fewest observations one needs before it is ADMITTED. A bucket with
#: eight observations has a positive mean about half the time whatever the alpha does.
STATE_BUCKETS = 5
MIN_STATE_OBS = 30
#: Capacity references, declared rather than fitted. `SPREAD_REF` is the round-trip spread at
#: which an H1 cell's capacity is judged HALVED (2 bp of price -- roughly Fusion's gold spread in
#: a normal session); `TICKS_REF` is the tick activity per bar at which depth stops binding.
#: Both are proxies and are named as proxies: this desk's feed publishes ticks, not contracts.
CAPACITY_SPREAD_REF = 2e-4
CAPACITY_TICKS_REF = 500.0
#: How far a parameter is moved to measure fragility. +-20%: large enough that a knife-edge fit
#: shows, small enough that the cell is still the same hypothesis.
FRAGILITY_PCT = 0.20

#: THE EXCHANGE RATES. Every term below is on a stated scale, and a weight is what the desk will
#: TRADE one term for another -- not a tuning knob, and not revisable to make a candidate pass.
#:
#:   delta_elog    1.0  annual growth POINTS the book gains. The unit of account: one fitness
#:                      point is one point of annual growth, because growth is what is being
#:                      maximised and every other term is a reason a measured edge will not
#:                      become growth.
#:   oos           0.5  holdout t. Two points of out-of-sample t are worth one point of growth:
#:                      evidence the edge survives a sample it never saw, priced but not
#:                      confused with the growth itself.
#:   novelty       0.5  1 - max|rho| against canon and population, in [0, 1]. Half a point for a
#:                      behaviourally new KIND of money, which is what keeps the search from
#:                      spending every generation on variants of what the book already owns.
#:   tail          2.0  standardised E[R | book's worst decile]. THE HEAVIEST REWARD, on purpose:
#:                      a diversifier that pays in the book's drawdown raises the total heat the
#:                      allocator can safely run, which is worth more than the same edge earned
#:                      on days the book was already making money.
#:   state_breadth 0.5  share of admitted state buckets with a positive forward mean, in [0, 1].
#:                      An edge that lives in one bucket is one bucket away from being over.
#:   capacity      0.5  spread x depth proxy in [0, 1]. An edge the desk cannot size into is a
#:                      paper edge; half a point, because the proxy is coarse.
#:   cost          1.0  round trip as a multiple of the gross edge. Charged at full weight: cost
#:                      is not a discount on the edge, it is the reason WS-006 (Holm-cleared at
#:                      t=+3.95) still netted -0.656 bp/bar.
#:   fragility     1.0  mean relative score loss under +-20% parameter perturbation, in [0, ~1].
#:                      Full weight: a cell that only works at one setting was fitted to noise.
#:   complexity    0.03 node count. The same LAMBDA_CX the evolution already charged, kept so the
#:                      promotion of this module changes what is measured, not the node price.
#:   multiplicity  0.5  the deflated-Sharpe hurdle E[max Sharpe over N trials] the gauntlet will
#:                      charge anyway. Half weight because the gauntlet charges it in full later;
#:                      here it only has to stop the search preferring the wider haystack.
WEIGHTS: dict[str, float] = {
    "delta_elog": 1.0, "oos": 0.5, "novelty": 0.5, "tail": 2.0, "state_breadth": 0.5,
    "capacity": 0.5, "cost": 1.0, "fragility": 1.0, "complexity": 0.03, "multiplicity": 0.5,
}
#: The terms the fitness SUBTRACTS. Held as data so `score` cannot disagree with the formula in
#: this module's docstring.
PENALTIES: frozenset[str] = frozenset({"cost", "fragility", "complexity", "multiplicity"})


# --------------------------------------------------------------------------- the book
@dataclass(frozen=True)
class Book:
    """The desk's CURRENT book: the daily P&L the tail conditions on, and the sleeves the
    growth term re-solves against. An empty book is a legal book and says so in `source`."""

    daily: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))
    sleeves: tuple[Any, ...] = ()
    hard_cap: float = 0.35
    source: str = "empty book"

    @property
    def is_empty(self) -> bool:
        return not len(self.daily) and not self.sleeves


def _read_json(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(Path(path).read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _daily_matrix(path: Path) -> pd.DataFrame | None:
    try:
        df = pd.read_parquet(path)
    except (OSError, ValueError, ImportError):
        return None
    if df.empty:
        return None
    df.index = pd.DatetimeIndex(pd.to_datetime(df.index, utc=True, errors="coerce"))
    return df[~df.index.isna()]


def load_book(*, allocation: Path = PF_ALLOCATION, daily: Path = SLEEVE_DAILY,
              sleeves_json: Path = SLEEVES_JSON) -> Book:
    """The current book, from the allocator's artifact, then the sleeve list, then empty.

    DEFENSIVE ON PURPOSE. This runs inside an hourly search on a box where the allocator may not
    have run yet, where the evidence cache may be older than the artifact, and where a sibling
    engineer may be mid-write. Every failure produces the NEXT source and a `source` string that
    says which one won -- never an exception into the search, never a silent empty book that
    reads like a book with nothing in it.
    """
    art = _read_json(allocation)
    heats = art.get("book") if isinstance(art.get("book"), dict) else {}
    mat = _daily_matrix(daily)
    if heats and mat is not None:
        cols = [c for c in mat.columns if str(c) in heats]
        if cols:
            w = pd.Series({c: float(heats[str(c)]) for c in cols}, dtype=float)
            book_daily = (mat[cols].fillna(0.0) * w).sum(axis=1)
            return Book(daily=book_daily, sleeves=_sleeve_evidence(mat[cols], art),
                        hard_cap=float(art.get("hard_cap") or art.get("total_heat") or 0.35),
                        source=f"{allocation.name} x {daily.name}: {len(cols)} funded sleeves")
    if mat is not None and heats:
        return Book(hard_cap=float(art.get("hard_cap") or 0.35),
                    source=f"{allocation.name}: heats without a matching daily-R matrix")
    doc = _read_json(sleeves_json)
    rows = doc.get("sleeves") if isinstance(doc.get("sleeves"), list) else None
    if rows:
        series: dict[str, pd.Series] = {}
        for r in rows:
            if not isinstance(r, dict):
                continue
            name = str(r.get("name") or r.get("sleeve") or "")
            vals = r.get("daily_r") or r.get("daily")
            if name and isinstance(vals, list) and vals:
                series[name] = pd.Series([float(v) for v in vals], dtype=float)
        if series:
            frame = pd.DataFrame(series)
            return Book(daily=frame.mean(axis=1), sleeves=_sleeve_evidence(frame, doc),
                        source=f"{sleeves_json.name}: {len(series)} sleeves, equal weight")
    return Book(source="empty book: no allocation artifact and no sleeve list")


def _sleeve_evidence(frame: pd.DataFrame, meta: Mapping[str, Any]) -> tuple[Any, ...]:
    """The book's sleeves as `SleeveEvidence`, or () when `robust_elog` is not importable.

    `n_trials` rides along from the artifact when it recorded one: the winner's-curse shrinkage
    is the whole reason that field exists, and dropping it here would size the candidate against
    a book whose own edges look better than the allocator believes them to be.
    """
    try:
        from libs.portfolio.robust_elog import SleeveEvidence
    except Exception:
        return ()
    trials = meta.get("evidence", {}).get("search_trials") if isinstance(
        meta.get("evidence"), dict) else None
    n_trials = int(trials) if isinstance(trials, (int, float)) and trials else 1
    out = []
    for c in frame.columns:
        arr = frame[c].to_numpy(dtype=float)
        arr = arr[np.isfinite(arr)]
        if arr.size:
            out.append(SleeveEvidence(name=str(c), daily_r=arr, n_trials=n_trials))
    return tuple(out)


# --------------------------------------------------------------------------- the terms
def _finite(x: pd.Series | np.ndarray) -> np.ndarray:
    arr = np.asarray(x, dtype=float)
    out: np.ndarray = arr[np.isfinite(arr)]
    return out


def _t_stat(arr: np.ndarray) -> float:
    if arr.size < MIN_OBS:
        return 0.0
    sd = float(arr.std(ddof=1))
    if not math.isfinite(sd) or sd <= 1e-15:
        return 0.0
    return float(arr.mean() / (sd / math.sqrt(arr.size)))


def delta_elog_term(book: Book, candidate_daily: pd.Series, *, name: str = "candidate",
                    cfg: Any = None) -> tuple[float, str]:
    """Annual growth POINTS the book gains by admitting the candidate, or 0.0 and a reason.

    THE SAME SOLVER THE ALLOCATOR RUNS. `marginal_delta_elog` re-solves both books, so "the book
    is full" is not an answer it can give: if the candidate improves robust growth the optimiser
    finds the heat by taking it from whatever it beats. That is what makes this a portfolio
    question rather than a correlation haircut.

    `cfg` may carry a cheaper world population for search-time scoring; the allocator's own pass
    uses its full one, so nothing sized on this number is sized on the cheap draw.
    """
    arr = _finite(candidate_daily)
    if not book.sleeves:
        return 0.0, f"no book to measure against ({book.source}): dE[logW_P] unmeasured"
    if arr.size < MIN_OBS:
        return 0.0, f"under {MIN_OBS} finite daily observations: dE[logW_P] unmeasured"
    try:
        from libs.portfolio.robust_elog import SleeveEvidence, marginal_delta_elog
        cand = SleeveEvidence(name=name, daily_r=arr, n_trials=1)
        out = marginal_delta_elog(list(book.sleeves), cand, hard_cap=book.hard_cap, cfg=cfg)
    except Exception as exc:
        return 0.0, f"marginal_delta_elog unavailable ({type(exc).__name__}): unmeasured"
    got = out.get("delta_annual_growth_pct")
    if not isinstance(got, (int, float)) or not math.isfinite(float(got)):
        return 0.0, "both books ruinous: dE[logW_P] refused rather than reported"
    return float(got), f"marginal_delta_elog against {book.source}"


def oos_term(daily: pd.Series, *, train_frac: float = TRAIN_FRAC) -> tuple[float, str]:
    """The holdout t of the candidate's own daily P&L. Measured, never used to choose.

    The split is chronological and the TRAIN half is what every other term is fitted on, so this
    is the one number in the vector that the search did not get to optimise directly.
    """
    arr = np.asarray(daily, dtype=float)
    cut = int(len(arr) * float(train_frac))
    hold = _finite(arr[cut:])
    if hold.size < MIN_OBS:
        return 0.0, f"holdout under {MIN_OBS} observations: OOS unmeasured"
    return _t_stat(hold), f"holdout t over {hold.size} days after a {train_frac:.0%} split"


def novelty_term(z: pd.Series, refs: Sequence[pd.Series]) -> tuple[float, str]:
    """1 - the largest absolute correlation with anything the desk already says.

    Feature-space novelty, so part of the search is always hunting a different KIND of money
    rather than a better version of the same one. NO REFERENCES IS UNMEASURED, NOT NOVEL: an
    absence of comparison is not evidence of difference, and paying the full credit for it would
    hand every candidate on an empty desk the novelty bonus the term exists to ration.
    """
    if not refs:
        return 0.0, "no reference alphas to be new against: novelty unmeasured"
    best = 0.0
    for r in refs:
        c = _corr(z, r)
        best = max(best, abs(c))
    return float(1.0 - best), f"1 - max|rho| over {len(refs)} references"


def _corr(a: pd.Series | None, b: pd.Series | None) -> float:
    if a is None or b is None:
        return 0.0
    j = pd.concat([pd.Series(a), pd.Series(b)], axis=1, join="inner").dropna()
    if len(j) < 20 or float(j.iloc[:, 0].std()) == 0.0 or float(j.iloc[:, 1].std()) == 0.0:
        return 0.0
    c = float(j.iloc[:, 0].corr(j.iloc[:, 1]))
    return c if math.isfinite(c) else 0.0


def tail_term(candidate_daily: pd.Series, book_daily: pd.Series, *, q: float = TAIL_Q,
              ) -> tuple[float, dict[str, Any], str]:
    """`E[R_i | R_P < q10]`, standardised -- the answer to "what pays when the book loses".

    REWARDED, NOT PENALISED, and weighted heaviest of the six credits. A cell that is merely
    average on the book's bad days is proposed by every other sweep; this term exists to find
    the one that is POSITIVE there, because that is the cell that raises the total heat the
    allocator can safely run rather than crowding the heat already committed.

    The raw conditional expectancy and the tail correlation ride along in the detail: the score
    is standardised so it can sit beside the other terms, and the raw number is what a human
    reads. With no book, or a book too short for a decile to mean anything, the term is 0.0 and
    named -- an unmeasured tail is not a neutral tail.
    """
    detail: dict[str, Any] = {"q": q, "tail_days": 0, "tail_contribution": None,
                              "tail_novelty": None}
    if book_daily is None or len(book_daily) < MIN_TAIL_DAYS:
        return 0.0, detail, f"book has under {MIN_TAIL_DAYS} days: tail contribution unmeasured"
    joined = pd.concat([pd.Series(candidate_daily).rename("i"),
                        pd.Series(book_daily).rename("p")], axis=1, join="inner").dropna()
    if len(joined) < MIN_TAIL_DAYS:
        return 0.0, detail, "candidate and book overlap on too few days: tail unmeasured"
    thr = float(joined["p"].quantile(q))
    bad = joined[joined["p"] <= thr]
    detail["tail_days"] = len(bad)
    if len(bad) < 5:
        return 0.0, detail, "worst decile holds under 5 shared days: tail unmeasured"
    mean_bad = float(bad["i"].mean())
    sd = float(joined["i"].std(ddof=1))
    detail["tail_contribution"] = round(mean_bad, 8)
    detail["tail_novelty"] = round(1.0 - abs(_corr(bad["i"], bad["p"])), 4)
    if not math.isfinite(sd) or sd <= 1e-15:
        return 0.0, detail, "candidate P&L has no dispersion: tail unmeasured"
    return float(mean_bad / sd), detail, (
        f"E[R_i | R_P <= q{int(q * 100)}] over {len(bad)} book-loss days, in candidate sigmas")


def state_breadth(state: pd.Series, forward: pd.Series, *, buckets: int = STATE_BUCKETS,
                  min_obs: int = MIN_STATE_OBS) -> tuple[float, dict[str, Any], str]:
    """Share of ADMITTED state buckets whose forward mean is positive.

    A bucket is admitted only with `min_obs` observations, because a bucket of eight has a
    positive mean about half the time whatever the alpha does -- counting it would make breadth
    a measure of how finely the state was sliced. An edge that lives in one bucket is one
    regime away from being over, and this is the term that says so before the money finds out.
    """
    detail: dict[str, Any] = {"buckets": 0, "admitted": 0, "positive": 0}
    j = pd.concat([pd.Series(state).rename("s"), pd.Series(forward).rename("f")],
                  axis=1, join="inner").dropna()
    if len(j) < min_obs * 2:
        return 0.0, detail, f"under {min_obs * 2} joint observations: state breadth unmeasured"
    try:
        labels = pd.qcut(j["s"], int(buckets), labels=False, duplicates="drop")
    except ValueError:
        return 0.0, detail, "state has no dispersion to bucket: breadth unmeasured"
    admitted = positive = 0
    for _label, grp in j.groupby(labels):
        detail["buckets"] += 1
        if len(grp) < min_obs:
            continue
        admitted += 1
        positive += int(float(grp["f"].mean()) > 0.0)
    detail["admitted"], detail["positive"] = admitted, positive
    if not admitted:
        return 0.0, detail, f"no bucket reached {min_obs} observations: breadth unmeasured"
    return positive / admitted, detail, f"{positive}/{admitted} admitted state buckets pay"


def capacity_term(spread_frac: float | None, activity: float | None) -> tuple[float, str]:
    """A spread x depth PROXY in [0, 1]: how much of this edge the desk could actually size into.

    Both halves are proxies and are named as such. Spread is real (the broker quotes it) and
    scores `REF / (REF + spread)`, which is 1 at no spread and 0.5 at the reference. Depth is
    NOT real: this feed publishes tick counts rather than traded contracts, so activity stands
    in for depth and is scored as a share of `TICKS_REF`, capped at 1. Neither half available
    means capacity is unmeasured, not full -- an unmeasured capacity has sunk more desks than a
    measured small one.
    """
    parts: list[str] = []
    score = 1.0
    if isinstance(spread_frac, (int, float)) and math.isfinite(float(spread_frac)) \
            and float(spread_frac) >= 0:
        s = CAPACITY_SPREAD_REF / (CAPACITY_SPREAD_REF + float(spread_frac))
        score *= s
        parts.append(f"spread {float(spread_frac):.2e} -> {s:.3f}")
    if isinstance(activity, (int, float)) and math.isfinite(float(activity)) \
            and float(activity) > 0:
        d = min(1.0, float(activity) / CAPACITY_TICKS_REF)
        score *= d
        parts.append(f"ticks/bar {float(activity):.0f} -> {d:.3f}")
    if not parts:
        return 0.0, "no spread and no activity: capacity unmeasured"
    return float(score), "capacity proxy: " + " x ".join(parts)


def cost_term(cost_frac: float | None, gross_per_trade: float | None,
              symbol: str = "") -> tuple[float, str]:
    """The round trip as a multiple of the gross edge it has to come out of.

    Charged on the DESK'S OWN cost model: the caller passes the `cost_frac` its screen already
    computed from `mt5desk.engine.Costs` (via `proposer_common.cost_frac`, the corrected model
    `external_gauntlet.costs_for` also constructs), and this only prices it against the edge.
    A cell whose gross edge is twice its round trip scores 0.5; one that barely covers it scores
    1.0; one that does not cover it scores above 1.0 and is meant to. Capped at 3 so a
    near-zero gross edge cannot dominate every other term with an arbitrarily large number.
    """
    if not isinstance(cost_frac, (int, float)) or not math.isfinite(float(cost_frac)):
        return 0.0, f"no cost model for {symbol or 'this cell'}: cost unmeasured"
    if not isinstance(gross_per_trade, (int, float)) or not math.isfinite(
            float(gross_per_trade)) or abs(float(gross_per_trade)) <= 1e-12:
        return 3.0, "gross edge is zero: the round trip is unpayable at any cost"
    return float(min(3.0, abs(float(cost_frac)) / abs(float(gross_per_trade)))), (
        f"round trip {float(cost_frac):.2e} against gross {float(gross_per_trade):.2e}")


def fragility(score_fn: Callable[[Mapping[str, Any]], float], params: Mapping[str, Any], *,
              pct: float = FRAGILITY_PCT) -> tuple[float, dict[str, Any], str]:
    """Mean relative score LOSS when each numeric parameter is moved +-`pct`.

    A cell that only works at one setting was fitted to the noise between settings, and the
    forward sample will not reproduce that setting. Only losses count: a perturbation that
    happens to score BETTER says the search under-optimised, not that the cell is robust, and
    averaging the gain in would let a lucky neighbour hide a knife edge on the other side.
    """
    detail: dict[str, Any] = {"perturbed": 0, "worst": None, "worst_param": None}
    try:
        base = float(score_fn(dict(params)))
    except Exception as exc:
        return 0.0, detail, f"base score unavailable ({type(exc).__name__}): fragility unmeasured"
    numeric = [k for k, v in params.items()
               if isinstance(v, (int, float)) and not isinstance(v, bool) and float(v) != 0.0]
    if not numeric or not math.isfinite(base) or abs(base) <= 1e-12:
        return 0.0, detail, "no perturbable numeric parameter or a zero base: unmeasured"
    losses: list[float] = []
    for k in numeric:
        for direction in (1.0 - pct, 1.0 + pct):
            moved = dict(params)
            v = params[k]
            moved[k] = round(float(v) * direction) if isinstance(v, int) else \
                float(v) * direction
            if moved[k] == v:
                continue
            try:
                got = float(score_fn(moved))
            except Exception:
                continue
            if not math.isfinite(got):
                continue
            loss = max(0.0, (base - got) / abs(base))
            losses.append(loss)
            detail["perturbed"] = int(detail["perturbed"]) + 1
            if detail["worst"] is None or loss > float(detail["worst"]):
                detail["worst"], detail["worst_param"] = round(loss, 4), k
    if not losses:
        return 0.0, detail, "no perturbation produced a finite score: fragility unmeasured"
    return float(np.mean(losses)), detail, (
        f"mean relative loss over {len(losses)} perturbations at +-{pct:.0%}")


def multiplicity_term(n_trials: int, *, sharpes: Sequence[float] | None = None,
                      variance_of_sharpes: float | None = None) -> tuple[float, str]:
    """The deflated-Sharpe hurdle the gauntlet will charge: `E[max Sharpe over N trials]`.

    THE SAME DEFLATION, FROM THE SAME MODULE. `libs.validation.dsr.expected_max_sharpe` is what
    `external_gauntlet`'s `deflated_sharpe` stage raises its benchmark to, so a candidate that
    the search prefers because it came out of a wider haystack is charged HERE for the width of
    that haystack, in the same units and by the same function that will charge it later. The
    variance of Sharpes is the desk's declared constant when `gate_policy` is readable and the
    measured batch dispersion otherwise -- the gauntlet's own order of preference.
    """
    n = max(1, int(n_trials))
    var = variance_of_sharpes
    basis = "given variance_of_sharpes"
    if var is None:
        try:
            from research.gate_policy import (  # type: ignore[import-not-found]
                FIXED_VARIANCE_OF_SHARPES,
            )
            if isinstance(FIXED_VARIANCE_OF_SHARPES, (int, float)) \
                    and float(FIXED_VARIANCE_OF_SHARPES) > 0:
                var, basis = float(FIXED_VARIANCE_OF_SHARPES), "gate_policy fixed variance"
        except Exception:
            var = None
    if var is None:
        arr = _finite(np.asarray(list(sharpes or []), dtype=float))
        if arr.size > 1:
            var, basis = float(arr.var(ddof=1)), "measured batch dispersion"
    if var is None or not math.isfinite(var) or var <= 0:
        return 0.0, f"no variance of Sharpes for {n} trials: multiplicity unmeasured"
    try:
        from libs.validation.dsr import expected_max_sharpe
        hurdle = float(expected_max_sharpe(n, var))
    except Exception as exc:
        return 0.0, f"expected_max_sharpe unavailable ({type(exc).__name__}): unmeasured"
    return hurdle, f"E[max Sharpe | {n} trials, var={var:.6f}] ({basis})"


# --------------------------------------------------------------------------- the vector
@dataclass(frozen=True)
class FitnessTerms:
    """Every term of the fitness, with what could not be measured named rather than zeroed."""

    delta_elog: float = 0.0
    oos: float = 0.0
    novelty: float = 0.0
    tail: float = 0.0
    state_breadth: float = 0.0
    capacity: float = 0.0
    cost: float = 0.0
    fragility: float = 0.0
    complexity: float = 0.0
    multiplicity: float = 0.0
    #: Term name -> why it is what it is. Every term has one, measured or not.
    why: dict[str, str] = field(default_factory=dict)
    #: Terms that could NOT be measured and are therefore 0.0 by absence, not by measurement.
    unmeasured: tuple[str, ...] = ()
    #: Raw readings a human wants beside the score (tail contribution, admitted buckets, ...).
    detail: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, float]:
        return {k: float(getattr(self, k)) for k in WEIGHTS}

    def score(self, weights: Mapping[str, float] | None = None) -> float:
        return score(self, weights)

    def objectives(self, weights: Mapping[str, float] | None = None) -> dict[str, float]:
        """Each term SIGNED as a thing to maximise -- what a multi-objective sort ranks on.

        The scalar `score` is a declared exchange rate between these; NSGA-II needs them apart,
        because a candidate that is best on the tail and worst on cost is not dominated by one
        that is mediocre at both, and collapsing them first hides exactly that candidate.
        """
        w = dict(WEIGHTS if weights is None else weights)
        return {k: (-1.0 if k in PENALTIES else 1.0) * float(w.get(k, 0.0)) * v
                for k, v in self.as_dict().items()}


def score(terms: FitnessTerms, weights: Mapping[str, float] | None = None) -> float:
    """The weighted sum, credits positive and `PENALTIES` negative. Non-finite terms are 0."""
    w = dict(WEIGHTS if weights is None else weights)
    total = 0.0
    for name, value in terms.as_dict().items():
        if not math.isfinite(value):
            continue
        total += (-1.0 if name in PENALTIES else 1.0) * float(w.get(name, 0.0)) * value
    return float(total)


@dataclass(frozen=True)
class Candidate:
    """Everything the fitness needs about one alpha. Absent fields make terms UNMEASURED."""

    daily: pd.Series                       # the candidate's own daily P&L, in R
    name: str = "candidate"
    symbol: str = ""
    z: pd.Series | None = None             # its normalised signal, for novelty and state breadth
    forward: pd.Series | None = None       # forward return per bar, for state breadth
    refs: tuple[pd.Series, ...] = ()       # canon and population series to be novel against
    complexity: int = 0
    cost_frac: float | None = None
    gross_per_trade: float | None = None
    spread_frac: float | None = None
    activity: float | None = None
    n_trials: int = 1
    sharpes: tuple[float, ...] = ()
    params: Mapping[str, Any] = field(default_factory=dict)
    score_fn: Callable[[Mapping[str, Any]], float] | None = None


def evaluate(candidate: Candidate, book: Book | None = None, *, cfg: Any = None,
             weights: Mapping[str, float] | None = None) -> FitnessTerms:
    """Every term for one candidate against one book. Never raises; absence is named.

    ORDER MATTERS ONLY FOR COST: `delta_elog` re-solves the book twice and is the expensive
    term, so a caller scoring a whole generation should evaluate cheaply first and reserve this
    for the survivors -- see `libs.research.search_populations`, which does exactly that.
    """
    bk = book if book is not None else Book()
    why: dict[str, str] = {}
    detail: dict[str, Any] = {}
    unmeasured: list[str] = []

    def _take(name: str, value: float, reason: str) -> float:
        why[name] = reason
        if "unmeasured" in reason or "refused" in reason:
            unmeasured.append(name)
        return value

    d_elog = _take("delta_elog", *delta_elog_term(bk, candidate.daily, name=candidate.name,
                                                  cfg=cfg))
    oos = _take("oos", *oos_term(candidate.daily))
    nov = _take("novelty", *novelty_term(candidate.z if candidate.z is not None
                                         else candidate.daily, candidate.refs))
    tail_value, tail_detail, tail_why = tail_term(candidate.daily, bk.daily)
    detail["tail"] = tail_detail
    tail = _take("tail", tail_value, tail_why)
    if candidate.z is not None and candidate.forward is not None:
        sb_value, sb_detail, sb_why = state_breadth(candidate.z, candidate.forward)
    else:
        sb_value, sb_detail, sb_why = 0.0, {}, "no state series or forward return: unmeasured"
    detail["state_breadth"] = sb_detail
    breadth = _take("state_breadth", sb_value, sb_why)
    cap = _take("capacity", *capacity_term(candidate.spread_frac, candidate.activity))
    cost = _take("cost", *cost_term(candidate.cost_frac, candidate.gross_per_trade,
                                    candidate.symbol))
    if candidate.score_fn is not None and candidate.params:
        fr_value, fr_detail, fr_why = fragility(candidate.score_fn, candidate.params)
    else:
        fr_value, fr_detail, fr_why = 0.0, {}, "no re-scoring function: fragility unmeasured"
    detail["fragility"] = fr_detail
    frag = _take("fragility", fr_value, fr_why)
    cx = _take("complexity", float(max(0, int(candidate.complexity))),
               f"{int(candidate.complexity)} nodes")
    mult = _take("multiplicity", *multiplicity_term(candidate.n_trials,
                                                    sharpes=candidate.sharpes))
    terms = FitnessTerms(delta_elog=d_elog, oos=oos, novelty=nov, tail=tail,
                         state_breadth=breadth, capacity=cap, cost=cost, fragility=frag,
                         complexity=cx, multiplicity=mult, why=why,
                         unmeasured=tuple(sorted(set(unmeasured))), detail=detail)
    detail["score"] = round(score(terms, weights), 6)
    detail["book"] = bk.source
    return terms


# --------------------------------------------------------------------------- multi-objective
def non_dominated_sort(rows: Sequence[Mapping[str, float]]) -> list[list[int]]:
    """NSGA-II's fronts over objective dicts to be MAXIMISED. Front 0 is the Pareto set.

    Written out rather than imported because the objectives here are a handful of terms over a
    few dozen candidates: the whole sort is microseconds, and a dependency for it would be a
    dependency on the money path.
    """
    n = len(rows)
    keys = sorted({k for r in rows for k in r})
    dominated: list[list[int]] = [[] for _ in range(n)]
    count = [0] * n
    fronts: list[list[int]] = [[]]
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            if _dominates(rows[i], rows[j], keys):
                dominated[i].append(j)
            elif _dominates(rows[j], rows[i], keys):
                count[i] += 1
        if count[i] == 0:
            fronts[0].append(i)
    k = 0
    while fronts[k]:
        nxt: list[int] = []
        for i in fronts[k]:
            for j in dominated[i]:
                count[j] -= 1
                if count[j] == 0:
                    nxt.append(j)
        k += 1
        fronts.append(nxt)
    return [f for f in fronts if f]


def _dominates(a: Mapping[str, float], b: Mapping[str, float], keys: Sequence[str]) -> bool:
    better = False
    for k in keys:
        av, bv = float(a.get(k, 0.0)), float(b.get(k, 0.0))
        if av < bv:
            return False
        if av > bv:
            better = True
    return better


def crowding_distance(rows: Sequence[Mapping[str, float]], front: Sequence[int]
                      ) -> dict[int, float]:
    """NSGA-II crowding distance within one front: the spread each member keeps alive.

    The extremes on every objective are infinitely crowded-out-proof on purpose -- losing the
    best tail contributor because it sits alone is exactly the failure this ordering exists to
    prevent.
    """
    dist = dict.fromkeys(front, 0.0)
    if len(front) <= 2:
        return dict.fromkeys(front, math.inf)
    keys = sorted({k for r in rows for k in r})
    for k in keys:
        order = sorted(front, key=lambda i: float(rows[i].get(k, 0.0)))
        lo = float(rows[order[0]].get(k, 0.0))
        hi = float(rows[order[-1]].get(k, 0.0))
        dist[order[0]] = dist[order[-1]] = math.inf
        if hi - lo <= 1e-15:
            continue
        for pos in range(1, len(order) - 1):
            nxt = float(rows[order[pos + 1]].get(k, 0.0))
            prev = float(rows[order[pos - 1]].get(k, 0.0))
            if math.isfinite(dist[order[pos]]):
                dist[order[pos]] += (nxt - prev) / (hi - lo)
    return dist


def nsga2_order(terms: Sequence[FitnessTerms],
                weights: Mapping[str, float] | None = None) -> list[int]:
    """Indices best-first by NSGA-II: Pareto front, then crowding distance inside each front."""
    rows = [t.objectives(weights) for t in terms]
    out: list[int] = []
    for front in non_dominated_sort(rows):
        dist = crowding_distance(rows, front)
        out.extend(sorted(front, key=lambda i: -dist[i]))
    return out
