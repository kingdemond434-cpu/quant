"""The off-box reader of the box's outside alarm: absent or torn is UNMEASURED, an old reading
is STALE, and only a fresh SENT ping is ARMED."""
from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("_quant_check_box_heartbeat",
                                               ROOT / "scripts" / "check_box_heartbeat.py")
assert _spec is not None and _spec.loader is not None
fence = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fence)

NOW = datetime(2026, 10, 13, 21, 30, tzinfo=UTC)


def _doc(age_min: float, ping: str | None) -> str:
    d: dict = {"at": (NOW - timedelta(minutes=age_min)).isoformat(), "verdict": "OK",
               "failing": []}
    if ping is not None:
        d["ping"] = {"status": ping}
    return json.dumps(d)


def test_absent_and_torn_are_unmeasured() -> None:
    assert fence.judge(None, NOW)["verdict"] == "UNMEASURED"
    assert fence.judge('{"at": "2026-10-13T21:2', NOW)["verdict"] == "UNMEASURED"
    assert fence.judge('{"verdict": "OK"}', NOW)["verdict"] == "UNMEASURED"


def test_an_old_reading_is_stale_whatever_it_claims() -> None:
    r = fence.judge(_doc(fence.MAX_AGE_MIN + 1, "SENT"), NOW)
    assert r["verdict"] == "STALE"


def test_only_a_fresh_sent_ping_is_armed() -> None:
    assert fence.judge(_doc(5, "SENT"), NOW)["verdict"] == "ARMED"
    for status in ("NOT_ARMED", "ERROR", "DRY_RUN", None):
        assert fence.judge(_doc(5, status), NOW)["verdict"] == "NOT_ARMED"


def test_the_age_line_is_two_publications() -> None:
    assert fence.MAX_AGE_MIN == 40


def test_exit_code_is_zero_only_when_armed(tmp_path: Path) -> None:
    p = tmp_path / "BOX_HEARTBEAT.json"
    p.write_text(_doc(0, "NOT_ARMED"))
    assert fence.main(["--file", str(p)]) == 1
    p.write_text(json.dumps({"at": datetime.now(UTC).isoformat(), "ping": {"status": "SENT"}}))
    assert fence.main(["--file", str(p)]) == 0
    assert fence.main(["--file", str(tmp_path / "absent.json")]) == 1


def test_the_reader_names_the_published_report() -> None:
    hb = (ROOT / "desks" / "mt5" / "scripts" / "box_heartbeat.py").read_text("utf-8")
    assert 'BASE / "reports" / "BOX_HEARTBEAT.json"' in hb
    assert fence.REPORT_REL == "desks/mt5/reports/BOX_HEARTBEAT.json"
