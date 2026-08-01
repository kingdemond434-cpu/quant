#!/usr/bin/env python3
"""COST IDENTIFICATION (L1.45) -- fit the execution cost surface from the desk's OWN fills.

This is the producer for the three `libs/execution/ramp_gate.py` step-up conditions that had NO
PRODUCER ANYWHERE IN THE REPO (verified 2026-08-01: `cost_ratio`, `slippage_ks_p` and
`calibration_mae_falling_months` appeared only in CONSUMERS -- ramp_gate.py:62,67,70 and
staging.py:84 -- plus mutation-test fixtures). `data/live_guard.json` shows the consequence:

    ramp.size_fraction = 0.10   blocked by: a_cost_le_1_25x, c_slippage_ks_p_gt_0_05,
                                            e_mae_falling_2_months, ...

The book was pinned to the FLOOR RUNG by three statistics nothing computed. The ramp could not
advance by waiting, because waiting was never what it was short of.

TWO NUMBERS, AND THEY ARE DIFFERENT KINDS OF THING:

  1. CALIBRATION (this file, today, from observational fills). "Is the modelled cost right?"
     realised pair slippage vs `data/cost_model.json`'s book-walk prediction. Purely
     observational, and that is FINE for calibration: comparing prediction to outcome needs no
     intervention. This is what unpins the ramp.

  2. THE CAUSAL SLOPE (this file, once excitation arms accrue). "What would cost be if we waited
     longer?" That is a COUNTERFACTUAL and observational fills CANNOT answer it: maker wait is a
     deterministic function of side today (240s iff spot BUY, 8s iff spot SELL,
     executor:1246), so wait and side are perfectly collinear. Reported UNIDENTIFIED until
     randomised arms exist -- never estimated from the confounded data and never defaulted.

WHY A BOOK-WALK CANNOT REPLACE THIS (and why the queued remedy of walking BIGGER sizes will not
work either): walking a recorded book measures the cost of consuming DISPLAYED depth in a book
that existed WITHOUT OUR ORDER IN IT -- biased down by refill and fade, biased up by hidden
liquidity, with neither bias signed a priori. No quantity of book-walking resolves a
counterfactual. Only our own fills measure our own cost.

THE REFUSAL PATH IS THE LOAD-BEARING PART. `cost_ratio` is a gate on SIZE INCREASES: publishing
one computed from too few fills would step the book up on fiction, which is strictly worse than
leaving it pinned. Below `MIN_FILLS_FOR_RAMP` this script writes NO ramp evidence at all, so
ramp_gate's fail-closed defaults (999.0 / 0.0 / 0.0) keep blocking. An UNDERPOWERED fit must
never read as a passed condition.

STATUS: OK / UNIDENTIFIED (no randomised arms -- causal slope unavailable) / UNDERPOWERED (fewer
than MIN_FILLS_FOR_RAMP instrumented fills) / NO-DATA (no usable fills at all).

    python scripts/run_cost_identification.py [--json] [--write-ramp]
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# L1.42 LAWFUL ENTRY: pages, does not block -- a governance fault must never silently stop the
# organ that unpins the ramp.
from libs.execution import excitation, execution_tape  # noqa: E402
from libs.ops.lawful import guard as _law_guard  # noqa: E402

_COST_MODEL = _ROOT / "data/cost_model.json"
_OUT = _ROOT / "data/cost_surface.json"
_RAMP = _ROOT / "data/ramp_state.json"

# PRE-REGISTERED. The minimum instrumented fills before ANY ramp evidence is published. Chosen
# before looking at the fit, and it binds hard: at the 2026-08-01 measurement only 10 of 523 tape
# rows carried slippage fields, so this script's first run refuses on purpose.
MIN_FILLS_FOR_RAMP = 30
# Trailing window the ramp gate's conditions are defined over (ramp_gate.TRAILING_WEEKS_REQUIRED).
TRAILING_DAYS = 56


def _f(v: Any) -> float | None:
    try:
        if v is None:
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _modelled_open_bps(cm: dict[str, Any], symbol: str, notional: float) -> float | None:
    """The book-walk prediction for opening `notional` in `symbol`, in bps of mid.

    Picks the NEAREST modelled size bucket rather than interpolating: the buckets are coarse
    (100/250/500/1000/2500) and a linear interpolation between them would invent a smoothness
    the book-walk never measured. Returns None when the symbol was never modelled -- which is
    itself the finding (the absorbing set), never a default.
    """
    try:
        pair = cm["symbols"][symbol]["pair"]
    except (KeyError, TypeError):
        return None
    best: tuple[float, float] | None = None
    for size_s, row in pair.items():
        size = _f(size_s)
        bps = _f(row.get("pair_open_bps")) if isinstance(row, dict) else None
        if size is None or bps is None:
            continue
        d = abs(size - notional)
        if best is None or d < best[0]:
            best = (d, bps)
    return None if best is None else best[1]


def _row_stamp(r: dict[str, Any]) -> str:
    return str(r.get("opened") or r.get("closed") or r.get("_taped") or "")


# A trading day counts as instrumented once at least this share of its fills carry slippage.
# Rollout days sit between 0 and 1 and must fall on the UNINSTRUMENTED side: the epoch is meant
# to mark where coverage became RELIABLE, not where it was first glimpsed.
_TCA_DAY_THRESHOLD = 0.5


def _tca_coverage(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Separate 'predates instrumentation' from 'should have been instrumented and was not'.

    THIS DISTINCTION IS THE WHOLE DIAGNOSIS AND GETTING IT WRONG COSTS A SESSION, in either
    direction. The raw ratio is 10 of 523 tape rows (1.9%), which reads as a catastrophic
    instrumentation hole and sends the next session to fix the TCA wrapper. Measured per day:

        07-20  0/20    07-21  0/38    07-22  1/47    07-26  1/12    07-27  2/5    07-31  6/6

    Instrumentation is at 100% and the fit is starved of FILLS, not of the FIELD -- the opposite
    next action (resume the book) from the one the raw ratio implies (go fix the recorder).

    THE EPOCH IS THE START OF THE LONGEST TRAILING RUN OF INSTRUMENTED DAYS, not the first
    instrumented row. The obvious first-row rule is what this function originally used and it was
    wrong on this very data: ONE stray instrumented fill on 07-22 dragged the epoch back nine
    days and reported '60 fills uninstrumented', recommending a fix to a recorder that now runs
    at 6/6. A single unrepresentative row must not be able to poison a diagnosis.
    """
    by_day: dict[str, list[bool]] = defaultdict(list)
    for r in rows:
        day = _row_stamp(r)[:10]
        if day:
            by_day[day].append(r.get("spot_slip_bps") is not None)
    days = sorted(by_day)
    per_day = {d: {"n": len(v), "instrumented": sum(v)} for d, v in by_day.items()}
    if not any(v["instrumented"] for v in per_day.values()):
        return {"epoch": None, "n_before_epoch": len(rows), "n_since_epoch": 0,
                "n_instrumented_since_epoch": 0, "uninstrumented_since_epoch": [],
                "per_day": per_day,
                "note": "no tape row has ever carried slippage fields"}
    # Walk back from the most recent day while coverage holds; the epoch is where it breaks.
    epoch = None
    for d in reversed(days):
        v = per_day[d]
        if v["n"] and (v["instrumented"] / v["n"]) >= _TCA_DAY_THRESHOLD:
            epoch = d
        else:
            break
    if epoch is None:
        return {"epoch": None, "n_before_epoch": len(rows), "n_since_epoch": 0,
                "n_instrumented_since_epoch": 0, "uninstrumented_since_epoch": [],
                "per_day": per_day,
                "note": ("no trading day has yet reached "
                         f"{_TCA_DAY_THRESHOLD:.0%} instrumentation -- rollout incomplete")}
    since = [r for r in rows if _row_stamp(r)[:10] >= epoch]
    missing = [f"{r.get('event')} {r.get('symbol')} {_row_stamp(r)[:10]}"
               for r in since if r.get("spot_slip_bps") is None]
    return {
        "epoch": epoch,
        "n_before_epoch": len(rows) - len(since),
        "n_since_epoch": len(since),
        "n_instrumented_since_epoch": len(since) - len(missing),
        "uninstrumented_since_epoch": missing,
        "per_day": per_day,
        "note": (f"instrumentation reliable from {epoch}; {len(rows) - len(since)} rows predate "
                 f"it and are NOT a defect. Gaps since the epoch, if any, are."),
    }


def _usable(rows: list[dict[str, Any]], cm: dict[str, Any],
            now: datetime) -> list[dict[str, Any]]:
    """Fills carrying BOTH realised slippage legs and a modelled counterpart.

    A row without slippage fields is not a cheap observation, it is NO observation: the tape
    records the fill, but the number this whole file is about was never captured on it.
    """
    out: list[dict[str, Any]] = []
    for r in rows:
        s, f = _f(r.get("spot_slip_bps")), _f(r.get("fut_slip_bps"))
        notional = _f(r.get("notional"))
        sym = str(r.get("symbol") or "")
        if s is None or f is None or not notional or notional <= 0 or not sym:
            continue
        stamp = str(r.get("opened") or r.get("closed") or r.get("_taped") or "")
        try:
            when = datetime.fromisoformat(stamp)
        except ValueError:
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=UTC)
        if (now - when).days > TRAILING_DAYS:
            continue
        modelled = _modelled_open_bps(cm, sym, notional)
        out.append({
            "symbol": sym,
            "when": when,
            "notional": notional,
            "realised_bps": s + f,
            "modelled_bps": modelled,
            "wait_s": _f(r.get("wait_s")),
            "exc_arm": r.get("exc_arm"),
            "exc_baseline": r.get("exc_baseline"),
            "event": r.get("event"),
        })
    return out


def _ks_p(a: list[float], b: list[float]) -> float | None:
    """Two-sample KS p-value, realised vs modelled. None when either sample is empty."""
    if not a or not b:
        return None
    try:
        from scipy import stats
    except ImportError:
        return None
    return float(stats.ks_2samp(a, b).pvalue)


def _mae_falling_months(paired: list[dict[str, Any]]) -> tuple[int, dict[str, float]]:
    """Consecutive most-recent months in which calibration MAE FELL.

    Returns (streak, per-month MAE). A month with no paired fills breaks the streak rather than
    being skipped: 'MAE fell' across a gap is not evidence the model improved, it is evidence
    nothing was measured, and the ramp condition must not be satisfiable by silence.
    """
    by_month: dict[str, list[float]] = defaultdict(list)
    for p in paired:
        if p["modelled_bps"] is None:
            continue
        by_month[p["when"].strftime("%Y-%m")].append(
            abs(p["realised_bps"] - p["modelled_bps"]))
    mae = {m: round(statistics.mean(v), 4) for m, v in sorted(by_month.items())}
    months = sorted(mae)
    streak = 0
    for i in range(len(months) - 1, 0, -1):
        if mae[months[i]] < mae[months[i - 1]]:
            streak += 1
        else:
            break
    return streak, mae


def _collinearity(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Is maker wait still a deterministic function of side in the observed fills?

    This is the identification diagnostic itself. While every open shares one wait and every
    close shares another, the wait coefficient is not weakly identified -- it is NOT IDENTIFIED,
    and no sample size changes that. Reporting it as a number would be the single most dangerous
    output this file could produce.
    """
    waits_by_event: dict[str, set[float]] = defaultdict(set)
    for r in rows:
        if r["wait_s"] is not None:
            waits_by_event[str(r["event"])].add(round(r["wait_s"], 3))
    distinct = {k: sorted(v) for k, v in waits_by_event.items()}
    randomised = [r for r in rows if r.get("exc_baseline") is False]
    return {
        "distinct_waits_by_event": distinct,
        "n_randomised_arms": len(randomised),
        "arms_seen": sorted({str(r.get("exc_arm")) for r in randomised}),
        "identified": len(randomised) > 0,
    }


def _absorbing(cm: dict[str, Any], design: excitation.Design) -> dict[str, Any]:
    """Symbols the cost model can never measure because the recorder never records them.

    The recorder's universe is [_BENCH, book_symbols, recently_traded, _CORE][:32] and the cost
    model walks only recorded symbols, so an unmeasured name needs ~4x the funding of a measured
    one to clear the entry gate -- which is why it is never traded, never recorded, and never
    measured. This counts the reachable set; it does not fix it.
    """
    measured = sorted(cm.get("symbols", {}))
    return {
        "n_measured": len(measured),
        "measured": measured,
        "n_design_cells_unidentified": len(design.unidentified_cells),
        "unidentified_cells": design.unidentified_cells,
    }


def build_report(now: datetime | None = None, root: Path | None = None) -> dict[str, Any]:
    """Pure: read tape + cost model, return the surface. No writes, so tests call it directly."""
    root = root or _ROOT
    now = now or datetime.now(tz=UTC)
    try:
        cm = json.loads((root / "data/cost_model.json").read_text("utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        cm = {}
        cm_note = f"cost model UNREADABLE: {e!r}"
    else:
        cm_note = f"cost model: {len(cm.get('symbols', {}))} symbols"

    tape_path = root / "data/moat/execution_tape/cashcarry_trades.jsonl"
    rows = execution_tape.read(path=tape_path)
    design = excitation.load_design(root / "data/excitation_design.json")
    usable = _usable(rows, cm, now)
    paired = [u for u in usable if u["modelled_bps"] is not None]
    tca = _tca_coverage(rows)

    realised = [p["realised_bps"] for p in paired]
    modelled = [p["modelled_bps"] for p in paired]
    ident = _collinearity(usable)
    streak, mae_by_month = _mae_falling_months(paired)

    cost_ratio = None
    if paired and statistics.median(modelled) > 0:
        cost_ratio = round(statistics.median(realised) / statistics.median(modelled), 4)
    ks_p = _ks_p(realised, modelled)

    # STATUS, worst first, and the empty case BEFORE OK (L1.28a).
    if not usable:
        status = "NO-DATA"
        detail = (f"0 of {len(rows)} tape rows carry slippage fields -- the tape records the "
                  f"fill but not the number this file exists to fit (R0058/R0084)")
    elif len(paired) < MIN_FILLS_FOR_RAMP:
        status = "UNDERPOWERED"
        detail = (f"{len(paired)} usable fills (< MIN_FILLS_FOR_RAMP={MIN_FILLS_FOR_RAMP}) -- "
                  f"NO ramp evidence published, so ramp_gate's fail-closed defaults keep "
                  f"blocking the step-up. TCA began {tca['epoch']}: {tca['n_before_epoch']} of "
                  f"{len(rows)} tape rows PREDATE instrumentation and are not a defect; "
                  f"{tca['n_instrumented_since_epoch']}/{tca['n_since_epoch']} rows since the "
                  f"epoch are instrumented")
    elif not ident["identified"]:
        status = "UNIDENTIFIED"
        detail = ("calibration fit is powered, but ZERO randomised arms -- the wait coefficient "
                  "is not weakly identified, it is unidentified (wait is a deterministic "
                  "function of side)")
    else:
        status = "OK"
        detail = (f"{len(paired)} instrumented fills, {ident['n_randomised_arms']} randomised "
                  f"arms across {len(ident['arms_seen'])} conditions")

    # PUBLISHED ONLY WHEN POWERED. This dict is what a caller may merge into ramp evidence;
    # empty means "nothing proven", which the gate correctly reads as "do not step up".
    ramp_evidence: dict[str, Any] = {}
    if status in ("OK", "UNIDENTIFIED") and cost_ratio is not None:
        ramp_evidence = {
            "cost_ratio": cost_ratio,
            "slippage_ks_p": ks_p,
            "calibration_mae_falling_months": streak,
            "_source": "scripts/run_cost_identification.py",
            "_n_fills": len(paired),
            "_generated": now.isoformat(),
        }

    return {
        "generated": now.isoformat(),
        "law": "L1.45 -- execution excitation: a controller that never perturbs cannot identify "
               "the cost surface it gates on",
        "status": status,
        "detail": detail,
        "n_tape_rows": len(rows),
        "n_instrumented": len(usable),
        "n_paired_with_model": len(paired),
        "instrumented_frac": round(len(usable) / len(rows), 4) if rows else 0.0,
        "cost_model_note": cm_note,
        "tca_coverage": tca,
        "calibration": {
            "realised_median_bps": round(statistics.median(realised), 4) if realised else None,
            "modelled_median_bps": round(statistics.median(modelled), 4) if modelled else None,
            "cost_ratio": cost_ratio,
            "slippage_ks_p": ks_p,
            "mae_by_month": mae_by_month,
            "calibration_mae_falling_months": streak,
        },
        "identification": ident,
        "causal_wait_slope_bps_per_s": (
            None if not ident["identified"] else "see arms -- fit deferred until n>=cell target"),
        "absorbing_set": _absorbing(cm, design),
        "ramp_evidence": ramp_evidence,
        "next_action": (
            "Instrument the fill path: no tape row has ever carried slippage fields"
            if status == "NO-DATA" else
            # The accurate call depends on WHICH shortage binds, and the two point opposite ways.
            (f"ACCRUE FILLS -- instrumentation is healthy "
             f"({tca['n_instrumented_since_epoch']}/{tca['n_since_epoch']} since {tca['epoch']}); "
             f"the fit needs the book trading, not a recorder fix"
             if not tca["uninstrumented_since_epoch"] else
             f"FIX INSTRUMENTATION -- {len(tca['uninstrumented_since_epoch'])} fills since "
             f"{tca['epoch']} carry no slippage: {tca['uninstrumented_since_epoch'][:5]}")
            if status == "UNDERPOWERED" else
            "Enable excitation arms so the wait coefficient becomes identifiable"
            if status == "UNIDENTIFIED" else "Merge ramp_evidence into data/ramp_state.json"),
    }


def _merge_ramp(rep: dict[str, Any], path: Path) -> str:
    """Merge published evidence into ramp_state.json WITHOUT clobbering other producers' keys.

    `evidence` is shared: live_sharpe and drill_pass_streak_weeks come from elsewhere. A whole-
    file rewrite here would delete another organ's evidence and read as a ramp regression with no
    cause -- the read-without-writer class, inverted.
    """
    if not rep["ramp_evidence"]:
        return f"nothing published ({rep['status']}) -- ramp_state.json left untouched"
    try:
        state = json.loads(path.read_text("utf-8")) if path.exists() else {}
        if not isinstance(state, dict):
            state = {}
    except (OSError, json.JSONDecodeError) as e:
        return f"ramp_state.json UNREADABLE ({e!r}) -- refusing to overwrite it"
    ev = state.get("evidence")
    state["evidence"] = {**(ev if isinstance(ev, dict) else {}), **rep["ramp_evidence"]}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2) + "\n", "utf-8")
    return f"merged {len(rep['ramp_evidence'])} fields into {path}"


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--write-ramp", action="store_true",
                    help="merge published evidence into data/ramp_state.json")
    args = ap.parse_args()
    rep = build_report()
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep, indent=2, default=str) + "\n", "utf-8")
    if args.write_ramp:
        rep["ramp_write"] = _merge_ramp(rep, _RAMP)
        _OUT.write_text(json.dumps(rep, indent=2, default=str) + "\n", "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2, default=str))
    else:
        print(f"cost identification (L1.45): {rep['status']} -- {rep['detail']}")
        c = rep["calibration"]
        print(f"  instrumented {rep['n_instrumented']}/{rep['n_tape_rows']} tape rows "
              f"({rep['instrumented_frac']:.1%}); paired with model: "
              f"{rep['n_paired_with_model']}")
        if c["cost_ratio"] is not None:
            print(f"  realised {c['realised_median_bps']} bps vs modelled "
                  f"{c['modelled_median_bps']} bps -> cost_ratio {c['cost_ratio']}")
        print(f"  identified: {rep['identification']['identified']} "
              f"(randomised arms: {rep['identification']['n_randomised_arms']}); "
              f"waits by event: {rep['identification']['distinct_waits_by_event']}")
        print(f"  next: {rep['next_action']}")
        if "ramp_write" in rep:
            print(f"  ramp: {rep['ramp_write']}")
    # A starved or unidentified fit is a REPORT, not a gate failure: this script's job is to
    # produce the number, and it cannot conjure fills that were never instrumented. The FENCE
    # (check_excitation.py) is what fails on it.
    return 0


if __name__ == "__main__":
    sys.exit(main())
