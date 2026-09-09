"""The attribution chain's four ledgers must cross the wire, or nothing off the box can verify it.

MEASURED 2026-09-08: `git log -- desks/mt5/data/{decision_ledger,order_intents,live_ledger}.jsonl
desks/mt5/reports/attribution_chain.json` was EMPTY -- none of the four had ever been committed.
The counterfactual organs (counterfactual_replay, action_counterfactuals, missed_growth,
execution_intelligence) read exactly these files and have reported n=0 on every arm since they
were written, and reports/COUNTERFACTUAL_WORLD.json says why in its own words: "no decision or
intent ledger under .../desks/mt5/data". Nothing in those organs is wrong; they were never given
an input.

Publishing a path takes three declarations that live in three files, and every one of them has
failed silently before: `$relPaths` in the sync script (a path not listed is not staged),
`.gitignore` (an ignored path is `git add`-ed as a no-op with exit 0 -- see
test_dashboard_inputs_are_committable), and `release.NON_CODE` plus its box-side mirror (a
published path the seal does not name refuses new risk within fifteen minutes -- see
test_release_seal). This pins all three, on the OUTCOME where one exists: `git check-ignore` in a
throwaway repo, not the text of any rule.
"""
from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from libs.ops import release

ROOT = Path(__file__).resolve().parents[2]
SYNC = ROOT / "desks" / "mt5" / "scripts" / "sync_shadow_to_git.ps1"

#: The chain: what the desk looked at, what it sent, what the venue gave, and the walk back.
CHAIN_PATHS = (
    "desks/mt5/data/decision_ledger.jsonl",
    "desks/mt5/data/order_intents.jsonl",
    "desks/mt5/data/live_ledger.jsonl",
    "desks/mt5/reports/attribution_chain.json",
)


def _published() -> list[str]:
    """`$relPaths`, parsed from the script -- the same parser test_release_seal uses."""
    ps = SYNC.read_text("utf-8")
    assert "$relPaths = @(" in ps, "the sync script no longer declares $relPaths -- retarget this"
    block = ps.split("$relPaths = @(", 1)[1].split("\n)", 1)[0]
    return [m for m in re.findall(r'"([^"]+)"', block) if "/" in m]


@pytest.mark.parametrize("rel", CHAIN_PATHS)
def test_the_sync_script_lists_the_ledger(rel: str) -> None:
    assert rel in _published(), (
        f"{rel} is not in sync_shadow_to_git.ps1's $relPaths, so the box never stages it and "
        "the chain stays on one Windows machine")


@pytest.fixture(scope="module")
def sandbox() -> Path:
    """A throwaway repo carrying only this .gitignore, asked on a CLEAN tree on purpose: git
    reports a TRACKED file as not ignored whatever the rules say, and on the box these four are
    untracked -- that is the condition to test."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        (root / ".gitignore").write_text((ROOT / ".gitignore").read_text("utf-8"), "utf-8")
        for rel in CHAIN_PATHS:
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("{}\n", "utf-8")
        yield root


@pytest.mark.parametrize("rel", CHAIN_PATHS)
def test_the_ledger_can_be_committed(sandbox: Path, rel: str) -> None:
    ignored = subprocess.run(["git", "check-ignore", "-q", "--", rel],
                             cwd=sandbox, capture_output=True).returncode == 0
    if ignored:
        why = subprocess.run(["git", "check-ignore", "-v", "--", rel],
                             cwd=sandbox, capture_output=True, text=True).stdout.strip()
        pytest.fail(
            f"{rel} is IGNORED: `git add` on it exits 0 and stages nothing, so the sync reports "
            f"success and publishes nothing. Git applies the LAST matching rule, so the allowlist "
            f"must sit BELOW every exclusion that matches it.\n  winning rule: {why}")


def test_the_allowlist_names_each_ledger_after_the_reports_exclusion() -> None:
    """attribution_chain.json lives under reports/, which `**/reports/*` excludes; its negation
    must come after that line or it is decorative. Pinned by text as well as by outcome so the
    failure message names the line to move."""
    lines = (ROOT / ".gitignore").read_text("utf-8").splitlines()
    blocked = lines.index("**/reports/*")
    for rel in CHAIN_PATHS:
        allow = f"!{rel}"
        assert allow in lines, f"{allow} is not in .gitignore"
        assert lines.index(allow) > blocked, f"{allow} sits before **/reports/*; last match wins"


def _box_identity() -> object:
    spec = importlib.util.spec_from_file_location(
        "release_identity_for_publication",
        ROOT / "desks" / "mt5" / "mt5desk" / "release_identity.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("rel", CHAIN_PATHS)
def test_the_seal_and_its_box_side_mirror_both_declare_the_ledger_non_code(rel: str) -> None:
    """A published path the seal does not name is 'unreleased code' to `accepts()`, and the
    gateway then refuses new risk from the first sync after any seal -- silently."""
    assert rel in release.NON_CODE, f"{rel} is published but release.NON_CODE does not name it"
    ri = _box_identity()
    assert rel in ri.NON_CODE, (  # type: ignore[attr-defined]
        f"{rel} is in release.NON_CODE but not in the box-side mirror release_identity.NON_CODE")


def test_a_sync_that_publishes_the_chain_leaves_a_seal_valid(tmp_path: Path) -> None:
    """End to end on a throwaway repository: seal, commit the seal alone, then commit all four
    ledgers the way the box does, and the running SHA must still be the sealed code."""
    if not __import__("shutil").which("git"):
        pytest.skip("git required")
    r = tmp_path / "repo"
    r.mkdir()

    def git(*a: str) -> str:
        return subprocess.run(["git", *a], cwd=str(r), capture_output=True, text=True,
                              check=True).stdout.strip()

    git("init", "-q", "-b", "main")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "t")
    git("config", "commit.gpgsign", "false")
    for rel in (*release.MONEY_PATH, *release.CONFIG_FILES, release.SURVIVORS):
        p = r / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"# {rel}\n", "utf-8")
    (r / release.IMMUTABLE_MANIFEST).write_text(
        '{"signed_utc": "x", "signed_by": "t", "files": {}}', "utf-8")
    (r / release.PYPROJECT).write_text('[project]\nname = "x"\ndependencies = []\n', "utf-8")
    git("add", "-A")
    git("commit", "-qm", "code")
    doc = release.seal(root=r)
    git("add", "--", release.RELEASE_REL)
    git("commit", "-qm", "seal release")
    head = ""
    for rel in CHAIN_PATHS:
        p = r / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('{"chain": true}\n', "utf-8")
        git("add", "--", rel)
        git("commit", "-qm", "mt5 shadow state sync")
        head = git("rev-parse", "HEAD")
    ok, why, code = release.accepts(head, doc, root=r)
    assert ok and code == [], f"publishing the chain refused the seal: {why}"
