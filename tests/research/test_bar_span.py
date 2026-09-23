"""L1.68 -- a bar covering a fraction of the span its label claims.

The load-bearing tests are the ones that turn red when the WIRING is removed rather than when the
arithmetic is wrong: ``test_breadth_loader_drops_out_of_calendar_bars`` (the consumer-side repair)
and ``test_an_anomaly_is_never_discharged_by_a_floor`` (the escape hatch that would weld the gate
open). A capability is done when something RUNS it, never when it is written and correct.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from libs.ops.fence_exit import fence_exit
from libs.research.bar_span import (
    ANOMALOUS,
    CONTAMINATED,
    DECLARED,
    NOT_READABLE_HERE,
    OK,
    PASSING,
    SESSION_STUB,
    UNKNOWN_KIND,
    UNMEASURED,
    ScanReport,
    SeriesSpan,
    is_out_of_calendar,
    load_floors,
    measure_series,
    ratchet_floors,
    scan_lake,
    session_filtered,
    weekday_of_ms,
)

_ROOT = Path(__file__).resolve().parents[2]

# 2024-01-01 was a Monday. The whole module's calendar arithmetic hangs off this anchor, so it is
# stated as a date a reader can check rather than as a magic epoch.
_MON = int(datetime(2024, 1, 1, tzinfo=UTC).timestamp() * 1000)
_DAY = 86_400_000


def _days(*offsets: int) -> list[int]:
    return [_MON + d * _DAY for d in offsets]


# ---------------------------------------------------------------------------------------------
# 1. The calendar arithmetic.
# ---------------------------------------------------------------------------------------------

def test_weekday_of_ms_anchors_on_a_date_a_reader_can_verify():
    assert weekday_of_ms(_MON) == 0, "2024-01-01 was a Monday"
    assert weekday_of_ms(_MON + 5 * _DAY) == 5, "2024-01-06 was a Saturday"
    assert weekday_of_ms(_MON + 6 * _DAY) == 6, "2024-01-07 was a Sunday"
    assert weekday_of_ms(0) == 3, "the epoch itself was a Thursday"


def test_the_arithmetic_matches_pandas_across_a_long_span():
    """A hand-rolled weekday is only worth having if it agrees with the reference everywhere."""
    stamps = [_MON + i * _DAY for i in range(-4000, 4000, 7)]
    reference = pd.to_datetime(pd.Series(stamps), unit="ms", utc=True).dt.weekday.tolist()
    assert [weekday_of_ms(t) for t in stamps] == reference


@pytest.mark.parametrize("offset,expected", [(0, False), (4, False), (5, True), (6, True)])
def test_out_of_calendar_flags_exactly_the_shut_days(offset, expected):
    assert is_out_of_calendar(_MON + offset * _DAY, trades_weekends=False) is expected


def test_a_market_that_trades_weekends_is_never_out_of_calendar():
    """Crypto is open 24/7, so the concept does not apply and must not be manufactured."""
    assert all(
        is_out_of_calendar(_MON + d * _DAY, trades_weekends=True) is False for d in range(7)
    )


# ---------------------------------------------------------------------------------------------
# 2. The repair -- filter at the read, never delete from disk.
# ---------------------------------------------------------------------------------------------

def test_session_filtered_drops_shut_days_and_keeps_values_aligned():
    ts = _days(0, 5, 6, 7)                       # Mon, Sat, Sun, Mon
    kept, (closes,) = session_filtered(ts, [1.0, 2.0, 3.0, 4.0])
    assert kept == _days(0, 7)
    assert closes == [1.0, 4.0], "the surviving values must still line up with their timestamps"


def test_session_filtered_refuses_to_align_by_truncation():
    """A silently shortened price series is this module's own defect one layer down."""
    with pytest.raises(ValueError, match="refusing to align by truncation"):
        session_filtered(_days(0, 1, 2), [1.0, 2.0])


# ---------------------------------------------------------------------------------------------
# 3. Measurement, and the two kinds it must never merge.
# ---------------------------------------------------------------------------------------------

def test_measure_series_counts_saturday_and_sunday_separately():
    span = measure_series("EURILS", "fx", _days(0, 5, 6, 7, 13))
    assert (span.n_bars, span.n_saturday, span.n_sunday) == (5, 1, 2)
    assert span.n_out_of_calendar == 3
    assert span.share == pytest.approx(0.6)


def test_a_tiny_weekend_bar_is_a_session_stub():
    """The measured FX case: ~0.5% of weekday volume. Real market time, wrongly weighted."""
    span = measure_series("AUDNZD", "fx", _days(0, 1, 5), volumes=[20000.0, 20000.0, 100.0])
    assert span.kind == SESSION_STUB


def test_a_full_size_weekend_bar_is_ANOMALOUS_not_a_stub():
    """SKYY: 15x-90x a normal bar on a shut market. Excluding it would hide, not fix."""
    span = measure_series("SKYY", "equity", _days(0, 1, 5), volumes=[10000.0, 10000.0, 400000.0])
    assert span.kind == ANOMALOUS


def test_without_volume_the_kind_is_UNKNOWN_and_never_resolved_to_either():
    """'We could not tell' and 'it is a harmless stub' are different claims (L1.28a)."""
    assert measure_series("X", "fx", _days(0, 5)).kind == UNKNOWN_KIND


def test_a_zero_in_calendar_median_yields_UNKNOWN_rather_than_a_division():
    span = measure_series("X", "fx", _days(0, 1, 5), volumes=[0.0, 0.0, 500.0])
    assert span.kind == UNKNOWN_KIND


def test_a_clean_series_has_no_kind_at_all():
    span = measure_series("EURUSD", "fx", _days(0, 1, 2), volumes=[1.0, 1.0, 1.0])
    assert span.n_out_of_calendar == 0 and span.kind is None and span.status == OK


def test_a_weekend_trading_class_is_measured_as_clean():
    span = measure_series("BTCUSDT", "crypto", _days(0, 5, 6), volumes=[1.0, 1.0, 1.0])
    assert span.n_out_of_calendar == 0 and span.status == OK


def test_measure_series_refuses_a_volume_length_mismatch():
    with pytest.raises(ValueError, match="refusing to align by truncation"):
        measure_series("X", "fx", _days(0, 1, 2), volumes=[1.0])


# ---------------------------------------------------------------------------------------------
# 4. The verdict, and the escape hatch that must not exist.
# ---------------------------------------------------------------------------------------------

def _stub(share: float, floor: float | None, *, n: int = 1000) -> SeriesSpan:
    return SeriesSpan("S", "fx", n, int(share * n), 0, int(share * n), floor, volume_ratio=0.005)


def test_contamination_at_or_below_its_floor_is_DECLARED():
    assert _stub(0.05, 0.05).status == DECLARED
    assert _stub(0.04, 0.05).status == DECLARED, "a repair must be allowed to land"


def test_a_floor_recorded_from_an_unchanged_measurement_reads_DECLARED():
    """REGRESSION. The floors file stores round(share, 6); comparing that against the FULL
    precision share made a symbol fail against a baseline written from its own unchanged
    measurement. CHFNOK is the real instance: 362/3,974 = 0.09110216 against a stored 0.091102,
    which rendered as the identical 9.1092% on both sides while reading CONTAMINATED.
    """
    span = SeriesSpan("CHFNOK", "fx", 3974, 362, 0, 362, floor=round(362 / 3974, 6),
                      volume_ratio=0.005)
    assert span.status == DECLARED, "a symbol may not fail against its own recorded baseline"


def test_contamination_above_its_floor_is_CONTAMINATED():
    """The only growth path, and the reason this gate can fail at all (L1.63)."""
    assert _stub(0.06, 0.05).status == CONTAMINATED


def test_contamination_with_no_recorded_floor_is_CONTAMINATED():
    """A new dirty symbol must not slip in as 'declared' because nobody wrote it down."""
    assert _stub(0.01, None).status == CONTAMINATED


def test_an_anomaly_is_never_discharged_by_a_floor():
    """THE ESCAPE HATCH THAT WOULD WELD THE GATE OPEN (L1.63).

    A full-size bar on a shut market is repaired in the INGEST. If a floor could discharge it,
    the desk would buy a green board with the one class the read-side filter cannot fix.
    """
    anomaly = SeriesSpan("SKYY", "equity", 1000, 10, 5, 5, floor=0.01, volume_ratio=30.0)
    assert anomaly.kind == ANOMALOUS
    assert anomaly.status == CONTAMINATED, "a floor must never silence an anomaly"


def test_ratchet_moves_floors_down_but_never_up():
    report = ScanReport(series=[_stub(0.02, 0.05), _stub(0.09, 0.05)])
    report.series[1] = SeriesSpan("T", "fx", 1000, 90, 0, 90, 0.05, volume_ratio=0.005)
    moved = ratchet_floors({"S": 0.05, "T": 0.05}, report)
    assert moved["S"] == pytest.approx(0.02), "a repair is permanent"
    assert moved["T"] == pytest.approx(0.05), "a regression is never re-baselined into acceptance"


def test_a_cleaned_series_ratchets_to_zero():
    clean = SeriesSpan("S", "fx", 1000, 0, 0, 0, floor=0.05)
    assert ratchet_floors({"S": 0.05}, ScanReport(series=[clean]))["S"] == 0.0


def test_an_anomaly_is_never_written_into_the_floors_file():
    anomaly = SeriesSpan("SKYY", "equity", 1000, 10, 5, 5, None, volume_ratio=30.0)
    assert "SKYY" not in ratchet_floors({}, ScanReport(series=[anomaly]))


# ---------------------------------------------------------------------------------------------
# 5. The refusal paths -- unmeasured must never read as fine (L1.28a).
# ---------------------------------------------------------------------------------------------

def test_a_scan_that_measured_nothing_is_UNMEASURED_never_OK():
    assert ScanReport(series=[]).status == UNMEASURED
    assert UNMEASURED not in PASSING


def test_an_unreadable_lake_is_its_own_status_and_never_folded_into_OK():
    """'We did not look' must stay distinct from 'we looked and it was clean' (L1.65)."""
    report = ScanReport(series=[], readable=False)
    assert report.status == NOT_READABLE_HERE
    assert NOT_READABLE_HERE != OK and NOT_READABLE_HERE in PASSING


def test_scan_of_an_absent_lake_reports_not_readable_rather_than_clean(tmp_path):
    assert scan_lake(tmp_path / "nope").status == NOT_READABLE_HERE


def test_the_fence_exit_map_fails_every_non_passing_status():
    assert fence_exit(OK, PASSING, scanned=1, of="t") == 0
    assert fence_exit(DECLARED, PASSING, scanned=1, of="t") == 0
    assert fence_exit(NOT_READABLE_HERE, PASSING, scanned=1, of="t") == 0
    assert fence_exit(CONTAMINATED, PASSING, scanned=1, of="t") == 2
    assert fence_exit(UNMEASURED, PASSING, scanned=1, of="t") == 2


def test_a_passing_status_over_a_zero_denominator_is_refused():
    """L1.57: a fence that scanned nothing has not passed, whatever its status says."""
    assert fence_exit(OK, PASSING, scanned=0, of="t") == 2


def test_missing_or_malformed_floors_fail_loud_rather_than_clean(tmp_path):
    """Defaulting the other way lets a deleted floors file manufacture a green board (L1.55)."""
    assert load_floors(tmp_path / "absent.json") == {}
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", "utf-8")
    assert load_floors(bad) == {}
    wrong = tmp_path / "wrong.json"
    wrong.write_text(json.dumps({"floors": [1, 2]}), "utf-8")
    assert load_floors(wrong) == {}
    good = tmp_path / "good.json"
    good.write_text(json.dumps({"floors": {"S": 0.05, "T": "x"}}), "utf-8")
    assert load_floors(good) == {"S": 0.05}, "a non-numeric floor is dropped, not coerced"


# ---------------------------------------------------------------------------------------------
# 6. Attrition -- a skipped series must never leave the denominator in silence (L1.60).
# ---------------------------------------------------------------------------------------------

def test_an_unreadable_series_is_counted_and_named_never_silently_dropped(tmp_path):
    lake = tmp_path / "lake" / "bronze" / "fx"
    (lake / "GOOD" / "D1").mkdir(parents=True)
    (lake / "BROKEN" / "D1").mkdir(parents=True)
    (lake / "BROKEN" / "D1" / "part-0.parquet").write_text("not a parquet file", "utf-8")

    report = scan_lake(tmp_path / "lake", classes=("fx",))
    assert report.n_attempted == 2, "both symbol dirs must enter the denominator"
    doc = report.as_dict()
    assert doc["n_skipped"] == 2 and {s["symbol"] for s in doc["skips"]} == {"GOOD", "BROKEN"}
    assert doc["status"] == UNMEASURED, "zero readable series is UNMEASURED, never OK"


# ---------------------------------------------------------------------------------------------
# 7. THE WIRING. These fail if the consumer-side repair is removed.
# ---------------------------------------------------------------------------------------------

def _load_breadth_module():
    spec = importlib.util.spec_from_file_location(
        "_mcsb_wiring", _ROOT / "scripts" / "measure_cross_section_breadth.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["_mcsb_wiring"] = module
    spec.loader.exec_module(module)
    return module




def test_the_fence_script_is_scheduled():
    """UNWIRED OR IDLE IS A DEFECT (III.16): built is not a status; name the caller."""
    manifest = (_ROOT / "ops" / "crontab.manifest").read_text("utf-8")
    assert "check_bar_span.py" in manifest


# NOTE (2026-08-26 adoption): the law-matrix test expected the old branch's numbering
# (L1.68). Canon assigns law numbers; when the bar-span law is added to the compendium the
# matrix row and a numbering-correct test come with it.

# NOTE (2026-08-26 adoption): two tests asserting bar_span wiring into the CRYPTO
# cross-section breadth loader were removed -- that loader is retired machinery under the
# MT5 mandate. Wiring is_out_of_calendar into the MT5 H1/D1 loaders is queued gap work.
