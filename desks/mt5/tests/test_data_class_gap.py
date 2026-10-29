"""The tier-1 data-class gap list, its three producer doors, and the terms-basis census.

No network. Fixtures (tests/fixtures/data_class_gap) copy the shapes of the publishers' live
responses read on 2026-10-29 (FiscalData auctions_query, CPC ONI and NAO tables), values trimmed
and partly synthetic. The EIA fixture follows the v2 documentation (response.data[] rows of
period/value, values as strings): the live EIA body was not read from the build container (no key,
no network), so its exact field set is UNMEASURED until the box fetches it.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import terms_fence as tf  # noqa: E402
from research import data_class_gap as G  # noqa: E402
from research import terms_basis_census as C  # noqa: E402
from research import world_dataset_hunter as W  # noqa: E402

FIX = DESK / "tests" / "fixtures" / "data_class_gap"
NOW = datetime(2026, 10, 29, 12, 0, tzinfo=UTC)


def _fx(name: str) -> bytes:
    return (FIX / name).read_bytes()


# ------------------------------------------------------------------------ the three doors ----
def test_treasury_auctions_parse_results_only_and_skip_cash_management_bills():
    df = W.frame_from_payload(_fx("treasury_auctions.json"), "treasury_auctions", {})
    codes = set(df["series_code"])
    assert "note_10y_bid_to_cover" in codes and "bill_13w_stop_yield" in codes
    assert "tips_5y_bid_to_cover" in codes
    # the announced 5-year (results "null") yields nothing at all, not even its size
    assert not any(c.startswith("note_5y") for c in codes)
    # the 42-day cash-management bill is off the calendar
    assert not any("42" in c for c in codes)
    row = df[(df.series_code == "note_10y_indirect_share")].iloc[0]
    assert row["period"] == "2026-10-08"
    assert row["value"] == pytest.approx(27230 / 38900)
    btc = df[(df.series_code == "note_10y_bid_to_cover")]["value"].iloc[0]
    assert btc == pytest.approx(2.54)


def test_cpc_oni_keys_each_season_on_its_last_month_and_drops_missing():
    df = W.frame_from_payload(_fx("oni.ascii.txt"), "cpc_ascii", {"series_code": "oni"})
    anom = dict(zip(df[df.series_code == "oni_anom"]["period"],
                    df[df.series_code == "oni_anom"]["value"], strict=True))
    assert anom["1950-02"] == pytest.approx(-1.32)          # DJF 1950 ends in February
    assert anom["2026-01"] == pytest.approx(-0.55)          # NDJ 2025 ends in January 2026
    assert anom["2026-09"] == pytest.approx(2.16)           # JAS ends in September
    assert "2026-10" not in anom                             # -99.90 is absent, never a value
    nao = W.frame_from_payload(_fx("nao.monthly.ascii"), "cpc_ascii", {"series_code": "nao"})
    assert list(nao["period"])[-1] == "2026-09" and len(nao) == 4


def test_eia_v2_parses_strings_and_refuses_an_error_document():
    df = W.frame_from_payload(_fx("eia_wcestus1.json"), "eia_v2",
                              {"series_code": "crude_stocks_ex_spr"})
    assert list(df["value"]) == [421350.0, 423100.0]        # the null week is absent
    with pytest.raises(W.FetchError):
        W.frame_from_payload(b'{"error": "API_KEY_MISSING"}', "eia_v2", {"series_code": "x"})


def test_gap_doors_declare_their_key_by_name_and_never_carry_one():
    doors = W.gap_doors()
    assert {d["provider"] for d in doors} == {"TREASURY", "NOAA_CPC", "EIA"}
    for d in doors:
        assert d in W.direct_sources(NOW)
        if d["provider"] == "EIA":
            assert d["key_env"] == "EIA_API_KEY" and "{api_key}" in d["url"]
        assert not re.search(r"api_key=[A-Za-z0-9]{8,}", d["url"])


def test_each_door_stands_on_a_quoted_row_of_the_one_register(monkeypatch):
    rows = {"TREASURY": "us_treasury_fiscaldata", "NOAA_CPC": "noaa_cpc", "EIA": "eia_api"}
    monkeypatch.delenv("EIA_API_KEY", raising=False)
    for d in W.gap_doors():
        key = tf.source_of_url(d["url"].replace("{api_key}", "x"))
        assert key == rows[d["provider"]]
        assert tf.terms_state(key) == "READ"
        assert tf.input_source(d["url"]) in (None, "eia_api")
    assert tf.live_input_status("us_treasury_fiscaldata") == tf.API_PERMITTED
    assert tf.live_input_status("noaa_cpc") == tf.PUBLIC_PAGE
    assert tf.live_input_status("eia_api") == tf.NEEDS_KEY          # named, never a zero
    monkeypatch.setenv("EIA_API_KEY", "k" * 20)
    assert tf.live_input_status("eia_api") == tf.API_PERMITTED


@pytest.fixture()
def store(tmp_path, monkeypatch):
    s = tmp_path / "world_datasets"
    monkeypatch.setattr(W, "STORE", s)
    monkeypatch.setattr(W, "OBS", s / "obs")
    monkeypatch.setattr(W, "MIN_REQUEST_GAP_S", 0.0)
    W._universe_at.cache_clear()
    return tmp_path


def _fetcher(seen: list[str]):
    def fetch(url: str, timeout: float) -> bytes:
        seen.append(url)
        if "auctions_query" in url:
            return _fx("treasury_auctions.json")
        if "cpc.ncep.noaa.gov" in url:
            return _fx("oni.ascii.txt") if "oni" in url else _fx("nao.monthly.ascii")
        if "api.eia.gov" in url:
            return _fx("eia_wcestus1.json")
        raise W.FetchError("not_found_404", url)
    return fetch


def test_a_pass_lands_the_doors_pit_stamped_and_eia_waits_for_its_key(store, monkeypatch):
    monkeypatch.delenv("EIA_API_KEY", raising=False)
    monkeypatch.setattr(W, "direct_sources", lambda now=None: W.gap_doors())
    seen: list[str] = []
    client = W.Client(_fetcher(seen), deadline=1e18)
    cat = W._blank_catalog()
    stats: Counter[str] = Counter()
    W.fetch_direct(client, cat, now=NOW, until=1e18, stats=stats, qstats=Counter(),
                   by_provider={p: Counter() for p in ("TREASURY", "NOAA_CPC", "EIA")})
    ds = cat["datasets"]
    assert ds["TREASURY/auctions"]["lifecycle"] in ("INGESTED", "QUALITY-PASSED")
    assert ds["NOAA_CPC/ONI"]["lifecycle"] in ("INGESTED", "QUALITY-PASSED")
    eia = [v for k, v in ds.items() if k.startswith("EIA/")]
    assert eia and all(v["fail_reason"] == "needs_key" for v in eia)
    assert stats["direct:needs_key"] == len(eia)
    assert not any("api.eia.gov" in u for u in seen)               # nothing sent without a key
    # PIT: an auction result is never keyed before the auction day closes
    import pandas as pd
    f = pd.read_parquet(W.dataset_path("TREASURY", "auctions"))
    r = f[f.series_code == "note_10y_bid_to_cover"].iloc[0]
    assert r["available_time"] >= pd.Timestamp("2026-10-09", tz="UTC")


def test_with_its_key_eia_lands_late_never_early_and_the_key_is_never_written(store,
                                                                                monkeypatch):
    secret = "SEKRETkey0123456789"  # noqa: S105 -- a fixture value, asserted never written
    monkeypatch.setenv("EIA_API_KEY", secret)
    monkeypatch.setattr(W, "direct_sources",
                        lambda now=None: [d for d in W.gap_doors() if d["provider"] == "EIA"])
    seen: list[str] = []
    cat = W._blank_catalog()
    W.fetch_direct(W.Client(_fetcher(seen), deadline=1e18), cat, now=NOW, until=1e18,
                   stats=Counter(), qstats=Counter(), by_provider={"EIA": Counter()})
    assert any(secret in u for u in seen)                           # the request carried it
    assert secret not in json.dumps(cat)
    for p in (store / "world_datasets").rglob("*"):
        if p.is_file():
            assert secret.encode() not in p.read_bytes()
    import pandas as pd
    f = pd.read_parquet(W.dataset_path("EIA", "PET.WCESTUS1.W"))
    r = f[f.period == "2026-10-17"].iloc[0]
    # week ending Fri 17 Oct, published Wed 22 Oct 10:30 ET: keyed no earlier than Fri 24 Oct
    assert r["available_time"] >= pd.Timestamp("2026-10-24", tz="UTC")


# ----------------------------------------------------------------------- the gap list ----
def _tree(root: Path) -> None:
    (root / "desks/mt5/research/countries/xx").mkdir(parents=True)
    (root / "desks/mt5/research/fetch_thing.py").write_text(
        'URL = ("https://api.example-stats.org/v1/"\n       "series/flows")\n', "utf-8")
    (root / "desks/mt5/research/countries/xx/pack.py").write_text(
        'URL = "https://www.weather-office.example.org/"\n', "utf-8")


CLASSES = (
    {"id": "flows", "name": "flows", "weight": 3, "mt5": ["EURUSD"], "tier1": "t",
     "producers": ["research/fetch_thing.py"], "catalogue_terms": r"flow",
     "candidates": [G._c("ex_flows", "example flows", "https://api.example-stats.org/v1/series",
                         "XX", "en"),
                    G._c("ex_other", "example other", "https://api.example-stats.org/v2/other",
                         "XX", "en")]},
    {"id": "weather", "name": "weather", "weight": 2, "mt5": ["XNGUSD"], "tier1": "t",
     "producers": [], "catalogue_terms": r"weather",
     "candidates": [G._c("ex_weather", "example weather",
                         "https://www.weather-office.example.org/data/", "XX", "en")]},
    {"id": "auctions", "name": "auctions", "weight": 2, "mt5": ["UST10Y"], "tier1": "t",
     "producers": [], "catalogue_terms": r"auction",
     "candidates": [G._c("fiscal", "fiscaldata auctions",
                         "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/"
                         "accounting/od/auctions_query", "US", "en")]},
)


@pytest.fixture()
def gap(tmp_path, monkeypatch):
    _tree(tmp_path)
    monkeypatch.setattr(G, "HOURLY", tmp_path / "hourly_cycle.py")
    monkeypatch.setattr(G, "RUNTIME_STATE", tmp_path / "runtime_state.json")
    monkeypatch.setattr(G, "WORLD_CATALOG", tmp_path / "catalog.json")
    monkeypatch.setattr(G, "REGISTRY", tmp_path / "data_registry.json")
    monkeypatch.setattr(G, "FREE_STACK", tmp_path / "free_stack_sources.json")
    return tmp_path


def test_a_fetcher_on_the_data_path_is_ingestion_and_a_catalogue_mention_is_not(gap):
    doc = G.build(NOW, root=gap, classes=CLASSES)
    rows = {r["id"]: r for r in doc["classes"]}
    flows = {c["id"]: c for c in rows["flows"]["candidates"]}
    assert flows["ex_flows"]["ingested"] is True                    # joined literal, same path
    assert flows["ex_flows"]["fetched_by"] == ["desks/mt5/research/fetch_thing.py"]
    assert flows["ex_other"]["ingested"] is False                   # same host, other dataset
    assert flows["ex_other"]["evidence"] == "HOST_NAMED_ONLY"
    w = rows["weather"]
    assert w["candidates"][0]["ingested"] is False                  # a country pack names it
    assert w["coverage"] == "CATALOGUED"
    assert rows["auctions"]["coverage"] == "NONE"
    # the flows producer exists but runs on no clock: UNWIRED is a defect, not cover
    assert rows["flows"]["producers"][0]["clock"] == "UNWIRED"
    assert rows["flows"]["coverage"] == "PRODUCER"


def test_terms_come_from_the_one_register_and_absence_is_unmeasured(gap):
    doc = G.build(NOW, root=gap, classes=CLASSES)
    rows = {r["id"]: r for r in doc["classes"]}
    assert rows["auctions"]["candidates"][0]["terms"]["live_basis"] == "OK"
    assert rows["auctions"]["candidates"][0]["terms"]["policy_row"] == "us_treasury_fiscaldata"
    t = rows["weather"]["candidates"][0]["terms"]
    assert t["live_basis"] == G.TERMS_UNMEASURED and t["policy_row"] is None
    assert any("ex_weather terms" in u for u in doc["unmeasured"])
    assert any("catalog.json absent" in u for u in doc["unmeasured"])


def test_scores_rank_missing_heavy_classes_first_and_never_zero_an_unmeasured_one(gap):
    doc = G.build(NOW, root=gap, classes=CLASSES)
    scores = [r["gap_score"] for r in doc["classes"]]
    assert scores == sorted(scores, reverse=True)
    assert [r["rank"] for r in doc["classes"]] == [1, 2, 3]
    for r in doc["classes"]:
        assert r["gap_score"] > 0                                    # nothing here is covered
    md = G.render_md(doc, top=3)
    assert "| rank | class |" in md and "UNMEASURED" in md


def test_a_wired_producer_with_no_readable_artifact_is_wired_not_fresh(gap, monkeypatch):
    (gap / "hourly_cycle.py").write_text(
        '_producer("fetch_thing", "research/fetch_thing.py")\n', "utf-8")
    (gap / "runtime_state.json").write_text(json.dumps({"organs": [
        {"organ": "leg:fetch_thing", "state": "LIVE",
         "artifact": "desks/mt5/reports/THING.json"}]}), "utf-8")
    doc = G.build(NOW, root=gap, classes=CLASSES[:1])
    r = doc["classes"][0]
    assert r["producers"][0]["clock"] == "hourly_cycle:fetch_thing"
    assert r["coverage"] == "WIRED"
    assert r["producers"][0]["freshness"]["age_h"] == G.UNMEASURED
    (gap / "desks/mt5/reports").mkdir(parents=True)
    (gap / "desks/mt5/reports/THING.json").write_text(
        json.dumps({"generated_at": "2026-10-29T10:00:00+00:00"}), "utf-8")
    doc = G.build(NOW, root=gap, classes=CLASSES[:1])
    assert doc["classes"][0]["coverage"] == "WIRED_FRESH"
    assert doc["classes"][0]["producers"][0]["freshness"]["age_h"] == 2.0


def test_the_real_class_table_is_mt5_pure_and_complete():
    ids = [c["id"] for c in G.CLASSES]
    assert len(ids) == len(set(ids)) >= 25
    for want in ("options_implied_vol", "fund_flows", "sovereign_auctions", "weather_climate",
                 "energy_inventories", "power_gas_grid", "shipping_ais_ports", "positioning",
                 "futures_curves", "physical_metals", "trade_hs_customs", "payments_mobility"):
        assert want in ids
    banned = ("binance", "bybit", "okx", "deribit", "coinbase", "kraken", "upbit", "bithumb",
              "hyperliquid", "coinmetrics", "bitfinex")
    for c in G.CLASSES:
        for cand in c["candidates"]:
            assert not any(b in cand["url"].lower() for b in banned), cand["id"]


def test_both_legs_are_wired_with_every_birth_row():
    src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    from libs.research.layers import LEG_LAYER
    from research import hourly_cycle as H
    for leg, mod in (("data_class_gap", "research/data_class_gap.py"),
                     ("terms_basis_census", "research/terms_basis_census.py")):
        assert re.search(rf'_costed\("{leg}", lambda: _producer\("{leg}",\s*"{mod}"', src)
        assert re.search(rf'"{leg}": (dcg|tbc)', src)
        assert leg in H.CORE_LEGS and leg in H.LEG_DEPARTMENT
        assert leg in H.LEG_BUDGET_SEC and leg in LEG_LAYER


# ------------------------------------------------------------------ terms-basis census ----
@pytest.fixture()
def canon(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "CANON", tmp_path / "canon.json")
    monkeypatch.setattr(C, "SURVIVORS", tmp_path / "survivors.json")
    monkeypatch.setattr(C, "WORLD_KEYS", tmp_path / "keys.json")

    def write(survivors: dict, keys: dict | None = None) -> None:
        (tmp_path / "canon.json").write_text(json.dumps({"survivors": survivors}), "utf-8")
        if keys is not None:
            (tmp_path / "keys.json").write_text(json.dumps(keys), "utf-8")
    return write


def _cert(sym: str, family: str, **params) -> dict:
    return {"sym": sym, "shadow_spec": {"symbol": sym, "family": family, "params": params}}


def test_no_certificates_is_unmeasured_never_zero(canon):
    doc = C.build(NOW)
    assert doc["summary"]["certificates"] == C.UNMEASURED
    assert doc["summary"]["ok"] == C.UNMEASURED


def test_every_input_resolves_to_a_word_and_none_unread_is_ok(canon):
    canon({"a.XAUUSD.session_range_breakout": _cert("XAUUSD", "session_range_breakout"),
           "b.EURUSD.world_macro_state": _cert("EURUSD", "world_macro_state",
                                               series_key="wabc"),
           "c.USDJPY.world_macro_state": _cert("USDJPY", "world_macro_state",
                                               series_key="wmissing"),
           "d.US500.exogenous_conditioner": _cert("US500", "exogenous_conditioner",
                                                  source="mql5"),
           "e.AUDUSD.cot_positioning": _cert("AUDUSD", "cot_positioning"),
           "f.GBPUSD.world_macro_state": _cert("GBPUSD", "world_macro_state")},
          {"wabc": ["TREASURY", "auctions", "note_10y_bid_to_cover"]})
    doc = C.build(NOW)
    rows = {r["certificate"]: r for r in doc["certificates"]}
    # the broker feed has no quoted row: every certificate is at best TERMS_UNMEASURED
    assert all(r["verdict"] != C.OK for r in rows.values())
    assert rows["a.XAUUSD.session_range_breakout"]["third_party_verdict"] == "BROKER_ONLY"
    assert rows["b.EURUSD.world_macro_state"]["third_party_verdict"] == C.OK
    assert rows["c.USDJPY.world_macro_state"]["third_party_verdict"] == C.TERMS_UNMEASURED
    assert rows["d.US500.exogenous_conditioner"]["verdict"] == C.REFUSED
    e = rows["e.AUDUSD.cot_positioning"]["inputs"]
    assert any(i["kind"] == "family_default" for i in e)
    f = rows["f.GBPUSD.world_macro_state"]["inputs"]
    assert f[-1]["kind"] == "unresolved" and f[-1]["basis"] == C.TERMS_UNMEASURED
    for ln in doc["missed_growth"]:
        assert ln["delta_elogw"] == "UNMEASURED" and ln["cause"]
    broker = next(x for x in doc["missed_growth"] if x["input"] == "mt5_broker")
    assert broker["certificates"] == 6


def test_a_quoted_broker_row_would_clear_the_broker_input(canon, monkeypatch):
    canon({"a.XAUUSD.session_range_breakout": _cert("XAUUSD", "session_range_breakout")})
    monkeypatch.setitem(tf.SOURCE_POLICY, "mt5_broker", {
        "hosts": (), "url_level": False, "status": tf.API_PERMITTED, "sources": ("mt5_broker",),
        "why": "fixture", "terms": {"url": "https://broker.example/terms",
                                    "clauses": {"x": "fixture clause"}}})
    doc = C.build(NOW)
    assert doc["certificates"][0]["verdict"] == C.OK


def test_census_without_world_keys_names_the_gap(canon):
    canon({"b.EURUSD.world_macro_state": _cert("EURUSD", "world_macro_state",
                                               series_key="wabc")})
    doc = C.build(NOW)
    assert doc["world_keys"] == C.UNMEASURED
    i = doc["certificates"][0]["inputs"][-1]
    assert i["basis"] == C.TERMS_UNMEASURED and "keys.json absent" in i["why"]
