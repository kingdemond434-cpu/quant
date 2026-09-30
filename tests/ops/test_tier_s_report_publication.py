"""THE TIER S MEASUREMENT REPORTS REACH GIT FROM THE BOX (2026-09-30).

The independent audit found no committed artifact for the null lab, the lag lane or the occupancy
map: `**/reports/*` is gitignored, so each existed only on the host that wrote it. Pinned here:
every one is in the box sync's `$relPaths`, declared NON_CODE in BOTH seal lists (or the gateway
would read the box's own state commit as unreleased code), not ignored by git (the sync stages
with a plain `git add`, which is silently a no-op on an ignored path), and written by a scheduled
leg.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]

REPORTS = {
    "desks/mt5/reports/NULL_LAB.json": "desks/mt5/research/null_lab.py",
    "desks/mt5/reports/KNOWN_BY_DATE.json": "scripts/check_known_by_date.py",
    "desks/mt5/reports/PIT_LAG_CENSUS.json": "scripts/check_known_by_date.py",
    "desks/mt5/reports/UNKNOWN_SHARE_CENSUS.json": "desks/mt5/research/daily_cycle.py",
    "desks/mt5/reports/OCCUPANCY_MAP.json": "desks/mt5/research/occupancy_map.py",
    "desks/mt5/reports/CULTURE_ORTHOGONALITY.json": "desks/mt5/research/culture_orthogonality.py",
    "desks/mt5/reports/RESEARCH_LIVE_IDENTITY.json":
        "desks/mt5/research/research_live_identity.py",
}


def _box_identity() -> Any:
    spec = importlib.util.spec_from_file_location(
        "release_identity_publication", ROOT / "desks" / "mt5" / "mt5desk" / "release_identity.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod        # dataclasses resolve string annotations via sys.modules
    spec.loader.exec_module(mod)
    return mod


def _rel_paths() -> list[str]:
    ps = (ROOT / "desks" / "mt5" / "scripts" / "sync_shadow_to_git.ps1").read_text("utf-8")
    block = ps.split("$relPaths = @(", 1)[1].split("\n)", 1)[0]
    return [ln.strip().strip(",").strip('"') for ln in block.splitlines()
            if ln.strip().startswith('"')]


@pytest.mark.parametrize("rel", sorted(REPORTS))
def test_report_is_published_declared_and_not_ignored(rel: str) -> None:
    from libs.ops import release
    release_identity = _box_identity()
    assert rel in _rel_paths(), f"{rel} is not in sync_shadow_to_git.ps1's $relPaths"
    assert rel in release.NON_CODE, f"{rel} missing from libs/ops/release.NON_CODE"
    assert rel in release_identity.NON_CODE, f"{rel} missing from the box-side NON_CODE mirror"
    ignored = subprocess.run(["git", "check-ignore", "-q", rel], cwd=ROOT, check=False)
    assert ignored.returncode == 1, f"{rel} is gitignored: the sync's git add would drop it"


@pytest.mark.parametrize(("rel", "writer"), sorted(REPORTS.items()))
def test_report_names_its_writer(rel: str, writer: str) -> None:
    src = (ROOT / writer).read_text("utf-8")
    assert Path(rel).name in src, f"{writer} does not write {Path(rel).name}"


def test_the_lag_lane_rides_the_hourly_pit_canaries_leg() -> None:
    cycle = (ROOT / "desks" / "mt5" / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_producer("pit_canaries", "scripts/check_pit_canaries.py")' in cycle
    canaries = (ROOT / "scripts" / "check_pit_canaries.py").read_text("utf-8")
    assert "kbd.publish()" in canaries
