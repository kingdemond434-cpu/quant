"""L1.28b conversion fence -- finding without fixing is half a deliverable.

The fence must (1) FLATLINE on a week of silence over a non-empty queue, (2) flag REPAIR-MODE
above the deep-sweep backpressure line, (3) treat a missing ledger as zero conversion (never OK),
(4) count a reasoned rejection as a conversion, and (5) stay wired: the law mapped in the
enforcement matrix, the artifact folded into the max-push queue, the manifest line present.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from scripts.check_conversion import REPAIR_MODE_BACKLOG, build_report

# 2026-08-28: read the INJECTED PAYLOAD, not one file. The 08-25 consolidation moved the
# law text from ops/principal_doctrine.txt into docs/LAWS.md and changed brain_env.sh to
# cat BOTH into every organ's prompt in the same breath -- no organ lost a line, and five
# fences went red about text one file away. libs.doctrine.corpus derives the file list
# from brain_env.sh itself, so a future relocation moves the fences with it.
from libs.doctrine.corpus import doctrine_text
from libs.ops.repair_mode import DIRECTION_FOR_STATUS

NOW = datetime(2026, 7, 31, 12, 0, tzinfo=UTC)


def _write_ledger(root: Path, rows: list[dict]) -> None:
    p = root / "docs/research/recommendation_ledger.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"recommendations": rows}), "utf-8")


def _row(rid: str, status: str, raised_days_ago: float, *, disposed_days_ago: float | None = None,
         due: str | None = None) -> dict:
    return {
        "id": rid, "status": status,
        "raised": (NOW - timedelta(days=raised_days_ago)).isoformat(),
        "disposed": (None if disposed_days_ago is None
                     else (NOW - timedelta(days=disposed_days_ago)).isoformat()),
        "due": due,
    }


def test_flatline_on_week_of_silence_with_backlog(tmp_path):
    _write_ledger(tmp_path, [
        _row("R1", "open", 10.0),
        _row("R2", "scheduled", 9.0),
        _row("R3", "implemented", 20.0, disposed_days_ago=9.0),  # converted, but not this week
    ])
    rep = build_report(tmp_path, NOW)
    assert rep["status"] == "FLATLINE"
    assert rep["repair_mode"] is True
    assert rep["dispositions_7d"] == 0


def test_repair_mode_above_backpressure_line(tmp_path):
    rows = [_row(f"R{i}", "open", 3.0) for i in range(REPAIR_MODE_BACKLOG + 1)]
    rows.append(_row("RX", "implemented", 5.0, disposed_days_ago=1.0))
    _write_ledger(tmp_path, rows)
    rep = build_report(tmp_path, NOW)
    assert rep["status"] == "REPAIR-MODE"
    assert rep["repair_mode"] is True
    assert rep["backlog"] == REPAIR_MODE_BACKLOG + 1


def test_ok_when_flow_keeps_pace_and_backlog_small(tmp_path):
    _write_ledger(tmp_path, [
        _row("R1", "open", 2.0, due="2026-09-01"),
        _row("R2", "implemented", 6.0, disposed_days_ago=1.0),
    ])
    rep = build_report(tmp_path, NOW)
    assert rep["status"] == "OK"
    assert rep["repair_mode"] is False


def test_missing_ledger_is_flatline_never_ok(tmp_path):
    # L1.28b(e): unmeasured conversion counts as zero conversion.
    rep = build_report(tmp_path, NOW)
    assert rep["status"] == "FLATLINE"
    assert rep["repair_mode"] is True


def test_reasoned_rejection_counts_as_conversion(tmp_path):
    _write_ledger(tmp_path, [
        _row("R1", "open", 2.0),
        _row("R2", "rejected", 6.0, disposed_days_ago=2.0),
    ])
    rep = build_report(tmp_path, NOW)
    assert rep["dispositions_7d"] == 1
    assert rep["status"] == "OK"


def test_past_due_rows_named(tmp_path):
    _write_ledger(tmp_path, [
        _row("R1", "scheduled", 10.0, due="2026-07-01"),      # overdue
        _row("R2", "scheduled", 3.0, due="2026-12-01"),       # future deadline, not due
        _row("R3", "implemented", 5.0, disposed_days_ago=1.0),
    ])
    rep = build_report(tmp_path, NOW)
    assert rep["past_due"] == 1
    assert rep["past_due_ids"] == ["R1"]


def test_untriaged_open_row_past_grace_is_past_due(tmp_path):
    """The branch that was structurally dead in production.

    add() writes `status: open, due: None` and only `dispose --status scheduled` ever sets a due,
    so ZERO rows in the live ledger had status open AND a due date -- yet the fence required a
    non-null due to consider anything past due. 28 untriaged rows were invisible, and
    run_max_push.py:239 consumes this artifact, so the desk prioritised off the lenient count."""
    _write_ledger(tmp_path, [
        _row("R1", "open", 3.0),                              # no due -- 3d > 24h grace
        _row("R2", "open", 0.5),                              # inside grace, not yet a defect
        _row("R3", "implemented", 5.0, disposed_days_ago=1.0),
    ])
    rep = build_report(tmp_path, NOW)
    assert rep["past_due_orphaned"] == 1
    assert rep["past_due_ids"] == ["R1"]


def test_row_due_today_is_past_due_not_invisible(tmp_path):
    """`"2026-07-31" < "2026-07-31"` is False, so a scheduled row was invisible for the whole day
    it came due. Six live rows sat in that blind spot."""
    _write_ledger(tmp_path, [
        _row("R1", "scheduled", 2.0, due=NOW.date().isoformat()),
        _row("R2", "implemented", 5.0, disposed_days_ago=1.0),
    ])
    rep = build_report(tmp_path, NOW)                          # NOW is 12:00, due parses to 00:00
    assert rep["past_due_overdue"] == 1
    assert rep["past_due_ids"] == ["R1"]


def test_finished_rows_are_not_backlog_forever(tmp_path):
    """`done`/`screened` are written by organs that bypass the CLI. They are completed work;
    counting them as backlog inflated the debt permanently and never counted as dispositions."""
    _write_ledger(tmp_path, [
        _row("R1", "done", 3.0),
        _row("R2", "screened", 3.0),
        _row("R3", "open", 0.5),
    ])
    rep = build_report(tmp_path, NOW)
    assert rep["backlog"] == 1                    # only the genuinely open row
    assert rep["terminal_unstamped"] == 2         # ...and the missing stamps stay VISIBLE


def test_law_is_enforced_in_matrix():
    # The law must be mapped to its fence, or it is prose (L2.0).
    # ASSERT THE MAPPING, NOT THE LITERAL. This was `'"L1.28b": ["scripts/check_conversion.py"]'
    # in src`, which pins the list to EXACTLY one enforcer -- so adding the L1.28b(d) actuator
    # (libs/ops/repair_mode.py, the thing that finally made the law's remedy reach an organ) broke
    # a test whose stated purpose is that the law be enforced. A test that fails when enforcement
    # is STRENGTHENED is pointed the wrong way; it should pin the fence's presence, not the
    # absence of colleagues.
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_matrix", Path("scripts/build_enforcement_matrix.py"))
    matrix = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(matrix)
    assert "scripts/check_conversion.py" in matrix._MAP["L1.28b"]


def test_artifact_feeds_max_push_queue():
    src = Path("scripts/run_max_push.py").read_text("utf-8")
    assert "data/conversion_status.json" in src
    assert "conversion_debt" in src
    assert "_from_conversion" in src


def test_manifest_schedules_the_fence():
    manifest = Path("ops/crontab.manifest").read_text("utf-8")
    assert "scripts/check_conversion.py" in manifest


def test_doctrine_carries_the_law():
    # Every organ inherits doctrine at spawn; the law must reach them, not just the constitution.
    doctrine = doctrine_text()
    assert "L1.28b" in doctrine
    # PIN THE RULE, NOT THE PROSE. The consolidation restates this law in sentence case
    # ("conversion parity -- finding without fixing is half a deliverable"); a fence that
    # demanded the old shouting would have blocked a legitimate rewrite while a real deletion
    # slipped past under different words. That is prompt_ratchet.py's stated trade, applied here.
    assert "conversion parity" in doctrine.lower()


def test_real_repo_ledger_produces_valid_report():
    rep = build_report(Path("."))
    # The full status set. It passes today only because the live backlog happens to exceed the
    # REPAIR-MODE line; the moment it drops below while conversion is still behind, the status
    # becomes DEBT-GROWING and an enum frozen at the old three would fail on a CORRECT reading.
    # A closed enum in a test must be widened when the code gains a member, or it is a bomb
    # waiting on data rather than on anyone's edit.
    assert rep["status"] in ("OK", "REPAIR-MODE", "FLATLINE",
                             "DEBT-GROWING", "ARRIVALS-COLLAPSED")
    # THE SAME BOMB THIS TEST'S OWN COMMENT WARNS ABOUT, ONE LEVEL UP (found 2026-08-28).
    # The enum was widened and this implication was not. `repair_mode` stopped meaning "the pile
    # is big" when check_conversion:327 made it `direction == "DRAIN"`: under ARRIVALS-COLLAPSED
    # the desk must HUNT, and draining a backlog by finding less is the denominator trick
    # L1.28b(f) forbids. Measured live: status ARRIVALS-COLLAPSED, backlog 282 over the line,
    # repair_mode correctly False -- the code is right and the assertion was stale.
    # Read the direction from the one mapping the producer reads, never from a second copy.
    assert rep["repair_mode"] is (DIRECTION_FOR_STATUS.get(rep["status"]) == "DRAIN")
    if (rep["backlog"] is not None and rep["backlog"] > REPAIR_MODE_BACKLOG
            and DIRECTION_FOR_STATUS.get(rep["status"]) == "DRAIN"):
        assert rep["repair_mode"] is True


class TestConversionMustCatchUpAndMustNotCatchUpByFindingLess:
    """The two halves of L1.28b(f), which the fence stated in prose and never measured.

    Both numbers this needs -- arrivals_7d and dispositions_7d -- were computed, printed into the
    artifact, and NEVER COMPARED (found 2026-08-05). Status asked only "is anything moving at
    all" and "is the pile big", so a desk raising 40 rows a week and dispositioning 3 read OK for
    as long as the backlog stayed under the REPAIR-MODE line, falling 37 further behind every
    week with the evidence sitting unread in its own output. On the live ledger the gap was 341
    raised against 157 dispositioned.

    The second half matters more, and it is the reason this class exists rather than one extra
    assertion: EVERY other reading in this fence improves when arrivals fall. Stop finding
    things and the backlog shrinks, dispositions keep pace trivially, and the fence goes green --
    so the cheapest route to a clean conversion score is to look less hard, and it would be
    indistinguishable from genuine success. A ratio whose denominator nobody guards is not a
    measurement of conversion; it is an invitation.
    """

    def _ledger(self, root: Path, *, arrivals: int, dispositions: int,
                prior_28d: int = 0) -> dict:
        """A ledger where each row contributes to EXACTLY ONE side of the comparison.

        The obvious fixture -- raise the dispositioned rows this week too -- makes them count as
        both arrivals and dispositions, so `arrivals` no longer means arrivals and every expected
        number drifts. Dispositioned rows are therefore raised 10d ago (outside the 7d arrival
        window) and closed 1d ago (inside the 7d disposition window).
        """
        rows = [_row(f"A{i}", "open", 3.0) for i in range(arrivals)]
        rows += [_row(f"D{i}", "implemented", 10.0, disposed_days_ago=1.0)
                 for i in range(dispositions)]
        # Extra history for the collapse baseline: raised and closed entirely inside the prior
        # 7-35d window, so they touch neither this week's arrivals nor this week's dispositions.
        rows += [_row(f"P{i}", "implemented", 14.0, disposed_days_ago=13.0)
                 for i in range(prior_28d)]
        _write_ledger(root, rows)
        return build_report(root, NOW)

    def test_falling_behind_is_a_named_failure_not_a_green_light(self, tmp_path) -> None:
        """The hole in the original logic: under the backpressure line and still losing ground."""
        rep = self._ledger(tmp_path, arrivals=20, dispositions=2)
        assert rep["backlog"] <= REPAIR_MODE_BACKLOG, "must test the UNDER-the-line case"
        assert rep["status"] == "DEBT-GROWING"
        assert rep["debt_growing"] is True
        assert rep["debt_growth_7d"] == 18
        assert rep["conversion_ratio_7d"] == 0.1

    def test_keeping_pace_is_not_punished(self, tmp_path) -> None:
        """A fence that fires while the desk is coping gets switched off, taking the real signal
        with it. One row raised and not yet dispositioned is coping, not sliding."""
        rep = self._ledger(tmp_path, arrivals=10, dispositions=9)
        assert rep["status"] == "OK"
        assert rep["debt_growing"] is False

    def test_a_small_absolute_shortfall_is_noise_not_a_trend(self, tmp_path) -> None:
        rep = self._ledger(tmp_path, arrivals=4, dispositions=1)
        assert rep["debt_growing"] is False, (
            "a 3-row shortfall cannot distinguish a slide from a slow week")

    def test_debt_still_fails_the_fence_when_repair_mode_takes_the_headline(self,
                                                                           tmp_path) -> None:
        """The precedence trap. REPAIR-MODE outranks DEBT-GROWING as a label because downstream
        consumers already read it -- but a desk over the line AND falling further behind must
        not exit 0 because the more urgent-sounding name got there first."""
        rep = self._ledger(tmp_path, arrivals=REPAIR_MODE_BACKLOG + 10, dispositions=2)
        assert rep["status"] == "REPAIR-MODE"
        assert rep["debt_growing"] is True, "the fact must survive losing the headline"

    # ------------------------------------------------------------------ the anti-gaming half

    def test_finding_less_is_a_defect_rather_than_a_route_to_a_clean_score(self,
                                                                          tmp_path) -> None:
        """The gaming path, executed: a desk that stops looking. Arrivals collapse against their
        own history, everything else goes quiet, and before this the fence said OK."""
        rows = [_row(f"P{i}", "implemented", 14.0, disposed_days_ago=13.0) for i in range(40)]
        rows.append(_row("A1", "open", 2.0))          # one lonely arrival this week
        rows.append(_row("D1", "implemented", 2.0, disposed_days_ago=1.0))
        _write_ledger(tmp_path, rows)
        rep = build_report(tmp_path, NOW)
        assert rep["arrivals_collapsed"] is True
        assert rep["status"] == "ARRIVALS-COLLAPSED", (
            "a desk that stopped finding things must never read as a desk that finished")
        assert rep["debt_growing"] is False, (
            "and it must NOT be reported as a conversion problem -- the required move is FIND "
            "HARDER, which is the opposite instruction to CONVERT FASTER")

    def test_a_steady_finding_rate_is_not_a_collapse(self, tmp_path) -> None:
        rep = self._ledger(tmp_path, arrivals=10, dispositions=9, prior_28d=40)
        assert rep["arrivals_collapsed"] is False
        assert rep["status"] == "OK"

    def test_a_thin_history_refuses_to_judge_rather_than_guessing(self, tmp_path) -> None:
        """A collapse detector built on three historical rows fires on noise, and a detector that
        cries wolf is one nobody keeps. UNMEASURED is the honest reading, and it is stated."""
        rep = self._ledger(tmp_path, arrivals=1, dispositions=1, prior_28d=2)
        assert rep["arrivals_collapsed"] is False
        assert rep["arrivals_baseline_7d"] is None
        assert "UNMEASURED" in rep["arrivals_baseline_status"]

    def test_the_two_failures_are_never_merged(self, tmp_path) -> None:
        """One number holding both would let each mask the other -- a desk could halve its
        finding rate and call the improved ratio progress."""
        behind = self._ledger(tmp_path / "a", arrivals=20, dispositions=2)
        assert behind["debt_growing"] is True and behind["arrivals_collapsed"] is False
        assert "NEVER be raised by finding less" in behind["anti_gaming_note"]


class TestTheExitMapKeepsBothTeeth:
    """The 2026-08-05 merge of two concurrent fixes to the SAME return statement.

    One session inverted the map to fail-CLOSED on any status outside a declared pass set
    (R0237); the other added ``debt_growing`` as a trigger. Taking either alone loses a real
    tooth, and the live ledger proves it: status REPAIR-MODE is a PASSING status, so the
    fail-closed map alone returns 0 on a desk whose debt is growing.
    """

    def test_a_passing_status_still_fails_when_debt_is_growing(self) -> None:
        from scripts.check_conversion import _PASSING
        assert "REPAIR-MODE" in _PASSING, (
            "REPAIR-MODE is a designed MODE signal that drives run_max_push, not a failure -- "
            "if this ever leaves the pass set, the debt_growing branch below is the only thing "
            "still catching the live 365-raised-vs-167-dispositioned case")

    def test_named_failures_may_never_drift_into_the_pass_set(self) -> None:
        """_PASSING is the exit map now, so widening it is how DEBT-GROWING goes quiet.

        Widening the pass set is a legitimate edit. Widening it *onto* one of the three statuses
        this fence exists to report is not, and nothing else in the file would say so.
        """
        from scripts.check_conversion import _FENCE_FAILURES, _PASSING
        overlap = _FENCE_FAILURES & _PASSING
        assert not overlap, (
            f"{sorted(overlap)} is both a named failure and a passing status -- the fence would "
            f"exit 0 on the thing it was built to catch")


class TestRepairModeCountsWhatOwesADecision:
    """L1.28b(d) says the line is "25 OPEN ROWS"; the fence applied it to every non-terminal row.

    A row SCHEDULED with a real reason and a future due date is one of the three lawful
    dispositions. Counting it as repair debt makes the desk's own correct behaviour raise the
    number that says the desk is behind -- and because scheduled rows accumulate faster than they
    come due, the gate welds ON. Measured on the live ledger 2026-08-12 by reconstructing the
    daily backlog from the raised/disposed stamps: `backlog` crossed 25 on 2026-07-28 and never
    returned below it, so REPAIR-MODE fired on 100% of runs for 15 consecutive days.

    That is not a cosmetic complaint. REPAIR-MODE's actuator is a BEHAVIOUR CHANGE -- it flips the
    next brain window from finding to fixing -- and a flip that is always on is not a flip. The
    §37 carry-over brief measures the cost directly: 15 items "shown to a LIVE cycle at least
    twice IN A ROW" and walked past.
    """

    def test_in_date_scheduled_rows_are_not_repair_debt(self, tmp_path) -> None:
        """The regression that welded the gate: lawful scheduling must not trigger repair mode."""
        rows = [_row(f"S{i}", "scheduled", 3.0, due="2026-11-15")
                for i in range(REPAIR_MODE_BACKLOG * 3)]
        rows += [_row("R1", "implemented", 2.0, disposed_days_ago=1.0)]
        _write_ledger(tmp_path, rows)
        rep = build_report(tmp_path, NOW)
        assert rep["backlog"] > REPAIR_MODE_BACKLOG, "fixture must be over the OLD line"
        assert rep["owed"] == 0, "no row owes a decision: every schedule is still in date"
        assert rep["status"] != "REPAIR-MODE", (
            "75 correctly-scheduled rows read as repair debt -- this is the welded gate: the "
            "desk doing the lawful thing is what holds the signal on")

    def test_an_overdue_schedule_owes_a_decision_exactly_as_an_orphan_does(self, tmp_path) -> None:
        """The fix must not become a hiding place -- a schedule that ran out is real debt.

        This is the direction that would make the change a LOOSENING rather than a population
        fix, so it is pinned: if `owed` counted only open rows, parking work in a scheduled row
        with a past due date would silence the fence completely.
        """
        # Raised recently with a due date that has already passed. The recency matters: rows aged
        # 30d would make arrivals_7d zero, and ARRIVALS-COLLAPSED (correctly) outranks REPAIR-MODE,
        # which would test the precedence order rather than the population.
        rows = [_row(f"S{i}", "scheduled", 3.0, due="2026-07-01")
                for i in range(REPAIR_MODE_BACKLOG + 1)]
        # A conversion this week, so FLATLINE (which also correctly outranks REPAIR-MODE) is not
        # the thing under test -- the question is purely whether an expired schedule is owed.
        rows += [_row("D1", "implemented", 3.0, disposed_days_ago=1.0)]
        _write_ledger(tmp_path, rows)
        rep = build_report(tmp_path, NOW)
        assert rep["owed"] == REPAIR_MODE_BACKLOG + 1
        assert rep["status"] == "REPAIR-MODE"

    def test_the_populations_backlog_conflates_are_published_separately(self, tmp_path) -> None:
        _write_ledger(tmp_path, [
            _row("O1", "open", 5.0),
            _row("S1", "scheduled", 5.0, due="2026-11-15"),
            _row("S2", "scheduled", 5.0, due="2026-11-15"),
            _row("D1", "implemented", 5.0, disposed_days_ago=1.0),
        ])
        rep = build_report(tmp_path, NOW)
        assert rep["backlog"] == 3, "backlog keeps its old meaning for existing consumers"
        assert rep["backlog_open"] == 1
        assert rep["backlog_scheduled"] == 2
        assert rep["owed"] == 1, "only the open row past grace owes a decision today"

    def test_the_drain_is_published_so_treading_water_is_visible(self, tmp_path) -> None:
        """oldest_backlog_age was computed from day one and compared to NOTHING.

        A desk DRAINING a burst stock and a desk servicing only new arrivals are byte-identical
        in this artifact -- same backlog size, same balanced flow, same conversion ratio. The age
        percentiles are the only fields that separate them, because under treading water they
        rise exactly one day per day.
        """
        rows = [_row(f"OLD{i}", "open", 20.0) for i in range(9)]
        rows += [_row("NEW1", "open", 1.0)]
        _write_ledger(tmp_path, rows)
        rep = build_report(tmp_path, NOW)
        assert rep["backlog_age_p50_days"] == 20.0
        assert rep["backlog_age_p90_days"] == 20.0
        assert rep["oldest_backlog_age_days"] == 20.0

    def test_an_empty_backlog_reports_zero_age_rather_than_crashing(self, tmp_path) -> None:
        """The refusal path (L1.41): no rows means no age, and it must not IndexError."""
        _write_ledger(tmp_path, [_row("D1", "implemented", 5.0, disposed_days_ago=1.0)])
        rep = build_report(tmp_path, NOW)
        assert rep["backlog"] == 0
        assert rep["owed"] == 0
        assert rep["backlog_age_p50_days"] == 0.0
