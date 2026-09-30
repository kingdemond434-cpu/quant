"""THE TEST THAT FAILS IF A SILENT PERMANENT HALT CAN RECUR.

On 2026-09-24 the live gold book placed nothing at 10:00Z or 14:00Z. The gateway wrote 583
`release_identity_refused` rows that day -- one a minute -- and not one of them reached an
alert, a dashboard or a human; the principal found it by eye. The first such row is
2026-09-07T07:35:15Z, so the condition had been costing windows for seventeen days while every
organ reported healthy.

Two things are pinned here, and they are different claims:

  1. `scripts/check_placement_interlock.py` SEES the halt -- given the ledger the box actually
     had that day, it fails.
  2. The fence is WIRED. A checker nobody runs is the same silence with more files in it, which
     is the defect this whole area keeps producing (LAWS III.16: unwired or idle is a defect).

The seal-classification half is pinned in `desks/mt5/tests/test_release_identity.py`; this file
is about the halt being audible, not about why it happened.
"""
from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location(
    "check_placement_interlock", ROOT / "scripts" / "check_placement_interlock.py")
assert _SPEC and _SPEC.loader
fence = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(fence)

LEDGER = "desks/mt5/data/decision_ledger.jsonl"
GATEWAY_STATE = "desks/mt5/data/gateway_state.json"
IDENTITY = "desks/mt5/data/release_identity.json"

NOW = datetime(2026, 9, 24, 16, 50, tzinfo=UTC)


def _write(root: Path, rel: str, text: str) -> Path:
    p = root / Path(*rel.split("/"))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, "utf-8")
    return p


def _rows(n: int, *, sleeve: str, reason: str, start: datetime,
          step_s: int = 60, taken: bool = False) -> list[str]:
    out = []
    for i in range(n):
        out.append(json.dumps({
            "decided_at": (start + timedelta(seconds=i * step_s)).isoformat(),
            "sleeve": sleeve, "strategy_id": sleeve, "symbol": "XAUUSD",
            "reason": reason, "taken": taken,
            "outcome": "EXECUTED" if taken else "VENUE_UNAVAILABLE",
        }))
    return out


@pytest.fixture
def box(tmp_path: Path) -> Path:
    """A host that places orders: it has a gateway state, so silence is measurable."""
    _write(tmp_path, GATEWAY_STATE, json.dumps({"armed": True, "last_reconcile": NOW.isoformat()}))
    return tmp_path


# --------------------------------------------------------------- 1. the fence sees the halt
def test_the_day_the_gold_book_went_quiet_is_a_failure(box: Path) -> None:
    """The measured shape of 2026-09-24: one placement early, then refusals all day."""
    rows = _rows(2, sleeve="gold_asia", reason="placed",
                 start=NOW - timedelta(hours=11), taken=True)
    rows += _rows(398, sleeve="gold_london_am", reason="release_identity_refused",
                  start=NOW - timedelta(hours=6, minutes=38))
    _write(box, LEDGER, "\n".join(rows) + "\n")

    doc = fence.scan(box, now=NOW)

    assert doc["ok"] is False, doc
    assert doc["verdict"] == "HALTED"
    assert any("gold_london_am" in p for p in doc["problems"]), doc["problems"]
    run = doc["runs"]["gold_london_am"]
    assert run["count"] == 398
    assert run["reason"] == "release_identity_refused"
    assert run["span_h"] is not None and run["span_h"] > fence.TRAILING_HOURS_MAX


def test_a_halt_is_caught_by_duration_even_when_the_row_count_is_small(box: Path) -> None:
    """A gateway that passes every ten minutes writes far fewer rows for the same outage. A
    fence that only counted rows would miss it entirely."""
    _write(box, LEDGER, "\n".join(_rows(
        6, sleeve="gold_afternoon", reason="release_identity_refused",
        start=NOW - timedelta(hours=3), step_s=1800)) + "\n")

    doc = fence.scan(box, now=NOW)

    assert doc["ok"] is False
    assert doc["runs"]["gold_afternoon"]["count"] < fence.TRAILING_REFUSALS_MAX
    assert any("gold_afternoon" in p for p in doc["problems"])


def test_the_fence_is_not_keyed_to_todays_reason_string(box: Path) -> None:
    """The next halt will carry a different `reason`. A fence written around
    `release_identity_refused` would be silent for it in exactly the same way."""
    _write(box, LEDGER, "\n".join(_rows(
        120, sleeve="gold_asia", reason="some_future_veto_nobody_has_written_yet",
        start=NOW - timedelta(hours=2))) + "\n")

    doc = fence.scan(box, now=NOW)

    assert doc["ok"] is False
    assert any("some_future_veto_nobody_has_written_yet" in p for p in doc["problems"])


def test_a_placement_clears_the_run(box: Path) -> None:
    """Refusals BEFORE a placement are history, not a halt -- otherwise the fence would stay red
    forever on a ledger that never forgets, and a permanently red fence gets switched off."""
    rows = _rows(300, sleeve="gold_asia", reason="release_identity_refused",
                 start=NOW - timedelta(hours=9))
    rows += _rows(2, sleeve="gold_asia", reason="placed",
                  start=NOW - timedelta(minutes=5), taken=True)
    _write(box, LEDGER, "\n".join(rows) + "\n")

    doc = fence.scan(box, now=NOW)

    assert doc["ok"] is True, doc["problems"]
    assert "gold_asia" not in doc["runs"]


def test_the_venues_own_answer_is_reported_not_breached(box: Path) -> None:
    """A run of broker rejections is the market saying no, not the desk declining to trade.
    Breaching on it would teach the desk to treat a rail as a bug."""
    _write(box, LEDGER, "\n".join(_rows(
        90, sleeve="gold_london_am", reason="broker_rejected",
        start=NOW - timedelta(hours=2))) + "\n")

    doc = fence.scan(box, now=NOW)

    assert doc["ok"] is True, doc["problems"]
    assert any("broker_rejected" in n for n in doc["notes"])


def test_a_refusing_identity_fails_even_with_no_ledger_rows(box: Path) -> None:
    """Breach (b). The one failure a ledger-shaped fence cannot see is a gateway that stops
    writing rows at all -- so the verdict itself is read directly."""
    _write(box, LEDGER, "\n".join(_rows(
        1, sleeve="gold_asia", reason="placed", start=NOW - timedelta(minutes=2),
        taken=True)) + "\n")
    _write(box, IDENTITY, json.dumps({
        "verdict": "REFUSED", "allows_new_risk": False, "ok": False,
        "at": (NOW - timedelta(minutes=1)).isoformat(),
        "reason": "running f08c1fcf4ab2 carries 139 path(s) the sealed release never named"}))

    doc = fence.scan(box, now=NOW)

    assert doc["ok"] is False
    assert any("refuses new risk" in p for p in doc["problems"]), doc["problems"]


# --------------------------------------------------- 2. applicability: red everywhere is off
def test_a_host_that_places_nothing_is_not_applicable(tmp_path: Path) -> None:
    """CI, a fresh clone and the VPS never place an order. A fence red on every machine that was
    never supposed to trade is a fence somebody switches off (L1.43)."""
    doc = fence.scan(tmp_path, now=NOW)
    assert doc["verdict"] == "NOT_APPLICABLE"
    assert doc["ok"] is True


def test_a_gateway_host_with_no_ledger_is_unmeasured_and_fails(box: Path) -> None:
    """UNMEASURED is a verdict, not a pass (L1.28a, WS-005). No evidence is exactly what the
    outage looked like."""
    doc = fence.scan(box, now=NOW)
    assert doc["verdict"] == "UNMEASURED"
    assert doc["ok"] is False


def test_an_unreadable_ledger_is_unmeasured_not_healthy(box: Path) -> None:
    _write(box, LEDGER, "")
    doc = fence.scan(box, now=NOW)
    assert doc["verdict"] == "UNMEASURED"
    assert doc["ok"] is False


# ------------------------------------------------------------------- 3. the fence is WIRED
def test_the_fence_runs_on_a_clock() -> None:
    """A checker nobody runs is the same silence with more files in it (LAWS III.16). This is
    the assertion that would have failed on 2026-09-23, when the halt was already 17 days old
    and no registered gate looked at the decision ledger at all."""
    gate = (ROOT / "scripts" / "run_law_gate.py").read_text("utf-8")
    assert "check_placement_interlock.py" in gate, (
        "check_placement_interlock.py is not registered in run_law_gate.py -- an unwired fence "
        "is a claim the desk cannot cash (L1.49)")


def test_the_fence_never_caps_or_gates_capital() -> None:
    """GROWTH GOVERNANCE. This file may make the book trade MORE by ending halts sooner; it must
    never be the thing that makes it trade less. Nothing here may write a sleeve, a lot or a
    threshold."""
    src = (ROOT / "scripts" / "check_placement_interlock.py").read_text("utf-8")
    for forbidden in ("sleeves.json", "risk_frac", "heat_floor", "gate_spec",
                      "UNIVERSAL_SURVIVORS"):
        assert forbidden not in src, f"the halt fence must not touch {forbidden}"


def test_thresholds_are_small_enough_to_catch_the_day_it_happens() -> None:
    """Thirty rows at one a minute is half an hour: short enough that a lost window is caught
    the same session, long enough that one contended seal does not page anybody. If a later
    session widens these, it is choosing to be blind for longer and this says so."""
    assert fence.TRAILING_REFUSALS_MAX <= 60
    assert fence.TRAILING_HOURS_MAX <= 2.0


# ------------------------------------------------------ 4. the halt reaches the event log
def test_a_halt_is_written_to_the_event_log(box: Path, tmp_path: Path,
                                            monkeypatch: pytest.MonkeyPatch) -> None:
    """LOUD means every surface: the artifact, the alert ledger AND the event log a dashboard or
    a consumer reads. A clean pass is recorded too, so silence is never the evidence."""
    from libs.ops import events
    log = tmp_path / "events.jsonl"
    monkeypatch.setattr(events, "PATH", log)
    _write(box, LEDGER, "\n".join(_rows(
        45, sleeve="gold_london_am", reason="release_identity_refused",
        start=NOW - timedelta(minutes=45))) + "\n")
    doc = fence.scan(box, now=NOW)
    assert fence.record_event(doc, ROOT) == "PLACEMENT_HALTED"
    row = json.loads(log.read_text("utf-8").splitlines()[-1])
    assert row["kind"] == "PLACEMENT_HALTED"
    assert row["sleeves"] == ["gold_london_am"]
    assert "unknown_kind" not in row

    _write(box, LEDGER, "\n".join(_rows(
        1, sleeve="gold_london_am", reason="placed", start=NOW, taken=True)) + "\n")
    assert fence.record_event(fence.scan(box, now=NOW), ROOT) == "PLACEMENT_CLEAR"
    assert fence.record_event(fence.scan(tmp_path / "nowhere", now=NOW), ROOT) is None
