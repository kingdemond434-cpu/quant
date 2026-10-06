"""Each MQL5 adapter's hourly artifact passes the canonical provenance door -- and since
2026-10-06 that artifact is the BLOCKED_TERMS refusal row, never a fetch (mql5_terms)."""
import importlib
import json
import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
if str(DESK) not in sys.path:
    sys.path.insert(0, str(DESK))


@pytest.mark.parametrize("name,miner", [
    ("mql5_articles", "mine_articles"),
    ("mql5_forum", "mine_forum"),
    ("mql5_codebase", "mine_codebase"),
    ("mql5_signals", "mine_signals"),
])
def test_adapter_publishes_a_stamped_refusal_and_never_mines(tmp_path, monkeypatch, name, miner):
    module = importlib.import_module("side_channels." + name)
    monkeypatch.setattr(module, "OUT", tmp_path)
    monkeypatch.setattr(module, "REFUSAL", tmp_path / module.REFUSAL.name)

    def _never() -> list:
        raise AssertionError(f"{name}.{miner} ran: the terms fence must refuse before mining")

    monkeypatch.setattr(module, miner, _never)
    emitted = module.run_and_save()
    assert emitted == []
    stored = json.loads(next(tmp_path.glob("*.json")).read_text("utf-8"))
    assert len(stored) == 1
    row = stored[0]
    assert row["kind"] == "walled" and row["verdict"] == "BLOCKED_TERMS"
    assert row["source"] == name
    assert row["payload_hash"]
    assert row["available_time"]
    assert row["ingested_time"]
    assert row["source_version"]
    assert row["url"] == "https://www.mql5.com/en/about/terms"
