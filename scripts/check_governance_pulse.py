"""GOVERNANCE AS A WEAPON -- the two governing documents enforced in the GROWTH direction.

WHY (principal 2026-08-27: "governance principles enforcing watchdogs so our two big ones always
get followed for maximum growth and survivors -- not strict conservative idle watching; the
enforcement must never flip into the opposite"). LAWS.md and RESEARCH.md are not brake pads.
Their operative clauses are THROUGHPUT clauses: unwired-or-idle is a DEFECT (III.16), a gate
that never ran is an uncashed claim (L1.49), coverage RATCHETS UP (L1.50), "exhausted" needs
per-axis evidence (L1.51), and every survivor claim must MOVE (desks/mt5 CLAUDE.md: "never let
a survivor sit un-actioned"). This fence measures whether the machine is hunting, testing, and
promoting AT CAPACITY -- and its breaches trigger the machinery, never a slowdown. The gates'
thresholds themselves are sealed and are NOT touched here: rigour stays; idleness dies.

Floors are a RATCHET (data/governance_ratchet.json): once the desk demonstrates a throughput,
falling durably below it is a breach. Floors only rise.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DESK = ROOT / "desks" / "mt5"
RATCHET = ROOT / "data" / "governance_ratchet.json"
OUT = ROOT / "web" / "governance_pulse.json"


def _read(p: Path):
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def main() -> int:
    now = datetime.now(tz=UTC)
    breaches: list[str] = []
    m: dict = {"at": now.isoformat(timespec="seconds")}
    ratchet = _read(RATCHET) or {"floors": {}}
    floors = ratchet.setdefault("floors", {})

    # --- L1.49/III.16: the gauntlet must JUDGE at demonstrated capacity, every hour
    gates = _read(DESK / "reports" / "universal_gates_external.json") or {}
    judged = int(gates.get("n_judged") or 0)
    m["judged_last_sweep"] = judged
    floor_j = int(floors.get("judged_per_sweep") or 0)
    if judged > floor_j:
        floors["judged_per_sweep"] = judged        # the ratchet only rises
    elif floor_j and judged < max(50, floor_j // 4):
        breaches.append(f"GAUNTLET: judged {judged} cells against a demonstrated capacity of "
                        f"{floor_j} -- the machine is idling far below what it has proven; "
                        f"idleness is the defect, not the cure")

    # --- the docket must offer the gauntlet real work
    docket = _read(DESK / "data" / "hypotheses" / "external_survivors.json")
    n_docket = len(docket) if isinstance(docket, list) else 0
    m["docket"] = n_docket
    floor_d = int(floors.get("docket") or 0)
    if n_docket > floor_d:
        floors["docket"] = n_docket
    elif floor_d and n_docket < max(100, floor_d // 10):
        breaches.append(f"DOCKET: {n_docket} candidates against a demonstrated {floor_d} -- "
                        f"the search is under-feeding the gates")

    # --- survivors must MOVE: a claim sitting un-actioned is a violation, not a wait
    ledger = _read(DESK / "reports" / "SURVIVORS_LEDGER.json") or {}
    rows = ledger.get("claims") if isinstance(ledger, dict) else None
    rows = rows if isinstance(rows, list) else (ledger if isinstance(ledger, list) else [])
    stuck = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        status = str(r.get("status") or "").upper()
        ts = str(r.get("updated_at") or r.get("claimed_at") or "")
        if status in ("CLAIMED", "UNIVERSAL", "SIGNAL_GATE") and ts:
            try:
                age_h = (now - datetime.fromisoformat(ts.replace("Z", "+00:00"))
                         .astimezone(UTC)).total_seconds() / 3600
                if age_h > 24:
                    stuck.append(f"{r.get('claim') or r.get('cell')}({status} {age_h:.0f}h)")
            except ValueError:
                continue
    m["ledger_claims"] = len(rows)
    m["ledger_stuck"] = len(stuck)
    if stuck:
        breaches.append(f"LEDGER: {len(stuck)} survivor claim(s) sitting un-actioned >24h -- "
                        f"'never let a survivor sit un-actioned across a session': "
                        f"{', '.join(stuck[:4])}")

    # --- L1.50 breadth: certified families and hunted classes only ratchet up
    surv = _read(DESK / "reports" / "UNIVERSAL_SURVIVORS.json") or {}
    fams = {str(v.get("shadow_spec", {}).get("family") or "?")
            for v in (surv.get("survivors") or {}).values() if isinstance(v, dict)}
    m["certified_families"] = len(fams)
    floor_f = int(floors.get("certified_families") or 0)
    if len(fams) > floor_f:
        floors["certified_families"] = len(fams)
    elif floor_f and len(fams) < floor_f:
        breaches.append(f"BREADTH: certified families fell {floor_f} -> {len(fams)} -- "
                        f"coverage ratchets UP (L1.50); a lost family is a lost mechanism")

    RATCHET.parent.mkdir(parents=True, exist_ok=True)
    ratchet["updated_at"] = m["at"]
    RATCHET.write_text(json.dumps(ratchet, indent=1), "utf-8")
    OUT.write_text(json.dumps({"at": m["at"],
                               "verdict": "AT CAPACITY" if not breaches else "IDLING",
                               "breaches": breaches, "measurements": m,
                               "floors": floors}, indent=1), "utf-8")
    if not breaches:
        print(f"governance: AT CAPACITY (judged={judged} docket={n_docket} "
              f"families={len(fams)} floors={floors})")
        return 0
    print(f"GOVERNANCE IDLING {m['at']}")
    for b in breaches:
        print(f"  - {b}")
    try:
        import sys
        sys.path.insert(0, str(ROOT / "scripts"))
        from auto_fixers import apply
        apply(list(breaches))
    except Exception as exc:
        print(f"  fixers unavailable: {exc}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
