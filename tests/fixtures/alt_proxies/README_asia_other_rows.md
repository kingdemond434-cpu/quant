# Fixtures for the Asia directive OTHER rows (2026-10-06)

All values are SYNTHETIC and illustrative: none is a measurement. Each fixture reproduces the
documented shape of the real reply. The authoring container's proxy refused both hosts, so a
fixture is the only way to exercise the parser here, and live yield stays UNMEASURED until the
box runs the leg.

- `sg_merch_trade.json`: SingStat Table Builder `api/table/tabledata/M451001`. The shape is
  `{"Data": {..., "row": [{"seriesNo", "rowText", "uoM", "columns": [{"key": "YYYY Mon",
  "value"}]}]}, "DataCount", "StatusCode", "Message"}`, as returned by the live API on
  2026-10-06 (read through the documentation fetcher). The seriesNo hierarchy (1, 2, 2.2, 3, 4,
  4.2, 5, 5.2) and the row texts are the real table's. The numbers for 2026 Jul are the
  published ones as read that day. The other months are invented.
- `sg_nodx_electronics.json`: the same API, table M450981 (Domestic Exports Of Major Non-Oil
  Products). Real seriesNo and row texts (1 Total Electronic Products, 1.3 Integrated Circuits,
  2 Non-Electronic Products).
- `wb_pink_sheet_asia.xlsx`: CMO-Historical-Data-Monthly.xlsx. A sheet named "Monthly Prices"
  holds a 4-line title block ending "Updated on <Month D, YYYY>", a blank row, one row of
  commodity names (the Pink Sheet's own labels, footnote asterisks included), one row of units,
  then one row per month keyed `YYYYMmm` in column A. A missing print is "…". The fixture is
  written by the stdlib (shared strings plus numeric cells), as Excel writes it. The column set
  is a subset of the real sheet's, and the box must confirm the header labels against the live
  file.
