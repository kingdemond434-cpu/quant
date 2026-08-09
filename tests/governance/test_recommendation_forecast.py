"""L1.29 forecast instrumentation on the recommendation ledger (R0112, decision point D).

The bar these tests hold is not "a forecast got logged". It is that this writer CANNOT leave an
ungraded row behind -- because an ungraded prediction inflates the apparent hit-rate by never
counting its misses, and check_calibration was already sitting at OVERDUE before this existed.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from libs.research import recommendation_forecast as rfc
from libs.self_improvement import forecast_calibration as fc

NOW = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _isolated_log(tmp_path, monkeypatch):
    """Never touch the live data/forecast_log.json from a test."""
    monkeypatch.setattr(fc, "_LOG", tmp_path / "forecast_log.json")


_OLD = (NOW - timedelta(days=40)).isoformat()          # raised long enough ago to have an outcome
_FAST = (NOW - timedelta(days=38)).isoformat()         # disposed 2d after raising: inside 14d


def _rows(implemented=0, rejected=0, open_=0, *, raised=_OLD, disposed=_FAST):
    out = []
    out += [{"id": f"R{i:04d}", "status": "implemented", "raised": raised, "disposed": disposed}
            for i in range(implemented)]
    out += [{"id": f"R1{i:03d}", "status": "rejected", "raised": raised, "disposed": disposed}
            for i in range(rejected)]
    out += [{"id": f"R2{i:03d}", "status": "open", "raised": raised, "disposed": None}
            for i in range(open_)]
    return out


def test_cold_start_is_declared_not_disguised_as_a_measurement():
    p, n, prov = rfc.base_rate(_rows(implemented=2, rejected=1), now=NOW)
    assert p == rfc._COLD_START_P and n == 3 and prov.startswith("COLD-START")


def test_the_rate_is_measured_once_the_window_has_elapsed():
    p, n, prov = rfc.base_rate(_rows(implemented=6, rejected=6), now=NOW)
    assert p == 0.5 and n == 12 and prov.startswith("MEASURED")


def test_rows_still_open_at_the_deadline_count_as_misses():
    """THE SURVIVORSHIP TRAP. Conditioning on rows that reached a terminal status reads 0.95 on
    the live ledger, because a row nobody ever decides never enters the denominator -- and those
    are exactly the failures. Forecasting off that would instrument the over-confidence INTO the
    system built to detect it."""
    p, n, _ = rfc.base_rate(_rows(implemented=6, rejected=6, open_=8), now=NOW)
    assert n == 20 and p == 0.3                       # 6/20, not 6/12


def test_a_row_whose_window_has_not_elapsed_is_not_scored_yet():
    """Its outcome is genuinely unknown -- counting it either way would be inventing evidence."""
    fresh = _rows(implemented=5, raised=(NOW - timedelta(days=2)).isoformat())
    p, n, prov = rfc.base_rate([*_rows(implemented=6, rejected=6), *fresh], now=NOW)
    assert n == 12 and p == 0.5 and prov.startswith("MEASURED")


def test_implemented_too_late_does_not_count_as_a_hit():
    """The claim is 'implemented BY a date'. Eventually is a different, easier claim."""
    slow = _rows(implemented=10, disposed=(NOW - timedelta(days=1)).isoformat())   # 39d after
    p, n, _ = rfc.base_rate([*slow, *_rows(rejected=2)], now=NOW)
    assert n == 12 and p == 0.0


def test_a_forecast_is_pre_registered_exactly_once():
    """Re-logging rolls resolve_by forward on every call and blinds the overdue check."""
    rows = _rows(implemented=6, rejected=6)
    first = rfc.on_add("R0500", rows, now=NOW)
    assert first is not None and first["resolve_by"].startswith("2026-08-19")
    assert rfc.on_add("R0500", rows, now=NOW + timedelta(days=5)) is None
    assert fc.get_forecast("rec:R0500")["resolve_by"].startswith("2026-08-19")


def test_the_claim_is_row_unique_so_scoring_does_not_collapse_them():
    """_scoreable keeps ONE observation per distinct claim string -- a shared claim would make
    every future row score as a single data point."""
    rows = _rows(implemented=6, rejected=6)
    rfc.on_add("R0501", rows, now=NOW)
    rfc.on_add("R0502", rows, now=NOW)
    claims = {fc.get_forecast(f"rec:R{n}")["claim"] for n in ("0501", "0502")}
    assert len(claims) == 2


def test_every_past_due_forecast_is_gradeable_from_the_ledger():
    """THE SELF-CLOSING PROPERTY -- the only reason this writer was allowed to exist."""
    rows = _rows(implemented=6, rejected=6)
    rfc.on_add("R0600", rows, now=NOW)
    rfc.on_add("R0601", rows, now=NOW)
    later = [*rows, {"id": "R0600", "status": "implemented"}, {"id": "R0601", "status": "rejected"}]

    assert rfc.settle(later, now=NOW + timedelta(days=1)) == []      # not due yet: untouched
    done = rfc.settle(later, now=NOW + timedelta(days=30))
    assert {d["key"]: d["outcome"] for d in done} == {"rec:R0600": True, "rec:R0601": False}
    assert fc.get_forecast("rec:R0600")["outcome"] == 1.0
    assert fc.get_forecast("rec:R0601")["outcome"] == 0.0
    assert rfc.settle(later, now=NOW + timedelta(days=60)) == []     # idempotent


def test_an_undisposed_row_grades_as_not_implemented_at_its_deadline():
    """The claim is 'reaches IMPLEMENTED by D', not 'eventually'. Still open at D is a miss --
    otherwise a row could dodge scoring forever by never being decided."""
    rows = _rows(implemented=6, rejected=6)
    rfc.on_add("R0700", rows, now=NOW)
    later = [*rows, {"id": "R0700", "status": "open"}]
    assert rfc.settle(later, now=NOW + timedelta(days=30))[0]["outcome"] is False


def test_a_vanished_row_is_never_force_graded():
    """A missing row is absence of evidence about the forecast, not evidence of failure."""
    rows = _rows(implemented=6, rejected=6)
    rfc.on_add("R0800", rows, now=NOW)
    assert rfc.settle(rows, now=NOW + timedelta(days=30)) == []
    assert not fc.get_forecast("rec:R0800").get("resolved")


def test_the_ledger_write_survives_a_broken_forecast_log(monkeypatch, capsys):
    """The ledger is the organ; the hook is instrumentation ON it. Losing a recommendation to a
    broken side-effect would trade what §42 guarantees for the thing measuring it -- and the
    failure must be PRINTED, never swallowed, or an unwritable log looks like a healthy one."""
    import scripts.recommendations as rec

    def _boom(*_a, **_k):
        raise OSError("forecast log unwritable")

    monkeypatch.setattr(rfc, "on_add", _boom)
    monkeypatch.setattr("libs.research.recommendation_forecast.on_add", _boom)
    assert rec._forecast_add("R0900", _rows(implemented=6, rejected=6)) is None
    assert "WARNING" in capsys.readouterr().out
