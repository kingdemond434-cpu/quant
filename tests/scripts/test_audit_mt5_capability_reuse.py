from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from scripts.audit_mt5_capability_reuse import audit


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, "utf-8")


def test_audit_traverses_transitive_shared_organs_and_exposes_unwired(tmp_path: Path) -> None:
    _write(tmp_path / "libs" / "validation" / "gate.py", "from libs.core.ids import stable\n")
    _write(tmp_path / "libs" / "core" / "ids.py", "def stable(): return 1\n")
    _write(tmp_path / "libs" / "portfolio" / "orphan.py", "VALUE = 1\n")
    _write(tmp_path / "libs" / "execution" / "binance_live.py", "VALUE = 1\n")
    _write(
        tmp_path / "desks" / "mt5" / "research" / "consumer.py",
        "from libs.validation.gate import stable\n",
    )

    payload = audit(tmp_path, now=datetime(2026, 8, 22, tzinfo=UTC))
    rows = {row["module"]: row for row in payload["rows"]}

    assert rows["libs.validation.gate"]["status"] == "REACHABLE_MT5_STATIC"
    assert rows["libs.core.ids"]["status"] == "REACHABLE_MT5_STATIC"
    assert rows["libs.portfolio.orphan"]["status"] == "UNWIRED_REVIEW"
    assert rows["libs.execution.binance_live"]["status"] == "VENUE_SPECIFIC_REVIEW"
    assert rows["libs.validation.gate"]["direct_mt5_consumers"] == [
        "desks/mt5/research/consumer.py"
    ]
