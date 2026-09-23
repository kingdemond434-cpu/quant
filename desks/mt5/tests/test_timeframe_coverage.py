"""The desk must be able to research more than one chart, and must know when it cannot.

`download_all_symbols.py` keyed its "already downloaded" set by SYMBOL alone, computed from
`*_H1.parquet` -- so the moment a symbol had an H1 file the downloader considered it finished and
never fetched a second timeframe for it. Not once, ever. The store held 101 H1 files and six
non-H1 in total, all placed by hand. The desk was structurally hourly and nothing said so, which
made a ceiling nobody chose look like a decision somebody had made.

The keying is fixed. Nothing checked the RESULT, and a fixed downloader that never ran leaves the
lake exactly as it was.

WHY IT IS AN EDGE QUESTION. Mechanisms live on charts. A desk researching one timeframe cannot
discover anything faster or slower than it and produces no evidence of what it missed, because an
untested mechanism leaves no trace of its absence.
"""
from __future__ import annotations

import sys
from pathlib import Path

DESK = Path(__file__).resolve().parent.parent
REPO = DESK.parent.parent
for _p in (str(DESK), str(REPO), str(DESK / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from scripts import check_timeframe_coverage as tf  # noqa: E402


def test_the_checker_and_the_downloader_agree_on_the_ladder() -> None:
    """Two lists that must match and are compared by nothing will drift.

    If the downloader learns a new timeframe and this check does not, the new chart is fetched and
    never graded; if this check gains one the downloader lacks, it reports a permanent gap nobody
    can close.
    """
    ok, why = tf.downloader_agrees()
    assert ok, why


def test_the_event_lane_is_not_graded_on_the_chart_ladder() -> None:
    """Single-name equities are traded on news and never hunted (principal, 2026-09-06).

    Demanding M1-through-D1 for hundreds of share CFDs would report a gap that is a deliberate
    policy AND spend the download budget filling it. Routing is by asset class from MetaTrader's
    registry, never a symbol list -- a ticker is what lies about a share CFD called `3M`.
    """
    cov = tf.coverage()
    assert cov["hunted_symbols"] + cov["event_lane_symbols"] == cov["symbols"]
    assert "never hunted" in cov["event_lane_note"]


def test_an_unroutable_symbol_is_not_treated_as_hunted() -> None:
    """UNKNOWN IS NOT PERMISSION.

    Unable to route means unable to say the ladder is required, and reporting a gap we cannot
    substantiate is how a board gets ignored.
    """
    assert tf._hunted("NOTREAL_NOT_A_SYMBOL_XYZ") is False


def test_h1_literals_are_graded_by_where_they_sit_not_counted() -> None:
    """A raw count over the tree reports hundreds and is useless.

    A hardcoded chart in a one-off debug script is noise; the same literal written as a DEFAULT
    into every mined row flattens the chart a strategy was described on before the docket sees it.
    Those are not the same defect and must not share a number.
    """
    graded = tf.hardcoding()
    assert graded, "no H1 literals found at all -- the pattern has stopped matching"
    assert set(graded) <= {"PIPELINE", "MINER_SOURCE", "OTHER", "THROWAWAY"}
    for tier, row in graded.items():
        assert row["count"] >= len(row["examples"]), tier


def test_tests_are_excluded_from_the_hardcoding_scan() -> None:
    """A test may legitimately name a chart; flagging them would make the fence unusable."""
    for rows in tf.hardcoding().values():
        for hit in rows["examples"]:
            assert "/tests/" not in hit, hit


def test_a_missing_chart_is_a_verdict_not_a_pass() -> None:
    """`main` exits non-zero while a chart is absent or a miner source hardcodes one.

    A green exit would say the desk can research every timeframe it stores, which is the claim the
    old downloader made implicitly for months.
    """
    cov = tf.coverage()
    hard = tf.hardcoding()
    expect_fail = bool(cov["absent_timeframes"]) or bool(
        hard.get("MINER_SOURCE", {}).get("count"))
    assert tf.main(["--report"]) == (1 if expect_fail else 0)


def test_the_ladder_covers_faster_and_slower_than_hourly() -> None:
    """The point of the ladder is charts H1 cannot see."""
    assert "M1" in tf.EXPECTED_TIMEFRAMES and "M5" in tf.EXPECTED_TIMEFRAMES
    assert "H4" in tf.EXPECTED_TIMEFRAMES and "D1" in tf.EXPECTED_TIMEFRAMES


def test_it_is_watched_for_freshness_like_every_other_producer() -> None:
    """A producer absent from CADENCE is a producer nothing can notice going quiet."""
    from research import issue_board

    named = {name for name, _rel, _cad, _prod in issue_board.CADENCE}
    assert "timeframe_coverage" in named
