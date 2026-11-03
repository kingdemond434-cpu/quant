"""Daily point-in-time holdings of GLD, SLV and IAU from the issuers' own public pages (SPDR's
GLD archive file, iShares' trust product pages), as a country pack of the world dataset hunter.
No network: the fixtures are SYNTHETIC numbers in the documented public layouts (the build host's
egress proxy refused both hosts on 2026-11-03).
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
ROUTES = {"GLD_US_archive": "spdr_gld_archive.csv", "ishares-silver-trust": "ishares_slv.html",
          "ishares-gold-trust": "ishares_iau.html"}
DOORS = ("etf_gld_holdings", "etf_slv_holdings", "etf_iau_holdings")


def _body(name: str) -> bytes:
    return (FIX / name).read_bytes()


class Web:
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


# ------------------------------------------------------------------------------- the parsers --
def test_the_gld_archive_parses_ounces_tonnes_and_shares() -> None:
    s = cp.parse_spdr_archive(_body("spdr_gld_archive.csv"), "gld")
    oz, t, sh = (dict(s[k]) for k in ("gld_ounces", "gld_tonnes", "gld_shares_outstanding"))
    assert oz["2025-09-01"] == 28_000_000.0 and t["2025-09-01"] == 870.90
    # shares outstanding = ounces in the trust / ounces of gold per share
    assert sh["2025-09-01"] == pytest.approx(28_000_000.0 / 0.092100, rel=1e-9)
    assert "2025-12-25" not in oz and "2026-01-01" not in oz        # HOLIDAY rows are absent
    assert max(oz) == "2026-10-30" and len(oz) > 250


def test_the_ishares_pages_parse_shares_and_metal_as_of_their_date() -> None:
    slv = cp.parse_ishares_page(_body("ishares_slv.html"), "slv")
    assert slv.as_of == date(2026, 11, 2)
    assert slv.values == {"slv_shares_outstanding": 521_350_000.0,
                          "slv_ounces": 472_815_402.30, "slv_tonnes": 14_706.21}
    iau = cp.parse_ishares_page(_body("ishares_iau.html"), "iau")
    assert iau.values["iau_tonnes"] == 423.41 and iau.as_of == date(2026, 11, 2)
    empty = cp.parse_ishares_page(b"<html><body>Choose your role</body></html>", "slv")
    assert empty.values == {} and empty.as_of is None


# --------------------------------------------------------------------- point in time stamps --
def test_each_holding_is_stamped_at_publication_never_its_date() -> None:
    g = {x["code"]: x for x in cp.series_from_bodies(cp.BY_ID["etf_gld_holdings"],
                                                      [_body("spdr_gld_archive.csv")], NOW)}
    rel = g["gld_ounces"]["release_at"]
    # SPDR strikes the trust at 4.15 p.m. New York and posts the file that evening: the day's
    # holdings are stamped the next day 01:00 UTC, never on their own date
    assert rel["2026-10-30"] == "2026-10-31T01:00:00+00:00"
    assert all(datetime.fromisoformat(v).date() > date.fromisoformat(p) for p, v in rel.items())
    assert g["gld_ounces"]["stems"] == ["XAU"]
    s = {x["code"]: x for x in cp.series_from_bodies(cp.BY_ID["etf_slv_holdings"],
                                                      [_body("ishares_slv.html")], NOW)}
    # iShares prints "as of" the prior day and updates the next morning: as-of + 1 day 14:00
    # UTC (a weekday), or the instant the desk saw it when that is earlier
    assert s["slv_tonnes"]["release_at"] == {"2026-11-02": "2026-11-03T12:00:00+00:00"}
    later = NOW + timedelta(days=1)
    s2 = {x["code"]: x for x in cp.series_from_bodies(cp.BY_ID["etf_slv_holdings"],
                                                       [_body("ishares_slv.html")], later)}
    assert s2["slv_tonnes"]["release_at"] == {"2026-11-02": "2026-11-03T14:00:00+00:00"}
    assert s["slv_tonnes"]["stems"] == ["XAG"]


def test_the_holdings_land_pit_stamped_and_mapped(box) -> None:
    web = Web()
    W.run(budget_s=120, fetch=web, now=NOW)
    mine = [c for c in web.calls if "spdrgoldshares" in c[0] or "ishares" in c[0]]
    assert len(mine) == 3 and all(h.get("User-Agent") == pf.DESK_UA for _, h in mine)
    frame = pd.read_parquet(W.dataset_path("ETF_ISSUER", "etf_gld_holdings"))
    assert (frame["available_time"] > frame["period_end"]).all()
    slv = pd.read_parquet(W.dataset_path("ETF_ISSUER", "etf_slv_holdings"))
    assert set(slv["series_code"]) == {"slv_shares_outstanding", "slv_ounces", "slv_tonnes"}
    expo = json.loads(W.EXPOSURE.read_text("utf-8"))
    assert W.series_key("ETF_ISSUER", "etf_gld_holdings", "gld_tonnes") in \
        expo["symbols"]["XAUUSD"]
    # a day later the page says the same: no new row; a new as-of day is a new row
    W.run(budget_s=120, fetch=web, now=NOW + timedelta(hours=7))
    slv2 = pd.read_parquet(W.dataset_path("ETF_ISSUER", "etf_slv_holdings"))
    assert len(slv2) == len(slv)
    live = json.loads(W.PACK_LIVENESS.read_text("utf-8"))
    assert all(live["dependencies"][d]["verdict"] == "GREEN" for d in DOORS)


# ---------------------------------------------------------------------------- liveness: RED --
def test_liveness_red_after_more_than_two_empty_runs(box) -> None:
    web = Web({"ishares-gold-trust": b"<html><body>Choose your role</body></html>"})
    for i in range(3):
        W.run(budget_s=120, fetch=web, now=NOW + timedelta(hours=7 * i))
    live = json.loads(W.PACK_LIVENESS.read_text("utf-8"))
    assert live["dependencies"]["etf_iau_holdings"]["verdict"] == "RED"
    assert "etf_iau_holdings" in live["red"] and live["sources"]["etf_issuers"] == "RED"
    assert live["dependencies"]["etf_gld_holdings"]["verdict"] == "GREEN"
    assert cp.liveness({}, NOW)["dependencies"]["etf_slv_holdings"]["verdict"] == "UNMEASURED"


# --------------------------------------------------------------------------- the terms label --
def test_issuer_terms_rows_label_and_never_stop_mining() -> None:
    for key, door_ids, url in (
            ("spdr_gold_shares", ("etf_gld_holdings",),
             "https://www.spdrgoldshares.com/assets/dynamic/GLD/GLD_US_archive_EN.csv"),
            ("ishares_trusts", ("etf_slv_holdings", "etf_iau_holdings"),
             "https://www.ishares.com/us/products/239855/ishares-silver-trust-fund")):
        row = tf.SOURCE_POLICY[key]
        v = ac.classify(dict(row["access_meta"]))
        assert row["access_label"] == v.access_label == "PUBLIC_WITH_TERMS" and v.mined, key
        assert row["redistribute"] is False and row["status"] == tf.PUBLIC_PAGE
        assert tf.source_of_url(url) == key and tf.input_source(url) is None
        assert tf.terms_state(key) == tf.UNREAD
        sz = tf.live_sizing_input(key)
        assert sz["permitted"] is False and sz["research"] is True
        assert sz["missed_growth"]["delta_elogw"] == "UNMEASURED"
        for d in door_ids:
            assert cp.gate(cp.BY_ID[d]) is None and tf.source_key(d) == key


# ------------------------------------------------------------- the retired script, revived --
def test_fetch_gld_is_the_door_not_a_laptop_path() -> None:
    text = (DESK / "research" / "fetch_gld.py").read_text("utf-8")
    assert "C:\\Users" not in text and "dell" not in text
    assert "country_packs" in text and "etf_gld_holdings" in text
    by = {s.row_id: s for s in aa.SEED}
    rel = str(W.dataset_path("ETF_ISSUER", "etf_gld_holdings").relative_to(W.DESK))
    assert by["etf_creation_redemption_metal"].desk_path == rel.replace("\\", "/")
