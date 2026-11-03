"""Alert channel registry + delivery ledger (gap #38).

The invariants that matter are the ones the two real pager deaths violated: one channel's failure
must never suppress another's, an unarmed pager must be a RECORDED state rather than silence, and
"nothing has been delivered anywhere" must be observable.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from libs.ops import alert_channels as ac


def _cfg(tmp_path: Path, channels: list[dict[str, Any]]) -> Path:
    p = tmp_path / "alert_channels.json"
    p.write_text(json.dumps({"channels": channels}), "utf-8")
    return p


def test_unarmed_is_recorded_never_silent(tmp_path: Path) -> None:
    led = tmp_path / "led.jsonl"
    res = ac.send_all("t", "b", config=tmp_path / "missing.json", ledger=led)
    assert res["armed"] == 0
    rows = [json.loads(x) for x in led.read_text("utf-8").splitlines()]
    assert rows and rows[0]["ok"] is False and "NOT-ARMED" in rows[0]["detail"]
    assert "HUMAN step" in res["note"]


def test_one_channel_failure_never_stops_another(tmp_path: Path,
                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    led = tmp_path / "led.jsonl"
    cfg = _cfg(tmp_path, [{"kind": "webhook", "url": "https://a"},
                          {"kind": "telegram", "token": "x", "chat_id": "1"}])

    def boom(*_a: object, **_k: object) -> str:
        raise OSError("network down")

    monkeypatch.setitem(ac._SENDERS, "webhook", boom)
    monkeypatch.setitem(ac._SENDERS, "telegram", lambda *_a, **_k: "http 200")
    res = ac.send_all("title", "body", config=cfg, ledger=led)
    assert res["armed"] == 2
    assert res["delivered"] == 1          # the good channel still delivered
    kinds = {r["channel"]: r["ok"] for r in res["results"]}
    assert kinds == {"webhook": False, "telegram": True}


def test_every_attempt_is_ledgered_both_ways(tmp_path: Path,
                                             monkeypatch: pytest.MonkeyPatch) -> None:
    led = tmp_path / "led.jsonl"
    cfg = _cfg(tmp_path, [{"kind": "webhook", "url": "https://a"}])
    monkeypatch.setitem(ac._SENDERS, "webhook", lambda *_a, **_k: "http 200")
    ac.send_all("ok-page", "b", config=cfg, ledger=led)

    def boom(*_a: object, **_k: object) -> str:
        raise OSError("nope")

    monkeypatch.setitem(ac._SENDERS, "webhook", boom)
    ac.send_all("bad-page", "b", config=cfg, ledger=led)
    rows = [json.loads(x) for x in led.read_text("utf-8").splitlines()]
    assert [r["ok"] for r in rows] == [True, False]


def test_alert_titles_are_hashed_not_stored(tmp_path: Path,
                                            monkeypatch: pytest.MonkeyPatch) -> None:
    # Alert bodies name positions; a delivery ledger must not become a book-state leak.
    led = tmp_path / "led.jsonl"
    cfg = _cfg(tmp_path, [{"kind": "webhook", "url": "https://a"}])
    monkeypatch.setitem(ac._SENDERS, "webhook", lambda *_a, **_k: "http 200")
    ac.send_all("COOKIEUSDT position 1.28x book", "b", config=cfg, ledger=led)
    raw = led.read_text("utf-8")
    assert "COOKIEUSDT" not in raw
    assert len(json.loads(raw.splitlines()[0])["title_sha"]) == 12


def test_all_silent_since_detects_and_clears(tmp_path: Path,
                                             monkeypatch: pytest.MonkeyPatch) -> None:
    led = tmp_path / "led.jsonl"
    assert ac.all_silent_since(24.0, ledger=led) is True     # no ledger at all = silent
    cfg = _cfg(tmp_path, [{"kind": "webhook", "url": "https://a"}])
    monkeypatch.setitem(ac._SENDERS, "webhook", lambda *_a, **_k: "http 200")
    ac.send_all("t", "b", config=cfg, ledger=led)
    assert ac.all_silent_since(24.0, ledger=led) is False     # a fresh success clears it


def test_failures_alone_still_count_as_silence(tmp_path: Path,
                                               monkeypatch: pytest.MonkeyPatch) -> None:
    # The 2026-07-19 shape: 39/39 attempts, zero successes. Attempts must NOT clear silence.
    led = tmp_path / "led.jsonl"
    cfg = _cfg(tmp_path, [{"kind": "webhook", "url": "https://a"}])

    def boom(*_a: object, **_k: object) -> str:
        raise OSError("latin-1 class failure")

    monkeypatch.setitem(ac._SENDERS, "webhook", boom)
    for _ in range(39):
        ac.send_all("t", "b", config=cfg, ledger=led)
    assert ac.all_silent_since(24.0, ledger=led) is True


def test_non_ascii_title_cannot_raise(tmp_path: Path) -> None:
    # The exact 29h-outage class: a raw emoji in a header. The ntfy sender must sanitise, and
    # send_all must never propagate whatever the network does.
    led = tmp_path / "led.jsonl"
    cfg = _cfg(tmp_path, [{"kind": "ntfy", "topic": "unit-test-topic-does-not-exist"}])
    res = ac.send_all("⚠️ DEADMAN FIRED", "body", config=cfg, ledger=led)
    assert res["armed"] == 1                      # no exception escaped
    assert len(ac.ledger_tail(5, ledger=led)) == 1


def test_status_reports_arming_owed(tmp_path: Path) -> None:
    st = ac.status(config=tmp_path / "nope.json", ledger=tmp_path / "nope.jsonl")
    assert st["arming_owed"] is True
    assert st["armed_kinds"] == []
    assert st["all_silent_24h"] is True


def test_unknown_kind_is_ignored_not_crashed(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path, [{"kind": "carrier-pigeon", "url": "x"}])
    assert ac.load_channels(cfg) == []
