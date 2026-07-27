"""CLAIM ESCALATOR -- turns a detected false claim into a blocker nobody can walk past.

Detection without escalation changes nothing. The NAV gap sat inside venue_divergence_shadow for
FOUR DAYS, widening 36% -> 176%, while every dashboard read green and no one was paged. A finding
in a JSON file is not a control; a finding wired into the channels that gate action is.

Separate from claim_verifier.py on purpose: DETECT and ACT are different jobs, and keeping them
apart means a bug in escalation cannot corrupt detection.

Every CRITICAL/HIGH claim failure is written to BOTH channels the desk already honours:
  data/PRINCIPAL_ACTION.md  -- the human pager (max_audit already uses it, so it is read)
  docs/GATE0_QUEUE.md       -- the live-capital blocker list

Idempotent: re-running on the same day does not duplicate entries. Read-only w.r.t. the desk's
data; it only appends to the two escalation surfaces.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "data/claim_verification.json"
PAGER = ROOT / "data/PRINCIPAL_ACTION.md"
QUEUE = ROOT / "docs/GATE0_QUEUE.md"
NL = chr(10)


def main() -> None:
    if not REPORT.exists():
        print("no claim_verification.json -- run claim_verifier.py first")
        return
    rep = json.loads(REPORT.read_text("utf-8"))
    crit = [c for c in rep.get("claims", []) if c.get("severity") in ("CRITICAL", "HIGH")]
    print("=== CLAIM ESCALATOR ===")
    print(f"    {rep.get('checked')} claims checked, {rep.get('failed')} failed, "
          f"{len(crit)} at CRITICAL/HIGH")
    if not crit:
        print("    nothing to escalate -- every claim survived contact with its source")
        return

    stamp = datetime.now(tz=UTC).date().isoformat()
    head = f"CLAIM-VERIFIER {stamp}: {len(crit)} unverified claim(s) -- DESK STATE DISPUTED"

    # --- pager -------------------------------------------------------------------------
    prev = PAGER.read_text("utf-8") if PAGER.exists() else ""
    if head in prev:
        print("    pager: already raised today (idempotent, no duplicate)")
    else:
        lines = [head, ""]
        for c in crit:
            lines.append(f"  - [{c['severity']}] {c['claim']}")
            lines.append(f"      claims : {c['claimed']}")
            lines.append(f"      source : {c['actual']}")
            lines.append(f"      why it matters: {c['consequence']}")
        lines.append("")
        PAGER.write_text(NL.join(lines) + NL + prev, "utf-8")
        print(f"    PAGED principal -> {PAGER.name}")

    # --- Gate-0 blocker queue ------------------------------------------------------------
    if QUEUE.exists():
        g = QUEUE.read_text("utf-8")
        add = []
        for c in crit:
            key = f"CV-{stamp}-{c['claim'][:26]}"
            if key in g:
                continue
            add.append(f"| CV | **{c['claim']}** `({key})` | claims `{c['claimed']}` but the "
                       f"source says `{c['actual']}` -- {c['consequence']} | BEFORE any live "
                       f"capital |")
        if add:
            QUEUE.write_text(g + NL + NL.join(add) + NL, "utf-8")
            print(f"    QUEUED {len(add)} Gate-0 blocker(s) -> {QUEUE.name}")
        else:
            print("    Gate-0 queue: already listed (idempotent)")

    print()
    for c in crit:
        print(f"    [{c['severity']}] {c['claim']}")
    print(f"{NL}    A claim failure is not a note -- it BLOCKS Gate-0 until explained.")


if __name__ == "__main__":
    main()
