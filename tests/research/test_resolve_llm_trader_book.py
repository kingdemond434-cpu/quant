"""The decline grader: it must grade, it must REFUSE rather than guess, and it must be idempotent.

This is the half that makes logging declines safe. check_calibration FAILS (exit 2) on any forecast
still unresolved past its resolve_by, so a grader that quietly skips work does not merely under-
report -- it turns a green survival fence permanently red.
"""
from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def mod(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location(
        "resolve_llm_trader_book", _ROOT / "scripts/resolve_llm_trader_book.py")
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    monkeypatch.setattr(m, "_BOOK", tmp_path / "llm_trader_book.jsonl")
    monkeypatch.setattr(m, "_ROOT", tmp_path)
    import libs.self_improvement.forecast_calibration as fc
    monkeypatch.setattr(fc, "_LOG", tmp_path / "forecast_log.json")
    return m


_NOW = datetime(2026, 8, 2, tzinfo=UTC)


def _row(**kw):
    base = {"action": "PASS", "symbol": "BTCUSDT", "direction": "LONG", "horizon_hours": 8,
            "probability": 0.6, "pass_reason": "already priced",
            "at": "2026-08-01T00:00:00+00:00", "resolve_by": "2026-08-01T08:00:00+00:00"}
    base.update(kw)
    return base


def _write(mod, *rows):
    mod._BOOK.write_text("".join(json.dumps(r) + "\n" for r in rows), "utf-8")


def _ms(iso: str) -> int:
    return int(datetime.fromisoformat(iso).timestamp() * 1000)


def _prices(mod, monkeypatch, *rows, entry=100.0, exit_px=101.0):
    """Price only the EXACT instants each row's own horizon defines.

    Deliberately exact rather than a blanket stub: an off-by-one in the instant the grader asks
    for returns None here and the row is skipped, so these tests also pin that entry is priced at
    `at` and exit at `resolve_by` -- the "same horizon" the sleeve's brief promises.
    """
    table: dict[int, float] = {}
    for r in rows:
        table[_ms(r["at"])] = entry
        table[_ms(r["resolve_by"])] = exit_px
    monkeypatch.setattr(mod, "fetch_price_at", lambda s, ms: table.get(ms))


# ---- refusal paths ---------------------------------------------------------------------

def test_an_absent_book_is_NO_DATA_not_OK(mod) -> None:
    """A grader that returns the same shape for 'nothing to grade' and 'nothing wrong' reports OK
    on absent input -- unmeasured counts as zero, never as fine (L1.28a)."""
    rep = mod.run(write=False, now=_NOW)
    assert rep["status"] == "NO-DATA"
    assert rep["participation"]["flag"] == "EMPTY"


def test_rows_that_exist_but_cannot_be_graded_are_UNMEASURED(mod, monkeypatch) -> None:
    _write(mod, _row(symbol=None, direction=None))
    rep = mod.run(write=False, now=_NOW)
    assert rep["status"] == "UNMEASURED"
    assert rep["n_skipped"] == 1 and "ungradeable" in rep["skipped"][0]["why"]


def test_a_missing_venue_price_refuses_rather_than_substituting(mod, monkeypatch) -> None:
    """A guessed outcome corrupts the measurement the grading exists to produce, and the error is
    invisible in the output."""
    _write(mod, _row())
    monkeypatch.setattr(mod, "fetch_price_at", lambda s, ms: None)
    rep = mod.run(write=True, now=_NOW)
    assert rep["declines"]["n_declines"] == 0
    assert "no venue price" in rep["skipped"][0]["why"]
    assert not (mod._ROOT / "forecast_log.json").exists()   # nothing logged, nothing resolved


def test_an_immature_horizon_is_not_graded_early(mod, monkeypatch) -> None:
    _write(mod, _row(resolve_by="2026-09-01T00:00:00+00:00"))
    monkeypatch.setattr(mod, "fetch_price_at", lambda s, ms: 100.0)
    rep = mod.run(write=False, now=_NOW)
    assert rep["skipped"][0]["why"] == "horizon not yet elapsed"


def test_a_malformed_line_is_counted_not_silently_dropped(mod) -> None:
    mod._BOOK.write_text(json.dumps(_row()) + "\nnot json\n", "utf-8")
    rep = mod.run(write=False, now=_NOW)
    assert rep["malformed_rows"] == 1


# ---- grading ---------------------------------------------------------------------------

def test_a_decline_is_graded_and_resolved_under_its_own_kind(mod, monkeypatch) -> None:
    row = _row()
    _write(mod, row)
    _prices(mod, monkeypatch, row, entry=100.0, exit_px=101.0)   # LONG would have been RIGHT
    rep = mod.run(write=True, now=_NOW)

    assert rep["declines"]["n_declines"] == 1
    assert rep["graded_detail"][0]["right"] is True
    assert rep["retroactively_registered"] == 1

    import libs.self_improvement.forecast_calibration as fc
    entry = fc.get_forecast("llm_trader:2026-08-01T00:00:00+00:00")
    assert entry["kind"] == "discretionary_pass_backfill"      # separable, never pooled with calls
    assert entry["resolved"] is True and entry["outcome"] == 1.0

    # THE SAFETY PROPERTY, end to end: a graded decline does not reach the sizing statistic.
    assert fc.report()["n_resolved"] == 0
    assert fc.report(exclude_kinds=())["n_resolved"] == 1


def test_a_short_decline_grades_the_other_way(mod, monkeypatch) -> None:
    row = _row(direction="SHORT")
    _write(mod, row)
    _prices(mod, monkeypatch, row, entry=100.0, exit_px=101.0)   # price rose -> SHORT was WRONG
    rep = mod.run(write=True, now=_NOW)
    assert rep["graded_detail"][0]["right"] is False
    assert rep["graded_detail"][0]["forgone_bps"] < 0          # declining SAVED money


def test_grading_is_idempotent(mod, monkeypatch) -> None:
    """The cron line reruns every 4h over the whole book; a second pass must not double-count or
    overwrite a scored outcome."""
    row = _row()
    _write(mod, row)
    _prices(mod, monkeypatch, row, entry=100.0, exit_px=101.0)
    first = mod.run(write=True, now=_NOW)
    second = mod.run(write=True, now=_NOW)
    assert first["retroactively_registered"] == 1
    assert second["retroactively_registered"] == 0            # already registered
    assert second["declines"]["n_declines"] == 0              # already resolved, not re-graded


def test_an_all_pass_book_is_flagged_by_the_grader(mod, monkeypatch) -> None:
    a, b = _row(), _row(at="2026-08-01T01:00:00+00:00",
                        resolve_by="2026-08-01T09:00:00+00:00")
    _write(mod, a, b)
    _prices(mod, monkeypatch, a, b)
    rep = mod.run(write=False, now=_NOW)
    assert rep["participation"]["flag"] == "ALL-PASS"


def test_the_key_matches_record_calls_scheme(mod) -> None:
    """A backfill that minted a different key would create a SECOND, ungradeable forecast for the
    same decision -- and an ungradeable forecast past its deadline fails check_calibration."""
    assert mod._key(_row()) == "llm_trader:2026-08-01T00:00:00+00:00"
    assert mod._key(_row(forecast_key="llm_trader:explicit")) == "llm_trader:explicit"
