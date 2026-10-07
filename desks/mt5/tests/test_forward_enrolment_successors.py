"""THE SUCCESSOR QUEUE HAS A READER: forward_enrolment answers every open successor hunt.

`hazard_engine` appends `successor_search` rows to data/hypotheses/successor_queue.jsonl. A file
with no reader is a defect on this desk (audit 2026-10-07, must-fix 3), so the hourly leg that
owns forward evidence reads it and says, per incumbent, whether a named replacement is accruing
-- and repairs the ones that are not. Every test writes under tmp_path.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import forward_enrolment as fe  # noqa: E402
from research import hazard_engine as hz  # noqa: E402

NOW = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
UNM = fe.UNMEASURED


def _cert(symbol: str, family: str, **kw: object) -> dict:
    return {"key": f"{symbol}.{family}.asia.LONG", "symbol": symbol, "family": family,
            "enrolled": True, "accruing": True, **kw}


def _queue(tmp: Path, *rows: dict) -> Path:
    p = tmp / "successor_queue.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\nnot json\n", "utf-8")
    return p


def _row(name: str, *cands: tuple[str, str], hours_ago: float = 1.0, **kw: object) -> dict:
    return {"kind": "successor_search", "for": name, "symbol": "EURUSD", "family": "inc",
            "at": (NOW - timedelta(hours=hours_ago)).isoformat(timespec="seconds"),
            "replacement_candidates": [{"cell": f"h.{s}.{f}", "symbol": s, "family": f}
                                       for s, f in cands], **kw}


def test_the_reader_reads_the_writers_file() -> None:
    assert fe.SUCCESSOR_QUEUE == hz.QUEUE


def test_the_leg_publishes_the_hunt_and_is_scheduled() -> None:
    src = (_DESK / "research" / "forward_enrolment.py").read_text("utf-8")
    assert '"successor_hunt": hunt' in src and "successor_hunt(body" in src
    cyc = (_DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_costed("forward_enrolment"' in cyc and "research/forward_enrolment.py" in cyc


def test_absent_queue_is_a_state_not_an_all_clear(tmp_path) -> None:
    out = fe.successor_hunt({"certificates": []}, tmp_path / "none.jsonl", NOW)
    assert out["status"] == "NO_QUEUE" and out["why"] and out["n_open"] == 0


def test_each_open_hunt_is_answered_and_stalled_candidates_are_repaired(tmp_path) -> None:
    body = {"certificates": [
        _cert("GBPUSD", "carry"),                                           # accruing
        _cert("AUDUSD", "gap", enrolled=False, accruing=UNM),               # no clock
        _cert("NZDUSD", "drift", accruing=False, blocker="BLOCKED_NO_BARS"),
    ]}
    q = _queue(tmp_path,
               _row("covered", ("GBPUSD", "carry"), ("AUDUSD", "gap")),
               _row("stalled", ("AUDUSD", "gap"), ("NZDUSD", "drift"), ("USDJPY", "x"),
                    trigger="tradability_health", state="STANDBY"),
               _row("orphan"),
               _row("cleared", ("AUDUSD", "gap"), hours_ago=fe.SUCCESSOR_OPEN_H + 1))
    out = fe.successor_hunt(body, q, NOW)
    by = {h["for"]: h for h in out["hunts"]}
    assert set(by) == {"covered", "stalled", "orphan"}           # the cleared hunt is closed
    assert by["covered"]["hunt"] == fe.HUNT_COVERED
    assert by["stalled"]["hunt"] == fe.HUNT_STALLED
    assert by["stalled"]["state"] == "STANDBY"
    assert by["stalled"]["trigger"] == "tradability_health"
    assert [c["state"] for c in by["stalled"]["candidates"]] == ["NO_CLOCK", "BLOCKED",
                                                                  "NOT_ADMITTED"]
    assert by["orphan"]["hunt"] == fe.HUNT_NO_CANDIDATE
    assert [h["for"] for h in out["hunts"]] == ["orphan", "stalled", "covered"]
    assert out["n_open"] == 3 and out["n_covered"] == 1 and out["n_stalled"] == 1
    assert out["n_no_candidate"] == 1 and out["n_malformed"] == 1
    assert set(out["repair_keys"]) == {"AUDUSD.gap.asia.LONG", "NZDUSD.drift.asia.LONG"}
    assert out["oldest_uncovered_h"] == 1.0


def test_the_newest_row_per_incumbent_wins(tmp_path) -> None:
    body = {"certificates": [_cert("GBPUSD", "carry")]}
    q = _queue(tmp_path, _row("a", hours_ago=30.0), _row("a", ("GBPUSD", "carry"), hours_ago=2.0))
    out = fe.successor_hunt(body, q, NOW)
    assert [h["hunt"] for h in out["hunts"]] == [fe.HUNT_COVERED]


def test_run_publishes_the_hunt_and_sends_blocked_successors_to_repair(tmp_path,
                                                                     monkeypatch) -> None:
    run = {"symbol": "NZDUSD", "family": "drift", "selector": "asia", "side": "LONG",
           "params": {}}
    key = "NZDUSD.drift.asia.LONG"
    monkeypatch.setattr(fe, "_run_key", lambda r: key)
    monkeypatch.setattr(fe, "certificates", lambda: ([run], [], ""))
    monkeypatch.setattr(fe, "clock_rows", lambda *a: {key: {
        "status": "BLOCKED_NO_BARS", "lane": "shadow_state.json", "last_error": "no bars"}})
    monkeypatch.setattr(fe, "certification_stamps", lambda: {})
    monkeypatch.setattr(fe, "integrity_gate", lambda: (None, "stub"))
    monkeypatch.setattr(fe, "SUCCESSOR_QUEUE", _queue(tmp_path, _row("inc", ("NZDUSD", "drift"))))
    seen: list[list[dict]] = []

    def fake_repair(missing, deadline, engine=None):
        seen.append(missing)
        return {"status": "SKIPPED_BUDGET", "n_missing": len(missing)}

    monkeypatch.setattr(fe, "repair", fake_repair)
    payload = fe.run(write=False, now=NOW, budget_s=5.0)
    assert [e["key"] for e in seen[0]] == [key]
    assert payload["repair"]["successor_keys"] == [key]
    assert payload["successor_hunt"]["hunts"][0]["hunt"] == fe.HUNT_STALLED
    assert "SUCCESSOR STALLED for inc" in fe.render(payload)
