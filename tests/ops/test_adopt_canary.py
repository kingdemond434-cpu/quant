"""The adopt canary (pre-mortem #1; Audit 2026-11-25 19:48Z/19:49Z): new code trades only the
canary window until one clean send; the bound never trusts the lane's own sizing."""
from __future__ import annotations

import importlib.util
import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from libs.ops import adopt_canary as ac
from libs.ops import adopt_guard as ag
from libs.ops import new_risk_hold as nrh

REPO = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 11, 26, 7, 0, tzinfo=UTC)
A, B = "a" * 40, "b" * 40


def _cli():
    spec = importlib.util.spec_from_file_location("adopt_guard_cli",
                                                  REPO / "scripts/adopt_guard.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _arm(root, *, allow=("asia",), deadline=NOW + timedelta(hours=24), prev=A, release=B):
    assert nrh.place_canary("t", release_id=release, allow=list(allow), deadline=deadline,
                            prev_head=prev, root=root)


def _row(**kw):
    # long: entry 2650, sl 2645 -> 5 x 100 x 0.2 lot = 100 USD at stop
    r = {"at": "2026-11-26T07:30:00+00:00", "window": "asia", "side": "buy_stop",
         "status": "SENT", "price": 2650.0, "sl": 2645.0, "tp": 2660.0, "lot": 0.2,
         "risk_usd": 100.0, "risk_frac": 0.01, "equity": 100000.0, "contract_size": 100.0,
         "room_to_floor": 2500.0, "armed": True}
    r.update(kw)
    return r


# ------------------------------------------------------------------------------- the hold
def test_the_canary_frees_only_its_named_window(tmp_path):
    _arm(tmp_path)
    assert nrh.reason(tmp_path, sleeve="asia", now=NOW) is None
    assert nrh.reason(tmp_path, sleeve="london_am", now=NOW) is not None
    assert nrh.reason(tmp_path, now=NOW) is not None  # a lane that names no sleeve stays held


def test_any_other_hold_still_holds_the_canary_window(tmp_path):
    _arm(tmp_path)
    assert nrh.place("x", by="adopt_guard", root=tmp_path)
    assert nrh.reason(tmp_path, sleeve="asia", now=NOW) is not None
    nrh.lift(by="adopt_guard", root=tmp_path)
    (tmp_path / nrh.HOLD_REL).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / nrh.HOLD_REL).write_text("{}", encoding="utf-8")
    assert nrh.reason(tmp_path, sleeve="asia", now=NOW) is not None


def test_an_expired_or_unreadable_canary_holds(tmp_path):
    _arm(tmp_path, deadline=NOW - timedelta(minutes=1))
    assert nrh.reason(tmp_path, sleeve="asia", now=NOW) is not None
    nrh.hold_file(nrh.CANARY_BY, tmp_path).write_text("not json", encoding="utf-8")
    assert nrh.reason(tmp_path, sleeve="asia", now=NOW) is not None
    assert nrh.canary(tmp_path) == {}


def test_re_arming_keeps_the_last_clean_head_and_never_drops_the_hold(tmp_path):
    _arm(tmp_path, prev=A, release=B)
    _arm(tmp_path, prev=B, release="c" * 40)
    doc = nrh.canary(tmp_path)
    assert doc["prev_head"] == A and doc["release_id"] == "c" * 40
    assert [f.name for f in (tmp_path / nrh.HOLD_DIR_REL).iterdir()] == ["adopt_canary.json"]


def test_an_unreadable_canary_is_not_overwritten(tmp_path):
    f = nrh.hold_file(nrh.CANARY_BY, tmp_path)
    f.parent.mkdir(parents=True)
    f.write_text("garbled", encoding="utf-8")
    _arm(tmp_path)
    assert f.read_text(encoding="utf-8") == "garbled"


# ------------------------------------------------------------------------------ the bound
def test_a_clean_send_has_no_problems():
    assert ac.problems(_row()) == []
    assert ac.problems(_row(side="sell_stop", price=2640.0, sl=2645.0, tp=2630.0)) == []


@pytest.mark.parametrize("kw, word", [
    ({"lot": 0}, "not positive"),
    ({"sl": 2655.0}, "wrong side"),
    ({"tp": None}, "missing"),
    ({"side": "hold"}, "unknown"),
    ({"risk_usd": 50.0}, "disagrees"),
    ({"risk_usd": None}, "no sized risk"),
    ({"risk_frac": 0.0005}, "budget"),
    ({"equity": None}, "cannot bound"),
    ({"room_to_floor": 99.0}, "room"),
    ({"room_to_floor": None}, "cannot bound"),
    ({"contract_size": 10.0}, "contract"),
])
def test_each_check_fails_its_own_send(kw, word):
    assert any(word in p for p in ac.problems(_row(**kw))), ac.problems(_row(**kw))


def test_the_bound_uses_its_own_contract_size_not_the_lanes():
    # the lane says 10/lot and sized to match: the bound still prices at 100/lot
    r = _row(contract_size=10.0, risk_usd=10.0, risk_frac=0.0001)
    assert any("budget" in p for p in ac.problems(r))


def test_budget_slack_is_ten_percent():
    assert ac.problems(_row(risk_frac=0.000915)) == []  # 100 <= 0.000915 x 1e5 x 1.1 = 100.65
    assert any("budget" in p for p in ac.problems(_row(risk_frac=0.0009)))  # 99.0


# ------------------------------------------------------------------------------ the verdict
def _hold(at=NOW, deadline=NOW + timedelta(hours=24)):
    return {"at": at.isoformat(), "deadline": deadline.isoformat(), "allow": ["asia"],
            "release_id": B, "prev_head": A}


def test_judge_verdicts():
    assert ac.judge(None, [], NOW)["verdict"] == ac.NONE
    assert ac.judge(_hold(), [], NOW)["verdict"] == ac.WAIT
    assert ac.judge(_hold(), [], NOW + timedelta(hours=25))["verdict"] == ac.EXPIRED
    assert ac.judge(_hold(), [_row()], NOW)["verdict"] == ac.PASS
    assert ac.judge(_hold(), [_row(), _row(status="REJECTED")], NOW)["verdict"] == ac.FAIL
    assert ac.judge(_hold(), [_row(lot=0.5)], NOW)["verdict"] == ac.FAIL
    assert ac.judge({"at": "x"}, [_row()], NOW)["verdict"] == ac.FAIL


def test_judge_ignores_paper_other_windows_and_sends_before_the_hold():
    old = _row(at=(NOW - timedelta(hours=1)).isoformat())
    rows = [old, _row(armed=False), _row(window="london_am")]
    assert ac.judge(_hold(), rows, NOW)["verdict"] == ac.WAIT


def test_watch_after_the_lift():
    lift = NOW
    t = lambda h: (lift + timedelta(hours=h)).isoformat()  # noqa: E731
    later = lift + timedelta(hours=2)
    assert ac.watch(lift, [_row(at=t(1))], later)["verdict"] == "OK"
    rej = [_row(at=t(1), status="REJECTED") for _ in range(3)]
    assert ac.watch(lift, rej, later)["verdict"] == "SPIKE"
    base = [_row(at=t(-1), status="REJECTED") for _ in range(2)]
    assert ac.watch(lift, rej + base, later)["verdict"] == "OK"  # 3 is not above 2 x 2
    assert ac.watch(lift, [_row(at=t(1), window="london_am", lot=0.9)], later)["verdict"] == "SPIKE"
    assert ac.watch(lift, rej, lift + timedelta(hours=25))["verdict"] == "DONE"


# ------------------------------------------------------------------------------- the CLI
def _journal(root, rows):
    f = root / ac.INTENTS_REL
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def _run(cli, root, *args):
    return cli.main(["--root", str(root), *args])


def test_cli_pass_lifts_and_records(tmp_path, monkeypatch, capsys):
    cli = _cli()
    monkeypatch.setattr(ag, "page", lambda *a, **k: None)
    nrh.place_canary("t", release_id=B, allow=["asia"], prev_head=A,
                     deadline=datetime.now(UTC) + timedelta(hours=24), root=tmp_path)
    assert _run(cli, tmp_path, "canary") == 0
    assert json.loads(capsys.readouterr().out)["decision"] == "CANARY_WAIT"
    _journal(tmp_path, [_row(at=(datetime.now(UTC) + timedelta(seconds=1)).isoformat())])
    assert _run(cli, tmp_path, "canary") == 0
    assert json.loads(capsys.readouterr().out)["decision"] == "CANARY_PASS"
    assert nrh.canary(tmp_path) is None
    st = ac.load_state(tmp_path)
    assert st["prev_head"] == A and st["release_id"] == B and st["lifted_at"]


def test_cli_fail_asks_for_the_rollback_and_keeps_the_hold(tmp_path, monkeypatch, capsys):
    cli = _cli()
    pages = []
    monkeypatch.setattr(ag, "page", lambda root, m: pages.append(m))
    nrh.place_canary("t", release_id=B, allow=["asia"], prev_head=A,
                     deadline=datetime.now(UTC) + timedelta(hours=24), root=tmp_path)
    _journal(tmp_path, [_row(at=(datetime.now(UTC) + timedelta(seconds=1)).isoformat(),
                             status="REJECTED")])
    assert _run(cli, tmp_path, "canary") == ag.ROLLBACK_FAILED
    out = json.loads(capsys.readouterr().out)
    assert out["decision"] == "CANARY_FAIL" and out["rollback_to"] == A and out["bad"] == B
    assert nrh.canary(tmp_path) and pages
    assert _run(cli, tmp_path, "canary-clear", "--release", "c" * 40) == 0
    assert nrh.canary(tmp_path)  # not that release: stays
    assert _run(cli, tmp_path, "canary-clear", "--release", B) == 0
    assert nrh.canary(tmp_path) is None


def test_cli_expired_pages_and_keeps(tmp_path, monkeypatch, capsys):
    cli = _cli()
    pages = []
    monkeypatch.setattr(ag, "page", lambda root, m: pages.append(m))
    nrh.place_canary("t", release_id=B, allow=["asia"], prev_head=A,
                     deadline=datetime.now(UTC) - timedelta(seconds=1), root=tmp_path)
    assert _run(cli, tmp_path, "canary") == 0
    assert json.loads(capsys.readouterr().out)["decision"] == "CANARY_EXPIRED"
    assert nrh.canary(tmp_path) and pages


def test_cli_arm_writes_the_canary_with_policy(tmp_path):
    cli = _cli()
    code, doc = cli._arm(tmp_path, B, A, {"decision": "HEALTHY"})
    assert code == ag.GO and doc["canary_armed"]
    h = nrh.canary(tmp_path)
    assert h["allow"] == ["asia"] and h["prev_head"] == A and h["release_id"] == B


def test_arm_failure_is_unhealthy(tmp_path, monkeypatch):
    cli = _cli()
    monkeypatch.setattr(nrh, "place_canary", lambda *a, **k: False)
    code, _ = cli._arm(tmp_path, B, A, {})
    assert code == ag.UNHEALTHY


# ------------------------------------------------------------------------- drift evidence
def _git(root, *args):
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def test_drift_is_copied_and_journaled_before_the_write(tmp_path):
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "libs").mkdir()
    (tmp_path / "libs/a.py").write_text("x = 1\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "c")
    assert ag.drift_evidence(tmp_path, "r1")[1]["decision"] == "NO_DRIFT"
    (tmp_path / "libs/a.py").write_text("x = 2\n", encoding="utf-8")
    (tmp_path / "libs/stray.py").write_text("y = 1\n", encoding="utf-8")
    code, doc = ag.drift_evidence(tmp_path, "r2")
    assert code == ag.GO and doc["drift"] == 2
    d = tmp_path / ag.DRIFT_DIR_REL / "r2"
    assert (d / "libs/a.py").read_text(encoding="utf-8") == "x = 2\n"
    assert (d / "libs/stray.py").exists()
    row = json.loads((tmp_path / ag.DRIFT_JOURNAL_REL).read_text(encoding="utf-8").splitlines()[-1])
    assert set(row["files"]) == {"libs/a.py", "libs/stray.py"} and not row["failed"]
    with pytest.raises(ag.GuardError):
        ag.drift_evidence(tmp_path, "../x")
