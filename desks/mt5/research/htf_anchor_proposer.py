"""Mint the video-derived anchor/exit mechanism as ordinary docket cells, at legal breadth.

WHAT THIS CONVERTS (RESEARCH.md §33). A public video walkthrough seen 2026-09-23 in which an
agent built a trend follower and searched about 200 variations. Four parts: a higher-timeframe
trend ANCHOR gating a lower-timeframe entry, an ATR stop, an exit when the anchor FLIPS, and an
exit when current ATR exceeds a multiple of the ATR observed AT ENTRY. The author said he had
never seen the last one before; neither had this desk.

THE HONEST PRIOR ON THE CLAIM, written into every row's mechanism note so it travels with the
cell and cannot be lost between here and a certificate. The video's Sharpe of 1.87 was the
MAXIMUM over ~200 searched variations with NO multiplicity charge applied, on ONE single-name
equity (Apple); its own Monte Carlo put the MEDIAN of that search near 1.30. A maximum over 200
trials estimates nothing. The desk's deflated-Sharpe charge already sits at n_trials=597 with
sr0=0.3786 and most cells are expected to fail; that is the bar this claim meets like any other.

THE TWO LANES ARE OBEYED AT THE DOOR. Apple -- the video's own instrument -- is a single-name
equity, traded here on news and never hunted for statistical hypotheses, so it is OUT OF SCOPE
for this conversion and `proposer_common.donate` refuses it at the docket's door as it would
refuse any equity row. The mechanism is minted on the hypothesis lane only: FX majors, crosses
and exotics, metals, energy, soft commodities, indices, bonds and Fusion's crypto CFDs.

NO BORROWED CONSTANT. The 4x multiple is swept, never assumed, and the video's 4H-over-1H is the
single point (chart=H1, anchor_mult=4) of a swept speed RATIO. Measured before minting (see
`data/hypotheses/exit_operator_bind_census.json`): at 4x the rule shortens 2.1% of a 120-bar hold
and 0.05% of a 12-bar hold on EURUSD H1 -- ATR does not quadruple inside twelve hours of FX. So
the video's own constant is nearly INERT on this desk's instruments, and minting it blindly would
have produced thousands of cells identical to their control arms.

WHY AN INERT CELL IS REFUSED, and why that is not a source brake. `LAWS §5e` forbids brakes on
DISCOVERY -- what may be mined, ingested, represented or tested. This refuses none of that: the
mechanism is mined, represented and tested in full. What it refuses to mint is a cell whose
operator provably changes NOTHING about the trades -- an exact duplicate of a candidate the
docket already holds, differing only in a parameter that never binds. Minting it would spend a
multiplicity charge on a question already being asked, raising the bar for every other cell on
the desk in exchange for no information. The bind census is published either way, so the inert
region is recorded as measured negative knowledge rather than silently skipped (L1.16a).

WHAT THIS COSTS, stated because every new cell raises the bar for every other one. The count
minted is in `data/hypotheses/htf_anchor_mint.json` under `minted`, and the report names it
against the docket's size at the time, so the charge this work added to the desk's shared
family-wise error budget is a number on disk and not a claim in a report.
"""
from __future__ import annotations

import json
import sys
import time
from functools import lru_cache
from itertools import product
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
for _p in (str(BASE), str(BASE / "research"), str(BASE.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

HYP = BASE / "data" / "hypotheses"
CENSUS = HYP / "exit_operator_bind_census.json"
MINT = HYP / "htf_anchor_mint.json"
SEAT = "video_anchor_exit"

#: The charts the mechanism is minted on. Declaring `timeframe` in params SUPPRESSES the
#: compiler's 16-way (chart x session) fan-out, which is deliberate: this conversion declares its
#: own breadth and does not want it silently multiplied by sixteen on top.
CHARTS: tuple[str, ...] = ("H1", "H4", "D1")

#: Arm A. The mechanism's own degrees of freedom. `(0.0, False)` is the CONTROL ARM -- the anchor
#: gate and ATR stop with the desk's ordinary stop/target/time exit -- without which the two exit
#: operators have nothing to be measured against. `entry_fast` and `stop_atr` are ordinary
#: nuisance parameters the desk's breadth machinery already sweeps everywhere; fixing them here
#: keeps the charge proportional to the NEW question instead of multiplying it by nine.
ANCHOR_MULTS: tuple[int, ...] = (3, 4, 6)
EXIT_ARMS: tuple[tuple[float, bool], ...] = (
    (0.0, False),    # control: no operator at all
    (1.25, False), (1.5, False), (2.0, False), (4.0, False),   # 4.0 is the video's, unprivileged
    (0.0, True),     # anchor-flip exit alone
    (1.5, True),     # both operators
)

#: Arm B. The multiples the operator is composed onto EXISTING entries with. Kept short on
#: purpose: the composition is 20-odd base families wide already, and the desk pays for width in
#: both directions at once.
COMPOSE_MULTS: tuple[float, ...] = (1.25, 1.5, 2.0)

#: A cell is minted only where the operator shortens at least this share of the base family's
#: holds on the census sample. Below it the operated cell and the base cell are the same trades.
BIND_FLOOR = 0.02

#: Symbols the bind census is measured on -- one liquid major, one cross, one exotic, one metal,
#: one index, one energy. Breadth of MINTING is the whole legal universe; breadth of MEASURING
#: the bind rate is a sample, because the bind rate is a property of the rule and the chart far
#: more than of the instrument, and an hourly leg has a budget.
CENSUS_SYMBOLS: tuple[str, ...] = ("EURUSD", "GBPJPY", "USDMXN", "XAUUSD", "US500", "USOUSD")

MECHANISM = (
    "a trend anchor computed on a chart anchor_mult times slower than the entry chart PERMITS "
    "(does not trigger) the entry; the position goes flat the moment the anchor flips against it, "
    "and/or when current ATR exceeds expansion_mult times the ATR printed at entry -- the claim "
    "being that a regime whose volatility has multiplied since entry is no longer the regime the "
    "trade was opened into. PRIOR: converted from a public video whose reported Sharpe 1.87 was "
    "the MAXIMUM of ~200 searched variations with no multiplicity charge, on one single-name "
    "equity; its own Monte Carlo median was ~1.30. A public claim is a hypothesis, never evidence."
)


def _legal_symbols() -> list[str]:
    """Hypothesis-lane symbols with bars. The two-lane law applied at the source, not downstream."""
    import universe_policy as policy
    try:
        meta = json.loads((BASE / "data" / "universe" / "universe.json").read_text("utf-8"))
    except (OSError, ValueError):
        return []
    src = meta.get("symbols", meta)
    names = list(src) if isinstance(src, dict) else [r.get("symbol") for r in src]
    have = {p.stem.rpartition("_")[0] for p in (BASE / "data" / "universe").glob("*_H1.parquet")}
    return sorted(s for s in names if s and s in have and policy.may_hypothesise(s))


@lru_cache(maxsize=32)
def _bars(sym: str, chart: str):
    """CACHED, because the census asks ~50 families the same question about the same frame.
    Re-reading a 54,000-row parquet once per family is most of the leg's wall clock."""
    import pandas as pd
    p = BASE / "data" / "universe" / f"{sym}_{chart}.parquet"
    if not p.exists():
        return None
    try:
        return pd.read_parquet(p)
    except Exception:
        return None


#: How many (chart, family) pairs one pass measures. THE CENSUS IS BOUNDED AND ROTATING, NOT
#: QUEUED (LAWS: nothing is queued; leftovers go FIRST next pass with their age published). The
#: first version of this walked every wrappable family on every chart in one pass and did not
#: finish inside twenty minutes on an 8 GB box already running nine python processes -- an
#: unbounded leg is an hourly leg that never lands, which is the same defect as an unwired one.
CENSUS_PAIRS_PER_PASS = 12


def bind_census(budget_s: float = 240.0) -> dict[str, Any]:
    """How often the operator actually shortens a hold, per (base_family, chart, multiple).

    PUBLISHED WHETHER IT BINDS OR NOT. A combination measured inert is negative knowledge with a
    named re-opening condition (a family whose holds get longer, or a chart with more volatile
    ATR), not a combination that was never looked at -- and the difference between those two is
    exactly what L1.28a says must never be collapsed.

    ROTATING AND ACCUMULATING. Each pass measures `CENSUS_PAIRS_PER_PASS` (chart, family) pairs
    starting from the cursor the last pass left, merges them into the readings already on disk,
    and publishes how many pairs are still unmeasured and how old the oldest reading is. So a
    pass always lands an artifact, coverage ratchets up, and `unmeasured` is a verdict rather
    than a silence.
    """
    from mt5desk.exit_operators import apply_exit_operators, exit_reasons
    from mt5desk.families import get_family_func, live_family_names
    from mt5desk.family_exit_operated import wrappable

    try:
        prev = json.loads(CENSUS.read_text("utf-8"))
    except (OSError, ValueError):
        prev = {}
    seen: dict[str, dict[str, Any]] = {f"{r['chart']}|{r['family']}|{r['expansion_mult']}": r
                                       for r in prev.get("rows", [])}

    bases = sorted(f for f in live_family_names() if wrappable(f) and f != "exit_operated")
    pairs = [(c, f) for c in CHARTS for f in bases]
    cursor = int(prev.get("cursor") or 0) % max(1, len(pairs))
    t0 = time.time()
    done = 0
    # THE BASE FAMILY IS RUN ONCE PER (chart, family), NOT ONCE PER MULTIPLE. Going through
    # `family_exit_operated` here would rebuild the base signals for every point of the grid --
    # four passes over the same bars to answer one question about the operator, and the operator
    # is the only thing that differs between them. `apply_exit_operators` is the same code the
    # wrapper calls; only the rebuild is skipped.
    while done < CENSUS_PAIRS_PER_PASS and time.time() - t0 < budget_s and pairs:
        chart, fam = pairs[cursor % len(pairs)]
        cursor = (cursor + 1) % len(pairs)
        done += 1
        fn = get_family_func(fam)
        if fn is None:
            continue
        for sym in CENSUS_SYMBOLS:
            d = _bars(sym, chart)
            if d is None or len(d) < 500:
                continue
            try:
                base = list(fn(d) or [])
            except Exception:
                break
            if len(base) < 20:
                break
            for mult in COMPOSE_MULTS:
                try:
                    out = apply_exit_operators(d, base, expansion_mult=mult)
                except Exception:
                    continue
                r = exit_reasons(base, out)
                seen[f"{chart}|{fam}|{mult}"] = {
                    "chart": chart, "family": fam, "symbol": sym, "expansion_mult": mult,
                    "n": r["signals"], "shortened": r["shortened"],
                    "bind_share": round(r["shortened_share"], 6),
                    "median_ttl_before": r["median_ttl_before"],
                    "median_ttl_after": r["median_ttl_after"],
                    "measured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
            break   # one symbol per (chart, family) is the census budget; see the docstring

    rows = sorted(seen.values(), key=lambda r: (r["chart"], r["family"], r["expansion_mult"]))
    binding = sorted({(r["chart"], r["family"], r["expansion_mult"])
                      for r in rows if r["bind_share"] >= BIND_FLOOR})
    measured_pairs = {(r["chart"], r["family"]) for r in rows}
    doc = {
        "measured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "bind_floor": BIND_FLOOR,
        "cursor": cursor,
        "pairs_total": len(pairs),
        "pairs_measured": len(measured_pairs),
        "pairs_unmeasured": len(pairs) - len(measured_pairs),
        "pairs_this_pass": done,
        "rows": rows,
        "binding": [{"chart": c, "family": f, "expansion_mult": m} for c, f, m in binding],
        "inert": [{"chart": r["chart"], "family": r["family"],
                   "expansion_mult": r["expansion_mult"], "bind_share": r["bind_share"]}
                  for r in rows if r["bind_share"] < BIND_FLOOR],
        "rule": ("an operator that shortens nothing makes the operated cell an exact duplicate of "
                 "the base cell; minting it spends a multiplicity charge on a question already "
                 "being asked. The inert region is RECORDED, never silently skipped, and "
                 "pairs_unmeasured is UNMEASURED -- a verdict, not a zero."),
    }
    CENSUS.parent.mkdir(parents=True, exist_ok=True)
    CENSUS.write_text(json.dumps(doc, indent=1), "utf-8")
    return doc


def _row(sym: str, family: str, params: dict[str, Any], note: str) -> dict[str, Any]:
    return {
        "kind": "hypothesis",
        "family": family,
        "symbols": [sym],
        "symbol": sym,
        "params": params,
        "mechanism": MECHANISM,
        "mechanism_status": "NAMED",
        "mechanism_note": note,
        "title": f"{family} on {sym} {params.get('timeframe', 'H1')} -- video-derived anchor/exit",
        "url": "",
        "source": SEAT,
        "event_time": None,
    }


#: How many rows one pass donates. NOT A BRAKE ON BREADTH -- the full grid is minted, a bounded
#: slice per pass, resuming where the last pass stopped, so coverage ratchets to the whole of it.
#: MEASURED, which is why the number is here at all: the first pass handed `donate` 10,005 rows
#: and `proposer_common._record_in_registry` was still writing them FORTY MINUTES later at roughly
#: four rows a second, which is longer than the hour the leg belongs to. An hourly organ that
#: cannot finish inside its hour lands no artifact, and an organ that lands no artifact is
#: indistinguishable from one that is not wired (III.16).
MINT_ROWS_PER_PASS = 1200
CURSOR = HYP / "htf_anchor_cursor.json"


def build_candidates(census: dict[str, Any], symbols: list[str]) -> list[dict[str, Any]]:
    """Arm A across the whole legal universe; arm B only where the operator was measured to bind."""
    out: list[dict[str, Any]] = []
    for sym, chart in product(symbols, CHARTS):
        for amult, (xmult, flip) in product(ANCHOR_MULTS, EXIT_ARMS):
            arm = ("control" if (xmult <= 0 and not flip)
                   else "flip" if xmult <= 0
                   else f"vol{xmult}" + ("+flip" if flip else ""))
            out.append(_row(sym, "htf_anchor_trend", {
                "timeframe": chart, "anchor_mult": amult,
                "expansion_mult": xmult, "exit_on_anchor_flip": flip,
            }, f"arm={arm}; anchor is {amult}x the entry chart"))
    for b in census.get("binding", []):
        fam, chart, mult = b["family"], b["chart"], b["expansion_mult"]
        for sym in symbols:
            out.append(_row(sym, "exit_operated", {
                "timeframe": chart, "base_family": fam, "base_params": {},
                "expansion_mult": mult, "exit_on_anchor_flip": False,
            }, f"exit operator composed onto {fam}; measured to bind on this chart"))
    return out


def main(argv: list[str] | None = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    from proposer_common import donate, donation_counts

    symbols = _legal_symbols()
    if not symbols:
        print("htf_anchor_proposer: no hypothesis-lane symbols with bars")
        return 0
    census = bind_census(budget_s=float(next((a.split("=")[1] for a in argv
                                              if a.startswith("--census-budget=")), 240.0)))
    every = build_candidates(census, symbols)
    # THE SLICE IS ROTATING, NOT A QUEUE. Leftovers are not parked for someone to drain later --
    # the next pass starts exactly where this one stopped and the backlog's size and age are
    # published below, which is what `scripts/check_no_queues.py` asks of every organ.
    try:
        start = int(json.loads(CURSOR.read_text("utf-8")).get("at") or 0)
    except (OSError, ValueError):
        start = 0
    start = start % max(1, len(every))
    cands = every[start:start + MINT_ROWS_PER_PASS]
    if len(cands) < MINT_ROWS_PER_PASS:
        cands += every[:MINT_ROWS_PER_PASS - len(cands)]     # wrap, so the grid is a ring
    nxt = (start + len(cands)) % max(1, len(every))
    CURSOR.parent.mkdir(parents=True, exist_ok=True)
    CURSOR.write_text(json.dumps({"at": nxt, "of": len(every),
                                  "written": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                           time.gmtime())}), "utf-8")
    path = donate(source=SEAT, candidates=cands, tests_run=len(census.get("rows", [])))
    counts = donation_counts()
    doc = {
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "symbols": len(symbols), "charts": list(CHARTS),
        "arm_a_grid": {"anchor_mults": list(ANCHOR_MULTS),
                       "exit_arms": [[m, f] for m, f in EXIT_ARMS]},
        "arm_b_binding": len(census.get("binding", [])),
        "grid_total": len(every), "cursor_from": start, "cursor_to": nxt,
        "passes_to_cover_grid": -(-len(every) // MINT_ROWS_PER_PASS),
        "built": len(cands), "minted": counts.get("donated", 0),
        "refused_wrong_lane": counts.get("refused_wrong_lane", 0),
        "refused_unstamped": counts.get("refused_unstamped", 0),
        "contract": str(path) if path else None,
        "census": str(CENSUS),
        "prior": ("the source video reported Sharpe 1.87 as the MAXIMUM of ~200 searched "
                  "variations with no multiplicity charge, on one single-name equity; its own "
                  "Monte Carlo median was ~1.30. Recorded so the 1.87 is never read as evidence."),
        "cost": ("every cell minted here raises the multiple-testing bar for every other cell on "
                 "the desk; `minted` is that charge and it is paid out of the same family-wise "
                 "error budget the deflated Sharpe charges per sweep. MEASURED on the first "
                 "batch (EURUSD, reports/reproduction_20260923T205343.json): 63 cells charged "
                 "n_trials=109 at sr0=0.3122, and the sweep's own effective-trials measure "
                 "priced those 63 as 2.895 INDEPENDENT trials -- 69 clone pairs. So most of this "
                 "grid's width is redundancy, which the judge already discounts and the docket "
                 "does not: the cells still cost build time even where they cost little alpha."),
    }
    MINT.parent.mkdir(parents=True, exist_ok=True)
    MINT.write_text(json.dumps(doc, indent=1), "utf-8")
    print(f"htf_anchor_proposer: built {len(cands)} -> minted {doc['minted']} "
          f"(wrong lane {doc['refused_wrong_lane']}, unstamped {doc['refused_unstamped']}); "
          f"arm B binding combos {doc['arm_b_binding']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
