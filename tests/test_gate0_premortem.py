"""Gate 0's pre-mortem criterion (R0105) -- runs against a TEMP root, never live state.

THE ROW THIS PINS. prompts/panel_missions/premortem.txt has sat in the weekly panel rotation since
2026-07-12 and has never once fired -- premortem is the only mission with zero rows in
data/external_panel_log.jsonl. Gate 0 now refuses to clear without it, so the cases below are what
stops that gate from being satisfied by something that is not a pre-mortem.

THE TWO FAILURES THESE EXIST TO CATCH, both of which would look green:
  * a DEGRADED free-seat run clearing the gate. The panel itself stamps sub-8-seat output
    "advisory-weak ... re-run on the full roster before acting on anything structural"; letting
    that unlock real capital is precisely the lowered-bar admission the desk forbids.
  * an unrelated mission satisfying the row. The obvious artifact to check, panel_inbox.md, is
    rewritten wholesale by every run, so a later audit mission would either clobber the evidence
    or supply it. The criterion reads the append-only mission-stamped log instead, and
    ``test_another_mission_does_not_satisfy_it`` is what keeps it that way.

Follows tests/test_gate0_soak.py: assert, never SystemExit, and nothing executes at import.
"""
import json
import tempfile
from pathlib import Path
from unittest import mock

import pytest
import scripts.check_gate0_ready as g


def run(rows: list[dict] | None, *, write_file: bool = True) -> dict:
    """Evaluate the criterion against a synthetic panel log in a throwaway root."""
    with tempfile.TemporaryDirectory() as td:
        r = Path(td)
        (r / "data").mkdir()
        if write_file:
            (r / "data/external_panel_log.jsonl").write_text(
                "".join(json.dumps(x) + "\n" for x in (rows or [])), "utf-8")
        with mock.patch.object(g, "_ROOT", r):
            return g._premortem_completed()


def _seats(n: int, *, mission: str = "premortem", chars: int = 500) -> list[dict]:
    return [{"ts": "2026-08-05T00:00:00Z", "mission": mission, "provider": f"seat-{i}",
             "model": f"vendor/model-{i}", "response": "x" * chars} for i in range(n)]


def test_a_full_roster_premortem_clears_the_gate() -> None:
    """POSITIVE CONTROL: the criterion must be satisfiable, or it is a wall, not a gate."""
    row = run(_seats(g._PREMORTEM_SEATS))
    assert row["status"] == "READY", row
    assert row["owner"] == g.DESK


def test_the_mission_having_never_run_is_not_ready_and_says_so() -> None:
    """Today's real state. 'Never ran' must be legible -- it is the whole finding of R0105."""
    row = run([])
    assert row["status"] == "NOT-READY"
    assert "NEVER run" in row["detail"]


def test_a_degraded_free_seat_run_does_not_clear_the_gate() -> None:
    """4 free seats is what an unfunded panel produces. Advisory-weak must not unlock capital."""
    row = run(_seats(4))
    assert row["status"] == "NOT-READY"
    assert "4/8" in row["detail"]


def test_another_mission_does_not_satisfy_it() -> None:
    """A rotation full of audit runs must never be mistaken for a pre-mortem."""
    row = run(_seats(20, mission="audit"))
    assert row["status"] == "NOT-READY"
    assert "0/8" in row["detail"]


def test_stub_responses_do_not_pad_the_quorum() -> None:
    """A seat that returned nothing answered nothing -- counting it would be quorum padding."""
    row = run(_seats(g._PREMORTEM_SEATS, chars=10))
    assert row["status"] == "NOT-READY"


def test_errored_seats_do_not_count() -> None:
    """Panel rows carry either `response` or `error`; an error is not a pre-mortem."""
    rows = [{"ts": "t", "mission": "premortem", "provider": f"s{i}", "error": "boom"}
            for i in range(g._PREMORTEM_SEATS)]
    assert run(rows)["status"] == "NOT-READY"


def test_the_same_seat_answering_repeatedly_is_still_one_seat() -> None:
    """Quorum is DISTINCT seats. Re-running one model 8 times is one opinion, not eight."""
    rows = [{"ts": "t", "mission": "premortem", "provider": "solo", "model": "m",
             "response": "x" * 500} for _ in range(g._PREMORTEM_SEATS * 2)]
    row = run(rows)
    assert row["status"] == "NOT-READY"
    assert "1/8" in row["detail"]


def test_a_corrupt_line_is_skipped_not_counted() -> None:
    with tempfile.TemporaryDirectory() as td:
        r = Path(td)
        (r / "data").mkdir()
        good = "".join(json.dumps(x) + "\n" for x in _seats(3))
        (r / "data/external_panel_log.jsonl").write_text(
            '{"mission": "premortem" broken\n' + good, "utf-8")
        with mock.patch.object(g, "_ROOT", r):
            row = g._premortem_completed()
    assert row["status"] == "NOT-READY"
    assert "3/8" in row["detail"]


def test_an_unreadable_log_is_blocked_unknown_never_ready() -> None:
    """FAIL CLOSED: 'could not measure' is never 'satisfied' -- the file's central doctrine."""
    row = run(None, write_file=False)
    assert row["status"] == "BLOCKED-UNKNOWN"


def test_the_criterion_is_registered_in_the_board() -> None:
    """Registration IS the mechanism: a criterion function nobody calls gates nothing."""
    names = [r["criterion"] for r in g.build()["rows"]]
    assert "premortem_completed" in names
    assert len(names) == len(set(names)), "criterion names must be unique"


@pytest.mark.parametrize("field", ["criterion", "status", "owner", "detail", "artifact", "action"])
def test_the_row_carries_the_full_board_shape(field: str) -> None:
    assert field in run(_seats(2))
