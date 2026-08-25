#!/usr/bin/env python3
"""Money-path content fence (GAP 128) -- canon files defend themselves in the shared tree.

MEASURED ATTACK, 2026-08-25: a sibling session overwrote gateway.py and promoter.py with a
stale 478-line ancestor at 19:39/19:43/19:46 -- twice within minutes of a manual restore --
and the hourly tree-sweep committer then wrote the stale versions into history (cbeb287d).
Manual restores lose that race by construction; this fence runs on a clock and restores canon
whenever a protected file loses its canon MARKER (a symbol that exists only in the canonical
version and in no ancestor). A marker check beats a hash pin because legitimate new work on
these files keeps its markers and passes untouched.

    python3 scripts/check_moneypath_fence.py          # restore + commit if breached; exit 1
"""
from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "data" / "moneypath_fence.log"

#: Known-good commit holding every protected file with its marker; the fallback source when
#: HEAD itself has been swept stale. Advancing this pin is a deliberate act in a commit that
#: also changes the protected file -- never automatic.
CANON_COMMIT = "b239108d"

#: file -> marker that exists ONLY in the canonical lineage of that file.
PROTECTED = {
    "desks/mt5/mt5desk/gateway.py": "run_family_sleeves",
    "desks/mt5/mt5desk/sizing.py": "BASE_RISK_FRAC",
    "desks/mt5/research/promoter.py": "authorized_specs",
    "desks/mt5/research/qquant_shadow.py": "PROMOTION_CANDIDATE",
    "desks/mt5/moat/moat_recorder.py": "copy_ticks_range",
    "desks/mt5/moat/moat_fence.py": "symbols_floor",
}


def log(msg: str) -> None:
    line = f"{datetime.now(tz=UTC).isoformat(timespec='seconds')} {msg}"
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line)


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                          timeout=120, check=False)


def head_has_marker(path: str, marker: str) -> bool:
    r = git("show", f"HEAD:{path}")
    return r.returncode == 0 and marker in r.stdout


def main() -> int:
    breached: list[str] = []
    for path, marker in PROTECTED.items():
        f = ROOT / path
        try:
            ok = f.is_file() and marker in f.read_text("utf-8", errors="ignore")
        except OSError:
            ok = False
        if ok:
            continue
        src = "HEAD" if head_has_marker(path, marker) else CANON_COMMIT
        r = git("checkout", src, "--", path)
        if r.returncode == 0:
            log(f"BREACH+RESTORED {path}: marker '{marker}' missing; restored from {src}")
            breached.append(path)
        else:
            log(f"BREACH UNRESTORABLE {path}: {r.stderr.strip()[:200]}")
            breached.append(path)
    if not breached:
        return 0
    # Commit ONLY the protected paths, so a sweep cannot re-commit the stale content on top
    # of a restored tree. Explicit paths per R0423; never -A.
    git("add", "--", *breached)
    r = git("commit", "-m",
            f"moneypath fence: restored {len(breached)} canon file(s) after shared-tree "
            f"revert (GAP 128)\n\nFiles: {', '.join(breached)}\n"
            f"The fence restores by canon marker; see data/moneypath_fence.log.")
    log(f"fence commit rc={r.returncode} for {breached}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
