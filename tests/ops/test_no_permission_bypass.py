"""NO UNATTENDED AGENT RUNS WITH THE BLANKET PERMISSION BYPASS.

The VPS organs used to call `claude -p ... <bypass flag>`, which hands every tool (writes, pushes,
crontab, secrets) to a seat whose brief is read-only or path-scoped. PR #175 moved the model
probes off it; this change moves the deep sweep, the capability hunt, the calibration probe and
the brain auth pings. This fence fails if the flag appears in any tracked .py/.sh/.ps1 file that
is not listed below, so the next organ cannot quietly bring it back.

ALLOWLIST holds lines that genuinely cannot change, each with its reason. It is EMPTY.

PENDING_SCOPING is NOT an allowlist. It names the shell agent lanes that still carry the flag
because each needs its own prompt read and its own scoped list (their prompts run to ~9,000
lines between them). It only shrinks: a NEW occurrence anywhere fails, and an entry that no
longer matches a line (because the lane was scoped) fails until it is deleted here.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
#: Built by concatenation so this file never contains the flag it fences.
FLAG = "--dangerously" + "-skip-permissions"

#: (path, stripped line) -> reason. Lines that genuinely cannot change. Starts, and stays, empty.
ALLOWLIST: dict[tuple[str, str], str] = {}

#: path -> number of occurrences still to scope. Shrinks only; see the module docstring.
PENDING_SCOPING: dict[str, int] = {
    "ops/run_blindrediscovery_dig.sh": 1,
    "ops/run_brain_hunter.sh": 1,
    "ops/run_cro_ai.sh": 1,
    "ops/run_dataaxis_dig.sh": 1,
    "ops/run_frontier_miner.sh": 1,
    "ops/run_gap_wirer.sh": 1,
    "ops/run_litminer_dig.sh": 1,
    "ops/run_prospector_dig.sh": 1,
    "ops/run_recommendation_worker.sh": 1,
    "ops/run_video_hunter.sh": 1,
}


def _scan(root: Path, files: list[str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for rel in filter(None, files):
        p = root / rel
        if not p.is_file():                 # a sparse checkout leaves tracked paths absent
            continue
        try:
            text = p.read_text("utf-8", errors="replace")
        except OSError:
            continue
        if FLAG in text:
            out[rel] = [ln.strip() for ln in text.splitlines() if FLAG in ln]
    return out


def _occurrences() -> dict[str, list[str]]:
    files = subprocess.run(["git", "ls-files", "-z", "*.py", "*.sh", "*.ps1"], cwd=ROOT,
                           capture_output=True, text=True, check=True).stdout.split("\0")
    return _scan(ROOT, files)


def _violations(found: dict[str, list[str]]) -> list[tuple[str, list[str]]]:
    allowed = {(p, ln) for p, ln in ALLOWLIST}
    out = []
    for path, lines in found.items():
        rest = [ln for ln in lines if (path, ln) not in allowed]
        if len(rest) > PENDING_SCOPING.get(path, 0):
            out.append((path, rest))
    return out


def test_the_allowlist_holds_only_reasoned_lines() -> None:
    for (path, line), reason in ALLOWLIST.items():
        assert FLAG in line and len(reason.strip()) >= 20, (path, line)


def test_no_permission_bypass_outside_the_lists() -> None:
    unexpected = _violations(_occurrences())
    assert not unexpected, (
        f"{FLAG} found where no list allows it -- give the agent a scoped --allowedTools list "
        f"(libs/ops/agent_denials.scoped_claude_args) instead: {unexpected}")


def test_pending_scoping_only_shrinks() -> None:
    found = _occurrences()
    stale = {p: n for p, n in PENDING_SCOPING.items()
             if (ROOT / p).is_file() and len(found.get(p, [])) < n}
    assert not stale, f"these lanes were scoped -- lower or delete their entries: {stale}"


@pytest.mark.parametrize("rel", ["scripts/run_deep_sweep.py", "scripts/run_capability_hunt.py",
                                 "scripts/run_calibration_probe.py", "ops/brain_env.sh",
                                 "ops/setup_brain_api_key.sh", "ops/setup_brain_token.sh",
                                 "scripts/brain_model_upgrade.py", "scripts/run_model_upgrade.py"])
def test_the_scoped_organs_carry_no_bypass(rel: str) -> None:
    assert FLAG not in (ROOT / rel).read_text("utf-8")
    assert rel not in PENDING_SCOPING


def test_the_fence_catches_a_planted_flag(tmp_path: Path) -> None:
    """The fence must see what it fences: a planted line in a scanned file type is found."""
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts/new_organ.py").write_text(f"argv = ['claude', '-p', 'x', '{FLAG}']\n",
                                                   "utf-8")
    (tmp_path / "ops").mkdir()
    (tmp_path / "ops/run_cro_ai.sh").write_text(f"claude -p x {FLAG}\nclaude -p y {FLAG}\n",
                                                "utf-8")
    found = _scan(tmp_path, ["scripts/new_organ.py", "ops/run_cro_ai.sh", "absent.ps1"])
    bad = dict(_violations(found))
    assert "scripts/new_organ.py" in bad
    # a pending lane may not GROW: a second bypass in it fails too
    assert "ops/run_cro_ai.sh" in bad
