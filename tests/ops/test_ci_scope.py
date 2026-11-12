"""Docs-, reports- and state-only PRs skip the heavy CI steps; everything else runs it all.

The coordinator's constraints (2026-11-11): an ALLOWLIST of skip paths, replay-shadow and the
audit gate still judge anything touching code, sizing, the gateway or a PROTECTED path, and a
skipped required check still reports SUCCESS so merges never hang (audit_gate.checks() requires a
success conclusion from every gating job, so the jobs run and only their steps are skipped).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
WF = ROOT / ".github" / "workflows"
GATE = "steps.scope.outputs.heavy != 'false'"
SCOPED = {
    "ci.yml": ("quality", "mt5-money-path", "coverage-floor"),
    "release-gates.yml": ("risk-invariants", "replay-shadow"),
}


def _load(name: str, rel: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


scope = _load("ci_scope_t", ".github/scripts/ci_scope.py")
gate = _load("audit_gate_scope_t", ".github/scripts/audit_gate.py")
governed = _load("release_scope_t", "libs/ops/release.py").is_governed_state


def _heavy(*paths: str) -> bool:
    return scope.decide(paths, governed, gate)[0]


@pytest.mark.parametrize(
    "paths",
    [
        ("docs/notes/idea.md",),
        ("context/decision_journal.jsonl",),
        ("docs/desk_lessons.jsonl",),
        ("reports/weekly.md", "desks/mt5/logs/run.log"),
        ("desks/mt5/docs/diagram.png",),
    ],
)
def test_prose_and_the_journal_are_light(paths) -> None:
    assert _heavy(*paths) is False


@pytest.mark.parametrize(
    "paths",
    [
        ("scripts/x.py",),  # code
        ("docs/a.md", "desks/mt5/mt5desk/gateway.py"),  # one code path makes the whole PR heavy
        ("docs/helper.py",),  # a code file type anywhere
        ("docs/run.ps1",),
        ("docs/notes.txt",),
        ("desks/mt5/data/cfg.yml",),
        ("desks/mt5/reports/pf_allocation.json",),
        # #983 audit M2: what the live book reads is heavy at ANY depth
        ("desks/mt5/data/universe/universe.json",),
        ("data/intelligence/x/y.json",),
        ("desks/mt5/data/history.jsonl",),
        ("desks/mt5/reports/sub/table.csv",),
        ("desks/mt5/data/notes.md",),
        ("reports/table.csv",),  # not prose
        ("docs/data.json",),  # not prose  # a replay-shadow input (sizing)
        ("desks/mt5/data/LIVE_MANIFEST.jsonl",),  # governed state
        ("desks/mt5/data/GENERIC_EXEC_ENABLED",),  # a switch
        ("desks/mt5/data/IMMUTABLE_MANIFEST.json",),
        ("data/secrets/x.json",),
        ("desks/mt5/data/secrets/k",),
        ("docs/cro/memo.md",),
        ("docs/research.md",),  # formerly protected prose
        ("docs/claude_rules.md",),
        ("docs/risk_policy.md",),  # governing names
        (".github/workflows/ci.yml",),
        (".github/scripts/ci_scope.py",),
        ("libs/ops/release.py",),
        ("ops/release/protected_paths.txt",),
        (),  # nothing read is never light
    ],
)
def test_anything_else_is_heavy(paths) -> None:
    assert _heavy(*paths) is True


def test_too_many_files_is_heavy() -> None:
    assert _heavy(*[f"docs/n{i}.md" for i in range(scope.MAX_FILES)]) is True


def test_any_failure_prints_heavy(tmp_path, capsys, monkeypatch) -> None:
    monkeypatch.setattr(scope, "pr_paths", lambda *a: (_ for _ in ()).throw(RuntimeError("x")))
    assert scope.main(["--pr", "1", "--head", "abc"]) == 0
    assert capsys.readouterr().out.strip() == "heavy=true"
    f = tmp_path / "p.txt"
    f.write_text("docs/a.md\n", encoding="utf-8")
    summ = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summ))
    scope.main(["--paths", str(f)])
    assert capsys.readouterr().out.strip() == "heavy=false"
    assert summ.read_text(encoding="utf-8").startswith("**LIGHT:")


def test_the_file_list_must_match_the_prs_count_and_head(monkeypatch) -> None:
    import json

    pages = {1: [{"filename": "docs/a.md"}], 2: []}

    def fake(arg: str) -> str:
        if "/files" in arg:
            return json.dumps(pages[int(arg.rsplit("page=", 1)[1])])
        return json.dumps({"head": {"sha": "h1"}, "changed_files": 2})

    monkeypatch.setattr(scope, "_gh", fake)
    with pytest.raises(RuntimeError):
        scope.pr_paths("o/r", 1, "h1")  # 1 listed, 2 changed
    with pytest.raises(RuntimeError):
        scope.pr_paths("o/r", 1, "moved")


@pytest.mark.parametrize("wf,job", [(w, j) for w, js in SCOPED.items() for j in js])
def test_every_heavy_step_is_gated_and_the_job_still_runs(wf, job) -> None:
    doc = yaml.safe_load((WF / wf).read_text(encoding="utf-8"))
    j = doc["jobs"][job]
    assert "steps.scope" not in str(j.get("if", "")), "a job-level skip would never succeed"
    steps = j["steps"]
    assert steps[0]["with"]["ref"] == "${{ github.event.pull_request.base.sha }}"
    assert steps[0]["with"]["path"] == "_ci_scope" and steps[1]["id"] == "scope"
    assert "_ci_scope/.github/scripts/ci_scope.py" in steps[1]["run"]
    assert 'echo "heavy=true"' in steps[1]["run"]  # no base filter yet: heavy
    for s in steps[2:]:
        assert GATE in str(s.get("if", "")), s.get("name") or s.get("uses")


def test_the_unscoped_jobs_are_untouched() -> None:
    for wf, job in (
        ("release-gates.yml", "independent-review"),
        ("trusted-eval.yml", "trusted-eval"),
        ("audit-gate.yml", "gate"),
    ):
        text = yaml.safe_dump(yaml.safe_load((WF / wf).read_text(encoding="utf-8"))["jobs"][job])
        assert "steps.scope" not in text and "ci_scope" not in text
