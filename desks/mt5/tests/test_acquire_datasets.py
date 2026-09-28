"""Regression tests for the public-dataset acquisition format boundary."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from tests.data.xls_builder import build_xls, cell_number, cell_sst

DESK = Path(__file__).resolve().parents[1]
if str(DESK) not in sys.path:
    sys.path.insert(0, str(DESK))

from research import acquire_datasets as acquisition  # noqa: E402


def test_legacy_eia_workbook_is_parsed_and_excel_dates_are_real_dates() -> None:
    records = cell_sst(0, 0, 0) + cell_sst(0, 1, 1)
    for row in range(1, 206):
        records += cell_number(row, 0, 43_000.0 + row)
        records += cell_number(row, 1, 70.0 + row / 100.0)
    raw = build_xls([("Data 1", records), ("Notes", cell_sst(0, 0, 2))],
                    ["Date", "WTI spot", "notes"])

    frame = acquisition._parse(raw, "https://www.eia.gov/example.xls")
    assert frame is not None
    assert list(frame.columns)[:2] == ["Date", "WTI spot"]
    dated = acquisition._dated(frame)
    assert dated is not None and len(dated) == 205
    assert dated.index.min() == pd.Timestamp("2017-09-23", tz="UTC")
    assert float(dated["WTI spot"].iloc[-1]) == 72.05


def test_markup_never_falls_through_to_delimited_parser() -> None:
    assert acquisition._parse(b"<html><table><tr><td>2026-01-01</td></tr></table></html>",
                              "https://example.test/data.xls") is None
