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
#: Where certificates of a BANNED family go when they leave the survivors (2026-09-30).
BANNED_ARCHIVE = DESK / "reports" / "UNIVERSAL_SURVIVORS_BANNED.json"

#: WHY A BANNED CERTIFICATE IS EVICTED AND NEVER RE-HOMED. `discovered` is a generic executor of
#: whatever feature band the searcher found (`families_orthogonal.family_discovered`): the rule is
#: "feature F in quantile band B -> hold H bars", with no mechanism behind it. No registered family
#: computes that rule, so "re-homing" one would mint a DIFFERENT hypothesis under a legitimate name
#: -- the ban routed around, not honoured -- and the principal's order (2026-09-22) is that every
#: discovery certificate is discarded. Each row is kept whole in `retired_certificates` (which the
#: canon publisher never revives) and in BANNED_ARCHIVE, with the reason on it.
REHOME_REFUSED = ("no registered family computes this rule: `discovered` executes a searcher's "
                  "feature band with no mechanism, so any re-homing would be a different "
                  "hypothesis under a legitimate name; the principal's order is that every "
                  "discovery certificate is discarded")


def _family_of(key: str, row: dict[str, Any]) -> str:
    spec = row.get("shadow_spec") if isinstance(row.get("shadow_spec"), dict) else {}
    fam = str(spec.get("family") or row.get("family") or "")
    if not fam:
        parts = str(key).split(".")
        fam = parts[2] if len(parts) >= 3 else ""
    return fam


def banned_rows(docs: list[Any]) -> list[dict[str, Any]]:
    """Every certificate of a banned family in the given registries, with the decision on it."""
    try:
        from family_policy import ban_reason, family_banned
    except ImportError:                                           # pragma: no cover - path only
        from research.family_policy import ban_reason, family_banned
    out: dict[str, dict[str, Any]] = {}
    for doc in docs:
        rows = doc.get("survivors") if isinstance(doc, dict) else None
        for key, row in (rows or {}).items() if isinstance(rows, dict) else []:
            if not isinstance(row, dict) or key in out:
                continue
            fam = _family_of(str(key), row)
            if not family_banned(fam):
                continue
            spec = row.get("shadow_spec") if isinstance(row.get("shadow_spec"), dict) else {}
            out[str(key)] = {"key": str(key), "family": fam,
                             "symbol": spec.get("symbol") or row.get("sym"),
                             "params": spec.get("params"), "gated_at": row.get("gated_at"),
                             "decision": "EVICTED", "reason": ban_reason(fam),
                             "rehome": f"REFUSED: {REHOME_REFUSED}"}
    return [out[k] for k in sorted(out)]


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
    try:
        canon_doc = json.loads(CANON.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        canon_doc = {}
    banned = banned_rows([doc, canon_doc])
    banned_keys = {b["key"] for b in banned}
    zombies: list[dict[str, Any]] = []
    for key, row in rows.items():
        if not isinstance(row, dict) or key in banned_keys:
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
        "n_runnable": len(rows) - len(zombies) - len(set(rows) & banned_keys),
        "unrunnable": zombies,
        # BANNED BUT COUNTED IS NOT A STATE THIS REGISTRY MAY HOLD. Every banned-family
        # certificate is listed with its decision; `n_counted` is what the desk may believe.
        "n_banned": len(banned),
        "banned": banned,
        "n_counted": len(rows) - len(zombies) - len(set(rows) & banned_keys),
        "status": "ATTENTION" if (zombies or banned) else "OK",
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


def evict_banned(doc: dict[str, Any]) -> dict[str, Any]:
    """Move every banned-family certificate into `retired_certificates`, reason on each row.

    The seal's `retired_certificates` is the record `canon_publication` NEVER revives, so the
    eviction survives every republication; the survivors' `n` drops the same pass.
    """
    decisions = {b["key"]: b for b in doc.get("banned") or []}
    if not decisions:
        return {"evicted": 0}
    stamp = doc.get("at") or datetime.now(tz=UTC).isoformat(timespec="seconds")
    moved: dict[str, Any] = {}
    for path in (SURVIVORS, CANON):
        if not path.exists():
            continue
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        surv = d.get("survivors") or {}
        retired = d.get("retired_certificates")
        retired = retired if isinstance(retired, dict) else {}
        hit = [k for k in list(surv) if k in decisions]
        if not hit:
            continue
        for k in hit:
            row = surv.pop(k)
            entry = {**row, "retired_at": stamp, "retired_reason": decisions[k]["reason"],
                     "retired_by": "certificate_hygiene", "rehome": decisions[k]["rehome"]}
            retired[k] = entry
            moved[k] = entry
        d["survivors"] = surv
        d["n"] = len(surv)
        d["retired_certificates"] = retired
        prior = d.get("banned_evicted") if isinstance(d.get("banned_evicted"), list) else []
        d["banned_evicted"] = sorted(set(prior) | set(hit))
        path.write_text(json.dumps(d, indent=1, default=str), encoding="utf-8")
    archive: dict[str, Any] = {}
    if BANNED_ARCHIVE.exists():
        try:
            archive = (json.loads(BANNED_ARCHIVE.read_text(encoding="utf-8")) or {}).get(
                "survivors") or {}
        except (OSError, ValueError):
            archive = {}
    archive.update(moved)
    BANNED_ARCHIVE.write_text(json.dumps(
        {"at": stamp, "n": len(archive), "survivors": archive,
         "why": ("certificates of a family the principal banned; evicted with the reason on "
                 "each row and never re-homed -- " + REHOME_REFUSED)},
        indent=1, default=str), encoding="utf-8")
    return {"evicted": len(moved), "to": "retired_certificates + "
            + str(BANNED_ARCHIVE.relative_to(ROOT))}


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


def requeue_for_rejudge() -> dict[str, Any]:
    """EVERY EVICTION RE-ENTERS THE DOCKET, FIRST, WITH ITS PARAMS RECORDED.

    An eviction used to be a dead end: the row's own `why` says it can only come back on a
    fresh window, and nothing ever put it on one. `rejudge_evicted` writes one never-judged,
    fully-parameterised, stamped cell per evicted certificate to the front of the judge's docket,
    each parameter with its provenance, and the sealed gauntlet judges it like any other cell
    (charged to the same trial census). The same organ runs hourly from `requeue_unrunnable`, so
    this call is the eviction's own hook, not the only clock. Never raises: a failure here must
    not undo an eviction that already happened, and it is reported instead.
    """
    try:
        import rejudge_evicted
        doc = rejudge_evicted.run(apply_changes=True)
        return {"cells": len(doc.get("cells") or []), "refused": len(doc.get("refused") or []),
                "applied": doc.get("applied"), "report": str(rejudge_evicted.OUT)}
    except Exception as exc:                                      # noqa: BLE001
        return {"status": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}"}


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
        doc["banned_applied"] = evict_banned(doc)
        print(f"  banned: evicted {doc['banned_applied'].get('evicted', 0)} certificate(s) of a "
              f"banned family")
        doc["applied"] = apply(doc)
        print(f"  moved {doc['applied'].get('moved', 0)} row(s) -> "
              f"{doc['applied'].get('to')}")
        doc["rejudge"] = requeue_for_rejudge()
        print(f"  re-judge: {doc['rejudge']}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
