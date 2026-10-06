"""The ten VPS shell agent lanes run on scoped allowlists, never the blanket permission bypass.

Each ops/run_*.sh lane in libs/ops/vps_lane_scopes.LANES calls `scoped_claude <lane>` from
ops/scoped_claude.sh, which builds the lane's arguments with agent_denials.scoped_claude_args and
pipes the stream-json output through scripts/record_agent_denials.py, so a refused call is a
MISSED row in the lane's log and in data/cro_ai_logs/agent_denials.jsonl.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from libs.ops import agent_denials as ad
from libs.ops import vps_lane_scopes as vls

ROOT = Path(__file__).resolve().parents[2]
FLAG = "--dangerously" + "-skip-permissions"


def _split(argv: list[str]) -> tuple[list[str], list[str]]:
    i = argv.index("--allowedTools")
    j = argv.index("--disallowedTools") if "--disallowedTools" in argv else len(argv)
    return argv[i + 1:j], argv[j + 1:]


@pytest.mark.parametrize("name", sorted(vls.LANES))
def test_each_launcher_runs_its_lane_through_the_scoped_runner(name: str) -> None:
    lane = vls.LANES[name]
    assert lane.launcher in vls.LAUNCHERS
    text = (ROOT / lane.launcher).read_text("utf-8")
    assert FLAG not in text
    assert "source ops/scoped_claude.sh" in text
    assert re.search(rf"^\s*scoped_claude {name} ", text, re.M), lane.launcher
    # no bare `claude ... -p` call left beside it
    assert not re.search(r"^\s*(timeout \d+ )?claude\s.*-p\b", text, re.M), lane.launcher


@pytest.mark.parametrize("name", sorted(vls.LANES))
def test_lane_args_are_scoped_and_carry_every_never_rule(name: str) -> None:
    argv = vls.lane_args(name, "BRIEF", effort="low")
    assert FLAG not in argv and "--permission-mode" not in argv
    assert argv[argv.index("--output-format") + 1] == "stream-json" and "--verbose" in argv
    allowed, denied = _split(argv)
    assert allowed and all(allowed)
    assert set(ad.NEVER_RULES) <= set(denied)
    assert set(vls.LANE_SELF_RULES) <= set(denied)
    assert not any("data/secrets" in r for r in allowed)
    assert "TOOL ALLOWLIST FOR THIS LANE" in argv[1]


def test_never_rules_are_not_weakened() -> None:
    for rule in ("Read(data/secrets/**)", "Edit(scripts/run_deadman_switch.py)",
                 "Write(ops/principal_doctrine.txt)", "Bash(git push --force:*)",
                 "Bash(git stash:*)", "Bash(git commit -a:*)", "Bash(git reset --hard:*)"):
        assert rule in ad.NEVER_RULES


def test_research_digs_keep_the_freeze() -> None:
    digs = [n for n, lane in vls.LANES.items() if not lane.edits_code]
    assert len(digs) == 7
    for n in digs:
        rules = vls.LANES[n].rules
        assert "Edit(docs/research/**)" in rules and "Write(data/intelligence/**)" in rules
        assert not any(r.startswith(("Edit(scripts", "Edit(libs", "Write(scripts", "Write(libs"))
                       for r in rules), n
        assert not any(r.startswith("Bash(git push") for r in rules), n


def test_blind_rediscovery_has_no_web_and_web_digs_do() -> None:
    assert not {"WebSearch", "WebFetch"} & set(vls.LANES["blindrediscovery_dig"].rules)
    for n in ("dataaxis_dig", "litminer_dig", "prospector_dig", "frontier_miner",
              "brain_hunter", "video_hunter", "cro_ai"):
        assert {"WebSearch", "WebFetch"} <= set(vls.LANES[n].rules), n


def test_only_the_gap_wirer_pushes_and_restarts_units() -> None:
    for n, lane in vls.LANES.items():
        pushes = any(r.startswith("Bash(git push") for r in lane.rules)
        units = any(r.startswith("Bash(systemctl --user restart") for r in lane.rules)
        assert pushes == (n == "gap_wirer") and units == (n == "gap_wirer"), n


def test_code_lanes_can_do_their_job() -> None:
    for n in ("gap_wirer", "recommendation_worker", "cro_ai"):
        rules = set(vls.LANES[n].rules)
        assert {"Edit(scripts/**)", "Edit(libs/**)", "Edit(tests/**)",
                "Bash(git commit -m:*)", "Bash(.venv/bin/python -m pytest:*)",
                "Bash(.venv/bin/python scripts/*)"} <= rules, n


def test_cli_emits_nul_separated_args_from_stdin() -> None:
    r = subprocess.run([sys.executable, "-m", "libs.ops.vps_lane_scopes", "argv", "gap_wirer",
                        "--effort", "max"], input="BRIEF", capture_output=True, text=True,
                       cwd=ROOT, check=True)
    argv = r.stdout.split("\0")[:-1]
    assert argv[0] == "-p" and argv[1].startswith("BRIEF")
    assert argv[argv.index("--effort") + 1] == "max"
    empty = subprocess.run([sys.executable, "-m", "libs.ops.vps_lane_scopes", "argv", "cro_ai"],
                           input="  ", capture_output=True, text=True, cwd=ROOT)
    assert empty.returncode == 2 and empty.stdout == ""


def _fake_claude(tmp: Path) -> Path:
    stream = [
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "toolu_A", "name": "Bash",
             "input": {"command": "crontab -e"}}]}},
        {"type": "system", "subtype": "permission_denied", "tool_name": "Bash",
         "tool_use_id": "toolu_A", "message": "denied"},
        {"type": "result", "subtype": "success", "is_error": False, "result": "DIG DONE",
         "permission_denials": [{"tool_name": "Bash", "tool_use_id": "toolu_A",
                                 "tool_input": {"command": "crontab -e"}}]},
    ]
    body = "\n".join(json.dumps(e) for e in stream)
    fake = tmp / "fake_claude"
    fake.write_text("#!/usr/bin/env bash\n"
                    'printf "%s\\n" "$@" > "$(dirname "$0")/argv.txt"\n'
                    f"cat <<'JSON'\n{body}\nJSON\nexit 7\n", "utf-8")
    fake.chmod(0o755)
    return fake


def test_scoped_runner_records_refusals_and_keeps_the_lane_exit_code(tmp_path: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    (work / "scripts").symlink_to(ROOT / "scripts")
    fake = _fake_claude(tmp_path)
    log = work / "lane.log"
    env = {**os.environ, "QUANT_PY": sys.executable, "CLAUDE_BIN": str(fake),
           "PYTHONPATH": str(ROOT), "_DOCTRINE": "DOCTRINE"}
    r = subprocess.run(["bash", "-c", f'source "{ROOT}/ops/scoped_claude.sh"; '
                        f'scoped_claude prospector_dig "{log}" low <<<"THE BRIEF"; echo "rc=$?"'],
                       cwd=work, env=env, capture_output=True, text=True, timeout=120)
    assert "rc=7" in r.stdout, (r.stdout, r.stderr)
    argv = (tmp_path / "argv.txt").read_text("utf-8").splitlines()
    assert FLAG not in argv and "--allowedTools" in argv and "--disallowedTools" in argv
    assert argv[:2] == ["--append-system-prompt", "DOCTRINE"]
    text = log.read_text("utf-8")
    assert "DIG DONE" in text and "PERMISSION DENIED (counts as MISSED" in text
    rows = [json.loads(x) for x in
            (work / "data/cro_ai_logs/agent_denials.jsonl").read_text("utf-8").splitlines()]
    assert len(rows) == 1 and rows[0]["counts_as"] == "MISSED"
    assert rows[0]["lane"] == "prospector_dig" and rows[0]["surface"] == "vps_agent"
    assert not list((work / "data/cro_ai_logs/.streams").iterdir())


def test_scoped_runner_never_starts_without_a_scope(tmp_path: Path) -> None:
    fake = _fake_claude(tmp_path)
    log = tmp_path / "lane.log"
    env = {**os.environ, "QUANT_PY": sys.executable, "CLAUDE_BIN": str(fake),
           "PYTHONPATH": str(ROOT)}
    r = subprocess.run(["bash", "-c", f'source "{ROOT}/ops/scoped_claude.sh"; '
                        f'scoped_claude no_such_lane "{log}" low <<<"X"; echo "rc=$?"'],
                       cwd=tmp_path, env=env, capture_output=True, text=True, timeout=120)
    assert "rc=2" in r.stdout
    assert not (tmp_path / "argv.txt").exists()
    assert "SCOPE UNAVAILABLE" in log.read_text("utf-8")
