"""The mechanical half of the gap-register re-rank.

THE ORGAN'S WHOLE DESIGN IS A REFUSAL, so most of these tests are about what it must NOT do.
`register_health` decides whether the re-rank duty was performed by reading the register's own
`Re-ranked <date>` stamp. An organ that wrote that stamp after doing only the countable part would
turn the check green while the judgment half never happened -- the defect stops being reported and
the work stops being done at the same moment, and only the first of those is visible. That is
strictly worse than having no organ.

So: the mechanical pass computes everything that needs no opinion, states plainly what it did not
do, and cannot discharge the judgment duty by any path.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import scripts.rerank_gaps as R

from libs.research.finding_registry import register_health

HEADER = (
    "# GAP REGISTER\n\n"
    "| id | title | why | plan | owner | added | status |\n"
    "|---|---|---|---|---|---|---|\n"
)


def _row(i, title, plan, owner="brain", added="07-16", status="open"):
    return f"| {i} | **{title}** | because | {plan} | {owner} | {added} | {status} |\n"


# ------------------------------------------------------------------ the refusal


def test_the_stamp_cannot_satisfy_the_judgment_rerank_check() -> None:
    """THE LOAD-BEARING TEST. If the mechanical stamp matched the re-rank regex, this organ would
    clear a check it had not satisfied on every cycle, forever -- and the register would report as
    driven while nothing weighed one row against another."""
    today = date(2026, 8, 2)
    stamp = R.stamp_line([{"id": 1, "verdict": "PARKED"}], today)
    # Feed a register whose ONLY stamp is the mechanical one.
    text = HEADER + _row(1, "x", "no date") + "\n" + stamp
    h = register_health(text, today=today)
    assert h.rerank_age_days == -1.0, "the mechanical stamp must not read as a re-rank"
    assert h.rerank_stale or h.rerank_breach


def test_the_stamp_says_out_loud_what_it_did_not_do() -> None:
    """A stamp that reads like a re-rank gets believed like one by a human skimming the file. The
    wording is the safeguard when the regex is not."""
    s = R.stamp_line([{"id": 3, "verdict": "PARKED"}], date(2026, 8, 2))
    assert "NOT a re-rank" in s
    assert "no row was weighed against another" in s
    assert "still owed" in s


def test_the_artifact_reports_the_judgment_half_without_claiming_it() -> None:
    """One artifact should answer 'is the register being driven?' -- but reporting the judgment
    clock is not the same as advancing it, and the note has to make that impossible to misread."""
    rep = json.loads((Path("data/gap_rerank.json")).read_text("utf-8")) if Path(
        "data/gap_rerank.json").exists() else None
    if rep is None:
        pytest.skip("organ has not run in this checkout")
    assert "judgment_rerank_owed" in rep
    assert "MECHANICAL HALF ONLY" in rep["note"]
    assert "nothing in this organ can discharge it" in rep["note"]


# ------------------------------------------------------------------ what it does compute


def test_a_passed_deadline_is_the_top_verdict() -> None:
    """A deferral whose date has gone by is not deferred -- it is parked with extra steps, and the
    register's own rule forbids parking. This outranks everything because it is the one state the
    row itself promised would not happen."""
    text = HEADER + _row(1, "late", "DEFERRED WITH DEADLINE 2026-07-01")
    rows = R.classify(text, date(2026, 8, 2))
    assert rows[0]["verdict"] == "DEADLINE-PASSED"
    assert rows[0]["deadline"] == "2026-07-01"
    assert "parked with extra steps" in rows[0]["why"]


def test_a_future_deadline_is_on_clock_not_a_defect() -> None:
    """Firing on a row that is doing exactly what it promised is how an alarm gets ignored."""
    rows = R.classify(HEADER + _row(1, "ok", "DEADLINE 2026-09-01"), date(2026, 8, 2))
    assert rows[0]["verdict"] == "ON-CLOCK"


def test_a_plan_with_no_date_is_parked() -> None:
    """The register's three legal exits are implement / defer WITH A DEADLINE / retire with a
    reason. A row with no date took none of them."""
    rows = R.classify(HEADER + _row(1, "vague", "we will look at this"), date(2026, 8, 2))
    assert rows[0]["verdict"] == "PARKED"
    assert "three legal exits" in rows[0]["why"]


def test_a_long_open_row_is_promoted_even_when_otherwise_healthy() -> None:
    """Priority decides ORDER, never entitlement. A dated, owned row that is simply never reached
    is being neglected by a rule that believes it is merely ordering -- the same starvation
    discipline the allocator uses."""
    old = _row(1, "ancient", "DEADLINE 2026-12-01", added="01-02")
    rows = R.classify(HEADER + old, date(2026, 8, 2))
    assert rows[0]["verdict"] == "STARVED"
    assert rows[0]["age_days"] >= R.STARVATION_DAYS


def test_closed_rows_are_not_carried() -> None:
    """A re-rank orders the work that remains. Including done rows pads the count and buries the
    live ones."""
    text = HEADER + _row(1, "done", "shipped", status="closed") + _row(2, "live", "no date")
    rows = R.classify(text, date(2026, 8, 2))
    assert [r["id"] for r in rows] == [2]


def test_verdicts_are_ordered_worst_first() -> None:
    """A ranked list whose head is not the worst thing is a list nobody reads twice."""
    text = (HEADER
            + _row(1, "fine", "DEADLINE 2026-12-01")
            + _row(2, "late", "DEADLINE 2026-01-01")
            + _row(3, "parked", "nothing"))
    rows = R.classify(text, date(2026, 8, 2))
    assert [r["verdict"] for r in rows][:2] == ["DEADLINE-PASSED", "PARKED"]


# ------------------------------------------------ re-deferral: BOTH facts, never one (R0365)


def test_a_re_deferred_row_reports_the_new_promise_AND_the_miss() -> None:
    """`min()` over every date let the FIRST miss dominate forever.

    A row re-deferred with a new dated reason has taken one of the register's three legal exits,
    and printing DEADLINE-PASSED anyway left exactly one way to clear it: delete the old date,
    which erases the miss. That is the denominator trick §34 forbids. Both facts, or neither is
    trustworthy.
    """
    text = HEADER + _row(1, "slipped", "DEADLINE 2026-07-01, re-deferred to DEADLINE 2026-09-01")
    rows = R.classify(text, date(2026, 8, 2))
    assert rows[0]["verdict"] == "RE-DEFERRED"
    assert rows[0]["deadline"] == "2026-09-01"          # the promise that is actually live
    assert rows[0]["missed_deadlines"] == 1             # and the one that was broken
    assert rows[0]["missed"] == ["2026-07-01"]


def test_the_nearest_future_deadline_wins_not_the_furthest() -> None:
    """The anti-`max()` guard, and the reason the obvious fix was the wrong one.

    Live row #64 carries 2026-08-15 (implement) and 2026-11-15 (fold it if nothing survives).
    Ranking on the latest date would hide a near milestone behind a far backstop -- a LOOSENING
    dressed as a correction, which is the failure this desk pays for most often.
    """
    text = HEADER + _row(1, "two", "IMPLEMENT BY 2026-08-15 ... fold by 2026-11-15")
    rows = R.classify(text, date(2026, 8, 2))
    assert rows[0]["deadline"] == "2026-08-15"
    assert rows[0]["verdict"] == "ON-CLOCK"
    assert rows[0]["missed_deadlines"] == 0


def test_a_row_with_only_passed_deadlines_is_unchanged() -> None:
    """The half that must NOT move. Nothing here may let an overdue row off."""
    text = HEADER + _row(1, "late", "DEADLINE 2026-06-01 and DEADLINE 2026-07-01")
    rows = R.classify(text, date(2026, 8, 2))
    assert rows[0]["verdict"] == "DEADLINE-PASSED"
    assert rows[0]["deadline"] == "2026-06-01"          # the WORST miss, as before
    assert rows[0]["missed_deadlines"] == 2
    assert "2 deadlines missed" in rows[0]["why"]


def test_a_re_deferred_row_does_not_sink_below_the_parked_ones() -> None:
    """The miss count must not be bought with the urgency it is evidence of."""
    text = (HEADER
            + _row(1, "parked", "no date at all")
            + _row(2, "slipped", "DEADLINE 2026-07-01 re-deferred DEADLINE 2026-09-01"))
    rows = R.classify(text, date(2026, 8, 2))
    assert [r["id"] for r in rows] == [2, 1]


def test_one_miss_is_the_register_working_and_two_is_a_treadmill() -> None:
    """A count, not a duration: L1.48 forbids gating on elapsed calendar time, and how many
    promises a row has broken is evidence in a way that how long it has been open is not."""
    once = R.classify(HEADER + _row(1, "a", "DEADLINE 2026-07-01 then DEADLINE 2026-09-01"),
                      date(2026, 8, 2))[0]
    twice = R.classify(HEADER + _row(1, "b", "DEADLINE 2026-06-01 DEADLINE 2026-07-01 "
                                             "now DEADLINE 2026-09-01"), date(2026, 8, 2))[0]
    assert once["verdict"] == twice["verdict"] == "RE-DEFERRED"
    assert not R.needs_decision(once), "re-committing once is the exit working, not a defect"
    assert R.needs_decision(twice), "a second miss is a treadmill and needs a decision"
    assert R.classify(HEADER + _row(1, "c", "DEADLINE 2026-07-01 DEADLINE 2026-06-15 "
                                            "DEADLINE 2026-09-01"),
                      date(2026, 8, 2))[0]["missed_deadlines"] == 2


# ------------------------------------------------ an id is a label; the text belongs to the row


def test_duplicate_ids_do_not_swap_their_deadlines() -> None:
    """MEASURED on the live register 2026-08-12: a branch merge unioned two lineages without
    renumbering, so 17 ids named two findings each. The old lookup scanned for `| <id> |` and took
    the FIRST hit, so six open rows were ranked on ANOTHER row's deadline -- including one that
    read TRACKED with no deadline while its own plan promised today's date.
    """
    text = (HEADER
            + _row(7, "first", "DEADLINE 2026-12-01", status="closed")
            + _row(7, "second", "DEADLINE 2026-01-01"))
    rows = R.classify(text, date(2026, 8, 2))
    assert [r["title"] for r in rows] == ["second"]
    assert rows[0]["deadline"] == "2026-01-01", "the row was read through the other row's text"
    assert rows[0]["verdict"] == "DEADLINE-PASSED"


def test_a_shared_id_is_reported_because_no_citation_of_it_resolves() -> None:
    """This organ cannot renumber the register, so the one thing it owes is to say so. Silence
    leaves the register looking addressable while two readers of "#100" reach different rows."""
    text = HEADER + _row(9, "a", "DEADLINE 2026-12-01") + _row(9, "b", "DEADLINE 2026-12-02")
    rows = R.classify(text, date(2026, 8, 2))
    assert all(r["id_ambiguous"] for r in rows)
    assert R.classify(HEADER + _row(9, "solo", "DEADLINE 2026-12-01"),
                      date(2026, 8, 2))[0]["id_ambiguous"] is False


# ------------------------------------------------------------------ against the LIVE register


def test_the_live_register_parses_and_ranks() -> None:
    """Run against the real file, because a fixture passing while production is unparseable is the
    exact shape this desk keeps finding.

    THIS TEST USED TO ASSERT that row #2 was DEADLINE-PASSED -- true when written, because its
    2026-07-31 principal deadline had gone by unreported and finding it is what this organ exists
    for. Then the deadline was discharged (re-deferred to 2026-08-23 with a stated reason) and the
    assertion failed on a FIX. A test pinned to a transient defect fails when the defect is closed,
    which trains everyone to weaken it; so what is asserted now is the invariant that survives the
    fix -- the register parses, and anything overdue sorts to the front."""
    reg = Path("docs/GAP_REGISTER.md")
    if not reg.exists():
        pytest.skip("no register in this checkout")
    rows = R.classify(reg.read_text("utf-8"), date(2026, 8, 2))
    assert len(rows) > 20, f"only {len(rows)} open rows parsed -- the table shape changed"
    assert all(r["verdict"] for r in rows)
    verdicts = [r["verdict"] for r in rows]
    if "DEADLINE-PASSED" in verdicts:
        assert verdicts[0] == "DEADLINE-PASSED", "an overdue row must sort to the front"


def test_the_run_writes_its_artifact_and_appends_history(tmp_path, monkeypatch) -> None:
    """History is append-only: the need-a-decision count is a trend, and a file rewritten each
    cycle cannot show whether the backlog is being worked or merely re-counted."""
    reg = tmp_path / "GAP_REGISTER.md"
    reg.write_text(HEADER + _row(1, "late", "DEADLINE 2026-01-01"), "utf-8")
    monkeypatch.setattr(R, "REGISTER", reg)
    monkeypatch.setattr(R, "REPORT", tmp_path / "out.json")
    monkeypatch.setattr(R, "HISTORY", tmp_path / "hist.jsonl")
    assert R.main() == 0
    assert R.main() == 0
    rep = json.loads((tmp_path / "out.json").read_text("utf-8"))
    assert rep["need_decision"] == 1
    assert len((tmp_path / "hist.jsonl").read_text("utf-8").strip().splitlines()) == 2


def test_a_missing_register_is_not_a_crash(tmp_path, monkeypatch) -> None:
    """This runs in the cadence. Taking the cycle down to report an absent doc is a blast radius
    that does not match the failure."""
    monkeypatch.setattr(R, "REGISTER", tmp_path / "nope.md")
    assert R.main() == 0
