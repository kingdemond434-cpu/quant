from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESK / "research"))

import shadow_cycle  # noqa: E402


def _canonical(reports: Path, n: int) -> None:
    import gate_policy
    gates = {name: {"passed": True} for name in gate_policy.GATES}
    (reports.parent / "UNIVERSAL_SURVIVORS.json").write_text(json.dumps({
        "gate_policy": gate_policy.ATTESTATION,
        "survivors": {f"cert-{i}": {"gates": gates} for i in range(n)},
    }))


def test_cycle_counts_only_certified_shadow_books_before_promoter(
    tmp_path: Path, monkeypatch,
) -> None:
    import external_shadow
    import promoter
    import qquant_shadow
    import scalp_shadow
    import shadow_forward

    calls: list[str] = []
    monkeypatch.setattr(external_shadow, "main", lambda: calls.append("external_reconcile"))
    monkeypatch.setattr(shadow_forward, "main", lambda: calls.append("legacy"))
    monkeypatch.setattr(scalp_shadow, "main", lambda: calls.append("scalp"))
    monkeypatch.setattr(qquant_shadow, "main", lambda: calls.append("qquant"))
    monkeypatch.setattr(promoter, "main", lambda: calls.append("promoter"))
    monkeypatch.setattr(shadow_cycle, "_refresh_scalp_bars", lambda: calls.append("refresh"))
    reports = tmp_path / "reports" / "shadow"
    reports.mkdir(parents=True)
    _canonical(reports, 3)
    (reports / "shadow_state.json").write_text(json.dumps({
        "configured_sleeves": 1, "gate_blocked_sleeves": 36,
        "XAUUSD.asia": {"n": 0, "gate_admission": "ORIGINAL_UNIVERSAL_10_PASS"},
    }))
    (reports / "scalp_shadow_state.json").write_text(
        json.dumps({"configured_sleeves": 1, "gate_blocked_sleeves": 4,
                    "sleeves": {"scalp": {"n": 0}}}))
    (reports / "qquant_shadow_state.json").write_text(json.dumps({
        "certified_qquant_sleeves": 1,
        "qquant.pass": {"n": 0, "status": "NO_DATA"},
    }))
    monkeypatch.setattr(shadow_cycle, "BASE", tmp_path)
    monkeypatch.setattr(shadow_cycle, "OUT", reports / "health.json")
    health, rc = shadow_cycle.run()
    assert calls == ["refresh", "external_reconcile", "legacy", "scalp", "qquant", "promoter"]
    assert rc == 2 and health["configured_sleeves"] == 3
    assert health["status"] == "EVIDENCE_BLOCKED"
    assert health["represented_sleeves"] == 3
    assert health["certified_sleeves_total"] == 3
    assert health["retired_shadow_sleeves"] == 0
    assert health["quarantined_uncertified_candidates"] == 40


def test_terminal_shadow_verdict_is_retained_but_not_active(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import external_shadow
    import promoter
    import qquant_shadow
    import scalp_shadow
    import shadow_forward

    for module in (external_shadow, shadow_forward, scalp_shadow, qquant_shadow, promoter):
        monkeypatch.setattr(module, "main", lambda: None)
    monkeypatch.setattr(shadow_cycle, "_refresh_scalp_bars", lambda: None)
    reports = tmp_path / "reports" / "shadow"
    reports.mkdir(parents=True)
    _canonical(reports, 1)
    (reports / "shadow_state.json").write_text(json.dumps({"configured_sleeves": 0}))
    (reports / "scalp_shadow_state.json").write_text(json.dumps({
        "configured_sleeves": 0, "sleeves": {},
    }))
    (reports / "qquant_shadow_state.json").write_text(json.dumps({
        "certified_qquant_sleeves": 1,
        "qquant.retired": {"n": 50, "status": "RETIRED_GATE_FAIL"},
    }))
    monkeypatch.setattr(shadow_cycle, "BASE", tmp_path)
    monkeypatch.setattr(shadow_cycle, "OUT", reports / "health.json")
    health, rc = shadow_cycle.run()
    assert rc == 0 and health["status"] == "OPERATING"
    assert health["configured_sleeves"] == 0
    assert health["certified_sleeves_total"] == 1
    assert health["retired_shadow_sleeves"] == 1


def test_missing_sleeve_fails_loud(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import external_shadow
    import promoter
    import qquant_shadow
    import scalp_shadow
    import shadow_forward

    monkeypatch.setattr(external_shadow, "main", lambda: None)
    monkeypatch.setattr(shadow_forward, "main", lambda: None)
    monkeypatch.setattr(scalp_shadow, "main", lambda: None)
    monkeypatch.setattr(qquant_shadow, "main", lambda: None)
    monkeypatch.setattr(promoter, "main", lambda: None)
    monkeypatch.setattr(shadow_cycle, "_refresh_scalp_bars", lambda: None)
    reports = tmp_path / "reports" / "shadow"
    reports.mkdir(parents=True)
    _canonical(reports, 1)
    (reports / "shadow_state.json").write_text(json.dumps({"configured_sleeves": 1}))
    (reports / "scalp_shadow_state.json").write_text(json.dumps({
        "configured_sleeves": 0, "sleeves": {},
    }))
    (reports / "qquant_shadow_state.json").write_text(json.dumps({
        "certified_qquant_sleeves": 0,
    }))
    monkeypatch.setattr(shadow_cycle, "BASE", tmp_path)
    monkeypatch.setattr(shadow_cycle, "OUT", tmp_path / "health.json")
    health, rc = shadow_cycle.run()
    assert rc == 3 and health["missing_sleeves"] == ["1 certified sleeve(s)"]


def test_fresh_authoritative_scalp_bars_avoid_a_second_terminal_connection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    universe = tmp_path / "data" / "universe"
    universe.mkdir(parents=True)
    (universe / "XAUUSD_scalp_source.json").write_text(json.dumps({
        "promotion_authority": True, "source_server": "FusionMarkets-Live",
    }))
    now = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)  # Monday, market open
    for timeframe in ("M1", "M5", "M15"):
        path = universe / f"XAUUSD_{timeframe}.parquet"
        path.write_bytes(b"canonical-bars")
        os.utime(path, (now.timestamp(), now.timestamp()))
    monkeypatch.setattr(shadow_cycle, "BASE", tmp_path)
    assert shadow_cycle._fresh_authoritative_scalp_bars(now) is True
    stale = universe / "XAUUSD_M1.parquet"
    old = now - timedelta(seconds=shadow_cycle.SCALP_BAR_MAX_AGE_SECONDS + 1)
    os.utime(stale, (old.timestamp(), old.timestamp()))
    assert shadow_cycle._fresh_authoritative_scalp_bars(now) is False


def test_closed_weekend_keeps_the_last_authoritative_bars_without_reconnecting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Friday close is the newest possible bar on Sunday, not a stale producer."""
    universe = tmp_path / "data" / "universe"
    universe.mkdir(parents=True)
    (universe / "XAUUSD_scalp_source.json").write_text(json.dumps({
        "promotion_authority": True, "source_server": "FusionMarkets-Live",
    }))
    friday = datetime(2026, 9, 25, 21, 55, tzinfo=UTC)
    sunday = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)
    for timeframe in ("M1", "M5", "M15"):
        path = universe / f"XAUUSD_{timeframe}.parquet"
        path.write_bytes(b"canonical-bars")
        os.utime(path, (friday.timestamp(), friday.timestamp()))
    monkeypatch.setattr(shadow_cycle, "BASE", tmp_path)
    assert shadow_cycle._fresh_authoritative_scalp_bars(sunday) is True


def test_closed_weekend_never_accepts_empty_or_non_authoritative_bars(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    universe = tmp_path / "data" / "universe"
    universe.mkdir(parents=True)
    sunday = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)
    (universe / "XAUUSD_scalp_source.json").write_text(json.dumps({
        "promotion_authority": False, "source_server": "Other-Demo",
    }))
    for timeframe in ("M1", "M5", "M15"):
        (universe / f"XAUUSD_{timeframe}.parquet").write_bytes(b"canonical-bars")
    monkeypatch.setattr(shadow_cycle, "BASE", tmp_path)
    assert shadow_cycle._fresh_authoritative_scalp_bars(sunday) is False


def test_nonzero_step_result_fails_loud(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import external_shadow
    import promoter
    import qquant_shadow
    import scalp_shadow
    import shadow_forward

    monkeypatch.setattr(external_shadow, "main", lambda: None)
    monkeypatch.setattr(shadow_forward, "main", lambda: None)
    monkeypatch.setattr(scalp_shadow, "main", lambda: None)
    monkeypatch.setattr(qquant_shadow, "main", lambda: 1)
    monkeypatch.setattr(promoter, "main", lambda: None)
    monkeypatch.setattr(shadow_cycle, "_refresh_scalp_bars", lambda: None)
    reports = tmp_path / "reports" / "shadow"
    reports.mkdir(parents=True)
    _canonical(reports, 0)
    (reports / "shadow_state.json").write_text(json.dumps({"configured_sleeves": 0}))
    (reports / "scalp_shadow_state.json").write_text(json.dumps({
        "configured_sleeves": 0, "sleeves": {},
    }))
    (reports / "qquant_shadow_state.json").write_text(json.dumps({
        "certified_qquant_sleeves": 0,
    }))
    monkeypatch.setattr(shadow_cycle, "BASE", tmp_path)
    monkeypatch.setattr(shadow_cycle, "OUT", tmp_path / "health.json")

    health, rc = shadow_cycle.run()

    assert rc == 1
    assert health["errors"]["qquant_shadow"] == "RuntimeError: returned non-zero status 1"


def test_gold_certificate_versions_are_one_live_exposure() -> None:
    assert shadow_cycle._canonical_live_exposure("gold_asia_v2") == "gold_asia"
    assert shadow_cycle._canonical_live_exposure("gold_asia_v14") == "gold_asia"
    assert shadow_cycle._canonical_live_exposure("gold_london_am_v3") == "gold_london_am"
    assert shadow_cycle._canonical_live_exposure("gold_afternoon_v4") == "gold_afternoon"
    assert shadow_cycle._canonical_live_exposure("other_alpha_v2") == "other_alpha_v2"


def test_zero_trade_diagnostics_separate_new_quiet_and_blocked_clocks() -> None:
    now = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)
    rows = [
        {"n": 0, "status": "ACTIVE", "enrolled_at": "2026-09-26T12:00:00+00:00",
         "last_attempt_at": "2026-09-27T11:00:00+00:00", "bar_source": "MT5:Fusion"},
        {"n": 0, "status": "ACTIVE", "forward_start": "2026-09-01T12:00:00+00:00"},
        {"n": 0, "status": "BLOCKED_NO_BARS", "forward_start": "2026-09-05T12:00:00+00:00"},
        {"n": 3, "status": "ACTIVE", "forward_start": "2026-09-01T12:00:00+00:00"},
    ]
    got = shadow_cycle._zero_trade_diagnostics(rows, now)
    assert got["count"] == 3
    assert got["by_status"] == {"ACTIVE": 2, "BLOCKED_NO_BARS": 1}
    assert got["mature_14d_without_trade"] == 2
    assert got["naturally_inactive"] == 1
    assert got["suppressed_or_unproven"] == 2
