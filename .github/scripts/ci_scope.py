"""Does this PR touch anything but prose under docs/, reports/ or logs/? Prints `heavy=true|false`.

WHY (2026-11-11). About 1,036 Actions runs were queued, 797 of them on PRs' current heads.
Each push starts ci (quality, mt5-money-path, coverage-floor) and release-gates (risk-invariants,
replay-shadow, independent-review). A PR that only adds a note under docs/ or a box report ran
the full suite, ahead of the code PRs waiting for the same free runners.

THE RULE IS AN ALLOWLIST. `heavy=false` only when EVERY changed path (both sides of a rename) is
either one of SKIP_FILES (the decision journal, the desk lessons) or a PROSE file (PROSE_EXTS)
under one of SKIP_PREFIXES (docs/, reports/, logs/ and the desk's docs/ and logs/), AND none of
them is:
  - a code or config file type anywhere (audit_gate.CODE_SPECS: *.py, *.ps1, *.yml, *.txt ...);
  - under a folder the live book reads (desks/mt5/data/, desks/mt5/reports/, data/), at ANY depth
    (#983 audit M2: decision_core reads desks/mt5/data/universe/universe.json; box state is not
    on the allowlist at all, so replay-shadow judges every change to it);
  - governed state (libs.ops.release.is_governed_state: pins, sign rows, survivor canon,
    allocator proof, live manifest, switches);
  - PROTECTED, formerly protected or in ops/release/protected_paths.txt, or a secrets path, or a
    governing document (audit_gate.FORCED_LIVE), all read from the gate itself.
Any doubt is heavy: an unreadable file list, a count that does not match the PR's, a head that
moved, an import that fails, a list of MAX_FILES or more.

WHAT `heavy=false` DOES. The gated jobs still RUN and conclude SUCCESS (their heavy steps are
skipped), because audit_gate.checks() requires a success conclusion from every gating job, and a
job skipped at job level would never merge. audit-gate, trusted-eval and independent-review are
untouched and run on every PR. This file runs from the PR's BASE (a PR cannot change the filter
that judges it), and .github/ is never on the allowlist, so a PR that edits it always runs heavy.
"""

from __future__ import annotations

import argparse
import fnmatch
import importlib.util
import json
import os
import subprocess
import sys
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
MAX_FILES = 3000

#: THE ALLOWLIST: prose under these folders. Nothing else is ever light.
SKIP_PREFIXES: tuple[str, ...] = (
    "docs/",
    "reports/",
    "logs/",
    "desks/mt5/docs/",
    "desks/mt5/logs/",
)
#: What counts as prose under SKIP_PREFIXES (audit_gate.LOW_EXTS plus .rst and .log).
PROSE_EXTS: tuple[str, ...] = (".md", ".rst", ".log", ".png", ".jpg", ".jpeg", ".svg", ".gif")
SKIP_FILES: frozenset[str] = frozenset(
    {
        "context/decision_journal.jsonl",
        "docs/desk_lessons.jsonl",
    }
)
#: Folders the live book reads (release-gates.yml replay-shadow's inputs live here): never light,
#: at any depth. Belt and braces: none of them is on SKIP_PREFIXES either.
LIVE_READ_PREFIXES: tuple[str, ...] = ("desks/mt5/data/", "desks/mt5/reports/", "data/")


def _load(name: str, rel: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    if spec is None or spec.loader is None:
        raise ImportError(rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def light_reason(path: str, governed: Callable[[str], bool], gate: Any) -> str | None:
    """None when `path` may skip the heavy suite; otherwise why it may not."""
    p = path.replace("\\", "/").lstrip("./")
    low = p.lower()
    if p.startswith(LIVE_READ_PREFIXES):
        return f"{p}: under a folder the live book reads"
    if not (p in SKIP_FILES or (p.startswith(SKIP_PREFIXES) and low.endswith(PROSE_EXTS))):
        return f"{p}: not prose under docs/, reports/ or logs/"
    base = p.rsplit("/", 1)[-1].lower()
    if any(fnmatch.fnmatchcase(base, spec) for spec in gate.CODE_SPECS if "/" not in spec):
        return f"{p}: a code or config file type, wherever it sits"
    if governed(p):
        return f"{p}: governed state"
    if any(fnmatch.fnmatchcase(low, s) for s in gate.SECRETS):
        return f"{p}: a secrets path"
    extra = gate.protected_patterns()
    if extra is None:
        return "ops/release/protected_paths.txt is unreadable"
    if gate.is_protected(p) or any(
        fnmatch.fnmatchcase(low, pat.lower()) for pat in (*gate.FORMERLY_PROTECTED, *extra)
    ):
        return f"{p}: protected or formerly protected"
    if gate.FORCED_LIVE.search(low):
        return f"{p}: a governing name"
    return None


def decide(paths: Iterable[str], governed: Callable[[str], bool], gate: Any) -> tuple[bool, str]:
    """(heavy, why). Empty is heavy: a PR whose files were not read is never light."""
    names = sorted({p for p in paths if p})
    if not names:
        return True, "no changed paths read"
    if len(names) >= MAX_FILES:
        return True, f"{len(names)} paths: at or past the file-list limit"
    for p in names:
        why = light_reason(p, governed, gate)
        if why is not None:
            return True, why
    return False, f"{len(names)} path(s), all prose under docs/, reports/ or logs/"


def _gh(*args: str) -> str:
    return subprocess.run(
        ["gh", "api", *args], capture_output=True, text=True, check=True, timeout=120
    ).stdout


def pr_paths(repo: str, pr: int, head: str) -> list[str]:
    """Every changed path of the PR, both sides of a rename, checked against the PR's own count
    on this very head. Raises on any mismatch."""
    api = f"repos/{repo}/pulls/{pr}"
    rows: list[dict[str, Any]] = []
    page = 1
    while True:
        batch = json.loads(_gh(f"{api}/files?per_page=100&page={page}") or "[]")
        if not batch:
            break
        rows.extend(batch)
        page += 1
        if len(rows) >= MAX_FILES:
            break
    meta = json.loads(_gh(api))
    if str((meta.get("head") or {}).get("sha")) != head:
        raise RuntimeError("the head moved while its files were read")
    if len(rows) != int(meta.get("changed_files") or -1):
        raise RuntimeError(
            f"the file list names {len(rows)} files, the PR changes {meta.get('changed_files')}"
        )
    out: list[str] = []
    for r in rows:
        out.extend(str(n) for n in (r.get("filename"), r.get("previous_filename")) if n)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    ap.add_argument("--pr", type=int, default=0)
    ap.add_argument("--head", default="")
    ap.add_argument("--paths", type=Path, help="a file of changed paths instead of the API")
    a = ap.parse_args(argv)
    try:
        gate = _load("_scope_gate", ".github/scripts/audit_gate.py")
        governed = _load("_scope_release", "libs/ops/release.py").is_governed_state
        if a.paths is not None:
            paths = a.paths.read_text(encoding="utf-8").splitlines()
        else:
            paths = pr_paths(a.repo, a.pr, a.head)
        heavy, why = decide(paths, governed, gate)
    except Exception as exc:  # any doubt is heavy
        heavy, why = True, f"could not decide ({type(exc).__name__}: {exc})"
    print(f"heavy={'true' if heavy else 'false'}")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary and not heavy:
        # #983 audit SF (L1.49): a green check on a light run must never read as a passed suite.
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(f"**LIGHT: the heavy steps of this job did not run.** {why}\n")
    print(f"ci_scope: {'HEAVY' if heavy else 'LIGHT'} -- {why}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
