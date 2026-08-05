#!/usr/bin/env python3
# INTENDED CADENCE (NOT wired here -- ops/crontab.manifest is owned by another agent this wave, so
# this comment is the REQUEST, not the installation):
#
#     53 6 * * 1   cd /opt/quant && python3 scripts/screen_venue_subsidy.py --probe-venues
#
# WEEKLY, Monday 06:53 UTC. Weekly and not daily on purpose: the inputs are a published fee sheet
# (which changes on venue announcement, not on a market clock) and the desk's own fill tape (which
# accrues over weeks, since tier attainment is measured on a trailing 30-day volume). A daily run
# would re-publish the same refusal 365 times a year and teach the reader to stop reading it. The
# probe is what keeps the "which venues are unreachable" half of the artifact current.
"""STAGE-A SCREEN: VENUE SUBSIDY / REBATE RENT -- pre-registered BEFORE any result is read.

================================================================================================
THIS DOCSTRING IS THE PRE-REGISTRATION. It was written before the screen was run against any fill
tape, and nothing below it may be edited in response to a result. Every construction tried is
logged, not only the one that printed.
================================================================================================

WHY THIS CLASS
--------------
`data/mechanism_census.json` ranks `venue_subsidy_rent` #4 of 20 (gap score 0.340 = plausibility
0.50 x orthogonality 0.85 x feasibility 0.80 x depth deficit 1.00), coverage NAMED-UNTESTED with
ZERO tested candidates -- one named construction and nothing behind it. Its orthogonality is the
highest in the top five (0.85): a venue's payment to its liquidity providers has no reason to
correlate with any price-derived signal the desk trades, because it is not a price phenomenon at
all.

1. THE ECONOMIC MECHANISM -- WHO PAYS WHOM, AND WHY IT IS NOT AN EDGE
----------------------------------------------------------------------
THE PAYER IS THE VENUE. It pays maker rebates and fee-tier discounts to buy liquidity it cannot
otherwise attract, because a thin book loses taker flow to a deeper competitor and taker fees are
where the venue's revenue is. The payment is therefore a SUBSIDY, and what the recipient sells is a
SERVICE -- resting size, at risk of adverse selection, that would not otherwise be there.

THAT MAKES IT RENT, NOT ALPHA, AND THE DISTINCTION IS THE WHOLE POINT. There is no mispricing here
and no counterparty being outsmarted; the money is an operating expense on the venue's income
statement. Rent has a property alpha does not: it is capturable ONLY by whoever actually performs
the service at the size the tier requires. The schedule is public; reaching tier 4 is not. That is
why the census names the load-bearing missing input as "evidence the desk can reach the rebate
tier, which only its own fills can supply", and not the fee sheet.

WHY IT PERSISTS: venues compete for order flow continuously, and a venue that stops subsidising
watches its book thin out and its taker revenue follow. The subsidy is structural to the business
model, not a temporary promotion.

2. THE HONEST HAZARD -- STATED HERE BECAUSE IT IS THE REASON THIS SCREEN MOSTLY REFUSES
----------------------------------------------------------------------------------------
    A REBATE IS ONLY INCOME IF THE STRATEGY WOULD HAVE TRADED ANYWAY.

A strategy that trades TO EARN THE REBATE is churn wearing a subsidy's name. This desk has already
paid cash for that lesson: the 2026-07 fee fire burned $1,750 of commission against ~$126 of logged
round-trips (`libs/execution/economics`), and 24.2% of fills -- the taker tail -- paid 96.5% of all
fees (`scripts/fill_quality_monitor`). A GROSS rebate number computed over that same tape would
have read as a profitable liquidity-provision business right through the fire.

SO THIS SCREEN TESTS CAPTURE **NET** OF THE ROUND-TRIP COST OF THE TRADES REQUIRED TO EARN IT, OR
IT REFUSES. There is no gross-only path: `libs/research/venue_subsidy` has no function that returns
a rebate total on its own, `RebateCapture.net_usd` is None whenever the cost side is unmeasured,
and in that state the artifact's verdict is REFUSED-NET-UNTESTABLE with the missing input named.
A smaller claim is not a safer claim here -- it is the fee fire's claim.

  THE TWO COUNTERFACTUALS, and which one applies decides everything:
    INCUMBENT       the trade happened for a reason that does not reference the rebate, so the
                    round trip was going to be paid for anyway and the rebate is genuine
                    incremental income. Requires EVERY fill in the set to be individually
                    attributed; this is asserted only behind an explicit flag, never inferred.
    REBATE_SEEKING  the trade exists to earn the rebate, so its FULL round-trip cost is the cost
                    of earning it. An unattributed fill is valued here -- assuming INCUMBENT would
                    let an unattributed tape claim its whole rebate as free money.

3. R0143 IS A HARD RAIL, NOT A FOOTNOTE
----------------------------------------
Every rebate tier is a volume threshold, so the shortest path from this mechanism to a
recommendation is "trade more, or bigger, to reach tier N". That is the SIZE lever, which the
desk's own law forbids as a growth argument: geometric growth peaks at Kelly f* and falls after it,
so a desk that "maximises growth" by sizing up compounds toward zero while every individual bet
still has positive expectancy. This screen therefore NEVER reports a tier the desk has not ALREADY
reached on its own observed volume. A tier out of reach yields the verdict
NOT-EARNABLE-AT-CURRENT-SIZE, which is a KILL and is explicitly not an argument to grow into it.

4. THE EXACT CONSTRUCTIONS -- TWO, FIXED, NAMED BEFORE ANY RESULT
------------------------------------------------------------------
Both are computable ONLY from a DATED fee schedule plus the desk's OWN fills, which is the point:
there is no construction here that a public fee page alone can feed.

    rebate_rate_in_force  the maker rebate in bps in force on day t, at the tier the desk's own
                          trailing-30-day volume actually reached on that day.
    tier_headroom         log(trailing 30-day volume / the best rebate tier's threshold). How far
                          inside -- or outside -- the tier the desk is sitting. Negative means the
                          tier is not reached, which under section 3 is a kill and not a target.

  TARGET (one, fixed):
    net_execution_bps     per-day NET execution economics in bps of notional: minus the sum of the
                          venue-charged fee and the realised slippage, over the day's notional.
                          POSITIVE means the desk was PAID to trade that day. The executor's own
                          convention is "positive bps ALWAYS MEANS WE PAID", so the sign is
                          negated exactly once, at the boundary, and the direction is stated in
                          the artifact. NaN -- never 0.0 -- on any day whose commission was not
                          readable: a day whose fee could not be read is not a day of free trading.

  THE ORDER OF OPERATIONS IS ITSELF A CONTROL. The NET ACCOUNTING GATE runs FIRST. Only if it
  produces a measured net series does any IC cell run at all. An IC computed on a gross series
  would answer "does a richer rebate predict more rebate", which is a tautology, and it would print
  a number where a refusal belongs.

5. THE FALSIFIABLE CLAIM
------------------------
  H0 (the desk's standing prior, and what a null CONFIRMS): venue rebate rent is not capturable
     net -- the round-trip cost of the trades required to earn a rebate meets or exceeds the
     rebate, so net_execution_bps has no positive relationship with the rebate in force.
  H1 (what would refute H0): a pre-registered cell shows |IC| >= 0.03 with best timing Sharpe
     >= 0.5, POWERED by the harness's own detection floor, past the angle-20 de-contamination
     gate, and clear of the family-wise critical value at alpha 0.05 -- AND the window's NET
     capture is positive under the counterfactual actually attributed.

6. THE MULTIPLICITY CHARGE -- alpha STAYS 0.05
----------------------------------------------
Family = 2 constructions x 1 target x V venues, floored at the pre-registered 2. Bonferroni via
`libs.validation.type2_cost.critical_z(alpha=0.05, n_tests=N, two_sided=True)`; N is the LARGER of
the pre-registered count and the cells actually scored, so a run that reads fewer venues cannot buy
significance by shrinking its own family. alpha never moves.

7. THE ALIGNMENT RULE -- DECLARED, because unstated alignment voids the screen
-------------------------------------------------------------------------------
  GRID     one row per UTC day on which the desk traded. No day is interpolated; a day with no
           fills simply does not exist in the series.
  SIGNAL   signal[t] is read from the fee tier IN FORCE at t, at the trailing-30-day volume
           measured over (t-30d, t]. Both are in the information set at the end of day t.
  TARGET   target[t] is the net execution economics realised OVER day t. `axis_screen` performs
           the forward shift itself and pairs signal[t] with target[t+1], so the predicted window
           is day t+1 and the day the signal was observed is excluded from it.
  DATES    a fee tier is applied ONLY where its published effective window covers the fill's own
           timestamp. `FeeSchedule.tier_at` returns None -- never "the current tier" -- otherwise.
           An undated sheet applied to old fills prices history at today's rates, and the error is
           invisible in the output, so an undated sheet disqualifies the whole window instead.

8. DATA, AND WHAT IS MISSING
-----------------------------
  FEE SCHEDULES WITH EFFECTIVE DATES -- data/venue_fee_schedules.json, a declared file with
    per-tier provenance (source_url, retrieved_utc, effective_from/to). `--probe-venues` fetches
    what is keyless and records what is not. Measured from this environment: Deribit publishes
    maker/taker commission per instrument keylessly (BTC-PERPETUAL maker +0.00015, i.e. the maker
    is CHARGED 1.5 bps -- not a rebate at all at base tier), while Binance returns HTTP 451 and
    Bybit HTTP 403. And even Deribit's endpoint publishes only the CURRENT value with no effective
    date, so it cannot value a historical fill.
  THE DESK'S OWN FILLS -- data/moat/execution_tape/cashcarry_trades.jsonl (the append-only tape)
    with data/cashcarry_trades.json as the rolling fallback.
  THE FEE ACTUALLY CHARGED -- and this is the input the desk does not have. The executor's tape
    records event, symbol, notional, leg modes and per-leg slippage, but NOT the commission: that
    lives in the venue income ledger (`binance_testnet.commission_events`), behind keys, and
    data/execution_economics.json currently reads NOT-READABLE-HERE for every fee term. A rebate
    is a FEE OUTCOME, so a tape without fees cannot measure one however many fills it holds.

Any of these absent -> a status artifact naming exactly which, and NO number. Never a simulation:
a rebate capture computed on invented fills is a fact about the invention.

Read-only over data/. Writes one artifact. No keys, no order path, zero promotion authority.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.execution import leg_modes  # noqa: E402
from libs.research.axis_screen import stage_a_screen  # noqa: E402
from libs.research.venue_subsidy import (  # noqa: E402
    CONSTRUCTIONS,
    MIN_TIER_DAYS,
    NOT_READABLE,
    REFUSED,
    FeeSchedule,
    FeeTier,
    Fill,
    daily_grid,
    net_execution_bps_series,
    net_rebate_capture,
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
MECHANISM_CLASS = "venue_subsidy_rent"

SCHEDULES = ROOT / "data/venue_fee_schedules.json"
TAPE = ROOT / "data/moat/execution_tape/cashcarry_trades.jsonl"
ROLLING = ROOT / "data/cashcarry_trades.json"
REPORT = ROOT / "data/venue_subsidy_screen.json"

#: Keyless fee-exposure probes, one per venue. Recorded whether they succeed or fail: "this venue
#: does not publish its schedule without keys" is itself the finding the census asked for.
VENUE_PROBES: tuple[tuple[str, str], ...] = (
    ("deribit", "https://www.deribit.com/api/v2/public/get_instrument"
                "?instrument_name=BTC-PERPETUAL"),
    ("binance", "https://api.binance.com/api/v3/exchangeInfo?symbol=BTCUSDT"),
    ("bybit", "https://api.bybit.com/v5/market/instruments-info?category=linear&symbol=BTCUSDT"),
)

TARGET_NAME = "net_execution_bps"
PREREGISTERED_FAMILY = len(CONSTRUCTIONS) * 1

IC_MIN = 0.03
SHARPE_MIN = 0.5
MIN_DAYS = 60

_KILL_REASONS = {
    "SCREEN-WEAK": ("powered and below the floors: |IC| < 0.03 or best timing Sharpe < 0.5 on a "
                    "sample that could have resolved an effect at 0.03"),
    "TIMING-ARTIFACT": ("angle-20 de-contamination FAILED: the rebate in force and the same day's "
                        "net execution economics are the same quantity measured twice"),
    "SUSPECT-LOOKAHEAD": ("too strong to be credible at this horizon -- read as misalignment, "
                          "never as edge; NEVER earns a clock"),
}
_KILL_VERDICTS = tuple(_KILL_REASONS)


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def pre_registration() -> dict[str, Any]:
    """The machine-readable echo of this module's docstring. Written into EVERY artifact."""
    return {
        "mechanism_class": MECHANISM_CLASS,
        "census_rank": 4,
        "census_gap_score": 0.340,
        "census_coverage": "NAMED-UNTESTED (0 tested candidates)",
        "payer": ("the venue itself, paying a maker rebate or listing incentive to buy liquidity "
                  "it cannot otherwise attract, because a thin book loses taker flow -- and taker "
                  "fees are where its revenue is"),
        "what_is_sold": ("a SERVICE: resting size at risk of adverse selection that would not "
                         "otherwise be there. This is RENT, not alpha -- no mispricing and no "
                         "counterparty outsmarted; the money is an operating expense on the "
                         "venue's income statement"),
        "persistence": ("venues compete for order flow continuously; one that stops subsidising "
                        "watches its book thin and its taker revenue follow. The subsidy is "
                        "structural to the business model, not a promotion"),
        "honest_hazard": (
            "A REBATE IS ONLY INCOME IF THE STRATEGY WOULD HAVE TRADED ANYWAY. A strategy that "
            "trades TO EARN THE REBATE is churn wearing a subsidy's name -- the 2026-07 fee-fire "
            "shape this desk already burned money on ($1,750 of commission against ~$126 of "
            "logged round-trips). So capture is tested NET of the round-trip cost of the trades "
            "required to earn it, never gross; if it cannot be tested net, the screen REFUSES and "
            "reports no number at all."
        ),
        "counterfactuals": {
            "INCUMBENT": ("the trade happened for a reason that does not reference the rebate, so "
                          "the round trip was paid for anyway and the rebate is incremental "
                          "income. Requires EVERY fill to be individually attributed; asserted "
                          "only behind an explicit flag, never inferred"),
            "REBATE_SEEKING": ("the trade exists to earn the rebate, so its FULL round-trip cost "
                               "is the cost of earning it"),
            "UNATTRIBUTED": ("valued as REBATE_SEEKING -- assuming INCUMBENT would let an "
                             "unattributed tape claim its whole rebate as free money"),
        },
        "r0143": ("every rebate tier is a volume threshold, so the shortest path from this "
                  "mechanism to a recommendation is 'trade more/bigger to reach tier N'. That is "
                  "the SIZE lever and it is forbidden as a growth argument: geometric growth peaks "
                  "at Kelly f* and falls after it. A tier the desk does not already reach on its "
                  "OWN observed volume yields NOT-EARNABLE-AT-CURRENT-SIZE, which is a KILL"),
        "constructions": sorted(CONSTRUCTIONS),
        "target": TARGET_NAME,
        "target_sign": ("POSITIVE means the desk was PAID to trade that day. The executor's "
                        "convention is 'positive bps ALWAYS MEANS WE PAID', so the sign is negated "
                        "exactly once, at the boundary"),
        "order_of_operations": ("the NET ACCOUNTING GATE runs FIRST; no IC cell runs unless it "
                                "produced a measured net series. An IC on a gross series would "
                                "answer 'does a richer rebate predict more rebate' -- a tautology "
                                "printed where a refusal belongs"),
        "falsifier": ("H0: rebate rent is not capturable net -- the round-trip cost of the trades "
                      "required to earn a rebate meets or exceeds it. H1 needs |IC| >= 0.03, best "
                      "timing Sharpe >= 0.5, POWERED, angle-20 passed, family-wise critical value "
                      "cleared at alpha 0.05, AND a positive NET capture under the counterfactual "
                      "actually attributed"),
        "family_preregistered": PREREGISTERED_FAMILY,
        "alpha": DEFAULT_ALPHA,
        "multiplicity": ("Bonferroni critical_z over N = max(pre-registered family, cells scored). "
                         "Shrinking the run cannot shrink the charge; alpha never moves."),
        "ic_min": IC_MIN, "sharpe_min": SHARPE_MIN,
        "min_tier_days": MIN_TIER_DAYS,
        "alignment": {
            "grid": "one row per UTC day the desk traded; no day is interpolated",
            "signal_at": ("the fee tier in force at day t, at the trailing-30-day volume over "
                          "(t-30d, t] -- both in the information set at the end of day t"),
            "target_over": "day t",
            "forward_pairing": ("the harness shifts forward itself and pairs signal[t] with "
                                "target[t+1]; the observation day is excluded from the predicted "
                                "window"),
            "effective_dates": ("a tier is applied ONLY where its published effective window "
                                "covers the fill's own timestamp; FeeSchedule.tier_at returns None "
                                "-- never 'the current tier' -- otherwise, because an undated "
                                "sheet prices history at today's rates and the error is invisible"),
            "excludes_current_period": True,
        },
        "authority": "NONE -- Stage A. No promotion, no sizing, no forward-clock file written.",
        "no_synthetic_fallback": ("no generator is in this script's import graph: an unreadable "
                                  "input yields a status artifact, never a fabricated fill"),
    }


def probe_venues(*, enabled: bool) -> list[dict[str, Any]]:
    """Which venues publish a fee schedule without keys. A failure here is a FINDING, not an error.

    The census's own note assumes fee schedules are public. They are public as WEB PAGES; what
    matters for an automated screen is whether they are readable without credentials, and from this
    environment two of three venues are not. Recording the exact status code is what turns "we
    could not test it" into "here is what an operator must do to make it testable".
    """
    out: list[dict[str, Any]] = []
    for venue, url in VENUE_PROBES:
        if not enabled:
            out.append({"venue": venue, "url": url, "status": "NOT-PROBED",
                        "note": "run with --probe-venues"})
            continue
        rec: dict[str, Any] = {"venue": venue, "url": url,
                               "probed_utc": datetime.now(tz=UTC).isoformat()}
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "quant-platform/1.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                body = json.loads(r.read())
            blob = json.dumps(body)
            maker = None
            if isinstance(body, dict) and isinstance(body.get("result"), dict):
                m = body["result"].get("maker_commission")
                maker = float(m) if isinstance(m, (int, float)) else None
            rec.update({
                "status": "REACHABLE",
                "publishes_maker_commission": maker is not None,
                "maker_commission": maker,
                "is_rebate": (maker is not None and maker < 0.0),
                "carries_effective_date": False,
                "why_unusable_for_history": (
                    "the endpoint publishes only the CURRENT value with no effective date, so it "
                    "cannot value a historical fill; an undated rate applied to old fills prices "
                    "history at today's rates"),
                "mentions_fee": ("fee" in blob.lower()),
            })
        except urllib.error.HTTPError as e:
            rec.update({"status": f"HTTP-{e.code}", "publishes_maker_commission": False,
                        "why": "venue does not serve this endpoint to this environment"})
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as e:
            rec.update({"status": "UNREACHABLE", "publishes_maker_commission": False,
                        "why": f"{type(e).__name__}"})
        out.append(rec)
    return out


def load_schedules(path: Path) -> tuple[dict[str, FeeSchedule], list[str]]:
    """Declared fee schedules with provenance. Returns (by venue, problems).

    The file is DECLARED rather than scraped because the load-bearing field -- the effective date --
    is not served by any keyless endpoint measured here. A schedule typed from memory would be a
    fabricated input wearing a citation's name, so every tier must carry `source_url` and
    `retrieved_utc` or it is rejected with its reason.
    """
    problems: list[str] = []
    if not path.is_file():
        return {}, [f"{_rel(path)} absent -- no per-venue maker-rebate tiers with effective dates"]
    try:
        blob = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError) as e:
        return {}, [f"{_rel(path)} unreadable: {type(e).__name__}"]
    if not isinstance(blob, dict):
        return {}, [f"{_rel(path)} is not an object of venue -> tiers"]
    out: dict[str, FeeSchedule] = {}
    for venue, rows in blob.items():
        if not isinstance(rows, list):
            problems.append(f"{venue}: tiers are not a list")
            continue
        tiers: list[FeeTier] = []
        for r in rows:
            if not isinstance(r, dict):
                continue
            if not r.get("source_url") or not r.get("retrieved_utc"):
                problems.append(f"{venue}:{r.get('tier')}: missing source_url/retrieved_utc -- a "
                                "schedule without provenance is a fabricated input")
                continue
            try:
                eff_from = (datetime.fromisoformat(str(r["effective_from"]))
                            if r.get("effective_from") else None)
                eff_to = (datetime.fromisoformat(str(r["effective_to"]))
                          if r.get("effective_to") else None)
                tiers.append(FeeTier(
                    venue=str(venue), tier=str(r.get("tier", "?")),
                    maker_bps=float(r["maker_bps"]), taker_bps=float(r["taker_bps"]),
                    min_30d_volume_usd=float(r.get("min_30d_volume_usd", 0.0)),
                    effective_from=eff_from, effective_to=eff_to,
                    source_url=str(r["source_url"]), retrieved_utc=str(r["retrieved_utc"])))
            except (KeyError, TypeError, ValueError) as e:
                problems.append(f"{venue}:{r.get('tier')}: {type(e).__name__}")
        if tiers:
            out[str(venue)] = FeeSchedule(venue=str(venue), tiers=tuple(tiers))
    return out, problems


def _ts(rec: dict[str, Any]) -> datetime | None:
    for k in ("closed", "opened", "ts", "timestamp"):
        v = rec.get(k)
        if not v:
            continue
        try:
            dt = datetime.fromisoformat(str(v))
        except (TypeError, ValueError):
            continue
        return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)
    return None


def _fee(rec: dict[str, Any]) -> float | None:
    """The venue-charged fee, or None. NEVER 0.0 by default.

    Same field names `scripts/fill_quality_monitor._fee` consults, so the two organs cannot
    disagree about whether a tape carries fees. The difference is the default: that monitor is
    measuring concentration among fills it already has and can treat an absent fee as zero; a
    rebate screen cannot, because "the fee was not recorded" and "the fee was zero" are the
    difference between a refusal and a finding.
    """
    for k in ("fee", "commission", "fee_usd"):
        v = rec.get(k)
        if isinstance(v, (int, float)):
            return float(v)
    return None


def load_fills(*, venue_default: str, attribute_incumbent: bool) -> \
        tuple[list[Fill], list[str], dict[str, Any]]:
    """The desk's own fills, one Fill per LEG. Returns (fills, problems, provenance).

    ONE FILL PER LEG, not per pair: a cash-carry round trip can rest maker on spot and cross taker
    on futures, and a rebate accrues per leg. Collapsing the pair to one row would let a maker leg
    launder a taker one.
    """
    problems: list[str] = []
    prov: dict[str, Any] = {"tape": _rel(TAPE), "rolling": _rel(ROLLING)}
    recs: list[dict[str, Any]] = []
    if TAPE.is_file():
        for line in TAPE.read_text("utf-8").splitlines():
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if isinstance(r, dict):
                recs.append(r)
        prov["tape_rows"] = len(recs)
    else:
        problems.append(f"{_rel(TAPE)} absent -- the append-only own-fill tape (VPS-only; data/ "
                        "is gitignored)")
        prov["tape_rows"] = 0
    if not recs and ROLLING.is_file():
        try:
            blob = json.loads(ROLLING.read_text("utf-8"))
            recs = [r for r in blob if isinstance(r, dict)] if isinstance(blob, list) else []
            prov["rolling_rows"] = len(recs)
            problems.append(f"{_rel(ROLLING)} used as fallback -- it is a rolling log[-500:] "
                            "buffer, so any window it covers is a WINDOW and not a total")
        except (OSError, ValueError):
            problems.append(f"{_rel(ROLLING)} unreadable")
    elif not ROLLING.is_file():
        problems.append(f"{_rel(ROLLING)} absent -- the rolling fallback is not here either")

    fills: list[Fill] = []
    assumed_venue = 0
    for r in recs:
        ts = _ts(r)
        if ts is None:
            continue
        try:
            notional = float(r.get("notional", 0.0))
        except (TypeError, ValueError):
            continue
        if notional <= 0.0:
            continue
        venue = str(r.get("venue") or r.get("exchange") or "")
        if not venue:
            venue = venue_default
            assumed_venue += 1
        modes = r.get("modes") if isinstance(r.get("modes"), dict) else {}
        legs = list(modes.items()) or [("unknown", None)]
        fee = _fee(r)
        cf = "INCUMBENT" if attribute_incumbent else "UNATTRIBUTED"
        for leg, mode in legs:
            slip = r.get(f"{leg}_slip_bps")
            fills.append(Fill(
                ts=ts, venue=venue, symbol=str(r.get("symbol", "?")),
                notional_usd=notional, is_maker=bool(leg_modes.is_maker(mode)),
                fee_usd=fee, counterfactual=cf,
                slip_bps=float(slip) if isinstance(slip, (int, float)) else None))
    if assumed_venue:
        problems.append(f"{assumed_venue} fill leg(s) carry no venue field; the screen's --venue "
                        f"default ({venue_default}) was assumed and is recorded as an assumption")
    if fills and all(f.fee_usd is None for f in fills):
        problems.append("NO fill carries a venue-charged fee: the executor's tape records notional, "
                        "leg mode and slippage but not commission, which lives in the venue income "
                        "ledger (binance_testnet.commission_events) behind keys")
    return fills, problems, prov


def screen_venue(venue: str, schedule: FeeSchedule, fills: list[Fill]) -> list[dict[str, Any]]:
    """The Stage-A cells for one venue -- reached ONLY after the net accounting gate passed."""
    days = daily_grid(fills)
    target = net_execution_bps_series(fills, days)
    rows: list[dict[str, Any]] = []
    for cname, fn in sorted(CONSTRUCTIONS.items()):
        sig = np.asarray(fn(schedule, fills, days), dtype="float64")
        ok = np.isfinite(sig) & np.isfinite(target)
        name = f"{venue}|{cname}|{TARGET_NAME}"
        base: dict[str, Any] = {"venue": venue, "construction": cname, "target": TARGET_NAME,
                                "n_paired": int(ok.sum())}
        if int(ok.sum()) < MIN_DAYS:
            rows.append({**base, "verdict": "TOO-FEW-PAIRS",
                         "why": (f"{int(ok.sum())} paired trading days against a floor of "
                                 f"{MIN_DAYS} -- an IC here would describe coincidence"),
                         "type2": indeterminate(
                             name, "fewer paired trading days than the screen's own floor",
                             source="scripts/screen_venue_subsidy.py",
                             effect_unit="ic").as_dict()})
            continue
        res = stage_a_screen(sig[ok], target[ok], name=name, ic_min=IC_MIN,
                             sharpe_min=SHARPE_MIN, horizon_days=1.0)
        rows.append({**base, **{k: v for k, v in res.items() if k != "name"}})
    return rows


def _significance(rows: list[dict[str, Any]], *, n_family: int) -> None:
    z = critical_z(DEFAULT_ALPHA, max(1, n_family), two_sided=True)
    for r in rows:
        n_eff, ic = r.get("n_eff"), r.get("ic")
        if not isinstance(n_eff, (int, float)) or not isinstance(ic, (int, float)):
            continue
        if not np.isfinite(float(n_eff)) or float(n_eff) <= 0:
            continue
        need = float(z) / float(np.sqrt(float(n_eff)))
        r["family_size"] = int(n_family)
        r["family_z_critical"] = round(float(z), 4)
        r["ic_needed_family_wise"] = round(need, 4)
        r["clears_family_wise"] = bool(abs(float(ic)) >= need)


def _type2(rows: list[dict[str, Any]], *,
           n_family: int) -> list[tuple[dict[str, Any], Type2Cost]]:
    costs: list[tuple[dict[str, Any], Type2Cost]] = []
    for r in rows:
        n = r.get("n")
        if not isinstance(n, (int, float)) or float(n) <= 0:
            continue
        cost = correlation_negative(
            f"{r.get('venue')}|{r.get('construction')}|{r.get('target')}",
            n_obs=float(n), source="scripts/screen_venue_subsidy.py",
            horizon_periods=1.0, panel_width=1, n_tests=n_family, alpha=DEFAULT_ALPHA,
            effect_unit="ic",
            note=("daily rows are non-overlapping so n_eff = paired trading days. A fee tier is "
                  "highly persistent, so the signal's serial correlation is severe and is NOT "
                  "deflated here -- this power figure is an UPPER BOUND and the true effective "
                  "sample is closer to the number of TIER CHANGES than to the number of days."))
        r["type2"] = cost.as_dict()
        r["type2_label"] = cost.label
        costs.append((r, cost))
    return costs


def build_report(*, captures: list[dict[str, Any]], rows: list[dict[str, Any]],
                 probes: list[dict[str, Any]], missing: list[str],
                 provenance: dict[str, Any]) -> dict[str, Any]:
    scored = [r for r in rows if isinstance(r.get("ic"), (int, float))]
    n_family = max(PREREGISTERED_FAMILY, len(scored))
    _significance(scored, n_family=n_family)
    pairs = _type2(scored, n_family=n_family)

    survivors: list[dict[str, Any]] = []
    graveyard: list[dict[str, Any]] = []
    net_measured = [c for c in captures if c.get("verdict") == "NET-MEASURED"]
    for r in scored:
        verdict = str(r.get("verdict", ""))
        venue_net = next((c for c in net_measured if c.get("venue") == r.get("venue")), None)
        if (verdict == "SCREEN-INTERESTING" and bool(r.get("powered"))
                and bool(r.get("clears_family_wise")) and venue_net is not None
                and isinstance(venue_net.get("net_usd"), (int, float))
                and float(venue_net["net_usd"]) > 0.0):
            survivors.append({**{k: r.get(k) for k in
                                 ("venue", "construction", "ic", "n", "n_eff",
                                  "ic_needed_family_wise")},
                              "net_usd": venue_net.get("net_usd"),
                              "counterfactual": venue_net.get("counterfactual"),
                              "earns": ("a pre-registered FORWARD CLOCK and nothing else; this "
                                        "script does not write one")})
            continue
        floor = ((r.get("type2") or {}).get("min_detectable_effect")
                 if isinstance(r.get("type2"), dict) else None)
        if verdict in _KILL_VERDICTS and bool(r.get("powered")):
            graveyard.append({
                "venue": r.get("venue"), "construction": r.get("construction"),
                "target": r.get("target"), "ic": r.get("ic"), "n": r.get("n"),
                "n_eff": r.get("n_eff"),
                "detection_floor_ic_unadjusted": r.get("min_detectable_ic"),
                "detection_floor_ic_family_wise": floor,
                "type2_label": r.get("type2_label"), "verdict": verdict,
                "reason": _KILL_REASONS[verdict]})

    refused = [c for c in captures if c.get("verdict") == REFUSED]
    tally: dict[str, int] = {}
    for r in rows:
        v = str(r.get("verdict", "?"))
        tally[v] = tally.get(v, 0) + 1
    desk = headline([c for _, c in pairs]) if pairs else None
    status = "SCREENED" if net_measured else (REFUSED if captures else "NOT-READABLE-HERE")
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_utc": datetime.now(tz=UTC).isoformat(),
        "script": "scripts/screen_venue_subsidy.py",
        "status": status,
        "stage": "A (zero promotion authority)",
        "mechanism_class": MECHANISM_CLASS,
        "pre_registration": pre_registration(),
        "net_testable": bool(net_measured),
        "rebate_captures": captures,
        "refused_venues": [c.get("venue") for c in refused],
        "gross_reported": False,
        "gross_refusal": (
            "NO GROSS NUMBER APPEARS IN THIS ARTIFACT. `libs/research/venue_subsidy` has no "
            "function that returns a rebate total without its cost side, and RebateCapture.net_usd "
            "is None whenever the round-trip cost of the trades required to earn it is unmeasured. "
            "A rebate earned by trades that would not otherwise have happened is churn, and the "
            "2026-07 fee fire is what the gross version of this number looks like."),
        "venue_probes": probes,
        "missing_inputs": missing,
        # WHAT AN OPERATOR MUST SUPPLY, exactly. A refusal that does not say how to lift itself is
        # a dead end; this is the whole contract, so the file can be built once by hand from venue
        # ANNOUNCEMENTS (which carry effective dates) rather than from a fee page (which does not).
        "schedule_contract": {
            "path": _rel(SCHEDULES),
            "shape": "{venue: [tier, ...]}",
            "required_fields_per_tier": ["tier", "maker_bps", "taker_bps", "min_30d_volume_usd",
                                         "effective_from", "source_url", "retrieved_utc"],
            "optional_fields_per_tier": ["effective_to"],
            "maker_bps_sign": "NEGATIVE means the venue PAYS the maker; positive means it charges",
            "why_effective_from_is_mandatory": (
                "a row without it is rejected outright rather than defaulted to the current rate. "
                "No keyless endpoint measured here publishes one -- Deribit serves the CURRENT "
                "commission and nothing historical -- so this file is built from venue ANNOUNCE"
                "MENTS, which are dated, not from the live fee page, which is not."),
            "why_provenance_is_mandatory": (
                "a schedule typed from memory is a fabricated input wearing a citation's name"),
        },
        "still_missing_after_the_schedule": (
            "even a complete dated schedule does NOT make this testable: the executor's own tape "
            "records notional, leg mode and per-leg slippage but NOT the commission the venue "
            "charged. That lives in the venue income ledger (binance_testnet.commission_events) "
            "behind keys, and data/execution_economics.json currently reads NOT-READABLE-HERE for "
            "every fee term. A rebate is a FEE OUTCOME, so a tape without fees cannot measure one "
            "however many fills it holds. BOTH inputs are required before any number exists."),
        "provenance": provenance,
        "hypotheses": len(rows), "scored": len(scored),
        "family_size_charged": n_family,
        "family_z_critical": round(float(critical_z(DEFAULT_ALPHA, n_family, two_sided=True)), 4),
        "declared_effects": list(DECLARED_CORRELATION_EFFECTS),
        "powered_cells_unadjusted": sum(1 for r in scored if bool(r.get("powered"))),
        "power_headline": (desk.summary() if desk is not None
                           else "no cell was scored -- the net accounting gate refused first, so "
                                "there is no negative to power-label and NOTHING is graveyarded"),
        "power_counts": {
            "negatives": desk.n_negatives if desk is not None else 0,
            "powered": desk.n_powered if desk is not None else 0,
            "underpowered": desk.n_underpowered if desk is not None else 0,
            "indeterminate": desk.n_indeterminate if desk is not None else 0,
        },
        "tally": tally,
        "survivors": survivors,
        "graveyard": graveyard,
        "rows": rows,
        "r0143": ("nothing in this artifact is an argument for more size or leverage. A rebate "
                  "tier the desk does not already reach on its own observed volume is recorded as "
                  "NOT-EARNABLE-AT-CURRENT-SIZE, which is a KILL."),
        "note": ("A REFUSAL IS THE DELIVERABLE when the net cannot be computed. It is not a "
                 "failure and it is not a smaller finding -- reporting a gross rebate instead "
                 "would be the fee fire's own arithmetic. Nothing here is graveyarded on a "
                 "refusal: refusing to measure is not evidence of absence."),
        "authority": "NONE -- Stage A. Nothing here promotes, sizes, or writes a clock file.",
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Stage-A screen: venue subsidy / rebate rent (gap #4)")
    ap.add_argument("--schedules", type=Path, default=SCHEDULES)
    ap.add_argument("--probe-venues", action="store_true",
                    help="fetch the keyless fee endpoints and record which venues refuse")
    ap.add_argument("--venue", default="binance",
                    help="venue assumed for fill rows carrying no venue field; recorded as an "
                         "assumption in the artifact")
    ap.add_argument("--attribute-incumbent", action="store_true",
                    help="assert EVERY fill happened for a reason that does not reference the "
                         "rebate. Requires principal-level evidence; default OFF, which values "
                         "the tape on the conservative REBATE_SEEKING branch")
    ap.add_argument("--roundtrip-cost-usd", type=float, default=None,
                    help="measured round-trip cost of the trades that earned the rebate. No "
                         "default: a zero here would be a claim that money did not move")
    ap.add_argument("--out", type=Path, default=REPORT)
    a = ap.parse_args(argv)

    probes = probe_venues(enabled=bool(a.probe_venues))
    schedules, sched_problems = load_schedules(Path(a.schedules))
    fills, fill_problems, provenance = load_fills(
        venue_default=str(a.venue), attribute_incumbent=bool(a.attribute_incumbent))
    missing = sched_problems + fill_problems

    venues = sorted(set(schedules) | {f.venue for f in fills}) or ["(none)"]
    captures: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    for v in venues:
        vf = [f for f in fills if f.venue == v]
        cap = net_rebate_capture(venue=v, fills=vf or None, schedule=schedules.get(v),
                                 roundtrip_cost_usd=a.roundtrip_cost_usd)
        captures.append(cap.as_dict())
        # THE GATE. Cells run ONLY when the net was actually measured. Anything else and the
        # screen has no legitimate series to correlate -- and printing one anyway is exactly the
        # gross-number failure this class is defined by.
        if cap.net_usd is not None and v in schedules:
            rows.extend(screen_venue(v, schedules[v], vf))

    report = build_report(captures=captures, rows=rows, probes=probes,
                          missing=missing, provenance=provenance)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1, default=str), "utf-8")

    print(f"venue-subsidy: status {report['status']}, net testable = {report['net_testable']}")
    for c in captures:
        print(f"  {c['venue']:<10} verdict {c['verdict']}  net {c['net_usd']}  "
              f"counterfactual {c['counterfactual']}  fills {c['n_fills']}")
        for m in c.get("missing", []):
            print(f"      MISSING {m}")
    if probes and any(p.get("status") != "NOT-PROBED" for p in probes):
        print("  venue fee-schedule probes:")
        for p in probes:
            print(f"      {p['venue']:<10} {p['status']:<14} "
                  f"publishes_maker_commission={p.get('publishes_maker_commission')} "
                  f"is_rebate={p.get('is_rebate', NOT_READABLE)}")
    if not report["net_testable"]:
        print(f"  {REFUSED}: no gross number is reported. A rebate earned by trades that would "
              "not otherwise have happened is churn, not income.")
        print("  nothing is graveyarded on a refusal -- refusing to measure is not evidence of "
              "absence")
    else:
        print(f"  {report['hypotheses']} cells, family {report['family_size_charged']} at alpha "
              f"{DEFAULT_ALPHA}, powered {report['powered_cells_unadjusted']}")
        for v, c in sorted(report["tally"].items(), key=lambda kv: -kv[1]):
            print(f"    {v:<24} {c}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
