"""The VPS agent organs run on scoped allowlists, and every refused call reads UNMEASURED.

run_deep_sweep, run_capability_hunt and run_calibration_probe used to hand `claude -p` the blanket
permission bypass. Each now passes the narrowest `--allowedTools` list its brief needs, reads the
stream-json output with libs/ops/agent_denials.py, and records one row per refused call. A seat
with a refused step never reads as success. The stream fixtures copy the shapes in
tests/ops/test_agent_denials.py (Claude Code 2.1.285, 2026-09-30).
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from libs.ops import agent_denials as ad

FLAG = "--dangerously" + "-skip-permissions"

_USE_BASH = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "id": "toolu_A", "name": "Bash",
     "input": {"command": "crontab -e"}}]}}
_DENIED_EVT = {"type": "system", "subtype": "permission_denied", "tool_name": "Bash",
               "tool_use_id": "toolu_A", "message": "denied"}


def _result(text: str, denials: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {"type": "result", "subtype": "success", "is_error": False, "result": text,
            "permission_denials": denials or []}


def _stream(text: str, *, denied: bool) -> str:
    events: list[dict[str, Any]] = []
    if denied:
        events += [_USE_BASH, _DENIED_EVT]
    events.append(_result(text, [{"tool_name": "Bash", "tool_use_id": "toolu_A",
                                  "tool_input": {"command": "crontab -e"}}] if denied else None))
    return "\n".join(json.dumps(e) for e in events) + "\n"


def _cp(stdout: str, code: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(["bash"], code, stdout=stdout, stderr="")


def _rules(argv: list[str]) -> tuple[list[str], list[str]]:
    """(allowed, disallowed) as the CLI would read them off an argv."""
    i = argv.index("--allowedTools")
    j = argv.index("--disallowedTools") if "--disallowedTools" in argv else len(argv)
    return argv[i + 1:j], argv[j + 1:]


def _no_bypass(argv: list[str]) -> None:
    assert FLAG not in argv and "bypassPermissions" not in argv and "acceptEdits" not in argv
    assert "--permission-mode" not in argv
    assert argv[argv.index("--output-format") + 1] == "stream-json" and "--verbose" in argv


# ------------------------------------------------------------------ the shared builder
def test_the_prompt_precedes_the_variadic_rule_lists() -> None:
    args = ad.scoped_claude_args("PROMPT", allowed=["Read", "Edit(x.md)"], effort="max")
    assert args[:2] == ["-p", "PROMPT"]
    allowed, denied = _rules(args)
    assert allowed == ["Read", "Edit(x.md)"]
    assert denied == list(ad.NEVER_RULES)
    assert args[args.index("--effort") + 1] == "max"


def test_an_empty_allowlist_means_no_tools_at_all() -> None:
    args = ad.scoped_claude_args("P", allowed=[], max_turns=1)
    assert args[args.index("--allowedTools") + 1] == "" and args[-1] == ""
    assert "--disallowedTools" not in args
    assert args[args.index("--max-turns") + 1] == "1"


def test_the_brain_wrapper_passes_the_scoped_args_through() -> None:
    argv = ad.brain_argv("organ", ["-p", "P"])
    assert argv[:2] == ["bash", "-c"] and argv[3] == "organ" and argv[4:] == ["-p", "P"]
    assert '"$@"' in argv[2] and "brain_auth_check" in argv[2] and FLAG not in argv[2]


def test_the_read_only_rules_hold_no_write_and_the_never_rules_hold_the_rails() -> None:
    for r in ad.READ_ONLY_RULES:
        assert not r.startswith(("Edit", "Write", "NotebookEdit", "WebFetch")), r
        for bad in ("git push", "git commit", "git add", "rm", "crontab -e", "python:*"):
            assert bad not in r, r
    for need in ("Read(data/secrets/**)", "Edit(scripts/run_deadman_switch.py)",
                 "Edit(ops/principal_doctrine.txt)", "Bash(git push --force:*)"):
        assert need in ad.NEVER_RULES


# ------------------------------------------------------------------ run_deep_sweep
@pytest.fixture()
def sweep(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    import scripts.run_deep_sweep as ds
    out = tmp_path / "docs/research/deep_sweep"
    out.mkdir(parents=True)
    monkeypatch.setattr(ds, "ROOT", tmp_path)
    monkeypatch.setattr(ds, "OUT", out)
    return ds


def test_an_auditor_may_write_only_its_own_report(sweep: Any) -> None:
    report = sweep.OUT / "20261001_infrastructure.md"
    rules = sweep.auditor_rules(report)
    writes = [r for r in rules if r.startswith(("Edit", "Write"))]
    assert writes == ["Edit(docs/research/deep_sweep/20261001_infrastructure.md)",
                      "Write(docs/research/deep_sweep/20261001_infrastructure.md)"]
    assert not any("git push" in r or "git commit" in r for r in rules)


def test_the_synthesis_lead_writes_what_its_brief_names_and_nothing_else(sweep: Any) -> None:
    rules = sweep.synthesis_rules(sweep.OUT / "20261001_SYNTHESIS.md")
    writes = {r for r in rules if r.startswith("Edit(")}
    assert writes == {"Edit(docs/research/deep_sweep/20261001_SYNTHESIS.md)",
                      "Edit(docs/research/TIER1_BENCHMARK.md)",
                      "Edit(docs/research/improvement_inbox.md)",
                      "Edit(data/PRINCIPAL_ACTION.md)"}
    assert "Bash(.venv/bin/python scripts/recommendations.py add:*)" in rules
    assert not any("recommendations.py dispose" in r for r in rules)


def test_a_sweep_seat_is_called_scoped(sweep: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[list[str]] = []

    def fake_run(argv: list[str], **_kw: Any) -> subprocess.CompletedProcess[str]:
        seen.append(argv)
        return _cp(_stream("done", denied=False))

    monkeypatch.setattr(sweep.subprocess, "run", fake_run)
    sweep.run_auditor("infrastructure", "brief", "20261001", "CORE")
    (argv,) = seen
    _no_bypass(argv)
    allowed, _denied = _rules(argv)
    assert allowed == sweep.auditor_rules(sweep.OUT / "20261001_infrastructure.md")
    assert "TOOL ALLOWLIST" in argv[argv.index("-p") + 1]


def _write_complete(report: Path) -> None:
    report.write_text("# r\n" + "x" * 1300 + "\nSTATUS: COMPLETE\n", "utf-8")


def test_a_refused_step_makes_a_finished_seat_unmeasured(
        sweep: Any, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    report = sweep.OUT / "20261001_infrastructure.md"

    def fake_run(_argv: list[str], **_kw: Any) -> subprocess.CompletedProcess[str]:
        _write_complete(report)
        return _cp(_stream("report written", denied=True))

    monkeypatch.setattr(sweep.subprocess, "run", fake_run)
    assert sweep.run_auditor("infrastructure", "brief", "20261001", "CORE") == "UNMEASURED"
    rows = [json.loads(x) for x in
            Path(f"{report}.DENIED").read_text("utf-8").splitlines()]
    assert len(rows) == 1
    r = rows[0]
    assert (r["verdict"], r["counts_as"], r["surface"], r["seat"]) == (
        "UNMEASURED", "MISSED", "deep_sweep", "infrastructure")
    assert "PERMISSION DENIED" in capsys.readouterr().out
    # and it stays UNMEASURED on resume rather than turning COMPLETE
    assert sweep.seat_status(report) == "UNMEASURED"


def test_a_clean_seat_is_complete_and_leaves_no_sidecar(
        sweep: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    report = sweep.OUT / "20261001_infrastructure.md"

    def fake_run(_argv: list[str], **_kw: Any) -> subprocess.CompletedProcess[str]:
        _write_complete(report)
        return _cp(_stream("ok", denied=False))

    monkeypatch.setattr(sweep.subprocess, "run", fake_run)
    assert sweep.run_auditor("infrastructure", "brief", "20261001", "CORE") == "COMPLETE"
    assert not Path(f"{report}.DENIED").exists()


# ------------------------------------------------------------------ run_capability_hunt
def test_the_hunt_proposer_is_read_only_and_the_builder_is_path_scoped() -> None:
    import scripts.run_capability_hunt as ch
    assert not any(r.startswith(("Edit", "Write")) for r in ch.PROPOSER_RULES)
    assert not any("git" in r and ("push" in r or "commit" in r or "add" in r)
                   for r in ch.PROPOSER_RULES)
    writes = [r for r in ch.BUILDER_RULES if r.startswith(("Edit(", "Write("))]
    assert writes and all("**" in r or r.endswith((".md)", ".manifest)")) for r in writes)
    for never in ("ops/principal_doctrine.txt", "data/secrets", "run_deadman_switch"):
        assert not any(r in (f"Edit({never})", f"Write({never})") for r in ch.BUILDER_RULES)
        assert any(never in r for r in ad.NEVER_RULES)
    assert "Bash(git commit -m:*)" in ch.BUILDER_RULES
    assert not any("--force" in r or "-f:" in r for r in ch.BUILDER_RULES)
    for rules in (ch.PROPOSER_RULES, ch.BUILDER_RULES):
        argv = ch.claude_argv("P", rules)
        _no_bypass(argv)
        allowed, denied = _rules(argv)
        assert allowed == rules and denied == list(ad.NEVER_RULES)


def test_a_hunt_stage_with_a_refusal_is_not_ok_and_says_why(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    import scripts.run_capability_hunt as ch
    monkeypatch.setattr(ch.subprocess, "run",
                        lambda *_a, **_k: _cp(_stream("MISSING CAPABILITY: x", denied=True)))
    ok, text, rows = ch._claude("P", rules=ch.PROPOSER_RULES, stage="propose",
                                stamp="20261001", slot=2)
    assert not ok and text == "MISSING CAPABILITY: x"
    assert [(r["verdict"], r["counts_as"], r["stage"], r["slot"]) for r in rows] == [
        ("UNMEASURED", "MISSED", "propose", 2)]
    assert "PERMISSION DENIED" in capsys.readouterr().out

    monkeypatch.setattr(ch.subprocess, "run",
                        lambda *_a, **_k: _cp(_stream("MISSING CAPABILITY: y", denied=False)))
    ok, text, rows = ch._claude("P", rules=ch.PROPOSER_RULES, stage="propose")
    assert ok and text == "MISSING CAPABILITY: y" and rows == []


def test_the_hunt_records_refusals_in_its_history(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import scripts.run_capability_hunt as ch
    (tmp_path / "data").mkdir()
    monkeypatch.setattr(ch, "_ROOT", tmp_path)
    monkeypatch.setattr(ch, "_OUT", tmp_path / "docs/research/capability_hunt")
    monkeypatch.setattr(ch, "_law_guard", lambda: None)
    monkeypatch.setattr(ch, "_gpt", lambda _p: (False, "dark"))
    calls = iter([_stream("proposal", denied=False), _stream("built", denied=True)])
    monkeypatch.setattr(ch.subprocess, "run", lambda *_a, **_k: _cp(next(calls)))
    monkeypatch.setattr("sys.argv", ["run_capability_hunt.py", "--slot", "1"])
    assert ch.main() == 0
    status = json.loads((tmp_path / "data/capability_hunt.json").read_text("utf-8"))
    assert status["verdict"] == "UNMEASURED" and status["built"] is False
    assert [d["stage"] for d in status["permission_denials"]] == ["build"]
    hist = json.loads((tmp_path / "data/capability_hunt_history.json").read_text("utf-8"))
    assert hist["runs"][-1]["permission_denials"][0]["counts_as"] == "MISSED"


# ------------------------------------------------------------------ run_calibration_probe
def _charts(root: Path) -> None:
    (root / "data").mkdir(exist_ok=True)
    (root / "data/chart_context.json").write_text(json.dumps({"charts": {
        f"S{i}": {"state": "OK", "timeframes": {"15m": {"price": 100.0 + i}}}
        for i in range(3)}}), "utf-8")


def test_the_calibration_probe_holds_no_tools_and_one_turn() -> None:
    from scripts.run_calibration_probe import ask_argv
    argv = ask_argv("P")
    _no_bypass(argv)
    assert argv[argv.index("--allowedTools") + 1] == ""
    assert "--disallowedTools" not in argv
    assert argv[argv.index("--max-turns") + 1] == "1"


def test_a_refused_call_poses_nothing_and_reads_unmeasured(tmp_path: Path) -> None:
    from scripts.run_calibration_probe import pose
    _charts(tmp_path)
    out = pose(tmp_path, n=3,
               ask=lambda _p: _stream('{"q1": 0.6, "q2": 0.4, "q3": 0.55}', denied=True))
    assert out["status"] == "UNMEASURED" and out["counts_as"] == "MISSED"
    (row,) = out["permission_denials"]
    assert row["surface"] == "calibration_probe" and row["verdict"] == "UNMEASURED"
    assert not (tmp_path / "data/calibration_probe.jsonl").exists()


def test_a_clean_stream_is_read_from_its_result_event(tmp_path: Path) -> None:
    from scripts.run_calibration_probe import pose
    _charts(tmp_path)
    out = pose(tmp_path, n=3,
               ask=lambda _p: _stream('{"q1": 0.6, "q2": 0.4, "q3": 0.55}', denied=False))
    assert out["status"] == "POSED" and out["n"] == 3
