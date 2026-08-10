"""IMMUTABLE-CORE FENCE -- the one law autonomous evolution may not edit (L2.8a, 2026-07-30).

The principal granted the organism permission to amend its own constitution, provided every change
serves the two supreme objectives. That grant is only safe because of L2.8a's IMMUTABLE CORE, and
a core that is merely WRITTEN is exactly the decoration this desk keeps finding. So it is hashed.

WHAT IT PROTECTS, and why each one:
  L1.23  survival rails (ruin <=2%, Tier-3 never loosened, size only on proven edge)
  L1.6   statistical validation -- the two-stage law and the never-loosen direction
  L1.1   the objective function itself
  L1.2   the objective hierarchy
  L2.8a  the immutable core, including the clause saying it is immutable

THE FAILURE MODE IT EXISTS FOR, stated plainly: a self-improving optimiser that may rewrite its own
limits will eventually notice that the cheapest way to raise a measured return is to lower the rail
constraining it. That is not evolution; it is the optimiser eating its safety margin. One ruin event
ends all compounding -- the same asymmetry L1.23 is built on.

HOW IT WORKS: each protected clause is normalised (whitespace-collapsed) and SHA-256'd into
`data/constitution_core.lock`. Any later edit changes the hash and FAILS this check. The lock is
committed, so the diff shows exactly which law moved.

DELIBERATE DESIGN CHOICE: a changed hash is NOT auto-reverted. Reverting would let a bug silently
undo a legitimate principal amendment. It FAILS LOUD and names the clause; a human confirms with
--reseal, which is the only path that rewrites the lock. Autonomy everywhere else; a human hand
on this one.

    python scripts/check_constitution_core.py            # verify (exit 1 on drift)
    python scripts/check_constitution_core.py --reseal   # principal-only: accept a new core
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_CONST = _ROOT / "docs/CONSTITUTION.md"
_LOCK = _ROOT / "data/constitution_core.lock"
_MASTER_REL = Path("docs/MASTER_QUANT_CONSTITUTION.md")
_MASTER_SECTIONS = tuple(range(218))

_PROTECTED = ("L1.1", "L1.2", "L1.6", "L1.23", "L2.8a")


def _clause(pid: str, text: str) -> str | None:
    """The full text of one clause: from its bold id to the next bold id."""
    m = re.search(rf"^\*\*{re.escape(pid)}\s.*?(?=^\*\*L\d)", text, re.MULTILINE | re.DOTALL)
    return m.group(0) if m else None


def _digest(body: str) -> str:
    # Whitespace-normalised so reflowing a paragraph is not a false alarm; every WORD still counts.
    return hashlib.sha256(" ".join(body.split()).encode("utf-8")).hexdigest()


def _canonical_text_bytes(text: str) -> bytes:
    """Stable UTF-8 bytes across Git/OS newline conversion.

    The principal seal protects words and structure, not whether a checkout used LF or CRLF.
    Hashing canonical text prevents core.autocrlf from creating a false constitutional breach
    after an otherwise equivalent deploy or recheckout.
    """
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def current() -> dict[str, str | None]:
    text = _CONST.read_text("utf-8")
    out: dict[str, str | None] = {}
    for pid in _PROTECTED:
        body = _clause(pid, text)
        out[pid] = _digest(body) if body else None
    return out


def master_current() -> tuple[dict[str, object] | None, list[str]]:
    """Digest and structurally verify the principal-sealed top-level master.

    The L1.x document remains the executable companion. The 218-section master is authority, so
    losing, truncating or silently replacing it must fail the same entry gate as a core edit.
    """
    path = _ROOT / _MASTER_REL
    if not path.is_file():
        return None, [f"{_MASTER_REL.as_posix()} is missing"]
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        return None, [f"master is not valid UTF-8: {exc}"]
    sections = tuple(int(x) for x in re.findall(r"^# (\d+)\.", text, re.MULTILINE))
    errors: list[str] = []
    if sections != _MASTER_SECTIONS:
        errors.append(
            f"master section sequence is not 0..217 exactly (found {len(sections)} headings)"
        )
    for phrase in (
        "SINGLE AUTHORITATIVE TOP-LEVEL OPERATING CONSTITUTION",
        "24 HOURS PER DAY.",
        "CONSTITUTION FREEZE DEFAULT",
        "FREEZE PROSE.",
    ):
        if phrase not in text:
            errors.append(f"master missing load-bearing phrase: {phrase}")
    return {
        "path": _MASTER_REL.as_posix(),
        "sha256": hashlib.sha256(_canonical_text_bytes(text)).hexdigest(),
        "sections": len(sections),
    }, errors


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reseal", action="store_true",
                    help="PRINCIPAL ONLY: accept the current core as the new baseline")
    args = ap.parse_args()
    now = current()
    master, master_errors = master_current()
    missing = [p for p, d in now.items() if d is None]

    if not _LOCK.exists() and not args.reseal:
        # DELIBERATE: a missing lock does NOT auto-seal. Auto-sealing looks convenient and is the
        # hole -- on any fresh clone or restored box the fence would silently bless whatever
        # constitution it found, including a tampered one, and report "intact". The lock is
        # committed (see .gitignore negation) so this state means the seal was LOST, which is
        # itself the finding.
        print(f"NO SEAL: {_LOCK.relative_to(_ROOT)} is missing -- the immutable core is unprotected.")
        print("  It is a committed artifact; a missing lock means it was deleted or never restored.")
        print("  Restore it from git, or --reseal ONLY if you have read the current core yourself.")
        return 1

    if args.reseal:
        if missing or master_errors:
            print(
                f"REFUSING TO SEAL: protected clause(s) missing={missing}; "
                f"master={master_errors}"
            )
            return 2
        _LOCK.parent.mkdir(parents=True, exist_ok=True)
        _LOCK.write_text(json.dumps(
            {"sealed": datetime.now(tz=UTC).isoformat(),
             "note": "L2.8a immutable core. Changing this file is a PRINCIPAL action; the "
                     "organism may not reseal itself as part of an amendment.",
             "digests": now, "master": master}, indent=2), "utf-8")
        print(f"constitution core SEALED over {len(now)} clauses -> "
              f"{_LOCK.relative_to(_ROOT)}")
        return 0

    lock_payload = json.loads(_LOCK.read_text("utf-8"))
    lock = lock_payload["digests"]
    drift = [p for p in _PROTECTED if lock.get(p) != now.get(p)]
    if missing:
        print(f"CORE VIOLATION: protected clause(s) DELETED from the constitution: {missing}")
        return 1
    if master_errors:
        print(f"MASTER VIOLATION: {master_errors}")
        return 1
    sealed_master = lock_payload.get("master")
    if master is not None and not isinstance(sealed_master, dict):
        print("MASTER VIOLATION: authoritative master exists but has no principal seal")
        return 1
    if master is not None and sealed_master != master:
        print("MASTER VIOLATION: authoritative master metadata or hash drifted")
        print(
            f"  sealed {str(sealed_master.get('sha256'))[:12]} != "
            f"now {str(master.get('sha256'))[:12]}"
        )
        return 1
    if drift:
        print("CORE VIOLATION -- an immutable clause was edited:")
        for p in drift:
            print(f"  {p}: sealed {str(lock.get(p))[:12]} != now {str(now.get(p))[:12]}")
        print("  L2.8a: evolution may raise a bar, never lower one, and may never touch the core.")
        print("  If this edit is a deliberate PRINCIPAL amendment, re-seal with --reseal.")
        return 1
    print(
        f"constitution core intact ({len(_PROTECTED)} clauses + "
        "sealed 218-section master verified)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
