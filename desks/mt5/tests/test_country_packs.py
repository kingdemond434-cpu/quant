"""Country open-data packs as world dataset hunter doors (Indonesia, Singapore, Saudi Arabia, Japan,
China). No network: every request goes through an injected fetcher.

Fixtures (desks/mt5/tests/fixtures/country_packs/):
  mof_feio.csv   the MoF intervention file's layout as read 2026-11-03 (nine columns, cp932,
                 blank year/month on continuation rows, quarterly 期計 rows); the 2022 and 2024
                 operations are the published figures, the zero quarters of 2025-2026 SYNTHETIC
  others         shapes declared from each publisher's documentation, values SYNTHETIC; their
                 live shape is UNMEASURED (IDEAS_ONLY or NEEDS_KEY, so never fetched here)
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import terms_fence as tf  # noqa: E402
from research import universe_policy as up  # noqa: E402
from research import world_dataset_hunter as W  # noqa: E402

FIX = DESK / "tests" / "fixtures" / "country_packs"
NOW = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)
UNIVERSE_ROWS = {
    "USDJPY": {"asset_class": "Forex", "currency_profit": "JPY"},
    "EURJPY": {"asset_class": "Forex", "currency_profit": "JPY"},
    "JPN225": {"asset_class": "Indices", "currency_profit": "JPY"},
    "USDIDR": {"asset_class": "Forex Exotics", "currency_profit": "IDR"},
    "USDSGD": {"asset_class": "Forex Exotics", "currency_profit": "SGD"},
    "XBRUSD": {"asset_class": "Energy", "currency_profit": "USD"},
    "XTIUSD": {"asset_class": "Energy", "currency_profit": "USD"},
    "3M": {"asset_class": "Equities", "currency_profit": "USD"},
}


@pytest.fixture()
def box(tmp_path, monkeypatch):
    store = tmp_path / "world_datasets"
    uni = tmp_path / "universe.json"
    uni.write_text(json.dumps(UNIVERSE_ROWS), "utf-8")
    reg = tmp_path / "data_registry.json"
    reg.write_text(json.dumps({"schema_version": 1, "datasets": {}}), "utf-8")
    for name, val in (("STORE", store), ("OBS", store / "obs"),
                      ("CATALOG", store / "catalog.json"), ("EXPOSURE", store / "exposure.json"),
                      ("KEYS", store / "keys.json"), ("HISTORY", store / "hunt_history.jsonl"),
                      ("REGISTRY", reg), ("UNIVERSE", uni),
                      ("REPORT", tmp_path / "DATASET_HUNT.json"), ("DESK", tmp_path),
                      ("MIN_REQUEST_GAP_S", 0.0)):
        monkeypatch.setattr(W, name, val)
    monkeypatch.setattr(up, "UNIVERSE", uni)
    monkeypatch.setattr(W, "_free_disk_ok", lambda: (True, {"free_gb": 99.0}))
    # only the pack doors: the other direct doors and the legacy probes are not under test
    monkeypatch.setattr(W, "direct_sources", lambda now=None: W.country_pack_doors())
    monkeypatch.setattr(W, "LEGACY_PROBES", {})
    for k in ("MAS_API_KEY", "BPS_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    up._registry.cache_clear()
    for fn in (W._universe_at, W._exposure_at, W._keys_at, W._frame_at):
        fn.cache_clear()
    yield tmp_path
    up._registry.cache_clear()
    W._universe_at.cache_clear()


def _fetcher(routes: dict[str, bytes]):
    """First route whose key is a substring of the URL wins; anything else is a blocked host.
    Every call is recorded, with the headers it carried."""
    calls: list[tuple[str, dict[str, str] | None]] = []

    def fetch(url: str, timeout: float, headers: dict[str, str] | None = None) -> bytes:
        calls.append((url, headers))
        for frag, payload in routes.items():
            if frag in url:
                return payload
        raise W.FetchError("blocked_proxy", url)

    fetch.calls = calls  # type: ignore[attr-defined]
    return fetch


def _mof() -> bytes:
    return (FIX / "mof_feio.csv").read_bytes()


def _pack(rep: dict, name: str) -> dict:
    return rep["country_packs"]["packs"][name]


def _door(rep: dict, pack: str, ds: str) -> dict:
    return next(d for d in _pack(rep, pack)["doors"] if d["dataset"] == ds)


# ------------------------------------------------------------------- MoF intervention (JP) ----
def test_mof_parser_signs_carries_year_and_month_and_counts_zero_quarters():
    df = W._mof_feio_frame(_mof())
    ops = df[df["series_code"] == "yen_bought_100m_jpy"].set_index("period")["value"]
    assert ops["2022-09-22"] == 28382 and ops["2022-10-24"] == 7296     # year/month carried
    assert ops["2024-05-01"] == 38700                                   # month on its own row
    assert len(ops) == 7 and (ops > 0).all()                            # yen BOUGHT is +
    q = df[df["series_code"] == "qtr_net_yen_bought_100m_jpy"].set_index("period")["value"]
    assert q["2022-Q4"] == 56202 + 7296 and q["2024-Q2"] == 59185 + 38700
    assert q["2023-Q1"] == 0.0 and len(q) == 22                         # every listed quarter
    yen_sold = ("年,月,日,Year,Month,Day,金額(amount),売買通貨,Currency pairs\n"
                "平成15年,1月,15日,2003,Jan,15,\"1,000\",日本円売り・米ドル買い,"
                "the Japanese yen (sold) the US dollar (bought)\n").encode("cp932")
    one = W._mof_feio_frame(yen_sold)                                   # SYNTHETIC row
    assert one[one["series_code"] == "yen_bought_100m_jpy"]["value"].iloc[0] == -1000


def test_mof_values_are_stamped_at_the_quarterly_release_not_the_operation_date():
    df = W._mof_feio_frame(_mof())
    row = df[(df["series_code"] == "yen_bought_100m_jpy") & (df["period"] == "2024-04-29")]
    at = datetime.fromisoformat(row["available_utc"].iloc[0])
    assert at == datetime(2024, 6, 30, 10, tzinfo=UTC) + timedelta(days=W.MOF_FEIO_RELEASE_LAG_D)
    # the stated release of the latest quarter (Apr-Jun 2026 on 2026-08-07) is never after it
    assert W.mof_feio_release(2026, 2) >= datetime(2026, 8, 7, 10, tzinfo=UTC)


def test_mof_door_is_live_lands_pit_rows_and_reaches_only_the_named_instruments(box):
    fetch = _fetcher({"foreign_exchange_intervention_operations.csv": _mof()})
    rep = W.run(budget_s=60, fetch=fetch, now=NOW)
    assert tf.terms_verdict("jp_mof_feio") == "confirmed"
    assert tf.input_source(W._MOF_FEIO_CSV) is None
    door = _door(rep, "japan", "MOF_FEIO")
    assert door["state"] == "GREEN" and door["policy_row"] == "jp_mof_feio"
    frame = pd.read_parquet(W.dataset_path("PACK_JP", "MOF_FEIO"))
    r = frame[(frame["series_code"] == "yen_bought_100m_jpy") & (frame["period"] == "2022-10-21")]
    assert r["available_time"].iloc[0] == pd.Timestamp(W.mof_feio_release(2022, 4))
    meta = json.loads(W.meta_path("PACK_JP", "MOF_FEIO").read_text("utf-8"))
    qs = meta["series"]["qtr_net_yen_bought_100m_jpy"]
    assert qs["quality"] == "PASS" and qs["instruments"] == ["JPN225", "USDJPY"]  # pinned
    exposure = json.loads(W.EXPOSURE.read_text("utf-8"))["symbols"]
    assert qs["key"] in exposure["USDJPY"] and "EURJPY" not in exposure
    # the research door serves it keyed on the release instant (world_macro_state reads this)
    idx = pd.date_range("2022-01-01", "2026-11-01", freq="D", tz="UTC")
    s = W.world_series_for("USDJPY", idx, now=NOW)[f"world_{qs['key']}"]
    # Q3 2022 is released 2022-11-14 10:00 UTC: the day's 00:00 bar still sees Q2 (0)
    assert s.loc["2022-11-14"] == 0 and s.loc["2022-11-15"] == 28382
    assert s.loc["2023-02-14"] == 28382                              # Q4 2022 not yet public
    assert s.loc["2023-02-15"] == 56202 + 7296                       # public after its release
    pk = _pack(rep, "japan")
    assert pk["instruments_mapped"] == ["JPN225", "USDJPY"] and pk["unmapped"] == []
    assert qs["key"] in pk["series_to_research"]


# ------------------------------------------------------------------------------ liveness ----
def test_a_door_that_lands_nothing_three_runs_running_turns_red_and_names_itself(box):
    empty = _fetcher({"foreign_exchange_intervention_operations.csv": b"Year,Month\n"})
    states = []
    for day in range(3):
        rep = W.run(budget_s=60, fetch=empty, now=NOW + timedelta(days=day, hours=1))
        states.append(_door(rep, "japan", "MOF_FEIO")["state"])
    assert states == ["AMBER", "AMBER", "RED"]                      # > 2 consecutive empties
    assert _pack(rep, "japan")["verdict"] == "RED"
    assert rep["status"].startswith("RED") and "japan/MOF_FEIO" in rep["status"]
    # the desk's existing board reads the organ's own last reading: a fail word, not GREEN
    from research import health_board as hb
    verdict, why = hb.judge({"state": "LIVE", "kind": "leg",
                             "last_reading": hb._last_reading(W.REPORT)},
                            {"kind": "LEG_DONE", "at": NOW.isoformat()})
    assert verdict == hb.AMBER and "RED" in why
    ok = _fetcher({"foreign_exchange_intervention_operations.csv": _mof()})
    rep = W.run(budget_s=60, fetch=ok, now=NOW + timedelta(days=4))
    assert _door(rep, "japan", "MOF_FEIO")["state"] == "GREEN" and rep["status"] == "OK"


# ---------------------------------------------------------------- IDEAS_ONLY and NEEDS_KEY ----
def test_ideas_only_doors_are_never_requested_and_carry_a_missed_growth_line(box):
    fetch = _fetcher({})
    rep = W.run(budget_s=60, fetch=fetch, now=NOW)
    asked = " ".join(u for u, _ in fetch.calls)
    for host in ("bi.go.id", "sama.gov.sa", "stat-search.boj.or.jp", "webapi.bps.go.id"):
        assert host not in asked, host
    for pack, ds, row in (("indonesia", "BI_JISDOR", "id_bank_indonesia"),
                          ("indonesia", "BPS_INDICATORS", "id_bps_webapi"),
                          ("japan", "BOJ_FM01_CALL", "jp_boj_stat_search"),
                          ("saudi_arabia", "saibor_daily", "sa_sama")):
        d = _door(rep, pack, ds)
        assert d["state"] == "IDEAS_ONLY" and d["policy_row"] == row, (pack, ds)
        mg = d["missed_growth"]
        assert mg["delta_elogw"] == "UNMEASURED" and mg["kind"] == "ideas_only_refusal"
    assert _pack(rep, "indonesia")["verdict"] == "HELD"
    assert _door(rep, "indonesia", "BPS_INDICATORS")["key"] == "NEEDS_KEY:BPS_API_KEY"
    cat = json.loads(W.CATALOG.read_text("utf-8"))["datasets"]
    assert cat["PACK_ID/BI_JISDOR"]["pack_state"] == "IDEAS_ONLY"
    assert int(cat["PACK_ID/BI_JISDOR"].get("fail_count") or 0) == 0   # a hold is not a failure


def test_mas_doors_read_needs_key_by_name_and_send_the_key_only_in_a_header(box, monkeypatch):
    rep = W.run(budget_s=60, fetch=_fetcher({}), now=NOW)
    d = _door(rep, "singapore", "MAS_DOMESTIC_RATES_DAILY")
    assert d["state"] == "NEEDS_KEY" and d["key"] == "NEEDS_KEY:MAS_API_KEY"
    assert _pack(rep, "singapore")["verdict"] == "HELD"
    secret = "fixture-not-a-real-key-1234"  # noqa: S105 -- a fixture value
    monkeypatch.setenv("MAS_API_KEY", secret)
    payload = (FIX / "mas_domestic_rates.json").read_bytes()
    fetch = _fetcher({"domestic_interest_rates_daily": payload})
    rep = W.run(budget_s=60, fetch=fetch, now=NOW + timedelta(days=1, hours=1))
    mas = [(u, h) for u, h in fetch.calls if "domestic_interest_rates_daily" in u]
    assert mas and all(secret not in u and h == {"KeyId": secret} for u, h in mas)
    blob = W.CATALOG.read_text("utf-8") + W.REPORT.read_text("utf-8")
    assert secret not in blob
    meta = json.loads(W.meta_path("PACK_SG", "MAS_DOMESTIC_RATES_DAILY").read_text("utf-8"))
    assert {"sora", "sora_index", "comp_sora_3m"} <= set(meta["series"])
    assert "USDSGD" in meta["series"]["sora"]["instruments"]


# --------------------------------------------------------------------- parsers on fixtures ----
def test_records_parser_reads_mas_sama_and_bps_shapes():
    mas = W._records_frame((FIX / "mas_domestic_rates.json").read_bytes(),
                           {"date_fields": ["end_of_day"], "freq": "daily"})
    sora = mas[mas["series_code"] == "sora"]
    assert list(sora["period"]) == ["2026-10-28", "2026-10-29"]          # null is absent
    assert "preliminary" not in set(mas["series_code"])                  # text is never a number
    sama = W._records_frame((FIX / "sama_saibor.json").read_bytes(), {"freq": "daily"})
    assert set(sama["series_code"]) == {"saibor_3m", "saibor_6m"}
    bps = W._records_frame((FIX / "bps_indicators.json").read_bytes(),
                           {"date_fields": ["periode"], "code_field": "title",
                            "value_fields": ["value"], "freq": "monthly"})
    assert list(bps["period"]) == ["2026-09", "2026-10"] and bps["value"].tolist() == [2.31, 2.12]


def test_boj_and_bank_indonesia_parsers():
    boj = W._boj_api_frame((FIX / "boj_fm01.json").read_bytes())
    assert boj["series_code"].unique().tolist() == ["STRDCLUCON"]
    assert boj["period"].tolist() == ["2026-10-28", "2026-10-30"]       # null skipped
    bi = W._bi_table_frame((FIX / "bi_jisdor.html").read_bytes(),
                           {"series_code": "jisdor_idr_per_usd"})
    assert bi.set_index("period")["value"].to_dict() == {
        "2026-10-31": 16612.0, "2026-10-30": 16598.0, "2026-10-29": 16640.0}


# --------------------------------------------------------------- China, Saudi, the register ----
def test_china_pack_reports_the_existing_organ_held_on_terms_and_builds_no_door(box):
    rep = W.run(budget_s=30, fetch=_fetcher({}), now=NOW)
    cn = _pack(rep, "china")
    assert cn["doors"] == [] and cn["verdict"] == "HELD" and "free_stack_cnx" in cn["organ"]
    for k in ("cnx_shfe", "cnx_dce", "cnx_czce"):
        assert cn["policy"][k]["status"] == tf.IDEAS_ONLY
        assert cn["policy"][k]["missed_growth"]["delta_elogw"] == "UNMEASURED"
    assert not any("shfe" in d["url"] or "dce.com" in d["url"] for d in W.country_pack_doors())


def test_saudi_doors_come_from_the_data_plane_catalogue_and_usdsar_is_unmapped(box):
    from research.countries.sa.data_plane import SamaLane
    urls = {r.url for r in SamaLane.CATALOGUE if r.url}
    doors = [d for d in W.country_pack_doors() if d["pack"] == "saudi_arabia"]
    assert doors and {d["url"] for d in doors} <= urls
    rep = W.run(budget_s=30, fetch=_fetcher({}), now=NOW)
    sa = _pack(rep, "saudi_arabia")
    assert sa["unmapped"] == ["USDSAR"] and sa["instruments_mapped"] == ["XBRUSD", "XTIUSD"]


def test_every_pack_row_is_in_the_one_register_with_its_clause_or_unread_reason():
    for p in W.COUNTRY_PACKS.values():
        for k in p["policy_rows"]:
            row = tf.SOURCE_POLICY[k]
            t = row["terms"]
            assert t.get("clauses") or t.get("unread"), k
    live = {"jp_mof_feio", "sg_mas_api"}
    for k in live:
        assert tf.terms_verdict(k) == "confirmed", k
    for k in ("jp_boj_stat_search", "jp_jquants", "id_bank_indonesia", "id_bps_webapi",
              "sa_sama"):
        assert tf.SOURCE_POLICY[k]["status"] == tf.IDEAS_ONLY, k
        assert tf.SOURCE_POLICY[k]["terms"]["checked_at"] == "2026-11-03", k
    assert "商用" in tf.SOURCE_POLICY["jp_jquants"]["terms"]["clauses"]["art8_2"]
    assert tf.input_source("https://api.jquants.com/v1/prices/daily_quotes") == "jp_jquants"
    assert tf.input_source("https://www.bi.go.id/en/statistik/") == "id_bank_indonesia"
    assert tf.terms_state("id_bank_indonesia") == tf.UNREAD
