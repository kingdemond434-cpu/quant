"""THE UNLANDED-CLEAR FENCE NAMES A LATE CLEAR, SEES A CHERRY-PICK AS LANDED, AND NEVER GUESSES."""

from __future__ import annotations

import importlib.util
import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "check_unlanded_clears", ROOT / "scripts" / "check_unlanded_clears.py"
)
assert SPEC and SPEC.loader
fence = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fence)

NOW = datetime(2026, 10, 29, 12, 0, tzinfo=UTC)
LIVE = "refs/heads/live"


def _no_comments(path: str) -> list[object]:
    return []


def _judge(**kw: Any) -> Any:
    """judge() with coverage pointed at nothing real: no network, no share."""
    kw.setdefault("gh", _no_comments)
    kw.setdefault("roots", ())
    kw.setdefault("baseline", Path("/nonexistent/baseline.json"))
    return fence.judge(now=NOW, **kw)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True,
                          text=True).stdout.strip()


def _commit(repo: Path, name: str, text: str) -> str:
    (repo / name).write_text(text, "utf-8")
    _git(repo, "add", name)
    _git(repo, "commit", "-q", "-m", name)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture()
def repo(tmp_path: Path) -> dict[str, object]:
    r = tmp_path / "r"
    r.mkdir()
    _git(r, "init", "-q", "-b", "live")
    _git(r, "config", "user.email", "t@t")
    _git(r, "config", "user.name", "t")
    _commit(r, "base.txt", "base\n")
    _git(r, "checkout", "-q", "-b", "side")
    picked = _commit(r, "picked.txt", "picked\n")
    _git(r, "checkout", "-q", "-b", "other", "live")
    unlanded = _commit(r, "unlanded.txt", "unlanded\n")
    _git(r, "checkout", "-q", "live")
    merged = _commit(r, "merged.txt", "merged\n")
    _git(r, "cherry-pick", picked)          # same patch, new sha
    return {"root": r, "merged": merged, "picked": picked, "unlanded": unlanded}


def _registry(tmp: Path, rows: list[dict[str, object]]) -> Path:
    p = tmp / "reg.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in rows), "utf-8")
    return p


def _row(rid: str, sha: object, hours_ago: float) -> dict[str, object]:
    return {"id": rid, "sha": sha, "kind": "bundle", "path": f"patches/{rid}.bundle",
            "cleared_at": (NOW - timedelta(hours=hours_ago)).isoformat(),
            "report": f"reports/audit/{rid}.md"}


def test_late_unlanded_is_red_and_landed_forms_are_not(repo: dict[str, object],
                                                       tmp_path: Path) -> None:
    reg = _registry(tmp_path, [_row("anc", repo["merged"], 100),
                               _row("pick", repo["picked"], 100),
                               _row("late", repo["unlanded"], 13),
                               _row("fresh", repo["unlanded"], 11),
                               _row("gone", "f" * 40, 50)])
    doc = _judge(repo=repo["root"], registry=reg, live=LIVE)
    states = {i["id"]: i["state"] for i in doc["items"]}
    assert states == {"anc": "LANDED", "pick": "LANDED_BY_PATCH_ID", "late": "LATE",
                      "fresh": "PENDING", "gone": "LATE"}
    assert doc["verdict"] == "RED"
    assert doc["late"] == ["late", "gone"]
    assert "UNMEASURED" in next(i["how"] for i in doc["items"] if i["id"] == "gone")


def test_nothing_late_is_green(repo: dict[str, object], tmp_path: Path) -> None:
    reg = _registry(tmp_path, [_row("anc", repo["merged"], 100),
                               _row("fresh", repo["unlanded"], 2)])
    assert _judge(repo=repo["root"], registry=reg, live=LIVE)["verdict"] == "GREEN"


def test_missing_live_ref_is_unmeasured(repo: dict[str, object], tmp_path: Path) -> None:
    reg = _registry(tmp_path, [_row("late", repo["unlanded"], 100)])
    doc = _judge(repo=repo["root"], registry=reg, live="refs/heads/nope")
    assert doc["verdict"] == "UNMEASURED" and "not in this clone" in doc["why"]


@pytest.mark.parametrize("bad", [
    {"sha": "abc"}, {"kind": "tag"}, {"cleared_at": "2026-10-14"}, {"report": ""},
    {"path": ""},
])
def test_malformed_row_is_a_breach(repo: dict[str, object], tmp_path: Path,
                                   bad: dict[str, object]) -> None:
    reg = _registry(tmp_path, [{**_row("x", repo["merged"], 1), **bad}])
    assert _judge(repo=repo["root"], registry=reg, live=LIVE)["verdict"] == "BREACH"


def test_exit_map_report_only_passes_red_never_breach(monkeypatch: pytest.MonkeyPatch) -> None:
    for verdict, plain, report_only in (("GREEN", 0, 0), ("UNMEASURED", 0, 0),
                                        ("RED", 1, 0), ("BREACH", 1, 1)):
        monkeypatch.setattr(fence, "judge", lambda verdict=verdict, **_: {"verdict": verdict,
                                                                           "why": "t"})
        assert fence.main([]) == plain, verdict
        assert fence.main(["--report-only"]) == report_only, verdict


def test_the_committed_registry_parses() -> None:
    rows, bad = fence.read_registry(fence.REGISTRY)
    assert not bad and rows


# --------------------------------------------------------------------------- S1, S2, MF2
def test_retired_row_is_never_late_and_names_its_successor(repo: dict[str, object],
                                                           tmp_path: Path) -> None:
    old = {**_row("old", repo["unlanded"], 100),
           "retired": {"reason": "re-cleared at a later head", "superseded_by": "new"}}
    reg = _registry(tmp_path, [old, _row("new", repo["merged"], 1)])
    doc = _judge(repo=repo["root"], registry=reg, live=LIVE)
    item = next(i for i in doc["items"] if i["id"] == "old")
    assert item["state"] == "RETIRED" and "superseded by new" in item["how"]
    assert doc["verdict"] == "GREEN"


@pytest.mark.parametrize("ret", [{"reason": ""}, "withdrawn", {"reason": "x",
                                                               "superseded_by": "ghost"}])
def test_retired_without_reason_or_with_unknown_successor_is_a_breach(
        repo: dict[str, object], tmp_path: Path, ret: object) -> None:
    reg = _registry(tmp_path, [{**_row("x", repo["merged"], 1), "retired": ret}])
    assert _judge(repo=repo["root"], registry=reg, live=LIVE)["verdict"] == "BREACH"


def test_report_says_as_of_fetch(repo: dict[str, object], tmp_path: Path) -> None:
    reg = _registry(tmp_path, [_row("anc", repo["merged"], 1)])
    doc = _judge(repo=repo["root"], registry=reg, live=LIVE)
    assert doc["live_fetched_at"]
    assert fence.render(doc)[1].startswith("  as of fetch at ")


def _gh_with(comments: list[dict[str, object]], pulls: list[dict[str, object]]) -> Any:
    def gh(path: str) -> list[dict[str, object]]:
        page = int(path.rsplit("page=", 1)[-1])
        if page > 1:
            return []
        return pulls if "/pulls" in path else comments
    return gh


def _comment(num: int, body: str) -> dict[str, object]:
    return {"issue_url": f"https://api.github.com/repos/o/r/issues/{num}", "body": body,
            "created_at": "2026-10-29T10:00:00Z", "html_url": f"u/{num}"}


def test_pr_comment_clear_without_a_row_is_red(repo: dict[str, object], tmp_path: Path) -> None:
    sha = str(repo["merged"])
    other = "a" * 40
    gh = _gh_with([_comment(1, f"AUDIT CLEAR {sha}"), _comment(2, f"AUDIT CLEAR {other}"),
                   _comment(3, f"AUDIT CLEAR {'b' * 40}"),
                   _comment(4, f"see AUDIT CLEAR {'c' * 40}")],
                  [{"number": 1, "state": "closed", "merged_at": "x"},
                   {"number": 2, "state": "open"},
                   {"number": 3, "state": "closed", "merged_at": None},   # closed unmerged
                   {"number": 4, "state": "open"}])                      # not at line start
    reg = _registry(tmp_path, [_row("anc", sha, 1)])
    doc = _judge(repo=repo["root"], registry=reg, live=LIVE, gh=gh)
    assert doc["verdict"] == "RED"
    assert doc["coverage"]["missing"] == [
        f"PR #2 comment AUDIT CLEAR {other[:9]} (2026-10-29T10:00:00Z) has no registry row"]
    assert doc["coverage"]["n_pr_comment_clears"] == 2


def test_gh_failure_is_unmeasured_never_green(repo: dict[str, object], tmp_path: Path) -> None:
    def broken(path: str) -> object:
        raise RuntimeError("gh CLI not on PATH")
    reg = _registry(tmp_path, [_row("anc", repo["merged"], 1)])
    doc = _judge(repo=repo["root"], registry=reg, live=LIVE, gh=broken)
    assert doc["verdict"] == "UNMEASURED" and "gh CLI not on PATH" in doc["why"]


def test_clear_files_need_a_row_or_an_unchanged_baseline(repo: dict[str, object],
                                                         tmp_path: Path) -> None:
    share = tmp_path / "share"
    (share / "d").mkdir(parents=True)
    (share / "d" / "cited.md").write_text("## X: CLEAR\n", "utf-8")
    (share / "d" / "old.md").write_text("VERDICT: CLEAR\n", "utf-8")
    (share / "d" / "new.md").write_text("**CLEAR**\n", "utf-8")
    (share / "d" / "hold.md").write_text("HOLD. NOT CLEAR. UNCLEAR. MUST-FIX (before CLEAR)\n",
                                         "utf-8")
    roots = (("share", share, False), ("repo", tmp_path / "absent", True))
    files, _ = fence.clear_files(roots)
    old = next(f for f in files if f["key"].endswith("old.md"))
    base = tmp_path / "base.json"
    base.write_text(json.dumps({"files": [{"where": "share", "key": old["key"],
                                           "sha256": old["sha256"]}]}), "utf-8")
    reg = _registry(tmp_path, [{**_row("c", repo["merged"], 1),
                                "report": "reports/audit/d/cited.md"}])
    doc = _judge(repo=repo["root"], registry=reg, live=LIVE, roots=roots, baseline=base)
    assert doc["coverage"]["missing"] == [
        "share:reports/audit/d/new.md carries a CLEAR and no row cites it"]
    assert doc["coverage"]["n_baselined"] == 1 and doc["verdict"] == "RED"
    (share / "d" / "old.md").write_text("VERDICT: CLEAR\n## Delta: CLEAR\n", "utf-8")
    (share / "d" / "new.md").unlink()
    doc = _judge(repo=repo["root"], registry=reg, live=LIVE, roots=roots, baseline=base)
    assert doc["coverage"]["missing"] == [
        "share:reports/audit/d/old.md carries a CLEAR and changed since the baseline"]


def test_absent_share_is_unmeasured(repo: dict[str, object], tmp_path: Path) -> None:
    reg = _registry(tmp_path, [_row("anc", repo["merged"], 1)])
    doc = _judge(repo=repo["root"], registry=reg, live=LIVE,
                 roots=(("share", tmp_path / "nope", False),))
    assert doc["verdict"] == "UNMEASURED" and "share: audit root absent here" in doc["why"]


def test_committed_baseline_parses_and_is_disjoint_from_cited_reports() -> None:
    rows, _ = fence.read_registry(fence.REGISTRY)
    doc = json.loads(fence.BASELINE.read_text("utf-8"))
    keys = {f["key"] for f in doc["files"]}
    assert keys and not keys & {r["report"] for r in rows}
    assert all(len(f["sha256"]) == 64 for f in doc["files"])


def test_desk_health_turns_red_into_a_problem_and_writes_the_report(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    spec = importlib.util.spec_from_file_location(
        "check_desk_health", ROOT / "desks" / "mt5" / "scripts" / "check_desk_health.py")
    assert spec and spec.loader
    dh = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dh)
    red = {"verdict": "RED", "why": "1 CLEAR item(s) unlanded", "live_fetched_at": "T",
           "items": [{"id": "x", "sha": "abc", "age_h": 20, "state": "LATE", "how": "h"}],
           "coverage": {"missing": []}}
    assert dh._unlanded_judge().__name__ == "judge"      # the real loader resolves
    monkeypatch.setattr(dh, "_unlanded_judge", lambda: lambda: red)
    dh._FINDINGS.clear()
    out = tmp_path / "UNLANDED_CLEARS.json"
    dh.check_unlanded_clears(out)
    assert [f["level"] for f in dh._FINDINGS] == ["PROBLEM"]
    assert "as of fetch at T" in dh._FINDINGS[0]["message"]
    assert json.loads(out.read_text("utf-8"))["verdict"] == "RED"
    for verdict, level in (("GREEN", "OK"), ("UNMEASURED", "UNKNOWN"), ("BREACH", "PROBLEM")):
        doc = {**red, "verdict": verdict}
        monkeypatch.setattr(dh, "_unlanded_judge", lambda doc=doc: lambda: doc)
        dh._FINDINGS.clear()
        dh.check_unlanded_clears(None)
        assert dh._FINDINGS[0]["level"] == level, verdict


def test_unlanded_clears_report_is_not_ignored() -> None:
    # The sync list and the two NON_CODE lists (PROTECTED files) carry it in the separate
    # publish PR, claude/unlanded-clears-publish; until then it stays on the box (README).
    rel = "desks/mt5/reports/UNLANDED_CLEARS.json"
    assert f"!{rel}" in (ROOT / ".gitignore").read_text("utf-8")
