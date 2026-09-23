import json
from datetime import UTC, datetime, timedelta

from scripts import check_miner_conversion as audit


def test_discovery_file_is_counted_once(tmp_path, monkeypatch):
    source = tmp_path / "news"
    source.mkdir()
    (source / "discoveries_today.json").write_text(json.dumps([{"title": "one"}]))
    monkeypatch.setattr(audit, "INTEL", [tmp_path])
    rows = audit.miner_rows(datetime.now(UTC) - timedelta(days=1))
    assert len(rows["news"]) == 1


def test_absent_mechanisms_cannot_be_duplicate_evidence():
    assert audit._mechanism_key({"title": "central bank surprise"}) is None
    assert audit._mechanism_key({"title": "swap observation"}) is None
    assert audit._mechanism_key({"family": "unknown"}) is None


def test_exposure_normalization_is_preserved():
    assert audit._mechanism_key({"family": "Trend", "symbol": "eurusd", "session": "ASIA"}) == (
        audit._mechanism_key({"family": "trend", "sym": "EURUSD", "window": "asia"}))
