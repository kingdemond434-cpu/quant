"""ZOMBIE CERTIFICATES -- passed all ten gates, can never be enrolled, still counted.

`survivor_publication.unrunnable_reason` is the desk's single judge of whether a certificate can
ever be enrolled, and it exists because four separate publishers disagreed about what a
publishable certificate was -- one refused `params is None`, the other three minted rows without
it. Its own docstring records the damage: "18 certificates that passed all ten gates, are counted
in every survivor total, inflate the desk's belief about its own edge, and can never be enrolled,
funded or falsified."

THE JUDGE PROTECTS NEW ROWS AND HAS NEVER BEEN ASKED ABOUT OLD ONES. Both writers in
`external_gauntlet` now emit `params: dict(params or {})`, so nothing new can be born unrunnable.
But the rows minted BEFORE that fix are still in the registry, still counted, and still unrunnable
-- measured 2026-09-12, six of them, each surfacing as an `ENROL-GAP` line on every forward
reconcile: "`shadow_spec.params` is NoneType, not a mapping -- unrunnable without guessing the
parameterization that passed."

WHY THIS IS NOT A COSMETIC COUNT. The certificate total is what the desk believes about its own
edge, and every one of those rows cost a share of a FIXED family-wise error budget that every
other hypothesis then had to clear. A zombie is therefore worse than a blank: it spent the scarce
resource, it inflates the belief, and it can never return anything. And because it looks like a
survivor, a reader counting 67 certificates cannot tell that 6 of them are uncashable.

IT NEVER GUESSES THE MISSING PARAMETERS, and that boundary is the whole reason these cannot simply
be repaired. `shadow_admission` forbids inventing lost parameters from a display name: a gauntlet
run on guessed parameters certifies a strategy nobody is actually trading, which is a worse
outcome than an honest eviction. So the row is MOVED, never fixed and never deleted -- the
evidence stays auditable in its own file, exactly as GOLD_RETIRED_VOIDED does for windows.

    python desks/mt5/research/certificate_hygiene.py [--apply]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SURVIVORS = DESK / "reports" / "UNIVERSAL_SURVIVORS.json"
CANON = DESK / "data" / "UNIVERSAL_SURVIVORS.canon.json"
EVICTED = DESK / "reports" / "UNIVERSAL_SURVIVORS_UNRUNNABLE.json"
OUT = DESK / "reports" / "CERTIFICATE_HYGIENE.json"


def build() -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    try:
        from survivor_publication import unrunnable_reason
    except ImportError as exc:
        return {"at": now.isoformat(timespec="seconds"), "status": "UNMEASURED",
                "why": f"the judge is not importable ({exc}) -- UNMEASURED, never 'all runnable'"}
    try:
        doc = json.loads(SURVIVORS.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {"at": now.isoformat(timespec="seconds"), "status": "UNMEASURED",
                "why": f"registry unreadable: {type(exc).__name__}: {exc}"}

    rows = doc.get("survivors") or {}
    zombies: list[dict[str, Any]] = []
    for key, row in rows.items():
        if not isinstance(row, dict):
            continue
        why = unrunnable_reason(row)
        if why:
            spec = row.get("shadow_spec") or {}
            zombies.append({
                "key": key, "why": why,
                "symbol": spec.get("symbol"), "family": spec.get("family"),
                "selector": spec.get("selector"),
                "gated_at": row.get("gated_at"),
                "hunt": row.get("hunt"),
            })
    return {
        "at": now.isoformat(timespec="seconds"),
        "n_certificates": len(rows),
        "n_unrunnable": len(zombies),
        "n_runnable": len(rows) - len(zombies),
        "unrunnable": zombies,
        "status": "ATTENTION" if zombies else "OK",
        "rule": ("the judge is survivor_publication.unrunnable_reason -- the same predicate every "
                 "publisher now asks before minting. Nothing new is invented here."),
        "boundary": ("parameters are NEVER guessed. shadow_admission forbids reconstructing lost "
                     "parameters from a display name, because a gauntlet run on guessed "
                     "parameters certifies a strategy nobody is trading -- worse than an honest "
                     "eviction. Rows are MOVED to their own file, never repaired, never deleted."),
        "why_it_matters": ("the certificate count is what the desk believes about its own edge, "
                           "and each of these spent a share of a FIXED family-wise error budget "
                           "every other hypothesis then had to clear."),
    }


def apply(doc: dict[str, Any]) -> dict[str, Any]:
    """Move the unrunnable rows out of the registry into their own file."""
    keys = {z["key"] for z in doc.get("unrunnable") or []}
    if not keys:
        return {"moved": 0}
    moved: dict[str, Any] = {}
    for path in (SURVIVORS, CANON):
        if not path.exists():
            continue
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        surv = d.get("survivors") or {}
        for k in list(surv):
            if k in keys:
                moved[k] = surv.pop(k)
        d["survivors"] = surv
        d["n"] = len(surv)
        d["unrunnable_evicted"] = sorted(keys)
        d["unrunnable_note"] = (
            "rows whose shadow_spec cannot be enrolled were moved to "
            "reports/UNIVERSAL_SURVIVORS_UNRUNNABLE.json. They passed the gates and cannot be "
            "run; counting them inflated the desk's belief about its own edge.")
        path.write_text(json.dumps(d, indent=1, default=str), encoding="utf-8")
    prior: dict[str, Any] = {}
    if EVICTED.exists():
        try:
            prior = (json.loads(EVICTED.read_text(encoding="utf-8")) or {}).get("survivors") or {}
        except (OSError, ValueError):
            prior = {}
    prior.update(moved)
    EVICTED.write_text(json.dumps(
        {"at": doc["at"], "n": len(prior), "survivors": prior,
         "why": ("passed the ten gates and cannot be enrolled -- kept in full so the evidence "
                 "stays auditable and a future certificate can revive the mechanism on a FRESH "
                 "pre-registered window, never by inheriting this row.")},
        indent=1, default=str), encoding="utf-8")
    return {"moved": len(moved), "to": str(EVICTED.relative_to(ROOT))}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="move the unrunnable rows out")
    a = ap.parse_args(argv)
    doc = build()
    print(f"certificate hygiene: {doc.get('status')}  "
          f"{doc.get('n_certificates', 0)} certificate(s), "
          f"{doc.get('n_unrunnable', 0)} unrunnable")
    for z in (doc.get("unrunnable") or [])[:12]:
        print(f"  {z.get('symbol')!s:<10} {str(z.get('family'))[:24]:<24} {z['why'][:70]}")
    if a.apply:
        doc["applied"] = apply(doc)
        print(f"  moved {doc['applied'].get('moved', 0)} row(s) -> "
              f"{doc['applied'].get('to')}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
