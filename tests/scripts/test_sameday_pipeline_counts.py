from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path


def test_headline_counts_only_live_forward_clocks(tmp_path: Path, monkeypatch) -> None:
    import scripts.check_sameday_pipeline as check

    shadow = tmp_path / "shadow"
    shadow.mkdir()
    now = datetime.now(UTC).isoformat()
    (shadow / "shadow_state.json").write_text(json.dumps({
        "live": {"status": "ACTIVE", "n": 0, "forward_start": now,
                 "last_attempt_at": now},
        "old": {"status": "RETIRED_ORPHAN", "n": 7, "forward_start": now,
                "last_attempt_at": now},
    }), "utf-8")
    certs = tmp_path / "UNIVERSAL_SURVIVORS.json"
    certs.write_text(json.dumps({"survivors": {}}), "utf-8")
    report = tmp_path / "report.json"
    monkeypatch.setattr(check, "SHADOW", shadow)
    monkeypatch.setattr(check, "CERTS", certs)
    monkeypatch.setattr(check, "REPORT", report)
    monkeypatch.setattr(check, "ALARM", tmp_path / "alarm.txt")

    assert check.main() == 0
    got = json.loads(report.read_text("utf-8"))
    assert got["forward_clocks"] == 1
    assert got["retired_rows_preserved"] == 1
