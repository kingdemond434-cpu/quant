"""Data-class gap #1 (fund flows), #6 (text sentiment) and the broker-feed terms row.

No network. The fixtures (tests/fixtures/data_class_gap) copy the layouts read on 2026-10-29:
MoF `week.csv` (Shift_JIS, 23 fields; the first two data rows are the live file's own), TIC
`slt_table1.txt` (preamble, three header rows, tab-separated rows; Austria rows are the live
file's), ECB `format=csvdata` (KEY/TIME_PERIOD/OBS_VALUE) and a Fed Data Download Program CSV.
The live ECB body, the live Z.1 zip and the recent MoF rows were not readable from the build
container (the proxy refuses those hosts), so their exact live shape is UNMEASURED until the box
fetches them.
"""
from __future__ import annotations

import importlib.util
import io
import re
import sys
import zipfile
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import terms_fence as tf  # noqa: E402
from research import data_class_gap as G  # noqa: E402
from research import world_dataset_hunter as W  # noqa: E402

FIX = DESK / "tests" / "fixtures" / "data_class_gap"
NOW = datetime(2026, 10, 29, 12, 0, tzinfo=UTC)


def _fx(name: str) -> bytes:
    return (FIX / name).read_bytes()


def _z1_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("Z1/z1_data.csv", _fx("z1_ddp_sample.csv"))
    return buf.getvalue()


# ------------------------------------------------------------------------- the MoF door ----
def test_mof_weekly_keeps_the_net_columns_of_both_sides_from_shift_jis():
    raw = _fx("mof_week.csv")
    with pytest.raises(UnicodeDecodeError):
        raw.decode("utf-8")                                 # the fixture is really cp932
    df = W.frame_from_payload(raw, "mof_weekly", {})
    first = df[df.period == "2005-01-02"].set_index("series_code")["value"]
    assert first["jp_outward_equity_net"] == 270.0          # F4: residents' foreign equity net
    assert first["jp_outward_total_net"] == 9811.0          # F12
    assert first["foreign_inward_equity_net"] == 2278.0     # F15: non-residents' JP equity net
    assert first["foreign_inward_total_net"] == 10363.0     # F23
    assert set(df["series_code"]) == set(W._MOF_NET_COLS.values())
    second = df[df.period == "2005-01-09"].set_index("series_code")["value"]
    assert second["jp_outward_stdebt_net"] == -671.0


def test_mof_week_periods_end_on_the_weeks_own_saturday_across_a_new_year():
    df = W.frame_from_payload(_fx("mof_week.csv"), "mof_weekly", {})
    for per in df["period"].unique():
        end, _ = W.period_end(per, "weekly")
        assert end is not None and end.weekday() == 5        # Sunday-Saturday weeks
    assert "2006-12-31" in set(df["period"])                 # "2006.12.31~ 2007.1.6"
    assert W.period_end("2006-12-31", "weekly")[0] == date(2007, 1, 6)


#: The 2026 release calendar as read from schedule.htm on 2026-10-29: (week end, release day).
#: Release time 08:50 JST = 23:50 UTC the day before.
_MOF_2026 = (("2026-09-19", "2026-10-01"), ("2026-09-26", "2026-10-01"),
             ("2026-10-03", "2026-10-08"), ("2026-10-10", "2026-10-16"),
             ("2026-10-17", "2026-10-22"), ("2026-10-24", "2026-10-29"),
             ("2026-10-31", "2026-11-06"), ("2026-11-07", "2026-11-12"),
             ("2026-11-14", "2026-11-19"), ("2026-11-21", "2026-11-27"),
             ("2026-11-28", "2026-12-03"), ("2026-12-05", "2026-12-10"),
             ("2026-12-12", "2026-12-17"), ("2026-12-19", "2026-12-24"))


@pytest.mark.parametrize("week_end,release", _MOF_2026)
def test_mof_stamp_is_never_before_the_measured_release(week_end, release):
    end = date.fromisoformat(week_end)
    available = datetime.combine(end + timedelta(days=W._mof_lag(end)), datetime.min.time(),
                                 tzinfo=UTC)
    released = datetime.combine(date.fromisoformat(release), datetime.min.time(),
                                tzinfo=UTC) + timedelta(hours=8, minutes=50) - timedelta(hours=9)
    assert available >= released
    # and an ordinary week outside a holiday cluster is not pushed past its Friday
    if W._mof_lag(end) == W._MOF_LAG_D:
        assert (available - released) < timedelta(days=2)


def test_mof_per_week_lag_reaches_the_store(tmp_path, monkeypatch):
    monkeypatch.setattr(W, "STORE", tmp_path / "world_datasets")
    monkeypatch.setattr(W, "OBS", tmp_path / "world_datasets" / "obs")
    monkeypatch.setattr(W, "MIN_REQUEST_GAP_S", 0.0)
    W._universe_at.cache_clear()
    doors = W.fund_flow_doors()
    monkeypatch.setattr(W, "direct_sources", lambda now=None: doors)
    payload = {"week.csv": _fx("mof_week.csv"), "slt_table1": _fx("tic_slt_table1.txt"),
               "slt_table2": _fx("tic_slt_table1.txt"), "IVF/": _fx("ecb_ivf.csv"),
               "FRB_Z1": _z1_zip(), "/mmf/mm_": _fx("ici_mm_release.html")}

    def fetch(url: str, timeout: float) -> bytes:
        return next(v for k, v in payload.items() if k in url)
    cat = W._blank_catalog()
    stats: Counter[str] = Counter()
    W.fetch_direct(W.Client(fetch, deadline=1e18), cat, now=NOW, until=1e18, stats=stats,
                   qstats=Counter(),
                   by_provider={d["provider"]: Counter() for d in doors})
    for key in ("JP_MOF/ITS_WEEKLY", "US_TIC/slt_table1", "ECB_IVF/ecb_ivf_total_funds_net_issues",
                "FED_Z1/FUND_FLOWS"):
        assert cat["datasets"][key]["lifecycle"] in ("INGESTED", "QUALITY-PASSED"), key
    import pandas as pd
    f = pd.read_parquet(W.dataset_path("JP_MOF", "ITS_WEEKLY"))
    r = f[(f.series_code == "foreign_inward_total_net") & (f.period == "2026-10-18")].iloc[0]
    assert r["available_time"] == pd.Timestamp("2026-10-30", tz="UTC")       # Sat + 6
    r = f[(f.series_code == "foreign_inward_total_net") & (f.period == "2006-12-31")].iloc[0]
    assert r["available_time"] == pd.Timestamp("2007-01-20", tz="UTC")       # holiday + 14
    z = pd.read_parquet(W.dataset_path("FED_Z1", "FUND_FLOWS"))
    q3 = z[(z.series_code == "FU263064105.Q") & (z.period == "2025Q3")].iloc[0]
    assert q3["available_time"] == pd.Timestamp("2025-09-30", tz="UTC") + pd.Timedelta(days=101)


# ------------------------------------------------------------- TIC, ECB and Z.1 parsers ----
def test_tic_keeps_net_flows_of_named_countries_and_totals_and_na_is_absent():
    df = W.frame_from_payload(_fx("tic_slt_table1.txt"), "tic_slt",
                              {"series_prefix": "foreign_in"})
    assert set(df["country"]) == {"Austria", "Japan", "Grand Total"}         # Narnia is not
    assert all(c.endswith("_net") for c in df["series_code"])
    assert "2020-03" not in set(df["period"])                                # every cell n.a.
    j = df[(df.series_code == "foreign_in_Japan_for_lt_treas_net")]["value"].iloc[0]
    assert j == 8000.0
    with pytest.raises(W.FetchError):
        W.frame_from_payload(b"Table 1\nno header here\n", "tic_slt", {})


def test_ecb_csvdata_reads_key_period_value_and_nan_is_absent():
    df = W.frame_from_payload(_fx("ecb_ivf.csv"), "ecb_sdmx_csv", {})
    assert list(df["period"]) == ["2026-05", "2026-06", "2026-07"]
    assert df["series_code"].iloc[0] == "IVF.M.U2.N.T0.L30.A.0.Z5.0000.Z01.E"


def test_z1_keeps_only_fund_flow_sectors_and_nd_is_absent():
    df = W.frame_from_payload(_z1_zip(), "z1_ddp_zip", {})
    assert set(df["series_code"]) == {"FU263064105.Q", "FL634090005.Q"}      # households out
    assert not ((df.series_code == "FU263064105.Q") & (df.period == "2025Q4")).any()


# ------------------------------------------------------------------- the one register ----
def test_each_fund_flow_door_reads_its_row_and_tic_is_permitted_on_its_cc0_clause():
    rows = {d["provider"]: tf.source_of_url(d["url"]) for d in W.fund_flow_doors()}
    assert rows == {"JP_MOF": "jp_mof", "US_TIC": "us_tic", "ECB_IVF": "ecb_data_portal",
                    "FED_Z1": "fed_board", "ICI": "ici_stats"}
    for key in ("jp_mof", "ecb_data_portal", "fed_board", "us_tic"):
        assert tf.terms_state(key) == "READ" and tf.terms_verdict(key) == "confirmed"
    # TIC IS PERMITTED ON A QUOTED CLAUSE, NOT BY LOOSENING: the Treasury's own data.json entry
    # (catalog.data.gov, read 2026-11-03) declares CC0 with public access. Without that quote the
    # row would fall back to UNREAD and refuse again.
    tic_row = tf.SOURCE_POLICY["us_tic"]
    assert tic_row["terms"]["clauses"]["access"] == (
        "Public: This dataset is intended for public access and use. License: Creative Commons "
        "CCZero")
    assert tic_row["terms"]["clauses"]["licence"] == \
        "http://creativecommons.org/publicdomain/zero/1.0/"
    assert tic_row["terms"]["clauses"]["publisher"] == "Department of the Treasury"
    assert tic_row["terms"]["url"].startswith("https://catalog.data.gov/dataset/")
    assert tic_row["terms"]["checked_at"] == "2026-11-03"
    assert tf.live_input_status("us_tic") == tf.PUBLIC_PAGE
    tic = next(d for d in W.fund_flow_doors() if d["provider"] == "US_TIC")
    assert tf.input_source(tic["url"]) is None
    doors = {r["door"]: r for r in W.terms_doors()}
    t = doors["US_TIC/slt_table1"]
    assert t["live_input"] == "PERMITTED" and "missed_growth" not in t
    assert t["access_label"] == "OPEN_DATA" and t["redistribute_allowed"] is True
    assert doors["JP_MOF/ITS_WEEKLY"]["live_input"] == "PERMITTED"


def test_speech_and_fss_rows_are_ideas_only_and_bis_statistics_keep_their_reading():
    assert tf.source_of_url("https://www.bis.org/speeches/speeches.zip") == "bis_speeches"
    assert tf.source_of_url("https://www.bis.org/cbspeeches/index.htm") == "bis_speeches"
    assert tf.input_source("https://www.bis.org/speeches/speeches.zip") == "bis_speeches"
    assert tf.platform_of_url("https://www.bis.org/cbspeeches/index.htm") is None  # still read
    assert tf.source_of_url("https://data.bis.org/static/bulk/WS_EER_csv_flat.zip") is None
    assert tf.live_input_status("kr_fss") == tf.IDEAS_ONLY
    assert "UNREAD" in tf.SOURCE_POLICY["kr_fss"]["why"]


def test_the_broker_row_quotes_clause_5_6_and_names_what_is_unmeasured():
    row = tf.SOURCE_POLICY["mt5_broker"]
    assert tf.source_key("mt5_broker") == "mt5_broker" and tf.terms_state("mt5_broker") == "READ"
    clause = row["terms"]["clauses"]["5.6"]
    assert "for the purpose of your trading with Fusion Markets only" in clause
    assert row["entity_match"].startswith("UNMEASURED")
    assert "E8" in row["use_scope"] and "FTMO" in row["use_scope"]
    assert tf.input_source("mt5_broker") is None


# ---------------------------------------------------------------------- the gap reading ----
def test_fund_flows_now_has_a_producer_and_reads_the_data_paths():
    spec = next(c for c in G.CLASSES if c["id"] == "fund_flows")
    assert spec["producers"] == ["research/world_dataset_hunter.py"]
    idx = G.code_hosts()
    row = G.measure_class(spec, idx=idx, legs=G.hourly_legs(), clocks={}, runtime={},
                          catalogues={}, now=NOW, tracked=None)
    cands = {c["id"]: c for c in row["candidates"]}
    for cid in ("jp_mof_weekly_securities", "us_tic", "ecb_ivf", "fed_z1"):
        assert cands[cid]["ingested"], cid
        assert "desks/mt5/research/world_dataset_hunter.py" in cands[cid]["fetched_by"]
    assert cands["jp_mof_weekly_securities"]["terms"]["live_basis"] == "OK"
    assert cands["us_tic"]["terms"]["live_basis"] == "OK"       # CC0 clause, 2026-11-03
    assert cands["kr_fss_foreign_flows"]["terms"]["live_basis"] == "REFUSED"
    assert row["coverage"].startswith("WIRED")
    text = next(c for c in G.CLASSES if c["id"] == "text_sentiment_multilang")
    t = G.measure_class(text, idx=idx, legs=G.hourly_legs(), clocks={}, runtime={},
                        catalogues={}, now=NOW, tracked=None)
    clocks = {p["module"]: p["clock"] for p in t["producers"]}
    assert clocks["desks/mt5/side_channels/central_bank_miner.py"] == \
        "hourly_cycle:central_bank_miner"


# ------------------------------------------------------------- the central-bank miner leg ----
@pytest.fixture()
def miner(tmp_path, monkeypatch):
    src = DESK / "side_channels" / "central_bank_miner.py"
    spec = importlib.util.spec_from_file_location("_cbm_leg_under_test", src)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "OUT", tmp_path)
    monkeypatch.setattr(mod, "ARCHIVE", tmp_path / "cb_documents.jsonl")
    monkeypatch.setattr(mod, "REPORT", tmp_path / "CENTRAL_BANK_MINER.json")
    return mod


_RSS = """<rss><channel><item><title>Policy statement</title><link>https://example.invalid/a</link>
<pubDate>Tue, 27 Oct 2026 18:00:00 GMT</pubDate></item></channel></rss>"""


def test_the_miner_fetches_only_through_the_polite_door_and_reports_every_feed(miner):
    calls: list[tuple[str, str]] = []

    def fetch(url, **kw):
        calls.append((url, kw.get("leg", "")))
        if "rba.gov.au" in url:
            return SimpleNamespace(ok=False, verdict="METHOD_BLOCKED", status=403, text="",
                                   error="held")
        if "boj.or.jp" in url:
            return SimpleNamespace(ok=False, verdict="", status=None, text="",
                                   error="connection")
        return SimpleNamespace(ok=True, verdict="", status=200, text=_RSS, error="")
    rows = miner.run_and_save(fetch=fetch)
    assert len(calls) == len(miner.FEEDS) and all(leg == "central_bank_miner" for _, leg in calls)
    import json
    doc = json.loads(miner.REPORT.read_text("utf-8"))
    by = {f["bank"]: f for f in doc["feeds"]}
    assert by["RBA"]["state"] == "REFUSED" and by["RBA"]["verdict"] == "METHOD_BLOCKED"
    assert by["BoJ"]["state"] == "FAILED"
    assert by["Fed"]["state"] == "OK" and by["Fed"]["new_items"] == 1
    assert doc["new_documents"] == len(rows) == 4                 # Fed, ECB, BoE, BoC
    assert "requests" not in miner.__dict__                        # no side door left
    # a second pass with nothing new writes no empty snapshot and says so
    miner.run_and_save(fetch=fetch)
    assert len(list(miner.OUT.glob("discoveries_*.json"))) == 1


def test_nothing_read_is_unmeasured_never_zero_new(miner):
    def fetch(url, **kw):
        return SimpleNamespace(ok=False, verdict="ROBOTS_UNREADABLE", status=None, text="",
                               error="")
    miner.run_and_save(fetch=fetch)
    import json
    doc = json.loads(miner.REPORT.read_text("utf-8"))
    assert doc["feeds_read"] == 0 and doc["new_documents"] == "UNMEASURED"


def test_the_central_bank_leg_is_wired_with_every_birth_row():
    src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    from libs.research.layers import LEG_LAYER
    from research import hourly_cycle as H
    assert re.search(r'_costed\("central_bank_miner", lambda: _producer\("central_bank_miner",'
                     r'\s*"side_channels/central_bank_miner.py"', src)
    assert re.search(r'"central_bank_miner": cbm', src)
    for table in (H.CORE_LEGS, H.LEG_DEPARTMENT, H.LEG_BUDGET_SEC, LEG_LAYER):
        assert "central_bank_miner" in table
    import json
    rs = json.loads((ROOT / "docs" / "research" / "runtime_state.json").read_text("utf-8"))
    row = next(r for r in rs["organs"] if r.get("organ") == "leg:central_bank_miner")
    assert row["artifact_declared"] == "desks/mt5/reports/CENTRAL_BANK_MINER.json"


# ------------------------------------------- the broker feed's scope (auditor 2026-10-29) ----
from research import terms_basis_census as C  # noqa: E402


@pytest.fixture()
def census(tmp_path, monkeypatch):
    import json
    for name, attr in (("canon.json", "CANON"), ("surv.json", "SURVIVORS"),
                       ("keys.json", "WORLD_KEYS"), ("account_state.json", "ACCOUNT"),
                       ("E8_BOOK.json", "E8_BOOK")):
        monkeypatch.setattr(C, attr, tmp_path / name)
    scope = tf.SOURCE_POLICY["mt5_broker"]["scope"]
    certs = {"a.XAUUSD.session_range_breakout":
             {"sym": "XAUUSD", "shadow_spec": {"symbol": "XAUUSD",
                                               "family": "session_range_breakout"}},
             "b.EURUSD.session_range_breakout":
             {"sym": "EURUSD", "shadow_spec": {"symbol": "EURUSD",
                                               "family": "session_range_breakout"}}}
    (tmp_path / "canon.json").write_text(json.dumps({"survivors": certs}), "utf-8")

    def setup(entity: str | None, e8: list[str] | None) -> dict:
        if entity is not None:
            C.ACCOUNT.write_text(json.dumps({"venue": entity}), "utf-8")
        if e8 is not None:
            C.E8_BOOK.write_text(json.dumps({"sleeves": [{"key": k} for k in e8]}), "utf-8")
        doc = C.build(NOW)
        return {r["certificate"]: r for r in doc["certificates"]} | {"_doc": doc}
    setup.scope = scope  # type: ignore[attr-defined]
    return setup


def test_in_scope_fusion_use_is_ok(census):
    rows = census(census.scope["entity"].upper().replace("LIMITED", "Ltd"), [])
    assert rows["a.XAUUSD.session_range_breakout"]["verdict"] == C.OK
    assert rows["a.XAUUSD.session_range_breakout"]["venues"] == [
        {"venue": "fusion", "use": "trading_with_fusion", "basis": C.OK}]


def test_e8_use_is_unmeasured_and_an_unreadable_e8_book_is_too(census):
    rows = census(census.scope["entity"], ["b.EURUSD.session_range_breakout"])
    assert rows["a.XAUUSD.session_range_breakout"]["verdict"] == C.OK
    b = rows["b.EURUSD.session_range_breakout"]
    assert b["verdict"] == C.TERMS_UNMEASURED
    e8 = next(v for v in b["venues"] if v["venue"] == "e8")
    assert e8["basis"] == C.TERMS_UNMEASURED
    venues = {v["venue"]: v for v in rows["_doc"]["venues"]}
    assert venues["e8"]["basis"] == venues["ftmo"]["basis"] == C.TERMS_UNMEASURED
    assert venues["ftmo"]["missed_growth"]["delta_elogw"] == "UNMEASURED"
    C.E8_BOOK.unlink()
    rows = C.build(NOW)["certificates"]
    assert all(r["verdict"] == C.TERMS_UNMEASURED for r in rows)


def test_entity_mismatch_and_unreadable_entity_are_unmeasured(census):
    rows = census("Fusion Markets Pty Ltd", [])
    a = rows["a.XAUUSD.session_range_breakout"]
    assert a["verdict"] == C.TERMS_UNMEASURED
    assert "entity mismatch" in a["inputs"][0]["why"]
    C.ACCOUNT.unlink()
    assert all(r["verdict"] == C.TERMS_UNMEASURED for r in C.build(NOW)["certificates"])


def test_publication_off_the_box_is_its_own_unmeasured_line_never_ok(census):
    doc = census(census.scope["entity"], [])["_doc"]
    pub = doc["publication"]
    assert pub["basis"] == C.TERMS_UNMEASURED and pub["use"] == "publish_raw_fusion_quotes_off_box"
    assert any(m.get("use") == "publish_raw_fusion_quotes_off_box" for m in doc["missed_growth"])
    assert doc["summary"]["ok"] == 2                  # publication never folds into a verdict


def test_the_broker_row_carries_the_auditors_scope():
    row = tf.SOURCE_POLICY["mt5_broker"]
    assert row["scope"] == {"venue": "fusion",
                            "entity": "Gleneagle Asset Management Limited trading as Fusion "
                                      "Markets", "use": "trading_with_fusion"}
    assert set(row["other_venues"]) == {"e8", "ftmo"}
    assert row["entity_match"].startswith("UNMEASURED")
