"""check_certification ages QQUANT_GATES.json by its swept_at, never by its mtime."""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from research.desk_self_heal import check_certification


def _write(root: Path, doc: dict) -> None:
    f = root / "desks/mt5/reports/QQUANT_GATES.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(doc), encoding="utf-8")


def test_fresh_mtime_old_swept_at_fails(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    _write(tmp_path, {"swept_at": "2026-09-12T00:00:00+00:00", "verdicts": []})
    f = check_certification(tmp_path, now)
    assert f.ok is False and "swept_at" in f.detail


def test_fresh_swept_at_passes(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    _write(tmp_path, {"swept_at": (now - timedelta(hours=1)).isoformat(),
                      "verdicts": [{"passed": True}, {"passed": False}]})
    f = check_certification(tmp_path, now)
    assert f.ok is True and "1 of 2" in f.detail


def test_missing_swept_at_is_unmeasured_not_fresh(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    _write(tmp_path, {"verdicts": []})
    f = check_certification(tmp_path, now)
    assert f.ok is False and "UNMEASURED" in f.detail
