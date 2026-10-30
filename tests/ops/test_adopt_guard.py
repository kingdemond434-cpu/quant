"""The unattended adopter's guard (libs/ops/adopt_guard.py): audited code only, never near a trade
window, and back to the running release on its own -- under a new-risk hold every lane obeys --
when the new one will not run."""

from __future__ import annotations

import importlib
import importlib.util
import json
import os
import re
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from libs.ops import adopt_guard as ag
from libs.ops import new_risk_hold as nrh

ROOT = Path(__file__).resolve().parents[2]
REL = "desks/mt5/data/RELEASE.json"
# 21:00 broker: outside every window and every start margin (the 120-minute margin keeps the
# adopter out of 01:30-04:30Z, 07:30-10:30Z and 11:30-14:30Z in US summer)
QUIET = datetime(2026, 10, 28, 18, 0, tzinfo=UTC)


def summer(_t: datetime) -> int:
    return 3


def winter(_t: datetime) -> int:
    return 2


def _g(repo: Path, *args: str, env: dict[str, str] | None = None, inp: str | None = None) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
        env=env,
        input=inp,
    ).stdout.strip()


def _write(repo: Path, rel: str, text: str) -> None:
    f = repo / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8")


def _commit(repo: Path, msg: str) -> str:
    _g(repo, "add", "-A")
    _g(repo, "commit", "-q", "-m", msg)
    return _g(repo, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A box checkout: code, box state, and a seal commit naming the code."""
    r = tmp_path / "r"
    r.mkdir()
    _g(r, "init", "-q", "-b", "live")
    _g(r, "config", "user.email", "t@t")
    _g(r, "config", "user.name", "t")
    _write(r, "libs/x.py", "X = 1\n")
    _write(r, "libs/y.py", "Y = 1\n")
    _write(r, "desks/mt5/data/state.json", "{}\n")
    _write(r, "desks/mt5/data/sleeves.json", '{"gold": 0.01}\n')
    base = _commit(r, "base")
    _write(r, REL, json.dumps({"code_sha": base}) + "\n")
    _commit(r, "seal")
    return r


def _origin(repo: Path, parent: str, files: dict[str, str | None], msg: str = "o") -> str:
    """A commit on `parent` as origin would carry it, built without touching the box checkout.
    A None value deletes the path."""
    env = {**os.environ, "GIT_INDEX_FILE": str(repo / ".git" / "side-index")}
    _g(repo, "read-tree", parent, env=env)
    for rel, text in files.items():
        if text is None:
            _g(repo, "update-index", "--remove", "--force-remove", rel, env=env)
            continue
        blob = _g(repo, "hash-object", "-w", "--stdin", env=env, inp=text)
        _g(repo, "update-index", "--add", "--cacheinfo", f"100644,{blob},{rel}", env=env)
    tree = _g(repo, "write-tree", env=env)
    return _g(repo, "commit-tree", tree, "-p", parent, "-m", msg, env=env)


def _clear(repo: Path, commit: str, verdict: str = "CLEAR", **extra: object) -> dict[str, Any]:
    row = ag.clear_row(repo, commit, verdict, "reports/audit/2026-10-28/X.md", base=f"{commit}~1")
    row.update(extra)
    return row


def _with_clears(repo: Path, parent: str, *rows: dict[str, Any]) -> str:
    """Origin's next commit: `parent` plus CLEAR/HOLD rows appended to its record."""
    prev = subprocess.run(
        ["git", "-C", str(repo), "show", f"{parent}:{ag.CLEARS_REL}"],
        capture_output=True,
        text=True,
        check=False,
    )
    text = prev.stdout if prev.returncode == 0 else ""
    text += "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows)
    return _origin(repo, parent, {ag.CLEARS_REL: text}, msg="clears")


def _head(repo: Path) -> str:
    return _g(repo, "rev-parse", "HEAD")


# ---------------------------------------------------------------------------------- blackout
@pytest.mark.parametrize(
    ("hhmm", "offset", "margin", "inside"),
    [
        ("03:29", summer, 0, False),  # gold asia = 07:00 broker = 04:00Z in US summer
        ("03:30", summer, 0, True),
        ("04:01", summer, 0, True),
        ("04:29", summer, 0, True),
        ("04:30", summer, 0, False),
        ("01:30", summer, 120, True),
        ("01:29", summer, 120, False),
        ("04:01", winter, 0, False),  # 05:00Z from 2026-11-01: 04:30Z..05:30Z
        ("04:29", winter, 0, False),
        ("04:30", winter, 0, True),
        ("05:01", winter, 0, True),
        ("09:45", summer, 0, True),  # london_am 13:00 broker = 10:00Z
        ("14:10", summer, 0, True),  # afternoon 17:00 broker = 14:00Z
        ("12:00", summer, 0, False),
        ("12:00", summer, 30, False),
    ],
)
def test_blackouts_are_on_the_broker_clock_for_every_gold_window(
    hhmm: str, offset: Any, margin: int, inside: bool
) -> None:
    h, m = map(int, hhmm.split(":"))
    now = datetime(2026, 10, 28, h, m, tzinfo=UTC)
    got = ag.blackout(now, ag.DEFAULT_POLICY, margin_min=margin, offset_h=offset)
    assert (got is not None) is inside, got


def test_the_real_broker_clock_moves_gold_asia_on_november_first() -> None:
    assert ag.broker_offset_h(datetime(2026, 10, 28, 4, tzinfo=UTC)) == 3
    assert ag.broker_offset_h(datetime(2026, 11, 2, 4, tzinfo=UTC)) == 2
    assert ag.blackout(datetime(2026, 11, 2, 5, 1, tzinfo=UTC), ag.DEFAULT_POLICY)
    assert ag.blackout(datetime(2026, 10, 28, 4, 1, tzinfo=UTC), ag.DEFAULT_POLICY)


def test_blackout_wraps_midnight() -> None:
    pol = {"blackouts_broker": [{"window": "w", "from": "23:00", "to": "01:00"}]}

    def utc(_t: datetime) -> int:
        return 0

    assert ag.blackout(datetime(2026, 1, 1, 0, 30, tzinfo=UTC), pol, offset_h=utc)
    assert ag.blackout(datetime(2026, 1, 1, 23, 0, tzinfo=UTC), pol, offset_h=utc)
    assert not ag.blackout(datetime(2026, 1, 1, 1, 0, tzinfo=UTC), pol, offset_h=utc)


# ------------------------------------------------------------------------------------ policy
def test_policy_can_widen_the_guard_but_never_loosen_it(repo: Path) -> None:
    _write(
        repo,
        ag.POLICY_REL,
        json.dumps(
            {
                "blackouts_broker": [],
                "health_wait_s": 10,
                "gateway_alive_s": 900,
                "lane_tasks": ["Extra-Lane"],
            }
        ),
    )
    pol = ag.load_policy(repo)
    assert pol["blackouts_broker"] == ag.DEFAULT_BLACKOUTS
    assert pol["health_wait_s"] == 600
    assert pol["gateway_alive_s"] == 900
    assert pol["lane_tasks"][-1] == "Extra-Lane" and "E8-Gold" in pol["lane_tasks"]


def test_an_unreadable_policy_refuses(repo: Path) -> None:
    _write(repo, ag.POLICY_REL, "{nope")
    with pytest.raises(ag.GuardError):
        ag.load_policy(repo)


# ------------------------------------------------------------------------------------ clears
@pytest.mark.parametrize(
    "line",
    [
        "not json",
        '{"commit": "abc", "verdict": "CLEAR", "report": "reports/audit/a.md", '
        '"paths": {"a": null}}',
        '{"commit": "' + "a" * 40 + '", "verdict": "MAYBE", "report": "reports/audit/a.md"}',
        '{"commit": "' + "a" * 40 + '", "verdict": "CLEAR", "report": "elsewhere.md", '
        '"paths": {"a": null}}',
        '{"commit": "' + "a" * 40 + '", "verdict": "CLEAR", "report": "reports/audit/a.md"}',
        '{"commit": "' + "a" * 40 + '", "verdict": "CLEAR", "report": "reports/audit/../x.md", '
        '"paths": {"a": null}}',
        '{"commit": "' + "a" * 40 + '", "verdict": "CLEAR", "report": "reports/audit/a.md", '
        '"paths": {"../a": null}}',
        '{"commit": "' + "a" * 40 + '", "verdict": "CLEAR", "report": "reports/audit/a.md", '
        '"paths": {"a": "zz"}}',
        '{"commit": "' + "a" * 40 + '", "verdict": "CLEAR", "report": "reports/audit/a.md", '
        '"paths": {"a": null}, "report_sha256": "short"}',
    ],
)
def test_a_malformed_row_refuses_the_whole_file(line: str) -> None:
    with pytest.raises(ag.GuardError):
        ag.parse_clears(line)


def test_a_hold_revokes_by_commit_and_by_blob() -> None:
    a, b = "a" * 40, "b" * 40
    blob1, blob2 = "1" * 40, "2" * 40
    clear = ag.Clear(a, "CLEAR", "reports/audit/a.md", {"p": blob1, "q": blob2})
    assert ag.vouched([clear]) == {("p", blob1), ("q", blob2)}
    # a HOLD on the same commit, in either order, revokes the whole row
    hold_a = ag.Clear(a, "HOLD", "reports/audit/b.md")
    assert ag.vouched([clear, hold_a]) == set() and ag.vouched([hold_a, clear]) == set()
    # a HOLD on ANOTHER commit carrying the same blob revokes that blob only
    hold_b = ag.Clear(b, "HOLD", "reports/audit/c.md", {"p": blob1})
    assert ag.vouched([clear, hold_b]) == {("q", blob2)}


# --------------------------------------------------------------------------------------- pre
def test_unaudited_code_holds_and_audited_code_goes(repo: Path) -> None:
    change = _origin(repo, _head(repo), {"libs/x.py": "X = 2\n"})
    code, doc = ag.pre(repo, change, now=QUIET, offset_h=summer)
    assert code == ag.HOLD and doc["decision"] == "HOLD_UNAUDITED"
    assert doc["uncovered"] == ["libs/x.py"]

    target = _with_clears(repo, change, _clear(repo, change))
    code, doc = ag.pre(repo, target, now=QUIET, offset_h=summer)
    assert code == ag.GO, doc
    assert doc["governed_paths"] == ["libs/x.py"]


def test_a_later_hold_beats_the_clear(repo: Path) -> None:
    change = _origin(repo, _head(repo), {"libs/x.py": "X = 2\n"})
    t1 = _with_clears(repo, change, _clear(repo, change))
    target = _with_clears(
        repo, t1, {"commit": change, "verdict": "HOLD", "report": "reports/audit/2026-10-28/Y.md"}
    )
    code, doc = ag.pre(repo, target, now=QUIET, offset_h=summer)
    assert code == ag.HOLD and doc["decision"] == "HOLD_UNAUDITED"


def test_a_hold_on_v2_revokes_v1s_clear_of_the_same_blob(repo: Path) -> None:
    head = _head(repo)
    v1 = _origin(repo, head, {"libs/x.py": "X = 2\n"}, msg="v1")
    v2 = _origin(repo, head, {"libs/x.py": "X = 2\n", "libs/y.py": "Y = 2\n"}, msg="v2")
    target = _with_clears(repo, v1, _clear(repo, v1), _clear(repo, v2, "HOLD"))
    code, doc = ag.pre(repo, target, now=QUIET, offset_h=summer)
    assert code == ag.HOLD and doc["uncovered"] == ["libs/x.py"]


def test_content_nobody_cleared_holds_even_if_the_path_was_cleared(repo: Path) -> None:
    change = _origin(repo, _head(repo), {"libs/x.py": "X = 2\n"})
    t1 = _with_clears(repo, change, _clear(repo, change))
    target = _origin(repo, t1, {"libs/x.py": "X = 3\n"}, msg="unreviewed edit")
    code, doc = ag.pre(repo, target, now=QUIET, offset_h=summer)
    assert code == ag.HOLD and doc["uncovered"] == ["libs/x.py"]


@pytest.mark.parametrize(
    ("rel", "governed"),
    [
        ("desks/mt5/data/sleeves.json", True),  # money config
        (ag.POLICY_REL, True),  # the guard's own policy
        ("desks/mt5/data/tools/helper.py", True),  # a script by its suffix, wherever it sits
        ("desks/mt5/data/ALLOCATOR_SOVEREIGN.json", True),
        ("desks/mt5/reports/anything.json", False),  # evidence
        ("reports/audit/2026-10-28/X.md", False),
        ("desks/mt5/data/live_ledger.jsonl", False),  # the box's own runtime record
    ],
)
def test_what_origin_changes_is_governed_unless_it_is_evidence(
    repo: Path, rel: str, governed: bool
) -> None:
    target = _origin(repo, _head(repo), {rel: '{"changed": 1}\n'})
    code, doc = ag.pre(repo, target, now=QUIET, offset_h=summer)
    if governed:
        assert code == ag.HOLD and doc["uncovered"] == [rel], doc
    else:
        assert code == ag.GO, doc


def test_state_the_box_changed_itself_is_the_boxs(repo: Path) -> None:
    head = _head(repo)
    target = _origin(repo, head, {"desks/mt5/data/state.json": '{"origin": 1}\n'})
    _write(repo, "desks/mt5/data/state.json", '{"box": 1}\n')
    _commit(repo, "box state")
    assert ag.pre(repo, target, now=QUIET, offset_h=summer)[0] == ag.GO


def test_a_gitlink_never_stands_where_a_cleared_deletion_was(repo: Path) -> None:
    head = _head(repo)
    gone = _origin(repo, head, {"libs/y.py": None}, msg="delete y")
    t1 = _with_clears(repo, gone, _clear(repo, gone))
    assert ag.pre(repo, t1, now=QUIET, offset_h=summer)[0] == ag.GO
    env = {**os.environ, "GIT_INDEX_FILE": str(repo / ".git" / "side-index")}
    _g(repo, "read-tree", t1, env=env)
    _g(repo, "update-index", "--add", "--cacheinfo", f"160000,{head},libs/y.py", env=env)
    sub = _g(repo, "commit-tree", _g(repo, "write-tree", env=env), "-p", t1, "-m", "s", env=env)
    code, doc = ag.pre(repo, sub, now=QUIET, offset_h=summer)
    assert code == ag.HOLD and doc["uncovered"] == ["libs/y.py"]


def test_an_edited_clear_record_is_refused(repo: Path) -> None:
    change = _origin(repo, _head(repo), {"libs/x.py": "X = 2\n"})
    t1 = _with_clears(
        repo, change, {"commit": change, "verdict": "HOLD", "report": "reports/audit/a/Y.md"}
    )
    target = _origin(repo, t1, {ag.CLEARS_REL: json.dumps(_clear(repo, change)) + "\n"})
    with pytest.raises(ag.GuardError, match="not a prefix"):
        ag.pre(repo, target, now=QUIET, offset_h=summer)


def test_blackout_holds_before_anything_is_read(repo: Path) -> None:
    at = datetime(2026, 10, 28, 3, 0, tzinfo=UTC)
    code, doc = ag.pre(repo, "no-such-ref", now=at, offset_h=summer)
    assert code == ag.HOLD and doc["decision"] == "HOLD_BLACKOUT"


def test_a_garbled_rollback_record_refuses(repo: Path) -> None:
    _write(repo, ag.ROLLBACKS_REL, '{"bad": "x"}\n')
    with pytest.raises(ag.GuardError, match="blobs"):
        ag.load_rollbacks(repo)
    _write(repo, ag.ROLLBACKS_REL, "garbage\n")
    with pytest.raises(ag.GuardError):
        ag.load_rollbacks(repo)


# ---------------------------------------------------------------------------------- rollback
def _adopt(repo: Path, target: str) -> None:
    """What Adopt-Release + the seal do, in miniature: land the target, seal it, and the box
    writes its own state on top."""
    _g(repo, "merge", "-q", "--no-edit", target)
    _write(repo, REL, json.dumps({"code_sha": _head(repo)}) + "\n")
    _write(repo, "desks/mt5/data/state.json", '{"box": 1}\n')
    _commit(repo, "seal + box state")


def test_rollback_restores_code_and_seal_keeps_state_and_blocks_readoption(repo: Path) -> None:
    before = _head(repo)
    bad = _origin(
        repo, before, {"libs/x.py": "X = 2\n", "libs/new.py": "N = 1\n", "libs/y.py": None}
    )
    target = _with_clears(repo, bad, _clear(repo, bad))
    assert ag.pre(repo, target, now=QUIET, offset_h=summer)[0] == ag.GO
    _adopt(repo, target)

    code, doc = ag.rollback(repo, before, bad=target, why="health failed")
    assert code == ag.GO, doc
    assert (repo / "libs/x.py").read_text() == "X = 1\n"
    assert (repo / "libs/y.py").read_text() == "Y = 1\n"
    assert not (repo / "libs/new.py").exists()
    assert ag.sealed_code_sha(repo) == ag.sealed_code_sha(repo, before)
    assert (repo / "desks/mt5/data/state.json").read_text() == '{"box": 1}\n'
    assert _g(repo, "status", "--porcelain", "--", "libs") == ""
    assert [r["bad"] for r in ag.load_rollbacks(repo)] == [target]

    code, doc = ag.pre(repo, target, now=QUIET, offset_h=summer)
    assert code == ag.HOLD and doc["decision"] == "HOLD_ROLLED_BACK"

    lifted = _with_clears(repo, target, _clear(repo, bad, lifts_rollback=[target]))
    assert ag.pre(repo, lifted, now=QUIET, offset_h=summer)[0] == ag.GO


def test_rollback_undoes_half_written_and_created_files(repo: Path) -> None:
    before = _head(repo)
    bad = _origin(repo, before, {"libs/x.py": "X = 2\n", "libs/new.py": "N = 1\n"})
    # Adopt-Release died mid-write: one tracked file rewritten, one new file created, no commit
    _write(repo, "libs/x.py", "X = 2\n")
    _write(repo, "libs/new.py", "N = 1\n")
    _write(repo, "libs/mine.py", "not the adoption's\n")
    code, doc = ag.rollback(repo, before, bad=bad, why="partial")
    assert code == ag.GO, doc
    assert (repo / "libs/x.py").read_text() == "X = 1\n"
    assert not (repo / "libs/new.py").exists()
    assert (repo / "libs/mine.py").exists()  # never the adoption's, never touched
    assert _head(repo) == before  # nothing committed: the tree already matched


def test_nothing_to_roll_back_commits_nothing(repo: Path) -> None:
    head = _head(repo)
    code, doc = ag.rollback(repo, head, bad=head, why="x")
    assert code == ag.GO and doc["decision"] == "NOTHING_TO_ROLL_BACK"
    assert _head(repo) == head


# ------------------------------------------------------------------------------------- smoke
def test_smoke_reports_the_failing_module(repo: Path) -> None:
    for rel in ag.DEFAULT_POLICY["smoke_files"]:
        _write(repo, rel, "")

    def runner(cmd: list[str], **kw: Any) -> subprocess.CompletedProcess[str]:
        bad = cmd[-2].endswith("e8_gold.py")
        return subprocess.CompletedProcess(
            cmd, 1 if bad else 0, "", "ImportError: libs" if bad else ""
        )

    code, doc = ag.smoke(repo, runner=runner)
    assert code == ag.UNHEALTHY and "e8_gold.py" in doc["reason"]


def test_smoke_runs_the_box_prestart_check(repo: Path) -> None:
    for rel in ag.DEFAULT_POLICY["smoke_files"]:
        _write(repo, rel, "")
    _write(repo, "desks/mt5/scripts/prestart_check.py", "")

    def runner(cmd: list[str], **kw: Any) -> subprocess.CompletedProcess[str]:
        rc = 1 if cmd[-1].endswith("prestart_check.py") else 0
        return subprocess.CompletedProcess(cmd, rc, "DO NOT START THE GATEWAY", "")

    code, doc = ag.smoke(repo, runner=runner)
    assert code == ag.UNHEALTHY and "DO NOT START" in doc["reason"]


def test_smoke_imports_real_files_without_running_main(repo: Path, tmp_path: Path) -> None:
    marker = tmp_path / "ran"
    for rel in ag.DEFAULT_POLICY["smoke_files"]:
        _write(repo, rel, f"if __name__ == '__main__':\n    open({str(marker)!r}, 'w')\n")
    code, doc = ag.smoke(repo)
    assert code == ag.GO, doc
    assert not marker.exists()


# ------------------------------------------------------------------------------------ health
def _clock(start: datetime) -> tuple[Any, Any]:
    t = [start]

    def now() -> datetime:
        return t[0]

    def sleep(s: float) -> None:
        t[0] += timedelta(seconds=s)

    return now, sleep


def _ok(sealed: str = "h") -> Any:
    def ident(_root: Path) -> dict[str, Any]:
        return {"verdict": "OK", "allows_new_risk": True, "release_sha": sealed, "reason": "r"}

    return ident


def _no_tasks(_name: str) -> None:
    return None


def _stamp(repo: Path, **doc: Any) -> None:
    _write(repo, ag.GATEWAY_LOADED_REL, json.dumps(doc))


def test_health_waits_for_the_identity_then_passes(repo: Path) -> None:
    now, sleep = _clock(QUIET)
    calls = {"n": 0}

    def ident(_root: Path) -> dict[str, Any]:
        calls["n"] += 1
        ok = calls["n"] >= 3
        return {
            "verdict": "OK" if ok else "REFUSED",
            "allows_new_risk": ok,
            "release_sha": "h" if ok else "old",
            "reason": "r",
        }

    code, doc = ag.health(
        repo,
        "h",
        QUIET,
        gateway_expected=False,
        identity=ident,
        task_info=_no_tasks,
        sleep=sleep,
        clock=now,
    )
    assert code == ag.GO and doc["decision"] == "HEALTHY"


def test_a_gateway_still_on_the_old_code_is_not_healthy(repo: Path) -> None:
    now, sleep = _clock(QUIET)
    before = (QUIET - timedelta(minutes=5)).isoformat()
    _stamp(repo, started_at=before, release_sha="h", last_pass_at=QUIET.isoformat())
    code, doc = ag.health(
        repo,
        "h",
        QUIET,
        gateway_expected=True,
        identity=_ok(),
        task_info=_no_tasks,
        sleep=sleep,
        clock=now,
    )
    assert code == ag.UNHEALTHY and "started since the recycle" in doc["reason"]


def test_a_gateway_that_restarted_under_another_seal_is_not_healthy(repo: Path) -> None:
    now, sleep = _clock(QUIET)
    s = QUIET + timedelta(seconds=30)
    _stamp(
        repo,
        started_at=s.isoformat(),
        release_sha="old",
        last_pass_at=(s + timedelta(seconds=60)).isoformat(),
    )
    code, doc = ag.health(
        repo,
        "h",
        QUIET,
        gateway_expected=True,
        identity=_ok(),
        task_info=_no_tasks,
        sleep=sleep,
        clock=now,
    )
    assert code == ag.UNHEALTHY and "started under release" in doc["reason"]


def test_a_gateway_that_loaded_the_seal_and_passed_is_healthy(repo: Path) -> None:
    now, sleep = _clock(QUIET)
    s = QUIET + timedelta(seconds=30)
    _stamp(
        repo,
        started_at=s.isoformat(),
        release_sha="h",
        last_pass_at=(s + timedelta(seconds=60)).isoformat(),
    )
    code, doc = ag.health(
        repo,
        "h",
        QUIET,
        gateway_expected=True,
        identity=_ok(),
        task_info=_no_tasks,
        sleep=sleep,
        clock=now,
    )
    assert code == ag.GO, doc


def test_a_failed_lane_is_unhealthy_at_once_and_idle_lanes_are_only_reported(repo: Path) -> None:
    after = (QUIET + timedelta(minutes=1)).isoformat()
    infos = {
        "E8-Executor": {"state": "Ready", "last": after, "result": 0},
        "E8-Gold": {"state": "Disabled", "last": after, "result": 1},
        "MT5-FTMO-Follower": {"state": "Ready", "last": after, "result": 1},
    }
    slept: list[float] = []
    code, doc = ag.health(
        repo,
        "h",
        QUIET,
        gateway_expected=False,
        identity=_ok(),
        task_info=infos.get,
        sleep=slept.append,
    )
    assert code == ag.UNHEALTHY and not slept
    assert "MT5-FTMO-Follower" in doc["reason"]
    assert doc["lanes"]["E8-Gold"] == "DISABLED"

    infos["MT5-FTMO-Follower"] = {"state": "Ready", "last": QUIET.isoformat(), "result": 1}
    code, doc = ag.health(
        repo, "h", QUIET, gateway_expected=False, identity=_ok(), task_info=infos.get
    )
    assert code == ag.GO and doc["lanes"]["MT5-FTMO-Follower"] == "NOT_RUN_SINCE"


def test_a_single_look_does_not_wait(repo: Path) -> None:
    slept: list[float] = []
    code, _ = ag.health(
        repo,
        "h",
        QUIET,
        gateway_expected=True,
        identity=_ok(),
        task_info=_no_tasks,
        sleep=slept.append,
        wait_s=0,
    )
    assert code == ag.UNHEALTHY and not slept


# --------------------------------------------------------------------------- new-risk hold
def test_holds_stand_side_by_side_and_each_writer_lifts_only_its_own(tmp_path: Path) -> None:
    assert nrh.reason(tmp_path) is None
    assert nrh.place("person", by="zuck", root=tmp_path)
    assert ag.hold_new_risk(tmp_path, "adopting")  # written even though a person's hold stands
    assert ag.hold_new_risk(tmp_path, "again")  # in force, not overwritten
    why = nrh.reason(tmp_path) or ""
    assert "zuck" in why and ag.BY in why and "again" not in why
    assert ag.own_hold_since(tmp_path) is not None
    assert nrh.lift(by="zuck", root=tmp_path)
    assert ag.BY in (nrh.reason(tmp_path) or "")  # lifting the person's leaves the guard's
    assert ag.lift_hold(tmp_path) and nrh.reason(tmp_path) is None
    with pytest.raises(ValueError):
        nrh.place("x", by="../escape", root=tmp_path)


def test_an_unreadable_hold_still_holds(tmp_path: Path) -> None:
    for f in (tmp_path / nrh.HOLD_REL, nrh.hold_file("someone", tmp_path)):
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("{garbled", encoding="utf-8")
        assert "unreadable" in (nrh.reason(tmp_path) or "")
        f.unlink()
    (tmp_path / nrh.HOLD_REL).write_text('{"by": "zuck", "why": "hand"}', encoding="utf-8")
    assert not ag.lift_hold(tmp_path) and "hand" in (nrh.reason(tmp_path) or "")


@pytest.mark.parametrize(
    ("rel", "before"),
    [
        ("desks/mt5/mt5desk/gateway.py", "if not NEW_RISK_OK:"),
        ("desks/mt5/prop/e8_executor.py", "if armed:"),
        ("desks/mt5/prop/e8_gold.py", "if blocker is not None:"),
        ("desks/mt5/prop/ftmo_follower.py", "def _place_locked("),
    ],
)
def test_every_lane_that_opens_risk_reads_the_hold_first(rel: str, before: str) -> None:
    src = (ROOT / rel).read_text(encoding="utf-8")
    at = src.index("_nrh.reason()")
    assert before in src[at:], f"{rel}: the hold is read after the last {before!r}"


# ------------------------------------------------------------------------------------- CLI
def _cli() -> Any:
    spec = importlib.util.spec_from_file_location(
        "adopt_guard_cli", ROOT / "scripts/adopt_guard.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_cli_rollback_holds_first_and_only_a_healthy_check_lifts(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cli = _cli()
    pages: list[str] = []
    monkeypatch.setattr(ag, "page", lambda _root, msg: pages.append(msg))
    seen: dict[str, Any] = {}

    def rollback(root: Path, to: str, *, bad: str, why: str) -> tuple[int, dict[str, Any]]:
        seen["held_during"] = nrh.reason(root)
        return ag.GO, {"decision": "ROLLED_BACK"}

    monkeypatch.setattr(ag, "rollback", rollback)
    head = _head(repo)
    argv = ["--root", str(repo), "rollback", "--to", head, "--bad", head, "--why", "w"]
    assert cli.main(argv) == 0
    assert seen["held_during"] and nrh.reason(repo) and not pages

    since = ["--since", QUIET.isoformat(), "--gateway-expected", "0"]
    monkeypatch.setattr(ag, "health", lambda *a, **k: (ag.UNHEALTHY, {"reason": "no"}))
    assert (
        cli.main(["--root", str(repo), "health", "--sealed-at", "HEAD", *since, "--page-on-fail"])
        == ag.UNHEALTHY
    )
    assert nrh.reason(repo) and pages

    monkeypatch.setattr(ag, "health", lambda *a, **k: (ag.GO, {"decision": "HEALTHY"}))
    assert cli.main(["--root", str(repo), "heal", "--gateway-expected", "0"]) == 0
    assert nrh.reason(repo) is None
    assert cli.main(["--root", str(repo), "heal", "--gateway-expected", "0"]) == 0


def test_cli_rollback_that_crashes_keeps_the_hold_and_pages(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cli = _cli()
    pages: list[str] = []
    monkeypatch.setattr(ag, "page", lambda _root, msg: pages.append(msg))

    def boom(*a: Any, **k: Any) -> Any:
        raise OSError("disk")

    monkeypatch.setattr(ag, "rollback", boom)
    head = _head(repo)
    argv = ["--root", str(repo), "rollback", "--to", head, "--bad", head, "--why", "w"]
    assert cli.main(argv) == ag.ROLLBACK_FAILED
    assert nrh.reason(repo) and pages and "FAILED" in pages[0]


# ------------------------------------------------------------------------------- the adopter
PS = (ROOT / "desks/mt5/scripts/Adopt-And-Seal.ps1").read_text(encoding="utf-8")


def test_adopt_and_seal_runs_the_guard_in_order() -> None:
    order = [
        'Write-GitWriterWitness -Script "Adopt-And-Seal.ps1"',
        "try { $script:HeadBefore = (git -C $RepoRoot rev-parse HEAD",
        'Invoke-AdoptGuard @("heal"',
        'Invoke-AdoptGuard @("pre"',
        "\n$script:Adopted = $true",
        "$adoptOut = @(& powershell.exe",
        'Invoke-AdoptGuard @("smoke")',
        'Invoke-AdoptGuard @("blackout", "--margin-min", "30")',
        "release.seal(by='Adopt-And-Seal')",
        "$script:Recycled = $true",
        'Invoke-AdoptGuard @("health", "--sealed", $head',
        'Done 0 "sealed"',
    ]
    at = [PS.rindex(o) if o.startswith("try { $script:HeadBefore") else PS.index(o) for o in order]
    assert at == sorted(at), dict(zip(order, at, strict=True))
    assert "--gateway-was-alive" not in PS and "GATEWAY_PAUSED" not in PS


def test_every_failure_after_the_first_write_goes_back() -> None:
    after = PS[PS.index("\n$script:Adopted = $true") :]
    stages = re.findall(r'\bDone \S+ "([^"]+)"', after)
    assert set(stages) <= {"target-unsealed", "already-sealed", "accepts-nothing-to-seal", "sealed"}
    for stage in (
        "adopt-release-partial",
        "ledger-handoff-failed",
        "smoke-failed",
        "dirty-code-path",
        "seal-failed",
        "seal-stage-failed",
        "seal-stage-contaminated",
        "seal-branch-unreadable",
        "seal-write-tree-failed",
        "seal-commit-tree-failed",
        "seal-update-ref-failed",
        "unhealthy",
    ):
        assert re.search(rf'Undo-Adoption .*"{stage}"', after), stage


def test_the_way_back_rechecks_the_restored_release() -> None:
    undo = PS[
        PS.index("function Undo-Adoption") : PS.index("if (-not (Test-Path $script:GuardScript))")
    ]
    order = ['@("rollback"', "loaded-since", "GATEWAY_RECYCLE", '@("health", "--sealed-at", "HEAD"']
    at = [undo.index(o) for o in order]
    assert at == sorted(at)
    assert "--page-on-fail" in undo and 'Done 12 "$stage-rolled-back-unhealthy"' in undo


def test_the_crlf_script_stays_crlf() -> None:
    raw = (ROOT / "desks/mt5/scripts/Adopt-And-Seal.ps1").read_bytes()
    assert raw.count(b"\r\n") == raw.count(b"\n")


# ------------------------------------------------------------------------------ v3 (audit v2)
def test_code_the_box_committed_without_a_seal_still_needs_a_clear(repo: Path) -> None:
    """Probe 16: a box session commits code unsealed; origin's target carries the same blob.
    HEAD already has it, the seal does not -- the CLEAR check must still run."""
    before = _head(repo)
    change = _origin(repo, before, {"libs/x.py": "X = 9\n"})
    _g(repo, "merge", "-q", "--ff-only", change)  # the box branch now carries it, unsealed
    code, doc = ag.pre(repo, change, now=QUIET, offset_h=summer)
    assert code == ag.HOLD and doc["uncovered"] == ["libs/x.py"], doc


@pytest.mark.parametrize("rel", sorted(ag.MONEY_EVIDENCE))
def test_evidence_files_the_lanes_size_from_are_governed(repo: Path, rel: str) -> None:
    target = _origin(repo, _head(repo), {rel: '{"changed": 1}\n'})
    code, doc = ag.pre(repo, target, now=QUIET, offset_h=summer)
    assert code == ag.HOLD and doc["uncovered"] == [rel]


def test_a_partial_adoptions_staged_leftovers_do_not_fail_the_rollback(repo: Path) -> None:
    before = _head(repo)
    bad = _origin(repo, before, {"libs/x.py": "X = 2\n"})
    _write(repo, "libs/x.py", "X = 2\n")
    _write(repo, "desks/mt5/data/state.json", '{"chunk": 1}\n')
    _g(repo, "add", "--", "libs/x.py", "desks/mt5/data/state.json")  # Adopt-Release's chunks
    code, doc = ag.rollback(repo, before, bad=bad, why="partial")
    assert code == ag.GO, doc
    assert (repo / "libs/x.py").read_text() == "X = 1\n"
    assert (repo / "desks/mt5/data/state.json").read_text() == '{"chunk": 1}\n'  # on disk, kept
    assert _g(repo, "diff", "--cached", "--name-only") == ""


def test_cli_hold_and_lift_and_a_stuck_hold_pages(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cli = _cli()
    pages: list[str] = []
    monkeypatch.setattr(ag, "page", lambda _root, msg: pages.append(msg))
    assert cli.main(["--root", str(repo), "hold", "--why", "adopting", "--run", "r1"]) == 0
    assert ag.own_hold_since(repo) is not None
    monkeypatch.setattr(ag, "health", lambda *a, **k: (ag.UNHEALTHY, {"reason": "no"}))
    assert cli.main(["--root", str(repo), "heal", "--gateway-expected", "0"]) == ag.UNHEALTHY
    assert not pages  # young hold: the next hour may still heal it
    f = nrh.hold_file(ag.BY, repo)
    f.write_text(json.dumps({"by": ag.BY, "at": "2026-01-01T00:00:00+00:00", "why": "old"}))
    assert cli.main(["--root", str(repo), "heal", "--gateway-expected", "0"]) == ag.UNHEALTHY
    assert pages and "held on every lane since 2026-01-01" in pages[0]
    # the hold was rewritten without r1's name: a nothing-landed lift by r1 leaves it standing
    assert cli.main(["--root", str(repo), "lift", "--run", "r1"]) == 0
    assert ag.own_hold_since(repo) is not None
    assert ag.lift_hold(repo) and ag.own_hold_since(repo) is None  # a passing health check may


def test_the_hold_goes_up_before_the_first_write_and_comes_down_only_where_nothing_landed() -> None:
    hold = PS.index('Invoke-AdoptGuard @("hold"')
    assert hold < PS.index("\n$script:Adopted = $true") < PS.index("$adoptOut = @(& powershell.exe")
    assert 'Done 8 "hold-unwritable"' in PS[hold : hold + 400]
    assert '"--run", $script:RunId' in PS[hold : hold + 60]
    # the hold is skipped only on an explicit "nothing governed changes"; a missing answer holds
    assert "if ($pre.Doc -and $pre.Doc.needs_hold -eq $false)" in PS[hold - 600 : hold]
    lifts = [m.start() for m in re.finditer(r'Invoke-AdoptGuard @\("lift"', PS)]
    assert len(lifts) == 2 and all('"--run", $script:RunId' in PS[at : at + 60] for at in lifts)
    lift_fn = PS[PS.index("function Lift-IfClean") : lifts[0] + 80]
    assert lift_fn.index("Get-DirtyCode") < lift_fn.index("Undo-Adoption") < lift_fn.index("lift")
    assert 'Done 7 "target-unsealed"' in PS[lifts[1] : lifts[1] + 160]
    for stage in ("already-sealed", "accepts-nothing-to-seal"):
        at = PS.index(f'Lift-IfClean "{stage}"')
        assert f'Done 0 "{stage}"' in PS[at : at + 200]


def test_a_gold_retry_waits_on_the_hold_and_is_billed() -> None:
    src = (ROOT / "desks/mt5/prop/e8_gold.py").read_text(encoding="utf-8")
    retry = src[src.index("def _retry_failed_legs") :]
    retry = retry[: retry.index("\ndef ", 10)]
    assert retry.index("_nrh.reason()") < retry.index("venue.quote(SYMBOL)")
    assert '("adopt_new_risk_hold", f"retry held: {adopt_hold}"' in retry


def test_the_hold_is_a_billed_veto_on_every_ledger() -> None:
    import sys

    sys.path.insert(0, str(ROOT / "desks" / "mt5"))
    from mt5desk import fusion_rails

    mg = importlib.import_module("research.missed_growth")

    assert "adopt_new_risk_hold" in fusion_rails.RAILS
    assert "adopt_new_risk_hold" in mg.FUSION_RAIL_NAMES
    assert "adopt_new_risk_hold" in mg._E8_BILLED_RAILS
    gw = (ROOT / "desks/mt5/mt5desk/gateway.py").read_text(encoding="utf-8")
    assert '_hold_rails.line_once("adopt_new_risk_hold"' in gw
    ex = (ROOT / "desks/mt5/prop/e8_executor.py").read_text(encoding="utf-8")
    assert '"RAIL_BLOCKED", "adopt_new_risk_hold", _hold' in ex


def test_the_resident_stamps_its_whole_identity_every_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sys

    sys.path.insert(0, str(ROOT / "desks" / "mt5" / "research"))
    sys.path.insert(0, str(ROOT / "desks" / "mt5"))
    gr = importlib.import_module("gateway_resident")

    monkeypatch.setattr(gr, "LOADED", tmp_path / "GATEWAY_LOADED.json")
    ident = {"pid": 7, "started_at": "2026-10-28T06:00:00+00:00", "release_sha": "a" * 40}
    monkeypatch.setattr(gr, "LOADED", tmp_path / "missing" / "GATEWAY_LOADED.json")
    assert not gr._stamp_loaded(ident, last_pass_at=None)  # the start stamp is lost ...
    monkeypatch.setattr(gr, "LOADED", tmp_path / "GATEWAY_LOADED.json")
    assert gr._stamp_loaded(ident, last_pass_at="2026-10-28T06:01:00+00:00")  # ... and repaired
    doc = json.loads((tmp_path / "GATEWAY_LOADED.json").read_text())
    assert doc == {**ident, "last_pass_at": "2026-10-28T06:01:00+00:00"}


# ------------------------------------------------------------------------- v5 (audit HOLD on v3)
def test_a_nothing_landed_lift_never_lifts_a_hold_left_by_a_failed_rollback(repo: Path) -> None:
    """MF1: place() reports True over an existing hold; only the run that wrote it may lift it."""
    assert ag.hold_new_risk(repo, "rollback of abc FAILED")  # no run: a rollback's hold
    assert ag.hold_new_risk(repo, "adopting x", run="r2")  # stands already; r2 wrote nothing
    assert not ag.lift_hold(repo, run="r2")
    assert ag.own_hold_since(repo) is not None
    assert ag.lift_hold(repo)  # health: proof the release runs


def test_a_run_lifts_its_own_hold(repo: Path) -> None:
    assert ag.hold_new_risk(repo, "adopting x", run="r3")
    assert not ag.lift_hold(repo, run="r4")
    assert ag.lift_hold(repo, run="r3") and ag.own_hold_since(repo) is None


def test_any_file_in_the_hold_folder_holds(repo: Path) -> None:
    d = repo / nrh.HOLD_DIR_REL
    d.mkdir(parents=True)
    (d / "manual.txt").write_text("stop")
    assert nrh.reason(repo) is not None


def test_heal_accepts_the_running_gateway_on_the_sealed_release(repo: Path) -> None:
    """MF2: nothing restarts a resident, so heal reads a pass after the hold under the seal."""
    held = datetime(2026, 10, 28, 6, 0, tzinfo=UTC)
    stamp = {
        "started_at": (held - timedelta(days=2)).isoformat(),
        "release_sha": "a" * 40,
        "last_pass_at": (held + timedelta(minutes=1)).isoformat(),
    }
    _write(repo, ag.GATEWAY_LOADED_REL, json.dumps(stamp))
    assert ag.loaded_problem(repo, "a" * 40, held) is not None  # an adoption still needs a restart
    assert ag.loaded_problem(repo, "a" * 40, held, running_ok=True) is None
    assert ag.loaded_problem(repo, "b" * 40, held, running_ok=True) is not None
    stamp["last_pass_at"] = (held - timedelta(minutes=1)).isoformat()
    _write(repo, ag.GATEWAY_LOADED_REL, json.dumps(stamp))
    assert ag.loaded_problem(repo, "a" * 40, held, running_ok=True) is not None


def test_heal_never_lifts_over_half_written_code(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cli = _cli()
    assert ag.hold_new_risk(repo, "adopting x", run="r5")
    monkeypatch.setattr(ag, "health", lambda *a, **k: (ag.GO, {"decision": "HEALTHY"}))
    _write(repo, "libs/x.py", "X = 2  # half-written\n")
    assert cli.main(["--root", str(repo), "heal", "--gateway-expected", "0"]) == ag.UNHEALTHY
    assert ag.own_hold_since(repo) is not None
    _g(repo, "checkout", "--", "libs/x.py")
    assert cli.main(["--root", str(repo), "heal", "--gateway-expected", "0"]) == ag.GO
    assert ag.own_hold_since(repo) is None


def test_pre_asks_for_the_hold_only_when_something_governed_changes(repo: Path) -> None:
    evidence = _origin(repo, _head(repo), {"desks/mt5/reports/x.json": "{}"})
    code, doc = ag.pre(repo, evidence, now=QUIET, offset_h=summer)
    assert code == ag.GO and doc["needs_hold"] is False
    change = _origin(repo, _head(repo), {"libs/x.py": "X = 3\n"})
    cleared = _with_clears(repo, change, _clear(repo, change))
    code, doc = ag.pre(repo, cleared, now=QUIET, offset_h=summer)
    assert code == ag.GO and doc["needs_hold"] is True


def test_heal_runs_first_and_the_code_roots_exist_before_they_are_used() -> None:
    assert PS.index('Invoke-AdoptGuard @("heal"') < PS.index("release_promotion.py")
    assert PS.index("$releaseCodePaths = @(") < PS.index("function Get-DirtyCode")
    roots = re.search(r"\$releaseCodePaths = @\((.*?)\)", PS, re.S)
    assert roots is not None
    assert tuple(re.findall(r'"([^"]+)"', roots.group(1))) == ag.CODE_ROOTS


def test_the_per_pass_gateway_writes_the_load_stamp() -> None:
    src = (ROOT / "desks/mt5/research/run_gateway_loop.py").read_text(encoding="utf-8")
    assert src.index("_STARTED_AT = ") < src.index("from mt5desk import gateway")
    assert src.index("_RELEASE_AT_START = ") < src.index("from mt5desk import gateway")
    main = src[src.index('if __name__ == "__main__":') :]
    assert "if _PASS_DONE:" in main and "_stamp_loaded()" in main
    body = src[src.index("def main()") : src.index("def _stamp_loaded")]
    assert body.index("gateway.main()") < body.index(
        "_PASS_DONE = gateway.STATE.stat().st_mtime >= _STARTED_EPOCH"
    )


def test_the_hold_goes_up_when_the_target_rewrites_code_the_box_committed(repo: Path) -> None:
    """v6 should-fix: nothing governed against the seal, but the lanes run HEAD's code."""
    sealed = _head(repo)
    _write(repo, "libs/x.py", "X = 5  # a box session's own commit\n")
    _commit(repo, "box")
    target = _origin(repo, sealed, {"desks/mt5/reports/x.json": "{}"})
    code, doc = ag.pre(repo, target, now=QUIET, offset_h=summer)
    assert code == ag.GO and doc["needs_hold"] is True, doc


def test_a_new_untracked_code_file_is_half_written_code(repo: Path) -> None:
    assert ag.code_dirty(repo) == []
    _write(repo, "libs/new_module.py", "Z = 1\n")
    assert ag.code_dirty(repo) == ["libs/new_module.py"]  # no record: every one counts


def test_strays_already_there_when_the_hold_went_up_never_keep_it_up(repo: Path) -> None:
    """Desk health 2026-10-28: the box carries 14 uncommitted code files of its own sessions."""
    _write(repo, "scripts/stray.py", "S = 1\n")
    _write(repo, "desks/mt5/data/E8_ARMED", "1")  # state is never code
    assert ag.hold_new_risk(repo, "adopting", run="r1")
    assert ag.code_dirty(repo) == []
    _write(repo, "libs/landed_half_way.py", "H = 1\n")  # written by the adoption
    assert ag.code_dirty(repo) == ["libs/landed_half_way.py"]
    # a second hold while the first stands keeps the first record
    assert ag.hold_new_risk(repo, "again", run="r2")
    assert ag.code_dirty(repo) == ["libs/landed_half_way.py"]
    (repo / ag.UNTRACKED_BASELINE_REL).write_text("{half")
    assert ag.code_dirty(repo) == ["libs/landed_half_way.py", "scripts/stray.py"]


def test_policy_adds_gold_lane_task_names_but_never_drops_one(repo: Path) -> None:
    _write(
        repo,
        ag.POLICY_REL,
        json.dumps({"gold_lane_tasks": {"ftmo": ["FTMO-Follower-2"], "fusion": []}}),
    )
    pol = ag.load_policy(repo)
    assert pol["gold_lane_tasks"]["ftmo"] == ["MT5-FTMO-Follower", "FTMO-Follower-2"]
    assert pol["gold_lane_tasks"]["fusion"] == ["MT5-Gateway"]
    _write(repo, ag.POLICY_REL, json.dumps({"gold_lane_tasks": {"ftmo": "Other"}}))
    with pytest.raises(ag.GuardError):
        ag.load_policy(repo)


def test_a_stray_rewritten_after_the_record_counts(repo: Path) -> None:
    """v10 audit B3: the record is path AND content."""
    _write(repo, "scripts/stray.py", "S = 1\n")
    assert ag.hold_new_risk(repo, "adopting", run="r1")
    assert ag.code_dirty(repo) == []
    _write(repo, "scripts/stray.py", "S = 2  # half-written over a stray path\n")
    assert ag.code_dirty(repo) == ["scripts/stray.py"]


def test_a_hold_deleted_by_hand_never_absorbs_a_failed_adoptions_files(repo: Path) -> None:
    """v10 audit B7: the record outlives a hold that went without a lift; a lift removes it."""
    assert ag.hold_new_risk(repo, "adopting", run="r1")
    _write(repo, "libs/left_over.py", "L = 1\n")  # the failed adoption's new file
    nrh.lift(by=ag.BY, root=repo)  # gone without the guard's lift, as by a hand delete
    assert ag.own_hold_since(repo) is None and (repo / ag.UNTRACKED_BASELINE_REL).exists()
    assert ag.hold_new_risk(repo, "next adoption", run="r2")
    assert ag.code_dirty(repo) == ["libs/left_over.py"]
    (repo / "libs/left_over.py").unlink()
    assert ag.lift_hold(repo, run="r2")
    assert not (repo / ag.UNTRACKED_BASELINE_REL).exists()
