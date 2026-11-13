"""The implied-vol families: registered, buildable, minted, point-in-time, and fed by the recorder.

WHAT THIS PINS, on synthetic bars and synthetic reference history only (no network):
  * `vrp_conditioned`, `iv_term_gated` and `iv_shock` resolve where the sealed gauntlet looks, are
    BUILDABLE (and EXOGENOUS, never price-only), are mapped by the axis registry and the alpha
    clusters, and are built by the sealed `build_cell` itself through `h1_override`;
  * the specialist catalogue mints them on the mapped instruments only, every cell buildable and
    charged;
  * PUBLICATION LAG: a close for date D is invisible before D+1 00:00 UTC, judged on the bar's
    TRUE UTC instant (broker stamps are UTC+2/+3), and a stale value is absent;
  * NO LOOKAHEAD: corrupting the reference history AND the bars from a cut changes no signal
    before the cut;
  * an absent series returns [] -- never the base cell's signals, never a price-only fallback;
  * the recorder persists the reference history it fetched, merges it, keeps dates the source
    stopped serving and logs restatements, under the file name the families read.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_DESK / "scripts"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk import families_implied_vol as fiv  # noqa: E402
from mt5desk import families_orthogonal as fo  # noqa: E402
from mt5desk import families_specialist as fs  # noqa: E402
from mt5desk.engine import Signal  # noqa: E402
from recorders import vol_archive as va  # noqa: E402

FAMS = ("vrp_conditioned", "iv_term_gated", "iv_shock")
DAYS = 600
START = "2021-01-04"


def _bars(seed: int, days: int = DAYS) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(START, periods=days, tz="UTC")
    idx = pd.DatetimeIndex([d + pd.Timedelta(hours=h) for d in dates for h in range(24)])
    r = rng.normal(0.0, 0.002, len(idx))
    close = 100.0 * np.exp(np.cumsum(r))
    open_ = np.r_[close[0], close[:-1]]
    return pd.DataFrame({"open": open_, "high": np.maximum(open_, close) * 1.0005,
                         "low": np.minimum(open_, close) * 0.9995, "close": close,
                         "tick_volume": 100}, index=idx)


def _iv(seed: int, level: float = 18.0, days: int = DAYS + 40) -> dict[str, float]:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(START, periods=days)
    v = level * np.exp(np.cumsum(rng.normal(0.0, 0.03, days)) * 0.3)
    return {d.date().isoformat(): float(x) for d, x in zip(dates, v, strict=True)}


def _write(ref_dir: Path, ticker: str, closes: dict[str, float]) -> None:
    ref_dir.mkdir(parents=True, exist_ok=True)
    (ref_dir / fiv.reference_filename(ticker)).write_text(json.dumps({"closes": closes}), "utf-8")


@pytest.fixture()
def ref(tmp_path, monkeypatch):
    """A reference store holding ^VIX, ^VIX9D, ^VIX3M (the 9D in backwardation for a stretch)."""
    d = tmp_path / "reference"
    vix = _iv(1)
    nine = {k: v * 0.93 for k, v in vix.items()}
    keys = sorted(nine)
    for k in keys[300:340]:                       # a planted inversion
        nine[k] = vix[k] * 1.15
    three = {k: v * 1.08 for k, v in vix.items()}
    for t, s in (("^VIX", vix), ("^VIX9D", nine), ("^VIX3M", three)):
        _write(d, t, s)
    monkeypatch.setattr(fiv, "REFERENCE_DIR", d)
    fiv._CACHE.clear()
    yield {"dir": d, "^VIX": vix, "^VIX9D": nine, "^VIX3M": three}
    fiv._CACHE.clear()


def _key(sigs: list[Signal]) -> list[tuple]:
    return [(pd.Timestamp(s.time).value, s.side, round(s.stop, 8), round(s.target, 8), s.tag)
            for s in sigs]


CASES = {
    "vrp_conditioned": {"base_family": "trend_ma_cross", "base_params": {},
                        "iv_ticker": "^VIX", "vrp_state": "high"},
    "iv_term_gated": {"base_family": "trend_ma_cross", "base_params": {},
                      "short_ticker": "^VIX9D", "long_ticker": "^VIX", "term_state": "contango"},
    "iv_shock": {"iv_ticker": "^VIX", "mode": "fade", "k_sd": 1.5},
}


# ------------------------------------------------------------------------ registration ---
@pytest.mark.parametrize("name", FAMS)
def test_registered_buildable_exogenous_and_mapped(name):
    from libs.research.alpha_clusters import classify_family
    from research import axis_registry
    from research import gauntlet_buildability as gb
    from research import orthogonal_sweep as osw
    assert fo.ORTHOGONAL_FAMILIES[name] is fs.SPECIALIST_FAMILIES[name]
    assert name in fo.FAMILY_INPUTS
    assert not fo.FAMILY_INPUTS[name][0].lower().startswith("price only")
    v, why = gb.family_verdict(name)
    assert v == gb.BUILDABLE and "not price-only" in why
    assert gb.information_class(name) == gb.EXOGENOUS
    assert gb.cell_verdict(name, CASES[name])[0] == gb.BUILDABLE
    # the event family decides at a broker hour (H1 only); the operators follow their base
    want_h4 = gb.TIMEFRAME_REFUSED if name == "iv_shock" else gb.BUILDABLE
    assert gb.cell_verdict(name, CASES[name], "H4")[0] == want_h4
    assert axis_registry.classify_family(name)[1] == "cross_asset"
    assert classify_family(name) == "options_implied"
    assert name in osw.NOT_SOURCED_HERE
    assert all("vol_archive/reference" in p for p in gb.foreign_series(name))


def test_a_cell_naming_no_series_is_refused_by_name():
    from research import gauntlet_buildability as gb
    assert gb.cell_verdict("iv_shock", {})[0] == gb.MISSING_PARAMS
    assert gb.cell_verdict("iv_shock", {"iv_ticker": ""})[0] == gb.MISSING_PARAMS
    assert gb.cell_verdict("iv_term_gated", {"base_family": "trend_ma_cross",
                                             "short_ticker": "^VIX9D"})[0] == gb.MISSING_PARAMS


def test_operators_are_never_wrapped_by_another_operator():
    for op in ("vrp_conditioned", "iv_term_gated"):
        assert not fs.wrappable(op)
    assert fs.wrappable("iv_shock")


# ------------------------------------------------------------------------- catalogue ---
def test_catalogue_mints_the_mapped_instruments_only_and_every_cell_is_buildable():
    from research.gauntlet_buildability import BUILDABLE, cell_verdict

    from research import specialist_cell as sc
    cells = sc.plan({"fx": ["EURUSD", "GBPUSD"], "metals": ["XAUUSD", "XAGUSD"],
                     "indices": ["US500", "NAS100", "US30", "GER40"]})
    iv = [c for c in cells if c["family"] in FAMS]
    by = {(c["symbol"], c["family"]) for c in iv}
    for sym in ("US500", "NAS100", "US30", "XAUUSD", "EURUSD"):
        assert (sym, "vrp_conditioned") in by and (sym, "iv_shock") in by
    for sym in ("US500", "NAS100", "US30"):
        assert (sym, "iv_term_gated") in by
    assert ("XAUUSD", "iv_term_gated") not in by and ("EURUSD", "iv_term_gated") not in by
    assert not {s for s, _f in by} & {"GBPUSD", "XAGUSD", "GER40"}
    assert {cell_verdict(c["family"], c["params"])[0] for c in iv} == {BUILDABLE}
    mapped = {c["symbol"]: c["params"].get("iv_ticker") for c in iv
              if c["family"] == "iv_shock"}
    assert mapped == {"US500": "^VIX", "NAS100": "^VXN", "US30": "^VXD", "XAUUSD": "^GVZ",
                      "EURUSD": "^EVZ"}
    assert len(iv) == 84                     # the declared grid, small and fixed up front
    assert all("crowding" in c["prior"] for c in iv)
    charged = sc.charge(iv)
    assert charged["n_raw"] == len(iv)
    assert sc.SEED_FLOOR == 66


def test_the_catalogue_maps_to_the_recorders_ground():
    """Every IV ticker the catalogue names is one the recorder fetches, so it is persisted."""
    from research import specialist_cell as sc
    fetched = {g.vol_ticker for g in va.GROUND} | {t for g in va.GROUND for t in g.term}
    assert set(sc.IV_OF.values()) <= fetched
    assert {t for pair in sc.VIX_TERM_PAIRS for t in pair} <= fetched


# ------------------------------------------------------------------- point in time ---
def test_publication_lag_is_d_plus_one_utc_midnight(ref):
    d0 = "2021-03-10"
    ns = np.array([pd.Timestamp("2021-03-10 23:59", tz="UTC").value,
                   pd.Timestamp("2021-03-11 00:00", tz="UTC").value])
    got = fiv.iv_asof("^VIX", ns)
    assert got is not None
    assert got[1] == pytest.approx(ref["^VIX"][d0])
    assert got[0] == pytest.approx(ref["^VIX"]["2021-03-09"])     # D still invisible at D 23:59


def test_the_lag_is_judged_on_the_bars_true_utc_instant(ref):
    """A broker stamp is UTC+2 in winter: D+1 01:00 broker is D 23:00 UTC, so D's close is not
    yet known there; D+1 02:00 broker is D+1 00:00 UTC and it is."""
    stamps = pd.DatetimeIndex(["2021-03-11 01:00", "2021-03-11 02:00"], tz="UTC")
    at = fiv.decision_utc_ns(stamps)
    assert at is not None
    got = fiv.iv_asof("^VIX", at)
    assert got is not None
    assert got[0] == pytest.approx(ref["^VIX"]["2021-03-09"])
    assert got[1] == pytest.approx(ref["^VIX"]["2021-03-10"])


def test_a_stale_value_is_absent_not_carried_forward(ref):
    at = np.array([pd.Timestamp("2030-06-01", tz="UTC").value])       # long after the series
    got = fiv.iv_asof("^VIX", at, max_stale_d=4)
    assert got is not None and np.isnan(got).all()


@pytest.mark.parametrize("name", FAMS)
def test_empty_when_the_series_is_absent(tmp_path, monkeypatch, name):
    monkeypatch.setattr(fiv, "REFERENCE_DIR", tmp_path / "nothing")
    fiv._CACHE.clear()
    df = _bars(7)
    assert fiv.IMPLIED_VOL_FAMILIES[name](df, **CASES[name]) == []
    # and the operators' bases DO fire here, so [] is the refusal, not a silent base
    if name != "iv_shock":
        assert fs.base_signals(df, "trend_ma_cross", {})


@pytest.mark.parametrize("name", FAMS)
def test_no_lookahead_with_the_reference_and_the_bars_corrupted(ref, name):
    df = _bars(11)
    fn = fiv.IMPLIED_VOL_FAMILIES[name]
    base = fn(df, **CASES[name])
    assert base, name
    cut = df.index[len(df) * 2 // 3]
    bad = df.copy()
    m = bad.index >= cut
    k = np.random.default_rng(5).normal(1.0, 0.05, int(m.sum()))
    for c in ("open", "high", "low", "close"):
        bad.loc[m, c] = bad.loc[m, c].to_numpy() * k
    rng = np.random.default_rng(9)
    for t in ("^VIX", "^VIX9D", "^VIX3M"):
        s = dict(ref[t])
        for day in s:
            if pd.Timestamp(day, tz="UTC") >= cut.normalize():
                s[day] = s[day] * float(rng.uniform(0.5, 2.0))
        _write(ref["dir"], t, s)
    fiv._CACHE.clear()
    after = fn(bad, **CASES[name])
    before = [s for s in base if pd.Timestamp(s.time) < cut]
    assert _key(before) == _key([s for s in after if pd.Timestamp(s.time) < cut])


# ------------------------------------------------------------------- what each does ---
def test_operators_only_drop_base_signals_and_their_states_partition(ref):
    df = _bars(13)
    base = _key(fs.base_signals(df, "trend_ma_cross", {}))
    for fam, key, states in (("vrp_conditioned", "vrp_state", ("high", "low")),
                             ("iv_term_gated", "term_state", ("contango", "backwardation"))):
        parts = []
        for st in states:
            p = {**CASES[fam], key: st}
            parts.append(set(_key(fiv.IMPLIED_VOL_FAMILIES[fam](df, **p))))
        assert parts[0] and parts[1], fam
        assert not parts[0] & parts[1], fam
        assert (parts[0] | parts[1]) <= set(base), fam


def test_backwardation_fires_only_inside_the_planted_inversion_after_its_lag(ref):
    df = _bars(13)
    p = {**CASES["iv_term_gated"], "term_state": "backwardation"}
    sigs = fiv.family_iv_term_gated(df, **p)
    assert sigs
    keys = sorted(ref["^VIX9D"])
    lo = pd.Timestamp(keys[300], tz="UTC") + pd.Timedelta(days=1)
    hi = pd.Timestamp(keys[340], tz="UTC") + pd.Timedelta(days=1)
    at = fiv.decision_utc_ns(pd.DatetimeIndex([pd.Timestamp(s.time) for s in sigs]))
    assert at is not None
    for ns in at:
        assert lo <= pd.Timestamp(ns, tz="UTC") < hi


def test_iv_shock_fires_the_first_decision_after_the_lag_and_fades_the_move(tmp_path,
                                                                            monkeypatch):
    rng = np.random.default_rng(3)
    dates = pd.bdate_range(START, periods=DAYS + 40)
    v = 18.0 * np.exp(rng.normal(0.0, 0.01, dates.size))
    jump_at = 400
    v[jump_at:] = v[jump_at:] * 1.6                         # a planted shock on one date
    closes = {d.date().isoformat(): float(x) for d, x in zip(dates, v, strict=True)}
    ref_dir = tmp_path / "reference"
    _write(ref_dir, "^VIX", closes)
    monkeypatch.setattr(fiv, "REFERENCE_DIR", ref_dir)
    fiv._CACHE.clear()
    df = _bars(17)
    sigs = fiv.family_iv_shock(df, iv_ticker="^VIX", mode="fade", k_sd=4.0, decision_hour=9)
    jump_day = dates[jump_at]
    hits = [s for s in sigs if abs(pd.Timestamp(s.time).tz_localize(None) - jump_day)
            < pd.Timedelta(days=5)]
    assert len(hits) == 1
    t = pd.Timestamp(hits[0].time)
    assert t.normalize().tz_localize(None) > jump_day          # never on the shock's own date
    utc = pd.Timestamp(fiv.decision_utc_ns(pd.DatetimeIndex([t]))[0], tz="UTC")
    assert utc >= pd.Timestamp(jump_day, tz="UTC") + pd.Timedelta(days=1)
    # fade: against the instrument's own one-day move into the decision bar
    follow = fiv.family_iv_shock(df, iv_ticker="^VIX", mode="follow", k_sd=4.0, decision_hour=9)
    twin = [s for s in follow if s.time == hits[0].time]
    assert twin and twin[0].side == -hits[0].side


# ---------------------------------------------------------------- the sealed gauntlet ---
@pytest.mark.parametrize("name", FAMS)
def test_the_sealed_build_cell_builds_each_family(ref, name):
    import external_gauntlet as eg
    df = _bars(19)
    cell = eg.build_cell("US500", name, dict(CASES[name]), {}, h1_override=df)
    assert cell is not None, (name, eg.LAST_BUILD_FAILURE)
    assert cell["sigs"], name


# --------------------------------------------------------------------- the recorder ---
def test_the_recorder_persists_merges_and_logs_restatements(tmp_path):
    data = {"^VIX": {"2026-09-01": 15.0, "2026-09-02": 16.0},
            "^VIX9D": {"2026-09-01": 14.0, "2026-09-02": 15.5},
            "^VIX3M": {"2026-09-01": 17.0, "2026-09-02": 17.5},
            "^VIX6M": {"2026-09-02": 18.0}, "^SKEW": {"2026-09-02": 140.0},
            "^GVZ": {"2026-09-02": 20.0}}
    src = va.CapturingSource(va.FakeVolSource(data, missing={"^EVZ"}))
    obs = va.observe(src, {"US500": {}, "XAUUSD": {}}, tmp_path / "universe",
                     now=datetime(2026, 9, 3, 12, tzinfo=UTC))
    assert obs and set(src.captured) >= {"^VIX", "^VIX9D", "^VIX3M", "^GVZ", "^SKEW"}
    assert "^EVZ" not in src.captured                     # an absence is not persisted as data
    ref_dir = tmp_path / "reference"
    got = va.persist_reference(src.captured, ref_dir, now=datetime(2026, 9, 3, tzinfo=UTC))
    assert got["^VIX"]["status"] == "WRITTEN" and got["^VIX"]["n"] == 2
    doc = json.loads((ref_dir / "VIX.json").read_text("utf-8"))
    assert doc["closes"] == {"2026-09-01": 15.0, "2026-09-02": 16.0}
    assert doc["schema"] == va.REFERENCE_SCHEMA and doc["public_series"] is True
    assert not list(ref_dir.glob("*.tmp"))                 # atomic: no half-written file left
    # next cycle: the source dropped 09-01, restated 09-02 and added 09-03
    va.persist_reference({"^VIX": {"2026-09-02": 16.5, "2026-09-03": 17.0}}, ref_dir,
                         now=datetime(2026, 9, 4, tzinfo=UTC))
    doc = json.loads((ref_dir / "VIX.json").read_text("utf-8"))
    assert doc["closes"] == {"2026-09-01": 15.0, "2026-09-02": 16.5, "2026-09-03": 17.0}
    assert doc["restatements"] == [{"date": "2026-09-02", "was": 16.0, "now": 16.5,
                                    "seen_at": "2026-09-04T00:00:00+00:00"}]
    assert doc["first_seen"]["2026-09-01"].startswith("2026-09-03")


def test_the_families_read_what_the_recorder_wrote(tmp_path, monkeypatch):
    for t in ("^VIX", "^VIX9D", "^GVZ", "^SKEW", "^EVZ"):
        assert va.reference_filename(t) == fiv.reference_filename(t)
    ref_dir = tmp_path / "reference"
    va.persist_reference({"^VIX": {"2026-09-01": 15.0, "2026-09-02": 16.0}}, ref_dir)
    monkeypatch.setattr(fiv, "REFERENCE_DIR", ref_dir)
    fiv._CACHE.clear()
    at = np.array([pd.Timestamp("2026-09-02 12:00", tz="UTC").value,
                   pd.Timestamp("2026-09-03 00:00", tz="UTC").value])
    got = fiv.iv_asof("^VIX", at)
    assert got is not None and list(got) == [15.0, 16.0]
    fiv._CACHE.clear()


def test_a_dry_run_cycle_writes_no_reference(tmp_path, monkeypatch):
    monkeypatch.setattr(va, "YahooVolSource", lambda: va.FakeVolSource({"^VIX": {"2026-09-01":
                                                                               15.0}}))
    monkeypatch.setattr(va, "UNIVERSE", tmp_path / "universe.json")
    rc = va.main(["--dry-run", "--archive", str(tmp_path / "obs.jsonl"),
                  "--universe", str(tmp_path), "--reference", str(tmp_path / "reference"),
                  "--out", str(tmp_path / "rep.json")])
    assert rc == 0 and not (tmp_path / "reference").exists()
    rc = va.main(["--archive", str(tmp_path / "obs.jsonl"), "--universe", str(tmp_path),
                  "--reference", str(tmp_path / "reference"), "--out", str(tmp_path / "rep.json")])
    assert rc == 0 and (tmp_path / "reference" / "VIX.json").exists()
    rep = json.loads((tmp_path / "rep.json").read_text("utf-8"))
    assert rep["reference_history"]["tickers"]["^VIX"]["status"] == "WRITTEN"
