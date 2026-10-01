"""EVERY TIER S EVIDENCE ARTIFACT REACHES GIT FROM THE BOX, OR THIS FAILS (2026-09-30).

A Tier S layer is DONE only on `data/tier_s/box_evidence.json` as committed from the trading box,
and a promotion is withheld on six box-local files `promotion_authority` reads (live_door, the
door verdicts, PROMOTION_FREEZE, RELEASE_STOP, ONLINE_FDR_ROWS, REPLICATION). Before this fence
only the attestation and live_door were on the box's sync list, so no reader off the box could
say why a promotion was withheld.

A file reaches git from the box only if all three hold:
  * it is in `sync_shadow_to_git.ps1`'s `$relPaths` (the sync stages nothing else);
  * it is declared NON_CODE in BOTH seal lists (`libs/ops/release.py` and the box-side mirror
    `desks/mt5/mt5desk/release_identity.py`), or the seal tests fail on the box's own state push;
  * it is not gitignored (a plain `git add` on an ignored path stages nothing and exits 0).

The list is `libs.tiers.box_evidence.SYNCED`, and it is itself checked against the paths the
promotion door reads, so a seventh door input added later cannot slip past by being unlisted.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import pytest

from libs.ops import release
from libs.tiers import box_evidence, promotion_authority, regression_stop

ROOT = Path(__file__).resolve().parents[2]
SYNC = ROOT / "desks" / "mt5" / "scripts" / "sync_shadow_to_git.ps1"


def _rel(p: Path) -> str:
    return str(p.resolve().relative_to(ROOT)).replace("\\", "/") if p.is_absolute() \
        else str(p).replace("\\", "/")


def _box_identity() -> Any:
    spec = importlib.util.spec_from_file_location(
        "release_identity_tier_s_evidence", ROOT / "desks" / "mt5" / "mt5desk" /
        "release_identity.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod        # dataclasses resolve string annotations via sys.modules
    spec.loader.exec_module(mod)
    return mod


def _rel_paths() -> list[str]:
    ps = SYNC.read_text("utf-8")
    block = ps.split("$relPaths = @(", 1)[1].split("\n)", 1)[0]
    return [ln.strip().strip(",").strip('"') for ln in block.splitlines()
            if ln.strip().startswith('"')]


def test_the_list_covers_every_input_the_promotion_door_reads() -> None:
    door_inputs = {_rel(p) for p in (
        promotion_authority.LIVE_DOOR, promotion_authority.DOOR_VERDICTS,
        promotion_authority.FREEZE, promotion_authority.REPLICATION,
        promotion_authority.FDR_ROWS, promotion_authority.RELEASE_STOP_REL,
        regression_stop.STOP_REL, box_evidence.OUT)}
    missing = sorted(door_inputs - set(box_evidence.SYNCED))
    assert not missing, f"box_evidence.SYNCED omits Tier S evidence the door reads: {missing}"


def test_the_sync_list_parses() -> None:
    assert len(_rel_paths()) >= 20, "the $relPaths block moved; this fence would pass vacuously"


@pytest.mark.parametrize("rel", box_evidence.SYNCED)
def test_on_the_box_sync_list(rel: str) -> None:
    assert rel in _rel_paths(), f"{rel} is not in sync_shadow_to_git.ps1's $relPaths"


@pytest.mark.parametrize("rel", box_evidence.SYNCED)
def test_declared_non_code_in_both_seal_lists(rel: str) -> None:
    assert rel in release.NON_CODE, f"{rel} missing from libs/ops/release.NON_CODE"
    assert rel in _box_identity().NON_CODE, (
        f"{rel} missing from desks/mt5/mt5desk/release_identity.NON_CODE")


def test_none_is_gitignored() -> None:
    """Asked in a clean sandbox carrying this .gitignore, with each file present, so an
    excluded PARENT DIRECTORY (git cannot re-include a file under one) is caught too."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        (root / ".gitignore").write_text((ROOT / ".gitignore").read_text("utf-8"), "utf-8")
        ignored = []
        for rel in box_evidence.SYNCED:
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("{}\n", "utf-8")
            if subprocess.run(["git", "check-ignore", "-q", "--", rel], cwd=root,
                              check=False).returncode == 0:
                ignored.append(rel)
    assert not ignored, f"gitignored, so the box's sync would stage nothing: {ignored}"


def test_the_attestation_digests_every_door_input() -> None:
    """The digest is the second road off the box: it must name every synced door input."""
    digested = set(box_evidence.PUBLISHED.values())
    missing = [r for r in box_evidence.SYNCED if r != _rel(box_evidence.OUT)
               and r not in digested]
    assert not missing, f"box_evidence.PUBLISHED does not digest {missing}"
