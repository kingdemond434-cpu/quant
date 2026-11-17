"""The fast lane (zuck 2026-11-17: "strip all checks of anything that doesn't touch live money").

A PR that touches no money path, no release or box machinery and no check merges on one `smoke`
job: no Auditor CLEAR, no APPROVE MERGES, no AUTO job, no trusted-eval. These pin both halves:
what counts as fast (.github/scripts/fast_lane.py) and what the gate does with it
(.github/scripts/audit_gate.py run_fast), plus the workflow wiring that skips the heavy jobs.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
WF = ROOT / ".github" / "workflows"


def _load(name: str, rel: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


fl = _load("fast_lane_t", ".github/scripts/fast_lane.py")
ag = _load("audit_gate_fast_t", ".github/scripts/audit_gate.py")


# ------------------------------------------------------------------------- what is fast


@pytest.mark.parametrize(
    "paths",
    [
        ["docs/some_note.md"],
        ["libs/research/zz_brand_new_reader.py", "tests/research/test_zz_brand_new_reader.py"],
        ["desks/mt5/research/zz_brand_new_miner.py"],
        ["scripts/zz_brand_new_report.py", "reports/zz.md"],
    ],
)
def test_research_docs_and_new_tests_are_fast(paths: list[str]) -> None:
    fast, why = fl.classify(paths)
    assert fast, why


@pytest.mark.parametrize(
    ("path", "word"),
    [
        ("desks/mt5/mt5desk/gateway.py", "money path"),  # the gateway
        ("desks/mt5/prop/e8_executor.py", "money path"),  # a prop executor
        ("libs/portfolio/zz_new.py", "money path"),  # MONEY_PATH folder, even a new file
        ("libs/risk/zz_new.py", "money path"),
        ("libs/execution/zz_new.py", "money path"),
        ("desks/mt5/data/sleeves.json", "protected"),  # what the gateway trades
        ("data/zz.json", "money path"),
        ("desks/mt5/scripts/zz_report.ps1", "box machinery"),  # every shell script
        ("desks/mt5/scripts/zz_report.py", "money path"),
        ("desks/mt5/research/promoter.py", "protected"),  # writes the LIVE rows
        ("desks/mt5/research/pf_allocator.py", "protected"),
        ("ops/release/replay_shadow.py", "protected"),  # replay-shadow itself
        (".github/workflows/ci.yml", "protected"),  # the checks
        (".github/scripts/fast_lane.py", "protected"),  # this lane cannot widen itself
        ("ops/box/workflow_gate.ps1", "protected"),  # the box
        ("desks/mt5/scripts/Adopt-And-Seal.ps1", "protected"),  # adoption
        ("libs/ops/release.py", "protected"),  # the seal
        ("pyproject.toml", "protected"),  # test configuration
        ("CLAUDE.md", "protected"),
        ("data/secrets/x.json", "protected"),
        ("desks/mt5/tests/test_sizing.py", "risk suite"),  # a risk suite
        ("tests/ops/test_audit_gate.py", "risk suite"),  # a release suite
    ],
)
def test_money_release_box_and_check_paths_are_never_fast(path: str, word: str) -> None:
    fast, why = fl.classify(["docs/fine.md", path])
    assert not fast and word in why, why


def test_the_closure_of_the_live_entry_points_is_money() -> None:
    rs = _load("rs_fast_t", "ops/release/replay_shadow.py")
    closure = rs.import_closure(ROOT, rs.ENTRY_POINTS)
    outside = sorted(f for f in closure if not f.startswith(rs.MONEY_PATH))
    assert outside, "the entry points import nothing outside the MONEY_PATH folders"
    fast, why = fl.classify([outside[0]])
    assert not fast and "money path" in why, why


def test_an_existing_test_of_money_code_is_money_and_a_new_one_is_not() -> None:
    rs = _load("rs_fast_t2", "ops/release/replay_shadow.py")
    closure = rs.import_closure(ROOT, (*rs.ENTRY_POINTS, *fl.EXTRA_ENTRIES))
    # imports mt5desk (the MONEY_PATH folder) and is in no suite list
    money_test = "desks/mt5/tests/test_account_key_stamp.py"
    assert fl.money_test(rs, money_test, closure)
    fast, why = fl.classify([money_test])
    assert not fast and "tests the money path" in why, why
    assert not fl.money_test(rs, "desks/mt5/tests/test_zz_not_yet_written.py", closure)


def test_a_module_the_executors_import_by_bare_name_is_money() -> None:
    """#1240 audit MF1: prop/ftmo_executor and e8_executor run `from admission_integrity import`
    through research/ on sys.path, and neither is an entry point."""
    fast, why = fl.classify(["desks/mt5/research/admission_integrity.py"])
    assert not fast and "money path" in why, why


@pytest.mark.parametrize(
    "path",
    [
        "ops/box_self_heal.py",  # a SYSTEM task that kills processes
        "ops/ensure_terminal.ps1",  # restarts the live terminal
        "ops/install_unattended.ps1",
        "requirements-vps.txt",  # the box's install sets
        "requirements-deploy.txt",
        "scripts/zz_anything.sh",  # any shell script, anywhere
        "scripts/zz_anything.cmd",
    ],
)
def test_box_machinery_is_never_fast(path: str) -> None:
    """#1240 audit MF2."""
    fast, why = fl.classify([path])
    assert not fast and "box machinery" in why, why


def test_a_registered_producer_of_a_file_the_money_path_reads_is_money() -> None:
    """#1240 audit MF3: alpha_breadth declares pf_allocation.json, which the allocator reads."""
    fast, why = fl.classify(["desks/mt5/research/alpha_breadth.py"])
    assert not fast and "component registry" in why, why


PRODUCER = (
    "import json\nfrom pathlib import Path\n"
    "OUT = Path('desks/mt5/reports/pf_allocation.json')\n"
    "def run():\n    OUT.write_text(json.dumps({'all': 1}))\n"
)


def test_a_new_file_that_writes_what_the_money_path_reads_is_money(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#1240 audit MF3, the unregistered case: the PR's own copy is read, not only the base's."""
    new = "desks/mt5/research/zz_new_producer.py"
    monkeypatch.setattr(fl, "head_text", lambda head, path: PRODUCER if path == new else None)
    fast, why = fl.classify([new], head="HEAD")
    assert not fast and "newly writes pf_allocation.json" in why, why
    monkeypatch.setattr(fl, "head_text", lambda head, path: "X = 1\n" if path == new else None)
    assert fl.classify([new], head="HEAD")[0]


def test_a_producer_is_caught_once_the_money_path_reads_its_file() -> None:
    """#1240 audit MF3, pinned for the exotic cost bar (#1117): once live_policy reads
    EXOTIC_COST_BAR.json, the file that writes it is money."""
    src = (
        "import json\nfrom pathlib import Path\nBAR = 'EXOTIC_COST_BAR.json'\n"
        "def publish(root):\n    (Path(root) / 'reports' / BAR).write_text(json.dumps({}))\n"
    )
    assert fl.money_writes(src, "x.py", {"exotic_cost_bar.json"}) == {"exotic_cost_bar.json"}
    assert fl.money_writes(src, "x.py", {"sleeves.json"}) == set()
    reader = "import json\ndef read():\n    return json.load(open('EXOTIC_COST_BAR.json'))\n"
    assert fl.money_writes(reader, "x.py", {"exotic_cost_bar.json"}) == set()  # a reader only


def test_nothing_or_an_unreadable_base_is_not_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    assert not fl.classify([])[0]
    assert not fl.classify(["", "  "])[0]
    monkeypatch.setattr(fl, "ROOT", ROOT / "no-such-dir")  # a new cache key: read afresh
    fast, why = fl.classify(["docs/x.md"])
    assert not fast and "could not read" in why


# ------------------------------------------------------------------- what the gate does


class Hub:
    """The GitHub reads and writes run_fast makes."""

    def __init__(self, *, smoke: str = "success", verdicts: list[str] | None = None,
                 activated: bool = True) -> None:  # fmt: skip
        self.smoke = smoke
        self.comments = [{"body": b, "created_at": "2026-11-17T10:00:00Z",
                          "author_association": "MEMBER", "user": {"login": "a"}}
                         for b in verdicts or []]  # fmt: skip
        board = []
        if activated:
            board.append({"body": ag.ACTIVATE, "author_association": "OWNER",
                          "created_at": "2026-10-29T13:52:14Z", "updated_at": None,
                          "performed_via_github_app": None})  # fmt: skip
        self.board = board
        self.writes: list[tuple[str, Any]] = []

    def __call__(self, path: str, *args: str, data: Any = None, timeout: Any = None) -> Any:
        if "-X" in args:
            self.writes.append((path, data))
            return {}
        if path.startswith("repos/o/r/issues/453/comments"):
            return [self.board]
        if path.startswith("repos/o/r/issues/7/comments"):
            return [self.comments]
        if "/check-runs" in path:
            run = {"name": "smoke", "status": "completed", "conclusion": self.smoke,
                   "started_at": "2026-11-17T11:00:00Z", "app": {"slug": "github-actions"},
                   "check_suite": {"id": 1}, "id": 1}  # fmt: skip
            return [{"check_runs": [run]}]
        if path == "repos/o/r/pulls/7":
            return {"head": {"sha": "a" * 40}}
        raise AssertionError(path)


HEAD = "a" * 40


def _run(monkeypatch: pytest.MonkeyPatch, hub: Hub, *, draft: bool = False) -> int:
    monkeypatch.setattr(ag, "_gh", hub)
    monkeypatch.setattr(ag, "_status", lambda *a: None)
    monkeypatch.setattr(ag, "provenance", lambda *a: lambda r: True)
    p = {"draft": draft, "head": {"sha": HEAD}}
    return int(ag.run_fast("o/r", 7, p, HEAD, ag.LIVE, "why", box=False, approvals_issue=453))


def _merged(hub: Hub) -> bool:
    return any(path.endswith("/pulls/7/merge") for path, _ in hub.writes)


def test_a_green_smoke_merges_with_no_clear_and_no_approval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hub = Hub()
    assert _run(monkeypatch, hub) == 0
    merge = next(d for path, d in hub.writes if path.endswith("/pulls/7/merge"))
    assert merge["sha"] == HEAD and merge["commit_title"].startswith("Merge #7 (FAST lane,")
    assert ag.is_registry_merge(merge["commit_title"])  # a red LIVE after it is auto-reverted
    assert any(path.endswith("ci.yml/dispatches") for path, _ in hub.writes)


def test_a_red_smoke_never_merges(monkeypatch: pytest.MonkeyPatch) -> None:
    hub = Hub(smoke="failure")
    assert _run(monkeypatch, hub) == 1 and not _merged(hub)


def test_a_running_smoke_waits(monkeypatch: pytest.MonkeyPatch) -> None:
    hub = Hub()
    monkeypatch.setattr(ag, "checks", lambda *a, **k: ("pending", "smoke running"))
    assert _run(monkeypatch, hub) == 0 and not _merged(hub)


def test_a_hold_still_stops_a_fast_pr(monkeypatch: pytest.MonkeyPatch) -> None:
    hub = Hub(verdicts=[f"AUDIT HOLD {HEAD}"])
    assert _run(monkeypatch, hub) == 0 and not _merged(hub)


def test_a_draft_waits_until_it_is_marked_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    hub = Hub()
    assert _run(monkeypatch, hub, draft=True) == 0 and not _merged(hub)


def test_deactivate_switches_the_fast_lane_off(monkeypatch: pytest.MonkeyPatch) -> None:
    hub = Hub(activated=False)
    assert _run(monkeypatch, hub) == 0 and not _merged(hub)


def test_the_lane_is_off_unless_the_workflow_turns_it_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ag.FAST_ENV, raising=False)
    assert ag.is_fast(["docs/x.md"]) == (False, "fast lane off")
    monkeypatch.setenv(ag.FAST_ENV, "1")
    assert ag.is_fast(["docs/x.md"])[0]
    assert not ag.is_fast(["desks/mt5/mt5desk/gateway.py"])[0]
    assert not ag.is_fast([])[0]


def test_the_smoke_job_must_come_from_ci_yml() -> None:
    assert ag.WORKFLOW_OF[ag.FAST_JOB] == ".github/workflows/ci.yml"


# ----------------------------------------------------------------------- the wiring


def _jobs(name: str) -> dict[str, Any]:
    doc = yaml.safe_load((WF / name).read_text("utf-8"))
    return dict(doc["jobs"])


@pytest.mark.parametrize(
    ("wf", "job", "flag"),
    [
        ("ci.yml", "quality", "needs.lane.outputs.fast"),
        ("ci.yml", "mt5-money-path", "needs.lane.outputs.fast"),
        ("ci.yml", "coverage-floor", "needs.quality.outputs.fast"),
        ("release-gates.yml", "risk-invariants", "needs.lane.outputs.fast"),
        ("release-gates.yml", "replay-shadow", "needs.lane.outputs.fast"),
        ("release-gates.yml", "independent-review", "needs.lane.outputs.fast"),
    ],
)
def test_every_heavy_step_skips_on_a_fast_pr_and_the_job_says_so(
    wf: str, job: str, flag: str
) -> None:
    j = _jobs(wf)[job]
    assert f"'{job} (fast lane: not run)'" in j["name"] and f"|| '{job}'" in j["name"]
    for step in j["steps"]:
        assert f"{flag} != 'true'" in str(step.get("if") or ""), (job, step)


def test_trusted_eval_skips_only_a_fast_pr() -> None:
    j = _jobs("trusted-eval.yml")["trusted-eval"]
    assert j["needs"] == ["lane"] and "needs.lane.outputs.fast != 'true'" in j["if"]


@pytest.mark.parametrize("wf", ["ci.yml", "release-gates.yml", "trusted-eval.yml"])
def test_the_lane_runs_the_base_s_classifier_on_the_base(wf: str) -> None:
    lane = _jobs(wf)["lane"]
    checkout = lane["steps"][0]
    assert checkout["with"]["ref"] == "${{ github.event.pull_request.base.sha }}"
    run = lane["steps"][-1]["run"]
    assert "python -I .github/scripts/fast_lane.py" in run and 'no "$EVENT run"' in run


def test_smoke_runs_on_fast_prs_only_and_audit_gate_turns_the_lane_on() -> None:
    smoke = _jobs("ci.yml")["smoke"]
    assert smoke["if"] == "needs.lane.outputs.fast == 'true'"
    run = "\n".join(str(s.get("run") or "") for s in smoke["steps"])
    assert "pytest --co" in run and "ruff check" in run
    text = (WF / "audit-gate.yml").read_text("utf-8")
    assert text.count('QUANT_FAST_LANE: "1"') == 2
