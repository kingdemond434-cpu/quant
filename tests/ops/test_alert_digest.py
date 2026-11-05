"""Opt-in daily digest (libs/ops/alert_digest.py): alert_channels itself is untouched."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from libs.ops import alert_channels as ac
from libs.ops import alert_digest as ad


def _cfg(tmp_path: Path, channels: list[dict[str, Any]]) -> Path:
    p = tmp_path / "alert_channels.json"
    p.write_text(json.dumps({"channels": channels}), "utf-8")
    return p


def test_opted_in_class_pages_once_a_day_and_default_callers_never_held(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    led = tmp_path / "led.jsonl"
    cfg = _cfg(tmp_path, [{"kind": "webhook", "url": "https://a"}])
    sent: list[tuple[str, str]] = []

    def fake(_c: dict[str, Any], title: str, body: str) -> str:
        sent.append((title, body))
        return "ok"

    monkeypatch.setitem(ac._SENDERS, "webhook", fake)
    for _ in range(4):
        ad.send("Restore drill UNMEASURED", "b", config=cfg, ledger=led,
                 digest_class="backup_unmeasured")
    assert len(sent) == 1
    # a caller that did NOT opt in pages every time, whatever its title says (audit HOLD e5110a958)
    for _ in range(3):
        ad.send("FTMO follow UNMEASURED", "b", config=cfg, ledger=led, digest_class=None)
    assert len(sent) == 4
    # another class is independent of the first
    jc = {"config": cfg, "ledger": led, "digest_class": "judge_coverage"}
    res = ad.send("JUDGE COVERAGE RED", "b", **jc)
    assert not res.get("suppressed") and len(sent) == 5
    held = ad.send("JUDGE COVERAGE RED", "b", **jc)
    assert held["suppressed"] and held["delivered"] == 1 and len(sent) == 5
    # alert_channels.send_all (every money-path pager) is never held, whatever its title
    ac.send_all("JUDGE COVERAGE RED", "b", config=cfg, ledger=led)
    assert len(sent) == 6
    # after the cooldown the next page carries the held count
    st = tmp_path / "alert_digest_state.json"
    doc = json.loads(st.read_text("utf-8"))
    doc["backup_unmeasured"]["last_paged"] = "2000-01-01T00:00:00+00:00"
    st.write_text(json.dumps(doc), "utf-8")
    ad.send("Restore drill UNMEASURED", "b", config=cfg, ledger=led,
            digest_class="backup_unmeasured")
    assert sent[-1][1].startswith("(+3 repeat(s)")
    lines = (tmp_path / "alert_digest.jsonl").read_text("utf-8").splitlines()
    digest = [json.loads(x) for x in lines]
    assert len(digest) == 4 and digest[0]["title"] == "Restore drill UNMEASURED"
    assert ac.all_silent_since(1.0, ledger=led) is False


def test_digest_state_corruption_fails_open(tmp_path: Path,
                                            monkeypatch: pytest.MonkeyPatch) -> None:
    led = tmp_path / "led.jsonl"
    cfg = _cfg(tmp_path, [{"kind": "webhook", "url": "https://a"}])
    (tmp_path / "alert_digest_state.json").write_text("{not json", "utf-8")
    sent: list[str] = []
    monkeypatch.setitem(ac._SENDERS, "webhook", lambda _c, t, _b: sent.append(t) or "ok")
    ad.send("BOX STATE METER SILENT", "b", config=cfg, ledger=led, digest_class="state_meter")
    assert sent == ["BOX STATE METER SILENT"]
