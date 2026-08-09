#!/usr/bin/env python3
# INTENDED CADENCE (NOT wired here -- ops/crontab.manifest is owned by another agent this wave, so
# this comment is the REQUEST, not the installation):
#
#     37 10 * * *  cd /opt/quant && python3 scripts/screen_vol_risk_premium.py
#
# Daily at 10:37 UTC: after collect_deribit_vol_markets.py's 09:17 snapshot has landed the day's
# row, and offset off the hour so it never collides with the executor or the recorders. It is
# read-only over data/ and writes exactly one artifact. Running it more often buys nothing -- the
# pre-registered family is fixed and the panel only grows in calendar time. On a box with no panel
# it exits 0 with a NOT-READABLE-HERE artifact, so installing the line early is harmless.
"""STAGE-A SCREEN: VOLATILITY RISK PREMIUM -- pre-registered BEFORE any result was read.

================================================================================================
THIS DOCSTRING IS THE PRE-REGISTRATION. It was written before the screen was run against any
panel, and nothing below it may be edited in response to a result. Every construction tried is
logged, not only the one that printed.
================================================================================================

WHY THIS CLASS, AND WHY IT IS THE CHEAPEST WIN ON THE BOARD
-----------------------------------------------------------
`data/mechanism_census.json` ranks `volatility_risk_premium` #5 of 20 (gap score 0.3264 =
plausibility 0.85 x orthogonality 0.80 x feasibility 0.80 x depth deficit 0.60), coverage
TESTED-SHALLOW with ONE prior kill. That kill is unusual and it is the whole reason this screen
exists: the graveyard's `options_vrp` row carries the campaign's BEST MEASURED IC ANYWHERE (+0.06)
and the census records that it died on BREADTH, not on sign --

    "The graveyard's `options VRP` row is the campaign's BEST measured IC (+0.06) and it died on
     BREADTH (2 markets), not on sign. The missing input is more vol markets, not a better
     estimator."

`scripts/run_options_vrp_backtest.py` says the same in its own honesty string: "2 assets = LOW
breadth ... a vol-timing overlay, not a broad alpha". It ran on the Deribit DVOL index, and DVOL
exists for exactly two currencies -- probed live before this screen was built: BTC and ETH return
data, SOL/XRP/AVAX/PAXG return empty, TRX/HYPE return HTTP 400. That feed is capped at 2 markets
forever. A mechanism that dies for want of breadth is the cheapest possible win: the edge estimate
already exists and the only missing input is more markets.

1. THE ECONOMIC MECHANISM -- WHO PAYS WHOM, AND WHY THE PAYMENT PERSISTS
------------------------------------------------------------------------
THE PAYER IS THE HEDGER BUYING PROTECTION. He buys an option because he cannot carry the tail
himself -- a miner with a fixed fiat cost base, a treasury with a mandate, a levered holder whose
liquidation price is a hard constraint. His demand is not an opinion about fair value; it is a
BALANCE-SHEET CONSTRAINT, and a constraint cannot be argued out of existence by learning that
implied vol is on average rich.

THE RECIPIENT IS THE OPTION SELLER, and what he is paid for is real. Selling an option is selling
short gamma and short jump risk: the loss is unbounded, it arrives fastest exactly when his other
positions are also losing, and his capital is finite. The premium is compensation for bearing a
risk that genuinely exists -- which is why the payment PERSISTS rather than being competed away:

  (a) THE RISK IS REAL. The seller is sometimes destroyed. This is not a mispricing that arbitrage
      removes; it is a price for insurance, and insurance is priced above expected loss in every
      market that has ever had one.
  (b) THE SELLER'S CAPITAL IS FINITE AND PRO-CYCLICAL. Crypto vol sellers are balance-sheet
      constrained and are forced OUT precisely when the premium is richest, so supply contracts
      exactly when demand spikes. Competition cannot flatten a curve whose suppliers keep failing.
  (c) THE BUYER IS PRICE-INSENSITIVE BY CONSTRUCTION. A hedge bought to satisfy a constraint is
      bought at the offered price.

WHAT WOULD KILL THE STORY. If the premium is fully compensation -- i.e. the tail takes back exactly
what the carry pays -- then the mean short-vol carry is positive, its Sharpe is not, and no
CONDITIONING variable improves it. That is the honest null, and this screen is built to report it.
Note carefully that "the average premium is positive" is NOT a finding here: the whole question is
whether the premium is CONDITIONALLY harvestable, which is why every cell asks a signal observed at
t to predict a payoff realised over (t, t+1] rather than asking whether a constant is positive.

2. THE BREADTH FIX -- WHERE THE MARKETS COME FROM, AND WHY THEY ARE REAL
-------------------------------------------------------------------------
DVOL: 2 currencies. THE OPTION CHAIN: 7 underlyings (BTC, ETH, SOL, XRP, AVAX, TRX, HYPE at the
time of writing) over 49 listed expiries. `scripts/collect_deribit_vol_markets.py` reads the chain
-- every underlying discovered from `currency=any` rather than typed, every listed expiry, and the
whole strike ladder -- and reconstructs the implied-vol HISTORY nobody was recording by inverting
Black-76 on each instrument's public mark-price series (verified against Deribit's own `mark_iv` to
within 0.01 vol points on both the coin-settled and USDC-settled families).

A MARKET IS (underlying x tenor bucket). Buckets are pre-registered at t07 / t30 / t90 / t180 by
days-to-expiry ON THE OBSERVATION DATE, so a contract migrates down the buckets as it ages and each
bucket always holds a roughly constant tenor.

AND THE BREADTH IS MEASURED, NOT ASSERTED. 30-day and 90-day BTC vol are NOT independent
observations. This screen therefore reports, beside the raw market count, the MEAN PAIRWISE
CORRELATION across markets and the EFFECTIVE INDEPENDENT COUNT that `libs.validation.type2_cost.
pooling_multiplier` derives from it -- and the detection floor that effective count buys. Breadth
that is counted but not deflated is how a 2-market result becomes a 20-market result on paper while
the standard error does not move at all, which would be a worse failure than the one being fixed.

3. THE EXACT CONSTRUCTIONS -- FOUR, FIXED, NAMED BEFORE ANY RESULT
------------------------------------------------------------------
From `libs/research/vol_risk_premium.py`. IV is the ATM implied vol for the market's bucket; RV is
annualised trailing realised vol from the SAME venue's perpetual, over a window MATCHED to the
bucket's tenor (7/30/90/180 days).

    vrp_level       IV(t) - RV(t-w .. t)     the premium as a trader observes it at t. Its trailing
                                             window includes day t's own return, which is the form
                                             most exposed to the contamination declared in section 5.
    vrp_level_lag   IV(t) - RV(t-1-w .. t-1) the DE-CONTAMINATED premium: day t's squared return is
                                             absent from the signal while remaining in the
                                             same-period target. Pre-registered here, up front,
                                             precisely so it can never be mistaken for a repair
                                             applied after watching the angle-20 gate fire.
    vrp_log_ratio   log(IV(t) / RV(t-1-w .. t-1))
                                             scale-free, hence the ONLY construction that may be
                                             pooled across underlyings whose vol levels differ 3x.
    iv_level        IV(t)                    THE CONTROL, and it is load-bearing. If the implied
                                             LEVEL alone scores as well as the premium, then
                                             "premium" is a story told over a vol-level signal and
                                             the mechanism claim is unsupported by this evidence.

  TARGETS (two, fixed):
    short_vol_carry     1 - r(t)^2 / (IV(t-1)^2 / 365) -- the normalised per-day P&L of a short
                        variance position struck at yesterday's implied level. THE MECHANISM'S OWN
                        PAYOFF, dimensionless so it pools, and honestly shaped: bounded above by 1
                        (a vol seller can win at most the premium) and unbounded below (the tail).
    underlying_return   the perpetual's log return. THE PRIOR ATTEMPT'S TARGET, kept unchanged so
                        this widened screen is directly comparable with the graveyard row it is
                        re-opening; without it, a different number on a different target could be
                        mistaken for having reproduced or refuted the +0.06.

  TWO LEVELS OF TEST, BOTH DECLARED IN ADVANCE:
    PRIMARY (confirmatory)   the POOLED book -- the cross-market mean of the scale-free
                             construction -- screened as ONE contiguous series, 1 construction x
                             2 targets = 2 cells. This is where breadth is supposed to pay, and it
                             is the only level from which a forward clock could ever be earned.
    SECONDARY (exploratory)  every per-market cell, 4 constructions x 2 targets x M markets. These
                             are the breadth INVENTORY. They are all reported however they land,
                             and NO per-market cell may be promoted on its own.
  Which construction is poolable is fixed by UNITS, not by results: only a scale-free series can be
  averaged across a 7-underlying cross-section without BTC's vol scale dominating it. There is no
  forking path here -- the choice was determined before any number existed.

  WHY A POOLED BOOK AND NOT A FLAT STACK OF MARKETS. `axis_screen` z-scores over a trailing
  20-period window and takes its own forward shift over whatever array it is handed. Concatenating
  M markets end to end puts a seam every T rows at which the z-window straddles two different
  markets and the forward shift pairs one market's signal with another market's target -- 21
  corrupted rows per seam, roughly 10% of a 20-market panel, silently. The cross-sectional mean
  keeps ONE contiguous series on ONE clock, so every harness operation is exactly what it claims.

4. THE MULTIPLICITY CHARGE -- alpha STAYS 0.05
----------------------------------------------
`libs.validation.type2_cost.critical_z(alpha=0.05, n_tests=N, two_sided=True)` -- Bonferroni, the
desk's own documented approximation to the Romano-Wolf max-null critical value. TWO charges are
computed and BOTH are published for every pooled cell:

    N_primary = max(2, pooled cells actually scored)          the confirmatory family
    N_full    = max(preregistered total, all cells scored)     every cell this script looked at

A pooled cell that clears the primary charge but not the full one is reported as exactly that, in
those words, and is NOT called a survivor. A per-market cell is charged at N_full always. N is
never allowed to shrink below the pre-registered count: a run that reads less panel than planned
cannot buy significance by shrinking its own family. alpha is never moved; the family only grows.

5. THE CONTAMINATION HAZARD -- DECLARED, NOT DESIGNED AWAY
-----------------------------------------------------------
A trailing realised vol computed through day t contains day t's squared return, and BOTH targets
are functions of that same squared return. Signal and same-period target are therefore mechanically
linked, and a naive VRP screen will read that link as forecasting skill. This is the identical
failure mode that killed coinbase-premium, Turkey-premium and kimchi, arriving through a different
door.

So the screen does three things, none optional:
  (a) It runs the AUDITED harness `libs/research/axis_screen.stage_a_screen`, whose angle-20
      de-contamination gate is baked in and cannot be skipped. Nothing here hand-rolls a screen.
  (b) It pre-registers the LAGGED-RV form alongside the through-t form, so the contaminated and
      de-contaminated readings of the same economics sit side by side in the artifact.
  (c) It pre-registers `iv_level` as a control, so a result that is really about the vol level
      cannot be reported as a result about the premium.

6. THE ALIGNMENT RULE -- DECLARED, because unstated alignment voids the screen
-------------------------------------------------------------------------------
ONE VENUE, ONE STAMP. Deribit stamps daily bars and settles options at 08:00 UTC. Option marks, the
perpetual closes used for realised variance, and the expiry instants are all read on that clock
(verified: option and perp 1D ticks land on identical 08:00 UTC timestamps). Sourcing implied and
realised from one venue and one stamp makes the session-offset artifact UNAVAILABLE rather than
merely unlikely -- and that class of artifact is what the desk's kimchi/Turkey/Coinbase kills were.

  SIGNAL   computed from the chain marked at 08:00 UTC on day t and from trailing realised variance
           ending at t (or t-1 for the lagged forms). Every input is in the information set at t.
  TARGET   the quantity realised OVER day t, i.e. across (t-1, t]. That is `axis_screen`'s own
           contract; the harness performs the forward shift ITSELF and pairs signal[t] with
           target[t+1]. Handing it an already-shifted target makes it shift twice, which is the
           misalignment signature its own lookahead rail fires on.
  WINDOW   the predicted window is therefore (t, t+1], and the day the signal was observed is NOT
           in it.
  GAPS     a market is screened on its LONGEST CONTIGUOUS DAILY RUN. Compacting around a gap would
           re-label the observation after it as "tomorrow" when it is a week later -- the exact
           misalignment the rail exists to catch, and invisible in the output. Truncating instead
           shortens the sample, which can only attenuate an IC toward zero, and the dropped count
           is reported rather than buried.
  RATES    none assumed. Black-76 is applied undiscounted on the forward recovered from put-call
           parity at the money -- Deribit's own mark convention. No interest-rate series is
           available keylessly and a guessed one would be a fabricated input wearing a model's name.

7. WHAT A SURVIVOR EARNS
------------------------
A forward clock, and nothing else. Stage A has ZERO promotion authority: this script cannot size a
position, cannot write a clock file, and cannot consume one of the desk's twelve Holm-corrected
forward slots. A pooled cell qualifies only if it is SCREEN-INTERESTING from the audited harness,
POWERED by the harness's own detection floor, past the angle-20 gate, and clear of the family-wise
critical value -- and even then it is a candidate for a clock, not a position.

8. NEGATIVE RESULTS ARE THE EXPECTED DELIVERABLE
-------------------------------------------------
Zero survivors is publishable -- but only if it is distinguishable from blindness. Every cell
carries a `libs/validation/type2_cost` reading: effective sample, detection floor at the family-wise
critical value, and power at the declared effect sizes. A cell labelled UNDERPOWERED is NOT
graveyard-grade and must never be recorded as a refutation; a POWERED negative is permanent
knowledge and is emitted with its reason and its floor. And because breadth is the exact thing that
killed the previous attempt, the artifact states the MARKET COUNT ACHIEVED, the effective
independent count after correlation, and the detection floor that count buys -- so the next reader
can tell whether the widening worked even if the mechanism did not.

9. DATA, AND THE REFUSAL TO FABRICATE
--------------------------------------
The panel is built by `scripts/collect_deribit_vol_markets.py` into data/, which is gitignored, so
absence is EXPECTED in a fresh checkout and a REAL blocker on a box with no egress. This script has
NO synthetic fallback and no generator anywhere in its import graph: an unreadable panel writes a
NOT-READABLE-HERE status artifact naming the exact missing paths and the exact command that fills
them, then exits 0. A premium measured on a simulated surface is a fact about the simulator.

Read-only over data/. Writes one artifact. No keys, no order path, zero promotion authority.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.research.axis_screen import stage_a_screen  # noqa: E402
from libs.research.vol_risk_premium import (  # noqa: E402
    CONSTRUCTIONS,
    MIN_MARKET_OBS,
    TARGETS,
    TENOR_BUCKETS,
    MarketSeries,
    VrpAlignment,
    align_markets,
    log_returns,
    longest_contiguous_run,
    market_key,
    mean_pairwise_corr,
    pooled_mean,
    realised_vol,
    rv_window_days,
)
from libs.validation.type2_cost import (  # noqa: E402
    DECLARED_CORRELATION_EFFECTS,
    DEFAULT_ALPHA,
    Type2Cost,
    correlation_negative,
    critical_z,
    headline,
    indeterminate,
    min_detectable_correlation,
    pooling_multiplier,
)

SCHEMA_VERSION = "1.0.0"
MECHANISM_CLASS = "volatility_risk_premium"

PANEL = ROOT / "data/deribit_vol_markets.jsonl"
BARS = ROOT / "data/deribit_underlying_bars.jsonl"
REPORT = ROOT / "data/vol_risk_premium_screen.json"
COLLECTOR = "scripts/collect_deribit_vol_markets.py --mode both"

#: The prior attempt's market count, from the census note and the script's own honesty string.
PRIOR_MARKETS = 2

#: The ONLY construction whose units permit cross-market pooling. Fixed by dimensional analysis,
#: not by results -- see section 3.
POOLABLE = ("vrp_log_ratio",)

#: PRE-REGISTERED family floors. `PRIMARY` is the confirmatory pooled family; `SECONDARY_PER_MARKET`
#: is per-market cells for ONE market and is multiplied by the market count at run time.
PRIMARY_FAMILY = len(POOLABLE) * len(TARGETS)
SECONDARY_PER_MARKET = len(CONSTRUCTIONS) * len(TARGETS)

#: Harness floors, restated so the artifact records the bar it was judged against. NOT tunable from
#: the command line: a bar that can be moved at the call site is not a bar.
IC_MIN = 0.03
SHARPE_MIN = 0.5

#: Bucket centres in days -- the expiry representing a bucket on a date is the listed one whose dte
#: is nearest this. Declared so the choice is a rule and not a per-run judgement.
BUCKET_CENTRE = {"t07": 7.0, "t30": 30.0, "t90": 90.0, "t180": 180.0}

#: Plausibility band for an annualised implied vol, in DECIMAL. Outside it a row is a parse error
#: (a unit mix-up, a crossed book, a stale mark), not a market observation, and it is dropped rather
#: than screened. 1% annualised does not exist in crypto and 500% is a dislocation, not a quote.
IV_MIN_DECIMAL = 0.01
IV_MAX_DECIMAL = 5.0

_KILL_REASONS = {
    "SCREEN-WEAK": ("powered and below the floors: |IC| < 0.03 or best timing Sharpe < 0.5 on a "
                    "sample that could have resolved an effect at 0.03"),
    "TIMING-ARTIFACT": ("angle-20 de-contamination FAILED: |same-period corr| > 0.20 or residual "
                        "IC collapsed below half the raw IC. For this class that is the specific "
                        "hazard declared in section 5 -- a trailing realised vol shares day t's "
                        "squared return with the same-period target, so the 'forecast' is a "
                        "restatement of a move that had already happened"),
    "SUSPECT-LOOKAHEAD": ("too strong to be credible at this horizon -- read as misalignment, "
                          "never as edge; NEVER earns a clock"),
}
_KILL_VERDICTS = tuple(_KILL_REASONS)


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def pre_registration(alignment: VrpAlignment, *, n_markets: int) -> dict[str, Any]:
    """The machine-readable echo of this module's docstring. Written into EVERY artifact.

    A pre-registration that lives only in prose cannot be diffed, so a later run that quietly
    screened a fifth construction would look identical to this one in the record.
    """
    return {
        "mechanism_class": MECHANISM_CLASS,
        "census_rank": 5,
        "census_gap_score": 0.3264,
        "census_coverage": "TESTED-SHALLOW (1 prior kill: options_vrp)",
        "prior_result": ("IC +0.06 -- the campaign's best measured IC anywhere -- killed on "
                         "BREADTH (2 markets: BTC and ETH DVOL), not on sign"),
        "payer": (
            "the hedger buying protection: a miner with a fixed fiat cost base, a treasury with a "
            "mandate, a levered holder with a hard liquidation price. His demand comes from a "
            "BALANCE-SHEET CONSTRAINT, not from an opinion about fair value, so it cannot be "
            "argued away by learning that implied vol is on average rich"
        ),
        "recipient": (
            "the option seller, who is short gamma and short jump risk: his loss is unbounded, it "
            "arrives fastest when his other positions are also losing, and his capital is finite"
        ),
        "persistence": (
            "the risk being transferred is GENUINE (insurance is priced above expected loss in "
            "every market that has one); the seller's capital is finite and pro-cyclical, so "
            "supply contracts exactly when demand spikes; and the buyer is price-insensitive by "
            "construction because a hedge bought to satisfy a constraint is bought at the offer"
        ),
        "falsifier": (
            "H0: for every pre-registered cell the premium carries no CONDITIONAL information -- "
            "|IC| < 0.03 against the next period's short-vol carry, and any apparent skill is "
            "accounted for by the trailing RV window sharing day t's squared return with the "
            "same-period target. H1 needs |IC| >= 0.03, best timing Sharpe >= 0.5, POWERED by the "
            "harness's own floor, angle-20 passed, AND |IC|*sqrt(n_eff) >= the family-wise "
            "critical value at alpha 0.05. 'The average premium is positive' is NOT a finding."
        ),
        "constructions": sorted(CONSTRUCTIONS),
        "targets": sorted(TARGETS),
        "poolable_constructions": list(POOLABLE),
        "poolable_chosen_by": ("UNITS, not results -- only a scale-free series can be averaged "
                               "across a 7-underlying cross-section without BTC's vol scale "
                               "dominating it. Determined before any number existed"),
        "tenor_buckets": [{"name": n, "dte_from": lo, "dte_to": hi} for n, lo, hi in TENOR_BUCKETS],
        "bucket_representative_expiry": ("the listed expiry whose days-to-expiry on the "
                                         "observation date is nearest the bucket centre"),
        "market_definition": "one underlying x one tenor bucket",
        "prior_attempt_markets": PRIOR_MARKETS,
        "markets_this_run": int(n_markets),
        "family_primary_preregistered": PRIMARY_FAMILY,
        "family_secondary_per_market": SECONDARY_PER_MARKET,
        "alpha": DEFAULT_ALPHA,
        "multiplicity": (
            "Bonferroni critical_z at alpha 0.05, computed TWICE and both published: N_primary "
            "over the confirmatory pooled family, N_full over every cell this script looked at. A "
            "pooled cell clearing the first and not the second is reported in exactly those words "
            "and is NOT called a survivor. Shrinking the run cannot shrink the charge."
        ),
        "ic_min": IC_MIN,
        "sharpe_min": SHARPE_MIN,
        "alignment": alignment.as_dict(),
        "contamination_hazard": (
            "a trailing realised vol through day t contains day t's squared return, and both "
            "targets are functions of that same squared return -- the coinbase/Turkey/kimchi "
            "failure mode arriving through a different door. Both the through-t and the "
            "ending-at-t-1 forms are pre-registered so the contaminated and de-contaminated "
            "readings of the same economics sit side by side"
        ),
        "control": ("iv_level -- if the implied LEVEL alone scores as well as the premium, then "
                    "'premium' is a story told over a vol-level signal"),
        "authority": "NONE -- Stage A. No promotion, no sizing, no forward-clock file written.",
        "no_synthetic_fallback": (
            "no generator is in this script's import graph: an unreadable panel yields a status "
            "artifact, never a fabricated row"
        ),
    }


def missing_paths() -> list[str]:
    out: list[str] = []
    for p in (PANEL, BARS):
        if not p.is_file():
            out.append(_rel(p))
        elif not p.read_text("utf-8").strip():
            out.append(f"{_rel(p)} (exists, empty)")
    return out


def not_readable_here(alignment: VrpAlignment) -> dict[str, Any]:
    """THE HONEST EMPTY RESULT. Not a failure, not a zero, and above all not a simulation."""
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_utc": datetime.now(tz=UTC).isoformat(),
        "script": "scripts/screen_vol_risk_premium.py",
        "status": "NOT-READABLE-HERE",
        "stage": "A (zero promotion authority)",
        "mechanism_class": MECHANISM_CLASS,
        "missing_paths": missing_paths(),
        "filled_by": COLLECTOR,
        "why": ("the vol-market panel is built into data/, which is gitignored, so this is "
                "EXPECTED in a fresh checkout and a REAL blocker on a box with no egress. The "
                "screen is otherwise complete and runs unchanged the moment the panel exists."),
        "refusal": ("no synthetic surface is generated and no result is reported. A premium "
                    "measured on a simulated surface is a fact about the simulator, and it would "
                    "enter the funnel wearing the same vocabulary as a real one."),
        "vps_runnable": ("keyless public REST against www.deribit.com; needs only outbound HTTPS. "
                         f"Run `{COLLECTOR}` then re-run this script unchanged."),
        "pre_registration": pre_registration(alignment, n_markets=0),
        "breadth": {"markets_achieved": 0, "prior_attempt_markets": PRIOR_MARKETS},
        "rows": [], "survivors": [], "graveyard": [], "tally": {},
        "authority": "NONE -- Stage A.",
    }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text("utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out


def bar_series(rows: list[dict[str, Any]]) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """(dates_ms, close) per underlying, ascending and de-duplicated. The realised-vol input."""
    by: dict[str, dict[int, float]] = defaultdict(dict)
    for r in rows:
        try:
            ts = int(r["ts_ms"])
            px = float(r["close"])
        except (KeyError, TypeError, ValueError):
            continue
        if px > 0.0:
            by[str(r.get("underlying", "")).upper()][ts] = px
    out: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for u, m in by.items():
        ts = np.array(sorted(m), dtype="int64")
        out[u] = (ts, np.array([m[int(t)] for t in ts], dtype="float64"))
    return out


def market_iv(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[int, float]]:
    """(underlying, bucket) -> {date_ms: ATM implied vol as an ANNUALISED DECIMAL}.

    THE UNIT IS CONVERTED HERE, ONCE, FROM THE ROW'S OWN DECLARATION -- never inferred from
    magnitude. Deribit publishes `mark_iv` in PERCENT while the collector's Black-76 inversion
    emits DECIMAL, and the two differ by 100x on a field that looks identical either way. A screen
    that guessed would silently divide a 45% vol into a 0.45% one, leaving every IC intact (the
    harness z-scores, so a constant factor cancels) while destroying every Sharpe and every
    variance-swap payoff that depends on the LEVEL. Rows written before the unit field existed are
    read as decimal, which is the collector's only convention.

    AND THE RESULT IS RANGE-CHECKED. An annualised vol outside [1%, 500%] is not a market
    observation, it is a parse error, and it is dropped rather than screened -- a 0.0045 that got
    through would look exactly like a very calm market to everything downstream.

    Where several expiries fall in one bucket on one date, the representative is the one whose dte
    is NEAREST THE BUCKET CENTRE -- a fixed rule, declared in the pre-registration, so the choice is
    never a per-run judgement and never a search over which expiry scored.
    """
    best: dict[tuple[str, str], dict[int, tuple[float, float]]] = defaultdict(dict)
    for r in rows:
        try:
            ts = int(r["ts_ms"])
            raw = float(r["atm_iv"])
            dte = float(r["dte_days"])
        except (KeyError, TypeError, ValueError):
            continue
        unit = str(r.get("atm_iv_unit", "decimal_annualised"))
        iv = raw / 100.0 if unit.startswith("percent") else raw
        bucket = str(r.get("bucket", ""))
        under = str(r.get("underlying", "")).upper()
        if bucket not in BUCKET_CENTRE or not under:
            continue
        if not (IV_MIN_DECIMAL <= iv <= IV_MAX_DECIMAL):
            continue
        dist = abs(dte - BUCKET_CENTRE[bucket])
        cur = best[(under, bucket)].get(ts)
        if cur is None or dist < cur[0]:
            best[(under, bucket)][ts] = (dist, iv)
    return {k: {ts: iv for ts, (_, iv) in v.items()} for k, v in best.items()}


def build_markets(panel: list[dict[str, Any]],
                  bars: dict[str, tuple[np.ndarray, np.ndarray]]) -> \
        tuple[list[MarketSeries], list[dict[str, Any]]]:
    """Assemble every (underlying, bucket) market on its longest contiguous daily run.

    Realised vol and daily returns are computed on the underlying's FULL uninterrupted bar series
    and then indexed into the market's dates -- never derived from a close array already subset to
    the dates an implied vol happens to exist for, which would price a three-day move as one day.
    """
    ivs = market_iv(panel)
    out: list[MarketSeries] = []
    inventory: list[dict[str, Any]] = []
    for (under, bucket), by_ts in sorted(ivs.items()):
        key = market_key(under, bucket)
        bar = bars.get(under)
        if bar is None:
            inventory.append({"market": key, "status": "NO-BARS", "n_iv_days": len(by_ts),
                              "why": f"no perpetual bar series for {under}"})
            continue
        bts, bpx = bar
        rets_full = log_returns(bpx)
        w = rv_window_days(bucket)
        rv_now_full = realised_vol(rets_full, w, lag=0)
        rv_lag_full = realised_vol(rets_full, w, lag=1)
        common = np.intersect1d(np.array(sorted(by_ts), dtype="int64"), bts)
        if common.size == 0:
            inventory.append({"market": key, "status": "NO-OVERLAP", "n_iv_days": len(by_ts),
                              "why": "implied and bar dates do not intersect"})
            continue
        start, stop = longest_contiguous_run(common)
        run = common[start:stop]
        idx = np.searchsorted(bts, run)
        series = MarketSeries(
            key=key, underlying=under, bucket=bucket, dates_ms=run,
            atm_iv=np.array([by_ts[int(t)] for t in run], dtype="float64"),
            close=bpx[idx], rets=rets_full[idx],
            rv_now=rv_now_full[idx], rv_lag=rv_lag_full[idx])
        inventory.append({
            "market": key, "status": "BUILT" if run.size >= MIN_MARKET_OBS else "TOO-SHORT",
            "n_iv_days": len(by_ts), "n_overlap_days": int(common.size),
            "n_contiguous_days": int(run.size),
            "dropped_to_contiguity": int(common.size - run.size),
            "rv_window_days": w,
            "first": datetime.fromtimestamp(int(run[0]) / 1000.0, tz=UTC).date().isoformat(),
            "last": datetime.fromtimestamp(int(run[-1]) / 1000.0, tz=UTC).date().isoformat(),
        })
        if run.size >= MIN_MARKET_OBS:
            out.append(series)
    return out, inventory


def screen_market(m: MarketSeries, alignment: VrpAlignment) -> list[dict[str, Any]]:
    """Every pre-registered (construction x target) cell for ONE market.

    EVERY cell produces a row, including the ones that could not be screened. A construction that
    silently vanishes from the record is indistinguishable from one that was never tried, and that
    difference is exactly what the pre-registration exists to preserve.
    """
    rows: list[dict[str, Any]] = []
    for cname, fn in sorted(CONSTRUCTIONS.items()):
        sig = np.asarray(fn(m), dtype="float64")
        for tname, tfn in sorted(TARGETS.items()):
            tgt = np.asarray(tfn(m), dtype="float64")
            ok = np.isfinite(sig) & np.isfinite(tgt)
            base: dict[str, Any] = {
                "level": "per_market", "market": m.key, "underlying": m.underlying,
                "bucket": m.bucket, "construction": cname, "target": tname,
                "n_paired": int(ok.sum()), "alignment": alignment.as_dict(),
            }
            name = f"{m.key}|{cname}|{tname}"
            if int(ok.sum()) < MIN_MARKET_OBS:
                rows.append({**base, "verdict": "TOO-FEW-PAIRS",
                             "why": (f"{int(ok.sum())} paired observations against a floor of "
                                     f"{MIN_MARKET_OBS} -- an IC here would describe coincidence"),
                             "type2": indeterminate(
                                 name, "fewer paired observations than the screen's own floor",
                                 source="scripts/screen_vol_risk_premium.py",
                                 effect_unit="ic").as_dict()})
                continue
            # CONTIGUITY IS PRESERVED THROUGH THE MASK. `ok` can only drop a PREFIX here in
            # practice (realised-vol warm-up and the carry's t=0 NaN), but a mid-series hole would
            # compact the array and re-label the row after it as "tomorrow". Taking the longest
            # contiguous run of the mask keeps the harness's positional forward shift honest.
            idx = np.flatnonzero(ok)
            s0, s1 = longest_contiguous_run(idx.astype("int64"), step_ms=1)
            use = idx[s0:s1]
            if use.size < MIN_MARKET_OBS:
                rows.append({**base, "verdict": "TOO-FEW-PAIRS",
                             "why": ("the longest CONTIGUOUS block of paired observations is "
                                     f"{use.size}, below the {MIN_MARKET_OBS} floor"),
                             "type2": indeterminate(
                                 name, "no contiguous block long enough to screen",
                                 source="scripts/screen_vol_risk_premium.py",
                                 effect_unit="ic").as_dict()})
                continue
            res = stage_a_screen(sig[use], tgt[use], name=name, ic_min=IC_MIN,
                                 sharpe_min=SHARPE_MIN, horizon_days=alignment.horizon_days)
            rows.append({**base, "n_contiguous_pairs": int(use.size),
                         **{k: v for k, v in res.items() if k != "name"}})
    return rows


def screen_pooled(markets: list[MarketSeries], alignment: VrpAlignment) -> \
        tuple[list[dict[str, Any]], dict[str, Any]]:
    """The CONFIRMATORY cells: the cross-market book of each poolable construction.

    Returns (rows, breadth block). The breadth block is the answer to the question the census asked
    -- did more markets buy anything -- and it is reported whether or not anything survived.
    """
    rows: list[dict[str, Any]] = []
    breadth: dict[str, Any] = {
        "market_definition": "one underlying x one tenor bucket",
        "prior_attempt_markets": PRIOR_MARKETS,
        "prior_attempt": ("scripts/run_options_vrp_backtest.py -- Deribit DVOL index, BTC + ETH "
                          "only, because DVOL exists for no other currency"),
        "markets_achieved": len(markets),
        "underlyings": sorted({m.underlying for m in markets}),
        "buckets": sorted({m.bucket for m in markets}),
    }
    if not markets:
        breadth["note"] = "no market cleared the observation floor; nothing to pool"
        return rows, breadth

    for cname in POOLABLE:
        fn = CONSTRUCTIONS[cname]
        sigs = [np.asarray(fn(m), dtype="float64") for m in markets]
        dates = [m.dates_ms for m in markets]
        grid, mat = align_markets(sigs, dates)
        rho = mean_pairwise_corr(mat)
        eff = pooling_multiplier(len(markets), 0.0 if not np.isfinite(rho) else float(rho))
        breadth[f"{cname}_common_dates"] = int(grid.size)
        breadth[f"{cname}_mean_pairwise_corr"] = (round(float(rho), 4)
                                                  if np.isfinite(rho) else None)
        breadth[f"{cname}_effective_independent_markets"] = round(float(eff), 3)
        if grid.size < MIN_MARKET_OBS:
            rows.append({"level": "pooled", "construction": cname, "target": "*",
                         "verdict": "TOO-FEW-PAIRS", "n_paired": int(grid.size),
                         "why": (f"{int(grid.size)} dates common to all {len(markets)} markets, "
                                 f"below the {MIN_MARKET_OBS} floor. The date INTERSECTION is "
                                 "used rather than a forward fill: a market not yet listed has "
                                 "no observation, and carrying one forward would inject a flat "
                                 "stretch that reads as low signal volatility"),
                         "type2": indeterminate(
                             f"pooled|{cname}", "too few dates common to every market",
                             source="scripts/screen_vol_risk_premium.py",
                             effect_unit="ic").as_dict()})
            continue
        book = pooled_mean(mat)
        for tname, tfn in sorted(TARGETS.items()):
            tsigs = [np.asarray(tfn(m), dtype="float64") for m in markets]
            _, tmat = align_markets(tsigs, dates)
            tbook = pooled_mean(tmat)
            ok = np.isfinite(book) & np.isfinite(tbook)
            idx = np.flatnonzero(ok)
            s0, s1 = longest_contiguous_run(idx.astype("int64"), step_ms=1)
            use = idx[s0:s1]
            base: dict[str, Any] = {
                "level": "pooled", "construction": cname, "target": tname,
                "markets_pooled": len(markets), "n_paired": int(ok.sum()),
                "n_contiguous_pairs": int(use.size),
                "mean_pairwise_corr": round(float(rho), 4) if np.isfinite(rho) else None,
                "effective_independent_markets": round(float(eff), 3),
                "alignment": alignment.as_dict(),
            }
            name = f"pooled|{cname}|{tname}"
            if use.size < MIN_MARKET_OBS:
                rows.append({**base, "verdict": "TOO-FEW-PAIRS",
                             "why": "no contiguous pooled block long enough to screen",
                             "type2": indeterminate(
                                 name, "pooled book too short",
                                 source="scripts/screen_vol_risk_premium.py",
                                 effect_unit="ic").as_dict()})
                continue
            res = stage_a_screen(book[use], tbook[use], name=name, ic_min=IC_MIN,
                                 sharpe_min=SHARPE_MIN, horizon_days=alignment.horizon_days)
            rows.append({**base, **{k: v for k, v in res.items() if k != "name"}})
    return rows, breadth


def _significance(rows: list[dict[str, Any]], *, n_primary: int, n_full: int) -> None:
    """Attach BOTH family-wise bars to every scored row, in place.

    A pooled row carries both charges because the honest statement about a confirmatory cell is
    "it cleared the family it was pre-registered in, and here is whether it also clears the charge
    for everything this script looked at". A per-market row carries only the full charge: it is
    exploratory and can never be promoted.
    """
    z_primary = critical_z(DEFAULT_ALPHA, max(1, n_primary), two_sided=True)
    z_full = critical_z(DEFAULT_ALPHA, max(1, n_full), two_sided=True)
    for r in rows:
        n_eff = r.get("n_eff")
        ic = r.get("ic")
        if not isinstance(n_eff, (int, float)) or not isinstance(ic, (int, float)):
            continue
        if not np.isfinite(float(n_eff)) or not np.isfinite(float(ic)) or float(n_eff) <= 0:
            continue
        root = float(np.sqrt(float(n_eff)))
        r["family_size_full"] = int(n_full)
        r["family_z_critical_full"] = round(float(z_full), 4)
        r["ic_needed_full_family"] = round(float(z_full) / root, 4)
        r["clears_full_family"] = bool(abs(float(ic)) >= float(z_full) / root)
        if str(r.get("level")) == "pooled":
            r["family_size_primary"] = int(n_primary)
            r["family_z_critical_primary"] = round(float(z_primary), 4)
            r["ic_needed_primary_family"] = round(float(z_primary) / root, 4)
            r["clears_primary_family"] = bool(abs(float(ic)) >= float(z_primary) / root)


def _type2(rows: list[dict[str, Any]], *, n_full: int) -> list[tuple[dict[str, Any], Type2Cost]]:
    """Attach the Type-II reading to every scored row, in place; return (row, cost) pairs.

    A zero without a power figure is unfalsifiable: it cannot be told apart from "we could not have
    seen anything even if it were there", and those two statements retire opposite things -- a
    hypothesis class in the first case, an INSTRUMENT in the second. 78% of this desk's recorded
    negatives carry no such figure, which is why every row here gets one.
    """
    costs: list[tuple[dict[str, Any], Type2Cost]] = []
    for r in rows:
        n = r.get("n")
        if not isinstance(n, (int, float)) or float(n) <= 0:
            continue
        cost = correlation_negative(
            f"{r.get('level')}|{r.get('market', 'book')}|{r.get('construction')}|"
            f"{r.get('target')}",
            n_obs=float(n),
            source="scripts/screen_vol_risk_premium.py",
            # Daily targets are NON-OVERLAPPING -- one day is one target -- so no overlap deflator
            # applies and this is the same n_eff the harness computed. The two must never disagree
            # about whether a cell was powered.
            horizon_periods=1.0,
            # The pooled book is ONE series on one clock, not a stack, so panel_width is 1 here as
            # well. Cross-market dependence is reported separately as the effective independent
            # market count -- it belongs to the BREADTH claim, not to this cell's sample size.
            panel_width=1,
            n_tests=n_full,
            alpha=DEFAULT_ALPHA,
            effect_unit="ic",
            note=("TWO FLOORS ARE REPORTED AND THEY ANSWER DIFFERENT QUESTIONS: the harness's "
                  "min_detectable_ic is the UNADJUSTED (N=1) floor its SCREEN-WEAK / "
                  "SCREEN-UNDERPOWERED split already encodes and the basis on which a cell may be "
                  "graveyarded, while min_detectable_effect here is the floor at the FULL family "
                  "charge -- the bar a FIND had to clear. A cell can be powered against the first "
                  "and not the second; that is the price of the family, not a contradiction. "
                  "Serial correlation in implied vol is NOT deflated, so this is an upper bound."),
        )
        r["type2"] = cost.as_dict()
        r["type2_label"] = cost.label
        costs.append((r, cost))
    return costs


def classify(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(survivors, graveyard rows). CONSERVATIVE ON BOTH SIDES.

    A SURVIVOR must be a POOLED (confirmatory) cell, must have earned SCREEN-INTERESTING from the
    audited harness, must be POWERED by the harness's own floor, and must clear BOTH family-wise
    charges. A per-market cell is never a survivor of this screen -- it is breadth inventory.

    A GRAVEYARD ROW is a POWERED negative or an artifact verdict, WITH its reason and its detection
    floor. UNDERPOWERED cells are excluded on purpose: the graveyard is permanent, and "could not
    tell" must never be filed as "it is dead" -- which is exactly the mistake that would have
    buried this mechanism class for good after its 2-market run.
    """
    survivors: list[dict[str, Any]] = []
    graveyard: list[dict[str, Any]] = []
    for r in rows:
        verdict = str(r.get("verdict", ""))
        pooled = str(r.get("level")) == "pooled"
        if (pooled and verdict == "SCREEN-INTERESTING" and bool(r.get("powered"))
                and bool(r.get("clears_primary_family")) and bool(r.get("clears_full_family"))):
            survivors.append({
                "level": "pooled", "construction": r.get("construction"),
                "target": r.get("target"), "ic": r.get("ic"), "n": r.get("n"),
                "n_eff": r.get("n_eff"), "markets_pooled": r.get("markets_pooled"),
                "effective_independent_markets": r.get("effective_independent_markets"),
                "ic_needed_primary_family": r.get("ic_needed_primary_family"),
                "ic_needed_full_family": r.get("ic_needed_full_family"),
                "same_period_corr": r.get("same_period_corr"),
                "residual_ic": r.get("residual_ic"),
                "earns": ("a pre-registered FORWARD CLOCK and nothing else -- this script does not "
                          "write one; consuming one of twelve Holm-corrected forward slots is a "
                          "principal-visible act"),
            })
            continue
        floor = ((r.get("type2") or {}).get("min_detectable_effect")
                 if isinstance(r.get("type2"), dict) else None)
        base = {
            "level": r.get("level"), "market": r.get("market", "book"),
            "construction": r.get("construction"), "target": r.get("target"),
            "ic": r.get("ic"), "n": r.get("n"), "n_eff": r.get("n_eff"),
            "detection_floor_ic_unadjusted": r.get("min_detectable_ic"),
            "detection_floor_ic_full_family": floor,
            "type2_label": r.get("type2_label"),
        }
        if verdict in _KILL_VERDICTS and bool(r.get("powered")):
            graveyard.append({**base, "verdict": verdict,
                              "same_period_corr": r.get("same_period_corr"),
                              "residual_ic": r.get("residual_ic"),
                              "reason": _KILL_REASONS[verdict]})
    return survivors, graveyard


def build_report(rows: list[dict[str, Any]], *, alignment: VrpAlignment,
                 markets: list[MarketSeries], inventory: list[dict[str, Any]],
                 breadth: dict[str, Any], panel_rows: int) -> dict[str, Any]:
    scored = [r for r in rows if isinstance(r.get("ic"), (int, float))]
    pooled_scored = [r for r in scored if str(r.get("level")) == "pooled"]
    n_primary = max(PRIMARY_FAMILY, len(pooled_scored))
    n_full = max(PRIMARY_FAMILY + SECONDARY_PER_MARKET * max(len(markets), 1), len(scored))
    _significance(scored, n_primary=n_primary, n_full=n_full)
    pairs = _type2(scored, n_full=n_full)
    survivors, graveyard = classify(scored)

    surv_keys = {(s["construction"], s["target"]) for s in survivors}
    costs = [c for r, c in pairs
             if not (str(r.get("level")) == "pooled"
                     and (r.get("construction"), r.get("target")) in surv_keys)]

    tally: dict[str, int] = {}
    for r in rows:
        v = str(r.get("verdict", "?"))
        tally[v] = tally.get(v, 0) + 1

    # THE BREADTH ANSWER, and it is the reason this screen exists. The detection floor is quoted at
    # the pooled book's own effective sample, because that is the series a decision would be taken
    # on -- and beside it, what the SAME arithmetic said for the 2-market predecessor, so a reader
    # can see whether the widening moved the floor or only the row count.
    pooled_n = max((float(r.get("n_eff") or 0.0) for r in pooled_scored), default=0.0)
    breadth["pooled_n_eff"] = round(pooled_n, 1)
    breadth["detection_floor_ic_unadjusted"] = (
        round(float(min_detectable_correlation(n_eff=pooled_n, n_tests=1, power=0.5)), 4)
        if pooled_n >= 3 else None)
    breadth["detection_floor_ic_primary_family"] = (
        round(float(min_detectable_correlation(n_eff=pooled_n, n_tests=n_primary)), 4)
        if pooled_n >= 3 else None)
    breadth["detection_floor_ic_full_family"] = (
        round(float(min_detectable_correlation(n_eff=pooled_n, n_tests=n_full)), 4)
        if pooled_n >= 3 else None)
    breadth["prior_measured_ic"] = 0.06
    # WHICH CONSTRAINT IS NOW BINDING. The census named BREADTH as the killer, so the screen owes
    # the next reader an answer to "did widening fix it, and if not what is stopping it now". These
    # are computed from the run's own numbers, never narrated: days_needed inverts
    # min_detectable_correlation at the prior measured effect, and the binding label follows from
    # comparing markets achieved against days achieved.
    z_unadj = float(critical_z(DEFAULT_ALPHA, 1, two_sided=True))
    z_prim = float(critical_z(DEFAULT_ALPHA, n_primary, two_sided=True))
    breadth["pooled_common_days"] = int(breadth.get(f"{POOLABLE[0]}_common_dates", 0) or 0)
    breadth["days_needed_at_prior_ic_unadjusted"] = int(np.ceil((z_unadj / 0.06) ** 2))
    breadth["days_needed_at_prior_ic_primary_family"] = int(np.ceil((z_prim / 0.06) ** 2))
    floor_unadj = breadth.get("detection_floor_ic_unadjusted")
    if len(markets) <= PRIOR_MARKETS:
        breadth["binding_constraint"] = "BREADTH"          # the widening did not happen
    elif floor_unadj is None or float(floor_unadj) > 0.06:
        breadth["binding_constraint"] = "DEPTH-AT-BREADTH"  # more markets, still cannot resolve
    else:
        breadth["binding_constraint"] = "NEITHER-RESOLVED"  # the panel can now see the prior IC
    breadth["why_depth_is_short"] = (
        "a backfill can only see a tenor bucket for as long as a CURRENTLY-LISTED contract has "
        "been inside it, because expired contracts are unretrievable. A bucket of width W days is "
        "therefore capped near W days of history per contract -- ~7d for t07, ~35d for t30, ~75d "
        "for t90 -- and only the long bucket chains several contracts. That is why the t180 "
        "markets carry ~315 days while every other bucket carries tens, and why the common-date "
        "intersection across all markets is short. It is a property of what is retrievable, not "
        "an estimator choice, and the ONLY thing that fixes it is calendar time: the daily "
        f"snapshot in {COLLECTOR} adds one day per day to every market at once.")
    breadth["breadth_gain_is_measured_not_asserted"] = (
        "markets_achieved is the RAW count; effective_independent_markets deflates it by the "
        "measured mean pairwise correlation via type2_cost.pooling_multiplier. Counting 30-day and "
        "90-day BTC vol as two independent observations is how a 2-market result becomes a "
        "20-market result on paper while the standard error does not move at all.")

    powered = sum(1 for r in scored if bool(r.get("powered")))
    desk = headline(costs) if costs else None
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_utc": datetime.now(tz=UTC).isoformat(),
        "script": "scripts/screen_vol_risk_premium.py",
        "status": "SCREENED",
        "stage": "A (zero promotion authority)",
        "mechanism_class": MECHANISM_CLASS,
        "pre_registration": pre_registration(alignment, n_markets=len(markets)),
        "breadth": breadth,
        "panel_rows": panel_rows,
        "market_inventory": inventory,
        "markets_screened": len(markets),
        "hypotheses": len(rows), "scored": len(scored),
        "family_size_primary": n_primary,
        "family_size_full": n_full,
        "family_z_critical_primary": round(
            float(critical_z(DEFAULT_ALPHA, n_primary, two_sided=True)), 4),
        "family_z_critical_full": round(
            float(critical_z(DEFAULT_ALPHA, n_full, two_sided=True)), 4),
        "declared_effects": list(DECLARED_CORRELATION_EFFECTS),
        "powered_cells_unadjusted": powered,
        "power_headline_at_full_charge": (
            desk.summary() if desk is not None else "no scored cell to power-label"),
        "power_counts_at_full_charge": {
            "negatives": desk.n_negatives if desk is not None else 0,
            "powered": desk.n_powered if desk is not None else 0,
            "underpowered": desk.n_underpowered if desk is not None else 0,
            "indeterminate": desk.n_indeterminate if desk is not None else 0,
        },
        "interesting_but_failed_multiplicity": sum(
            1 for r in scored if str(r.get("verdict")) == "SCREEN-INTERESTING"
            and not bool(r.get("clears_full_family"))),
        "tally": tally,
        "survivors": survivors,
        "graveyard": graveyard,
        "rows": rows,
        "note": (
            "ZERO SURVIVORS IS AN EXPECTED AND PUBLISHABLE OUTCOME. What makes it knowledge rather "
            "than silence is the power column beside every verdict: a POWERED negative looked and "
            "found nothing, an UNDERPOWERED cell could not have seen anything and refutes NOTHING. "
            "Only the first is graveyard-grade. Because this class died on BREADTH last time, the "
            "breadth block is part of the result, not decoration: it records how many markets were "
            "achieved, how independent they actually are, and the detection floor that bought."),
        "authority": "NONE -- Stage A. Nothing here promotes, sizes, or writes a clock file.",
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Stage-A screen: volatility risk premium (gap #5)")
    ap.add_argument("--panel", type=Path, default=PANEL)
    ap.add_argument("--bars", type=Path, default=BARS)
    ap.add_argument("--out", type=Path, default=REPORT)
    a = ap.parse_args(argv)

    alignment = VrpAlignment()
    out_path = Path(a.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    panel = _read_jsonl(Path(a.panel))
    bar_rows = _read_jsonl(Path(a.bars))
    if not panel or not bar_rows:
        report = not_readable_here(alignment)
        out_path.write_text(json.dumps(report, indent=1, default=str), "utf-8")
        print(f"vrp-screen: NOT-READABLE-HERE -- {len(report['missing_paths'])} missing input(s)")
        for p in report["missing_paths"]:
            print(f"    MISSING {p}")
        print(f"  fill with: python3 {COLLECTOR}")
        print("  no synthetic surface is generated and no result is reported")
        return 0

    bars = bar_series(bar_rows)
    markets, inventory = build_markets(panel, bars)
    rows: list[dict[str, Any]] = []
    for m in markets:
        rows.extend(screen_market(m, alignment))
    pooled_rows, breadth = screen_pooled(markets, alignment)
    rows.extend(pooled_rows)

    report = build_report(rows, alignment=alignment, markets=markets, inventory=inventory,
                          breadth=breadth, panel_rows=len(panel))
    out_path.write_text(json.dumps(report, indent=1, default=str), "utf-8")

    b = report["breadth"]
    print(f"vrp-screen: {report['hypotheses']} pre-registered hypotheses over "
          f"{report['markets_screened']} markets ({len(panel)} panel rows)")
    print(f"  BREADTH  {b['markets_achieved']} markets achieved vs {PRIOR_MARKETS} in the prior "
          f"attempt; underlyings {', '.join(b['underlyings'])}")
    for c in POOLABLE:
        print(f"    {c}: mean pairwise corr {b.get(f'{c}_mean_pairwise_corr')} -> "
              f"{b.get(f'{c}_effective_independent_markets')} effective independent markets")
    print(f"    pooled n_eff {b['pooled_n_eff']}, detection floor IC "
          f"{b['detection_floor_ic_unadjusted']} unadjusted / "
          f"{b['detection_floor_ic_primary_family']} primary-family / "
          f"{b['detection_floor_ic_full_family']} full-family "
          f"(prior measured IC {b['prior_measured_ic']})")
    print(f"    BINDING CONSTRAINT NOW: {b['binding_constraint']} -- "
          f"{b['pooled_common_days']} common days against "
          f"{b['days_needed_at_prior_ic_unadjusted']} needed to resolve the prior IC unadjusted")
    print(f"  family charged {report['family_size_primary']} primary / "
          f"{report['family_size_full']} full at alpha {DEFAULT_ALPHA}; powered cells "
          f"{report['powered_cells_unadjusted']} unadjusted / "
          f"{report['power_counts_at_full_charge']['powered']} at the full charge")
    for v, c in sorted(report["tally"].items(), key=lambda kv: -kv[1]):
        print(f"  {v:<24} {c}")
    if report["survivors"]:
        print(f"  SURVIVORS ({len(report['survivors'])}) -- pooled, powered, both charges:")
        for s in report["survivors"]:
            print(f"    {s['construction']}->{s['target']} IC={s['ic']} "
                  f"(needed {s['ic_needed_full_family']} at the full charge)")
    else:
        print("  NO SURVIVORS -- an expected and publishable outcome"
              + (f" ({report['interesting_but_failed_multiplicity']} cell(s) cleared the harness "
                 "and were removed by the multiplicity charge)"
                 if report["interesting_but_failed_multiplicity"] else ""))
    if report["graveyard"]:
        print(f"  GRAVEYARD-GRADE NEGATIVES ({len(report['graveyard'])}) -- each with its reason "
              "and detection floor")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
