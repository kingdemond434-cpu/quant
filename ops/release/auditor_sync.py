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
  * any line that is not {"pr": int, "sha": 40 hex, "verdict": "CLEAR"|"HOLD", "at": time};
  * a registry that is not the old copy plus appended rows. The record is append-only: a row
    that vanished could be a HOLD, so a rewritten history is never accepted here. Repairing
    one is a person's act at the box (delete the copy; the next run takes the ref whole);
  * an output path that is the gate's own owner-appended registry (QUANT_AUDIT_REGISTRY):
    that file is the owner's, and nothing automatic ever writes it.

WHAT A GOOD RUN DOES. Writes the copy atomically and stamps it now, also when nothing changed:
the stamp says "as of now the Auditor's registry holds no row this copy lacks", which is what
the gate's freshness limit asks.

WHAT THIS IS NOT. Every Claude session pushes through one GitHub identity, so the ref is not
proof of who wrote a row. It keeps an accidental self-CLEAR from merging; a deliberate forge
of both records needs an authenticated Auditor channel, which is the named follow-up.

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


def fetch(repo_dir: Path, ref: str = REF, name: str = FILE) -> str:
    """The registry file at the ref's tip on origin, as text."""
    for args in (("fetch", "-q", "--no-tags", "origin", ref), ("show", f"FETCH_HEAD:{name}")):
        try:
            done = subprocess.run(["git", "-C", str(repo_dir), *args], capture_output=True,
                                  timeout=GIT_TIMEOUT_S, check=False)  # fmt: skip
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise Refused(f"git {args[0]} did not run ({type(exc).__name__})") from exc
        if done.returncode != 0:
            raise Refused(f"git {args[0]} failed: {done.stderr.decode('utf-8', 'replace')[:200]}")
    try:
        return done.stdout.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise Refused("the registry is not UTF-8") from exc


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
    ap.add_argument("--ref", default=REF)
    a = ap.parse_args(argv)
    try:
        print(f"auditor-sync: {sync(fetch(a.repo_dir, a.ref), a.out)}")
    except Refused as exc:
        print(f"auditor-sync: REFUSED -- {exc}; the old copy is kept and will read stale")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
