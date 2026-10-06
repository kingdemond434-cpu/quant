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



# ---------------------------------------------------------------------------------------------
# OUR OWN AGENTS' CONFIGS (2026-10-06 audit of #179). The CLI flag is not the only way to switch
# permissions off: `"defaultMode": "bypassPermissions"` in .claude/settings*.json, an agent
# definition's permission mode, or a launcher passing `--permission-mode bypassPermissions` does
# the same thing with no flag in sight. Any `defaultMode` in a settings file is flagged too: the
# desk's agents get their permissions from explicit --allowedTools lists, never from a mode.
#
# THE PRINCIPAL'S OWN CODEX RUNNERS ARE NOT FENCED HERE. The midnight controller, the brain
# hunter's Codex failover and Run-DeskCycle's Codex lane are the principal's own runners, set up
# by the principal on the principal's seat; their Codex sandbox flags are the principal's call,
# so CI never fails on them. They are excluded BY NAME below, and the exclusion covers only the
# Codex tokens -- a Claude bypass in the same file is still fenced by the tests above.

#: Built by concatenation so this file is not itself a match.
BYPASS_MODE = "bypass" + "Permissions"
DEFAULT_MODE = "default" + "Mode"
CODEX_BYPASS = ("--dangerously" + "-bypass-approvals-and-sandbox", "danger" + "-full-access",
                "--full" + "-auto")

#: The principal's own Codex runners (path -> what it is). Codex tokens in these files never
#: fail CI. Add nothing here that is not the principal's own runner.
PRINCIPAL_CODEX_RUNNERS: dict[str, str] = {
    "ops/run_midnight_codex_controller.sh": "the principal's midnight Codex controller",
    "ops/run_brain_hunter.sh": "the principal's brain hunter (its Codex failover branch)",
    "desks/mt5/scripts/Run-DeskCycle.ps1": "the principal's desk cycle (its Codex lane flags)",
}


def _is_test(rel: str) -> bool:
    """Tests ASSERT the tokens are absent, so they necessarily name them."""
    parts = Path(rel).parts
    return "tests" in parts or Path(rel).name.startswith("test_")


def _config_files(root: Path) -> list[str]:
    """Our agents' configs: settings (tracked or local), agent and command definitions."""
    out: set[str] = set()
    claude = root / ".claude"
    if claude.is_dir():
        out |= {str(p.relative_to(root)) for p in claude.glob("settings*.json")}
        for sub in ("agents", "commands"):
            if (claude / sub).is_dir():
                out |= {str(p.relative_to(root)) for p in (claude / sub).rglob("*")
                        if p.is_file()}
    return sorted(out)


def _scan_modes(root: Path, configs: list[str], scripts: list[str]) -> dict[str, list[str]]:
    """path -> offending lines: a bypass mode or a defaultMode in a config; a bypass mode in a
    launcher script; a Codex bypass flag outside the principal's runners."""
    out: dict[str, list[str]] = {}

    def _lines(rel: str) -> list[str]:
        try:
            return (root / rel).read_text("utf-8", errors="replace").splitlines()
        except OSError:
            return []

    for rel in configs:
        bad = [ln.strip() for ln in _lines(rel) if BYPASS_MODE in ln or DEFAULT_MODE in ln]
        if bad:
            out[rel] = bad
    for rel in filter(None, scripts):
        if _is_test(rel) or not (root / rel).is_file():
            continue
        bad = [ln.strip() for ln in _lines(rel) if BYPASS_MODE in ln]
        if rel not in PRINCIPAL_CODEX_RUNNERS:
            bad += [ln.strip() for ln in _lines(rel) if any(t in ln for t in CODEX_BYPASS)]
        if bad:
            out.setdefault(rel, []).extend(bad)
    return out


def test_no_bypass_mode_in_our_agent_configs_or_launchers() -> None:
    scripts = subprocess.run(["git", "ls-files", "-z", "*.py", "*.sh", "*.ps1"], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout.split("\0")
    found = _scan_modes(ROOT, _config_files(ROOT), scripts)
    assert not found, (
        f"a permission bypass by mode ({BYPASS_MODE} / {DEFAULT_MODE} / a Codex bypass flag) in "
        f"our own agents' configs or launchers -- scope the agent with an explicit "
        f"--allowedTools list instead: {found}")


def test_the_principal_runners_are_excluded_by_name_and_still_exist() -> None:
    for rel, why in PRINCIPAL_CODEX_RUNNERS.items():
        assert (ROOT / rel).is_file(), f"{rel} is gone: drop it from the exclusion"
        assert "principal" in why


def test_the_mode_fence_catches_planted_configs(tmp_path: Path) -> None:
    (tmp_path / ".claude/agents").mkdir(parents=True)
    (tmp_path / ".claude/settings.local.json").write_text(
        '{"permissions": {"' + DEFAULT_MODE + '": "acceptEdits"}}', "utf-8")
    (tmp_path / ".claude/agents/hunter.md").write_text(
        f"---\npermissionMode: {BYPASS_MODE}\n---\n", "utf-8")
    (tmp_path / "ops").mkdir()
    (tmp_path / "ops/new_lane.sh").write_text(
        f"claude -p x --permission-mode {BYPASS_MODE}\ncodex exec {CODEX_BYPASS[0]} -\n",
        "utf-8")
    (tmp_path / "ops/run_midnight_codex_controller.sh").write_text(
        f"ARGS=({CODEX_BYPASS[0]})\n", "utf-8")
    (tmp_path / "ops/run_brain_hunter.sh").write_text(
        f"codex exec --sandbox {CODEX_BYPASS[1]} -\nclaude --permission-mode {BYPASS_MODE}\n",
        "utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/test_x.py").write_text(f"assert '{BYPASS_MODE}' not in argv\n",
                                              "utf-8")
    configs = _config_files(tmp_path)
    assert ".claude/settings.local.json" in configs and ".claude/agents/hunter.md" in configs
    found = _scan_modes(tmp_path, configs,
                        ["ops/new_lane.sh", "ops/run_midnight_codex_controller.sh",
                         "ops/run_brain_hunter.sh", "tests/test_x.py"])
    assert set(found) == {".claude/settings.local.json", ".claude/agents/hunter.md",
                          "ops/new_lane.sh", "ops/run_brain_hunter.sh"}
    assert len(found["ops/new_lane.sh"]) == 2
    # the principal's runner: its Codex flag is excluded, a Claude bypass mode in it is not
    assert found["ops/run_brain_hunter.sh"] == [f"claude --permission-mode {BYPASS_MODE}"]
    assert "ops/run_midnight_codex_controller.sh" not in found


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
