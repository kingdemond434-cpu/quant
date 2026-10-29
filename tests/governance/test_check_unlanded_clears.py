"""THE UNLANDED-CLEAR FENCE NAMES A LATE CLEAR, SEES A CHERRY-PICK AS LANDED, AND NEVER GUESSES."""

from __future__ import annotations

import importlib.util
import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

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
    doc = fence.judge(repo=repo["root"], registry=reg, live=LIVE, now=NOW)
    states = {i["id"]: i["state"] for i in doc["items"]}
    assert states == {"anc": "LANDED", "pick": "LANDED_BY_PATCH_ID", "late": "LATE",
                      "fresh": "PENDING", "gone": "LATE"}
    assert doc["verdict"] == "RED"
    assert doc["late"] == ["late", "gone"]
    assert "UNMEASURED" in next(i["how"] for i in doc["items"] if i["id"] == "gone")


def test_nothing_late_is_green(repo: dict[str, object], tmp_path: Path) -> None:
    reg = _registry(tmp_path, [_row("anc", repo["merged"], 100),
                               _row("fresh", repo["unlanded"], 2)])
    assert fence.judge(repo=repo["root"], registry=reg, live=LIVE, now=NOW)["verdict"] == "GREEN"


def test_missing_live_ref_is_unmeasured(repo: dict[str, object], tmp_path: Path) -> None:
    reg = _registry(tmp_path, [_row("late", repo["unlanded"], 100)])
    doc = fence.judge(repo=repo["root"], registry=reg, live="refs/heads/nope", now=NOW)
    assert doc["verdict"] == "UNMEASURED" and "not in this clone" in doc["why"]


@pytest.mark.parametrize("bad", [
    {"sha": "abc"}, {"kind": "tag"}, {"cleared_at": "2026-10-14"}, {"report": ""},
    {"path": ""},
])
def test_malformed_row_is_a_breach(repo: dict[str, object], tmp_path: Path,
                                   bad: dict[str, object]) -> None:
    reg = _registry(tmp_path, [{**_row("x", repo["merged"], 1), **bad}])
    assert fence.judge(repo=repo["root"], registry=reg, live=LIVE, now=NOW)["verdict"] == "BREACH"


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
