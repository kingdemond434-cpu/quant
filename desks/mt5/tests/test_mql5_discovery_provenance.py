"""Each MQL5 adapter hands the same stamped row to disk and its next consumer."""
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
def test_adapter_publishes_provenance_before_returning(tmp_path, monkeypatch, name, miner):
    module = importlib.import_module("side_channels." + name)
    monkeypatch.setattr(module, "OUT", tmp_path)
    original = {"source": name, "url": "https://www.mql5.com/example", "title": "example"}
    monkeypatch.setattr(module, miner, lambda: [original])
    emitted = module.run_and_save()
    stored = json.loads(next(tmp_path.glob("*.json")).read_text("utf-8"))
    assert emitted == stored
    assert stored[0]["payload_hash"]
    assert stored[0]["available_time"]
    assert stored[0]["ingested_time"]
    assert stored[0]["source_version"]
    assert stored[0]["url"] == original["url"]
    assert "payload_hash" not in original
