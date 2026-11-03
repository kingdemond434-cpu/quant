"""v5f: nothing on the order path touches the network; the outbox is delivered elsewhere.

`account_key` runs between order_send and the next bracket leg. In v5e it could page from there,
so a page-state write that failed, or a sender that raised, could repeat a 12 s send on every
row. Now the order path only appends a row to an outbox, and `deliver_pending` (MT5-BoxHeartbeat,
MT5-ProcessHealth) writes the ledger and pages, under one OS lock. The in-process dedupe expires
after REPAGE_H so a long-lived process still repages, and the recovery pages exactly once across
processes. Every sender here is fake; no test reaches a real channel. Fake logins only.
"""

from __future__ import annotations

import inspect
import json
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from libs.ops import provenance as pv

ROOT = Path(__file__).resolve().parents[2]


class _Pages:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []
        self.delivered = 1

    def __call__(self, title: str, body: str) -> dict[str, Any]:
        self.sent.append((title, body))
        return {"armed": 1, "delivered": self.delivered}


@pytest.fixture
def box(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    key = tmp_path / "data" / "secrets" / "account_key.hmac"
    key.parent.mkdir(parents=True)
    monkeypatch.setenv(pv.KEY_ENV, str(key))
    monkeypatch.setattr(pv, "_ENQUEUED", {})
    monkeypatch.setattr(pv, "_ENQUEUE_FAILED", {})
    monkeypatch.setattr(pv, "_LAST_TRY", {})
    monkeypatch.setattr(pv, "SENDER", _Pages())
    monkeypatch.setattr(pv, "_default_sender",
                        lambda: pytest.fail("the real sender was reached"))
    pv._KEY_CACHE.clear()
    return key


def _short(key: Path) -> None:
    key.write_bytes(b"ab12")
    pv._KEY_CACHE.clear()


@pytest.mark.parametrize("mode", ["hangs", "raises"])
def test_the_order_path_never_blocks_on_a_send(
        box: Path, monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    calls: list[str] = []

    def bad(title: str, body: str) -> dict[str, Any]:
        calls.append(title)
        if mode == "hangs":
            time.sleep(30)
        raise RuntimeError("channel down")

    monkeypatch.setattr(pv, "SENDER", bad)
    _short(box)
    t0 = time.monotonic()
    for i in range(50):
        assert pv.account_key(7000001 + i % 3, "Srv-1", create=True) is None
        assert pv.account_key("trader.alice", "Srv-1") is None
    elapsed = time.monotonic() - t0
    assert calls == [], "the order path called the sender"
    assert elapsed < 2.0, f"the order path took {elapsed:.2f}s"
    # the rows are queued for the deliverer, which is where the send happens
    assert pv._outbox_path().exists()


def test_a_page_state_that_cannot_be_written_never_slows_the_order_path(
        box: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sends: list[str] = []

    def record(t: str, b: str) -> dict[str, Any]:
        sends.append(t)
        return {"delivered": 1}

    monkeypatch.setattr(pv, "SENDER", record)
    pv._page_state_path().mkdir(parents=True)        # a directory where the state file goes
    _short(box)
    t0 = time.monotonic()
    for _ in range(50):
        assert pv.account_key(7000001, "Srv-1", create=True) is None
    assert time.monotonic() - t0 < 2.0 and sends == []


def test_a_failed_enqueue_records_its_retry_time(
        box: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import os
    real = os.open
    attempts: list[str] = []

    def denied(path: Any, *a: Any, **k: Any) -> int:
        if str(path).endswith("account_key_outbox.jsonl"):
            attempts.append(str(path))
            raise PermissionError("denied")
        return real(path, *a, **k)

    monkeypatch.setattr(os, "open", denied)
    _short(box)
    for i in range(30):
        assert pv.account_key(7000001 + i, "Srv-1", create=True) is None
    assert len(attempts) == 1, "a failed append was retried per row"
    monkeypatch.setattr(pv, "RETRY_UNDELIVERED_S", 0.0)
    pv.account_key(7000001, "Srv-1", create=True)
    assert len(attempts) == 2


def test_the_deliverer_pages_and_writes_the_ledger(box: Path) -> None:
    _short(box)
    for _ in range(5):
        pv.account_key(7000001, "Srv-1", create=True)
    res = pv.deliver_pending()
    assert res["ledger"] == "written" and [s["sent"] for s in res["sent"]] == [True]
    assert len(pv.SENDER.sent) == 1   # type: ignore[union-attr]
    assert not pv._outbox_path().exists()
    led = json.loads(pv._alert_ledger_path().read_text("utf-8"))["alerts"]
    assert led[pv.ALERT_KEY]["state"] == "NEEDS_HUMAN"
    pv.deliver_pending()
    assert len(pv.SENDER.sent) == 1   # type: ignore[union-attr]


def test_a_sender_that_raises_records_the_retry_and_loses_nothing(
        box: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(t: str, b: str) -> dict[str, Any]:
        raise RuntimeError("down")

    monkeypatch.setattr(pv, "SENDER", boom)
    _short(box)
    pv.account_key(7000001, "Srv-1", create=True)
    res = pv.deliver_pending()
    assert res["sent"][0]["sent"] is False and "raised" in res["sent"][0]["reason"]
    assert pv._LAST_TRY, "the retry time was not recorded on a raise"
    assert pv.deliver_pending()["sent"] == [], "the raise was retried at once"
    pages = _Pages()
    monkeypatch.setattr(pv, "SENDER", pages)
    monkeypatch.setattr(pv, "RETRY_UNDELIVERED_S", 0.0)
    assert pv.deliver_pending()["sent"][0]["sent"] is True
    assert len(pages.sent) == 1 and "UNUSABLE" in pages.sent[0][0]


def _age_last_page(hours: float) -> None:
    p = pv._page_state_path()
    doc = json.loads(p.read_text("utf-8"))
    at = (datetime.now(UTC) - timedelta(hours=hours)).isoformat(timespec="microseconds")
    doc[pv.ALERT_KEY]["paged"]["at"] = at
    doc[pv.ALERT_KEY]["want_at"] = at
    p.write_text(json.dumps(doc), "utf-8")


def test_a_long_lived_process_repages_a_standing_incident_every_6h(
        box: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    clock = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: clock[0])
    _short(box)
    pv.account_key(7000001, "Srv-1", create=True)
    pv.deliver_pending()
    assert len(pv.SENDER.sent) == 1   # type: ignore[union-attr]
    _age_last_page(7)
    clock[0] += 3600                     # an hour later, same process: still deduplicated
    pv.account_key(7000001, "Srv-1", create=True)
    pv.deliver_pending()
    assert len(pv.SENDER.sent) == 1, "repaged without the incident being re-observed"  # type: ignore[union-attr]
    clock[0] += 6 * 3600                 # past REPAGE_H: the in-process dedupe has expired
    pv.account_key(7000001, "Srv-1", create=True)
    pv.deliver_pending()
    assert len(pv.SENDER.sent) == 2, "a long-lived process never repaged"  # type: ignore[union-attr]


def test_an_unreadable_page_state_drains_nothing(box: Path) -> None:
    _short(box)
    pv.account_key(7000001, "Srv-1", create=True)
    pv._page_state_path().write_text("{not json", "utf-8")
    res = pv.deliver_pending()
    assert "unreadable" in res.get("error", "")
    assert pv._outbox_path().exists(), "a row was drained into a state nobody could read"


_DELIVER = """
import sys, time
sys.path.insert(0, sys.argv[2])
from libs.ops import provenance as p
log = sys.argv[1]
def send(title, body):
    time.sleep(0.3)
    with open(log, "a") as fh:
        fh.write(title + "\\n")
    return {"armed": 1, "delivered": 1}
p.SENDER = send
assert p.account_key(7000001, "Srv-1") is not None   # a fresh process: enqueues the recovery
p.deliver_pending()
"""


def test_the_recovery_pages_exactly_once_across_processes(
        box: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _short(box)
    pv.account_key(7000001, "Srv-1", create=True)
    pv.deliver_pending()
    assert len(pv.SENDER.sent) == 1   # type: ignore[union-attr]
    box.write_bytes(b"k" * 64)                      # restored
    log = tmp_path / "pages.log"
    env = {**__import__("os").environ, pv.KEY_ENV: str(box)}
    procs = [subprocess.Popen([sys.executable, "-c", _DELIVER, str(log), str(ROOT)],
                              cwd=str(tmp_path), env=env) for _ in range(3)]
    assert [p.wait(timeout=120) for p in procs] == [0, 0, 0]
    assert log.read_text("utf-8").splitlines() == ["ACCOUNT KEY OK again"]
    led = json.loads(pv._alert_ledger_path().read_text("utf-8"))["alerts"]
    assert led[pv.ALERT_KEY]["state"] == "FIXED"


def test_the_v5e_page_entry_point_keeps_its_signature_and_goes_off_the_order_path(
        box: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert list(inspect.signature(pv._page).parameters) == ["aid", "status", "sig", "title",
                                                             "body"]
    calls: list[str] = []

    def hang(t: str, b: str) -> dict[str, Any]:
        calls.append(t)
        time.sleep(30)
        return {"delivered": 1}

    monkeypatch.setattr(pv, "SENDER", hang)
    t0 = time.monotonic()
    res = pv._page("cross_account_key", "OPEN", "k1", "OCO KEY", "body")
    assert time.monotonic() - t0 < 1.0 and calls == []
    assert isinstance(res, dict) and res["sent"] is False and res["queued"] is True
    again = pv._page("cross_account_key", "OPEN", "k1", "OCO KEY", "body")
    assert again["queued"] is False                      # deduplicated, as v5e's was
    pages = _Pages()
    monkeypatch.setattr(pv, "SENDER", pages)
    pv.deliver_pending()
    assert pages.sent == [("OCO KEY", "body")]
    # like v5e's _page, it never writes the AlertLedger
    assert not pv._alert_ledger_path().exists()
    pv._page("cross_account_key", "OK", "recovered", "OCO KEY OK", "ok")
    pv._page("cross_account_key", "OK", "recovered", "OCO KEY OK", "ok")
    pv.deliver_pending()
    pv.deliver_pending()
    assert [t for t, _ in pages.sent] == ["OCO KEY", "OCO KEY OK"]
    assert pv._page("x", "BOGUS", "s", "t", "b")["queued"] is False   # never raises


def test_an_ok_with_nothing_paged_sends_nothing(box: Path) -> None:
    box.write_bytes(b"k" * 64)
    assert pv.account_key(7000001, "Srv-1") is not None
    pv.deliver_pending()
    assert pv.SENDER.sent == []   # type: ignore[union-attr]


def test_the_outbox_is_delivered_on_the_heartbeat_and_the_hourly_health_clock(
        monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "hb_under_test", ROOT / "desks" / "mt5" / "scripts" / "box_heartbeat.py")
    assert spec and spec.loader
    hb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hb)
    seen: list[int] = []

    def fake() -> dict[str, Any]:
        seen.append(1)
        return {"rows": 2, "sent": [], "ledger": "written"}

    monkeypatch.setattr(pv, "deliver_pending", fake)
    assert hb.deliver_account_key_alerts()["rows"] == 2 and seen == [1]
    main_src = inspect.getsource(hb.main)
    assert "deliver_account_key_alerts()" in main_src and "dry_run" in main_src
    ph = (ROOT / "ops" / "process_health.py").read_text("utf-8")
    assert "_deliver_account_key_alerts()" in ph.split("def main", 1)[1]
