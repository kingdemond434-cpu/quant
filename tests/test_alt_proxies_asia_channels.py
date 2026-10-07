"""Asia directive OTHER rows: the SingStat trade tables (NODX, electronics, commodity trade) and
the World Bank Pink Sheet Asian commodity channels, as alt_proxies rows.

Fixtures under tests/fixtures/alt_proxies are SYNTHETIC files shaped like each publisher's reply
(README_asia_other_rows.md says what each shape is based on); the numbers are never measured.
"""
from __future__ import annotations

import io
import json
import sys
import zipfile
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data.xls_reader import XlsError, read_xlsx  # noqa: E402
from research import alt_proxies as A  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "alt_proxies"
NOW = datetime(2026, 10, 6, 12, tzinfo=UTC)
NEW = ("sg_merch_trade", "sg_nodx_electronics", "wb_pink_sheet_asia")


def _obs(sid: str, name: str) -> dict[tuple[str, date], A.Obs]:
    parse = A.BY_ID[sid].parse
    assert parse is not None
    return {(o.series, o.period): o for o in parse((FIX / name).read_bytes(), A.Ctx())}


def test_singstat_trade_reads_rows_by_series_number_never_by_position() -> None:
    by = _obs("sg_merch_trade", "sg_merch_trade.json")
    jul = date(2026, 7, 31)
    assert by[("nodx", jul)].value == 19378953.0                  # row 4.2, not 2.2 or 5.2
    assert by[("nonoil_imports", jul)].value == 66634597.0
    assert by[("nonoil_re_exports", jul)].value == 60250884.0
    assert by[("total_trade", jul)].value == 167718472.0
    assert ("food_live_animals", jul) not in by                    # unmapped rows never emitted
    assert all(o.published_at is None for o in by.values())       # the calendar rule governs


def test_singstat_electronics_reads_the_electronics_and_ic_rows() -> None:
    by = _obs("sg_nodx_electronics", "sg_nodx_electronics.json")
    jul = date(2026, 7, 31)
    assert by[("electronics_dx", jul)].value == pytest.approx(7670643.4)
    assert by[("ic_dx", jul)].value == pytest.approx(3142224.7)
    assert by[("non_electronics_dx", jul)].value == 11708309.0
    assert {s for s, _ in by} == {"electronics_dx", "ic_dx", "non_electronics_dx"}


def test_pink_sheet_finds_the_header_by_name_and_skips_missing_prints() -> None:
    by = _obs("wb_pink_sheet_asia", "wb_pink_sheet_asia.xlsx")
    series = {s for s, _ in by}
    assert series == set(A.PINK_SHEET_COLUMNS.values())     # Brent is in the sheet, unmapped
    assert ("lng_japan", date(2024, 1, 31)) not in by              # "…" is skipped, never zero
    assert ("palm_oil", date(2024, 1, 31)) in by
    assert max(p for _, p in by) == date(2026, 9, 30)


def test_pink_sheet_update_date_stamps_only_the_newest_month() -> None:
    by = _obs("wb_pink_sheet_asia", "wb_pink_sheet_asia.xlsx")
    stamped = {p for (_, p), o in by.items() if o.published_at is not None}
    assert stamped == {date(2026, 9, 30)}
    o = by[("nickel", date(2026, 9, 30))]
    assert o.published_at == datetime(2026, 10, 2, 23, 59, tzinfo=UTC)


def test_pink_sheet_release_rule_is_the_third_business_day_never_earlier() -> None:
    # The page's own "Next update: November 3, 2026" is the 2nd business day of November.
    assert A.rule_pink_sheet(date(2026, 10, 31)) == datetime(2026, 11, 4, tzinfo=UTC)
    for m in range(1, 13):
        end = A._month_end(2026, m)
        t = A.rule_pink_sheet(end)
        assert t.date() > end and t.weekday() < 5
        # never before the second business day of the next month
        d, n = end + timedelta(days=1), 0
        while n < 2:
            n += d.weekday() < 5
            d += timedelta(days=1)
        assert t.date() >= d - timedelta(days=1)


def test_a_pink_sheet_month_is_available_only_from_its_release_and_revisions_append() -> None:
    src = A.BY_ID["wb_pink_sheet_asia"]
    obs = list(_obs("wb_pink_sheet_asia", "wb_pink_sheet_asia.xlsx").values())
    store: dict[str, dict[str, object]] = {}
    A.merge_vintages(store, src, obs, NOW)
    revised = [A.Obs("tin", date(2026, 8, 31), 99999.0)]
    m = A.merge_vintages(store, src, revised, NOW + timedelta(days=30))
    assert m == {"added": 0, "revised": 1}
    row = store["tin|2026-08-31"]
    assert row["value_first"] != 99999.0 and row["value_last"] == 99999.0
    pts = A.build_points(src, store)["tin"]
    for p in pts:
        assert datetime.fromisoformat(p["available_time"]).date() > date.fromisoformat(p["d"])
    assert any(p["surprise_z"] is not None for p in pts)          # mom pace -> surprise -> z


def test_terms_are_confirmed_with_verbatim_evidence_and_the_gate_stays_closed() -> None:
    for sid in NEW:
        assert A.TERMS[sid][0] == "confirmed"
        ev = A.TERMS_EVIDENCE[sid]
        assert ev["terms_url"].startswith("https://") and ev["terms_quote"]
        assert ev["checked_at"] == "2026-10-07"
    assert "commercial use" in A.TERMS_EVIDENCE["wb_pink_sheet_asia"]["terms_quote_2"]
    # the existing fail-closed rows are untouched
    assert A.TERMS["cn_sge_premium"][0] == "to_confirm"
    assert A.TERMS["jp_jnto_arrivals"][0] == "refused"


def test_every_cell_names_its_provider_and_dataset() -> None:
    gains = {"wb_pink_sheet_asia|nickel|XNIUSD": {"verdict": "PASS", "ic": 0.2, "n": 40},
             "sg_merch_trade|nodx|USDSGD": {"verdict": "PASS", "ic": -0.1, "n": 40},
             "kr_exports_early|daily_avg_yoy|USDKRW": {"verdict": "PASS", "ic": -0.1, "n": 40}}
    cells = {c["cell"]: c for c in A.direct_cells(gains, NOW)}
    ds = {c["provenance"]["source_id"]: c["data_source"] for c in cells.values()}
    assert ds == {"wb_pink_sheet_asia": "worldbank:cmo_pink_sheet_monthly",
                  "sg_merch_trade": "singstat:M451001",
                  "kr_exports_early": "alt_proxies:kr_exports_early"}


def test_every_mapped_cell_is_charged_and_share_cfds_never_mint() -> None:
    src = A.BY_ID["wb_pink_sheet_asia"]
    for s in src.signal_series:
        legs = src.instruments_for(s)
        assert legs, s
        assert all(A.may_mint(sym) for sym in legs), s


def test_the_pink_sheet_is_fetched_at_most_once_per_utc_day() -> None:
    src = A.BY_ID["wb_pink_sheet_asia"]
    state: dict[str, object] = {}
    first = A.requests_for(src, NOW, state)
    assert len(first) == 1 and state["fetched_day_next"] == "2026-10-06"
    state["fetched_day"] = state.pop("fetched_day_next")
    assert A.requests_for(src, NOW + timedelta(hours=1), state) == []
    assert len(A.requests_for(src, NOW + timedelta(days=1), state)) == 1


def test_fixture_pass_publishes_axes_the_field_catalogue_reads(tmp_path: Path) -> None:
    """THE CONSUMER: `alpha_dsl.axis_fields` (FieldCatalogue -> world_model ->
    representation_forge) reads every alt_<id> axis; the new rows must arrive there PIT-stamped."""
    paths = A.Paths(tmp_path / "desk")
    rep = A.run(paths, fixtures=FIX, donate=False, now=NOW)
    from libs.research.alpha_dsl import axis_fields
    for sid in NEW:
        assert rep["sources"][sid]["store_rows"] > 0, sid
        fields = [f for f in axis_fields(paths.axes) if f.source == f"axis:alt_{sid}"]
        assert fields and all(f.availability == "available_time" for f in fields), sid
    assert (paths.series / "alt_wb_pink_sheet_asia__palm_oil.csv").exists()
    assert (paths.series / "alt_sg_merch_trade__nodx.csv").exists()


def test_xlsx_reader_finds_sheets_by_name_and_refuses_garbage() -> None:
    sheets = read_xlsx((FIX / "wb_pink_sheet_asia.xlsx").read_bytes())
    assert [s.name for s in sheets] == ["AFOSHEET", "Monthly Prices"]
    assert sheets[0].cells[(0, 0)] == "About this file (synthetic fixture)"   # inline string
    with pytest.raises(XlsError):
        read_xlsx(b"not a zip")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("xl/workbook.xml", "<broken")
    with pytest.raises(XlsError):
        read_xlsx(buf.getvalue())


def test_singstat_fixture_shape_matches_the_documented_reply() -> None:
    for name in ("sg_merch_trade.json", "sg_nodx_electronics.json"):
        doc = json.loads((FIX / name).read_text("utf-8"))
        assert set(doc) == {"Data", "DataCount", "StatusCode", "Message"}
        for r in doc["Data"]["row"]:
            assert {"seriesNo", "rowText", "uoM", "columns"} <= set(r)


# ---------------------------------------------------------------- audit HOLD fixes (PR #253)
def _old_weekday_rule(period: date) -> date:
    """The rule the audit held: third WEEKDAY, holidays ignored (kept here as the control)."""
    t, n = period + timedelta(days=1), 0
    while True:
        if t.weekday() < 5:
            n += 1
            if n == 3:
                return t
        t += timedelta(days=1)


def test_pink_sheet_rule_never_stamps_before_the_release_over_108_months() -> None:
    """Release = the second US federal business day of the next month, computed independently
    with pandas' CustomBusinessDay over USFederalHolidayCalendar. Over 2018-01..2026-12 the
    weekday-only rule stamped 15 months on or before that day; the federal rule stamps none."""
    import pandas as pd
    from pandas.tseries.holiday import USFederalHolidayCalendar
    from pandas.tseries.offsets import CustomBusinessDay
    bday = CustomBusinessDay(calendar=USFederalHolidayCalendar())
    early_new = early_old = 0
    months = [A._month_end(2018 + i // 12, i % 12 + 1) for i in range(108)]
    assert len(months) == 108 and months[-1] == date(2026, 12, 31)
    for end in months:
        first = pd.Timestamp(end + timedelta(days=1))
        release = (first - bday + 2 * bday).date()            # 2nd federal business day
        stamp = A.rule_pink_sheet(end)
        assert stamp.tzinfo is not None and stamp.hour == 0
        early_new += stamp.date() <= release
        early_old += _old_weekday_rule(end) <= release
    assert early_new == 0
    assert early_old == 15                                     # the audited defect, reproduced
    # Labor Day 2025 (Sep 1): release Sep 3, so the stamp is Sep 4, never Sep 3
    assert A.rule_pink_sheet(date(2025, 8, 31)) == datetime(2025, 9, 4, tzinfo=UTC)
    # New Year's Day 2026 (Thu): release Jan 5 (Mon), stamp Jan 6
    assert A.rule_pink_sheet(date(2025, 12, 31)) == datetime(2026, 1, 6, tzinfo=UTC)


def test_every_cited_terms_evidence_key_exists() -> None:
    """A TERMS reason or a TERMS_EVIDENCE text that names another source (or says
    'TERMS_EVIDENCE') cites evidence; every cited key must be a TERMS_EVIDENCE row."""
    import re
    ids = set(A.BY_ID)

    def cited(text: str) -> set[str]:
        return {t for t in re.findall(r"[a-z][a-z0-9_]+", text) if t in ids}

    missing: list[tuple[str, str]] = []
    for sid, (_, why) in A.TERMS.items():
        keys = cited(why) - {sid}
        if "TERMS_EVIDENCE" in why:
            keys.add(sid)
        missing += [(sid, k) for k in keys if k not in A.TERMS_EVIDENCE]
    for sid, ev in A.TERMS_EVIDENCE.items():
        for field, text in ev.items():
            if field.endswith("_url") or field == "robots":
                continue
            missing += [(f"{sid}.{field}", k) for k in cited(text) - {sid}
                        if k not in A.TERMS_EVIDENCE]
    assert missing == []
    assert "sg_port_throughput" in A.TERMS_EVIDENCE           # the once-dangling reference


def test_licence_quotes_are_single_verbatim_sentences_from_the_licence_pages() -> None:
    wb = A.TERMS_EVIDENCE["wb_pink_sheet_asia"]
    assert wb["terms_quote"] == ("CC-BY 4.0, with the additional terms below, is the default "
                                 "license for all Datasets produced by the World Bank itself and "
                                 "distributed as open data.")
    assert wb["terms_quote_2"].startswith("The Creative Commons Attribution 4.0 International")
    for sid in ("sg_port_throughput", *NEW):
        ev = A.TERMS_EVIDENCE[sid]
        assert " / " not in ev["terms_quote"], sid              # never two sentences glued
        assert "application" not in ev["terms_url"] and "mobile-app" not in ev["terms_url"], sid
    for sid in ("sg_port_throughput", "sg_merch_trade", "sg_nodx_electronics"):
        ev = A.TERMS_EVIDENCE[sid]
        assert ev["terms_url"] == ev["licence_url"] == "https://data.gov.sg/open-data-licence"
        assert ev["terms_quote"].startswith("You can use, access, download, copy, distribute")


def test_attribution_rides_on_the_axis_doc_the_lake_csv_and_every_cell(tmp_path: Path) -> None:
    import csv
    paths = A.Paths(tmp_path / "desk")
    A.run(paths, fixtures=FIX, donate=False, now=NOW)
    want = {"wb_pink_sheet_asia": ("The World Bank: Commodity Price Data (The Pink Sheet)",
                                   "https://data.worldbank.org/summary-terms-of-use"),
            "sg_merch_trade": ("SingStat Table Builder table M451001",
                               "https://data.gov.sg/open-data-licence"),
            "sg_nodx_electronics": ("SingStat Table Builder table M450981",
                                    "https://data.gov.sg/open-data-licence")}
    for sid, (credit, url) in want.items():
        doc = json.loads((paths.axes / f"alt_{sid}.json").read_text("utf-8"))
        assert credit in doc["attribution"]["credit"] and doc["attribution"]["licence_url"] == url
        assert "{accessed}" not in doc["attribution"]["credit"]
        lake = next(paths.series.glob(f"alt_{sid}__*.csv"))
        rows = list(csv.DictReader(lake.open(encoding="utf-8")))
        assert rows and all(credit in r["credit"] and r["licence_url"] == url for r in rows)
    assert "Singapore Open Data Licence version 1.0" in A.attribution_of(
        A.BY_ID["sg_merch_trade"], NOW)["credit"]                              # type: ignore[index]
    assert "accessed on 2026-10-06" in A.attribution_of(
        A.BY_ID["sg_merch_trade"], NOW)["credit"]                              # type: ignore[index]
    gains = {"wb_pink_sheet_asia|nickel|XNIUSD": {"verdict": "PASS", "ic": 0.2, "n": 40},
             "sg_merch_trade|nodx|USDSGD": {"verdict": "PASS", "ic": -0.1, "n": 40},
             "kr_exports_early|daily_avg_yoy|USDKRW": {"verdict": "PASS", "ic": -0.1, "n": 40}}
    for c in A.direct_cells(gains, NOW):
        sid = c["provenance"]["source_id"]
        if sid in want:
            assert want[sid][0] in c["attribution"]["credit"], sid
            assert c["attribution"]["licence_url"] == want[sid][1], sid
        else:
            assert c["attribution"] is None                    # no credit asked, none invented


def _pink_bytes() -> bytes:
    return (FIX / "wb_pink_sheet_asia.xlsx").read_bytes()


def _collect_pink(tmp_path: Path, now: datetime, getter: object) -> tuple[A.Paths, dict]:
    paths = A.Paths(tmp_path / "desk")
    rec = A.collect(paths, A.BY_ID["wb_pink_sheet_asia"], {}, now, fetch=True, fixtures=None,
                    deadline=float("inf"), getter=getter)  # type: ignore[arg-type]
    return paths, rec


def _alarms(paths: A.Paths) -> list[dict]:
    if not paths.alarms.exists():
        return []
    return [json.loads(x) for x in paths.alarms.read_text("utf-8").splitlines() if x.strip()]


def test_a_current_pink_sheet_raises_no_alarm(tmp_path: Path) -> None:
    paths, rec = _collect_pink(tmp_path, NOW, lambda url: (_pink_bytes(), "application/xlsx"))
    assert "alarm" not in rec and _alarms(paths) == []


def test_a_pink_sheet_missing_the_current_month_records_an_alarm_row(tmp_path: Path) -> None:
    # The fixture's newest month is 2026-09; by 2026-11-06 October is out (stamped Nov 4).
    later = datetime(2026, 11, 6, 12, tzinfo=UTC)
    paths, rec = _collect_pink(tmp_path, later, lambda url: (_pink_bytes(), "application/xlsx"))
    assert rec["alarm"]["alarm"] == "NO_CURRENT_MONTH"
    assert rec["alarm"]["expected_period"] == "2026-10-31"
    rows = _alarms(paths)
    assert len(rows) == 1 and rows[0]["source_id"] == "wb_pink_sheet_asia"
    assert "ALT_WB_PINK_SHEET_URL" in rows[0]["action"]
    ev = [json.loads(x) for x in paths.events.read_text("utf-8").splitlines()]
    assert ev[-1]["kind"] == "PLUMBING_DEFECT" and ev[-1]["organ"] == "alt_proxies"


def test_a_dead_pink_sheet_link_records_an_alarm_row(tmp_path: Path) -> None:
    import urllib.error

    def dead(url: str) -> tuple[bytes, str]:
        raise urllib.error.HTTPError(url, 404, "Not Found", None, None)  # type: ignore[arg-type]

    paths, rec = _collect_pink(tmp_path, NOW, dead)
    assert rec["alarm"]["alarm"] == "LINK_DEAD"
    assert _alarms(paths)[0]["alarm"] == "LINK_DEAD"


def test_research_roi_routes_alt_proxies_ids_to_their_region() -> None:
    from research import research_roi as R
    assert R.region_of("wb_pink_sheet_asia") == "asean"
    assert R.region_of("alt_proxies:sg_merch_trade") == "asean"
    assert R.region_of("singstat:M450981") == "asean"
    assert R.region_of("worldbank:cmo_pink_sheet_monthly") == "asean"
    assert R.region_of("USDIDR.exogenous_conditioner.alt_wb_pink_sheet_asia__nickel") == "asean"
    assert R.region_of("alt_proxies:kr_mof_container_teu") == "korea"
    assert R.region_of("alt_cn_nbs_retail") == "china"
    # a multi-country row with no declared forest stays unrouted -- never guessed
    assert R.region_of("wiki_asia_attention") is None
    assert R.region_of("japan") == "japan"                      # the table still governs
