#!/usr/bin/env python3
"""THE BOX'S COPY OF THE AUDITOR'S REGISTRY -- the second record the gate asks for.

WHY (2026-11-10, #816). The gate lets the Auditor's `AUDIT CLEAR` comment adjudicate a failed
robot review only when a second, separate record agrees: the Auditor's own registry, as a file
on the box named by QUANT_AUDITOR_ROWS, fresh, whose latest row for the PR is a CLEAR of the
same head (audit_gate.auditor_row_agrees). The box cannot read the Auditor's workspace, so the
Auditor pushes its registry to one ref on origin and this script, on a schedule, copies it down.

    python ops/release/auditor_sync.py --repo-dir <clean LIVE checkout> --out <box file>

WHAT IT REFUSES (each leaves the old copy untouched, so it ages and the gate waits):
  * the ref or the file cannot be fetched;
  * any line that is not exactly {"pr": int, "sha": 40 hex, "verdict": "CLEAR"|"HOLD",
    "at": time with a zone} -- a missing key or an extra one refuses the whole registry;
  * a registry that is not the old copy plus appended rows. The record is append-only: a row
    that vanished could be a HOLD, so a rewritten history is never accepted here. Repairing
    one is a person's act at the box (delete the copy; the next run takes the ref whole);
  * an output path that is the gate's own owner-appended registry (QUANT_AUDIT_REGISTRY):
    that file is the owner's, and nothing automatic ever writes it.

WHAT IT TOUCHES IN THE CHECKOUT. One ref of its own, refs/auditor-sync/registry, and the
objects behind it. It never writes FETCH_HEAD (the adopter reads the one already on disk), the
index, the work tree, HEAD or any branch, so it takes no index or work-tree lock and does not
need the box's git-writer mutex: a ref update is atomic in git, and nothing else reads this ref.

WHAT A GOOD RUN DOES. Writes the copy atomically and stamps it now, also when nothing changed:
the stamp says "as of now the Auditor's registry holds no row this copy lacks", which is what
the gate's freshness limit asks.

WHAT THIS IS NOT. Every Claude session pushes through one GitHub identity, so the ref is not
proof of who wrote a row. It keeps an accidental self-CLEAR from merging; a deliberate forge
of both records needs an authenticated Auditor channel, which is the named follow-up.

THE MEMECOIN REGISTRY (2026-11-10 23:17Z, Governance). The Auditor keeps the memecoin repo's
verdicts in a second sole-writer file, MEMECOIN_FILE on the same ref. With --memecoin-out the
same run copies it, under the same rules, to the file memecoin_gate reads
(MEMECOIN_AUDIT_REGISTRY). Each file is synced or refused on its own; one refusal never blocks
the other, and the exit code is 1 if either was refused.

Exit 0 synced; 1 refused (the reason is printed and the old copy is kept).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REF = "refs/heads/audit-registry"
FILE = "REGISTRY_ROWS.jsonl"
MEMECOIN_FILE = "MEMECOIN_REGISTRY_ROWS.jsonl"
#: Where the fetched tip is kept in the checkout: a ref of this script's own, outside heads,
#: remotes and tags, so no branch, no adopter and no gate ever reads it.
LOCAL_REF = "refs/auditor-sync/registry"
KEYS = frozenset({"pr", "sha", "verdict", "at"})
OWNER_REGISTRY_ENV = "QUANT_AUDIT_REGISTRY"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
GIT_TIMEOUT_S = 120


class Refused(RuntimeError):
    pass


def check_rows(text: str) -> int:
    """The number of rows; raises Refused on the first line that is not a registry row."""
    n = 0
    for i, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except ValueError as exc:
            raise Refused(f"line {i} is not JSON") from exc
        if not isinstance(r, dict):
            raise Refused(f"line {i} is not an object")
        if set(r) != KEYS:
            raise Refused(f"line {i}: keys are not exactly {sorted(KEYS)}")
        pr, at = r.get("pr"), str(r.get("at") or "")
        if isinstance(pr, bool) or not isinstance(pr, int) or pr <= 0:
            raise Refused(f"line {i}: pr is not a positive integer")
        if not HEX40.match(str(r.get("sha") or "")):
            raise Refused(f"line {i}: sha is not 40 hex")
        if r.get("verdict") not in ("CLEAR", "HOLD"):
            raise Refused(f"line {i}: verdict is neither CLEAR nor HOLD")
        try:
            when = datetime.fromisoformat(at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise Refused(f"line {i}: at is not a time") from exc
        if when.tzinfo is None:
            raise Refused(f"line {i}: at has no time zone")
        n += 1
    return n


def _git(repo_dir: Path, *args: str) -> bytes:
    try:
        done = subprocess.run(["git", "-C", str(repo_dir), *args], capture_output=True,
                              timeout=GIT_TIMEOUT_S, check=False)  # fmt: skip
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise Refused(f"git {args[0]} did not run ({type(exc).__name__})") from exc
    if done.returncode != 0:
        raise Refused(f"git {args[0]} failed: {done.stderr.decode('utf-8', 'replace')[:200]}")
    return done.stdout


def fetch_ref(repo_dir: Path, ref: str = REF) -> None:
    """Fetch the ref's tip to LOCAL_REF. FETCH_HEAD is never written: the box adopter reads "the
    FETCH_HEAD already on disk" of the same checkout, and a sync landing in between would hand it
    this one-file tree (Auditor, #818)."""
    _git(repo_dir, "fetch", "-q", "--no-tags", "--no-write-fetch-head", "origin",
         f"+{ref}:{LOCAL_REF}")  # fmt: skip


def read_file(repo_dir: Path, name: str = FILE) -> str:
    """One registry file at the fetched tip (LOCAL_REF), as text."""
    out = _git(repo_dir, "show", f"{LOCAL_REF}:{name}")
    try:
        return out.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise Refused(f"{name} is not UTF-8") from exc


def fetch(repo_dir: Path, ref: str = REF, name: str = FILE) -> str:
    """The registry file at the ref's tip on origin, as text (fetch_ref, then read_file)."""
    fetch_ref(repo_dir, ref)
    return read_file(repo_dir, name)


def _lines(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def sync(new: str, out: Path, owner_registry: str | None = None) -> str:
    """Replace `out` with `new` when it is valid and extends the old copy; says what it did."""
    owner = owner_registry if owner_registry is not None else os.environ.get(OWNER_REGISTRY_ENV)
    if owner and Path(owner).resolve() == out.resolve():
        raise Refused(f"{out} is the owner's registry ({OWNER_REGISTRY_ENV}): never written here")
    n = check_rows(new)
    old_n = 0
    if out.exists():
        try:
            old = _lines(out.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeDecodeError) as exc:
            raise Refused(f"the old copy is unreadable ({type(exc).__name__})") from exc
        old_n = len(old)
        if _lines(new)[:old_n] != old:
            raise Refused("the registry is not the old copy plus appended rows (append-only)")
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text("".join(ln + "\n" for ln in _lines(new)), encoding="utf-8")
    os.replace(tmp, out)  # a new file: its stamp is now, also when no row was added
    return f"synced {n} row(s), {n - old_n} new"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--memecoin-out", type=Path, help="memecoin_gate's MEMECOIN_AUDIT_REGISTRY")
    ap.add_argument("--ref", default=REF)
    a = ap.parse_args(argv)
    if a.memecoin_out is not None and a.memecoin_out.resolve() == a.out.resolve():
        print("auditor-sync: REFUSED -- --memecoin-out is the same file as --out")
        return 1
    try:
        fetch_ref(a.repo_dir, a.ref)
    except Refused as exc:
        print(f"auditor-sync: REFUSED -- {exc}; every old copy is kept and will read stale")
        return 1
    rc = 0
    jobs = [(FILE, a.out)] + ([(MEMECOIN_FILE, a.memecoin_out)] if a.memecoin_out else [])
    for name, out in jobs:
        try:
            print(f"auditor-sync {name}: {sync(read_file(a.repo_dir, name), out)}")
        except Refused as exc:
            print(f"auditor-sync {name}: REFUSED -- {exc}; the old copy is kept")
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
