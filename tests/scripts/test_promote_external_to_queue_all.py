from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "promote_external_to_queue", ROOT / "scripts" / "promote_external_to_queue.py"
)
assert SPEC and SPEC.loader
promoter = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = promoter
SPEC.loader.exec_module(promoter)


def test_every_fresh_exact_cell_is_projected_without_a_daily_quota(tmp_path: Path,
                                                                   monkeypatch) -> None:
    survivors = tmp_path / "external_survivors.json"
    queue = tmp_path / "research_queue.json"
    ledger = tmp_path / "queued_external.json"
    rows = [{"symbol": f"S{i}", "family": "f", "params": {"rr": i}, "t_stat": i}
            for i in range(20)]
    survivors.write_text(json.dumps(rows), "utf-8")
    queue.write_text("[]", "utf-8")
    monkeypatch.setattr(promoter, "SURV", survivors)
    monkeypatch.setattr(promoter, "QUEUE", queue)
    monkeypatch.setattr(promoter, "LEDGER", ledger)
    assert promoter.main() == 0
    projected = json.loads(queue.read_text("utf-8"))
    assert len(projected) == len(rows)
    assert all(row["status"] == "QUEUED_CANONICAL_GAUNTLET" for row in projected)


def test_reprojects_ledgered_cell_missing_from_queue_after_writer_regression(
        tmp_path: Path, monkeypatch) -> None:
    survivors = tmp_path / "external_survivors.json"
    queue = tmp_path / "research_queue.json"
    ledger = tmp_path / "queued_external.json"
    row = {"symbol": "XAUUSD", "family": "carry", "params": {"lookback": 20}}
    survivors.write_text(json.dumps([row]), "utf-8")
    queue.write_text("[]", "utf-8")
    ledger.write_text(json.dumps([promoter.key(row)]), "utf-8")
    monkeypatch.setattr(promoter, "SURV", survivors)
    monkeypatch.setattr(promoter, "QUEUE", queue)
    monkeypatch.setattr(promoter, "LEDGER", ledger)

    assert promoter.main() == 0
    projected = json.loads(queue.read_text("utf-8"))
    assert len(projected) == 1
    assert projected[0]["external_screen"]["symbol"] == "XAUUSD"
