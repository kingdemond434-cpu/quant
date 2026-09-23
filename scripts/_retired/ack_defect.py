"""ACK A MAX-AUDIT DEFECT -- the writer data/max_audit_acks.json never had.

THE GAP (governance audit, 2026-07-30): max_audit has read acks since the day it was built --
`acks.get(did)` with a reason and an expiry, "no permanent burial, ever" -- but NOTHING WRITES the
file. It did not exist. So the desk ran 26 live defects with 0 acked, including states everyone
had already accepted (the R0044 vrp exception), and the daily report was noise stacked on signal.
An ack path that requires hand-editing JSON is an ack path nobody uses, and un-ackable defects get
mentally muted -- which is burial by another name, minus the paper trail.

THE RULES, enforced here rather than hoped for (they are max_audit's own doctrine, header lines
14-18):
  * every ack carries a REASON a reader in six months can act on (>=12 chars);
  * every ack EXPIRES -- 30 days maximum, no permanent burial, ever;
  * an ack names WHO accepted the state;
  * acking a defect id that is not currently live is refused -- pre-acking future defects is
    exactly the silent-burial move the expiry rule exists to prevent.

    python scripts/ack_defect.py                          # list live defects with their ids
    python scripts/ack_defect.py --id organ-never-kimi \
        --reason "blocked on OpenRouter funding, principal decision 2026-07-30" --days 14 --by zaid
    python scripts/ack_defect.py --prune                  # drop expired acks (audit also ignores them)
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_ACKS = _ROOT / "data/max_audit_acks.json"
#: R0393: REPO-scope acks go in the TRACKED registry so they travel with the commit that reasons
#: about them. The routing input costs nothing -- max_audit already records `scope` per defect in
#: the report this script reads to validate the id.
_ACKS_REPO = _ROOT / "data/max_audit_acks_repo.json"
_REPORT = _ROOT / "data/max_audit_report.json"
_MAX_DAYS = 30


def _registry_for(scope: str) -> tuple[Path, str]:
    """Which registry an ack of this scope belongs in, and why.

    RUNTIME defects rest on untracked evidence -- a clone can neither confirm nor close them -- so
    their disposition is genuinely per-box. Everything else (REPO, and UNSCOPED which max_audit
    escalates as REPO so unknown provenance is never an excuse) is identically true in every
    checkout and must be disposed of where every checkout can see it.
    """
    if scope == "RUNTIME":
        return _ACKS, ("RUNTIME -- the evidence is untracked, so this ack is correctly per-box "
                       "and stays out of git")
    return _ACKS_REPO, (f"{scope} -- true in every checkout, so the ack is TRACKED and must be "
                        "committed, or it keeps firing (and escalating) everywhere else")


def _load(p: Path) -> dict:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return {}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", dest="did", help="defect id to ack (as printed by max_audit)")
    ap.add_argument("--reason", default="", help="why this below-max state is accepted, for now")
    ap.add_argument("--days", type=int, default=14, help=f"expiry in days (max {_MAX_DAYS})")
    ap.add_argument("--by", default="", help="who accepts it")
    ap.add_argument("--prune", action="store_true", help="remove expired acks and exit")
    args = ap.parse_args()

    now = datetime.now(tz=UTC)

    if args.prune:
        # BOTH registries. Pruning only the local one would let expired tracked acks linger as
        # permanent burial -- the one thing this script's own rules forbid outright.
        total = 0
        for path in (_ACKS, _ACKS_REPO):
            acks = _load(path)
            if not acks:
                continue
            keep = {k: v for k, v in acks.items() if str(v.get("until", "")) > now.isoformat()}
            path.write_text(json.dumps(keep, indent=2), "utf-8")
            print(f"{path.name}: pruned {len(acks) - len(keep)} expired ack(s); "
                  f"{len(keep)} remain")
            total += len(acks) - len(keep)
        print(f"pruned {total} expired ack(s) in total")
        return 0

    report = _load(_REPORT)
    live = {d.get("id"): d.get("msg", "") for d in report.get("live", [])}
    scopes = {d.get("id"): str(d.get("scope") or "UNSCOPED") for d in report.get("live", [])}
    if not args.did:
        if not live:
            print("no live defects in data/max_audit_report.json (run scripts/max_audit.py first)")
            return 0
        print(f"{len(live)} live defect(s):")
        for did, msg in live.items():
            print(f"  {did}: {str(msg)[:100]}")
        print("\nack one: python scripts/ack_defect.py --id <id> --reason '...' --days N --by <name>")
        return 0

    if args.did not in live:
        print(f"REFUSED: {args.did!r} is not a LIVE defect. Pre-acking a defect that is not "
              "currently firing is the silent-burial move the expiry rule exists to prevent. "
              "Run scripts/max_audit.py, confirm it fires, then ack it.")
        return 2
    if len(args.reason.strip()) < 12:
        print("REFUSED: the reason is the record. State why this below-max state is accepted, in "
              "a sentence a reader in six months can act on.")
        return 2
    if not args.by.strip():
        print("REFUSED: --by is required. An accepted state nobody owns is a buried one.")
        return 2
    if not (1 <= args.days <= _MAX_DAYS):
        print(f"REFUSED: expiry must be 1..{_MAX_DAYS} days. No permanent burial, ever -- the "
              "audit re-fires when the ack lapses, which is the point.")
        return 2

    scope = scopes.get(args.did, "UNSCOPED")
    path, why = _registry_for(scope)
    acks = _load(path)
    acks[args.did] = {
        "reason": args.reason.strip(), "by": args.by.strip(),
        "acked": now.isoformat(),
        "until": (now + timedelta(days=args.days)).isoformat(),
        #: The scope this ack was ROUTED on, recorded beside it. A later reader asking why an ack
        #: sits in one file rather than the other should not have to re-derive it from a run that
        #: may no longer produce the same defect.
        "scope": scope,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(acks, indent=2), "utf-8")
    print(f"acked {args.did} for {args.days}d (expires {acks[args.did]['until'][:10]}) -- "
          f"max_audit will report it as [acked] until then, then re-fire")
    print(f"  -> {path.relative_to(_ROOT)}  [{why}]")
    if path is _ACKS_REPO:
        print("  COMMIT IT. An uncommitted tracked ack is a per-box ack wearing a tracked "
              "filename, and the defect keeps escalating on every other checkout.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
