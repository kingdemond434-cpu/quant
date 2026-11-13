"""Open-PR backlog replayed through the release authority: dry run, no free text published."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import authority_replay as ar  # noqa: E402

SECRET = "SECRETHOST rdp-zuck@62.171.172.249"


def base_facts(**kw: Any) -> dict[str, Any]:
    f = {"open": True, "same_repo": True, "base_ok": True, "cls": "AUTO", "tier": "AUTO",
         "head": "a" * 40, "files": ["scripts/x.py"]}  # fmt: skip
    f.update(kw)
    return f


@pytest.mark.parametrize(
    ("facts", "verdict", "reasons", "want"),
    [
        (base_facts(), "CLEAR", [], "READY"),
        (base_facts(cls="ROOT"), "HOLD", ["ROOT: root file x"], "ROOT"),
        (base_facts(cls="REFUSED"), "HOLD", [], "REFUSED"),
        (base_facts(hold="AUDIT HOLD abc"), "HOLD", [], "AUDIT_HOLD"),
        (base_facts(deactivated=True), "WAIT", [], "DEACTIVATED"),
        (base_facts(), "FAIL", ["a required check failed: quality"], "CHECK_FAILED"),
        (base_facts(), "WAIT", ["independent-review queued: no free reviewer"], "REVIEW_QUEUED"),
        (base_facts(), "WAIT", ["not up to date: behind"], "BEHIND"),
        (base_facts(), "WAIT", ["checks not finished: x"], "CHECKS_PENDING"),
        (base_facts(open=False), "WAIT", [], "NOT_ELIGIBLE"),
    ],
)
def test_every_verdict_names_one_blocker_and_who_acts(
    facts: dict[str, Any], verdict: str, reasons: list[str], want: str
) -> None:
    assert ar.blocker(facts, verdict, reasons) == want
    assert want in ar.NEXT


class FakeGate:
    def __init__(self, prs: list[dict[str, Any]]) -> None:
        self.prs = prs

    def _gh(self, path: str) -> Any:
        assert "pulls?state=open" in path, path  # the replay itself reads only the open list
        return self.prs


def fake_authority(prs: list[dict[str, Any]], facts_by_pr: dict[int, Any]) -> Any:
    def facts(ag: Any, repo: str, pr: int, base: str, policy: Any, enforced: bool = False):
        got = facts_by_pr[pr]
        if isinstance(got, Exception):
            raise got
        return got

    def decide(f: dict[str, Any]) -> tuple[str, list[str]]:
        return f["_verdict"], [f"reason naming {SECRET}"]

    def classify(names, tier, policy, rb, rh, enforced=False):
        return ("CONTROLLER" if enforced else "ROOT"), []

    def forbidden(*a: Any, **k: Any) -> None:
        raise AssertionError("the replay must never sign, write or post")

    return SimpleNamespace(
        gate=lambda: FakeGate(prs),
        facts=facts,
        pol=SimpleNamespace(decide=decide, classify=classify, load_policy=lambda: {}),
        _git_bytes=lambda *a: b"",
        issue=forbidden,
        write=forbidden,
        post_status=forbidden,
    )


def pr(n: int, head: str) -> dict[str, Any]:
    return {"number": n, "title": f"title {SECRET}", "head": {"sha": head}}


def test_a_pass_judges_through_the_authority_signs_nothing_and_publishes_no_text() -> None:
    prs = [pr(1, "a" * 40), pr(2, "b" * 40), pr(3, "c" * 40)]
    facts = {
        1: base_facts(_verdict="CLEAR", head="a" * 40),
        2: base_facts(_verdict="HOLD", cls="ROOT", head="b" * 40),
        3: RuntimeError(f"gh api ...: {SECRET} (HTTP 502)"),
    }
    full = ar.run("o/r", "LIVE", None, 10, 60.0, auth=fake_authority(prs, facts))
    rows = {r["pr"]: r for r in full["local_rows"]}
    assert rows[1]["blocker"] == "READY" and rows[2]["blocker"] == "ROOT"
    assert rows[2]["class_if_level2"] == "CONTROLLER"
    assert rows[3]["verdict"] == "UNREADABLE" and rows[3]["error"] == {
        "type": "RuntimeError", "http": 502,
    }  # fmt: skip
    s = full["summary"]
    assert s["ready_now"] == [1] and s["need_zuck_root"] == [2]
    assert s["root_only_until_level2"] == [2]
    published = {**{k: v for k, v in full.items() if k != "local_rows"},
                 "prs": [ar.publishable(r) for r in full["local_rows"]]}  # fmt: skip
    text = json.dumps(published)
    assert "SECRETHOST" not in text and "62.171" not in text and "title" not in text
    for r in published["prs"]:
        assert tuple(r) == ar.ROW_KEYS


def test_new_or_moved_heads_go_first_and_closed_prs_drop() -> None:
    prev = {"prs": [
        {"pr": 1, "head": "a" * 40, "verdict": "WAIT", "judged_at": "2026-11-13T01:00:00+00:00"},
        {"pr": 2, "head": "old", "verdict": "WAIT", "judged_at": "2026-11-13T02:00:00+00:00"},
        {"pr": 9, "head": "z", "verdict": "WAIT", "judged_at": "2026-11-13T00:00:00+00:00"},
    ]}  # fmt: skip
    prs = [pr(1, "a" * 40), pr(2, "b" * 40), pr(3, "c" * 40)]
    assert ar.order(prs, {int(r["pr"]): r for r in prev["prs"]}) == [2, 3, 1]
    facts = {n: base_facts(_verdict="WAIT") for n in (1, 2, 3)}
    full = ar.run("o/r", "LIVE", prev, 2, 60.0, auth=fake_authority(prs, facts))
    assert full["judged_this_pass"] == 2
    assert sorted(r["pr"] for r in full["local_rows"]) == [1, 2, 3]  # 9 closed: dropped
    assert {r["pr"]: r["judged_at"] for r in full["local_rows"]}[1].startswith("2026-11-13T01")


def test_full_rows_live_only_where_git_ignores_them() -> None:
    assert ar.LOCAL.relative_to(ROOT).parts[0] == "data"
    got = subprocess.run(["git", "check-ignore", "-q", str(ar.LOCAL)], cwd=ROOT, check=False)
    assert got.returncode == 0


def test_the_replay_never_calls_a_writer_of_the_authority() -> None:
    code = (ROOT / "scripts" / "authority_replay.py").read_text(encoding="utf-8")
    for call in (".issue(", ".write(", ".post_status(", "attestation", "check_state_app("):
        assert call not in code.split('"""', 2)[2], call
    assert ".facts(" in code and ".pol.decide(" in code


def test_the_merge_watch_runs_the_replay_and_never_fails_on_it(monkeypatch: Any) -> None:
    import merge_pipeline_watch as mpw

    def boom(argv: list[str]) -> int:
        raise RuntimeError(SECRET)

    seen: list[list[str]] = []
    monkeypatch.setattr(ar, "main", boom)
    mpw._authority_replay("o/r", "b", Path("x"))  # must not raise
    monkeypatch.setattr(ar, "main", lambda argv: seen.append(argv) or 0)
    mpw._authority_replay("o/r", "b", Path("reports"))
    assert seen[0][seen[0].index("--out") + 1] == str(Path("reports") / "AUTHORITY_REPLAY.json")
    code = (ROOT / "scripts" / "merge_pipeline_watch.py").read_text(encoding="utf-8")
    assert "_authority_replay(a.repo, a.base, a.out.parent)" in code
