"""WHICH SURVIVORS NEVER MADE IT INTO SHADOW -- the gap between passing a gate and accruing.

THE FAILURE THIS CATCHES IS SILENT BY CONSTRUCTION

The protocol's ladder is `hypothesis -> falsify -> sweep -> shadow -> promoter -> live`, and every
rung reports its own success. A sweep prints "4 survivors" and exits 0. Shadow prints its ledger
and exits 0. Neither is responsible for the JOIN, so a cell that clears its gate and is never
added to `shadow_forward.SLEEVES` is invisible: the sweep did its job, shadow did its job, and the
candidate simply never existed on the rung above.

That is III.16's shape applied to evidence rather than code -- an edge that is validated and
accruing nothing looks identical, in every report the desk prints, to one that is doing fine.

WHY THIS READS THE LIST RATHER THAN A COPY OF IT

`SLEEVES` is IMPORTED from `shadow_forward`, never re-parsed or re-typed. The protocol's Step 2
makes the same demand of conditioning functions and for the same reason: a check built on a copy
of the list measures a third thing that neither the sweep nor shadow will ever run. If the import
fails, this refuses -- it does not fall back to a regex.

BOTH DIRECTIONS ARE REPORTED

    MISSING   a cell passed a gate and is not in shadow      -> evidence that is not being gathered
    ORPHAN    a shadow sleeve no hunt report vouches for     -> evidence being gathered for nothing

An orphan is not automatically wrong -- the three XAUUSD conditioned entries are deliberately in
shadow to be MEASURED AGAINST their live parent rather than promoted -- so orphans are listed and
never counted as failures. Missing cells are the finding.

ABSENT REPORTS ARE NOT AN EMPTY GAP

`reports/` is gitignored, so on a fresh clone there are no hunt records at all. Reporting "0
missing" there would be WS-005 exactly: absence resolving to the clean verdict. With no reports
readable this exits 2 and says the question is UNANSWERED on this host.

    python research/shadow_gap.py [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

REPORTS = BASE / "reports"
OUT = BASE / "shadow_gap.json"

SHADOW_GAP_VERSION = "shadow-gap-2026-08-20-a"

#: Keys a hunt report may use for the same three fields. Written down rather than guessed: a
#: report spelling `symbol` where this expects `sym` would silently contribute zero cells, and
#: zero cells reads exactly like zero gap.
_SYM = ("sym", "symbol")
_WIN = ("win", "window")
_STATE = ("state", "day_state")


def _cell(d: dict) -> tuple[str, str, str | None] | None:
    """(symbol, window, state) from a report row, or None if it is not a sleeve cell."""
    sym = next((d[k] for k in _SYM if d.get(k)), None)
    win = next((d[k] for k in _WIN if d.get(k)), None)
    if not sym or not win:
        return None
    state = next((d[k] for k in _STATE if d.get(k)), None)
    return (str(sym), str(win), str(state) if state and state != "base" else None)


def survivors() -> tuple[dict[tuple, list[str]], int]:
    """Every gated cell across every readable hunt report -> {cell: [report names]}."""
    found: dict[tuple, list[str]] = {}
    read = 0
    for f in sorted(REPORTS.glob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            continue
        read += 1
        rows = d.get("survivors")
        if rows is None:
            rows = [c for c in d.get("all", []) if isinstance(c, dict) and c.get("gate")]
        for r in rows or []:
            if not isinstance(r, dict):
                continue
            c = _cell(r)
            if c:
                found.setdefault(c, []).append(f.name)
    return found, read


def shadow_cells() -> set[tuple]:
    """The live SLEEVES list, IMPORTED. Never re-parsed -- see the module docstring."""
    from research.shadow_forward import SLEEVES              # noqa: PLC0415
    return {(s[0], s[1], s[2] if len(s) > 2 else None) for s in SLEEVES}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    gated, n_reports = survivors()
    # NO GATED CELLS IS UNANSWERED, NOT CLEAN -- and the first version of this guard tested
    # `n_reports == 0`, which was too weak by exactly the margin that matters. On this clone
    # `reports/` holds one file (daily_stop.json) carrying no survivor rows, so a report WAS read,
    # zero cells came out, and the tool printed "every gated cell is in shadow": vacuously true,
    # indistinguishable from a real all-clear, and produced by the check written to catch this
    # very shape. The denominator is the thing to test, not the file count.
    if not gated:
        print(f"UNANSWERED on this host: {n_reports} report(s) readable under {REPORTS}, and NOT "
              "ONE gated cell among them.\n"
              "reports/ is gitignored, so a fresh clone carries no hunt records. With no "
              "denominator there is no gap to measure -- '0 missing' here would be absence read "
              "as a clean verdict (WS-005). Run this where the hunts ran.", file=sys.stderr)
        return 2

    in_shadow = shadow_cells()
    # `state` is None for unconditioned cells, and None does not order against str -- so sort
    # on a normalised key rather than the tuple. Sorting the raw tuples raises TypeError the
    # moment a conditioned and an unconditioned cell meet, which is every real report.
    _k = lambda c: (c[0], c[1], c[2] or "")            # noqa: E731
    missing = sorted((c for c in gated if c not in in_shadow), key=_k)
    orphan = sorted((c for c in in_shadow if c not in gated), key=_k)

    art = {
        "version": SHADOW_GAP_VERSION, "reports_read": n_reports,
        "gated_cells": len(gated), "in_shadow": len(in_shadow),
        "missing": [{"symbol": s, "window": w, "state": st, "reports": gated[(s, w, st)]}
                    for s, w, st in missing],
        "orphan": [{"symbol": s, "window": w, "state": st} for s, w, st in orphan],
        "state": "OK" if not missing else "MISSING-FROM-SHADOW",
        "note": ("An ORPHAN is not a failure: the conditioned XAUUSD entries are in shadow to be "
                 "measured against their live parent, not to be promoted. MISSING is the finding "
                 "-- a cell that cleared a gate and is accruing no forward evidence."),
    }
    OUT.write_text(json.dumps(art, indent=1), encoding="utf-8")

    if args.json:
        print(json.dumps(art, indent=1))
        return 0 if not missing else 1

    print(f"SHADOW GAP  [{SHADOW_GAP_VERSION}]")
    print(f"  {n_reports} report(s) read, {len(gated)} gated cell(s), {len(in_shadow)} in shadow")
    if missing:
        print(f"\n  MISSING FROM SHADOW ({len(missing)}) -- passed a gate, gathering nothing:")
        for s, w, st in missing:
            print(f"    ({s!r}, {w!r}, {st!r})   <- from {', '.join(gated[(s, w, st)])}")
        print("\n  To add: append the tuple to SLEEVES in research/shadow_forward.py. "
              "Nothing else (protocol Part III, Step 3).")
    else:
        print("\n  every gated cell is in shadow")
    if orphan:
        print(f"\n  orphan ({len(orphan)}) -- in shadow, no report vouches. Not a failure:")
        for s, w, st in orphan:
            print(f"    ({s!r}, {w!r}, {st!r})")
    print(f"\n-> {OUT}")
    return 0 if not missing else 1


if __name__ == "__main__":
    raise SystemExit(main())
