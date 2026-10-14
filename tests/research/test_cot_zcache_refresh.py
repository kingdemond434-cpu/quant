"""The COT z cache is derived from RAW net positions only, and a z-only cache is rebuilt.

THE DEFECT (2026-10-14). `scripts/refresh_cot_zcache.py` banked 52-week z-scores, then joined
those z values with the new weeks' RAW net positioning and took a rolling z over the mixture:
an appended week was a contract count standardised against a window of z-scores. These tests
pin the repair with no network: `_fetch` is replaced by fixtures.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _load():
    spec = importlib.util.spec_from_file_location(
        "refresh_cot_zcache_under_test", _ROOT / "scripts" / "refresh_cot_zcache.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _rows(mod, dates, base=50_000.0):
    """CFTC-shaped rows for every mapped code, net = base + 1000*i (+ a per-code offset)."""
    out = []
    for i, d in enumerate(dates):
        for j, code in enumerate(mod.CODES.values()):
            net = base + 1000.0 * i + 37.0 * j + (5000.0 if i % 3 == 0 else 0.0)
            out.append({"cftc_contract_market_code": code,
                        "report_date_as_yyyy_mm_dd": d.strftime("%Y-%m-%dT00:00:00.000"),
                        "noncomm_positions_long_all": str(net + 10_000.0),
                        "noncomm_positions_short_all": "10000"})
    return out


def _point(mod, tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "CACHE", tmp_path / "cot_zcache.parquet")
    monkeypatch.setattr(mod, "NETCACHE", tmp_path / "cot_netcache.parquet")


def test_z_is_computed_only_from_raw_values():
    mod = _load()
    dates = pd.date_range("2020-01-07", periods=80, freq="W-TUE", tz="UTC")
    raw = mod.raw_nets(_rows(mod, dates))
    assert set(raw.columns) == set(mod.CODES)
    # Inverted symbols carry the sign flip on the RAW nets.
    assert (raw["USDJPY"] < 0).all() and (raw["EURUSD"] > 0).all()

    z = mod.zscores_from_raw(raw)
    s = raw["EURUSD"]
    roll = s.rolling(mod.ZWIN, min_periods=mod.MIN_PERIODS)
    want = ((s - roll.mean()) / roll.std(ddof=0)).dropna()
    got = z["EURUSD"].reindex(want.index)
    assert np.allclose(got.to_numpy(), want.to_numpy())
    # Daily forward-fill between reports, keyed on the report date (no release lag here).
    assert (z.index[1] - z.index[0]) == pd.Timedelta(days=1)
    tue = want.index[-2]
    assert z.loc[tue + pd.Timedelta(days=3), "EURUSD"] == pytest.approx(want.loc[tue])
    # A z-score is O(1); a raw net standardised against z values would be O(1e4).
    assert z.abs().max().max() < 10


def test_incremental_refresh_appends_raw_and_rederives_z(tmp_path, monkeypatch):
    mod = _load()
    _point(mod, tmp_path, monkeypatch)
    dates = pd.date_range("2020-01-07", periods=90, freq="W-TUE", tz="UTC")
    full = _rows(mod, dates)
    n_codes = len(mod.CODES)
    banked = mod.raw_nets(full[: 80 * n_codes])
    banked.to_parquet(mod.NETCACHE)
    mod.zscores_from_raw(banked).to_parquet(mod.CACHE)

    monkeypatch.setattr(mod, "_fetch", lambda since: [
        r for r in full if r["report_date_as_yyyy_mm_dd"][:10] > since])
    assert mod.main() == 0

    raw_after = pd.read_parquet(mod.NETCACHE)
    z_after = pd.read_parquet(mod.CACHE)
    assert len(raw_after) == 90
    expected = mod.zscores_from_raw(mod.raw_nets(full))
    pd.testing.assert_frame_equal(z_after, expected, check_freq=False)
    assert z_after.abs().max().max() < 10


def test_a_z_only_cache_is_rebuilt_from_source_never_mixed(tmp_path, monkeypatch):
    mod = _load()
    _point(mod, tmp_path, monkeypatch)
    dates = pd.date_range("2020-01-07", periods=90, freq="W-TUE", tz="UTC")
    full = _rows(mod, dates)
    # The legacy shape: z values only, daily, no raw history beside it.
    old_z = mod.zscores_from_raw(mod.raw_nets(full[: 80 * len(mod.CODES)]))
    old_z.to_parquet(mod.CACHE)
    assert not mod.NETCACHE.exists()
    assert mod.needs_rebuild(old_z, None)

    seen: list[str] = []

    def fake_fetch(since):
        seen.append(since)
        return [r for r in full if r["report_date_as_yyyy_mm_dd"][:10] > since]

    monkeypatch.setattr(mod, "_fetch", fake_fetch)
    assert mod.main() == 0
    assert seen == [mod.REBUILD_SINCE], "a z-only cache must be rebuilt from source"
    z_after = pd.read_parquet(mod.CACHE)
    pd.testing.assert_frame_equal(z_after, mod.zscores_from_raw(mod.raw_nets(full)),
                                  check_freq=False)
    assert mod.NETCACHE.exists()


def test_a_short_rebuild_fetch_leaves_the_banked_files_untouched(tmp_path, monkeypatch):
    mod = _load()
    _point(mod, tmp_path, monkeypatch)
    dates = pd.date_range("2020-01-07", periods=60, freq="W-TUE", tz="UTC")
    full = _rows(mod, dates)
    old_z = mod.zscores_from_raw(mod.raw_nets(full))
    old_z.to_parquet(mod.CACHE)
    before = mod.CACHE.read_bytes()
    # The fetch lost one symbol's code: refuse, never write a partial or mixed cache.
    drop = mod.CODES["XTIUSD"]
    monkeypatch.setattr(mod, "_fetch", lambda since: [
        r for r in full if r["cftc_contract_market_code"] != drop])
    assert mod.main() == 1
    assert mod.CACHE.read_bytes() == before
    assert not mod.NETCACHE.exists()


def test_the_refresh_no_longer_mixes_banked_z_with_raw():
    src = (_ROOT / "scripts" / "refresh_cot_zcache.py").read_text(encoding="utf-8")
    assert "hist_net = cache.copy()" not in src
    assert "out.loc[fresh_idx] = z.loc[fresh_idx]" not in src


def test_xtiusd_maps_to_the_nymex_wti_code():
    from libs.data.cot_source import COT_MAP

    assert COT_MAP["XTIUSD"][0] == "067651"
    assert _load().CODES["XTIUSD"] == "067651"
