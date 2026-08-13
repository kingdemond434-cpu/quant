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
  the 218-section MASTER, whole -- authority may not be truncated or replaced
  the DOCTRINE's own "CONSTITUTION (immutable ...)" block -- the copy that is INJECTED into
    every organ at spawn, and until R0392 the only one of the three under no seal at all

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

#: THE THIRD BODY OF CONSTITUTIONAL TEXT, AND IT WAS THE ONLY UNSEALED ONE (R0392).
#:
#: `ops/principal_doctrine.txt` carries a block delimited by the two markers below and labelled, in
#: its own words, "CONSTITUTION (immutable, governs every answer you give)". Measured 2026-08-12,
#: whitespace-normalised: its 27 substantive lines appear in NEITHER sealed document -- 0/27 in
#: `docs/CONSTITUTION.md` and 0/27 in the 218-section master. It is not a restatement of either; it
#: is a disjoint third core.
#:
#: WHY THAT IS THE EXPENSIVE ONE TO LEAVE UNSEALED: the doctrine is the copy that is actually
#: INJECTED, verbatim, into every organ at spawn (`ops/brain_env.sh` cats the file into
#: `$_DOCTRINE`, which every seat receives as its appended system prompt). So the desk sealed the
#: two documents that describe its behaviour and left unsealed the one that CAUSES it. Any agent
#: editing this file could silently rewrite text calling itself immutable -- weakening SURVIVAL,
#: RATCHET or IMMUTABLE CORE -- and this fence would print "core intact" on the same run.
#: L2.8a bars core edits in either direction and had no instrument here: the desk's own
#: "a duty with no instrument is a wish" (L1.46) pointed at its own constitutional core.
#:
#: SCOPE IS THE DELIMITED BLOCK, NEVER THE WHOLE FILE. The doctrine legitimately grows every week
#: as duties land; a seal over all 88KB would be red by tomorrow, and a fence red from day one gets
#: switched off (L1.43). Only the text that declares itself immutable is held immutable.
_DOCTRINE_REL = Path("ops/principal_doctrine.txt")
_DOCTRINE_OPEN = "=== CONSTITUTION (immutable"
_DOCTRINE_CLOSE = "=== END CONSTITUTION ==="
#: A floor on the block's substantive line count, checked BEFORE the hash. Without it, deleting
#: every line between the markers leaves a well-formed, stably-hashing, EMPTY core that a
#: `--seal-doctrine` run would happily bless: a verdict over an empty population is vacuous, never
#: a pass (L1.57). Set below the measured 27 so honest editing inside the block is not a breach --
#: any edit at all still fails the hash, which is the point; this floor only refuses to seal a
#: gutted block in the first place.
_DOCTRINE_MIN_LINES = 20


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


def doctrine_current() -> tuple[dict[str, object] | None, list[str]]:
    """Digest the doctrine's self-declared immutable block -- the core that is actually injected.

    Returns ``(payload, errors)`` with the same contract as :func:`master_current`. The line count
    travels WITH the hash because a hash alone cannot distinguish "this block is intact" from
    "this block is now two lines and hashes fine" (L1.57): the seal records what it counted.
    """
    path = _ROOT / _DOCTRINE_REL
    if not path.is_file():
        return None, [f"{_DOCTRINE_REL.as_posix()} is missing -- the injected core is unreadable"]
    try:
        text = _canonical_text_bytes(path.read_text("utf-8", errors="strict")).decode("utf-8")
    except (UnicodeDecodeError, OSError) as exc:
        return None, [f"doctrine is unreadable: {exc}"]
    lines = text.split("\n")
    opens = [i for i, ln in enumerate(lines) if ln.startswith(_DOCTRINE_OPEN)]
    closes = [i for i, ln in enumerate(lines) if ln.strip() == _DOCTRINE_CLOSE]
    if len(opens) != 1 or len(closes) != 1:
        # Ambiguity is a violation, not a parse to guess at: two opens means a reader cannot say
        # which block is the core, and zero means the delimiters were removed -- the cheapest
        # attack on a delimiter-scoped seal, exactly as clause DELETION is on a clause-scoped one.
        return None, [f"doctrine constitution markers are not exactly one pair "
                      f"(open={len(opens)}, close={len(closes)})"]
    if closes[0] < opens[0]:
        return None, ["doctrine constitution block closes before it opens"]
    body = [ln for ln in lines[opens[0] + 1:closes[0]] if ln.strip()]
    if len(body) < _DOCTRINE_MIN_LINES:
        return None, [f"doctrine constitution block has {len(body)} substantive line(s), "
                      f"below the floor of {_DOCTRINE_MIN_LINES} -- it has been gutted"]
    return {
        "path": _DOCTRINE_REL.as_posix(),
        "sha256": _digest("\n".join(body)),
        "lines": len(body),
    }, []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reseal", action="store_true",
                    help="PRINCIPAL ONLY: accept the current core as the new baseline")
    ap.add_argument("--seal-doctrine", action="store_true",
                    help="Establish the FIRST baseline for the doctrine's constitution block. "
                         "Refuses if one already exists, or if anything else has drifted.")
    args = ap.parse_args()
    now = current()
    master, master_errors = master_current()
    doctrine, doctrine_errors = doctrine_current()
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
        if missing or master_errors or doctrine_errors:
            print(
                f"REFUSING TO SEAL: protected clause(s) missing={missing}; "
                f"master={master_errors}; doctrine={doctrine_errors}"
            )
            return 2
        _LOCK.parent.mkdir(parents=True, exist_ok=True)
        _LOCK.write_text(json.dumps(
            {"sealed": datetime.now(tz=UTC).isoformat(),
             "note": "L2.8a immutable core. Changing this file is a PRINCIPAL action; the "
                     "organism may not reseal itself as part of an amendment.",
             "digests": now, "master": master, "doctrine": doctrine}, indent=2), "utf-8")
        print(f"constitution core SEALED over {len(now)} clauses -> "
              f"{_LOCK.relative_to(_ROOT)}")
        return 0

    lock_payload = json.loads(_LOCK.read_text("utf-8"))

    if args.seal_doctrine:
        # STRICTLY WEAKER THAN --reseal, AND DELIBERATELY SO. --reseal rewrites every digest, so
        # running it to pick up a newly-protected artifact would bless any concurrent drift in the
        # clauses it was not aiming at -- the reseal trap, and the reason a first baseline needed
        # its own door. This one can ADD the doctrine entry and nothing else: it refuses if the
        # entry already exists (re-baselining an edited core stays a PRINCIPAL act via --reseal),
        # and it refuses unless everything already sealed verifies intact FIRST, so it can never
        # be the instrument that launders a core edit. `sealed`, `digests` and `master` are carried
        # through byte-identical.
        if lock_payload.get("doctrine") is not None:
            print("REFUSING: the doctrine block is already sealed. Re-baselining a sealed core "
                  "is a PRINCIPAL action -- use --reseal after reading the block yourself.")
            return 2
        if missing or master_errors or doctrine_errors:
            print(f"REFUSING TO SEAL: clause(s) missing={missing}; master={master_errors}; "
                  f"doctrine={doctrine_errors}")
            return 2
        drift_now = [p for p in _PROTECTED if lock_payload["digests"].get(p) != now.get(p)]
        if drift_now or lock_payload.get("master") != master:
            print(f"REFUSING TO SEAL: the existing seal does not verify (clause drift={drift_now}, "
                  "master drift="
                  f"{lock_payload.get('master') != master}). Resolve that first -- a first "
                  "baseline may never be taken over an already-broken seal.")
            return 2
        lock_payload["doctrine"] = doctrine
        _LOCK.write_text(json.dumps(lock_payload, indent=2), "utf-8")
        assert doctrine is not None                        # doctrine_errors was empty
        print(f"doctrine constitution block SEALED ({doctrine['lines']} lines, "
              f"{str(doctrine['sha256'])[:12]}) -> {_LOCK.relative_to(_ROOT)}")
        return 0
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
    if doctrine_errors:
        print(f"DOCTRINE VIOLATION: {doctrine_errors}")
        return 1
    sealed_doctrine = lock_payload.get("doctrine")
    if doctrine is not None and not isinstance(sealed_doctrine, dict):
        print("DOCTRINE VIOLATION: the injected constitution block exists but has no seal")
        print("  It is the copy every organ receives at spawn -- seal it: --seal-doctrine")
        return 1
    # COMPARED ON THE HASH, NOT THE WHOLE PAYLOAD -- and the difference is load-bearing enough that
    # the test for it caught this on its first run. `lines` travels with the seal so the artifact
    # records what it counted (L1.57), but it must not VOTE: the digest is whitespace-normalised so
    # re-wrapping a paragraph is not a breach, while a line COUNT changes on exactly that edit.
    # Comparing the whole dict made a cosmetic re-flow print "the injected immutable block was
    # edited" over two identical hashes -- a fence that cries wolf on a re-wrap is muted by the
    # first cosmetic edit and then protects nothing (L1.43). Gutting is still refused, by the
    # independent floor in doctrine_current(), which runs on every verify.
    if doctrine is not None and sealed_doctrine.get("sha256") != doctrine["sha256"]:
        print("DOCTRINE VIOLATION -- the injected immutable block was edited:")
        print(f"  sealed {str(sealed_doctrine.get('sha256'))[:12]} "
              f"({sealed_doctrine.get('lines')} lines) != now "
              f"{str(doctrine.get('sha256'))[:12]} ({doctrine.get('lines')} lines)")
        print("  L2.8a: this is the core that STEERS every organ; it may not be edited in "
              "either direction. A deliberate PRINCIPAL amendment re-seals with --reseal.")
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
        "sealed 218-section master + "
        f"{doctrine['lines'] if doctrine else 0}-line injected doctrine block verified)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
