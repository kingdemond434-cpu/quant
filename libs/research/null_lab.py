"""THE NULL LAB: each family's own pipeline run on data where no edge can exist.

WHAT THE DESK ALREADY HAD, AND WHY IT WAS NOT THIS (surveyed 2026-09-30).

    libs/tiers/traps.py + meta_benchmark.py   planted SYNTHETIC cases (leakage, selection,
                                              label_randomization, ...) scored by a REFERENCE
                                              validator and the production certifier -- one
                                              toy signal per kind, never a family's own code
    research/placebo_audit.py                 ONE planted edge and eight defect twins through
                                              the real gauntlet -- recall of the gates, not of
                                              any family
    libs/tiers/test_invention.py              proposes new checks from labelled suites
    traps "label_randomization"               a lookup table fitted to noise labels

None of them answers the question a family's certificate depends on: *when this family's own
signal code is run through the gauntlet's own cell builder on data with no edge in it, how often
does the gate pass?* A gate at a nominal 5% that passes one family's null 15% of the time is a
5% gate for everyone else and a 15% gate for that family, and every certificate that family
holds was bought at a third of the price the desk believes it paid.

THREE NULLS, EACH DESTROYING A DIFFERENT THING:

    block_shuffle   the instrument's own bars, cut into blocks and re-ordered. Keeps the
                    marginal distribution, fat tails and short-range volatility clustering;
                    destroys every dependence longer than a block and, because blocks are not
                    day-aligned, the hour-of-day structure a session family could legitimately
                    trade. What remains cannot be predicted across blocks.
    random_walk     a Gaussian walk with the instrument's own per-bar volatility and intrabar
                    range, on the same timestamps. No tails, no clustering, no edge at all --
                    the cleanest null, and the one where a family that still passes is most
                    plainly fitting its own mechanics.
    sign_permute    the REAL bars and the family's REAL signals, each signal's direction flipped
                    by a fair coin (stop/target/trigger mirrored about the signal bar's close so
                    the bracket is the same distance). Keeps timing, frequency, exposure and the
                    real market; destroys only the family's directional information.

The statistics are the gauntlet's own per-cell ones, recomputed on the cell's daily R series the
way `external_gauntlet.daily_series` builds it: `in_sample_screen` (Sharpe > 0), the
`deflated_sharpe` gate at one trial (the probabilistic Sharpe ratio >= DSR_THRESHOLD -- the gate's
own statistic with no multiplicity charge, so its nominal level is exact), and the Stage-A screen
t >= 1.96 on trade R. Each has a NOMINAL level under the null; the lab measures the EMPIRICAL one.

THE CONSEQUENCE. `charge()` turns a family's measured null pass rate on the deflated-Sharpe gate
into a multiplier on its p-values: posterior null rate / nominal, never below 1. The online FDR
organ (`libs/tiers/online_fdr.charge_null_fpr`) applies it, so a family whose gate is easier to
pass on noise spends more of the lifetime error budget per certificate -- the honest price. A
family the lab could not measure is charged nothing and is listed UNMEASURED; absence is never
read as a clean null (L1.28a).
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

import numpy as np
import numpy.typing as npt

F = npt.NDArray[np.float64]

ARMS: tuple[str, ...] = ("block_shuffle", "random_walk", "sign_permute")
#: The gauntlet's deflated-Sharpe pass bar (`external_gauntlet.DSR_THRESHOLD`); a test pins them.
DSR_THRESHOLD = 0.95
SCREEN_T = 1.96
MIN_TRADES = 20
MIN_DAYS = 60
#: gate -> its nominal pass rate under a true null
NOMINAL: dict[str, float] = {
    "deflated_sharpe_1trial": 1.0 - DSR_THRESHOLD,
    "screen_t": 0.025,
    "in_sample_screen": 0.5,
}
#: the gate whose null rate prices a family's certificates (online FDR draws p from 1 - DSR)
CHARGED_GATE = "deflated_sharpe_1trial"
#: prior strength (pseudo-draws at the nominal rate): a family is not repriced on three draws
PRIOR_DRAWS = 20.0
BLOCK = 12
UNMEASURED = "UNMEASURED"


# ------------------------------------------------------------------------------ null bars
def _frame_arrays(df: Any) -> tuple[F, F, F, F]:
    o = df["open"].to_numpy(float)
    h = df["high"].to_numpy(float)
    lo = df["low"].to_numpy(float)
    c = df["close"].to_numpy(float)
    return o, h, lo, c


def _rebuild(df: Any, o: F, h: F, lo: F, c: F, extra_perm: npt.NDArray[np.int64] | None) -> Any:
    out = df.copy()
    out["open"], out["high"], out["low"], out["close"] = o, h, lo, c
    if extra_perm is not None:
        for col in out.columns:
            if col not in ("open", "high", "low", "close"):
                out[col] = df[col].to_numpy()[extra_perm]
    return out


def block_shuffle(df: Any, rng: np.random.Generator, block: int = BLOCK) -> Any:
    """The frame's own bars re-ordered in blocks of `block`, on the ORIGINAL timestamps.

    Each bar is carried as log offsets from the previous close (gap, high, low, close), so the
    rebuilt path is continuous and every bar's shape survives. A random circular offset before
    blocking means block edges never line up with the day."""
    o, h, lo, c = _frame_arrays(df)
    n = len(c)
    if n < 2 * block:
        raise ValueError(f"{n} bars is too few to block-shuffle at {block}")
    prev = np.concatenate([[o[0]], c[:-1]])
    rel = np.log(np.column_stack([o, h, lo, c]) / prev[:, None])
    start = int(rng.integers(0, block))
    idx = np.roll(np.arange(n), -start)
    blocks = [idx[i:i + block] for i in range(0, n, block)]
    order = rng.permutation(len(blocks))
    perm = np.concatenate([blocks[k] for k in order]).astype(np.int64)
    rel = rel[perm]
    closes = c[0] * np.exp(np.cumsum(rel[:, 3]))
    pc = np.concatenate([[c[0]], closes[:-1]])
    new = np.exp(rel) * pc[:, None]
    hi = np.maximum.reduce([new[:, 1], new[:, 0], new[:, 3]])
    low = np.minimum.reduce([new[:, 2], new[:, 0], new[:, 3]])
    return _rebuild(df, new[:, 0], hi, low, new[:, 3], perm)


def random_walk(df: Any, rng: np.random.Generator) -> Any:
    """A Gaussian walk with the frame's own per-bar log-return volatility and its median
    high-low range, on the frame's timestamps. The volume/spread columns are kept as they are:
    they carry no price information once the price is noise."""
    _o, h, lo, c = _frame_arrays(df)
    r = np.diff(np.log(c))
    sigma = float(np.std(r[np.isfinite(r)], ddof=1)) if len(r) > 2 else 0.001
    sigma = sigma if sigma > 0 and math.isfinite(sigma) else 0.001
    rng_frac = np.log(h / np.maximum(lo, 1e-12))
    half = float(np.nanmedian(rng_frac[np.isfinite(rng_frac)])) / 2.0 if len(c) else sigma
    n = len(c)
    steps = rng.normal(0.0, sigma, size=n)
    steps[0] = 0.0
    closes = c[0] * np.exp(np.cumsum(steps))
    opens = np.concatenate([[c[0]], closes[:-1]])
    wick = np.abs(rng.normal(0.0, max(half, 1e-9), size=(n, 2)))
    hi = np.maximum(opens, closes) * np.exp(wick[:, 0])
    low = np.minimum(opens, closes) * np.exp(-wick[:, 1])
    return _rebuild(df, opens, hi, low, closes, None)


def sign_permute(sigs: Sequence[Any], df: Any, rng: np.random.Generator) -> list[Any]:
    """Each signal's side flipped with probability 1/2, its bracket mirrored about the close of
    its own bar so the stop and target keep their distances. Signals whose bar is not in the
    frame are kept unflipped (they cannot be mirrored honestly) and counted by the caller."""
    import dataclasses
    close = df["close"]
    out: list[Any] = []
    for g in sigs:
        if rng.random() >= 0.5:
            out.append(g)
            continue
        try:
            ref = float(close.loc[g.time])
        except (KeyError, TypeError, ValueError):
            out.append(g)
            continue
        changes: dict[str, Any] = {"side": -int(g.side), "stop": 2 * ref - float(g.stop),
                                   "target": 2 * ref - float(g.target)}
        if getattr(g, "trigger", None) is not None:
            changes["trigger"] = 2 * ref - float(g.trigger)
        out.append(dataclasses.replace(g, **changes))
    return out


# ------------------------------------------------------------------------------ statistics
def trade_t(r: Sequence[float]) -> float | None:
    a = np.asarray(list(r), dtype=float)
    a = a[np.isfinite(a)]
    if len(a) < MIN_TRADES:
        return None
    sd = float(a.std(ddof=1))
    if sd <= 0:
        return None
    return float(a.mean() / (sd / math.sqrt(len(a))))


def gate_stats(trade_r: Sequence[float], daily: Sequence[float]) -> dict[str, Any]:
    """The per-cell gate statistics on one draw, with a pass flag per gate.

    A gate that cannot be judged on this draw (too few trades or days) reports passed=None and
    the draw counts toward that gate's UNMEASURED, never toward its passes or its fails."""
    from libs.validation.dsr import probabilistic_sharpe_ratio, sharpe_ratio
    d = np.asarray(list(daily), dtype=float)
    d = d[np.isfinite(d)]
    out: dict[str, Any] = {"n_trades": len(list(trade_r)), "n_days": len(d)}
    t = trade_t(trade_r)
    out["screen_t"] = {"stat": t, "passed": None if t is None else bool(t >= SCREEN_T)}
    if len(d) < MIN_DAYS or float(d.std(ddof=1)) <= 0:
        out["in_sample_screen"] = {"stat": None, "passed": None}
        out["deflated_sharpe_1trial"] = {"stat": None, "passed": None}
        return out
    sr = float(sharpe_ratio(d))
    psr = float(probabilistic_sharpe_ratio(d, sr_benchmark=0.0))
    out["in_sample_screen"] = {"stat": sr, "passed": bool(sr > 0.0)}
    out["deflated_sharpe_1trial"] = {"stat": psr,
                                     "passed": bool(psr >= DSR_THRESHOLD)}
    return out


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return 0.0, 1.0
    p = k / n
    den = 1 + z * z / n
    mid = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, mid - half), min(1.0, mid + half)


def _quantiles(xs: Sequence[float]) -> dict[str, float] | None:
    a = np.asarray([x for x in xs if x is not None and math.isfinite(x)], dtype=float)
    if not len(a):
        return None
    qs = np.quantile(a, [0.05, 0.25, 0.5, 0.75, 0.95, 0.99])
    return {k: round(float(v), 6) for k, v in zip(("q05", "q25", "q50", "q75", "q95", "q99"),
                                                   qs, strict=True)}


def summarise(draws: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Per family, per gate (and per arm): the empirical null pass rate, its Wilson interval,
    the null distribution of the statistic, and whether the rate EXCEEDS its nominal level
    (Wilson lower bound above nominal -- a noisy family is not flagged on luck)."""
    by: dict[str, list[Mapping[str, Any]]] = {}
    for d in draws:
        if d.get("family"):
            by.setdefault(str(d["family"]), []).append(d)
    fams: dict[str, Any] = {}
    for fam, rows in sorted(by.items()):
        run = [r for r in rows if r.get("status") == "RUN"]
        rec: dict[str, Any] = {"draws": len(rows), "run": len(run),
                               "not_run": len(rows) - len(run),
                               "not_run_why": sorted({str(r.get("why") or "")[:120]
                                                      for r in rows if r.get("status") != "RUN"
                                                      })[:5],
                               "gates": {}}
        for gate, nominal in NOMINAL.items():
            g_all = [r for r in run if (r.get("stats") or {}).get(gate, {}).get("passed")
                     is not None]
            k = sum(1 for r in g_all if r["stats"][gate]["passed"])
            n = len(g_all)
            lo, hi = wilson(k, n)
            per_arm = {}
            for arm in ARMS:
                ga = [r for r in g_all if r.get("arm") == arm]
                ka = sum(1 for r in ga if r["stats"][gate]["passed"])
                per_arm[arm] = {"n": len(ga), "passed": ka,
                                "rate": round(ka / len(ga), 6) if ga else None}
            rec["gates"][gate] = {
                "nominal": nominal, "n": n, "passed": k,
                "rate": round(k / n, 6) if n else None,
                "wilson": [round(lo, 6), round(hi, 6)] if n else None,
                "posterior_rate": round(posterior_rate(k, n, nominal), 6),
                "exceeds_nominal": bool(n and lo > nominal),
                "unmeasured_draws": len(run) - n,
                "per_arm": per_arm,
                "null_distribution": _quantiles(
                    [(r.get("stats") or {}).get(gate, {}).get("stat") for r in run]),
            }
        cg = rec["gates"][CHARGED_GATE]
        rec["status"] = "MEASURED" if cg["n"] else UNMEASURED
        rec["fpr_charge"] = charge(cg["passed"], cg["n"], cg["nominal"]) if cg["n"] else None
        fams[fam] = rec
    return fams


def posterior_rate(k: int, n: int, nominal: float, prior: float = PRIOR_DRAWS) -> float:
    """Beta posterior mean with a prior of `prior` pseudo-draws AT the nominal rate: a family is
    believed nominal until its own draws say otherwise."""
    return (k + prior * nominal) / (n + prior)


def charge(k: int, n: int, nominal: float) -> float:
    """p-value multiplier for a family: its posterior null pass rate over the nominal level,
    never below 1 (a family whose null passes LESS than nominal is not given a discount -- the
    lab measures an easy gate, it does not certify a hard one)."""
    if n <= 0 or nominal <= 0:
        return 1.0
    return round(max(1.0, posterior_rate(k, n, nominal) / nominal), 6)


def charges(doc: Mapping[str, Any] | None) -> dict[str, float]:
    """{family: charge > 1} from a NULL_LAB.json document. Families at 1.0 or UNMEASURED are
    left out: they are charged exactly what they were charged before."""
    fams = (doc or {}).get("families") if isinstance(doc, Mapping) else None
    out: dict[str, float] = {}
    for fam, rec in (fams or {}).items() if isinstance(fams, Mapping) else ():
        if not isinstance(rec, Mapping):
            continue
        c = rec.get("fpr_charge")
        if isinstance(c, (int, float)) and math.isfinite(float(c)) and float(c) > 1.0:
            out[str(fam)] = float(c)
    return out
