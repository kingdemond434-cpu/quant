"""An armed loss rail lacking a published anchor or headroom is RED; Fusion publishes both."""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


chk = _load("_clra", ROOT / "scripts" / "check_loss_rail_anchors.py")
fd = _load("_fd_headroom", ROOT / "desks" / "mt5" / "proposals" / "fusion_deadman.py")
NOW = datetime(2026, 10, 29, 15, 50, tzinfo=UTC)


def _stamp(**kw) -> dict:
    s = {"mode": "LIVE", "checked_at": NOW.isoformat(), "rails": fd.rails(),
         "loss_rails": fd.loss_rail_headroom([], 568.77, 457.74, "2026-10-01T00:00:00+00:00",
                                             now=NOW)}
    s.update(kw)
    return s


def test_a_clean_armed_stamp_passes() -> None:
    assert chk.judge(_stamp(), now=NOW, max_age_h=2) == []


def test_an_armed_stamp_without_anchor_is_red() -> None:
    bad = _stamp()
    del bad["loss_rails"]
    d = chk.judge(bad, now=NOW, max_age_h=2)
    assert any("WEEKLY_LOSS" in x for x in d) and any("DAILY_LOSS" in x for x in d)


def test_stale_and_unmeasured_are_red_and_unarmed_passes() -> None:
    old = _stamp(checked_at=(NOW - timedelta(hours=5)).isoformat())
    assert any("old" in x for x in chk.judge(old, now=NOW, max_age_h=2))
    um = _stamp(loss_rails=fd.loss_rail_headroom(None, 568.77, 457.74, None, now=NOW))
    assert any("UNMEASURED" in x for x in chk.judge(um, now=NOW, max_age_h=2))
    assert chk.judge({"mode": "DRY-RUN", "rails": fd.rails()}, now=NOW, max_age_h=2) == []


def test_headroom_mirrors_the_weekly_trip_rule() -> None:
    rows = [{"time": (NOW - timedelta(days=6)).isoformat(), "pl_quote": -25.42},
            {"time": (NOW - timedelta(days=8)).isoformat(), "pl_quote": -500.0}]
    w = fd.loss_rail_headroom(rows, 568.77, 457.74, None, now=NOW)["WEEKLY_LOSS"]
    assert w["weekly_anchor"] == 568.77 and w["trip_at_ccy"] == round(0.2 * 568.77, 2)
    assert w["headroom_ccy"] == round(0.2 * 568.77 - 25.42, 2)
    # exactly at the headroom the rail has not yet tripped; one cent more and it has
    trip = [{"time": (NOW - timedelta(days=1)).isoformat(), "pl_quote": -(w["trip_at_ccy"] + 0.01)}]
    assert "WEEKLY_LOSS" in [c for c, _ in fd.evaluate({"equity": 457.74}, [], trip, 568.77,
                                                       now=NOW)]


def test_keyed_ledger_rows_are_read(tmp_path: Path, monkeypatch) -> None:
    acct = tmp_path / "acct.json"
    acct.write_text(json.dumps({"login": 123, "server": fd.FUSION_LIVE_SERVER}))
    led = tmp_path / "led.jsonl"
    base = {"account_kind": "live", "server": fd.FUSION_LIVE_SERVER, "pl_quote": -1.0,
            "time": NOW.isoformat()}
    led.write_text("\n".join(json.dumps(r) for r in (
        {**base, "account": 123}, {**base, "account_key": "sha256:aaaa"},
        {**base, "account_key": "sha256:bbbb"})))
    monkeypatch.setattr(fd, "_declared_key", lambda login: "sha256:aaaa")
    rows, _ = fd.ledger_checked(led, acct)
    assert rows is not None and len(rows) == 2
