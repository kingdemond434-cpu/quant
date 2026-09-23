"""L1.50 -- A FLOOR THAT HAS NOT RISEN IS A RATCHET THAT HAS STOPPED.

The ratchet failed on REGRESSION and was silent on STAGNATION. A desk measuring 89.06% every day
for a year is permanently green and permanently unimproved, and the instrument built to force
improvement reports success throughout. That is L1.49's shape one level up: not a gate that never
ran, but a gate that runs, passes, and asks nothing.

THE TWO WAYS THIS FEATURE COULD BE BUILT WRONG, both tested below, because both would leave a
check that looks like it works:

  1. `last_raised` stamped on every `--update` run. Then running the updater is indistinguishable
     from improving coverage, and the stall detector reports health in exchange for being invoked.
     That is GAP #85 exactly -- an `n` counting READINGS OF THE WORLD rather than events in it, so
     diligence in running the audit becomes the mechanism by which the audit goes wrong.
  2. A missing `last_raised` treated as 0 days. Then the OLDEST records -- the ones written before
     this law existed, the ones most likely to be stalled -- get the healthiest possible reading.
     That is GAP #83 exactly, where a register never driven once scored perfect because -1.0 fails
     every `age > bar` comparison.

And the third property, which is a design choice rather than a bug: STALLING MUST NOT EXIT
NON-ZERO. A check that goes red on a quiet day gets deleted, and a deleted check enforces nothing.
Regression is CI's business; stagnation is the auditor's.
"""

from __future__ import annotations

import contextlib
import io
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import scripts.check_coverage_floors as C


def _report(repo: float = 90.0, money: float = 60.0) -> dict[str, Any]:
    """A coverage.py JSON report shaped like the real one, with EVERY money-path file present.

    It used to synthesise only ``MONEY_PATH[0]``, which is not a shape a real pytest run can
    produce and which made these tests unable to exercise the module-absence branch at all. Since
    L1.60 an absent money-path module is a refusal -- it leaves numerator and denominator
    together, so the percentage RISES as the order path goes dark -- and a fixture narrower than
    reality would have quietly asserted the opposite (the widest-real-schema rule, desk lesson
    on libs/features/validation.py).
    """
    n = len(C.MONEY_PATH)
    return {
        "totals": {"percent_covered": repo},
        "files": {
            rel: {"summary": {"num_statements": 1000 // n,
                              "covered_lines": round(money * 10) // n}}
            for rel in C.MONEY_PATH
        },
    }


def _run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    rec: dict[str, Any],
    report: dict[str, Any],
    *,
    update: bool = False,
) -> tuple[int, str, dict[str, Any]]:
    """Drive main() against an isolated record; return (exit code, stdout, record after)."""
    rpath = tmp_path / "coverage.json"
    rpath.write_text(json.dumps(report), "utf-8")
    recpath = tmp_path / "COVERAGE_RATCHET.json"
    recpath.write_text(json.dumps(rec), "utf-8")
    monkeypatch.setattr(C, "RECORD", recpath)
    argv = ["check_coverage_floors.py", "--report", str(rpath)] + (["--update"] if update else [])
    monkeypatch.setattr("sys.argv", argv)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = C.main()
    after = json.loads(recpath.read_text("utf-8"))
    return code, buf.getvalue(), after


def _rec(repo: float, money: float, raised: str | None) -> dict[str, Any]:
    return {
        "high_water": {"repo_pct": repo, "money_path_pct": money},
        **({"last_raised": raised} if raised is not None else {}),
    }


def test_measure_normalizes_windows_coverage_paths() -> None:
    report = _report(repo=93.0, money=75.0)
    details = report["files"].pop(C.MONEY_PATH[0])
    report["files"][C.MONEY_PATH[0].replace("/", "\\")] = details

    measured = C.measure(report)

    assert measured["repo_pct"] == 93.0
    assert measured["money_path_pct"] == 75.0
    assert measured["money_path_statements"] == 1000


# ------------------------------------------------------------------ the stall itself


def test_A_LONG_QUIET_RATCHET_IS_REPORTED_AS_STALLED(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """The whole point. Floors holding is the MINIMUM; it is not the target, and an instrument
    that says only "both floors held" lets a permanently-green desk read as a finished one."""
    old = (datetime.now(tz=UTC) - timedelta(days=40)).isoformat()
    code, out, _ = _run(monkeypatch, tmp_path, _rec(89.06, 59.59, old), _report(90.0, 60.0))
    assert "STALL" in out and "40 days" in out
    assert code == 0, "stagnation must REPORT, never block -- a check that reddens quiet days dies"


def test_A_RECENT_RAISE_IS_NOT_A_STALL(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """The other half of the bar. A detector that fires always is not a detector."""
    recent = (datetime.now(tz=UTC) - timedelta(days=2)).isoformat()
    _code, out, _ = _run(monkeypatch, tmp_path, _rec(89.06, 59.59, recent), _report())
    assert "STALL" not in out
    assert "ratchet moving" in out


def test_A_MISSING_TIMESTAMP_IS_NOT_A_CLEAN_READING(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """GAP #83's shape. Every record written before this law has no `last_raised`, and those are
    precisely the records most likely to be stalled. If absence read as "raised today" the oldest
    records would score healthiest -- absence of evidence rendered as evidence of compliance, on
    the instrument whose entire job is to notice that nothing is happening."""
    _code, out, _ = _run(monkeypatch, tmp_path, _rec(89.06, 59.59, None), _report())
    assert "STALL" in out
    assert "never recorded a raise" in out


@pytest.mark.parametrize("bad", ["", "not-a-date", "2026-08-06T00:00:00"])
def test_AN_UNPARSEABLE_OR_NAIVE_STAMP_IS_ALSO_NOT_CLEAN(monkeypatch, tmp_path, bad: str) -> None:  # type: ignore[no-untyped-def]
    """A NAIVE datetime is in the list deliberately. It parses fine and then compares wrong against
    every aware timestamp in this repo -- max_audit carries a dedicated check for exactly this --
    so accepting it would produce a confident number computed from an incomparable pair. Refusing
    to grade is the correct answer to input that cannot be compared (L1.28a)."""
    _code, out, _ = _run(monkeypatch, tmp_path, _rec(89.06, 59.59, bad), _report())
    assert "STALL" in out


# ------------------------------------------------- the stamp must track the world, not the auditor


def test_UPDATE_WITHOUT_A_RAISE_DOES_NOT_TOUCH_THE_STAMP(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """GAP #85's shape, and the single most important test here. If `--update` stamped
    `last_raised` unconditionally, then RUNNING THE UPDATER would be indistinguishable from
    IMPROVING COVERAGE -- the stall detector would report health in exchange for being invoked, and
    a desk could clear this law forever by scheduling a cron job."""
    old = (datetime.now(tz=UTC) - timedelta(days=40)).isoformat()
    # measured EQUALS the floors: nothing rose.
    _code, out, after = _run(
        monkeypatch, tmp_path, _rec(90.0, 60.0, old), _report(90.0, 60.0), update=True
    )
    assert after["last_raised"] == old, "the updater stamped a raise that did not happen"
    assert "no raise" in out


def test_A_REAL_RAISE_MOVES_THE_STAMP_AND_THE_FLOOR(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    old = (datetime.now(tz=UTC) - timedelta(days=40)).isoformat()
    _code, out, after = _run(
        monkeypatch, tmp_path, _rec(89.06, 59.59, old), _report(91.0, 62.0), update=True
    )
    assert after["last_raised"] != old
    assert after["high_water"]["repo_pct"] == 91.0
    assert after["high_water"]["money_path_pct"] == 62.0
    assert "RAISED" in out


def test_A_RAISE_ON_EITHER_FLOOR_ALONE_COUNTS(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """The money path is tracked separately precisely because a repo-wide average hides it. Moving
    it while the aggregate sits still is real progress -- arguably the most valuable kind here --
    and must not be recorded as a stall."""
    old = (datetime.now(tz=UTC) - timedelta(days=40)).isoformat()
    _code, _out, after = _run(
        monkeypatch, tmp_path, _rec(90.0, 59.59, old), _report(90.0, 62.0), update=True
    )
    assert after["last_raised"] != old
    assert after["high_water"]["repo_pct"] == 90.0, "the untouched floor must not move"


def test_FLOORS_STILL_NEVER_FALL(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """The original guarantee, re-asserted because this change edited the --update branch: a
    measurement BELOW the mark must not lower it. A floor edited to fit the measurement is not a
    floor."""
    _code, _out, after = _run(
        monkeypatch, tmp_path, _rec(89.06, 59.59, None), _report(70.0, 30.0), update=True
    )
    assert after["high_water"]["repo_pct"] == 89.06
    assert after["high_water"]["money_path_pct"] == 59.59


# ------------------------------------------------------------ regression still fails, stall never


def test_REGRESSION_STILL_EXITS_NONZERO(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """The bar for this whole change: adding a soft signal must not have softened the hard one."""
    code, out, _ = _run(monkeypatch, tmp_path, _rec(89.06, 59.59, None), _report(70.0, 30.0))
    assert code == 1
    assert "BREACH" in out and "MONEY PATH" in out


def test_THE_SLACK_BAND_IS_NOT_A_BREACH(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Coverage moves with test ordering and optional-dependency skips. A floor that fires on noise
    gets deleted, which is worse than a floor set one point low."""
    code, _out, _ = _run(monkeypatch, tmp_path, _rec(89.06, 59.59, None), _report(88.5, 59.0))
    assert code == 0


# --------------------------------------------------------------- the target is printed every run


def test_THE_DISTANCE_TO_100_IS_ALWAYS_REPORTED(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """A floor is a MINIMUM and the target is 100%. Printing only the floor is how "both floors
    held" comes to sound like completion. The money-path residue is additionally rendered in
    STATEMENTS, not just percentage points, because "+40pp" is an abstraction and "~400 uncovered
    statements on the code that can move funds" is a work item."""
    _code, out, _ = _run(monkeypatch, tmp_path, _rec(89.06, 59.59, None), _report(90.0, 60.0))
    assert "to 100%" in out
    assert "+10.00pp" in out and "+40.00pp" in out
    assert "uncovered statements" in out


def test_days_since_REFUSES_RATHER_THAN_GUESSES() -> None:
    """Unit bar on the helper, since every caller's correctness rests on None meaning NOT MEASURED
    rather than zero."""
    assert C.days_since(None) is None
    assert C.days_since("") is None
    assert C.days_since("2026-08-06T00:00:00") is None, "naive stamps compare wrong -- refuse"
    fresh = C.days_since(datetime.now(tz=UTC).isoformat())
    assert fresh is not None and fresh < 0.01
    future = C.days_since((datetime.now(tz=UTC) + timedelta(days=5)).isoformat())
    assert future == 0.0, "a clock skew into the future must clamp, never report negative age"


# =============================================================================================
# THE FLOOR WAS GUARDING RETIRED CODE (gap-fixer 2026-08-29).
#
# Until today MONEY_PATH was the five `libs/execution/binance_*` adapters. The principal retired
# that universe on 2026-08-18 (LAWS §1: no crypto-exchange-native ground, ever again), and
# nobody updated the list -- so the "money path 89.44%" every session read at the top of its
# context was measured entirely over code that can never execute, while
# `desks/mt5/mt5desk/gateway.py` (1510 lines, FOUR `mt5.order_send` call sites) and
# `libs/execution/broker.py` (`place_order`/`cancel_order`) sat in no floor at all.
#
# A guard aimed at retired ground reads healthy forever. These tests pin the three properties
# that keep that from happening again -- and note the FIRST one is about the list itself, since
# every other property here would have passed unchanged while the list pointed at dead code.
# =============================================================================================


def test_the_money_path_is_the_universe_the_desk_actually_trades() -> None:
    """The defect itself: a floor whose population the mandate retired seven days earlier."""
    banned = [f for f in C.MONEY_PATH if "binance" in f]
    assert not banned, (
        f"MONEY_PATH still contains retired crypto adapters {banned}. LAWS §1 bans that universe "
        "permanently, so their coverage cannot describe code that can move funds -- it describes "
        "code that cannot run. Retired populations belong in MONEY_PATH_RETIRED."
    )
    assert C.MONEY_PATH, "an empty money path is not a clean reading, it is an absent one"
    live = set(C.MONEY_PATH) | set(C.MONEY_PATH_UNMEASURABLE_HERE)
    assert "desks/mt5/mt5desk/gateway.py" in live, (
        "the MT5 gateway places every real order on the mandated universe; it must be in the "
        "money path, either measured or explicitly named unmeasurable"
    )


def test_an_unmeasurable_money_path_file_is_named_never_silently_dropped() -> None:
    """L1.28a. `gateway.py` cannot be imported here (MetaTrader5 is Windows-only).

    Absent-and-fine and absent-and-broken must not render identically, and the reason has to
    travel with the verdict or the next reader re-derives it from scratch.
    """
    assert C.MONEY_PATH_UNMEASURABLE_HERE, "the unmeasurable set went empty -- was it dropped?"
    for path, reason in C.MONEY_PATH_UNMEASURABLE_HERE.items():
        assert len(reason) > 80, f"{path} carries no real reason, just a label"
    measured = C.measure(_report())
    assert measured["money_path_unmeasurable_here"] == sorted(C.MONEY_PATH_UNMEASURABLE_HERE)
    # ...and the percentage must not absorb it: 88 statements of broker+staging is the whole
    # denominator, so an unmeasurable 1510-line file cannot flatter the number by joining it.
    assert "desks/mt5/mt5desk/gateway.py" not in C.MONEY_PATH


def test_gap_to_target_never_claims_zero_while_a_file_is_unmeasurable() -> None:
    """At 100% of the measurable set this printed '~0 uncovered statements on the code that can
    move funds' -- with the largest order-placing file in the repo executed by nothing."""
    text = C.gap_to_target(C.measure(_report(repo=100.0, money=100.0)))
    assert "UNKNOWN, not zero" in text, text
    assert "desks/mt5/mt5desk/gateway.py" in text, text


def test_a_floor_from_one_population_is_never_compared_to_another(  # type: ignore[no-untyped-def]
    monkeypatch, tmp_path
) -> None:
    """The GENERAL form of today's bug, and the fence that would have caught it on 08-18.

    Comparing a new population to an inherited floor is meaningless in both directions: it
    invents a breach when the new set is younger and certifies a pass when it is easier.
    """
    rec = _rec(repo=90.0, money=89.44, raised=datetime.now(tz=UTC).isoformat())
    rec["money_path_files"] = ["libs/execution/binance_live.py", "libs/execution/staging.py"]
    code, out, _ = _run(monkeypatch, tmp_path, rec, _report(repo=95.0, money=10.0))
    assert "POPULATION CHANGED" in out, out
    assert "MONEY PATH coverage" not in out, (
        "a 10% measurement was compared against a 89.44% floor earned by DIFFERENT files; "
        f"that comparison is not a measurement:\n{out}"
    )
    assert code == 0, f"an inherited-population notice is not a breach:\n{out}"


def test_migration_preserves_the_old_floor_and_its_files(  # type: ignore[no-untyped-def]
    monkeypatch, tmp_path
) -> None:
    """Deleting the retired number would be the denominator trick; max()-ing across populations
    would pin an unrelated set to a bar it never ran against. Neither: archive, then establish."""
    # repo coverage held FLAT on purpose: if it rose, `last_raised` would move for a legitimate
    # reason and the assertion below could not tell that apart from the migration moving it.
    rec = _rec(repo=95.0, money=89.44, raised="2026-08-09T03:39:44.592569+00:00")
    rec["money_path_files"] = ["libs/execution/binance_live.py"]
    code, out, after = _run(monkeypatch, tmp_path, rec, _report(repo=95.0, money=40.0), update=True)
    assert code == 0, out
    sup = after["high_water"].get("superseded_money_path")
    assert sup, f"the old floor was discarded rather than archived: {after['high_water']}"
    assert sup["pct"] == 89.44
    assert sup["files"] == ["libs/execution/binance_live.py"], "archived without its population"
    assert after["high_water"]["money_path_pct"] == 40.0, (
        "the new population must be floored on its own FIRST measurement, not max()'d against a "
        "bar earned by files it does not contain"
    )
    # A MIGRATION IS NOT A RAISE: stamping last_raised here would restart the L1.50 stall clock
    # on an accounting change and the ratchet would read as moving while nothing improved.
    assert after["last_raised"] == "2026-08-09T03:39:44.592569+00:00", (
        f"last_raised moved on a population migration: {after['last_raised']}"
    )
