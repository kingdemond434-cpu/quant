"""Country open-data packs (Turkey, Poland, Sweden, South Africa) through the world dataset
hunter's direct doors. No network: every request is served from tests/fixtures/country_packs.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import terms_fence as tf  # noqa: E402
from research import country_packs as cp  # noqa: E402
from research import universe_policy as up  # noqa: E402
from research import world_dataset_hunter as W  # noqa: E402

FIX = DESK / "tests" / "fixtures" / "country_packs"
NOW = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)
FX = {"asset_class": "Forex Exotics"}
UNIVERSE_ROWS = {
    "USDTRY": {**FX, "currency_profit": "TRY"}, "USDPLN": {**FX, "currency_profit": "PLN"},
    "EURPLN": {**FX, "currency_profit": "PLN"}, "USDSEK": {**FX, "currency_profit": "SEK"},
    "EURSEK": {**FX, "currency_profit": "SEK"}, "USDZAR": {**FX, "currency_profit": "ZAR"},
    "XAUUSD": {"asset_class": "Commodities", "currency_profit": "USD"},
    "EURUSD": {"asset_class": "Forex", "currency_profit": "USD"},
}
ROUTES = {
    "TP.DK.USD.A.YTL": "evds_usdtry.json", "TP.FG.J0": "evds_cpi.json",
    "TP.APIFON4": "evds_funding.json",
    "exchangerates/rates/A/USD": "nbp_usd.json", "exchangerates/rates/A/EUR": "nbp_usd.json",
    "cenyzlota": "nbp_gold.json", "stopy_procentowe": "nbp_rates.xml",
    "SECBREPOEFF": "swea_policy.json", "SEKUSDPMI": "swea_usdsek.json",
    "SEKEURPMI": "swea_usdsek.json", "swestr": "swestr.json", "api.scb.se": "scb_cpi.json",
    # the World Gold Council pack's public pages (test_country_pack_wgc.py tests them)
    "monthly-central-bank-statistics": "wgc_cb_monthly.html",
    "gold-etfs-holdings-and-flows": "wgc_etf_flows.html",
    # the metal ETF issuers' pages (test_country_pack_etf_issuers.py tests them)
    "GLD_US_archive": "spdr_gld_archive.csv", "ishares-silver-trust": "ishares_slv.html",
    "ishares-gold-trust": "ishares_iau.html",
}


def _body(name: str) -> bytes:
    return (FIX / name).read_bytes()


class Web:
    """A fetcher serving fixtures by URL fragment; records every call and every header."""

    def __init__(self, override: dict[str, Any] | None = None) -> None:
        self.calls: list[tuple[str, dict[str, str], bytes | None]] = []
        self.override = override or {}

    def __call__(self, url: str, timeout: float, headers: dict[str, str] | None = None,
                 data: bytes | None = None) -> bytes:
        self.calls.append((url, dict(headers or {}), data))
        for frag, val in [*self.override.items(), *ROUTES.items()]:
            if frag in url:
                if isinstance(val, Exception):
                    raise val
                return val if isinstance(val, bytes) else _body(val)
        raise W.FetchError("blocked_proxy", url)

    def urls(self) -> list[str]:
        return [c[0] for c in self.calls]


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
                      ("REPORT", tmp_path / "DATASET_HUNT.json"),
                      ("PACK_LIVENESS", tmp_path / "COUNTRY_PACK_LIVENESS.json"),
                      ("DESK", tmp_path), ("MIN_REQUEST_GAP_S", 0.0)):
        monkeypatch.setattr(W, name, val)
    monkeypatch.setattr(up, "UNIVERSE", uni)
    monkeypatch.setattr(W, "_free_disk_ok", lambda: (True, {"free_gb": 99.0}))
    # Only the pack doors run: the DBnomics backbone and the other direct doors are not tested here.
    monkeypatch.setattr(W, "discover", lambda *a, **k: None)
    monkeypatch.setattr(W, "attempt_legacy", lambda *a, **k: None)
    monkeypatch.setattr(W, "fetch_direct", lambda *a, **k: None)
    monkeypatch.setattr(W, "fetch_dbnomics", lambda *a, **k: None)
    monkeypatch.setenv("EVDS_API_KEY", "fixture-key-not-real")
    for env in ("ALT_EVDS_RESERVES_SERIES", "ALT_EVDS_CA_SERIES"):
        monkeypatch.delenv(env, raising=False)
    up._registry.cache_clear()
    for fn in (W._universe_at, W._exposure_at, W._keys_at, W._frame_at):
        fn.cache_clear()
    yield tmp_path
    up._registry.cache_clear()
    W._universe_at.cache_clear()


# ------------------------------------------------------------------------------ the register --
LIVE_ROWS = ("tr_evds_macro", "se_riksbank", "se_scb")
# pl_nbp: its only permitting clause, s.1(6), grants copying "for personal use" -- not a permission
# for a desk's research, so the row is IDEAS_ONLY (fail closed for live input, 2026-11-03)
HELD_ROWS = ("za_sarb", "za_statssa_macro", "pl_nbp")


def test_each_pack_publisher_is_one_fence_row_with_its_verdict() -> None:
    for k in LIVE_ROWS:
        row = tf.SOURCE_POLICY[k]
        assert row["status"] == tf.API_PERMITTED and row["hosts"] == (), k
        assert row["terms"]["clauses"] and row["terms"]["url"].startswith("https://"), k
        assert tf.terms_verdict(k) == "confirmed", k
    for k in HELD_ROWS:
        row = tf.SOURCE_POLICY[k]
        assert row["status"] == tf.IDEAS_ONLY and row["unblock"], k
        assert row["missed_growth"]["delta_elogw"] == "UNMEASURED", k
        assert "UNMEASURED" in row["missed_growth"]["cause"], k
    q = " ".join(tf.SOURCE_POLICY["za_sarb"]["terms"]["clauses"].values())
    assert "without the prior written consent of the South African Reserve Bank" in q
    assert "licence CC0" in " ".join(tf.SOURCE_POLICY["se_scb"]["terms"]["clauses"].values())
    assert "automatiserat" in tf.SOURCE_POLICY["se_riksbank"]["terms"]["clauses"]["api"]
    # every door names a row of the ONE register, and the row names the door
    for d in cp.DOORS:
        assert d.id in tf.SOURCE_POLICY[d.policy]["sources"], d.id
        assert tf.source_key(d.id) == d.policy, d.id


def test_gate_holds_ideas_only_and_reads_keys_and_codes(monkeypatch) -> None:
    monkeypatch.setenv("EVDS_API_KEY", "x")
    monkeypatch.delenv("ALT_EVDS_RESERVES_SERIES", raising=False)
    assert cp.gate(cp.BY_ID["za_sarb_rates"])[0] == "HELD"
    assert cp.gate(cp.BY_ID["tr_fx_reserves"])[0] == "NEEDS_CONFIG"
    assert cp.gate(cp.BY_ID["tr_usdtry_cbrt"]) is None
    assert cp.gate(cp.BY_ID["pl_fx_usd"])[0] == "HELD" and cp.gate(cp.BY_ID["se_cpi"]) is None
    monkeypatch.setenv("ALT_EVDS_RESERVES_SERIES", "TP.AB.TOPLAM")
    assert cp.gate(cp.BY_ID["tr_fx_reserves"]) is None
    monkeypatch.delenv("EVDS_API_KEY")
    st, why = cp.gate(cp.BY_ID["tr_usdtry_cbrt"])
    assert st == "NEEDS_KEY" and "EVDS_API_KEY" in why


def test_evds_key_travels_in_the_header_only(monkeypatch) -> None:
    monkeypatch.setenv("EVDS_API_KEY", "secret-fixture")
    (req,) = cp.requests_for(cp.BY_ID["tr_usdtry_cbrt"], NOW, first=True)
    assert "secret-fixture" not in req.url and req.headers == {"key": "secret-fixture"}
    assert "series=TP.DK.USD.A.YTL" in req.url


def test_nbp_ranges_never_exceed_the_api_cap() -> None:
    reqs = cp.requests_for(cp.BY_ID["pl_fx_usd"], NOW, first=True)
    assert len(reqs) > 1
    for r in reqs:
        a, b = r.url.split("/A/USD/")[1].split("/")[:2]
        span = (date.fromisoformat(b) - date.fromisoformat(a)).days + 1
        assert 0 < span <= cp.NBP_MAX_RANGE_D


# --------------------------------------------------------------------------------- parsers --
def test_parsers_read_every_fixture_shape() -> None:
    d = cp.BY_ID
    usd = cp.parse_evds(_body("evds_usdtry.json"), d["tr_usdtry_cbrt"], "TP.DK.USD.A.YTL")
    assert len(usd) > 250 and usd[0][0] < usd[-1][0]          # the null holiday is absent
    cpi = cp.parse_evds(_body("evds_cpi.json"), d["tr_cpi"], "TP.FG.J0")
    assert cpi[0][0] == "2018-01" and len(cpi) == 105
    assert cp.parse_nbp_fx(_body("nbp_usd.json"), d["pl_fx_usd"])[0][1] > 3
    assert cp.parse_nbp_gold(_body("nbp_gold.json"), d["pl_gold"])[-1][0] == "2026-10-30"
    ev = cp.nbp_rate_events(_body("nbp_rates.xml"))
    assert ev["reference"][-1] == (date(2025, 10, 9), 4.5) and len(ev["deposit"]) == 5
    step = dict(cp.step_daily(ev["reference"], date(2025, 10, 6), date(2025, 10, 13)))
    assert step["2025-10-08"] == 4.75 and step["2025-10-09"] == 4.5 and "2025-10-11" not in step
    assert cp.parse_swea(_body("swea_policy.json"), d["se_policy_rate"])[-1][1] == 1.75
    pts, rel = cp.parse_swestr(_body("swestr.json"), d["se_swestr"])
    assert rel[pts[0][0]].endswith("09:00:00+00:00") and rel[pts[0][0]] > pts[0][0]
    m = cp.parse_jsonstat_months(_body("scb_cpi.json"), d["se_cpi"])
    assert m[0][0] == "2017-01" and m[-1][0] == "2026-09"
    sarb = cp.parse_sarb(_body("sarb_rates.json"), d["za_sarb_rates"])
    assert sarb["repo_rate"] == [("2026-10-30", 7.0)]


def test_a_wrong_code_or_error_envelope_parses_to_nothing() -> None:
    door = cp.BY_ID["tr_usdtry_cbrt"]
    assert cp.parse_evds(_body("evds_usdtry.json"), door, "TP.WRONG.CODE") == []
    assert cp.series_from_bodies(cp.BY_ID["se_usdsek"], [b"[]"], NOW) == []
    assert cp.parse_jsonstat_months(b'{"error":"x"}', cp.BY_ID["se_cpi"]) == []


def test_release_clocks_are_the_publishers() -> None:
    r = cp.release_at
    assert r("tr_cpi", date(2026, 9, 30)) == datetime(2026, 10, 5, 7, tzinfo=UTC)  # 3rd = Sat
    assert r("nbp_fix", date(2026, 10, 30)) == datetime(2026, 10, 30, 11, 30, tzinfo=UTC)
    assert r("se_fix", date(2026, 10, 30)) == datetime(2026, 10, 30, 16, tzinfo=UTC)
    assert r("se_cpi", date(2026, 9, 30)) == datetime(2026, 10, 16, 7, tzinfo=UTC)
    assert r("tr_weekly", date(2026, 10, 23)) == datetime(2026, 10, 29, 12, tzinfo=UTC)
    s = {x["code"]: x for x in cp.series_from_bodies(cp.BY_ID["tr_cpi"],
                                                      [_body("evds_cpi.json")], NOW)}
    assert set(s) == {"cpi_index", "cpi_yoy", "cpi_yoy_chg"}
    assert s["cpi_yoy"]["release_at"]["2026-09"] == "2026-10-05T07:00:00+00:00"


# --------------------------------------------------------------------- through the hunter --
def test_packs_land_pit_stamped_and_mapped_through_the_hunter(box) -> None:
    web = Web()
    rep = W.run(budget_s=120, fetch=web, now=NOW)
    urls = web.urls()
    assert not any("resbank" in u for u in urls)                 # held: never requested
    assert not any("nbp.pl" in u for u in urls)                  # held: never requested
    assert not any("TP.AB" in u or "ALT_EVDS" in u for u in urls)  # unconfigured: no request
    evds = [c for c in web.calls if "TP.DK.USD" in c[0]]
    assert evds and all(c[1].get("key") == "fixture-key-not-real" for c in evds)
    scb = [c for c in web.calls if "api.scb.se" in c[0]]
    assert scb and scb[0][2] and json.loads(scb[0][2])["response"]["format"] == "json-stat2"

    packs = rep["country_packs"]["packs"]
    assert packs["pl"]["doors"]["pl_fx_usd"]["verdict"] == "HELD"
    assert packs["pl"]["verdict"] == "HELD" and rep["country_packs"]["missed_growth"]["pl_nbp"]
    assert set(packs["pl"]["doors"]["pl_fx_usd"]["instruments"]) >= {"USDPLN", "EURPLN"}
    assert "XAUUSD" in packs["pl"]["doors"]["pl_gold"]["instruments"]
    assert set(packs["se"]["doors"]["se_usdsek"]["instruments"]) >= {"USDSEK", "EURSEK"}
    assert "USDTRY" in packs["tr"]["doors"]["tr_usdtry_cbrt"]["instruments"]
    assert packs["tr"]["doors"]["tr_fx_reserves"]["verdict"] == "NEEDS_CONFIG"
    assert packs["za"]["doors"]["za_sarb_rates"]["verdict"] == "HELD"
    assert packs["za"]["verdict"] == "HELD"
    assert packs["pl"]["local_indices_unmapped"] == ["PL20", "POL20", "WIG20"]
    assert packs["za"]["not_built"] and rep["country_packs"]["missed_growth"]["za_sarb"]
    assert rep["country_packs"]["verdict"] == "GREEN"

    # PIT: the stored available_time is the publisher's release instant, not a cadence lag
    assert not W.dataset_path("NBP", "pl_fx_usd").exists()      # held: nothing landed
    sw = pd.read_parquet(W.dataset_path("RIKSBANK", "se_swestr"))
    first = sw.sort_values("period").iloc[0]
    assert first["available_time"] > first["period_end"]
    assert first["available_time"].hour == 9

    # the series reach the world_macro_state door: exposed per symbol, rebuildable by key
    expo = json.loads(W.EXPOSURE.read_text("utf-8"))
    sek = expo["symbols"]["USDSEK"]
    key = W.series_key("RIKSBANK", "se_usdsek", "se_usdsek")
    assert key in sek and W.series_key("SCB", "se_cpi", "cpi_yoy") in sek
    assert W.series_key("RIKSBANK", "se_swestr", "se_swestr") in sek
    assert W.series_key("NBP", "pl_fx_usd", "pl_fx_usd") not in expo["symbols"].get("USDPLN",
                                                                                    [])
    assert W.series_key("CBRT_EVDS", "tr_cpi", "cpi_yoy_chg") in expo["symbols"]["USDTRY"]
    s = W.raw_world_series(key)
    assert s is not None and len(s) > 250
    assert s.index.max() <= pd.Timestamp(NOW)

    live = json.loads(W.PACK_LIVENESS.read_text("utf-8"))
    assert live["verdict"] == "GREEN" and live["red_after_runs"] == 2 and live["red"] == []


def test_a_door_empty_on_three_consecutive_runs_turns_red_and_recovers(box) -> None:
    web = Web({"SEKUSDPMI": b"[]"})
    for i in range(3):
        rep = W.run(budget_s=120, fetch=web, now=NOW + timedelta(hours=7 * i))
        dep = json.loads(W.PACK_LIVENESS.read_text("utf-8"))["dependencies"]["se_usdsek"]
        assert dep["empty_streak"] == i + 1
        assert rep["country_packs"]["verdict"] == ("RED" if i == 2 else "GREEN")
    live = json.loads(W.PACK_LIVENESS.read_text("utf-8"))
    assert live["red"] == ["se_usdsek"] and live["sources"]["se"] == "RED"
    assert live["dependencies"]["se_usdsek"]["last_reason"] == "empty"
    # a transport failure counts the same as an empty body
    web2 = Web({"SEKUSDPMI": W.FetchError("timeout", "x")})
    W.run(budget_s=120, fetch=web2, now=NOW + timedelta(hours=21))
    assert json.loads(W.PACK_LIVENESS.read_text("utf-8"))["dependencies"]["se_usdsek"][
        "empty_streak"] == 4
    # the door delivers again: the streak resets and the verdict clears
    W.run(budget_s=120, fetch=Web(), now=NOW + timedelta(hours=28))
    live = json.loads(W.PACK_LIVENESS.read_text("utf-8"))
    assert live["verdict"] == "GREEN"
    assert live["dependencies"]["se_usdsek"]["empty_streak"] == 0


def test_no_door_reached_is_unmeasured_never_green(box) -> None:
    down = W.FetchError("blocked_proxy", "x")
    rep = W.run(budget_s=120, fetch=Web({"api.": down, "static.nbp": down, "tcmb": down,
                                         "gold.org": down, "spdrgoldshares": down,
                                         "ishares": down}), now=NOW)
    assert rep["country_packs"]["verdict"] == "UNMEASURED"
    assert rep["country_packs"]["packs"]["pl"]["doors"]["pl_fx_usd"]["rows"] == "UNMEASURED"


def test_process_health_reads_the_pack_verdict(tmp_path) -> None:
    import importlib.util
    spec = importlib.util.spec_from_file_location("process_health_t",
                                                  ROOT / "ops" / "process_health.py")
    assert spec and spec.loader
    ph = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ph)
    assert ph.dependency_liveness(tmp_path / "absent.json")["verdict"] == "UNMEASURED"
    p = tmp_path / "COUNTRY_PACK_LIVENESS.json"
    p.write_text(json.dumps(cp.liveness({"se_usdsek": {"empty_streak": 3,
                                                       "fail_reason": "empty"}}, NOW)), "utf-8")
    got = ph.dependency_liveness(p)
    assert got["verdict"] == "RED" and got["red"][0]["dependency"] == "se_usdsek"
