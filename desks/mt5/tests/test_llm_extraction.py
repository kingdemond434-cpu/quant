"""LLM-native extraction: no extracted row is trusted until the source text vouches for it."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import extraction_validator as ev  # noqa: E402
from research import llm_extractor as lx  # noqa: E402

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
SRC = ("国家统计局 2026年8月 居民消费价格同比上涨 0.5%。 Exports in August 2026 were 1,234.5 "
       "billion yuan. Industrial output rose 4,8 per cent in 2026-07. Outlook: 2027 growth 5%.")


def test_every_reason_code_fires_on_the_row_that_earns_it() -> None:
    rows = [
        {"period": "2026年8月", "variable": "cpi_yoy", "value": 0.5, "quote": "同比上涨 0.5%"},
        {"period": "2026-08", "variable": "exports", "value": 1234.5,
         "quote": "Exports in August 2026 were 1,234.5"},
        {"period": "2026-07", "variable": "ip", "value": 4.8, "quote": "rose 4,8 per cent"},
        {"period": "2026-08", "variable": "imports", "value": 99, "quote": "Imports were 99"},
        {"period": "2026-08", "variable": "exports2", "value": 1300,
         "quote": "Exports in August 2026 were 1,234.5"},
        {"period": "2027", "variable": "gdp", "value": 5, "quote": "2027 growth 5%"},
        {"period": "someday", "variable": "x", "value": 1, "quote": "Outlook"},
        {"period": "2026-08", "variable": "y", "value": "n/a", "quote": "Outlook"},
        {"period": "2026-08", "variable": "", "value": 1, "quote": "Outlook"},
        {"period": "2026-08", "variable": "exports", "value": 1234.0,
         "quote": "1,234.5 billion yuan"},
    ]
    v = ev.validate(rows, SRC, fetched_at=NOW)
    assert v["n_accepted"] == 3
    rc = v["reason_codes"]
    assert rc["QUOTE_NOT_IN_SOURCE"] == 1
    assert rc["VALUE_NOT_IN_QUOTE"] >= 2
    assert rc["FUTURE_PERIOD"] == 1
    assert rc["PERIOD_UNPARSEABLE"] == 1
    assert rc["NON_NUMERIC_VALUE"] == 1
    assert rc["MISSING_FIELD"] == 1
    assert set(rc) <= set(ev.REASONS)
    assert 0 < v["acceptance_rate"] < 1 and v["mean_score"] < 1


def test_a_second_value_for_the_same_period_and_variable_is_a_duplicate() -> None:
    src = "Exports were 10 in 2026-08 and 12 in 2026-08 revised."
    v = ev.validate([
        {"period": "2026-08", "variable": "exports", "value": 10, "quote": "Exports were 10"},
        {"period": "2026-08", "variable": "exports", "value": 12, "quote": "12 in 2026-08"}],
        src, fetched_at=NOW)
    assert v["n_accepted"] == 1 and v["reason_codes"] == {"DUPLICATE_ROW": 1}


def test_periods_parse_in_every_shape_a_release_writes() -> None:
    assert ev.parse_period("2026Q2") == datetime(2026, 4, 1, tzinfo=UTC)
    assert ev.parse_period("2026年8月") == datetime(2026, 8, 1, tzinfo=UTC)
    assert ev.parse_period("２０２６－０８") == datetime(2026, 8, 1, tzinfo=UTC)
    assert ev.parse_period("2026") == datetime(2026, 1, 1, tzinfo=UTC)
    assert ev.parse_period("soon") is None


def _parser_fixture(tmp_path: Path) -> dict[str, Path]:
    series = tmp_path / "series"
    series.mkdir()
    (series / "nbs_cpi.txt").write_text(SRC, encoding="utf-8")
    (tmp_path / "parser.json").write_text(json.dumps({"rows": [
        {"id": "nbs_cpi", "status": "PARSED", "kind": "pdf_text",
         "fetched_utc": "2026-09-20T00:00:00+00:00", "url": "https://stats.example/cpi.pdf"},
        {"id": "tables_ok", "status": "PARSED", "kind": "html_tables"}]}))
    return {"parser": tmp_path / "parser.json", "series": series,
            "cursor": tmp_path / "cursor.json"}


def test_with_no_seat_extraction_is_unmeasured_and_nothing_is_written(tmp_path) -> None:
    p = _parser_fixture(tmp_path)
    doc = lx.run(now=NOW, seat_available=False, paths=p)
    assert doc["status"] == "UNMEASURED" and "no LLM seat" in doc["why"]
    assert doc["candidates"] == 1
    assert not list(p["series"].glob("*.parquet")) and not p["cursor"].exists()


def test_absent_parser_report_is_unmeasured(tmp_path) -> None:
    doc = lx.run(now=NOW, seat_available=True, chat=lambda *a, **k: ("", None),
                 paths={"parser": tmp_path / "none.json", "cursor": tmp_path / "c.json"})
    assert doc["status"] == "UNMEASURED"


def test_only_validated_rows_become_a_pit_stamped_series(tmp_path) -> None:
    p = _parser_fixture(tmp_path)
    calls: list[str] = []

    def chat(prompt, **kw):
        calls.append(prompt)
        assert kw["temperature"] == 0.0
        return json.dumps({"rows": [
            {"period": "2026-08", "variable": "exports", "value": 1234.5, "unit": "bn",
             "quote": "Exports in August 2026 were 1,234.5"},
            {"period": "2026-07", "variable": "ip", "value": 4.8, "unit": "%",
             "quote": "rose 4,8 per cent"},
            {"period": "2026-08", "variable": "invented", "value": 7.7, "unit": "%",
             "quote": "an invented sentence"}]}), None

    doc = lx.run(now=NOW, chat=chat, paths=p)
    assert doc["status"] == "MEASURED" and len(calls) == 1 and "nbs_cpi" in calls[0]
    t = doc["totals"]
    assert (t["rows_extracted"], t["rows_accepted"], t["rows_rejected"]) == (3, 2, 1)
    assert t["reason_codes"]["QUOTE_NOT_IN_SOURCE"] == 1
    rec = doc["docs"][0]
    assert rec["series"]["written"] and rec["series"]["canonical_alias"] == "nbs_cpi.parquet"
    frame = pd.read_parquet(p["series"] / "nbs_cpi__llm.parquet")
    assert "available_time" in frame.columns and "invented" not in frame.columns
    assert set(frame.columns) >= {"exports", "ip"}
    # a second pass inside the resend window sends nothing
    doc2 = lx.run(now=NOW, chat=chat, paths=p)
    assert doc2["due"] == 0 and len(calls) == 1


def test_an_unparseable_reply_is_named_not_counted_as_zero_rows(tmp_path) -> None:
    p = _parser_fixture(tmp_path)
    doc = lx.run(now=NOW, chat=lambda *a, **k: ("I cannot help", None), paths=p)
    assert doc["docs"][0]["status"] == "UNPARSEABLE_REPLY"
    assert doc["acceptance_rate"] is None


def test_fetch_alfred_leg_mode_exits_zero_and_writes_its_report_without_a_key(
        monkeypatch, tmp_path) -> None:
    from research import fetch_alfred as fa
    monkeypatch.setattr(fa, "api_key", lambda: None)
    monkeypatch.setattr(fa, "REPORTS", tmp_path)
    assert fa.main(["--leg"]) == 0
    rep = json.loads((tmp_path / "alfred_vintages.json").read_text())
    assert rep["status"] == "UNAVAILABLE" and rep["written"] == 0
    assert fa.main([]) == 2          # the manual run still says so loudly
