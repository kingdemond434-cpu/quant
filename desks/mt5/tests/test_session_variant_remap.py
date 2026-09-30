"""DEAD SESSION VARIANTS -- the oracle says when a family can fire, and no producer mints fewer.

The load-bearing pins:
  * `test_session_cells_never_mint_fewer` -- a dead slot is REPLACED one for one, so the count a
    producer mints never falls and every minted cell is distinct;
  * `test_unmeasured_is_never_dead` -- a family the oracle cannot measure keeps its variant;
  * `test_tz_mismatch_is_counted_apart_and_never_remapped` -- a variant dead only because the
    shared filter reads the server clock is SESSION_TZ_MISMATCH, not DEAD;
  * `test_leg_marks_donates_and_is_idempotent` -- the docket is read, never written; stand-ins go
    through the registry door once.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "desks" / "mt5"
for p in (str(ROOT), str(BASE), str(BASE / "research")):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.research import family_firing as ff  # noqa: E402


def _rec(hours: dict[int, int], market: dict[str, int]) -> dict:
    return {"status": "MEASURED", "n": sum(hours.values()), "chart": "H1",
            "hours": {str(h): c for h, c in hours.items()},
            "market_sessions": {s: market.get(s, 0) for s in ff.MARKET_SESSIONS}}


def _cache(entries: dict[str, dict], verified: tuple[str, ...] = ()) -> dict:
    return {"version": ff.VERSION, "keys": entries,
            "shift_verified": dict.fromkeys(verified, True)}


# ------------------------------------------------------------------------------ the verdicts
def test_verdicts_on_both_clocks() -> None:
    rec = _rec({16: 100}, {"london": 100, "ny": 100})
    assert ff.verdict(rec, "asia") == ff.DEAD            # never in Tokyo's session
    assert ff.verdict(rec, "ny") == ff.LIVE               # server window [14, 22) and NY's own
    assert ff.verdict(rec, "london") == ff.TZ_MISMATCH    # London's own clock yes, server no
    assert ff.verdict(rec, "all") == ff.LIVE


def test_unmeasured_is_never_dead() -> None:
    thin = {**_rec({16: 5}, {"ny": 5}), "status": ff.UNMEASURED}
    assert ff.verdict(thin, "asia") == ff.UNMEASURED
    assert ff.verdict(None, "asia") == ff.UNMEASURED
    cache = _cache({})
    slots = ff.session_cells("london_close_momentum", {}, ("all", "asia", "london", "ny"),
                             cache=cache)
    assert [s for s, _p, _n in slots] == ["all", "asia", "london", "ny"]
    assert all(n is None for _s, _p, n in slots)


def test_market_clock_follows_dst() -> None:
    import pandas as pd
    # Server stamps are New York + 7h (`libs/regime/session_clock`). 10:00 server is 08:00 London
    # whenever US and UK DST agree; 09:00 server is 07:00 London -- before the open.
    times = pd.DatetimeIndex(["2026-07-01 10:00", "2026-01-15 10:00", "2026-07-01 09:00"],
                             tz="UTC")
    m = ff.market_masks(times)
    assert list(m["london"]) == [True, True, False]
    # In the weeks the US has sprung forward and the UK has not (2026-03-08 .. 03-29) server
    # 10:00 is 07:00 London: the EET model called it the open, New York + 7h does not.
    gap = ff.market_masks(pd.DatetimeIndex(["2026-03-20 10:00", "2026-03-20 11:00"], tz="UTC"))
    assert list(gap["london"]) == [False, True]
    # 15:00 server is 08:00 New York in every week.
    ny = ff.market_masks(pd.DatetimeIndex(["2026-07-01 15:00", "2026-01-15 15:00",
                                           "2026-03-20 15:00", "2026-07-01 14:00"], tz="UTC"))["ny"]
    assert list(ny) == [True, True, True, False]


def test_the_oracle_uses_the_one_session_clock() -> None:
    from libs.regime import session_clock
    assert ff.session_clock is session_clock
    assert ff.MARKET_SESSIONS == dict(session_clock.MARKET_SESSIONS)
    assert "Athens" not in ff.CLOCK_BASIS


# ------------------------------------------------------------------------------ remapping
def test_session_cells_never_mint_fewer() -> None:
    fam = "london_close_momentum"
    cache = _cache({ff.key(fam, {}): _rec({16: 100}, {"london": 0, "ny": 100})})
    axis = ("all", "asia", "london", "ny")
    slots = ff.session_cells(fam, {}, axis, cache=cache)
    assert len(slots) == len(axis)
    idents = {json.dumps(p, sort_keys=True) for _s, p, _n in slots}
    assert len(idents) == len(axis)                       # every minted cell distinct
    remapped = [n for _s, _p, n in slots if n and n.get("remapped")]
    assert len(remapped) == 2                             # asia and london were dead
    for s, p, n in slots:
        if n and n.get("remapped"):
            assert s == "ny" and p.get("session") == "ny" and p.get("regime") in ff.REHOME_REGIMES
            assert ff.verdict(cache["keys"][ff.key(fam, p)], "ny") == ff.LIVE


def test_hour_parameter_is_reanchored_to_the_market_open() -> None:
    fam = "session_range_breakout"
    if not ff.hour_params(fam):
        pytest.skip("family has no hour parameter on this tree")
    cache = _cache({ff.key(fam, {}): _rec({7: 100}, {"asia": 100})},
                   verified=(f"{fam}|H1",))
    slots = ff.session_cells(fam, {}, ("all", "asia", "london", "ny"), cache=cache)
    by = {s: (p, n) for s, p, n in slots}
    assert by["asia"][1] is None                           # it fires there already
    london, note = by["london"]
    assert note and note["remap"] == "reanchored"
    assert london["range_start"] == ff.MARKET_OPEN_SERVER["london"]
    assert by["ny"][0]["range_start"] == ff.MARKET_OPEN_SERVER["ny"]


def test_unverified_shift_is_not_trusted() -> None:
    fam = "session_range_breakout"
    cache = _cache({ff.key(fam, {}): _rec({7: 100}, {"asia": 100})})
    slots = ff.session_cells(fam, {}, ("all", "asia", "london", "ny"), cache=cache)
    for _s, _p, n in slots:
        if n and n.get("remapped"):
            assert n["remap"] == "rehomed"                 # no guessed re-anchor


def test_tz_mismatch_is_counted_apart_and_never_remapped() -> None:
    fam = "london_close_momentum"
    cache = _cache({ff.key(fam, {}): _rec({16: 100}, {"london": 100, "ny": 100})})
    p, note = ff.standin(fam, {}, "london", cache=cache)
    assert p == {"session": "london"}
    assert note and note["cause"] == ff.TZ_MISMATCH and note["remapped"] is False


def test_live_session_never_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_a, **_k):
        raise RuntimeError("oracle down")
    monkeypatch.setattr(ff, "standin", boom)
    assert ff.live_session("x", {"a": 1}, "asia") == ({"a": 1}, "asia", None)


# ------------------------------------------------------------------------------ measurement
def test_measures_a_fixed_hour_family_on_cached_bars() -> None:
    if not (ff.UNIVERSE / "EURUSD_H1.parquet").exists():
        pytest.skip("no cached EURUSD H1 bars on this host")
    rec = ff.measure("london_close_momentum", {}, "EURUSD")
    assert rec["status"] == "MEASURED"
    assert set(rec["hours"]) == {"16"}
    assert ff.verdict(rec, "asia") == ff.DEAD
    assert ff.stale(rec) is False


def test_unmeasured_from_another_host_is_retried() -> None:
    rec = {"status": ff.UNMEASURED, "host": "some-other-box", "measured_at": 1e12}
    assert ff.stale(rec) is True
    assert ff.stale({**rec, "host": ff._host()}) is False


# ------------------------------------------------------------------------------ producers
def test_compiler_expand_axes_keeps_its_count(monkeypatch: pytest.MonkeyPatch) -> None:
    from research import miner_candidate_compiler as mcc
    fam = "london_close_momentum"
    cache = _cache({ff.key(fam, {}): _rec({16: 100}, {"ny": 100})})
    monkeypatch.setattr(ff, "current_cache", lambda path=None: cache)
    monkeypatch.setattr(mcc, "_charts_with_bars", lambda _s: [])
    monkeypatch.setattr(mcc, "_invariance", lambda _s, _f: None)
    out = mcc.expand_axes([{"symbol": "EURUSD", "family": fam, "params": {}}])
    assert len(out) == len(mcc.SESSION_AXIS)
    assert len({json.dumps(v["params"], sort_keys=True) for v in out}) == len(out)
    assert sum(1 for v in out if v.get("session_remap", {}).get("remapped")) == 2


def test_breadth_sweep_slots_keep_their_count(monkeypatch: pytest.MonkeyPatch) -> None:
    from research import breadth_sweep as bs
    fam = "london_close_momentum"
    cache = _cache({ff.key(fam, {}): _rec({16: 100}, {"ny": 100})})
    monkeypatch.setattr(ff, "current_cache", lambda path=None: cache)
    slots = bs._session_slots(fam, {}, "H1", "EURUSD")
    assert len(slots) == len(bs.SESSION_AXIS)
    assert len({json.dumps(p, sort_keys=True) for p, _n in slots}) == len(slots)


# ------------------------------------------------------------------------------ the leg
def test_leg_marks_donates_and_is_idempotent(tmp_path: Path,
                                             monkeypatch: pytest.MonkeyPatch) -> None:
    import session_variant_remap as svr

    from libs.moat import registry
    fam = "london_close_momentum"
    cache_path = tmp_path / "firing.json"
    ff.save_cache(_cache({ff.key(fam, {}): {**_rec({16: 100}, {"london": 100, "ny": 100}),
                                            "host": ff._host(), "measured_at": 1e12}}),
                  cache_path)
    docket = tmp_path / "external_survivors.json"
    rows = [{"genome_id": f"g{s}", "symbol": "EURUSD", "family": fam,
             "params": {"session": s}} for s in ("asia", "london", "ny")]
    rows.append({"genome_id": "gall", "symbol": "EURUSD", "family": fam, "params": {}})
    docket.write_text(json.dumps(rows), encoding="utf-8")
    before = docket.read_text(encoding="utf-8")
    registry.set_path(tmp_path / "registry.sqlite")
    try:
        kw = {"budget_s": 30.0, "docket": docket, "cache_path": cache_path,
              "sidecar": tmp_path / "DEAD.jsonl", "out": tmp_path / "REMAP.json"}
        doc = svr.run(**kw)
        assert docket.read_text(encoding="utf-8") == before       # box state untouched
        assert doc["session_variants"] == 3
        assert doc["dead_found"] == 1 and doc["session_tz_mismatch"] == 1
        assert doc["live"] == 1 and doc["remapped"] == 1
        assert doc["donation"]["created"] == 1
        marks = [json.loads(x) for x in (tmp_path / "DEAD.jsonl").read_text().splitlines()]
        assert {m["cause"] for m in marks} == {ff.NEVER_FIRES, ff.TZ_MISMATCH}
        for m in marks:
            for k in svr.CULTURE_KEYS:
                assert m[k]
        again = svr.run(**kw)
        assert again["donation"]["created"] == 0 and again["donation"]["already_present"] == 1
    finally:
        registry.set_path(None)


def test_leg_is_wired() -> None:
    from libs.research.layers import LEG_LAYER
    assert LEG_LAYER["session_variant_remap"] == "prediction"
    src = (BASE / "research" / "hourly_cycle.py").read_text(encoding="utf-8")
    assert '_costed("session_variant_remap"' in src
    assert '"session_variant_remap": 300' in src
