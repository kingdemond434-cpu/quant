"""Name every certificate that has no forward clock, and say why -- per certificate.

    py -3 desks\\mt5\\scripts\\check_enrolment_gap.py

WHAT THIS REPLACES. The issue board says:

    23 runnable certificate(s) are on no forward clock ...
    Check the shadow_forward log for ENROL-GAP lines naming each refusal.

That instruction cannot be followed usefully. The log is append-only and interleaved with every
other pass, the ENROL-GAP lines from a run three hours ago look identical to this hour's, and a
certificate that is missing because nothing ever REACHED it prints no line at all -- so the
loudest failures are the ones already understood and the silent ones stay silent.

THE ARITHMETIC THE BOARD DOES, AND WHAT IT CANNOT SEE. `certs:clockless` is
`certified - unrunnable - forward_clocks`: three aggregate counts from two different artifacts.
It is a correct subtraction and it names nothing. This joins the two populations by KEY instead,
so the answer is a list of certificates rather than a number.

THREE CAUSES, WHICH NEED THREE DIFFERENT FIXES AND LOOK IDENTICAL IN THE COUNT:

  REFUSED       `shadow_forward.certified_sleeves()` declined to enrol it, and says why:
                no window mapping for the selector, no resolvable constructor, or a SHORT
                certificate on a family that takes no `side`. A wiring gap; the log line is real.
  NO ROW        it passed enrolment and no row exists in any lane file. This is the silent one --
                nothing refused it, the engine simply never got that far, and it prints nothing.
  BLOCKED       a row EXISTS carrying a reason (BLOCKED_NO_BARS is the common one: the terminal
                served no history for that symbol). Those rows still count as clocks in the
                dashboard's arithmetic, so a BLOCKED certificate is NOT part of the clockless
                figure -- it is reported here anyway, because "has a clock" and "is accruing
                evidence" are different claims and only one of them is what the desk needs.

Reads only. It changes nothing and enrols nothing; `research/shadow_forward.py` is the enroller.
"""
from __future__ import annotations

import collections
import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parent.parent
REPO = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SHADOW_DIR = DESK / "reports" / "shadow"
LANES = ("shadow_state.json", "qquant_shadow_state.json",
         "scalp_shadow_state.json", "external_shadow_state.json")


def _rows_on_clocks() -> dict[str, dict[str, Any]]:
    """Every forward row across all four lanes, keyed as the lanes key them."""
    out: dict[str, dict[str, Any]] = {}
    for name in LANES:
        path = SHADOW_DIR / name
        try:
            doc = json.loads(path.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        items = list(doc.items())
        nested = doc.get("sleeves")
        if isinstance(nested, dict):
            items += list(nested.items())
        for key, row in items:
            if isinstance(row, dict) and "status" in row:
                out.setdefault(key, {**row, "_lane": name})
    return out


def main() -> int:
    try:
        import shadow_forward as sf
        from shadow_admission import authorized_runs
    except Exception as exc:                                            # noqa: BLE001
        print(f"FATAL: cannot import the forward engine ({type(exc).__name__}: {exc})")
        return 2

    # certified_sleeves() logs its refusals to stdout; capture them so each can be attributed to
    # the certificate it refused rather than left in a shared log.
    buf = io.StringIO()
    with redirect_stdout(buf):
        enrolled = sf.certified_sleeves()
        runs = authorized_runs(sf.BASE)
    refusals = [ln for ln in buf.getvalue().splitlines() if "ENROL-GAP" in ln]

    enrolled_keys = {
        sf.sleeve_key(sym, win, params, fam, side): (sym, win, fam, side)
        for sym, win, params, fam, side in enrolled
    }
    clocks = _rows_on_clocks()

    print("ENROLMENT GAP")
    print(f"  authorized runnable certificates : {len(runs)}")
    print(f"  passed enrolment                 : {len(enrolled)}")
    print(f"  refused at enrolment             : {len(runs) - len(enrolled)}")
    print(f"  forward rows across {len(LANES)} lanes     : {len(clocks)}")
    print()

    no_row: list[str] = []
    blocked: list[tuple[str, str]] = []
    for key in sorted(enrolled_keys):
        row = clocks.get(key)
        if row is None:
            no_row.append(key)
        elif str(row.get("status", "")).upper().startswith("BLOCKED"):
            blocked.append((key, str(row.get("last_error") or row.get("status"))))

    if refusals:
        print(f"REFUSED AT ENROLMENT ({len(refusals)}) -- a wiring gap, named by the engine:")
        for line in refusals:
            print(f"  {line.split('ENROL-GAP:', 1)[-1].strip()[:150]}")
        print()

    if no_row:
        # THE SILENT ONE. Nothing refused these and no row exists: the engine never reached them.
        # A pass that dies partway, a lane file rewritten from a stale snapshot, or a symbol the
        # loop skipped before it could write anything all land here and print nothing anywhere.
        print(f"PASSED ENROLMENT BUT HAVE NO ROW ({len(no_row)}) -- nothing refused these:")
        for key in no_row:
            sym, win, fam, side = enrolled_keys[key]
            print(f"  {key:52} {fam} {side}")
        print("  -> run: py -3 research\\shadow_forward.py   (the enroller; writes the rows)")
        print()

    if blocked:
        print(f"HAVE A ROW BUT ARE ACCRUING NOTHING ({len(blocked)}):")
        for key, why in blocked:
            print(f"  {key:52} {why[:90]}")
        print("  -> these COUNT as clocks in the board's arithmetic; the cure is bars, not")
        print("     enrolment: subscribe the symbol in Market Watch and backfill its history.")
        print()

    by_family = collections.Counter(enrolled_keys[k][2] for k in no_row)
    if by_family:
        print("MISSING ROWS BY FAMILY:", dict(by_family))
    if not no_row and not refusals:
        print("VERDICT: every runnable certificate is enrolled. Any clockless figure on the")
        print("         board is then a counting difference, not an enrolment gap -- compare")
        print("         the census basis against the lane files rather than re-running the engine.")
    return 0


if __name__ == "__main__":                                              # pragma: no cover
    raise SystemExit(main())
