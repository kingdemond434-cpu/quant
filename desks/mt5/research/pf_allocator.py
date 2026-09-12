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
import os
import sys
import time
from collections.abc import Callable
from contextlib import suppress
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

from mt5desk.gateway_config_fallback import MAX_SLEEVE_HEAT_SHARE  # noqa: E402

from libs.portfolio.latent_factors import crisis_share_from_drift  # noqa: E402
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
    MIN_STATE_WORLDS,
    StateCurve,
    enforce_family_cap,
    evidence_readiness,
    heat_accounting,
    measured_ceiling,
    per_sleeve_bounds,
    resolve,
)

OUT = BASE / "reports" / "pf_allocation.json"
DONE = BASE / "reports" / "DONE_pf_allocation"
#: The change-point report `research/drift_monitor.py` writes. Read by the crisis overlay below;
#: absent or stale, the crisis-world share is exactly what it was.
DRIFT = BASE / "reports" / "DRIFT.json"
CACHE = BASE / "data" / "pf_allocator_cache"
ARMED = BASE / "data" / "PF_ALLOCATOR_ARMED"
#: Append-only record of what each pass EXPECTED. Read by `allocator_attribution.py`.
FORECASTS = BASE / "data" / "pf_forecast_log.jsonl"

#: How stale the assembled daily-R matrix may be before a `normal` pass rebuilds it. The matrix
#: changes when a new certificate lands or a sleeve accumulates bars -- both hourly events -- so
#: an hour is the honest refresh, and the heavy clock rebuilds unconditionally anyway.
#:
#: DERIVED FROM THE PRODUCERS' OWN CADENCE, not chosen: 3600s is exactly one firing interval of
#: the two things that can change this matrix. The gauntlet mints certificates on an hourly
#: schedule and the forward clocks accrue a bar per hour, so a matrix younger than 3600s cannot
#: have missed either event, and one older than 3600s may have missed exactly one. The same
#: reasoning the CHART_STALE_H precedent uses: a staleness bound set from a known firing rate is
#: a fact you look up in the manifest, not a number anyone picked.
EVIDENCE_MAX_AGE_S = 3600

#: Heat curve grid for certification. Spans the free optimum through the hard ceiling so the
#: peak is bracketed rather than assumed.
#:
#: THE ENDPOINTS ARE THE DERIVATION. It runs 0.02 to 0.30 because `heat_policy` reads its ceiling
#: OFF THIS CURVE, and `measured_ceiling` will never return a heat nobody sampled -- so the grid's
#: top IS the highest heat the desk can ever deploy, and its bottom must sit below any plausible
#: optimum for the peak to be bracketed rather than clipped. 0.30 was the recorded hard ceiling
#: when the grid was written. Spacing tightens from 0.025 to 0.0125 above 0.10 because that is
#: where the optimum has actually landed on every measured book, and a peak located on a coarse
#: grid is a peak reported to the grid's resolution rather than the book's.
#:
#: RAISING THE TOP IS THE ONE EDIT THAT MATTERS: the principal removed the fixed 30% cap on
#: 2026-09-05, and until this tuple extends past 0.30 no measurement can license a heat above it
#: -- not because a rule forbids it, but because nothing sampled it.
#: THE GRID RUNS TO 100% AND THE CAP ON IT IS GONE (principal, 2026-09-12: "remove the cap fully",
#: "i told u no caps"). This is a MEASUREMENT grid: sampling a heat is not deploying it, and the
#: only way the desk can ever learn that 60% is bad is to have measured 60%.
#:
#: Measured that day: the curve was monotonically RISING at every one of its ten points and stopped
#: at 0.225 -- not because growth turned, but because it was never asked. Growth per day went
#: +0.00716 at 2% to +0.02821 at 22.5% and was still climbing; the free optimum wanted 40.7%. The
#: reported "measured ceiling 22.5%" was the edge of the sweep wearing the name of an economic
#: limit, and its own reason string said so: "sweep further out to earn more."
CURVE_GRID = (0.02, 0.04, 0.06, 0.08, 0.10, 0.125, 0.15, 0.175, 0.20, 0.225, 0.25, 0.275,
              0.30, 0.325, 0.35, 0.375, 0.40, 0.425, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70,
              0.80, 0.90, 1.00)

#: The highest heat the growth curve is MEASURED at. A MEASUREMENT bound, not a policy bound, and
#: the distinction is the whole point of this constant existing separately from HEAT_HARD_CEILING.
#:
#: THE 30% CAP WAS STILL OPERATIVE, ONE LAYER BELOW WHERE ANYONE WAS LOOKING. The principal
#: removed the fixed ceiling on 2026-09-05 and `heat_policy.measured_ceiling` was rewritten to read
#: the bound off the curve, so it CAN return 34%, 39%, 45%. But `heat_curve` skipped every grid
#: point above HEAT_HARD_CEILING and solved with `hard_cap=HEAT_HARD_CEILING`, so the curve it
#: reads could never CONTAIN a point above 30% -- and `measured_ceiling` never returns past the
#: last heat anyone sampled. The removal was real and completely inert: the constant had stopped
#: being the policy and was still the sampler.
#:
#: THIS CANNOT RAISE TODAY'S HEAT, and that is what makes it safe. It changes what is MEASURED,
#: never what is DEPLOYED. `measured_ceiling` still returns the peak where growth turns over,
#: still refuses to run past the last sampled point, still falls back to HEAT_HARD_CEILING on an
#: unreadable curve, and still clamps to HEAT_TARGET when growth is non-positive anywhere. On the
#: book that produced the recorded curve -- robust score already negative at 30% -- it will keep
#: returning ~22%, and the four new grid points will simply record negative growth. What changes
#: is that a FUTURE book with genuine breadth can earn 45%, instead of being silently unable to
#: express it.
#:
#: 0.45 because that is the number the principal named as the top of the range worth measuring
#: ("20, 21, 23, 25, 27, 30, 34, 39, 45"). Raising it further is a decision about how far the desk
#: is willing to SIMULATE, which costs solver time and nothing else -- it is not a decision about
#: how much risk to take, because no heat is deployed that the curve did not first justify.
#: RAISED FROM 0.45 TO 1.00 (principal, 2026-09-12). Solver time is the only thing this costs:
#: no heat is deployed that the curve did not first justify, `measured_ceiling` still refuses
#: every heat past the turnover point, and it still never runs past the last SAMPLED point. The
#: previous 0.45 was itself a range the principal had named; the instruction now is that the
#: measurement must not be bounded at all, so the desk can find where growth genuinely turns
#: instead of reporting the edge of its own grid as an economic result.
CURVE_SAMPLE_MAX = 1.00

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
#: PRINCIPAL OVERRIDE (2026-09-11, instructed in session 01WZHzZoD3QX9Tx668fkAaw6): "make it
#: follow the optimum always no coping or getting scared js cuz returns show extreme".
#: QUANT_IMPLAUSIBLE_ANNUAL_PCT raises or removes the fence (0 or a negative value disables it).
#:
#: WHAT THE FENCE WAS FOR, kept here because the override does not make the reasoning wrong.
#: It fires on a BROKEN INPUT, not on a big number -- the case that justified it produced 2.8e14
#: percent from sleeves stacked on mismatched date clocks. On 2026-09-11 the desk's own realised
#: record was measured against it and the fence lost that argument on the evidence: six trading
#: days at +0.0327 log/day realised against the model's +0.0174 claim, i.e. the model was HALF
#: the realised rate, not a fantasy multiple of it. On a EUR 600 account four figures a year is
#: arithmetic, not absurdity.
#:
#: WHAT DISABLING IT COSTS, stated plainly. The fence was the only check standing between a
#: date-misalignment defect and a sized book: with it off, an input error that inflates growth
#: is deployed rather than refused. The compensating measurements are `heat.effective`
#: (where the heat actually lands) and the survival ceiling from `kelly_surface.envelope`,
#: both of which still bind every pass and neither of which is disabled here.
#: THE DEFAULT NOW APPLIES THE OVERRIDE INSTEAD OF DESCRIBING IT (2026-09-11). The reasoning
#: above was written and the constant was left at 5000, so the fence went on refusing every pass
#: while the file explained why it should not. Measured that evening: three consecutive passes
#: reported a free optimum of 2.8e5 - 5.1e5 percent a year, which is 0.0319 log/day -- BELOW the
#: +0.0327 log/day the desk realised over the preceding six trading days. A fence that refuses a
#: rate the account has already earned is not measuring plausibility, and 5000%/yr is 0.0156
#: log/day, under half the realised rate. The bar is set where it can only catch ARITHMETIC
#: corruption (the 2.8e14 date-clock defect is seven orders of magnitude above it) and can never
#: again fire on a book a real account could produce. Set QUANT_IMPLAUSIBLE_ANNUAL_PCT=0 to
#: remove it entirely.
IMPLAUSIBLE_ANNUAL_PCT = float(os.environ.get("QUANT_IMPLAUSIBLE_ANNUAL_PCT", "1e7"))

#: Regime-mixture bounds. No regime the desk has enough history for is ever assigned zero worlds
#: (MIN), and no regime may own more than MAX of the population however certain the classifier
#: sounds. See `regime_state` for the measurement that made both necessary.
#:
#: BOTH FIGURES ARE POPULATION-SIZE ARITHMETIC, not taste. The world population is 256 draws, so
#: MIN=0.08 puts a floor of ~20 worlds under any regime the desk has history for -- just above
#: `MIN_STATE_WORLDS = 24`'s own basis, which is the count at which a bucket stops being "one or
#: two draws wearing a distribution". A smaller floor would admit regimes whose curve the desk has
#: already measured as uninformative. MAX=0.60 leaves ~102 worlds across every OTHER regime
#: combined, which is what keeps a confident classifier from turning a mixture into a point
#: estimate: at 0.60 the alternatives still carry more than a third of the CVaR tail.
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


#: The scalp lane's per-trade forward ledgers, one file per clock, written by `scalp_shadow`.
SCALP_LEDGERS = "ledger_*.json"


def scalp_evidence() -> tuple[dict[str, pd.Series], dict[str, Any]]:
    """Daily-R series for every scalp clock, from its OWN forward ledger.

    THE DEFECT THIS EXISTS TO FIX, and it is the same one `certified_evidence` was written for --
    one lane later. Measured 2026-09-05: `pf_allocator.py` did not contain the string "scalp"
    anywhere, so no scalp sleeve had ever been priced. Follow that through the promoter and the
    lane is a dead end by construction:

        scalp_shadow      matures a clock to PROMOTION_CANDIDATE on 50 forward trades
        promote_scalp     builds the exact recipe and asks `capital_verdict`
        admission_of      finds no allocator row answering to the sleeve -> (None, "not in the
                          priced universe")
        capital_verdict   UNMEASURED (correctly: nobody looked)
        _door_status      "LIVE" only on a measured admission -> STANDBY

    So a scalp sleeve with a perfect forward record -- 50+ trades, positive expectancy, inside its
    drawdown bound -- lands on the roster at STANDBY and stays there for ever, and every artifact
    reads healthy the whole time. The promoter says PROMOTED, the clock says PROMOTION_CANDIDATE,
    the allocator says nothing at all, and nothing anywhere says "this cannot become live".

    THE LANE IS NOT IN `UNIVERSAL_SURVIVORS` AND THAT IS NOT AN OVERSIGHT: `promote_scalp` states
    it plainly -- "the ten-gate gauntlet has no path that certifies an M5/M15 scalp spec", so the
    lane's FORWARD CLOCK is its certificate. What was missing is the other half of that decision.
    A lane whose certificate is its forward record must have that forward record priced, or the
    lane cannot reach capital however good the record is.

    FORWARD PHASE ONLY. `scalp_shadow` writes every trade to `ledger_<name>.json` tagged
    `historical` or `forward` against its frozen pre-registration boundary. Only forward rows are
    read here: the historical ones are in-sample for this lane, and pricing a sleeve on the
    evidence that selected it is the same overfit the ten gates exist to refuse. It is also the
    difference between a marginal the allocator can trust and one it cannot.

    THE NAME IS THE CLOCK'S OWN KEY, so `promoter._join_keys`' first and most specific key --
    the raw sleeve name, lowercased -- matches directly. A second naming convention here would
    reproduce the join failure this function exists to remove.
    """
    acct: dict[str, Any] = {"ledgers": 0, "priced": 0, "not_scalp": 0, "refused": {}}
    shadow = BASE / "reports" / "shadow"
    if not shadow.exists():
        acct["refused"]["shadow"] = f"{shadow} absent on this host"
        return {}, acct
    out: dict[str, pd.Series] = {}
    for path in sorted(shadow.glob(SCALP_LEDGERS)):
        name = path.stem[len("ledger_"):]
        acct["ledgers"] += 1
        try:
            rows = json.loads(path.read_text("utf-8"))
        except (OSError, ValueError) as exc:
            acct["refused"][name] = f"{type(exc).__name__}: {exc}"
            continue
        if not isinstance(rows, list):
            acct["refused"][name] = "ledger is not a list of trades"
            continue
        # NOT EVERY `ledger_*.json` IS A SCALP LEDGER, and the glob cannot tell. `shadow_forward`
        # writes its certified clocks to the same directory with the same prefix -- rows carrying
        # `r_multiple` / `entry_time`, not `r` / `opened_at` -- and those sleeves are priced by
        # the CERTIFIED library, never here. Reading them here would price them twice; refusing
        # them for "0 forward day(s)" (which is what `r.get("r")` returning None produced, on
        # all 81 of them, measured 2026-09-08) reports a plumbing gap as missing evidence. They
        # are counted apart so `scalp_library` reads as what it is: 85 files, 81 another lane's.
        if rows and all(isinstance(r, dict) and "r" not in r and "r_multiple" in r
                        for r in rows[:5]):
            acct["not_scalp"] += 1
            continue
        by_day: dict[Any, float] = {}
        for r in rows:
            if not isinstance(r, dict) or str(r.get("phase")) != "forward":
                continue
            # THE WRITER'S OWN FIELD NAMES COME FIRST, and their absence is why no scalp sleeve
            # has ever been funded. `scalp_reverse_engineering.simulate(detailed=True)` -- the
            # only producer of these ledgers -- emits `opened_at` / `closed_at`. This read asked
            # for `exit_time` / `entry_time` / `time`, none of which any row has ever carried, so
            # `stamp` was None on EVERY row, `by_day` finished empty, and the clock was refused
            # with "0 forward day(s)". Measured 2026-09-08 on four gold clocks holding 344 real
            # forward trades spanning Aug 24 to Sep 8:
            #
            #   scalp_evidence refuses -> sleeve absent from the priced universe
            #     -> no allocator row -> promoter's capital_verdict finds nothing
            #     -> "PROMOTED (scalp) ... -> STANDBY at 0.00% risk"
            #
            # Three sleeves sat at PROMOTION CANDIDATE, past their 14-day window, for weeks, and
            # the reason was two spellings of "when did this trade happen".
            stamp = (r.get("closed_at") or r.get("opened_at")
                     or r.get("exit_time") or r.get("entry_time") or r.get("time"))
            value = r.get("r")
            if stamp is None or value is None:
                continue
            try:
                day = pd.Timestamp(str(stamp)).date()
                by_day[day] = by_day.get(day, 0.0) + float(value)
            except (ValueError, TypeError):
                continue
        if len(by_day) < 2:
            acct["refused"][name] = (f"{len(by_day)} forward day(s) in the ledger: a series the "
                                     f"bootstrap cannot draw from is not evidence")
            continue
        out[name] = pd.Series([by_day[d] for d in sorted(by_day)], index=sorted(by_day))
        acct["priced"] += 1
    _log(f"scalp library: {acct['priced']}/{acct['ledgers']} clock(s) priced from their forward "
         f"ledgers, {acct['not_scalp']} belong to the certified lane, "
         f"{len(acct['refused'])} refused")
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
        by_day = {str(d): lab[int(j)]
                  for d, j in zip(close.index, eng.filtered_states, strict=True)}
        labels = tuple(by_day.get(str(d)[:10], "") for d in daily.index)

        # The filtered posterior is the STARTING point, summed onto LABELS rather than latent
        # state indices because two states can carry the same economic label.
        post = eng.posteriors[-1]
        filtered: dict[str, float] = {}
        for j, pj in enumerate(post):
            filtered[lab[int(j)]] = filtered.get(lab[int(j)], 0.0) + float(pj)

        # CAUSAL PATH, NOT THE SMOOTHED ONE. `forecast` reads this path twice: `_runs` for the
        # current run's age and `age_hazard` for the dwell-time hazard fitted on historical run
        # LENGTHS. Viterbi produces artificially crisp blocks -- that is what smoothing is for --
        # so a hazard fitted on it says regimes persist longer than a desk watching in real time
        # would ever have seen, and the current age is measured off a run whose start was chosen
        # with hindsight. The filtered path is noisier and is the honest input.
        fc = regime_forecast(eng.hmm.transmat, post, lab, eng.filtered_states,
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
    # THE LIFETIME LEDGER (Quanti's discipline): the desk's whole history of trials per family,
    # taken as the LARGER of the gate report's count and the lifetime count. A tightening only.
    try:
        from libs.research.experiment_ledger import lifetime
        life = lifetime(write=False)
        for fam, n in (life.get("by_family") or {}).items():
            out[f"family:{fam}"] = max(int(out.get(f"family:{fam}", 0)), int(n))
        out["lifetime_total"] = max(int(out.get("lifetime_total", 0)),
                                    int(life.get("lifetime_trials", 0)))
    except Exception:
        pass
    return out


def _execution_costs(names: Any) -> dict[str, Any]:
    """Each sleeve's measured execution under-charge, keyed by sleeve name.

    THE SYMBOL AND THE SELECTOR BOTH COME OUT OF THE SLEEVE NAME, which is how every other organ
    on this desk reads them (`_symbol_of`, `_state_returns`, `classify_sleeve`), so no new
    metadata channel is invented for this and no certificate has to be re-issued for it to work.
    A name that carries no session token is UNPRICED and says so; it is not guessed at, because a
    guessed fill hour prices the sleeve at an hour it does not trade.
    """
    try:
        from libs.portfolio.execution_cost import costs_for
        surface = json.loads((BASE / "data" / "cost_surface.json").read_text("utf-8"))
    except (OSError, ValueError, ImportError) as exc:
        return {"sleeves": {},
                "summary": {"n_sleeves": 0, "n_measured": 0, "n_unpriced": 0,
                            "n_undercharged": 0, "n_overcharged": 0, "n_clipped": 0,
                            "n_registry_defect": 0, "n_no_spread_provenance": 0,
                            "worst_undercharge": None,
                            "verdict": f"no cost surface on this host ({type(exc).__name__})"}}
    # THE REGISTRY IS PASSED SO THE PROVENANCE GATE CAN RUN. Without it every symbol prices, and
    # on this desk's data that means pricing 241 of 251 symbols off a spread nobody can attribute
    # to a producer. An unreadable registry is treated as "no provenance for anything", which is
    # the conservative direction: nothing is corrected.
    try:
        reg = json.loads((BASE / "data" / "universe" / "universe.json").read_text("utf-8"))
        reg = reg.get("symbols", reg) if isinstance(reg, dict) else {}
    except (OSError, ValueError):
        reg = {}
    rows = [{"name": str(c), "symbol": str(c).split("_")[0], "selector": str(c)} for c in names]
    return costs_for(rows, surface, registry=reg)


def sleeve_evidence(daily: pd.DataFrame, forward: dict[str, dict[str, float]],
                    live: dict[str, int],
                    trials: dict[str, int] | None = None,
                    phase: str | None = None,
                    trades_by_sleeve: dict[str, list[dict]] | None = None,
                    broker_utc_offset_h: int = 0,
                    forward_only_days: dict[str, int] | None = None) -> list[SleeveEvidence]:
    """Fold backtest, certified, forward and live evidence into one record per sleeve.

    THE UNIVERSE IS THE UNION, which is the whole point. The backtest matrix (gold book + hunt12
    survivors) and the certified library (what cleared the ten gates) were disjoint sets, so
    whichever one the allocator read, it could not fund the other. Both are priced here, on the
    same daily clock, and compete for the same heat.

    Forward days are APPENDED to the series, not averaged into it: they are additional
    observations of the same sleeve, and the posterior weights them 4x (live 12x) precisely
    because they are the only ones the sleeve could not have been selected on.
    """
    # EXECUTION PRICED AT EACH SLEEVE'S OWN FILL HOUR, before any sleeve is built. Until
    # 2026-09-07 every sleeve was handed the literal `cost_r=0.05` -- one constant for a session
    # breakout on EURZAR filling at 01:00 and for a gold bracket on an administered spread -- and
    # `research/cost_surface.py` had ALREADY measured that the pooled scalar those returns were
    # charged at is 6.16x too small on USDZAR's own fill bars, on a live certified sleeve. The
    # measurement reached the gauntlet and never reached the allocator, which is the
    # producer/consumer collapse this desk keeps paying for.
    cost_doc = _execution_costs(daily.columns)
    _log(f"execution cost: {cost_doc['summary']['n_measured']}/"
         f"{cost_doc['summary']['n_sleeves']} sleeves priced at their own fill hour; "
         f"{cost_doc['summary']['n_undercharged']} under-charged, worst "
         f"{cost_doc['summary']['worst_undercharge']}")
    costs = cost_doc["sleeves"]

    out: list[SleeveEvidence] = []
    # NO ZERO-FILL HERE. `align` reindexes every sleeve onto the union of trading days, so a
    # sleeve that has lived a fortnight carries NaN on the ~2,247 days before it existed.
    # `fillna(0.0)` turned each of those into a REAL OBSERVATION OF ZERO RETURN -- the desk's
    # shipped defect #4 -- which diluted the sleeve's mean, flattened its dispersion and told the
    # shrinkage it had 2,260 observations. The NaN now survives to `_posterior_mu`, which takes
    # each sleeve's mean/std/n from its OWN days, while every portfolio-level consumer
    # (`sample_worlds`, `_corr_abs`, `_corr_to_book`) fills flat at its own stacking site. That
    # split is the protocol's rule verbatim: NaN day, never 0; flat only at portfolio level.
    series: dict[str, np.ndarray] = {
        str(c): daily[c].to_numpy(dtype=float) for c in daily.columns
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
            # A LANE WHOSE WHOLE SERIES IS FORWARD COUNTS ITS OWN DAYS. `forward` holds days
            # APPENDED to a backtest history, so `len(fwd)` is right for a sleeve with both.
            # The scalp lane has no backtest half: `scalp_evidence` reads FORWARD PHASE ONLY
            # and that series arrives through `daily`, so `fwd` is empty and this reported 1
            # forward day for clocks holding 13-14. Not cosmetic -- it feeds
            # `oos = 4*forward_days + 12*live_days`, the weight deciding how hard the mean is
            # shrunk toward the family prior. Measured 2026-09-10: 53/94/97 forward trades
            # over 13/14/14 days, all reported as forward_days=1.
            forward_days=len(fwd) or int((forward_only_days or {}).get(name, 0)),
            live_days=int(live.get(name, 0)),
            # Cost LEVEL is already inside the replayed R multiples (Costs.from_symbol at the
            # honest 2x baseline); `cost_r` is the per-trade scale used to size the UNCERTAINTY
            # around it, never a second charge -- and it now MOVES WITH THE SLEEVE, because a
            # sleeve filling where the spread is three times the pooled scalar is not merely more
            # expensive, it is more uncertainly expensive.
            #
            # `cost_bias_r` is the separate, deterministic statement: the R per trade the replay
            # did NOT charge, measured as (spread at this sleeve's own fill hour / the pooled
            # spread it was charged at). Zero where the desk cannot price the sleeve, which is
            # exactly the behaviour that existed before -- unpriced is not cheap.
            cost_r=float((costs.get(name) or {}).get("cost_r", 0.05)),
            cost_bias_r=float((costs.get(name) or {}).get("cost_bias_r", 0.0)),
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
        base = returns_in_phase(rows, phase, broker_utc_offset_h=broker_utc_offset_h)
    except Exception as exc:
        _log(f"state conditioning unavailable for {name}: {type(exc).__name__}: {exc}")
        return np.array([], dtype=float)
    # THE OTHER ADMITTED DIMENSIONS NARROW THE SAME BUCKET. Session was the only dimension that
    # reached the posterior; event and weekday were judged by `state_admission` and, where not
    # buried, may condition too. Each admitted dimension's CURRENT bucket is read from the
    # state vector and the sleeve's trades are filtered to those whose own point-in-time label
    # matches -- the same labellers the admission test used, so a dimension conditions here on
    # exactly the terms it was judged on. k_state = 40 protects the narrower bucket as before.
    extra = _admitted_extra_dims()
    if not extra:
        return base
    try:
        from session_phase import _entry_hour  # noqa: F401  (kept for parity with returns_in_phase)

        from libs.regime.state_admission import Trade, build_labeller
        keep = []
        fns = {d: build_labeller(d) for d, _cur in extra}
        for r in rows:
            when = str(r.get("entry_time") or r.get("opened_at") or "")
            if not when:
                continue
            t = Trade(sleeve=name, when=when, r=float(r.get("r_multiple", 0.0)))
            ok = True
            for d, cur in extra:
                fn = fns.get(d)
                if fn is None or fn(t) != cur:
                    ok = False
                    break
            if ok:
                keep.append(r)
        if not keep:
            return base
        return returns_in_phase(keep, phase, broker_utc_offset_h=broker_utc_offset_h)
    except Exception as exc:
        _log(f"extra-dimension conditioning unavailable for {name}: "
             f"{type(exc).__name__}: {exc}; session-only bucket used")
        return base


_EXTRA_DIMS_CACHE: tuple[float, tuple] = (0.0, ())


def _admitted_extra_dims() -> tuple[tuple[str, str], ...]:
    """(dimension, current bucket) for every admitted non-session dimension, from the artifacts.

    Read once per pass (mtime-cached): the admission report says which dimensions may condition,
    the state vector says which bucket each is in right now. A dimension missing from either is
    simply not applied -- absence is not a claim.
    """
    global _EXTRA_DIMS_CACHE
    try:
        adm_p = BASE / "reports" / "STATE_ADMISSION.json"
        sv_p = BASE / "data" / "state_vector.json"
        key = adm_p.stat().st_mtime + sv_p.stat().st_mtime
        if key == _EXTRA_DIMS_CACHE[0]:
            return _EXTRA_DIMS_CACHE[1]
        adm = json.loads(adm_p.read_text("utf-8"))
        sv = json.loads(sv_p.read_text("utf-8"))
        allowed = set(adm.get("admitted") or []) - {"session"}
        from datetime import datetime as _dt
        now_bucket = {"event": str((sv.get("event") or {}).get("phase") or ""),
                      "weekday": _dt.now(UTC).strftime("%a")}
        out = tuple((d, now_bucket[d]) for d in sorted(allowed)
                    if now_bucket.get(d))
        _EXTRA_DIMS_CACHE = (key, out)
        return out
    except Exception:
        return ()


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
                 cfg: WorldConfig,
                 *, bounds_at: Callable[[float], dict[str, float]] | None = None,
                 ) -> dict[float, float]:
    """Mean log growth of the OPTIMALLY COMPOSED book at each total heat on the grid.

    This is the curve `heat_policy.certify` reads, and it must be measured with the same
    per-sleeve bounds the desk will actually run: without them the optimiser answers the mandate
    by parking heat in the flattest sleeve it can find, and the curve comes out flat because the
    surplus was never really deployed. A certification measured on an unconstrained solve
    certifies a book nobody would run.
    """
    curve: dict[float, float] = {}
    for h in CURVE_GRID:
        # Bounded by the MEASUREMENT ceiling, not by the policy one. Sampling a heat is not
        # deploying it: `heat_policy.measured_ceiling` reads this curve and still refuses every
        # heat past its turnover point, so measuring 45% is how the desk learns 45% is bad.
        if h > CURVE_SAMPLE_MAX:
            continue
        # THE BOUNDS MUST BE THE ONES THE DESK WOULD RUN *AT THIS HEAT*, and passing one fixed set
        # made the curve unable to measure its own ceiling.
        #
        # MEASURED 2026-09-12. The caller passed `per_sleeve_bounds(dd, HEAT_TARGET)` -- the bounds
        # for a 20% book -- and they sum to ~22.5%. Every grid point above that failed
        # `sum(ub) < h` and was skipped, so the curve stopped at 0.225 with growth STILL RISING
        # (+0.02693/day at 0.200, +0.02821 at 0.225, monotone throughout, never turning).
        # `measured_ceiling` then correctly reported "the bound is the edge of the MEASUREMENT,
        # not of the opportunity -- sweep further out to earn more" and returned 22.5%.
        #
        # So the deployed ceiling was the SUM OF THE FLOOR'S BOUNDS wearing the name of an
        # economic limit, while the free optimum wanted 40.7% and the survival envelope allowed
        # 28.5%. The desk was not being held back by where growth turns; it was being held back by
        # never having asked.
        #
        # `bounds_at(h)` re-derives the per-sleeve bounds for the heat under test, which is the
        # only honest question: what would this book do IF it ran at h, under the bounds it would
        # have at h. Every safety property is untouched -- measured_ceiling still refuses past the
        # turnover point, still never runs past the last SAMPLED point, and the survival envelope
        # still binds independently.
        b = bounds_at(h) if bounds_at is not None else bounds
        ub = {k: min(v, h) for k, v in b.items()}
        if sum(ub.values()) < h:
            continue                     # bounds cannot fund this heat; not a growth finding
        try:
            r = optimise(ev, hard_cap=CURVE_SAMPLE_MAX, target=h, cfg=cfg, worlds=worlds,
                         max_per_sleeve=ub)
        except ValueError:
            continue
        if math.isfinite(r.mean_log_growth):
            curve[h] = r.mean_log_growth
    return curve


def _competing_pairs(d: dict[str, Any], top: int = 10) -> list[dict[str, Any]]:
    """The sleeve pairs whose cross-partial says they are the SAME BET, worst first.

    d2G/dh_i dh_j is most negative for sleeves that load the same thing: buying one makes the
    other worse. Normalised by the geometric mean of the two diagonals so the ranking is about
    the RELATIONSHIP rather than about which sleeve happens to be large -- the result is a
    correlation-like number in [-1, 0] where -1 is a duplicate.

    This is the same finding `breadth_credit` reaches from declared cluster occupancy, arrived at
    from realised returns instead. Where the two disagree, the disagreement is the finding: a pair
    the taxonomy calls independent and the Hessian calls a duplicate is a cluster label that is
    wrong, and it is wrong in the direction that flatters the book.
    """
    names = d.get("names") or []
    H = d.get("hessian")
    if d.get("status") != "MEASURED" or not H or len(names) < 2:
        return []
    m = np.asarray(H, dtype="float64")
    diag = np.diag(m)
    out: list[dict[str, Any]] = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            den = math.sqrt(abs(float(diag[i])) * abs(float(diag[j])))
            if den <= 0 or not math.isfinite(den):
                continue
            out.append({"a": names[i], "b": names[j],
                        "normalised_cross_partial": round(float(m[i, j]) / den, 4),
                        "raw": round(float(m[i, j]), 10)})
    out.sort(key=lambda r: r["normalised_cross_partial"])
    return out[:top]


def margin_use_from(margin: float, equity: float, deployed_heat: float,
                    heats: Any) -> tuple[dict[float, float] | None, str]:
    """Margin use at each sampled heat, extrapolated from ONE measured point. Pure arithmetic.

    The broker charges margin per LOT and the book's lots scale with its heat, so margin use is
    linear in heat through the origin: at deployed heat h0 the account uses m0/equity of its
    margin, therefore at heat h it would use (m0/equity) * (h/h0). One measured point and a
    proportion -- no model, and nothing here is extrapolated past what the surface sampled.

    Returns (None, why) on every input that cannot support the proportion: no equity, no
    deployed heat, or -- the common case on a flat book -- no margin in use, which is 0/0 and
    not "margin is free". A refusal here means the envelope carries NO margin clause and binds
    exactly as it does today.
    """
    try:
        m, eq, h0 = float(margin), float(equity), float(deployed_heat)
    except (TypeError, ValueError):
        return None, "account figures are not numbers"
    if not (math.isfinite(m) and math.isfinite(eq) and math.isfinite(h0)):
        return None, "account figures are not finite"
    if eq <= 0.0:
        return None, f"equity is {eq}: no denominator for margin use"
    if h0 <= 0.0:
        return None, "the book deploys no heat: margin per unit heat is 0/0"
    if m <= 0.0:
        return None, ("no margin in use (the book is flat or the positions are not open yet): "
                      "0/0 is not a measurement of margin per unit heat, and an unmeasured "
                      "margin never licenses heat")
    per_unit = (m / eq) / h0
    out: dict[float, float] = {}
    for h in heats:
        try:
            hv = float(h)
        except (TypeError, ValueError):
            continue
        if math.isfinite(hv) and hv > 0.0:
            out[round(hv, 6)] = per_unit * hv
    if not out:
        return None, "no sampled heat to price margin at"
    return out, (f"margin {m:.2f} on equity {eq:.2f} at {h0:.2%} deployed heat = "
                 f"{m / eq:.2%} of the account, i.e. {per_unit:.4f} of margin per unit of heat")


def account_margin() -> tuple[float | None, float | None, str]:
    """(margin, equity) from the live terminal, or (None, None) with the reason. Never raises.

    Measured the way `promoter.account_in_hand` measures the account: an existing connection is
    used and left alone, otherwise one is opened from `data/terminal_path.txt` and closed again.
    A host without MetaTrader5, without a terminal, or without an account is UNMEASURED -- which
    is the honest answer and the one that leaves the survival envelope exactly as it is.
    """
    try:
        import MetaTrader5 as mt5
    except ImportError:
        return None, None, "MetaTrader5 is not importable on this host"
    opened = False
    try:
        if mt5.terminal_info() is None:
            try:
                from mt5desk.config import terminal_path
                path = terminal_path()
            except Exception:
                path = ""
            opened = bool(mt5.initialize(path=path) if path else mt5.initialize())
            if not opened:
                return None, None, f"terminal unreachable ({mt5.last_error()})"
        acc = mt5.account_info()
        if acc is None:
            return None, None, "the terminal reports no account"
        return float(acc.margin), float(acc.equity), "measured from the live terminal"
    except Exception as exc:
        return None, None, f"{type(exc).__name__}: {exc}"
    finally:
        if opened:
            with suppress(Exception):
                mt5.shutdown()


def _capacity_ceiling() -> float | None:
    """The most total heat the MARKET can absorb, in account fraction, or None when unmeasured.

    `research/capacity.py` measures this desk's capacity as a FLOOR problem -- the minimum lot
    binds below EUR 3,293 -- and refuses the CEILING outright, because market impact needs
    realised fills and `execution.matched_fills` is 0. So this returns None today and the survival
    envelope simply carries no capacity clause.

    THE REFUSAL IS THE POINT, and it is why this is a function rather than a constant. An
    unmeasured capacity is not infinite capacity; it is a clause that cannot be evaluated, and
    the envelope says so by name instead of quietly treating the market as bottomless. The moment
    the box records fills and capacity publishes a measured ceiling, this binds with no further
    edit -- which is the only way a constraint ever starts working on a desk that is not watching.
    """
    try:
        doc = json.loads((BASE / "reports" / "CAPACITY.json").read_text("utf-8"))
    except (OSError, ValueError):
        return None
    if str(doc.get("ceiling_status")) != "MEASURED":
        return None
    h = doc.get("ceiling_heat_fraction")
    if not isinstance(h, (int, float)) or not math.isfinite(float(h)) or float(h) <= 0.0:
        return None
    return float(h)


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
    # THE INERTIA RAIL IS CALIBRATED BY ITS OWN LEDGER LINE. `missed_growth` bills what holding
    # cost or saved each day; a rail that persistently costs growth has its multiplier walked
    # down inside [0.5, 2.0] (libs.portfolio.rails), so the desk rebalances sooner. Never up.
    try:
        from libs.portfolio.rails import rail_multiplier as _rail_mult
        inertia_mult = _rail_mult("position_inertia")
    except Exception:
        inertia_mult = 1.0
    cost = turnover * TURNOVER_COST_R * inertia_mult
    benefit = max(gain_per_day, 0.0) * NO_TRADE_HORIZON_DAYS
    go = benefit > cost
    return {
        "verdict": "REBALANCE" if go else "NO CHANGE",
        "turnover": round(turnover, 6),
        "cost": round(cost, 8),
        "inertia_multiplier": round(inertia_mult, 4),
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

    THE FALLBACK IS NORMALISED TO THE MANDATE FLOOR, and until 2026-09-11 it was not. Q_OPT is a
    PER-SLEEVE nominal quantum, so a flat book of it totals whatever the roster size happens to
    make: 46 live sleeves x 1.2702% = 58.43% "held" heat, and 100 sleeves would have read 127%.
    A baseline whose total is a function of how many rows are live is not a measurement of
    anything, and it fed `bind_verdict`, whose one hard rule is that it may not hold the desk
    outside the mandated band.

    THAT BUILT A TRAP THE BOOK COULD NOT ESCAPE. Measured this evening: the plausibility fence
    refused a pass, the book published empty, so the next pass found no `book` to read and fell
    through to this branch, which returned 58.43% -- out of band -- so `bind_verdict` declined to
    hold it and published the empty solve AGAIN. Once the book emptied it could never come back
    under its own power, and the gateway logged `sizing: no allocator book` on every pass while
    the allocator logged "the previous book stands". Scaling the flat book to HEAT_TARGET keeps
    the baseline in band, so a refused pass now HOLDS instead of zeroing, which is what the
    refusal always claimed to do.
    """
    if OUT.exists():
        try:
            prev = json.loads(OUT.read_text("utf-8"))
            book = prev.get("book")
            if isinstance(book, dict) and book:
                return {str(k): float(v) for k, v in book.items()}
        except (OSError, ValueError):
            pass

    def _flat(names: list[str]) -> dict[str, float]:
        """A flat book over `names` totalling the mandate floor, not Q_OPT x len(names)."""
        if not names:
            return {}
        each = float(HEAT_TARGET) / float(len(names))
        return dict.fromkeys(names, each)

    try:
        from mt5desk.gateway import sleeve_set
        return _flat([str(s["name"]) for s in sleeve_set()])
    except Exception:
        try:
            from research.promoter import GOLD_SLEEVE_NAMES, _load_gold_retired
            retired = set(_load_gold_retired())
            return _flat([n for n in GOLD_SLEEVE_NAMES if n not in retired])
        except Exception:
            return {}


def bind_verdict(nt: dict[str, Any], prev_book: dict[str, float], held: dict[str, float],
                 book: AllocationResult, funded: dict[str, float],
                 *, floor: float = HEAT_TARGET, ceiling: float = HEAT_HARD_CEILING,
                 ) -> tuple[AllocationResult, dict[str, float]]:
    """Make the no-trade verdict BIND the book that is published. Returns (book, funded).

    Until 2026-09-05 `no_trade` was written beside a `book` that was always the fresh solve, so
    the gateway sized toward every proposal and the filter was a report about a decision already
    taken. On a five-minute clock that is churn by construction. The principal's cadence rule is
    recompute every pass, EXECUTE only when the growth the move buys clears turnover, slippage
    and the uncertainty buffer -- so NO CHANGE publishes the HELD book with the held book's own
    growth numbers, and the declined solve rides along as `proposed_book` for the next pass, the
    dashboard and `missed_growth` (which bills what holding cost or saved).

    The one thing a verdict may never do is hold the desk BELOW the mandated floor or ABOVE the
    ceiling: a held book outside the band is a defect the filter has no authority over, and the
    solve goes out unchanged with the reason on `nt["why_not_binding"]`. A held book the worlds
    cannot score is not a book to keep either. `nt["binding"]` says which way it went.

    OUT OF BAND NEVER MEANS ZERO (2026-09-11, principal: "fix that permanently"). Declining to
    hold is only safe when there is a SOLVE to publish instead. Measured this evening: the
    plausibility fence refused three consecutive passes, so `book` arrived EMPTY, the held book
    read 58.43% (out of band), this branch declined to bind -- and the empty solve went out. Zero
    heat, `allocator_ok=False`, `CATASTROPHE GUARD: allocator produced no usable book`, and the
    gateway logging `sizing: no allocator book` on every pass. Refusing to hold 58% because it is
    above a 30% ceiling, and publishing 0% instead, misses the ceiling by more than holding did
    and violates the 20% floor as well; it is the strictly worst of the three available answers.

    So when there is no solve to fall back on, the held book is SCALED into the band rather than
    discarded -- same composition, mandated total. The growth numbers travel with a note saying
    which total they were measured at, because scaling the weights does not rescore them and
    publishing them as if it had would be the defect wearing a plausible answer.
    """
    nt["binding"] = False
    if nt.get("verdict") != "NO CHANGE":
        return book, funded
    held_total = float(sum(float(v) for v in prev_book.values()))
    scorable = bool(prev_book) and math.isfinite(float(held.get("mean_log_growth", float("nan"))))
    out_of_band = held_total < floor - 1e-4 or held_total > ceiling + 1e-4
    # A solve worth publishing instead of the held book: non-empty and carrying real heat.
    have_solve = bool(book.heat) and book.total_heat > 1e-9
    if not scorable:
        nt["why_not_binding"] = "no scorable held book to keep"
    elif out_of_band and have_solve:
        nt["why_not_binding"] = (f"held book at {held_total:.2%} is outside the mandated "
                                 f"[{floor:.0%}, {ceiling:.0%}] band; publishing the solve")
    elif out_of_band:
        target = min(max(held_total, floor), ceiling)
        k = target / held_total if held_total > 1e-12 else 0.0
        scaled = {str(s): float(v) * k for s, v in prev_book.items() if float(v) * k > 1e-5}
        nt["binding"] = True
        nt["held_rescaled"] = {"from": round(held_total, 6), "to": round(target, 6),
                               "factor": round(k, 6)}
        nt["why_not_binding"] = ""
        kept = AllocationResult(
            heat=scaled, total_heat=float(sum(scaled.values())),
            robust_score=float(held["robust_score"]),
            mean_log_growth=float(held["mean_log_growth"]),
            cvar_log_growth=float(held["cvar_log_growth"]),
            annual_growth_pct=float(held["annual_growth_pct"]),
            prob_annual_loss=float(held["prob_annual_loss"]),
            marginal=dict(book.marginal),
            note=(f"held and rescaled: the solve was empty, so the held book was scaled "
                  f"{held_total:.2%} -> {target:.2%} into the mandated band rather than "
                  f"published as zero. Growth numbers were measured at {held_total:.2%}."))
        _log(f"NO SOLVE TO PUBLISH: holding the book, rescaled {held_total:.2%} -> "
             f"{target:.2%} into the [{floor:.0%}, {ceiling:.0%}] band across "
             f"{len(scaled)} sleeves. Zero heat is not the safe answer here.")
        return kept, {k2: round(v, 6) for k2, v in scaled.items()}
    else:
        nt["binding"] = True
        kept = AllocationResult(
            heat={k: float(v) for k, v in prev_book.items() if float(v) > 1e-5},
            total_heat=held_total,
            robust_score=float(held["robust_score"]),
            mean_log_growth=float(held["mean_log_growth"]),
            cvar_log_growth=float(held["cvar_log_growth"]),
            annual_growth_pct=float(held["annual_growth_pct"]),
            prob_annual_loss=float(held["prob_annual_loss"]),
            marginal=dict(book.marginal),
            note=(f"held: the no-trade filter declined the solve (benefit "
                  f"{float(nt.get('benefit_over_horizon', 0.0)):.6f} < cost "
                  f"{float(nt.get('cost', 0.0)):.6f})"))
        _log(f"NO CHANGE binds: publishing the held book at {held_total:.2%}; the solve "
             f"({sum(funded.values()):.2%}) is carried as proposed_book")
        return kept, {k: round(v, 6) for k, v in kept.heat.items() if v > 1e-5}
    _log(f"NO CHANGE not binding: {nt['why_not_binding']}; the solve is published")
    return book, funded


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


def fill_floor(book: AllocationResult, ev: list[SleeveEvidence], target: float,
               ub: dict[str, float], family_of: dict[str, str], *,
               cfg: WorldConfig, worlds: Worlds) -> tuple[AllocationResult, dict[str, Any]]:
    """Hold the resolved heat; yield the per-sleeve bounds, in order, until it is funded.

    FLOOR FILL (principal, 2026-09-04): the resolved heat -- 20% floor, growth above it to the
    ceiling -- is what the book HOLDS, not what it reports as a shortfall. When the per-sleeve
    bounds cannot fund it, the bounds yield in the order of how little each was ever proven to
    earn: the drawdown-derived leg first, then the mechanism cap, then the single-sleeve share
    cap, and last a proportional scale of the solved book. Every relaxation is returned in the
    note and billed by `missed_growth` as that rail's opportunity cost. The one thing the fill
    never overrides is the ruin guard: a candidate wiped out in a sampled world is skipped, and
    the caller's ruin check still runs on whatever is returned.
    """
    note: dict[str, Any] = {"needed": False}
    short = target - book.total_heat
    if not (math.isfinite(book.mean_log_growth) and short > 1e-4):
        return book, note
    share_cap = MAX_SLEEVE_HEAT_SHARE * target
    levels = (("drawdown_bound", dict.fromkeys(ub, share_cap), True),
              ("family_cap", dict.fromkeys(ub, share_cap), False),
              ("share_cap", dict.fromkeys(ub, target), False))
    g_before = book.mean_log_growth
    for level, bnd, keep_family in levels:
        try:
            # `max(..., target)` because the SOLVER's bound must never sit below the heat the
            # POLICY licensed. `target` arrives from heat_policy, which is itself bounded by the
            # measured curve, so this can only ever admit a heat the curve already justified --
            # and with HEAT_HARD_CEILING as the floor of the bound, nothing below 30% changes.
            # Before this, a policy that measured 38% solved against a 30% cap and quietly
            # delivered 30%, which reads on every report as "the optimum was 30".
            cand = optimise(ev, hard_cap=max(HEAT_HARD_CEILING, target), target=target, cfg=cfg,
                            worlds=worlds, max_per_sleeve=bnd, warm_start=book.heat or None)
            if keep_family:
                capped = enforce_family_cap(cand.heat, family_of, cand.total_heat)
                if not all(math.isinf(v) for v in capped.values()):
                    tight = {k: min(bnd.get(k, math.inf), capped.get(k, math.inf))
                             for k in bnd}
                    cand = optimise(ev, hard_cap=max(HEAT_HARD_CEILING, target), target=target,
                                    cfg=cfg, worlds=worlds, max_per_sleeve=tight,
                                    warm_start=cand.heat or None)
        except ValueError:
            continue                                  # these bounds cannot fund it; next level
        if not math.isfinite(cand.mean_log_growth):
            continue
        if cand.total_heat > book.total_heat + 1e-6:
            book = cand
            note = {"needed": True, "relaxed": level,
                    "growth_gap": round(cand.mean_log_growth - g_before, 8)}
        if book.total_heat >= target - 1e-4:
            break
    if book.total_heat > 0 and book.total_heat < target - 1e-4:
        scale = target / book.total_heat
        scaled = {k: v * scale for k, v in book.heat.items()}
        sc = score_book(ev, scaled, cfg=cfg, worlds=worlds)
        if math.isfinite(sc["mean_log_growth"]):
            book = AllocationResult(
                heat=scaled, total_heat=float(sum(scaled.values())),
                robust_score=sc["robust_score"], mean_log_growth=sc["mean_log_growth"],
                cvar_log_growth=sc["cvar_log_growth"], annual_growth_pct=sc["annual_growth_pct"],
                prob_annual_loss=sc["prob_annual_loss"], marginal=book.marginal,
                iterations=book.iterations, converged=book.converged,
                note="floor filled by proportional scale of the bounded solve")
            note = {"needed": True, "relaxed": "proportional",
                    "growth_gap": round(sc["mean_log_growth"] - g_before, 8)}
    return book, note


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

    # THE GRAVEYARD BINDS. `state_admission_run` judges each state dimension walk-forward on the
    # desk's own realised trades: does conditioning on it predict trades it has NEVER SEEN better
    # than not conditioning? A dimension measured WORSE loses its access here, not in a report
    # somebody reads. Fails open to conditioning as before when no report exists, because
    # withdrawing a dimension on the strength of a missing file would be substituting one
    # unmeasured decision for another.
    try:
        from state_admission_run import read_graveyard
        barred, why = read_graveyard()
        _log(f"state admission: {why}")
        if "session" in barred:
            _log("state: session conditioning is in the GRAVEYARD -- measured worse out of "
                 "sample, so this pass solves without it")
            return None, {}, off
    except Exception as exc:
        _log(f"state admission unreadable ({type(exc).__name__}: {exc}); conditioning stands")

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
            except Exception:
                continue
            if isinstance(rows, list) and rows:
                trades.setdefault(f.stem[len("ledger_"):], []).extend(
                    r for r in rows if isinstance(r, dict) and "r_multiple" in r)
    return phase, trades, off


def hazard_by_sleeve(drift: dict[str, Any] | None) -> dict[str, float]:
    """P(edge breaks next horizon | history) per sleeve, from drift_monitor's nine channels.

    Only rows that carry a hazard: `perishability.edge_hazard` returns None under its own floors
    (fewer than three measured channels, or no sleeve-scoped one), and an absent hazard must read
    as no tilt rather than as a confident zero.
    """
    rows = (drift or {}).get("hazard_by_sleeve") or {}
    out: dict[str, float] = {}
    for name, row in rows.items():
        h = (row or {}).get("hazard") if isinstance(row, dict) else None
        if isinstance(h, (int, float)) and 0.0 < float(h) <= 1.0:
            out[str(name)] = float(h)
    return out


#: HOW THE DRIFT MONITOR'S PER-SLEEVE HAZARD REACHES THE SOLVE.
#:
#:   "decay_posterior"  (the path since 2026-09-09) each sleeve with a measured hazard carries
#:                      it as its OWN decay probability, `decay_prob_i = min(hazard, blanket)`,
#:                      and the world population decays that sleeve's edge in that share of
#:                      worlds instead of the blanket 30%. A sleeve the monitor calls healthy
#:                      stops paying the blanket and can earn MORE heat; a sleeve it calls
#:                      breaking is charged the blanket -- never more than every sleeve was
#:                      charged before, because the blanket is the ceiling (`robust_elog.
#:                      decay_prob_of`). Billed by `missed_growth.measure_decay_posterior`.
#:   "mean_shrink"      the previous path: `apply_hazard_shrink` tilts the posterior mean by
#:                      (1 - hazard) post hoc and every sleeve pays the blanket decay. Kept
#:                      available behind the same `hazard_shrink` rail and its billing.
#:
#: One of the two runs on a pass, never both: the hazard entering twice would charge one fact
#: as two.
HAZARD_MODE = "decay_posterior"


def apply_decay_posterior(ev: list[SleeveEvidence], haz: dict[str, float],
                          blanket: float) -> dict[str, Any]:
    """Hand each sleeve with a measured hazard its own decay probability, capped at the blanket.

    THE OTHER HALF OF "DECAY IS A CONSTANT". `robust_elog` decayed every sleeve's edge in 30% of
    worlds whatever the desk had measured about it, and the only per-sleeve decay input was a
    post-hoc shrink of the mean -- so a sleeve the drift monitor had watched for weeks and found
    stable paid exactly what an unwatched one paid. This writes the monitor's P(edge breaks |
    history) onto the sleeve as `decay_prob_i`, which `sample_worlds` uses in place of the
    blanket. Both numbers are returned per sleeve so the artifact can show the relief.

    NEVER ABOVE THE BLANKET. `min(hazard, blanket)` here, and `decay_prob_of` caps again inside
    the library: a sleeve's decay can only be relieved by this, never deepened, which is what
    lets it run on the money path under the standing order that nothing may size a sleeve below
    what it gets today. A sleeve without a measured hazard keeps the blanket exactly as before.
    """
    from dataclasses import replace as _replace
    by_sleeve: dict[str, dict[str, float]] = {}
    for i, e in enumerate(ev):
        h = haz.get(e.name)
        if h is None:
            continue
        p = min(float(h), float(blanket))
        ev[i] = _replace(e, decay_prob_i=p)
        by_sleeve[e.name] = {"hazard": round(float(h), 6), "decay_prob_i": round(p, 6),
                             "relief_vs_blanket": round(float(blanket) - p, 6)}
    return {"mode": "decay_posterior", "blanket": float(blanket),
            "n_from_hazard": len(by_sleeve), "n_blanket": len(ev) - len(by_sleeve),
            "by_sleeve": by_sleeve,
            "rule": ("decay_prob_i = min(drift_monitor hazard, blanket) per sleeve; a sleeve "
                     "without a measured hazard pays the blanket; nothing is ever charged above "
                     "the blanket, so this can only relieve today's haircut")}


def apply_hazard_shrink(ev: list[SleeveEvidence], haz: dict[str, float]) -> dict[str, Any]:
    """Shrink each sleeve's posterior mean by (1 - hazard) BEFORE any retirement threshold.

        "allocation changes BEFORE the formal retirement threshold"      -- the principal

    THE MEAN ONLY. `daily_r_shrunk = daily_r - mean * hazard` moves the centre and leaves the
    dispersion exactly where it was; scaling the series by (1 - h) would shrink its variance too
    and make a decaying sleeve look SAFER as its edge disappeared -- the opposite of the truth,
    and the kind of error that is invisible until the drawdown arrives.
    """
    from dataclasses import replace as _replace
    applied: dict[str, float] = {}
    for i, e in enumerate(ev):
        h = haz.get(e.name)
        if h is None or getattr(e.daily_r, "size", 0) == 0:
            continue
        ev[i] = _replace(e, daily_r=e.daily_r - float(e.daily_r.mean()) * h)
        applied[e.name] = round(h, 6)
    return {"applied": applied, "n_shrunk": len(applied),
            "rule": "posterior mean x (1 - hazard); dispersion unchanged; retirement unaffected"}


def read_drift() -> tuple[dict[str, Any] | None, str]:
    """`reports/DRIFT.json` if it can be read, else None with the reason. Never raises.

    The freshness decision itself lives in `latent_factors.crisis_share_from_drift`, which reads
    the document's own `generated_utc` -- one place decides whether a change-point signal is still
    about today's market, and it is unit-testable without touching a filesystem.
    """
    try:
        doc = json.loads(DRIFT.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        return None, f"DRIFT.json unreadable ({type(exc).__name__})"
    if not isinstance(doc, dict):
        return None, "DRIFT.json is not an object"
    return doc, f"DRIFT.json verdict={doc.get('verdict')} structure={doc.get('structure_verdict')}"


#: The structural-duplicate map `research/alpha_genome.py` writes. Its own docstring (:23-25)
#: says it is consumed "by the allocator artifact, where `n_clusters` is reported beside
#: `k_eff`" -- and a repo-wide grep for ALPHA_GENOME found no allocator reader at all, so the
#: claim was false for as long as it had been written. This is that reader.
GENOME = BASE / "reports" / "ALPHA_GENOME.json"


def alpha_genome_view(ev: list[SleeveEvidence], book: dict[str, float]) -> dict[str, Any]:
    """`n_clusters` and each FUNDED sleeve's structural cluster, beside the book's k_eff.

    WHY IT BELONGS NEXT TO k_eff AND NOT INSTEAD OF IT. `latent_factors.effective` measures
    independence from realised RETURNS (covariance, latent factor, tail); `alpha_genome.cluster`
    measures it from what each edge structurally IS -- mechanism, direction, clock, shared
    currency leg -- before it has traded. Two sleeves can look independent day to day and be one
    trade wearing two names, which is exactly what the genome found on this desk (twenty
    session_range_breakout sleeves in one cluster, twelve overnight_gap_decay rows sharing one
    parameter hash). Reporting the two numbers together is what lets a reader see them disagree.

    REPORTING ONLY. Nothing here sizes, caps or vetoes: the cluster id reaches the artifact and
    stops. A sleeve whose cluster cannot be resolved is COUNTED AND NAMED, never assigned a
    cluster of its own -- that would read as breadth the book has not got (L1.28a).
    """
    out: dict[str, Any] = {"status": "UNMEASURED", "consumed": False,
                           "note": ("structural clusters from reports/ALPHA_GENOME.json, "
                                    "reported beside the covariance/factor/tail k_eff; "
                                    "nothing here sizes anything")}
    try:
        doc = json.loads(GENOME.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        return {**out, "why": f"ALPHA_GENOME.json unreadable ({type(exc).__name__})"}
    genome = doc.get("genome") or {}
    clusters = doc.get("clusters") or {}
    if not isinstance(genome, dict) or not isinstance(clusters, dict) or not clusters:
        return {**out, "why": "ALPHA_GENOME.json carries no clusters"}
    cluster_of_key = {m: name for name, members in clusters.items()
                      for m in (members if isinstance(members, list) else [])}
    # THE JOIN, on the parts both sides already carry. The genome keys on its certificate key
    # and stamps symbol/family/clock on every row; the allocator names a sleeve
    # SYM_family_selector. Matching on (symbol, family, clock) first and (symbol, family) only
    # when that is UNAMBIGUOUS is the same rule `promoter._index` uses, for the same reason: a
    # sleeve funded on another sleeve's cluster id is worse than one that did not join.
    by_triple: dict[tuple[str, str, str], list[str]] = {}
    by_pair: dict[tuple[str, str], list[str]] = {}
    for key, row in genome.items():
        if not isinstance(row, dict):
            continue
        sym = str(row.get("symbol") or "").lower()
        fam = str(row.get("family") or "").lower()
        clk = str(row.get("clock") or "").lower()
        by_triple.setdefault((sym, fam, clk), []).append(key)
        by_pair.setdefault((sym, fam), []).append(key)
    by_name = {e.name: e for e in ev}
    funded = [n for n, h in (book or {}).items() if float(h) > 1e-5]
    per_sleeve: dict[str, str] = {}
    unjoined: dict[str, str] = {}
    for name in sorted(funded):
        e = by_name.get(name)
        if e is None:
            unjoined[name] = "not in the priced universe"
            continue
        sym, fam = str(e.symbol).lower(), str(e.family).lower()
        sel = _selector_of(e).lower()
        hits = by_triple.get((sym, fam, sel)) or []
        how = "symbol|family|clock"
        if not hits:
            hits, how = by_pair.get((sym, fam)) or [], "symbol|family"
        if not hits:
            unjoined[name] = f"no genome row for {sym}|{fam}|{sel or '(no selector)'}"
            continue
        names = {cluster_of_key.get(k) for k in hits} - {None}
        if len(names) != 1:
            unjoined[name] = (f"{len(hits)} genome row(s) on {how} spanning {len(names)} "
                              f"cluster(s); ambiguous, so no cluster is claimed")
            continue
        per_sleeve[name] = str(next(iter(names)))
    occupied = sorted(set(per_sleeve.values()))
    return {
        **out, "status": "MEASURED",
        "generated_utc": doc.get("generated_utc"),
        "n_clusters": doc.get("n_clusters"),
        "n_sleeves": doc.get("n_sleeves"),
        "structural_breadth": doc.get("structural_breadth"),
        "largest_clusters": [{"cluster": c.get("cluster"), "n": c.get("n")}
                             for c in (doc.get("largest_clusters") or [])[:5]
                             if isinstance(c, dict)],
        # THE BOOK'S OWN STRUCTURE: how many distinct clusters the FUNDED sleeves occupy, which
        # is the number to read against k_eff -- a book of eight sleeves in one cluster is one
        # structural bet however its returns happened to covary.
        "book_clusters_occupied": len(occupied),
        "book_clusters": occupied,
        "cluster_by_sleeve": per_sleeve,
        "n_funded_joined": len(per_sleeve),
        "n_funded_unjoined": len(unjoined),
        "unjoined": unjoined,
        "why": (f"{len(per_sleeve)}/{len(funded)} funded sleeve(s) joined to "
                f"{len(occupied)} of the genome's {doc.get('n_clusters')} structural cluster(s)"),
    }


def effective_heat_of(ev: list[SleeveEvidence], book: dict[str, float]) -> dict[str, Any]:
    """The four heats of `book` -- nominal, covariance, factor, tail -- or an `error` key.

    Wrapped rather than called inline because this runs BEFORE the solve now: the ceiling
    `heat_policy.resolve` enforces is derived from it, so a failure here has to be a stated
    UNMEASURED that leaves the nominal bar standing, never an exception that takes the pass.
    """
    if not book:
        return {"error": "no candidate book to measure"}
    try:
        from libs.portfolio.latent_factors import effective as _effective
        out: dict[str, Any] = _effective(ev, book)
        return out
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def state_growth_curves(ev: list[SleeveEvidence], worlds: Worlds, book: dict[str, float],
                        cfg: WorldConfig, now_buckets: dict[str, str] | None = None,
                        ) -> tuple[dict[str, StateCurve], str]:
    """E[log W | state] at each total heat on the grid, per admitted state bucket.

    THE SURFACE THE PRINCIPAL ASKED FOR, LEARNED RATHER THAN MAPPED: "H*_t = argmax_{H in [20,30]}
    E[logW | X_t]". `growth_curve` measures the unconditional curve by RE-OPTIMISING the
    composition at each heat; this measures the conditional one by SCORING the candidate book,
    proportionally scaled, on each state's own worlds.

    THAT DIFFERENCE IS STATED AND NOT HIDDEN. Re-optimising the composition inside every bucket is
    the better measurement and costs a full solve per bucket per grid point -- thirteen solves
    times the number of states, on a five-minute heavy pass whose budget is already the world
    population. What this measures is therefore "how does THE BOOK THE DESK IS ABOUT TO HOLD
    behave at each heat in this state", which is the question the heat law asks, and the artifact
    records `basis: scaled_candidate` so nobody later reads it as the stronger claim.
    """
    if not book or worlds is None or not worlds.regimes:
        return {}, "no book or no regime-labelled worlds: the global curve stands"
    try:
        from libs.portfolio.allocator_proof import _subworlds, buckets_from_worlds
    except Exception as exc:
        return {}, f"state buckets unavailable ({type(exc).__name__}: {exc})"
    buckets = buckets_from_worlds(worlds, now_buckets, min_worlds=MIN_STATE_WORLDS)
    if not buckets:
        return {}, f"no state bucket reached {MIN_STATE_WORLDS} worlds"
    total = float(sum(book.values()))
    if total <= 0:
        return {}, "candidate book holds no heat"
    out: dict[str, StateCurve] = {}
    for sid, idx in sorted(buckets.items()):
        try:
            sub = _subworlds(worlds, idx)
            curve: dict[float, float] = {}
            for h in CURVE_GRID:
                if h > CURVE_SAMPLE_MAX:
                    continue
                scaled = {k: v * h / total for k, v in book.items()}
                g = score_book(ev, scaled, cfg=cfg, worlds=sub)["mean_log_growth"]
                if math.isfinite(g):
                    curve[float(h)] = float(g)
            if len(curve) >= 3:
                out[sid] = StateCurve(state=sid, curve=curve, n_worlds=len(idx))
        except (ValueError, KeyError, IndexError) as exc:
            _log(f"state curve for {sid} unmeasured ({type(exc).__name__}: {exc})")
    return out, (f"{len(out)} state curve(s) of >= {MIN_STATE_WORLDS} worlds "
                 f"from {len(buckets)} bucket(s)")


def state_book(ev: list[SleeveEvidence], worlds: Worlds, cfg: WorldConfig, *,
               state: str, now_buckets: dict[str, str] | None, total_heat: float,
               bounds: dict[str, float], family_of: dict[str, str],
               warm_start: dict[str, float] | None,
               global_book: dict[str, float] | None) -> dict[str, Any]:
    """The COMPOSITION re-optimised inside the CURRENT state bucket alone -- one extra solve.

    `state_growth_curves` scores the global book proportionally scaled on each state's worlds,
    so the per-state curve carries the global solve's composition and only the EVALUATION is
    conditional (`state_curves_basis: scaled_candidate`). This is the stronger measurement for
    the one state that matters -- the one the desk is in -- and it costs exactly one solve: the
    same evidence, the same bounds and family cap the published book was solved under, at the
    same resolved total heat, on the current state's worlds only. The global book is scored on
    those same worlds beside it, so the artifact says in one number what solving FOR the state
    would have bought over holding the global composition in it.

    PUBLISHED, NOT CONSUMED. The gateway sizes from `book`; it reads `heat.state` to pick which
    allocator's certificate applies (`allocator_proof.select`) and nothing reads this block for
    a size. It is written so the comparison exists and so a later change that lets the live
    state's own composition size the floor can be argued from a measured delta rather than a
    belief. `consumed` is False on every return until that change exists.

    THE TOTAL IS THE RESOLVED HEAT AND THE BOUNDS ARE THE BOOK'S. Solved at exactly
    `total_heat` (the floor or above, as the law resolved it) under `bounds` -- so even if a
    reader took this book as the answer, no sleeve would sit above its bound and the total would
    be neither below the floor nor above what the law licensed.
    """
    out: dict[str, Any] = {
        "status": "UNMEASURED", "state": state or "", "consumed": False,
        "basis": ("reoptimised_in_state: the composition re-solved on the current state "
                  "bucket's worlds alone, at the resolved total heat, under the published "
                  "book's own per-sleeve bounds and family cap"),
        "note": ("published, not consumed: the gateway reads heat.state and the proof "
                 "certificate's per-state verdict to choose WHICH allocator sizes; nothing "
                 "sizes from this block yet")}
    if not state:
        return {**out, "why": "no current state id this pass"}
    # `sample_worlds` returns a tuple of EMPTY labels when nothing conditioned the draw, which is
    # a non-empty tuple: testing the tuple alone would let an unconditioned population produce a
    # "state book" that is the global solve wearing a state's name.
    if worlds is None or not any(getattr(worlds, "regimes", ()) or ()):
        return {**out, "why": "no regime-labelled worlds: no state bucket to solve inside"}
    if total_heat <= 0:
        return {**out, "why": "no resolved heat (catastrophe guard): nothing to compose"}
    try:
        from libs.portfolio.allocator_proof import _subworlds, buckets_from_worlds
    except Exception as exc:
        return {**out, "why": f"state buckets unavailable ({type(exc).__name__}: {exc})"}
    buckets = buckets_from_worlds(worlds, now_buckets, min_worlds=MIN_STATE_WORLDS)
    idx = buckets.get(state)
    if not idx:
        return {**out, "why": (f"the current state {state!r} has no bucket of >= "
                               f"{MIN_STATE_WORLDS} worlds ({len(buckets)} bucket(s) reached "
                               "it); the global composition stands")}
    sub = _subworlds(worlds, idx)
    ub = {k: min(float(v), float(total_heat)) for k, v in bounds.items()}
    try:
        solve = optimise(ev, hard_cap=max(CURVE_SAMPLE_MAX, float(total_heat)),
                         target=float(total_heat), cfg=cfg, worlds=sub, max_per_sleeve=ub,
                         warm_start=warm_start or None)
        capped = enforce_family_cap(solve.heat, family_of, solve.total_heat)
        family_bound = not all(math.isinf(v) for v in capped.values())
        if family_bound:
            tight = {k: min(ub.get(k, math.inf), capped.get(k, math.inf)) for k in ub}
            solve = optimise(ev, hard_cap=max(CURVE_SAMPLE_MAX, float(total_heat)),
                             target=float(total_heat), cfg=cfg, worlds=sub,
                             max_per_sleeve=tight, warm_start=solve.heat or None)
    except ValueError as exc:
        return {**out, "n_worlds": len(idx),
                "why": f"the bounds cannot fund {total_heat:.2%} inside this state ({exc})"}
    if not math.isfinite(solve.mean_log_growth):
        return {**out, "n_worlds": len(idx),
                "why": "the state-solved book is wiped out in one of the state's own worlds"}
    growth = {"mean_log_per_day": round(solve.mean_log_growth, 10),
              "cvar_log_per_day": round(solve.cvar_log_growth, 10),
              "robust_score": round(solve.robust_score, 10),
              "annual_growth_pct": solve.annual_growth_pct,
              "prob_annual_loss": solve.prob_annual_loss}
    res: dict[str, Any] = {
        **out, "status": "MEASURED", "n_worlds": len(idx),
        "total_heat": round(solve.total_heat, 6),
        "book": {k: round(v, 6) for k, v in solve.heat.items() if v > 1e-5},
        "growth_on_state": growth, "family_cap_bound": bool(family_bound),
        "converged": bool(solve.converged), "iterations": int(solve.iterations),
        "why": f"solved on the {len(idx)} world(s) of state {state!r}",
    }
    if global_book:
        g = score_book(ev, global_book, cfg=cfg, worlds=sub)
        res["global_book_on_state"] = {k: (round(float(v), 10) if math.isfinite(float(v))
                                           else None) for k, v in g.items()}
        if math.isfinite(g["mean_log_growth"]):
            res["delta_elogw_per_day"] = round(solve.mean_log_growth - g["mean_log_growth"], 10)
            res["delta_robust"] = round(solve.robust_score - g["robust_score"], 10)
            res["reading"] = (
                f"solving FOR state {state!r} would grow "
                f"{res['delta_elogw_per_day']:+.6f}/day faster than holding the global "
                f"composition in it (robust {res['delta_robust']:+.6f}); reported, not sized")
    return res


# ---------------------------------------------------------------------------------------
# ADMISSION -- dE[log W] AGAINST THE BOOK THE DESK IS ACTUALLY HOLDING
# ---------------------------------------------------------------------------------------

#: Wall clock ONE candidate's warm-started re-solve may spend, in seconds. Until 2026-09-09 this
#: was a 180 s budget for the WHOLE scan: ~150 candidates an hour, and everything past the cut
#: left `unscored` -- named, refused, and refused again next hour if the rotation did not reach
#: it. A compute limit hardening into a verdict. The budget is now PER CANDIDATE and the scan
#: runs over EVERY candidate on every heavy pass; a re-solve that hits its own budget is not
#: refused, it is carried forward WARM-STARTED from the exact point it stopped and continues on
#: the next pass (`optimise(..., deadline=)`, `AllocationResult.budget_hit`). A warm-started
#: candidate re-solve is ~1.2 s on the desk's 110-sleeve population; 8 s is headroom for one
#: that starts far from the incumbent, not a cap on the scan. Zero or negative means unbounded.
ADMISSION_CANDIDATE_BUDGET_S = 8.0
#: Share of the book's TOTAL heat that may be lent to exploration among candidates whose
#: dE[log W] sits INSIDE the admission margin -- the ambiguous ones, which the criterion could
#: neither admit nor refuse on evidence and which were parked at zero for ever. Lent from
#: WITHIN the total (incumbents scaled proportionally; the total is unchanged by construction),
#: Thompson-sampled so an ambiguous candidate is funded in proportion to how often a draw from
#: its own noise says it wins, and billed as the `explore_thompson` rail. Five percent of the
#: book is one percent of account heat on the 20% floor: enough to accrue a forward record,
#: small enough that the growth it can cost is inside the margin by construction.
EXPLORE_SHARE = 0.05
#: Iterations a candidate's re-solve gets, warm-started from the incumbent's own optimum. One
#: sleeve added to a solved book is a small perturbation; a cold solve of the same problem
#: converged in 104 iterations, so this is headroom, and `converged` is recorded either way.
ADMISSION_ITERATIONS = 120
#: How stale a published scan may be before a reader must treat it as absent. Matches
#: `allocator_proof.MAX_AGE_S`: one number for "this measurement still describes today's book".
#:
#: WHERE 26 COMES FROM: the heavy admission scan is on a 24-HOUR clock, so the tolerance must
#: exceed 24h or a scan is judged stale in the minutes before its own successor runs -- a reader
#: would then see ABSENT once a day, every day, at the moment the book was in fact freshest.
#: 26 = 24 + 2, and the 2 is one missed run's worth of slack measured against the scan's own
#: observed runtime (829s on the 2026-09-12 pass, so ~0.23h) plus scheduler jitter. Anything
#: below 25 re-creates the daily false-absent; far above 26 starts admitting a scan taken before
#: the previous session's book, which is a different book.
ADMISSION_MAX_AGE_S = 26 * 3600
#: Marginal growth this small is inside the noise of a sampled-world estimate, so it is not a
#: win. Expressed as a fraction of the incumbent book's OWN growth rate, and it is the same
#: `allocator_proof.MARGIN_FRAC` the proof uses -- one margin, not two that drift apart.
try:                                                                     # pragma: no cover
    from libs.portfolio.allocator_proof import MARGIN_FRAC as ADMISSION_MARGIN_FRAC
except Exception:                                                        # pragma: no cover
    ADMISSION_MARGIN_FRAC = 0.02

#: Cap on the FULL-KELLY REFERENCE solve in `kelly_fraction`. Not a risk limit -- nothing is ever
#: deployed from this solve -- but a reference on an unbounded simplex does not terminate on
#: anything meaningful, and 500% heat is far above any book this desk could hold. When the
#: reference lands ON it the fraction is reported as an upper bound and says so.
REFERENCE_CAP = 5.0


def _selector_of(e: SleeveEvidence) -> str:
    """The selector (window / session / state suffix) inside a sleeve's own name.

    `sleeve_evidence` builds names as `SYMBOL_family_selector` and keeps symbol and family on the
    record but not the remainder, and the remainder is exactly what a forward clock keys on. So
    it is recovered from the name rather than guessed, and an unparseable name yields "" -- which
    joins on nothing, which is the honest outcome for a name nobody can decompose.
    """
    name = str(e.name)
    rest = name[len(e.symbol) + 1:] if e.symbol and name.startswith(f"{e.symbol}_") else ""
    if e.family and rest.startswith(f"{e.family}_"):
        rest = rest[len(e.family) + 1:]
    return rest


def _annual_sharpe(r: np.ndarray) -> float | None:
    """Standalone annualised Sharpe of a daily-R series, or None when it cannot be measured.

    REPORTED, NEVER RANKED ON. It is on the row so a reader can SEE that the admission decision
    disagreed with the Sharpe ordering -- which is the whole point of the criterion.
    """
    # ON ITS OWN DAYS. A sleeve's standalone Sharpe is a statement about the sleeve, so the days
    # before it existed are not zero-return days in it (defect #4). Reported at 0.285 when it was
    # 3.71, this number is what a reader uses to sanity-check an admission verdict, so a 13x
    # understatement here hid the corrupted input rather than exposing it.
    a = np.asarray(r, dtype=float)
    a = a[np.isfinite(a)]
    if a.size < 2:
        return None
    sd = float(a.std(ddof=1))
    if not (sd > 0):
        return None
    return float(a.mean() / sd * math.sqrt(252.0))


def _corr_to_book(cand: np.ndarray, held: dict[str, float],
                  by_name: dict[str, SleeveEvidence]) -> float | None:
    """Correlation of a candidate's daily R to the HELD book's own daily R, or None.

    The book stream is the heat-weighted sum of what the desk is holding -- the thing the
    candidate is actually being added to, not an average of pairwise correlations, which is a
    different and weaker number.
    """
    legs = [(by_name[k], float(v)) for k, v in held.items()
            if k in by_name and float(v) > 0 and by_name[k].daily_r.size > 1]
    if not legs:
        return None
    obs = min([int(cand.size)] + [int(e.daily_r.size) for e, _ in legs])
    if obs < 30:
        return None
    # PORTFOLIO LEVEL: a day a leg did not exist contributes no P&L to the book stream, so flat
    # is the honest fill HERE (protocol: "flat only at portfolio level, explicitly"). Without the
    # fill the NaN now carried by young sleeves would propagate and return None for every
    # candidate, which would read as "correlation unmeasurable" instead of "recently born".
    stream = np.zeros(obs, dtype=float)
    for e, h in legs:
        stream += h * np.nan_to_num(np.asarray(e.daily_r[-obs:], dtype=float), nan=0.0)
    c = np.nan_to_num(np.asarray(cand[-obs:], dtype=float), nan=0.0)
    if not (stream.std() > 0 and c.std() > 0):
        return None
    return float(np.corrcoef(stream, c)[0, 1])


def marginal_admission(ev: list[SleeveEvidence], worlds: Worlds, cfg: WorldConfig, *,
                       incumbent: dict[str, float], bounds: dict[str, float],
                       total_heat: float,
                       order: dict[str, float] | None = None,
                       prefer: set[str] | None = None,
                       budget_s: float = ADMISSION_CANDIDATE_BUDGET_S,
                       iterations: int = ADMISSION_ITERATIONS,
                       margin_frac: float = ADMISSION_MARGIN_FRAC,
                       warm: dict[str, dict[str, float]] | None = None,
                       explore_share: float = EXPLORE_SHARE,
                       explore_seed: int | None = None) -> dict[str, Any]:
    """dE[log W]_i = E[log W | book + i] - E[log W | book], on ONE world population.

        "Don't rank candidates primarily by Sharpe. Rank by dE[log W] after adding the candidate
         to the existing portfolio. A Sharpe-1.2 strategy at correlation -0.2 to the book can be
         vastly more valuable than a Sharpe-2.5 strategy at correlation +0.9. Now make that
         principle the actual automatic admission criterion."       -- the principal, 2026-09-05

    WHAT WAS ACTUALLY MISSING, measured on this tree. `robust_elog.marginal_delta_elog` has
    computed exactly this since the module was written, and `libs/research/alpha_fitness.py`
    calls it -- inside the EVOLUTIONARY search, to breed alphas. Nothing on the CAPITAL path used
    it. The allocation artifact's field named `marginal_delta_elog` is `AllocationResult.marginal`,
    the per-sleeve GRADIENT at the solved optimum: a real number, a useful ranking for the heat
    cap to trim by, and NOT the marginal value of admitting a candidate the book does not hold.
    A gradient at h_i = 0 says how the objective moves for the first infinitesimal unit; it does
    not say what the book looks like once the optimiser has re-spent its whole budget around the
    new sleeve, and those differ by exactly the reallocation the candidate causes. So the desk
    could rank what it held and could not price what it did not, and the promoter admitted on a
    forward clock with no reference to the book at all.

    EQUAL TOTAL HEAT, WHICH IS THE ONLY FAIR VERSION OF THE QUESTION. Both books are re-solved at
    the SAME total heat on the SAME worlds, so a candidate cannot win by adding exposure -- it
    wins by displacing something, and `displaced` says what paid for it. This is the same
    equalisation `allocator_proof.contest` applies for the same reason. The one exception is a
    desk holding nothing: there is no book to displace from, so both solves are free under the
    same cap and `basis` says `free` rather than `equal_heat`.

    THE MARGIN IS NOT ZERO. A hair's-breadth win over a sampled-world estimate is noise, and
    admitting on it is admitting on luck; the bar is `margin_frac` of the incumbent book's own
    growth rate, the same fraction the proof certificate demands of the allocator itself.

    THE BUDGET IS PER CANDIDATE AND THE SCAN RUNS TO COMPLETION (2026-09-09). `budget_s` bounds
    ONE re-solve, not the pass; every candidate is re-solved every heavy pass, in the `prefer`
    rotation's order. A re-solve that hits its own budget before converging is not a verdict:
    it is written to `unscored` with the partial reading beside it (`partial`), and its book is
    carried in `warm` so the NEXT pass warm-starts that candidate from where this one stopped
    rather than from the incumbent again. Nothing is refused for compute; a candidate the
    solver has not finished with is one the solver continues.

    Returns the artifact block. Every candidate is either SCORED (with its delta, the heat the
    re-solve gave it, what it displaced, and -- reported beside, never ranked on -- its standalone
    Sharpe and its correlation to the held book) or NAMED as unscored with the reason. A partial
    reading is not admitted: absence is never permission, and neither is half a solve.
    """
    t0 = time.time()
    by_name = {e.name: e for e in ev}
    names = [e.name for e in ev]
    held = {k: float(v) for k, v in (incumbent or {}).items()
            if k in by_name and float(v) > 1e-9}
    cap = max(float(HEAT_HARD_CEILING), float(total_heat))

    def _ub(allowed: set[str]) -> dict[str, float]:
        """Per-sleeve bounds that admit exactly `allowed` -- everything else is pinned to zero."""
        return {n: (min(float(bounds.get(n, cap)), cap) if n in allowed else 0.0) for n in names}

    allowed_base = set(held)
    room = float(sum(_ub(allowed_base).values()))
    target: float | None
    if allowed_base and room > 1e-9:
        target, basis = min(float(total_heat), room), "equal_heat"
    else:
        target, basis = None, "free"

    doc: dict[str, Any] = {
        "measured_utc": datetime.now(UTC).isoformat(),
        "basis": basis, "total_heat": round(float(total_heat), 6),
        "margin_frac": margin_frac, "budget_s": budget_s,
        "budget": {"per_candidate_s": budget_s, "iterations": iterations,
                   "scope": ("per candidate; the scan re-solves EVERY candidate each pass and a "
                             "re-solve that hits its budget is carried forward warm-started, "
                             "never refused for compute")},
        # PARTIAL SOLVES, carried to the next pass: candidate -> the book the solver reached.
        "warm": {}, "partial": {},
        # THE SCAN CARRIES ITS OWN EXPIRY, like the proof certificate does. `promoter` refuses to
        # price capital from a scan older than this -- stated here so the rule travels with the
        # measurement instead of living only in the reader.
        "max_age_s": ADMISSION_MAX_AGE_S,
        "incumbent": {k: round(v, 6) for k, v in sorted(held.items(), key=lambda kv: -kv[1])},
        "rule": ("a candidate is admitted when re-solving the book WITH it, at the same total "
                 "heat on the same sampled worlds, raises robust mean log growth by more than "
                 "the margin -- never on its standalone Sharpe, which is reported beside the "
                 "decision so a reader can see the two disagree"),
        "candidates": {}, "admitted": [], "refused": [], "unscored": {},
        # THE PARTS OF EVERY PRICED SLEEVE. `pf_allocator` names a sleeve `SYM_family_selector`;
        # the forward clocks and the promoter name the same thing `SYM.selector[.STATE]` or by
        # its certificate key. Publishing the parts is what lets `promoter._join_keys` recognise
        # them as the same sleeve instead of matching nothing and calling it a refusal.
        "universe": {e.name: {"symbol": e.symbol, "family": e.family,
                              "selector": _selector_of(e)} for e in ev},
    }
    if worlds is None or not ev:
        doc["status"] = "UNMEASURED: no world population"
        return doc

    g_base = 0.0
    base_heat: dict[str, float] = {}
    if allowed_base:
        try:
            base = optimise(ev, hard_cap=cap, target=target, cfg=cfg, worlds=worlds,
                            max_per_sleeve=_ub(allowed_base), warm_start=held or None)
        except ValueError as exc:
            doc["status"] = f"UNMEASURED: the held book cannot be re-solved ({exc})"
            return doc
        g_base, base_heat = float(base.mean_log_growth), dict(base.heat)
        if not math.isfinite(g_base):
            # A ruinous incumbent has no growth rate to add to. Reporting a delta against -inf
            # would make every candidate look infinitely valuable, which is the opposite of true.
            doc["status"] = ("UNMEASURED: the held book is wiped out in at least one sampled "
                             "world, so it has no growth rate a candidate can be marginal to")
            return doc
    doc["incumbent_elogw_per_day"] = round(g_base, 10)
    doc["incumbent_elogw_per_year"] = round(g_base * 252.0, 6)
    bar = abs(g_base) * float(margin_frac)
    doc["margin_per_day"] = round(bar, 10)

    # THE ORDER, AND WHY IT ROTATES. Within a pass the most promising candidate goes first: the
    # free solve's marginal at the current book is the best cheap guess at which re-solve is worth
    # spending a second on. But a pass whose budget runs out would otherwise leave the SAME tail
    # unmeasured every hour -- a candidate below the cut could never be admitted, which is a
    # compute limit hardening into a verdict. So whatever the last pass could not reach goes
    # FIRST, ranked among itself, and the rest follow ranked among themselves. Coverage is
    # therefore complete over a few passes without any pass giving up its ranking.
    cand_names = [n for n in names if n not in allowed_base]
    rank = order or {}
    pref = set(prefer or ())
    cand_names.sort(key=lambda n: (n not in pref, -float(rank.get(n, 0.0)), n))
    doc["n_candidates"] = len(cand_names)
    doc["order"] = ("last pass's unreached candidates first, then the rest; each group ranked by "
                    "the free solve's marginal at the current book"
                    if pref else "ranked by the free solve's marginal at the current book")
    doc["n_carried_from_last_unreached"] = len(pref & set(cand_names))

    warm_in = {str(k): v for k, v in (warm or {}).items() if isinstance(v, dict) and v}
    solve_s: list[float] = []
    for name in cand_names:
        e = by_name[name]
        sharpe = _annual_sharpe(e.daily_r)
        corr = _corr_to_book(e.daily_r, held, by_name)
        row: dict[str, Any] = {
            "sharpe_standalone_annual": (None if sharpe is None else round(sharpe, 4)),
            "corr_to_book": (None if corr is None else round(corr, 4)),
            "family": e.family, "symbol": e.symbol, "selector": _selector_of(e),
            "forward_days": int(e.forward_days), "live_days": int(e.live_days),
        }
        # WHERE THIS SOLVE STARTS: the point the last pass's solve stopped at, when it hit its
        # budget, else the incumbent's own optimum with the candidate at zero. The projection
        # inside `optimise` re-fits a carried point to THIS pass's bounds and cap.
        carried = warm_in.get(name)
        ws = ({str(k): float(v) for k, v in carried.items()} if carried
              else {**base_heat, name: 0.0})
        deadline = (time.time() + float(budget_s)) if budget_s and budget_s > 0 else None
        t_c = time.time()
        try:
            ext = optimise(ev, hard_cap=cap, target=target, cfg=cfg, worlds=worlds,
                           max_per_sleeve=_ub(allowed_base | {name}),
                           warm_start=ws, iterations=iterations, deadline=deadline)
        except ValueError as exc:
            doc["unscored"][name] = f"re-solve refused ({exc}); NOT admitted"
            continue
        solve_s.append(time.time() - t_c)
        row.update({"solve_s": round(solve_s[-1], 3), "iterations": int(ext.iterations),
                    "budget_hit": bool(ext.budget_hit),
                    "warm_started_from_last_pass": bool(carried)})
        got = float(ext.heat.get(name, 0.0))
        g_ext = float(ext.mean_log_growth)
        if not math.isfinite(g_ext):
            row.update({"delta_elogw_per_day": None, "heat_earned": round(got, 6),
                        "admit": False, "converged": bool(ext.converged),
                        "why": "the book WITH this candidate is wiped out in a sampled world"})
            doc["candidates"][name] = row
            doc["refused"].append(name)
            continue
        delta = g_ext - g_base
        # WHAT PAID FOR IT. The candidate's own heat is not displacement -- it is the thing being
        # paid for -- so it is excluded here; `heat_earned` already carries it.
        displaced = {k: round(float(ext.heat.get(k, 0.0)) - v, 6)
                     for k, v in base_heat.items()
                     if k != name and abs(float(ext.heat.get(k, 0.0)) - v) > 1e-5}
        admit = bool(delta > bar and got > 1e-5)
        if ext.budget_hit and not ext.converged and not admit:
            # A PARTIAL SOLVE IS NOT A REFUSAL AND NOT A VERDICT. The reading is written beside
            # the name so a reader can see how far it got, the book it reached is carried, and
            # the next pass continues from there. It is not admitted on half a solve either.
            doc["unscored"][name] = (
                f"per-candidate budget ({float(budget_s):.1f}s) hit after {ext.iterations} "
                f"iteration(s) without convergence; NOT admitted on a partial reading "
                f"(dE {delta:+.6f}/day so far) -- carried forward warm-started, so the next "
                f"pass continues this solve instead of restarting it")
            doc["warm"][name] = {k: round(float(v), 8) for k, v in ext.heat.items()
                                 if float(v) > 0.0}
            doc["partial"][name] = {**row, "delta_elogw_per_day": round(delta, 10),
                                    "heat_earned": round(got, 6)}
            continue
        sr, rho = row["sharpe_standalone_annual"], row["corr_to_book"]
        shape = (f"standalone Sharpe {sr:.2f}" if sr is not None else "Sharpe unmeasured")
        shape += (f" at correlation {rho:+.2f} to the held book" if rho is not None
                  else ", correlation to the book unmeasured")
        if admit:
            why = (f"admitted: re-solving at {float(total_heat):.2%} total heat with it raises "
                   f"robust growth {delta:+.6f}/day ({delta * 252.0:+.2%}/yr) and it earns "
                   f"{got:.2%} heat -- {shape}")
        elif got <= 1e-5:
            why = (f"refused: the optimiser gives it {got:.4%} heat at equal total heat, so the "
                   f"book does not want it at any size -- {shape}")
        else:
            why = (f"refused: {delta:+.6f}/day is not above the {bar:.6f}/day noise margin -- "
                   f"{shape}")
        row.update({
            "delta_elogw_per_day": round(delta, 10),
            "delta_elogw_per_year": round(delta * 252.0, 6),
            "heat_earned": round(got, 6),
            "displaced": dict(sorted(displaced.items(), key=lambda kv: kv[1])[:6]),
            "converged": bool(ext.converged), "admit": admit, "why": why,
        })
        doc["candidates"][name] = row
        (doc["admitted"] if admit else doc["refused"]).append(name)

    # THE RANKING IS THE DELTA, and it is written in that order so a reader cannot mistake which
    # number decided. Sharpe is on every row and orders nothing.
    doc["admitted"].sort(key=lambda n: -(doc["candidates"][n].get("delta_elogw_per_day") or 0.0))
    doc["refused"].sort(key=lambda n: -(doc["candidates"][n].get("delta_elogw_per_day") or -1e9))
    doc["n_scored"] = len(doc["candidates"])
    doc["priced"] = doc["n_scored"]
    doc["n_admitted"] = len(doc["admitted"])
    doc["n_unscored"] = len(doc["unscored"])
    doc["n_partial"] = len(doc["partial"])
    doc["elapsed_s"] = round(time.time() - t0, 1)
    doc["per_candidate_s"] = (round(float(np.mean(solve_s)), 3) if solve_s else None)
    doc["max_candidate_s"] = (round(float(max(solve_s)), 3) if solve_s else None)
    doc["status"] = "MEASURED"
    # EXPLORATION INSIDE THE MARGIN: the ambiguous candidates, funded a little from within the
    # book so they accrue a forward record instead of standing at zero for ever. Computed here
    # because it needs every row's delta against THIS bar; applied (or not) by the caller, which
    # is where the published book lives, and billed by the `explore_thompson` rail.
    doc["explore"] = thompson_explore(doc["candidates"], held, bounds, bar=bar,
                                      total_heat=float(total_heat), basis=basis,
                                      share=explore_share, seed=explore_seed)
    # THE RENT LINE (AGENTS.md): what this criterion is worth is the growth the admitted set adds
    # to the held book, measured the same way each candidate was. It is a SUM OF SEPARATE
    # marginals, not the delta of admitting them together -- said here so nobody reads it as the
    # joint number, which would need one more solve and is the honest next measurement.
    doc["rent"] = {
        "unit": "log-wealth per day",
        "sum_admitted_delta_elogw_per_day": round(sum(
            float(doc["candidates"][n].get("delta_elogw_per_day") or 0.0)
            for n in doc["admitted"]), 10),
        "note": ("sum of individually-measured marginals over the admitted set, each against the "
                 "same held book at the same total heat; the joint delta of admitting all of "
                 "them at once is a different and smaller number"),
    }
    return doc


def thompson_explore(rows: dict[str, dict[str, Any]], held: dict[str, float],
                     bounds: dict[str, float], *, bar: float, total_heat: float, basis: str,
                     share: float = EXPLORE_SHARE, seed: int | None = None) -> dict[str, Any]:
    """A small Thompson-sampled heat for the candidates the criterion could not decide.

    THE HOLE. A candidate whose dE[log W] lands inside the noise margin is refused -- correctly,
    a hair's-breadth win is luck -- and refused again next hour, and the hour after: nothing
    ever resolves the ambiguity because a sleeve at zero heat accrues no forward record. The
    research bandit explores among research DIRECTIONS; nothing explored among validated sleeves
    for capital.

    THE DRAW. For each candidate in the band |dE| <= bar (and which the re-solve wanted at some
    size), one draw z ~ N(dE, bar): the margin IS the declared noise scale of the estimate, so a
    candidate is funded in proportion to how often its own noise says it wins. Draws at or below
    zero fund nothing this pass. Winners share `share x total heat`, each capped at the heat the
    equal-heat re-solve gave it and at its per-sleeve bound.

    FROM WITHIN THE TOTAL, OR NOT AT ALL. The heat is lent by the incumbents pro rata (see
    `apply_explore`): the total is unchanged by construction, no incumbent goes below zero or
    above its bound (they only scale down), and when that cannot be satisfied for a pass --
    nothing held, the free basis, or a lent share the incumbents cannot fund -- the block says
    so and funds nothing. `seed` fixed per UTC day by the caller keeps the explored set stable
    within a day rather than re-drawn every pass, which is the churn control.
    """
    out: dict[str, Any] = {
        "status": "NONE", "applied": False, "share": float(share), "bar": float(bar),
        "rule": ("Thompson draw z ~ N(dE[log W], margin) per candidate inside |dE| <= margin; "
                 "positive draws share EXPLORE_SHARE of total heat, each capped at the heat the "
                 "re-solve gave the candidate and at its bound; lent by incumbents pro rata, "
                 "total unchanged; billed by the explore_thompson rail")}
    if basis != "equal_heat" or not held:
        return {**out, "why": "no held book to fund exploration from (free basis)"}
    band: dict[str, dict[str, Any]] = {}
    for name, row in rows.items():
        d = row.get("delta_elogw_per_day")
        got = float(row.get("heat_earned") or 0.0)
        if d is None or row.get("admit") or got <= 1e-5 or abs(float(d)) > float(bar):
            continue
        band[name] = {"delta_elogw_per_day": float(d), "heat_earned_in_resolve": got}
    out["n_band"] = len(band)
    if not band:
        return {**out, "why": ("no candidate inside the margin that the re-solve wanted at any "
                               "size; nothing is ambiguous this pass")}
    try:
        from libs.portfolio.rails import rail_multiplier as _rail_mult
        mult = float(_rail_mult("explore_thompson"))
    except Exception:
        mult = 1.0
    budget = float(share) * mult * float(total_heat)
    out.update({"rail_multiplier": round(mult, 4), "budget_heat": round(budget, 6),
                "seed": seed})
    if budget <= 1e-9:
        return {**out, "why": "the exploration budget is zero (share, rail multiplier or total)"}
    rng = np.random.default_rng(seed)
    sigma = max(float(bar), 0.0)
    for b in band.values():
        b["z_draw"] = float(rng.normal(b["delta_elogw_per_day"], sigma)) if sigma > 0 \
            else b["delta_elogw_per_day"]
    winners = {n: b["z_draw"] for n, b in band.items() if b["z_draw"] > 0.0}
    if not winners:
        out["band"] = {n: {k: round(v, 10) for k, v in b.items()} for n, b in band.items()}
        return {**out, "why": ("every ambiguous candidate's draw came out at or below zero this "
                               "pass; nothing funded, the band is listed")}
    z_sum = float(sum(winners.values()))
    heats: dict[str, float] = {}
    for name, z in winners.items():
        cap_n = min(float(bounds.get(name, total_heat)), band[name]["heat_earned_in_resolve"])
        x = min(budget * z / z_sum, cap_n)
        if x > 1e-6:
            heats[name] = x
    for name in band:
        band[name]["explore_heat"] = round(heats.get(name, 0.0), 6)
    out["band"] = {n: {k: (round(v, 10) if isinstance(v, float) else v) for k, v in b.items()}
                   for n, b in band.items()}
    x_total = float(sum(heats.values()))
    if x_total <= 1e-9:
        return {**out, "why": "every positive draw capped to nothing (bound or re-solve heat)"}
    inc_total = float(sum(held.values()))
    if x_total >= inc_total - 1e-9:
        return {**out, "why": (f"the lent share {x_total:.4%} is not fundable from within the "
                               f"{inc_total:.4%} the incumbents hold; nothing funded")}
    out.update({"status": "FUNDED", "explore_heat": {k: round(v, 6) for k, v in heats.items()},
                "explore_heat_total": round(x_total, 6),
                "why": (f"{len(heats)} of {len(band)} ambiguous candidate(s) drew positive; "
                        f"{x_total:.4%} of heat lent from within the book's "
                        f"{inc_total:.4%}")})
    return out


def apply_explore(funded: dict[str, float], heats: dict[str, float],
                  bounds: dict[str, float]) -> tuple[dict[str, float], str]:
    """The published book with the exploration heat lent from within it, or the book unchanged.

    Incumbents scale by one common factor so the total is preserved exactly; a candidate already
    in the book is SET to its exploration heat, never topped up. Returns (book, why) and refuses
    -- returning the input book -- whenever the rule cannot be honoured: nothing held, a lent
    share the incumbents cannot fund, an incumbent that would have to GROW past its bound to
    keep the total (a held book already carrying more exploration than this draw), or a total
    that would move. Each refusal is the reason string, never a silent no-op.
    """
    base = {k: float(v) for k, v in funded.items() if float(v) > 0.0}
    lend = {k: float(v) for k, v in (heats or {}).items() if float(v) > 1e-9}
    if not lend:
        return dict(base), "no exploration heat to apply"
    total = float(sum(base.values()))
    if total <= 1e-9:
        return dict(base), "no held book to lend from"
    incumbents = {k: v for k, v in base.items() if k not in lend}
    inc_sum = float(sum(incumbents.values()))
    x_total = float(sum(lend.values()))
    if inc_sum <= 1e-9 or x_total >= total - 1e-9:
        return dict(base), (f"the lent {x_total:.4%} is not fundable from the {inc_sum:.4%} "
                            "the incumbents hold")
    scale = (total - x_total) / inc_sum
    if scale > 1.0 + 1e-9:
        return dict(base), ("the held book already carries more exploration heat than this "
                            "draw; incumbents would have to grow to keep the total, so the "
                            "book stands as held")
    for k, v in lend.items():
        if v > float(bounds.get(k, total)) + 1e-9:
            return dict(base), f"{k}: exploration heat {v:.4%} exceeds its bound"
    book = {k: v * scale for k, v in incumbents.items()}
    book.update(lend)
    if abs(sum(book.values()) - total) > 1e-6:
        return dict(base), "the explored book would not sum to the held total"
    return book, (f"{x_total:.4%} lent to {len(lend)} candidate(s); incumbents scaled by "
                 f"{scale:.4f}; total {total:.4%} unchanged")


def without_explore(book: dict[str, float], lend: dict[str, float]) -> dict[str, float]:
    """The explored book with the lent heat handed back: incumbents scaled up to the total.

    A counterfactual for SCORING (the rail's `growth_without`), never published -- scaling the
    incumbents back up can put one a hair over its bound, which is fine for a comparison on the
    same worlds and not fine for a book the gateway sizes from. Empty when there is no incumbent
    to hand the heat back to.
    """
    inc = {k: float(v) for k, v in book.items() if k not in lend and float(v) > 0.0}
    x = float(sum(float(book.get(k, 0.0)) for k in lend))
    s = float(sum(inc.values()))
    if s <= 1e-12:
        return {}
    return {k: v * (s + x) / s for k, v in inc.items()}


def zeroed_live(ev: list[SleeveEvidence], funded: dict[str, float],
                extra: dict[str, float] | None = None) -> dict[str, str]:
    """Rostered sleeves this solve gave NO heat -- 0% right now, and NOT retired.

        "Never have 'this strategy is allocated 3% forever'. Have 'this strategy currently earns
         7.4% portfolio risk because its posterior edge, uncertainty, conditional state and
         covariance make that the current robust log-optimal allocation.' Five minutes/hour/session
         later, it can be 0%."                                      -- the principal, 2026-09-05

    THE HOLE THIS FILLS, TRACED END TO END. `run()` publishes `book` filtered to heat > 1e-5, so a
    sleeve the optimiser zeroes DISAPPEARS from the artifact. `decision_core.book_from_allocation`
    then cannot see it, `gateway` reads `from_book = name in book` as False, and
    `decision_core.promoted_lot` falls through to `ramped_fraction` -> `sizing.clamp_risk_frac`,
    which FLOORS at BASE_RISK_FRAC. So the allocator's "zero" arrived at the venue as 3% of equity
    times the authority ramp. The allocator could not say zero; it could only say "small", and
    below 3% it could not even say that.

    Naming them explicitly is what lets the answer be zero. The gateway already handles a zero
    lot at every placement site ("allocator gave this sleeve no heat; skipped") -- that path was
    simply unreachable. Nothing here retires anything: the sleeve keeps its row, its clock and its
    certificate, and the next pass that wants it funds it again.

    Only sleeves the desk can actually TRADE are listed (the promoted roster plus whatever the
    caller passes as `extra`, normally the previously-held book), because a list of the hundred
    library sleeves nobody holds would be noise in a file the money path reads.
    """
    priced = {e.name for e in ev}
    rostered: set[str] = set()
    try:
        rows = json.loads((BASE / "data" / "sleeves.json").read_text("utf-8")).get("sleeves") or []
        rostered = {str(r.get("name")) for r in rows
                    if isinstance(r, dict) and str(r.get("status") or "").upper() == "LIVE"}
    except (OSError, ValueError, AttributeError):
        rostered = set()
    rostered |= {str(k) for k in (extra or {})}
    out: dict[str, str] = {}
    for name in sorted(rostered):
        if name in funded or name not in priced:
            continue
        out[name] = ("the current solve gives this sleeve no heat: its posterior edge, "
                     "uncertainty, conditional state and covariance with the rest of the book "
                     "make zero the log-optimal allocation right now. NOT retired -- its row, "
                     "clock and certificate stand, and the next solve that wants it funds it.")
    return out


def kelly_fraction(ev: list[SleeveEvidence], cfg: WorldConfig, *,
                   deployed: float, bounds: dict[str, float],
                   seed: int = 0) -> dict[str, Any]:
    """The effective Kelly fraction, MEASURED -- not an emergent property nobody can name.

        "fractional Kelly rather than blindly betting full Kelly"   -- the principal, 2026-09-05

    Full Kelly on an ESTIMATED edge is how estimation error compounds into ruin, and this desk
    does shrink -- in six separate places, none of which ever produced a number anybody could
    quote. `robust_elog` deflates the mean for the winner's curse, shrinks it hierarchically
    toward the family and toward no edge, draws the mean from its own posterior, decays the edge
    in 30% of worlds, widens the cost, overlays crisis worlds, blends the objective 50/50 with
    the CVaR of the worst fifth, and charges correlation-weighted redundancy. The book that
    results is a fraction of the full-Kelly book, and the fraction was nowhere.

    HOW IT IS MEASURED. The same evidence and the same solver are run against a POINT-ESTIMATE
    reference: no winner's-curse deflation (`n_trials = 1`), no crisis worlds, no edge decay, no
    cost spread, no CVaR blend and no redundancy charge -- the book a full-Kelly bettor who
    believed his own backtest would hold. `f_eff = H_deployed / H_full_kelly`.

    WHAT IT DOES NOT CLAIM. The residual sampling noise in the posterior MEAN (`se` in
    `_posterior_mu`) is present in both solves, so it is not counted as shrinkage; the reference
    is "the same estimates, believed" and not "the truth". The rungs are measured one at a time
    against the same reference, so each says what THAT layer costs in heat, and they do not sum:
    the layers interact.

    A PINNED REFERENCE IS REPORTED AS A BOUND, NOT AS A NUMBER. Full Kelly on a hundred
    believed-at-face-value sleeves is enormous, so the reference solve needs a cap or it does not
    terminate on anything sane. `REFERENCE_CAP` is set far above any heat this desk would ever
    deploy, and when the solve still sits ON it the fraction reported is an UPPER BOUND -- the
    true full-Kelly book is larger, so the true fraction is smaller. Reporting the pinned ratio
    as if it were measured is a defect wearing a plausible answer, which is the one thing this
    module's own plausibility fence exists to refuse.
    """
    from dataclasses import replace as _replace

    out: dict[str, Any] = {
        "definition": ("f_eff = deployed heat / the heat a full-Kelly bettor would deploy on the "
                       "same evidence believed at face value (no winner's-curse deflation, no "
                       "crisis worlds, no edge decay, no cost spread, no CVaR blend, no "
                       "redundancy charge)"),
        "deployed_heat": round(float(deployed), 6),
    }
    # A REFERENCE, NOT A SIZING DECISION, so it is measured on a smaller population than the book
    # itself. Seven solves at the heavy pass's own 256 worlds would add minutes to a clock whose
    # job is to keep the book fresh, and the fast leg stands down while an allocator runs. The
    # fraction is a ratio of two totals and is insensitive to the last few worlds; the BOOK is
    # never solved on this population.
    naive_cfg = _replace(cfg, crisis_prob=0.0, decay_prob=0.0, cost_uncertainty=0.0,
                         robust_lambda=0.0, redundancy_lambda=0.0, seed=int(seed) + 7717,
                         n_worlds=min(int(cfg.n_worlds), 96), n_rows=min(int(cfg.n_rows), 200))
    naive_ev = [_replace(e, n_trials=1) for e in ev]
    out["reference_population"] = {"n_worlds": naive_cfg.n_worlds, "n_rows": naive_cfg.n_rows}
    try:
        w_full = sample_worlds(naive_ev, naive_cfg)
        full = optimise(naive_ev, hard_cap=REFERENCE_CAP, target=None, cfg=naive_cfg,
                        worlds=w_full, max_per_sleeve=None, iterations=200)
    except (ValueError, MemoryError) as exc:
        out["status"] = f"UNMEASURED: the full-Kelly reference could not be solved ({exc})"
        return out
    h_full = float(full.total_heat)
    out["full_kelly_heat"] = round(h_full, 6)
    out["full_kelly_annual_growth_pct"] = full.annual_growth_pct
    out["reference_cap"] = REFERENCE_CAP
    if not (h_full > 1e-9):
        out["status"] = ("UNMEASURED: even believed at face value the evidence wants no heat, so "
                         "there is no full-Kelly book to be a fraction of")
        return out
    pinned = h_full >= REFERENCE_CAP - 1e-6
    out["kelly_fraction"] = round(float(deployed) / h_full, 4)
    out["reference_pinned"] = bool(pinned)
    out["status"] = "BOUND" if pinned else "MEASURED"
    if pinned:
        out["bound_note"] = (
            f"the full-Kelly reference sits ON its {REFERENCE_CAP:.0%} cap, so the true reference "
            f"is larger and the true fraction is SMALLER than {out['kelly_fraction']:.4f}. "
            f"Reported as an upper bound rather than as a measurement.")

    # THE LADDER: what each shrinkage layer costs in heat, each measured alone against the same
    # reference, so "where and how much" is a table rather than a paragraph.
    rungs: dict[str, Any] = {}
    ladder = (
        ("winners_curse_deflation", {}, False),
        ("crisis_worlds", {"crisis_prob": cfg.crisis_prob,
                           "crisis_vol_mult": cfg.crisis_vol_mult,
                           "crisis_common_share": cfg.crisis_common_share}, True),
        ("edge_decay", {"decay_prob": cfg.decay_prob, "decay_floor": cfg.decay_floor}, True),
        ("cost_uncertainty", {"cost_uncertainty": cfg.cost_uncertainty}, True),
        ("cvar_blend", {"robust_lambda": cfg.robust_lambda, "cvar_alpha": cfg.cvar_alpha}, True),
        ("redundancy_charge", {"redundancy_lambda": cfg.redundancy_lambda}, True),
    )
    for label, overrides, keep_naive_ev in ladder:
        try:
            c = _replace(naive_cfg, **overrides)
            e_ = naive_ev if keep_naive_ev else list(ev)
            w_ = sample_worlds(e_, c)
            r_ = optimise(e_, hard_cap=REFERENCE_CAP, target=None, cfg=c, worlds=w_,
                          max_per_sleeve=None, iterations=200)
            h_ = float(r_.total_heat)
            rungs[label] = {
                "heat": round(h_, 6),
                "heat_cost_vs_full_kelly": round(h_ - h_full, 6),
                # A RUNG PINNED AT THE SAME CAP AS THE REFERENCE HAS NOT BEEN MEASURED. Both
                # sides sit on the bound, the difference is zero by construction, and "this layer
                # costs nothing" would be the wrong reading of a saturated solve.
                "pinned": bool(h_ >= REFERENCE_CAP - 1e-6),
                "settings": {k: float(v) for k, v in overrides.items()} or
                            {"n_trials": "the desk's own search intensity"}}
            if rungs[label]["pinned"] and pinned:
                rungs[label]["why"] = ("both this rung and the reference sit on the "
                                       f"{REFERENCE_CAP:.0%} cap: UNMEASURED, not costless")
        except (ValueError, MemoryError) as exc:
            rungs[label] = {"status": f"UNMEASURED ({type(exc).__name__}: {exc})"}
    rungs["per_sleeve_bounds"] = {
        "note": ("drawdown-derived per-sleeve caps and the mechanism cap bind the COMPOSITION as "
                 "well as the total; they are applied to the deployed book and not to the "
                 "reference, so their effect is inside f_eff rather than a rung of its own"),
        "n_bounded": sum(1 for v in bounds.values() if math.isfinite(v)),
    }
    out["ladder"] = rungs
    out["ladder_note"] = ("each rung is that layer ALONE against the same full-Kelly reference; "
                          "they interact, so they do not sum to the total shrinkage")
    return out


def run(mode: str = "normal", *, seed: int = 0) -> dict[str, Any]:
    """One allocator pass. Returns the artifact it wrote."""
    t0 = time.time()
    heavy = mode == "heavy"
    daily, forward = build_evidence(force=heavy)
    live = live_days_by_sleeve()
    certified, cert_acct = certified_evidence()
    # THE SCALP LANE JOINS THE SOLVE. Its clocks are its certificates -- the ten gates have no
    # path that certifies an M5/M15 spec -- so their FORWARD ledgers are the evidence, and until
    # this line existed no scalp sleeve was ever in the priced universe. A matured scalp clock
    # therefore reached the roster at STANDBY and could never leave it, because `admission_of`
    # had nothing to join to and `_door_status` writes LIVE only on a MEASURED admission.
    scalp, scalp_acct = scalp_evidence()
    daily = align(align(daily, certified), scalp)
    _log(f"aligned universe: {daily.shape[1]} sleeves on {daily.shape[0]} trading days "
         f"({len(scalp)} of them scalp clocks priced on forward ledgers)")
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
                         trades_by_sleeve=trades_by_sleeve, broker_utc_offset_h=broker_off,
                         # The scalp lane's series IS its forward record, so its own day
                         # count is the forward day count. `join_forward` never sees these
                         # names -- they are not in `forward` -- so nothing else supplies it.
                         forward_only_days={n: len(sr) for n, sr in scalp.items()})
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
        except Exception as exc:
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
    #
    # PER FACTOR BLOCK, UNDER THAT SCALAR (2026-09-09). The scalar fused every sleeve onto one
    # common factor at the same loading, so a gold sleeve was stressed for a USD co-explosion it
    # does not share with EURUSD. The calibration now also measures the stress-regime correlation
    # INSIDE each block `libs/risk/fx_factors` can name (USD leg, JPY leg, metals) and hands each
    # sleeve its block's share -- with the ratcheted scalar as the CEILING, so a block measured
    # less fused keeps that independence in crisis worlds and nothing is ever stressed harder.
    cov_cal = None
    try:
        from libs.portfolio.conditional_covariance import calibrate as _calibrate_cov
        _base = WorldConfig()
        _hist = daily.to_numpy(dtype=float)
        cov_cal = _calibrate_cov(_hist, labels or None,
                                 standing_share=_base.crisis_common_share,
                                 standing_vol_mult=_base.crisis_vol_mult,
                                 symbols={e.name: e.symbol for e in ev},
                                 names=[str(c) for c in daily.columns])
        _log(f"crisis calibration: common_share={cov_cal.crisis_common_share:.3f} "
             f"vol_mult={cov_cal.crisis_vol_mult:.2f} ({cov_cal.note})")
    except Exception as exc:
        _log(f"crisis calibration unavailable ({type(exc).__name__}: {exc}); constants stand")

    # THE ALLOCATOR LISTENS TO THE DRIFT MONITOR (2026-09-05). `drift_monitor` has written
    # `reports/DRIFT.json` -- structure_verdict, hazard_max, what_changed -- naming this crisis
    # overlay as a consumer, and nothing here had ever opened the file. So the desk could know its
    # sleeves had fused onto one factor and still draw the same 6% crisis worlds it draws on a
    # quiet Tuesday. STRUCTURE_SHIFTED now multiplies that share, DRIFT_AHEAD does so in
    # proportion to the hazard, and a stale or absent report changes nothing and says so. It is
    # not a rail: it changes the POPULATION E[log W] solves over, not a cap on the answer.
    drift_doc, drift_why = read_drift()
    crisis_share, crisis_why = crisis_share_from_drift(drift_doc, WorldConfig().crisis_prob)
    _log(f"drift: {drift_why}")
    _log(f"crisis worlds: {crisis_why}")
    # THE HAZARD, BEFORE THE SOLVE AND BEFORE ANY RETIREMENT THRESHOLD. Under `HAZARD_MODE =
    # "decay_posterior"` each sleeve with a measured hazard carries it as its OWN decay
    # probability, capped at the blanket, so the healthy ones stop paying the blanket 30% and
    # the breaking ones pay no more than before (`apply_decay_posterior`). Under "mean_shrink"
    # the previous tilt of the posterior mean runs instead, billed by the `hazard_shrink` rail.
    # Exactly one of the two runs: the hazard is one fact and is charged once.
    _haz = hazard_by_sleeve(drift_doc)
    _blanket = WorldConfig().decay_prob
    if HAZARD_MODE == "mean_shrink":
        hazard_meta = apply_hazard_shrink(ev, _haz)
        decay_meta: dict[str, Any] = {
            "mode": "mean_shrink", "blanket": _blanket, "n_from_hazard": 0,
            "n_blanket": len(ev), "by_sleeve": {},
            "why": ("HAZARD_MODE is mean_shrink: the hazard tilts the posterior mean "
                    "(hazard_shrink) and every sleeve pays the blanket decay")}
        if hazard_meta["n_shrunk"]:
            _tilted = ", ".join(f"{k}={v:.2f}"
                                for k, v in list(hazard_meta["applied"].items())[:5])
            _log(f"hazard shrink: {hazard_meta['n_shrunk']} sleeve(s) tilted ({_tilted})")
    else:
        decay_meta = apply_decay_posterior(ev, _haz, _blanket)
        hazard_meta = {"applied": {}, "n_shrunk": 0, "mode": HAZARD_MODE,
                       "superseded_by": "decay_posterior",
                       "rule": ("the hazard enters as each sleeve's own decay probability "
                                "(see decay_posterior); the post-hoc mean tilt did not run")}
        if decay_meta["n_from_hazard"]:
            _relieved = sorted(decay_meta["by_sleeve"].items(),
                               key=lambda kv: -kv[1]["relief_vs_blanket"])[:5]
            _relieved_txt = ", ".join(f"{k}={v['decay_prob_i']:.2f}" for k, v in _relieved)
            _log(f"decay posterior: {decay_meta['n_from_hazard']} sleeve(s) carry their own "
                 f"decay (blanket {_blanket:.2f}); most relieved {_relieved_txt}")

    cfg = WorldConfig(seed=seed, regime_labels=labels, regime_probs=probs,
                      # The fast clock buys its speed here and nowhere else: a smaller world
                      # population, never a shortcut through the posterior or the crisis worlds.
                      n_worlds=256 if heavy else 128,
                      n_rows=384 if heavy else 256,
                      crisis_prob=crisis_share,
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

    # 1. WHAT GROWTH ACTUALLY WANTS -- no mandate, no floor, AND NO POLICY CAP. This number
    # certifies the target, so a cap on it is a cap on the whole law: the free optimum was solved
    # with `hard_cap=HEAT_HARD_CEILING` until 2026-09-07, which meant "what growth wants" could
    # never be reported above 30% and the removal of the constant one layer up was inert. The
    # bound here is the MEASUREMENT bound (`CURVE_SAMPLE_MAX`) -- how far the desk is willing to
    # simulate -- and nothing is deployed at a heat the curve and the survival surface have not
    # both justified further down.
    bounds = per_sleeve_bounds(dd, HEAT_TARGET)
    free = optimise(ev, hard_cap=CURVE_SAMPLE_MAX, target=None, cfg=cfg, worlds=worlds,
                    max_per_sleeve=bounds)
    _log(f"free optimum H*={free.total_heat:.2%} ann={free.annual_growth_pct:.1f}% "
         f"P(annual loss)={free.prob_annual_loss:.1%}")
    # A SANITY FENCE, NOT A CAP. Nothing in this desk's history compounds at four figures a year;
    # a number that large is a broken input, and the one that produced 2.8e14% was sleeves stacked
    # on mismatched date clocks. The fence does not clip the number -- clipping would hide the
    # defect behind a plausible-looking answer -- it refuses the whole pass.
    # A fence at or below zero is OFF (QUANT_IMPLAUSIBLE_ANNUAL_PCT=0), and the pass then follows
    # the optimum whatever it computes -- the principal's instruction of 2026-09-11.
    implausible = (IMPLAUSIBLE_ANNUAL_PCT > 0
                   and free.annual_growth_pct > IMPLAUSIBLE_ANNUAL_PCT)
    if implausible:
        _log(f"REFUSING THIS PASS: free optimum reports {free.annual_growth_pct:.3g}% a year, "
             f"above the {IMPLAUSIBLE_ANNUAL_PCT:.0f}% plausibility fence. That is an input "
             f"defect, not an opportunity. The previous book stands.")

    # 2. THE CURVE, then the law.
    curve = growth_curve(ev, worlds, bounds, cfg,
                         bounds_at=lambda _h: per_sleeve_bounds(dd, _h)) if heavy else {}
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

    # ---------------------------------------------- WHAT THE CANDIDATE BOOK IS REALLY MADE OF
    # MEASURED BEFORE THE SOLVE, because the ceiling is derived from it. Until 2026-09-05 the four
    # heats were computed AFTER the book was published and only reported, so H_eff = max(cov,
    # factor, tail) bound nothing and a book of four sleeves that was one hidden USD factor bought
    # the room four independent bets would have. The candidate is the FREE solve's composition --
    # the shape the mandated book will hold -- and its concentration sets the ceiling
    # (`heat_policy.effective_ceiling`); the floor stays nominal, deployed, 24/7.
    eff_pre = effective_heat_of(ev, free.heat)
    _log(f"candidate effective heat: nominal={eff_pre.get('nominal')} "
         f"cov={eff_pre.get('covariance')} factor={eff_pre.get('factor')} "
         f"tail={eff_pre.get('tail')} n_eff={eff_pre.get('n_eff')} "
         f"{eff_pre.get('error') or ''}")

    # ------------------------------------------------------- THE STATE THE TARGET IS SOLVED FOR
    # H*_t = argmax_{H in [floor, ceiling]} E[log W | X_t] on the CURRENT state's own worlds. The
    # state id joins the admitted state dimensions' present buckets (STATE_ADMISSION.json decides
    # which may condition at all) to the regime the worlds were drawn from.
    now_buckets = {**dict(_admitted_extra_dims()), **({"session": phase} if phase else {})}
    top_regime = probs[0][0] if probs else ""
    try:
        from libs.portfolio.allocator_proof import admitted_now, state_id
        kept_dims, adm_why = admitted_now(ROOT, now_buckets)
        current_state = state_id(kept_dims, top_regime)
    except Exception as exc:
        kept_dims, adm_why, current_state = {}, f"{type(exc).__name__}: {exc}", ""
    curves, curves_why = ((state_growth_curves(ev, worlds, free.heat, cfg, kept_dims))
                          if heavy else ({}, f"{mode} clock: the global curve stands"))
    _log(f"state: id={current_state or '(none)'} ({adm_why}); {curves_why}")

    # THE CEILING IS MEASURED, NOT DECREED (principal, 2026-09-05: the fixed 30% cap is removed;
    # "if growth optimum permits 32 35 40 45 wtv in future w new edges etc it can use those w 20
    # as minimum floor"). `measured_ceiling` reads the highest heat THIS opportunity set still
    # buys growth at, never past the last heat actually sampled, and falls back to the recorded
    # constant when the curve cannot be read -- absence is never permission. So a richer book
    # earns more than 30% and a thin one is held tighter than 30% ever held it.
    ceiling_now, ceiling_why = measured_ceiling(curve, floor=HEAT_TARGET)
    _log(f"heat growth ceiling: {ceiling_why}")

    # THE SURVIVAL CEILING, MEASURED BEFORE THE RESOLVE AND NOT AFTER IT (principal, 2026-09-07:
    # "remove 30 heat cap fully"). The Kelly surface has computed `f_tail` -- the largest scale of
    # the book at which P(ruin) is zero and P(drawdown > tolerance) stays inside the CVaR
    # fraction -- on every pass since it was written, and it bound NOTHING: it was computed after
    # publication and handed to `aggression.explain` as an audit input while the operative bar
    # stayed the 0.30 constant. Computing it here, on the FREE candidate book, makes it the bar.
    #
    # THE FRACTION GRID IS CHOSEN SO THE SURFACE SPANS THE SIMULATION BOUND. The default 0..2x
    # grid spans 0..2x the candidate's own heat, so a thin book would bound itself at twice its
    # own size for no reason but the grid. Sampling to CURVE_SAMPLE_MAX makes the measurement
    # bound explicit and identical to the growth curve's.
    survival: dict[str, Any] = {}
    surv_ceiling: float | None = None
    surv_why = ""
    try:
        from mt5desk.gateway_config_fallback import MAX_DRAWDOWN_TOLERANCE as _DD_TOL

        from libs.portfolio.kelly_surface import MAX_MARGIN_USE as _MAX_MARGIN_USE
        from libs.portfolio.kelly_surface import envelope as _envelope
        from libs.portfolio.kelly_surface import surface as _surface
        _free_total = float(free.total_heat)
        if _free_total > 1e-9:
            _top = max(2.0, CURVE_SAMPLE_MAX / _free_total)
            _fr = tuple(round(x, 4) for x in np.linspace(0.0, _top, 21))
            _pre_surface = _surface(worlds, free.heat, tolerance=_DD_TOL, alpha=cfg.cvar_alpha,
                                    fractions=_fr)
            # THE MARGIN CLAUSE, FED FROM THE BROKER (2026-09-09). `envelope` has carried a
            # `margin_use` clause and a MAX_MARGIN_USE since it was written and NOTHING had ever
            # passed the argument -- the one clause that is a fact about the venue rather than
            # about the desk's own worlds was inert. It is measured from `mt5.account_info()`
            # (margin over equity at the heat currently deployed, extrapolated linearly across
            # the sampled heats) and OMITTED whenever the terminal, the account or an open
            # position is missing, in which case the envelope binds exactly as it does today.
            #
            # THIS IS THE INTEGRITY CLAUSE, NOT A PREFERENCE. Past the broker's own feasibility
            # a margin call liquidates positions the desk chose to hold, which no growth
            # argument survives; it is the same class as `margin_guard` and it is why
            # `survival_ceiling` is registered integrity rather than tunable.
            _mu, _mu_why = (None, "not measured")
            _mu_heats = [r.get("heat") for r in (_pre_surface.get("rows") or [])]
            _acc_margin, _acc_equity, _acc_why = account_margin()
            if _acc_margin is not None and _acc_equity is not None:
                _mu, _mu_why = margin_use_from(_acc_margin, _acc_equity, _free_total, _mu_heats)
            else:
                _mu_why = f"margin unmeasured: {_acc_why}"
            _log(f"margin use: {_mu_why}")
            # MEASURED AND PUBLISHED, NOT FED (principal's standing order, 2026-09-08, stated
            # three times: never reduce the aggressiveness, only the dynamicness). The margin
            # clause is the one term in this wave that can bind the envelope BELOW today's
            # ceiling: on a margin-starved account `margin_use` shortens the feasible run and
            # the book gets smaller than it is now. That is a risk reduction by fiat, so the
            # measurement rides in `survival["margin_use"]` where the principal can read it and
            # decide, and the envelope is computed exactly as it was before this wave.
            # Flip `margin_use=_mu` back on only on the principal's explicit yes.
            survival = _envelope(_pre_surface.get("rows") or [], alpha=cfg.cvar_alpha,
                                 fallback=HEAT_HARD_CEILING,
                                 margin_use=None,
                                 capacity_max=_capacity_ceiling())
            survival["margin_use"] = {
                "status": "MEASURED" if _mu else "UNMEASURED", "why": _mu_why,
                "account_margin": _acc_margin, "account_equity": _acc_equity,
                "deployed_heat": round(_free_total, 6),
                "max_margin_use": _MAX_MARGIN_USE,
                "by_heat": ({round(k, 6): round(v, 6) for k, v in sorted(_mu.items())}
                            if _mu else {}),
                "rule": ("margin use is linear in heat through the origin (lots scale with "
                         "heat); an unmeasured margin carries NO clause, so the envelope binds "
                         "exactly as it did before this was fed"),
            }
            if survival.get("status") == "MEASURED":
                surv_ceiling = float(survival["ceiling"])
            surv_why = str(survival.get("why") or "")
            survival["surface_max_fraction"] = _top
    except Exception as exc:
        survival = {"error": f"{type(exc).__name__}: {exc}", "status": "UNMEASURED",
                    "why": "survival surface unavailable this pass; the recorded constant stands"}
    _log(f"heat survival ceiling: {survival.get('why') or survival.get('error')}")

    verdict = resolve(free.total_heat, curve=curve, target=HEAT_TARGET,
                      hard_ceiling=ceiling_now,
                      survival_ceiling=surv_ceiling, survival_why=surv_why, mandate=True,
                      readiness=ready, readiness_why=ready_why,
                      effective_heat=eff_pre, state=current_state, curves=curves,
                      allocator_ok=(bool(free.heat) and math.isfinite(free.mean_log_growth)
                                    and not implausible))
    for why in verdict.reasons:
        _log(why)

    # 3. THE BOOK, at the heat the law resolved.
    fam_share: dict[str, float] = {}
    fill_note: dict[str, Any] = {"needed": False}
    ub: dict[str, float] = {}
    family_of = {e.name: e.family for e in ev}
    if verdict.total_heat <= 0:
        book = AllocationResult(heat={}, total_heat=0.0, robust_score=0.0, mean_log_growth=0.0,
                                cvar_log_growth=0.0, annual_growth_pct=0.0, prob_annual_loss=0.0,
                                note="catastrophe guard: no heat")
    else:
        ub = {k: min(v, verdict.total_heat) for k, v in
              per_sleeve_bounds(dd, verdict.total_heat).items()}
        try:
            book = optimise(ev, hard_cap=max(CURVE_SAMPLE_MAX, verdict.total_heat),
                            target=verdict.total_heat, cfg=cfg,
                            worlds=worlds, max_per_sleeve=ub,
                            warm_start=current_book() or None)
        except ValueError as exc:
            # The bounds cannot fund the mandate at all. Not a failed pass: the floor fill below
            # starts from the free solve and yields the bounds until the resolved heat is held.
            _log(f"bounded solve refused ({exc}); the floor fill starts from the free optimum")
            book = free

        # MECHANISM CONCENTRATION, enforced by re-solving under tightened bounds rather than
        # priced. Measured 2026-09-02 the first solved book held 97% of its heat in one family;
        # the redundancy term could not see it, because those sleeves are weakly correlated day
        # to day while sharing a mechanism and a 01:00 fill hour. Two passes converge: the cap
        # scales the offending family's members proportionally, the optimiser re-spends what it
        # frees on everything else, and a family already inside the cap is never touched.
        for _pass in range(2):
            capped = enforce_family_cap(book.heat, family_of, book.total_heat)
            if all(math.isinf(v) for v in capped.values()):
                break                                   # every mechanism already inside the cap
            tight = {k: min(ub.get(k, math.inf), capped.get(k, math.inf)) for k in ub}
            try:
                book = optimise(ev, hard_cap=max(CURVE_SAMPLE_MAX, verdict.total_heat),
                                target=verdict.total_heat,
                                cfg=cfg, worlds=worlds, max_per_sleeve=tight,
                                warm_start=book.heat or None)
            except ValueError as exc:
                _log(f"family-capped solve refused ({exc}); the floor fill decides the cap")
                break
        # FLOOR FILL (principal, 2026-09-04): the resolved heat -- 20% floor, growth above it to
        # the ceiling -- is what the book HOLDS, not what it reports as a shortfall. When the
        # per-sleeve bounds cannot fund it, the bounds yield, in the order of how little each
        # was ever proven to earn: the drawdown-derived leg first, then the mechanism cap, then
        # the single-sleeve share cap, and last a proportional scale of the solved book. Every
        # relaxation is written to the artifact and billed by `missed_growth` as that rail's
        # opportunity cost. The one thing the fill never overrides is the ruin guard below: a
        # filled book that is wiped out in a sampled world is still not a book.
        held_before = book.total_heat
        book, fill_note = fill_floor(book, ev, verdict.total_heat, ub, family_of,
                                     cfg=cfg, worlds=worlds)
        if fill_note.get("needed"):
            _log(f"FLOOR FILL: bounded solve held {held_before:.2%} of the "
                 f"{verdict.total_heat:.2%} resolved; {fill_note}")
        for name, h in book.heat.items():
            if h > 1e-6:
                fam = family_of.get(name, "?")
                fam_share[fam] = fam_share.get(fam, 0.0) + h
        if fam_share:
            top = max(fam_share.items(), key=lambda kv: kv[1])
            _log(f"mechanism mix: {len(fam_share)} family(ies), largest {top[0]} at "
                 f"{top[1] / max(book.total_heat, 1e-9):.0%} of the book")
    funded = {k: round(v, 6) for k, v in book.heat.items() if v > 1e-5}

    # ---------------------------------------- THE BOOK SOLVED FOR THE STATE THE DESK IS IN
    # One extra solve on the current state bucket's worlds alone, at the resolved heat, under
    # the same bounds and family cap -- the composition the state itself would choose, beside
    # what the global composition earns in it. Published as `state_book`; consumed by nothing.
    if heavy:
        sbook = state_book(ev, worlds, cfg, state=current_state, now_buckets=kept_dims,
                           total_heat=float(verdict.total_heat), bounds=ub, family_of=family_of,
                           warm_start=funded or None, global_book=funded or None)
        _log(f"state book: {sbook.get('status')} -- {sbook.get('why')}"
             + (f"; {sbook.get('reading')}" if sbook.get("reading") else ""))
    else:
        sbook = {"status": "not measured on this clock", "consumed": False,
                 "state": current_state or ""}

    # ---------------------------------------------------- THE POSTERIOR MULTI-PERIOD BOOK
    # `libs/portfolio/posterior_growth` solves the same objective over a POSTERIOR on worlds --
    # mean and covariance uncertainty, the winner's-curse shrinkage the evidence carries -- across
    # T periods with turnover priced and ruin/stop-out bounded on the same sampled paths. It is a
    # CHALLENGER, not a second authority: it takes the funded book's place only when `compare`
    # says it beats that book on identical paths with the bootstrap CI excluding zero -- rule 1
    # ("every risk reduction mechanism must prove that it increases robust forward E[log W]")
    # applied to the swap itself. Its certificate is written to the artifact either way, so a
    # posterior that keeps losing the contest is a measured fact and not a silent organ.
    posterior: dict[str, Any] = {}
    if funded and worlds is not None:
        try:
            from libs.portfolio.posterior_growth import compare as _pg_compare
            from libs.portfolio.posterior_growth import sample_paths as _pg_paths
            from libs.portfolio.posterior_growth import solve as _pg_solve
            _pg_prev = current_book()
            _pg_paths_ = _pg_paths(ev, n_paths=400, horizon=max(1, int(NO_TRADE_HORIZON_DAYS)),
                                   worlds=worlds, seed=seed)
            _pbook = _pg_solve(ev, h_prev=_pg_prev, paths=_pg_paths_,
                               floor=float(verdict.total_heat),
                               ceiling=max(CURVE_SAMPLE_MAX, verdict.total_heat),
                               caps=per_sleeve_bounds(dd, max(CURVE_SAMPLE_MAX,
                                                              verdict.total_heat)),
                               turnover_cost=TURNOVER_COST_R)
            _cmp = _pg_compare(_pbook, funded, _pg_paths_, h_prev=_pg_prev,
                               turnover_cost=TURNOVER_COST_R, seed=seed)
            posterior = {"certificate": _pbook.certificate(), "vs_funded": _cmp,
                         "adopted": False}
            _log(f"posterior book: {_pbook.total_heat:.2%} heat, binding={_pbook.binding}, "
                 f"E[logW]/day={_pbook.elogw_per_day:+.5f} (p10 {_pbook.elogw_p10:+.5f}); "
                 f"dE vs funded {_cmp['delta_elogw_per_day']:+.5f} "
                 f"CI [{_cmp['ci_lo']:+.5f}, {_cmp['ci_hi']:+.5f}] -> "
                 f"{'ADOPT' if _cmp.get('beats') else 'funded book stands'}")
            if _cmp.get("beats") and _pbook.h:
                sc = score_book(ev, _pbook.h, cfg=cfg, worlds=worlds)
                book = AllocationResult(
                    heat=dict(_pbook.h), total_heat=float(_pbook.total_heat),
                    robust_score=float(sc["robust_score"]),
                    mean_log_growth=float(sc["mean_log_growth"]),
                    cvar_log_growth=float(sc["cvar_log_growth"]),
                    annual_growth_pct=float(sc["annual_growth_pct"]),
                    prob_annual_loss=float(sc["prob_annual_loss"]),
                    note=(f"posterior multi-period book adopted: dE[log W] "
                          f"{_cmp['delta_elogw_per_day']:+.5f}/day with the CI excluding 0; "
                          f"binding={_pbook.binding}"))
                funded = {k: round(v, 6) for k, v in book.heat.items() if v > 1e-5}
                posterior["adopted"] = True
                if _pbook.binding == "ruin_guard":
                    # The one mechanism licensed below the resolved floor, and it has just
                    # proved its dE[log W] on the same paths -- said out loud, never quietly.
                    _log(f"POSTERIOR RUIN GUARD: the adopted book holds {_pbook.total_heat:.2%},"
                         f" below the resolved {verdict.total_heat:.2%}; p_ruin at the floor "
                         f"breached eps and the reduction raised robust E[log W]")
        except Exception as exc:
            posterior = {"status": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}"}
            _log(f"posterior book unmeasured: {posterior['why']}")

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
    # PUBLISHED, BECAUSE ANOTHER LAYER HAS TO PRICE THE SAME MOVE. `macro.interrupt.should_fire`
    # asks "is acting NOW worth more than waiting for the fast clock", and its economic gate needs
    # log-wealth per day at risk -- which is this number, the gap between what the new solve is
    # worth and what the desk is actually holding. It was reachable only as
    # `benefit_over_horizon / horizon_days`, so the macro layer passed None and every interrupt
    # decision died at "expected gain not priced by the allocator". A derived field would also
    # break silently the day NO_TRADE_HORIZON_DAYS changes.
    #
    # NON-FINITE IS PUBLISHED AS None, not as a large number. `gain` is +inf when the held book is
    # currently ruinous and has no growth rate to improve on; that is the right answer for the
    # no-trade filter (move off it) and an unusable one for an economic gate that compares a gain
    # to a cost. None means "cannot price", which the interrupt reads as HOLD and the fast clock
    # handles on its own schedule.
    nt["gain_per_day"] = round(gain, 10) if math.isfinite(gain) else None
    proposed_book = dict(funded)
    book, funded = bind_verdict(nt, prev_book, held, book, funded)
    opp = opportunity(free, funded, HEAT_TARGET)

    # ------------------------------------------------- ADMISSION BY dE[log W], NOT BY SHARPE
    # THE CRITERION, NOT A REPORT (principal, 2026-09-05). Every priced sleeve the published book
    # does NOT hold is re-solved INTO that book at the same total heat on these same worlds, and
    # what it is worth is the growth it adds. `promoter.py` reads this block and gives capital to
    # nothing that fails it, however good its standalone Sharpe -- which is on every row, beside
    # the correlation to the held book, so the disagreement between the two orderings is legible
    # rather than asserted.
    #
    # HEAVY CLOCK ONLY, AND CARRIED WITH ITS AGE. A candidate re-solve is a full optimisation; a
    # hundred of them do not fit in a five-minute clock. The heavy pass runs hourly, and the
    # short clocks carry its answer forward stamped with when it was taken, so a reader (and the
    # promoter's freshness check) can tell a measurement from an inheritance.
    #
    # MOVED AHEAD OF THE PROOF (2026-09-09), because the scan's `explore` block may now lend a
    # slice of the book to ambiguous candidates, and the book the contest certifies must be the
    # book that is published.
    admission: dict[str, Any]
    adm_bounds = per_sleeve_bounds(dd, max(book.total_heat, HEAT_TARGET))
    prev_admission: dict[str, Any] = {}
    try:
        _prev_art = json.loads(OUT.read_text("utf-8")).get("admission")
        prev_admission = _prev_art if isinstance(_prev_art, dict) else {}
    except (OSError, ValueError, AttributeError):
        prev_admission = {}
    if heavy and funded:
        admission = marginal_admission(ev, worlds, cfg, incumbent=funded, bounds=adm_bounds,
                                       total_heat=book.total_heat, order=free.marginal,
                                       # Whatever the last scan could not finish goes first, and
                                       # continues from the book its solve had reached.
                                       prefer=set(prev_admission.get("unscored") or {}),
                                       warm=prev_admission.get("warm") or {},
                                       # One draw per UTC day: the explored set is stable across
                                       # the hourly passes of a day instead of re-drawn hourly.
                                       explore_seed=int(seed) + int(datetime.now(UTC)
                                                                    .strftime("%Y%m%d")))
        _log(f"admission: {admission.get('status')} -- {admission.get('n_admitted', 0)}/"
             f"{admission.get('priced', 0)} priced candidate(s) raise robust growth "
             f"(basis={admission.get('basis')}, {admission.get('elapsed_s', 0)}s, "
             f"{admission.get('per_candidate_s')}s/candidate, "
             f"{admission.get('n_unscored', 0)} unscored of which "
             f"{admission.get('n_partial', 0)} partial and carried, "
             f"{admission.get('n_carried_from_last_unreached', 0)} continued from last pass)")
    else:
        admission = {"status": "not measured on this clock", "candidates": {},
                     "admitted": [], "refused": [], "unscored": {}, "warm": {}, "partial": {}}
        if prev_admission.get("status") == "MEASURED":
            admission = {**prev_admission,
                         "carried_from": prev_admission.get("measured_utc"),
                         "carried_by": mode}

    # EXPLORATION APPLIED TO THE PUBLISHED BOOK. On a heavy pass the draw was just made; on a
    # short clock the carried draw is re-applied to THIS pass's book so the explored set keeps
    # its heat for the day. Candidates the main solve has since funded on its own are dropped
    # from the lent set (they are no longer ambiguous). The total never moves; the explored book
    # and the un-explored one are both scored on these worlds so the rail can be billed.
    explore = admission.get("explore") if isinstance(admission.get("explore"), dict) else None
    if explore is not None:
        explore = dict(explore)
        explore["applied"] = False
        lend = {k: float(v) for k, v in (explore.get("explore_heat") or {}).items()
                if float(v) > 1e-9}
        # A drawn candidate the main solve now funds ABOVE its lent heat is no longer ambiguous
        # and is dropped from the lent set; one held AT its lent heat is the held book carrying
        # last pass's draw, and stays.
        lend = {k: v for k, v in lend.items() if float(funded.get(k, 0.0)) <= v + 1e-6}
        if explore.get("status") == "FUNDED" and lend and funded:
            base_now = {k: float(v) for k, v in funded.items() if float(v) > 0.0}
            explored, e_why = apply_explore(base_now, lend, adm_bounds)
            changed = any(abs(explored.get(k, 0.0) - base_now.get(k, 0.0)) > 1e-9
                          for k in set(explored) | set(base_now))
            held_already = all(abs(base_now.get(k, 0.0) - v) <= 1e-6 for k, v in lend.items())
            if changed or held_already:
                without = without_explore(explored, lend)
                sc_with = score_book(ev, explored, cfg=cfg, worlds=worlds)
                sc_without = (score_book(ev, without, cfg=cfg, worlds=worlds) if without
                              else {"mean_log_growth": float("nan")})
                if math.isfinite(sc_with["mean_log_growth"]):
                    explore.update({
                        "applied": True,
                        "applied_via": ("heavy" if heavy else ("carried" if changed else "held")),
                        "applied_why": (e_why if changed else
                                        "the held book already carries this draw's heat"),
                        "growth_with": round(float(sc_with["mean_log_growth"]), 10),
                        "growth_without": (round(float(sc_without["mean_log_growth"]), 10)
                                           if math.isfinite(sc_without["mean_log_growth"])
                                           else None),
                        "book": {k: round(v, 6) for k, v in explored.items() if v > 1e-6},
                        "paid_by": {k: round(explored.get(k, 0.0) - v, 6)
                                    for k, v in base_now.items()
                                    if k not in lend and abs(explored.get(k, 0.0) - v) > 1e-6},
                        "without_basis": ("the same book with the lent heat removed and the "
                                          "incumbents scaled back to the total; scored, not "
                                          "published"),
                    })
                    if changed:
                        book = AllocationResult(
                            heat={k: v for k, v in explored.items() if v > 1e-6},
                            total_heat=float(sum(explored.values())),
                            robust_score=float(sc_with["robust_score"]),
                            mean_log_growth=float(sc_with["mean_log_growth"]),
                            cvar_log_growth=float(sc_with["cvar_log_growth"]),
                            annual_growth_pct=float(sc_with["annual_growth_pct"]),
                            prob_annual_loss=float(sc_with["prob_annual_loss"]),
                            marginal=dict(book.marginal), iterations=book.iterations,
                            converged=book.converged,
                            note=(f"{book.note}; explore: {e_why}").strip("; "))
                        funded = {k: round(v, 6) for k, v in book.heat.items() if v > 1e-5}
                    _log(f"explore ({explore['applied_via']}): {explore['applied_why']} -> "
                         f"growth {explore['growth_with']:+.6f} vs "
                         f"{explore['growth_without']} log/day un-explored")
                else:
                    explore["applied_why"] = ("explored book is wiped out in a sampled world; "
                                              "nothing lent")
            else:
                explore["applied_why"] = e_why
        elif explore.get("status") == "FUNDED":
            explore["applied_why"] = ("nothing left to lend: every drawn candidate is funded by "
                                      "the main solve on its own, or no book is held")
        admission["explore"] = explore
    # SLEEVES THIS SOLVE ZEROED, NAMED so the answer can actually BE zero. Without this list the
    # gateway cannot see a zeroed sleeve at all and falls back to the 3% base fraction: see
    # `zeroed_live` for the trace. Not a retirement -- the row and the clock stand.
    zeroed = zeroed_live(ev, funded, extra=prev_book)
    if zeroed:
        _log(f"zeroed but NOT retired: {len(zeroed)} rostered sleeve(s) earn 0% this pass "
             f"({', '.join(sorted(zeroed)[:6])})")

    # ------------------------------------------------------ THE BASELINE CONTEST, EVERY PASS
    # A dynamic allocator sits above every edge and reallocates, so it can destroy compounding
    # faster than any single sleeve can. It therefore has to beat the answers anyone could have
    # written in an afternoon -- equal weight, inverse vol, risk parity, and doing nothing --
    # on THESE worlds, at EQUAL total heat, before it is allowed to size a position.
    # The gateway reads the certificate this writes; without a fresh passing one it keeps
    # ranking with the optimiser and sizing with Q_OPT exactly as it does today.
    fallback: dict[str, Any] = {}
    try:
        from libs.portfolio.allocator_proof import certify, contest
        # A*_t NEEDS THE STATE IT WAS SOLVED IN. Without `now_buckets` the certificate's
        # `by_state` keys carry the regime alone, so `select` can only match by regime suffix and
        # a session- or event-conditioned bucket that the admission gauntlet HAS judged is thrown
        # away at exactly the moment it would decide which allocator to trust.
        proof = contest(ev, funded, current_book(), cfg=cfg, worlds=worlds,
                        now_buckets=kept_dims, root=ROOT)
        certify(proof, root=ROOT, book=funded)
        # THE FLOOR'S FALLBACK: the best baseline at the same total heat, carried on the
        # artifact so a failed or stale proof changes who allocates the floor, never whether.
        best = str(proof.get("best_baseline") or "")
        fb_book = (proof.get("books") or {}).get(best) or {}
        if best and fb_book:
            fallback = {"name": best, "book": {k: round(float(v), 6) for k, v in fb_book.items()
                                               if float(v) > 1e-6}}
        _log(f"proof: {'PASS' if proof['passed'] else 'FAIL'} -- {proof['why']}")
    except Exception as exc:
        # A failed contest must never take the allocation pass with it: the book is still worth
        # publishing for ranking and total heat. What it loses is the right to SIZE, which is
        # exactly the fail-closed direction.
        proof = {"passed": False, "why": f"{type(exc).__name__}: {exc}"}
        _log(f"proof: FAILED TO RUN -- {proof['why']}")

    # THE AGGRESSION GOVERNOR'S AUDIT AND THE KELLY SURFACE: why the deployed heat is what it
    # is, and how much more the worlds would bear. Report-only -- `heat_policy.resolve` is the
    # lever -- but UNUSED_UPSIDE is a verdict `missed_growth` will not let stand.
    ks_doc: dict[str, Any] = {}
    ks_crisis: dict[str, Any] = {"status": "UNMEASURED", "binds": False,
                                 "why": "no funded book to condition on the crisis worlds"}
    aggression: dict[str, Any] = {}
    try:
        from mt5desk.gateway_config_fallback import MAX_DRAWDOWN_TOLERANCE as _DD_TOL

        from libs.portfolio.aggression import explain as _explain
        from libs.portfolio.kelly_surface import crisis_block as _crisis_block
        from libs.portfolio.kelly_surface import surface as _surface
        if funded:
            ks_doc = _surface(worlds, funded, tolerance=_DD_TOL, alpha=cfg.cvar_alpha)
            ks_doc["rows"] = ks_doc.get("rows", [])[::2]          # every second grid point
            # THE CRISIS KELLY, BESIDE THE BLENDED ONE, FOR COMPARISON (2026-09-09). The same
            # surface on `worlds.crisis` alone -- "what would Kelly be if the crisis world is
            # the one we are in" -- with the sign of the difference named. It binds nothing:
            # computed after the heat is resolved and the book solved, read by no sizing path.
            ks_crisis = _crisis_block(worlds, funded, ks_doc, tolerance=_DD_TOL,
                                      alpha=cfg.cvar_alpha)
            _log(f"crisis kelly: {ks_crisis.get('status')} on {ks_crisis.get('n_worlds')} "
                 f"crisis world(s): f_opt={ks_crisis.get('f_opt')} vs blended "
                 f"{ks_doc.get('f_opt')} -- {ks_crisis.get('why') or 'comparison only'}")
        # THE OPERATIVE CEILING, NOT THE FALLBACK CONSTANT. `aggression` decides between
        # CEILING_BOUND and UNUSED_UPSIDE by comparing the book against the bar it was
        # actually held by; handing it 0.30 while the law ran a measured 22% would report
        # UNUSED_UPSIDE every pass and send `missed_growth` hunting a rail that did not bind.
        _op_ceiling = min(float(ceiling_now),
                          float(surv_ceiling) if surv_ceiling is not None else float("inf"))
        # MARGIN HEADROOM, from the same broker reading the survival envelope's clause used.
        # `aggression.explain` has carried a `margin_headroom` component since it was written
        # and every pass reported it as a GAP ("no account margin reading on this host"); it is
        # an audit input and moves nothing.
        _headroom = None
        _srv_mu = (survival.get("margin_use") or {}) if isinstance(survival, dict) else {}
        if _srv_mu.get("status") == "MEASURED" and _srv_mu.get("account_equity"):
            _headroom = 1.0 - (float(_srv_mu["account_margin"])
                               / float(_srv_mu["account_equity"]))
        aggression = _explain(floor=HEAT_TARGET, ceiling=_op_ceiling,
                              total_heat=book.total_heat, free_optimum=free.total_heat,
                              readiness=ready, proof_passed=bool(proof.get("passed")),
                              surface=ks_doc, book=funded, ev=ev,
                              margin_headroom=_headroom)
        _log(f"aggression: A={aggression['A']:.2f} {aggression['verdict']} "
             f"tail_max={ (aggression['components']['tail_safety'] or {}).get('heat_tail_max')}")
    except Exception as exc:
        aggression = {"error": f"{type(exc).__name__}: {exc}"}
        _log(f"aggression audit unavailable: {aggression['error']}")
    # WHERE THE NEXT BASIS POINT GOES (principal, 2026-09-07: "the allocator can literally answer:
    # where does the next 10 basis points of risk create the most wealth?"). Exact closed-form
    # dG/dh_i and d2G/dh_i dh_j on the SAME world array the solve used -- no re-optimisation, no
    # finite differences -- plus the second-order gain from a 10bp step, which is the question as
    # actually asked: a gradient ranking is only exact in the limit, and a sleeve with a big
    # gradient and violent curvature ranks first on the gradient and second on the real step.
    growth_derivs: dict[str, Any] = {}
    try:
        from libs.portfolio.growth_derivatives import best_next as _best_next
        from libs.portfolio.growth_derivatives import derivatives as _derivs
        if funded and worlds is not None and getattr(worlds, "r", None) is not None:
            _names = list(worlds.names)
            _h = np.array([float(funded.get(n, 0.0)) for n in _names], dtype="float64")
            _d = _derivs(worlds.r, _h, names=_names)
            _step = _best_next(_d, delta=0.001,
                               cap=per_sleeve_bounds(dd, max(book.total_heat, HEAT_TARGET)),
                               held=funded)
            growth_derivs = {
                "status": _d.get("status"), "why": _d.get("why"),
                "curvature_ok": _d.get("curvature_ok"),
                "n_usable_rows": _d.get("n_usable"), "n_ruined_rows": _d.get("n_ruined"),
                "gradient": {k: round(v, 8) for k, v in (_d.get("gradient") or {}).items()},
                "curvature": {k: round(v, 8) for k, v in (_d.get("hessian_diag") or {}).items()},
                # The full Hessian is n^2 and the artifact is read by humans; the DIAGONAL and the
                # ranked step are what a reader acts on, and the strongest competing PAIRS are
                # what the breadth work needs -- so the matrix is summarised, not dumped.
                "next_10bp": {k: _step.get(k) for k in
                              ("status", "best", "best_gain_per_day", "linear_best",
                               "second_order_changes_the_answer", "why")},
                "next_10bp_ranked": (_step.get("ranked") or [])[:12],
                "competing_pairs": _competing_pairs(_d),
            }
            _log(f"next 10bp -> {_step.get('best')} "
                 f"({_step.get('best_gain_per_day')}/day); {_step.get('why')}")
    except Exception as exc:
        growth_derivs = {"status": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}"}

    # THE FOUR HEATS AND THE WORLDS-BASED TRADE VALUE: what the nominal heat is really made of
    # (covariance / latent-factor / tail), and what moving from the held book buys on these
    # worlds net of turnover -- the inertia rail's own measurement.
    effective_heat: dict[str, Any] = {}
    trade_value: dict[str, Any] = {}
    try:
        from libs.portfolio.multiperiod_worlds import trade_value as _trade_value
        if funded:
            effective_heat = effective_heat_of(ev, funded)
            trade_value = _trade_value(worlds, prev_book, funded)
            _log(f"effective heat: nominal={effective_heat.get('nominal')} "
                 f"eff={effective_heat.get('effective')} n_eff={effective_heat.get('n_eff')}; "
                 f"trade value {trade_value.get('verdict')} ({trade_value.get('trade_value')})")
    except Exception as exc:
        effective_heat = {"error": f"{type(exc).__name__}: {exc}"}
    # NOMINAL VS EFFECTIVE, AND WHICH BOUND BOUND -- on the published book beside the candidate
    # the ceiling was actually derived from, so the artifact can be read as an argument rather
    # than as an assertion: what was measured before the solve, what the cap came out at, what
    # the book ended up carrying, and which of the two bars decided.
    # THE STRUCTURAL INDEPENDENCE NUMBER, BESIDE THE STATISTICAL ONE. `alpha_genome` clusters
    # every certified edge by what it IS (mechanism, direction, clock, shared leg) and its own
    # docstring has claimed since it was written that `n_clusters` is reported here beside
    # k_eff -- a claim no reader existed for. Reporting only: nothing sizes on a cluster id.
    effective_heat["alpha_genome"] = alpha_genome_view(ev, funded)
    _log(f"alpha genome: {effective_heat['alpha_genome'].get('status')} -- "
         f"{effective_heat['alpha_genome'].get('why')}")
    effective_heat["candidate_pre_solve"] = eff_pre
    effective_heat["ceiling"] = {
        "growth_bar": round(float(ceiling_now), 6),
        "survival_bar": (None if surv_ceiling is None else round(float(surv_ceiling), 6)),
        "unmeasured_fallback": HEAT_HARD_CEILING,
        "effective_bar": round(verdict.effective_ceiling, 6),
        "derived_from": verdict.effective,
        "bound_by": verdict.binding,
        "rule": ("the FLOOR counts nominal heat (20% deployed is a standing instruction about "
                 "capital at work); the CEILING counts max(covariance, factor, tail), because "
                 "hidden concentration bites at the top of the band and nowhere else"),
    }
    # WHAT THE PER-SLEEVE DECAY POSTERIOR IS WORTH, billed on the PUBLISHED book. The same book
    # scored on its own worlds and on a population drawn identically except that every sleeve
    # carries the blanket -- the random stream is shared, so the two differ only in which
    # sleeves decay in which worlds. `missed_growth.measure_decay_posterior` reads the pair. A
    # cached world population (fast clock) was not drawn under this pass's decay and is not
    # compared against; it says so rather than billing a number.
    if decay_meta.get("n_from_hazard") and funded:
        if "cached" in str(worlds.note):
            decay_meta["billing"] = {"status": "UNMEASURED",
                                     "why": "world population reused from cache; the with/"
                                            "without pair needs worlds drawn this pass"}
        else:
            try:
                from dataclasses import replace as _replace_ev
                _ev_blanket = [_replace_ev(e, decay_prob_i=None) for e in ev]
                _w_blanket = sample_worlds(_ev_blanket, cfg)
                _g_with = score_book(ev, funded, cfg=cfg, worlds=worlds)["mean_log_growth"]
                _g_without = score_book(_ev_blanket, funded, cfg=cfg,
                                        worlds=_w_blanket)["mean_log_growth"]
                decay_meta["growth_with"] = (round(_g_with, 10) if math.isfinite(_g_with)
                                             else None)
                decay_meta["growth_without"] = (round(_g_without, 10)
                                                if math.isfinite(_g_without) else None)
                decay_meta["billing"] = {
                    "status": "MEASURED", "basis": "same book, same seed, per-sleeve decay vs "
                                                   "the blanket",
                    "delta_logw_per_day": (round(_g_with - _g_without, 10)
                                           if math.isfinite(_g_with) and math.isfinite(_g_without)
                                           else None)}
                _log(f"decay posterior billing: with {_g_with:+.6f} vs blanket "
                     f"{_g_without:+.6f} log/day")
            except (ValueError, MemoryError) as exc:
                decay_meta["billing"] = {"status": "UNMEASURED",
                                         "why": f"{type(exc).__name__}: {exc}"}
    elif decay_meta.get("mode") == "decay_posterior":
        decay_meta["billing"] = {"status": "NOT_BINDING",
                                 "why": "no sleeve carried a measured hazard this pass; every "
                                        "sleeve paid the blanket"}

    # THE FRACTIONAL-KELLY NUMBER, said out loud. Heavy clock: it costs a second world population
    # and a handful of solves, and it is the number the principal asked to be reported rather
    # than left emergent.
    kelly: dict[str, Any]
    if heavy:
        kelly = kelly_fraction(ev, cfg, deployed=book.total_heat, bounds=adm_bounds, seed=seed)
        _log(f"kelly: f_eff={kelly.get('kelly_fraction')} "
             f"(deployed {kelly.get('deployed_heat')} of full-Kelly "
             f"{kelly.get('full_kelly_heat')}) -- {kelly.get('status')}")
    else:
        kelly = {"status": "not measured on this clock"}
        try:
            prev_k = json.loads(OUT.read_text("utf-8")).get("kelly")
            # BOUND carries forward too: an upper bound on the fraction is a real answer, and
            # dropping it on the short clocks would make the number vanish for 59 minutes an hour.
            if isinstance(prev_k, dict) and prev_k.get("status") in ("MEASURED", "BOUND"):
                kelly = {**prev_k, "carried_by": mode}
        except (OSError, ValueError, AttributeError):
            pass

    # THE AI CAPITAL MODIFIER LEDGER: what the state conditioning claimed for each funded
    # sleeve this pass, so each category can later prove its increment.
    try:
        from libs.portfolio.capital_modifiers import record as _record_modifiers
        _mods = _record_modifiers(ev, funded, phase or "")
        if _mods:
            _log("capital modifiers: " + ", ".join(
                f"{c}={sum(1 for m in _mods if m['category'] == c)}"
                for c in ("STRONG_VETO", "REDUCE", "NORMAL", "BOOST", "STRONG_BOOST")))
    except Exception as exc:
        _log(f"capital modifier ledger not written: {type(exc).__name__}: {exc}")

    art: dict[str, Any] = {
        "generated_utc": datetime.now(UTC).isoformat(),
        "mode": mode,
        "elapsed_s": round(time.time() - t0, 1),
        "armed": ARMED.exists(),
        "advisory": not ARMED.exists(),
        "heat": {
            # `total` is the heat of the book PUBLISHED below -- the number the gateway caps at
            # and the fence checks the book sums to. When the no-trade verdict binds, that is
            # the held book; `resolved` keeps the target this pass solved for either way.
            "total": round(book.total_heat if nt.get("binding") else verdict.total_heat, 6),
            "resolved": round(verdict.total_heat, 6),
            "held": bool(nt.get("binding")),
            "free_optimum": round(verdict.free_optimum, 6),
            "target": verdict.target, "hard_ceiling": verdict.hard_ceiling,
            # THE ENVELOPE THE GATEWAY READS. `decision_core.allocator_heat` refuses any total
            # above the recorded constant UNLESS this block says a survival surface measured
            # higher on THIS pass -- which is what makes "remove the 30% cap" real on the money
            # path rather than only in the research artifact. Absent or UNMEASURED, the constant
            # binds exactly as before: a missing measurement is never a licence.
            "envelope": {
                "growth_ceiling": round(float(ceiling_now), 6),
                "growth_why": ceiling_why,
                "survival_ceiling": (None if surv_ceiling is None
                                     else round(float(surv_ceiling), 6)),
                "survival": survival,
                "operative_ceiling": round(
                    min(float(ceiling_now),
                        float(surv_ceiling) if surv_ceiling is not None else float("inf"),
                        float(verdict.effective_ceiling) if verdict.effective_ceiling > 0
                        else float("inf")), 6),
                "sample_max": CURVE_SAMPLE_MAX,
                "unmeasured_fallback": HEAT_HARD_CEILING,
                "rule": ("the operative ceiling is min(growth, survival, effective-independence) "
                         "-- three MEASURED bars, none of them a constant. The recorded 0.30 "
                         "survives only as the fallback when a bar cannot be read, because a "
                         "monitoring failure must never read as permission."),
            },
            "binding": verdict.binding, "certified": verdict.certified,
            "filled": filled, "shortfall": round(shortfall, 6),
            "readiness": round(verdict.readiness, 4), "floor": round(verdict.floor, 6),
            "readiness_why": ready_why,
            # THE MANDATE'S PRICE, MEASURED EVERY PASS. The principal's instruction on removing
            # the fixed cap was explicit that the 20% floor must not hide inside the optimum:
            # "measure the incremental growth/drawdown cost of that policy continuously, rather
            # than hiding it". So the artifact carries the unconstrained answer, the robust one,
            # what was deployed, which bound bit, and what the floor gave up when it was the
            # thing that bit. A floor nobody audits is a belief; a floor whose cost is on the
            # dashboard every pass is a decision, with the evidence to overturn it.
            **heat_accounting(raw=free.total_heat, robust=verdict.total_heat, curve=curve,
                              floor=HEAT_TARGET),
            # THE CEILING THE BOOK'S INDEPENDENCE EARNED, and the four heats behind it. `binding`
            # above reads "effective_ceiling" when this is what bound rather than the nominal bar.
            "effective_ceiling": round(verdict.effective_ceiling, 6),
            "effective": verdict.effective,
            # WHICH STATE THE TARGET WAS CONDITIONED ON, and on how many worlds.
            "state": verdict.state, "state_worlds": verdict.state_worlds,
            "state_optimum": round(verdict.state_optimum, 6),
            "state_curves": {k: {"n_worlds": v.n_worlds,
                                 "curve": [[round(h, 4), round(g, 8)]
                                           for h, g in sorted(v.curve.items())]}
                             for k, v in (curves or {}).items()},
            "state_curves_why": curves_why,
            "state_curves_basis": ("scaled_candidate: the candidate book proportionally scaled to "
                                   "each heat and scored on that state's worlds -- the "
                                   "composition is the global solve's, only the EVALUATION is "
                                   "conditional"),
            "reasons": list(verdict.reasons),
            "curve": [[round(h, 4), round(g, 8)] for h, g in sorted(curve.items())],
        },
        # WHAT THE CRISIS-WORLD SHARE WAS, AND WHY. `drift_monitor`'s verdict is the only thing
        # that moves it, and a stale or absent report says so here rather than silently standing.
        "drift_overlay": {"crisis_prob": round(crisis_share, 6),
                          "standing": WorldConfig().crisis_prob,
                          "why": crisis_why, "source": drift_why},
        "book": funded,
        # ROSTERED SLEEVES THIS SOLVE GAVE ZERO. Read by `decision_core.book_from_allocation`,
        # which carries them into the sizing book AT ZERO so the gateway can size them at zero
        # instead of falling back to the 3% base fraction. Nothing here is retired.
        "book_zeroed": zeroed,
        # THE COMPOSITION SOLVED INSIDE THE CURRENT STATE, beside what the global book earns
        # there. `consumed` is False: the gateway sizes from `book` and reads `heat.state` only
        # to choose whose certificate applies. Published so the delta is a measurement.
        "state_book": sbook,
        # THE ADMISSION CRITERION: dE[log W] per candidate against THIS book, on THESE worlds, at
        # equal total heat. `promoter.py` gives capital to nothing that fails it.
        "admission": admission,
        # WHAT FRACTION OF FULL KELLY THE DEPLOYED BOOK IS, and which shrinkage layer costs what.
        "kelly": kelly,
        # The solve this pass produced, whether or not the verdict let it out. Equal to `book`
        # on a REBALANCE pass; the declined move on a binding NO CHANGE.
        "proposed_book": proposed_book,
        # WHICH ALLOCATOR WON WHERE. The gateway's `select` reads the certificate, not this;
        # the artifact carries the same verdicts so a reader can see the meta-allocator's map
        # without opening a second file.
        "proof_by_state": {k: {"passed": v.get("passed"), "best": v.get("best"),
                               "n_worlds": v.get("n_worlds")}
                           for k, v in (proof.get("by_state") or {}).items()},
        "proof": {"passed": bool(proof.get("passed")), "why": proof.get("why", ""),
                  "best_baseline": proof.get("best_baseline", ""),
                  "scores": {k: (v.get("mean_log_growth") if isinstance(v, dict) else None)
                             for k, v in (proof.get("scores") or {}).items()}},
        # The best baseline at the same heat: `gateway.allocator_book` sizes the floor with it
        # whenever the dynamic weights have no fresh passing proof.
        "book_fallback": fallback,
        "floor_fill": fill_note,
        "aggression": aggression,
        "posterior_growth": posterior,
        "kelly_surface": ks_doc,
        # THE CRISIS-CONDITIONAL KELLY beside the blended one. `binds` is False on every pass:
        # a comparison a reader can make, not a bar anything sizes against.
        "kelly_surface_crisis": ks_crisis,
        "growth_derivatives": growth_derivs,
        "effective_heat": effective_heat,
        "trade_value_worlds": trade_value,
        # WHICH MECHANISMS HOLD THE BOOK. A single-family book is a single bet however many
        # sleeves it is spread across, and that is invisible from the sleeve list alone.
        "mechanism_mix": {k: round(v, 6)
                          for k, v in sorted(fam_share.items(), key=lambda kv: -kv[1])},
        # THE GRADIENT AT THE SOLVED OPTIMUM, and the name is a legacy the readers depend on
        # (`decision_core.allocator_rank`, `hour_surface`, `portfolio_gap`). It is the value of
        # each FUNDED sleeve's LAST unit of heat -- the correct ordering for `cap_by_heat` to trim
        # by -- and it is NOT the marginal value of admitting a sleeve the book does not hold.
        # That measurement is `admission.candidates[*].delta_elogw_per_day`, which re-solves the
        # whole book around the candidate instead of reading a slope at zero. Kept apart on
        # purpose: conflating them is how the desk came to believe it had an admission criterion.
        "marginal_delta_elog": book.marginal,
        "marginal_delta_elog_basis": (
            "gradient of the robust objective at the solved book (per-sleeve value of the last "
            "unit of heat); the ADMISSION marginal is `admission.candidates[*]"
            ".delta_elogw_per_day`, which re-solves the book with the candidate in it"),
        "growth": {
            "annual_growth_pct": book.annual_growth_pct,
            "mean_log_per_day": round(book.mean_log_growth, 8),
            "cvar_log_per_day": round(book.cvar_log_growth, 8),
            "prob_annual_loss": book.prob_annual_loss,
            "robust_score": round(book.robust_score, 8),
            "free_annual_growth_pct": free.annual_growth_pct,
        },
        # WHAT THE HAZARD TILT DID. `missed_growth.measure_hazard_shrink` reads this pair; both
        # scores must come from the SAME sampled worlds at the SAME total heat, which is the only
        # comparison in which the difference is the tilt rather than the sizing.
        "hazard_shrink": hazard_meta,
        # THE PER-SLEEVE DECAY POSTERIOR: which sleeves carry their own decay probability, from
        # which hazard, how far below the blanket, and what that was worth on the published book
        # (`billing`). `missed_growth.measure_decay_posterior` reads growth_with/growth_without.
        "decay_posterior": decay_meta,
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
            # THE SHARE PER FACTOR BLOCK, measured on the stress pool and applied UNDER the
            # scalar. `share_by_sleeve` lists only the sleeves relieved below the scalar; every
            # other sleeve is stressed exactly as the scalar stresses it.
            "by_block": {k: {"status": v.status, "n_sleeves": v.n_sleeves, "n_days": v.n_days,
                             "mean_corr": (None if not math.isfinite(v.mean_corr)
                                           else round(v.mean_corr, 4)),
                             "shrunk_share": round(v.shrunk_share, 4),
                             "applied_share": round(v.applied_share, 4), "why": v.why}
                         for k, v in cov_cal.by_block.items()},
            "share_by_sleeve": dict(sorted(cov_cal.share_by_sleeve.items())),
            "n_sleeves_relieved": len(cov_cal.share_by_sleeve),
            "blocks_by_sleeve": {k: list(v) for k, v in cov_cal.blocks_by_sleeve.items() if v},
            "block_rule": ("crisis share per factor block (USD leg, JPY leg, metals) measured "
                           "on the stress regime's own rows; the ratcheted book-wide scalar is "
                           "the ceiling for every block, so a block can only be LESS fused than "
                           "the book, never more; a sleeve in two blocks takes the higher share; "
                           "a block under 3 live sleeves carries the scalar"),
        } if cov_cal else {"note": "calibration unavailable; standing constants used"}),
        "evidence": {
            "sleeves": len(ev), "rows": int(daily.shape[0]),
            "with_forward": sum(1 for e in ev if e.forward_days > 0),
            "with_live": sum(1 for e in ev if e.live_days > 0),
            "worlds": worlds.r.shape[0], "world_rows": worlds.r.shape[1],
            "note": worlds.note,
            "forward_join": fwd_acct,
            "certified_library": cert_acct,
            # REPORTED BESIDE THE CERTIFIED LIBRARY, not folded into it: a scalp clock's evidence
            # is its own forward record, not a ten-gate certificate, and a reader deciding whether
            # to trust a scalp sleeve's heat needs to know which kind of evidence stands behind it.
            "scalp_library": scalp_acct,
            "search_trials": trials,
            # BOTH DECAY VALUES, ON THE EVIDENCE BLOCK: the blanket every sleeve used to pay and
            # each hazard-carrying sleeve's own probability beside it.
            "decay": {
                "mode": decay_meta.get("mode"),
                "blanket": decay_meta.get("blanket"),
                "n_from_hazard": decay_meta.get("n_from_hazard", 0),
                "n_blanket": decay_meta.get("n_blanket", len(ev)),
                "by_sleeve": {k: {"hazard": v["hazard"], "decay_prob_i": v["decay_prob_i"]}
                              for k, v in (decay_meta.get("by_sleeve") or {}).items()},
                "min_decay_prob_i": (min((v["decay_prob_i"] for v in
                                          (decay_meta.get("by_sleeve") or {}).values()),
                                         default=None)),
            },
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
