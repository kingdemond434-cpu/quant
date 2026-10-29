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


def test_the_weekly_anchor_is_the_peak_not_the_day_start() -> None:
    """evaluate's day_ref is max(peak, equity) (fusion_deadman.py L334): at peak 568.77 and day
    start 458.79, a -100 week (beyond 0.2 x 458.79 = 91.76, inside 0.2 x 568.77 = 113.75) does
    NOT trip; the daily equity leg trips at 0.9 x 458.79 = 412.91."""
    day = fd.broker_day(NOW)
    acct = {"equity": 457.74, "day_start_equity": {"date": day, "equity": 458.79}}
    rows = [{"time": (NOW - timedelta(days=3)).isoformat(), "pl_quote": -100.0}]
    assert "WEEKLY_LOSS" not in [c for c, _ in fd.evaluate(acct, [], rows, 568.77, now=NOW)]
    blk = fd.loss_rail_headroom(rows, 568.77, 457.74, None, now=NOW,
                                opening=acct["day_start_equity"])
    assert blk["WEEKLY_LOSS"]["trip_at_ccy"] == 113.75
    assert blk["DAILY_LOSS"]["equity_trip_at"] == 412.91
    low = {**acct, "equity": 412.91}
    assert "DAILY_LOSS" in [c for c, _ in fd.evaluate(low, [], [], 568.77, now=NOW)]


def _mixed(tmp_path: Path, key: str) -> tuple[Path, Path]:
    acct = tmp_path / "acct.json"
    acct.write_text(json.dumps({"login": 123, "server": fd.FUSION_LIVE_SERVER}))
    led = tmp_path / "led.jsonl"
    base = {"account_kind": "live", "server": fd.FUSION_LIVE_SERVER, "pl_quote": -1.0,
            "time": NOW.isoformat()}
    led.write_text(json.dumps({**base, "account": 123}) + "\n"
                   + json.dumps({**base, "account_key": key}))
    return led, acct


def test_an_underivable_key_over_keyed_rows_is_unmeasured(tmp_path: Path, monkeypatch) -> None:
    led, acct = _mixed(tmp_path, "sha256:aaaa")
    monkeypatch.setattr(fd, "_declared_key", lambda login: None)
    rows, why = fd.ledger_checked(led, acct)
    assert rows is None and "UNMEASURED" in why


def test_the_real_provenance_key_joins_keyed_rows(tmp_path: Path, monkeypatch) -> None:
    from libs.ops import provenance
    kf = tmp_path / "box.key"
    kf.write_bytes(b"k" * 64)
    monkeypatch.setenv(provenance.KEY_ENV, str(kf))
    key = provenance.account_key(123, fd.FUSION_LIVE_SERVER, create=False)
    assert key and key.startswith("sha256:")
    led, acct = _mixed(tmp_path, key)
    rows, _ = fd.ledger_checked(led, acct)
    assert rows is not None and len(rows) == 2
