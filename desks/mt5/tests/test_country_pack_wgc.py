"""World Gold Council doors (central-bank purchases by country, gold ETF holdings and flows by
region) as a country pack of the world dataset hunter. No network: every request is served from
tests/fixtures/country_packs, whose numbers are SYNTHETIC (the build host's egress proxy refused
gold.org on 2026-11-03, so the fixtures follow the documented public table layout).
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

from libs.data import polite_fetch as pf  # noqa: E402
from libs.data import terms_fence as tf  # noqa: E402
from libs.research import access_classifier as ac  # noqa: E402
from research import actor_atlas as aa  # noqa: E402
from research import country_packs as cp  # noqa: E402
from research import universe_policy as up  # noqa: E402
from research import world_dataset_hunter as W  # noqa: E402

FIX = DESK / "tests" / "fixtures" / "country_packs"
NOW = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)
UNIVERSE_ROWS = {"XAUUSD": {"asset_class": "Commodities", "currency_profit": "USD"},
                 "XAGUSD": {"asset_class": "Commodities", "currency_profit": "USD"},
                 "EURUSD": {"asset_class": "Forex", "currency_profit": "USD"}}
ROUTES = {"monthly-central-bank-statistics": "wgc_cb_monthly.html",
          "gold-etfs-holdings-and-flows": "wgc_etf_flows.html"}
PUBLIC = ("wgc_cb_monthly", "wgc_etf_flows")
DOWNLOADS = ("wgc_cb_xlsx", "wgc_etf_xlsx")


def _body(name: str) -> bytes:
    return (FIX / name).read_bytes()


class Web:
    """Serves the WGC fixtures by URL fragment; every other door is unreachable."""

    def __init__(self, override: dict[str, Any] | None = None) -> None:
        self.calls: list[tuple[str, dict[str, str]]] = []
        self.override = override or {}

    def __call__(self, url: str, timeout: float, headers: dict[str, str] | None = None,
                 data: bytes | None = None) -> bytes:
        self.calls.append((url, dict(headers or {})))
        for frag, val in [*self.override.items(), *ROUTES.items()]:
            if frag in url:
                if isinstance(val, Exception):
                    raise val
                return val if isinstance(val, bytes) else _body(val)
        raise W.FetchError("blocked_proxy", url)

    def wgc(self) -> list[str]:
        return [u for u, _ in self.calls if "gold.org" in u]


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
    for fn in ("discover", "attempt_legacy", "fetch_direct", "fetch_dbnomics"):
        monkeypatch.setattr(W, fn, lambda *a, **k: None)
    up._registry.cache_clear()
    for fn in (W._universe_at, W._exposure_at, W._keys_at, W._frame_at):
        fn.cache_clear()
    yield tmp_path
    up._registry.cache_clear()
    W._universe_at.cache_clear()


# ------------------------------------------------------------------------------- the parser --
def test_the_parser_reads_the_public_table_layout() -> None:
    cb = cp.parse_wgc_tables(_body("wgc_cb_monthly.html"))
    assert cb.published == date(2026, 11, 2)
    pol = dict(cb.series["cb_net_t_poland"])
    assert "2023-05" not in pol                       # "-" is absent, never zero
    assert pol["2023-06"] == 2.4 and pol["2023-08"] == -0.6   # "(0.6)" is a sale
    assert min(pol) == "2023-06" and max(pol) == "2026-07"   # its Aug-2026 cell is "-"
    assert max(dict(cb.series["cb_net_t_china"])) == "2026-08"
    assert {"cb_net_t_china", "cb_net_t_czech_republic", "cb_net_t_uzbekistan"} <= set(cb.series)
    # the reporting total is derived from the countries, period by period
    tot = dict(cb.series["cb_net_t_total_reporting"])
    assert tot["2023-06"] == pytest.approx(sum(dict(v).get("2023-06", 0.0)
                                               for k, v in cb.series.items()
                                               if k != "cb_net_t_total_reporting"))

    etf = cp.parse_wgc_tables(_body("wgc_etf_flows.html"))
    assert etf.published == date(2026, 10, 8)
    regions = ("north_america", "europe", "asia", "other")
    for m in ("etf_holdings_t", "etf_flows_t", "etf_flows_usd_mn"):
        for r in regions:
            assert len(etf.series[f"{m}_{r}"]) == 40, (m, r)
    assert dict(etf.series["etf_holdings_t_north_america"])["2023-06"] == 1685.0  # "1,685.0"
    assert dict(etf.series["etf_flows_t_north_america"])["2023-06"] == -15.0
    assert dict(etf.series["etf_flows_usd_mn_north_america"])["2023-07"] == -786.5


def test_a_page_without_the_table_parses_to_nothing() -> None:
    assert cp.parse_wgc_tables(b"<html><body><div id='app'></div></body></html>").series == {}
    assert cp.series_from_bodies(cp.BY_ID["wgc_cb_monthly"], [b"<html></html>"], NOW) == []


# ------------------------------------------------------------------ point in time: published --
def test_each_observation_is_stamped_by_publication_never_by_its_period() -> None:
    s = {x["code"]: x for x in cp.series_from_bodies(cp.BY_ID["wgc_cb_monthly"],
                                                      [_body("wgc_cb_monthly.html")], NOW)}
    rel = s["cb_net_t_china"]["release_at"]
    for per, stamp in rel.items():
        end = cp._month_end(int(per[:4]), int(per[5:7]))
        assert datetime.fromisoformat(stamp).date() > end, per    # never the period date
    # history: the publisher's monthly lag rule (month end + 45 days, 12:00 UTC, a weekday)
    assert rel["2026-06"] == "2026-08-14T12:00:00+00:00"
    # the newest period is first published by THIS page: its own date binds when it is later
    assert rel["2026-08"] == "2026-11-03T00:00:00+00:00"
    assert s["cb_net_t_china"]["stems"] == ["XAU"]
    etf = {x["code"]: x for x in cp.series_from_bodies(cp.BY_ID["wgc_etf_flows"],
                                                       [_body("wgc_etf_flows.html")], NOW)}
    # ETF flows: month end + 10 days 12:00 UTC (Oct 10 is a Saturday -> Monday); the page's own
    # date (Oct 8) is earlier, so the rule binds -- never earlier than either
    assert etf["etf_flows_t_europe"]["release_at"]["2026-09"] == "2026-10-12T12:00:00+00:00"


def test_the_store_keys_each_value_on_its_publication(box) -> None:
    web = Web()
    rep = W.run(budget_s=120, fetch=web, now=NOW)
    assert len(web.wgc()) == 2                         # the two public pages, nothing else
    for _url, hdr in [c for c in web.calls if "gold.org" in c[0]]:
        assert hdr.get("User-Agent") == pf.DESK_UA      # the honest desk agent
    frame = pd.read_parquet(W.dataset_path("WGC", "wgc_cb_monthly"))
    assert (frame["available_time"] > frame["period_end"]).all()
    last = frame[(frame["series_code"] == "cb_net_t_china") & (frame["period"] == "2026-08")]
    assert last["available_time"].iloc[0] == pd.Timestamp("2026-11-03T00:00:00Z")
    expo = json.loads(W.EXPOSURE.read_text("utf-8"))
    assert W.series_key("WGC", "wgc_etf_flows", "etf_flows_t_asia") in expo["symbols"]["XAUUSD"]
    assert W.series_key("WGC", "wgc_cb_monthly", "cb_net_t_total_reporting") in \
        expo["symbols"]["XAUUSD"]
    assert "EURUSD" not in {s for s, keys in expo["symbols"].items()
                            if any(k == W.series_key("WGC", "wgc_cb_monthly", "cb_net_t_poland")
                                   for k in keys)}
    wgc = rep["country_packs"]["packs"]["wgc"]
    assert wgc["doors"]["wgc_cb_monthly"]["verdict"] == "GREEN"
    assert wgc["doors"]["wgc_etf_flows"]["verdict"] == "GREEN"


# ---------------------------------------------------------------------------- liveness: RED --
def test_liveness_turns_red_after_more_than_two_empty_runs(box) -> None:
    rows = {"wgc_cb_monthly": {"empty_streak": 2, "fail_reason": "empty"}}
    assert cp.liveness(rows, NOW)["dependencies"]["wgc_cb_monthly"]["verdict"] == "AMBER"
    rows = {"wgc_cb_monthly": {"empty_streak": 3, "fail_reason": "empty"}}
    live = cp.liveness(rows, NOW)
    assert live["red"] == ["wgc_cb_monthly"] and live["sources"]["wgc"] == "RED"

    web = Web({"monthly-central-bank-statistics": b"<html><body><div id='app'></div></body>"
                                                   b"</html>"})
    for i in range(3):
        W.run(budget_s=120, fetch=web, now=NOW + timedelta(hours=7 * i))
        dep = json.loads(W.PACK_LIVENESS.read_text("utf-8"))["dependencies"]["wgc_cb_monthly"]
        assert dep["empty_streak"] == i + 1
        assert dep["verdict"] == ("RED" if i == 2 else "AMBER")
    live = json.loads(W.PACK_LIVENESS.read_text("utf-8"))
    assert "wgc_cb_monthly" in live["red"] and live["verdict"] == "RED"
    assert live["dependencies"]["wgc_etf_flows"]["verdict"] == "GREEN"


def test_never_reached_from_this_host_is_unmeasured() -> None:
    live = cp.liveness({}, NOW)
    for d in PUBLIC:
        assert live["dependencies"][d]["verdict"] == "UNMEASURED"


# ------------------------------------------------------------------------ the login-held path --
def test_the_download_files_are_held_on_their_login_with_missed_growth() -> None:
    for d in DOWNLOADS:
        st, why = cp.gate(cp.BY_ID[d])
        assert st == "HELD" and "login" in why, d
    row = tf.SOURCE_POLICY["wgc_goldhub_download"]
    assert row["status"] == tf.METHOD_BLOCKED and row["reason"] == "login"
    assert row["permitted_route"] == "wgc_goldhub"
    mg = cp.missed_growth_lines()["wgc_goldhub_download"]
    assert mg["delta_elogw"] == "UNMEASURED" and "login" in mg["cause"]
    live = cp.liveness({}, NOW)
    for d in DOWNLOADS:
        assert live["dependencies"][d]["verdict"] == "UNMEASURED"   # never asked, never GREEN
    rows = {d: {"pack_state": "HELD"} for d in DOWNLOADS}
    assert all(cp.liveness(rows, NOW)["dependencies"][d]["verdict"] == "HELD" for d in DOWNLOADS)


def test_a_login_wall_on_a_public_door_holds_it_for_a_person(box) -> None:
    web = Web({"gold-etfs-holdings-and-flows": _body("wgc_login.html")})
    W.run(budget_s=120, fetch=web, now=NOW)
    dep = json.loads(W.PACK_LIVENESS.read_text("utf-8"))["dependencies"]["wgc_etf_flows"]
    assert dep["verdict"] == "HELD" and dep["last_reason"] == "login_required"
    assert dep["empty_streak"] == 0                     # a hold is not an empty run
    n = len(web.wgc())
    # held for a person: later passes never ask again, and the hold never turns RED
    for i in range(1, 4):
        W.run(budget_s=120, fetch=web, now=NOW + timedelta(days=i))
    assert [u for u in web.wgc()[n:] if "etf" in u] == []
    dep = json.loads(W.PACK_LIVENESS.read_text("utf-8"))["dependencies"]["wgc_etf_flows"]
    assert dep["verdict"] == "HELD"
    rep = json.loads(W.REPORT.read_text("utf-8"))
    door = rep["country_packs"]["packs"]["wgc"]["doors"]["wgc_etf_flows"]
    assert door["missed_growth"]["delta_elogw"] == "UNMEASURED"
    # a redirect into a login wall (the fetch guard's refusal) is the same hold
    web2 = Web({"monthly-central-bank-statistics": W.FetchError(
        "terms_fenced", "redirected into login_wall: https://www.gold.org/user/login")})
    W.run(budget_s=120, fetch=web2, now=NOW + timedelta(days=5))
    dep = json.loads(W.PACK_LIVENESS.read_text("utf-8"))["dependencies"]["wgc_cb_monthly"]
    assert dep["verdict"] == "HELD" and dep["empty_streak"] == 0


# --------------------------------------------------------------------------- the terms label --
def test_the_terms_row_labels_and_never_stops_mining() -> None:
    row = tf.SOURCE_POLICY["wgc_goldhub"]
    # LAWS 5e: the label is derived by the access router, and it MINES
    verdict = ac.classify(dict(row["access_meta"]))
    assert row["access_label"] == verdict.access_label == "PUBLIC_WITH_TERMS"
    assert verdict.mined and not verdict.redistribute_allowed and verdict.may("alpha_input")
    assert row["redistribute"] is False
    assert row["status"] == tf.PUBLIC_PAGE and tf.input_source(
        "https://www.gold.org/goldhub/data/gold-etfs-holdings-and-flows") is None
    for d in PUBLIC:
        assert cp.gate(cp.BY_ID[d]) is None, d         # fetched for research every pass
        assert d in row["sources"] and tf.source_key(d) == "wgc_goldhub"
    # the terms were not read from this host: no clause, so never a live sizing input
    assert tf.terms_state("wgc_goldhub") == tf.UNREAD
    sz = tf.live_sizing_input("wgc_goldhub")
    assert sz["permitted"] is False and sz["research"] is True
    assert sz["missed_growth"]["delta_elogw"] == "UNMEASURED"
    assert "terms-and-conditions" in row["terms"]["url"]
    # the unblock is a quoted clause: with one, the same row becomes a sizing input
    flipped = {**row, "live_sizing_input": True,
               "terms": {**row["terms"], "clauses": {"x": "a quoted permitting clause"}}}
    try:
        tf.SOURCE_POLICY["wgc_goldhub"] = flipped
        assert tf.live_sizing_input("wgc_goldhub")["permitted"] is True
    finally:
        tf.SOURCE_POLICY["wgc_goldhub"] = row
    rows = {d: {"fetched_at": NOW.isoformat()} for d in PUBLIC}
    dep = cp.liveness(rows, NOW)["dependencies"]["wgc_cb_monthly"]
    assert dep["access"]["access_label"] == "PUBLIC_WITH_TERMS"
    assert dep["access"]["live_sizing"] == "WITHHELD"


# ----------------------------------------------------- the actor atlas: who must transact ----
def test_the_central_bank_and_etf_atlas_rows_read_the_wgc_store() -> None:
    by = {s.row_id: s for s in aa.SEED}
    cb, etf = by["central_bank_gold_reserve_flow"], by["regional_gold_etf_flow"]
    rel = lambda p: str(p.relative_to(W.DESK)).replace("\\", "/")  # noqa: E731
    assert cb.desk_path == rel(W.dataset_path("WGC", "wgc_cb_monthly"))
    assert etf.desk_path == rel(W.dataset_path("WGC", "wgc_etf_flows"))
    assert "prefix:XAU" in cb.selectors and "prefix:XAU" in etf.selectors
    assert "World Gold Council" in cb.source and "World Gold Council" in etf.source
