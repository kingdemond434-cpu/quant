"""THE MIDDLE EAST INTERACTION MINER -- six mechanism families and two cross-region triples.

WHAT THIS ORGAN IS FOR. The three Middle East packs (`countries.sa`, `countries.ae`,
`countries.il`) declare actors, domains and transmission seeds. The three data planes store the
official series point-in-time. This module is what turns the two into QUESTIONS THE GAUNTLET CAN
ANSWER: it walks a family, resolves each leg from a stored series or from the desk's own bars,
runs a CONDITIONAL LEAD-LAG SCREEN with a permutation null when every leg exists, records one
discovery per family for `miner_candidate_compiler` (generator `mena:<family>`), and names -- by
leg -- every family it could not measure.

THE SIX FAMILIES, AND WHY EACH IS A FAMILY RATHER THAN A SIGNAL.

    oil_liquidity_state          Saudi money and deposits against the oil regime. The swing
                                 producer's domestic liquidity conditions how hard its supply
                                 policy must defend a price; the claim is CONDITIONAL and the
                                 unconditional correlation is expected to be near zero.
    domestic_demand_nowcast      The SAMA weekly point-of-sale print -- the only weekly official
                                 demand series in the Gulf -- as a nowcast of the economy that
                                 sets the marginal barrel.
    petrodollar_liquidity        Reserves, money supply and deposits as the recycling meter into
                                 US duration, gold and global risk.
    usd_liquidity_regional_funding  EIBOR and UAE deposits as the Gulf's dollar-funding state.
                                 The DEPOSIT LEG IS NOT OPTIONAL: a widening a liquidity drain
                                 explains is a credit cycle, not stress.
    trade_shipping               Jebel Ali throughput, the Fujairah weekly stockpile, Hormuz
                                 transit risk and -- when an Egypt pack exists -- Suez. The
                                 Egyptian leg belongs to the Africa civilization and is UNMEASURED
                                 by name until that pack lands; it is never proxied.
    il_rates_ils_tech            Israel's policy rate, the shekel and the institutional hedging
                                 channel that ties USDILS mechanically to NASDAQ.

THE TWO CROSS-REGION TRIPLES. A triple is not three signals averaged: it is a CONDITIONED pair.
`saudi_liquidity_x_oil_x_brazil` asks what a Saudi liquidity state does to the dollar and gold
WHEN an oil shock and a Brazilian commodity state agree -- reading the `br` lane when a sibling
builder has landed one, and saying so by name when not. `gulf_risk_x_jpy_funding_x_us_vol` asks
the same of a risk-off regime.

WHAT IT REFUSES TO DO. It never invents a leg. A family whose lead, target or condition is not
knowable point-in-time returns UNMEASURED WITH THE LEG NAMED (L1.28a) and still records the
question, because a question the desk cannot yet answer is the most valuable thing a data-gap
report can carry. It never targets a Gulf currency (none is quoted here), never a single-name
equity (two-lane order, 2026-09-06) and never crypto-exchange ground (mandate, 2026-08-18).

    python desks/mt5/research/middle_east_interaction.py --dry-run
    python desks/mt5/research/middle_east_interaction.py --budget-s 240
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
for _p in (str(ROOT), str(BASE), str(BASE / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

AXES = BASE / "data" / "axes"
UNIVERSE_DIR = BASE / "data" / "universe"
REPORT = BASE / "reports" / "MIDDLE_EAST_INTERACTION.json"

REGION = "middle_east"
TAG = "mena:"
GENERATOR_PREFIX = TAG

#: The screen's own floor. `libs.hypmax.fast_screen` uses 120 aligned observations before it will
#: charge a permutation null, and this module uses the SAME number so a cell screened here and a
#: cell screened there mean the same thing. Below it the answer is UNMEASURED, never "no effect".
MIN_OBS = 120
N_PERM = 200
PERM_P_MAX = 0.30
MIN_ABS_IC = 0.005

RULE = ("Middle East official series are SENSORS for instruments the desk already trades. Every"
        " family names its legs, resolves each one point-in-time, screens the pair CONDITIONED on"
        " a state with a permutation null, and reports UNMEASURED BY LEG when any leg is absent."
        " The region's own currencies are pegged or unquoted and are never the target; no"
        " single-name equity is ever a target; no crypto-exchange ground is ever read.")


# ------------------------------------------------------------------------------ leg and family
@dataclass(frozen=True)
class Leg:
    """One resolvable input. `kind` says where it comes from and therefore how it can fail."""

    kind: str                  # "series" (a data-plane axis) or "bars" (the desk's own capture)
    what: str                  # a human name, used in the UNMEASURED row when it cannot resolve
    country: str = ""
    lane: str = ""
    series: str = ""
    symbol: str = ""
    optional: bool = False     # an optional leg degrades the screen; it does not kill the family

    def key(self) -> str:
        if self.kind == "bars":
            return f"bars:{self.symbol}"
        return f"{self.country}:{self.lane}:{self.series}"


@dataclass(frozen=True)
class Family:
    """One mechanism family: a lead, a target, an optional conditioning state, and the discipline.

    `control` and `falsifier` are not decoration. The control is what the screen must ALSO run so
    an effect can be told from the desk's own sampling, and the falsifier is what would retire the
    family. A family with neither is a story.
    """

    fid: str
    title: str
    country: str
    lead: Leg
    targets: tuple[str, ...]
    condition: Leg | None = None
    horizon: int = 5
    mechanism: str = ""
    control: str = ""
    falsifier: str = ""
    mechanism_families: tuple[str, ...] = ()
    extra_legs: tuple[Leg, ...] = ()
    cross_region: bool = False

    def legs(self) -> tuple[Leg, ...]:
        rows = [self.lead, *self.extra_legs]
        if self.condition is not None:
            rows.append(self.condition)
        return tuple(rows)


def _series_leg(country: str, lane: str, series: str, what: str, *,
                optional: bool = False) -> Leg:
    return Leg(kind="series", what=what, country=country, lane=lane, series=series,
               optional=optional)


def _bars_leg(symbol: str, what: str, *, optional: bool = False) -> Leg:
    return Leg(kind="bars", what=what, symbol=symbol, optional=optional)


# ------------------------------------------------------------------------------ the families
FAMILIES: tuple[Family, ...] = (
    Family(
        fid="oil_liquidity_state",
        title="Saudi liquidity as the conditioner on the marginal barrel",
        country="sa",
        lead=_series_leg("sa", "sama", "money_supply_weekly_sar",
                         "SAMA weekly money supply (the Gulf's only weekly liquidity read)"),
        condition=_bars_leg("XBRUSD", "the oil regime itself, as the conditioning state"),
        targets=("XBRUSD", "XTIUSD"),
        horizon=10,
        mechanism="the swing producer's domestic liquidity conditions how hard its supply policy "
                  "has to defend a price: a tightening domestic liquidity state with a wide "
                  "fiscal gap raises the probability of a defended cut",
        control="the oil price's own momentum partialled out, and the unconditional leg reported "
                "beside the conditional one -- the claim is that the effect exists ONLY in one "
                "oil regime, so an unconditional near-zero is a confirmation and not a refutation",
        falsifier="the conditional and unconditional screens are indistinguishable over three "
                  "years, which would mean the conditioning state carries no information",
        mechanism_families=("liquidity_state", "supply_state", "policy_signal"),
    ),
    Family(
        fid="domestic_demand_nowcast",
        title="The SAMA weekly point-of-sale print as a Gulf demand nowcast",
        country="sa",
        lead=_series_leg("sa", "sama", "pos_value_sar",
                         "SAMA weekly point-of-sale value (نقاط البيع)"),
        condition=_series_leg("sa", "sama", "money_supply_weekly_sar",
                              "the weekly liquidity state, as the conditioner", optional=True),
        targets=("XBRUSD", "XAUUSD", "US500"),
        horizon=10,
        mechanism="the only weekly official demand series in the Gulf, measuring the domestic "
                  "economy of the country that sets the marginal barrel's price; its seasonality "
                  "is HIJRI, so the Hijri overlap flag from countries.sa.pack:pos_weeks must "
                  "condition every window",
        control="matched non-Hijri weeks of the same calendar month, the same week of the "
                "preceding three years, and a placebo target with no Gulf exposure",
        falsifier="POS growth and the non-oil activity print diverge in sign for four consecutive "
                  "quarters, which would mean the card series has stopped measuring demand",
        mechanism_families=("domestic_demand_nowcast", "consumption_state", "hijri_seasonal"),
    ),
    Family(
        fid="petrodollar_liquidity",
        title="Reserves, money and deposits as the petrodollar recycling meter",
        country="sa",
        lead=_series_leg("sa", "sama", "net_foreign_assets_sar",
                         "SAMA net foreign assets (الاحتياطي)"),
        condition=_bars_leg("XBRUSD", "the oil regime, which must be partialled out before any "
                                      "recycling claim"),
        targets=("XAUUSD", "USDX", "UST10Y", "US500"),
        horizon=20,
        mechanism="an accumulating reserve is a real bid for reserve assets -- gold is the part "
                  "of that bid which is not US duration, and the dollar is the funding leg",
        control="the oil price partialled out FIRST, other exporters' reserves as the common "
                "factor, and announced sovereign-fund transfers excluded -- a reserve fall that "
                "is a transfer is not a reserve fall that is a deficit",
        falsifier="reserves and the oil price decouple for three consecutive years with no "
                  "sovereign-fund transfer to explain it",
        mechanism_families=("petrodollar_recycling", "sovereign_flow", "peg_defence"),
    ),
    Family(
        fid="usd_liquidity_regional_funding",
        title="EIBOR against UAE deposits: the Gulf dollar-funding state",
        country="ae",
        lead=_series_leg("ae", "cbuae", "eibor_3m", "3-month EIBOR (إيبور)"),
        condition=_series_leg("ae", "cbuae", "bank_deposits_aed",
                              "UAE bank deposits -- THE control, not an optional extra"),
        targets=("XAUUSD", "USDX", "US500"),
        horizon=10,
        mechanism="under the peg EIBOR is the dollar's cost wearing a local name, so a widening "
                  "that deposit growth does NOT explain is a statement about dollar scarcity in "
                  "the region holding the largest external surplus",
        control="deposit growth and the liquid-asset ratio first; SAIBOR against the same curve "
                "as the peg-sharing sibling; a matched calm-period window",
        falsifier="an EIBOR widening with no deposit or liquidity-ratio move, twice running, and "
                  "no measurable effect on the dollar or gold",
        mechanism_families=("regional_funding", "funding_stress", "gulf_risk_state"),
    ),
    Family(
        fid="trade_shipping",
        title="Jebel Ali, Fujairah and the chokepoint: the trade and transit state",
        country="ae",
        lead=_series_leg("ae", "fujairah", "fujairah_middle_distillates",
                         "the weekly Fujairah middle-distillate stockpile, outside Hormuz"),
        condition=_bars_leg("XBRUSD", "the crude regime, as the conditioning state"),
        targets=("XBRUSD", "XTIUSD", "XAUUSD"),
        horizon=10,
        mechanism="a weekly physical inventory at the world's second bunkering hub, on the Indian "
                  "Ocean side of the Strait of Hormuz, reads regional supply, rerouting and "
                  "transit risk in one number",
        control="global product inventories as the common factor and matched non-disruption "
                "weeks; a build during a rerouting episode is a different object from a build in "
                "a calm week",
        falsifier="the weekly stockpile shows no response to three consecutive Hormuz or Red Sea "
                  "transit episodes",
        mechanism_families=("physical_inventory", "shipping_state", "hormuz_risk"),
        extra_legs=(
            Leg(kind="series", what="Suez transit from an Egypt pack in the Africa civilization",
                country="eg", lane="suez", series="suez_transits", optional=True),
        ),
    ),
    Family(
        fid="il_rates_ils_tech",
        title="Israeli rates, the shekel and the institutional hedge on global technology",
        country="il",
        lead=_bars_leg("NAS100", "the global technology beta that the hedging rule rebalances "
                                 "against"),
        condition=_series_leg("il", "boi", "institutional_hedge_ratio",
                              "the institutional currency hedge ratio -- the GAIN on the channel",
                              optional=True),
        targets=("USDILS", "EURILS"),
        horizon=5,
        mechanism="Israeli institutions hold a large foreign equity portfolio and hedge it, so a "
                  "rise in global equities forces them to SELL dollars to restore the hedge "
                  "ratio. The relationship is a rebalancing RULE, not a risk-sentiment beta, and "
                  "the hedge ratio sets its gain",
        control="other developed currencies' response to the same equity move, so a global "
                "risk-on effect is not attributed to Israeli hedging; matched non-month-end "
                "windows",
        falsifier="USDILS stops responding negatively to a large NASDAQ move over three years "
                  "with the hedge ratio unchanged",
        mechanism_families=("hedging_flow", "forced_flow", "tech_cycle"),
        extra_legs=(
            _series_leg("il", "boi", "boi_policy_rate", "the Bank of Israel rate", optional=True),
        ),
    ),
)

CROSS_REGION: tuple[Family, ...] = (
    Family(
        fid="saudi_liquidity_x_oil_x_brazil",
        title="Saudi liquidity x an oil shock x the Brazilian commodity state",
        country="sa",
        lead=_series_leg("sa", "sama", "money_supply_weekly_sar",
                         "SAMA weekly money supply, the Gulf liquidity leg"),
        condition=_bars_leg("XBRUSD", "the oil shock leg"),
        targets=("USDX", "XAUUSD", "US500"),
        horizon=20,
        cross_region=True,
        mechanism="two commodity-surplus blocs recycling into the same dollar: when Gulf "
                  "liquidity and a Brazilian commodity state agree about the direction of the "
                  "terms of trade, the dollar and gold should carry it. When they disagree, the "
                  "signal is the DISAGREEMENT and the family says so rather than averaging them",
        control="the oil price partialled out of both legs; US liquidity as the common factor; "
                "the two-leg version reported beside the three-leg one so the third leg's "
                "contribution is measured rather than assumed",
        falsifier="the three-leg conditional screen is no better than the two-leg one over three "
                  "years, which retires the Brazilian leg rather than the family",
        mechanism_families=("petrodollar_recycling", "terms_of_trade", "cross_region"),
        extra_legs=(
            Leg(kind="series", what="the Brazilian commodity state from a `br` lane",
                country="br", lane="bcb", series="commodity_index", optional=True),
        ),
    ),
    Family(
        fid="gulf_risk_x_jpy_funding_x_us_vol",
        title="Gulf risk x JPY funding x US volatility: a risk-off regime",
        country="ae",
        lead=_series_leg("ae", "cbuae", "eibor_3m",
                         "the Gulf funding leg (EIBOR, residualised on deposits)"),
        condition=_bars_leg("USDJPY", "the JPY funding leg -- the carry currency's own path"),
        targets=("XAUUSD", "US500", "USDJPY"),
        horizon=10,
        cross_region=True,
        mechanism="a risk-off regime shows up in three places at once: Gulf dollar funding "
                  "tightens, the yen funding leg unwinds, and US volatility rises. The claim is "
                  "that the THREE TOGETHER identify the regime better than any one, which is a "
                  "testable statement about conditioning and not a narrative",
        control="each leg's own momentum partialled out; a matched calm regime; a placebo on an "
                "instrument with no funding exposure",
        falsifier="the three-leg conditional screen adds nothing to the best single leg over "
                  "three years",
        mechanism_families=("gulf_risk_state", "funding_stress", "risk_off_regime"),
        extra_legs=(
            _bars_leg("US500", "the US volatility leg, taken from realised range when no "
                               "volatility index is quoted", optional=True),
        ),
    ),
)

ALL_FAMILIES: tuple[Family, ...] = FAMILIES + CROSS_REGION


# ------------------------------------------------------------------------------ the readers
def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def default_series(country: str, lane: str, series: str) -> list[tuple[str, float]]:
    """A stored data-plane series as (available_time, value). EMPTY IS A MEASUREMENT.

    Reads through the Middle East lane base when it imports, so the point-in-time semantics are
    the store's own and not a second implementation of them.
    """
    try:
        from countries.sa.data_plane import read_series
        return list(read_series(AXES, country, lane, series))
    except Exception:       # pragma: no cover -- a tree where the lane base has not landed
        doc = _read_json(AXES / f"{country}_{lane}_{series}.json")
        if not isinstance(doc, Mapping):
            return []
        rows = [(str(p.get("available_time") or ""), float(p.get("value") or 0.0))
                for p in (doc.get("points") or []) if isinstance(p, Mapping)]
        return sorted(r for r in rows if r[0])


#: The capture this box actually holds, in the order the reader tries them. NOT every symbol has
#: an H1 file -- US500 on this box has D1 and H4 and no H1 -- and a reader that only knows H1
#: reports a symbol the desk has six years of history for as UNMEASURED. Measured 2026-09-17.
BAR_CHARTS: tuple[str, ...] = ("H1", "D1", "H4")


def default_bars(symbol: str, chart: str = "") -> list[tuple[str, float]]:
    """The desk's own capture, collapsed to one close per DAY. `[]` when NO chart file exists.

    Daily because every Middle East lead is weekly, monthly or quarterly: screening a monthly
    series against hourly bars measures the bar clock, not the mechanism.
    """
    charts = (chart,) if chart else BAR_CHARTS
    path = next((UNIVERSE_DIR / f"{symbol}_{c}.parquet" for c in charts
                 if (UNIVERSE_DIR / f"{symbol}_{c}.parquet").exists()), None)
    if path is None:
        return []
    try:
        import pandas as pd
        frame = pd.read_parquet(path, columns=["close"])
    except Exception:       # pragma: no cover -- no pyarrow, or a frame without a close column
        return []
    if frame.empty:
        return []
    try:
        index = pd.DatetimeIndex(pd.to_datetime(frame.index, utc=True, errors="coerce"))
        frame = frame[~index.isna()]
        frame.index = index[~index.isna()]
        daily = frame["close"].resample("1D").last().dropna()
    except Exception:       # pragma: no cover -- an index shape the capture changed
        return []
    return [(str(ts.date()), float(v)) for ts, v in daily.items()]


# ------------------------------------------------------------------------------ the screen
def as_of_join(lead: Sequence[tuple[str, float]],
               target: Sequence[tuple[str, float]]) -> list[tuple[str, float, float]]:
    """(date, lead value KNOWN at that date, target price). The PIT join a backtest would make.

    The lead's stamp is its AVAILABLE time, so a monthly figure published on the 28th joins to the
    28th and not to the month it describes. That single choice is the difference between a
    tradable screen and a look-ahead.
    """
    lead_rows = sorted((str(d), float(v)) for d, v in lead if d)
    out: list[tuple[str, float, float]] = []
    i = 0
    current: float | None = None
    for day, price in sorted((str(d), float(v)) for d, v in target if d):
        while i < len(lead_rows) and lead_rows[i][0][:10] <= day[:10]:
            current = lead_rows[i][1]
            i += 1
        if current is not None:
            out.append((day, current, price))
    return out


def _ranks(values: Sequence[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        mid = (i + j) / 2.0
        for k in range(i, j + 1):
            ranks[order[k]] = mid
        i = j + 1
    return ranks


def rank_ic(signal: Sequence[float], forward: Sequence[float]) -> float:
    """Spearman rank IC. Rank-based because one outlier can manufacture a Pearson correlation."""
    if len(signal) < 3 or len(signal) != len(forward):
        return 0.0
    rs, rf = _ranks(signal), _ranks(forward)
    n = len(rs)
    ms, mf = sum(rs) / n, sum(rf) / n
    num = sum((a - ms) * (b - mf) for a, b in zip(rs, rf, strict=True))
    ds = math.sqrt(sum((a - ms) ** 2 for a in rs))
    df = math.sqrt(sum((b - mf) ** 2 for b in rf))
    return float(num / (ds * df)) if ds > 0 and df > 0 else 0.0


def permutation_p(signal: Sequence[float], forward: Sequence[float], *, n_perm: int = N_PERM,
                  seed: int = 0) -> float:
    """Fraction of shuffled pairings producing |IC| at least as large as the observed one.

    Reuses `libs.hypmax.fast_screen` when it imports -- the desk already owns this null and two
    implementations of one statistic is how two organs come to disagree about the same cell. The
    local fallback shuffles the FORWARD returns, which is the same null: it destroys the pairing
    while preserving each series' own distribution.
    """
    try:
        from libs.hypmax import fast_screen
        return float(fast_screen.permutation_p(list(signal), list(forward), n_perm=n_perm,
                                               seed=seed))
    except Exception:       # pragma: no cover -- a tree without hypmax
        import numpy as np
        if len(signal) < MIN_OBS:
            return 1.0
        obs = abs(rank_ic(signal, forward))
        rng = np.random.default_rng(seed)
        arr = np.asarray(forward, dtype=float)
        hits = sum(1 for _ in range(n_perm)
                   if abs(rank_ic(signal, list(rng.permutation(arr)))) >= obs)
        return (hits + 1) / (n_perm + 1)


def conditional_lead_lag(lead: Sequence[tuple[str, float]],
                         target: Sequence[tuple[str, float]],
                         condition: Sequence[tuple[str, float]] | None = None, *,
                         horizon: int = 5, min_obs: int = MIN_OBS, n_perm: int = N_PERM,
                         seed: int = 0) -> dict[str, Any]:
    """The screen: does the lead's CHANGE predict the target's forward return, in a state?

    Three numbers come back and all three are published. The UNCONDITIONAL leg is the honest
    baseline. The CONDITIONED leg is the claim -- the sample restricted to the state's upper half.
    The CONTROL leg is the complement, and it is the reason the conditional number means anything:
    an effect that is equally strong in both halves is not conditional, it is just an effect, and
    a family that claimed conditionality has been refuted rather than confirmed.

    Fewer than `min_obs` aligned observations returns UNMEASURED. It does NOT return "no effect":
    a screen that never ran is not a screen that found nothing (L1.28a).
    """
    joined = as_of_join(lead, target)
    if len(joined) < horizon + 2:
        return {"verdict": "UNMEASURED", "n": len(joined),
                "why": f"{len(joined)} aligned observation(s) before the {horizon}-step forward "
                       f"window can even be formed"}
    signal: list[float] = []
    forward: list[float] = []
    days: list[str] = []
    for i in range(1, len(joined) - horizon):
        prev_lead, cur_lead = joined[i - 1][1], joined[i][1]
        p0, p1 = joined[i][2], joined[i + horizon][2]
        if p0 <= 0 or p1 <= 0:
            continue
        delta = (cur_lead / prev_lead - 1.0) if prev_lead else (cur_lead - prev_lead)
        signal.append(delta)
        forward.append(math.log(p1 / p0))
        days.append(joined[i][0])
    if len(signal) < min_obs:
        return {"verdict": "UNMEASURED", "n": len(signal), "min_obs": min_obs,
                "why": f"{len(signal)} aligned observation(s) < {min_obs}: nothing is measurable "
                       f"here, and an unmeasured pair is never reported as an absent effect "
                       f"(L1.28a)"}
    out: dict[str, Any] = {"n": len(signal), "horizon": horizon,
                           "ic": round(rank_ic(signal, forward), 5),
                           "p_permutation": round(permutation_p(signal, forward, n_perm=n_perm,
                                                                seed=seed), 4),
                           "null": f"permutation, {n_perm} draws, forward returns shuffled",
                           "first": days[0], "last": days[-1]}
    if condition:
        # The conditioning state, joined the same PIT way: its value KNOWN on each screen day.
        state = {row[0]: row[1] for row in as_of_join(condition, [(d, 1.0) for d in days])}
        values = sorted(state.values())
        if len(values) >= min_obs:
            median = values[len(values) // 2]
            hi = [(s, f) for s, f, d in zip(signal, forward, days, strict=True)
                  if state.get(d, median) >= median]
            lo = [(s, f) for s, f, d in zip(signal, forward, days, strict=True)
                  if state.get(d, median) < median]
            out["conditional"] = _leg(hi, "state HIGH (the claim)", n_perm, seed)
            out["control"] = _leg(lo, "state LOW (the complement, which is the control)", n_perm,
                                  seed)
            # SEPARATION NEEDS A MEASURED CONTROL. A degenerate state -- one that is constant, or
            # whose median leaves one side below the floor -- puts every observation in the claim
            # half and none in the control, and the control then comes back UNMEASURED. Reading
            # that as "the effect is absent in the control half" is the L1.28a error in its purest
            # form: an unmeasured leg would be standing in as evidence FOR the conditional claim.
            # So separation requires the control to have actually run AND to have failed.
            out["separates"] = bool(out["conditional"].get("verdict") == "SCREENED"
                                    and out["control"].get("verdict") == "NOT_SEPARATED")
            if min(len(hi), len(lo)) < min_obs:
                out["conditioning"] = (
                    f"DEGENERATE SPLIT: {len(hi)} observation(s) in the claim half and {len(lo)} "
                    f"in the control half against a floor of {min_obs}. The state does not "
                    f"separate this sample, so the conditional claim is UNMEASURED rather than "
                    f"confirmed, whatever the full-sample screen says.")
        else:
            out["conditional"] = {"verdict": "UNMEASURED",
                                  "why": f"the conditioning state is knowable on {len(values)} of "
                                         f"{len(days)} screen days, fewer than {min_obs}"}
    verdict = ("SCREENED" if (abs(out["ic"]) >= MIN_ABS_IC
                              and out["p_permutation"] <= PERM_P_MAX) else "NOT_SEPARATED")
    out["verdict"] = verdict
    out["why"] = (f"IC {out['ic']:+.4f} with permutation p {out['p_permutation']:.3f} over "
                  f"{out['n']} observations at horizon {horizon}")
    return out


def _leg(pairs: Sequence[tuple[float, float]], label: str, n_perm: int,
         seed: int) -> dict[str, Any]:
    if len(pairs) < MIN_OBS:
        return {"verdict": "UNMEASURED", "label": label, "n": len(pairs),
                "why": f"{len(pairs)} observation(s) in this half < {MIN_OBS}"}
    signal = [p[0] for p in pairs]
    forward = [p[1] for p in pairs]
    ic = rank_ic(signal, forward)
    p = permutation_p(signal, forward, n_perm=n_perm, seed=seed)
    return {"verdict": "SCREENED" if (abs(ic) >= MIN_ABS_IC and p <= PERM_P_MAX)
            else "NOT_SEPARATED",
            "label": label, "n": len(pairs), "ic": round(ic, 5), "p_permutation": round(p, 4)}


# ------------------------------------------------------------------------------ the context
@dataclass
class Ctx:
    """Readers, budget and ledger. A test injects its own readers and touches no disk."""

    series_fn: Callable[[str, str, str], list[tuple[str, float]]] = default_series
    bars_fn: Callable[[str], list[tuple[str, float]]] = default_bars
    record_fn: Callable[..., Any] | None = None
    conn: Any = None
    dry_run: bool = True
    budget_s: float = 240.0
    min_obs: int = MIN_OBS
    n_perm: int = N_PERM
    started: float = field(default_factory=time.monotonic)
    unmeasured: list[dict[str, Any]] = field(default_factory=list)
    recorded: list[dict[str, Any]] = field(default_factory=list)

    def over(self) -> bool:
        return (time.monotonic() - self.started) >= float(self.budget_s)

    def note_unmeasured(self, family: str, leg: str, why: str) -> None:
        """UNMEASURED BY NAME. An absence recorded here is a verdict, never a silent zero."""
        self.unmeasured.append({"family": family, "leg": leg, "why": why})

    def resolve(self, leg: Leg) -> list[tuple[str, float]]:
        if leg.kind == "bars":
            return list(self.bars_fn(leg.symbol) or [])
        return list(self.series_fn(leg.country, leg.lane, leg.series) or [])

    def record(self, *, family: str, mechanism: str, assets: Sequence[str],
               payload: Mapping[str, Any], **extra: Any) -> str:
        """One DiscoveryObject per family, stamped `mena:<family>`. Dry runs persist nothing."""
        row = {"source_id": f"mena:{family}", "source_type": "mena_interaction",
               "mechanism": mechanism[:400], "origin": "EXTERNAL",
               "generator": f"{GENERATOR_PREFIX}{family}", "assets": list(assets),
               "payload": {**dict(payload), "region": REGION, "rule": RULE}, **extra}
        self.recorded.append(row)
        if self.dry_run:
            return ""
        if self.record_fn is not None:
            got = self.record_fn(**row)
            return str(got[0]) if isinstance(got, tuple) else str(got)
        try:
            from libs.moat import registry as R
            did, _ = R.record_discovery(conn=self.conn, **row)
            return str(did)
        except Exception:   # pragma: no cover -- a registry that cannot be opened is not fatal
            return ""


def now_iso() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


# ------------------------------------------------------------------------------ the pass
def run_family(ctx: Ctx, fam: Family) -> dict[str, Any]:
    """One family: resolve every leg, screen what can be screened, record the question either way.

    A missing REQUIRED leg makes the family UNMEASURED and the discovery is recorded anyway, with
    the missing leg named in its payload. That is deliberate: the compiler's backlog of blocked
    cells IS the data-acquisition plan, and a family that silently disappears when a series is
    absent produces no plan at all.
    """
    row: dict[str, Any] = {"family": fam.fid, "title": fam.title, "country": fam.country,
                           "targets": list(fam.targets), "horizon": fam.horizon,
                           "cross_region": bool(fam.cross_region),
                           "mechanism_families": list(fam.mechanism_families),
                           "control": fam.control, "falsifier": fam.falsifier,
                           "legs": [], "screens": [], "missing": []}
    resolved: dict[str, list[tuple[str, float]]] = {}
    for leg in fam.legs():
        values = ctx.resolve(leg)
        row["legs"].append({"leg": leg.key(), "what": leg.what, "n": len(values),
                            "optional": leg.optional})
        if values:
            resolved[leg.key()] = values
            continue
        row["missing"].append(leg.key())
        ctx.note_unmeasured(fam.fid, leg.key(),
                            f"{leg.what}: nothing stored -- the leg is UNMEASURED by name, not "
                            f"empty, and the family cannot be screened on it (L1.28a)")
    lead = resolved.get(fam.lead.key())
    condition = resolved.get(fam.condition.key()) if fam.condition is not None else None
    if lead is None:
        row["verdict"] = "UNMEASURED"
        row["why"] = (f"the LEAD leg {fam.lead.key()} is not stored; every target of this family "
                      f"is blocked on it")
    else:
        for symbol in fam.targets:
            prices = ctx.bars_fn(symbol) or []
            if not prices:
                row["missing"].append(f"bars:{symbol}")
                ctx.note_unmeasured(fam.fid, f"bars:{symbol}",
                                    f"no bars for {symbol} on this box -- the target is "
                                    f"UNMEASURED, not flat")
                continue
            screen = conditional_lead_lag(lead, prices, condition, horizon=fam.horizon,
                                          min_obs=ctx.min_obs, n_perm=ctx.n_perm)
            screen.update({"family": fam.fid, "target": symbol, "lead": fam.lead.key(),
                           "condition": fam.condition.key() if fam.condition else None})
            row["screens"].append(screen)
            if ctx.over():
                ctx.note_unmeasured(fam.fid, f"bars:{symbol}",
                                    f"budget {ctx.budget_s:.0f}s exhausted before the remaining "
                                    f"targets of this family were screened")
                break
        verdicts = {s.get("verdict") for s in row["screens"]}
        row["verdict"] = ("SCREENED" if "SCREENED" in verdicts
                          else ("NOT_SEPARATED" if "NOT_SEPARATED" in verdicts
                                else "UNMEASURED"))
        row["why"] = (f"{len(row['screens'])} target screen(s); verdicts "
                      f"{sorted(v for v in verdicts if v)}")
    row["discovery_id"] = ctx.record(
        family=fam.fid,
        mechanism=f"{fam.title}: {fam.mechanism}",
        assets=fam.targets,
        payload={"family": fam.fid, "country": fam.country, "legs": row["legs"],
                 "missing": row["missing"], "screens": row["screens"],
                 "verdict": row["verdict"], "control": fam.control,
                 "cross_region": bool(fam.cross_region)},
        horizons=[f"{fam.horizon}d"], sessions=["all"],
        required_data=[leg.key() for leg in fam.legs()],
        pit_requirements=["every leg joined at its AVAILABLE time, never its period end"],
        falsifier=fam.falsifier,
        economic_rationale=fam.mechanism,
        novelty=0.6, confidence=0.4 if row["verdict"] == "UNMEASURED" else 0.55)
    return row


def run(*, dry_run: bool = True, budget_s: float = 240.0, families: Sequence[str] | None = None,
        ctx: Ctx | None = None, report_path: Path | None = None) -> dict[str, Any]:
    """Every family and every cross-region triple, one pass, one report."""
    context = ctx or Ctx(dry_run=dry_run, budget_s=budget_s)
    chosen = [f for f in ALL_FAMILIES if not families or f.fid in set(families)]
    rows = [run_family(context, fam) for fam in chosen]
    screens = [s for r in rows for s in r["screens"]]
    doc = {
        "at": now_iso(),
        "region": REGION,
        "families": [r for r in rows if not r["cross_region"]],
        "cross_region": [r for r in rows if r["cross_region"]],
        "screens": screens,
        "discoveries_recorded": len(context.recorded),
        "unmeasured": context.unmeasured,
        "counts": {
            "families": len(rows),
            "screened": sum(1 for s in screens if s.get("verdict") == "SCREENED"),
            "not_separated": sum(1 for s in screens if s.get("verdict") == "NOT_SEPARATED"),
            "unmeasured_screens": sum(1 for s in screens if s.get("verdict") == "UNMEASURED"),
            "unmeasured_legs": len(context.unmeasured),
        },
        "dry_run": bool(context.dry_run),
        "rule": RULE,
    }
    if not context.dry_run:
        target = Path(report_path) if report_path is not None else REPORT
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="The Middle East interaction miner: six families and "
                                             "two cross-region triples")
    ap.add_argument("--dry-run", action="store_true",
                    help="screen and print; write nothing, record nothing")
    ap.add_argument("--budget-s", type=float, default=240.0)
    ap.add_argument("--family", action="append", choices=sorted(f.fid for f in ALL_FAMILIES))
    a = ap.parse_args(argv)
    doc = run(dry_run=a.dry_run, budget_s=a.budget_s, families=a.family)
    for row in doc["families"] + doc["cross_region"]:
        print(f"{row['family']:<34} {row['verdict']:<14} targets={len(row['targets'])} "
              f"screens={len(row['screens'])} missing={len(row['missing'])}")
        if row["missing"]:
            print(f"    UNMEASURED legs: {', '.join(row['missing'][:4])}")
    counts = doc["counts"]
    print(f"  screened={counts['screened']} not_separated={counts['not_separated']} "
          f"unmeasured_screens={counts['unmeasured_screens']} "
          f"unmeasured_legs={counts['unmeasured_legs']}")
    print(f"  discoveries={doc['discoveries_recorded']} "
          f"{'(dry run: nothing written, nothing recorded)' if a.dry_run else f'-> {REPORT.name}'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
