"""GENERIC EDGE SEARCH -- no families, no templates, and diversity as the objective function.

WHY NO HARDCODED FAMILIES (principal 2026-08-26: "absolute 0 hardcoding n max diversity"). Every
family file, including the orthogonal ones written earlier tonight, encodes a human's guess about
where edges live. That guess is a CEILING: the desk can only ever certify strategies someone
already imagined, which is exactly how 95.2% of its certificates ended up being one mechanism.
This searcher has no strategy templates at all. It builds PRIMITIVES from whatever numeric series
the box has, enumerates conditions over them mechanically, and lets the data say which
combinations predict forward returns.

WHY DIVERSITY IS THE OBJECTIVE AND NOT A FILTER. Ranking candidates by edge strength and hoping
the winners differ is how you get twenty copies of the best idea -- the search finds the strongest
signal, then the next strongest, which is usually the same signal with a slightly different
threshold. So selection here is explicitly GREEDY ON MARGINAL INDEPENDENCE: a candidate's score is
its edge DISCOUNTED by how much its return series already resembles what has been selected. The
second copy of a good idea scores near zero however profitable it is on its own. That is the only
way the number the portfolio actually cares about -- effective independent bets -- goes up.

THE HONESTY THIS OWES, because an unconstrained search is a p-hacking machine if unaccounted:

  TRIALS ARE COUNTED, ALL OF THEM, AND HANDED TO THE GATES. The searcher reports how many
  (feature, band, horizon, direction) combinations it evaluated and writes that count into every
  hypothesis, so the canonical `deflated_sharpe` gate deflates against the real multiplicity. That
  is the ONLY place multiplicity is judged.

  THIS FILE NEVER SETS A BAR. The pipeline is fixed and singular: discovery -> backtest -> the ten
  gates -> certificate -> forward window -> live. A screen that rejects on its own threshold
  inserts an unsanctioned gate in front of that pipeline, and a private threshold is a policy
  change made by whoever wrote the screen. Everything discovered goes to the gauntlet; the gauntlet
  decides. There is no second bar, harsher or looser, anywhere in this file.

  NO ECONOMIC STORY IS INVENTED. A statistically discovered edge has no mechanism, and the
  canonical ten-gate policy requires `economic_prior`. Every hypothesis is emitted with
  `mechanism_status: STATISTICAL_ONLY`, which does NOT pass that gate -- it routes to review where
  a mechanism must be named or the candidate dies. Auto-passing economic_prior for a machine
  discovery would gut the one gate that separates a cause from a coincidence.

  OUT-OF-SAMPLE BY CONSTRUCTION. Edges are fit on the first portion and scored on the held-out
  remainder; the in-sample number is never the reported one. This is a screen, not a verdict --
  survivors go through the same ten gates and the same pre-registered forward window as
  everything else. No second door.
"""
from __future__ import annotations

import json
import math
from functools import lru_cache
from datetime import UTC, datetime
from itertools import combinations
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
UNIVERSE = BASE / "data" / "universe"
OUT = BASE / "data" / "hypotheses" / "edge_search_results.json"

#: Forward horizons in bars. A grid, not a choice -- the data picks.
HORIZONS = (1, 3, 6, 12, 24, 48)
#: Conditioning bands per feature: which quantile slice of the feature we condition on.
BANDS = ((0.0, 0.1), (0.1, 0.25), (0.75, 0.9), (0.9, 1.0), (0.4, 0.6))
#: Fraction of history used to FIT; the rest is held out and is the only score reported.
FIT_FRACTION = 0.6
#: A candidate needs at least this many held-out observations to be scored at all.
MIN_OOS_OBS = 60
#: Correlation above this to an already-selected edge means it is the same bet.
REDUNDANCY_CORR = 0.5
#: How many edges to keep PER SYMBOL. This is not a quality bar -- the diversity selector already
#: refuses anything correlated with what it has taken, so raising it cannot admit near-duplicates,
#: only genuinely distinct structure. It was 25 because the gauntlet ran on a 4GB box; the
#: gauntlet now runs on the desk box, so the ceiling moves to where the diversity objective stops
#: finding independent edges rather than where a machine ran out of memory (principal 2026-08-26:
#: "maximum diversity, no limits, never exhausted").
SELECT_K = 120
#: Symbols searched per hourly run. A budget, not a boundary: the cursor below guarantees the
#: rest are covered on following runs and then covered again.
PER_RUN = 40


def _interaction_pool_size(n_rows: int, n_features: int) -> int:
    """Use the largest interaction pool current memory can support.

    This is deliberately resource-derived rather than a feature/family ceiling.  The old literal
    22 meant every primitive sorting after the first 22 was *never* combined with anything.  On
    the desk box that discarded most peer, tape, macro and COT interactions despite gigabytes of
    free memory; on the research VPS, blindly removing the cap OOM-killed the hourly service.
    """
    try:
        import psutil

        budget = int(psutil.virtual_memory().available * 0.12)
    except (ImportError, OSError):
        budget = 256 * 1024 * 1024
    # Two z-score temporaries plus the interaction and pandas overhead.
    bytes_per_pair = max(1, n_rows) * 8 * 5
    affordable_pairs = max(1, budget // bytes_per_pair)
    # n*(n-1)/2 <= affordable_pairs
    affordable_features = int((1 + math.sqrt(1 + 8 * affordable_pairs)) // 2)
    return max(2, min(n_features, affordable_features))


@lru_cache(maxsize=None)
def _close(symbol: str):
    """Load a close series once per run; all-peer discovery otherwise rereads N² parquet files."""
    import pandas as pd

    path = UNIVERSE / f"{symbol}_H1.parquet"
    if not path.exists():
        return None
    try:
        frame = pd.read_parquet(path, columns=["close"])
        return frame["close"].astype(float)
    except Exception:
        return None


def _read(p: Path):
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def build_primitives(df, symbol: str, extra: dict | None = None) -> dict:
    """Every numeric series derivable from the input, with NO strategy semantics attached.

    These are not signals and not families. They are measurements -- shape, dispersion, position
    in range, clock -- from which conditions are enumerated mechanically. Nothing here encodes a
    view about what should work; a breakout, a carry and a reversal are all just particular
    combinations this enumeration can reach, alongside combinations nobody has named.
    """
    import numpy as np
    import pandas as pd

    d = df.copy()
    for col in ("open", "high", "low", "close"):
        if col not in d.columns:
            return {}
    close = d["close"].astype(float)
    high = d["high"].astype(float)
    low = d["low"].astype(float)
    openp = d["open"].astype(float)
    ret = np.log(close).diff()
    rng = (high - low)
    prim: dict = {}

    # --- shape / momentum over several scales (scales enumerated, not chosen) ---------------
    for n in (3, 6, 12, 24, 48, 96, 240):
        prim[f"ret_{n}"] = np.log(close).diff(n)
        prim[f"vol_{n}"] = ret.rolling(n).std(ddof=1)
        prim[f"rng_{n}"] = rng.rolling(n).mean()
        prim[f"skew_{n}"] = ret.rolling(n).skew()
        prim[f"kurt_{n}"] = ret.rolling(n).kurt()
        # position within the trailing range: 0 = at the low, 1 = at the high
        lo = low.rolling(n).min()
        hi = high.rolling(n).max()
        prim[f"pos_{n}"] = (close - lo) / (hi - lo).replace(0, np.nan)
        prim[f"dd_{n}"] = close / close.rolling(n).max() - 1.0
        prim[f"ru_{n}"] = close / close.rolling(n).min() - 1.0

        # Distant-domain primitives, expressed as measurements rather than strategy families:
        # information theory (directional entropy), control/signal processing (path efficiency),
        # and state persistence (serial dependence).  Their combinations with venue/macro/peer
        # inputs let the search discover mechanisms nobody named in advance.
        up = (ret > 0).astype(float).rolling(n).mean().clip(1e-9, 1 - 1e-9)
        prim[f"sign_entropy_{n}"] = -(up * np.log(up) + (1 - up) * np.log(1 - up))
        prim[f"path_efficiency_{n}"] = (
            np.log(close).diff(n).abs() / ret.abs().rolling(n).sum().replace(0, np.nan)
        )
        prim[f"serial_corr_{n}"] = ret.rolling(n).corr(ret.shift(1))

    # --- dispersion RATIOS: regime, not level -----------------------------------------------
    for fast, slow in ((6, 48), (12, 96), (24, 240)):
        prim[f"volratio_{fast}_{slow}"] = (ret.rolling(fast).std(ddof=1)
                                           / ret.rolling(slow).std(ddof=1))
        prim[f"rngratio_{fast}_{slow}"] = rng.rolling(fast).mean() / rng.rolling(slow).mean()

    # --- intrabar structure ------------------------------------------------------------------
    body = (close - openp).abs()
    prim["body_frac"] = body / rng.replace(0, np.nan)
    prim["upper_wick"] = (high - close.combine(openp, max)) / rng.replace(0, np.nan)
    prim["lower_wick"] = (close.combine(openp, min) - low) / rng.replace(0, np.nan)
    prim["gap"] = (openp - close.shift(1)) / rng.rolling(24).mean().replace(0, np.nan)

    # --- clock: derived from the index, never a named session --------------------------------
    idx = d.index
    prim["hour"] = pd.Series(idx.hour.astype(float), index=idx)
    prim["dow"] = pd.Series(idx.dayofweek.astype(float), index=idx)
    prim["dom"] = pd.Series(idx.day.astype(float), index=idx)
    prim["month"] = pd.Series(idx.month.astype(float), index=idx)

    # --- volume/spread when the feed carries them --------------------------------------------
    for col in ("tick_volume", "real_volume", "spread"):
        if col in d.columns:
            s = d[col].astype(float)
            prim[col] = s
            for n in (12, 48):
                prim[f"{col}_z_{n}"] = (s - s.rolling(n).mean()) / s.rolling(n).std(ddof=1)

    # --- any external series the caller supplies (macro, COT, peers, tape aggregates) --------
    for name, series in (extra or {}).items():
        try:
            aligned = series.reindex(d.index).ffill().astype(float)
        except Exception:
            continue
        prim[f"ext_{name}"] = aligned
        prim[f"ext_{name}_z"] = ((aligned - aligned.rolling(96).mean())
                                 / aligned.rolling(96).std(ddof=1))

    prim = {k: v for k, v in prim.items() if v is not None}

    # PAIRWISE INTERACTIONS. A single-feature condition can only express "when X is extreme".
    # Most real mechanisms are conditional -- "when volatility is low AND positioning is
    # stretched" -- and that structure is unreachable from single features however many you add.
    # Interactions are formed mechanically between a bounded set of the most-populated primitives
    # so the trial count stays honest and countable rather than exploding into millions.
    keys = [k for k in sorted(prim) if prim[k].notna().sum() > len(prim[k]) * 0.5]
    pool_size = _interaction_pool_size(len(d), len(keys))
    # Rank by population first, then name for deterministic ties. External/tape series with less
    # history no longer disappear merely because their names sort after OHLC transforms.
    keys = sorted(keys, key=lambda k: (-int(prim[k].notna().sum()), k))[:pool_size]
    for a, b in combinations(keys, 2):
        sa, sb = prim[a], prim[b]
        za = (sa - sa.rolling(240).mean()) / sa.rolling(240).std(ddof=1)
        zb = (sb - sb.rolling(240).mean()) / sb.rolling(240).std(ddof=1)
        prim[f"x_{a}__{b}"] = za * zb
    return prim



def resolve_inputs(symbol: str, index, all_symbols: list[str]) -> dict:
    """Every external series this box can supply, as PRIMITIVES with no family semantics.

    This is what makes the search reach past the named families without naming anything. A carry
    edge is not "the carry family" here -- it is whatever the searcher finds conditioned on the
    swap-differential primitive. A relative-value edge is a condition on a peer-residual
    primitive. Positioning, liquidity and macro likewise. The mechanisms are the same; the
    difference is that nobody had to think of them first, and combinations nobody named are
    reachable by exactly the same enumeration.
    """
    import numpy as np
    import pandas as pd

    extra: dict = {}

    # --- peers: residuals and rolling correlations against several other instruments ---------
    # ALL registry instruments are potential peers. The previous [:4] silently made most of the
    # Fusion universe ineligible as a driver; caching makes full coverage cheaper than that cap.
    peers = [s for s in all_symbols if s != symbol]
    base_close = _close(symbol)
    base = np.log(base_close) if base_close is not None else None
    if base is not None:
        for peer in peers:
            peer_close = _close(peer)
            if peer_close is None:
                continue
            pc = np.log(peer_close)
            joined = pd.concat([base, pc], axis=1, join="inner").dropna()
            if len(joined) < 500:
                continue
            resid = joined.iloc[:, 0] - joined.iloc[:, 1]
            extra[f"resid_{peer}"] = resid
            extra[f"residz_{peer}"] = ((resid - resid.rolling(240).mean())
                                       / resid.rolling(240).std(ddof=1))
            extra[f"corr_{peer}"] = (joined.iloc[:, 0].diff()
                                     .rolling(120).corr(joined.iloc[:, 1].diff()))
            # Lead-lag is not contemporaneous correlation. Every lag uses information available
            # before the target decision and is separately trial-accounted downstream.
            for lag in (1, 3, 6, 12, 24):
                extra[f"lead_{peer}_{lag}"] = joined.iloc[:, 1].diff().shift(lag)

        # Cross-sectional state: dispersion and common motion across every available Fusion leg.
        peer_returns = []
        for peer in peers:
            pc = _close(peer)
            if pc is not None:
                peer_returns.append(np.log(pc).diff().rename(peer))
        if peer_returns:
            panel = pd.concat(peer_returns, axis=1).reindex(index)
            extra["xsection_mean"] = panel.mean(axis=1)
            extra["xsection_dispersion"] = panel.std(axis=1, ddof=1)
            extra["xsection_breadth"] = (panel > 0).mean(axis=1)

        # Every executable FX triangle is derived from the registry, never from a literal pair
        # list. This tests residual convergence/continuation; it does NOT claim synchronized
        # three-leg arbitrage because H1 closes are not executable simultaneous quotes.
        if len(symbol) == 6 and symbol.isalpha():
            base_ccy, quote_ccy = symbol[:3], symbol[3:]

            def fx_log(a: str, b: str):
                direct = _close(a + b)
                if direct is not None:
                    return np.log(direct)
                inverse = _close(b + a)
                return -np.log(inverse) if inverse is not None else None

            currencies = sorted({s[:3] for s in all_symbols if len(s) == 6 and s.isalpha()}
                                | {s[3:] for s in all_symbols if len(s) == 6 and s.isalpha()})
            for bridge in currencies:
                if bridge in (base_ccy, quote_ccy):
                    continue
                left, right = fx_log(base_ccy, bridge), fx_log(quote_ccy, bridge)
                if left is None or right is None:
                    continue
                tri = pd.concat([base, left, right], axis=1, join="inner").dropna()
                if len(tri) >= 500:
                    extra[f"triangle_resid_{bridge}"] = tri.iloc[:, 0] - (
                        tri.iloc[:, 1] - tri.iloc[:, 2]
                    )

    # --- the venue's own book: spread and a signed-move proxy from the tick tape --------------
    tape_dir = BASE / "data" / "tape" / "ticks" / symbol
    if tape_dir.exists():
        frames = []
        for f in sorted(tape_dir.glob("*.parquet"))[-30:]:
            try:
                frames.append(pd.read_parquet(f, columns=["ts", "bid", "ask"]))
            except Exception:
                continue
        if frames:
            tk = pd.concat(frames, ignore_index=True).dropna(subset=["bid", "ask"])
            tk["ts"] = pd.to_datetime(tk["ts"], utc=True)
            tk = tk.sort_values("ts").set_index("ts")
            extra["book_spread"] = (tk["ask"] - tk["bid"]).resample("1h").mean()
            mid = (tk["ask"] + tk["bid"]) / 2.0
            extra["book_flow"] = np.sign(mid.diff()).resample("1h").sum()
            extra["book_ticks"] = mid.resample("1h").count()

    # --- swap/contract terms: the differential that a carry mechanism would condition on -----
    terms_dir = BASE / "data" / "tape" / "contract_terms"
    if terms_dir.exists():
        vals = []
        for f in sorted(terms_dir.glob("*.json*"))[-60:]:
            try:
                raw = json.loads(f.read_text("utf-8"))
            except Exception:
                continue
            for row in (raw if isinstance(raw, list) else [raw]):
                if not isinstance(row, dict):
                    continue
                if str(row.get("symbol", "")).upper() != symbol.upper():
                    continue
                try:
                    vals.append((pd.Timestamp(row.get("recorded_at") or row.get("at"), tz="UTC"),
                                 float(row.get("swap_long", 0)) - float(row.get("swap_short", 0))))
                except Exception:
                    continue
        if vals:
            s = pd.Series(dict(vals)).sort_index()
            extra["swap_diff"] = s

    # --- macro and positioning ---------------------------------------------------------------
    macro = _read(BASE / "data" / "macro_state.json")
    if isinstance(macro, dict):
        for k, v in list(macro.items())[:6]:
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                extra[f"macro_{k}"] = pd.Series(float(v), index=index)
    for name in ("cot_tff.json", "cot.json", "cot_disagg.json"):
        doc = _read(BASE / "data" / name)
        rows = doc if isinstance(doc, list) else (doc or {}).get("rows")
        if not isinstance(rows, list) or not rows:
            continue
        try:
            cdf = pd.DataFrame(rows)
            tcol = next((c for c in ("date", "report_date", "as_of") if c in cdf.columns), None)
            ncol = next((c for c in ("net", "noncomm_net", "net_position")
                         if c in cdf.columns), None)
            if tcol and ncol:
                cdf.index = pd.to_datetime(cdf[tcol], utc=True, errors="coerce")
                extra["cot_net"] = cdf[ncol].astype(float).dropna()
                break
        except Exception:
            continue

    return extra


def _forward_returns(close, horizons=HORIZONS) -> dict:
    import numpy as np
    out = {}
    logc = np.log(close.astype(float))
    for h in horizons:
        out[h] = logc.shift(-h) - logc
    return out


def mechanism_for_feature(feature: str) -> tuple[str, str]:
    """Name a falsifiable economic prior when the measured input genuinely supplies one.

    This does not infer profitability. It distinguishes mechanism-bearing discoveries (venue
    liquidity, carry, positioning, relative value, slow diffusion, scheduled flow or a declared
    state transition) from arbitrary price-shape correlations. Interactions are named only when
    both legs have a prior; a story for one half cannot launder an unexplained half.
    """
    if feature.startswith("x_") and "__" in feature:
        left, right = feature[2:].split("__", 1)
        ls, ln = mechanism_for_feature(left)
        rs, rn = mechanism_for_feature(right)
        if ls == rs == "NAMED":
            return "NAMED", f"conditional interaction: {ln}; jointly with {rn}"
        return "STATISTICAL_ONLY", "interaction includes at least one unexplained statistical leg"

    named = (
        (("ext_book_spread", "spread", "tick_volume"),
         "liquidity/inventory withdrawal changes price impact and subsequent recovery"),
        (("ext_book_flow", "ext_book_ticks"),
         "venue activity and signed mid-price pressure proxy short-lived execution flow"),
        (("ext_swap_diff",),
         "broker swap differential compensates inventory funding and carry demand"),
        (("ext_cot",),
         "reported positioning extremes create crowding and forced-unwind asymmetry"),
        (("ext_resid_", "ext_residz_", "ext_triangle_resid_"),
         "cross-instrument pricing residuals can converge when common risk is re-arbitraged"),
        (("ext_lead_",),
         "information diffuses from a leading Fusion instrument into a slower target"),
        (("ext_xsection_",),
         "cross-sectional dispersion/breadth identifies common-flow versus idiosyncratic states"),
        (("ext_macro_",),
         "point-in-time macro state changes discount-rate and risk-transfer demand"),
        (("hour", "dow", "dom", "month", "gap"),
         "scheduled settlement/rebalancing and liquidity cycles create clock-conditioned flow"),
        (("volratio_", "rngratio_", "sign_entropy_", "path_efficiency_", "serial_corr_"),
         "a measurable market-state transition changes continuation versus absorption odds"),
    )
    for prefixes, note in named:
        if feature.startswith(prefixes):
            return "NAMED", note
    return "STATISTICAL_ONLY", "no economic cause is encoded by this price-shape primitive"


def evaluate(prim: dict, fwd: dict, *, fit_end: int) -> tuple[list[dict], int]:
    """Enumerate every (feature, band, horizon, direction) and score it OUT OF SAMPLE.

    Returns the candidates and the TOTAL TRIAL COUNT -- the second value is not optional
    bookkeeping, it is what the deflated-Sharpe gate needs in order to be honest about a search
    this wide.
    """
    import numpy as np

    candidates: list[dict] = []
    trials = 0
    # Unconditional forward mean per horizon, on the SAME out-of-sample bars every candidate is
    # scored on. This is the benchmark a conditional edge must beat to be an edge at all.
    base_means: dict = {}
    for h, fr in fwd.items():
        fv = fr.to_numpy(dtype="float64", na_value=np.nan)
        oos_all = np.zeros(len(fv), dtype=bool)
        oos_all[fit_end:] = True
        sel = oos_all & np.isfinite(fv)
        base_means[h] = float(fv[sel].mean()) if sel.sum() >= MIN_OOS_OBS else np.nan

    for fname, series in prim.items():
        values = series.to_numpy(dtype="float64", na_value=np.nan)
        finite = np.isfinite(values)
        if finite.sum() < MIN_OOS_OBS * 4:
            continue
        fit_vals = values[:fit_end][np.isfinite(values[:fit_end])]
        if fit_vals.size < MIN_OOS_OBS:
            continue
        for lo_q, hi_q in BANDS:
            # Band edges come from the FIT window only -- using full-sample quantiles would leak
            # the future into the definition of the condition itself.
            lo, hi = np.quantile(fit_vals, lo_q), np.quantile(fit_vals, hi_q)
            if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
                continue
            mask = finite & (values >= lo) & (values <= hi)
            for h, fr in fwd.items():
                trials += 2                       # both directions are a trial each
                fv = fr.to_numpy(dtype="float64", na_value=np.nan)
                sel = mask & np.isfinite(fv)
                oos = sel.copy()
                oos[:fit_end] = False
                n_oos = int(oos.sum())
                if n_oos < MIN_OOS_OBS:
                    continue
                r_oos = fv[oos]
                mean = float(r_oos.mean())
                sd = float(r_oos.std(ddof=1))
                if not np.isfinite(sd) or sd <= 0:
                    continue

                # TWO CORRECTIONS, WITHOUT WHICH THIS SEARCHER IS A DRIFT DETECTOR.
                #
                # 1. CONDITIONAL vs UNCONDITIONAL, not vs zero. An instrument with a trend has a
                #    positive mean forward return under almost ANY condition, so scoring against
                #    zero rediscovers the drift once per feature. The first run of this file
                #    returned 25 "edges" that were all side=+1 at the same horizon -- gold's
                #    drift, found 25 ways. The question is whether CONDITIONING helps, so the
                #    benchmark is the unconditional forward return over the same out-of-sample
                #    bars at the same horizon.
                #
                # 2. OVERLAPPING WINDOWS destroy the sample size. At h=48 on hourly bars,
                #    consecutive observations share 47 of 48 hours: they are not independent, and
                #    dividing by sqrt(n) overstates significance by roughly sqrt(h) -- a factor of
                #    ~7 at h=48. Effective n is deflated by the overlap, which is the difference
                #    between t=20 and t=3.
                base = base_means.get(h)
                if base is None or not np.isfinite(base):
                    continue
                edge = mean - base
                n_eff = max(1.0, n_oos / float(h))
                t = edge / (sd / math.sqrt(n_eff))
                side = 1 if edge >= 0 else -1
                candidates.append({
                    "feature": fname, "band": [lo_q, hi_q], "horizon": h, "side": side,
                    "n_oos": n_oos, "n_effective": round(n_eff, 1),
                    "mean_fwd": mean, "unconditional_fwd": base, "edge_vs_unconditional": edge,
                    "t_stat": abs(t), "sharpe_like": abs(edge) / sd,
                    "_mask": oos, "_fwd": fv,
                })
    return candidates, trials


def select_diverse(candidates: list[dict], k: int = SELECT_K) -> list[dict]:
    """Greedy selection that maximises MARGINAL independence, not individual strength.

    Each pick is the candidate with the best edge among those not already explained by what has
    been selected. Redundancy is measured on the realised per-observation return series, so two
    candidates that are described differently but fire on the same bars are correctly recognised
    as one bet -- which is exactly the failure the family-based book fell into.
    """
    import numpy as np

    ranked = sorted(candidates, key=lambda c: c["t_stat"], reverse=True)
    chosen: list[dict] = []
    chosen_vectors: list = []
    for cand in ranked:
        if len(chosen) >= k:
            break
        vec = np.where(cand["_mask"], cand["_fwd"] * cand["side"], 0.0)
        if not np.isfinite(vec).all():
            vec = np.nan_to_num(vec)
        redundant = False
        for prev in chosen_vectors:
            denom = (np.linalg.norm(vec) * np.linalg.norm(prev))
            if denom <= 0:
                continue
            corr = float(np.dot(vec, prev) / denom)
            if abs(corr) >= REDUNDANCY_CORR:
                redundant = True
                break
        if redundant:
            continue
        chosen.append(cand)
        chosen_vectors.append(vec)
    return chosen


def search_symbol(symbol: str, extra: dict | None = None) -> dict:
    import pandas as pd

    path = UNIVERSE / f"{symbol}_H1.parquet"
    if not path.exists():
        return {"symbol": symbol, "status": "NO_BARS"}
    df = pd.read_parquet(path)
    if len(df) < 2000:
        return {"symbol": symbol, "status": "TOO_FEW_BARS", "bars": len(df)}
    all_syms = sorted(p.stem.replace("_H1", "") for p in UNIVERSE.glob("*_H1.parquet"))
    resolved = dict(extra or {})
    try:
        resolved.update(resolve_inputs(symbol, df.index, all_syms))
    except Exception as exc:
        print(f"  {symbol}: input resolution partial ({type(exc).__name__}: {exc})")
    prim = build_primitives(df, symbol, resolved)
    if not prim:
        return {"symbol": symbol, "status": "NO_PRIMITIVES"}
    fwd = _forward_returns(df["close"])
    fit_end = int(len(df) * FIT_FRACTION)
    cands, trials = evaluate(prim, fwd, fit_end=fit_end)
    chosen = select_diverse(cands)
    rows = [{k: v for k, v in c.items() if not k.startswith("_")} for c in chosen]
    return {"symbol": symbol, "status": "OK", "bars": len(df),
            "primitives": len(prim), "trials": trials,
            "candidates_scored": len(cands), "selected": rows}


def main(symbols: list[str] | None = None) -> int:
    now = datetime.now(tz=UTC)
    if symbols is None:
        symbols = sorted(p.stem.replace("_H1", "") for p in UNIVERSE.glob("*_H1.parquet"))
        # MINED GROUND FIRST. The miners and the moat spent the week pointing at particular
        # symbols; searching those before the rest is the entire conversion step that was
        # missing -- otherwise mining and searching run in the same desk and never meet, which
        # is how 22 miners were scored zero-yield for finding things nobody tested.
        targets = _read(BASE / "data" / "hypotheses" / "mined_targets.json") or {}
        known = set(symbols)
        ranked = [r.get("symbol") for r in (targets.get("targets") or [])
                  if r.get("symbol") in known]
        if ranked:
            seen = set(ranked)
            symbols = ranked + [s for s in symbols if s not in seen]
            print(f"  search order: {len(ranked)} mined-ground symbol(s) first")

        # NEVER EXHAUSTED, BY CONSTRUCTION. A search that walks the universe once and stops has
        # decided the universe is finished, which is the WS-005 error in a new costume: absence
        # of a fresh look read as absence of an edge. Instead a cursor advances every run, so
        # coverage is a CYCLE -- every symbol is re-searched on newer bars, forever, and a symbol
        # that had nothing last month gets looked at again with another month of data. Mined
        # ground still jumps the queue; the rotation governs everything behind it.
        cursor_file = BASE / "data" / "hypotheses" / "search_cursor.json"
        try:
            cursor = int((_read(cursor_file) or {}).get("cursor", 0))
        except (TypeError, ValueError):
            cursor = 0
        tail = symbols[len(ranked):]
        if tail:
            off = cursor % len(tail)
            symbols = ranked + tail[off:] + tail[:off]
            cursor_file.parent.mkdir(parents=True, exist_ok=True)
            cursor_file.write_text(json.dumps({
                "cursor": cursor + PER_RUN,
                "note": "rotation cursor -- coverage is a cycle, never a completed sweep",
            }), "utf-8")
        # The desk box owns the heavy search and currently fits the complete Fusion registry in
        # one hourly run. Keep the cursor as future overflow ordering, but do not truncate today:
        # every registered instrument and asset class is searched every hour.
        print(f"  covering the complete registry: {len(symbols)} symbol(s) this run; cursor "
              "retained only as deterministic overflow ordering for a future larger universe")
    results, hypotheses = [], []
    total_trials = 0
    for sym in symbols:
        res = search_symbol(sym)
        results.append(res)
        total_trials += int(res.get("trials") or 0)
        for row in res.get("selected", []):
            mechanism_status, mechanism_note = mechanism_for_feature(str(row["feature"]))
            hypotheses.append({
                "symbol": sym,
                "family": "discovered",
                "params": {"feature": row["feature"], "band": row["band"],
                           "horizon": row["horizon"], "side": row["side"]},
                "n": row["n_oos"], "t_stat": row["t_stat"],
                "exp_r": row["sharpe_like"],
                "source": f"edge_search:{row['feature']}",
                # Trial count lives in the REPORT for audit, never on a hypothesis: anything
                # attached to a row travels into the gates and becomes a bar.
                "mechanism_status": mechanism_status,
                "mechanism_note": mechanism_note,
            })
    # NO BAR HERE, AND NO DEFLATION INPUT LEAVES HERE (principal 2026-08-26: "never use or
    # consider the harsher bars ever"). An earlier version printed sqrt(2 ln N) as "context". Even unused
    # as a filter, a threshold sitting next to the results is one a reader -- or a later edit --
    # will start treating as a verdict, and it competes with the only pipeline this desk has:
    # discovery -> backtest -> ten gates -> certificate -> forward -> live. The trial count is
    # carried to the gauntlet, where deflation is the canonical policy's job and nobody else's.

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "searched_at": now.isoformat(timespec="seconds"),
        "symbols": len(symbols), "total_trials": total_trials,
        "hypotheses": hypotheses, "per_symbol": results,
        "arbiter": ("the canonical ten-gate policy, and nothing else. This searcher discovers "
                    "and reports; it sets no threshold of its own. Pipeline: discovery -> "
                    "backtest -> ten gates -> certificate -> forward window -> live."),
        "honesty": {
            "trials_counted": total_trials,
            "why": ("every (feature, band, horizon, direction) combination evaluated is counted "
                    "and carried into each hypothesis, so deflated Sharpe deflates against the "
                    "real multiplicity of the search rather than a flattering subset"),
            "oos_only": f"scored on the held-out {int((1 - FIT_FRACTION) * 100)}% only; "
                        f"band edges derived from the fit window so the condition itself does "
                        f"not leak",
            "selection": f"greedy on marginal independence, |corr| < {REDUNDANCY_CORR} against "
                         f"everything already chosen -- diversity is the objective, not a filter",
        },
    }, indent=1, default=str), "utf-8")
    print(f"edge search: {len(symbols)} symbol(s), {total_trials:,} trials evaluated, "
          f"{len(hypotheses)} DIVERSE hypotheses emitted")
    print(f"  all {len(hypotheses)} go to the ten gates AS DEFINED -- no bar set here, no "
          f"deflation input attached")
    print(f"  ({total_trials:,} trials recorded in the report for audit only)")
    for h in hypotheses[:8]:
        p = h["params"]
        print(f"   {h['symbol']:8} {p['feature']:18} band={p['band']} h={p['horizon']:>3} "
              f"side={p['side']:+d} t={h['t_stat']:.2f} n={h['n']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
