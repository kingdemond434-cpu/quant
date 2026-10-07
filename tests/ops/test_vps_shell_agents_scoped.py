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
from libs.ops import lane_guard as lg
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


# ------------------------------------------------------------------ the whole-command fence
BOX = lg.BOX_BRANCH

#: (id, command): every push form the audit of #199 named, one test each. Ids are literal so
#: `pytest -n auto` collects the same set on every worker.
REFUSED_PUSHES = [
    ("force_long_first", "git push --force origin feature"),
    ("force_long_after_remote", "git push origin feature --force"),
    ("force_short", "git push -f origin feature"),
    ("force_short_after_refspec", "git push origin feature -f"),
    ("force_short_combined", "git push -uf origin feature"),
    ("force_short_combined_tail", "git push origin feature -vfu"),
    ("force_with_lease", "git push --force-with-lease origin feature"),
    ("force_with_lease_value_after_remote",
     "git push origin feature --force-with-lease=feature:abc"),
    ("force_plus_refspec", "git push origin +feature"),
    ("delete_refspec", "git push origin :branch"),
    ("delete_refspec_refs_heads", "git push origin :refs/heads/branch"),
    ("delete_long", "git push --delete origin branch"),
    ("delete_long_after_remote", "git push origin --delete branch"),
    ("delete_short", "git push -d origin branch"),
    ("mirror", "git push --mirror origin"),
    ("mirror_after_remote", "git push origin --mirror"),
    ("box_branch_plain", f"git push origin {BOX}"),
    ("box_branch_head_refspec", f"git push origin HEAD:{BOX}"),
    ("box_branch_refs_heads", f"git push origin refs/heads/{BOX}"),
    ("box_branch_head_refs_heads", f"git push origin HEAD:refs/heads/{BOX}"),
    ("box_branch_from_other_src", f"git push origin desk-sync-clean:refs/heads/{BOX}"),
    ("box_branch_second_refspec", f"git push origin desk-sync-clean {BOX}"),
    ("git_dash_C", "git -C /home/quant/quant-platform push origin feature --force"),
    ("chained", "cd ops && git push origin feature -f"),
    ("nested_shell", 'bash -c "git push origin feature --force"'),
    ("inline_alias", "git -c alias.p=push p origin feature"),
    ("all_refs", "git push --all origin"),
]


@pytest.mark.parametrize("cmd", [c for _, c in REFUSED_PUSHES],
                         ids=[i for i, _ in REFUSED_PUSHES])
def test_push_matcher_refuses(cmd: str) -> None:
    assert lg.push_refusal(cmd, "desk-sync-clean"), cmd
    assert lg.refusal("Bash", {"command": cmd}, "desk-sync-clean"), cmd


def test_push_matcher_resolves_a_bare_push_to_the_checked_out_branch() -> None:
    assert lg.push_refusal("git push origin", BOX)
    assert lg.push_refusal("git push origin HEAD", BOX)
    assert lg.push_refusal("git push origin HEAD", None)  # unknown target: refused, not guessed
    assert lg.push_refusal("git push origin", "desk-sync-clean") is None


@pytest.mark.parametrize("cmd", [
    "git push origin desk-sync-clean", "git push -u origin claude/fix-x",
    "git push origin HEAD:claude/fix-x", "git status", "git log --force-with-lease",
    "echo git-push --force",
], ids=["desk_branch", "upstream_feature", "head_to_feature", "status", "log_flag", "echo"])
def test_push_matcher_allows_ordinary_pushes(cmd: str) -> None:
    assert lg.push_refusal(cmd, "desk-sync-clean") is None


#: (id, command): a read of data/secrets through every program the audit named, one test each.
REFUSED_SECRET_READS = [
    ("cat", "cat data/secrets/keys.env"),
    ("head", "head -n 5 data/secrets/keys.env"),
    ("tail", "tail -c 200 data/secrets/keys.env"),
    ("grep", "grep -i token data/secrets/keys.env"),
    ("grep_recursive_cwd", "grep -rn token ."),
    ("grep_recursive_no_path", "grep -R token"),
    ("grep_recursive_data", "grep -r token data/"),
    ("jq", "jq . data/secrets/keys.json"),
    ("jq_glob", "jq . data/*/keys.json"),
    ("scripts_cli",
     ".venv/bin/python scripts/collect_youtube_corpus.py --key data/secrets/yt.txt"),
    ("scripts_cli_equals", ".venv/bin/python scripts/any_tool.py --in=./data//secrets/yt.txt"),
    ("absolute_path", "head /home/quant/quant-platform/data/secrets/keys.env"),
    ("dotdot_path", "tail data/../data/secrets/keys.env"),
    ("glob_dir", "head data/s*/keys.env"),
    ("variable", "cat data/$SECRET_DIR/keys.env"),
    ("chained", "ls data && head data/secrets/keys.env"),
    ("nested_shell", "bash -c 'jq . data/secrets/keys.json'"),
]


@pytest.mark.parametrize("cmd", [c for _, c in REFUSED_SECRET_READS],
                         ids=[i for i, _ in REFUSED_SECRET_READS])
def test_secrets_fence_refuses(cmd: str) -> None:
    assert lg.secrets_refusal(cmd), cmd
    assert lg.refusal("Bash", {"command": cmd}, "desk-sync-clean"), cmd


@pytest.mark.parametrize("cmd", [
    "head data/universe.json", "jq . data/*.json", "grep -rn edge docs/research",
    "grep -r edge desks/mt5/data", "tail -n 50 data/cro_ai_logs/x.log",
], ids=["head_catalog", "jq_glob_flat", "grep_r_docs", "grep_r_desk_data", "tail_log"])
def test_secrets_fence_allows_the_catalogs(cmd: str) -> None:
    assert lg.secrets_refusal(cmd) is None


def test_secrets_fence_covers_non_bash_tools() -> None:
    assert lg.refusal("Read", {"file_path": "/home/quant/quant-platform/data/secrets/k"})
    assert lg.refusal("Grep", {"pattern": "x", "path": "data/secrets"})
    assert lg.refusal("Glob", {"pattern": "data/secrets/**"})
    assert lg.refusal("Read", {"file_path": "docs/LAWS.md"}) is None


def _hook(payload: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-I", str(ROOT / "libs/ops/lane_guard.py"), "hook"],
                          input=payload, capture_output=True, text=True, timeout=60)


def test_hook_blocks_with_the_recorders_refusal_wording(tmp_path: Path) -> None:
    r = _hook(json.dumps({"tool_name": "Bash", "cwd": str(tmp_path),
                          "tool_input": {"command": "git push origin x --force"}}))
    assert r.returncode == 2 and lg.REFUSAL in r.stderr
    assert ad._is_refusal(r.stderr)  # so the stream parser records it as MISSED
    r = _hook(json.dumps({"tool_name": "Bash", "tool_input": {"command": "head data/secrets/k"}}))
    assert r.returncode == 2
    ok = _hook(json.dumps({"tool_name": "Bash", "tool_input": {"command": "ls docs"}}))
    assert ok.returncode == 0 and ok.stderr == ""


def test_hook_fails_closed() -> None:
    assert _hook("not json").returncode == 2
    unbalanced = json.dumps({"tool_name": "Bash", "tool_input": {"command": "cat 'x"}})
    assert _hook(unbalanced).returncode == 2


@pytest.mark.parametrize("name", sorted(vls.LANES))
def test_every_lane_carries_the_hook(name: str) -> None:
    argv = vls.lane_args(name, "BRIEF", effort="low")
    assert argv[0] == "-p" and argv[2] == "--settings"
    hooks = json.loads(argv[3])["hooks"]["PreToolUse"]
    cmd = hooks[0]["hooks"][0]["command"]
    assert hooks[0]["matcher"] == "*" and "lane_guard.py" in cmd and cmd.endswith("|| exit 2")
    assert "Write(libs/ops/lane_guard.py)" in vls.LANE_DENIED
