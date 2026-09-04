#!/usr/bin/env python3
"""THE CAPITAL BRAIN -- robust posterior E[log W] over every validated edge, on many clocks.

    "At every moment, identify and allocate to the combination of currently available validated
     independent edges that maximizes robust expected log-wealth after costs and uncertainty.
     Never force a trade when the robust marginal Elog is non-positive; instead feed that
     opportunity gap back into research."                          -- the principal, 2026-09-02

WHAT THIS IS. The desk's allocation decision, made from evidence and written to
`reports/pf_allocation.json`. It solves for PER-SLEEVE HEAT, not weights, so the answer to "how
much in total" and "on what" is one optimisation instead of a constant and an optimisation. It
runs on three clocks:

    --mode fast     ~5 min   reuse the cached scenario population, re-solve the book
    --mode normal  ~15 min   rebuild evidence, re-solve, re-run the no-trade filter
    --mode heavy    hourly   resample the whole world population, re-measure the growth curve,
                             re-certify the utilisation target

WHY THREE. The expensive part is the scenario population (posterior draws x regimes x crisis
overlays x execution draws), not the optimisation -- measured 2026-09-02, sampling 256 worlds
over 109 sleeves costs 0.3 s and the solve 3 s, while ASSEMBLING the evidence costs 104 s. So the
cheap loops reuse the cache and the heavy loop earns it. Nothing here is throttled to protect
compute; it is split because the inputs genuinely change on different clocks.

WHAT IT DOES NOT DO. It places no orders and moves no capital. It writes the book the gateway
reads and the marginal ranking `cap_by_heat` trims by. Arming stays a human act
(`data/PF_ALLOCATOR_ARMED`); until that file exists this is a measurement the desk can compare
against what it is actually doing -- which is itself the finding, because the two have never been
compared.

THE NO-TRADE REGION. `--mode` says how often it RECOMPUTES, never how often it TRADES. A
recomputation that wants less turnover than it is worth returns NO CHANGE, so the allocator can
run every 15 minutes and move the book twice a day.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.portfolio.robust_elog import (  # noqa: E402
    AllocationResult,
    SleeveEvidence,
    WorldConfig,
    Worlds,
    optimise,
    sample_worlds,
    score_book,
)
from research.heat_policy import (  # noqa: E402
    HEAT_HARD_CEILING,
    HEAT_TARGET,
    enforce_family_cap,
    evidence_readiness,
    per_sleeve_bounds,
    resolve,
)

OUT = BASE / "reports" / "pf_allocation.json"
DONE = BASE / "reports" / "DONE_pf_allocation"
CACHE = BASE / "data" / "pf_allocator_cache"
ARMED = BASE / "data" / "PF_ALLOCATOR_ARMED"
#: Append-only record of what each pass EXPECTED. Read by `allocator_attribution.py`.
FORECASTS = BASE / "data" / "pf_forecast_log.jsonl"

#: How stale the assembled daily-R matrix may be before a `normal` pass rebuilds it. The matrix
#: changes when a new certificate lands or a sleeve accumulates bars -- both hourly events -- so
#: an hour is the honest refresh, and the heavy clock rebuilds unconditionally anyway.
EVIDENCE_MAX_AGE_S = 3600

#: Heat curve grid for certification. Spans the free optimum through the hard ceiling so the
#: peak is bracketed rather than assumed.
CURVE_GRID = (0.02, 0.04, 0.06, 0.08, 0.10, 0.125, 0.15, 0.175, 0.20, 0.225, 0.25, 0.275, 0.30)

#: Round-trip execution cost charged against a unit of heat moved, in account fraction. Turnover
#: below the growth it buys is not an improvement, and this is the price that decides.
TURNOVER_COST_R = 0.06
#: Days of growth the rebalance is expected to earn before the next one supersedes it. Short on
#: purpose: a rebalance justified only by a month of undisturbed holding is not justified.
NO_TRADE_HORIZON_DAYS = 5.0

#: Annual growth above which the pass is REFUSED as an input defect. The armed gold book replays
#: at ~36%/yr and the widest optimised book measured here at ~219%; four figures has never been
#: produced by anything real on this desk. Set well above every honest number so it can only fire
#: on a defect, and it fires by refusing the pass rather than by clipping the number -- a clipped
#: number is a defect wearing a plausible answer.
IMPLAUSIBLE_ANNUAL_PCT = 5000.0

#: Regime-mixture bounds. No regime the desk has enough history for is ever assigned zero worlds
#: (MIN), and no regime may own more than MAX of the population however certain the classifier
#: sounds. See `regime_state` for the measurement that made both necessary.
REGIME_MIN_SHARE = 0.08
REGIME_MAX_SHARE = 0.60

#: Horizon, IN DAYS, the world population is drawn for. The regime that matters for sizing is the
#: one that will prevail while the book is HELD, not the one holding at the instant of the solve:
#: an edge can be excellent inside a trend and terrible around its termination.
#:
#: ONE DAY, AND THAT IS MEASURED RATHER THAN CHOSEN. `data/pf_forecast_log.jsonl` records the book
#: this allocator actually solved on each pass. Over its 87 booked passes the median pass-to-pass
#: total-variation change is 0.0006 -- the no-trade region and turnover cost make the book very
#: sticky -- and it drifts 0.18 from its starting composition within half a day before flattening.
#: So a book solved now is still substantially the same book a day out, and is not obviously the
#: same book much beyond that. The log spans 1.6 days, so it cannot support a longer claim, and
#: guessing one would be picking a number to suit an answer.
#:
#: `REGIME_TERM_STRUCTURE` is reported in the artifact but never used for sizing, so the horizon
#: can be re-chosen against evidence later without anyone having to re-derive what it changes.
REGIME_FORECAST_H = 1
REGIME_TERM_STRUCTURE = (1, 2, 5, 21)


def _log(msg: str) -> None:
    print(f"[{datetime.now(UTC):%H:%M:%S}] {msg}", flush=True)


# ---------------------------------------------------------------------------------------
# EVIDENCE
# ---------------------------------------------------------------------------------------

def build_evidence(*, force: bool = False) -> tuple[pd.DataFrame, dict[str, dict[str, float]]]:
    """The daily-R matrix for every priced sleeve, plus forward days per sleeve.

    Cached to parquet because assembling it costs ~104 s and the 5-minute clock cannot pay that.
    A STALE CACHE IS DECLARED, never silently used as fresh: the artifact carries the cache age so
    a reader can tell a live allocation from one standing on yesterday's matrix (L1.28a).
    """
    CACHE.mkdir(parents=True, exist_ok=True)
    mat = CACHE / "daily_r.parquet"
    age = time.time() - mat.stat().st_mtime if mat.exists() else float("inf")
    if force or age > EVIDENCE_MAX_AGE_S or not mat.exists():
        from research.portfolio_projection import (
            build_daily,
            build_sleeves,
            h18_survivor_sleeves,
        )
        _log("assembling evidence (backtest daily-R over gold book + hunt survivors)")
        sleeves = build_sleeves()
        h18, excluded = h18_survivor_sleeves()
        sleeves += h18
        if excluded:
            _log(f"excluded {len(excluded)} survivor(s) fail-closed")
        daily = build_daily(sleeves)
        daily.index = [str(x) for x in daily.index]
        daily.to_parquet(mat)
        _log(f"evidence rebuilt: {daily.shape[0]} days x {daily.shape[1]} sleeves")
    else:
        daily = pd.read_parquet(mat)
        _log(f"evidence from cache ({age / 60:.0f} min old): {daily.shape}")

    forward: dict[str, dict[str, float]] = {}
    try:
        from research.portfolio_evidence import daily_series
        forward = daily_series()
    except Exception as exc:
        _log(f"forward evidence unavailable ({type(exc).__name__}); backtest basis only")
    return daily, forward


def certified_evidence() -> tuple[dict[str, pd.Series], dict[str, Any]]:
    """Daily-R series for every sleeve that has cleared the ten gates, replayed the gauntlet's way.

    THE DEFECT THIS EXISTS TO FIX, measured 2026-09-02. `portfolio_projection.build_sleeves()`
    prices the gold book and the hunt12 survivors -- 109 sleeves. `UNIVERSAL_SURVIVORS.json`
    holds 63 certificates over 28 distinct sleeves. THE OVERLAP IS ZERO. So the E[log W]
    allocator was solving over a universe that contained none of the things that actually passed
    the ten gates, and "all validated edges compete jointly for capital" was false by
    construction: a certified sleeve could not be funded because it was never priced.

    REPLAYED THROUGH `external_gauntlet.build_cell`, NOT THROUGH A SECOND COPY OF THE LOGIC. That
    function is what turned the spec into signals when the certificate was earned -- same family
    function, same fill-hour spread surface, same `Costs.from_symbol`. A private replay here
    would be a second cost model, and the desk has spent a lot of commits removing those.

    Returns (series by sleeve name, accounting). Every refusal is named: a sleeve that cannot be
    priced is reported, never dropped into a silence that reads like an empty library.
    """
    acct: dict[str, Any] = {"certificates": 0, "priced": 0, "refused": {}}
    try:
        sys.path.insert(0, str(BASE / "scripts"))
        import external_gauntlet as eg  # type: ignore[import-not-found]

        from research.portfolio_gap import load_survivors
    except Exception as exc:
        acct["refused"]["import"] = f"{type(exc).__name__}: {exc}"
        return {}, acct

    try:
        meta = json.loads((BASE / "data" / "universe" / "universe.json").read_text("utf-8"))
    except (OSError, ValueError) as exc:
        acct["refused"]["universe"] = str(exc)
        return {}, acct

    seen: set[tuple[str, str, str]] = set()
    out: dict[str, pd.Series] = {}
    survivors = load_survivors()
    acct["certificates"] = len(survivors)
    for sv in survivors:
        sym, fam, win = sv.get("symbol", ""), sv.get("family", ""), sv.get("window", "")
        if not sym or not fam or (sym, fam, win) in seen:
            continue
        seen.add((sym, fam, win))
        name = f"{sym}_{fam}_{win}" if win else f"{sym}_{fam}"
        try:
            # THE CERTIFICATE'S OWN PARAMS, not defaults. Replaying `{}` runs a different
            # strategy under the certified strategy's name -- the same substitution that put an
            # unconditioned +0.163R behind a conditioned sleeve's +0.276R promotion.
            cell = eg.build_cell(sym, fam, dict(sv.get("params") or {}), meta)
            if not cell or cell.get("sigs") is None:
                acct["refused"][name] = "build_cell returned no signals"
                continue
            ser = eg.daily_series(cell["df"], cell["sigs"], cell["costs"])
            if ser is None or len(ser) < 2:
                acct["refused"][name] = f"replay produced {0 if ser is None else len(ser)} days"
                continue
            # DATE-INDEXED, and that is not cosmetic. `sample_worlds` stacks sleeves by
            # POSITION, so handing it two series on different clocks pairs unrelated days and
            # destroys every correlation in the book. Measured 2026-09-02: unaligned certified
            # series produced a free optimum pinned at the 30% ceiling and a reported 2.8e14%
            # annual growth, because the bootstrap was drawing days that never co-occurred.
            ser.index = pd.to_datetime(pd.Index(ser.index)).date
            out[name] = ser.groupby(level=0).sum()
            acct["priced"] += 1
        except Exception as exc:
            acct["refused"][name] = f"{type(exc).__name__}: {exc}"
    _log(f"certified library: {acct['priced']}/{len(seen)} sleeves priced "
         f"({acct['certificates']} certificates), {len(acct['refused'])} refused")
    return out, acct


def live_days_by_sleeve() -> dict[str, int]:
    """Days of REAL-CAPITAL evidence per sleeve, from the gateway's live ledger.

    Live days outrank forward days outrank backtest days in `_posterior_mu`, so this is what lets
    a sleeve earn size by trading rather than by having been fitted. The ledger was empty until
    2026-09-01 (the gateway required a broker-rewritable comment prefix), so an empty answer here
    is expected for now and is reported as zero live evidence rather than hidden.
    """
    path = BASE / "data" / "live_ledger.jsonl"
    if not path.exists():
        return {}
    days: dict[str, set[str]] = {}
    for line in path.read_text("utf-8").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        name, when = str(row.get("sleeve") or ""), str(row.get("close_time") or "")[:10]
        if name and when:
            days.setdefault(name, set()).add(when)
    return {k: len(v) for k, v in days.items()}


def regime_state(daily: pd.DataFrame,
                 ) -> tuple[tuple[str, ...], tuple[tuple[str, float], ...], dict[str, Any]]:
    """Per-day regime label over the matrix's own clock, and the regime mix to SIZE AGAINST.

    PROBABILITIES, NOT A LABEL. `libs/regime/engine.py` already cross-checks an HMM against a GMM
    and dampens confidence on disagreement; what the allocator needs from it is the POSTERIOR, so
    a book is scored against the mix of worlds the desk believes it is in rather than switched
    wholesale into whichever state the classifier called this minute. A classifier that flickers
    then costs a little weight, not the whole book.

    AND NOT TODAY'S PROBABILITIES EITHER (fixed 2026-09-04). This used the FILTERED posterior --
    P(Z_t | data now) -- so the desk sized a book it holds for days against the regime holding at
    the instant of the solve. `GaussianHMM` has estimated a full transition matrix by Baum-Welch
    since it was written and nothing had ever read it. `libs.regime.transitions` propagates the
    posterior forward `REGIME_FORECAST_H` days through an age-conditioned hazard -- so a trend
    eighteen days old and a trend two days old are no longer given the same chance of surviving --
    and the world population is drawn from THAT distribution.

    THE RISK RESPONSE IS THE OBJECTIVE'S, NOT A KNOB'S. When a transition is likely the forward
    distribution is flatter than the filtered one, so the worlds span more regimes, so E[log W]
    sizes down of its own accord. No entropy multiplier, no hand-set haircut around transitions:
    the uncertainty enters where every other uncertainty on this desk enters.

    STILL FITTED ON XAUUSD DAILY CLOSES, which is a real limitation and not a design: EURUSD can
    be trending while gold ranges. A per-asset regime hierarchy is the next piece of work; this
    function's contract does not change when it arrives. Returns empty tuples when the engine
    cannot fit, in which case `sample_worlds` draws unconditioned worlds and says so.
    """
    diag: dict[str, Any] = {}
    try:
        from libs.regime.engine import RegimeEngine
        from libs.regime.transitions import forecast as regime_forecast

        px = pd.read_parquet(BASE / "data" / "universe" / "XAUUSD_H1.parquet")
        col = next((c for c in ("close", "Close", "c") if c in px.columns), None)
        tcol = next((c for c in ("time", "Time", "datetime") if c in px.columns), None)
        if col is None:
            raise KeyError("no close column on XAUUSD_H1")
        idx = pd.to_datetime(px[tcol] if tcol else px.index, utc=True, errors="coerce")
        close = pd.Series(px[col].to_numpy(dtype=float), index=idx).dropna()
        close = close.groupby(close.index.date).last()
        if close.size < 250:
            raise ValueError(f"only {close.size} daily closes; refusing to fit a regime on that")

        eng = RegimeEngine().fit(close)
        lab = {j: str(ch["label"]) for j, ch in eng.hmm_char.items()}
        by_day = {str(d): lab[int(j)] for d, j in zip(close.index, eng.hmm_states, strict=True)}
        labels = tuple(by_day.get(str(d)[:10], "") for d in daily.index)

        # The filtered posterior is the STARTING point, summed onto LABELS rather than latent
        # state indices because two states can carry the same economic label.
        post = eng.posteriors[-1]
        filtered: dict[str, float] = {}
        for j, pj in enumerate(post):
            filtered[lab[int(j)]] = filtered.get(lab[int(j)], 0.0) + float(pj)

        fc = regime_forecast(eng.hmm.transmat, post, lab, eng.hmm_states,
                             horizons=REGIME_TERM_STRUCTURE)
        raw = dict(fc.p_ahead.get(REGIME_FORECAST_H) or filtered)
        diag = {
            "horizon_days": REGIME_FORECAST_H,
            "filtered_now": {k: round(v, 4) for k, v in filtered.items()},
            "forward": {str(h): {k: round(v, 4) for k, v in d.items()}
                        for h, d in fc.p_ahead.items()},
            "p_leave": {str(h): round(v, 4) for h, v in fc.p_leave.items()},
            "entropy": {str(h): round(v, 4) for h, v in fc.entropy.items()},
            "regime_age_days": fc.age_bars,
            "duration_weight": round(fc.duration_weight, 4),
            "note": fc.note,
        }
        _log(f"regime age={fc.age_bars}d P(leave in {REGIME_FORECAST_H}d)="
             f"{fc.p_leave.get(REGIME_FORECAST_H, float('nan')):.1%} "
             f"entropy={fc.entropy.get(REGIME_FORECAST_H, 0.0):.2f} "
             f"duration_weight={fc.duration_weight:.2f} ({fc.note})")

        # A FILTER POSTERIOR OF 1.0 IS A HARD SWITCH WEARING A PROBABILITY'S CLOTHES, and this
        # engine produces them: measured 2026-09-02 it returned bull/high_vol at 100.0%, which
        # sent every sampled world into one regime's days. The principal's instruction was
        # explicit -- "don't make the regime classifier binary" -- so the raw posterior is
        # tempered three ways before the allocator is allowed to believe it:
        #
        #   1. BLENDED with the empirical frequency of each regime over history, weighted by the
        #      engine's OWN confidence (which it already dampens on HMM/GMM disagreement). A
        #      confident classifier keeps its posterior; an uncertain one falls back to how often
        #      each regime actually occurs.
        #   2. FLOORED, so no regime with enough history is ever assigned zero worlds. The desk
        #      is never certain it is not in a regime.
        #   3. CAPPED, so no single regime may own more than REGIME_MAX_SHARE of the worlds. This
        #      is the one that stops a 100% posterior from becoming a 100% world population.
        freq: dict[str, float] = {}
        for v in by_day.values():
            freq[v] = freq.get(v, 0.0) + 1.0
        tot = sum(freq.values()) or 1.0
        freq = {k: v / tot for k, v in freq.items()}
        conf = float(str(eng.current().get("confidence") or 0.0))
        keys = sorted(set(raw) | set(freq))
        probs = {k: conf * raw.get(k, 0.0) + (1.0 - conf) * freq.get(k, 0.0) for k in keys}
        probs = {k: max(v, REGIME_MIN_SHARE) for k, v in probs.items()}
        tot = sum(probs.values()) or 1.0
        probs = {k: v / tot for k, v in probs.items()}
        if max(probs.values()) > REGIME_MAX_SHARE:
            top = max(probs, key=lambda k: probs[k])
            spill = probs[top] - REGIME_MAX_SHARE
            rest = sum(v for k, v in probs.items() if k != top) or 1.0
            probs = {k: (REGIME_MAX_SHARE if k == top else v + spill * v / rest)
                     for k, v in probs.items()}
        _log(f"regime forward({REGIME_FORECAST_H}d)="
             f"{ {k: round(v, 3) for k, v in raw.items()} } conf={conf:.2f} "
             f"-> used={ {k: round(v, 3) for k, v in probs.items()} }")
        diag["used"] = {k: round(v, 4) for k, v in probs.items()}
        diag["engine_confidence"] = round(conf, 4)
        covered = sum(1 for x in labels if x)
        if covered < 0.5 * len(labels):
            _log(f"regime labels cover only {covered}/{len(labels)} matrix days; unconditioned")
            diag["unconditioned_because"] = f"labels cover {covered}/{len(labels)} matrix days"
            return (), (), diag
        return labels, tuple(sorted(probs.items(), key=lambda kv: -kv[1])), diag
    except Exception as exc:
        _log(f"regime engine unavailable ({type(exc).__name__}: {exc}); worlds are unconditioned")
        diag["unconditioned_because"] = f"{type(exc).__name__}: {exc}"
    return (), (), diag


def join_forward(columns: list[str], forward: dict[str, dict[str, float]],
                 ) -> tuple[dict[str, dict[str, float]], dict[str, Any]]:
    """Attribute forward series to priced sleeves, and ACCOUNT for the ones that cannot be.

    THE TWO SIDES KEY DIFFERENTLY. The forward clocks record `<symbol>_<window>` (sometimes with a
    family in the middle: `CHFNOK_carry_asia`); the backtest matrix records
    `<symbol>_<window>_<state>`. Measured 2026-09-02: 20 sleeves carried forward evidence and the
    allocator reported `with_forward: 0`, because nothing joined and a failed join returns the
    same empty dict as "no forward evidence exists". That is the silent-zero class this desk has
    a law about (L1.28a) -- absence is never health.

    AMBIGUOUS JOINS ARE REFUSED, NOT SPREAD. `CADJPY_asia` matches CADJPY_asia_TREND_DAY,
    _NORMAL_DAY and _RANGE_DAY. Those forward trades were taken UNCONDITIONED, so attributing
    them to a state-conditioned sleeve would append the returns of a strategy the sleeve does not
    run -- the exact substitution that produced +0.163R-unconditioned against the +0.276R that
    earned promotion. Appending to all three would additionally count one day of evidence three
    times. Both are refused; the count is reported so the mismatch is visible.

    Returns (attributed series by column name, accounting).
    """
    exact = {c: forward[c] for c in columns if c in forward}
    unmatched, ambiguous = {}, {}
    for name, series in forward.items():
        if name in exact:
            continue
        hits = [c for c in columns if c == name or c.startswith(name + "_")]
        if len(hits) == 1:
            exact[hits[0]] = series
        elif hits:
            ambiguous[name] = [str(h) for h in hits]
        else:
            unmatched[name] = len(series)
    acct = {
        "forward_series_seen": len(forward),
        "attributed": len(exact),
        "ambiguous_state_variants": ambiguous,
        "no_priced_sleeve": unmatched,
        "note": ("forward clocks key on (symbol, window); the matrix keys on "
                 "(symbol, window, state). Unattributed forward evidence cannot inform "
                 "allocation and is NOT counted as zero evidence -- it is counted as unjoined."),
    }
    if ambiguous or unmatched:
        _log(f"forward join: {len(exact)}/{len(forward)} attributed, "
             f"{len(ambiguous)} ambiguous, {len(unmatched)} name no priced sleeve")
    return exact, acct


def align(daily: pd.DataFrame, certified: dict[str, pd.Series] | None) -> pd.DataFrame:
    """One matrix, one clock. Every sleeve reindexed onto the union of trading days.

    A sleeve that did not trade on a day contributes 0.0 THAT DAY -- which is what actually
    happened -- so the bootstrap draws days on which the whole book's real behaviour co-occurs.
    Without this, sleeves are stacked by POSITION and the resampler pairs a gold Tuesday with an
    EURNOK Thursday, manufacturing diversification that does not exist. Measured 2026-09-02 on
    the first unioned run: a free optimum pinned at the 30% ceiling, a book of seven exotic
    crosses, and a reported annual growth rate of 2.8e14 percent.
    """
    if not certified:
        return daily
    frames = {str(c): daily[c] for c in daily.columns}
    for name, ser in certified.items():
        s = pd.Series(ser.to_numpy(dtype=float), index=[str(d) for d in ser.index])
        if name not in frames or int(s.notna().sum()) > int(frames[name].notna().sum()):
            frames[name] = s
    idx = sorted({str(i) for f in frames.values() for i in f.index})
    return pd.DataFrame({k: v.groupby(level=0).sum().reindex(idx) for k, v in frames.items()},
                        index=idx, dtype=float)


def search_trials() -> dict[str, int]:
    """Trials each hunt searched, from the desk's own gate reports. The winner's-curse input.

    `QQUANT_GATES.json` records n_trials per hunt (hunt12: 2,023; hunt16: 3,001) and
    `universal_gates_external.json` records the external campaign's. These are the numbers the
    `deflated_sharpe` gate already uses to decide WHETHER a sleeve is real; the allocator uses
    them to decide how much of its measured edge to bet on. Absent report = 1 trial, i.e. no
    deflation -- which is the conservative direction for the GATE and the aggressive one here, so
    it is reported rather than assumed away.
    """
    out: dict[str, int] = {}
    for f, key in ((BASE / "reports" / "QQUANT_GATES.json", "n_trials"),
                   (BASE / "reports" / "universal_gates_external.json", "n_trials")):
        try:
            doc = json.loads(f.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        v = doc.get(key)
        if isinstance(v, dict):
            out.update({str(k): int(n) for k, n in v.items() if isinstance(n, (int, float))})
        elif isinstance(v, (int, float)):
            out["external"] = int(v)
    return out


def sleeve_evidence(daily: pd.DataFrame, forward: dict[str, dict[str, float]],
                    live: dict[str, int],
                    trials: dict[str, int] | None = None,
                    phase: str | None = None,
                    trades_by_sleeve: dict[str, list[dict]] | None = None,
                    broker_utc_offset_h: int = 0) -> list[SleeveEvidence]:
    """Fold backtest, certified, forward and live evidence into one record per sleeve.

    THE UNIVERSE IS THE UNION, which is the whole point. The backtest matrix (gold book + hunt12
    survivors) and the certified library (what cleared the ten gates) were disjoint sets, so
    whichever one the allocator read, it could not fund the other. Both are priced here, on the
    same daily clock, and compete for the same heat.

    Forward days are APPENDED to the series, not averaged into it: they are additional
    observations of the same sleeve, and the posterior weights them 4x (live 12x) precisely
    because they are the only ones the sleeve could not have been selected on.
    """
    out: list[SleeveEvidence] = []
    series: dict[str, np.ndarray] = {
        str(c): daily[c].fillna(0.0).to_numpy(dtype=float) for c in daily.columns
    }
    for name, hist in series.items():
        fwd = forward.get(name, {})
        if fwd:
            hist = np.concatenate([hist, np.array(list(fwd.values()), dtype=float)])
        parts = name.split("_")
        # FAMILY IS THE MECHANISM, NOT THE SYMBOL. The hierarchical posterior pools a sleeve
        # toward its family mean, and pooling by SYMBOL pools EURJPY_asia_TREND with
        # EURJPY_london_NORMAL -- two different mechanisms that happen to share an instrument --
        # while leaving every session_range_breakout sleeve in a family of one. The mechanism is
        # what shares a prior; the instrument is what shares a correlation, and correlation is
        # handled by the worlds.
        fam = ("session_bracket" if name.startswith("gold_") or parts[-1].endswith("_DAY")
               or (len(parts) > 2 and parts[-1] in ("TREND", "NORMAL", "RANGE"))
               else "_".join(parts[1:-1]) or "unspecified")
        # WHICH SEARCH FOUND IT decides how hard its mean is deflated. A session-bracket sleeve
        # came out of the hunt12/hunt16 grid; a certified external sleeve came out of the
        # external campaign. Unknown provenance takes the LARGEST known trial count rather than
        # the smallest: an unattributable sleeve must not be the least-deflated thing in the book
        # (L1.28a), which is the same rule cap_by_heat applies to an unpriceable one.
        tr = trials or {}
        n_trials = (max(tr.get("hunt12", 1), tr.get("hunt16", 1)) if fam == "session_bracket"
                    else tr.get("external", max(tr.values()) if tr else 1))
        out.append(SleeveEvidence(
            name=name, daily_r=hist, family=fam, symbol=parts[0], n_trials=int(n_trials),
            forward_days=len(fwd), live_days=int(live.get(name, 0)),
            # Cost LEVEL is already inside the replayed R multiples (Costs.from_symbol at the
            # honest 2x baseline); this is the per-trade scale used to size the UNCERTAINTY
            # around it, never a second charge.
            cost_r=0.05,
            # THE HOUR, AS THE NARROWEST LEVEL OF A SHRINKAGE THAT ALREADY EXISTED. Empty unless
            # a phase and this sleeve's own trades were supplied, and empty means the posterior
            # behaves exactly as it did before -- a caller that does not know the hour is not
            # penalised for saying so. `_posterior_mu` shrinks this at k=40, so a six-trade
            # bucket moves the estimate slightly and forty move it fully.
            state_r=_state_returns(name, phase, trades_by_sleeve, broker_utc_offset_h),
            state_key=phase or "",
        ))
    return out


def _state_returns(name: str, phase: str | None,
                   trades_by_sleeve: dict[str, list[dict]] | None,
                   broker_utc_offset_h: int) -> np.ndarray:
    """This sleeve's realised R for trades entered in `phase`, or empty when unknown.

    Returns EMPTY rather than zeros on every failure path. A zero-filled state series would read
    to the posterior as measured evidence of no edge at this hour, which is a claim; absence is
    not, and the unconditional mean is the honest answer when the hour is unknown.
    """
    if not phase or not trades_by_sleeve:
        return np.array([], dtype=float)
    rows = trades_by_sleeve.get(name)
    if not rows:
        return np.array([], dtype=float)
    try:
        from session_phase import returns_in_phase
        return returns_in_phase(rows, phase, broker_utc_offset_h=broker_utc_offset_h)
    except Exception as exc:                                        # noqa: BLE001
        _log(f"state conditioning unavailable for {name}: {type(exc).__name__}: {exc}")
        return np.array([], dtype=float)


def worst_dd_r(daily: pd.DataFrame) -> dict[str, float]:
    """Each sleeve's worst peak-to-trough drawdown in R -- the input to its per-sleeve bound.

    An UNMEASURED drawdown is reported as 0.0 and `heat_policy.per_sleeve_bounds` treats that as
    the armed book's own worst (33.7R), so a sleeve nobody has measured is bounded as tightly as
    the most-measured one rather than as loosely as a flawless one.
    """
    out: dict[str, float] = {}
    cols: dict[str, np.ndarray] = {
        str(c): daily[c].fillna(0.0).to_numpy(dtype=float) for c in daily.columns
    }
    for name, arr in cols.items():
        eq = np.cumsum(arr)
        dd = np.maximum.accumulate(eq) - eq if eq.size else np.array([0.0])
        out[name] = float(dd.max()) if dd.size else 0.0
    return out


# ---------------------------------------------------------------------------------------
# SOLVE
# ---------------------------------------------------------------------------------------

def growth_curve(ev: list[SleeveEvidence], worlds: Worlds, bounds: dict[str, float],
                 cfg: WorldConfig) -> dict[float, float]:
    """Mean log growth of the OPTIMALLY COMPOSED book at each total heat on the grid.

    This is the curve `heat_policy.certify` reads, and it must be measured with the same
    per-sleeve bounds the desk will actually run: without them the optimiser answers the mandate
    by parking heat in the flattest sleeve it can find, and the curve comes out flat because the
    surplus was never really deployed. A certification measured on an unconstrained solve
    certifies a book nobody would run.
    """
    curve: dict[float, float] = {}
    for h in CURVE_GRID:
        if h > HEAT_HARD_CEILING:
            continue
        ub = {k: min(v, h) for k, v in bounds.items()}
        if sum(ub.values()) < h:
            continue                     # bounds cannot fund this heat; not a growth finding
        try:
            r = optimise(ev, hard_cap=HEAT_HARD_CEILING, target=h, cfg=cfg, worlds=worlds,
                         max_per_sleeve=ub)
        except ValueError:
            continue
        if math.isfinite(r.mean_log_growth):
            curve[h] = r.mean_log_growth
    return curve


def no_trade(current: dict[str, float], proposed: dict[str, float],
             gain_per_day: float) -> dict[str, Any]:
    """Is the move worth its own cost? Returns the verdict and the arithmetic behind it.

    "Don't rebalance simply because the optimizer ran." Turnover is charged at a round trip on
    every unit of heat that moves, and the move only happens when the growth it buys over
    `NO_TRADE_HORIZON_DAYS` exceeds that. This is what lets the allocator recompute every fifteen
    minutes and still trade twice a day.
    """
    names = set(current) | set(proposed)
    moved = {n: proposed.get(n, 0.0) - current.get(n, 0.0) for n in names}
    turnover = 0.5 * sum(abs(v) for v in moved.values())
    cost = turnover * TURNOVER_COST_R
    benefit = max(gain_per_day, 0.0) * NO_TRADE_HORIZON_DAYS
    go = benefit > cost
    return {
        "verdict": "REBALANCE" if go else "NO CHANGE",
        "turnover": round(turnover, 6),
        "cost": round(cost, 8),
        "benefit_over_horizon": round(benefit, 8),
        "horizon_days": NO_TRADE_HORIZON_DAYS,
        "largest_moves": dict(sorted(((k, round(v, 5)) for k, v in moved.items() if abs(v) > 1e-5),
                                     key=lambda kv: -abs(kv[1]))[:12]),
    }


def current_book() -> dict[str, float]:
    """What the desk is running now, in heat -- the baseline the no-trade filter measures against.

    Read from the previous allocation when there is one, else from the gateway's own sleeve set
    priced at Q_OPT. NOT from a list in this file: a second opinion about what is live is the
    exact drift this whole module exists to remove.
    """
    if OUT.exists():
        try:
            prev = json.loads(OUT.read_text("utf-8"))
            book = prev.get("book")
            if isinstance(book, dict) and book:
                return {str(k): float(v) for k, v in book.items()}
        except (OSError, ValueError):
            pass
    try:
        from mt5desk.gateway import sleeve_set
        from mt5desk.gateway_config_fallback import Q_OPT
        return {str(s["name"]): float(Q_OPT) for s in sleeve_set()}
    except Exception:
        try:
            from mt5desk.gateway_config_fallback import Q_OPT

            from research.promoter import GOLD_SLEEVE_NAMES, _load_gold_retired
            retired = set(_load_gold_retired())
            return {n: float(Q_OPT) for n in GOLD_SLEEVE_NAMES if n not in retired}
        except Exception:
            return {}


def opportunity(free: AllocationResult, book: dict[str, float],
                target: float) -> dict[str, Any]:
    """Opportunity density and the heat gap -- what research is asked to go and find.

    OD = sum of POSITIVE marginal dE[log W] across the eligible library. High OD means many
    independent things are worth betting on and a large budget is fillable; low OD means the
    honest answer to "why is the book not at target" is that the world is not currently offering
    twenty percent of independent edge, and that is a RESEARCH REQUEST, not a risk decision.

    The gap is expressed by session and family so the crawler has somewhere to point: a gap that
    says "4% unfilled" is a number, and one that says "4% unfilled, nothing in the Asia session
    outside JPY" is a search.
    """
    pos = {k: v for k, v in free.marginal.items() if v > 0}
    od = float(sum(pos.values()))
    funded = {k for k, v in book.items() if v > 1e-5}
    gap = max(target - sum(book.values()), 0.0)
    by_session: dict[str, float] = {}
    by_family: dict[str, float] = {}
    for name, mv in pos.items():
        parts = str(name).split("_")
        sess = parts[1] if len(parts) > 2 else (parts[0] if name.startswith("gold") else "?")
        by_session[sess] = by_session.get(sess, 0.0) + mv
        by_family[parts[0]] = by_family.get(parts[0], 0.0) + mv
    return {
        "opportunity_density": round(od, 6),
        "n_positive_marginal": len(pos),
        "n_funded": len(funded),
        "heat_gap": round(gap, 6),
        "positive_marginal_by_session": {k: round(v, 6) for k, v in
                                         sorted(by_session.items(), key=lambda kv: -kv[1])},
        "positive_marginal_by_family": {k: round(v, 6) for k, v in
                                        sorted(by_family.items(), key=lambda kv: -kv[1])[:15]},
        "research_request": ([] if gap <= 1e-6 else
                             [f"{gap:.2%} of the heat target is unfundable by the current "
                              f"library at its per-sleeve bounds"]),
    }


# ---------------------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------------------


def _live_state() -> tuple[str | None, dict[str, list[dict]], int]:
    """The phase now, each sleeve's own trades, and the broker's clock offset.

    RETURNS (None, {}, 0) ON ANY DOUBT, and that is the whole safety property: an unknown state
    yields an EMPTY conditional series, which `_posterior_mu` treats exactly as it treated every
    solve before conditioning existed. A wrong phase would be worse than no phase -- it would
    price every sleeve against an hour the desk is not in -- so nothing here guesses.

    THE OFFSET IS READ, NEVER ASSUMED. The desk measured its own feed at broker EET, three hours
    ahead of UTC in summer (mt5desk/families.py `_h1`, 2026-08-29). A hardcoded 0 would mislabel
    every bucket by three hours without raising anything, so when the live terminal cannot be
    asked the answer is "no state", not "assume UTC".
    """
    try:
        from datetime import datetime as _dt

        from session_phase import phase_at
    except ImportError as exc:
        _log(f"state: session_phase unavailable ({exc}); solving unconditioned")
        return None, {}, 0

    # Live terminal, then the recorded measurement, then nothing. The rule lives in
    # `session_phase` so the state-vector builder resolves the SAME clock this does; two answers
    # to "what time does the broker think it is" is how a cell gets certified in one clock and
    # traded in another.
    from session_phase import broker_utc_offset_h
    off, off_source = broker_utc_offset_h()
    if off is None:
        _log("state: broker UTC offset unknown -- solving unconditioned rather than assuming UTC")
        return None, {}, 0

    phase = phase_at(_dt.now(UTC), broker_utc_offset_h=off)

    # PER-SLEEVE TRADES, KEYED THE WAY THE BOOK IS KEYED. The shadow ledgers are
    # ledger_<SYM>_<window>.json and the allocator's columns are the sleeve names, so the join is
    # on the file stem. A ledger that does not match a column is simply unused -- never merged
    # into a neighbouring sleeve, which would attribute one edge's hours to another.
    trades: dict[str, list[dict]] = {}
    for d in (BASE / "reports" / "shadow", ROOT / "backups" / "moat" / "shadow_ledgers"):
        if not d.is_dir():
            continue
        for f in sorted(d.glob("ledger_*.json")):
            try:
                rows = json.loads(f.read_text("utf-8"))
            except Exception:                                        # noqa: BLE001
                continue
            if isinstance(rows, list) and rows:
                trades.setdefault(f.stem[len("ledger_"):], []).extend(
                    r for r in rows if isinstance(r, dict) and "r_multiple" in r)
    return phase, trades, off


def run(mode: str = "normal", *, seed: int = 0) -> dict[str, Any]:
    """One allocator pass. Returns the artifact it wrote."""
    t0 = time.time()
    heavy = mode == "heavy"
    daily, forward = build_evidence(force=heavy)
    live = live_days_by_sleeve()
    certified, cert_acct = certified_evidence()
    daily = align(daily, certified)
    _log(f"aligned universe: {daily.shape[1]} sleeves on {daily.shape[0]} trading days")
    forward, fwd_acct = join_forward([str(c) for c in daily.columns], forward)
    trials = search_trials()
    _log(f"search intensity for deflation: {trials or 'UNMEASURED (no deflation applied)'}")
    # ------------------------------------------------ THE STATE THE BOOK IS BEING SOLVED FOR
    # THE MATHEMATICS WAS WIRED AND THE CALL WAS NOT. `sleeve_evidence` grew `phase` and
    # `trades_by_sleeve`, and `_posterior_mu` grew the state level of its hierarchy -- and this
    # line still passed neither, so every solve ran on an empty state and the conditioning was
    # arithmetic nobody reached. "It is London open, therefore this posterior" was true in the
    # library and false in production, which is the desk's most repeated defect wearing new code.
    phase, trades_by_sleeve, broker_off = _live_state()
    _log(f"state: phase={phase or 'UNKNOWN'} broker_utc_offset={broker_off:+d}h "
         f"sleeves_with_trades={len(trades_by_sleeve)}")
    ev = sleeve_evidence(daily, forward, live, trials, phase=phase,
                         trades_by_sleeve=trades_by_sleeve, broker_utc_offset_h=broker_off)
    dd = worst_dd_r(daily)

    # THE STATE VECTOR ENTERS AS INFORMATION, NOT AS AUTHORITY. `state_vector_build` fits the
    # per-asset, per-factor and per-clock states the hourly cycle can afford and this reads the
    # artifact in milliseconds. It is RECORDED here and its id is available to stamp on orders;
    # what draws the scenario worlds is still the global regime below, unchanged. A new state
    # dimension takes capital authority by improving calibration or marginal E[log W] against the
    # existing gates -- never by being plausible, and never in the change that introduces it.
    state_vec, sv_why = (None, "not read on the fast clock")
    if mode in ("heavy", "normal"):
        try:
            from state_vector_build import load as _load_sv
            state_vec, sv_why = _load_sv()
        except Exception as exc:                                     # noqa: BLE001
            state_vec, sv_why = None, f"{type(exc).__name__}: {exc}"
        _log(f"state vector: {sv_why}")

    labels, probs, regime_diag = (regime_state(daily) if mode in ("heavy", "normal")
                                  else ((), (), {"skipped": f"{mode} clock"}))
    # CRISIS SEVERITY, MEASURED RATHER THAN ASSUMED. `crisis_common_share` IS the pairwise
    # correlation the crisis worlds impose (a one-factor overlay with share s has pairwise
    # correlation exactly s), and it was the constant 0.55 with nothing behind it. The book's own
    # return matrix can be asked. The calibration RATCHETS ONLY UPWARD: a quiet sample never
    # licenses modelling crises as gentler than the standing assumption, because that is how a
    # book finds out its real correlations at the worst possible moment.
    cov_cal = None
    try:
        from libs.portfolio.conditional_covariance import calibrate as _calibrate_cov
        _base = WorldConfig()
        _hist = daily.to_numpy(dtype=float)
        cov_cal = _calibrate_cov(_hist, labels or None,
                                 standing_share=_base.crisis_common_share,
                                 standing_vol_mult=_base.crisis_vol_mult)
        _log(f"crisis calibration: common_share={cov_cal.crisis_common_share:.3f} "
             f"vol_mult={cov_cal.crisis_vol_mult:.2f} ({cov_cal.note})")
    except Exception as exc:                                         # noqa: BLE001
        _log(f"crisis calibration unavailable ({type(exc).__name__}: {exc}); constants stand")

    cfg = WorldConfig(seed=seed, regime_labels=labels, regime_probs=probs,
                      # The fast clock buys its speed here and nowhere else: a smaller world
                      # population, never a shortcut through the posterior or the crisis worlds.
                      n_worlds=256 if heavy else 128,
                      n_rows=384 if heavy else 256,
                      **(cov_cal.as_overrides() if cov_cal else {}))

    cachef = CACHE / "worlds.npz"
    worlds: Worlds | None = None
    if mode == "fast" and cachef.exists() and time.time() - cachef.stat().st_mtime < 3600:
        try:
            z = np.load(cachef, allow_pickle=False)
            if tuple(z["names"]) == tuple(e.name for e in ev):
                worlds = Worlds(r=z["r"], names=tuple(str(x) for x in z["names"]),
                                crisis=z["crisis"], mu_draws=z["mu"],
                                note="reused cached world population")
                _log("world population reused from cache")
        except (OSError, ValueError, KeyError):
            worlds = None
    if worlds is None:
        worlds = sample_worlds(ev, cfg)
        _log(f"worlds {worlds.r.shape} crisis={int(worlds.crisis.sum())} {worlds.note}")
        try:
            CACHE.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(cachef, r=worlds.r, names=np.array(worlds.names),
                                crisis=worlds.crisis, mu=worlds.mu_draws)
        except OSError as exc:
            _log(f"world cache not written ({exc}); next fast pass will resample")

    # 1. WHAT GROWTH ACTUALLY WANTS -- no mandate, no floor. This number certifies the target.
    bounds = per_sleeve_bounds(dd, HEAT_TARGET)
    free = optimise(ev, hard_cap=HEAT_HARD_CEILING, target=None, cfg=cfg, worlds=worlds,
                    max_per_sleeve=bounds)
    _log(f"free optimum H*={free.total_heat:.2%} ann={free.annual_growth_pct:.1f}% "
         f"P(annual loss)={free.prob_annual_loss:.1%}")
    # A SANITY FENCE, NOT A CAP. Nothing in this desk's history compounds at four figures a year;
    # a number that large is a broken input, and the one that produced 2.8e14% was sleeves stacked
    # on mismatched date clocks. The fence does not clip the number -- clipping would hide the
    # defect behind a plausible-looking answer -- it refuses the whole pass.
    implausible = free.annual_growth_pct > IMPLAUSIBLE_ANNUAL_PCT
    if implausible:
        _log(f"REFUSING THIS PASS: free optimum reports {free.annual_growth_pct:.3g}% a year, "
             f"above the {IMPLAUSIBLE_ANNUAL_PCT:.0f}% plausibility fence. That is an input "
             f"defect, not an opportunity. The previous book stands.")

    # 2. THE CURVE, then the law.
    curve = growth_curve(ev, worlds, bounds, cfg) if heavy else {}
    if not curve and OUT.exists():
        try:                                    # a fast pass inherits the last heavy curve
            prev = json.loads(OUT.read_text("utf-8")).get("heat", {}).get("curve") or []
            curve = {float(h): float(g) for h, g in prev}
        except (OSError, ValueError, TypeError):
            curve = {}
    # READINESS: THE TARGET IS EARNED, NOT ASSERTED (principal, 2026-09-02 -- "once we have a
    # good amount of live edges it should increase to 20 percent itself daily ... and once it
    # earns it, it forces full 20 percent allocation every hour"). Out-of-sample day-equivalents
    # per sleeve, weighted by the heat the FREE solve wants to give it, because the question is
    # about the capital and not the roster. At readiness 1.0 the floor IS the target and every
    # pass enforces it; below that the desk bets what its evidence supports and the gap is a
    # research request rather than a number someone decided to force.
    oos = {e.name: 4.0 * e.forward_days + 12.0 * e.live_days for e in ev}
    ready, ready_why = evidence_readiness(oos, free.heat)
    _log(f"readiness {ready:.1%} -- {ready_why}")
    verdict = resolve(free.total_heat, curve=curve, target=HEAT_TARGET,
                      hard_ceiling=HEAT_HARD_CEILING, mandate=True,
                      readiness=ready, readiness_why=ready_why,
                      allocator_ok=(bool(free.heat) and math.isfinite(free.mean_log_growth)
                                    and not implausible))
    for why in verdict.reasons:
        _log(why)

    # 3. THE BOOK, at the heat the law resolved.
    fam_share: dict[str, float] = {}
    if verdict.total_heat <= 0:
        book = AllocationResult(heat={}, total_heat=0.0, robust_score=0.0, mean_log_growth=0.0,
                                cvar_log_growth=0.0, annual_growth_pct=0.0, prob_annual_loss=0.0,
                                note="catastrophe guard: no heat")
    else:
        ub = {k: min(v, verdict.total_heat) for k, v in
              per_sleeve_bounds(dd, verdict.total_heat).items()}
        book = optimise(ev, hard_cap=HEAT_HARD_CEILING, target=verdict.total_heat, cfg=cfg,
                        worlds=worlds, max_per_sleeve=ub,
                        warm_start=current_book() or None)

        # MECHANISM CONCENTRATION, enforced by re-solving under tightened bounds rather than
        # priced. Measured 2026-09-02 the first solved book held 97% of its heat in one family;
        # the redundancy term could not see it, because those sleeves are weakly correlated day
        # to day while sharing a mechanism and a 01:00 fill hour. Two passes converge: the cap
        # scales the offending family's members proportionally, the optimiser re-spends what it
        # frees on everything else, and a family already inside the cap is never touched.
        family_of = {e.name: e.family for e in ev}
        for _pass in range(2):
            capped = enforce_family_cap(book.heat, family_of, book.total_heat)
            if all(math.isinf(v) for v in capped.values()):
                break                                   # every mechanism already inside the cap
            tight = {k: min(ub.get(k, math.inf), capped.get(k, math.inf)) for k in ub}
            book = optimise(ev, hard_cap=HEAT_HARD_CEILING, target=verdict.total_heat, cfg=cfg,
                            worlds=worlds, max_per_sleeve=tight, warm_start=book.heat or None)
        for name, h in book.heat.items():
            if h > 1e-6:
                fam = family_of.get(name, "?")
                fam_share[fam] = fam_share.get(fam, 0.0) + h
        if fam_share:
            top = max(fam_share.items(), key=lambda kv: kv[1])
            _log(f"mechanism mix: {len(fam_share)} family(ies), largest {top[0]} at "
                 f"{top[1] / max(book.total_heat, 1e-9):.0%} of the book")
    funded = {k: round(v, 6) for k, v in book.heat.items() if v > 1e-5}

    # A BOOK THE OPTIMISER CANNOT SCORE IS NOT A BOOK. The mandated solve can come back -inf --
    # a book that is wiped out in at least one sampled world -- and publishing that would hand
    # `gateway.allocator_heat()` a total heat with no growth behind it. Measured 2026-09-02: the
    # first unioned run published exactly that, 30% heat across seven exotic crosses with
    # annual_growth_pct = -inf. It routes to the catastrophe layer, which is the only thing
    # allowed to take exposure below target.
    if not math.isfinite(book.mean_log_growth) and book.total_heat > 0:
        _log(f"RESOLVED BOOK IS RUINOUS at {book.total_heat:.2%}: at least one sampled world "
             f"wipes it out. Publishing zero heat and the reason, not the book.")
        verdict = resolve(free.total_heat, curve=curve, target=HEAT_TARGET,
                          hard_ceiling=HEAT_HARD_CEILING, mandate=True, allocator_ok=False)
        book = AllocationResult(heat={}, total_heat=0.0, robust_score=0.0, mean_log_growth=0.0,
                                cvar_log_growth=0.0, annual_growth_pct=0.0,
                                prob_annual_loss=0.0,
                                note="mandated book was ruinous on the sampled worlds")
        funded = {}

    # DID THE MANDATE ACTUALLY FILL? Once readiness earns the target the floor is a standing
    # instruction, so a pass that lands short is a defect and not a preference. Only the
    # catastrophe layer may resolve below it, and it says so in `binding`; anything else short is
    # the per-sleeve bounds failing to fund the budget, which is a research gap
    # (portfolio_gap.py) and must never read as a quiet risk decision.
    shortfall = verdict.total_heat - book.total_heat
    filled = abs(shortfall) <= 1e-4
    if not filled and verdict.binding != "catastrophe":
        _log(f"HEAT NOT FILLED: resolved {verdict.total_heat:.2%}, book holds "
             f"{book.total_heat:.2%} ({shortfall:+.2%}). The eligible library cannot fund the "
             f"budget under its per-sleeve bounds -- a research gap, not a risk choice.")

    _log(f"book: {len(funded)} funded sleeves at {book.total_heat:.2%} total heat, "
         f"ann={book.annual_growth_pct:.1f}% [{'FILLED' if filled else 'SHORT'}]")

    # THE BASELINE IS WHAT THE DESK HOLDS, not the free optimum. Measuring the proposal against
    # the unconstrained solve answers "how far from ideal is this", which is a different question
    # from "is moving worth the turnover" and gave the no-trade filter a meaningless number.
    prev_book = current_book()
    held = score_book(ev, prev_book, cfg=cfg, worlds=worlds)
    gain = (book.mean_log_growth - held["mean_log_growth"]
            if math.isfinite(held["mean_log_growth"]) and math.isfinite(book.mean_log_growth)
            # A currently-ruinous book has no growth rate to improve on, and refusing to move off
            # it because the arithmetic is undefined would be the worst possible reading.
            else float("inf"))
    nt = no_trade(prev_book, funded, gain)
    nt["held"] = {k: round(v, 8) for k, v in held.items()}
    opp = opportunity(free, funded, HEAT_TARGET)

    # ------------------------------------------------------ THE BASELINE CONTEST, EVERY PASS
    # A dynamic allocator sits above every edge and reallocates, so it can destroy compounding
    # faster than any single sleeve can. It therefore has to beat the answers anyone could have
    # written in an afternoon -- equal weight, inverse vol, risk parity, and doing nothing --
    # on THESE worlds, at EQUAL total heat, before it is allowed to size a position.
    # The gateway reads the certificate this writes; without a fresh passing one it keeps
    # ranking with the optimiser and sizing with Q_OPT exactly as it does today.
    try:
        from libs.portfolio.allocator_proof import certify, contest
        proof = contest(ev, funded, current_book(), cfg=cfg, worlds=worlds)
        certify(proof, root=ROOT, book=funded)
        _log(f"proof: {'PASS' if proof['passed'] else 'FAIL'} -- {proof['why']}")
    except Exception as exc:                                        # noqa: BLE001
        # A failed contest must never take the allocation pass with it: the book is still worth
        # publishing for ranking and total heat. What it loses is the right to SIZE, which is
        # exactly the fail-closed direction.
        proof = {"passed": False, "why": f"{type(exc).__name__}: {exc}"}
        _log(f"proof: FAILED TO RUN -- {proof['why']}")

    art: dict[str, Any] = {
        "generated_utc": datetime.now(UTC).isoformat(),
        "mode": mode,
        "elapsed_s": round(time.time() - t0, 1),
        "armed": ARMED.exists(),
        "advisory": not ARMED.exists(),
        "heat": {
            "total": round(verdict.total_heat, 6),
            "free_optimum": round(verdict.free_optimum, 6),
            "target": verdict.target, "hard_ceiling": verdict.hard_ceiling,
            "binding": verdict.binding, "certified": verdict.certified,
            "filled": filled, "shortfall": round(shortfall, 6),
            "readiness": round(verdict.readiness, 4), "floor": round(verdict.floor, 6),
            "readiness_why": ready_why,
            "reasons": list(verdict.reasons),
            "curve": [[round(h, 4), round(g, 8)] for h, g in sorted(curve.items())],
        },
        "book": funded,
        "proof": {"passed": bool(proof.get("passed")), "why": proof.get("why", ""),
                  "best_baseline": proof.get("best_baseline", "")},
        # WHICH MECHANISMS HOLD THE BOOK. A single-family book is a single bet however many
        # sleeves it is spread across, and that is invisible from the sleeve list alone.
        "mechanism_mix": {k: round(v, 6)
                          for k, v in sorted(fam_share.items(), key=lambda kv: -kv[1])},
        "marginal_delta_elog": book.marginal,
        "growth": {
            "annual_growth_pct": book.annual_growth_pct,
            "mean_log_per_day": round(book.mean_log_growth, 8),
            "cvar_log_per_day": round(book.cvar_log_growth, 8),
            "prob_annual_loss": book.prob_annual_loss,
            "robust_score": round(book.robust_score, 8),
            "free_annual_growth_pct": free.annual_growth_pct,
        },
        "no_trade": nt,
        "opportunity": opp,
        # `probabilities` is the FORWARD mix the worlds were drawn from; `transition` carries the
        # filtered posterior beside it, so the two can never be confused by a later reader and
        # the size of the forward adjustment is always visible rather than inferred.
        "regime": {"probabilities": dict(probs), "conditioned": bool(labels),
                   "transition": regime_diag},
        # The world as the desk described it when this book was solved. `state_vector_id` is what
        # ties a fill, weeks later, back to the conditions the decision was made under.
        "state_vector": ({"id": state_vec.id, "at": state_vec.at, "why": sv_why,
                          **state_vec.to_dict()} if state_vec is not None
                         else {"id": None, "why": sv_why}),
        # What the crisis worlds assumed, and the measurement behind it. Recorded so the
        # correlation the book is being stressed at is a number anyone can check.
        "crisis_calibration": ({
            "crisis_common_share": cov_cal.crisis_common_share,
            "crisis_vol_mult": cov_cal.crisis_vol_mult,
            "stress_regime": cov_cal.stress_regime,
            "note": cov_cal.note,
            "by_regime": {k: {"n_days": v.n_days, "mean_corr": round(v.mean_corr, 4),
                              "mean_vol": round(v.mean_vol, 6),
                              "diversification_ratio": round(v.diversification_ratio, 4)}
                          for k, v in cov_cal.by_regime.items()},
        } if cov_cal else {"note": "calibration unavailable; standing constants used"}),
        "evidence": {
            "sleeves": len(ev), "rows": int(daily.shape[0]),
            "with_forward": sum(1 for e in ev if e.forward_days > 0),
            "with_live": sum(1 for e in ev if e.live_days > 0),
            "worlds": worlds.r.shape[0], "world_rows": worlds.r.shape[1],
            "note": worlds.note,
            "forward_join": fwd_acct,
            "certified_library": cert_acct,
            "search_trials": trials,
        },
        "solver": {"iterations": book.iterations, "converged": book.converged},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(art, indent=2, default=str), encoding="utf-8")
    DONE.write_text(datetime.now(UTC).isoformat(), encoding="utf-8")

    # THE FORECAST LOG IS APPEND-ONLY AND IT IS WHAT MAKES THIS LOOP LEARN. `pf_allocation.json`
    # is overwritten every pass, so without this the desk has no record of what it EXPECTED --
    # and "expected vs realized" is the only measurement that can tell a bad edge model from a
    # bad cost model from a bad correlation model. One compact line per pass; the artifact keeps
    # the detail, this keeps the claim.
    try:
        FORECASTS.parent.mkdir(parents=True, exist_ok=True)
        with FORECASTS.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "t": art["generated_utc"], "mode": mode,
                "total_heat": art["heat"]["total"],
                "binding": art["heat"]["binding"],
                "certified": art["heat"]["certified"],
                "expected_log_per_day": art["growth"]["mean_log_per_day"],
                "expected_cvar_per_day": art["growth"]["cvar_log_per_day"],
                "prob_annual_loss": art["growth"]["prob_annual_loss"],
                "book": funded,
                "regime": dict(probs),
                "n_universe": len(ev),
            }, default=str) + "\n")
    except OSError as exc:
        _log(f"forecast log NOT written ({exc}) -- this pass cannot be scored later")
    _log(f"-> {OUT.relative_to(ROOT)}  [{nt['verdict']}]  {art['elapsed_s']}s")
    return art


#: Admission memory per mode. This box has 3.8 GB, NO SWAP and a documented OOM history, so a
#: job that does not fit destroys its own run and endangers the neighbours -- but a gate set
#: ABOVE the real need is just as broken, and quieter about it. These were 900/600/400 by
#: guesswork and stood the heavy pass down for twelve minutes on a box with 589 MB free.
#:
#: MEASURED 2026-09-02 with /usr/bin/time -v on a full heavy pass over 126 sleeves: peak RSS
#: 484 MB, wall 5:16. Set at ~1.35x the observed peak, which is headroom, not hope. Re-measure
#: when the universe grows; the tall part is the parquet rebuild, not the world tensor.
_NEED_MB = {"heavy": 650, "normal": 550, "fast": 350}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mode", choices=("fast", "normal", "heavy"), default="normal")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    # ONE LOCK ACROSS ALL THREE CLOCKS, not one per mode. The clocks overlap by design -- a heavy
    # pass takes ~5 minutes and the fast clock fires every 5 -- and three allocators resident at
    # once is ~750 MB on a box with ~700 MB free. A fast pass while a heavy pass is running has
    # nothing to add anyway: it would re-solve the same evidence at lower fidelity and overwrite
    # the better answer.
    try:
        from research.job_lock import exclusive_job, free_mb
    except ModuleNotFoundError:            # entrypoint put research/ on the path, not desks/mt5
        from job_lock import exclusive_job, free_mb  # type: ignore[no-redef,import-not-found]

    # ONLY THE HOURLY PASS IS WORTH WAITING FOR. `exclusive_job(need_mb=...)` holds a process
    # alive for up to twelve minutes waiting for room, which is right when the next trigger is an
    # hour away and wrong when it is five minutes: measured 2026-09-02, two `normal` passes sat
    # resident at 352 MB and 170 MB waiting for memory neither would get, on a box with 113 MB
    # free -- the waiting itself was the shortage. The short clocks now check once and leave; the
    # next trigger is minutes away and the caches make it resume rather than restart.
    need = _NEED_MB[args.mode]
    if args.mode != "heavy":
        room = free_mb()
        if room is not None and room < need:
            _log(f"stood down: needs ~{need}MB, box has {room}MB. The next {args.mode} trigger "
                 f"retries in minutes; waiting here would BE the shortage.")
            return 0
        need = 0                            # room confirmed above; do not wait a second time

    with exclusive_job("pf_allocator", need_mb=need) as go:
        if not go:
            _log(f"stood down: another allocator pass holds the lock, or the box cannot fit "
                 f"{_NEED_MB[args.mode]}MB. The previous book stands.")
            return 0
        try:
            run(args.mode, seed=args.seed)
        except Exception as exc:
            # A crash here must never read as "no allocation was needed" (L1.28a). The artifact
            # keeps its last good content and the failure is loud and non-zero.
            _log(f"ALLOCATOR FAILED: {type(exc).__name__}: {exc}")
            raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
