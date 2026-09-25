"""PRE-REGISTRATION FENCE -- a donation that fails to pre-register is a LOUD defect.

Pre-registration is what separates a TESTED hypothesis from a FITTED one. Without a card hashed
before the evidence existed, the desk cannot claim a cell's specification was fixed before its
result was seen -- which is the single thing the whole ten-gate apparatus exists to establish.
The deflated-Sharpe charge, the walk-forward split and the lockbox all assume the specification
came first. A certificate issued on an unpre-registered cell is weaker than it reads.

WHAT WAS MEASURED, 2026-09-23, across every donation row on the trading box:

    537,933 donation rows in 23,114 contract files
      2,908 carried a `prereg_hash`                             -> 0.54%
        535,025 did not
     28 of 28 standing certificates rest on cells with NO pre-registration -- and decisively so:
        the EARLIEST card in the ledger is 2026-09-05T12:39, the LATEST certificate was gated
        2026-09-02T23:37. Every standing certificate predates the entire ledger, so no join
        subtlety can rescue one; there is no card that could have preceded any of their evidence.

The cause was three compounding faults in the donation path, all fixed in
`libs/research/preregistration.py` and `desks/mt5/research/proposer_common._preregister`: a
`horizon` derivation that read a key occurring zero times while missing the two that occur, a
try block wrapped around the whole loop so one bad row silenced the batch, and a bare
`except Exception: pass` that hid all of it for the path's entire 19-day life.

THE PAST IS NOT BACKFILLED. A card written after the verdict is a forgery of the exact guarantee
pre-registration provides, so rows donated before the cutover are MARKED
`RETROSPECTIVELY_UNPREREGISTERED` -- honestly, permanently, and counted here -- never issued a
card. This fence judges only what was donated after the fix could run.

It never argues for donating less. Coverage is raised by pre-registering MORE rows, never by
mining fewer; the failure counts here are a measurement defect, never a reason to narrow intake.

    python scripts/check_preregistration.py [--json] [--report-only]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.research.preregistration import (  # noqa: E402
    LEDGER,
    RETROSPECTIVELY_UNPREREGISTERED,
    UNDECLARED,
)

#: THE CUTOVER. Rows donated at or after this instant are judged; rows before it are the
#: retrospectively unpre-registered corpus and can never honestly be repaired.
#:
#: Dated to the first full day after the fix can REACH THE TRADING BOX, not the day it was
#: written. The box adopts hourly at :12 and donates every hour in between, so a cutover set to
#: the writing date would fail on rows the fixed code never touched -- a fence that cries wolf on
#: a correct tree gets switched off, which is how enforcement dies. It may only ever move
#: EARLIER: pushing it later to dodge a breach would be the denominator trick, retiring the
#: evidence instead of fixing the path.
CUTOVER = "2026-09-25T00:00:00+00:00"

_INTEL = (_ROOT / "desks" / "mt5" / "data" / "intelligence",
          _ROOT / "data" / "intelligence")
_SURVIVORS = _ROOT / "desks" / "mt5" / "reports" / "UNIVERSAL_SURVIVORS.json"
_OUT = _ROOT / "desks" / "mt5" / "reports" / "PREREG_COVERAGE.json"


def _j(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _rel(p: Path) -> str:
    """Repo-relative when it can be (a scan root given by a test lives outside the tree)."""
    try:
        return str(p.relative_to(_ROOT))
    except ValueError:
        return str(p)


def scan_donations(roots: tuple[Path, ...] = _INTEL) -> dict[str, Any]:
    """Count every donated row and how many carry a pre-registration hash."""
    rows = hashed = files = unreadable = 0
    post_rows = post_hashed = 0
    stamped_failed = 0
    by_seat: dict[str, dict[str, int]] = {}
    reasons: dict[str, int] = {}
    offenders: list[dict[str, Any]] = []
    for root in roots:
        if not root.exists():
            continue
        for p in sorted(root.rglob("discoveries_*.json")):
            files += 1
            doc = _j(p)
            if not isinstance(doc, dict):
                unreadable += 1
                continue
            disc = doc.get("discoveries")
            if not isinstance(disc, list):
                continue
            gen = str(doc.get("generated_at") or "")
            seat = str(doc.get("source") or p.parent.name)
            post = bool(gen) and gen >= CUTOVER
            seat_row = by_seat.setdefault(seat, {"rows": 0, "hashed": 0, "post_rows": 0,
                                                 "post_hashed": 0})
            for c in disc:
                if not isinstance(c, dict):
                    continue
                rows += 1
                seat_row["rows"] += 1
                has = bool(c.get("prereg_hash"))
                if has:
                    hashed += 1
                    seat_row["hashed"] += 1
                elif c.get("prereg_status"):
                    # A NAMED failure: the absence was recorded rather than swallowed.
                    stamped_failed += 1
                    why = str(c.get("prereg_failure") or c.get("prereg_status"))[:120]
                    reasons[why] = reasons.get(why, 0) + 1
                if post:
                    post_rows += 1
                    seat_row["post_rows"] += 1
                    if has:
                        post_hashed += 1
                        seat_row["post_hashed"] += 1
                    elif len(offenders) < 25:
                        offenders.append({"file": _rel(p), "seat": seat,
                                          "generated_at": gen,
                                          "symbol": c.get("symbol"),
                                          "prereg_status": c.get("prereg_status"),
                                          "why": c.get("prereg_failure")})
    return {"files": files, "unreadable_files": unreadable, "rows": rows, "hashed": hashed,
            "coverage": (hashed / rows) if rows else None,
            "post_cutover_rows": post_rows, "post_cutover_hashed": post_hashed,
            "post_cutover_coverage": (post_hashed / post_rows) if post_rows else None,
            "post_cutover_uncovered": post_rows - post_hashed,
            "rows_with_named_failure": stamped_failed,
            "retrospectively_unpreregistered": rows - hashed - stamped_failed,
            "failure_reasons": dict(sorted(reasons.items(), key=lambda kv: -kv[1])[:15]),
            "post_cutover_offenders": offenders,
            "by_seat": dict(sorted(by_seat.items(), key=lambda kv: -kv[1]["rows"])[:25])}


def read_cards(path: Path = LEDGER) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        text = path.read_text("utf-8", errors="replace")
    except OSError:
        return out
    for ln in text.splitlines():
        if ln.strip():
            try:
                out.append(json.loads(ln))
            except ValueError:
                continue
    return out


def certificates(cards: list[dict[str, Any]],
                 path: Path = _SURVIVORS) -> dict[str, Any]:
    """Which standing certificates rest on a cell pre-registered BEFORE its evidence was seen.

    MEASURED AND PUBLISHED, NEVER ACTED ON HERE. Nothing is retired and no threshold moves: this
    reports the STRENGTH of the evidence the desk is already acting on, which the principal is
    owed honestly. A certificate on an unpre-registered cell is not void -- it is a certificate
    whose specification cannot be proven to predate its result, and it should be read that way.
    """
    surv = _j(path)
    if not isinstance(surv, dict):
        return {"measured": False, "why": f"no survivor store at {path}"}
    survivors = surv.get("survivors")
    if not isinstance(survivors, dict):
        return {"measured": False, "why": "survivor store carries no `survivors` map"}
    by_sym: dict[str, list[str]] = {}
    for c in cards:
        uni = c.get("universe")
        for u in (uni if isinstance(uni, list) else [uni]):
            if u:
                by_sym.setdefault(str(u), []).append(str(c.get("registered_utc") or ""))
    earliest = min((str(c.get("registered_utc") or "~") for c in cards), default="")
    rows = []
    for key, s in survivors.items():
        if not isinstance(s, dict):
            continue
        gated = str(s.get("gated_at") or "")
        sym = str(s.get("sym") or "")
        before = [t for t in by_sym.get(sym, []) if t and gated and t < gated]
        rows.append({"certificate": key, "sym": sym, "gated_at": gated,
                     "cards_for_symbol_before_gate": len(before),
                     "preregistered": bool(before)})
    n_pre = sum(1 for r in rows if r["preregistered"])
    return {"measured": True, "standing": len(rows), "preregistered": n_pre,
            "unpreregistered": len(rows) - n_pre,
            "earliest_card_registered_utc": earliest,
            "latest_certificate_gated_at": max((r["gated_at"] for r in rows), default=""),
            "rule": ("a certificate whose cell holds no card registered before its gate is "
                     "RETROSPECTIVELY UNPREREGISTERED: its ten gates ran, and its specification "
                     "cannot be shown to predate its evidence"),
            "rows": sorted(rows, key=lambda r: r["certificate"])}


def evaluate() -> dict[str, Any]:
    t0 = time.time()
    cards = read_cards()
    don = scan_donations()
    certs = certificates(cards)
    undeclared = sum(1 for c in cards if c.get("horizon") == UNDECLARED)
    if not don["rows"]:
        status = "UNMEASURED"          # no donation corpus here: a real answer, never a pass
    elif don["post_cutover_rows"] == 0:
        status = "UNMEASURED_POST_CUTOVER"
    elif don["post_cutover_uncovered"] > 0:
        status = "BREACH"
    else:
        status = "OK"
    return {
        "checked": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "elapsed_s": round(time.time() - t0, 1),
        "status": status,
        "cutover": CUTOVER,
        "law": ("pre-registration is the claim that the specification preceded the evidence; a "
                "donation that cannot make it is a defect, never a silence"),
        "donations": don,
        "ledger": {"cards": len(cards),
                   "horizon_UNDECLARED": undeclared,
                   "horizon_undeclared_share": (undeclared / len(cards)) if cards else None,
                   "note": ("a card whose horizon is UNDECLARED still froze the rest of the "
                            "specification before the verdict; it is weaker than one that "
                            "pinned a holding period, and it says so on its face rather than "
                            "inventing one")},
        "certificates": certs,
        "retrospective_marker": RETROSPECTIVELY_UNPREREGISTERED,
        "no_backfill": ("rows donated before the cutover are NEVER issued a card. Writing one "
                        "after the evidence was seen would fabricate the exact guarantee "
                        "pre-registration exists to provide, and would be worse than the defect"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--report-only", action="store_true", help="always exit 0")
    args = ap.parse_args()

    rep = evaluate()
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep, indent=1, default=str), "utf-8")

    don = rep["donations"]
    if args.json:
        print(json.dumps(rep, indent=1, default=str))
    else:
        cov = don["coverage"]
        print(f"preregistration | {rep['status']} | "
              f"{don['hashed']}/{don['rows']} rows carry a prereg_hash"
              f" ({'n/a' if cov is None else f'{cov:.2%}'})")
        print(f"  post-cutover ({CUTOVER}): {don['post_cutover_hashed']}/"
              f"{don['post_cutover_rows']} covered, {don['post_cutover_uncovered']} uncovered")
        print(f"  retrospectively unpreregistered rows: "
              f"{don['retrospectively_unpreregistered']} (never backfilled)")
        c = rep["certificates"]
        if c.get("measured"):
            print(f"  standing certificates: {c['unpreregistered']}/{c['standing']} rest on "
                  f"cells with NO card registered before their gate")
        for row in don["post_cutover_offenders"][:5]:
            print(f"  UNCOVERED {row['seat']:24} {row['generated_at']} {row['why'] or ''}")
    if args.report_only:
        return 0
    return 1 if rep["status"] == "BREACH" else 0


if __name__ == "__main__":
    raise SystemExit(main())
