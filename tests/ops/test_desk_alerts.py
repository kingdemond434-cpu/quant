"""The box's alarm through one GitHub issue: transitions only, confirmed, coalesced, a daily digest
at most, a failed delivery retried, and no credential ever in the artifact."""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from libs.ops import desk_alerts as da

T0 = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)
SECRET = "ghp_" + "x" * 36   # a fake token, asserted absent from the artifact


class Route:
    def __init__(self, login: str = "someone-else", fail: bool = False) -> None:
        self.posts: list[str] = []
        self.login, self.fail, self.created = login, fail, 0

    def __call__(self, method: str, path: str, payload: dict[str, Any] | None
                 ) -> tuple[int, Any]:
        if self.fail:
            return 403, None
        if path.startswith("search/"):
            return 200, {"items": []}
        if path == f"repos/{da.REPO}/issues":
            self.created += 1
            return 201, {"number": 42, "html_url": "https://x/42", "node_id": "N"}
        if path == "graphql":
            return 200, {"data": {}}
        if path.endswith("/comments"):
            self.posts.append(str((payload or {}).get("body")))
            return 201, {"html_url": f"https://x/42#c{len(self.posts)}"}
        if path == "user":
            return 200, {"login": self.login}
        return 404, None


def _reading(*failing: str, new: tuple[str, ...] = ()) -> dict[str, Any]:
    checks: dict[str, Any] = {k: {"fail": True, "age_min": 99} for k in failing}
    if new:
        checks["silent"] = {"fail": True, "fence": "RED", "new_silent": list(new)}
    return {"checks": checks, "failing": sorted(set(failing) | ({"silent"} if new else set())),
            "verdict": "FAIL" if failing or new else "OK", "ping": {"status": "NOT_ARMED"}}


def _run(tmp: Path, reading: dict[str, Any], now: datetime, route: Route | None,
         census: list[str] | None = None) -> dict[str, Any]:
    cp = tmp / "SILENT_ORGANS.json"
    if census is None:
        cp.unlink(missing_ok=True)
    else:
        cp.write_text(json.dumps({"organs": [{"organ": o} for o in census]}))
    da.dispatch(reading, out=tmp / "DESK_ALERTS.json", census_path=cp, now=now,
                routes=[] if route is None else [("token", route)],
                extra=lambda m: {"state": "NOT_ARMED"})
    return json.loads((tmp / "DESK_ALERTS.json").read_text())


def test_one_flicker_posts_nothing_and_a_confirmed_red_posts_once(tmp_path: Path) -> None:
    r = Route()
    _run(tmp_path, _reading("disk"), T0, r, [])
    _run(tmp_path, _reading(), T0 + timedelta(minutes=5), r, [])
    assert r.posts == [] and r.created == 0
    _run(tmp_path, _reading("disk"), T0 + timedelta(minutes=10), r, [])
    d = _run(tmp_path, _reading("disk"), T0 + timedelta(minutes=15), r, [])
    assert len(r.posts) == 1 and r.posts[0].startswith("**RED**") and r.created == 1
    assert d["told"] == ["disk"] and d["last_alert"]["kind"] == "RED"
    assert d["issue"]["number"] == 42 and d["verdict"] == "ARMED"
    for m in range(20, 120, 5):           # it stays RED: silence
        _run(tmp_path, _reading("disk"), T0 + timedelta(minutes=m), r, [])
    assert len(r.posts) == 1


def test_recovery_needs_three_clean_beats_then_posts_all_clear(tmp_path: Path) -> None:
    r = Route()
    for m in (0, 5):
        _run(tmp_path, _reading("gateway"), T0 + timedelta(minutes=m), r, [])
    for m in (40, 45):
        _run(tmp_path, _reading(), T0 + timedelta(minutes=m), r, [])
    assert len(r.posts) == 1
    d = _run(tmp_path, _reading(), T0 + timedelta(minutes=50), r, [])
    assert len(r.posts) == 2 and r.posts[1].startswith("**ALL CLEAR**") and d["told"] == []


def test_changes_inside_the_gap_are_coalesced_not_dropped(tmp_path: Path) -> None:
    r = Route()
    for m in (0, 5):
        _run(tmp_path, _reading("disk"), T0 + timedelta(minutes=m), r, [])
    for m in (10, 15):
        d = _run(tmp_path, _reading("disk", "watchdog"), T0 + timedelta(minutes=m), r, [])
    assert len(r.posts) == 1 and d["action"] == "DEFERRED" and d["pending"] == "RED"
    d = _run(tmp_path, _reading("disk", "watchdog"), T0 + timedelta(minutes=35), r, [])
    assert len(r.posts) == 2 and "`watchdog`" in r.posts[1] and d["told"] == ["disk", "watchdog"]


def test_digest_at_most_daily_while_red(tmp_path: Path) -> None:
    r = Route()
    for m in (0, 5):
        _run(tmp_path, _reading("disk"), T0 + timedelta(minutes=m), r, [])
    _run(tmp_path, _reading("disk"), T0 + timedelta(hours=23), r, [])
    assert len(r.posts) == 1
    _run(tmp_path, _reading("disk"), T0 + timedelta(hours=24, minutes=6), r, [])
    _run(tmp_path, _reading("disk"), T0 + timedelta(hours=24, minutes=40), r, [])
    assert len(r.posts) == 2 and r.posts[1].startswith("**Daily digest")


def test_a_new_silent_organ_posts_at_once_and_clears_only_when_the_census_drops_it(
        tmp_path: Path) -> None:
    r = Route()
    _run(tmp_path, _reading(new=("MT5-X",)), T0, r, ["MT5-X"])
    assert len(r.posts) == 1 and "silent:MT5-X" in r.posts[0]
    # next census: AMBER (fence not RED), organ still listed -> still RED, no post
    _run(tmp_path, _reading(), T0 + timedelta(hours=1), r, ["MT5-X"])
    # an unreadable census never clears it
    d = _run(tmp_path, _reading(), T0 + timedelta(hours=2), r, None)
    assert len(r.posts) == 1 and "silent:MT5-X" in d["active"]
    d = _run(tmp_path, _reading(), T0 + timedelta(hours=3), r, [])
    assert len(r.posts) == 2 and d["told"] == []


def test_failed_delivery_keeps_the_transition_and_retries(tmp_path: Path) -> None:
    bad = Route(fail=True)
    for m in (0, 5):
        d = _run(tmp_path, _reading("disk"), T0 + timedelta(minutes=m), bad, [])
    assert d["action"] == "FAILED" and d["told"] == [] and d["verdict"] == "ERROR"
    good = Route()
    d = _run(tmp_path, _reading("disk"), T0 + timedelta(minutes=10), good, [])
    assert d["action"] == "DEFERRED"            # no hammering inside the gap
    d = _run(tmp_path, _reading("disk"), T0 + timedelta(minutes=40), good, [])
    assert len(good.posts) == 1 and d["told"] == ["disk"]


def test_no_route_is_unmeasured_never_clean(tmp_path: Path) -> None:
    for m in (0, 5):
        d = _run(tmp_path, _reading("disk"), T0 + timedelta(minutes=m), None, [])
    assert d["verdict"] == "UNMEASURED" and d["github"]["state"] == "UNMEASURED"
    assert d["told"] == [] and d["pending"] == "RED"


def test_posting_as_the_owner_is_recorded_not_called_notified(tmp_path: Path) -> None:
    r = Route(login=da.OWNER)
    for m in (0, 5):
        d = _run(tmp_path, _reading("disk"), T0 + timedelta(minutes=m), r, [])
    assert len(r.posts) == 1 and d["github"]["notifies_owner"] is False
    assert d["verdict"] == "RECORDED_NOT_NOTIFIED"


def test_the_token_is_read_from_the_environment_and_never_written(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert da.read_token({"GITHUB_TOKEN": f" {SECRET} "}, registry=False) == SECRET
    assert da.read_token({}, registry=False) is None
    monkeypatch.setenv("GITHUB_TOKEN", SECRET)
    r = Route()
    for m in (0, 5):
        _run(tmp_path, _reading("disk"), T0 + timedelta(minutes=m), r, [])
    assert SECRET not in (tmp_path / "DESK_ALERTS.json").read_text()


def test_under_pytest_the_default_routes_are_never_used(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[int] = []
    monkeypatch.setattr(da, "default_routes", lambda: called.append(1) or [])
    for m in (0, 5):
        da.dispatch(_reading("disk"), out=tmp_path / "a.json", census_path=tmp_path / "n",
                    now=T0 + timedelta(minutes=m), extra=lambda m: {"state": "NOT_ARMED"})
    assert called == []


def test_write_is_atomic_and_survives_one_read_only_refusal(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out = tmp_path / "x.json"
    out.write_text('{"old": true}')
    calls: list[int] = []
    real = da.os.replace

    def once(src: Any, dst: Any) -> None:
        calls.append(1)
        if len(calls) == 1:
            raise PermissionError(13, "Access is denied")
        real(src, dst)
    monkeypatch.setattr(da.os, "replace", once)
    da.write_json_atomic(out, {"v": 1})
    assert json.loads(out.read_text()) == {"v": 1} and not (tmp_path / "x.json.tmp").exists()

    def refuse(src: Any, dst: Any) -> None:
        raise PermissionError(13, "Access is denied")
    monkeypatch.setattr(da.os, "replace", refuse)
    with pytest.raises(PermissionError):
        da.write_json_atomic(out, {"v": 2})
    assert json.loads(out.read_text()) == {"v": 1} and not (tmp_path / "x.json.tmp").exists()
