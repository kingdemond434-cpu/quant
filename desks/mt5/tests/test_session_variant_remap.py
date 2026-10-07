"""DEAD SESSION VARIANTS -- the oracle says when a family can fire, and no producer mints fewer.

The load-bearing pins:
  * `test_session_cells_never_mint_fewer` -- a dead slot is REPLACED one for one, so the count a
    producer mints never falls and every minted cell is distinct;
  * `test_unmeasured_is_never_dead` -- a family the oracle cannot measure keeps its variant;
  * PASS 2 (2026-10-06): the shared filter IS the market clock, and an anchor-clocked family
    (open / close / gap / rollover) keeps its anchor -- `test_verdicts_on_the_filter_clock`,
    `test_market_session_fire_is_live_not_a_mismatch`,
    `test_anchor_clocked_family_is_live_in_its_anchored_sessions`;
  * `test_certified_chfdkk_eurzar_asia_are_never_dead` -- the audit's case: two ten-gate
    certificates (overnight_gap_decay asia, fires at server 00) stay LIVE on the anchor clock;
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


def _rec(hours: dict[int, int], market: dict[str, int],
         kept: dict[str, int] | None = None, digest: dict[str, str] | None = None) -> dict:
    """A measured record. `kept` is the shared filter's own count per session (the anchored
    window for an anchor-clocked family); without it the filter count is the market count."""
    rec = {"status": "MEASURED", "n": sum(hours.values()), "chart": "H1",
           "hours": {str(h): c for h, c in hours.items()},
           "market_sessions": {s: market.get(s, 0) for s in ff.MARKET_SESSIONS}}
    if kept is not None:
        rec["filter_sessions"] = {s: kept.get(s, 0) for s in ff.MARKET_SESSIONS}
    if digest is not None:
        rec["filter_digest"] = dict(digest)
    return rec


#: overnight_gap_decay as measured: every signal at server 00, the prior close, which lies in the
#: anchored window of all three sessions and in no market's 08:00-16:00.
GAP = dict.fromkeys(("asia", "london", "ny"), 269)
#: ...and the SAME 269 signals in each: one mask, one fingerprint.
GAP_DIGEST = dict.fromkeys(("asia", "london", "ny", "all"), "gap-at-the-prior-close")


def _gap() -> dict:
    return _rec({0: 269}, {}, GAP, GAP_DIGEST)


def _cache(entries: dict[str, dict], verified: tuple[str, ...] = ()) -> dict:
    return {"version": ff.VERSION, "keys": entries,
            "shift_verified": dict.fromkeys(verified, True)}


# ------------------------------------------------------------------------------ the verdicts
def test_verdicts_on_the_filter_clock() -> None:
    rec = _rec({16: 100}, {"london": 100, "ny": 100})
    assert ff.verdict(rec, "asia") == ff.DEAD            # never in Tokyo's session
    assert ff.verdict(rec, "ny") == ff.LIVE
    assert ff.verdict(rec, "london") == ff.LIVE           # pass 2: London's own clock is the filter
    assert ff.verdict(rec, "all") == ff.LIVE
    # A plain family at server 00 is outside Tokyo 08-16: DEAD, there is no filter-only class.
    late = _rec({0: 100}, {})
    assert ff.verdict(late, "asia") == ff.DEAD
    # The same hours for an anchor-clocked family: the filter's own count says LIVE.
    anchored = _rec({0: 100}, {}, {"asia": 100, "london": 100, "ny": 100})
    assert {ff.verdict(anchored, s) for s in ("asia", "london", "ny")} == {ff.LIVE}
    # The two pre-pass-2 classes are never produced.
    for r in (rec, late, anchored):
        for s in ("asia", "london", "ny"):
            assert ff.verdict(r, s) not in (ff.TZ_MISMATCH, ff.LIVE_FILTER_ONLY)


def test_anchor_clocked_family_is_live_in_its_anchored_sessions() -> None:
    fam = "overnight_gap_decay"
    from libs.regime import session_clock
    assert session_clock.anchor_clocked(fam)
    cache = _cache({ff.key(fam, {}, SYM): _gap()})
    for s in ("asia", "london", "ny"):
        assert ff.verdict(_gap(), s) == ff.LIVE
    # ONE ANCHOR, ONE CELL: the same 269 trades in every window are the Tokyo-open cell, once.
    slots = ff.session_cells(fam, {}, ("all", "asia", "london", "ny"), cache=cache, symbol=SYM)
    assert slots == [("asia", {"session": "asia"}, None)]
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
    # The measured shape (fires at server 00 only): LIVE on the anchor clock, by the rule alone.
    measured = _rec({0: 269}, {}, GAP)
    for sym in ("CHFDKK", "EURZAR"):
        assert ff.guarded_verdict(measured, "asia", symbol=sym, family=fam,
                                  params={"session": "asia"}, guard=guard) == ff.LIVE
    # Even a firing set the filter calls DEAD cannot overrule the certificate. Server 23 lies
    # after Tokyo's 16:00 close and before the next prior-close boundary.
    nowhere = _rec({23: 269}, {}, {"ny": 269})
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


def test_distinct_anchors_stay_distinct_cells() -> None:
    # Fires at the prior close AND at a later anchor: asia keeps the first set only, london and ny
    # keep both (identical), `all` keeps both. Two masks, two cells -- asia and london.
    fam = "overnight_gap_decay"
    rec = _rec({0: 100, 12: 100}, {}, {"asia": 100, "london": 200, "ny": 200},
               {"asia": "tokyo", "london": "tokyo+london", "ny": "tokyo+london",
                "all": "tokyo+london"})
    cache = _cache({ff.key(fam, {}, SYM): rec})
    slots = ff.session_cells(fam, {}, ("all", "asia", "london", "ny"), cache=cache, symbol=SYM)
    assert [s for s, _p, _n in slots] == ["london", "asia"]
    assert ff.same_cell(fam, {}, "london", "ny", cache=cache, symbol=SYM)
    assert not ff.same_cell(fam, {}, "asia", "london", cache=cache, symbol=SYM)
    # A session the caller already holds is never minted again.
    held = ff.session_cells(fam, {}, ("asia", "london", "ny"), cache=cache, symbol=SYM,
                            held=["ny"])
    assert [s for s, _p, _n in held] == ["asia"]


def test_a_plain_family_keeps_all_its_sessions_even_with_equal_masks() -> None:
    fam = "london_close_momentum"
    from libs.regime import session_clock
    assert not session_clock.anchor_clocked(fam)
    rec = _rec({16: 100}, {"london": 100, "ny": 100}, None,
               dict.fromkeys(("asia", "london", "ny", "all"), "same"))
    cache = _cache({ff.key(fam, {}, SYM): rec})
    slots = ff.session_cells(fam, {}, ("all", "asia", "london", "ny"), cache=cache, symbol=SYM)
    assert len(slots) == 4 and [s for s, _p, _n in slots][::2] == ["all", "london"]
    assert not ff.same_cell(fam, {}, "london", "ny", cache=cache, symbol=SYM)


def test_unmeasured_or_protected_anchored_variants_are_never_folded(tmp_path: Path) -> None:
    fam = "overnight_gap_decay"
    # No fingerprint recorded: nothing is known to be identical, every slot is minted.
    bare = _cache({ff.key(fam, {}, SYM): _rec({0: 269}, {}, GAP)})
    assert len(ff.session_cells(fam, {}, ("asia", "london", "ny"), cache=bare,
                                symbol=SYM)) == 3
    # A certified london cell keeps its own identity even though its mask equals asia's.
    canon = _canon(tmp_path / "canon.json", [(SYM, fam, "london")])
    guard = ff.load_guard(canon, tmp_path / "no_ledger.jsonl")
    keys = ff.anchor_keys(fam, {}, ("asia", "london", "ny"), symbol=SYM, guard=guard,
                          cache=_cache({ff.key(fam, {}, SYM): _gap()}))
    assert keys == {"asia": "asia", "london": "london", "ny": "asia"}


def test_trial_count_equals_distinct_cells(monkeypatch: pytest.MonkeyPatch) -> None:
    from research import miner_candidate_compiler as mcc
    fam = "overnight_gap_decay"
    cache = _cache({ff.key(fam, {}, SYM): _gap()})
    monkeypatch.setattr(ff, "current_cache", lambda path=None: cache)
    monkeypatch.setattr(ff, "_safe_guard", lambda: None)
    monkeypatch.setattr(mcc, "_charts_with_bars", lambda _s: [])
    monkeypatch.setattr(mcc, "_invariance", lambda _s, _f: None)
    out = mcc.expand_axes([{"symbol": SYM, "family": fam, "params": {}}])
    cells = {json.dumps(v["params"], sort_keys=True) for v in out}
    assert len(out) == len(cells) == 1                    # one mask on the tape, one trial
    assert out[0]["params"] == {"session": "asia"}


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
    assert ff.MARKET_OPEN_SERVER == {"asia": 2, "london": 11, "ny": 15}
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


def test_market_session_fire_is_live_not_a_mismatch() -> None:
    # Pre-pass-2 this was SESSION_TZ_MISMATCH: in London's own session, outside the old 8-16
    # server window. The filter is London's own clock now, so it is simply LIVE.
    fam = "london_close_momentum"
    cache = _cache({ff.key(fam, {}, SYM): _rec({16: 100}, {"london": 100, "ny": 100})})
    assert ff.standin(fam, {}, "london", cache=cache, symbol=SYM) == ({"session": "london"}, None)


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


def test_measures_an_anchor_clocked_family_on_its_anchor() -> None:
    if not (ff.UNIVERSE / "EURUSD_H1.parquet").exists():
        pytest.skip("no cached EURUSD H1 bars on this host")
    rec = ff.measure("overnight_gap_decay", {}, "EURUSD")
    if rec["status"] != "MEASURED":
        pytest.skip(f"overnight_gap_decay unmeasured on EURUSD here: {rec.get('why')}")
    assert rec["anchor_clocked"] is True
    # It fires on the day's first bar, outside every market's 08-16, inside every anchored window.
    assert rec["market_sessions"]["asia"] == 0
    assert rec["filter_sessions"]["asia"] == rec["n"]
    assert ff.verdict(rec, "asia") == ff.LIVE
    # Measured, not assumed: the same trades in every window, so one cell under asia.
    dig = rec["filter_digest"]
    assert dig["asia"] == dig["london"] == dig["ny"] == dig["all"]
    cache = _cache({ff.key("overnight_gap_decay", {}, "EURUSD"): rec})
    slots = ff.session_cells("overnight_gap_decay", {}, ("all", "asia", "london", "ny"),
                             cache=cache, symbol="EURUSD")
    assert [s for s, _p, _n in slots] == ["asia"]


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
    assert sum(1 for v in out if v.get("session_remap", {}).get("remapped")) == 2


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
        # Pass 2: london is LIVE on London's own clock; only asia is dead.
        assert doc["dead_found"] == 1 and doc["session_tz_mismatch"] == 0
        assert doc["live"] == 2 and doc["remapped"] == 1
        assert doc["donation"]["created"] == 1
        marks = [json.loads(x) for x in (tmp_path / "DEAD.jsonl").read_text().splitlines()]
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


def test_leg_keeps_anchor_clocked_certified_variants_out_of_the_sidecar(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import session_variant_remap as svr
    fam = "overnight_gap_decay"
    cache_path = tmp_path / "firing.json"
    ff.save_cache(_cache({ff.key(fam, {}, sym): {**_gap(), "host": ff._host(),
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
    # Anchored to the prior close, the gap family is LIVE in all three sessions with ONE mask:
    # the certified asia cell is kept, london and ny are that cell again, charged once.
    assert doc["dead_found"] == 0 and doc["live_filter_only"] == 0
    assert doc["live"] == 2 and doc["anchored_duplicates"] == 4 and doc["distinct_cells"] == 2
    assert doc["guard"]["certified_or_positive_dead"] == 0
    marks = [json.loads(x) for x in (tmp_path / "DEAD.jsonl").read_text().splitlines()]
    assert sorted((m["symbol"], m["session"]) for m in marks) == [
        (sym, s) for sym in ("CHFDKK", "EURZAR") for s in ("london", "ny")]
    assert {m["cause"] for m in marks} == {ff.DUPLICATE}
    assert {m["duplicate_of"]["session"] for m in marks} == {"asia"}


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


# ------------------------------------------------- #230 hold fixes (2026-10-07)
def test_remapped_standins_are_minted_not_dropped_as_duplicates(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """A family that fires in Tokyo only: its london and ny slots are DEAD and come back as two
    stand-ins that LAND in asia. The moat explosion keyed slots by where they landed, so both
    were read as folds (DUPLICATE_ANCHORED_MASK) and the card minted 0 of them; LIVE minted 2."""
    mce = pytest.importorskip("research.moat_card_explosion")
    fam = "asia_momentum"
    from libs.regime import session_clock
    assert not session_clock.anchor_clocked(fam)
    cache = _cache({ff.key(fam, {}, SYM): _rec({4: 100}, {"asia": 100})})
    monkeypatch.setattr(ff, "current_cache", lambda path=None: cache)
    monkeypatch.setattr(ff, "_safe_guard", lambda: None)
    card = {"family": fam, "params": {}, "session": "all", "symbol": SYM}
    got = mce._live_slots(card, ["asia", "london", "ny"])
    assert got[0] == ("asia", None)
    standins = [(landed, note) for landed, note in got[1:] if note and note.get("remapped")]
    assert len(standins) == 2
    assert {n["dead_session"] for _l, n in standins} == {"london", "ny"}
    assert all(n.get("cause") != ff.DUPLICATE for _l, n in got[1:] if n)
    # Two distinct cells, each distinct from the asia child.
    idents = {json.dumps(n["params"], sort_keys=True) for _l, n in standins}
    assert len(idents) == 2 and json.dumps({"session": "asia"}) not in idents


#: Real tags the two families emit, with the spec parameters that the old rule read as clocks.
_NOT_CLOCKS = {"pin_bar_reversal": {"anchor": "open"},
               "hedging_demand_close": {"close_hour": 22}}


def test_pin_bar_reversal_and_hedging_demand_close_stay_distinct_cells() -> None:
    """The judge filters by each signal's tag (no params), so the oracle must too: a price
    `anchor` and a firing-hour `close_hour` are not clocks. Neither family is anchor-clocked, and
    every session variant is its own cell even when the recorded masks happen to be equal."""
    from libs.regime import session_clock
    for fam, params in _NOT_CLOCKS.items():
        assert session_clock.anchor_clocked(fam, params) is False, fam
        assert session_clock.anchor_clocked(fam, params) == session_clock.anchor_clocked(fam)
        rec = _rec({3: 50, 12: 50, 18: 50}, {"asia": 50, "london": 50, "ny": 50}, None,
                   dict.fromkeys(("asia", "london", "ny", "all"), "same-mask"))
        cache = _cache({ff.key(fam, params, SYM): rec})
        keys = ff.anchor_keys(fam, params, ("asia", "london", "ny"), cache=cache, symbol=SYM)
        assert keys == {"asia": "asia", "london": "london", "ny": "ny"}, fam
        assert not ff.same_cell(fam, params, "asia", "london", cache=cache, symbol=SYM)
        slots = ff.session_cells(fam, params, ("all", "asia", "london", "ny"), cache=cache,
                                 symbol=SYM)
        assert [s for s, _p, _n in slots] == ["all", "asia", "london", "ny"], fam
    # The two families are two cells on every axis: distinct oracle keys.
    keys_ = {ff.key(f, p, SYM) for f, p in _NOT_CLOCKS.items()}
    assert len(keys_) == 2


def test_oracle_and_judge_read_the_same_anchor_rule() -> None:
    """`family_firing` decides the window with (family, params); the judge with the signal's tag
    alone. They agree for every family the desk builds, because params never decide."""
    from libs.regime import session_clock
    cases = [("overnight_gap_decay", {}), ("opening_range", {"open_hour": 8}),
             ("overnight_drift", {"anchor_hour": 0}), ("htf_anchor_trend", {"anchor_mult": 4}),
             ("some_family", {"open_hour": 9}), *_NOT_CLOCKS.items()]
    for fam, params in cases:
        assert session_clock.anchor_clocked(fam, params) == session_clock.anchor_clocked(fam), fam


def test_filter_digest_is_the_same_in_every_unit() -> None:
    import pandas as pd
    idx = pd.DatetimeIndex(["2026-07-15 00:00", "2026-07-16 00:00", "2026-07-17 09:00"],
                           tz="UTC")
    want = ff._digest(idx.as_unit("ns"))
    assert ff._digest(idx.as_unit("us")) == want
    assert ff._digest(idx.as_unit("ms")) == want
    assert ff._digest(idx.as_unit("s")) == want
    assert ff._digest(list(idx.as_unit("us"))[::-1]) == want      # Timestamps, any order
