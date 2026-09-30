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
    monkeypatch.setattr(jc, "_bar_bytes", lambda sym: 1_010_000)
    parked = (NOW - timedelta(days=1)).isoformat()
    never = {"sym": "EURUSD", "days": 0, "bar_bytes": 1_000_000, "parked_at": parked}
    assert not jc.readmit_due(never, now=NOW)
    monkeypatch.setattr(jc, "_bar_bytes", lambda sym: 1_260_000)
    assert jc.readmit_due(never, now=NOW)
    rare = {"sym": "EURUSD", "days": 30, "bar_bytes": 1_000_000, "parked_at": parked}
    assert not jc.readmit_due(rare, now=NOW), "30 days needs the history doubled to reach 60"
    monkeypatch.setattr(jc, "_bar_bytes", lambda sym: 2_000_000)
    assert jc.readmit_due(rare, now=NOW)


def test_readmission_after_max_wait(monkeypatch) -> None:
    monkeypatch.setattr(jc, "_bar_bytes", lambda sym: 1_000_000)
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
