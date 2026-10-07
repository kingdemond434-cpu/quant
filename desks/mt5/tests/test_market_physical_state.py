"""Market-state engines (vol term structure, implied vs realised, curve, beta) and the EIA
physical states, PIT and directionless. Everything is synthetic; nothing touches the network."""
from __future__ import annotations

import json
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_ROOT), str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import event_surprise as es  # noqa: E402
import source_evig as se  # noqa: E402
from macro import market_state as ms  # noqa: E402
from macro import physical_state as ps  # noqa: E402

from libs.research import sensor_contract as sc  # noqa: E402

NOW = datetime(2026, 10, 6, 15, 0, tzinfo=UTC)


def _days(n: int, end: date = date(2026, 10, 5)) -> list[str]:
    return [(end - timedelta(days=n - 1 - i)).isoformat() for i in range(n)]


def _bars(closes: list[float], end: date = date(2026, 10, 5)) -> pd.DataFrame:
    idx = pd.DatetimeIndex([pd.Timestamp(d, tz="UTC") + pd.Timedelta(hours=20)
                            for d in _days(len(closes), end)])
    return pd.DataFrame({"open": closes, "close": closes}, index=idx)


def _series() -> dict[str, list[tuple[str, float]]]:
    days = _days(300)
    ser: dict[str, list[tuple[str, float]]] = {}
    for sid, y in (("DGS3MO", 4.5), ("DGS2", 4.0), ("DGS5", 3.9), ("DGS10", 4.1),
                   ("DGS30", 4.4)):
        ser[sid] = [(d, y + 0.001 * i) for i, d in enumerate(days)]
    return ser


def _vol_rows() -> list[dict]:
    """vol_archive observations: 40 daily ^VIX/^GVZ rows, the last a spike in backwardation."""
    rows = []
    for i, d in enumerate(_days(40)):
        seen = (datetime.fromisoformat(d) + timedelta(hours=21)).replace(tzinfo=UTC)
        last = i == 39
        rows.append({"observed_at": seen.isoformat(), "value_date": d, "vol_ticker": "^VIX",
                     "mt5_symbol": "US500", "implied_vol": 30.0 if last else 15.0 + i % 5,
                     "term": {"^VIX": 30.0 if last else 15.0, "^VIX3M": 18.0},
                     "term_shape": "backwardation" if last else "contango",
                     "variance_risk_premium": 9.0 if last else 2.0 + (i % 3),
                     "realised_vol_cc": 21.0, "iv_over_rv": 1.4})
        rows.append({"observed_at": seen.isoformat(), "value_date": d, "vol_ticker": "^EVZ",
                     "mt5_symbol": "EURUSD", "implied_vol": 7.0, "status": "OBSERVED",
                     "reason": "no bars"})
    return rows


def test_vol_state_reads_the_archive_as_held_and_ranks_it() -> None:
    vol = ms.vol_state(_vol_rows(), NOW)
    vix = vol["^VIX"]
    assert vix["date"] == "2026-10-05" and vix["term_shape"] == "backwardation"
    assert vix["implied_percentile"] == 1.0 and vix["vrp_percentile"] == 1.0
    assert vix["vix_vix3m_ratio"] == pytest.approx(30.0 / 18.0, rel=1e-3)
    assert vol["^EVZ"]["realised"]["status"] == "UNMEASURED"
    # an observation the desk had not yet made is not read
    early = ms.vol_state(_vol_rows(), datetime(2026, 10, 5, 20, 0, tzinfo=UTC))
    assert early["^VIX"]["date"] == "2026-10-04"
    assert ms.vol_state([], NOW)["_status"]["status"] == "UNMEASURED"
    assert ms.regime_from(vol) == "vol_backwardation_high"


def test_beta_from_bars() -> None:
    rng = np.random.default_rng(7)
    bench = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, 300)))
    gold_r = 2.0 * np.diff(np.log(bench))
    gold = list(100 * np.exp(np.concatenate([[0.0], np.cumsum(gold_r)])))
    b = ms.betas({"US500": _bars(list(bench)), "XAUUSD": _bars(gold)}, NOW)
    assert b["symbols"]["XAUUSD"]["beta"] == pytest.approx(2.0, rel=1e-6)
    assert b["symbols"]["XAUUSD"]["corr"] == pytest.approx(1.0, rel=1e-6)
    assert b["symbols"]["USOIL"]["status"] == "UNMEASURED"


def test_curve_regime_and_ledger() -> None:
    rep = ms.build(now=NOW, series=_series(), charts={}, vol_rows=_vol_rows())
    gc = rep["curve"]
    assert gc["slope_10y3m"] == pytest.approx(4.1 - 4.5, abs=1e-6)
    assert gc["inverted_10y3m"] is True
    assert gc["curvature"] == pytest.approx(2 * 3.9 - 4.0 - 4.1, abs=1e-6)
    # the vol indices come through Yahoo's chart API: held; FRED's VIX/VIX3M carry the key
    assert rep["terms"]["vol"]["gauntlet"] == "HELD"
    assert rep["regime"] == "UNMEASURED" and rep["regime_source"] == "fred:VIXCLS+VXVCLS"
    ser = {**_series(), "VIXCLS": [(d, 15.0 + (i % 7)) for i, d in enumerate(_days(300))],
           "VXVCLS": [(d, 18.0) for d in _days(300)]}
    ser["VIXCLS"][-2] = (ser["VIXCLS"][-2][0], 30.0)
    fr = ms.build(now=NOW, series=ser, charts={}, vol_rows=_vol_rows())
    assert fr["regime"] == "vol_backwardation_high"
    assert rep["terms"]["curve"]["gauntlet"] == "admitted"
    assert rep["option_chains"]["status"] == "EXTERNALLY_BLOCKED"
    obs = ms.observations(rep, NOW)
    assert obs and all(sc.defects(o) == [] for o in obs)
    assert {o.sensor_id for o in obs} >= {"market:implied_vol", "market:vrp",
                                          "market:vol_term", "market:ust_curve"}
    assert all(o.authority == "NONE" for o in obs)
    src = {o.sensor_id: o.source_id for o in obs}
    assert src["market:implied_vol"] == ms.VOL_SOURCE and src["market:ust_curve"] == "fred:h15"


def test_terms_gate_on_vol_sources_and_chains_routed_to_discovery(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Audit #211 should-fix: the J sources pass the terms gate; chains go to discovery."""
    from macro import release_vintages as rv
    monkeypatch.setattr(rv, "CLEARANCES", tmp_path / "clear.json")
    assert ms.terms(ms.VOL_SOURCE)["gauntlet"] == "HELD"
    (tmp_path / "clear.json").write_text(json.dumps(
        {k: {"status": "CLEARED", "by": "t", "terms_url": "https://example.test/terms",
              "terms_quote": "machine use permitted"}
         for k in ("yahoo", "cboe")}))
    rep = ms.build(now=NOW, series=_series(), charts={}, vol_rows=_vol_rows())
    assert rep["regime"] == "vol_backwardation_high"
    req = tmp_path / "endpoints_world_sensor.json"
    req.write_text(json.dumps({"endpoints": [{"id": "other", "url": "u"}]}))
    got = ms.route_chains_to_discovery(req)
    assert got["routed"] == "discovery" and got["candidate_id"] == "option_chains_per_strike"
    ms.route_chains_to_discovery(req)                    # idempotent: one row, others kept
    rows = json.loads(req.read_text())["endpoints"]
    assert [r["id"] for r in rows] == ["other", "option_chains_per_strike"]
    assert rows[1]["machine_use_allowed"] is None and "UNCONFIRMED" in rows[1]["terms"]


def _weekly(years: int, bump: float) -> list[tuple[str, float]]:
    """Crude stocks that build 1,000 kbbl every week, except the final week builds `bump`."""
    start = date(2026, 10, 2) - timedelta(weeks=52 * years)
    rows, level = [], 400_000.0
    n = 52 * years
    for i in range(n + 1):
        level += 1000.0 if i < n else bump
        rows.append(((start + timedelta(weeks=i)).isoformat(), level))
    return rows


def test_physical_state_seasonal_surprise_and_clock() -> None:
    assert ps.knowable("2026-10-02") == datetime(2026, 10, 7, 14, 30, tzinfo=UTC)
    rep = ps.build(now=datetime(2026, 10, 9, tzinfo=UTC),
                   series={"WCESTUS1": _weekly(7, 4000.0)})
    crude = rep["series"]["WCESTUS1"]
    assert crude["status"] == "MEASURED" and crude["week_end"] == "2026-10-02"
    assert crude["seasonal_expected"] == pytest.approx(1000.0)
    assert crude["surprise"] == pytest.approx(3000.0)
    assert rep["series"]["WGTSTUS1"]["status"] == "UNMEASURED"
    rows = [r for r in rep["store_rows"] if r["reference_period"] == "2026-10-02"]
    assert rows[0]["actual"] == 4.0 and rows[0]["consensus"] == 1.0
    assert rows[0]["instruments"] == ["USOIL", "UKOIL"]
    assert rows[0]["at"] == "2026-10-07T14:30:00+00:00"
    assert rows[0]["clock"] == ps.CLOCK
    # not yet knowable: the week is invisible
    early = ps.build(now=datetime(2026, 10, 7, 14, 0, tzinfo=UTC),
                     series={"WCESTUS1": _weekly(7, 4000.0)})
    assert early["series"]["WCESTUS1"]["week_end"] == "2026-09-25"
    joined = es.join_sides(rep["store_rows"])
    assert joined and all(j["joined"] == "single_document" for j in joined)
    obs = ps.observations(rep, datetime(2026, 10, 9, tzinfo=UTC))
    assert len(obs) == 1 and sc.defects(obs[0]) == []
    assert obs[0].seasonal_expected == pytest.approx(1000.0)



def test_eia_clock_follows_the_release_calendar_and_holiday_shifts() -> None:
    """Audit #211 item 1: Wednesday 10:30 ET, Thursday 12:00 ET after a Mon-Wed federal holiday,
    Friday 12:00 ET after a Christmas Wednesday; never the old blanket +1 day."""
    et = ZoneInfo("America/New_York")

    def at(y: int, m: int, d: int, hh: int, mm: int) -> datetime:
        return datetime(y, m, d, hh, mm, tzinfo=et).astimezone(UTC)

    assert ps.knowable("2026-09-25") == at(2026, 9, 30, 10, 30)          # ordinary week
    assert ps.knowable("2026-09-04") == at(2026, 9, 10, 12, 0)           # Labor Day Monday
    assert ps.knowable("2026-05-22") == at(2026, 5, 28, 12, 0)           # Memorial Day
    assert ps.knowable("2026-10-09") == at(2026, 10, 15, 12, 0)          # Columbus Day
    assert ps.knowable("2024-12-20") == at(2024, 12, 27, 12, 0)          # Christmas Wednesday
    assert ps.knowable("2024-06-14") == at(2024, 6, 20, 12, 0)           # Juneteenth Wednesday
    assert ps.knowable("2026-11-20") == at(2026, 11, 25, 10, 30)         # Thanksgiving week
    # Christmas 2025 fell on the Thursday: the print came 126.5 h after the Wednesday, so the
    # stamp is a conservative bound that is never earlier than that
    wed = at(2025, 12, 24, 10, 30)
    assert ps.knowable("2025-12-19") >= wed + timedelta(hours=126.5)
    # DST: the same 10:30 ET is 14:30 UTC in summer and 15:30 UTC in winter
    assert ps.knowable("2026-01-09").hour == 15 and ps.knowable("2026-07-10").hour == 14
    ps.RELEASE_OVERRIDES["2026-07-10"] = "2026-07-16T12:00"
    try:
        assert ps.release_at("2026-07-10") == (at(2026, 7, 16, 12, 0), "announced override")
    finally:
        ps.RELEASE_OVERRIDES.pop("2026-07-10")


def test_seasonal_norm_wraps_the_year_and_gives_iso_week_53_a_norm() -> None:
    """Audit #211 should-fix: week 1 neighbours week 52, and ISO week 53 (2026-12-31 ends one)
    finds its same-date neighbours in every prior year."""
    start = date(2019, 1, 4)
    rows, level = [], 400_000.0
    d = start
    while d <= date(2027, 1, 8):
        level += 1000.0
        rows.append((d.isoformat(), level))
        d += timedelta(weeks=1)
    wk = {w["week_end"]: w for w in ps.weeks(rows)}
    assert date(2027, 1, 1).isocalendar()[1] == 53
    for day in ("2027-01-01", "2026-01-02", "2025-12-26"):
        assert wk[day]["seasonal_expected"] == pytest.approx(1000.0), day


def test_donor_terminal_provider_cards_are_priced(tmp_path: Path,
                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    donors = tmp_path / "provider_donors" / "openterminal"
    donors.mkdir(parents=True)
    (donors / "providers_20261006.json").write_text(json.dumps({"providers": [
        {"id": "cboe_vix", "name": "CBOE VIX history", "url": "https://cdn.cboe.com/x.csv",
         "targets": ["US500"], "observable": "implied volatility index", "cadence": "daily",
         "access": "public", "licence": "UNMEASURED"},
        {"id": "paid_feed", "name": "Paid quotes", "access": "paid"}]}))
    monkeypatch.setattr(se, "DONORS", tmp_path / "provider_donors")
    monkeypatch.setattr(se, "FOUND", tmp_path / "none")
    rows = {r["id"]: r for r in se.price(se._derived(), {}, {})}
    assert {"donor:openterminal:cboe_vix", "donor:openterminal:paid_feed"} <= set(rows)
    assert rows["donor:openterminal:cboe_vix"]["donor"] == "openterminal"
    assert rows["donor:openterminal:paid_feed"]["access"] == "paid"


def test_absent_provider_cards_are_unmeasured_and_gated_cards_never_proposed(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Audit #211 item 2: no card file is UNMEASURED (never an empty success); paid and
    machine_use_allowed:false cards stay priced but are never proposed for acquisition."""
    monkeypatch.setattr(se, "DONORS", tmp_path / "provider_donors")
    monkeypatch.setattr(se, "FOUND", tmp_path / "none")
    monkeypatch.setattr(se, "REGISTRY", tmp_path / "none.json")
    monkeypatch.setattr(se, "STATE", tmp_path / "state.json")
    absent = se.provider_cards()
    assert absent["status"] == "UNMEASURED" and "no provider card" in absent["why"]
    assert se.build()["provider_cards"]["status"] == "UNMEASURED"
    donors = tmp_path / "provider_donors" / "openterminal"
    donors.mkdir(parents=True)
    (donors / "providers_20261006.json").write_text("{not json")
    assert se.provider_cards()["status"] == "UNMEASURED"
    (donors / "providers_20261007.json").write_text(json.dumps({"providers": [
        {"id": "open", "targets": ["US500"], "access": "public", "machine_use_allowed": True},
        {"id": "unread", "targets": ["US500"], "access": "public"},
        {"id": "paid_feed", "targets": ["US500"], "access": "paid"},
        {"id": "no_machine", "targets": ["XAUUSD"], "access": "public",
         "machine_use_allowed": False}]}))
    cards = se.provider_cards()
    assert cards["status"] == "MEASURED" and cards["providers"] == 4
    rep = se.build()
    ids = {r["id"] for r in rep["proposals"]}
    assert "donor:openterminal:open" in ids
    assert not ids & {"donor:openterminal:paid_feed", "donor:openterminal:no_machine",
                      "donor:openterminal:unread"}
    assert rep["n_gated_from_proposals"] == 3
    assert "donor:openterminal:unread" in rep["terms_review"]   # fail closed, still visible
    gated = {r["id"]: r["acquisition_gate"] for r in rep["rows"]}
    assert "paid" in gated["donor:openterminal:paid_feed"]
    assert "machine_use_allowed" in gated["donor:openterminal:no_machine"]


def test_store_reads_only_the_current_eia_clock(tmp_path: Path,
                                                monkeypatch: pytest.MonkeyPatch) -> None:
    """Rows written under the old +1 day clock are superseded, not double counted."""
    monkeypatch.setattr(es, "STORE", tmp_path / "store.jsonl")
    base = {"release": "EIA crude oil stocks ex SPR w/w|seasonal5y", "actual": 4.0,
            "consensus": 1.0, "provides": "both", "kind": "inventory_surprise",
            "instruments": ["USOIL"], "source_id": "fred:WCESTUS1",
            "reference_period": "2026-09-25"}
    old = {**base, "period": "2026-10-01", "at": "2026-10-01T14:30:00+00:00"}
    new = {**base, "period": "2026-09-30", "at": "2026-09-30T14:30:00+00:00",
           "clock": ps.CLOCK}
    stored, _ = es.merge_store([old, new], now=datetime(2026, 10, 6, tzinfo=UTC))
    es.STORE.write_text("".join(json.dumps(r) + "\n" for r in stored))
    pairs, status = es.store_pairs(30, datetime(2026, 10, 6, tzinfo=UTC))
    assert [p["at"] for p in pairs] == ["2026-09-30T14:30:00+00:00"]
    assert status["superseded_clock"] == 1
