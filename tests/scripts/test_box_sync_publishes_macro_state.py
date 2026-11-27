"""macro_state.json IS PUBLISHED BY THE BOX, AS STATE, AND STILL JUDGED BY THE LOGIN FENCE.

MEASURED 2026-10-21 (reports/macro/MACRO_STATE_DIAGNOSIS_2026-10-21.md): the branch copy of
`desks/mt5/data/macro_state.json` stopped at 2026-09-12, an ad-hoc box commit, while the box's
macro_desk loop kept rewriting it hourly -- because no organ listed it. Its sibling
`cross_asset_anchors.pkl`, written by the same loop, was added to $reportPaths on 2026-09-30 and
flowed; the JSON did not. These pin every link of the wire: listed, not ignored, state to the
seal, tracked (so the live-identifier fence reads it), and its box-local publisher cache and
hard-stop file (data/macro_sources/) never published: raw publisher series stay on the box.
"""
from __future__ import annotations

import importlib.util
import subprocess
import tempfile
from pathlib import Path

from libs.ops import release, state_publication

ROOT = Path(__file__).resolve().parents[2]
REL = "desks/mt5/data/macro_state.json"
SIBLING = "desks/mt5/data/cross_asset_anchors.pkl"
CACHE = "desks/mt5/data/macro_sources/bls.json"


def _report_block() -> str:
    src = (ROOT / state_publication.SYNC_REL).read_text("utf-8", errors="ignore")
    start = src.index("$reportPaths = @(")
    return src[start:src.index("\n)", start)]


def test_the_publisher_lists_macro_state_next_to_its_sibling() -> None:
    published = state_publication.published_paths(ROOT)
    assert REL in published, "$reportPaths does not carry macro_state.json; the branch freezes"
    assert SIBLING in published
    block = _report_block()
    assert block.index(f'"{SIBLING}"') < block.index(f'"{REL}"'), (
        "macro_state.json belongs beside the anchors pickle its loop writes in the same pass")


def test_macro_state_is_state_to_the_seal_and_not_code() -> None:
    assert release.is_state_path(REL), (
        "a published path the seal reads as CODE refuses new risk on the next sync")


def test_macro_state_survives_gitignore_and_its_cache_does_not() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        (root / ".gitignore").write_text((ROOT / ".gitignore").read_text("utf-8"), "utf-8")
        for rel in (REL, CACHE):
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("{}\n", "utf-8")
        state = subprocess.run(["git", "check-ignore", "-q", "--", REL], cwd=root, check=False)
        cache = subprocess.run(["git", "check-ignore", "-q", "--", CACHE], cwd=root,
                               check=False)
    assert state.returncode != 0, "macro_state.json is ignored: `git add` would stage nothing"
    assert cache.returncode == 0, "raw publisher series and the halt file must stay off git"


def test_the_login_fence_still_judges_the_published_file() -> None:
    """The live-identifier fence scans `git ls-files`: published = tracked = judged, no pass."""
    tracked = subprocess.run(["git", "ls-files", "--", REL], cwd=ROOT, capture_output=True,
                             text=True, check=False).stdout.split()
    assert tracked == [REL], "macro_state.json is untracked, so no fence reads what the box ships"
    fence_path = ROOT / "tests" / "ops" / "test_live_infrastructure_is_not_published.py"
    spec = importlib.util.spec_from_file_location("_live_infra_fence", fence_path)
    assert spec is not None and spec.loader is not None
    fence = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fence)
    assert REL not in fence.ALLOWED, "macro_state.json must never be exempt from the login fence"
    assert REL in fence._tracked()
    text = (ROOT / REL).read_text("utf-8", errors="ignore")
    for needle in fence.LIVE:
        assert not fence._contains_identifier(text, needle)
