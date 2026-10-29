"""news_hawkes (ROMAN-0826, ROMAN-0830) on SYNTHETIC events and bars only.

Planted: a simulated Hawkes news stream whose live excess intensity scales the next broker day's
range -> the forecast contract is GAIN; the same stream against independent ranges is not.
Planted: payroll releases whose follow-on news count scales the vol of the next three days ->
the post-NFP persistence contract is GAIN; with flat vol it is not."""
from __future__ import annotations

import math
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_ROOT), str(_DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from macro import news_hawkes as nh  # noqa: E402

from libs.quant_models import hawkes  # noqa: E402

NOW = datetime(2024, 1, 1, 21, 30, tzinfo=UTC)
TRUE = hawkes.HawkesParams.univariate(0.02, 0.6 * math.log(2) / 12.0, math.log(2) / 12.0)


def _news(fam: str = "war_escalation", days: int = 1300, seed: int = 1) -> list[nh.Event]:
    start = NOW - timedelta(days=days)
    t, _ = hawkes.simulate(TRUE, days * 24.0, seed=seed)
    return [nh.Event(start + timedelta(hours=float(h)), fam, 0) for h in t]


def _daily(events: list[nh.Event], planted: bool, seed: int, days: int = 900
           ) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    times = np.asarray([nh._h(e.at) for e in events])
    dates = [d.date() for d in pd.bdate_range(NOW - timedelta(days=days), NOW - timedelta(days=1))]
    g = np.asarray([nh._h(datetime(d.year, d.month, d.day, 21, tzinfo=UTC) - timedelta(days=1))
                    for d in dates])
    ex = hawkes.intensity_at(TRUE, times, g)[:, 0] - TRUE.mu[0]
    out = {}
    for sym in nh.FAMILY_SYMBOLS["war_escalation"]:
        mult = 1.0 + 4.0 * ex / TRUE.mu[0] if planted else np.ones(len(dates))
        var = 1e-4 * mult * rng.exponential(1.0, len(dates))
        rng_log = np.sqrt(var * 4 * math.log(2))
        close = 100 * np.exp(np.cumsum(rng.normal(0, 1, len(dates)) * np.sqrt(var)))
        out[sym] = pd.DataFrame({"open": close, "high": close * np.exp(rng_log / 2),
                                 "low": close * np.exp(-rng_log / 2), "close": close},
                                index=pd.to_datetime(dates))
    return out


@pytest.mark.parametrize("planted", [True, False])
def test_intensity_forecasts_range_only_when_planted(planted: bool) -> None:
    news = _news()
    daily = _daily(news, planted, seed=3)
    rep = nh.build(NOW, news=news, releases=[], daily=daily, hourly={}, history_d=900,
                   window_d=365, refit_d=90)
    war = [c for c in rep["contracts"] if c.get("family") == "war_escalation"
           and c["target"] == "range_var"]
    assert len(war) == 3
    verdicts = {c["verdict"] for c in war}
    if planted:
        assert verdicts == {"GAIN"}
    else:
        assert "GAIN" not in verdicts
    # families with no events are UNMEASURED, never zero
    infl = [c for c in rep["contracts"] if c.get("family") == "inflation_surprise"]
    assert infl and all(c["verdict"] == "UNMEASURED" for c in infl)
    # fitted branching is near the truth and the half-life is in hours
    st = rep["latest"]["war_escalation"]
    assert st["branching_ratio"] == pytest.approx(0.6, abs=0.15)
    assert st["half_life_h"] == pytest.approx(12.0, rel=0.5)


def test_series_rows_are_point_in_time() -> None:
    news = _news(days=600)
    grid = nh.eval_grid(NOW, 120)
    full = nh.fit_family("war_escalation", news, grid, window_d=365, refit_d=30)
    cut_at = grid[60]
    early = [e for e in news if e.at < cut_at]
    part = nh.fit_family("war_escalation", early, grid[:61], window_d=365, refit_d=30)
    # every value up to the cut is identical whether or not later events exist
    np.testing.assert_allclose(full.intensity[:61], part.intensity, rtol=1e-10)
    assert all(g.hour == 21 for g in grid)


def _nfp_world(planted: bool, seed: int = 5) -> tuple[nh.FamilyPath, list[datetime],
                                                      dict[str, pd.DataFrame]]:
    rng = np.random.default_rng(seed)
    start = datetime(2014, 1, 1, tzinfo=UTC)
    nfps = [datetime(2014 + m // 12, m % 12 + 1, 6, 13, 30, tzinfo=UTC) for m in range(118)]
    events: list[nh.Event] = []
    follow = {}
    for tau in nfps:
        events.append(nh.Event(tau, "labour_surprise", 1, nh.NFP_TITLE))
        k = int(rng.integers(0, 9))
        follow[tau] = k
        for h in np.sort(rng.uniform(1.0, 22.0, k)):
            events.append(nh.Event(tau + timedelta(hours=float(h)), "labour_surprise", 0))
    for h in np.sort(rng.uniform(0, 10 * 365 * 24.0, 600)):
        events.append(nh.Event(start + timedelta(hours=float(h)), "labour_surprise", 0))
    grid = [start + timedelta(days=200 + i, hours=21) for i in range(0, 3400)]
    path = nh.fit_family("labour_surprise", events, grid, window_d=365, refit_d=180)
    idx = pd.date_range(start, start + timedelta(days=3700), freq="h", tz="UTC")
    vol = np.full(idx.size, 1e-3)
    if planted:
        for tau, k in follow.items():
            lo = idx.searchsorted(pd.Timestamp(tau + timedelta(hours=24)))
            vol[lo:lo + 72] *= 1.0 + 0.25 * k
    close = 100 * np.exp(np.cumsum(rng.normal(0, 1, idx.size) * vol))
    frame = pd.DataFrame({"open": close, "high": close, "low": close, "close": close}, index=idx)
    usable = [t for t in nfps if t >= grid[0]]
    return path, usable, {"EURUSD": frame}


@pytest.mark.parametrize("planted", [True, False])
def test_post_nfp_persistence_contract(planted: bool) -> None:
    path, nfps, hourly = _nfp_world(planted)
    rows = nh.post_nfp_rows(path, nfps, hourly)
    assert len(rows) >= 100
    for r in rows:   # persistence is knowable 24h after the release, never before
        assert r["available_time"] > r["nfp_at"]
    c = nh.nfp_contract(rows)
    assert c["cards"] == ["ROMAN-0830"]
    if planted:
        assert c["verdict"] == "GAIN"
    else:
        assert c["verdict"] != "GAIN"


def test_too_few_releases_is_unmeasured() -> None:
    c = nh.nfp_contract([])
    assert c["verdict"] == "UNMEASURED"


def test_ledger_and_calendar_intake(tmp_path: Path) -> None:
    import json
    obs = tmp_path / "observations"
    obs.mkdir()
    rows = [
        {"kind": "document", "knowable_at": "2023-12-01T10:00:00+00:00",
         "knowable_basis": "printed_stamp",
         "attributes": {"event_kind": "war_escalation", "event_id": "e1", "copy_of": ""}},
        {"kind": "document", "knowable_at": "2023-12-01T09:00:00+00:00",
         "knowable_basis": "printed_stamp",
         "attributes": {"event_kind": "war_escalation", "event_id": "e1", "copy_of": ""}},
        {"kind": "document", "knowable_at": "2023-12-01T11:00:00+00:00",
         "knowable_basis": "printed_stamp",
         "attributes": {"event_kind": "war_escalation", "event_id": "e2", "copy_of": "x"}},
        {"kind": "document", "knowable_at": "UNMEASURED", "knowable_basis": "UNMEASURED",
         "attributes": {"event_kind": "labour_surprise", "event_id": "e3"}},
        {"kind": "document", "knowable_at": "2023-12-01T12:00:00+00:00",
         "knowable_basis": "printed_stamp",
         "attributes": {"event_kind": "central_bank_surprise", "event_id": "e4"}},
    ]
    (obs / "2023-12-01.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    evs = nh.ledger_events(tmp_path, now=NOW)
    got = sorted((e.family, e.at.hour) for e in evs)
    assert got == [("central_bank", 12), ("war_escalation", 9)]
    cal = tmp_path / "cal"
    cal.mkdir()
    (cal / "discoveries_x.json").write_text(json.dumps({"discoveries": [
        {"title": nh.NFP_TITLE, "event_date": "2023-12-08T08:30:00-05:00",
         "captured_at": "2023-12-07T00:00:00+00:00", "forecast": "180K"},
        {"title": "USD Unemployment Rate", "event_date": "2023-12-08T08:30:00-05:00",
         "captured_at": "2023-12-07T00:00:00+00:00", "forecast": "3.9%"},
        {"title": "USD Federal Funds Rate", "event_date": "2023-12-13T14:00:00-05:00",
         "captured_at": "2023-12-07T00:00:00+00:00"},
        {"title": "USD CPI m/m", "event_date": "2024-02-13T08:30:00-05:00",
         "captured_at": "2023-12-07T00:00:00+00:00"},
    ]}))
    rel = nh.release_events(NOW, vintages=cal, alfred=tmp_path / "none")
    fams = sorted((e.family, e.label) for e in rel)
    assert fams == [("central_bank", "USD Federal Funds Rate"),
                    ("labour_surprise", nh.NFP_TITLE)]
    assert nh.nfp_instants(rel) == [datetime(2023, 12, 8, 13, 30, tzinfo=UTC)]
