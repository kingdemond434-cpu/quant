"""THE TEST THAT FAILS IF AN ORGAN CAN RUN, SUCCEED AND PRODUCE NOTHING IN SILENCE.

On 2026-09-24 twelve intelligence seats had donated nothing for a day. Five were not stubs:
`event_response_atlas` had written 258 artifacts and stopped, `graveyard_resurrection` 220,
`research_tree` 138, `fbs_tape` 82, `axis_registry` 45. Four of the five logged `LEG_DONE
outcome=ok` EVERY HOUR while producing nothing, rewriting their own reports faithfully on the way
past; the fifth logged `LEG_FAILED outcome=TIMEOUT` on every run for a day and a half. Three
fences already watched this ground and none of them joined "it ran" to "its output moved", so a
broken donation door and a healthy organ were the same picture.

What is pinned here, and they are different claims:

  1. The fence SEES each shape -- the silent no-op, the organ that reports but produces nothing,
     and the leg that fails every single time (which `check_leg_rotation` counts as attendance).
  2. It does NOT see shapes that are not defects -- a mirror host, a producer having one quiet
     hour, an organ that has simply not been observed enough to convict.
  3. It is WIRED. A checker nobody runs is the same silence with more files in it (LAWS III.16).
  4. It gates no capital and caps nothing, in either direction.
"""
from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location(
    "check_organ_cadence", ROOT / "scripts" / "check_organ_cadence.py")
assert _SPEC and _SPEC.loader
fence = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(fence)

LEDGER = "docs/research/tier1_program.json"
EVENTS = "desks/mt5/data/events.jsonl"
DEBT = "docs/research/organ_cadence_debt.json"

NOW = datetime(2026, 9, 24, 22, 0, tzinfo=UTC)


def _write(root: Path, rel: str, text: str) -> Path:
    p = root / Path(*rel.split("/"))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, "utf-8")
    return p


def _touch(path: Path, when: datetime) -> None:
    import os
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("{}", "utf-8")
    os.utime(path, (when.timestamp(), when.timestamp()))


def _events(rows: list[tuple[str, datetime, bool]]) -> str:
    return "\n".join(json.dumps({
        "at": when.isoformat(timespec="seconds"),
        "kind": "LEG_DONE" if ok else "LEG_FAILED", "leg": leg,
        "outcome": "ok" if ok else "TIMEOUT",
    }) for leg, when, ok in rows) + "\n"


def _declare_ledger(root: Path, legs: dict[str, str]) -> None:
    """`scheduled_by` + `artifact`, the two fields the repo already carries."""
    _write(root, LEDGER, json.dumps({"items": [
        {"id": f"T{i}", "scheduled_by": f"hourly_cycle:{leg}", "artifact": art}
        for i, (leg, art) in enumerate(legs.items())]}))


@pytest.fixture
def box(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A host that RUNS the clocks: its artifact mtimes mean something."""
    monkeypatch.setattr(fence, "runs_clocks_here", lambda _root: True)
    (tmp_path / "desks" / "mt5" / "reports").mkdir(parents=True, exist_ok=True)
    return tmp_path


# ------------------------------------------------------- 1. the fence sees each dark shape
def test_an_organ_that_exits_zero_and_writes_nothing_is_a_failure(box: Path) -> None:
    """SILENT_NOOP: the measured shape of `event_response_atlas` -- 15 clean runs, no write."""
    _declare_ledger(box, {"event_response_atlas": "desks/mt5/reports/ERA.json"})
    _touch(box / "desks" / "mt5" / "reports" / "ERA.json", NOW - timedelta(hours=72))
    _write(box, EVENTS, _events([("event_response_atlas", NOW - timedelta(hours=h), True)
                                 for h in range(15, 0, -1)]))

    doc = fence.scan(box, now=NOW)

    assert doc["ok"] is False, doc
    assert doc["verdict"] == "DARK"
    row = next(r for r in doc["organs"] if r["organ"] == "event_response_atlas")
    assert row["verdict"] == "SILENT_NOOP"
    assert row["runs_ok_in_window"] == 15
    assert any("event_response_atlas" in p for p in doc["problems"])


def test_reporting_is_not_producing(box: Path) -> None:
    """REPORTS_BUT_PRODUCES_NOTHING: `research_tree`'s shape. Its own report is written every
    hour -- which is the organ describing itself -- while the seat the compiler reads is frozen.
    A fence that watched only the report would have called this perfect health."""
    _declare_ledger(box, {"research_tree": "desks/mt5/reports/RESEARCH_TREE.json"})
    _touch(box / "desks" / "mt5" / "reports" / "RESEARCH_TREE.json", NOW - timedelta(minutes=45))
    _touch(box / "desks" / "mt5" / "data" / "intelligence" / "research_tree" / "d.json",
           NOW - timedelta(hours=36))
    _write(box, EVENTS, _events([("research_tree", NOW - timedelta(hours=h), True)
                                 for h in range(17, 0, -1)]))

    doc = fence.scan(box, now=NOW)

    row = next(r for r in doc["organs"] if r["organ"] == "research_tree")
    assert row["verdict"] == "REPORTS_BUT_PRODUCES_NOTHING", row
    assert row["self_age_h"] < 1.0
    assert row["product_age_h"] > 30.0
    assert doc["ok"] is False


def test_a_leg_that_fails_every_time_is_not_attendance(box: Path) -> None:
    """ALWAYS_FAILING: `axis_registry` timed out on every run for 31 hours, and the fence that
    asks whether a leg RAN counted all of them. Whether it WORKED is a different question."""
    _declare_ledger(box, {"axis_registry": "desks/mt5/reports/AXIS_REGISTRY.json"})
    _touch(box / "desks" / "mt5" / "reports" / "AXIS_REGISTRY.json", NOW - timedelta(minutes=10))
    _write(box, EVENTS, _events([("axis_registry", NOW - timedelta(hours=h), False)
                                 for h in range(11, 0, -1)]))

    doc = fence.scan(box, now=NOW)

    row = next(r for r in doc["organs"] if r["organ"] == "axis_registry")
    assert row["verdict"] == "ALWAYS_FAILING"
    assert row["runs_failed_in_window"] == 11 and row["runs_ok_in_window"] == 0
    assert doc["ok"] is False


def test_the_fence_is_not_keyed_to_todays_organ_names(box: Path) -> None:
    """The next organ to go dark has a name nobody has typed yet. The contract is read from the
    ledger, so an organ declared tomorrow is judged tomorrow with no edit here."""
    _declare_ledger(box, {"an_organ_invented_next_march": "desks/mt5/reports/X.json"})
    _touch(box / "desks" / "mt5" / "reports" / "X.json", NOW - timedelta(days=9))
    _write(box, EVENTS, _events([("an_organ_invented_next_march", NOW - timedelta(hours=h), True)
                                 for h in range(9, 0, -1)]))

    doc = fence.scan(box, now=NOW)

    assert doc["ok"] is False
    assert any("an_organ_invented_next_march" in p for p in doc["problems"])


# ----------------------------------------------- 2. and does NOT see what is not a defect
def test_a_producing_organ_passes(box: Path) -> None:
    _declare_ledger(box, {"good_organ": "desks/mt5/reports/GOOD.json"})
    _touch(box / "desks" / "mt5" / "reports" / "GOOD.json", NOW - timedelta(minutes=20))
    _touch(box / "desks" / "mt5" / "data" / "intelligence" / "good_organ" / "d.json",
           NOW - timedelta(minutes=25))
    _write(box, EVENTS, _events([("good_organ", NOW - timedelta(hours=h), True)
                                 for h in range(10, 0, -1)]))

    doc = fence.scan(box, now=NOW)

    assert doc["ok"] is True, doc["problems"]
    assert next(r for r in doc["organs"] if r["organ"] == "good_organ")["verdict"] == "LIVE"


def test_one_quiet_hour_is_searching_not_a_defect(box: Path) -> None:
    """A producer legitimately finds nothing on a pass -- that IS searching. A fence that called
    a single empty hour a defect would be switched off within the week, and then the real break
    is silent again (L1.43)."""
    _declare_ledger(box, {"miner": "desks/mt5/reports/MINER.json"})
    _touch(box / "desks" / "mt5" / "reports" / "MINER.json", NOW - timedelta(minutes=15))
    _touch(box / "desks" / "mt5" / "data" / "intelligence" / "miner" / "d.json",
           NOW - timedelta(hours=2))
    _write(box, EVENTS, _events([("miner", NOW - timedelta(hours=h), True)
                                 for h in range(12, 0, -1)]))

    doc = fence.scan(box, now=NOW)

    assert doc["ok"] is True, doc["problems"]
    assert next(r for r in doc["organs"] if r["organ"] == "miner")["verdict"] == "LIVE"


def test_too_few_runs_to_convict_is_not_a_conviction(box: Path) -> None:
    """Below MIN_OK_RUNS the organ has not been observed enough for 'it runs fine' to be a claim,
    and saying so is the honest answer rather than a guess in either direction."""
    _declare_ledger(box, {"new_organ": "desks/mt5/reports/NEW.json"})
    _touch(box / "desks" / "mt5" / "reports" / "NEW.json", NOW - timedelta(days=5))
    _write(box, EVENTS, _events([("new_organ", NOW - timedelta(hours=1), True)]))

    doc = fence.scan(box, now=NOW)

    assert doc["ok"] is True, doc["problems"]
    assert next(r for r in doc["organs"] if r["organ"] == "new_organ")["verdict"] == "LIVE"


def test_a_mirror_host_judges_nobody(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The build box holds the trading box's state and runs no cycle, so every artifact mtime
    there is a sync time. Convicting organs on a sync would report work that is happening
    correctly elsewhere as dark -- and a fence red on a machine that was never running the organ
    is one somebody switches off."""
    monkeypatch.setattr(fence, "runs_clocks_here", lambda _root: False)
    (tmp_path / "desks" / "mt5" / "reports").mkdir(parents=True, exist_ok=True)
    _declare_ledger(tmp_path, {"event_response_atlas": "desks/mt5/reports/ERA.json"})
    _touch(tmp_path / "desks" / "mt5" / "reports" / "ERA.json", NOW - timedelta(hours=72))
    _write(tmp_path, EVENTS, _events([("event_response_atlas", NOW - timedelta(hours=h), True)
                                      for h in range(15, 0, -1)]))

    doc = fence.scan(tmp_path, now=NOW)

    assert doc["verdict"] == "MIRROR_OF_ANOTHER_HOST"
    assert doc["ok"] is True
    # ...and it still PUBLISHES what it read, so the mirror is not also a blindfold.
    assert doc["n_organs"] == 1


def test_a_declared_organ_is_a_worklist_not_a_pass(box: Path) -> None:
    """A known-dark organ named in the debt does not fail the gate -- and it is still reported,
    so declaring is a promise to fix rather than a way to stop looking."""
    _declare_ledger(box, {"event_response_atlas": "desks/mt5/reports/ERA.json"})
    _touch(box / "desks" / "mt5" / "reports" / "ERA.json", NOW - timedelta(hours=72))
    _write(box, EVENTS, _events([("event_response_atlas", NOW - timedelta(hours=h), True)
                                 for h in range(15, 0, -1)]))
    _write(box, DEBT, json.dumps({"declared_max": 1, "declared": {
        "event_response_atlas": {"verdict": "SILENT_NOOP", "why": "private bonferroni bar",
                                 "owner": "liveness lane"}}}))

    doc = fence.scan(box, now=NOW)

    assert doc["ok"] is True, doc["problems"]
    assert any("event_response_atlas" in n for n in doc["notes"])
    assert doc["debt"]["n_breached"] == 1 and doc["debt"]["n_undeclared"] == 0


def test_the_declared_debt_may_only_shrink(box: Path) -> None:
    """The one way a debt list becomes a hiding place is by growing. It cannot."""
    _declare_ledger(box, {"a": "desks/mt5/reports/A.json", "b": "desks/mt5/reports/B.json"})
    for n in ("A", "B"):
        _touch(box / "desks" / "mt5" / "reports" / f"{n}.json", NOW - timedelta(hours=72))
    _write(box, EVENTS, _events([(leg, NOW - timedelta(hours=h), True)
                                 for leg in ("a", "b") for h in range(15, 0, -1)]))
    _write(box, DEBT, json.dumps({"declared_max": 1, "declared": {
        "a": {"why": "x"}, "b": {"why": "y"}}}))

    doc = fence.scan(box, now=NOW)

    assert doc["ok"] is False
    assert any("may only SHRINK" in p for p in doc["problems"])


# ----------------------------------------------------- 3. the seal's duty cycle per window
def test_a_window_that_closed_on_refusals_is_counted(box: Path) -> None:
    """The measurement the 2026-09-24 freeze needed: not 'is placement halted now' (the sibling
    fence answers that) but 'how many windows did the rail cost us'."""
    _declare_ledger(box, {"x": "desks/mt5/reports/X.json"})
    _touch(box / "desks" / "mt5" / "reports" / "X.json", NOW - timedelta(minutes=5))
    _write(box, EVENTS, _events([("x", NOW - timedelta(hours=1), True)]))
    rows = []
    for day in range(1, 4):                       # three days of refusals, none placed
        for i in range(40):
            rows.append(json.dumps({
                "decided_at": (NOW - timedelta(days=day, minutes=i)).isoformat(),
                "sleeve": "gold_asia", "reason": "release_identity_refused", "taken": False}))
    rows.append(json.dumps({"decided_at": (NOW - timedelta(days=4)).isoformat(),
                            "sleeve": "gold_asia", "reason": "placed", "taken": True}))
    _write(box, "desks/mt5/data/decision_ledger.jsonl", "\n".join(rows) + "\n")

    doc = fence.scan(box, now=NOW)
    seal = doc["seal_duty_cycle"]

    assert seal["available"] is True
    assert seal["windows_lost"] == 3 and seal["windows_placed"] == 1
    assert seal["lost_by_reason"]["release_identity_refused"] == 120


def test_windows_lost_carries_a_falling_ratchet(box: Path) -> None:
    _declare_ledger(box, {"x": "desks/mt5/reports/X.json"})
    _touch(box / "desks" / "mt5" / "reports" / "X.json", NOW - timedelta(minutes=5))
    _write(box, EVENTS, _events([("x", NOW - timedelta(hours=1), True)]))
    _write(box, "desks/mt5/data/decision_ledger.jsonl", "\n".join(json.dumps({
        "decided_at": (NOW - timedelta(days=d)).isoformat(), "sleeve": "gold_asia",
        "reason": "release_identity_refused", "taken": False}) for d in range(1, 5)) + "\n")
    _write(box, DEBT, json.dumps({"declared": {}, "windows_lost_max": 2}))

    doc = fence.scan(box, now=NOW)

    assert doc["ok"] is False
    assert any("without a placement" in p for p in doc["problems"])


# ------------------------------------------------------ 4. applicability and measurement
def test_a_host_that_runs_no_cycle_is_not_applicable(tmp_path: Path) -> None:
    """CI and a fresh clone run no organ. A fence red on every machine that was never supposed to
    run one is a fence somebody switches off (L1.43)."""
    doc = fence.scan(tmp_path, now=NOW)
    assert doc["verdict"] == "NOT_APPLICABLE"
    assert doc["ok"] is True


def test_a_cycle_host_with_no_event_log_is_unmeasured_and_fails(box: Path) -> None:
    """UNMEASURED is a verdict, not a pass (L1.28a). An organ plane that records no runs is
    exactly what a silent stall looks like."""
    _declare_ledger(box, {"x": "desks/mt5/reports/X.json"})
    _touch(box / "desks" / "mt5" / "reports" / "X.json", NOW)
    doc = fence.scan(box, now=NOW)
    assert doc["verdict"] == "UNMEASURED"
    assert doc["ok"] is False


def test_the_leg_token_is_normalised(box: Path) -> None:
    """`hourly_cycle._leg_artifacts` takes the token whole, so `hourly_cycle:causal_lab (macro
    department)` resolves to a leg that has never run. Measured on the box: 79 of 263 declaration
    rows -- 30% -- dropped on the floor by that parser."""
    _write(box, LEDGER, json.dumps({"items": [
        {"id": "T1", "scheduled_by": "hourly_cycle:causal_lab (macro department)",
         "artifact": "desks/mt5/reports/CAUSAL_LAB.json"}]}))
    _touch(box / "desks" / "mt5" / "reports" / "CAUSAL_LAB.json", NOW)
    organs, unparsed = fence.declared_organs(box)
    assert "causal_lab" in organs, organs
    assert unparsed == []


# ------------------------------------------------------------------- 5. the fence is WIRED
def test_the_fence_runs_on_a_clock() -> None:
    """A checker nobody runs is the same silence with more files in it (LAWS III.16)."""
    gate = (ROOT / "scripts" / "run_law_gate.py").read_text("utf-8")
    assert "check_organ_cadence.py" in gate, (
        "check_organ_cadence.py is not registered in run_law_gate.py -- an unwired fence is a "
        "claim the desk cannot cash (L1.49)")


def test_the_fence_never_caps_or_gates_capital() -> None:
    """GROWTH GOVERNANCE. This file exists to make more organs produce; it must never be the
    thing that makes the book smaller. Nothing here may write a sleeve, a lot or a threshold."""
    src = (ROOT / "scripts" / "check_organ_cadence.py").read_text("utf-8")
    for forbidden in ("sleeves.json", "risk_frac", "heat_floor", "gate_spec",
                      "UNIVERSAL_SURVIVORS", "fixed_trial_count"):
        assert forbidden not in src, f"the cadence fence must not touch {forbidden}"


def test_thresholds_catch_the_day_it_happens() -> None:
    """The real breaks were at 31, 36, 42, 72 and 72 hours. A window wider than a day, or a
    staleness allowance wider than a shift, is choosing to be blind for longer -- and this says
    so, so a later widening is a decision somebody makes on the record."""
    assert fence.WINDOW_H <= 24.0
    assert fence.PRODUCT_STALE_CADENCES <= 12.0
    assert fence.MIN_OK_RUNS >= 2, "one clean run is not evidence that an organ runs fine"


# ------------------------------- 6. THE STREAM THAT KEPT ITS CURSOR AND STOPPED KEEPING UP
#
# The shape neither existing channel can see. On 2026-09-25 `registry_sync` ran hourly, exited
# zero, advanced its cursor and rewrote its report every pass -- self channel perfect, product
# channel moving -- while the `gate_verdicts` cursor sat at byte 226,198 of a 54,119,184-byte
# ledger. 227,497 verdicts unpoured, the input growing 113x faster than the cursor advanced, and
# `judged_at` set on 1,278 candidates in the desk's whole history. "It ran" was true and "its
# output moved" was true and the funnel was still severed.


def _registry_at(tmp: Path, cursors: dict[str, int]):
    """A real registry at a temp path carrying the given cursor values."""
    import sys as _sys
    _sys.path.insert(0, str(ROOT))
    from libs.moat import registry as R
    R.set_path(tmp / "data" / "alpha_registry.sqlite")
    (tmp / "data").mkdir(parents=True, exist_ok=True)
    conn = R.connect()
    for key, value in cursors.items():
        conn.execute("INSERT OR REPLACE INTO sync_cursor(key, value, updated_at) VALUES(?,?,?)",
                     (key, str(value), "2026-09-25T00:00:00+00:00"))
    conn.commit()
    conn.close()
    return R


@pytest.fixture
def registry_box(box: Path):
    """A clock-running host with a real registry, restored to the canonical path afterwards."""
    import sys as _sys
    _sys.path.insert(0, str(ROOT))
    from libs.moat import registry as R
    before = R.path()
    yield box
    R.set_path(before)


def test_a_cursor_that_moves_but_never_keeps_up_is_a_severed_funnel(registry_box: Path) -> None:
    """THE REGRESSION. A cursor 0.42% through its input, on a host that runs the clocks."""
    led = "desks/mt5/data/hypotheses/gate_verdict_ledger.jsonl"
    _write(registry_box, led, "x" * 54_000_000)
    _registry_at(registry_box, {"gate_verdicts": 226_198})

    got = fence.stream_backlogs(registry_box)
    assert got["status"] == "MEASURED", got
    rec = next(r for r in got["streams"] if r["stream"] == "gate_verdicts")
    assert rec["verdict"] == "STREAM_DIVERGING", rec
    assert rec["unread_fraction"] > 0.99
    assert any(b["stream"] == "gate_verdicts" for b in got["breaches"])


def test_a_stream_that_is_keeping_up_is_not_a_defect(registry_box: Path) -> None:
    """A cursor near the end of its input is a stream doing its job; convicting it would make the
    fence fire on every healthy pass and it would be off within the week."""
    led = "desks/mt5/data/hypotheses/gate_verdict_ledger.jsonl"
    _write(registry_box, led, "x" * 54_000_000)
    _registry_at(registry_box, {"gate_verdicts": 53_900_000})

    rec = next(r for r in fence.stream_backlogs(registry_box)["streams"]
               if r["stream"] == "gate_verdicts")
    assert rec["verdict"] == "OK", rec


def test_a_small_unread_tail_is_one_passs_lag_whatever_the_ratio(registry_box: Path) -> None:
    """A brand-new stream is 100% unread and is not broken. The byte floor is what says so."""
    led = "desks/mt5/data/hypotheses/gate_verdict_ledger.jsonl"
    _write(registry_box, led, "x" * 1000)
    _registry_at(registry_box, {"gate_verdicts": 0})

    rec = next(r for r in fence.stream_backlogs(registry_box)["streams"]
               if r["stream"] == "gate_verdicts")
    assert rec["verdict"] == "OK", rec


def test_a_stream_with_no_cursor_at_all_is_a_breach(registry_box: Path) -> None:
    """A restore wiped all four cursor keys once and nothing said so; every row on disk was then
    invisible to the registry. A missing receipt is a defect, never a fresh start."""
    led = "desks/mt5/data/hypotheses/gate_verdict_ledger.jsonl"
    _write(registry_box, led, "x" * 54_000_000)
    _registry_at(registry_box, {"hypothesis_graph": 10})

    got = fence.stream_backlogs(registry_box)
    rec = next(r for r in got["streams"] if r["stream"] == "gate_verdicts")
    assert rec["verdict"] == "NO_CURSOR", rec


def test_a_host_with_no_registry_is_unmeasured_not_clean(tmp_path: Path) -> None:
    """UNMEASURED is a verdict (L1.28a). The build box holds no live registry and must not be
    reported as a host whose streams are healthy."""
    import sys as _sys
    _sys.path.insert(0, str(ROOT))
    from libs.moat import registry as R
    before = R.path()
    try:
        R.set_path(tmp_path / "data" / "nothing.sqlite")
        got = fence.stream_backlogs(tmp_path)
        assert got["status"] == fence.UNMEASURED
        assert got["why"]
    finally:
        R.set_path(before)


def test_a_diverging_stream_fails_the_scan_on_a_clock_host(registry_box: Path) -> None:
    """WIRED, not merely measured: the breach must reach `scan`'s verdict, or it is a number in a
    report nobody acts on."""
    _write(registry_box, "desks/mt5/data/hypotheses/gate_verdict_ledger.jsonl", "x" * 54_000_000)
    _registry_at(registry_box, {"gate_verdicts": 1000})
    _declare_ledger(registry_box, {"alpha": "desks/mt5/reports/alpha.json"})
    ok_runs = [("alpha", NOW - timedelta(hours=h), True) for h in (1, 2, 3)]
    _write(registry_box, EVENTS, _events(ok_runs))
    _touch(registry_box / "desks" / "mt5" / "reports" / "alpha.json", NOW)

    doc = fence.scan(registry_box, now=NOW)
    assert doc["ok"] is False
    assert doc["verdict"] == "DARK"
    assert any("STREAM_DIVERGING" in p for p in doc["problems"]), doc["problems"]


def test_a_mirror_host_is_not_convicted_for_a_stale_cursor(registry_box: Path,
                                                           monkeypatch: pytest.MonkeyPatch
                                                           ) -> None:
    """On a host that does not run the clocks a cursor behind its input is the mirror being a
    mirror -- the same rule every other verdict in this file already follows."""
    monkeypatch.setattr(fence, "runs_clocks_here", lambda _root: False)
    _write(registry_box, "desks/mt5/data/hypotheses/gate_verdict_ledger.jsonl", "x" * 54_000_000)
    _registry_at(registry_box, {"gate_verdicts": 1000})
    _declare_ledger(registry_box, {"alpha": "desks/mt5/reports/alpha.json"})
    _write(registry_box, EVENTS, _events([("alpha", NOW - timedelta(hours=1), True)]))

    doc = fence.scan(registry_box, now=NOW)
    assert not any("STREAM_DIVERGING" in p for p in doc["problems"]), doc["problems"]


def test_the_read_back_door_is_indexed(registry_box: Path) -> None:
    """THE FIX ITSELF, PINNED. `mark_candidate` matches `WHERE id=? OR donated_cell=?`; with no
    index on `donated_cell` an OR across one indexed and one unindexed column can use neither,
    and SQLite reads `SCAN research_candidates` -- 740,357 rows per verdict, measured at 2.09
    rows/s on the trading box against 87,931 rows/s with the index. That single missing index is
    why the desk stamped `judged_at` on 1,278 candidates in its whole history while the gauntlet
    ruled on 228,469 cells."""
    R = _registry_at(registry_box, {})
    conn = R.connect()
    try:
        names = {r["name"] for r in conn.execute("PRAGMA index_list('research_candidates')")}
        assert "ix_candidates_donated_cell" in names, (
            "no index on research_candidates(donated_cell): the verdict read-back door is a full "
            "table scan again, and judged_at will silently stop advancing")
        plan = " ".join(str(r[-1]) for r in conn.execute(
            "EXPLAIN QUERY PLAN UPDATE research_candidates SET status=? "
            "WHERE id=? OR donated_cell=?", ("judged", "a", "b")))
        assert "SCAN research_candidates" not in plan, plan
        assert "MULTI-INDEX OR" in plan or "SEARCH" in plan, plan
    finally:
        conn.close()


def test_a_registry_outside_the_judged_tree_is_unmeasured_not_borrowed(tmp_path: Path) -> None:
    """`registry.path()` is process-global. Judging one tree's streams against ANOTHER tree's
    cursors is a verdict about the wrong object -- measured on the build host when this fence was
    ported: a scan of a test box read the host's own registry and reported its missing
    `desk_lessons` cursor as the box's defect."""
    import sys as _sys
    _sys.path.insert(0, str(ROOT))
    from libs.moat import registry as R
    before = R.path()
    try:
        _registry_at(tmp_path / "elsewhere", {"gate_verdicts": 0})
        judged = tmp_path / "judged"
        judged.mkdir()
        got = fence.stream_backlogs(judged)
        assert got["status"] == fence.UNMEASURED
        assert "not under" in got["why"]
    finally:
        R.set_path(before)
