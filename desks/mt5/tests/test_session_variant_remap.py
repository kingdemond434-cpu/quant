"""DEAD SESSION VARIANTS -- the oracle says when a family can fire, and no producer mints fewer.

The load-bearing pins:
  * `test_session_cells_never_mint_fewer` -- a dead slot is REPLACED one for one, so the count a
    producer mints never falls and every minted cell is distinct;
  * `test_unmeasured_is_never_dead` -- a family the oracle cannot measure keeps its variant;
  * `test_tz_mismatch_is_counted_apart_and_never_remapped` -- a variant dead only because the
    shared filter reads the server clock is SESSION_TZ_MISMATCH, not DEAD;
  * `test_live_filter_only_is_kept_and_never_remapped` -- DEAD needs BOTH clocks empty; a variant
    that fires under today's filter is LIVE_FILTER_ONLY and trades as it stands;
  * `test_certified_chfdkk_eurzar_asia_are_never_dead` -- the audit's case: two ten-gate
    certificates the market-clock-only rule marked DEAD;
  * `test_cache_version_follows_the_clock_module` -- a change to session_clock re-measures;
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

#: The symbol every in-memory cache below is keyed on: firing hours are measured per symbol.
SYM = "EURUSD"


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
    # Fires at server 00: inside today's asia filter [0, 8), outside Tokyo 08-16 (server 1/2-9).
    late = _rec({0: 100}, {})
    assert ff.verdict(late, "asia") == ff.LIVE_FILTER_ONLY
    assert ff.verdict(late, "london") == ff.DEAD          # neither clock


def test_live_filter_only_is_kept_and_never_remapped() -> None:
    fam = "overnight_gap_decay"
    cache = _cache({ff.key(fam, {}, SYM): _rec({0: 269}, {})})
    slots = ff.session_cells(fam, {}, ("all", "asia", "london", "ny"), cache=cache, symbol=SYM)
    assert len(slots) == 4
    assert slots[1] == ("asia", {"session": "asia"}, None)  # minted exactly as proposed, no mark
    for _s, _p, note in slots[2:]:                        # london / ny: neither clock -> DEAD
        assert note and note["dead_session"] in ("london", "ny")
        assert note["cause"] == ff.NEVER_FIRES
    assert ff.replacements(fam, {}, "asia", cache=cache, symbol=SYM) == []
    assert ff.standin(fam, {}, "asia", cache=cache, symbol=SYM) == ({"session": "asia"}, None)


def _canon(path: Path, cells: list[tuple[str, str, str]]) -> Path:
    survivors = {f"external.{sym}.{fam}.p=44136fa355b3678a": {
        "cell": f"{sym}.{fam}.p=44136fa355b3678a", "sym": sym,
        "shadow_spec": {"symbol": sym, "selector": sel, "family": fam, "params": {}}}
        for sym, fam, sel in cells}
    path.write_text(json.dumps({"survivors": survivors}), encoding="utf-8")
    return path


def test_certified_chfdkk_eurzar_asia_are_never_dead(tmp_path: Path) -> None:
    fam = "overnight_gap_decay"
    canon = _canon(tmp_path / "canon.json", [("CHFDKK", fam, "asia"), ("EURZAR", fam, "asia")])
    guard = ff.load_guard(canon, tmp_path / "no_ledger.jsonl")
    # The measured shape (fires at server 00 only): LIVE_FILTER_ONLY on the rule alone.
    measured = _rec({0: 269}, {})
    for sym in ("CHFDKK", "EURZAR"):
        assert ff.guarded_verdict(measured, "asia", symbol=sym, family=fam,
                                  params={"session": "asia"}, guard=guard) == ff.LIVE_FILTER_ONLY
    # Even a firing set that says DEAD on both clocks cannot overrule the certificate.
    nowhere = _rec({23: 269}, {})
    assert ff.verdict(nowhere, "asia") == ff.DEAD
    for sym in ("CHFDKK", "EURZAR"):
        assert ff.guarded_verdict(nowhere, "asia", symbol=sym, family=fam,
                                  params={"session": "asia"}, guard=guard) == ff.PROTECTED
    assert ff.guarded_verdict(nowhere, "asia", symbol="EURUSD", family=fam,
                              params={"session": "asia"}, guard=guard) == ff.DEAD
    assert ff.guarded_verdict(nowhere, "london", symbol="CHFDKK", family=fam,
                              params={"session": "london"}, guard=guard) == ff.DEAD


def test_the_real_canon_protects_its_certified_session_sleeves() -> None:
    guard = ff.load_guard()
    doc = json.loads(ff.CANON.read_text(encoding="utf-8")) if ff.CANON.exists() else {}
    specs = [r.get("shadow_spec") or {} for r in (doc.get("survivors") or {}).values()]
    session_specs = [s for s in specs if str(s.get("selector") or "") in ff.SESSION_NAMES]
    if not session_specs:
        pytest.skip("no session-selected certificate in this tree's canon")
    for spec in session_specs:
        assert ff.protected(guard, spec["symbol"], spec["family"], spec.get("params") or {},
                            spec["selector"])


def test_net_positive_and_passed_verdicts_are_never_dead(tmp_path: Path) -> None:
    fam = "london_close_momentum"
    ledger = tmp_path / "gate_verdict_ledger.jsonl"
    cid = ff.gauntlet_cell_id("GBPUSD", fam, {"session": "asia"})
    assert cid
    ledger.write_text(json.dumps({"cell": cid, "passed": True}) + "\n", encoding="utf-8")
    guard = ff.load_guard(tmp_path / "no_canon.json", ledger)
    ff.note_net_verdict(guard, {"symbol": "EURUSD", "family": fam, "params": {"session": "asia"},
                                "net_verdict": "NET_POSITIVE_UNCONFIRMED"})
    dead = _rec({16: 100}, {"london": 100, "ny": 100})
    for sym in ("EURUSD", "GBPUSD"):
        assert ff.guarded_verdict(dead, "asia", symbol=sym, family=fam,
                                  params={"session": "asia"}, guard=guard) == ff.PROTECTED
    assert ff.guarded_verdict(dead, "asia", symbol="USDJPY", family=fam,
                              params={"session": "asia"}, guard=guard) == ff.DEAD


def test_cache_version_follows_the_clock_settings(tmp_path: Path) -> None:
    from libs.regime import session_clock
    assert ff.VERSION.endswith(ff.clock_hash())
    cfg = ff.clock_settings()
    assert cfg["server_tz"] == session_clock.SERVER_TZ
    assert cfg["server_shift_h"] == session_clock.SERVER_SHIFT_H
    assert ff.clock_hash(dict(cfg)) == ff.clock_hash()      # same settings, same version
    moved = {**cfg, "server_shift_h": cfg["server_shift_h"] + 1}
    assert ff.clock_hash(moved) != ff.clock_hash()
    sess = {**cfg, "market_sessions": {**cfg["market_sessions"],
                                       "london": ["Europe/London", 7, 16]}}
    assert ff.clock_hash(sess) != ff.clock_hash()
    cache_path = tmp_path / "firing.json"
    ff.save_cache(_cache({"k": _rec({1: 40}, {})}), cache_path)
    assert ff.load_cache(cache_path)["keys"] == {"k": _rec({1: 40}, {})}
    doc = json.loads(cache_path.read_text(encoding="utf-8"))
    doc["version"] = f"{ff.SCHEMA_VERSION}+clock:{ff.clock_hash(moved)}"
    cache_path.write_text(json.dumps(doc), encoding="utf-8")
    assert ff.load_cache(cache_path)["keys"] == {}         # another conversion: re-measure


def test_always_in_session_hours_are_derived_from_the_clock() -> None:
    import pandas as pd

    from libs.regime import session_clock
    # London: server 10 is outside London on the US/UK mismatch days of 2026; 11-17 never is.
    assert ff.MARKET_SERVER_HOURS["london"] == frozenset(range(11, 18))
    assert ff.MARKET_OPEN_SERVER == {"asia": 2, "london": 11, "ny": 15,
                                     "tokyo_fix": 3, "london_fix": 18, "overlap": 15}
    days = pd.bdate_range("2026-01-01", "2026-12-31")
    out10 = days[~session_clock.in_session(days + pd.Timedelta(hours=10), "london")]
    assert len(out10) == 20
    assert {d.strftime("%m-%d") for d in out10} >= {"03-09", "03-27", "10-26", "10-30"}
    for h in ff.MARKET_SERVER_HOURS["london"]:
        assert session_clock.in_session(days + pd.Timedelta(hours=h), "london").all()


def test_cache_key_carries_symbol_and_asset_class() -> None:
    fam = "london_close_momentum"
    a, b = ff.key(fam, {}, "EURUSD"), ff.key(fam, {}, "CHFDKK")
    assert a != b
    assert json.loads(a)[-2:] == ["EURUSD", ff.asset_class("EURUSD")]
    assert ff.key(fam, {"lookback": 5}, "EURUSD") == a         # a non-hour param shares it
    cache = _cache({a: _rec({16: 100}, {"ny": 100})})
    assert ff.verdict(ff.firing(fam, {}, cache=cache, symbol="EURUSD"), "asia") == ff.DEAD
    # EURUSD's firing set is never applied to CHFDKK.
    assert ff.verdict(ff.firing(fam, {}, cache=cache, symbol="CHFDKK"), "asia") == ff.UNMEASURED
    assert ff.measure(fam, {}, None)["status"] == ff.UNMEASURED


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
    assert dict(session_clock.MARKET_SESSIONS) == ff.MARKET_SESSIONS
    assert "Athens" not in ff.CLOCK_BASIS


# ------------------------------------------------------------------------------ remapping
def test_session_cells_never_mint_fewer() -> None:
    fam = "london_close_momentum"
    cache = _cache({ff.key(fam, {}, SYM): _rec({16: 100}, {"london": 0, "ny": 100})})
    axis = ("all", "asia", "london", "ny")
    slots = ff.session_cells(fam, {}, axis, cache=cache, symbol=SYM)
    assert len(slots) == len(axis)
    idents = {json.dumps(p, sort_keys=True) for _s, p, _n in slots}
    assert len(idents) == len(axis)                       # every minted cell distinct
    remapped = [n for _s, _p, n in slots if n and n.get("remapped")]
    assert len(remapped) == 2                             # asia and london were dead
    for s, p, n in slots:
        if n and n.get("remapped"):
            assert s == "ny" and p.get("session") == "ny" and p.get("regime") in ff.REHOME_REGIMES
            assert ff.verdict(cache["keys"][ff.key(fam, p, SYM)], "ny") == ff.LIVE


def test_hour_parameter_is_reanchored_to_the_market_open() -> None:
    fam = "session_range_breakout"
    if not ff.hour_params(fam):
        pytest.skip("family has no hour parameter on this tree")
    cache = _cache({ff.key(fam, {}, SYM): _rec({7: 100}, {"asia": 100})},
                   verified=(f"{fam}|H1",))
    slots = ff.session_cells(fam, {}, ("all", "asia", "london", "ny"), cache=cache, symbol=SYM)
    by = {s: (p, n) for s, p, n in slots}
    assert by["asia"][1] is None                           # it fires there already
    london, note = by["london"]
    assert note and note["remap"] == "reanchored"
    assert london["range_start"] == ff.MARKET_OPEN_SERVER["london"]
    assert by["ny"][0]["range_start"] == ff.MARKET_OPEN_SERVER["ny"]


def test_unverified_shift_is_not_trusted() -> None:
    fam = "session_range_breakout"
    cache = _cache({ff.key(fam, {}, SYM): _rec({7: 100}, {"asia": 100})})
    slots = ff.session_cells(fam, {}, ("all", "asia", "london", "ny"), cache=cache, symbol=SYM)
    for _s, _p, n in slots:
        if n and n.get("remapped"):
            assert n["remap"] == "rehomed"                 # no guessed re-anchor


def test_tz_mismatch_is_counted_apart_and_never_remapped() -> None:
    fam = "london_close_momentum"
    cache = _cache({ff.key(fam, {}, SYM): _rec({16: 100}, {"london": 100, "ny": 100})})
    p, note = ff.standin(fam, {}, "london", cache=cache, symbol=SYM)
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
    cache = _cache({ff.key(fam, {}, SYM): _rec({16: 100}, {"ny": 100})})
    monkeypatch.setattr(ff, "current_cache", lambda path=None: cache)
    monkeypatch.setattr(mcc, "_charts_with_bars", lambda _s: [])
    monkeypatch.setattr(mcc, "_invariance", lambda _s, _f: None)
    out = mcc.expand_axes([{"symbol": "EURUSD", "family": fam, "params": {}}])
    assert len(out) == len(mcc.SESSION_AXIS)
    assert len({json.dumps(v["params"], sort_keys=True) for v in out}) == len(out)
    # fires at server hour 16 only: asia, london, tokyo_fix and london_fix hold none of it and
    # are remapped; ny and overlap (15-18) hold it
    assert sum(1 for v in out if v.get("session_remap", {}).get("remapped")) == 4


def test_breadth_sweep_slots_keep_their_count(monkeypatch: pytest.MonkeyPatch) -> None:
    from research import breadth_sweep as bs
    fam = "london_close_momentum"
    cache = _cache({ff.key(fam, {}, SYM): _rec({16: 100}, {"ny": 100})})
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
    ff.save_cache(_cache({ff.key(fam, {}, SYM): {**_rec({16: 100}, {"london": 100, "ny": 100}),
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
              "sidecar": tmp_path / "DEAD.jsonl", "out": tmp_path / "REMAP.json",
              "canon": tmp_path / "no_canon.json", "ledger": tmp_path / "no_ledger.jsonl"}
        doc = svr.run(**kw)
        assert docket.read_text(encoding="utf-8") == before       # box state untouched
        assert doc["session_variants"] == 3
        assert doc["dead_found"] == 1 and doc["session_tz_mismatch"] == 1
        assert doc["live"] == 1 and doc["remapped"] == 1
        assert doc["donation"]["created"] == 1
        marks = [json.loads(x) for x in (tmp_path / "DEAD.jsonl").read_text().splitlines()]
        # SESSION_TZ_MISMATCH is counted, never written to the sort-last sidecar.
        assert {m["cause"] for m in marks} == {ff.NEVER_FIRES}
        assert doc["session_tz_mismatch_in_sidecar"] == 0
        for m in marks:
            for k in svr.CULTURE_KEYS:
                assert m[k]
        assert doc["guard"]["certified_or_positive_dead"] == 0
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


def test_leg_keeps_certified_and_filter_only_variants_out_of_the_sidecar(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import session_variant_remap as svr
    fam = "overnight_gap_decay"
    cache_path = tmp_path / "firing.json"
    ff.save_cache(_cache({ff.key(fam, {}, sym): {**_rec({0: 269}, {}), "host": ff._host(),
                                                 "measured_at": 1e12}
                          for sym in ("CHFDKK", "EURZAR")}), cache_path)
    docket = tmp_path / "external_survivors.json"
    rows = [{"genome_id": f"{sym}{s}", "symbol": sym, "family": fam, "params": {"session": s}}
            for sym in ("CHFDKK", "EURZAR") for s in ("asia", "london", "ny")]
    docket.write_text(json.dumps(rows), encoding="utf-8")
    canon = _canon(tmp_path / "canon.json", [("CHFDKK", fam, "asia"), ("EURZAR", fam, "asia")])
    doc = svr.run(budget_s=30.0, donate_rows=False, docket=docket, cache_path=cache_path,
                  sidecar=tmp_path / "DEAD.jsonl", out=tmp_path / "REMAP.json", canon=canon,
                  ledger=tmp_path / "no_ledger.jsonl")
    assert doc["live_filter_only"] == 2 and doc["dead_found"] == 4
    assert doc["guard"]["certified_or_positive_dead"] == 0
    assert doc["dead_but_server_window_fires"] == 0
    marks = [json.loads(x) for x in (tmp_path / "DEAD.jsonl").read_text().splitlines()]
    assert all(m["session"] != "asia" for m in marks)


def test_unreadable_universe_is_warned_and_published_and_stays_unmeasured(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture) -> None:
    """The audit of #145: an unreadable universe.json makes every class key miss the cache. The
    variants stay UNMEASURED (never DEAD, never 0) and the cause is warned and published."""
    import logging

    import research.universe_policy as up
    import session_variant_remap as svr
    fam = "london_close_momentum"
    cache_path = tmp_path / "firing.json"
    # Measured under the real registry's class for EURUSD...
    ff.save_cache(_cache({ff.key(fam, {}, SYM): {**_rec({16: 100}, {"london": 100, "ny": 100}),
                                            "host": ff._host(), "measured_at": 1e12}}),
                  cache_path)
    assert ff.universe_unreadable() == ""
    # ...then the registry becomes unreadable.
    broken = tmp_path / "universe.json"
    broken.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(up, "UNIVERSE", broken)
    monkeypatch.setattr(ff, "_CLASS_CACHE", {})
    monkeypatch.setattr(ff, "_WARNED", set())
    monkeypatch.setattr(ff, "measure", lambda *a, **k: {"status": ff.UNMEASURED, "n": 0})
    assert "unreadable" in ff.universe_unreadable()
    docket = tmp_path / "external_survivors.json"
    docket.write_text(json.dumps([{"genome_id": f"g{s}", "symbol": SYM, "family": fam,
                                   "params": {"session": s}} for s in ("asia", "london", "ny")]),
                      encoding="utf-8")
    with caplog.at_level(logging.WARNING, logger=ff.__name__):
        doc = svr.run(budget_s=5.0, donate_rows=False, docket=docket, cache_path=cache_path,
                      sidecar=tmp_path / "DEAD.jsonl", out=tmp_path / "REMAP.json",
                      canon=tmp_path / "no_canon.json", ledger=tmp_path / "no_ledger.jsonl")
    assert doc["universe_unreadable"] and str(broken) in doc["universe_unreadable"]
    assert json.loads((tmp_path / "REMAP.json").read_text())["universe_unreadable"]
    assert doc["unmeasured"] == 3 and doc["dead_found"] == 0 and doc["live"] == 0
    assert doc["dead_share_of_measured"] == ff.UNMEASURED
    assert any("broker registry unreadable" in r.getMessage() for r in caplog.records)
    # Nothing is cached off the broken read: the class returns the moment the file does.
    assert ff._CLASS_CACHE == {}
