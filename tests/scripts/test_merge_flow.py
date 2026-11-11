"""scripts/merge_flow.py: the release train's SLO (Hourly pass idea 587)."""

from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("merge_flow", ROOT / "scripts/merge_flow.py")
mf = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(mf)

NOW = datetime(2026, 11, 11, 3, 0, tzinfo=UTC)
OK = (True, "gh api user: ok")


def _iso(h_ago: float) -> str:
    return (NOW - timedelta(hours=h_ago)).isoformat()


def _pr(n: int, sha: str, draft: bool = False) -> dict[str, Any]:
    return {"number": n, "head": {"sha": sha}, "draft": draft}


def _row(n: int, sha: str, h_ago: float, verdict: str = "CLEAR") -> dict[str, Any]:
    return {"pr": n, "sha": sha, "verdict": verdict, "at": _iso(h_ago)}


def _st(min_ago: float, desc: str = "waiting on: tests") -> dict[str, Any]:
    t = (NOW - timedelta(minutes=min_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"context": "audit/clear", "state": "pending", "description": desc, "updated_at": t}


def test_newest_rows_last_wins_and_skips_junk() -> None:
    lines = [json.dumps(_row(1, "a", 5, "HOLD")), "not json", json.dumps({"pr": "x"}),
             json.dumps(_row(1, "b", 1)), json.dumps(_row(2, "c", 2))]  # fmt: skip
    got = mf.newest_rows(lines)
    assert set(got) == {1, 2} and got[1]["sha"] == "b" and got[1]["verdict"] == "CLEAR"


def test_last_merge_needs_merge_title_and_two_parents() -> None:
    commits = [
        {"sha": "x1", "parents": [{}], "commit": {"message": "Merge #5 lookalike",
         "committer": {"date": "2026-11-11T02:00:00Z"}}},
        {"sha": "x2", "parents": [{}, {}], "commit": {"message": "Merge branch 'live'",
         "committer": {"date": "2026-11-11T01:30:00Z"}}},
        {"sha": "m1", "parents": [{}, {}], "commit": {"message": "Merge #900: thing",
         "committer": {"date": "2026-11-11T01:00:00Z"}}},
    ]  # fmt: skip
    sha, at = mf.last_merge(commits)
    assert sha == "m1" and at == datetime(2026, 11, 11, 1, 0, tzinfo=UTC)
    assert mf.last_merge([]) is None


def test_green_when_merging_and_gate_alive() -> None:
    doc = mf.assess(NOW, [_pr(1, "a")], {1: _row(1, "a", 1)}, ("m", NOW - timedelta(hours=1)),
                    {1: _st(5)}, OK)  # fmt: skip
    assert doc["verdict"] == "GREEN" and doc["reasons"] == []
    assert doc["cleared_waiting"] == 1 and doc["in_veto_window"] == 1


def test_clear_inside_veto_window_never_alarms() -> None:
    # 20 h since the CLEAR and no merge for 20 h: inside the 24 h veto window, which is design.
    doc = mf.assess(NOW, [_pr(1, "a")], {1: _row(1, "a", 20)}, ("m", NOW - timedelta(hours=20)),
                    {1: _st(5)}, OK)  # fmt: skip
    assert "MERGE_SLO" not in doc["reasons"] and doc["overdue"] == 0


def test_merge_slo_past_window_plus_slo() -> None:
    doc = mf.assess(NOW, [_pr(1, "a")], {1: _row(1, "a", 27)}, ("m", NOW - timedelta(hours=5)),
                    {1: _st(5)}, OK)  # fmt: skip
    assert doc["reasons"] == ["MERGE_SLO"] and doc["overdue"] == 1
    # ... but a recent merge means the train moves: no MERGE_SLO.
    doc = mf.assess(NOW, [_pr(1, "a")], {1: _row(1, "a", 27)}, ("m", NOW - timedelta(hours=1)),
                    {1: _st(5)}, OK)  # fmt: skip
    assert doc["verdict"] == "GREEN"


def test_clear_only_counts_for_current_head_and_clear_verdict() -> None:
    prs = [_pr(1, "new"), _pr(2, "b"), _pr(3, "c")]
    rows = {1: _row(1, "old", 30), 2: _row(2, "b", 30, "HOLD")}
    doc = mf.assess(NOW, prs, rows, None, {}, OK)
    assert doc["cleared_waiting"] == 0 and doc["verdict"] == "GREEN"


def test_gate_silent_when_no_recent_status() -> None:
    prs, rows = [_pr(1, "a"), _pr(2, "b")], {1: _row(1, "a", 3), 2: _row(2, "b", 3)}
    doc = mf.assess(NOW, prs, rows, None, {1: _st(70), 2: None}, OK)
    assert doc["reasons"] == ["GATE_SILENT"] and doc["gate_last_seen_min"] == 70.0
    assert doc["blockers"] == {"waiting on: tests": 1, "no gate status on this head": 1}
    doc = mf.assess(NOW, prs, rows, None, {1: None, 2: None}, OK)
    assert doc["reasons"] == ["GATE_SILENT"] and doc["gate_last_seen_min"] is None
    # nothing sampled (nothing to read) is not evidence of silence
    assert mf.assess(NOW, prs, rows, None, {}, OK)["verdict"] == "GREEN"


def test_box_login_is_its_own_reason() -> None:
    doc = mf.assess(NOW, [], {}, None, {}, (False, "gh api user: HTTP 401: Bad credentials"))
    assert doc["reasons"] == ["BOX_LOGIN"] and "401" in doc["box_login"]["detail"]


def test_heal_only_gate_silent_with_working_login_and_rate_limited() -> None:
    silent = {"reasons": ["GATE_SILENT"]}
    assert mf.heal_plan(silent, None, NOW) == "start_gate"
    assert mf.heal_plan(silent, NOW - timedelta(minutes=10), NOW) is None
    assert mf.heal_plan(silent, NOW - timedelta(minutes=56), NOW) == "start_gate"
    assert mf.heal_plan({"reasons": ["GATE_SILENT", "BOX_LOGIN"]}, None, NOW) is None
    assert mf.heal_plan({"reasons": ["MERGE_SLO"]}, None, NOW) is None


def _red(reasons: list[str]) -> dict[str, Any]:
    return {"verdict": "RED", "reasons": reasons, "merge_age_h": 30.0, "overdue": 2,
            "cleared_waiting": 5, "oldest_clear_waiting_h": 31.0, "gate_last_seen_min": None,
            "box_login": {"ok": False, "detail": "401"}, "blockers": {"x": 2},
            "last_merge": None}  # fmt: skip


def test_page_transitions() -> None:
    doc = _red(["GATE_SILENT"])
    title, body = mf.page(doc, {}, NOW)
    assert "GATE_SILENT" in title and "ever min" in body and "x x2" in body
    same = {"reasons": ["GATE_SILENT"], "paged_at": _iso(1)}
    assert mf.page(doc, same, NOW) is None
    assert mf.page(doc, {**same, "paged_at": _iso(3.1)}, NOW) is not None
    assert mf.page(_red(["GATE_SILENT", "BOX_LOGIN"]), same, NOW) is not None
    green = {"verdict": "GREEN", "reasons": [], "cleared_waiting": 0,
             "last_merge": {"sha": "abc"}}  # fmt: skip
    assert mf.page(green, same, NOW)[0] == "Merges are flowing again"
    assert mf.page(green, {"reasons": []}, NOW) is None


def test_every_reason_has_words() -> None:
    for r in ("MERGE_SLO", "GATE_SILENT", "BOX_LOGIN"):
        assert mf.page(_red([r]), {}, NOW) is not None


def test_collect_falls_back_to_anonymous_reads() -> None:
    calls: list[tuple[str, str]] = []

    def gh(path: str) -> Any:
        calls.append(("gh", path))
        raise RuntimeError("HTTP 401: Bad credentials")

    def anon(path: str) -> Any:
        calls.append(("anon", path))
        if "/pulls" in path:
            return [_pr(7, "s7")]
        if path.endswith("/status"):
            return {"statuses": [{"context": "other"}, _st(90)]}
        return []

    doc = mf.collect("o/r", NOW, gh=gh, anon=anon,
                     registry=lambda _r: [json.dumps(_row(7, "s7", 3))])  # fmt: skip
    assert calls[0] == ("gh", "user") and all(k == "anon" for k, _ in calls[1:])
    assert doc["reasons"] == ["GATE_SILENT", "BOX_LOGIN"]
    assert doc["prs"][0]["pr"] == 7


def test_collect_samples_oldest_clears_first_and_bounded() -> None:
    n = mf.STATUS_SAMPLE + 5
    prs = [_pr(i, f"s{i}") for i in range(n)]
    rows = [json.dumps(_row(i, f"s{i}", float(i))) for i in range(n)]
    seen: list[str] = []

    def gh(path: str) -> Any:
        if path == "user":
            return {"login": "box"}
        if "/pulls" in path:
            return prs
        if path.endswith("/status"):
            seen.append(path)
            return {"statuses": [_st(5)]}
        return []

    mf.collect("o/r", NOW, gh=gh, anon=gh, registry=lambda _r: rows)
    assert len(seen) == mf.STATUS_SAMPLE
    assert f"/s{n - 1}/status" in seen[0]  # the oldest CLEAR is read first


def test_main_print_unmeasured_on_collect_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def boom(*_a: Any, **_k: Any) -> Any:
        raise OSError("network down")

    monkeypatch.setattr(mf, "collect", boom)
    assert mf.main(["--print"]) == 0
    assert json.loads(capsys.readouterr().out)["verdict"] == "UNMEASURED"


def test_main_heals_pages_and_writes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(mf, "REPORT", tmp_path / "MERGE_FLOW.json")
    monkeypatch.setattr(mf, "STATE", tmp_path / "state.json")
    red = {**_red(["GATE_SILENT"]), "box_login": {"ok": True, "detail": "ok"}}
    monkeypatch.setattr(mf, "collect", lambda *_a, **_k: dict(red))
    started: list[int] = []
    monkeypatch.setattr(mf, "start_gate", lambda: started.append(1) or "started")
    assert mf.main(["--no-alert"]) == 2
    assert started == [1]
    rep = json.loads((tmp_path / "MERGE_FLOW.json").read_text(encoding="utf-8"))
    assert rep["heal"] == "started"
    st = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert st["reasons"] == ["GATE_SILENT"] and "healed_at" in st
    assert mf.main(["--no-alert"]) == 2
    assert started == [1]  # rate-limited: one start per HEAL_EVERY


def test_wired_as_core_leg_and_published() -> None:
    hc = (ROOT / "desks/mt5/research/hourly_cycle.py").read_text(encoding="utf-8")
    assert '"merge_flow",' in hc and '"scripts/merge_flow.py"' in hc
    assert '"merge_flow": mfl' in hc
    assert hc.index('_costed("merge_flow"') < hc.index('_costed("publish_state"')
    for p in ("desks/mt5/scripts/sync_shadow_to_git.ps1", "desks/mt5/mt5desk/release_identity.py",
              "libs/ops/release.py", "ops/organ_contract.py"):  # fmt: skip
        assert "desks/mt5/reports/MERGE_FLOW.json" in (ROOT / p).read_text(encoding="utf-8"), p


def test_never_writes_to_github() -> None:
    src = (ROOT / "scripts/merge_flow.py").read_text(encoding="utf-8")
    for bad in ('"-X"', "POST", "PUT", "PATCH", "DELETE", '/merge"', "/reviews", "/comments"):
        assert bad not in src, bad
