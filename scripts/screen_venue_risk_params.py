"""R0523 / BR-19 -- venue risk-parameter metadata as a carry conditioning variable.

THE HYPOTHESIS. Binance sets `fundingIntervalHours` (4h/8h/1h) and `adjustedFundingRateCap` per
symbol from the full position and liquidation distribution nobody outside the exchange can see.
The desk reads them as plumbing constants. If the venue's risk desk shortens an interval or tightens
a cap because it can see crowding building, the parameter is a free read on private information --
and it should condition carry returns AFTER controlling for the funding level itself.

THE FALSIFIER, PRE-REGISTERED AND LOAD-BEARING. The strongest argument against is that the
parameter is nothing but a coarsened copy of the contemporaneous funding level: a venue shortens
the interval BECAUSE funding is extreme, so a naive test would rediscover the funding level under
a new name. `axis_screen`'s de-contamination gate implements exactly that control -- the residual
IC is taken after orthogonalising against the same-period and prior-period return -- so a collapse
of `residual_ic` below half the raw IC IS the falsifier firing, not a bug.

WHY THIS RUN REFUSES TO PRODUCE A VERDICT, AND WHY THAT IS THE DELIVERABLE.

  1. THE ONLY DEEP CONDITIONER ON DISK IS A SNAPSHOT. `data/funding_caps.json` carries one
     file-level `fetched_at` for 760 symbols and no per-symbol as-of date. Joining it to the
     2019-2026 D1 panel asserts TODAY's cadence for every past bar. That is the `pct_circ_now`
     class the desk has already paid for once, and it FAILS TOWARD A FALSE NULL -- the direction
     no gate here catches, because a killed axis produces no alert. The drift is measured, not
     hypothetical: the R0523 card recorded 426/812 on 4h at 2026-08-12; the same file on
     2026-08-19 reads 445/760. WORSE, THE LABEL IS ENDOGENOUS TO THE OUTCOME -- the venue moves a
     symbol BECAUSE of its recent funding, so today's label leaks the past of the very series
     being predicted.

  2. THE LOOK-AHEAD-FREE CONDITIONER EXISTS AND IS TOO SHORT. `libs.research.funding_interval_history`
     derives the as-of interval from the venue's own next-settlement stamps in
     `data/funding_cross_section.jsonl`, reading nothing from the future. Measured this run: 300
     snapshots, 152 structurally BLIND (the 8h grid is a subset of the 4h grid, so at most instants
     both classes point at the same stamp), 148 usable, 14 dates, 843 symbols. Fourteen daily
     observations is fewer than the screen's own 21-row z-score warm-up.

  3. THE SWITCH-EVENT ROUTE IS RARER STILL. Exactly ONE symbol changed interval inside the window
     (HFTUSDT, 8h -> 4h on 2026-08-07). At ~1 switch per 14 days across 824 symbols, an event
     study needs years of accrual, not a longer query.

So the axis is UNMEASURABLE TODAY on look-ahead-free data, and certifying it SCREEN-WEAK from the
contaminated snapshot would mint a graveyard-grade refutation the evidence cannot support (L1.62:
an unmeasured panel can never be `powered`, and only a powered screen may record a kill). This run
therefore publishes the refusal, its measurements, and the DATE the axis becomes screenable.

Every construction attempted is logged whatever its verdict -- reporting only a winner is the
garden of forking paths, and a refusal is a first-class deliverable.

    python scripts/screen_venue_risk_params.py [--json]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops import box_state  # noqa: E402
from libs.ops.lawful import guard as _law_guard  # noqa: E402
from libs.research.funding_interval_history import build_history  # noqa: E402

_STATE_ROOT, _STATE_BASIS = box_state.data_root(_ROOT)
_TAPE = "data/funding_cross_section.jsonl"
_OUT = _ROOT / "reports/axis_screens/venue_risk_params.json"

#: The screen's own z-score warm-up (libs/research/axis_screen.SCREEN_WARMUP_ROWS) plus the 30
#: scored points it demands before it will look at anything. Below this a daily panel cannot be
#: screened at all, whatever the cross-section is.
_MIN_DATES = 21 + 30

#: Pre-registered constructions. BOTH are reported whatever happens (garden-of-forking-paths):
#: naming them here, before the run, is what makes the trial count honest.
CONSTRUCTIONS = (
    ("interval_4h_vs_8h",
     "as-of fundingIntervalHours as a binary cross-sectional conditioner on carry returns, "
     "controlling for the contemporaneous funding level"),
    ("interval_switch_event",
     "the venue's decision to SHORTEN a symbol's interval, as a dated event"),
)


def _snapshots() -> tuple[list[dict[str, Any]], str | None]:
    p = _STATE_ROOT / _TAPE
    try:
        raw = p.read_text("utf-8").splitlines()
    except FileNotFoundError:
        return [], f"absent ({_TAPE} -- has the collector ever run on this box?)"
    except OSError as e:
        return [], f"unreadable ({e!r})"
    rows: list[dict[str, Any]] = []
    bad = 0
    for ln in raw:
        if not ln.strip():
            continue
        try:
            r = json.loads(ln)
        except json.JSONDecodeError:
            bad += 1                       # attrition, counted (L1.60)
            continue
        if isinstance(r, dict):
            rows.append(r)
        else:
            bad += 1
    return rows, (f"{bad} unparseable rows" if bad else None)


def novelty() -> dict[str, Any]:
    """Graveyard gate BEFORE compute (universal duty). Advisory; the decision is recorded.

    THE DENOMINATOR IS PART OF THE VERDICT (L1.57). `data/graveyard_priors.json` is gitignored, so
    from a worktree `load_priors()` returns an EMPTY list and `hypothesis_novelty` duly reports
    score 1.0, nearest None -- "perfectly novel", computed against nothing. Measured on this very
    screen: two identical runs minutes apart returned 0.6974 (nearest
    grave:cross-exchange funding dispersion) and 1.0 (nearest None). A gate that passes everything
    carries zero information, and this one exists to stop the desk re-testing dead ground and
    burning multiplicity budget twice. Priors are therefore read from the BOX, and the prior COUNT
    is published so a zero-prior pass can never masquerade as a clean bill.
    """
    try:
        from scripts.build_graveyard_priors import load_priors

        from libs.alpha_factory.hypothesis_novelty import hypothesis_novelty
        priors = load_priors(path=_STATE_ROOT / "data/graveyard_priors.json")
        if not priors:
            return {"status": "UNMEASURED", "n_priors": 0,
                    "why": ("the graveyard prior set is empty -- a novelty score against zero "
                            "priors is vacuous, not clean (L1.57). Run "
                            "scripts/build_graveyard_priors.py on the box.")}
        res = hypothesis_novelty(
            "venue risk parameter metadata funding interval hours adjusted funding rate cap "
            "as carry conditioning variable controlling for funding level exchange risk desk "
            "private position liquidation distribution",
            features=["funding", "venue_metadata", "interval", "cap", "carry", "conditioning"],
            priors=priors)
        return {"status": "MEASURED", "n_priors": len(priors),
                "novelty_score": round(res.novelty_score, 4), "nearest": res.nearest_id,
                "redundant": res.is_redundant}
    except Exception as e:                 # advisory gate: absence is recorded, never fatal
        return {"status": "UNAVAILABLE", "why": f"{type(e).__name__}: {e}"}


def _log_memory(trials: list[dict[str, Any]]) -> dict[str, Any]:
    """One research-memory row per construction, INCLUDING the refusals (universal duty).

    A factory that forgets its refusals re-runs them, which is the novelty-gate failure arriving
    by amnesia.

    INVOKED FROM THE BOX'S CHECKOUT, because research_memory resolves its sqlite path from its own
    `__file__`. Run from a worktree it opens an EMPTY database and every row raises "no such table"
    -- which is how this run first went: two refusals computed, logged nowhere, and the failure
    swallowed by `check=False`. The outcome is now returned and published, because a memory write
    that silently did not happen is worse than one that never claimed to (L2.4).
    """
    ok, errs = 0, []
    for tr in trials:
        r = subprocess.run(
            [sys.executable, str(_STATE_ROOT / "scripts/research_memory.py"), "log",
             "--category", "hypothesis",
             "--statement", f"{tr['construction']}: venue risk-parameter carry conditioner (R0523)",
             "--result", "screening",
             "--axis", "venue_risk_params",
             "--metrics", json.dumps({k: tr.get(k) for k in
                                      ("verdict", "n_dates", "n_symbols", "why") if k in tr}),
             "--lessons", str(tr.get("why", ""))[:400]],
            cwd=_STATE_ROOT, capture_output=True, text=True, timeout=60, check=False)
        if r.returncode == 0:
            ok += 1
        else:
            errs.append((r.stderr or "").strip().splitlines()[-1:] or ["(no stderr)"])
    return {"rows_written": ok, "rows_attempted": len(trials),
            "errors": [e[0] for e in errs][:3]}


def run() -> dict[str, Any]:
    rows, tape_note = _snapshots()
    hist = build_history(rows)
    trials: list[dict[str, Any]] = []

    n_dates = int(hist.get("n_dates") or 0)
    n_syms = int(hist.get("n_symbols") or 0)

    # CONSTRUCTION 1 -- the cross-sectional conditioner.
    if n_dates >= _MIN_DATES:
        verdict, why = "READY", (
            f"{n_dates} look-ahead-free dates clears the {_MIN_DATES}-date floor -- run the "
            "stage_a_screen cell grid with MEASURED panel breadth (L1.62)")
    else:
        verdict, why = "SCREEN-UNMEASURABLE", (
            f"{n_dates} look-ahead-free dates against a {_MIN_DATES}-date floor (21-row z-score "
            f"warm-up + 30 scored points). The deep 2019-2026 panel is reachable ONLY through "
            "data/funding_caps.json, a single-instant snapshot whose label is endogenous to the "
            "outcome -- screening on it would mint a false-null kill no gate here would catch.")
    trials.append({"construction": CONSTRUCTIONS[0][0], "hypothesis": CONSTRUCTIONS[0][1],
                   "verdict": verdict, "n_dates": n_dates, "n_symbols": n_syms, "why": why})

    # CONSTRUCTION 2 -- the switch as an event.
    switches = _switches(hist)
    trials.append({
        "construction": CONSTRUCTIONS[1][0], "hypothesis": CONSTRUCTIONS[1][1],
        "verdict": "SCREEN-UNMEASURABLE", "n_events": len(switches), "events": switches,
        "n_dates": n_dates, "n_symbols": n_syms,
        "why": (f"{len(switches)} interval switch(es) observed across {n_syms} symbols in "
                f"{n_dates} days. An event study on this needs years of accrual, not a wider "
                "query -- and ~2 non-zero days in 30 reads as noise on every continuous "
                "statistic (the event-shaped-gate rule)."),
    })

    ready_date = _ready_date(hist)
    return {
        "ran": datetime.now(tz=UTC).isoformat(),
        "row": "R0523",
        "axis": "venue_risk_params",
        "verdict": "SCREEN-UNMEASURABLE",
        "state_root": str(_STATE_ROOT), "state_basis": _STATE_BASIS,
        "tape_note": tape_note,
        "novelty": novelty(),
        "clock": ("interval derived from the venue's own next-settlement stamp as of each "
                  "snapshot's receipt clock `t`; the D1 return leg would be the bar `timestamp` "
                  "column. Nothing reads the future (L1.46)."),
        "interval_history": {k: hist.get(k) for k in
                             ("measured", "snapshots_attempted", "snapshots_blind",
                              "snapshots_unusable", "snapshots_used", "n_dates", "n_symbols",
                              "intra_day_conflicts")},
        "window": [hist["dates"][0], hist["dates"][-1]] if hist.get("dates") else None,
        "variants_tried": len(trials),
        "trials": trials,
        "promotion_authority": "NONE -- no forward clock minted, no slot consumed, no bar moved",
        "becomes_screenable": ready_date,
        "refusal": (
            "The deep panel's conditioner is a today-snapshot and its label is endogenous to the "
            "outcome; the look-ahead-free conditioner is 14 days deep. Certifying SCREEN-WEAK "
            "from the former would be a graveyard-grade refutation the evidence cannot support "
            "(L1.62). UNMEASURED is a real answer (L1.28a)."),
    }


def _switches(hist: dict[str, Any]) -> list[dict[str, Any]]:
    """Symbols whose as-of interval changed inside the observed window."""
    panel = hist.get("panel") or {}
    dates = hist.get("dates") or []
    out: list[dict[str, Any]] = []
    for sym in {s for d in dates for s in panel.get(d, {})}:
        seq = [(d, panel[d][sym]) for d in dates if sym in panel.get(d, {})]
        vals = {v for _, v in seq}
        if len(vals) > 1:
            first_change = next((d for (d, v), (_, prev) in zip(seq[1:], seq, strict=False)
                                 if v != prev), None)
            out.append({"symbol": sym, "at": first_change,
                        "from": seq[0][1], "to": seq[-1][1]})
    return sorted(out, key=lambda r: str(r["symbol"]))


def _ready_date(hist: dict[str, Any]) -> str:
    """When the look-ahead-free panel clears the screen's own floor, at the observed accrual rate."""
    dates = hist.get("dates") or []
    if not dates:
        return "UNKNOWN -- no look-ahead-free dates accrued yet"
    need = _MIN_DATES - len(dates)
    if need <= 0:
        return "NOW"
    last = datetime.fromisoformat(dates[-1]).date()
    return (f"~{need} more daily observations after {last.isoformat()} "
            f"(one per UTC day while the collector runs)")


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    rep = run()
    # Logged BEFORE the artifact is written, so the artifact can record whether it landed.
    rep["research_memory"] = _log_memory(rep["trials"])
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep, indent=1), "utf-8")

    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        ih = rep["interval_history"]
        print("=== R0523 venue risk-parameter carry conditioner ===")
        print(f"  VERDICT: {rep['verdict']}")
        print(f"  look-ahead-free interval history: {ih['n_dates']} dates x {ih['n_symbols']} "
              f"symbols from {ih['snapshots_used']}/{ih['snapshots_attempted']} snapshots "
              f"({ih['snapshots_blind']} structurally blind)")
        for tr in rep["trials"]:
            print(f"  TRIAL {tr['construction']:<24} {tr['verdict']}")
            print(f"        {tr['why']}")
        print(f"  becomes screenable: {rep['becomes_screenable']}")
        print(f"  novelty: {rep['novelty']}")
        print(f"  research memory: {rep['research_memory']['rows_written']}"
              f"/{rep['research_memory']['rows_attempted']} rows written"
              + (f" -- {rep['research_memory']['errors']}"
                 if rep["research_memory"]["errors"] else ""))
        print(f"  -> {_OUT.relative_to(_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
