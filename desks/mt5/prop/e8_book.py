"""WHICH 24 SLEEVES THE E8 ACCOUNT TRADES, chosen from the certified survivors this venue lists.

Not a new hunt and not a new certificate. Every row here already holds a ten-gate universal
certificate; this file only decides which of them the E8 lane runs, and refuses the ones the
venue cannot fill.

THREE FILTERS, IN THIS ORDER, and the order is the point:

  1. THE VENUE MUST LIST IT. E8's catalogue is 46 instruments with no Scandi or EM crosses, so
     ten of the sixty-one certificates are unfillable here -- and they are the ten best by
     expected value, including `carry`'s only certificate (CHFNOK, ev 0.5929). An order on an
     instrument the venue does not list is not a small trade, it is a rejected one.
  2. DIVERSITY BEFORE EXPECTANCY. Taking the top 24 by ev would take 24 `discovered` rows,
     because `discovered` is 33 of the 51 survivors. The pass probability of this account is
     driven by how many INDEPENDENT bets it holds, not by the mean of their expectancies, so the
     selection round-robins across mechanisms and only then ranks within one.
  3. ONE ROW PER (mechanism, symbol). Two certificates on the same mechanism and the same
     instrument are one bet with two names -- exactly the breadth illusion `orthogonality.py`
     measures, bought on purpose.

SIZE IS NOT CHOSEN HERE. `RISK_FRAC` is the principal's decision recorded in docs/PROP_FIRM_E8.md
and re-derived under TAIL-implied correlation, and the executor reads it from this module so
there is one number in one place.

Artifact: desks/mt5/reports/E8_BOOK.json
"""
from __future__ import annotations

import json
import math
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SURVIVORS = DESK / "reports" / "UNIVERSAL_SURVIVORS.json"


def _family_banned(family: str) -> bool:
    """research/family_policy.family_banned, reached from this lane's own path; an unreadable
    policy reads as nothing banned, the same way the policy module itself reads it."""
    try:
        if str(DESK / "research") not in sys.path:
            sys.path.insert(0, str(DESK / "research"))
        from family_policy import family_banned
        return bool(family_banned(family))
    except Exception:
        return False
OUT = DESK / "reports" / "E8_BOOK.json"

#: The last catalogue the venue actually reported. Written whenever the live call succeeds, read
#: when it does not. A prop venue's instrument list changes on the order of months; a connection
#: fails on the order of minutes, and the desk must not lose rule 1 for the length of an outage.
CATALOGUE_CACHE = DESK / "data" / "e8_catalogue.json"


def _cache_catalogue(keys: set[str]) -> None:
    """Remember what the venue lists, so an outage costs freshness and not the rule."""
    try:
        CATALOGUE_CACHE.parent.mkdir(parents=True, exist_ok=True)
        CATALOGUE_CACHE.write_text(json.dumps({
            "measured_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "n": len(keys),
            "instruments": sorted(keys),
        }, indent=1), encoding="utf-8")
    except OSError:
        pass


def _cached_catalogue() -> set[str] | None:
    """The last measured catalogue, or None. None is 'I do not know', never 'no restriction'."""
    try:
        doc = json.loads(CATALOGUE_CACHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    rows = doc.get("instruments")
    if not isinstance(rows, list) or not rows:
        return None
    return {str(r) for r in rows}

#: HOW MANY SLEEVES, and it is a breadth decision rather than a taste one. Every certified sleeve
#: fires in the asia window, so the whole book lands at once into a 2.5% daily floor; widening the
#: book at a smaller per-sleeve size is what raises pass probability, and 24 x 0.05% keeps gross
#: simultaneous exposure at 1.2% -- under half the daily wall, before any stand-down.
MAX_SLEEVES = 24

#: RISK PER TRADE, as a fraction of the $100,000 initial balance. 0.15%, i.e. $150.
#:
#: RAISED FROM 0.05% ON 2026-09-14, on the principal's decision, against a measured sweep of the
#: real barrier -- `research/prop_barrier.py` over 4,000 paths per cell at the book actually
#: fielded (24 sleeves, rr 1.5, 0.64 trades per sleeve per day) and expectancy NET of cost at
#: +0.135R, which is the honest reading of the desk's +0.20 gross replay figure.
#:
#: WHAT 0.05% WAS COSTING, at tail-implied rho 0.58:
#:
#:     risk     P(pass)   median days   p90
#:     0.050%    99.6%         91       146
#:     0.075%   100.0%         61       106
#:     0.100%    99.9%         45        87
#:     0.125%    98.2%         37        74      <- here
#:     0.150%    88.3%         31        65
#:     0.200%    47.4%         20        37
#:
#: Fifty-four days bought one and a half points of pass probability. That is not a conservative
#: trade, it is an expensive one: E8 publishes no time limit on Pro, but every extra day is a day
#: of daily-floor exposure that the 2.5% rule can end, so a slower pass is not a monotonically
#: safer pass. The earlier 0.05% reading compared 0.05% against 0.07% only, where the difference
#: really was 96.3% against 84.0%; it never priced the speed being given up, because the sweep it
#: cited did not report days.
#:
#: WHY NOT FURTHER. Above 0.15% the curve falls off a cliff -- 47.4% at 0.20% -- because this
#: account truncates the right tail at +2% a day and leaves the left free to -2.5%. The pass-
#: optimal size is therefore well below the growth-optimal one, and 0.125% is the last point
#: where P(pass) is still near the ceiling while the median more than halves.
#:
#: This is an INCREASE in size and that is deliberate (growth governance Rule 2: a strong
#: opportunity must be allowed more capital when the evidence supports it). Nothing here lowers
#: any limit on the live MT5 book, which solves a different problem on a different venue --
#: `mt5desk/account_profile.py` is where that line is drawn.
#:
#: RAISED AGAIN TO 0.15% THE SAME NIGHT, once the venue's spreads were measured LIVE rather than
#: over a closed weekend. The first sample had every symbol frozen (min == max == median across
#: 11 draws); with the session open the same instruments quote EURUSD 0.431 bps and XAUUSD 1.175,
#: which on a 20-pip stop is a haircut of ~0.025R, not the ~0.065R the cost note assumed. Net
#: expectancy is therefore nearer +0.175 than +0.135 and the whole curve shifts.
#:
#: THE BINDING CONSTRAINT IS THE DAILY FLOOR, NOT THE STATIC ONE. At net +0.175, rho 0.58:
#:
#:     risk     P(pass)   median   p_fail_daily   worst_dd_p90
#:     0.125%    99.9%      35          0.1%          2.75%
#:     0.150%    98.3%      30          1.6%          3.30%     <- here
#:     0.175%    91.7%      26          8.0%          3.76%
#:     0.200%    78.0%      22         21.9%          3.90%
#:
#: Between 0.15% and 0.175% the daily-breach probability QUINTUPLES to buy four days. Worst
#: drawdown at p90 is 3.3% against a 10% static floor, so the $90,000 line is not what ends these
#: accounts -- the 2.5% daily one is.
#:
#: AND IT IS THE LAST SIZE THAT SURVIVES BEING WRONG. Across net +0.175 / +0.135 / +0.100:
#:     0.125%  ->  99.9 / 99.6 / 98.5
#:     0.150%  ->  98.3 / 97.1 / 93.6
#:     0.175%  ->  91.7 / 87.6 / 79.6
#: 0.175% collapses on the pessimistic leg; 0.15% does not. `rho` 0.58 is TAIL-IMPLIED and has
#: never been measured on live fills (`matched_fills` is still 0), and correlation error is what
#: larger size punishes hardest -- which is the whole reason the ceiling is here and not higher.
RISK_FRAC = 0.0015


def _load_survivors() -> list[dict[str, Any]]:
    doc = json.loads(SURVIVORS.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for key, val in (doc.get("survivors") or {}).items():
        spec = val.get("shadow_spec") or {}
        sym = str(spec.get("symbol") or val.get("sym") or "").upper()
        fam = str(spec.get("family") or "")
        if not sym or not fam:
            continue
        # A BANNED FAMILY IS NOT IN THE E8 BOOK EITHER (2026-09-16): the same policy file the
        # MT5 roster reads; the executor closes what such a sleeve still holds.
        if _family_banned(fam):
            continue
        rows.append({
            "key": key, "symbol": sym, "family": fam,
            "selector": spec.get("selector") or "asia",
            "params": {k: v for k, v in spec.items()
                       if k not in ("symbol", "family", "selector", "is_universe", "hunt")},
            "ev": ((val.get("gates") or {}).get("expected_value") or {}).get("ev"),
            # THE COST-STRESSED EXPECTANCY IS WHAT THE GROWTH SCORE RANKS ON, not `ev`.
            # `stress_costs.exp_x3` is the same cell replayed at THREE TIMES the modelled cost,
            # and it is the gate that separates the yen crosses from each other: CADJPY falls
            # 0.1631 -> 0.0624 (a 62% haircut) where USDJPY falls 0.1586 -> 0.0798 (48%), so on
            # raw `ev` they are a dead heat and on cost robustness they are not close.
            "exp_x3": ((val.get("gates") or {}).get("stress_costs") or {}).get("exp_x3"),
            "lockbox": ((val.get("gates") or {}).get("lockbox") or {}).get("lockbox_sharpe"),
            "days": val.get("days"),
            "n_trials": ((val.get("gates") or {}).get("deflated_sharpe") or {}).get("n_trials"),
        })
    return rows


#: Instruments that share a leg move together, so they are one bet wearing several names.
#: MEASURED (principal, 2026-09-24): EURJPY against GBPJPY is +0.891, and the four yen crosses
#: together are worth barely two independent bets; XAUUSD against the same block is -0.117, which
#: is why gold plus ONE yen cross is diversification and gold plus four is not.
#:
#: ONLY THE YEN BLOCK IS LISTED, AND THAT IS THE POINT. The book also holds three CHF crosses on
#: `overnight_gap_decay` (GBPCHF, AUDCHF, CADCHF) which are very likely the same story -- but the
#: desk has MEASURED the yen correlation and has not measured that one, and a block cut on an
#: assumed correlation would be exactly the un-evidenced shrink Growth Governance Rule 1 refuses.
#: It is published in the report as `unmeasured_blocks` instead, so it is visible rather than
#: quietly acted on. Add a block here when its correlation is measured, never before.
CORRELATED_BLOCKS: dict[str, str] = {"JPY": "JPY"}


def block_of(symbol: str) -> str | None:
    """The correlation block `symbol` belongs to, or None when it is in no MEASURED block."""
    sym = symbol.upper()
    for leg, name in CORRELATED_BLOCKS.items():
        # The leg must be one of the two sides of a 6-character FX pair, not a substring of a
        # longer instrument name, or an index whose ticker happens to contain the letters would
        # be swept into a currency block it has nothing to do with.
        if len(sym) == 6 and leg in (sym[:3], sym[3:]):
            return name
    return None


#: Per-cell measured distribution: n, win_rate, exp_r, profit_factor, max_dd_r for every
#: (symbol, family, params) the external backtest ran. ~2,100 trades per cell.
BACKTEST = DESK / "data" / "hypotheses" / "external_backtest_results.json"


def _measured() -> dict[tuple[str, str, float, float], dict[str, Any]]:
    """(symbol, family, rr, wait_bars) -> the backtest's measured summary for that cell."""
    try:
        doc = json.loads(BACKTEST.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if isinstance(doc, dict):
        doc = doc.get("results") or doc.get("rows") or list(doc.values())
    out: dict[tuple[str, str, float, float], dict[str, Any]] = {}
    for r in doc if isinstance(doc, list) else []:
        if not isinstance(r, dict):
            continue
        prm = r.get("params") or {}
        rr, wb = prm.get("rr"), prm.get("wait_bars")
        if rr is None or wb is None:
            continue
        try:
            k = (str(r.get("symbol") or "").upper(), str(r.get("family") or ""),
                 float(rr), float(wb))
        except (TypeError, ValueError):
            continue
        out[k] = r
    return out


def growth_score(row: Mapping[str, Any], risk_frac: float = 0.0) -> float | None:
    """E[log W] per trade for this certificate at `risk_frac`, or None if it cannot be derived.

    WHY NOT `ev` (principal, 2026-09-24): "add best MAXIMUM GROWTH yen one". Mean R and log-wealth
    growth rank differently, because log punishes a drawdown harder than it rewards the same-sized
    gain -- so a cell can carry the better mean R and compound more slowly.

    THE PAYOFF IS MEASURED, NOT ASSUMED, AND THE FIRST VERSION OF THIS FUNCTION ASSUMED IT WRONG.
    It modelled a `session_range_breakout` position as resolving at its rr target or its -1R stop
    and backed the win rate out as (e + 1) / (rr + 1), which put USDJPY rr=2.0 at 36.0%. The
    shadow ledgers refute that: every row exits on `reason: "ttl"`, at whatever R the clock finds,
    and the measured win rate is 53.7%. So the distribution is fitted to THREE measured moments
    from `external_backtest_results.json` -- win_rate, exp_r and profit_factor -- which determines
    a two-point payoff exactly:

        (1-p) * mean_loss = exp_r / (PF - 1)        p * mean_win = PF * exp_r / (PF - 1)

    then scaled to the cell's 3x-cost-stressed expectancy, because the cost charged against these
    cells has been corrected repeatedly and the stressed number is the one that survives being
    wrong again. Growth is  p*ln(1 + f*mean_win) + (1-p)*ln(1 - f*mean_loss).

    Returns None rather than a guess whenever any input is missing: absence is never scored as
    zero, which would silently rank an unmeasured cell last instead of leaving it unjudged.
    """
    f = risk_frac or RISK_FRAC
    prm = (row.get("params") or {}).get("params") or {}
    rr, wb = prm.get("rr"), prm.get("wait_bars")
    e3, ev = row.get("exp_x3"), row.get("ev")
    if rr is None or wb is None or e3 is None or not ev or not (0.0 < f < 1.0):
        return None
    try:
        m = _measured().get((str(row.get("symbol") or "").upper(), str(row.get("family") or ""),
                             float(rr), float(wb)))
    except (TypeError, ValueError):
        return None
    if not m:
        return None
    p, exp_r, pf = m.get("win_rate"), m.get("exp_r"), m.get("profit_factor")
    if p is None or exp_r is None or pf is None:
        return None
    p, exp_r, pf = float(p), float(exp_r), float(pf)
    if not (0.0 < p < 1.0) or pf <= 1.0 or exp_r <= 0:
        return None
    mean_loss = (exp_r / (pf - 1.0)) / (1.0 - p)
    mean_win = (pf * exp_r / (pf - 1.0)) / p
    # Charge the cost stress to the win side: a cost is paid on every trade, so a heavier cost
    # shows up as a smaller average win against an unchanged stop.
    mean_win -= (1.0 - float(e3) / float(ev)) * exp_r / p
    if mean_win <= 0 or f * mean_loss >= 1.0:
        return None
    return p * math.log(1.0 + f * mean_win) + (1.0 - p) * math.log(1.0 - f * mean_loss)


def select(tradeable: set[str] | None = None, max_sleeves: int = MAX_SLEEVES) -> dict[str, Any]:
    """The book, plus everything refused and why. An absence here is always named (L1.28a)."""
    rows = _load_survivors()
    blocked = []
    live = []
    for r in rows:
        if tradeable is not None and r["symbol"] not in tradeable:
            blocked.append({**r, "why": "not listed by the venue"})
        else:
            live.append(r)

    # one row per (mechanism, symbol): the best ev wins, the rest are named as duplicates
    # THE CHART IS PART OF THE IDENTITY (fixed 2026-09-14).
    #
    # This keyed on (mechanism, symbol) alone, so a session_range_breakout on M15 and its H1
    # sibling were ONE row and the later one was discarded as a duplicate. That was correct while
    # H1 was the only chart the desk collected -- two certificates differing in nothing but a
    # parameter hash really are one bet with two names -- and it becomes wrong the moment the
    # collector writes M30/M15/M5/M1: an M15 breakout reads different bars, sets a different stop
    # and fills at different times from the H1 one.
    #
    # IT WOULD HAVE CANCELLED THE DIVERSITY IT WAS MEANT TO ENFORCE, silently. The measured case
    # for collecting intraday at all is that rho falls from 0.58 toward ~0.29 as charts are added,
    # which on the barrier is worth four days AND takes daily-breach risk from 1.8% to 1.1%.
    # Collapsing the charts back into one row would have kept the book at 20 H1 sleeves while the
    # report cheerfully counted the rest as duplicates.
    #
    # A DIFFERENT CHART IS NOT A FULLY INDEPENDENT BET and this does not pretend otherwise: the
    # round-robin below still spreads across MECHANISMS first, so charts of one family can only
    # fill slots the other mechanisms have not claimed. The chart widens the identity; it does not
    # promote a family.
    def _tf(row: dict[str, Any]) -> str:
        return str((row.get("params") or {}).get("timeframe") or "H1").upper()

    # WITHIN A (mechanism, symbol, chart), GROWTH PICKS THE SURVIVOR, not `ev`.
    #
    # THIS ORDERING IS LOAD-BEARING AND IT SILENTLY PICKED THE WRONG CELL WHEN IT RANKED ON `ev`.
    # USDJPY's highest-`ev` certificate is the UNSUFFIXED `external.USDJPY.session_range_breakout`
    # (0.1641), which records no rr and no wait_bars -- so it cannot be scored for growth at all,
    # and it is a weaker identity besides (the gateway's own note: "PARAMS ARE PART OF THE
    # IDENTITY. Without them the spec says only 'XAUUSD asia'"). Taking it here left USDJPY
    # unscorable, so the correlation rule below could not rank it, and the JPY slot went to
    # EURJPY -- the third-best cross by growth -- while the best one was discarded as a duplicate.
    # Ranking on growth makes the parameterised rr=2.5 cell the survivor and the order comes out
    # right. `ev` remains the tiebreak so a family with no measured distribution is still ordered.
    def _rank(r: dict[str, Any]) -> tuple[float, float]:
        g = growth_score(r)
        return (-9.0 if g is None else g, r["ev"] or -9)

    best: dict[tuple[str, str, str], dict[str, Any]] = {}
    dupes = []
    for r in sorted(live, key=lambda x: (-_rank(x)[0], -_rank(x)[1])):
        k = (r["family"], r["symbol"], _tf(r))
        if k in best:
            dupes.append({**r, "why": f"duplicate of {best[k]['key']} "
                                      "on the same mechanism+symbol+chart"})
            continue
        best[k] = r

    # ONE ROW PER (mechanism, CORRELATION BLOCK), and the survivor is chosen on GROWTH.
    #
    # Rule 3 above ("one row per mechanism+symbol") catches two certificates on the same
    # instrument. It does not catch four DIFFERENT instruments that are the same bet: measured
    # 2026-09-24, this book held USDJPY, CADJPY, EURJPY and GBPJPY on `session_range_breakout`
    # at once, and EURJPY against GBPJPY is +0.891. That is four of eight slots spent on about
    # two independent bets, on an account whose pass probability is driven by how many
    # INDEPENDENT bets it holds -- the exact failure `orthogonality.py` measures and the reason
    # the principal's order was "add ONE yen cross, not all four".
    #
    # IT DOES SHRINK NOMINAL GROSS, AND THAT IS REPORTED RATHER THAN DRESSED UP. The round-robin
    # below is CERTIFICATE-limited, not slot-limited -- the book fills 6-8 of its 24 slots because
    # that is how many distinct certificates the venue lists, so dropping three rows frees three
    # slots that nothing refills. Measured here: n_selected 8 -> 6 and gross 1.20% -> 0.90%.
    #
    # WHAT IS NOT LOST IS THE PART THAT WAS DOING WORK. At the measured rho of 0.891,
    # `libs/validation/effective_sample.cross_dependence_deflator(4, 0.891) = 0.273`, so the four
    # yen rows were carrying about 1.09 independent bets between them; one row carries 1.00. The
    # book gives up 25% of its NOMINAL exposure to give up 8% of its EFFECTIVE breadth.
    #
    # THIS IS THE PRINCIPAL'S OWN INSTRUCTION ("add ONE yen cross, not all four", 2026-09-24),
    # the same class of act as the `discovered` family ban -- not a session lowering risk by fiat,
    # which the standing order forbids. Redeploying the freed 0.30% is a change to `RISK_FRAC`,
    # which is the principal's decision recorded in docs/PROP_FIRM_E8.md and is NOT touched here.
    blocked_by_corr = []
    per_block: dict[tuple[str, str], dict[str, Any]] = {}
    survivors: list[dict[str, Any]] = []
    for r in best.values():
        blk = block_of(r["symbol"])
        if blk is None:
            survivors.append(r)
            continue
        k2 = (r["family"], blk)
        held = per_block.get(k2)
        if held is None:
            per_block[k2] = r
            continue
        # Growth decides, and a cell that cannot be scored never displaces one that can.
        g_new, g_held = growth_score(r), growth_score(held)
        if g_new is not None and (g_held is None or g_new > g_held):
            per_block[k2] = r
            blocked_by_corr.append({**held, "why": f"{blk} block already represented on "
                                                   f"{r['family']} by {r['key']} (higher growth)"})
        else:
            blocked_by_corr.append({**r, "why": f"{blk} block already represented on "
                                                f"{r['family']} by {held['key']} (higher growth)"})
    survivors.extend(per_block.values())

    # round-robin across mechanisms, best-first within each
    by_fam: dict[str, list[dict[str, Any]]] = {}
    for r in survivors:
        by_fam.setdefault(r["family"], []).append(r)
    for fam in by_fam:
        by_fam[fam].sort(key=lambda x: -(x["ev"] or -9))
    chosen: list[dict[str, Any]] = []
    i = 0
    while len(chosen) < max_sleeves:
        took = False
        for fam in sorted(by_fam, key=lambda f: -len(by_fam[f])):
            if i < len(by_fam[fam]) and len(chosen) < max_sleeves:
                chosen.append(by_fam[fam][i])
                took = True
        if not took:
            break
        i += 1

    fams: dict[str, int] = {}
    for r in chosen:
        fams[r["family"]] = fams.get(r["family"], 0) + 1
    evs = [r["ev"] for r in chosen if r["ev"] is not None]
    return {
        "generated_utc": datetime.now(UTC).isoformat(),
        "risk_frac": RISK_FRAC,
        "max_sleeves": max_sleeves,
        "n_certified": len(rows),
        "n_tradeable": len(live),
        "n_blocked_by_venue": len(blocked),
        "n_duplicate_mechanism_symbol": len(dupes),
        "n_blocked_by_correlation": len(blocked_by_corr),
        "blocked_by_correlation": blocked_by_corr,
        #: Concentrations this rule can SEE but has not measured, so has not acted on (L1.28a:
        #: unmeasured is a verdict, not a zero). Published so the next correlation measurement
        #: has a named target rather than being rediscovered.
        "unmeasured_blocks": sorted({
            f"{fam}:{leg}" for fam, leg in {
                (r["family"], r["symbol"][3:]) for r in chosen if len(r["symbol"]) == 6}
            if block_of("XXX" + leg) is None
            and sum(1 for x in chosen
                    if x["family"] == fam and len(x["symbol"]) == 6 and x["symbol"][3:] == leg) > 1
        }),
        "by_chart": {tf: sum(1 for x in chosen if str((x.get("params") or {}).get(
            "timeframe") or "H1").upper() == tf)
            for tf in sorted({str((x.get("params") or {}).get("timeframe") or "H1").upper()
                              for x in chosen})},
        "n_selected": len(chosen),
        "gross_exposure_if_all_fire": round(len(chosen) * RISK_FRAC, 5),
        "by_mechanism": fams,
        "mean_ev": None if not evs else round(sum(evs) / len(evs), 4),
        "sleeves": chosen,
        "blocked_by_venue": sorted({r["symbol"] for r in blocked}),
        "rule": ("venue-listed first, then diversity across mechanisms, then expectancy within "
                 "one; one row per (mechanism, symbol) because two certificates on the same "
                 "mechanism and instrument are one bet with two names"),
    }


def write(doc: dict[str, Any], path: Path = OUT) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--no-live-venue", action="store_true",
                    help="do NOT ask the venue what it lists. The book is then written only if a "
                         "previously measured catalogue is on disk; with neither, nothing is "
                         "written, because an unfiltered book is not a safer book.")
    args = ap.parse_args(argv)

    # RULE 1 OF THIS FILE WAS OPTIONAL, AND OFF BY DEFAULT (fixed 2026-09-14).
    #
    # The docstring's first selection rule is THE VENUE MUST LIST IT. The implementation asked
    # for the catalogue only under `--live-venue`, and the scheduled task runs
    # `python e8_book.py` with no arguments -- so `tradeable` was None, `select()` reads None as
    # "apply no filter", and the rule that leads the file was never applied on any scheduled
    # pass. `n_blocked_by_venue` then published 0, which is not "nothing was blocked" but "I did
    # not look".
    #
    # MEASURED ON THE LIVE $100k ACCOUNT TONIGHT: of the 24 sleeves in the book, EIGHT were Scandi
    # and EM crosses -- EURNOK, CHFNOK, GBPMXN and siblings -- that E8's 46-instrument catalogue
    # does not carry. The executor caught every one and refused it as NOT_LISTED, so no bad order
    # was sent; the cost was worse than an error. A third of the book's slots were spent on
    # instruments that cannot trade, on an account whose pass probability is a function of how
    # many INDEPENDENT mechanisms are actually running, with a five-day hard speed floor and a
    # right tail that is confiscated at 2% a day. Those eight slots were unavailable to the
    # certified sleeves that E8 does list.
    #
    # ABSENCE IS NOT PERMISSION (LAWS). `None` meaning "no filter" is that violation in one
    # sentinel: the failure to measure and the decision not to restrict were the same value.
    # They are now different values and the failure fails CLOSED.
    tradeable: set[str] | None = None
    source = ""
    if not args.no_live_venue:
        try:
            from prop.tradelocker_venue import TradeLockerVenue
            tradeable = set(TradeLockerVenue().connect()._by_key)
            source = f"live venue ({len(tradeable)} instruments)"
            _cache_catalogue(tradeable)
        except Exception as exc:
            print(f"live venue UNREACHABLE ({type(exc).__name__}: {exc}); falling back to the "
                  f"last measured catalogue")
    if tradeable is None:
        cached = _cached_catalogue()
        if cached:
            tradeable, source = cached, f"cached catalogue ({len(cached)} instruments)"

    if tradeable is None:
        # NOT AN ERROR TO SWALLOW. Writing an unfiltered book here would republish the exact
        # defect this fix removes, and silently: the artifact would look complete. Keeping the
        # last good book is the conservative act -- it was written when the catalogue WAS known.
        print("REFUSING to write the book: the venue's catalogue is unknown and no cached one "
              "exists, so rule 1 (the venue must list it) cannot be applied. The previous book "
              "stands.")
        return 1

    doc = select(tradeable)
    doc["catalogue_source"] = source
    write(doc)
    print(f"E8 book: {doc['n_selected']} sleeve(s) at {RISK_FRAC:.2%} "
          f"= {doc['gross_exposure_if_all_fire']:.2%} gross if every one fires")
    print(f"  catalogue: {source}")
    print(f"  by mechanism: {doc['by_mechanism']}")
    print(f"  mean ev {doc['mean_ev']} | {doc['n_blocked_by_venue']} blocked by the venue, "
          f"{doc['n_duplicate_mechanism_symbol']} duplicate (mechanism, symbol)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
