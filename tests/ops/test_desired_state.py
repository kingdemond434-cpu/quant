"""Box-local switches flipped by the adopter (libs/ops/desired_state.py): only audited
content, only switches with a check, each committed version once, never near a gold window, and
provisional -- put back on their own -- until a gold window has run on them."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from tests.ops.test_adopt_guard import QUIET, _commit, _g, _write, summer

from libs.ops import adopt_guard as ag
from libs.ops import desired_state as ds
from libs.ops import new_risk_hold as nrh

ROOT = Path(__file__).resolve().parents[2]
OLD = {"lanes": ["e8", "fusion"]}
WANT = {"lanes": ["e8", "fusion", "ftmo"], "modes": {"fusion": "oco", "ftmo": "fallback"}}
DESIRED_REL = f"{ds.DESIRED_DIR}/GOLD_OCO_MODE.json"
LIVE = "desks/mt5/data/GOLD_OCO_MODE.json"
TASKS = ["E8-Gold", "MT5-FTMO-Follower", "MT5-Gateway"]


@pytest.fixture
def pages(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    out: list[str] = []
    monkeypatch.setattr(ag, "page", lambda _root, m: out.append(m))
    return out


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pages: list[str]) -> Path:
    r = tmp_path / "r"
    r.mkdir()
    _g(r, "init", "-q", "-b", "live")
    _g(r, "config", "user.email", "t@t")
    _g(r, "config", "user.name", "t")
    _write(
        r, ".gitignore", "desks/mt5/data/GOLD_OCO_MODE.json\ndesks/mt5/data/box_state_backups/\n"
    )
    _write(r, "libs/x.py", "X = 1\n")
    _commit(r, "base")
    _write(r, LIVE, json.dumps(OLD))
    monkeypatch.setattr(ds, "_protocol", lambda _root: 1)
    return r


def _want(repo: Path, doc: dict[str, Any] = WANT, *, clear: bool = True) -> str:
    _write(repo, DESIRED_REL, json.dumps(doc))
    c = _commit(repo, "desired")
    if clear:
        row = ag.clear_row(repo, c, "CLEAR", "reports/audit/2026-10-28/X.md", base=f"{c}~1")
        prev = repo / ag.CLEARS_REL
        text = prev.read_text() if prev.exists() else ""
        _write(repo, ag.CLEARS_REL, text + json.dumps(row, sort_keys=True) + "\n")
        c = _commit(repo, "clears")
    return c


def _task(result: int, at: datetime) -> dict[str, Any]:
    return {"state": "Ready", "last": at.isoformat(), "result": result}


def _ok_before(_name: str) -> dict[str, Any]:
    return _task(0, QUIET - timedelta(minutes=1))


def _reader(lane: str, max_age_s: float = 0) -> tuple[dict[str, Any] | None, str]:
    return {"lane": lane, "protocol": 1}, "fresh"


def _apply(repo: Path, **kw: Any) -> tuple[int, dict[str, Any]]:
    kw.setdefault("task_info", _ok_before)
    kw.setdefault("read_lane", _reader)
    return ds.apply(repo, now=QUIET, offset_h=summer, **kw)


def _verify(repo: Path, now: datetime, **kw: Any) -> tuple[int, dict[str, Any]]:
    kw.setdefault("read_lane", _reader)
    kw.setdefault("offset_h", summer)
    return ds.verify(repo, now=now, **kw)


def _confirm(repo: Path) -> None:
    """Run the provisional switch through its gold window: one verify inside it, one after."""
    (row,) = ds.load_provisional(repo)
    start, end = (datetime.fromisoformat(row[k]) for k in ("window_start", "window_end"))
    ran = lambda n: _task(0, start + timedelta(minutes=5))  # noqa: E731
    _verify(repo, start + timedelta(minutes=10), task_info=ran)
    _verify(repo, end + timedelta(minutes=5), task_info=ran)


def _live(repo: Path) -> Any:
    return json.loads((repo / LIVE).read_text(encoding="utf-8"))


def _journal(repo: Path) -> list[str]:
    return [r["result"] for r in ds._journal_rows(repo)]


def test_audited_switch_is_applied_provisionally_with_no_hold(repo: Path) -> None:
    _want(repo)
    code, doc = _apply(repo)
    assert (code, doc["decision"]) == (ag.GO, "APPLIED_PROVISIONAL"), doc
    assert _live(repo) == WANT
    assert _journal(repo) == ["APPLYING", "APPLIED"]
    assert nrh.reason(repo) is None  # no lane loses entries over a gold switch (Rule 1)
    (row,) = ds.load_provisional(repo)
    assert sorted(row["tasks"]) == TASKS and row["added_gold_lanes"] == ["ftmo"]
    assert json.loads(Path(row["backup"]).read_text()) == OLD
    # the gold Asia window after 18:00Z (summer): broker 06:30-07:30 = 03:30-04:30Z next day
    assert row["window_start"].startswith("2026-10-29T03:30")


def test_each_committed_version_is_applied_once(repo: Path) -> None:
    """A person's later box-local edit stands; only a new committed version is a new decision."""
    _want(repo)
    _apply(repo)
    _confirm(repo)
    assert ds.load_provisional(repo) == []
    _write(repo, LIVE, json.dumps(OLD))  # dropped ftmo by hand during an incident
    _code, doc = _apply(repo)
    assert doc["decision"] == "NOTHING_TO_APPLY" and "applied once already" in doc["skipped"][0]
    assert _live(repo) == OLD


def test_unaudited_switch_is_never_applied(repo: Path) -> None:
    _want(repo, clear=False)
    _code, doc = _apply(repo)
    assert doc["decision"] == "NOTHING_TO_APPLY" and "no auditor CLEAR" in doc["skipped"][0]
    assert _live(repo) == OLD


def test_a_switch_without_a_check_is_never_applied(repo: Path) -> None:
    _write(repo, f"{ds.DESIRED_DIR}/sleeves.json", "{}")
    _commit(repo, "x")
    _code, doc = _apply(repo)
    assert "no check is written" in doc["skipped"][0]
    assert not (repo / "desks/mt5/data/sleeves.json").exists()


def test_never_near_a_gold_window(repo: Path) -> None:
    _want(repo)
    near = datetime(2026, 10, 28, 3, 0, tzinfo=UTC)  # inside the start margin before gold asia
    code, doc = ds.apply(repo, now=near, offset_h=summer, read_lane=_reader, task_info=_ok_before)
    assert (code, doc["decision"]) == (ag.HOLD, "HOLD_BLACKOUT")
    assert _live(repo) == OLD


def test_adding_a_lane_that_does_not_publish_is_refused_and_paged_once(
    repo: Path, pages: list[str]
) -> None:
    _want(repo)

    def absent(lane: str, max_age_s: float = 0) -> tuple[None, str]:
        return None, f"the {lane} gold state is absent"

    for _ in range(3):
        _code, doc = _apply(repo, read_lane=absent)
        assert doc["decision"] == "REFUSED" and "gold would freeze" in doc["skipped"][-1]
    assert len(pages) == 1 and "ftmo" in pages[0]
    assert _live(repo) == OLD
    assert _apply(repo)[1]["decision"] == "APPLIED_PROVISIONAL"  # refused is retried when ready


@pytest.mark.parametrize(
    ("doc", "why"),
    [
        ({"lanes": ["fusion"]}, "e8"),
        ({"lanes": ["e8", "cme"]}, "non-empty list"),
        ({"lanes": ["e8"], "modes": {"fusion": "oco"}}, "not in lanes"),
        ({"lanes": ["e8", "fusion"], "modes": {"fusion": "yolo"}}, "oco or fallback"),
        ({"lanes": ["e8"], "extra": 1}, "unknown keys"),
    ],
)
def test_the_gold_oco_check_refuses_what_gold_oco_would_misread(
    repo: Path, doc: dict[str, Any], why: str
) -> None:
    assert why in (ds.check_gold_oco(repo, doc, None, _reader) or "")


def test_a_lane_failing_on_the_switch_puts_it_back(repo: Path, pages: list[str]) -> None:
    _want(repo)
    _apply(repo)
    later = QUIET + timedelta(hours=10)

    def info(name: str) -> dict[str, Any]:
        return _task(1 if name == "E8-Gold" else 0, later - timedelta(minutes=2))

    code, doc = _verify(repo, later, task_info=info)
    assert (code, doc["restored"]) == (ag.UNHEALTHY, ["GOLD_OCO_MODE.json"])
    assert _live(repo) == OLD and ds.load_provisional(repo) == []
    assert _journal(repo)[-1] == "RESTORED" and "E8-Gold" in pages[-1]


def test_a_running_task_is_not_a_failure(repo: Path) -> None:
    """v4 audit MF1: LastTaskResult reads 267009 while the task runs."""
    _want(repo)
    _apply(repo)
    later = QUIET + timedelta(hours=10)
    code, doc = _verify(repo, later, task_info=lambda n: _task(267009, later))
    assert code == ag.GO and doc["provisional"] == ["GOLD_OCO_MODE.json"]
    assert _live(repo) == WANT
    assert ag.task_verdict(_task(267011, later), QUIET) == "RUNNING"
    assert ag.task_verdict(_task(267009, later), QUIET) == "RUNNING"
    assert ag.lane_problems(repo, QUIET, lambda n: _task(267009, later))[0] == []


def test_an_added_lane_going_silent_puts_it_back(repo: Path) -> None:
    """gold_oco freezes gold on every lane while a declared lane is silent."""
    _want(repo)
    _apply(repo)

    def silent(lane: str, max_age_s: float = 0) -> tuple[dict[str, Any] | None, str]:
        if lane == "ftmo" and max_age_s == ds.LIVE_LANE_MAX_AGE_S:
            return None, "900s old"
        return {"lane": lane, "positions": [], "orders": []}, "ok"  # flat when last seen

    _code, doc = _verify(repo, QUIET + timedelta(hours=1), task_info=_ok_before, read_lane=silent)
    assert doc["restored"] == ["GOLD_OCO_MODE.json"] and _live(repo) == OLD


def test_a_lane_already_failing_is_never_judged(repo: Path) -> None:
    """v4 audit MF3: a terminal that was down before the switch does not roll it back."""
    _want(repo)
    _apply(repo, task_info=lambda n: _task(1 if n == "MT5-FTMO-Follower" else 0, QUIET))
    (row,) = ds.load_provisional(repo)
    assert "MT5-FTMO-Follower" not in row["judged"]
    later = QUIET + timedelta(hours=2)
    info = lambda n: _task(1 if n == "MT5-FTMO-Follower" else 0, later)  # noqa: E731
    code, _doc = _verify(repo, later, task_info=info)
    assert code == ag.GO and _live(repo) == WANT


def test_confirmed_only_after_a_gold_window_ran_on_it(repo: Path) -> None:
    _want(repo)
    _apply(repo)
    (row,) = ds.load_provisional(repo)
    start, end = (datetime.fromisoformat(row[k]) for k in ("window_start", "window_end"))
    before_window = lambda n: _task(0, start - timedelta(minutes=5))  # noqa: E731
    assert _verify(repo, start - timedelta(minutes=1), task_info=before_window)[1]["provisional"]
    in_window = lambda n: _task(0, end - timedelta(minutes=1))  # noqa: E731
    # v6 audit MF1: a success stamped inside the window but only seen afterwards is not evidence
    _code, doc = _verify(repo, end + timedelta(minutes=5), task_info=in_window)
    assert doc["confirmed"] == [] and doc["provisional"] == ["GOLD_OCO_MODE.json"]
    (row,) = ds.load_provisional(repo)
    assert datetime.fromisoformat(row["window_start"]) > end  # rolled to the next window
    _confirm(repo)
    assert ds.load_provisional(repo) == [] and _journal(repo)[-1] == "CONFIRMED"


def test_one_lane_unseen_in_the_window_keeps_it_provisional(repo: Path) -> None:
    _want(repo)
    _apply(repo)
    (row,) = ds.load_provisional(repo)
    start, end = (datetime.fromisoformat(row[k]) for k in ("window_start", "window_end"))

    def info(n: str) -> dict[str, Any] | None:
        return None if n == "MT5-FTMO-Follower" else _task(0, start + timedelta(minutes=5))

    _verify(repo, start + timedelta(minutes=10), task_info=info)
    _code, doc = _verify(repo, end + timedelta(minutes=5), task_info=info)
    assert doc["confirmed"] == [] and _live(repo) == WANT


def _roll(repo: Path, info: Any) -> dict[str, Any]:
    """One verify inside the switch's current window and one after it ends."""
    (row,) = ds.load_provisional(repo)
    start, end = (datetime.fromisoformat(row[k]) for k in ("window_start", "window_end"))
    _verify(repo, start + timedelta(minutes=10), task_info=info)
    return _verify(repo, end + timedelta(minutes=5), task_info=info)[1]


def test_an_unmeasurable_switch_is_kept_and_its_restore_disarmed_after_a_trading_day(
    repo: Path, pages: list[str]
) -> None:
    """UNMEASURED is never CONFIRMED; after a trading day of gold windows it pages once and the
    switch is kept, its restore off: a lane's unrelated failure later never reverts it."""
    _want(repo)
    _apply(repo)
    for _ in range(ds.UNCONFIRMED_WINDOWS - 1):
        assert _roll(repo, lambda n: None)["provisional"] and not pages
    done = _roll(repo, lambda n: None)
    assert done["confirmed"] == [] and done["provisional"] == []
    assert len(pages) == 1 and "restore is now off" in pages[0]
    assert _journal(repo)[-1] == "KEPT_UNCONFIRMED"
    later = QUIET + timedelta(days=10)
    _code, doc = _verify(repo, later, task_info=lambda n: _task(1, later))
    assert doc["decision"] == "NOTHING_PROVISIONAL" and _live(repo) == WANT
    assert _apply(repo)[1]["decision"] == "NOTHING_TO_APPLY"


def test_a_weekend_window_never_counts(repo: Path) -> None:
    """v10 audit MF1: a broker Saturday or Sunday window is a closed market."""
    pol = ag.load_policy(repo)
    friday_night = datetime(2026, 10, 30, 21, 30, tzinfo=UTC)  # broker Sat 00:30
    start, _end = ds.next_window(friday_night, pol, summer)
    assert (start + timedelta(hours=summer(start))).weekday() == 0  # broker Monday
    for d in range(14):
        s, _e = ds.next_window(QUIET + timedelta(hours=7 * d), pol, summer)
        assert (s + timedelta(hours=summer(s))).weekday() < 5


def test_an_always_running_gateway_counts_by_its_pass_stamp(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """v8 audit W1: MT5-Gateway starts a pass every minute, so its task reads 267009 at :12.
    Its stamp counts only from the release the switch was applied under."""
    monkeypatch.setattr(ds, "_sealed", lambda _root: "a" * 40)
    _want(repo)
    _apply(repo)

    def stamp(runner: str, minutes: int, release: str = "a" * 40) -> None:
        (row,) = ds.load_provisional(repo)
        at = datetime.fromisoformat(row["window_start"]) + timedelta(minutes=minutes)
        doc = {"runner": runner, "last_pass_at": at.isoformat(), "release_sha": release}
        _write(repo, ag.GATEWAY_LOADED_REL, json.dumps(doc))

    def ok_in_window(n: str) -> dict[str, Any]:
        (row,) = ds.load_provisional(repo)
        start = datetime.fromisoformat(row["window_start"])
        return _task(267009 if n == "MT5-Gateway" else 0, start + timedelta(minutes=5))

    stamp("MT5-Gateway", -1)  # a pass before the window: no evidence
    assert _roll(repo, ok_in_window)["confirmed"] == []
    stamp("MT5-Gateway", 9, release="b" * 40)  # a pass of another release
    assert _roll(repo, ok_in_window)["confirmed"] == []
    stamp("MT5-Gateway", 9)
    assert _roll(repo, ok_in_window)["confirmed"] == ["GOLD_OCO_MODE.json"]


def test_another_runners_stamp_is_no_evidence(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ds, "_sealed", lambda _root: "a" * 40)
    _want(repo)
    _apply(repo)
    (row,) = ds.load_provisional(repo)
    start = datetime.fromisoformat(row["window_start"])
    doc = {
        "runner": "MT5-GatewayResident",
        "last_pass_at": (start + timedelta(minutes=9)).isoformat(),
        "release_sha": "a" * 40,
    }
    _write(repo, ag.GATEWAY_LOADED_REL, json.dumps(doc))
    assert not ds._passed_in_window(
        repo, "MT5-Gateway", start, start + timedelta(minutes=10), "a" * 40
    )
    assert ds._passed_in_window(
        repo, "MT5-GatewayResident", start, start + timedelta(minutes=10), "a" * 40
    )


def test_a_newer_cleared_version_supersedes_a_provisional_one(repo: Path) -> None:
    """v8 audit S1: it does not wait behind it, and its restore goes back to before both."""
    _want(repo)
    _apply(repo)
    newer = {"lanes": ["e8", "fusion"], "modes": {"fusion": "fallback"}}
    _want(repo, newer)
    _code, doc = _apply(repo)
    assert doc["decision"] == "APPLIED_PROVISIONAL" and _live(repo) == newer
    (row,) = ds.load_provisional(repo)
    assert json.loads(Path(row["backup"]).read_text()) == OLD
    assert _journal(repo)[-2:] == ["APPLIED", "SUPERSEDED"]


def test_a_garbled_provisional_record_never_blocks_a_cancel(repo: Path) -> None:
    """v8 audit should-fix: the record guards switches, not order withdrawals."""
    _write(repo, ds.PROVISIONAL_REL, "[half")
    req = {
        "requests": [
            {
                "id": "x",
                "lane": "ftmo",
                "tickets": [7],
                "expires_at": (QUIET + timedelta(hours=2)).isoformat(),
                "why": "t",
            }
        ]
    }
    _write(repo, f"{ds.DESIRED_DIR}/CANCEL_PENDING.json", json.dumps(req))
    c = _commit(repo, "cancel")
    row = ag.clear_row(repo, c, "CLEAR", "reports/audit/2026-10-28/X.md", base=f"{c}~1")
    _write(repo, ag.CLEARS_REL, json.dumps(row, sort_keys=True) + "\n")
    _commit(repo, "clears")
    _code, doc = _apply(repo, any_time_only=True)
    assert doc["applied"] == ["CANCEL_PENDING.json"], doc


def test_a_lane_holding_gold_is_never_undeclared(repo: Path, pages: list[str]) -> None:
    """v6 audit MF2: putting the switch back would let E8 and Fusion trade blind to its gold."""
    _want(repo)
    _apply(repo)

    def busy(lane: str, max_age_s: float = 0) -> tuple[dict[str, Any] | None, str]:
        if lane == "ftmo" and max_age_s == ds.LIVE_LANE_MAX_AGE_S:
            return None, "900s old"
        return {"lane": lane, "positions": [{"ticket": 7}], "orders": []}, "ok"

    for h in (1, 2):
        code, doc = _verify(repo, QUIET + timedelta(hours=h), task_info=_ok_before, read_lane=busy)
        assert code == ag.UNHEALTHY and doc["restored"] == [] and _live(repo) == WANT
    assert len(pages) == 1 and "NOT put back" in pages[0]
    assert ds.load_provisional(repo)  # restore stays armed for when the lane is flat


def test_a_lane_never_seen_is_never_undeclared(repo: Path) -> None:
    _want(repo)
    _apply(repo)

    def gone(lane: str, max_age_s: float = 0) -> tuple[dict[str, Any] | None, str]:
        return (None, "absent") if lane == "ftmo" else ({"lane": lane}, "ok")

    _code, doc = _verify(repo, QUIET + timedelta(hours=1), task_info=_ok_before, read_lane=gone)
    assert doc["restored"] == [] and _live(repo) == WANT


def test_an_apply_that_died_half_way_is_retried(repo: Path) -> None:
    """v6 should-fix: APPLYING with no APPLIED after it is not a final decision."""
    _want(repo)
    blob = ag._tree(repo, ag._rev(repo, "HEAD"))[DESIRED_REL]
    ds._journal(repo, {"name": "GOLD_OCO_MODE.json", "blob": blob, "result": "APPLYING"})
    _code, doc = _apply(repo)
    assert doc["decision"] == "APPLIED_PROVISIONAL" and _live(repo) == WANT


def test_a_journal_that_cannot_be_written_stops_the_apply(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _want(repo)

    def broken(_root: Path, _row: dict[str, Any]) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(ds, "_journal", broken)
    with pytest.raises(OSError):
        _apply(repo)
    assert _live(repo) == OLD and ds.load_provisional(repo) == []


def test_switches_wait_while_the_adopters_hold_stands(repo: Path) -> None:
    _want(repo)
    assert ag.hold_new_risk(repo, "unhealthy release")
    code, doc = _apply(repo)
    assert (code, doc["decision"]) == (ag.HOLD, "HOLD_RELEASE_HELD")
    assert _live(repo) == OLD


def test_the_switch_path_is_governed_state_not_code() -> None:
    assert not ag.is_code(DESIRED_REL) and ag.is_governed_state(DESIRED_REL)
    assert ds.BACKUP_DIR + "/" in (ROOT / ".gitignore").read_text()
    assert ds.PROVISIONAL_REL.startswith(ds.BACKUP_DIR + "/")


def test_adopt_and_seal_applies_on_healthy_exits_and_verifies_every_run() -> None:
    ps = (ROOT / "desks/mt5/scripts/Adopt-And-Seal.ps1").read_text(encoding="utf-8")
    for stage in ("already-sealed", "accepts-nothing-to-seal", "sealed"):
        assert re.search(r"Invoke-StateApply\s*\r?\n\s*Done 0 \"" + stage + '"', ps), stage
    assert ps.count("Invoke-StateApply") == 4  # the definition and three calls
    verify = ps.index('Invoke-AdoptGuard @("state-verify")')
    assert ps.index('Invoke-AdoptGuard @("heal"') < verify < ps.index("release_promotion.py")


# ------------------------------------------------------------------- cancel requests (any time)
CANCEL_REL = f"{ds.DESIRED_DIR}/CANCEL_PENDING.json"


def _cancel_doc(hours: float = 4) -> dict[str, Any]:
    exp = (datetime.now(UTC) + timedelta(hours=hours)).isoformat()
    return {
        "requests": [
            {
                "id": "ftmo-1",
                "lane": "ftmo",
                "tickets": [111616773],
                "expires_at": exp,
                "why": "stale",
            }
        ]
    }


def _want_cancel(repo: Path, doc: dict[str, Any]) -> None:
    _write(repo, CANCEL_REL, json.dumps(doc))
    c = _commit(repo, "cancel")
    row = ag.clear_row(repo, c, "CLEAR", "reports/audit/2026-10-28/X.md", base=f"{c}~1")
    prev = repo / ag.CLEARS_REL
    text = prev.read_text() if prev.exists() else ""
    _write(repo, ag.CLEARS_REL, text + json.dumps(row, sort_keys=True) + "\n")
    _commit(repo, "clears")


def test_a_cancel_request_is_applied_inside_a_window_and_never_provisional(repo: Path) -> None:
    doc = _cancel_doc()
    _want_cancel(repo, doc)
    inside = datetime(2026, 10, 28, 3, 45, tzinfo=UTC)  # gold Asia, summer
    _code, out = ds.apply(
        repo,
        now=inside,
        offset_h=summer,
        read_lane=_reader,
        task_info=_ok_before,
        any_time_only=True,
    )
    assert out["decision"] == "APPLIED_PROVISIONAL" and out["applied"] == ["CANCEL_PENDING.json"]
    assert json.loads((repo / "desks/mt5/data/CANCEL_PENDING.json").read_text()) == doc
    assert ds.load_provisional(repo) == []


def test_a_cancel_request_waits_for_nothing_but_a_gold_switch_still_waits(repo: Path) -> None:
    _want(repo)
    _want_cancel(repo, _cancel_doc())
    assert ag.hold_new_risk(repo, "unhealthy release")
    inside = datetime(2026, 10, 28, 3, 45, tzinfo=UTC)
    _code, out = ds.apply(
        repo, now=inside, offset_h=summer, read_lane=_reader, task_info=_ok_before
    )
    assert out["applied"] == ["CANCEL_PENDING.json"]
    assert any("GOLD_OCO_MODE.json: waits" in s for s in out["skipped"])
    assert _live(repo) == OLD


def test_a_bad_cancel_request_is_refused(repo: Path, pages: list[str]) -> None:
    _want_cancel(repo, _cancel_doc(hours=60))
    _code, out = _apply(repo, any_time_only=True)
    assert out["decision"] == "REFUSED" and "expires more than" in out["skipped"][0]
    assert not (repo / "desks/mt5/data/CANCEL_PENDING.json").exists() and pages


def test_state_verify_still_applies_a_cancel_over_a_garbled_record(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.ops.test_adopt_guard import _cli

    _write(repo, ds.PROVISIONAL_REL, "[half")
    seen: list[bool] = []

    def fake_apply(root: Path, **kw: Any) -> tuple[int, dict[str, Any]]:
        seen.append(kw.get("any_time_only", False))
        return ag.GO, {"decision": "APPLIED_PROVISIONAL", "applied": ["CANCEL_PENDING.json"]}

    monkeypatch.setattr(ds, "apply", fake_apply)
    assert _cli().main(["--root", str(repo), "state-verify"]) == ag.ERROR
    assert seen == [True]


def test_a_superseding_version_still_never_undeclares_a_lane_holding_gold(
    repo: Path, pages: list[str]
) -> None:
    """v10 audit MF2 (SP2/SP3): v1 adds ftmo, v2 only changes its mode. v2's restore goes back to
    before v1, so ftmo is still an added lane and is busy-checked."""
    _want(repo)
    _apply(repo)
    v2 = {"lanes": ["e8", "fusion", "ftmo"], "modes": {"fusion": "fallback", "ftmo": "fallback"}}
    _want(repo, v2)
    _apply(repo)
    (row,) = ds.load_provisional(repo)
    assert row["added_gold_lanes"] == ["ftmo"]

    def busy(lane: str, max_age_s: float = 0) -> tuple[dict[str, Any] | None, str]:
        if lane == "ftmo" and max_age_s == ds.LIVE_LANE_MAX_AGE_S:
            return None, "900s old"
        return {"lane": lane, "positions": [{"ticket": 7}], "orders": []}, "ok"

    _code, doc = _verify(repo, QUIET + timedelta(hours=1), task_info=_ok_before, read_lane=busy)
    assert doc["restored"] == [] and _live(repo) == v2 and "NOT put back" in pages[-1]


def test_the_window_after_a_dst_change_is_on_its_own_days_clock(repo: Path) -> None:
    """v11 audit should-fix 2: Friday 2026-10-30 21:30Z, US clocks go back 2026-11-01. Monday's
    gold asia blackout (06:30 broker, UTC+2 by then) opens 04:30Z, not 03:30Z."""
    start, end = ds.next_window(
        datetime(2026, 10, 30, 21, 30, tzinfo=UTC), ag.load_policy(repo), ag.broker_offset_h
    )
    assert start == datetime(2026, 11, 2, 4, 30, tzinfo=UTC)
    assert end - start == timedelta(hours=1)
