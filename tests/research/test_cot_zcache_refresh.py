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


# ------------------------------------------------- audit COT_AXIS_DEEPENING MF2 + should-fixes


def test_the_refresh_stamps_the_definition_version(tmp_path, monkeypatch):
    from libs.data.cot_source import COT_ZCACHE_VERSION, zcache_version

    mod = _load()
    _point(mod, tmp_path, monkeypatch)
    dates = pd.date_range("2020-01-07", periods=70, freq="W-TUE", tz="UTC")
    full = _rows(mod, dates)
    monkeypatch.setattr(mod, "_fetch", lambda since: [
        r for r in full if r["report_date_as_yyyy_mm_dd"][:10] > since])
    assert mod.main() == 0
    assert zcache_version(mod.CACHE) == COT_ZCACHE_VERSION
    # The stamp travels inside the file and the frame still reads back unchanged.
    pd.testing.assert_frame_equal(pd.read_parquet(mod.CACHE),
                                  mod.zscores_from_raw(mod.raw_nets(full)), check_freq=False)


def test_an_unstamped_cache_is_rederived_even_when_no_new_week_arrived(tmp_path, monkeypatch):
    from libs.data.cot_source import COT_ZCACHE_VERSION, zcache_version

    mod = _load()
    _point(mod, tmp_path, monkeypatch)
    dates = pd.date_range("2020-01-07", periods=70, freq="W-TUE", tz="UTC")
    raw = mod.raw_nets(_rows(mod, dates))
    raw.to_parquet(mod.NETCACHE)
    (raw * 0.0).to_parquet(mod.CACHE)               # a version-1 file: no stamp, wrong values
    assert zcache_version(mod.CACHE) is None
    monkeypatch.setattr(mod, "_fetch", lambda since: [])
    assert mod.main() == 0
    assert zcache_version(mod.CACHE) == COT_ZCACHE_VERSION
    pd.testing.assert_frame_equal(pd.read_parquet(mod.CACHE), mod.zscores_from_raw(raw),
                                  check_freq=False)
    # Stamped and current: a pass with nothing new writes nothing.
    before = mod.CACHE.read_bytes()
    assert mod.main() == 0
    assert mod.CACHE.read_bytes() == before


def test_needs_rebuild_and_the_refusal_normalise_naive_and_aware_indexes(tmp_path, monkeypatch):
    """SF (probed TypeError): a banked cache with a NAIVE index against a UTC fetch."""
    mod = _load()
    _point(mod, tmp_path, monkeypatch)
    dates = pd.date_range("2020-01-07", periods=60, freq="W-TUE", tz="UTC")
    full = _rows(mod, dates)
    raw = mod.raw_nets(full)
    naive_z = mod.zscores_from_raw(raw)
    naive_z.index = naive_z.index.tz_localize(None)
    assert mod.needs_rebuild(naive_z, raw) is None          # no TypeError, same start
    late_raw = raw.iloc[20:]
    assert mod.needs_rebuild(naive_z, late_raw) == "raw history starts after the z cache"
    naive_raw = raw.copy()
    naive_raw.index = naive_raw.index.tz_localize(None)
    assert mod.needs_rebuild(mod.zscores_from_raw(raw), naive_raw) is None
    # The rebuild refusal compares the same way: a short (late) fetch against a naive cache.
    naive_z.to_parquet(mod.CACHE)
    before = mod.CACHE.read_bytes()
    late = [r for r in full if r["report_date_as_yyyy_mm_dd"][:10] > "2020-06-01"]
    monkeypatch.setattr(mod, "_fetch", lambda since: late)
    assert mod.main() == 1
    assert mod.CACHE.read_bytes() == before


def test_the_fetch_declares_an_honest_user_agent():
    ua = _load().UA["User-Agent"]
    assert "Mozilla" not in ua
    assert "github.com/kingdemond434-cpu/quant" in ua


def _family_source() -> str:
    import inspect

    from mt5desk.families_orthogonal import family_cot_positioning
    return inspect.getsource(family_cot_positioning)


@pytest.fixture
def _desk_path():
    desk = _ROOT / "desks" / "mt5"
    for p in (str(desk), str(desk / "research")):
        if p not in sys.path:
            sys.path.insert(0, p)
    yield desk
    # `_cot_frame` is lru-cached: a frame read from a tmp cache must not answer a later test.
    osw = sys.modules.get("orthogonal_sweep")
    if osw is not None:
        osw._cot_frame.cache_clear()


def test_the_family_identity_carries_the_definition_version(tmp_path, _desk_path):
    """MF2: the family's code identity changes with the zcache definition, so the existing
    organs restart every clock on it (verify -> IDENTITY_BROKEN -> rebase_code)."""
    import importlib.util
    import re

    import sleeve_registry as reg
    from mt5desk.families_orthogonal import family_cot_positioning

    from libs.data.cot_source import COT_ZCACHE_VERSION

    src = _family_source()
    literals = re.findall(r'cot\.attrs\.get\("cot_zcache_version", (\d+)\) != (\d+)', src)
    assert literals == [(str(COT_ZCACHE_VERSION), str(COT_ZCACHE_VERSION))], \
        "bump COT_ZCACHE_VERSION and the family's literal together"
    # The identity the live EURUSD clock froze under definition 1 no longer matches.
    assert reg.code_hash(family_cot_positioning) != "7a57ee8bf3b231cf"
    # And it moves again with the next definition: the same body with v+1 hashes differently,
    # in source AND in bytecode (so verify() can never read it as a prose edit).
    bumped = src.replace(f", {COT_ZCACHE_VERSION}) != {COT_ZCACHE_VERSION}:",
                         f", {COT_ZCACHE_VERSION + 1}) != {COT_ZCACHE_VERSION + 1}:")
    header = ("from __future__ import annotations\nimport numpy as np\nimport pandas as pd\n"
              "from mt5desk.families_orthogonal import Signal, _atr, _h1  # noqa\n")

    def load(name: str, body: str):
        path = tmp_path / f"{name}.py"         # one file per body: getsource reads the file
        path.write_text(header + body, "utf-8")
        spec = importlib.util.spec_from_file_location(name, path)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.family_cot_positioning

    same, moved = load("same_family", src), load("bumped_family", bumped)
    assert reg.code_hash(same) == reg.code_hash(family_cot_positioning)
    assert reg.code_hash(moved) != reg.code_hash(same)
    assert reg.behaviour_hash(moved) != reg.behaviour_hash(same)


def _stamped(tmp_path, monkeypatch, version):
    """A cache at <tmp>/data/cot_zcache.parquet, pointed at by both the judge-path rule
    (cot_source.ZCACHE) and the reader (orthogonal_sweep.BASE)."""
    import orthogonal_sweep as osw
    import pyarrow as pa
    import pyarrow.parquet as pq

    from libs.data import cot_source

    path = tmp_path / "data" / "cot_zcache.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(cot_source, "ZCACHE", path)
    monkeypatch.setattr(osw, "BASE", tmp_path / "desks" / "mt5")
    osw._cot_frame.cache_clear()
    frame = pd.DataFrame({"EURUSD": np.linspace(-1, 1, 400)},
                         index=pd.date_range("2018-01-02", periods=400, freq="7D", tz="UTC"))
    table = pa.Table.from_pandas(frame)
    if version is not None:
        meta = dict(table.schema.metadata or {})
        meta[b"cot_zcache_version"] = str(version).encode()
        table = table.replace_schema_metadata(meta)
    pq.write_table(table, path)
    return osw


@pytest.mark.parametrize("version", [None, 1])
def test_a_stale_cache_is_refused_by_name_by_judge_and_clock(tmp_path, monkeypatch, _desk_path,
                                                             version):
    from mt5desk import legacy_family_inputs as lfi

    osw = _stamped(tmp_path, monkeypatch, version)
    why = lfi.input_preflight("cot_positioning", {"input_source": "cot_point_in_time"})
    assert why and why.startswith("BLOCKED_DATA") and "UNMEASURED" in why
    assert lfi.input_preflight("carry", {}) is None                     # other families untouched
    assert osw._cot_frame("EURUSD") is None                             # never read, never subbed
    assert "UNMEASURED" in (osw.cot_input_refusal("EURUSD") or "")


def test_a_current_cache_is_read_and_stamped_on_the_frame(tmp_path, monkeypatch, _desk_path):
    from mt5desk import legacy_family_inputs as lfi

    from libs.data.cot_source import COT_ZCACHE_VERSION

    osw = _stamped(tmp_path, monkeypatch, COT_ZCACHE_VERSION)
    assert lfi.input_preflight("cot_positioning", {"input_source": "cot_point_in_time"}) is None
    frame = osw._cot_frame("EURUSD")
    assert frame is not None and len(frame) >= 52
    assert frame.attrs["cot_zcache_version"] == COT_ZCACHE_VERSION


def _write(path, doc):
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc), "utf-8")


def test_the_receipt_lists_every_cot_sleeve_and_survivor(tmp_path):
    mod = _load()
    desk = tmp_path / "desk"
    live = "EURUSD.cot_positioning.continuous#input_source=cot_point_in_time"
    dead = "GBPUSD.cot_positioning.continuous"
    _write(desk / "data" / "sleeve_registry.json", {"sleeves": {
        live: {"status": "LIVE", "forward_start": "2026-09-15T02:22:32+00:00",
               "identity": {"family": "cot_positioning", "code_hash": "7a57ee8bf3b231cf",
                            "params": {"input_source": "cot_point_in_time"}}},
        dead: {"status": "KILL_EXPECTANCY", "identity": {"family": "cot_positioning"}},
        "XAUUSD.asia": {"status": "LIVE", "identity": {"family": "session_range_breakout"}}}})
    _write(desk / "data" / "UNIVERSAL_SURVIVORS.canon.json", {"survivors": {
        "external.USDJPY.cot_positioning.p=ab": {"cell": "USDJPY.cot_positioning.p=ab"},
        "external.XAUUSD.session_range_breakout": {"cell": "XAUUSD.session_range_breakout"}}})
    _write(desk / "data" / "sleeves.json", {"sleeves": [
        {"name": "cot_eur", "family": "cot_positioning", "status": "LIVE"},
        {"name": "gold", "family": "session_range_breakout", "status": "LIVE"}]})
    _write(desk / "reports" / "shadow" / "shadow_state.json",
           {live: {"status": "ACTIVE"}, "XAUUSD.asia": {"status": "ACTIVE"}})
    _write(desk / "data" / "hypotheses" / "external_survivors.json", [
        {"symbol": "AUDUSD", "family": "cot_positioning",
         "params": {"input_source": "cot_point_in_time"}, "genome_id": "g1"},
        {"symbol": "XAUUSD", "family": "session_range_breakout"}])
    # reports/UNIVERSAL_SURVIVORS.json is absent: UNMEASURED, never empty.
    got = mod.rejudge_receipt(desk, new_code_hash="5c2882a617fcb9d6")
    assert [r["key"] for r in got["registry"]] == [live, dead]
    assert got["registry"][0]["action"].startswith("RESTART")
    assert "7a57ee8bf3b231cf -> 5c2882a617fcb9d6" in got["registry"][0]["action"]
    assert got["registry"][1]["action"].startswith("NONE")
    assert [c["key"] for c in got["certificates"]] == ["external.USDJPY.cot_positioning.p=ab"]
    assert got["certificates"][0]["action"].startswith("RE-JUDGE")
    assert [s["name"] for s in got["gateway_sleeves"]] == ["cot_eur"]
    assert [s["key"] for s in got["shadow_clocks"]] == [live]
    assert [c["symbol"] for c in got["candidates"]] == ["AUDUSD"]
    assert got["unmeasured"] == ["reports/UNIVERSAL_SURVIVORS.json"]
