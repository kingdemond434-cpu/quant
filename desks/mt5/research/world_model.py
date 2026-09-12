"""F3 -- THE PROBABILISTIC MARKET WORLD MODEL: distributions and disagreement, never a label.

THE PRINCIPAL, 2026-09-12, ranking this third of the remaining blueprint:

    Ensemble POSTERIOR models of volatility, liquidity, trend/reversion, jumps, event state,
    macro state, cross-asset transmission, participant pressure and structural breaks, emitting
    DISTRIBUTIONS and uncertainty rather than one regime label.

WHAT THE DESK ALREADY HAS AND WHY IT IS NOT THIS. `libs/regime/engine.py` fits an HMM and a GMM,
cross-checks them, and emits ONE regime with a confidence scalar and a leverage multiplier. That
is a good classifier. It is not a world model, and the difference is not pedantic:

    A LABEL DESTROYS THE THING SIZING NEEDS. "high_vol, confidence 0.8" cannot answer "what is the
    95th percentile of tomorrow's move", which is the only question the survival envelope asks. A
    posterior can. E[log W] is an expectation over a DISTRIBUTION of outcomes; handing it a point
    estimate and a confidence is handing it the mean and throwing away the variance.

    DISAGREEMENT IS INFORMATION, AND THE CLASSIFIER SPENDS IT. engine.py's rule is that HMM/GMM
    disagreement DAMPENS confidence -- one number, falling. But WHICH axis the two estimators
    disagree on is the whole content: two estimators that agree on volatility and disagree on
    mean-reversion describe a completely different market from the reverse, and both collapse to
    "confidence 0.6". This organ keeps the disagreement per axis, because that is where a missing
    mechanism announces itself (and it is precisely what F8's anomaly queue is downstream of).

NINE AXES, EACH BY AT LEAST TWO INDEPENDENT ESTIMATORS. An "ensemble" of one estimator run twice
is one opinion counted twice -- the same error the audit lane refuses when it puts two seats on
different model families. So every axis here is estimated by methods that fail differently: a
conjugate posterior fails when the likelihood is wrong, a block bootstrap fails when the sample is
unrepresentative, and they do not fail together.

    volatility               conjugate inverse-gamma posterior | EWMA | block bootstrap
    trend_reversion          bootstrapped AR(1) phi            | variance ratio
    jumps                    Beta-Binomial exceedance intensity | Hill tail index
    liquidity                spread distribution               | tick-volume activity
    participant_pressure     signed-volume imbalance           | sign persistence
    structural_break         vol-regime break posterior        | mean-level break posterior
    cross_asset_transmission bootstrapped lead-lag             | contemporaneous benchmark
    event_state              the macro ledger
    macro_state              the ingested axes

UNMEASURED IS AN AXIS STATE, NOT A ZERO (L1.28a). event_state and macro_state are reported
UNMEASURED on this box today because the event ledger parses to nothing and the axes directory is
empty -- the same finding F8 surfaces from the other end. A world model that quietly filled those
with a neutral prior would be asserting that nothing is happening in the world, which is a much
stronger claim than admitting it cannot see.

NOTHING HERE SIZES, TRADES OR PROMOTES. It writes one report. The posteriors are available to
whatever wants them; no sizing path is rewired by this commit, and in particular nothing here
lowers any bound -- it publishes a distribution where there was a label.

    python desks/mt5/research/world_model.py [--apply]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

UNI = DESK / "data" / "universe"
SLEEVES = DESK / "data" / "sleeves.json"
EVENTS = DESK / "data" / "macro" / "event_ledger.jsonl"
AXES = DESK / "data" / "axes"
OUT = DESK / "reports" / "WORLD_MODEL.json"

#: Bars of history. ~2,000 H1 is about fourteen months -- two summers, two year-ends and at least
#: one policy turn, which is the shortest window in which "this regime is unusual" means anything.
BARS = 2000

#: The recent window every axis calls "now". 240 H1 bars is ten trading days: long enough for a
#: posterior to have shape, short enough that it is about the present rather than the year.
RECENT = 240

#: Bootstrap draws. 600 is enough for 5th/95th percentiles to be stable to about a percentage
#: point, which is finer than any decision made off them.
BOOT = 600

#: Block length for the block bootstrap, in bars. Hourly returns carry volatility clustering that
#: an i.i.d. resample destroys -- and destroying it is exactly how a bootstrap comes back
#: confidently wrong about the tail. 24 keeps a day intact.
BLOCK = 24

#: A jump is an absolute return beyond this many robust sigmas. 4 is chosen so that a Gaussian
#: world would deliver roughly one per 15,000 bars -- i.e. essentially none over this window, so
#: whatever is counted is the non-Gaussian part rather than the ordinary tail.
JUMP_SIGMA = 4.0

SEED = 20260912


def _live_symbols(limit: int = 20) -> list[str]:
    try:
        doc = json.loads(SLEEVES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    rows = doc if isinstance(doc, list) else (doc.get("sleeves") or [])
    out: list[str] = []
    for r in rows:
        if isinstance(r, dict) and str(r.get("status", "")).upper() == "LIVE":
            s = str(r.get("symbol") or "").strip()
            if s and s not in out:
                out.append(s)
    return out[:limit]


def _frame(symbol: str) -> Any:
    try:
        import pandas as pd
    except ImportError:
        return None
    p = UNI / f"{symbol}_H1.parquet"
    if not p.exists():
        return None
    try:
        df = pd.read_parquet(p)
    except (OSError, ValueError):
        return None
    if "close" not in df.columns or len(df) < 800:
        return None
    return df.tail(BARS)


def _q(xs: Any, ps: tuple[float, ...] = (5, 50, 95)) -> dict[str, float]:
    import numpy as np
    a = np.asarray(xs, dtype=float)
    a = a[np.isfinite(a)]
    if a.size == 0:
        return {}
    return {f"q{int(p):02d}": round(float(np.percentile(a, p)), 8) for p in ps}


def _disagreement(members: dict[str, float]) -> float | None:
    """How far apart SAME-UNIT, strictly positive estimators are, as a fraction of their scale.

    Scale-relative on purpose: an absolute gap of 0.0004 between two volatility estimates is
    enormous for EURUSD and negligible for XAUUSD, and a number that cannot be compared across
    symbols is a number nobody reads twice.

    IT REFUSES MIXED UNITS AND REFUSES NEAR-ZERO CENTRES, because both produce a large number that
    means nothing. Dividing a spread-in-points by a tick count is arithmetic, not a measurement;
    and two estimates either side of zero give a denominator near zero and a ratio that screams
    about a difference of 0.001. The first run of this organ reported "estimators differ by 200%
    of scale" on liquidity and participant_pressure for nearly every symbol, and both were this
    bug rather than a contested market -- so those axes now use the comparison that fits them.
    """
    vals = [v for v in members.values() if isinstance(v, (int, float)) and math.isfinite(v)]
    if len(vals) < 2:
        return None
    if min(vals) <= 0:
        return None
    centre = sum(vals) / len(vals)
    return round((max(vals) - min(vals)) / centre, 4) if centre > 0 else None


def _gap(members: dict[str, float]) -> float | None:
    """Absolute gap, for estimators that already share a bounded common scale.

    Probabilities and correlations live on [0, 1] or [-1, 1], where an absolute difference IS the
    comparable quantity and dividing by the mean only manufactures a big number near zero.
    """
    vals = [v for v in members.values() if isinstance(v, (int, float)) and math.isfinite(v)]
    if len(vals) < 2:
        return None
    return round(max(vals) - min(vals), 4)


def _block_boot(r: Any, stat: Any, draws: int = BOOT) -> list[float]:
    """Block bootstrap -- keeps volatility clustering intact, which an i.i.d. resample destroys."""
    import numpy as np
    rng = np.random.default_rng(SEED)
    a = np.asarray(r, dtype=float)
    n = a.size
    if n < BLOCK * 4:
        return []
    nblocks = max(1, n // BLOCK)
    out: list[float] = []
    for _ in range(draws):
        starts = rng.integers(0, n - BLOCK, size=nblocks)
        sample = np.concatenate([a[s:s + BLOCK] for s in starts])
        try:
            v = float(stat(sample))
        except Exception:
            continue
        if math.isfinite(v):
            out.append(v)
    return out


# --------------------------------------------------------------------------- the nine axes

def _axis_volatility(r: Any) -> dict[str, Any]:
    """Posterior predictive over next-bar |return|, three ways that fail differently."""
    import numpy as np
    a = np.asarray(r, dtype=float)
    recent = a[-RECENT:]
    n = recent.size
    if n < 60:
        return {"status": "UNMEASURED", "why": "fewer than 60 recent bars"}

    # (1) CONJUGATE. Normal likelihood, Jeffreys prior on variance -- the posterior for sigma^2 is
    # inverse-gamma, so draws are exact rather than asymptotic. Fails if returns are not Normal,
    # which they are not; that is why it is one member of three rather than the answer.
    rng = np.random.default_rng(SEED)
    ss = float(np.sum(recent ** 2))
    draws_conj = np.sqrt(ss / rng.chisquare(df=max(n - 1, 1), size=BOOT))

    # (2) EWMA at 0.94 -- RiskMetrics' decay. Fails in the opposite direction: it tracks a level
    # shift far faster than the conjugate window and therefore over-reacts to a single bar.
    lam = 0.94
    w = lam ** np.arange(n)[::-1]
    ewma = float(np.sqrt(np.sum(w * recent ** 2) / np.sum(w)))

    # (3) BLOCK BOOTSTRAP over the FULL window -- makes no distributional assumption at all and
    # fails only if the last fourteen months are unrepresentative of tomorrow.
    boot = _block_boot(a, lambda s: float(np.std(s)))

    members = {"conjugate": float(np.median(draws_conj)), "ewma": ewma,
               "block_bootstrap": float(np.median(boot)) if boot else float("nan")}
    pooled = np.concatenate([draws_conj, np.asarray(boot or [ewma], dtype=float)])
    return {"status": "OK", "unit": "per-bar log return sd",
            "posterior": _q(pooled), "members": {k: round(v, 8) for k, v in members.items()
                                                 if math.isfinite(v)},
            "disagreement": _disagreement(members),
            "reads": "the 95th percentile IS the survival envelope's input; a label is not"}


def _axis_trend_reversion(r: Any) -> dict[str, Any]:
    """P(mean-reverting) as a posterior, from two statistics that disagree in different worlds."""
    import numpy as np
    a = np.asarray(r, dtype=float)
    if a.size < 300:
        return {"status": "UNMEASURED", "why": "fewer than 300 bars"}

    def phi(s: Any) -> float:
        x, y = s[:-1], s[1:]
        d = float(np.dot(x, x))
        return float(np.dot(x, y) / d) if d > 0 else 0.0

    boot_phi = _block_boot(a, phi)
    if not boot_phi:
        return {"status": "UNMEASURED", "why": "bootstrap produced no finite draws"}

    # VARIANCE RATIO at 8 bars. Independent of AR(1) in the way that matters: a series can be
    # unpredictable one step ahead and still strongly mean-reverting over a day, and phi alone
    # calls that random.
    def vr(s: Any, k: int = 8) -> float:
        m = s.size // k * k
        if m < k * 4:
            return float("nan")
        agg = s[:m].reshape(-1, k).sum(axis=1)
        v1, vk = float(np.var(s[:m])), float(np.var(agg))
        return vk / (k * v1) if v1 > 0 else float("nan")

    boot_vr = _block_boot(a, vr)
    p_revert_phi = float(np.mean(np.asarray(boot_phi) < 0))
    p_revert_vr = float(np.mean(np.asarray(boot_vr) < 1.0)) if boot_vr else float("nan")
    # BOTH MEMBERS ARE PROBABILITIES, so the comparable quantity is the absolute gap.
    members = {"ar1_phi": p_revert_phi, "variance_ratio": p_revert_vr}
    return {"status": "OK",
            "p_mean_reverting": {"ar1": round(p_revert_phi, 4),
                                 "variance_ratio": (None if not boot_vr
                                                    else round(p_revert_vr, 4))},
            "phi_posterior": _q(boot_phi),
            "variance_ratio_posterior": _q(boot_vr) if boot_vr else {},
            "disagreement": _gap(members),
            "disagreement_unit": "absolute difference in P(mean-reverting)",
            "reads": ("a series can be unpredictable one bar ahead and strongly mean-reverting "
                      "over a day; phi alone calls that random, which is why both are kept")}


def _axis_jumps(r: Any) -> dict[str, Any]:
    """Jump intensity as a Beta posterior, and the tail's own thickness."""
    import numpy as np
    a = np.asarray(r, dtype=float)
    if a.size < 400:
        return {"status": "UNMEASURED", "why": "fewer than 400 bars"}
    # ROBUST sigma -- the MAD scaling, because estimating a jump threshold with a standard
    # deviation the jumps themselves inflate is how a jump detector learns to see nothing.
    sigma = float(np.median(np.abs(a - np.median(a)))) * 1.4826
    if sigma <= 0:
        return {"status": "UNMEASURED", "why": "degenerate scale"}
    k = int(np.sum(np.abs(a) > JUMP_SIGMA * sigma))
    n = int(a.size)
    # Jeffreys Beta(0.5, 0.5): the posterior over an intensity observed ZERO times is a
    # distribution with mass near zero, not the point zero. "No jump in fourteen months" is not
    # "jumps are impossible", and the difference is the entire tail of the book.
    rng = np.random.default_rng(SEED)
    post = rng.beta(0.5 + k, 0.5 + n - k, size=BOOT)

    # HILL tail index on the upper 5% of |r| -- how heavy the tail is, given that it is reached.
    tail = np.sort(np.abs(a))[::-1]
    m = max(10, int(0.05 * n))
    top = tail[:m]
    hill = float(np.mean(np.log(top[:-1] / top[-1]))) if top[-1] > 0 else float("nan")
    alpha = 1.0 / hill if hill and math.isfinite(hill) and hill > 0 else float("nan")
    return {"status": "OK", "n_exceedances": k, "n_bars": n, "threshold_sigma": JUMP_SIGMA,
            "intensity_posterior": _q(post),
            "expected_jumps_per_1000_bars": round(float(np.median(post)) * 1000, 3),
            "hill_tail_index": None if not math.isfinite(alpha) else round(alpha, 3),
            "reads": ("an intensity observed zero times has a POSTERIOR near zero, not the point "
                      "zero -- 'no jump in fourteen months' is not 'jumps are impossible', and "
                      "that difference is the whole tail of the book")}


def _axis_liquidity(df: Any) -> dict[str, Any]:
    """Two proxies: what a round trip costs, and how much trade there is to hide in."""
    import numpy as np
    out: dict[str, Any] = {"status": "OK"}
    members: dict[str, float] = {}
    if "spread" in df.columns:
        sp = np.asarray(df["spread"].tail(RECENT), dtype=float)
        sp = sp[np.isfinite(sp)]
        if sp.size and float(np.max(sp)) > 0:
            out["spread_points_posterior"] = _q(sp)
            members["spread"] = float(np.median(sp))
        else:
            out["spread"] = {"status": "UNMEASURED",
                             "why": ("the bar feed records spread 0 for every recent bar -- that "
                                     "is the feed not carrying it, never a zero-cost venue")}
    if "tick_volume" in df.columns:
        tv = np.asarray(df["tick_volume"], dtype=float)
        tv = tv[np.isfinite(tv)]
        if tv.size > RECENT:
            recent_med = float(np.median(tv[-RECENT:]))
            base_med = float(np.median(tv[:-RECENT])) or float("nan")
            out["activity_vs_history"] = (None if not math.isfinite(base_med) or base_med <= 0
                                          else round(recent_med / base_med, 3))
            out["tick_volume_posterior"] = _q(_block_boot(tv[-RECENT * 4:], np.median) or tv)
            members["tick_volume"] = recent_med
    if not members and "spread" not in out:
        return {"status": "UNMEASURED", "why": "the bar feed carries neither spread nor volume"}
    # NO DISAGREEMENT SCALAR HERE, DELIBERATELY. The two members are a spread in POINTS and a
    # tick COUNT; there is no ratio between them that means anything, and the first run of this
    # organ printed "200% of scale" for almost every symbol by computing one anyway.
    out["disagreement"] = None
    out["disagreement_why_none"] = (
        "the two members are measured in different units -- a spread in points and a tick count. "
        "A ratio between them is arithmetic, not a measurement, so each is reported on its own.")
    out["n_members"] = len(members)
    out["boundary"] = ("bar spread and tick volume are PROXIES for liquidity, not depth. The "
                       "depth probe is the real measurement and it is a separate path.")
    return out


def _axis_participant_pressure(df: Any, r: Any) -> dict[str, Any]:
    """Who is leaning on the tape, by two constructions that answer different questions."""
    import numpy as np
    a = np.asarray(r, dtype=float)
    if "tick_volume" not in df.columns or a.size < RECENT:
        return {"status": "UNMEASURED", "why": "no tick volume, or too little history"}
    v = np.asarray(df["tick_volume"], dtype=float)[-a.size:]
    if not np.isfinite(v).all() or float(np.sum(v)) <= 0:
        return {"status": "UNMEASURED", "why": "tick volume is absent or degenerate"}
    recent_r, recent_v = a[-RECENT:], v[-RECENT:]

    # (1) SIGNED-VOLUME IMBALANCE -- volume weighted by the sign of its own bar. A crude tick
    # rule, and it is crude in a KNOWN direction: it attributes the whole bar's volume to the
    # bar's net direction, so it overstates one-sided pressure in a chopping hour.
    imb = float(np.sum(np.sign(recent_r) * recent_v) / np.sum(recent_v))
    boot_imb = _block_boot(np.sign(recent_r) * recent_v / np.mean(recent_v), np.mean)

    # (2) SIGN PERSISTENCE -- P(next bar's sign repeats). Volume-free, so it survives exactly the
    # failure that breaks (1): a venue whose tick volume is a quote count rather than a trade one.
    s = np.sign(recent_r)
    same = float(np.mean(s[1:] == s[:-1])) if s.size > 1 else float("nan")
    # BOTH MEMBERS LIVE ON [-1, 1] AND BOTH SIT NEAR ZERO, so a scale-relative ratio is
    # meaningless -- it divides by a near-zero centre and reports a number about nothing. What a
    # reader actually wants is whether the two agree on DIRECTION, plus the absolute gap.
    excess = same - 0.5
    members = {"signed_volume_imbalance": imb, "sign_persistence_excess": excess}
    agree = None
    if math.isfinite(imb) and math.isfinite(excess) and imb != 0 and excess != 0:
        agree = (imb > 0) == (excess > 0)
    return {"status": "OK",
            "signed_volume_imbalance": round(imb, 5),
            "imbalance_posterior": _q(boot_imb) if boot_imb else {},
            "sign_persistence": None if not math.isfinite(same) else round(same, 4),
            "members_agree_on_direction": agree,
            "disagreement": _gap(members),
            "disagreement_unit": "absolute gap on the shared [-1, 1] scale",
            "boundary": ("MT5 tick_volume is a tick count, not traded size. This is a pressure "
                         "PROXY and is labelled as one; nothing sizes off it.")}


def _axis_structural_break(r: Any) -> dict[str, Any]:
    """Has the process changed -- in scale, in level -- and with what posterior probability?"""
    import numpy as np
    a = np.asarray(r, dtype=float)
    if a.size < 800:
        return {"status": "UNMEASURED", "why": "fewer than 800 bars"}
    recent, hist = a[-RECENT:], a[:-RECENT]
    rng = np.random.default_rng(SEED)

    # A PERMUTATION POSTERIOR, not a p-value dressed up. The null is "the recent window is an
    # ordinary draw from the same process"; the statistic's position in its own null distribution
    # IS the posterior probability of a break under a flat prior, and saying so beats quoting a
    # p-value that everyone then reads as a probability anyway.
    def _break_prob(stat_fn: Any) -> float:
        obs = float(stat_fn(recent))
        pool = np.concatenate([hist, recent])
        null = []
        nblocks = max(1, RECENT // BLOCK)
        for _ in range(BOOT):
            starts = rng.integers(0, pool.size - BLOCK, size=nblocks)
            samp = np.concatenate([pool[s:s + BLOCK] for s in starts])
            null.append(float(stat_fn(samp)))
        arr = np.asarray(null, dtype=float)
        arr = arr[np.isfinite(arr)]
        return float(np.mean(np.abs(arr - np.median(arr)) < abs(obs - np.median(arr)))) \
            if arr.size else float("nan")

    p_vol = _break_prob(np.std)
    p_mean = _break_prob(np.mean)
    # SCALE AND LEVEL ARE DIFFERENT QUESTIONS, not two estimates of one. The "disagreement"
    # here is therefore not estimator noise -- it is the informative statement that the process
    # changed in one moment and not the other, and it is on a probability scale either way.
    members = {"scale_break": p_vol, "level_break": p_mean}
    return {"status": "OK",
            "p_break_in_scale": None if not math.isfinite(p_vol) else round(p_vol, 4),
            "p_break_in_level": None if not math.isfinite(p_mean) else round(p_mean, 4),
            "disagreement": _gap(members),
            "disagreement_unit": "absolute difference between the two break probabilities",
            "reads": ("a break in SCALE and a break in LEVEL are different failures of a "
                      "calibrated threshold and are reported separately; DIST_SHIFT asks the "
                      "same question of a sleeve's own feature, this asks it of the price")}


def _axis_cross_asset(series: dict[str, Any]) -> dict[str, Any]:
    """Which symbol's move shows up in another's NEXT bar, and is the lead real?"""
    import numpy as np
    names = list(series)
    if len(names) < 2:
        return {"status": "UNMEASURED", "why": "fewer than two symbols with usable history"}
    import pandas as pd
    frame = pd.DataFrame(series).dropna()
    if len(frame) < 600:
        return {"status": "UNMEASURED", "why": f"only {len(frame)} shared bars"}
    rows: list[dict[str, Any]] = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            x, y = frame[a].to_numpy(), frame[b].to_numpy()
            # LEAD-LAG AGAINST ITS OWN CONTEMPORANEOUS BENCHMARK. A raw lag-1 correlation in two
            # assets that simply move together reads as a lead; the excess over the same-bar
            # correlation is the part that is actually predictive rather than simultaneous.
            c0 = float(np.corrcoef(x, y)[0, 1])
            ab = float(np.corrcoef(x[:-1], y[1:])[0, 1])
            ba = float(np.corrcoef(y[:-1], x[1:])[0, 1])
            best, lead = (ab, f"{a}->{b}") if abs(ab) >= abs(ba) else (ba, f"{b}->{a}")
            rows.append({"pair": f"{a}|{b}", "lead": lead,
                         "lag1_corr": round(best, 4), "contemporaneous": round(c0, 4),
                         "excess": round(abs(best) - abs(c0), 4)})
    rows.sort(key=lambda r: -abs(float(r["lag1_corr"])))
    real = [r for r in rows if float(r["excess"]) > 0]
    return {"status": "OK", "n_pairs": len(rows),
            "strongest_leads": rows[:8],
            "n_with_excess_over_contemporaneous": len(real),
            "reads": ("a lag-1 correlation between two assets that simply move together reads as "
                      "a lead. Only the EXCESS over the same-bar correlation is predictive, and "
                      f"{len(real)} of {len(rows)} pairs clear that bar at all")}


def _axis_event_state() -> dict[str, Any]:
    if not EVENTS.exists():
        return {"status": "UNMEASURED",
                "why": f"no macro event ledger at {EVENTS.relative_to(ROOT)}",
                "consequence": ("every extreme move is 'unexplained' by construction -- the same "
                                "defect UNKNOWN_UNKNOWNS.json reports from the other end")}
    n = 0
    for ln in EVENTS.read_text(encoding="utf-8", errors="replace").splitlines():
        if ln.strip():
            try:
                json.loads(ln)
                n += 1
            except ValueError:
                continue
    if n == 0:
        return {"status": "UNMEASURED", "why": "the event ledger exists and parses to zero rows"}
    return {"status": "OK", "n_events": n}


def _axis_macro_state() -> dict[str, Any]:
    if not AXES.exists():
        return {"status": "UNMEASURED",
                "why": f"no ingested axes directory at {AXES.relative_to(ROOT)}"}
    files = sorted(p.name for p in AXES.glob("*.json"))
    if not files:
        return {"status": "UNMEASURED", "why": "the axes directory exists and is empty"}
    return {"status": "OK", "axes_present": files}


# --------------------------------------------------------------------------------- assembly

def build() -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    try:
        import numpy as np
    except ImportError as exc:
        return {"at": now.isoformat(timespec="seconds"), "status": "UNMEASURED",
                "why": f"numpy unavailable ({exc})"}

    syms = _live_symbols()
    per_symbol: dict[str, Any] = {}
    series: dict[str, Any] = {}
    for s in syms:
        df = _frame(s)
        if df is None:
            continue
        px = df["close"]
        r = np.log(px.astype(float)).diff().dropna()
        if len(r) < 400:
            continue
        series[s] = r
        arr = r.to_numpy()
        per_symbol[s] = {
            "n_bars": int(arr.size),
            "volatility": _axis_volatility(arr),
            "trend_reversion": _axis_trend_reversion(arr),
            "jumps": _axis_jumps(arr),
            "liquidity": _axis_liquidity(df),
            "participant_pressure": _axis_participant_pressure(df, arr),
            "structural_break": _axis_structural_break(arr),
        }

    if not per_symbol:
        return {"at": now.isoformat(timespec="seconds"), "status": "UNMEASURED",
                "n_symbols": 0,
                "why": "no live symbol has usable H1 history on this box"}

    axes = {
        "cross_asset_transmission": _axis_cross_asset(series),
        "event_state": _axis_event_state(),
        "macro_state": _axis_macro_state(),
    }

    # WHAT A SINGLE LABEL WOULD HAVE HIDDEN. The headline of this organ is not any one posterior;
    # it is the axes where the estimators disagree, because that disagreement is the uncertainty
    # a confidence scalar averages away and the place a missing mechanism announces itself.
    contested: list[dict[str, Any]] = []
    for sym, row in per_symbol.items():
        for axis, val in row.items():
            if not isinstance(val, dict):
                continue
            d = val.get("disagreement")
            # THE THRESHOLD IS 0.30 ON EACH AXIS'S OWN SCALE, and the scale is carried with the
            # row: 0.30 is 30% of the estimators' own size for volatility, and 0.30 of probability
            # for the axes whose members share the [0, 1] or [-1, 1] ranges. Mixing those in one
            # ranking without saying which is which is how a comparable-looking number stops
            # being comparable.
            if isinstance(d, (int, float)) and d >= 0.30:
                contested.append({"symbol": sym, "axis": axis, "disagreement": d,
                                  "unit": val.get("disagreement_unit",
                                                  "fraction of the estimators' own scale")})
    contested.sort(key=lambda r: -float(r["disagreement"]))

    unmeasured = [k for k, v in axes.items() if v.get("status") == "UNMEASURED"]
    for sym, row in per_symbol.items():
        for axis, val in row.items():
            if isinstance(val, dict) and val.get("status") == "UNMEASURED":
                unmeasured.append(f"{sym}.{axis}")

    return {
        "at": now.isoformat(timespec="seconds"),
        "n_symbols": len(per_symbol), "bars": BARS, "recent_window": RECENT,
        "symbols": per_symbol,
        "axes": axes,
        "contested": contested[:20],
        "n_contested": len(contested),
        "unmeasured_axes": sorted(set(unmeasured)),
        "status": "OK" if per_symbol else "UNMEASURED",
        "why_not_a_label": (
            "engine.py emits one regime with a confidence scalar and a leverage multiplier. That "
            "cannot answer 'what is the 95th percentile of tomorrow's move', which is the only "
            "question the survival envelope asks. E[log W] is an expectation over a DISTRIBUTION; "
            "handing it a point estimate and a confidence hands it the mean and discards the "
            "variance."),
        "why_disagreement_is_kept": (
            "engine.py's rule is that HMM/GMM disagreement DAMPENS confidence -- one number, "
            "falling. But WHICH axis they disagree on is the content: agreeing on volatility and "
            "disagreeing on mean-reversion describes a different market from the reverse, and "
            "both collapse to the same scalar."),
        "boundary": (
            "NOTHING HERE SIZES, TRADES OR PROMOTES, and nothing here lowers a bound. It "
            "publishes distributions where the desk had a label. Any consumer faces the same "
            "gates as before."),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write the report")
    a = ap.parse_args(argv)
    doc = build()
    if doc.get("status") == "UNMEASURED":
        print(f"world model: UNMEASURED -- {doc.get('why')}")
        return 0
    print(f"world model: {doc['status']}   {doc['n_symbols']} symbol(s), "
          f"{doc['n_contested']} contested axis-reading(s)")
    for sym, row in list(doc["symbols"].items())[:6]:
        vol = row["volatility"].get("posterior") or {}
        jmp = row["jumps"]
        tr = row["trend_reversion"].get("p_mean_reverting") or {}
        print(f"  {sym:<10} sd q05/q50/q95 "
              f"{vol.get('q05', 0):.5f}/{vol.get('q50', 0):.5f}/{vol.get('q95', 0):.5f}"
              f"  P(revert) ar1 {tr.get('ar1')}  jumps/1k "
              f"{jmp.get('expected_jumps_per_1000_bars')}")
    for c in doc["contested"][:6]:
        print(f"  CONTESTED  {c['symbol']:<10} {c['axis']:<22} "
              f"{float(c['disagreement']):.2f}  ({c.get('unit')})")
    x = doc["axes"]["cross_asset_transmission"]
    if x.get("status") == "OK":
        print(f"  cross-asset: {x['n_with_excess_over_contemporaneous']}/{x['n_pairs']} pair(s) "
              f"lead beyond their same-bar correlation")
        for r in x["strongest_leads"][:3]:
            print(f"     {r['lead']:<24} lag1 {r['lag1_corr']:+.3f} "
                  f"vs same-bar {r['contemporaneous']:+.3f}")
    if doc["unmeasured_axes"]:
        print(f"  UNMEASURED: {', '.join(doc['unmeasured_axes'][:8])}")
    if not a.apply:
        print("  --apply not given; nothing written")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
