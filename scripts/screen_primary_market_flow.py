#!/usr/bin/env python3
# INTENDED CADENCE (NOT wired here -- ops/crontab.manifest is owned by another agent this wave, so
# this comment is the request, not the installation):
#
#     17 0 * * *  cd /opt/quant && python3 scripts/screen_primary_market_flow.py
#
# DAILY, seventeen minutes after the collector's 23:41 run, so each screen reads a ledger that
# already contains the trading day that just closed. Daily is the data's own cadence -- ETF flow
# publishes once per trading day -- so a second run buys nothing but a duplicate artifact. The
# screen is read-only over data/primary_market_flow.jsonl and writes exactly one file; on a box
# with no ledger it exits 0 with a NOT-READABLE-HERE artifact, so installing the line early is
# harmless.
"""STAGE-A SCREEN: PRIMARY-MARKET CREATION FLOW -- pre-registered BEFORE any result is read.

================================================================================================
THIS DOCSTRING IS THE PRE-REGISTRATION. It was written before the screen was run against any data,
and nothing below it may be edited in response to a result. Charter section 26 clause 3: every
construction tried is logged, not only the one that printed.
================================================================================================

WHY THIS CLASS, MEASURED, NOT ASSERTED
--------------------------------------
`scripts/run_mechanism_census.py` ranks `primary_market_creation_flow` #2 of 20 economic classes
(gap score 0.364 = plausibility 0.70 x orthogonality 0.65 x feasibility 0.80 x depth deficit 1.00),
coverage NAMED-UNTESTED: FOUR named constructions, ZERO tested candidates, and no screen artifact
anywhere in this tree. Separately, `scripts/measure_cross_mechanism_corr.py` measured the desk's
44-candidate maximum-power campaign occupying 2.787 effective classes of 20 (diversity 0.139) at a
cross-mechanism N_eff of 4.08 against the ~100 independent bets a weak-edge portfolio needs. The
binding constraint is DISTINCT MECHANISMS. Another rule on the same OHLCV tape cannot move it.

1. THE ECONOMIC MECHANISM -- WHO PAYS WHOM, AND WHY THE PAYMENT PERSISTS
------------------------------------------------------------------------
Spot-ETF creations and redemptions, and on-chain stablecoin mint/burn, are NON-DISCRETIONARY
PRIMARY-MARKET FLOWS.

  THE AUTHORISED PARTICIPANT pays. When an AP creates ETF units he must deliver the underlying to
  the custodian. He does not get to decide that today's price is unattractive: the creation is a
  contractual obligation triggered by a subscription that has already happened. The purchase is
  price-INELASTIC and it must clear into whatever float exists that day.

  THE STABLECOIN DEPOSITOR pays in the same shape. A mint is fiat that has already been wired to
  the issuer; it exists as a token because someone intends to deploy it. The issuer does not choose
  the timing, and the capital does not sit as a token indefinitely.

  WHO COLLECTS. The liquidity provider who fills that inelastic demand and CARRIES THE INVENTORY
  until he can work it off. He is paid for immediacy and for the risk of holding the position
  against whatever comes next.

  WHY THE PAYMENT PERSISTS -- and this is the leg that makes the class worth a slot. The flow is
  mandated BY THE CREATION MECHANISM, not chosen on price. Publishing this screen cannot teach the
  AP to stop creating, because he is not creating out of an opinion; he is discharging an
  obligation. That is the same structural reason the desk's only confirmed edge (forced
  deleveraging) survives: a constraint cannot be updated away by learning about it.

  WHAT WOULD KILL THE STORY. If the creation is fully pre-hedged -- the AP buys spot during the
  session against the subscription and the ETF is merely the wrapper -- then by the time the flow
  is PUBLISHED the price impact has already happened, and what remains is a report about the past.
  That is the honest null, it is the more likely one, and this screen is built to be able to
  report it.

2. THE FALSIFIABLE CLAIM
------------------------
  H0 (the desk's standing prior, and what a null result CONFIRMS):
      For every pre-registered (construction x form x horizon) cell, primary-market flow observed
      at the moment it BECAME READABLE has zero forward information about the asset's return:
      |IC| < 0.03.

  H1 (what would refute H0):
      At least one CAUSAL cell shows |IC| >= 0.03 with best timing Sharpe >= 0.5, is POWERED by the
      harness's own detection floor, passes the angle-20 de-contamination gate, and clears the
      family-wise critical value at alpha = 0.05 over the pre-registered family below.

  A cell that clears H1 earns a FORWARD CLOCK and nothing else. Stage A has zero promotion
  authority; this script cannot size a position and passes no `clock=` to the harness.

3. THE ALIGNMENT RULE -- THE HAZARD OF THIS CLASS, DECLARED IN FULL
-------------------------------------------------------------------
ETF CREATION DATA IS STAMPED BY TRADE DATE AND PUBLISHED WITH A LAG. Using the trade date as if it
were knowable that day is LOOK-AHEAD, and it is the invisible kind: the series looks like a clean
daily panel and joins cleanly to a daily price.

  DECISION INSTANT   24:00Z on UTC day D -- the close of the day the number became READABLE.
  ETF SIGNAL         the flow for trade date t is placed at D = THE NEXT TRADE DATE IN THE SOURCE'S
                     OWN TABLE. A creation basket settles T+1 and the issuer table for t appears
                     during the US session of the next trading day, so it is readable by 24:00Z
                     that day. The publication calendar is DERIVED FROM THE DATA -- the set of
                     trade dates the table contains IS the US ETF trading calendar, holidays and
                     all -- so no external holiday table can drift and no hand-written business-day
                     rule can be wrong about Good Friday.
  MOST RECENT ROW    DROPPED. Its publication day has not been observed yet, so any value assumed
                     for it would be a guess about knowability -- exactly the look-ahead this rule
                     exists to prevent.
  PLACEHOLDER ROWS   DROPPED. A row whose issuer cells are all em-dashes still reports Total 0.0.
                     US market holidays and the not-yet-published current day both render that way
                     (verified live 2026-08-05). Reading the Total column writes a fabricated zero.
  CHAIN SIGNAL       the net mint/burn over UTC day d is placed at D = d + 1 day. The chain itself
                     is observable in real time, but THE DESK READS A VENDOR'S DAILY AGGREGATE, and
                     the alignment must describe the instrument actually used, not the one that
                     could exist. The extra day is charged against us.
  TARGET             the horizon-CALENDAR-DAY return whose window OPENS at the decision instant.
                     The harness applies the D -> D+1 shift itself, so the predicted window is
                     measured in calendar days FROM THE DECISION and never in rows. This matters:
                     publication days are US business days, so consecutive rows are one calendar
                     day apart on Tuesday and three on Monday, and a row-spaced target would call
                     both "h = 1".
  SAME-PERIOD REF    the horizon-day window opening at the PREVIOUS decision instant -- already
                     realised at D. The harness's de-contamination gate therefore compares the
                     signal against a return that had already happened, never a future one.

  THE LOOK-AHEAD CONTROL IS RUN ON PURPOSE. Every construction is ALSO screened under the naive
  build, with the signal placed on its own stamp as if it were knowable that day, over THE SAME
  UNDERLYING OBSERVATIONS so the only difference between the two forms is the alignment. It can
  never be a survivor. It exists so the size of the publication leak is a MEASURED number: if the
  control scores and the causal build does not, that gap IS the leak, and the artifact reports it
  as an artifact rather than quietly publishing the better one.

  RESIDUAL RISK, DECLARED BECAUSE ONE SNAPSHOT CANNOT ELIMINATE IT. The causal rule asserts that
  the row for trade date t was readable by the close of the next trading day. That is the vendor's
  documented behaviour and it matches what this desk observed live, but a single page fetch cannot
  PROVE when a historical row appeared. The collector keeps a first-seen ledger so the assumed lag
  becomes a measured one going forward; rows collected at bootstrap are marked `backfilled` and
  are NOT evidence about publication time.

4. THE EXACT CONSTRUCTIONS -- FIVE, FIXED, NAMED BEFORE ANY RESULT
------------------------------------------------------------------
    etf_creation_pressure         net ETF creation in US$ / float market cap. The denominator is
                                  the mechanism, not decoration: an inelastic buyer must source
                                  from whatever float exists that day.
    etf_creation_absorption       creation pressure MINUS the price response already observed over
                                  the trade date, both as trailing z-scores. Flow that arrived
                                  WITHOUT moving price is flow somebody absorbed, so the pressure
                                  is deferred rather than spent. The census's own named
                                  `etf_flow_price_divergence_absorption`.
    stablecoin_net_mint_pressure  day-over-day net mint/burn of USDT+USDC / circulating supply.
    stablecoin_net_mint_usdc      the same, Circle only. Issuer attribution is load-bearing:
                                  Tether pre-authorises treasury inventory minted before anyone
                                  has paid for it, so pooled supply reads inventory staging as
                                  capital arriving. Circle does not carry that inventory.
    primary_flow_composite        equal-weight sum of the trailing z-scores of the ETF and
                                  stablecoin legs. Pre-registered as a cell in its own right, NOT
                                  chosen after seeing which leg scored.

  FORMS: causal, lookahead_control -- both always reported (clause 3).
  HORIZONS: 1, 5, 20 calendar days. Adopted unchanged from `screen_exchange_netflow.py` so this
  screen cannot be accused of having searched the horizon grid.
  GRIDS: the three ETF-bearing constructions are screened on the ETF publication-day grid; the two
  stablecoin constructions on their native daily grid. Each construction is screened at its own
  cadence rather than being down-sampled to the sparsest one, because throwing away 30% of the
  chain rows to make a table look uniform would cost power that is already the binding constraint.

  BTC ONLY, AND THE REASON IS A DATA GAP, NOT A CHOICE. ETH ETF flow IS collected (510 trading
  days) and is deliberately NOT screened: `etf_creation_pressure` is defined as flow over FLOAT
  market cap, and no free keyless ETH float history was reachable from this container
  (blockchain.info is BTC-only; CoinGecko's market-cap history returns HTTP 401 beyond 365 days
  without a key). Screening ETH with a different denominator would be a DIFFERENT construction
  wearing a pre-registered name. The cells are reported NOT-BUILDABLE with that reason rather than
  omitted, and the data waits for a float source.

  ALSO COLLECTED AND DELIBERATELY OUTSIDE THE FAMILY: `stablecoin_exchange_flows`, the census's
  fourth named construction. Keyless public Ethereum RPC serves only ~128 recent blocks -- archive
  eth_call returns HTTP 403 on every public endpoint tried -- so there is no history to screen, and
  `scripts/screen_exchange_netflow.py` already owns that question on a source that has one.

5. THE MULTIPLICITY CHARGE -- alpha STAYS 0.05
----------------------------------------------
  Family = 5 constructions x 2 forms x 3 horizons = 30 pre-registered cells.

  The critical value is `libs.validation.type2_cost.critical_z(alpha=0.05, n_tests=N, two_sided)`
  -- Bonferroni, the desk's documented approximation to the Romano-Wolf max-null critical value. N
  is the LARGER of the pre-registered 30 and the number of cells actually scored: a run that reads
  less data than planned cannot buy significance by shrinking its own family. A cell must satisfy
  |IC| * sqrt(n_eff) >= z_crit ON TOP of every gate the harness already applies. alpha is never
  moved; the family only ever grows.

6. PRE-DECLARED POWER VERDICT -- COMPUTED FROM SAMPLE LENGTH ALONE, BEFORE ANY IC IS SEEN
-----------------------------------------------------------------------------------------
`stage_a_screen` calls a cell POWERED only when 1.96/sqrt(n_eff) <= ic_min = 0.03, i.e. it needs
n_eff >= 4,268 independent observations. The US spot-BTC ETF has existed since 2024-01-11, which
is ~640 trading days; the chain grid gives ~940 daily rows over the same window. At h = 1 the
detection floor is therefore ~0.08 unadjusted and ~0.13 at the family charge, and at h = 20 the
harness's overlap deflator divides n_eff by 20 again.

SO EVERY CELL IN THIS RUN IS EXPECTED TO RETURN SCREEN-UNDERPOWERED AT THE HARNESS'S OWN FLOOR,
AT EVERY HORIZON, BEFORE A SINGLE NUMBER IS COMPUTED. This is stated here, in the pre-registration,
because the alternative -- discovering it afterwards and describing the nulls as refutations -- is
the exact defect today's audit found in 78% of this desk's recorded negatives. The run happens
anyway, for three reasons that do not depend on power at 0.03:
  (a) the ICs are recorded evidence a later meta-analysis can pool, and "we never looked" is the
      defect the data-utilisation law exists to kill;
  (b) the ALIGNMENT DIAGNOSTIC -- causal versus look-ahead control -- is a statement about the
      difference between two builds on identical observations, and it can be read whatever the
      absolute power;
  (c) TIMING-ARTIFACT and SUSPECT-LOOKAHEAD remain reachable, and an artifact kill is real
      knowledge.
NOTHING UNDERPOWERED IS GRAVEYARDED. The graveyard is permanent and "could not tell" must never be
filed as "it is dead". The artifact instead reports, per cell, the |IC| that WOULD have been needed
and how many more publication days the axis needs before a null here would mean anything.

WHAT IS GRAVEYARDED, THEN -- stated here because the pre-declared verdict above makes it the whole
question. A kill is filed when ITS OWN TRIGGER is resolved by this sample, which is not always the
same test as `powered`:
    SCREEN-WEAK        needs `powered` at ic_min. It is an ABSENCE claim -- "we looked and it is
                       not there" -- and without absence power that sentence is a shrug.
    TIMING-ARTIFACT    needs the CONTAMINATION resolved: |same-period corr| must exceed the 0.20
                       de-contamination bar by more than the sampling band at this n_eff. This is
                       not an absence claim at all; it asserts that a measured correlation is
                       large, and resolving 0.37 takes a fraction of the sample that resolving an
                       IC of 0.03 does. Gating it on `powered` would suppress every artifact kill
                       this screen can make, on a daily axis where nothing is ever powered at 0.03.
    SUSPECT-LOOKAHEAD  needs the harness's `implausible_leak` flag AND |IC| exceeding the 0.35
                       credibility ceiling by more than the band.
The two gates can disagree about the same cell and that is not a contradiction: they answer
different questions. Every filed kill records which test resolved it.

THE BAR IS NEVER MOVED TO MANUFACTURE POWER. Raising ic_min would make `powered` true by declaring
that the desk only cares about larger effects; that is a different question, not a better answer,
and it is not this screen's to ask.

7. DATA, AND THE REFUSAL TO FABRICATE
-------------------------------------
Reads exactly one file, `data/primary_market_flow.jsonl`, written by
`scripts/collect_primary_market_flow.py`. There is NO generator anywhere in this import graph. When
the ledger is absent or too thin, the screen writes a NOT-READABLE-HERE / INSUFFICIENT status
artifact naming what is missing and exits 0. A survivor found on synthetic flow is a fact about the
generator, and it would enter the funnel wearing the same vocabulary as a real one.

Read-only over data/. Writes one artifact. No keys, no order paths, zero promotion authority.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.research.axis_screen import stage_a_screen  # noqa: E402
from libs.research.primary_market_flow import (  # noqa: E402
    CONSTRUCTIONS,
    FORMS,
    HORIZONS_DAYS,
    ZWIN,
    Alignment,
    align_to_publication,
    as_of_series,
    horizon_targets,
    net_mint,
    publication_day_map,
    scaled_flow,
    trailing_z,
)
from libs.validation.type2_cost import (  # noqa: E402
    DECLARED_CORRELATION_EFFECTS,
    DEFAULT_ALPHA,
    Type2Cost,
    correlation_negative,
    critical_z,
    headline,
    indeterminate,
)

SCHEMA_VERSION = "1.0.0"
MECHANISM_CLASS = "primary_market_creation_flow"
CENSUS_RANK = 2
CENSUS_GAP_SCORE = 0.364

LEDGER = ROOT / "data/primary_market_flow.jsonl"
REPORT = ROOT / "data/primary_market_flow_screen.json"

#: PRE-REGISTERED family size: 5 constructions x 2 forms x 3 horizons. The multiplicity charge is
#: never smaller than this, whatever the run actually manages to score.
PREREGISTERED_FAMILY = len(CONSTRUCTIONS) * len(FORMS) * len(HORIZONS_DAYS)

#: The harness floors, restated so the artifact records the bar it was judged against. NOT tunable
#: from the command line: a bar that can be moved at the call site is not a bar.
IC_MIN = 0.03
SHARPE_MIN = 0.5

#: Paired (signal, target) rows below which a cell is not screened at all. `axis_screen` needs >30
#: after its 20-period warmup; 60 is `screen_orderbook_state.py`'s floor and is kept so the two
#: organs mean the same thing by "too short".
MIN_PAIRED = 60

#: Series the ledger must carry before anything can be screened, with what each one is for.
REQUIRED_SERIES = {
    "etf_flow_btc": "daily spot-BTC ETF creation/redemption (the mechanism)",
    "price_btc": "BTC daily UTC closes (the target leg)",
    "float_btc": "BTC circulating supply (the denominator that makes flow a pressure)",
    "stablecoin_usdt": "Tether daily circulating supply",
    "stablecoin_usdc": "Circle daily circulating supply",
}

#: Verdicts that constitute graveyard-grade negative knowledge, each with the reason it is filed
#: under. UNDERPOWERED is deliberately absent: "could not tell" is not "it is dead".
_KILL_REASONS = {
    "SCREEN-WEAK": ("powered and below the floors: |IC| < 0.03 or best timing Sharpe < 0.5 on a "
                    "sample that could have resolved an effect at 0.03"),
    "TIMING-ARTIFACT": ("angle-20 de-contamination FAILED: |same-period corr| > 0.20 or residual "
                        "IC collapsed below half the raw IC -- the coinbase/turkey/kimchi failure "
                        "mode"),
    "SUSPECT-LOOKAHEAD": ("too strong to be credible at this horizon -- read as misalignment, "
                          "never as edge; NEVER earns a clock"),
}
_KILL_VERDICTS = tuple(_KILL_REASONS)

#: The harness's own de-contamination and lookahead rails, restated so the resolution test below
#: measures against the same numbers the verdict was produced from.
CONTAM_MAX = 0.20
IC_CEILING = 0.35


def kill_is_resolved(row: dict[str, Any]) -> tuple[bool, str]:
    """Is this kill's OWN TRIGGER resolved by this sample? (verdict-specific, and NOT `powered`.)

    WHY THIS IS NOT SIMPLY `powered`, AND WHY THE TWO CAN HONESTLY DISAGREE. `powered` asks one
    question: could the sample have resolved an IC of 0.03? That is the right question for an
    ABSENCE claim -- SCREEN-WEAK says "we looked for an effect and it is not there", and without
    power that sentence is a shrug. It is the WRONG question for an ARTIFACT claim. TIMING-ARTIFACT
    does not assert that an effect is absent; it asserts that a MEASURED same-period correlation
    exceeded 0.20. Resolving a correlation of 0.37 needs a fraction of the sample that resolving an
    IC of 0.03 does, so gating an artifact kill on `powered` would suppress a finding the data
    plainly supports -- and on a daily axis, where nothing is ever powered at 0.03, it would
    suppress EVERY artifact kill this screen can make.

    So each kill is tested against ITS OWN trigger, at the sampling band for a correlation at this
    n_eff (1.96/sqrt(n_eff)):

        SCREEN-WEAK        `powered` at ic_min. Unchanged: an absence claim needs absence power.
        TIMING-ARTIFACT    |same_period_corr| must exceed 0.20 by more than the band.
        SUSPECT-LOOKAHEAD  the harness must have flagged `implausible_leak`, and |IC| must exceed
                           the 0.35 ceiling by more than the band. The corroborated
                           exceeds-contemporaneous path is deliberately NOT filed: it is a
                           judgement about a pattern rather than a measurement against a threshold.

    Returns (resolved, the sentence explaining what was resolved). This can only ever ADD kills
    whose trigger the sample resolved; it can never create a survivor, never relax a floor, and
    never file an unresolved reading.
    """
    n_eff = row.get("n_eff")
    if not isinstance(n_eff, (int, float)) or float(n_eff) <= 0:
        return False, ""
    band = float(1.96 / np.sqrt(float(n_eff)))
    verdict = str(row.get("verdict", ""))
    if verdict == "SCREEN-WEAK":
        if bool(row.get("powered")):
            return True, (f"powered at ic_min={IC_MIN}: the sample could have resolved an effect "
                          f"worth caring about and did not find one")
        return False, ""
    if verdict == "TIMING-ARTIFACT":
        same = row.get("same_period_corr")
        if isinstance(same, (int, float)) and abs(float(same)) - CONTAM_MAX > band:
            return True, (f"contamination RESOLVED: |same-period corr| {abs(float(same)):.3f} "
                          f"exceeds the {CONTAM_MAX} de-contamination bar by more than the "
                          f"sampling band {band:.4f} at n_eff {float(n_eff):.0f}")
        return False, ""
    if verdict == "SUSPECT-LOOKAHEAD":
        ic = row.get("ic")
        if (bool(row.get("implausible_leak")) and isinstance(ic, (int, float))
                and abs(float(ic)) - IC_CEILING > band):
            return True, (f"implausibility RESOLVED: |IC| {abs(float(ic)):.3f} exceeds the "
                          f"{IC_CEILING} credibility ceiling by more than the sampling band "
                          f"{band:.4f} at n_eff {float(n_eff):.0f}")
        return False, ""
    return False, ""

_ETF_RULE = ("D = the NEXT TRADE DATE in the source's own table after the trade date t; the "
             "creation basket settles T+1 and the issuer table for t appears during the US session "
             "of that day, so it is readable by 24:00Z. The most recent trade date has no observed "
             "successor and is dropped.")
_CHAIN_RULE = ("D = d + 1 calendar day. The chain is observable in real time, but the desk reads a "
               "vendor's daily aggregate, so the alignment describes the instrument actually used "
               "and the extra day is charged against us.")

#: Which grid each construction lives on, and the publication rule that grid obeys. Named as data
#: so the artifact can never disagree with the code about how a cell was aligned.
_GRID = {
    "etf_creation_pressure": ("etf_publication_days", "etf_trade_date", _ETF_RULE),
    "etf_creation_absorption": ("etf_publication_days", "etf_trade_date", _ETF_RULE),
    "primary_flow_composite": ("etf_publication_days", "etf_trade_date", _ETF_RULE),
    "stablecoin_net_mint_pressure": ("chain_days", "utc_chain_day", _CHAIN_RULE),
    "stablecoin_net_mint_usdc": ("chain_days", "utc_chain_day", _CHAIN_RULE),
}


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def pre_registration() -> dict[str, Any]:
    """The machine-readable echo of this module's docstring, written into EVERY artifact.

    A pre-registration that lives only in prose cannot be diffed, so a later run that quietly
    screened a sixth construction would look identical to this one in the record.
    """
    return {
        "mechanism_class": MECHANISM_CLASS,
        "census_rank": CENSUS_RANK,
        "census_gap_score": CENSUS_GAP_SCORE,
        "census_coverage": "NAMED-UNTESTED (4 constructions named, 0 ever run)",
        "mechanism": (
            "Spot-ETF creations/redemptions and on-chain stablecoin mint/burn are NON-"
            "DISCRETIONARY primary-market flows. An authorised participant creating ETF units must "
            "acquire the underlying regardless of price -- the creation is a contractual "
            "obligation triggered by a subscription that already happened, so the purchase is "
            "price-inelastic and must clear into whatever float exists that day. A stablecoin mint "
            "is fiat that has already been wired and must be deployed."
        ),
        "payer": (
            "the liquidity provider who fills that inelastic demand and CARRIES THE INVENTORY "
            "until he can work it off; he is paid for immediacy and for holding the position "
            "against whatever comes next"
        ),
        "persistence": (
            "the flow is mandated BY THE CREATION MECHANISM, not chosen on price. Publishing this "
            "screen cannot teach an AP to stop creating, because he is not creating out of an "
            "opinion -- he is discharging an obligation, and a constraint cannot be updated away "
            "by learning about it."
        ),
        "what_would_kill_it": (
            "if creations are fully pre-hedged intraday, the price impact has already happened by "
            "the time the flow is PUBLISHED and what remains is a report about the past. That is "
            "the honest null, it is the more likely one, and this screen can report it."
        ),
        "falsifier": (
            "H0: every cell has |IC| < 0.03. H1 needs a CAUSAL cell with |IC| >= 0.03, best timing "
            "Sharpe >= 0.5, POWERED, angle-20 gate passed, AND |IC|*sqrt(n_eff) >= the family-wise "
            "critical value at alpha 0.05."
        ),
        "constructions": dict(CONSTRUCTIONS),
        "forms": list(FORMS),
        "primary_form": "causal",
        "horizons_calendar_days": list(HORIZONS_DAYS),
        "grids": {k: {"grid": v[0], "stamp_kind": v[1], "publication_rule": v[2]}
                  for k, v in _GRID.items()},
        "family_preregistered": PREREGISTERED_FAMILY,
        "alpha": DEFAULT_ALPHA,
        "multiplicity": (
            "Bonferroni critical_z over N = max(preregistered family, cells scored). Shrinking the "
            "run cannot shrink the charge; alpha never moves."
        ),
        "ic_min": IC_MIN,
        "sharpe_min": SHARPE_MIN,
        "zwin": ZWIN,
        "alignment": {
            "hazard": (
                "ETF creation data is stamped by TRADE DATE and published with a lag. Using the "
                "trade date as if it were knowable that day is LOOK-AHEAD, and it is the invisible "
                "kind: the series looks like a clean daily panel and joins cleanly to a daily "
                "price. UNSTATED ALIGNMENT VOIDS THE SCREEN."
            ),
            "decision_instant": "24:00Z on UTC day D -- the close of the day the number became "
                                "READABLE",
            "etf_publication_rule": _ETF_RULE,
            "chain_publication_rule": _CHAIN_RULE,
            "target": ("the horizon-CALENDAR-DAY return whose window OPENS at the decision "
                       "instant; the harness applies the D -> D+1 shift itself, so the predicted "
                       "window is measured in calendar days from the decision and never in rows"),
            "same_period_reference": ("the horizon-day window opening at the PREVIOUS decision "
                                      "instant -- already realised at D, never future"),
            "placeholder_policy": ("a row whose issuer cells are all em-dashes still reports Total "
                                   "0.0; US holidays and the not-yet-published current day both "
                                   "render that way, and reading the Total writes a fabricated "
                                   "zero"),
            "control": ("every construction is ALSO screened under the naive stamp-as-knowable "
                        "build, over THE SAME UNDERLYING OBSERVATIONS so the only difference is "
                        "the alignment. It can never survive; it exists so the leak is measured."),
            "residual_risk": ("one page fetch cannot prove when a historical row appeared. The "
                              "collector's first-seen ledger turns the assumed lag into a measured "
                              "one going forward; bootstrap rows are marked `backfilled` and are "
                              "NOT evidence about publication time."),
        },
        "predeclared_power_verdict": (
            "stage_a_screen calls a cell POWERED only when 1.96/sqrt(n_eff) <= ic_min = 0.03, i.e. "
            "n_eff >= 4268. The US spot-BTC ETF has existed since 2024-01-11 (~640 trading days) "
            "and the chain grid gives ~940 daily rows, so EVERY CELL IS EXPECTED TO RETURN "
            "SCREEN-UNDERPOWERED AT THE HARNESS'S OWN FLOOR BEFORE ANY NUMBER IS COMPUTED. Stated "
            "here rather than discovered afterwards, because describing those nulls as refutations "
            "is the exact defect found in 78% of this desk's recorded negatives. Nothing "
            "underpowered is graveyarded."
        ),
        "graveyard_rule": (
            "a kill is filed when ITS OWN TRIGGER is resolved by the sample, which is not always "
            "the `powered` test. SCREEN-WEAK is an ABSENCE claim and needs `powered` at ic_min. "
            "TIMING-ARTIFACT asserts a MEASURED same-period correlation exceeds 0.20 and is filed "
            "when that excess clears the sampling band at this n_eff -- resolving 0.37 takes a "
            "fraction of the sample that resolving an IC of 0.03 does, and gating it on `powered` "
            "would suppress every artifact kill this screen can make on a daily axis. "
            "SUSPECT-LOOKAHEAD needs `implausible_leak` and |IC| clearing the 0.35 ceiling by more "
            "than the band. The two gates can disagree about one cell without contradiction; every "
            "filed kill records which test resolved it."
        ),
        "not_screened": {
            "eth_etf_flow": ("collected (510 trading days) but NOT screened: etf_creation_pressure "
                             "is defined over FLOAT market cap and no free keyless ETH float "
                             "history was reachable here (blockchain.info is BTC-only; CoinGecko "
                             "market-cap history is HTTP 401 beyond 365 days without a key). "
                             "Screening it with a different denominator would be a different "
                             "construction wearing a pre-registered name."),
            "stablecoin_exchange_flows": ("the census's fourth named construction. Keyless public "
                                          "Ethereum RPC serves only ~128 recent blocks (archive "
                                          "eth_call = HTTP 403 on every endpoint tried), so there "
                                          "is no history to screen; screen_exchange_netflow.py "
                                          "already owns the question on a source that has one."),
        },
        "authority": "NONE -- Stage A. No promotion, no sizing, no forward-clock file written.",
        "no_synthetic_fallback": (
            "no generator exists in this import graph: an unreadable or thin ledger yields a "
            "status artifact, never a fabricated row"
        ),
    }


# ----------------------------------------------------------------------------------- ledger read

def load_ledger(path: Path) -> tuple[dict[str, dict[date, float]], dict[str, Any]]:
    """{series: {stamp -> value}} plus the ledger's own provenance summary.

    LAST WRITE WINS PER (series, stamp). The ledger is append-only and the collector only appends
    stamps it has never seen, so a duplicate can only come from a manual re-run against a truncated
    file; taking the later line is the only rule that cannot silently resurrect a stale value.
    """
    series: dict[str, dict[date, float]] = {}
    meta: dict[str, Any] = {"observation_rows": 0, "run_rows": 0, "unparseable_lines": 0,
                            "backfilled_rows": 0, "measured_rows": 0, "runs": []}
    if not path.exists():
        return series, meta
    for line in path.read_text("utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            meta["unparseable_lines"] += 1
            continue
        if not isinstance(rec, dict):
            meta["unparseable_lines"] += 1
            continue
        if rec.get("kind") == "run":
            meta["run_rows"] += 1
            meta["runs"].append({"run_utc": rec.get("run_utc"),
                                 "sources_ok": sum(1 for s in rec.get("sources", [])
                                                   if isinstance(s, dict) and s.get("status")
                                                   == "OK"),
                                 "sources": [{"source": s.get("source"), "status": s.get("status"),
                                              "reason": s.get("reason")}
                                             for s in rec.get("sources", [])
                                             if isinstance(s, dict)]})
            continue
        if rec.get("kind") != "observation":
            continue
        try:
            stamp = date.fromisoformat(str(rec["stamp"]))
            value = float(rec["value"])
        except (KeyError, TypeError, ValueError):
            meta["unparseable_lines"] += 1
            continue
        if not np.isfinite(value):
            continue
        series.setdefault(str(rec.get("series")), {})[stamp] = value
        meta["observation_rows"] += 1
        if rec.get("backfilled"):
            meta["backfilled_rows"] += 1
        else:
            meta["measured_rows"] += 1
    return series, meta


# --------------------------------------------------------------------------- signal construction

def _daily_return(closes: dict[date, float], day: date) -> float:
    """The return realised OVER UTC day `day`. Both closes are at or before `day`, so causal."""
    p1 = closes.get(day)
    p0 = closes.get(day - timedelta(days=1))
    if p0 is None or p1 is None or p0 <= 0.0:
        return float("nan")
    return p1 / p0 - 1.0


def _finite_map(stamps: list[date], values: np.ndarray) -> dict[date, float]:
    return {d: float(v) for d, v in zip(stamps, values, strict=True) if np.isfinite(v)}


def etf_signals(series: dict[str, dict[date, float]]) -> dict[str, dict[date, float]]:
    """The two ETF constructions, keyed by TRADE DATE (the source stamp, not yet aligned).

    Both are built here rather than at the call site so the causal and control forms are guaranteed
    to be the SAME NUMBERS differing only in which day they are placed on -- which is the entire
    point of running the control.
    """
    flow_by_day = series.get("etf_flow_btc", {})
    closes = series.get("price_btc", {})
    floats = series.get("float_btc", {})
    stamps = sorted(flow_by_day)
    if not stamps:
        return {}
    flow = np.array([flow_by_day[d] for d in stamps], dtype="float64")
    # `as_of` for both denominators: the float chart lags a day or two and the price series can
    # miss a candle. A denominator carried forward a bounded number of days is causal; one carried
    # forever would let a dead feed look like a flat signal.
    fl = as_of_series(floats, stamps, max_staleness_days=10)
    px = as_of_series(closes, stamps, max_staleness_days=5)
    pressure = scaled_flow(flow, fl, px)
    trade_ret = np.array([_daily_return(closes, d) for d in stamps], dtype="float64")
    # ABSORPTION: flow that arrived without moving price. Both legs are trailing z-scores computed
    # on strictly prior observations, so the difference is computable at the trade-date close and
    # is knowable well before the publication day it will be placed on.
    absorption = trailing_z(pressure, win=ZWIN) - trailing_z(trade_ret, win=ZWIN)
    return {
        "etf_creation_pressure": _finite_map(stamps, pressure),
        "etf_creation_absorption": _finite_map(stamps, absorption),
    }


def stablecoin_signals(series: dict[str, dict[date, float]]) -> dict[str, dict[date, float]]:
    """The two stablecoin constructions, keyed by UTC CHAIN DAY (the source stamp)."""
    usdt = series.get("stablecoin_usdt", {})
    usdc = series.get("stablecoin_usdc", {})
    out: dict[str, dict[date, float]] = {}

    days_c = sorted(usdc)
    if len(days_c) >= 2:
        out["stablecoin_net_mint_usdc"] = _finite_map(
            days_c, net_mint(np.array([usdc[d] for d in days_c], dtype="float64")))

    both = sorted(set(usdt) & set(usdc))
    if len(both) >= 2:
        total = np.array([usdt[d] + usdc[d] for d in both], dtype="float64")
        out["stablecoin_net_mint_pressure"] = _finite_map(both, net_mint(total))
    return out


def composite_signal(etf_pressure: dict[date, float], chain_pressure: dict[date, float],
                     grid: list[date]) -> dict[date, float]:
    """Equal-weight sum of the two legs' trailing z-scores, on the ETF grid.

    The chain leg is taken AS OF each ETF decision day -- the most recent chain value already
    published -- because the two families do not share a calendar and the only causal join is
    "what did the desk already know". Both legs are z-scored on the grid they are screened on, so
    the composite is a sum of comparable quantities rather than of a ratio and a fraction.
    """
    if not grid:
        return {}
    etf = np.array([etf_pressure.get(d, np.nan) for d in grid], dtype="float64")
    chain = as_of_series(chain_pressure, grid, max_staleness_days=7)
    return _finite_map(grid, trailing_z(etf, win=ZWIN) + trailing_z(chain, win=ZWIN))


def placements(stamped: dict[date, float], pub_map: dict[date, date],
               form: str) -> dict[date, float]:
    """Place a stamped series on decision days under one of the two pre-registered forms.

    BOTH FORMS ARE RESTRICTED TO THE SAME UNDERLYING STAMPS -- the ones `pub_map` covers. Without
    that restriction the control would also carry the most recent stamp, which the causal build
    must drop, and the two forms would differ by one observation as well as by their alignment.
    The comparison is only a leak measurement if the alignment is the ONLY difference.
    """
    usable = {d: v for d, v in stamped.items() if d in pub_map}
    if form == "causal":
        return align_to_publication(usable, pub_map)
    return usable


def screen_cell(name: str, signal_by_day: dict[date, float], closes: dict[date, float], *,
                alignment: Alignment) -> dict[str, Any]:
    """One pre-registered cell. EVERY cell produces a row, including ones that could not be run.

    A construction that silently vanishes from the record is indistinguishable from one that was
    never tried, and that difference is exactly what clause 3 exists to preserve.
    """
    base: dict[str, Any] = {"name": name, "alignment": alignment.as_dict()}
    days = sorted(signal_by_day)
    if len(days) < MIN_PAIRED:
        return {**base, "n_paired": len(days), "verdict": "TOO-FEW-ROWS",
                "why": (f"{len(days)} decision days against a floor of {MIN_PAIRED} -- an IC here "
                        "would describe coincidence"),
                "type2": indeterminate(name, "fewer decision days than the screen's own floor",
                                       source="scripts/screen_primary_market_flow.py",
                                       effect_unit="ic").as_dict()}
    sig = np.array([signal_by_day[d] for d in days], dtype="float64")
    tgt = horizon_targets(days, closes, horizon=alignment.horizon)
    ok = np.isfinite(sig) & np.isfinite(tgt)
    n_ok = int(ok.sum())
    base["n_rows"] = len(days)
    base["n_paired"] = n_ok
    base["span"] = [days[0].isoformat(), days[-1].isoformat()]
    base["target_missing"] = len(days) - n_ok
    if n_ok < MIN_PAIRED:
        return {**base, "verdict": "TOO-FEW-ROWS",
                "why": (f"{n_ok} paired (signal, target) rows against a floor of {MIN_PAIRED} "
                        "after dropping rows whose target window has no close at one end"),
                "type2": indeterminate(name, "fewer paired rows than the screen's own floor",
                                       source="scripts/screen_primary_market_flow.py",
                                       effect_unit="ic").as_dict()}
    res = stage_a_screen(sig[ok], tgt[ok], name=name, zwin=ZWIN,
                         ic_min=IC_MIN, sharpe_min=SHARPE_MIN,
                         horizon_days=alignment.horizon_days)
    return {**base, **{k: v for k, v in res.items() if k != "name"}}


def build_rows(series: dict[str, dict[date, float]]) -> list[dict[str, Any]]:
    """Every pre-registered (construction x form x horizon) cell, in a fixed order."""
    closes = series.get("price_btc", {})
    etf = etf_signals(series)
    chain = stablecoin_signals(series)
    etf_pub = publication_day_map(series.get("etf_flow_btc", {}))
    # The chain publication rule is deterministic (d -> d+1), so every chain stamp has a decision
    # day and none is dropped -- unlike the ETF rule, whose last stamp has no observed successor.
    chain_days = sorted({d for sig in chain.values() for d in sig})
    chain_pub = {d: d + timedelta(days=1) for d in chain_days}

    rows: list[dict[str, Any]] = []
    for cname in CONSTRUCTIONS:
        grid_name, stamp_kind, rule = _GRID[cname]
        for form in FORMS:
            if cname in etf:
                placed = placements(etf[cname], etf_pub, form)
            elif cname in chain:
                placed = placements(chain[cname], chain_pub, form)
            elif cname == "primary_flow_composite":
                etf_leg = placements(etf.get("etf_creation_pressure", {}), etf_pub, form)
                chain_leg = placements(chain.get("stablecoin_net_mint_pressure", {}),
                                       chain_pub, form)
                placed = composite_signal(etf_leg, chain_leg, sorted(etf_leg))
            else:
                placed = {}
            for h in HORIZONS_DAYS:
                al = Alignment(form=form, horizon=h, stamp_kind=stamp_kind, publication_rule=rule)
                cell = f"{cname}|{form}|h{h}d"
                if not placed:
                    rows.append({
                        "name": cell, "construction": cname, "form": form, "horizon_days": h,
                        "grid": grid_name, "alignment": al.as_dict(), "verdict": "NOT-BUILDABLE",
                        "why": ("the ledger does not carry the series this construction needs; "
                                "reported rather than omitted so a missing input is visible as a "
                                "hole and never as a quiet pass"),
                        "type2": indeterminate(
                            cell, "construction could not be built from the ledger",
                            source="scripts/screen_primary_market_flow.py",
                            effect_unit="ic").as_dict()})
                    continue
                res = screen_cell(cell, placed, closes, alignment=al)
                rows.append({**res, "construction": cname, "form": form, "horizon_days": h,
                             "grid": grid_name})
    return rows


# ------------------------------------------------------------------------- statistics and power

def _significance(rows: list[dict[str, Any]], *, n_family: int) -> None:
    """Attach the family-wise bar to every scored row, in place.

    Bonferroni over N -- the desk's documented approximation to the Romano-Wolf max-null critical
    value. Applied ON TOP of every gate the harness already ran, so it can only remove candidates.
    """
    z_crit = critical_z(DEFAULT_ALPHA, n_family, two_sided=True)
    for r in rows:
        n_eff, ic = r.get("n_eff"), r.get("ic")
        if not isinstance(n_eff, (int, float)) or not isinstance(ic, (int, float)):
            continue
        if not np.isfinite(float(n_eff)) or not np.isfinite(float(ic)) or float(n_eff) <= 0:
            continue
        need = float(z_crit) / float(np.sqrt(float(n_eff)))
        r["family_size"] = int(n_family)
        r["family_z_critical"] = round(float(z_crit), 4)
        r["ic_needed_family_wise"] = round(need, 4)
        r["clears_family_wise"] = bool(abs(float(ic)) >= need)
        # HOW FAR THE SAMPLE IS FROM MEANING ANYTHING, in the units a collector can add: ROWS.
        # A null without this is a shrug; with it, it is a schedule. TWO NUMBERS, because the two
        # bars answer different questions and quoting one under the other's name is how a floor
        # gets silently misread:
        #   ..._harness_powered   what it takes for `powered` to flip -- the UNADJUSTED (N=1)
        #                         test the harness's SCREEN-WEAK / SCREEN-UNDERPOWERED split
        #                         encodes, i.e. when a null here becomes graveyard-grade.
        #   ..._family_wise       what it takes for a FIND at ic_min to clear the multiplicity
        #                         charge. Always the larger of the two, and the reason a cell can
        #                         be powered to refute long before it is powered to discover.
        # Both are scaled by horizon_days because overlapping targets sampled daily buy fractional
        # independent observations, exactly as the harness's own deflator assumes.
        h = float(r.get("horizon_days", 1.0))
        r["rows_needed_for_harness_powered"] = int(np.ceil((1.96 / IC_MIN) ** 2 * h))
        r["rows_needed_for_family_wise_at_ic_min"] = int(np.ceil((float(z_crit) / IC_MIN) ** 2 * h))


def _type2(rows: list[dict[str, Any]], *,
           n_family: int) -> list[tuple[dict[str, Any], Type2Cost]]:
    """Attach the Type-II reading to every scored row, in place; return (row, cost) pairs.

    A zero without a power figure is unfalsifiable: it cannot be told apart from "we could not have
    seen anything even if it were there", and those two statements retire opposite things -- a
    hypothesis class in the first case, an INSTRUMENT in the second. 78% of this desk's recorded
    negatives carry no such figure; none of these will.
    """
    costs: list[tuple[dict[str, Any], Type2Cost]] = []
    for r in rows:
        n = r.get("n")
        if not isinstance(n, (int, float)) or float(n) <= 0:
            continue
        cost = correlation_negative(
            str(r.get("name")),
            n_obs=float(n),
            source="scripts/screen_primary_market_flow.py",
            # Rows are sampled once per decision day while the target spans `horizon_days` calendar
            # days, so overlapping targets are deflated exactly as the harness deflates them. The
            # two must never disagree about whether a cell was powered.
            horizon_periods=float(r.get("horizon_days", 1.0)),
            panel_width=1,
            n_tests=n_family,
            alpha=DEFAULT_ALPHA,
            effect_unit="ic",
            note=("TWO FLOORS ARE REPORTED AND THEY ANSWER DIFFERENT QUESTIONS: the harness's "
                  "min_detectable_ic is the UNADJUSTED (N=1) floor its SCREEN-WEAK / "
                  "SCREEN-UNDERPOWERED split already encodes, while min_detectable_effect here is "
                  "the floor at the FAMILY-WISE charge -- the bar a FIND had to clear. A cell can "
                  "be powered against the first and not the second; that is the price of 30 "
                  "cells, not a contradiction. Serial correlation in flow is NOT deflated beyond "
                  "the horizon overlap, so this figure is an upper bound on power."),
        )
        r["type2"] = cost.as_dict()
        r["type2_label"] = cost.label
        costs.append((r, cost))
    return costs


def alignment_diagnostics(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """CAUSAL vs LOOK-AHEAD CONTROL, per (construction, horizon). THE POINT OF THIS SCREEN.

    Reported for every pair regardless of power, and deliberately NOT in the graveyard: this is a
    statement about the DIFFERENCE between two builds over identical observations, not a claim that
    an effect is absent. The sampling band for a correlation difference at this n_eff is carried
    alongside, so an unresolved gap reads as an unresolved gap rather than as a leak.

    A resolved gap in favour of the control is the finding the class was most at risk of: it means
    the apparent edge lived entirely in pretending the trade date was knowable that day.
    """
    idx = {(r.get("construction"), r.get("horizon_days"), r.get("form")): r for r in rows}
    out: list[dict[str, Any]] = []
    for (cname, h, form), causal in sorted(idx.items(), key=lambda kv: str(kv[0])):
        if form != "causal":
            continue
        control = idx.get((cname, h, "lookahead_control"))
        ic_c, ic_l = causal.get("ic"), (control or {}).get("ic")
        if not isinstance(ic_c, (int, float)) or not isinstance(ic_l, (int, float)):
            continue
        n_eff = float(causal.get("n_eff") or 0.0)
        band = float(1.96 * np.sqrt(2.0 / n_eff)) if n_eff > 0 else float("inf")
        gap = abs(float(ic_l)) - abs(float(ic_c))
        same_c = causal.get("same_period_corr")
        same_l = (control or {}).get("same_period_corr")
        # THE MAGNITUDE GAP IS NOT THE ONLY EVIDENCE, AND ON A SHORT SAMPLE IT IS THE WEAKEST.
        # Two sharper fingerprints are reported alongside it, because a leak can be plain in them
        # while the |IC| difference sits inside a band that ~600 rows cannot resolve:
        #   CONTAMINATION -- the naive build's signal sits on a day whose return has already
        #     happened, so its same-period correlation jumps. That is a directly measured quantity
        #     with its own, much easier, resolution bar.
        #   SIGN FLIP -- if the two alignments disagree about the DIRECTION of the relationship,
        #     they are not measuring the same thing at different strengths; at most one of them is
        #     measuring the mechanism at all.
        # `leak_resolved` keeps its pre-registered definition (the magnitude gap against the band);
        # these are additional readings, never a re-definition of it.
        flip = (isinstance(ic_c, (int, float)) and isinstance(ic_l, (int, float))
                and float(ic_c) * float(ic_l) < 0.0)
        contam_jump = (abs(float(same_l)) - abs(float(same_c))
                       if isinstance(same_l, (int, float)) and isinstance(same_c, (int, float))
                       else None)
        out.append({
            "construction": cname, "horizon_days": h,
            "ic_causal": ic_c, "ic_lookahead_control": ic_l,
            "control_minus_causal": round(gap, 4),
            "noise_band_at_n_eff": round(band, 4),
            "leak_resolved": bool(gap > band),
            "same_period_corr_causal": same_c,
            "same_period_corr_control": same_l,
            "contamination_jump": round(contam_jump, 4) if contam_jump is not None else None,
            "control_failed_decontam": (control or {}).get("decontam_passed") is False,
            "causal_failed_decontam": causal.get("decontam_passed") is False,
            "sign_flip": flip,
            "reading": ("the control BEATS the causal build by more than sampling noise: the "
                        "apparent edge lives in treating the trade date as knowable that day, "
                        "which it was not. ARTIFACT, not edge." if gap > band else
                        "the causal/control gap is inside the sampling band at this n_eff -- no "
                        "publication leak is resolved on MAGNITUDE; read contamination_jump and "
                        "sign_flip, which resolve on far smaller samples"),
        })
    return out


def classify(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(survivors, graveyard rows). CONSERVATIVE ON BOTH SIDES.

    A SURVIVOR must be the CAUSAL form, must have earned SCREEN-INTERESTING from the audited
    harness, must be POWERED by the harness's own detection floor, and must clear the family-wise
    critical value. The look-ahead control is never a survivor of this screen -- it is the leak
    measurement -- so a construction that scores only under the naive alignment is recorded as a
    kill, with the diagnosis rather than a generic label.

    A GRAVEYARD ROW is a POWERED negative or an artifact verdict, WITH its reason and its detection
    floor. UNDERPOWERED cells are excluded on purpose: the graveyard is permanent and "could not
    tell" must never be filed as "it is dead".
    """
    idx = {(r.get("construction"), r.get("horizon_days"), r.get("form")): r for r in rows}
    survivors: list[dict[str, Any]] = []
    graveyard: list[dict[str, Any]] = []
    for r in rows:
        verdict = str(r.get("verdict", ""))
        form = str(r.get("form", ""))
        key = (r.get("construction"), r.get("horizon_days"))
        twin = idx.get((*key, "lookahead_control" if form == "causal" else "causal"))
        if form == "causal" and verdict == "SCREEN-INTERESTING" \
                and bool(r.get("powered")) and bool(r.get("clears_family_wise")):
            survivors.append({
                "construction": r.get("construction"), "horizon_days": r.get("horizon_days"),
                "ic": r.get("ic"), "n": r.get("n"), "n_eff": r.get("n_eff"),
                "ic_needed_family_wise": r.get("ic_needed_family_wise"),
                "control_twin_ic": (twin or {}).get("ic"),
                "same_period_corr": r.get("same_period_corr"),
                "earns": ("a pre-registered FORWARD CLOCK and nothing else -- this script does not "
                          "write one; consuming one of twelve Holm-corrected forward slots is a "
                          "principal-visible act"),
            })
            continue
        floor = ((r.get("type2") or {}).get("min_detectable_effect")
                 if isinstance(r.get("type2"), dict) else None)
        # LOOKAHEAD-ONLY IS CHECKED FIRST, and the ordering is the point. A causal cell whose
        # control twin scored would otherwise land on the generic SCREEN-WEAK row, which records
        # THAT it died without recording WHY -- and "why" is the entire finding for this class: the
        # forecast was a number that had not been published yet. It still requires `powered`, so an
        # underpowered causal cell never gets to claim the control was a leak.
        lookahead_only = (
            form == "causal" and verdict == "SCREEN-WEAK" and bool(r.get("powered"))
            and twin is not None and str(twin.get("verdict")) == "SCREEN-INTERESTING"
        )
        base = {
            "construction": r.get("construction"), "horizon_days": r.get("horizon_days"),
            "form": r.get("form"), "ic": r.get("ic"), "n": r.get("n"), "n_eff": r.get("n_eff"),
            # BOTH floors, because a kill without one is unfalsifiable and a kill quoting only the
            # family-wise one understates what the sample could actually see.
            "detection_floor_ic_unadjusted": r.get("min_detectable_ic"),
            "detection_floor_ic_family_wise": floor,
            "type2_label": r.get("type2_label"),
        }
        if lookahead_only and twin is not None:
            graveyard.append({
                **base, "form": "causal-vs-control", "verdict": "PUBLICATION-LAG-ARTIFACT",
                "control_ic": twin.get("ic"),
                "resolved_by": "powered at ic_min on the causal twin",
                "reason": ("the naive trade-date build scored and the publication-aligned build "
                           "did not: the apparent forecast used a number that had not been "
                           "published at the decision instant. This is the class's pre-registered "
                           "alignment null, confirmed."),
            })
            continue
        if verdict not in _KILL_VERDICTS:
            continue
        resolved, how = kill_is_resolved(r)
        if resolved:
            graveyard.append({
                **base, "verdict": verdict,
                "same_period_corr": r.get("same_period_corr"),
                "residual_ic": r.get("residual_ic"),
                "resolved_by": how,
                "reason": _KILL_REASONS[verdict],
            })
    return survivors, graveyard


# ------------------------------------------------------------------------------------- artifacts

def _status_artifact(status: str, why: str, missing: list[str],
                     meta: dict[str, Any]) -> dict[str, Any]:
    """THE HONEST EMPTY RESULT. Not a failure, not a zero, and above all not a simulation.

    `mechanism_census.py` already distinguishes NOT-READABLE-HERE from UNTESTED for exactly this
    reason: a runtime-only artifact absent from a checkout must never be counted as evidence of
    absence. The same word is used here so the census can read this artifact untranslated.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_utc": datetime.now(tz=UTC).isoformat(),
        "script": "scripts/screen_primary_market_flow.py",
        "status": status,
        "stage": "A (zero promotion authority)",
        "mechanism_class": MECHANISM_CLASS,
        "missing": missing,
        "why": why,
        "written_by": "scripts/collect_primary_market_flow.py",
        "refusal": ("no synthetic flow is generated and no result is reported. A survivor found on "
                    "generated flow is a fact about the generator, and it would enter the funnel "
                    "wearing the same vocabulary as a real one."),
        "pre_registration": pre_registration(),
        "ledger": meta,
        "rows": [], "survivors": [], "graveyard": [], "alignment_diagnostics": [], "tally": {},
        "authority": "NONE -- Stage A.",
    }


def _resolvability(causal_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """The run's own answer to "so what would it take", taken from its best-powered causal cell.

    A screen that reports thirty underpowered nulls and stops has told the desk nothing it can act
    on. The actionable content of an underpowered null is the SCHEDULE: how many more decision days
    the axis needs before a null here would refute anything, and how many before a find could clear
    the multiplicity charge. Both are arithmetic, both follow from the pre-declared power verdict,
    and neither depends on any IC this run happened to observe.
    """
    ranked = [r for r in causal_rows
              if isinstance(r.get("n"), (int, float))
              and isinstance(r.get("rows_needed_for_harness_powered"), int)]
    if not ranked:
        return {"status": "no scored causal cell"}
    best = min(ranked, key=lambda r: float(r.get("min_detectable_ic") or 1e9))
    have = int(float(best["n"]))
    need_refute = int(best["rows_needed_for_harness_powered"])
    need_find = int(best["rows_needed_for_family_wise_at_ic_min"])
    return {
        "best_cell": best.get("name"),
        "rows_available": have,
        "detection_floor_now_unadjusted": best.get("min_detectable_ic"),
        "detection_floor_now_family_wise": best.get("ic_needed_family_wise"),
        "rows_needed_to_refute_at_ic_min": need_refute,
        "rows_needed_to_find_at_ic_min": need_find,
        "shortfall_to_refute": max(0, need_refute - have),
        "reading": (
            "THIS IS NOT A REFUTATION AND MUST NEVER BE RECORDED AS ONE. At this sample the screen "
            "can only resolve effects at the floor above; anything smaller is invisible to it in "
            "EITHER direction. The mechanism class stays UNTESTED-BUT-INSTRUMENTED: the collector "
            "now accrues the data daily, the alignment is fixed and causal, and the arithmetic "
            "above says exactly when a null here starts to mean something. If the shortfall is "
            "larger than the desk is willing to wait, the honest conclusion is that this axis "
            "needs a HIGHER-FREQUENCY observation of the same mechanism -- intraday creation "
            "baskets, per-issuer rather than aggregate flow -- not a lower bar."
        ),
    }


def build_report(rows: list[dict[str, Any]], meta: dict[str, Any]) -> dict[str, Any]:
    scored = [r for r in rows if isinstance(r.get("ic"), (int, float))]
    n_family = max(PREREGISTERED_FAMILY, len(scored))
    _significance(scored, n_family=n_family)
    pairs = _type2(scored, n_family=n_family)
    survivors, graveyard = classify(scored)
    diagnostics = alignment_diagnostics(scored)

    surv_keys = {(s["construction"], s["horizon_days"]) for s in survivors}
    costs = [c for r, c in pairs
             if not (str(r.get("form")) == "causal"
                     and (r.get("construction"), r.get("horizon_days")) in surv_keys)]

    tally: dict[str, int] = {}
    for r in rows:
        v = str(r.get("verdict", "?"))
        tally[v] = tally.get(v, 0) + 1

    powered = sum(1 for r in scored if bool(r.get("powered")))
    desk = headline(costs) if costs else None
    causal_scored = [r for r in scored if str(r.get("form")) == "causal"]
    floors = [float(r["min_detectable_ic"]) for r in causal_scored
              if isinstance(r.get("min_detectable_ic"), (int, float))]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_utc": datetime.now(tz=UTC).isoformat(),
        "script": "scripts/screen_primary_market_flow.py",
        "status": "SCREENED",
        "stage": "A (zero promotion authority)",
        "mechanism_class": MECHANISM_CLASS,
        "pre_registration": pre_registration(),
        "ledger": meta,
        "hypotheses": len(rows), "scored": len(scored),
        "family_size_charged": n_family,
        "family_z_critical": round(float(critical_z(DEFAULT_ALPHA, n_family, two_sided=True)), 4),
        "declared_effects": list(DECLARED_CORRELATION_EFFECTS),
        # THE NULL'S CREDENTIALS, ON BOTH BASES, EACH NAMED. Reported even -- especially -- when
        # there are no survivors: it is the difference between "we looked and it is not there" and
        # "we could not have seen it".
        "powered_cells_unadjusted": powered,
        "best_detection_floor_causal": round(min(floors), 4) if floors else None,
        # WHAT IT WOULD TAKE, stated once at the top so a reader does not have to reconstruct it
        # from thirty rows. This is the difference between "the axis is dead" and "the axis cannot
        # be resolved yet, and here is the arithmetic" -- and only one of those is true here.
        "resolvability": _resolvability(causal_scored),
        "power_headline_at_family_charge": (
            desk.summary() if desk is not None else "no scored cell to power-label"),
        "power_counts_at_family_charge": {
            "negatives": desk.n_negatives if desk is not None else 0,
            "powered": desk.n_powered if desk is not None else 0,
            "underpowered": desk.n_underpowered if desk is not None else 0,
            "indeterminate": desk.n_indeterminate if desk is not None else 0,
        },
        "interesting_but_failed_multiplicity": sum(
            1 for r in scored if str(r.get("verdict")) == "SCREEN-INTERESTING"
            and not bool(r.get("clears_family_wise"))),
        "tally": tally,
        "survivors": survivors,
        "graveyard": graveyard,
        "alignment_diagnostics": diagnostics,
        "rows": rows,
        "note": (
            "ZERO SURVIVORS IS THE EXPECTED AND PUBLISHABLE OUTCOME, and at this sample size so is "
            "ZERO GRAVEYARD ROWS. What makes either one knowledge rather than silence is the power "
            "column: a POWERED-NEGATIVE cell looked and found nothing, an UNDERPOWERED cell could "
            "not have seen anything and refutes NOTHING. Only the first is graveyard-grade. "
            "`rows_needed_for_powered_at_ic_min` on each row turns the second into a schedule "
            "instead of a shrug. A survivor earns a forward clock and never a cent."
        ),
        "authority": "NONE -- Stage A. Nothing here promotes, sizes, or writes a clock file.",
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Stage-A screen: primary-market creation flow")
    ap.add_argument("--ledger", type=Path, default=LEDGER)
    ap.add_argument("--out", type=Path, default=REPORT)
    a = ap.parse_args(argv)

    ledger_path, out_path = Path(a.ledger), Path(a.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    series, meta = load_ledger(ledger_path)
    meta["path"] = _rel(ledger_path)
    meta["series_seen"] = {k: len(v) for k, v in sorted(series.items())}

    if not series:
        report = _status_artifact(
            "NOT-READABLE-HERE",
            ("the collector's append-only ledger is absent or carries no observation rows. This is "
             "EXPECTED in a fresh checkout (data/ is gitignored) and a REAL blocker on a box where "
             "the collector has never run. The screen is complete and runs unchanged the moment "
             "the ledger exists."),
            [_rel(ledger_path)], meta)
        out_path.write_text(json.dumps(report, indent=1, default=str), "utf-8")
        print(f"primary-market-flow: NOT-READABLE-HERE -- {_rel(ledger_path)}")
        print("  run scripts/collect_primary_market_flow.py first; no synthetic flow is generated")
        return 0

    missing = [f"{k} ({why})" for k, why in REQUIRED_SERIES.items() if not series.get(k)]
    if missing:
        report = _status_artifact(
            "INSUFFICIENT-SERIES",
            ("the ledger exists but does not carry every series the pre-registered family needs. "
             "The absent ones are named rather than substituted, because a construction built on a "
             "stand-in denominator is a different construction wearing a pre-registered name."),
            missing, meta)
        out_path.write_text(json.dumps(report, indent=1, default=str), "utf-8")
        print(f"primary-market-flow: INSUFFICIENT-SERIES -- {len(missing)} missing")
        for m in missing:
            print(f"    MISSING {m}")
        return 0

    report = build_report(build_rows(series), meta)
    out_path.write_text(json.dumps(report, indent=1, default=str), "utf-8")

    print(f"primary-market-flow: {report['hypotheses']} pre-registered hypotheses, "
          f"{report['scored']} scored")
    print(f"  family charged {report['family_size_charged']} at alpha {DEFAULT_ALPHA} "
          f"(z_crit {report['family_z_critical']}), powered cells "
          f"{report['powered_cells_unadjusted']} unadjusted / "
          f"{report['power_counts_at_family_charge']['powered']} at the family charge")
    print(f"  best causal detection floor |IC| >= {report['best_detection_floor_causal']} "
          f"(unadjusted); ic_min is {IC_MIN} and is NOT moved to manufacture power")
    res = report["resolvability"]
    if "rows_available" in res:
        print(f"  RESOLVABILITY  {res['best_cell']}: {res['rows_available']} rows now, "
              f"{res['rows_needed_to_refute_at_ic_min']} needed to REFUTE at ic_min "
              f"(shortfall {res['shortfall_to_refute']}), "
              f"{res['rows_needed_to_find_at_ic_min']} to FIND under the family charge")
    for v, c in sorted(report["tally"].items(), key=lambda kv: -kv[1]):
        print(f"  {v:<24} {c}")
    if report["survivors"]:
        print(f"  SURVIVORS ({len(report['survivors'])}) -- causal, powered, family-wise:")
        for s in report["survivors"]:
            print(f"    {s['construction']}@h{s['horizon_days']}d IC={s['ic']} "
                  f"(needed {s['ic_needed_family_wise']}), control twin IC {s['control_twin_ic']}")
    else:
        print("  NO SURVIVORS -- the expected outcome and a publishable one"
              + (f" ({report['interesting_but_failed_multiplicity']} cell(s) cleared the harness "
                 "and were removed by the multiplicity charge)"
                 if report["interesting_but_failed_multiplicity"] else ""))
    diags = report["alignment_diagnostics"]
    leaks = [d for d in diags if d["leak_resolved"]]
    contaminated = [d for d in diags if d["control_failed_decontam"]
                    and not d["causal_failed_decontam"]]
    print(f"  ALIGNMENT DIAGNOSTIC: {len(leaks)}/{len(diags)} pairs show a leak resolved on IC "
          f"MAGNITUDE; {len(contaminated)}/{len(diags)} show the naive build failing "
          "de-contamination where the causal build passes")
    for d in leaks:
        print(f"    LEAK {d['construction']}@h{d['horizon_days']}d "
              f"causal {d['ic_causal']} vs control {d['ic_lookahead_control']} "
              f"(band {d['noise_band_at_n_eff']})")
    for d in contaminated:
        print(f"    NAIVE-CONTAMINATED {d['construction']}@h{d['horizon_days']}d "
              f"same-period {d['same_period_corr_causal']} -> {d['same_period_corr_control']} "
              f"(jump {d['contamination_jump']:+}), sign flip {d['sign_flip']}")
    if report["graveyard"]:
        print(f"  GRAVEYARD-GRADE NEGATIVES ({len(report['graveyard'])}) -- each with its reason "
              "and detection floor")
        for g in report["graveyard"]:
            print(f"    {g['verdict']} {g['construction']}@h{g['horizon_days']}d "
                  f"[{g['form']}] IC={g['ic']} floor={g['detection_floor_ic_unadjusted']} "
                  f"-- {g['resolved_by']}")
    else:
        print("  GRAVEYARD EMPTY -- nothing here was powered enough to refute, and 'could not "
              "tell' is never filed as 'it is dead'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
