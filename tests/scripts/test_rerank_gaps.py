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


# ------------------------------------------------------------------ against the LIVE register


def test_the_live_register_parses_and_finds_the_real_overdue_row() -> None:
    """Run against the real file, because a fixture passing while production is unparseable is
    the exact shape this desk keeps finding. #2 carries a PRINCIPAL DEADLINE of 2026-07-31 that
    went by with nothing reporting it -- which is the finding this organ exists to produce."""
    reg = Path("docs/GAP_REGISTER.md")
    if not reg.exists():
        pytest.skip("no register in this checkout")
    rows = R.classify(reg.read_text("utf-8"), date(2026, 8, 2))
    assert len(rows) > 20, f"only {len(rows)} open rows parsed -- the table shape changed"
    overdue = [r for r in rows if r["verdict"] == "DEADLINE-PASSED"]
    assert any(r["id"] == 2 for r in overdue), [r["id"] for r in overdue]


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
