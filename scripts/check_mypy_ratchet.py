"""MYPY RATCHET -- gap #52: `scripts/` is outside the strictest gate in the repo (263 of 268 files).

The register's plan of record is explicit and correct: incremental tranches, risk-path files LAST,
never a bulk fix -- *"editing the live executor to satisfy a type checker is a known way to inject
bugs into working code."* But an untracked backlog has no direction: it can grow silently, and it
did (the pyproject comment records 408 errors across 87 files, measured 2026-07-25).

This makes the backlog a RATCHET (constitution L1.0): per-file error counts are committed to
data/mypy_ratchet.json, and the check FAILS when any file's count RISES or a new file appears with
errors. Counts may only fall. That converts "we should type these eventually" into a number that
cannot get worse, and feeds `scripts_mypy_clean` into the ratchet fence.

WHAT IT DELIBERATELY DOES NOT DO: it does not add files to the `[tool.mypy] files` list, and it
does not touch risk-path code. Promotion into the real gate stays a deliberate, reviewed act per
file. scripts/run_deadman_switch.py is EXCLUDED here as well as from the gate -- the pyproject
comment explains why (strict mode forces `from typing import Any`, which trips the Tier-3 rail's
own import-allowlist guard; the rail's protection is isolation, not type coverage).

    python scripts/check_mypy_ratchet.py [--rebaseline] [--json] [--report-only]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops.fence_exit import fence_exit  # noqa: E402

_BASELINE = _ROOT / "data/mypy_ratchet.json"

# NEVER type-checked here, and the exclusion is load-bearing, not convenience.
_EXCLUDED = {"scripts/run_deadman_switch.py"}

_ERR = re.compile(r"^(?P<file>[^:]+):\d+:(?:\d+:)?\s*error:")


def _gated_files() -> set[str]:
    cfg = tomllib.loads((_ROOT / "pyproject.toml").read_text("utf-8"))
    files = cfg.get("tool", {}).get("mypy", {}).get("files", [])
    return {str(f) for f in files}


def _targets() -> list[str]:
    gated = _gated_files()
    return sorted(str(p.relative_to(_ROOT)) for p in (_ROOT / "scripts").glob("*.py")
                  if str(p.relative_to(_ROOT)) not in gated
                  and str(p.relative_to(_ROOT)) not in _EXCLUDED)


def measure(targets: list[str], *, chunk: int = 40) -> tuple[dict[str, int], list[str]]:
    """Per-file error counts. Chunked because module-name collisions and memory make one giant
    invocation unreliable on a 4GB box; a chunk that crashes is recorded as UNCHECKABLE rather
    than silently scoring zero (a crash that reads as 'clean' is the fail-open shape this repo
    has been bitten by before)."""
    counts: dict[str, int] = dict.fromkeys(targets, 0)
    uncheckable: list[str] = []
    for i in range(0, len(targets), chunk):
        batch = targets[i:i + chunk]
        try:
            proc = subprocess.run(
                # --explicit-package-bases is REQUIRED, not optional: pyproject sets
                # mypy_path="." and scripts/ has no __init__.py, so without it mypy aborts the
                # whole batch with "Source file found twice under different module names"
                # (scripts.doctrine vs doctrine) at returncode 2 -- which the first run of this
                # script recorded as 263 UNCHECKABLE files. A tool that reports "cannot check"
                # when the real answer is "one flag missing" produces a false clean bill.
                [sys.executable, "-m", "mypy", "--strict", "--no-error-summary",
                 "--ignore-missing-imports", "--no-incremental",
                 "--explicit-package-bases", *batch],
                cwd=_ROOT, capture_output=True, text=True, timeout=900, check=False)
        except (subprocess.TimeoutExpired, OSError):
            uncheckable.extend(batch)
            continue
        if proc.returncode not in (0, 1):
            uncheckable.extend(batch)
            continue
        for line in (proc.stdout or "").splitlines():
            m = _ERR.match(line.strip())
            if not m:
                continue
            f = m.group("file")
            if f in counts:
                counts[f] += 1
    for f in uncheckable:
        counts.pop(f, None)
    return counts, uncheckable


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebaseline", action="store_true",
                    help="record the CURRENT counts as the baseline (only in a commit that "
                         "reduces them; the check itself never rewrites a worse baseline)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--report-only", action="store_true")
    args = ap.parse_args()

    targets = _targets()
    counts, uncheckable = measure(targets)
    total = sum(counts.values())
    clean = [f for f, n in counts.items() if n == 0]

    try:
        base = json.loads(_BASELINE.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        base = {}
    base_per: dict[str, int] = {str(k): int(v) for k, v in (base.get("per_file") or {}).items()}

    regressions = [f"{f}: {n} (was {base_per[f]})" for f, n in sorted(counts.items())
                   if f in base_per and n > base_per[f]]
    new_dirty = [f"{f}: {n}" for f, n in sorted(counts.items())
                 if f not in base_per and n > 0]
    improved = [f"{f}: {n} (was {base_per[f]})" for f, n in sorted(counts.items())
                if f in base_per and n < base_per[f]]

    report: dict[str, Any] = {
        "measured": __import__("time").strftime("%Y-%m-%dT%H:%M:%SZ", __import__("time").gmtime()),
        "n_files_checked": len(counts), "total_errors": total,
        "n_clean": len(clean), "clean_fraction": round(len(clean) / max(len(counts), 1), 4),
        "baseline_total": base.get("total_errors"),
        "regressions": regressions, "new_dirty_files": new_dirty, "improved": improved,
        "uncheckable": uncheckable,
        "excluded_forever": sorted(_EXCLUDED),
        "note": "counts may only FALL; promotion into [tool.mypy] files stays a deliberate "
                "per-file act, and risk-path files go last",
    }

    if args.rebaseline:
        # Only ever writes counts that are <= the recorded ones, per file. A rebaseline cannot
        # launder a regression -- same asymmetry as the ratchet fence.
        merged = dict(base_per)
        for f, n in counts.items():
            merged[f] = min(n, base_per[f]) if f in base_per else n
        _BASELINE.parent.mkdir(parents=True, exist_ok=True)
        _BASELINE.write_text(json.dumps(
            {"generated": report["measured"], "total_errors": sum(merged.values()),
             "per_file": dict(sorted(merged.items())),
             "clean_fraction": round(sum(1 for v in merged.values() if v == 0)
                                     / max(len(merged), 1), 4)},
            indent=2), "utf-8")
        report["rebaselined"] = True

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"mypy ratchet | {len(counts)} files | {total} errors | "
              f"{len(clean)} clean ({report['clean_fraction']:.1%}) | "
              f"baseline total {report['baseline_total']}")
        for label, rows in (("REGRESSION", regressions), ("NEW DIRTY", new_dirty),
                            ("improved", improved), ("UNCHECKABLE", uncheckable)):
            for row in rows[:12]:
                print(f"  {label:12} {row}")
    bad = bool(regressions or new_dirty)

    # THE DENOMINATOR IS THE FILES THAT WERE ACTUALLY CHECKED (L1.57, R0417), and here that is
    # strictly smaller than the target list: `measure()` pops every UNCHECKABLE file out of
    # `counts`, so a file mypy could not read is not merely unjudged, it has left the ratchet.
    # Uninstall mypy (or let every batch time out) and every target becomes uncheckable ->
    # `counts` is empty -> `total_errors` 0, `n_files_checked` 0, `regressions` [] ,
    # `new_dirty` [] -> exit 0. A type-checker that never ran publishes a perfect score, and the
    # ratchet it feeds records the improvement.
    #
    # This is why the count must be `len(counts)` and not `len(targets)`: `targets` is what we
    # INTENDED to check and never falls when checking fails, which is the constant-denominator
    # half of the same defect. The attrition is already reported (`uncheckable` is in the report
    # and printed), per L1.60 -- what was missing is that the verdict never consulted it.
    # --report-only returns before the verdict, per the house pattern (check_conversion,
    # check_denominators): it is the explicit "write the artifact, do not gate" switch, and
    # daily_research_cycle.py:121 runs this fence that way. A denominator refuses a PASS; where
    # there is no verdict there is nothing to refuse.
    if args.report_only:
        return 0
    return fence_exit("REGRESSION" if bad else "OK", {"OK"},
                      scanned=len(counts), of="scripts/*.py files mypy actually checked",
                      fence="check_mypy_ratchet.py")


if __name__ == "__main__":
    raise SystemExit(main())
