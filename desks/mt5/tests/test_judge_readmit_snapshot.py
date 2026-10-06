"""Re-admission measures a chart once per pass without retaining stale bar sizes."""
from datetime import UTC, datetime

from research import judge_coverage as jc


def test_bank_snapshots_each_chart_and_refreshes_next_pass(tmp_path, monkeypatch):
    now = datetime.now(UTC).isoformat()
    rows = {
        "one": {"sym": "USDJPY", "tf": "H1", "bar_bytes": 100,
                "days": 0, "parked_at": now},
        "two": {"sym": "USDJPY", "tf": "H1", "bar_bytes": 100,
                "days": 0, "parked_at": now},
        "other_chart": {"sym": "USDJPY", "tf": "M15", "bar_bytes": 100,
                        "days": 0, "parked_at": now},
    }
    import json
    target = tmp_path / "bank.json"
    target.write_text(json.dumps(rows), encoding="utf-8")
    calls = []
    size = {"H1": 100, "M15": 125}

    def measured(sym, tf):
        calls.append((sym, tf))
        return size[tf]

    monkeypatch.setattr(jc, "_bar_bytes", measured)
    first = jc.update_unrunnable_bank({}, at=now, path=target)
    assert calls == [("USDJPY", "H1"), ("USDJPY", "M15")]
    assert first["readmitted_on_bar_growth"] == 1
    assert first["bank_size"] == 2
    calls.clear()
    size["H1"] = 125
    second = jc.update_unrunnable_bank({}, at=now, path=target)
    assert calls == [("USDJPY", "H1")]
    assert second["readmitted_on_bar_growth"] == 2
    assert second["bank_size"] == 0


def test_direct_readmit_does_not_cache_between_calls(monkeypatch):
    row = {"sym": "USDJPY", "tf": "H1", "bar_bytes": 100, "days": 0}
    measurements = iter([100, 125])
    monkeypatch.setattr(jc, "_bar_bytes", lambda *args: next(measurements))
    assert jc.readmit_due(row) is False
    assert jc.readmit_due(row) is True
