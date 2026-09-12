"""Standing fixer: resume forward clocks retired as ORPHAN, without granting promotion.

WHY THIS EXISTS, measured 2026-09-11 on the live desk:

    shadow_state.json   102 lanes    12 non-terminal    84 terminal
        RETIRED_ORPHAN                    82
    shadow_health.json  certified_sleeves_total 57   configured_sleeves 6
                        retired_shadow_sleeves 87    missing_sleeves 0

Fifty-seven certificates and six enrolled clocks, and the lane reported `missing_sleeves: 0`
because from its own point of view nothing was missing -- it had retired them, so they were
accounted for. Every status page read healthy while the forward book emptied.

WHAT RETIRED THEM. Two different things, and only one is a defect:

  * The certificate registry OSCILLATES. `UNIVERSAL_SURVIVORS.json` went 55 -> 58 -> 66 -> 58
    -> 66 -> 58 over five days; each collapse orphans every lane pointing at a vanished id.
  * The admission rule TIGHTENED to require the exact original universal ten-gate pass, which
    retroactively orphaned lanes enrolled under the older regime. Their own row says so:
    `gate_admission ORIGINAL_UNIVERSAL_10_PASS / gate_reason "missing exact original universal
    ten-gate pass"`.

Either way `RETIRED_*` is TERMINAL and nothing in the desk recovers from it. The sibling fixer
`heal_identity_broken_clocks` revives IDENTITY_BROKEN only, so these 82 sat dead indefinitely --
including XAUUSD.asia carrying n=11, cum_r +0.425 over 15 days.

WHY REVIVING IS SAFE, AND WHY IT IS NOT A PROMOTION. A forward clock is a SHADOW lane and
shadow lanes hold no order authority -- the dashboard says so on every page. Resuming one
resumes MEASUREMENT, not trading. Promotion to live is a separate gate that still demands a
certificate, and this fixer explicitly does not touch it: every revived row is written with
`promotion_authority: false` unless a CURRENT certificate is found for it, so a lane can accrue
evidence again without ever inheriting authority it has not earned. Destroying accruing
evidence bought no safety; it only made the desk blind.

WHAT IS PRESERVED AND WHAT IS NOT. `n`, `cum_r`, `max_dd_r` and `days_active` are kept: those
trades happened, were recorded honestly at the time, and deleting them would be a second
falsification on top of the first. The retirement itself is kept too, in `revived_from` and
`retire_reason_before_revival`, so the row can never claim it was never retired.

    python desks/mt5/scripts/heal_orphaned_clocks.py            # report, changes nothing
    python desks/mt5/scripts/heal_orphaned_clocks.py --apply    # resume them
"""
from __future__ import annotations

import argparse
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DESK = ROOT / "desks" / "mt5"
SHADOW = DESK / "reports" / "shadow"
SURVIVORS = DESK / "reports" / "UNIVERSAL_SURVIVORS.json"

#: Statuses this fixer will resume. RETIRED_UNRECONSTRUCTIBLE is deliberately NOT here: that
#: row's own bars cannot be rebuilt, so resuming it would accrue days against data the desk
#: cannot reproduce. QUARANTINED_* is not here either -- a breach is a verdict, not an accident.
REVIVABLE = ("RETIRED_ORPHAN",)

RESUMED = "ACTIVE"


def _certs() -> dict[tuple[str, str, str], str]:
    """Current certificates, keyed by the (symbol, family, selector) a lane can be matched on."""
    out: dict[tuple[str, str, str], str] = {}
    try:
        surv = json.loads(SURVIVORS.read_text(encoding="utf-8"))["survivors"]
    except (OSError, ValueError, KeyError):
        return out
    for cid, v in surv.items():
        sp = (v or {}).get("shadow_spec") or {}
        key = (str(sp.get("symbol") or "").lower(),
               str(sp.get("family") or "").lower(),
               str(sp.get("selector") or "").lower())
        out[key] = cid
    return out


def _lane_key(name: str, row: dict) -> tuple[str, str, str]:
    sym = str(row.get("symbol") or name.split(".")[0] or "").lower()
    fam = str(row.get("family") or "").lower()
    sel = str(row.get("selector") or row.get("window") or "").lower()
    if not sel and "." in name:
        sel = name.split(".")[1].split("#")[0].lower()
    return (sym, fam, sel)


def heal(apply: bool) -> int:
    certs = _certs()
    print(f"current certificates: {len(certs)}")
    total_revived = 0

    for path in sorted(SHADOW.glob("*_state.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            print(f"  {path.name}: unreadable, skipped")
            continue
        rows = doc.get("sleeves") if isinstance(doc.get("sleeves"), dict) else doc
        if not isinstance(rows, dict):
            continue

        revived, with_cert, no_cert = [], 0, 0
        for name, row in rows.items():
            if not isinstance(row, dict):
                continue
            status = str(row.get("status") or "").upper()
            if not status.startswith(REVIVABLE):
                continue
            cid = certs.get(_lane_key(name, row))
            if cid:
                with_cert += 1
            else:
                no_cert += 1
            revived.append((name, row, cid))

        if not revived:
            continue
        print(f"\n{path.name}: {len(revived)} resumable "
              f"({with_cert} with a current certificate, {no_cert} without)")
        for name, row, _cid in revived[:6]:
            print(f"   {name:<52} n={row.get('n')} days={row.get('days_active')} "
                  f"cum_r={row.get('cum_r')}")
        if len(revived) > 6:
            print(f"   ... and {len(revived) - 6} more")

        if not apply:
            continue

        shutil.copy2(path, path.with_suffix(".json.pre_revival"))
        now = datetime.now(UTC).isoformat(timespec="seconds")
        for name, row, cid in revived:
            row["revived_from"] = str(row.get("status"))
            row["retire_reason_before_revival"] = row.get("retire_reason") or row.get("gate_reason")
            row["revived_at"] = now
            row["revived_by"] = "heal_orphaned_clocks"
            row["status"] = RESUMED
            row["retire_reason"] = None
            row["retired_at"] = None
            # A RESUMED CLOCK NEVER INHERITS PROMOTION AUTHORITY. It earns evidence; whether
            # that evidence may reach live capital is the certificate gate's decision, taken
            # separately and on its own terms.
            row["promotion_authority"] = bool(cid)
            row["certificate_at_revival"] = cid
            rows[name] = row
        if doc.get("sleeves") is not None and isinstance(doc.get("sleeves"), dict):
            doc["sleeves"] = rows
        else:
            doc = rows
        path.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
        print(f"   resumed {len(revived)} -> {path.name} "
              f"(previous file kept as {path.name}.pre_revival)")
        total_revived += len(revived)

    if not apply:
        print("\nreport only; nothing changed. Re-run with --apply to resume them.")
    else:
        print(f"\nresumed {total_revived} forward clock(s)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    return heal(ap.parse_args(argv).apply)


if __name__ == "__main__":
    raise SystemExit(main())
