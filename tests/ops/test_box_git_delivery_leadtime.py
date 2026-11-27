"""Delivery lead time (zuck 2026-11-25 17:33Z, L16): every stage stamped, the bottleneck named,
nothing guessed, nothing changed."""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from ops.box_git import box_loop
from ops.box_git import delivery_leadtime as dl

NOW = datetime(2026, 11, 25, 18, 0, tzinfo=UTC)
A, B, M = "a" * 40, "b" * 40, "c" * 40


def _t(h: float) -> str:
    return (NOW - timedelta(hours=h)).isoformat()


def _clear(head: str, h: float, login: str = "auditor") -> dict:
    return {"user": {"login": login}, "created_at": _t(h), "body": f"AUDIT CLEAR {head} merge"}


def _status(state: str, h: float, desc: str = "", who: str = "box-ci") -> dict:
    return {"creator": {"login": who}, "status": state, "created_at": _t(h),
            "updated_at": _t(h), "description": desc}


def _anc(a: str, b: str) -> bool:
    return (a, b) in {(M, "p1"), (M, "g1")}


PRS = [
    {"number": 1, "head": {"sha": A}, "title": "shipped", "state": "closed", "merged": True,
     "merged_at": _t(30), "merge_commit_sha": M, "created_at": _t(40)},
    {"number": 2, "head": {"sha": B}, "title": "stuck", "state": "open", "created_at": _t(100)},
]
COMMENTS = {1: [_clear(A, 41), _clear(A, 50, login="claude")],
            2: [_clear(B, 120), _clear(A, 130)]}
STATUSES = {A: [_status("pending", 39), _status("success", 35)],
            B: [_status("pending", 99), _status("failure", 98, "+++ Timeout +++"),
                _status("failure", 97, "3 failed", who="claude")]}
FULL = [{"kind": "full", "head": "g1", "ok": True, "at": _t(20), "why": "law gate rc=0; ok"},
        {"kind": "full", "head": "r1", "ok": False, "at": _t(60),
         "why": "law gate rc=124; Could not determine home directory"}]


def _doc(adopted=None):
    return dl.build(PRS, COMMENTS, STATUSES, full_results=FULL,
                    production=[(NOW - timedelta(hours=10), "p1")], adopted=adopted,
                    is_ancestor=_anc, now=NOW)


def test_every_stage_is_stamped_from_its_own_source():
    shipped = _doc()["changes"][0]["stages"]
    assert shipped["clear"] == _t(41)            # the auditor's, not the claude account's
    assert shipped["forge_pr"] == _t(40) and shipped["ci_start"] == _t(39)
    assert shipped["ci_end"] == _t(35) and shipped["live"] == _t(30)
    assert shipped["full_green"] == _t(20) and shipped["production"] == _t(10)
    assert shipped["adopted"] is None


def test_a_clear_counts_only_at_the_exact_head_and_only_from_a_clearing_account():
    assert dl.clear_at([_clear(A, 5, login="claude")], A) is None
    assert dl.clear_at([_clear(A, 5)], B) is None
    assert dl.clear_at([_clear(B, 5, login="quant-admin")], B) == NOW - timedelta(hours=5)


def test_ci_failures_are_classified_and_other_accounts_statuses_ignored():
    stuck = _doc()["changes"][1]
    assert stuck["ci_causes"] == ["env"] and stuck["stages"]["live"] is None


def test_the_week_names_lead_time_backlog_green_share_and_the_bottleneck():
    s = _doc()["summary"]
    assert s["lead_time_h"] == {"n": 1, "median": 31.0, "p90": 31.0}
    assert s["built_not_live"]["n"] == 1 and s["built_not_live"]["oldest_h"] == 120.0
    assert s["full_runs"] == {"n": 2, "green": 1, "green_share": 0.5,
                              "failed_by_cause": {"env": 1}}
    # PR 2 has waited ~97 h since its last CI answer: the stalled stage is the bottleneck
    assert s["bottleneck"] == "ci_end" and s["hours_held_by_stage"]["ci_end"] >= 97
    assert "adopted" in s["unmeasured_stages"] and "first_use" in s["unmeasured_stages"]


def test_an_adoption_record_fills_the_adopted_stage_and_counts():
    d = _doc(adopted=[(NOW - timedelta(hours=2), "p1")])
    assert d["changes"][0]["stages"]["adopted"] == _t(2) and d["summary"]["adoptions"] == 1
    assert "adopted" not in d["summary"]["unmeasured_stages"]


def test_causes():
    assert dl.cause("exit status 128") == "env"
    assert dl.cause("law gate rc=2; ok") == "law_gate"
    assert dl.cause("rc=124") == "timeout"
    assert dl.cause("2 failed, 9 passed") == "tests"
    assert dl.cause("") == "other"


class _Forge:
    def __init__(self):
        self.calls: list[str] = []

    def _all(self, path):
        self.calls.append(path)
        if "/pulls?" in path:
            return [{**p, "base": {"ref": box_loop.LIVE}} for p in PRS] + [
                {"number": 9, "head": {"sha": "d" * 40}, "base": {"ref": "production"}}]
        if "/comments" in path:
            return COMMENTS[int(path.split("/issues/")[1].split("/")[0])]
        return STATUSES[path.split("/commits/")[1].split("/")[0]]


def test_the_loop_stage_writes_the_report_read_only_and_not_more_than_every_5_min(
        tmp_path, monkeypatch):
    cfg = box_loop.Config(forge_url="x", bare=tmp_path, work=tmp_path, tokens=tmp_path,
                          ca=tmp_path, state=tmp_path / "state.json")
    forge = _Forge()
    monkeypatch.setattr(box_loop, "_forge", lambda c, a: forge)
    monkeypatch.setattr(box_loop, "_production_commits", lambda c: [(NOW, "p1")])
    monkeypatch.setattr(box_loop, "_run", lambda argv, **k: (1, ""))
    why = box_loop.leadtime_tick(cfg, now=NOW)
    doc = json.loads(Path(tmp_path / dl.REPORT).read_text(encoding="utf-8"))
    assert [c["pr"] for c in doc["changes"]] == [1, 2]          # only PRs into LIVE
    assert "backlog 2" in why          # ancestry stubbed: nothing reached production
    assert all(not c.startswith("POST") for c in forge.calls)
    n = len(forge.calls)
    again = box_loop.leadtime_tick(cfg, now=NOW + timedelta(minutes=3))  # (r20) 5 min
    assert again.startswith("lead time fresh")
    assert len(forge.calls) == n


def test_the_loop_runs_the_lead_time_stage_last():
    import inspect
    # (r20) the light stages run in LIGHT's order, every round and once more after the heavy ones
    assert box_loop.LIGHT[-1] == "leadtime" and "promote" in box_loop.LIGHT
    src = inspect.getsource(box_loop.tick)
    assert src.count("for name in LIGHT") == 3


def _c(body: str, h: float, login: str) -> dict:
    return {"body": body, "created_at": _t(h), "user": {"login": login}}


def test_pr_view_matches_the_pr_stage_reading_of_verdicts():
    from ops.box_git import forge_api
    a, b = "a" * 40, "b" * 40
    cases = [
        [],
        [_c(f"AUDIT CLEAR {a} merge", 1, "auditor")],
        [_c(f"AUDIT CLEAR {b} merge", 1, "auditor"), _c(f"AUDIT CLEAR {a} merge", 2, "auditor")],
        [_c(f"AUDIT CLEAR {a} merge", 1, "auditor"), _c(f"AUDIT CLEAR {b} merge", 2, "auditor")],
        [_c(f"AUDIT CLEAR {a} merge", 1, "auditor"), _c(f"AUDIT HOLD {a} merge", 2, "claude")],
        [_c(f"AUDIT CLEAR {a} merge", 1, "claude")],
        [_c(f"AUDIT CLEAR {a} merge", 1, "auditor"), _c(f"AUDIT CLEAR {b} merge", 2, "claude")],
        [_c(f"AUDIT CLEAR {a} merge", 1, "quant-admin")],
        [_c(f"note\nAUDIT HOLD {a}\n", 1, "auditor"), _c(f"AUDIT CLEAR {a} squash", 2, "auditor")],
    ]
    for cs in cases:
        want = box_loop.audited_clear([forge_api._comment(c) for c in cs], a)
        assert dl.pr_view(cs, a)["clear_at_head"] is want, cs


def test_pr_view_names_the_line_that_blocks_a_clear_pr():
    a, b = "a" * 40, "b" * 40
    v = dl.pr_view([_c(f"AUDIT CLEAR {a} merge", 1, "auditor"),
                    _c(f"AUDIT CLEAR {b} merge", 2, "auditor")], a)
    assert v["clear_at_head"] is False and v["verdict_lines"] == 2
    assert v["last_verdict"]["kind"] == "CLEAR" and v["last_verdict"]["sha"] == b[:12]


def test_rows_carry_the_pr_view_and_the_box_ci_status_count():
    doc = _doc()
    for r in doc["changes"]:
        assert set(r["pr_view"]) == {"verdict_lines", "last_verdict", "clear_at_head",
                                     "box_ci_statuses"}


def test_stuck_lists_clear_changes_without_box_ci_or_not_live_past_their_limit():
    now = datetime(2026, 11, 26, 16, 0, tzinfo=UTC)
    def r(n, clear_h, ci=False, live=False, state="open"):
        at = lambda h: (now - timedelta(hours=h)).isoformat()  # noqa: E731
        return {"pr": n, "head": "a" * 40, "title": f"t{n}", "state": state,
                "pr_view": {"clear_at_head": False},
                "stages": {"clear": at(clear_h), "ci_start": at(clear_h - 0.1) if ci else None,
                           "live": at(0.5) if live else None}}
    rows = [r(53, 40), r(147, 1), r(128, 8, ci=True), r(5, 9, ci=True, live=True),
            r(6, 50, state="closed"), {"pr": 7, "state": "open", "stages": {"clear": None}}]
    s = dl.stuck(rows, now)
    assert [i["pr"] for i in s["no_ci"]] == [53]          # #147 is under the 2 h limit
    assert [i["pr"] for i in s["not_live"]] == [128]      # CI ran, 8 h and not live
    assert s["n"] == 2 and s["no_ci"][0]["clear_at_head"] is False


def test_the_summary_carries_the_stuck_block():
    assert set(_doc()["summary"]["stuck"]) == {"limits_h", "no_ci", "not_live", "n"}
