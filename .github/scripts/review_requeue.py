"""Re-run every queued independent review, on a clock of its own (Combiner blocker, 2026-11-10).

A review that ends UNAVAILABLE (no free model answered in time, exit 75) is QUEUED: never a pass,
never a quarantine. Until now only two things re-ran it, and both had to look at the PR first:
the audit-gate run, which stops at "no AUDIT verdict on this PR yet" before it ever gets to the
re-run, and the box sweep, which stops when the box does. #604 #618 #667 #713 sat queued from
11-06 04:5xZ to 11-10 with no attempt after their second.

This job only asks GitHub to run the same review job again, through audit_gate.queued_review()
and audit_gate.requeue(): the same rules as the gate (the run must be a genuine job of this
repo's workflow on the PR's current head, its own REVIEW_UNAVAILABLE annotation must say it
queued, the last attempt must be RETRY_AFTER_S old, at most MAX_ATTEMPTS). It reads no verdict,
writes no status, merges nothing, and a re-run is only another chance for the votes to come in.

    GH_TOKEN=... python -I .github/scripts/review_requeue.py --repo o/r
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

_spec = importlib.util.spec_from_file_location(
    "audit_gate", Path(__file__).resolve().parent / "audit_gate.py"
)
assert _spec is not None and _spec.loader is not None
gate = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("audit_gate", gate)
_spec.loader.exec_module(gate)


def sweep(
    repo: str,
    genuine_for: Callable[[str, int, str], Callable[[Mapping[str, Any]], bool]] | None = None,
) -> list[str]:
    """One line per open same-repo PR into LIVE whose newest review on its head is queued."""
    gh = gate._gh
    genuine_for = genuine_for or gate.provenance
    out: list[str] = []
    pulls = gate._flat(gh(f"repos/{repo}/pulls?state=open&base={gate.LIVE}&per_page=100",
                          "--paginate", "--slurp"))  # fmt: skip
    for p in pulls:
        if ((p.get("head") or {}).get("repo") or {}).get("full_name") != repo:
            continue  # a fork's PR never gets this job (release-gates runs same-repo PRs only)
        n, head = int(p["number"]), str(p["head"]["sha"])
        try:
            pages = gh(f"repos/{repo}/commits/{head}/check-runs?per_page=100",
                       "--paginate", "--slurp")  # fmt: skip
            runs = [r for page in gate._flat_pages(pages) for r in (page.get("check_runs") or [])]
            review = gate.queued_review(repo, runs, genuine_for(repo, n, head))
            if review is not None:
                out.append(f"#{n} @ {head[:9]}: {gate.requeue(repo, review)}")
        except RuntimeError as exc:  # one PR's failed read never stops the others
            out.append(f"#{n} @ {head[:9]}: not looked at ({exc})")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    a = ap.parse_args(argv)
    lines = sweep(a.repo)
    for line in lines or ["no queued review"]:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
