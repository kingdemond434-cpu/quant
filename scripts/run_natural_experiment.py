"""THE DESK'S FIRST CAUSAL STUDY -- a difference-in-differences on dated token unlocks (R0207).

Stage A. ZERO promotion authority: this earns a pre-registered forward clock at most, never a cent.

=================================================================================================
WHY THIS COHORT AND NOT THE ONE THE ROW ASKED FOR
=================================================================================================
R0207 specifies "funding-interval or leverage-cap change -> basis/OI/realised-vol vs matched
controls" and names `data/exchange_announcements.jsonl` as the feed already being collected. THAT
PREMISE IS FALSE AT THE DATA LAYER and it is stated here rather than worked around: that file
holds 232 rows from `cointelegraph` (96), `coindesk` (92), `defillama_hacks` (25) and `okx` (19).
It is a NEWS feed. Across all 232 titles there are 6 listing mentions, 2 delisting mentions and
ZERO funding-interval, margin-tier, leverage-cap or fee-schedule rule changes; only 43 rows carry
a symbol at all. No venue rule-change calendar exists anywhere on this disk -- `cost_model.json`
is a current snapshot with no dates, `screen_funding_interval_mismatch.json` is a 2026-08-05
snapshot with no transition dates, and a grep for margin_tier/leverageBracket/risk_limit/fee_tier
across `data/*.json*` returns nothing dated.

So the CAPABILITY GAP the row identifies is real and is closed by `libs.research.natural_
experiment`; the FIRST EXPERIMENT it proposes is not runnable, and substituting a better cohort is
the honest response rather than manufacturing one from a news feed.

TOKEN UNLOCKS ARE A STRICTLY BETTER FIRST EXPERIMENT, and on the row's own criterion. R0207's
stated KNOWN THREAT is that venue rule changes are ENDOGENOUS -- "venues change margin tiers
BECAUSE they see risk" -- and it asks for the endogeneity argument to be reported with the
estimate. A vesting schedule is fixed at token genesis, typically years before any outcome window,
and is published in advance. The unlock DATE cannot be a response to the returns it precedes,
because it was chosen before those returns existed. That is a stronger exogeneity argument than
anything the announcement feed could have supplied.

=================================================================================================
PRE-REGISTRATION -- every constant below is fixed BEFORE the estimate, and changing one is a diff
=================================================================================================
Sweeping windows and reporting the best is data-mining our own collector (the discipline
`listing_events.py` holds its window and direction to). DIRECTION is pre-registered DOWN: an
unlock raises circulating supply, so the predicted price effect is negative. That matters
mechanically as well as scientifically -- `event_study` is a ONE-SIDED POSITIVE test, so an
unsigned DiD would have reported NO-EFFECT on a true negative effect forever.

THE LOOK-AHEAD THAT IS DELIBERATELY NOT USED: `unlock_events.json` carries `pct_circ_now`, which
is the unlock as a share of the 2026 float applied to events back to 2016. Supply grows, so old
unlocks that were huge shares of their float record as small ones -- a look-ahead in the
CONDITIONING variable, and it fails toward a FALSE NULL, the one direction no gate here catches.
This study does not condition on intensity at all. `data/circulating_supply.jsonl`, which would
supply a dated denominator, does not exist.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from libs.ops import lawful
from libs.research.natural_experiment import (
    MIN_POST_OBS,
    MIN_PRE_OBS,
    TreatedUnit,
    difference_in_differences,
)
from libs.validation.event_study import MIN_EVENTS

ROOT = Path(__file__).resolve().parents[1]
UNLOCKS = ROOT / "data/unlock_events.json"
REPORT = ROOT / "data/natural_experiment.json"

#: Categories whose unlock is a genuine supply release to a holder who may sell. `Uncategorized`
#: (13,997 of 24,201 rows) is excluded because it is not a category -- it is a missing field, and
#: pooling it in would mix locked-staking and burn events with insider vesting.
TREATED_CATEGORIES = ("insiders", "privateSale")

#: Trading days each side of the event. PRE must clear MIN_PRE_OBS for the parallel-trends test to
#: have power; POST is short because a supply shock that takes a quarter to show up is not the
#: effect being claimed.
PRE_DAYS = 30
POST_DAYS = 5

#: Study window. Starts where the panel has real cross-sectional breadth; ends 2026-06-30 because
#: only 79 of 285 symbols run past 2026-08-01 and a thinning control set would silently change the
#: control leg's composition mid-study.
START = "2023-01-01"
END = "2026-06-30"

#: Minimum never-unlocked peers alive on a given day for that day's control mean to be usable. A
#: cross-sectional mean over 3 symbols is not a market, it is three symbols.
MIN_CONTROLS_PER_DAY = 20

#: Pre-registered sign: an unlock raises circulating supply, so price pressure is DOWN.
DIRECTION = "decrease"

#: EVERY DESIGN RUN IS A TRIAL AND ALL OF THEM ARE CHARGED. (control_mode, require_clean_pre).
#: They are not three attempts at a result -- they are one nested sequence, each fixing a named
#: defect in the one before, and the honest way to report a sequence is to report all of it. The
#: multiplicity charge is len(DESIGNS) for every one of them; quoting only the survivor would be
#: the garden of forking paths, which is what the desk's "two exit rules are two trials" rule
#: exists to stop.
DESIGNS = (
    ("never-treated", False),      # the obvious design; refused -- controls are a different
    #                                population (majors vs VC-backed alts)
    ("not-yet-treated", False),    # same population, timing varies; refused -- repeat vesting
    #                                puts a prior unlock inside almost every pre-window
    ("not-yet-treated", True),     # + clean pre-window: the contamination above removed
)

#: The argument for exogeneity. Required by the estimator, never inspected by it -- it is a claim
#: about the world and it travels with the number so a reader can reject it.
EXOGENEITY = (
    "A token's vesting schedule is fixed in its distribution contract at genesis, typically years "
    "before the outcome window, and is published in advance. The unlock DATE therefore cannot be "
    "chosen in response to the returns it precedes. The residual threat is not endogeneity of the "
    "date but ANTICIPATION: the date is public, so the effect may be priced before it arrives -- "
    "which biases toward a NULL here, not toward a false positive, and is visible as a pre-period "
    "drift the parallel-trends rail refuses on."
)


def _panel() -> pd.DataFrame:
    """Daily close panel, symbols x dates, from the bronze lake."""
    from libs.autodiscovery.crypto_adapter import crypto_symbols
    from libs.data.instruments import AssetClass, InstrumentSpec, register_instrument
    from libs.data.lake import Layer, ParquetLake
    from libs.data.timeframe import Timeframe

    lake = ParquetLake(str(ROOT / "data/lake"))
    closes: dict[str, pd.Series] = {}
    for s in crypto_symbols(Timeframe.D1):
        register_instrument(InstrumentSpec(symbol=s, asset_class=AssetClass.CRYPTO,
                                           description=s))
        df = lake.read_bars(Layer.BRONZE, s, Timeframe.D1).set_index("timestamp")
        if len(df):
            closes[s] = df["close"]
    return pd.DataFrame(closes).sort_index()


def _events() -> list[dict[str, Any]]:
    rows = json.loads(UNLOCKS.read_text("utf-8"))
    return rows if isinstance(rows, list) else list(rows.get("events", []))


def build_cohort(rets: pd.DataFrame, events: list[dict[str, Any]],
                 *, control_mode: str = "not-yet-treated",
                 require_clean_pre: bool = False) -> dict[str, Any]:
    """Assemble treated units and their matched control legs. Pure, so it is testable.

    TWO CONTROL DESIGNS, AND THE FIRST ONE IS WRONG -- kept because the desk's own record is worth
    more than a tidy file, and because the parallel-trends rail caught it rather than a reviewer.

    `never-treated` is the obvious design and the one this study ran first: controls are symbols
    that never appear in the unlock file at all. It REFUSED at a pre-period gap of t=-13.26, and
    the refusal is correct -- "never has a vesting schedule" selects majors and old chains, while
    the treated group is VC-backed alts. Those two populations differ in level AND trend for
    reasons that have nothing to do with unlocks, so a DiD between them measures the population
    difference. The rail did exactly its job: it refused a comparison that would otherwise have
    reported a confident, entirely spurious "effect".

    `not-yet-treated` is the standard fix for a staggered cohort and the default here: controls
    are drawn from the SAME population -- symbols that do have vesting schedules -- excluding any
    symbol within a treatment window of its own unlock on those days. Population is held fixed and
    only the TIMING varies, which is the variation the vesting schedule actually randomises.

    The control leg is the per-day cross-sectional mean over eligible peers alive that day.
    `natural_experiment.control_mean` is not used: it requires a rectangular peer matrix, and
    symbol liveness varies day to day, so no such matrix exists here without dropping peers.
    """
    if control_mode not in ("never-treated", "not-yet-treated"):
        raise ValueError(f"unknown control_mode {control_mode!r}")

    ever_unlocked = {str(e.get("symbol") or "") for e in events}
    lo, hi = pd.Timestamp(START, tz="UTC"), pd.Timestamp(END, tz="UTC")
    idx = rets.index

    # Every unlock date per symbol, used to blank a peer while it is itself in a window.
    unlock_days: dict[str, list[pd.Timestamp]] = defaultdict(list)
    for e in events:
        try:
            unlock_days[str(e.get("symbol") or "")].append(pd.Timestamp(str(e["date"]), tz="UTC"))
        except (KeyError, ValueError):
            continue

    if control_mode == "never-treated":
        eligible = [s for s in rets.columns if s not in ever_unlocked]
    else:
        eligible = [s for s in rets.columns if s in ever_unlocked]
    ctrl = rets[eligible]

    if control_mode == "not-yet-treated":
        # Blank each peer on the days it is itself under treatment, so a "control" is never a
        # symbol currently absorbing its own unlock. This is what makes the peers UNTREATED on
        # the days they are used, which is the only sense in which a staggered control is clean.
        mask = pd.DataFrame(True, index=ctrl.index, columns=ctrl.columns)
        span_lo, span_hi = pd.Timedelta(days=PRE_DAYS), pd.Timedelta(days=POST_DAYS)
        for sym, days in unlock_days.items():
            if sym not in mask.columns:
                continue
            for d in days:
                mask.loc[(mask.index >= d - span_lo) & (mask.index <= d + span_hi), sym] = False
        ctrl = ctrl.where(mask)

    # A day whose control mean rests on too few live peers is dropped by masking it to NaN, which
    # then propagates into the window checks below rather than being quietly averaged in.
    ctrl_mean = ctrl.mean(axis=1).where(ctrl.notna().sum(axis=1) >= MIN_CONTROLS_PER_DAY)
    # SUTVA denominator: distinct peers that actually serve as controls somewhere in the study.
    n_control_pool = int((ctrl.notna().sum(axis=0) > 0).sum())

    units: list[TreatedUnit] = []
    dropped: dict[str, int] = defaultdict(int)

    for e in events:
        sym = str(e.get("symbol") or "")
        if str(e.get("category") or "") not in TREATED_CATEGORIES:
            dropped["category"] += 1
            continue
        if sym not in rets.columns:
            dropped["symbol-not-in-panel"] += 1
            continue
        try:
            day = pd.Timestamp(str(e["date"]), tz="UTC")
        except (KeyError, ValueError):
            dropped["unparseable-date"] += 1
            continue
        if not (lo <= day <= hi):
            dropped["outside-window"] += 1
            continue

        pos = int(idx.searchsorted(day))
        if pos - PRE_DAYS < 0 or pos + POST_DAYS > len(idx):
            dropped["window-off-panel"] += 1
            continue
        # ALREADY-TREATED CONTAMINATION -- the defect the first two designs died of. These tokens
        # vest on monthly cliffs (2,039 events on 44 symbols, ~46 each), so an event's PRE window
        # routinely sits inside the previous event's POST window. The "before" leg is then already
        # under supply pressure, the treated series looks chronically weak against its peers, and
        # parallel trends fails for a reason that has nothing to do with the event being measured.
        # Requiring a clean pre-window is the standard staggered-DiD remedy; it costs events, and
        # the count it costs is reported rather than absorbed.
        if require_clean_pre:
            window_lo = idx[pos - PRE_DAYS]
            if any(window_lo <= d < day for d in unlock_days.get(sym, ())):
                dropped["prior-unlock-in-pre-window"] += 1
                continue
        pre_i, post_i = idx[pos - PRE_DAYS:pos], idx[pos:pos + POST_DAYS]

        # A symbol is never its own control: for the not-yet-treated design the peer mean over
        # this window is recomputed with the treated symbol dropped, or it would appear on both
        # legs and shrink the estimate toward zero mechanically.
        own = ctrl[sym] if sym in ctrl.columns else None
        if own is not None:
            peers = ctrl.drop(columns=[sym])
            leg = peers.mean(axis=1).where(peers.notna().sum(axis=1) >= MIN_CONTROLS_PER_DAY)
        else:
            leg = ctrl_mean

        t_pre = rets[sym].reindex(pre_i).dropna()
        t_post = rets[sym].reindex(post_i).dropna()
        c_pre = leg.reindex(pre_i).dropna()
        c_post = leg.reindex(post_i).dropna()
        if (len(t_pre) < MIN_PRE_OBS or len(c_pre) < MIN_PRE_OBS
                or len(t_post) < MIN_POST_OBS or len(c_post) < MIN_POST_OBS):
            dropped["short-window"] += 1
            continue

        units.append(TreatedUnit(
            unit_id=f"{sym}@{day.date()}", cohort_key=sym,
            event_ts=float(day.timestamp()),
            treated_pre=[float(x) for x in t_pre], treated_post=[float(x) for x in t_post],
            control_pre=[float(x) for x in c_pre], control_post=[float(x) for x in c_post]))

    return {"units": units, "n_control_pool": n_control_pool, "dropped": dict(dropped),
            "control_mode": control_mode, "require_clean_pre": require_clean_pre,
            "treated_symbols": sorted({u.cohort_key for u in units})}


def main(argv: list[str] | None = None) -> int:
    lawful.guard()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=REPORT)
    a = ap.parse_args(argv)

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    if not UNLOCKS.exists():
        report = {"status": "NOT-READABLE-HERE", "missing": str(UNLOCKS.relative_to(ROOT)),
                  "note": "the unlock collector is the blocker; no synthetic cohort is generated "
                          "and no result is reported"}
        out.write_text(json.dumps(report, indent=1), "utf-8")
        print(f"natural-experiment: NOT-READABLE-HERE -- {UNLOCKS.relative_to(ROOT)} missing")
        return 0

    events = _events()
    rets = _panel().pct_change(fill_method=None)

    # BOTH DESIGNS ARE RUN AND BOTH ARE REPORTED. They are TWO TRIALS on the same hypothesis, so
    # the multiplicity charge is n_cohort=2 for each -- running the pair and quoting only the
    # survivor is the garden of forking paths, and it is the exact thing the desk's own
    # "two exit rules are two trials" rule exists to stop.
    designs = []
    for rank, (mode, clean) in enumerate(DESIGNS, start=1):
        c = build_cohort(rets, events, control_mode=mode, require_clean_pre=clean)
        r = difference_in_differences(
            c["units"], n_control_pool=c["n_control_pool"], exogeneity_note=EXOGENEITY,
            direction=DIRECTION, n_cohort=len(DESIGNS), rank=rank)
        designs.append({
            "control_mode": mode, "require_clean_pre": clean,
            "cohort": {
                "n_events_on_disk": len(events),
                "n_treated_units": len(c["units"]),
                "n_treated_symbols": len(c["treated_symbols"]),
                "n_control_pool": c["n_control_pool"],
                "dropped": c["dropped"],
            },
            "result": r.model_dump(),
        })

    report: dict[str, Any] = {
        "generated": datetime.now(tz=UTC).isoformat(),
        "row": "R0207",
        "stage": "A (zero promotion authority)",
        "design": "difference-in-differences over dated token unlocks, two control designs",
        "hypothesis": (
            "a scheduled insider/private-sale token unlock raises circulating supply, so the "
            "unlocked token underperforms comparable peers over the days after the unlock"),
        "why_not_the_cohort_the_row_named": (
            "R0207 names data/exchange_announcements.jsonl and a funding-interval or leverage-cap "
            "change. That file is a NEWS feed -- 232 rows from cointelegraph/coindesk/"
            "defillama_hacks/okx, with ZERO venue rule changes and only 43 rows carrying a symbol "
            "-- and no dated venue rule-change calendar exists anywhere on disk. Unlocks are a "
            "STRONGER cohort on the row's own criterion: it flags rule changes as endogenous "
            "(venues act because they see risk), while a vesting schedule is fixed at genesis "
            "years before the outcome window and cannot respond to the returns it precedes."),
        "pre_registered": {
            "categories": list(TREATED_CATEGORIES), "pre_days": PRE_DAYS,
            "post_days": POST_DAYS, "start": START, "end": END,
            "direction": DIRECTION, "min_controls_per_day": MIN_CONTROLS_PER_DAY,
            "n_trials_charged": len(DESIGNS),
            "conditioning_variable": None,
            "why_no_conditioning": (
                "pct_circ_now is a 2026 float applied to events back to 2016 -- a look-ahead in "
                "the conditioning variable that fails toward a false null; no dated circulating "
                "supply exists on disk"),
        },
        "designs": designs,
    }
    out.write_text(json.dumps(report, indent=1, default=str), "utf-8")

    print(f"natural-experiment (R0207): DiD over dated token unlocks, "
          f"{len(DESIGNS)} trials charged")
    for d in designs:
        c, r = d["cohort"], d["result"]
        tag = f"{d['control_mode']}{'+clean-pre' if d['require_clean_pre'] else ''}"
        print(f"  [{tag}] {c['n_treated_units']} unit(s) on "
              f"{c['n_treated_symbols']} symbol(s) vs {c['n_control_pool']} control(s); "
              f"dropped {c['dropped']}")
        print(f"      {r['verdict']}")
        if c["n_treated_units"] < MIN_EVENTS:
            print(f"      UNDERPOWERED: {c['n_treated_units']}/{MIN_EVENTS} -- reported, "
                  "not scored")
    print(f"-> {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
