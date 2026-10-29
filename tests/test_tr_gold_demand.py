"""Turkish household gold demand state (IDEA_QUEUE 257): CBRT EVDS TRY gold price premium over
XAUUSD x USDTRY, monthly gold import surge z, CBRT gold reserves; Borsa Istanbul on fixtures
only. No network: every fetch is faked or refused."""
from __future__ import annotations

import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import terms_fence as tf  # noqa: E402
from research import alt_proxies as A  # noqa: E402
from research import asia_gold_physical as G  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "alt_proxies"
NOW = datetime(2026, 10, 29, 12, tzinfo=UTC)
EVDS = (G.TR_PRICE_ID, G.TR_IMPORT_ID, G.TR_RESERVE_ID)
FAKE_KEY = "fixture-not-a-key-0000"


# ---------------------------------------------------------------------------- parsers
def test_evds_daily_body_skips_null_and_empty_cells_never_zero() -> None:
    rows = G.parse_evds((FIX / f"{G.TR_PRICE_ID}.json").read_bytes(), "TP.MK.KUL.YTL")
    days = {r["date"]: r["value"] for r in rows}
    assert days["2026-10-28"] == 5478.40 and days["2026-10-27"] == 5452.10
    assert "2026-10-18" not in days                    # a Sunday's null cell is absent
    assert "2026-10-20" not in days                    # an empty cell is absent, not 0
    assert all(r["freq"] == "D" for r in rows)


def test_evds_monthly_dates_to_month_end_and_a_wrong_code_reads_nothing() -> None:
    body = (FIX / f"{G.TR_IMPORT_ID}.json").read_bytes()
    rows = G.parse_evds(body, "")                      # no code: the sole TP_ column
    assert rows[0]["date"] == "2024-01-31" and rows[-1]["date"] == "2026-09-30"
    assert all(r["freq"] == "M" for r in rows)
    assert G.parse_evds(body, "TP.SOMETHING.ELSE") == []
    assert G.parse_evds(b"<html>error</html>", "") == []
    two = json.dumps({"items": [{"Tarih": "01-01-2026", "TP_A": "1", "TP_B": "2"}]}).encode()
    assert G.parse_evds(two, "") == []                 # several columns, none named: nothing


def test_bist_table_reads_turkish_number_format() -> None:
    rows = G.parse_bist_metal_prices((FIX / f"{G.TR_BIST_ID}.html").read_bytes())
    assert [r["date"] for r in rows] == ["2026-10-27", "2026-10-28"]
    assert rows[1]["try_per_kg"] == 5476250.0 and rows[1]["usd_per_oz"] == 4004.80


def test_evds_url_takes_only_a_series_code_and_never_the_key() -> None:
    url = G.evds_url("https://evds3.tcmb.gov.tr/igmevdsms-dis", "TP.MK.KUL.YTL",
                     date(2026, 1, 2), date(2026, 10, 28))
    assert url == ("https://evds3.tcmb.gov.tr/igmevdsms-dis/series=TP.MK.KUL.YTL"
                   "&startDate=02-01-2026&endDate=28-10-2026&type=json")
    for bad in ("", "TP.X&key=1", "abc", "TP.A B"):
        with pytest.raises(ValueError):
            G.evds_url("https://x/", bad, date(2026, 1, 1), date(2026, 1, 2))


# ---------------------------------------------------------------------------- arithmetic + PIT
def test_premium_is_zero_at_parity_and_inner_joined() -> None:
    xau, fx = 4000.0, 42.0
    par = xau * fx / G.TROY_OZ_G * G.TR_BAR_PURITY        # TRY per gram of 995 bar at parity
    rows = G.tr_premium_series({"2026-10-28": par * 1.02, "2026-10-29": par},
                               {"2026-10-28": fx}, {"2026-10-28": xau, "2026-10-29": xau})
    assert len(rows) == 1 and rows[0]["premium_pct"] == pytest.approx(2.0)
    assert rows[0]["premium_z"] is None                   # too few priors: None, never 0


def test_release_instants_are_late_and_never_the_period_itself() -> None:
    fri = date(2026, 10, 23)
    assert G.tr_release_at(G.TR_PRICE_ID, fri) == datetime(2026, 10, 26, 6, tzinfo=UTC)
    assert G.tr_release_at(G.TR_IMPORT_ID, date(2026, 8, 31)) == datetime(
        2026, 10, 1, 8, tzinfo=UTC)
    assert G.tr_release_at(G.TR_RESERVE_ID, fri) == datetime(2026, 10, 29, 12, tzinfo=UTC)
    assert G.tr_release(G.TR_IMPORT_ID, "2026-09") == "2026-11-02T08:00:00+00:00"
    # alt_proxies stamps with the same functions
    for sid in EVDS:
        assert A.BY_ID[sid].rule(fri) == G.tr_release_at(sid, fri)


def test_import_surge_z_uses_strictly_prior_months() -> None:
    imp = {r["date"][:7]: r["value"]
           for r in G.parse_evds((FIX / f"{G.TR_IMPORT_ID}.json").read_bytes(), "")}
    rows = G.tr_import_surge(imp, {})
    assert rows[0]["import_surge_z"] is None and rows[-1]["import_surge_z"] > 3
    assert rows[-1]["available_time"] == G.UNMEASURED


# ---------------------------------------------------------------------------- terms
def test_evds_row_is_live_on_its_own_quoted_terms_and_needs_its_key(
        monkeypatch: pytest.MonkeyPatch) -> None:
    row = tf.SOURCE_POLICY[G.TR_EVDS_POLICY]
    assert row["status"] == tf.API_PERMITTED and row["key_env"] == ("EVDS_API_KEY",)
    assert "kaynak gösterilmek koşuluyla" in row["terms"]["clauses"]["use"]
    assert "ticari veya ticari olmayan" in row["terms"]["clauses"]["commercial"]
    assert "prior written permission" in row["terms"]["site_disclaimer"]["quote"]
    assert tf.terms_verdict(G.TR_EVDS_POLICY) == "confirmed"
    monkeypatch.delenv("EVDS_API_KEY", raising=False)
    assert tf.status(G.TR_EVDS_POLICY) == tf.NEEDS_KEY
    monkeypatch.setenv("EVDS_API_KEY", FAKE_KEY)
    assert tf.status(G.TR_EVDS_POLICY) == tf.API_PERMITTED
    for sid in EVDS:
        assert tf.source_key(sid) == G.TR_EVDS_POLICY and tf.input_source(sid) is None
        assert A.TERMS[sid][0] == "confirmed" == A.BY_ID[sid].terms
        assert A.TERMS_EVIDENCE[sid]["policy_row"] == G.TR_EVDS_POLICY


def test_bist_and_iar_are_ideas_only_with_missed_growth_lines() -> None:
    bist, iar = tf.SOURCE_POLICY[G.TR_BIST_ID], tf.SOURCE_POLICY[G.TR_IAR_POLICY]
    assert bist["status"] == iar["status"] == tf.IDEAS_ONLY
    assert "prior written consent" in bist["terms"]["clauses"]["copying"]
    assert tf.terms_state(G.TR_IAR_POLICY) == tf.UNREAD
    assert A.BY_ID[G.TR_BIST_ID].terms == "to_confirm"
    lines = {ln["policy_row"]: ln for ln in G.missed_growth_lines()}
    for k in (G.TR_BIST_ID, G.TR_IAR_POLICY):
        assert lines[k]["delta_elogw"] == "UNMEASURED" and lines[k]["kind"] == "ideas_only_refusal"
    assert G.TR_EVDS_POLICY not in lines                # NEEDS_KEY is a named state, not terms


def test_bist_is_never_fetched(tmp_path: Path) -> None:
    def boom(url: str, *a: Any) -> tuple[bytes, str]:
        raise AssertionError(f"fetched {url}")
    rec = A.collect(A.Paths(tmp_path / "desk"), A.BY_ID[G.TR_BIST_ID], {}, NOW, fetch=True,
                    fixtures=None, deadline=1e18, getter=boom)
    assert rec["requests"] == 0 and rec["status"].startswith("BLOCKED_ON_TERMS")


# ---------------------------------------------------------------------------- fetch door
def test_no_key_or_no_code_builds_no_request(monkeypatch: pytest.MonkeyPatch) -> None:
    src = A.BY_ID[G.TR_PRICE_ID]
    monkeypatch.delenv("EVDS_API_KEY", raising=False)
    monkeypatch.setenv("ALT_EVDS_GOLD_PRICE_SERIES", "TP.MK.KUL.YTL")
    assert A.status_of(src) == "BLOCKED_ON_KEY:EVDS_API_KEY"
    assert A.requests_for(src, NOW, {}) == []
    monkeypatch.setenv("EVDS_API_KEY", FAKE_KEY)
    monkeypatch.delenv("ALT_EVDS_GOLD_PRICE_SERIES")
    assert A.status_of(src) == "UNCONFIGURED:ALT_EVDS_GOLD_PRICE_SERIES"
    assert A.requests_for(src, NOW, {}) == []


def test_key_travels_in_the_header_through_polite_fetch(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from libs.data import polite_fetch
    monkeypatch.setenv("EVDS_API_KEY", FAKE_KEY)
    monkeypatch.setenv("ALT_EVDS_GOLD_PRICE_SERIES", "TP.MK.KUL.YTL")
    seen: list[dict[str, Any]] = []
    body = (FIX / f"{G.TR_PRICE_ID}.json").read_bytes()

    def fake_get(url: str, **kw: Any) -> polite_fetch.Response:
        seen.append({"url": url, **kw})
        return polite_fetch.Response(url=url, status=200, body=body,
                                     content_type="application/json")
    monkeypatch.setattr(polite_fetch, "get", fake_get)
    src = A.BY_ID[G.TR_PRICE_ID]
    assert src.polite and src.parent_selectors == A.TR_SELECTORS
    rec = A.collect(A.Paths(tmp_path / "desk"), src, {}, NOW, fetch=True, fixtures=None,
                    deadline=1e18)
    assert len(seen) == 1 and seen[0]["live_input"] is True
    assert seen[0]["headers"] == {G.EVDS_KEY_HEADER: FAKE_KEY}
    assert FAKE_KEY not in seen[0]["url"] and "series=TP.MK.KUL.YTL" in seen[0]["url"]
    assert rec["parsed"] == 9                           # 14 days - 4 weekend - 1 empty
    vaulted = "".join(p.read_text("utf-8", "replace") for p in (tmp_path / "desk").rglob("*")
                      if p.is_file())
    assert FAKE_KEY not in vaulted


# ---------------------------------------------------------------------------- wiring
def _h1(universe: Path, sym: str, closes: dict[str, float]) -> None:
    universe.mkdir(parents=True, exist_ok=True)
    idx = pd.DatetimeIndex([pd.Timestamp(f"{d} {G.TR_XAU_HOUR:02d}:00", tz="UTC")
                            for d in closes])
    pd.DataFrame({"close": list(closes.values())}, index=idx).to_parquet(
        universe / f"{sym}_H1.parquet")


def test_derived_premium_point_from_the_store(tmp_path: Path) -> None:
    paths = A.Paths(tmp_path / "desk")
    _h1(paths.universe, "XAUUSD", {"2026-10-27": 3990.5, "2026-10-28": 4005.25})
    _h1(paths.universe, "USDTRY", {"2026-10-27": 42.05, "2026-10-28": 42.11})
    src = A.BY_ID[G.TR_PRICE_ID]
    store: dict[str, Any] = {}
    obs = A.parse_tr_evds((FIX / f"{G.TR_PRICE_ID}.json").read_bytes(),
                          A.Ctx(part=G.TR_PRICE_ID))
    A.merge_vintages(store, src, obs, NOW)
    pts = A.asia_gold_derived(paths, src, store)
    last = pts["premium_pct"][-1]
    assert last["d"] == "2026-10-28" and 1.0 < last["value"] < 2.0
    doc = G.state_from_alt(paths, {}, NOW)
    assert doc["states"][G.TR_PRICE_ID]["verdict"] == G.UNMEASURED   # store not on disk


def test_children_condition_europe_and_asia_windows_only() -> None:
    src = A.BY_ID[G.TR_IMPORT_ID]
    assert src.instruments == {"XAUUSD": 1}
    assert A._on_selectors(src, {"name": "XAUUSD.asia#rr=1.5", "selector": "asia"})
    assert A._on_selectors(src, {"name": "x", "params": {"session": "london"}})
    assert A._on_selectors(src, {"name": "XAUUSD.london_am", "selector": "london_am"})
    assert not A._on_selectors(src, {"name": "XAUUSD.ny_open", "selector": "ny_open"})


def test_macro_state_engine_reads_the_turkish_inputs() -> None:
    from research import macro_state_engine as M
    spec = next(s for s in M.LATENT_SPECS if s.id == "cn_physical_gold")
    got = {i.terms_source: i for i in spec.inputs if i.terms_source}
    for sid in EVDS:
        assert got[sid].axis == f"alt_{sid}" and got[sid].key_env == "EVDS_API_KEY"


def test_live_state_without_key_names_needs_key(monkeypatch: pytest.MonkeyPatch,
                                                tmp_path: Path) -> None:
    monkeypatch.delenv("EVDS_API_KEY", raising=False)
    doc = G.state_from_alt(A.Paths(tmp_path / "desk"), {}, NOW)
    for sid in EVDS:
        b = doc["states"][sid]
        assert b["verdict"] == G.UNMEASURED and b["policy_status"] == tf.NEEDS_KEY
        assert b["why"].startswith("NEEDS_KEY: EVDS_API_KEY")
