"""HOW MANY INDEPENDENT BETS IS THE CRYPTO CROSS-SECTION -- once the market factor is removed.

WHY THIS ONE NUMBER GATES EVERY CROSS-SECTIONAL MECHANISM THIS DESK WILL EVER BUILD.
`libs/research/alpha_economics.py` treats `narrow_breadth` (breadth < ~5) as HALF OF A HARD KILL:
`price_only AND narrow_breadth` returns REJECT *regardless of the EV arithmetic*. `breadth` in
that file is documented as "number of independent bets/assets the signal spans" -- i.e. N_eff,
not the symbol count. Nobody had ever measured what the crypto cross-section's N_eff actually is.
Below 5 and `narrow_breadth` would be a permanent property of THE VENUE rather than of any one
idea, and every cross-sectional mechanism this desk screens would be hard-killed by its own EV
gate before a backtest ran. Devastating finding, or reprieve. Measured now, on real bars.

MEASURED 2026-08-01 -- 28 crypto-native USDT perps x 498 confirmed daily bars (OKX, ~16 months):

    raw log-return correlation        mean +0.682   -> N_eff  1.5     (what everyone already knows)
    residual, market factor removed   mean -0.033   -> N_eff 20.4     (the actual answer)

IT IS A REPRIEVE. 20.4 clears the narrow_breadth line of 5 by a factor of four, so the crypto
cross-section is NOT structurally hard-killed and cross-sectional mechanisms remain screenable.
But the nominal count of 28 is still an illusion: the honest IR multiplier is sqrt(20.4) = 4.5,
not sqrt(28) = 5.3, so budgeting breadth off the symbol count overstates the IR ceiling by 17%.
That is a mild tax, and it is emphatically NOT where the desk's problem is.

THE FINDING THAT ALMOST WENT THE OTHER WAY, AND IT IS THE MOST IMPORTANT THING IN THIS FILE.
Regress each perp on BTC -- the obvious choice, the one every crypto desk reaches for first --
and the same panel reports mean residual correlation +0.412 and N_eff 2.31. That FIRES
narrow_breadth, and it would have concluded that this desk's entire cross-sectional research
programme is dead on arrival. It is an artifact. Proof, and it is the reason the synthetic-panel
machinery in this file exists: build a one-factor panel at THIS panel's measured betas and vols
whose idiosyncratic parts are INDEPENDENT BY CONSTRUCTION (true residual correlation exactly 0),
and the single-asset-proxy estimator reports mean residual correlation +0.472 and N_eff 2.04 --
i.e. it returns the "hard kill" answer, slightly MORE emphatically, on data with no residual
structure whatsoever. Whatever that estimator is measuring, it is not the market. The mechanism
is errors-in-variables: BTC is the factor PLUS BTC's own idiosyncratic return, so regressing on
it injects -beta_i * e_BTC into every residual, and those injected terms are perfectly correlated
across names. The equal-weight cross-sectional mean averages 27 idiosyncratic components down by
1/27 before they can contaminate anything, which is why it is the factor used here.

A NUMBER WITH NO FLOOR IS NOT A MEASUREMENT, and residual correlations have a floor that is pure
arithmetic. Removing a cross-sectional factor forces the residuals to sum to ~0 at every date,
which pins mean pairwise correlation near -1/(N-1) -- `cohort_independence.demeaning_floor()`,
-0.037 at N=28 -- with no structure present whatsoever. Verified on the synthetic one-factor
panel: measured -0.034 against a floor of -0.037, i.e. the estimator correctly reports "nothing
here". The real panel reads -0.033, only +0.0045 above its floor. So the equicorrelation N_eff
pins at its own ceiling of N (28.0) and can say only "no measurable UNIFORM redundancy survives
the market factor" -- true, and not the whole truth, because a matrix of offsetting clusters has
a mean correlation of zero while being nothing like independent.

SO THE HEADLINE USES THE ESTIMATOR THAT CAN SEE CLUSTERS, calibrated against the same null.
`cohort_independence`'s docstring invites exactly this cross-check and warns that the
participation ratio's "absolute value is unreadable" without knowing its floor -- so the floor is
measured rather than assumed. Participation ratio on the residual matrix: 18.73. On the
independent-idiosyncratic null at the same T, N, betas and vols: 25.62 (note: NOT 28 -- fitting
28 betas burns real degrees of freedom, and an uncalibrated PR would have booked that loss as
crypto being less diversified than it is). Calibrated breadth 18.73/25.62 * 28 = 20.47, the
headline. Three residual eigenvalues sit above the Marchenko-Pastur noise edge of 1.53, and the
top residual eigenvector loads positively on BTC/ETH/SOL/XRP and negatively on FIL/TIA/OP/NEAR --
a majors-versus-alts dispersion factor, economically legible rather than a statistical curiosity.

MEASURED AND REJECTED, recorded so nobody re-derives it: 1'C^-1 1, the exact generalisation of
the equicorrelation formula (it reproduces N/(1+(N-1)rho) identically under equicorrelation and
is the true Grinold breadth of an equal-alpha portfolio). It returns 1642 on the real residual
matrix and 1556 on the null -- both nonsense, because the smallest sample eigenvalue is 0.016 and
inverting a correlation matrix through it amplifies estimation noise without bound. Right
formula, wrong estimator at this sample size; it needs shrinkage before it is usable, and the
null is what proves the number is noise rather than a finding.

WHAT IR 1.0 ACTUALLY COSTS HERE, and it reframes the desk's search. Grinold: IR = IC*sqrt(BR).
On the cross-section alone, IR 1.0 needs IC = 1/sqrt(20.47) = 0.221. This desk's BEST-EVER
MEASURED IC IS +0.06 (options VRP, docs/institutional_knowledge.md) -- 3.7x short. No achievable
universe width closes that: even 100 perfectly independent perps would need IC 0.10, still 1.7x
beyond anything ever measured here. The multiplier has to come from BETS PER YEAR, which is a
statement about how fast a signal decorrelates from itself, not about how many symbols it spans.
At 12 independent rebalances a year IC 0.06 gives IR 0.94; at 52, IR 1.96. THE BINDING CONSTRAINT
IS SIGNAL HALF-LIFE, NOT BREADTH -- and this measurement is what licenses the desk to stop
widening universes and start measuring decay (scripts/signal_halflife.py).

WHAT THE EV GATE SAYS AT THE MEASURED BREADTH, since that was the question. `narrow_breadth` does
NOT fire, so the price_only hard kill does not trigger. The generic price-only cross-sectional
idea still scores REJECT -- but on EV arithmetic (ev 0.0014 against a 0.002 threshold), which is
a SOFT and escapable rejection: a better-evidenced est_sharpe, a genuinely orthogonal data axis,
or lower effort moves it. That distinction is the whole finding. A hard kill is a closed door; an
EV rejection is a price. The crypto cross-section is expensive, not forbidden.

NO MARKET DATA IS EVER FABRICATED HERE. If no panel is on disk and `--fetch` is not passed, this
writes a BLOCKED report naming the exact missing input and exits NONZERO. It never falls back to
simulation and there is no flag that makes it. The synthetic panels above are not an exception
and the distinction is the whole point: they CALIBRATE AN ESTIMATOR'S FLOOR on data whose true
answer is known by construction, and they are never a substitute for the market. Simulating a
null to learn what an estimator reports when nothing is there is measurement; simulating a market
to learn what the market is doing is invention, and it would have answered the desk's gating
question with a number that felt earned and was not.

    python3 scripts/measure_cross_section_breadth.py --fetch     # populate the cache, measure
    python3 scripts/measure_cross_section_breadth.py             # measure from cache/lake only
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:                       # runnable as `python3 scripts/...` from root
    sys.path.insert(0, str(ROOT))

from libs.research.alpha_economics import Idea, ev_score  # noqa: E402
from libs.research.cohort_independence import demeaning_floor, measure  # noqa: E402

CACHE = ROOT / "data" / "perp_close_panel.json"
LAKE = ROOT / "data" / "lake"
OUT = ROOT / "reports" / "cross_section_breadth.json"

#: The universe is FROZEN IN SOURCE, not ranked live, and that is a bias fix rather than laziness.
#: W-21 (docs/research/deep_sweep/20260726_validation-stats.md) recorded two survivorship defects
#: in this desk's existing universe selection: ranking by END-OF-SAMPLE liquidity then serving the
#: whole history, and applying a single live 24h volume snapshot to years of bars. Both select for
#: names that appreciated across the sample. Here the names come from the desk's OWN declared
#: crypto universes -- scripts/run_recorder.py `_CORE` (20 majors) plus the crypto-native L1/DeFi
#: names in scripts/build_dev_factor.py -- so the list is fixed before any price is seen.
#:
#: EXCLUDED ON PURPOSE: OKX's top-by-dollar-volume SWAP list is now dominated by TOKENISED
#: EQUITIES and commodities (SNDK, MU, SKHYNIX, SOXL, SPCX, XAU, CL -- seven of its top twenty on
#: 2026-08-01). Those are not crypto perps. Including them would have INFLATED measured breadth
#: with instruments carrying no BTC beta at all, answering a question about the crypto
#: cross-section with the equity cross-section. A naive "top-30 by volume" fetch is the single
#: easiest way to get a wrong and flattering answer here.
UNIVERSE: tuple[str, ...] = (
    "BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "ADA", "AVAX", "LINK", "LTC",
    "TRX", "DOT", "BCH", "NEAR", "SUI", "UNI", "APT", "FIL", "ARB", "OP",
    "ATOM", "AAVE", "LDO", "MKR", "INJ", "TIA", "XLM", "ETC", "ZEC", "XTZ",
)

#: Below this many usable symbols or observations the answer is not measurable and the run BLOCKS.
#: Deliberately NOT "best effort on whatever survived": a breadth number computed on 4 names is
#: not a small version of this finding, it is a different and unasked question -- and it would be
#: read as the finding anyway.
_MIN_SYMBOLS = 8
_MIN_OBS = 120

#: A symbol must cover at least this fraction of the longest available history to enter the panel.
#: The alignment is an INNER JOIN (see `_aligned_panel`), so one late listing truncates every
#: other series to its own start date. Measured cost on 2026-08-01: keeping ZEC (268 confirmed
#: bars against the panel's 499) would have cost 231 of 498 observations -- 46% of the sample --
#: to add 1 name of 29, dropping T/N from 17.8 to 9.2. The trade is not close. Recorded bias
#: direction: this drops RECENTLY LISTED names, which tend to be higher-beta and more
#: idiosyncratic, so it if anything UNDERSTATES breadth. Conservative for the question asked.
_MIN_COVERAGE = 0.75

#: Days of trailing history used to fit the first beta in the trailing-residual variant.
_BETA_WARMUP = 120

#: The narrow_breadth line from libs/research/alpha_economics.py (`breadth < ~5` -> 0.25x prior,
#: and a hard kill when paired with price_only). A NUMBER here because the library encodes it as
#: a comment on a prior rather than as a constant; the gate itself is imported and called, never
#: paraphrased, so this constant cannot silently drift away from the verdict it reports.
NARROW_BREADTH_LINE = 5.0

#: Best information coefficient this desk has ever MEASURED (options VRP, +0.06 at breadth 2 --
#: docs/institutional_knowledge.md). Every required-IC figure is compared to this and never to a
#: textbook 0.05, because the textbook number was not earned here.
DESK_BEST_IC = 0.06

#: Return standard deviation below which a symbol's feed is treated as DEAD rather than quiet.
#: A `> 0` variance guard does not survive floating-point dust: on a frozen feed numpy returns
#: ~5e-38 for the variance of a constant series, which passes `> 0`, and that exact hole shipped a
#: 1.4e31 prediction premium here on 2026-08-01 (libs/research/volatility_signals._VAR_FLOOR).
#: A pegged pair, a delisted alt or a halted market lands in this branch. A dead column left in
#: the panel reads as the most DIVERSIFYING name in the cross-section -- it correlates with
#: nothing because it does nothing -- so the failure mode is manufactured breadth, which is
#: precisely the lie this script exists to avoid. 1e-6 in daily return sd is 0.0001%/day: far
#: below any real perp's quietest regime, far above float dust.
_RET_SD_FLOOR = 1e-6

#: Draws used to calibrate an estimator's floor on a known-answer null. Fixed seed: the report is
#: an artifact other code reads, and a headline that moves when nothing moved is not a headline.
_NULL_DRAWS = 25
_NULL_SEED = 20260801

_OKX = "https://www.okx.com"
_OKX_SUFFIX = "-USDT-SWAP"
_PAGE = 100
_REQ_SLEEP = 0.12       # OKX history-candles allows 20 req / 2s per IP; this sits under half.


@dataclass(frozen=True)
class Panel:
    """An aligned daily close panel. `closes` is (observations x symbols), oldest row first."""

    symbols: tuple[str, ...]
    timestamps: np.ndarray          # int64 epoch ms, ascending, one per row
    closes: np.ndarray              # (T x N) float64
    source: str
    fetched_utc: str
    dropped_short: tuple[str, ...] = ()


# --------------------------------------------------------------------------------------------
# Loading. Disk first, always. Network only on an explicit flag. Never synthetic.
# --------------------------------------------------------------------------------------------

def _aligned_panel(bars: dict[str, dict[str, list[float]]], source: str,
                   fetched_utc: str, *, min_coverage: float = _MIN_COVERAGE) -> Panel | None:
    """Inner-join per-symbol bar series on their timestamps, after a coverage screen.

    INNER JOIN, NEVER FORWARD-FILL. A forward-filled close repeats yesterday's price, which is a
    zero return, which DEPRESSES that symbol's correlation with everything and inflates breadth --
    the same manufactured-diversification failure as a dead feed arriving through a different
    door. Short histories are dropped by the coverage screen and recorded, never padded.
    """
    long_enough = {s: b for s, b in bars.items() if len(b.get("t", [])) >= _MIN_OBS}
    if len(long_enough) < _MIN_SYMBOLS:
        return None
    longest = max(len(b["t"]) for b in long_enough.values())
    usable = {s: b for s, b in long_enough.items()
              if len(b["t"]) >= min_coverage * longest}
    dropped_short = tuple(sorted(set(long_enough) - set(usable)))
    if len(usable) < _MIN_SYMBOLS:
        return None
    common: set[int] | None = None
    for b in usable.values():
        ts = {int(t) for t in b["t"]}
        common = ts if common is None else (common & ts)
    if not common or len(common) < _MIN_OBS:
        return None
    index = np.array(sorted(common), dtype="int64")
    syms = tuple(sorted(usable))
    cols = []
    for s in syms:
        by_ts = {int(t): float(c) for t, c in zip(usable[s]["t"], usable[s]["close"], strict=True)}
        cols.append(np.array([by_ts[int(t)] for t in index], dtype="float64"))
    return Panel(syms, index, np.column_stack(cols), source, fetched_utc, dropped_short)


def load_cache(path: Path = CACHE) -> Panel | None:
    """Read the on-disk close panel written by a previous `--fetch`. None if absent/unreadable."""
    try:
        raw = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None
    bars = raw.get("bars")
    if not isinstance(bars, dict) or not bars:
        return None
    return _aligned_panel(bars, str(raw.get("source", f"cache:{path}")),
                          str(raw.get("fetched_utc", "unknown")))


def load_lake(lake_root: Path = LAKE) -> Panel | None:
    """Read D1 crypto closes from the desk's Parquet lake, if one exists on this box.

    Imported lazily: `libs.data.lake` pulls in pandas/pyarrow, and this script must still run --
    and still BLOCK correctly -- on a box where the lake was never built. A missing lake is a
    MISSING INPUT, not a crash, and it must not be able to take down the blocked-report path.
    """
    root = lake_root / "bronze" / "crypto"
    if not root.exists():
        return None
    try:
        from libs.data.lake import Layer, ParquetLake
        from libs.data.timeframe import Timeframe
    except ImportError:
        return None
    lake = ParquetLake(str(lake_root))
    bars: dict[str, dict[str, list[float]]] = {}
    for base in UNIVERSE:
        sym = f"{base}USDT"
        if not (root / sym / Timeframe.D1.value).exists():
            continue
        try:
            frame = lake.read_bars(Layer.BRONZE, sym, Timeframe.D1)
        except Exception:
            continue
        bars[base] = {"t": [float(int(v.value // 1_000_000)) for v in frame["timestamp"]],
                      "close": [float(c) for c in frame["close"]]}
    if not bars:
        return None
    return _aligned_panel(bars, f"lake:{lake_root}", "on-disk")


def _okx_get(url: str, *, tries: int = 3) -> list[list[str]]:
    last: Exception | None = None
    for _ in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "quant-platform/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = json.loads(resp.read())
            if str(body.get("code")) != "0":
                raise RuntimeError(f"okx code={body.get('code')} msg={body.get('msg')}")
            return [[str(f) for f in row] for row in (body.get("data") or [])]
        except (urllib.error.URLError, ValueError, RuntimeError) as exc:
            last = exc
            time.sleep(1.0)
    raise RuntimeError(f"okx GET failed after {tries}: {url} :: {last}")


def fetch_okx(days: int, *, universe: tuple[str, ...] = UNIVERSE) -> dict[str, Any]:
    """Daily CONFIRMED perp candles from OKX. Returns the raw cache document.

    OKX rather than Binance because on 2026-08-01 `fapi.binance.com` answers HTTP 451 from this
    box (geo-block) and `api.bybit.com` is CloudFront-blocked -- neither is a data gap to work
    around, both are hard refusals, and both are named in the BLOCKED report so the next reader
    does not repeat the diagnosis. OKX serves the same instrument class (`BASE-USDT-SWAP`
    perpetuals) and is already the desk's third funding venue in libs/data/multiexchange.py.

    ONLY confirm=="1" ROWS ARE KEPT. OKX's newest daily row is the IN-PROGRESS bar: its "close"
    is the current price, not a close. Keeping it would put a partial bar at the panel's edge for
    every symbol SIMULTANEOUSLY -- one extra row of pure synchronised common factor, biasing
    correlation up and breadth down. Verified present in the live feed: the first row of every
    page carried confirm=="0".
    """
    pages = max(1, -(-days // _PAGE))
    bars: dict[str, dict[str, list[float]]] = {}
    dropped: dict[str, str] = {}
    for base in universe:
        inst = f"{base}{_OKX_SUFFIX}"
        rows: list[list[str]] = []
        cursor = ""
        try:
            for _ in range(pages):
                page = _okx_get(f"{_OKX}/api/v5/market/history-candles?instId={inst}"
                                f"&bar=1D&limit={_PAGE}{cursor}")
                if not page:
                    break
                rows.extend(page)
                cursor = f"&after={page[-1][0]}"
                time.sleep(_REQ_SLEEP)
        except RuntimeError as exc:
            dropped[base] = str(exc)
            continue
        good = [r for r in rows if len(r) >= 9 and r[8] == "1"]
        if len(good) < _MIN_OBS:
            dropped[base] = f"only {len(good)} confirmed daily bars (need {_MIN_OBS})"
            continue
        good.sort(key=lambda r: int(r[0]))
        bars[base] = {"t": [float(int(r[0])) for r in good],
                      "close": [float(r[4]) for r in good],
                      "quote_volume": [float(r[7]) for r in good]}
    return {"source": "okx:history-candles:1D:confirmed",
            "instrument": f"BASE{_OKX_SUFFIX}",
            "fetched_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "declared_universe": list(universe),
            "dropped": dropped,
            "bars": bars}


# --------------------------------------------------------------------------------------------
# Residualisation.
# --------------------------------------------------------------------------------------------

def log_returns(closes: np.ndarray) -> np.ndarray:
    """(T-1 x N) log returns. Log so the market factor is additive across the panel."""
    c = np.asarray(closes, dtype="float64")
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.diff(np.log(np.where(c > 0.0, c, np.nan)), axis=0)
    return np.asarray(out, dtype="float64")


def live_columns(returns: np.ndarray) -> np.ndarray:
    """Columns that are finite everywhere AND actually move. See `_RET_SD_FLOOR`.

    The dangerous column here is not the noisy one, it is the DEAD one: a frozen feed correlates
    with nothing and would be counted as the panel's best diversifier.
    """
    r = np.asarray(returns, dtype="float64")
    finite = np.isfinite(r).all(axis=0)
    moves = np.zeros(r.shape[1], dtype=bool)
    if r.shape[0] > 1:
        with np.errstate(invalid="ignore"):
            sd = np.nanstd(np.where(np.isfinite(r), r, np.nan), axis=0)
        moves = np.asarray(np.isfinite(sd) & (sd > _RET_SD_FLOOR))
    return np.asarray(finite & moves)


def leave_one_out_market(returns: np.ndarray) -> np.ndarray:
    """(T x N) -- column i is the equal-weight mean return of every symbol EXCEPT i.

    Excluding a symbol from its own regressor is a correctness fix, not a refinement: an
    all-inclusive mean gives symbol i weight 1/N in its own factor, so part of i's idiosyncratic
    return is subtracted from every other name's regressor. The exclusion costs nothing and
    removes the one term that is unambiguously an artifact.

    WHAT IT DOES NOT FIX, stated because the first version of this file claimed it did: the
    residuals still sum to ~0 across names at each date whenever betas are near 1, so mean
    pairwise residual correlation is still pinned near `demeaning_floor(N)`. That floor is
    arithmetic, applies to any cross-sectional factor removal, and is reported alongside every
    residual correlation rather than being mistaken for diversification.
    """
    r = np.asarray(returns, dtype="float64")
    n = r.shape[1]
    if n < 2:
        return np.zeros_like(r)
    total = r.sum(axis=1, keepdims=True)
    return np.asarray((total - r) / float(n - 1))


def _beta(x: np.ndarray, y: np.ndarray) -> tuple[float, float, float]:
    """OLS slope of y on x with an intercept. Returns (beta, mean_x, mean_y)."""
    xm, ym = float(np.mean(x)), float(np.mean(y))
    xc = x - xm
    denom = float(np.dot(xc, xc))
    if denom <= 0.0:
        return 0.0, xm, ym
    return float(np.dot(xc, y - ym)) / denom, xm, ym


def residualise(returns: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Full-sample market-beta residuals against the leave-one-out mean. Returns (resid, betas).

    IN-SAMPLE BY CONSTRUCTION and stated rather than hidden: the beta is fitted on the very rows
    whose residuals are then correlated, so it strips more market than any real-time hedge could
    and the resulting breadth is an UPPER BOUND. That is the right bound for "is breadth
    catastrophically narrow" -- had even the optimistic reading failed the line the finding would
    be airtight. `residualise_trailing` says how much of it a live book actually keeps.
    """
    r = np.asarray(returns, dtype="float64")
    f = leave_one_out_market(r)
    resid = np.empty_like(r)
    betas = np.empty(r.shape[1], dtype="float64")
    for i in range(r.shape[1]):
        b, xm, ym = _beta(f[:, i], r[:, i])
        betas[i] = b
        resid[:, i] = (r[:, i] - ym) - b * (f[:, i] - xm)
    return resid, betas


def residualise_single_proxy(returns: np.ndarray, k: int) -> np.ndarray:
    """Residuals against ONE asset (column k) as the factor proxy. Column k itself is dropped.

    Present so the desk can see the number it would have got from the obvious choice, next to the
    null that proves what that number means. Regressing BTC on BTC yields an identically-zero
    residual, which `measure` would drop anyway -- so the proxy silently measures N-1 names, and
    the one excluded is the one with the largest weight in the factor.
    """
    r = np.asarray(returns, dtype="float64")
    others = [i for i in range(r.shape[1]) if i != k]
    cols = []
    for i in others:
        b, xm, ym = _beta(r[:, k], r[:, i])
        cols.append((r[:, i] - ym) - b * (r[:, k] - xm))
    return np.column_stack(cols)


def residualise_trailing(returns: np.ndarray, *, warmup: int = _BETA_WARMUP) -> np.ndarray:
    """Residuals whose beta for row t is fitted on rows [0, t) ONLY. Rows < warmup are NaN.

    PREFIX INVARIANCE is the property this exists to guarantee, and it is tested: truncating the
    input must not change any earlier output. Row t's beta never sees row t or anything after it,
    so `residualise_trailing(r[:k]) == residualise_trailing(r)[:k]` exactly. This is the variant a
    live book could hold; `residualise` is the in-sample upper bound.
    """
    r = np.asarray(returns, dtype="float64")
    f = leave_one_out_market(r)
    out = np.full(r.shape, np.nan)
    if r.shape[0] <= warmup:
        return out
    for i in range(r.shape[1]):
        for t in range(warmup, r.shape[0]):
            b, xm, ym = _beta(f[:t, i], r[:t, i])
            out[t, i] = r[t, i] - (ym + b * (f[t, i] - xm))
    return out


# --------------------------------------------------------------------------------------------
# Breadth estimators, each reported against its own measured floor.
# --------------------------------------------------------------------------------------------

def participation_ratio(residuals: np.ndarray) -> float:
    """(sum lambda)^2 / sum lambda^2 of the correlation matrix -- effective eigen-directions.

    Sees CLUSTERS, which is exactly what the equicorrelation estimator cannot do: a residual
    matrix of offsetting blocks has a mean pairwise correlation of ~0 while being nothing like
    independent, and the mean-correlation route reports it as fully diversified. Its absolute
    value is not readable on its own (`cohort_independence`'s docstring says so), which is why
    `one_factor_null` measures its floor rather than assuming one.
    """
    m = np.asarray(residuals, dtype="float64")
    rows = np.isfinite(m).all(axis=1)
    m = m[rows]
    if m.shape[0] < 2 or m.shape[1] < 2:
        return float("nan")
    c = np.corrcoef(m, rowvar=False)
    ev = np.linalg.eigvalsh(np.where(np.isfinite(c), c, 0.0))
    denom = float(np.sum(ev ** 2))
    if denom <= 0.0:
        return float("nan")
    return float(np.sum(ev) ** 2 / denom)


def one_factor_null(betas: np.ndarray, market_sd: float, resid_sd: np.ndarray, n_obs: int, *,
                    draws: int = _NULL_DRAWS, seed: int = _NULL_SEED) -> dict[str, float]:
    """What each estimator reports when the residuals are INDEPENDENT BY CONSTRUCTION.

    THIS IS ESTIMATOR CALIBRATION, NOT A SUBSTITUTE FOR MARKET DATA, and the difference is the
    line this whole file is built around. Nothing here is used to answer "what is crypto's
    breadth" -- the panel answers that. These draws answer "what does this estimator print when
    the true answer is known to be N independent bets", which is the only thing that makes the
    panel's number readable. The null is parameterised by the REAL panel's own measured betas,
    market volatility and residual volatilities, so it is the same estimation problem with the
    structure removed rather than a generic textbook null.

    Returns the null's mean/sd for: leave-one-out residual correlation, its participation ratio,
    and the single-asset-proxy residual correlation and N_eff.
    """
    b = np.asarray(betas, dtype="float64")
    sd = np.asarray(resid_sd, dtype="float64")
    n = b.size
    loo_mc, loo_pr, proxy_mc, proxy_neff = [], [], [], []
    for d in range(draws):
        rng = np.random.default_rng(seed + d)
        f = rng.normal(0.0, max(market_sd, 1e-12), (n_obs, 1))
        panel = f * b.reshape(1, n) + rng.normal(0.0, 1.0, (n_obs, n)) * sd.reshape(1, n)
        resid, _ = residualise(panel)
        loo_mc.append(measure(resid).mean_corr)
        loo_pr.append(participation_ratio(resid))
        proxy = measure(residualise_single_proxy(panel, 0))
        proxy_mc.append(proxy.mean_corr)
        proxy_neff.append(proxy.n_eff)
    return {"loo_mean_corr": float(np.mean(loo_mc)), "loo_mean_corr_sd": float(np.std(loo_mc)),
            "participation_ratio": float(np.mean(loo_pr)),
            "participation_ratio_sd": float(np.std(loo_pr)),
            "single_proxy_mean_corr": float(np.mean(proxy_mc)),
            "single_proxy_mean_corr_sd": float(np.std(proxy_mc)),
            "single_proxy_n_eff": float(np.mean(proxy_neff)), "draws": float(draws)}


def expanding_breadth(residuals: np.ndarray, *, min_obs: int = _MIN_OBS) -> np.ndarray:
    """Participation ratio computed on rows [0, t] for each t. Prefix-invariant END TO END.

    FEED THIS THE TRAILING RESIDUALS, NOT THE FULL-SAMPLE ONES. The first version of this file
    passed it `residualise`'s output, whose betas are fitted on the whole sample -- so every point
    on the "trailing" path was built from a beta that had seen the end of the data. The path looked
    fine and was lookahead-contaminated, which is the failure this desk's prefix-invariance rule
    exists to catch. With `residualise_trailing` as the input, row t depends only on rows <= t at
    every stage, so truncating the panel cannot move any earlier point. Tested.

    PARTICIPATION RATIO rather than the equicorrelation N_eff because the latter pins at its
    ceiling of N as soon as residual correlation reaches the demeaning floor, which it does here
    on every window -- a flat line at 28.0 that would read as perfect stability while measuring
    nothing. Its floor drifts with T, so read the SHAPE of this path, not its level.
    """
    m = np.asarray(residuals, dtype="float64")
    out = np.full(m.shape[0], np.nan)
    for t in range(min_obs - 1, m.shape[0]):
        window = m[: t + 1]
        rows = np.isfinite(window).all(axis=1)
        if int(rows.sum()) < min_obs:
            continue
        out[t] = participation_ratio(window[rows])
    return out


def mp_structure(residuals: np.ndarray) -> dict[str, float]:
    """Marchenko-Pastur read of the residual correlation matrix -- the sampling caveat, quantified.

    Under pure noise on T observations and N series the sample correlation eigenvalues fall below
    (1 + sqrt(N/T))^2. Eigenvalues ABOVE that edge are structure the sample size cannot explain,
    which turns "is T big enough" from a worry into a count of surviving factors. `min_eigenvalue`
    is reported because it is what disqualified 1'C^-1 1: inverting through 0.023 amplifies
    estimation noise without bound.
    """
    m = np.asarray(residuals, dtype="float64")
    m = m[np.isfinite(m).all(axis=1)]
    t, n = m.shape
    if t < 2 or n < 2:
        return {"q": float("nan"), "mp_edge": float("nan"), "top_eigenvalue": float("nan"),
                "n_above_edge": float("nan"), "min_eigenvalue": float("nan")}
    c = np.corrcoef(m, rowvar=False)
    eig = np.sort(np.linalg.eigvalsh(np.where(np.isfinite(c), c, 0.0)))[::-1]
    q = float(n) / float(t)
    edge = float((1.0 + np.sqrt(q)) ** 2)
    return {"q": q, "mp_edge": edge, "top_eigenvalue": float(eig[0]),
            "n_above_edge": float(int(np.sum(eig > edge))), "min_eigenvalue": float(eig[-1])}


def required_ic(n_eff: float, *, ir_target: float = 1.0, bets_per_year: float = 1.0) -> float:
    """Grinold inverted: the IC needed to hit `ir_target` at this breadth.

    IR = IC * sqrt(BR). `bets_per_year = 1` reads BR as the CROSS-SECTION ALONE, which is the
    convention `libs/research/alpha_economics.py` uses (`breadth: int = 20`, "independent
    bets/assets the signal spans") and therefore the number the narrow_breadth gate is about.
    Higher values annualise, and are reported separately BECAUSE THE ANNUALISED FORM IS THE
    EASIEST PLACE ON THIS DESK TO LIE TO ITSELF: BR = N_eff * 252 asserts that a daily rebalance
    yields 252 SERIALLY INDEPENDENT bets per name per year, i.e. a signal with zero
    autocorrelation at one day. No signal measured here has that property, and asserting it turns
    IC 0.06 into an IR of 4.3 -- a fantasy with a formula attached.
    """
    br = max(n_eff, 0.0) * max(bets_per_year, 0.0)
    if br <= 0.0:
        return float("inf")
    return float(ir_target / np.sqrt(br))


def gate_verdict(n_eff: float) -> dict[str, Any]:
    """Run the desk's OWN EV gate at the measured breadth -- not a paraphrase of it.

    `alpha_economics.ev_score` is imported and called rather than re-described, so this report
    cannot drift from the gate it reports on. The idea scored is the archetype the finding is
    about: a generic price-only cross-sectional crypto mechanism.
    """
    tags = ["price_only"] + (["narrow_breadth"] if n_eff < NARROW_BREADTH_LINE else [])
    idea = Idea(name="generic price-only crypto cross-section",
                breadth=max(round(n_eff), 1), tags=tags)
    return ev_score(idea)


# --------------------------------------------------------------------------------------------
# Reporting.
# --------------------------------------------------------------------------------------------

def blocked_report(missing: str, checked: list[str], remedy: str) -> dict[str, Any]:
    """The artifact written when there is no panel. A BLOCKED report is a RESULT, not a failure.

    It names the exact missing input, because "no data" that does not say WHICH data is a second
    investigation rather than an answer. The one thing it must never do is degrade into a number.
    """
    return {"status": "BLOCKED",
            "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "missing_input": missing,
            "checked": checked,
            "remedy": remedy,
            "headline_n_eff": None,
            "note": ("No panel on disk. NOT simulated: a synthetic cross-section would describe "
                     "its generator, not the market, and this measurement gates the desk's EV "
                     "hard-kill on narrow_breadth.")}


def build_report(panel: Panel, *, warmup: int = _BETA_WARMUP,
                 null_draws: int = _NULL_DRAWS) -> dict[str, Any]:
    """Measure the panel end to end. Any unmeasurable step BLOCKS; nothing is ever guessed."""
    rets_all = log_returns(panel.closes)
    live = live_columns(rets_all)
    dead = [s for s, ok in zip(panel.symbols, live, strict=True) if not ok]
    symbols = tuple(s for s, ok in zip(panel.symbols, live, strict=True) if ok)
    rets = rets_all[:, live]
    n_obs, n_sym = rets.shape
    if n_sym < _MIN_SYMBOLS or n_obs < _MIN_OBS:
        return blocked_report(
            f"usable panel too small after cleaning: {n_sym} symbols x {n_obs} return "
            f"observations (need >= {_MIN_SYMBOLS} x {_MIN_OBS})",
            [str(CACHE), str(LAKE)],
            "widen the fetch window (--days) or re-fetch; do NOT lower the minimums")

    raw = measure(rets)
    resid, betas = residualise(rets)
    ind = measure(resid)

    # UNKNOWN MUST BLOCK. A non-finite result here means the correlation structure was not
    # measurable. Emitting it as a number -- or as 0.0, or as "n/a" beside populated fields -- is
    # exactly the ambiguous-branch-allows defect: no downstream reader of this artifact would
    # treat a NaN breadth as a refusal, so the refusal has to be the status.
    if not np.isfinite(ind.n_eff) or not np.isfinite(ind.mean_corr):
        return blocked_report(f"residual correlation not measurable: {ind.verdict}",
                              [str(CACHE), str(LAKE)],
                              "inspect the panel for degenerate columns; never report an "
                              "unmeasurable N_eff as a number")

    floor = demeaning_floor(n_sym)
    pr_measured = participation_ratio(resid)
    null = one_factor_null(betas, float(np.std(rets.mean(axis=1))),
                           np.std(resid, axis=0), n_obs, draws=null_draws)
    pr_null = null["participation_ratio"]
    # Calibrated breadth: the participation ratio expressed as a fraction of what the SAME
    # estimator returns on a panel known to hold N independent bets. Residualisation itself burns
    # degrees of freedom (null PR is below N, not equal to it), so the raw ratio understates
    # breadth by a fixed amount that this division removes.
    pr_calibrated = (float("nan") if not np.isfinite(pr_null) or pr_null <= 0
                     else min(float(pr_measured / pr_null * n_sym), float(n_sym)))
    if not np.isfinite(pr_calibrated):
        return blocked_report("participation-ratio null did not calibrate",
                              [str(CACHE), str(LAKE)],
                              "estimator floor unknown -> breadth unreadable; do not report it")

    # HEADLINE = the most conservative usable estimator. The equicorrelation figure pins at its
    # own ceiling of N once residual correlation reaches the demeaning floor, so taking the
    # minimum is what keeps a ceiling-pinned estimator from setting the desk's IR budget.
    headline = min(float(ind.n_eff), pr_calibrated)

    proxy_idx = symbols.index("BTC") if "BTC" in symbols else 0
    proxy = measure(residualise_single_proxy(rets, proxy_idx))
    trail = residualise_trailing(rets, warmup=warmup)
    trail_rows = np.isfinite(trail).all(axis=1)
    ind_trail = measure(trail[trail_rows]) if int(trail_rows.sum()) >= _MIN_OBS else None

    path = expanding_breadth(trail)
    finite_path = path[np.isfinite(path)]
    mp = mp_structure(resid)
    annual = {str(int(r)): {"ir_at_desk_best_ic": round(DESK_BEST_IC * float(np.sqrt(headline * r)),
                                                        3),
                            "ic_for_ir_1": round(required_ic(headline, bets_per_year=float(r)), 4)}
              for r in (1, 12, 52, 252)}

    return {
        "status": "MEASURED",
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "source": panel.source,
        "fetched_utc": panel.fetched_utc,
        "headline_n_eff": round(headline, 2),
        "panel": {
            "universe_declared": list(UNIVERSE),
            "symbols": list(symbols),
            "n_symbols": n_sym,
            "n_obs": n_obs,
            "dropped_short_history": list(panel.dropped_short),
            "dropped_dead_or_nonfinite": dead,
            "first_bar_utc": datetime.fromtimestamp(int(panel.timestamps[0]) / 1000,
                                                    UTC).isoformat(timespec="seconds"),
            "last_bar_utc": datetime.fromtimestamp(int(panel.timestamps[-1]) / 1000,
                                                   UTC).isoformat(timespec="seconds"),
        },
        "market_factor": "leave-one-out equal-weight cross-sectional mean log return",
        "raw": {"mean_corr": round(raw.mean_corr, 4), "median_corr": round(raw.median_corr, 4),
                "n_eff": round(raw.n_eff, 2)},
        "residual": {
            "mean_corr": round(ind.mean_corr, 4),
            "median_corr": round(ind.median_corr, 4),
            "n_eff_equicorrelation": round(ind.n_eff, 2),
            "demeaning_floor": round(floor, 4),
            "excess_above_floor": round(ind.mean_corr - floor, 4),
            "verdict": ind.verdict,
            "note": ("mean pairwise correlation is pinned near the demeaning floor by arithmetic; "
                     "only the excess above it is evidence of surviving common structure"),
        },
        "residual_trailing": (None if ind_trail is None else {
            "mean_corr": round(ind_trail.mean_corr, 4),
            "n_eff": round(ind_trail.n_eff, 2),
            "n_obs": int(ind_trail.n_obs),
            "note": "beta from strictly prior rows only -- what a live book can actually hold"}),
        "estimators": {
            "equicorrelation_n_eff": round(ind.n_eff, 2),
            "participation_ratio": round(float(pr_measured), 2),
            "participation_ratio_one_factor_null": round(pr_null, 2),
            "participation_ratio_calibrated": round(pr_calibrated, 2),
            "headline_n_eff": round(headline, 2),
            "headline_rule": "min(equicorrelation, calibrated participation ratio)",
            "rejected": {
                "generalised_1_Cinv_1": {
                    "why": ("exact generalisation of the equicorrelation formula and the true "
                            "Grinold breadth of an equal-alpha portfolio, but it inverts through "
                            f"a smallest sample eigenvalue of {mp['min_eigenvalue']:.3f} and "
                            "returns ~1e3 on both the panel and the null. Right formula, wrong "
                            "estimator at this T/N. Needs shrinkage before it is usable."),
                },
            },
        },
        "single_asset_proxy": {
            "factor": symbols[proxy_idx],
            "mean_corr": round(proxy.mean_corr, 4),
            "n_eff": round(proxy.n_eff, 2),
            "one_factor_null_mean_corr": round(null["single_proxy_mean_corr"], 4),
            "one_factor_null_n_eff": round(null["single_proxy_n_eff"], 2),
            "would_fire_narrow_breadth": bool(proxy.n_eff < NARROW_BREADTH_LINE),
            "finding": ("errors-in-variables: a single asset is the factor PLUS its own "
                        "idiosyncratic return, which is injected into every residual and is "
                        "perfectly correlated across names. The null -- independent "
                        "idiosyncratics by construction -- reproduces this estimator's 'hard "
                        "kill' answer, so the answer is the estimator, not the market."),
        },
        "market_betas": {s: round(float(b), 3) for s, b in zip(symbols, betas, strict=True)},
        "breadth_illusion": {
            "nominal_n": n_sym,
            "nominal_sqrt_n": round(float(np.sqrt(n_sym)), 3),
            "effective_sqrt_n_eff": round(float(np.sqrt(headline)), 3),
            "ir_overstatement_x": round(float(np.sqrt(n_sym) / np.sqrt(headline)), 3),
        },
        "narrow_breadth": {
            "line": NARROW_BREADTH_LINE,
            "fires": bool(headline < NARROW_BREADTH_LINE),
            "margin": round(headline - NARROW_BREADTH_LINE, 2),
            "ev_gate_verdict": gate_verdict(headline),
        },
        "ic_required": {
            "ir_target": 1.0,
            "cross_sectional_only": round(required_ic(headline), 4),
            "desk_best_measured_ic": DESK_BEST_IC,
            "shortfall_x": round(required_ic(headline) / DESK_BEST_IC, 2),
            "by_bets_per_year": annual,
            "note": ("bets_per_year > 1 assumes serially INDEPENDENT rebalances, which is "
                     "unproven here. Signal half-life, not universe width, is the binding "
                     "constraint on IR at this breadth."),
        },
        "sampling_caveat": {
            "noise_dominated": bool(ind.noise_dominated),
            "t_over_n": round(float(n_obs) / float(n_sym), 2),
            "pairwise_corr_sampling_sd": round(float(1.0 / np.sqrt(max(n_obs - 3, 1))), 4),
            "null_loo_mean_corr": round(null["loo_mean_corr"], 4),
            "null_loo_mean_corr_sd": round(null["loo_mean_corr_sd"], 4),
            "null_draws": int(null["draws"]),
            "marchenko_pastur": {k: (round(v, 4) if np.isfinite(v) else None)
                                 for k, v in mp.items()},
            "note": ("eigenvalues above the MP edge are structure the sample size cannot "
                     "explain; that count is why the calibrated breadth sits below N"),
        },
        "stability": {
            "estimator": "participation ratio on trailing-beta residuals",
            "expanding_last": round(float(finite_path[-1]), 2) if finite_path.size else None,
            "expanding_min": round(float(finite_path.min()), 2) if finite_path.size else None,
            "expanding_max": round(float(finite_path.max()), 2) if finite_path.size else None,
            "note": ("trailing only at every stage -- truncating the sample cannot move any "
                     "earlier point (prefix invariance). The PR floor drifts with window "
                     "length, so read the shape of the path rather than its level."),
        },
    }


def _fmt_blocked(rep: dict[str, Any]) -> str:
    return ("\n=== CROSS-SECTION BREADTH :: BLOCKED ===\n"
            f"missing input : {rep['missing_input']}\n"
            f"checked       : {chr(10).join(rep['checked'])}\n"
            f"remedy        : {rep['remedy']}\n"
            f"{rep['note']}\n")


def _fmt_measured(rep: dict[str, Any]) -> str:
    p, res, est = rep["panel"], rep["residual"], rep["estimators"]
    ill, nb, ic = rep["breadth_illusion"], rep["narrow_breadth"], rep["ic_required"]
    samp, prox, mp = rep["sampling_caveat"], rep["single_asset_proxy"], \
        rep["sampling_caveat"]["marchenko_pastur"]
    trail = rep["residual_trailing"]
    n = rep["headline_n_eff"]
    lines = [
        "",
        "=== CROSS-SECTION BREADTH :: crypto perps, market factor removed ===",
        f"source   : {rep['source']}  ({rep['fetched_utc']})",
        f"panel    : {p['n_symbols']} symbols x {p['n_obs']} daily returns  "
        f"[{p['first_bar_utc'][:10]} .. {p['last_bar_utc'][:10]}]   T/N = {samp['t_over_n']}",
        f"factor   : {rep['market_factor']}",
        "",
        f"{'':30s}{'mean corr':>11s}{'floor':>9s}{'N_eff':>9s}",
        f"{'raw returns':30s}{rep['raw']['mean_corr']:11.3f}{'-':>9s}"
        f"{rep['raw']['n_eff']:9.2f}",
        f"{'residual (in-sample)':30s}{res['mean_corr']:11.3f}"
        f"{res['demeaning_floor']:9.3f}{res['n_eff_equicorrelation']:9.2f}",
    ]
    if trail is not None:
        lines.append(f"{'residual (trailing beta)':30s}{trail['mean_corr']:11.3f}"
                     f"{res['demeaning_floor']:9.3f}{trail['n_eff']:9.2f}")
    lines += [
        f"   excess above the arithmetic floor: {res['excess_above_floor']:+.4f}"
        f"   (null: {samp['null_loo_mean_corr']:+.4f} +/- {samp['null_loo_mean_corr_sd']:.4f})",
        "",
        "ESTIMATORS (each against its own measured floor)",
        f"  equicorrelation N_eff             {est['equicorrelation_n_eff']:8.2f}"
        "   (pins at N once corr hits the floor)",
        f"  participation ratio               {est['participation_ratio']:8.2f}"
        f"   vs one-factor null {est['participation_ratio_one_factor_null']:.2f}",
        f"  participation ratio, calibrated   {est['participation_ratio_calibrated']:8.2f}",
        f"  HEADLINE N_eff                    {n:8.2f}   [{est['headline_rule']}]",
        "",
        f"SINGLE-ASSET PROXY ({prox['factor']} as the factor) -- the tempting wrong answer",
        f"  measured  mean corr {prox['mean_corr']:+.3f} -> N_eff {prox['n_eff']:.2f}"
        f"   ({'WOULD FIRE' if prox['would_fire_narrow_breadth'] else 'would not fire'}"
        " narrow_breadth)",
        f"  null      mean corr {prox['one_factor_null_mean_corr']:+.3f} -> "
        f"N_eff {prox['one_factor_null_n_eff']:.2f}"
        "   <- SAME ANSWER ON DATA WITH NO RESIDUAL STRUCTURE",
        "",
        f"BREADTH ILLUSION  counting symbols gives sqrt(N)={ill['nominal_sqrt_n']:.2f}; "
        f"the truth is sqrt(N_eff)={ill['effective_sqrt_n_eff']:.2f}",
        f"                  -> IR ceiling overstated {ill['ir_overstatement_x']:.2f}x",
        "",
        f"NARROW_BREADTH (< {nb['line']:.0f}) : "
        f"{'FIRES -- the cross-section is hard-killed' if nb['fires'] else 'does NOT fire'}"
        f"   (N_eff {n:.2f}, margin {nb['margin']:+.2f})",
        "  desk EV gate on a price-only cross-sectional idea at this breadth:",
        f"    {nb['ev_gate_verdict']['verdict']}   (ev={nb['ev_gate_verdict']['ev']}, "
        f"p_survive={nb['ev_gate_verdict']['p_survive']})",
        "",
        f"IC NEEDED FOR IR 1.0 on the cross-section alone : "
        f"{ic['cross_sectional_only']:.3f}",
        f"  desk's best-ever MEASURED IC                  : "
        f"{ic['desk_best_measured_ic']:.3f}   -> short by {ic['shortfall_x']:.1f}x",
        f"{'bets/yr':>10s}{'IR @ IC=0.06':>14s}{'IC for IR=1.0':>15s}",
    ]
    for r, v in ic["by_bets_per_year"].items():
        lines.append(f"{r:>10s}{v['ir_at_desk_best_ic']:14.2f}{v['ic_for_ir_1']:15.3f}")
    lines += [
        f"  ({ic['note']})",
        "",
        "SAMPLING CAVEAT",
        f"  noise_dominated (T < 3N)  : {samp['noise_dominated']}     "
        f"T/N = {samp['t_over_n']}     per-pair sampling sd "
        f"{samp['pairwise_corr_sampling_sd']:.3f}",
        f"  Marchenko-Pastur edge     : {mp['mp_edge']:.2f} (q={mp['q']:.3f}); top residual "
        f"eigenvalue {mp['top_eigenvalue']:.2f}; {int(mp['n_above_edge'])} above the noise edge",
        f"  smallest eigenvalue       : {mp['min_eigenvalue']:.3f} "
        "(why 1'C^-1 1 is unusable here)",
        f"  expanding PR, trailing    : last {rep['stability']['expanding_last']}, "
        f"range [{rep['stability']['expanding_min']}, "
        f"{rep['stability']['expanding_max']}]  (shape, not level)",
        f"  {res['verdict']}",
        "",
    ]
    if p["dropped_short_history"]:
        lines.append(f"dropped, short history : {', '.join(p['dropped_short_history'])}")
    if p["dropped_dead_or_nonfinite"]:
        lines.append(f"dropped, dead feed     : {', '.join(p['dropped_dead_or_nonfinite'])}")
    return "\n".join(lines)


def render(rep: dict[str, Any]) -> str:
    return _fmt_blocked(rep) if rep["status"] == "BLOCKED" else _fmt_measured(rep)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Effective breadth of the crypto perp cross-section")
    ap.add_argument("--fetch", action="store_true",
                    help="populate data/perp_close_panel.json from OKX (REAL bars, never synthetic)")
    ap.add_argument("--days", type=int, default=500, help="calendar days of daily bars to fetch")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args(argv)

    # Read the module-level paths AT CALL TIME rather than relying on the parameter defaults,
    # which bind at definition time: with `load_cache()` the caller could never redirect the
    # panel location, so a test (or an operator with a lake elsewhere) would silently measure
    # the wrong file while believing it had pointed the script at a new one.
    panel = load_cache(CACHE) or load_lake(LAKE)
    if panel is None and args.fetch:
        doc = fetch_okx(args.days)
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(doc), "utf-8")
        panel = load_cache()

    if panel is None:
        rep = blocked_report(
            "no daily close panel for the crypto perp universe on disk",
            [f"  {CACHE} (cached panel: absent or unreadable)",
             f"  {LAKE}/bronze/crypto/*/D1 (Parquet lake: absent)",
             "  data/moat/fut/* (scripts/run_recorder.py tick moat: absent)"],
            "run with --fetch (OKX public daily perp candles), or build the lake via "
            "scripts/ingest_crypto.py. NOTE 2026-08-01: fapi.binance.com returns HTTP 451 and "
            "api.bybit.com is CloudFront-blocked from this box, so ingest_crypto.py "
            "(Binance-backed) cannot populate the lake here.")
    else:
        rep = build_report(panel)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2, sort_keys=True), "utf-8")
    print(render(rep))
    print(f"wrote {out}")
    # An exit code proves a process ended, never that it produced. The STATUS IN THE ARTIFACT
    # decides the code -- not the absence of a traceback.
    return 0 if rep["status"] == "MEASURED" else 2


if __name__ == "__main__":
    sys.exit(main())
