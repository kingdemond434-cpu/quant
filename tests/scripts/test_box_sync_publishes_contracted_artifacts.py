"""A CONTRACTED ARTIFACT THAT NEVER LEAVES THE BOX IS MEASURED BY NOBODY OFF IT (2026-11-10).

`ops/organ_contract.py` names the artifact every scheduled organ must keep fresh. The hourly pass
reads those artifacts from origin. Measured 2026-11-10: seven of them (the E8 gold and executor
books, the trial allocation, the combiner coverage, the heavy admission scan, the allocator's
fractions and the daily-cycle stamp) were fresh on the box and absent from origin, because each
sat under a gitignore rule and on neither of `sync_shadow_to_git.ps1`'s publish lists. Every pass
scored them UNMEASURED and nothing failed.

This fence makes the gap a test failure. A contracted artifact must reach origin one of three
ways: it is tracked and not ignored (some other committer carries it), it is on `$relPaths` or
`$reportPaths`, or it is named in KNOWN_UNPUBLISHED below. That set is a ratchet (L1.50): it may
only shrink. A NEW organ whose artifact is not published fails here, and an entry that has since
been published must be deleted from the set, or that fails too.
"""
from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent
_SYNC = _ROOT / "desks" / "mt5" / "scripts" / "sync_shadow_to_git.ps1"

#: What the hourly pass named on 2026-11-10. These may never fall off the publish lists.
REQUIRED = frozenset({
    "desks/mt5/reports/E8_GOLD.json",
    "desks/mt5/reports/E8_EXEC.json",
    "desks/mt5/reports/TRIAL_ALLOCATION.json",
    "desks/mt5/reports/COMBINER_COVERAGE.json",
    "desks/mt5/reports/admission_heavy_pass.json",
    "desks/mt5/reports/pf_allocation.json",
    # the read-only mirror of the per-box stamp data/daily_cycle_state.json (which stays ignored)
    "desks/mt5/reports/DAILY_CYCLE_STATE.json",
    # tracked, yet stale on origin since 2026-09-16: tracking alone carries nothing off the box
    "desks/mt5/data/stall_watch.json",
})

#: Contracted artifacts that did not reach origin on 2026-11-10 and are not yet published. This is
#: debt, not permission: it may only shrink. Logs are excluded by rule (below), not listed here.
KNOWN_UNPUBLISHED = frozenset({
    "desks/mt5/reports/E8_BOOK.json",
    "desks/mt5/reports/E8_SPREADS.json",
    "desks/mt5/reports/DATA_AXES.json",
    "desks/mt5/reports/AXIS_INGEST.json",
    "desks/mt5/reports/CEO_DOCKET.json",
    "desks/mt5/reports/NEVER_STALE.json",
    "desks/mt5/reports/TAPE_RECORDER.json",
    "desks/mt5/reports/FRONTIER_INTELLIGENCE.json",
    "desks/mt5/data/terminal_boot_ok.json",
    "desks/mt5/reports/RESEARCH_REPORT_CLOCK.json",
    "desks/mt5/reports/DIST_SHIFT.json",
    "desks/mt5/reports/CERTIFICATE_HYGIENE.json",
    "desks/mt5/reports/RELEASE_AUTHORITY_AUDIT.json",
    "desks/mt5/reports/MOAT_CAPTURE.json",
    "desks/mt5/reports/PIT_AUDIT.json",
    "desks/mt5/reports/FORWARD_CALIBRATION.json",
    "desks/mt5/reports/ORTHOGONALITY.json",
    "desks/mt5/reports/UNKNOWN_UNKNOWNS.json",
    "desks/mt5/reports/BOOK_FORENSICS.json",
    "desks/mt5/reports/WORLD_MODEL.json",
    "desks/mt5/reports/REPRESENTATION_DISCOVERY.json",
    "desks/mt5/reports/RESEARCH_TREE.json",
    "desks/mt5/reports/SCIENTIST_TOURNAMENT.json",
    "desks/mt5/reports/EVIDENCE_VAULT.json",
    "desks/mt5/reports/CAUSAL_DISCOVERY.json",
    "desks/mt5/reports/CREDIT_ASSIGNMENT.json",
    "desks/mt5/reports/ADVERSARY_EVOLUTION.json",
    "desks/mt5/reports/MODIFIER_COUNTERFACTUALS.json",
    "desks/mt5/reports/MISSED_GROWTH.json",
    "desks/mt5/reports/FORMAL_INVARIANTS.json",
    "desks/mt5/reports/INDEPENDENT_VERIFIER.json",
    "desks/mt5/reports/META_RND.json",
    "desks/mt5/reports/QUANTBENCH.json",
    "desks/mt5/reports/CAPACITY_FRONTIER.json",
    "desks/mt5/reports/CAPACITY.json",
    "desks/mt5/reports/EXECUTION_SCIENCE.json",
    "desks/mt5/reports/SUBHOUR_COUNTERFACTUALS.json",
    "desks/mt5/reports/INFORMATION_VALUE.json",
    "desks/mt5/reports/MARKET_ECOLOGY.json",
    "desks/mt5/reports/BUDGET_MARKET.json",
    "desks/mt5/reports/META_CONTROLLER.json",
    "desks/mt5/reports/FRONTIER_MAP.json",
    "desks/mt5/reports/NEGATIVE_KNOWLEDGE.json",
    "desks/mt5/reports/JOINT_EVOLUTION.json",
    "desks/mt5/reports/MARKET_POSTERIORS.json",
    "desks/mt5/reports/CHART_ALLOCATION.json",
})


def _listed() -> set[str]:
    src = _SYNC.read_text("utf-8", errors="ignore")
    out: set[str] = set()
    for name in ("$relPaths", "$reportPaths"):
        start = src.index(name + " = @(")
        out |= set(re.findall(r'"(desks/[^"]+)"', src[start:src.index("\n)", start)]))
    return out


def _contracted() -> set[str]:
    path = _ROOT / "ops" / "organ_contract.py"
    spec = importlib.util.spec_from_file_location("organ_contract_publish_t", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["organ_contract_publish_t"] = mod
    spec.loader.exec_module(mod)
    contracts: dict[str, Any] = mod.CONTRACTS
    out = set()
    for row in contracts.values():
        art = row[0] if isinstance(row, tuple) else row
        if isinstance(art, str) and art.startswith("desks/") and not art.endswith(".log"):
            out.add(art)
    return out


def _reaches_origin_otherwise(rel: str) -> bool:
    tracked = subprocess.run(["git", "ls-files", "--error-unmatch", "--", rel], cwd=_ROOT,
                             capture_output=True, check=False).returncode == 0
    ignored = subprocess.run(["git", "check-ignore", "-q", "--", rel], cwd=_ROOT,
                             capture_output=True, check=False).returncode == 0
    return tracked and not ignored


def test_the_contract_and_the_lists_parse() -> None:
    """Without this every assertion below passes vacuously on a parse miss (L1.63)."""
    assert len(_contracted()) >= 40 and len(_listed()) >= 40


@pytest.mark.parametrize("rel", sorted(REQUIRED))
def test_the_hourly_pass_artifacts_are_published(rel: str) -> None:
    assert rel in _listed(), f"{rel} fell off sync_shadow_to_git.ps1's publish lists"
    assert subprocess.run(["git", "check-ignore", "-q", "--", rel], cwd=_ROOT,
                          check=False).returncode != 0, (
        f"{rel} is listed but .gitignore excludes it, so `git add` stages nothing and exits 0")


def test_the_daily_stamp_itself_stays_box_local() -> None:
    rel = "desks/mt5/data/daily_cycle_state.json"
    assert rel not in _listed()
    assert subprocess.run(["git", "check-ignore", "-q", "--", rel], cwd=_ROOT,
                          check=False).returncode == 0


def test_every_contracted_artifact_reaches_origin() -> None:
    listed = _listed()
    missing = sorted(a for a in _contracted() - KNOWN_UNPUBLISHED
                     if a not in listed and not _reaches_origin_otherwise(a))
    assert not missing, (
        "contracted artifacts that never reach origin, so every reader off the box scores them "
        f"UNMEASURED: {missing}. Add each to $reportPaths in sync_shadow_to_git.ps1 with a `!` "
        "allowlist line at the end of .gitignore. Do not add it to KNOWN_UNPUBLISHED: that set "
        "only shrinks.")


def test_the_debt_only_shrinks() -> None:
    listed = _listed()
    contracted = _contracted()
    paid = sorted(a for a in KNOWN_UNPUBLISHED
                  if a in listed or _reaches_origin_otherwise(a) or a not in contracted)
    assert not paid, f"published or no longer contracted, so remove from KNOWN_UNPUBLISHED: {paid}"
