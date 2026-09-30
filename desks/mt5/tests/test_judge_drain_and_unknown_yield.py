"""The drain meter reads the judge's sustained rate, and never-firing cells stop eating the judge."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import judge_coverage as jc  # noqa: E402

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)


def _ledger(tmp_path: Path, rows: list[dict]) -> Path:
    p = tmp_path / "gate_verdict_ledger.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in rows), "utf-8")
    return p


def test_sustained_rate_is_the_average_not_the_burst_hour(tmp_path: Path) -> None:
    """One sweep stamps 5,000 verdicts in one hour; the day holds 5,000, so 208/h, not 5,000/h."""
    at = (NOW - timedelta(hours=2)).isoformat()
    rows = [{"at": at, "cell": f"c{i}", "family": "f", "terminal_gate": "cpcv"}
            for i in range(5_000)]
    rows += [{"at": at, "cell": f"n{i}", "family": "f", "downstream_status": "NOT_RUN_X"}
             for i in range(900)]
    r = jc.sustained_rate(_ledger(tmp_path, rows), now=NOW)
    assert r["counts"]["24h"] == 5_000, "a NOT_RUN deferral is not a verdict"
    assert abs(r["per_hour_24h"] - 5_000 / 24.0) < 0.01
    assert jc.measured_capacity({}, _ledger(tmp_path, rows), now=NOW) >= 5_000


def test_drain_reports_growing_when_backlog_rises() -> None:
    d = jc.drain(1_398_253, 220.0, prior_backlog=1_395_253,
                 prior_at=NOW - timedelta(hours=24), now=NOW)
    assert d["status"] == "GROWING" and d["hours"] is None
    assert d["net_per_day"] == 3000.0
    assert d["hours_at_zero_creation"] == round(1_398_253 / 220.0, 1)


def test_drain_eta_uses_net_fall() -> None:
    d = jc.drain(1_000, 100.0, prior_backlog=1_100, prior_at=NOW - timedelta(hours=1), now=NOW)
    assert d["status"] == "DRAINING" and d["hours"] == 10.0


def test_drain_unmeasured_without_verdicts() -> None:
    d = jc.drain(10, 0.0, prior_backlog=None, prior_at=None, now=NOW)
    assert d["status"] == "UNMEASURED"


def test_readmission_needs_real_history_growth(tmp_path: Path, monkeypatch) -> None:
    """One more hour of bars must not re-admit a spec that never fired on the whole history."""
    monkeypatch.setattr(jc, "_bar_bytes", lambda sym, tf="H1": 1_010_000)
    parked = (NOW - timedelta(days=1)).isoformat()
    never = {"sym": "EURUSD", "days": 0, "bar_bytes": 1_000_000, "parked_at": parked}
    assert not jc.readmit_due(never, now=NOW)
    monkeypatch.setattr(jc, "_bar_bytes", lambda sym, tf="H1": 1_260_000)
    assert jc.readmit_due(never, now=NOW)
    rare = {"sym": "EURUSD", "days": 30, "bar_bytes": 1_000_000, "parked_at": parked}
    assert not jc.readmit_due(rare, now=NOW), "30 days needs the history doubled to reach 60"
    monkeypatch.setattr(jc, "_bar_bytes", lambda sym, tf="H1": 2_000_000)
    assert jc.readmit_due(rare, now=NOW)


def test_readmission_after_max_wait(monkeypatch) -> None:
    monkeypatch.setattr(jc, "_bar_bytes", lambda sym, tf="H1": 1_000_000)
    old = {"sym": "X", "days": 0, "bar_bytes": 1_000_000,
           "parked_at": (NOW - timedelta(days=jc.READMIT_MAX_DAYS + 1)).isoformat()}
    assert jc.readmit_due(old, now=NOW)


def test_never_fire_pairs_need_volume_and_no_fired_sibling() -> None:
    bank = {f"c{i}": {"reason": "never_fires", "family": "f", "sym": "A"}
            for i in range(jc.SIBLING_NEVER_FIRES_MIN)}
    bank.update({f"d{i}": {"reason": "never_fires", "family": "f", "sym": "B"}
                 for i in range(jc.SIBLING_NEVER_FIRES_MIN)})
    bank.update({f"e{i}": {"reason": "never_fires", "family": "f", "sym": "C"} for i in range(3)})
    dead = jc.never_fire_pairs(bank, fired={("f", "B")})
    assert dead == {("f", "A")}


def test_fired_pairs_skip_unknown(tmp_path: Path) -> None:
    p = _ledger(tmp_path, [
        {"family": "f", "sym": "A", "terminal_gate": "UNKNOWN"},
        {"family": "f", "sym": "B", "terminal_gate": "in_sample_screen"}])
    assert jc.fired_pairs(p) == {("f", "B")}


def test_not_run_cells_are_named_and_parked(tmp_path: Path, monkeypatch) -> None:
    """A cell that could not be BUILT stops coming back at the head of every sweep."""
    report = tmp_path / "gates.json"
    report.write_text(json.dumps({"verdicts": [
        {"cell": "a", "sym": "EURUSD", "family": "f", "passed": None,
         "downstream_status": "NOT_RUN_DATA_MISSING",
         "why": "point-in-time M5 parquet is missing or empty"},
        {"cell": "b", "sym": "EURUSD", "family": "f", "passed": None,
         "downstream_status": "NOT_RUN_BUILD_FAILED", "why": "boom"},
        {"cell": "c", "sym": "EURUSD", "family": "f", "passed": None,
         "downstream_status": "NOT_RUN_BUILD_BUDGET_DEFERRED"}]}), "utf-8")
    monkeypatch.setattr(jc, "_bar_bytes", lambda sym, tf="H1": 0 if tf == "M5" else 5_000)
    named = jc.name_not_run(report)
    assert set(named) == {"a", "b"}, "a budget deferral is work not yet done, never parked"
    assert named["a"]["reason"] == "data_missing" and named["a"]["tf"] == "M5"
    assert named["b"]["reason"] == "build_failed"
    bank = tmp_path / "bank.json"
    res = jc.update_unrunnable_bank(named, at=NOW.isoformat(), path=bank)
    assert res["bank_size"] == 2


def test_data_missing_readmits_when_its_own_chart_appears(monkeypatch) -> None:
    row = {"sym": "EURUSD", "tf": "M5", "reason": "data_missing", "bar_bytes": 0,
           "parked_at": NOW.isoformat()}
    monkeypatch.setattr(jc, "_bar_bytes", lambda sym, tf="H1": 0 if tf == "M5" else 9_999)
    assert not jc.readmit_due(row, now=NOW), "H1 bars growing says nothing about the M5 chart"
    monkeypatch.setattr(jc, "_bar_bytes", lambda sym, tf="H1": 100)
    assert jc.readmit_due(row, now=NOW)


def test_build_failed_retries_after_a_week(monkeypatch) -> None:
    monkeypatch.setattr(jc, "_bar_bytes", lambda sym, tf="H1": 1_000)
    row = {"sym": "X", "tf": "H1", "reason": "build_failed", "bar_bytes": 1_000,
           "parked_at": (NOW - timedelta(days=2)).isoformat()}
    assert not jc.readmit_due(row, now=NOW)
    row["parked_at"] = (NOW - timedelta(days=jc.BUILD_FAILED_RETRY_DAYS + 0.1)).isoformat()
    assert jc.readmit_due(row, now=NOW)


def test_prewarm_share_counts_build_and_data_failures(tmp_path: Path) -> None:
    report = tmp_path / "gates.json"
    report.write_text(json.dumps({"prewarm": {"submitted": 100, "failures": {
        "NOT_RUN_DATA_MISSING": 40, "NOT_RUN_BUILD_FAILED": 29, "ERROR": 1}}}), "utf-8")
    assert jc._prewarm_share(report) == 0.7


def _fence_report(tmp_path: Path, totals: dict) -> Path:
    p = tmp_path / "JUDGE_COVERAGE.json"
    fams = {"f": {"unjudged": 0, "queued": 0, "judged_window": 1}}
    p.write_text(json.dumps({"at": NOW.isoformat(), "families": fams, "totals": totals,
                             "ranking": []}), "utf-8")
    return p


def test_fence_fails_when_the_backlog_grows_twice(tmp_path: Path) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import check_judge_coverage as fence

    doc = fence.judge(now=NOW, report=_fence_report(tmp_path, {"drain_status": "GROWING",
                                               "prior_drain_status": "GROWING"}))
    checks = {c["metric"]: c for c in doc["checks"]}
    assert checks["judge_keeps_pace"]["state"] == "FAIL"
    assert "never throttle" in checks["judge_keeps_pace"]["why"]
    doc = fence.judge(now=NOW, report=_fence_report(tmp_path, {"drain_status": "GROWING",
                                               "prior_drain_status": "DRAINING"}))
    assert {c["metric"]: c for c in doc["checks"]}["judge_keeps_pace"]["state"] == "WARN"


def test_fence_ratchets_prewarm_failures(tmp_path: Path) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import check_judge_coverage as fence

    doc = fence.judge(now=NOW, report=_fence_report(tmp_path, {"prewarm_fail_share": 0.5,
                                               "prior_prewarm_fail_share": 0.3}))
    assert {c["metric"]: c for c in doc["checks"]}["prewarm_fail_ratchet"]["state"] == "FAIL"
    doc = fence.judge(now=NOW, report=_fence_report(tmp_path, {"prewarm_fail_share": 0.2,
                                               "prior_prewarm_fail_share": 0.3}))
    assert {c["metric"]: c for c in doc["checks"]}["prewarm_fail_ratchet"]["state"] == "OK"


def test_refresh_bars_asks_for_the_charts_the_judge_wanted(tmp_path: Path) -> None:
    from research import hourly_cycle as hc

    rep = tmp_path / "JUDGE_COVERAGE.json"
    rep.write_text(json.dumps({"bars_wanted": {"EURUSD_M5": 3, "EURUSD_M1": 4,
                                               "GBPJPY_M15": 5, "USDMXN_H1": 1}}), "utf-8")
    assert hc.bars_wanted_symbols(rep) == ["EURUSD", "GBPJPY", "USDMXN"]
    assert hc.bars_wanted_symbols(tmp_path / "absent.json") == []
