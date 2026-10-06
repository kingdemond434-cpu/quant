"""Market-state engines (vol term structure, implied vs realised, curve, beta) and the EIA
physical states, PIT and directionless. Everything is synthetic; nothing touches the network."""
from __future__ import annotations

import json
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

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
    assert rep["regime"] == "vol_backwardation_high"
    assert rep["option_chains"]["status"] == "EXTERNALLY_BLOCKED"
    obs = ms.observations(rep, NOW)
    assert obs and all(sc.defects(o) == [] for o in obs)
    assert {o.sensor_id for o in obs} >= {"market:implied_vol", "market:vrp",
                                          "market:vol_term", "market:ust_curve"}
    assert all(o.authority == "NONE" for o in obs)


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
    assert ps.knowable("2026-10-02") == datetime(2026, 10, 8, 14, 30, tzinfo=UTC)
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
    assert rows[0]["at"] == "2026-10-08T14:30:00+00:00"
    # not yet knowable: the week is invisible
    early = ps.build(now=datetime(2026, 10, 8, 14, 0, tzinfo=UTC),
                     series={"WCESTUS1": _weekly(7, 4000.0)})
    assert early["series"]["WCESTUS1"]["week_end"] == "2026-09-25"
    joined = es.join_sides(rep["store_rows"])
    assert joined and all(j["joined"] == "single_document" for j in joined)
    obs = ps.observations(rep, datetime(2026, 10, 9, tzinfo=UTC))
    assert len(obs) == 1 and sc.defects(obs[0]) == []
    assert obs[0].seasonal_expected == pytest.approx(1000.0)


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
