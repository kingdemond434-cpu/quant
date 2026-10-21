"""v5f.1 (audit should-fixes on v5f): the immediate drain, the ledger write that is retried and
not dropped, and outbox rows that are validated and quarantined. Fake senders, fake logins, and a
temp key, so nothing here reaches a real channel or the repository's alert state."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from libs.ops import provenance as pv
from libs.ops.alert_ledger import AlertLedger, AlertLedgerBusy, AlertLedgerUnreadable

ROOT = Path(__file__).resolve().parents[2]


class _Pages:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def __call__(self, title: str, body: str) -> dict[str, Any]:
        self.sent.append((title, body))
        return {"armed": 1, "delivered": 1}


@pytest.fixture
def box(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    key = tmp_path / "data" / "secrets" / "account_key.hmac"
    key.parent.mkdir(parents=True)
    monkeypatch.setenv(pv.KEY_ENV, str(key))
    monkeypatch.delenv(pv.IMMEDIATE_DRAIN_ENV, raising=False)
    monkeypatch.setattr(pv, "_ENQUEUED", {})
    monkeypatch.setattr(pv, "_ENQUEUE_FAILED", {})
    monkeypatch.setattr(pv, "_LAST_TRY", {})
    monkeypatch.setattr(pv, "_LAST_KICK", [])
    monkeypatch.setattr(pv, "SENDER", _Pages())
    monkeypatch.setattr(pv, "_default_sender",
                        lambda: pytest.fail("the real sender was reached"))
    pv._KEY_CACHE.clear()
    return key


def _ledger(box: Path) -> dict[str, Any]:
    p = pv._alert_ledger_path()
    return json.loads(p.read_text("utf-8"))["alerts"] if p.exists() else {}


# ------------------------------------------------------------------ 1. the immediate drain
def test_an_enqueue_kicks_an_immediate_deliverer_without_waiting_for_it(
        box: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    started = threading.Event()
    release = threading.Event()

    def slow_spawner() -> None:
        started.set()
        release.wait(10)            # a deliverer that takes its time

    monkeypatch.setattr(pv, "DRAIN_SPAWNER", slow_spawner)
    t0 = time.monotonic()
    assert pv._page("KEY_MISMATCH", "OPEN", "s1", "KEY MISMATCH", "body")["queued"] is True
    assert time.monotonic() - t0 < 0.5, "the caller waited for the deliverer"
    assert started.wait(5), "no immediate deliverer was started"
    release.set()


def test_the_kick_is_throttled_and_can_be_turned_off(
        box: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    kicks: list[int] = []
    monkeypatch.setattr(pv, "DRAIN_SPAWNER", lambda: kicks.append(1))
    pv._page("UNDECLARED", "OPEN", "a", "UNDECLARED", "b")
    pv._page("KEY_MISMATCH", "OPEN", "b", "KEY MISMATCH", "b")
    for _ in range(50):
        if kicks:
            break
        time.sleep(0.02)
    assert kicks == [1], "more than one kick inside IMMEDIATE_DRAIN_MIN_S"
    monkeypatch.setattr(pv, "_LAST_KICK", [])
    monkeypatch.setenv(pv.IMMEDIATE_DRAIN_ENV, "0")
    assert pv._kick_drain() is False


def test_a_spawner_that_raises_never_reaches_the_caller(
        box: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom() -> None:
        raise OSError("cannot spawn")

    monkeypatch.setattr(pv, "DRAIN_SPAWNER", boom)
    assert pv._page("KEY_MISMATCH", "OPEN", "s", "KEY MISMATCH", "b")["queued"] is True


def test_no_real_deliverer_is_spawned_from_a_test_unless_asked(
        box: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def no_popen(*a: Any, **k: Any) -> None:
        raise AssertionError("a real deliverer was spawned")

    monkeypatch.setattr(subprocess, "Popen", no_popen)
    monkeypatch.setattr(pv, "DRAIN_SPAWNER", None)
    assert pv._kick_drain() is False


def test_the_child_is_detached_below_normal_and_marked(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    class _P:
        def __init__(self, cmd: list[str], **kw: Any) -> None:
            seen.update(cmd=cmd, **kw)

    monkeypatch.setattr(subprocess, "Popen", _P)
    pv._spawn_drain_child()
    assert seen["cmd"][1:] == ["-m", "libs.ops.provenance", "--deliver-alerts"]
    assert seen["env"][pv._DRAIN_CHILD_ENV] == "1"
    assert seen["stdin"] is subprocess.DEVNULL and seen["stdout"] is subprocess.DEVNULL
    if sys.platform == "win32":
        assert seen["creationflags"] & subprocess.BELOW_NORMAL_PRIORITY_CLASS
    else:
        assert seen["start_new_session"] is True


def test_the_child_does_not_kick_another_child(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(pv._DRAIN_CHILD_ENV, "1")
    monkeypatch.setattr(pv, "DRAIN_SPAWNER", lambda: pytest.fail("the child kicked a child"))
    monkeypatch.setattr(pv, "_LAST_KICK", [])
    assert pv._kick_drain() is False


def test_a_real_immediate_deliverer_drains_the_outbox(box: Path, tmp_path: Path) -> None:
    """End to end: the real child delivers with no channels configured (NOT-ARMED: no network),
    so the outbox is drained into the page state within seconds, not at the next heartbeat."""
    pv._page("KEY_MISMATCH", "OPEN", "s", "KEY MISMATCH", "fake body")
    assert pv._outbox_path().exists()
    env = {**os.environ, pv.KEY_ENV: str(box)}
    env.pop("PYTEST_CURRENT_TEST", None)
    proc = subprocess.Popen([sys.executable, "-m", "libs.ops.provenance", "--deliver-alerts"],
                            cwd=str(ROOT), env={**env, pv._DRAIN_CHILD_ENV: "1"},
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    assert proc.wait(timeout=120) == 0
    assert not pv._outbox_path().exists()
    state = json.loads(pv._page_state_path().read_text("utf-8"))
    assert state["KEY_MISMATCH"]["want"] == "OPEN"


# ------------------------------------------------------------ 2. the ledger write is retried
@pytest.mark.parametrize("exc", [AlertLedgerBusy("held"), AlertLedgerUnreadable("transient")])
def test_a_busy_or_unreadable_ledger_keeps_the_needs_human_write_for_retry(
        box: Path, monkeypatch: pytest.MonkeyPatch, exc: Exception) -> None:
    box.write_bytes(b"ab12")
    pv._KEY_CACHE.clear()
    assert pv.account_key(7000001, "Srv-1", create=True) is None
    real = AlertLedger.transaction

    def fail(*a: Any, **k: Any) -> Any:
        raise exc

    monkeypatch.setattr(AlertLedger, "transaction", fail)
    res = pv.deliver_pending()
    assert res["ledger"].startswith("not written") and res["ledger_pending"] == [pv.ALERT_KEY]
    assert pv.SENDER.sent, "the page waited on the ledger"   # type: ignore[union-attr]
    assert _ledger(box) == {}
    monkeypatch.setattr(AlertLedger, "transaction", real)
    res = pv.deliver_pending()                     # no new row: the pending write is retried
    assert res["rows"] == 0 and res["ledger"] == "written"
    assert _ledger(box)[pv.ALERT_KEY]["state"] == "NEEDS_HUMAN"
    assert pv.deliver_pending()["ledger"] == "nothing to write"


# ------------------------------------------------------- 5. rows are validated, bad ones kept
@pytest.mark.parametrize("bad", [
    {"aid": {"nested": 1}, "status": "OPEN", "sig": "s", "title": "T", "body": "b"},
    {"aid": "", "status": "OPEN", "sig": "s", "title": "T", "body": "b"},
    {"aid": "has spaces", "status": "OPEN", "sig": "s", "title": "T", "body": "b"},
    {"aid": "X", "status": "OPEN", "sig": "s", "title": "", "body": "b"},
    {"aid": "X", "status": "OPEN", "sig": "s", "title": {"t": 1}, "body": "b"},
    {"aid": "X", "status": "MAYBE", "sig": "s", "title": "T", "body": "b"},
    {"aid": "X", "status": "OPEN", "sig": "s", "title": "T", "body": "b", "at": "yesterday"},
    "not a row",
])
def test_a_malformed_outbox_row_is_quarantined_and_never_pages(box: Path, bad: Any) -> None:
    if isinstance(bad, dict):
        bad = {"at": "2026-10-21T00:00:00+00:00", **bad}
    out = pv._outbox_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    good = {"at": "2026-10-21T00:00:01+00:00", "aid": "GOOD", "status": "OPEN", "sig": "s",
            "title": "GOOD TITLE", "body": "b", "needs_human": "", "ledger": False}
    out.write_text(json.dumps(bad) + "\n{broken json\n" + json.dumps(good) + "\n", "utf-8")
    pv.deliver_pending()
    assert pv.SENDER.sent == [("GOOD TITLE", "b")]   # type: ignore[union-attr]
    q = out.with_name("account_key_outbox.quarantine.jsonl")
    kept = [json.loads(x) for x in q.read_text("utf-8").splitlines()]
    assert len(kept) == 2 and {k["why"] for k in kept} >= {"not JSON"}
    state = json.loads(pv._page_state_path().read_text("utf-8"))
    assert set(state) == {"GOOD"}


def test_page_refuses_a_dict_aid_or_an_empty_title_and_never_raises(box: Path) -> None:
    assert pv._page({"aid": 1}, "OPEN", "s", "T", "b")["queued"] is False   # type: ignore[arg-type]
    assert pv._page("X", "OPEN", "s", "", "b")["queued"] is False
    assert pv._page("X", "OPEN", "s", "T", {"b": 1})["queued"] is False   # type: ignore[arg-type]
    assert not pv._outbox_path().exists()
