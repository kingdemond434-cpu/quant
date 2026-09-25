#!/usr/bin/env python3
"""Give `median_spread_pts` a PROVENANCE by recomputing it from the broker's own tape.

    python scripts/repair_universe_spreads.py            # report only, changes nothing
    python scripts/repair_universe_spreads.py --apply     # write the registry
    python scripts/repair_universe_spreads.py --source h1 # the superseded H1 statistic

THE SOURCE CHANGED ON 2026-09-24 AND THE OLD ONE IS KEPT ONLY SO IT CAN BE NAMED. Everything
below this paragraph is the H1 story and it remains true about the REGISTRY; it is no longer true
about the REPAIR, because the H1 statistic it prescribes does not describe this broker:

    sym      H1 nonzero median   H1 p25   M1 median   live symbol_info
    AUDUSD          50.0          50.0       0.0            0
    EURUSD          50.0          50.0       0.0            0
    GBPUSD          50.0          50.0       0.0            0
    AUDCHF         160.0           3.0       0.0            1
    EURCAD         160.0           3.0       0.0            2

Exactly 50.0 on three unrelated majors and exactly 160.0 on two unrelated crosses is not a
spread. MEASURED on all 248 H1 parquets: every symbol carries ONE fixed spread on every bar from
the start of its history to a single cut-over (2020-12-11 01:00 for FX, 2020-12-31 for the CFDs),
the same constant appears in H1/H4/D1 and in no other timeframe, and 121 symbols begin it at the
same instant. It is the BROKER'S OWN HISTORY: Fusion's server did not record a per-bar spread
before December 2020 and serves that era at a fixed per-symbol spread. After it, this account
quotes 0 points on 80-96% of FX bars -- so `nz = kept[kept > 0]` below DELETES the modern era and
leaves the fixed-spread block as the majority of what survives. The exclusion selects for the
placeholder, and applying it would have charged the majors up to eighty times their real cost.

`research/fusion_spread_tape.py` is the source now: the M1 tape, ticked bars only, the same
session filter, zero-spread bars KEPT (a 0-point quote is what a Zero account quotes) and a zero
central value never WRITTEN. It carries the dispersion and three cross-checks per symbol. This
file keeps what it was always right about -- the provenance stamp, the two apply directions, the
verified gate, and the naming of every row that gets cheaper.

THE BLOCKER THIS CLEARS. `libs/portfolio/execution_cost.py` prices each sleeve at the hour it
actually fills, and on 2026-09-07 it priced ZERO of 76 sleeves. Not because the surface is
missing -- it covers 196 symbols -- but because the number the replay CHARGED cannot be
attributed to anything:

    241 of 251 symbols carry no `_provenance` entry for median_spread_pts at all
     23 of 195 read 0.0, i.e. the registry says the instrument is free to trade
     GBPJPY reads 1.0 beside a spread_pts_at_collection of 7.0 and hourly medians of 13-50

`universe_registry.py` names the cause and has since it was written: three producers write that
field with three different meanings -- `fetch_universe` takes the median of the H1 spread column,
`expand_universe` and `download_all_symbols` take `symbol_info.spread`, a point-in-time snapshot
that is not a median at all. "EURUSD reads 12 under one producer and 0 under the next."

THE CORRECT VALUE HAS BEEN ON DISK THE WHOLE TIME. Every symbol's H1 parquet carries a `spread`
column -- it is what `cost_surface` builds its whole per-hour surface from. EURUSD's registry says
0.0 and its own bars say 12.0. This recomputes the field from those bars, by the SAME exclusions
`cost_surface.profile_symbol` uses, and stamps where the number came from.

WHY THE EXCLUSIONS ARE SHARED AND NOT RE-DERIVED. Two modules computing "the spread" with
different filters is the producer collapse this file exists to end. Full-session days only (a
spliced short day aggregates the whole day's ticks), non-zero bars only (a zero spread is a
no-quote bar, not a free trade), and at least MIN_OBS of them -- imported from `cost_surface`, so
the surface and the registry cannot disagree about what a spread is.

IT CHANGES SLEEVE IDENTITY, AND THE DESK ALREADY HAS THE SAFE PATH FOR THAT.
`sleeve_registry.rebase_cost` fires on `cost_hash` ALONE: it keeps `forward_start` (a cost
correction does not un-observe a day), the engine replays every pass so no observation survives
priced at the old cost, and any other drifted field leaves the clock terminal. It also sets
`cost_rebase_cheaper` when a correction REDUCES the charge, which is the shape of a desk talking
itself into an edge.

THE DIRECTION HERE IS OVERWHELMINGLY MORE EXPENSIVE -- 0.0 to 12.0, 1.0 to 13.0 -- which is the
safe direction and the reason this is a repair rather than a rebase of convenience. Every symbol
the repair would make CHEAPER is listed by name in the report and counted separately, because
that is the set a reviewer must actually look at.

REPORT BY DEFAULT. `--apply` is a deliberate act: it rewrites the number every backtest, gauntlet
verdict and certificate is priced against, and the clocks rebase on the next pass.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

UNIVERSE = BASE / "data" / "universe"
REGISTRY = UNIVERSE / "universe.json"
REPORT = BASE / "reports" / "SPREAD_PROVENANCE.json"

#: What the `_provenance` stamp says under `--source h1`. A reader must be able to tell this apart
#: from `realized_fills` (the desk's own executions), from `fusion_zero_m1_tape` (the source of
#: record since 2026-09-24) and from an unstamped value (which is what this exists to eliminate).
SOURCE = "h1_spread_median"

#: The source of record. Superseded `h1_spread_median` on 2026-09-24 -- see the header for the
#: fixed-spread era that statistic was reading.
DEFAULT_SOURCE = "tape"

#: The tape artifact, so a reader of the registry can find the dispersion and the cross-checks
#: behind any stamped value rather than only the scalar.
TAPE_REPORT = BASE / "reports" / "SPREAD_TAPE.json"

#: The ONE exception to "realised fills beat bars". A fills-derived spread more than this multiple
#: of the symbol's own bar median is not a better measurement -- past it a cell can never clear
#: `stress_costs`, so the number is suppressing the instrument rather than pricing it. The
#: multiple is the gauntlet's own, mirrored from `libs.portfolio.fusion_cost`.
FILLS_IMPLAUSIBLE_ABOVE_BARS = 3.0

#: A correction this large is reported as SUSPECT rather than applied silently. Not a cap -- the
#: value is still written under --apply -- but a 50x move in the number every certificate is
#: priced against is a thing a person should see named, not discover later in a P&L.
SUSPECT_RATIO = 50.0


def measured_spread(sym: str) -> tuple[float | None, str, dict[str, Any]]:
    """The median non-zero spread on full-session days, by `cost_surface`'s own exclusions."""
    try:
        import numpy as np
        import pandas as pd
        from research.cost_surface import MIN_OBS, MIN_SESSION_BARS, SESSION_SHARE, session_bars
    except ImportError as exc:
        return None, f"cannot import the shared exclusions ({exc})", {}
    f = UNIVERSE / f"{sym}_H1.parquet"
    if not f.exists():
        return None, "no local H1 bars", {}
    try:
        df = pd.read_parquet(f, columns=["spread"])
    except (OSError, ValueError, KeyError):
        return None, "no spread column in the parquet", {}
    if df.empty:
        return None, "empty frame", {}
    idx = pd.DatetimeIndex(df.index)
    sess = session_bars(idx)
    if sess < MIN_SESSION_BARS:
        return None, "session unestablishable (<2 bars/day at mode and p90)", {}
    thr = max(MIN_SESSION_BARS, int(np.ceil(SESSION_SHARE * sess)))
    per_day = pd.Series(1, index=idx).groupby(idx.date).transform("size")
    kept = df.loc[np.asarray(per_day >= thr), "spread"].astype(float)
    nz = kept[kept > 0]
    if int(nz.size) < MIN_OBS:
        return None, (f"{int(nz.size)} priced bars on full-session days, below the {MIN_OBS} "
                      "floor -- no number is emitted, so no consumer can read one"), {}
    return float(nz.median()), "median non-zero spread on full-session H1 bars", {
        "n_bars_total": int(df.shape[0]), "n_bars_full_session": int(kept.size),
        "n_priced": int(nz.size), "zero_frac": round(1.0 - nz.size / max(kept.size, 1), 4),
        "p75": float(nz.quantile(0.75)), "p90": float(nz.quantile(0.90)),
    }


#: The tape measurement for this pass, keyed by symbol. Populated once per `run()` because the
#: measurement opens a terminal and 248 parquets; a per-symbol call would do both 251 times.
_TAPE: dict[str, Any] = {}


def load_tape(write: bool = True) -> dict[str, Any]:
    """Run the tape measurement once, cache its rows and publish the artifact behind the scalar.

    Its own function so the registry repair and the measurement stay separable: the repair is
    about which number gets WRITTEN and to what provenance, the measurement is about what the
    broker quotes, and a test of one should not need a terminal for the other.
    """
    from research.fusion_spread_tape import measure

    doc = measure(ROOT)
    _TAPE.clear()
    _TAPE.update(doc.get("by_symbol") or {})
    if write and doc.get("status") != "UNMEASURED":
        TAPE_REPORT.parent.mkdir(parents=True, exist_ok=True)
        TAPE_REPORT.write_text(json.dumps(doc, indent=1, default=str) + "\n", "utf-8")
    return doc


def tape_spread(sym: str) -> tuple[float | None, str, dict[str, Any]]:
    """The broker's own quote for `sym`, from `research/fusion_spread_tape.py`.

    Returns the SAME triple as `measured_spread` so the apply path, the provenance stamp and the
    report below are shared rather than duplicated. A row the tape measured but refuses to write
    -- a zero central value, or a cheapening every other source contradicts -- comes back as
    None WITH ITS REASON, which lands it in `unmeasured` and leaves its old value alone.
    """
    row = _TAPE.get(sym)
    if not isinstance(row, dict):
        return None, "the tape measurement produced no row for this symbol", {}
    from research.fusion_spread_tape import applicable

    value, why = applicable(row)
    detail: dict[str, Any] = {"dispersion": row.get("dispersion"), "window": row.get("window"),
                              "cross_checks": row.get("cross_checks"),
                              "disagreements": row.get("disagreements"),
                              "corroboration": row.get("corroboration"),
                              "corroborated_by": row.get("corroborated_by"),
                              "hours_traded": row.get("hours_traded")}
    # `n_priced` is what the report and the console printer below already read.
    detail["n_priced"] = (row.get("window") or {}).get("n")
    return value, why, detail


def _verified(path: Path | None) -> set[str] | None:
    """The symbols whose correction was SHOWN to move the charge toward the broker's own
    quote, from `desks/mt5/research/cost_truth.py`. None means "no gate asked for".

    NOTHING ON THE CAPITAL PATH MAY READ A SPREAD NOBODY JUST VERIFIED. These corrections
    were computed 2026-09-16 and sat in report_only for a week; applying 136 of them at
    once on the strength of the same bars that produced them would be a re-pricing by
    argument. `cost_truth` compares each one to the LIVE terminal's own quote and writes
    only the improvements here. An unreadable file yields an EMPTY set, not None: a gate
    that cannot be read must block, never wave through.
    """
    if path is None:
        return None
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return set()
    syms = doc.get("verified_symbols") if isinstance(doc, dict) else None
    return {str(s) for s in syms} if isinstance(syms, list) else set()


def run(apply: bool = False, write: bool = True,
        widening_only: bool = False, only_verified: Path | None = None,
        source: str = DEFAULT_SOURCE) -> dict[str, Any]:
    try:
        doc = json.loads(REGISTRY.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        return {"status": "UNMEASURED", "why": f"registry unreadable: {type(exc).__name__}"}
    rows = doc.get("symbols") if isinstance(doc, dict) and "symbols" in doc else doc
    if not isinstance(rows, dict):
        return {"status": "UNMEASURED", "why": "registry is not a symbol map"}

    # THE SOURCE IS CHOSEN ONCE AND NAMED IN EVERY STAMP IT WRITES. `h1` is kept reachable so the
    # superseded statistic can be reproduced and compared, never because it is still correct.
    tape_doc: dict[str, Any] = {}
    if source == "tape":
        tape_doc = load_tape(write=write)
        if tape_doc.get("status") == "UNMEASURED":
            return {"status": "UNMEASURED",
                    "why": f"the tape measurement refused: {tape_doc.get('why')}"}
        probe_fn, stamp = tape_spread, str(tape_doc.get("source") or "fusion_zero_m1_tape")
    elif source == "h1":
        probe_fn, stamp = measured_spread, SOURCE
    else:
        return {"status": "UNMEASURED", "why": f"unknown source {source!r}"}

    corrected: list[dict[str, Any]] = []
    stamped_same: list[str] = []
    cheaper: list[dict[str, Any]] = []
    applied_syms: list[str] = []
    suspect: list[dict[str, Any]] = []
    kept_better: list[str] = []
    #: `realized_fills` rows overridden because the fills value is implausible against its own
    #: bars. Named and counted separately: this is the one place the repair overrules a
    #: measurement with an inference, and a reviewer must be able to find every instance.
    fills_overridden: list[dict[str, Any]] = []
    unmeasured: dict[str, str] = {}
    #: Corrections refused because no live quote verified them. Named, never silent.
    skipped_unverified: list[str] = []
    verified = _verified(only_verified)
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")

    for sym in sorted(rows):
        row = rows[sym]
        if not isinstance(row, dict):
            continue
        src = ((row.get("_provenance") or {}).get("median_spread_pts") or {}).get("source")
        if src == "realized_fills":
            # THE DESK'S OWN EXECUTIONS BEAT AN ESTIMATE FROM BARS -- with ONE exception, added
            # 2026-09-10 because the unconditional version was protecting the two worst numbers
            # in the registry.
            #
            # MEASURED: GBPCHF carries a fills-derived 165.0 pts against a bar median of 7.0
            # (23.6x) and NZDJPY 147.0 against 15.0 (9.8x). In pips those are 16.5 and 14.7,
            # roughly five times what any account quotes on those crosses. A bar stamp samples
            # the widest instant of its hour, so the bar median is ALREADY the wide reading and
            # a fills value far above it is not a better measurement -- it is a broken estimate,
            # almost certainly slippage or a rollover caught in a handful of fills.
            #
            # The line is the gauntlet's own `stress_costs` multiple and not a number chosen
            # here: past 3x the symbol's own bars, a cell can never pass whatever its edge, so
            # the value is suppressing the instrument rather than pricing it. Inside 3x the
            # original rule stands untouched, which is where it was right.
            probe, _why, pdetail = probe_fn(sym)
            old_raw = row.get("median_spread_pts")
            old_val = float(old_raw) if isinstance(old_raw, (int, float)) else None
            implausible = (probe is not None and old_val is not None and probe > 0
                           and old_val > probe * FILLS_IMPLAUSIBLE_ABOVE_BARS)
            if not implausible:
                kept_better.append(sym)
                continue
            # ITS OWN LIST, NOT `suspect`. That one means "a >50x move" and is read as such;
            # folding a different finding into it would make both counts mean neither.
            fills_overridden.append({"symbol": sym, "old": old_val, "new": probe,
                            "source_was": "realized_fills",
                            "over_bars": round(old_val / probe, 2), **pdetail,
                            "why": (f"a fills-derived {old_val} pts against a bar median of "
                                    f"{probe} is {old_val / probe:.1f}x -- past the "
                                    f"{FILLS_IMPLAUSIBLE_ABOVE_BARS}x the stress gate tests, so "
                                    "nothing on this symbol can pass. Repaired from bars")})
        got, why, detail = probe_fn(sym)
        if got is None:
            unmeasured[sym] = why
            continue
        old = row.get("median_spread_pts")
        old_f = float(old) if isinstance(old, (int, float)) else None
        entry = {"symbol": sym, "old": old_f, "new": got, **detail}
        if old_f is not None and abs(old_f - got) < 1e-9:
            stamped_same.append(sym)                       # right value, missing provenance
        else:
            corrected.append(entry)
            if old_f is not None and old_f > 0 and got < old_f:
                cheaper.append(entry)
            if old_f is not None and old_f > 0 and max(got / old_f, old_f / got) > SUSPECT_RATIO:
                suspect.append(entry)
        # THE TWO DIRECTIONS ARE NOT THE SAME DECISION, and `--apply` treated them as one.
        #
        # A correction that WIDENS a spread can only make the desk charge itself more: every
        # certificate priced against the old number was too generous, and re-pricing can only
        # retire claims, never mint them. Measured 2026-09-14: 74 of 191 re-measured symbols
        # carry a registry spread of ZERO -- USDRUB 0 -> 2582.5, EURRUB 0 -> 250, NOKSEK 0 -> 39
        # -- and 26.3% of the judged docket (1,803 of 6,854 cells) was evaluated at zero spread
        # cost because of it. Nothing on the live book is affected; the exposure is research
        # pricing, which is where claims are minted.
        #
        # A correction that NARROWS one is the opposite act: it makes previously-uneconomic
        # cells look tradeable, which is the shape of a desk talking itself into an edge. Those
        # are exactly the rows whose medians are zero-inflated -- GBPCHF prices 46% of its
        # full-session bars, so its median lands in the near-zero cluster while its p75 is 150.
        #
        # `--apply-widening-only` lets the conservative half be taken WITHOUT the half that needs
        # a person to look at each row. It is not a lesser `--apply`; it is the half whose
        # direction of error is knowable in advance.
        # ONLY A PENDING CORRECTION CAN BE SKIPPED. A symbol whose stored value already
        # equals the measurement has nothing to apply, and counting it here would report
        # a refusal that never happened.
        if verified is not None and sym not in verified:
            if old_f is None or abs(old_f - got) >= 1e-9:
                skipped_unverified.append(sym)
            continue
        if apply and (not widening_only or old_f is None or got > old_f):
            row["median_spread_pts"] = got
            prov = row.setdefault("_provenance", {})
            # THE DISPERSION RIDES WITH THE SCALAR. A reader of the registry alone cannot tell a
            # symbol that is 2 all day from one that is 2 for twenty-three hours and 158 at the
            # rollover, and the sleeves that fire at the rollover pay the second one. The scalar
            # stays a MEDIAN and nothing else -- writing a p90 into a field named for a median is
            # the producer collapse `universe_registry` exists to end -- but the band and the
            # window it was taken over are stamped beside it, with the artifact that holds the
            # per-hour detail named so it can be found.
            prov["median_spread_pts"] = {"at": now, "source": stamp, "was": old_f,
                                         "mode": "widening_only" if widening_only else "full"}
            if source == "tape":
                prov["median_spread_pts"].update({
                    "dispersion": detail.get("dispersion"),
                    "window": detail.get("window"),
                    "corroboration": detail.get("corroboration"),
                    "detail": "desks/mt5/reports/SPREAD_TAPE.json"})
            applied_syms.append(sym)

    if apply and write:
        REGISTRY.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", "utf-8")

    out = {
        "status": "MEASURED", "generated_utc": now, "applied": bool(apply),
        "source": source, "provenance_stamp": stamp,
        "tape_summary": {k: tape_doc.get(k) for k in (
            "at", "account", "terminal_status", "live_freshness", "n_measured", "n_unmeasured",
            "n_dearer", "n_cheaper", "n_unchanged", "n_priced_from_zero",
            "n_cheaper_contradicted", "n_cheaper_tape_only", "cheaper_contradicted",
            "n_with_disagreement")} if tape_doc else None,
        "apply_mode": ("widening_only" if (apply and widening_only) else
                       "full" if apply else "report_only"),
        "n_applied": len(applied_syms),
        "verified_gate": None if verified is None else sorted(verified),
        "n_skipped_unverified": len(skipped_unverified),
        "skipped_unverified": sorted(skipped_unverified)[:60],
        "n_zero_registry_spread": sum(
            1 for e in corrected if (e.get("old") or 0) == 0),
        # THE NUMBER THE ZERO ARGUMENT IS ACTUALLY ABOUT, and the one the count above cannot
        # answer. That one counts zeros this pass REPAIRED; this counts zeros it LEAVES, which is
        # the set still priced at no cost at all. They are different facts and reporting only the
        # first reads as "the zeros are handled".
        #
        # A zero survives for exactly one reason and it is not a failure to look: at this venue's
        # integer-point resolution the symbol's median genuinely IS zero -- EURUSD quotes bid ==
        # ask on 96% of its ticked minutes and `symbol_info.spread` reads 0 on an open market --
        # so a Zero account carries that instrument's whole cost in the COMMISSION. Writing a
        # fabricated positive spread there would be an invention; writing the measured zero is
        # refused because a zero lets a non-edge certify. Naming them is the third option, and
        # their tails are in SPREAD_TAPE.json.
        "n_still_priced_at_zero": sum(
            1 for s, r in rows.items()
            if isinstance(r, dict) and r.get("median_spread_pts") == 0),
        "still_priced_at_zero": sorted(
            s for s, r in rows.items()
            if isinstance(r, dict) and r.get("median_spread_pts") == 0),
        "n_symbols": len(rows),
        "n_corrected": len(corrected), "n_already_correct": len(stamped_same),
        "n_kept_realized_fills": len(kept_better), "n_unmeasured": len(unmeasured),
        "n_made_cheaper": len(cheaper), "n_suspect": len(suspect),
        # THE SET A REVIEWER MUST ACTUALLY LOOK AT. A correction that makes a sleeve cheaper is
        # the shape of a desk talking itself into an edge, so it is named rather than counted.
        "made_cheaper": cheaper,
        "suspect": suspect[:40],
        "corrected": corrected[:60],
        "unmeasured": dict(sorted(unmeasured.items())[:40]),
        # THE COMPLETE MAP, BECAUSE A TRUNCATED LIST IS READ AS AN ABSENCE BY MACHINES.
        #
        # The three lists above are a READER'S sample -- `corrected[:60]` of 191 is the right
        # length for a person and the wrong length for anything that consumes this file.
        # Measured 2026-09-14: `factor_residual_engine` now refuses to propose a cell whose
        # target's spread was re-derived materially wider than the registry value it priced
        # against, and it reads this artifact to find out. Eleven of its sixteen proposals --
        # ZARJPY, GBPHUF, NZDHUF, NOKSEK, SEKJPY, NOKJPY, CHFNOK, EURRUB, GBPMXN, USDRUB,
        # EURILS -- were re-measured and sat in the 131 rows the truncation dropped, so the
        # fence classified every one of them as UNMEASURED and let them through. A sampled
        # artifact does not report a smaller set; it reports a DIFFERENT ANSWER, and the caller
        # cannot tell. The same shape as the NOAA rename: absence indistinguishable from a
        # quiet world.
        #
        # This is one small object per symbol over 251 symbols. There is no reason to sample it.
        "by_symbol": {r["symbol"]: {"old": r.get("old"), "new": r.get("new"),
                                    "bucket": r.get("_bucket", "corrected")}
                      for r in corrected},
        "kept_realized_fills": sorted(kept_better),
        "n_fills_overridden": len(fills_overridden),
        "fills_overridden": fills_overridden,
        "rule": (f"median_spread_pts is recomputed from source={source!r} and stamped "
                 f"{stamp!r}. The tape source is the symbol's own M1 spread column over TICKED "
                 "bars on full-session days, by cost_surface's exclusions, with zero-spread bars "
                 "KEPT and a zero central value never written; the h1 source is the superseded "
                 "non-zero H1 median, which on this broker reads a pre-2021 fixed-spread era. "
                 "`realized_fills` rows are never overwritten -- an "
                 "execution beats an inference. Identity: this changes cost_hash, and "
                 "sleeve_registry.rebase_cost handles a cost-only change without losing "
                 "forward_start, because the engine replays every pass."),
    }
    if write:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(out, indent=1) + "\n", "utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply-widening-only", action="store_true",
                    help="apply ONLY the corrections that make a symbol more expensive. The "
                         "direction of error is knowable in advance for these: a wider spread "
                         "can only retire claims, never mint them. The narrowing half needs a "
                         "person to look at each row and is left alone.")
    ap.add_argument("--apply", action="store_true",
                    help="write the registry (default: report only)")
    ap.add_argument("--no-write", action="store_true", help="do not write the report either")
    ap.add_argument("--only-verified", type=Path, default=None,
                    help="apply ONLY the symbols listed in this file's verified_symbols "
                         "(desks/mt5/data/spread_repair_verified.json, written by "
                         "research/cost_truth.py after comparing each correction to the "
                         "live terminal's own quote). Every other correction is skipped "
                         "and named. An unreadable file applies NOTHING.")
    ap.add_argument("--source", choices=("tape", "h1"), default=DEFAULT_SOURCE,
                    help="where the number comes from. 'tape' is the broker's own M1 quote "
                         "(research/fusion_spread_tape.py) and is the source of record. 'h1' is "
                         "the superseded non-zero H1 median, which on this broker reads a "
                         "pre-2021 FIXED-SPREAD era -- reachable so it can be reproduced and "
                         "compared, never because it is still correct.")
    a = ap.parse_args(argv)
    r = run(apply=a.apply or a.apply_widening_only, write=not a.no_write,
            widening_only=a.apply_widening_only, only_verified=a.only_verified,
            source=a.source)
    if r.get("status") != "MEASURED":
        print(f"REFUSED: {r.get('why')}")
        return 1
    print(f"spread provenance: {r['n_symbols']} symbols  source={r['source']}"
          f"  corrected={r['n_corrected']}  already_correct={r['n_already_correct']}"
          f"  kept_realized_fills={r['n_kept_realized_fills']}  unmeasured={r['n_unmeasured']}")
    if r.get("tape_summary"):
        t = r["tape_summary"]
        print(f"  tape: dearer={t['n_dearer']} cheaper={t['n_cheaper']} "
              f"unchanged={t['n_unchanged']} from_zero={t['n_priced_from_zero']}  "
              f"cheapenings contradicted by every other source={t['n_cheaper_contradicted']} "
              f"{t['cheaper_contradicted'][:8]}  tape_only={t['n_cheaper_tape_only']}  "
              f"symbols with a published disagreement={t['n_with_disagreement']}")
    if r.get("n_fills_overridden"):
        print(f"  FILLS OVERRULED (implausible against their own bars): "
              f"{r['n_fills_overridden']}")
        for e in r["fills_overridden"]:
            print(f"    {e['symbol']:12s} {e['old']} -> {e['new']}  ({e['over_bars']}x bars)")
    print(f"  would make CHEAPER: {r['n_made_cheaper']}"
          + (f"  {[c['symbol'] for c in r['made_cheaper'][:12]]}" if r["made_cheaper"] else ""))
    print(f"  suspect (>{SUSPECT_RATIO:.0f}x move): {r['n_suspect']}")
    for e in r["suspect"][:12]:
        print(f"    {e['symbol']:12s} {e['old']} -> {e['new']}")
    if r["corrected"]:
        print(f"  CORRECTED: {r['n_corrected']}")
        for c in r["corrected"][:12]:
            print(f"    {c['symbol']:12s} {c['old']} -> {c['new']}  ({c['n_priced']} priced bars)")
    print(f"  STILL priced at ZERO after this pass: {r['n_still_priced_at_zero']} "
          f"{r['still_priced_at_zero']}")
    if not (a.apply or a.apply_widening_only):
        print(f"  {r['n_zero_registry_spread']} symbol(s) carry a registry spread of ZERO and are "
              f"therefore priced at no cost at all.")
        print("  REPORT ONLY -- nothing written to the registry.")
        print("    --apply-widening-only   take the conservative half (charges MORE, never less)")
        print("    --apply                 take both halves; the narrowing half needs review")
    else:
        print(f"  APPLIED {r['n_applied']} symbol(s) in mode {r['apply_mode']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
