"""libs/ops/send_alert.py falls back to the box pager's EXISTING ntfy topic (2026-11-17).

With data/secrets/alert_channels.json absent, every registry veto notice failed, so the box gate
merged nothing by the registry. The pager topic already reaches the phone, and arming it needs
no new credential and no human step.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

SEND_ALERT = Path(__file__).resolve().parents[2] / "libs" / "ops" / "send_alert.py"


def _mod(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Any:
    spec = importlib.util.spec_from_file_location("send_alert_pager", SEND_ALERT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod.alert_channels, "_LEDGER", tmp_path / "led.jsonl")
    return mod


def _topic(tmp_path: Path, rel: str, raw: bytes) -> None:
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(raw)


def test_nothing_armed_goes_to_the_pager_topic_and_counts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    mod = _mod(monkeypatch, tmp_path)
    _topic(tmp_path, "data/secrets/ntfy.json", json.dumps({"topic": "quant-desk-x"}).encode())
    monkeypatch.setattr(mod, "send_all", lambda t, b: {"armed": 0, "delivered": 0, "results": []})
    sent: list[dict[str, Any]] = []
    monkeypatch.setitem(
        mod.alert_channels.__dict__, "_send_ntfy", lambda c, t, b: sent.append(c) or "http 200"
    )
    assert mod.main(["veto", "body"]) == 0
    assert sent == [{"topic": "quant-desk-x"}]
    # the default ledger path is relative; _log was called with it
    rows = [
        json.loads(x) for x in (tmp_path / "data/alert_delivery.jsonl").read_text().splitlines()
    ]
    assert rows[-1]["channel"] == "ntfy-pager" and rows[-1]["ok"] is True
    assert "quant-desk-x" not in (tmp_path / "data/alert_delivery.jsonl").read_text()


def test_the_desk_copy_counts_and_a_utf16_file_reads(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    mod = _mod(monkeypatch, tmp_path)
    _topic(
        tmp_path, "desks/mt5/data/secrets/ntfy.json", json.dumps({"topic": "t1"}).encode("utf-16")
    )
    assert mod.pager_topic() == "t1"


def test_a_failed_pager_send_still_fails_and_is_ledgered(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    mod = _mod(monkeypatch, tmp_path)
    _topic(tmp_path, "data/secrets/ntfy.json", json.dumps({"topic": "t"}).encode())
    monkeypatch.setattr(mod, "send_all", lambda t, b: {"armed": 0, "delivered": 0, "results": []})

    def boom(*_a: object) -> str:
        raise OSError("down")

    monkeypatch.setitem(mod.alert_channels.__dict__, "_send_ntfy", boom)
    assert mod.main(["t", "b"]) == 1
    rows = (tmp_path / "data/alert_delivery.jsonl").read_text()
    assert '"channel":"ntfy-pager","ok":false' in rows


def test_no_topic_no_send_and_a_delivered_registry_never_doubles(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    mod = _mod(monkeypatch, tmp_path)
    calls: list[int] = []
    monkeypatch.setitem(
        mod.alert_channels.__dict__, "_send_ntfy", lambda *a: calls.append(1) or "http 200"
    )
    monkeypatch.setattr(mod, "send_all", lambda t, b: {"armed": 0, "delivered": 0, "results": []})
    assert mod.main(["t", "b"]) == 1 and calls == []  # no topic file: unarmed stays a failure
    _topic(tmp_path, "data/secrets/ntfy.json", json.dumps({"topic": "t"}).encode())
    monkeypatch.setattr(mod, "send_all", lambda t, b: {"armed": 1, "delivered": 1, "results": []})
    assert mod.main(["t", "b"]) == 0 and calls == []  # a registry channel delivered
    failed_ntfy = {"armed": 1, "delivered": 0, "results": [{"channel": "ntfy", "ok": False}]}
    monkeypatch.setattr(mod, "send_all", lambda t, b: failed_ntfy)
    assert mod.main(["t", "b"]) == 1 and calls == []  # the registry already tried ntfy
