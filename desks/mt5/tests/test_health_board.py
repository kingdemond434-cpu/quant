"""The health board: UNMEASURED is never GREEN, a failed leg is RED, and the desk is GREEN only
when every source is fresh and no organ is RED, AMBER or UNMEASURED."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from research import health_board as hb  # noqa: E402


def _now(h: float = 0.0) -> str:
    return (datetime.now(tz=UTC) - timedelta(hours=h)).isoformat()


def _write(p: Path, d: object) -> Path:
    p.write_text(json.dumps(d), "utf-8")
    return p


def _fixture(tmp: Path, organs: list[dict], events: list[dict], stall_age_h: float = 0.0,
             actions: list[str] | None = None) -> dict:
    rt = _write(tmp / "rt.json", {"generated_at": _now(), "organs": organs})
    ev = tmp / "ev.jsonl"
    ev.write_text("".join(json.dumps(e) + "\n" for e in events), "utf-8")
    acc = _write(tmp / "acc.json", {"at": _now(), "properties": {"AP1": {"status": "PASS",
                                                                         "measured": True}}})
    sw = _write(tmp / "sw.json", {"checked_at": _now(stall_age_h), "actions": actions or []})
    return hb.build(runtime=rt, events=ev, acceptance=acc, stall=sw, readers={})


def test_judge_verdicts() -> None:
    assert hb.judge({"state": "LIVE", "kind": "leg"}, {"kind": "LEG_DONE"})[0] == hb.GREEN
    assert hb.judge({"state": "LIVE", "kind": "leg"}, {"kind": "LEG_FAILED"})[0] == hb.RED
    assert hb.judge({"state": "LIVE", "kind": "leg"}, None)[0] == hb.AMBER
    assert hb.judge({"state": "MISSING"}, None)[0] == hb.RED
    assert hb.judge({"state": "STALE"}, {"kind": "LEG_DONE"})[0] == hb.RED
    assert hb.judge({"state": "NEVER"}, None)[0] == hb.UNMEASURED


def test_all_fresh_and_done_is_green(tmp_path: Path) -> None:
    doc = _fixture(tmp_path, [{"organ": "leg:a", "kind": "leg", "state": "LIVE"}],
                   [{"at": _now(), "kind": "LEG_DONE", "leg": "a"}])
    assert doc["desk_verdict"] == hb.GREEN


def test_unmeasured_organ_keeps_desk_off_green(tmp_path: Path) -> None:
    doc = _fixture(tmp_path, [{"organ": "leg:a", "kind": "leg", "state": "LIVE"},
                              {"organ": "leg:b", "kind": "leg", "state": "NEVER"}],
                   [{"at": _now(), "kind": "LEG_DONE", "leg": "a"}])
    assert doc["desk_verdict"] == hb.AMBER
    assert doc["counts"][hb.UNMEASURED] == 1


def test_failed_leg_is_red_and_stale_source_unmeasured(tmp_path: Path) -> None:
    doc = _fixture(tmp_path, [{"organ": "leg:a", "kind": "leg", "state": "LIVE"}],
                   [{"at": _now(), "kind": "LEG_FAILED", "leg": "a"}])
    assert doc["desk_verdict"] == hb.RED
    doc = _fixture(tmp_path, [{"organ": "leg:a", "kind": "leg", "state": "LIVE"}],
                   [{"at": _now(), "kind": "LEG_DONE", "leg": "a"}], stall_age_h=5.0,
                   actions=["FAILING MT5-Hourly"])
    assert doc["desk_verdict"] == hb.UNMEASURED            # stale watchdog: shown, not counted
    assert doc["box_tasks"]["stale_claims"] == ["FAILING MT5-Hourly"]
    assert "stall_watch" in doc["desk_verdict_why"]


def test_absent_sources_are_unmeasured(tmp_path: Path) -> None:
    doc = hb.build(runtime=tmp_path / "a", events=tmp_path / "b", acceptance=tmp_path / "c",
                   stall=tmp_path / "d", readers={"x": tmp_path / "X.json"})
    assert doc["desk_verdict"] == hb.UNMEASURED
    assert "Desk verdict: UNMEASURED" in hb.render_md(doc)
