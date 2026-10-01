"""Crop-belt weather: POWER parsed, first prints kept, seasons judged against prior years only."""
from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import numpy as np
import pandas as pd

from libs.data import crop_weather as cw
from libs.data import pit_certificate as pit
from libs.data import repo_mined_feeds as rmf


def _payload(start: date, end: date, *, lat: float, bump: float = 0.0,
             missing_after: date | None = None) -> bytes:
    par: dict[str, dict[str, float]] = {p: {} for p in cw.PARAMS}
    d = start
    while d <= end:
        k = f"{d:%Y%m%d}"
        doy = d.timetuple().tm_yday
        season = np.sin(2 * np.pi * doy / 365.25)
        noise = ((d.toordinal() * 7919) % 97) / 97.0
        gone = missing_after is not None and d > missing_after
        par["T2M_MIN"][k] = cw.MISSING if gone else 10 + 8 * season + 3 * noise + bump - lat / 50
        par["T2M_MAX"][k] = cw.MISSING if gone else 25 + 8 * season + 4 * noise + bump
        par["PRECTOTCORR"][k] = cw.MISSING if gone else max(0.0, 3 + 3 * season + 5 * noise - 3)
        d += timedelta(days=1)
    return json.dumps({"properties": {"parameter": par}}).encode()


def _fetcher(calls: list[str], **kw):
    def fetch(u: str):
        calls.append(u)
        q = parse_qs(urlparse(u).query)
        start = datetime.strptime(q["start"][0], "%Y%m%d").date()
        end = datetime.strptime(q["end"][0], "%Y%m%d").date()
        return _payload(start, end, lat=float(q["latitude"][0]), **kw), "application/json"
    return fetch


def test_parse_drops_the_padded_days():
    raw = _payload(date(2026, 9, 1), date(2026, 9, 10), lat=0.0, missing_after=date(2026, 9, 7))
    got = cw.parse(raw)
    assert sorted(got) == [f"2026-09-0{i}" for i in range(1, 8)]
    assert all(len(v) == 3 for v in got.values())


def test_every_soft_and_grain_cfd_has_a_belt():
    covered = {s for c in cw.CROPS for s in c.symbols}
    assert covered == {"COFARA", "COFROB", "USCOCOA", "UKCOCOA", "SUGAR", "SUGARRAW", "CORN",
                       "WHEAT", "SOYBEAN", "COTTON", "OJ"}
    assert cw.symbols_for("cropwx_cocoa_prcp30_z") == ("USCOCOA", "UKCOCOA")


def test_first_print_is_never_rewritten(tmp_path):
    now = datetime(2026, 9, 20, tzinfo=UTC)
    calls: list[str] = []
    cw.ingest(tmp_path, fetch=_fetcher(calls), now=now, per_pass=100)
    assert calls and "community=AG" in calls[0]
    held = json.loads((tmp_path / "us_iowa.json").read_text())
    first = held["days"]["1991-01-05"]
    # the source restates history; the ledger keeps what it first saw
    cw.ingest(tmp_path, fetch=_fetcher([], bump=5.0), now=now + timedelta(days=3), per_pass=100)
    again = json.loads((tmp_path / "us_iowa.json").read_text())
    assert again["days"]["1991-01-05"] == first
    assert len(again["days"]) > len(held["days"])


def _backfilled(tmp_path, now: datetime) -> None:
    for k in range(6):                                  # a 35-year history over chunked passes
        cw.ingest(tmp_path, fetch=_fetcher([]), now=now + timedelta(minutes=k), per_pass=100)


def test_frames_are_stamped_and_causal(tmp_path):
    now = datetime(2026, 9, 20, tzinfo=UTC)
    _backfilled(tmp_path, now)
    fr = cw.frames(tmp_path, now + timedelta(hours=1))
    for name in ("cropwx_coffee_arabica_frost7", "cropwx_corn_heat7", "cropwx_cocoa_prcp30_z",
                 "cropwx_oj_tmin"):
        assert name in fr and len(fr[name]) > 1000, name
    f = fr["cropwx_corn_tmax"]
    lag = f["available_time"] - f.index
    assert lag.min() >= cw.LAG
    assert lag[f.index < pd.Timestamp("2020-01-01", tz="UTC")].max() == cw.SETTLE
    z = fr["cropwx_cocoa_prcp30_z"]
    assert z.index.min() >= pd.Timestamp("1996-01-01", tz="UTC")   # five prior years first


def test_seasonal_z_reads_only_prior_years():
    idx = pd.date_range("2000-01-01", "2012-12-31", freq="D", tz="UTC")
    s = pd.Series(np.sin(2 * np.pi * idx.dayofyear / 365.25), index=idx)
    z1 = cw.seasonal_z(s)
    s2 = s.copy()
    s2[s2.index >= "2011-01-01"] += 50.0                 # a shock in the future
    z2 = cw.seasonal_z(s2)
    early = z1.index < "2011-01-01"
    pd.testing.assert_series_equal(z1[early], z2[early])
    assert z2["2011-06-01"] > 10


def test_registers_with_authority_on_the_second_pass(tmp_path):
    now = datetime(2026, 9, 20, tzinfo=UTC)
    _backfilled(tmp_path / "crop_weather", now)
    reg: dict = {"by_url": {}, "series": {}}
    for k in range(2):
        rep = rmf.absorb_crop_weather(reg, tmp_path, fetch=_fetcher([]), certify=pit.certify,
                                      write_certificate=lambda c: None,
                                      now=now + timedelta(hours=1 + k))
    assert "cropwx_sugar_prcp30" in rep["new_series"]
    row = reg["series"]["cropwx_sugar_prcp30"]
    assert row["pit_authority"] is True, row["pit_blocking"]
    assert "SUGARRAW" in row["mt5_use"]
    assert reg["by_url"][cw.API]["status"] == "SUCCESS"


def test_unreachable_is_named(tmp_path):
    rep = cw.ingest(tmp_path, fetch=lambda u: (None, "unreachable"), per_pass=2)
    assert rep["status"] == "UNREACHABLE" and len(rep["refused"]) == 2
