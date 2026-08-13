#!/usr/bin/env python3
"""PANEL BREADTH FENCE (L1.62) -- a power figure whose denominator was assumed is not a measurement.

WHAT THIS WATCHES. `libs/research/axis_screen.stage_a_screen` converts a stacked (symbol x date)
panel into a power verdict by dividing the row count by a cross-sectional factor. That factor
decides `powered`, and `powered` is the single bit that separates the desk's two negative
verdicts:

    SCREEN-WEAK          "tested and refuted"   -- graveyard-grade negative knowledge
    SCREEN-UNDERPOWERED  "could not tell"       -- no graveyard entry, no clock, NO TRACE

Until 2026-08-13 that factor was never measured on any panel. It was `panel_width` -- an assertion
that K symbols carry exactly ONE independent observation per bar. Before 2026-08-11 it was the
opposite assertion (K observations, every t-stat inflated by sqrt(K) ~ 11.8x at K=139). The desk
swung between the two endpoints in a single change, and `scripts/screen_oi_ls_axes.py:126` records
what the first endpoint cost: "42 'graveyard-grade' SCREEN-WEAK verdicts the screen lacked the
power to make". NEITHER ENDPOINT WAS EVER MEASURED, and the measured answer on the desk's own
139-symbol panel is ~93 bets per date -- near neither, so the honest divisor is 1.50 rather than
139 and the detection floor was running 9.6x too high.

THE TWO DEFECTS THIS SEPARATES, BECAUSE THEY DEMAND OPPOSITE REPAIRS.

  ASSUMED-BREADTH -- a panel cell (panel_width > 1) with no measured basis. Its power figure is a
    guess. It is recorded and counted, and it is NOT a failure on its own: the assumption runs
    CONSERVATIVE (full-K), so the cell reads SCREEN-UNDERPOWERED and claims nothing. This is a
    coverage RATCHET whose gap is the work queue (L1.0) -- a fence that goes red on the day it is
    built gets switched off (L1.43), and the honest state of a legacy artifact is "not yet
    measured", not "broken".

  OVERCLAIMED-BREADTH -- a cell that reports `powered: true`, or the graveyard-grade SCREEN-WEAK
    verdict, on a basis that is UNMEASURED or absent. THIS IS THE FAILURE. It is the false-null
    direction no other gate catches: a refutation banked against a sample size nobody measured,
    which retires a hypothesis class on arithmetic rather than evidence. `stage_a_screen` now
    forbids it structurally (`powered` requires a measured basis when panel_width > 1), so a
    finding here means a cell was written by code that predates the rail, or by a second copy of
    the expression that was never wired -- exactly the failure mode `libs/validation/type2_cost.py`
    warns about at its own `correlation_n_eff`, which is a deliberate copy of the same arithmetic.

UNMEASURED IS A REAL ANSWER AND IT IS NOT `OK`. A run that finds zero panel cells anywhere has not
verified anything, and says UNMEASURED rather than passing (L1.28a). This is the WS-005 defect
class -- absence resolving to a clean verdict -- and it is the one this fence must not commit
itself.

ANTI-TIMIDITY READING (L1.28, required of every restraint clause). This is a MEASUREMENT duty and
a SCOPE EXPANSION. It lifts nothing, sizes nothing, promotes nothing, opens no gate and loosens no
statistical bar -- ic_min, sharpe_min, the angle-20 gate, Holm, alpha and MAX_FORWARD_SLOTS are
untouched. Its entire effect is to make "this panel's power rests on a measurement" distinguishable
from "this panel's power rests on an assumption nobody checked" -- byte-identical on this desk
until now, and only one of them is evidence. Every error it catches points the same way: toward a
screen that looked better-founded than it was.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.ops.fence_exit import fence_exit  # noqa: E402
from libs.ops.lawful import guard as _law_guard  # noqa: E402

_OUT = ROOT / "data/panel_breadth_coverage.json"
_PASSING = frozenset({"OK", "PARTIAL"})

#: Where screen verdicts land: `reports/` is the screens' own home (including axis_screens/) and
#: `data/` holds every artifact a fence or board reads.
#:
#: THESE MUST NOT NEST. The first version listed "reports/axis_screens" ALONGSIDE "reports", and
#: rglob walked every axis-screen artifact twice -- 48 real panel cells were reported as 90. A
#: denominator that double-counts is the same class of lie as one that silently drops rows
#: (L1.60): it is honest about what it counted and wrong about what that count means. Caught by
#: this fence's own first run, which is the only reason it is written down here rather than
#: shipped. `_paths()` de-duplicates by resolved path so a future nested entry cannot re-introduce
#: it, because a comment is not a control (it fires on recall).
_SCAN = ("data", "reports")

#: A verdict this fence recognises as a screen cell at all.
_VERDICTS = ("SCREEN-", "SUSPECT-", "TIMING-")


def _cells(obj: Any, out: list[dict[str, Any]]) -> None:
    """Every screen-verdict dict anywhere in a nested artifact, at any depth."""
    if isinstance(obj, dict):
        v = obj.get("verdict")
        if isinstance(v, str) and v.startswith(_VERDICTS) and "panel_width" in obj:
            out.append(obj)
        for x in obj.values():
            _cells(x, out)
    elif isinstance(obj, list):
        for x in obj:
            _cells(x, out)


def _paths() -> list[Path]:
    """Every JSON artifact in scope, each exactly ONCE, in a stable order.

    De-duplication is by RESOLVED path, so a nested `_SCAN` entry (or a symlinked tree) cannot
    double-count a cell into the denominator -- the defect this fence's own first run committed.
    """
    seen: dict[Path, None] = {}
    for rel in _SCAN:
        base = ROOT / rel
        if not base.is_dir():
            continue
        for p in base.rglob("*.json"):
            seen.setdefault(p.resolve(), None)
    return sorted(seen)


def build() -> dict[str, Any]:
    # EVERY DISCARD IS COUNTED (L1.60). `attempted` is incremented before the first exit, so a
    # tree that becomes unreadable cannot shrink this fence's denominator into a quiet pass.
    attempted = unreadable = 0
    cells: list[dict[str, Any]] = []
    sources: dict[str, int] = {}
    for p in _paths():
        attempted += 1
        try:
            doc = json.loads(p.read_text("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            unreadable += 1
            continue
        found: list[dict[str, Any]] = []
        _cells(doc, found)
        if found:
            rel = str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p)
            sources[rel] = len(found)
            for c in found:
                c["_src"] = rel
            cells.extend(found)

    panel = [c for c in cells if int(c.get("panel_width") or 1) > 1]
    single = len(cells) - len(panel)
    measured = [c for c in panel if c.get("breadth_basis") == "MEASURED"]
    assumed = [c for c in panel if c.get("breadth_basis") != "MEASURED"]

    # THE FAILURE: a powered claim, or a graveyard-grade refutation, on an unmeasured denominator.
    overclaimed = [
        {"name": c.get("name"), "src": c.get("_src"), "panel_width": c.get("panel_width"),
         "verdict": c.get("verdict"), "powered": c.get("powered"),
         "breadth_basis": c.get("breadth_basis", "<absent>"),
         "n_eff": c.get("n_eff"), "min_detectable_ic": c.get("min_detectable_ic")}
        for c in assumed
        if bool(c.get("powered")) or c.get("verdict") == "SCREEN-WEAK"
    ]

    cov = (len(measured) / len(panel)) if panel else float("nan")
    if not panel:
        status = "UNMEASURED"
        nxt = ("no panel cell (panel_width > 1) found anywhere in "
               f"{', '.join(_SCAN)} -- this fence verified nothing. Run a panel screen "
               "(scripts/screen_oi_ls_axes.py) or fix the scan scope; do NOT read this as health.")
    elif overclaimed:
        status = "OVERCLAIMED"
        nxt = (f"{len(overclaimed)} cell(s) claim `powered` or a graveyard-grade SCREEN-WEAK on an "
               "UNMEASURED breadth basis -- a refutation banked against a sample size nobody "
               "measured. Re-run those screens through the current harness, which forbids it.")
    elif assumed:
        status = "PARTIAL"
        nxt = (f"{len(assumed)} panel cell(s) still rest on the assumed full-K divisor. They are "
               "conservative, so nothing is over-claimed, but their SCREEN-UNDERPOWERED verdicts "
               "are uninformative. Wire measure_panel_breadth into their callers; coverage is a "
               "ratchet and this gap is the work queue.")
    else:
        status = "OK"
        nxt = "every panel cell on disk carries a measured cross-sectional breadth basis."

    return {
        "law": "L1.62", "status": status,
        "generated": __import__("datetime").datetime.now(tz=__import__("datetime").UTC).isoformat(),
        "n_examined": attempted, "n_unreadable": unreadable,
        "n_cells": len(cells), "n_panel_cells": len(panel), "n_single_series": single,
        "n_measured": len(measured), "n_assumed": len(assumed),
        "coverage": None if panel == [] else round(cov, 4),
        "n_overclaimed": len(overclaimed), "overclaimed": overclaimed[:40],
        "sources": dict(sorted(sources.items(), key=lambda kv: -kv[1])[:20]),
        "next_action": nxt,
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--report-only", action="store_true", help="write the artifact, exit 0")
    ap.add_argument("--json", action="store_true", help="print the artifact")
    args = ap.parse_args()

    rep = build()
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep, indent=2), "utf-8")

    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        cov = "n/a" if rep["coverage"] is None else f"{rep['coverage']:.1%}"
        print(f"panel breadth (L1.62): {rep['status']} -- {rep['n_measured']}/"
              f"{rep['n_panel_cells']} panel cells measured ({cov}), "
              f"{rep['n_overclaimed']} over-claimed, over {rep['n_examined']} artifact(s) "
              f"[{rep['n_unreadable']} unreadable], {rep['n_single_series']} single-series cells")
        for o in rep["overclaimed"]:
            print(f"  OVERCLAIMED  {o['name']} ({o['src']}) K={o['panel_width']} "
                  f"{o['verdict']} powered={o['powered']} basis={o['breadth_basis']}")
        print(f"  next: {rep['next_action']}")

    if args.report_only:
        return 0
    # Subject to L1.57/L1.60: the denominator counts every artifact HANDED to the scan, including
    # the unreadable ones, so this fence cannot shrink its way to a pass.
    return fence_exit(rep["status"], _PASSING, scanned=rep["n_examined"],
                      of="json artifacts scanned for screen verdicts",
                      fence="check_panel_breadth.py")


if __name__ == "__main__":
    raise SystemExit(main())
