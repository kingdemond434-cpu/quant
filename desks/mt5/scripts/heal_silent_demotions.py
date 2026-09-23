"""Standing fixer: restore LIVE sleeves demoted to STANDBY with no reason recorded.

MEASURED 2026-09-11 on the big box, 56 minutes after the desk moved there:

    data/sleeves.json   65 rows   LIVE 44   STANDBY 21
    all 21 STANDBY rows: "(no reason recorded)"

The roster carried 65 LIVE rows at cutover. An organ rewrote it at 21:04 and 21 rows came back
STANDBY -- including every scalp but one, and 16 of the 53 certified family survivors -- with
no `retire_reason`, no `status_reason`, and nothing in any log naming a cell. The book shrank
by a third and no artifact said why.

A DEMOTION WITHOUT A REASON IS NOT A VERDICT. That is the same law the desk applies everywhere
else: absence never resolves to a clean verdict (WS-005 / L1.28a), and a retirement that does
not propagate its cause is a rename rather than a retirement (the 2026-08-26 RETIRED_ORPHAN
lesson, which cost 82 forward clocks). A promoter that demotes for cause records the cause; a
demotion that records nothing is indistinguishable from a file that was rewritten by something
that never read the row at all -- and this desk has spent the whole day finding exactly that.

WHAT IT WILL NOT DO. A row demoted WITH a reason is left alone, always. That is the promoter
doing its job -- automatic retirement is standing policy and this fixer never overrides a
judgement someone actually made. Only the silent ones are restored, and each restoration is
stamped so the next reader can tell a revived row from one that was never touched.

RESTORING LIVE IS NOT SIZING. A LIVE row is REACHABLE, not funded: `cap_by_heat` still prices
it, the allocator still decides its fraction, and the release identity still has to be clean
for anything to place. Restoring reachability cannot by itself put on a position.

    python desks/mt5/scripts/heal_silent_demotions.py            # report
    python desks/mt5/scripts/heal_silent_demotions.py --apply    # restore
"""
from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SLEEVES = ROOT / "desks" / "mt5" / "data" / "sleeves.json"

#: Fields any organ demoting for cause is expected to leave behind. If none carries text, the
#: demotion recorded nothing and this fixer treats it as an accident rather than a decision.
REASON_FIELDS = ("retire_reason", "status_reason", "reason", "why", "demoted_reason",
                 "retired_reason", "gate_reason")

#: Statuses this fixer will lift back to LIVE. STANDBY is the promoter's holding state; KILL,
#: RETIRED and QUARANTINED are verdicts and are never touched here whatever they do or do not
#: record, because lifting a verdict is a different act needing a different justification.
LIFTABLE = ("STANDBY",)


def _reason(row: dict) -> str:
    for f in REASON_FIELDS:
        v = row.get(f)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def heal(apply: bool) -> int:
    doc = json.loads(SLEEVES.read_text(encoding="utf-8"))
    rows = doc["sleeves"]
    by_status = Counter(str(r.get("status") or "?") for r in rows)
    print(f"roster: {len(rows)} rows   {dict(by_status)}")

    silent, reasoned = [], []
    for r in rows:
        if str(r.get("status") or "").upper() not in LIFTABLE:
            continue
        (reasoned if _reason(r) else silent).append(r)

    print(f"\nSTANDBY with a recorded reason : {len(reasoned)}  (left alone -- a real verdict)")
    for r in reasoned[:4]:
        print(f"   {str(r.get('name'))[:46]:<48} {_reason(r)[:70]}")
    print(f"STANDBY with NO reason         : {len(silent)}  (restorable)")
    for r in silent[:8]:
        print(f"   {str(r.get('name'))[:46]:<48} exec={r.get('exec')} sym={r.get('symbol')}")
    if len(silent) > 8:
        print(f"   ... and {len(silent) - 8} more")

    if not silent:
        print("\nnothing to restore")
        return 0
    if not apply:
        print("\nreport only; nothing changed. Re-run with --apply to restore them.")
        return 0

    shutil.copy2(SLEEVES, SLEEVES.with_suffix(".json.pre_undemote"))
    now = datetime.now(UTC).isoformat(timespec="seconds")
    for r in silent:
        r["status"] = "LIVE"
        r["restored_from"] = "STANDBY"
        r["restored_at"] = now
        r["restored_by"] = "heal_silent_demotions"
        r["restored_why"] = ("demoted to STANDBY with no reason recorded on any of "
                             f"{', '.join(REASON_FIELDS)}; a demotion that records nothing is "
                             "not a verdict")
    SLEEVES.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    after = Counter(str(x.get("status") or "?") for x in rows)
    print(f"\nrestored {len(silent)} row(s) -> {dict(after)}")
    print(f"previous file kept as {SLEEVES.name}.pre_undemote")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    return heal(ap.parse_args(argv).apply)


if __name__ == "__main__":
    raise SystemExit(main())
