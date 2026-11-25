"""The world-practice methods: no lookahead, no exotics, the learner learns, every cell charged."""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from typing import ClassVar

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research"), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import families_cross_sectional as xs  # noqa: E402
from mt5desk import family_global_methods as gm  # noqa: E402

SYMS = [f"S{i}" for i in range(7)]
SPLIT_FRAC = 0.6


def _bars(seed: int, n_days: int = 1100) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2019-01-01", periods=24 * n_days, freq="h", tz="UTC").as_unit("ns")
    idx = idx[idx.dayofweek < 5]
    r = rng.normal(0, 0.002, len(idx)) + 0.0004 * rng.standard_t(3, len(idx))
    c = 100 * np.exp(np.cumsum(r))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) * (1 + np.abs(rng.normal(0, 0.001, len(c))))
    lo = np.minimum(o, c) * (1 - np.abs(rng.normal(0, 0.001, len(c))))
    v = rng.integers(10, 200, len(c)).astype(float)
    return pd.DataFrame({"open": o, "high": h, "low": lo, "close": c, "tick_volume": v},
                        index=idx)


def _corrupt(df: pd.DataFrame, split: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    out = df.copy()
    k = len(df) - split
    scale = np.exp(np.cumsum(rng.normal(0.001, 0.01, k)))
    for col in ("open", "high", "low", "close"):
        out.iloc[split:, out.columns.get_loc(col)] = df[col].to_numpy()[split:] * scale
    out.iloc[split:, out.columns.get_loc("tick_volume")] = rng.integers(1, 999, k)
    return out


@pytest.fixture
def _panel(monkeypatch):
    frames = {s: _bars(i) for i, s in enumerate(SYMS)}
    state = {"frames": frames}
    monkeypatch.setattr(xs, "class_of", lambda s: "index" if s in SYMS else None)
    monkeypatch.setattr(gm, "class_members", lambda k: list(SYMS))
    monkeypatch.setattr(gm, "_is_exotic", lambda s: s.startswith("USDTRY"))

    def load(sym):
        f = state["frames"].get(sym)
        if f is None:
            return None
        return f.index.as_unit("ns").asi8.astype("int64"), f["close"].to_numpy("float32")
    monkeypatch.setattr(gm, "load_series", load)
    return state


def _key(sigs):
    return sorted((pd.Timestamp(s.time).value, s.side, round(s.stop, 6), round(s.target, 6),
                   s.tag, None if s.trigger is None else round(s.trigger, 6)) for s in sigs)


CASES = [
    ("cross_sectional_class_ltr", {"symbol": "S0", "hold_d": 5, "train_d": 200,
                                   "refit_d": 10, "min_train_d": 60}),
    ("cross_sectional_class_hf_moment", {"symbol": "S0", "measure": "skew"}),
    ("cross_sectional_class_hf_moment", {"symbol": "S0", "measure": "signed_variation"}),
    ("cross_sectional_class_hf_moment", {"symbol": "S0", "measure": "max_ret", "window_d": 20}),
    ("value_area_rule", {"rule": "eighty"}),
    ("value_area_rule", {"rule": "acceptance", "profile": "tick_volume", "confirm_bars": 2}),
    ("volatility_breakout_kr", {"direction": "long"}),
    ("volatility_breakout_kr", {"direction": "short", "k_mode": "noise",
                                "ma_filter": "ma_score"}),
]


@pytest.mark.parametrize("family,kw", CASES)
def test_perturbing_future_bars_never_changes_a_past_signal(_panel, family, kw):
    """Every bar after the split -- the symbol's AND every peer's -- is rewritten; every signal
    stamped at or before the split must be identical."""
    fn = gm.GLOBAL_METHOD_FAMILIES[family]
    clean = dict(_panel["frames"])
    own = clean["S0"]
    split = int(len(own) * SPLIT_FRAC)
    cutoff = own.index[split - 1]
    a = [s for s in fn(own, **kw) if pd.Timestamp(s.time) <= cutoff]
    dirty = {s: _corrupt(f, int(f.index.searchsorted(cutoff, side="right")), i)
             for i, (s, f) in enumerate(clean.items())}
    _panel["frames"] = dirty
    b = [s for s in fn(dirty["S0"], **kw) if pd.Timestamp(s.time) <= cutoff]
    _panel["frames"] = clean
    assert a, f"{family} {kw} produced no signal before the split: the test would be vacuous"
    assert _key(a) == _key(b), f"{family} {kw} read the future ({len(a)} -> {len(b)})"


def test_the_perturbation_test_can_fail(_panel):
    """A peeking family (enters on tomorrow's close) must be caught by the same comparison."""
    own = _panel["frames"]["S0"]
    split = int(len(own) * SPLIT_FRAC)
    cutoff = own.index[split - 1]

    def peek(df):
        c = df["close"].to_numpy()
        return [types.SimpleNamespace(time=df.index[i], side=1 if c[i + 24] > c[i] else -1,
                                      stop=float(c[i + 24]), target=0.0, tag="peek",
                                      trigger=None)
                for i in range(0, len(df) - 24, 24)]
    a = [s for s in peek(own) if pd.Timestamp(s.time) <= cutoff]
    b = [s for s in peek(_corrupt(own, split, 1)) if pd.Timestamp(s.time) <= cutoff]
    assert _key(a) != _key(b)


def test_an_exotic_is_neither_a_leg_nor_a_peer(_panel, monkeypatch):
    _panel["frames"]["USDTRY"] = _bars(99)
    monkeypatch.setattr(gm, "class_members",
                        lambda k: [s for s in [*SYMS, "USDTRY"] if not gm._is_exotic(s)])
    xs_of = xs.class_of
    monkeypatch.setattr(xs, "class_of", lambda s: "index" if s == "USDTRY" else xs_of(s))
    d = gm._h1(_panel["frames"]["S0"])
    panel = gm.clean_panel(d, "S0")
    assert panel is not None and "USDTRY" not in panel["members"]
    assert gm.family_cross_sectional_class_hf_moment(_panel["frames"]["USDTRY"],
                                                     symbol="USDTRY") == []


def test_the_real_policy_calls_majors_clean_and_exotics_exotic():
    from research import universe_policy as up
    for s in ("EURUSD", "GBPJPY", "XAUUSD", "BTCUSD", "US500"):
        assert not up.is_exotic_symbol(s), s
    for s in ("USDTRY", "EURNOK", "USDZAR", "AUDSGD"):
        assert up.is_exotic_symbol(s), s


def test_lambdarank_recovers_the_planted_feature():
    rng = np.random.default_rng(3)
    r, n, f = 400, 12, 5
    x = rng.normal(0, 0.3, (r, n, f))
    label = 2.0 * x[:, :, 2] - 0.5 * x[:, :, 4] + rng.normal(0, 0.1, (r, n))
    w = gm.lambdarank_fit(x, gm._grades(label), iters=60)
    assert int(np.argmax(w)) == 2 and w[2] > 0 and w[4] < 0, w


def test_ltr_fit_reads_only_realised_labels():
    """Changing the LAST `hold_d` rows' prices must not move the score at a row before them,
    because every label in the fit at that row ended at or before it."""
    rng = np.random.default_rng(5)
    lv = np.cumsum(rng.normal(0, 0.01, (400, 7)), axis=0)
    kw = {"hold_d": 5, "train_d": 150, "refit_d": 7, "min_train_d": 40}
    a = gm.ltr_scores(lv, **kw)
    lv2 = lv.copy()
    lv2[300:] += rng.normal(0, 0.5, lv2[300:].shape)
    b = gm.ltr_scores(lv2, **kw)
    assert np.allclose(np.nan_to_num(a[:300]), np.nan_to_num(b[:300]))
    assert np.isfinite(a[-1]).all()


def test_realised_skew_matches_its_formula():
    t = (np.arange(200, dtype="int64") * 3_600_000_000_000)
    rng = np.random.default_rng(1)
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, 200)))
    stamp = np.array([t[-1]])
    got = gm.realised_moment((t, c), stamp, 1, "skew", 30, 10)[0]
    r = np.diff(np.log(c))
    want = np.sqrt(r.size) * (r ** 3).sum() / (r ** 2).sum() ** 1.5
    assert got == pytest.approx(want)
    sv = gm.realised_moment((t, c), stamp, 1, "signed_variation", 30, 10)[0]
    up, tot = (r[r > 0] ** 2).sum(), (r ** 2).sum()
    assert sv == pytest.approx((2 * up - tot) / tot)


def test_value_area_holds_seventy_percent_around_the_poc():
    lo = np.array([1.0, 1.0, 1.0, 1.0, 1.5, 2.5])
    hi = lo + 0.5
    val, poc, vah = gm.value_area(lo, hi, np.ones(6), bins=6, va_pct=0.7)
    assert val <= poc <= vah and 1.0 <= poc <= 1.5 and vah - val < 2.0


# ----------------------------------------------------------------------------- the producer ---
class _Policy:
    """A registry stand-in: two FX classes (one with an exotic), a share, an unclassified."""
    CLASS: ClassVar[dict[str, str]] = {"EURUSD": "fx_usd", "GBPUSD": "fx_usd", "AUDUSD": "fx_usd", "NZDUSD": "fx_usd",
             "USDJPY": "fx_usd", "USDTRY": "fx_usd", "USDCAD": "fx_usd"}

    def may_hypothesise(self, s, family=None):
        return s in self.CLASS

    def lane(self, s):
        return "hypothesis" if s in self.CLASS else ("event" if s == "AAPL" else "unclassified")

    def is_exotic_symbol(self, s, asset_class=None):
        return s == "USDTRY"

    def peer_class(self, s):
        return self.CLASS.get(s)

    def peer_classes(self):
        out: dict[str, list[str]] = {}
        for s, k in self.CLASS.items():
            out.setdefault(k, []).append(s)
        return out


def _desk(tmp_path):
    from research import global_methods as gmp
    uni = tmp_path / "data" / "universe"
    uni.mkdir(parents=True)
    for s in [*_Policy.CLASS, "AAPL", "MYSTERY"]:
        (uni / f"{s}_H1.parquet").write_bytes(b"")
    return gmp, gmp.Paths(tmp_path)


def _door(calls):
    def donate(source, rows, *, ledger, dry_run):
        calls.append(rows)
        fams: dict[str, int] = {}
        for r in rows:
            fams[r["family"]] = fams.get(r["family"], 0) + 1
        from research import proposer_common as pc
        if ledger is not None and not dry_run:
            ledger.parent.mkdir(parents=True, exist_ok=True)
            with ledger.open("a", encoding="utf-8") as fh:
                for r in rows:
                    fh.write(json.dumps({"cell_id": pc.identity(r["symbol"], r["family"],
                                                                r["params"])}) + "\n")
        return {"offered": len(rows), "already_charged": 0, "incomplete": 0,
                "tests_run_by_family": fams, "tests_run_total": len(rows),
                "donated_by_family": fams, "donated_total": len(rows)}
    return donate


@pytest.mark.parametrize("method", ["xs_ltr", "hf_moment", "value_area", "vol_breakout"])
def test_producer_mints_no_exotic_and_charges_every_cell_once(tmp_path, method):
    gmp, paths = _desk(tmp_path)
    calls: list = []
    prod = gmp.Producer(method, paths, policy=_Policy(), donate=_door(calls),
                        days=lambda s: 2000)
    rep = prod.run(60.0)
    assert rep["status"] == "RAN", rep
    rows = calls[0]
    assert rows and all(r["symbol"] != "USDTRY" for r in rows)
    assert {r["symbol"] for r in rows} <= set(_Policy.CLASS) - {"USDTRY"}
    fam = gmp.METHODS[method].family
    assert all(r["family"] == fam and r["params"]["timeframe"] == "H1" for r in rows)
    if gm.NEEDS_CLASS[fam]:
        assert all(r["params"]["symbol"] == r["symbol"] for r in rows)
    assert rep["tests_run"] >= rep["cells_proposed"] == len(rows)
    assert rep["scope"]["excluded"].get("exotic (universe_policy.is_exotic_symbol)") == 1
    again = gmp.Producer(method, paths, policy=_Policy(), donate=_door(calls),
                         days=lambda s: 2000).run(60.0)
    assert again["cells_proposed"] == 0 and again["cells_charged_total"] == len(rows)
    doc = json.loads(paths.report(gmp.METHODS[method]).read_text("utf-8"))
    assert doc["cells_charged_total"] == len(rows)


def test_producer_holds_a_symbol_without_the_history(tmp_path):
    gmp, paths = _desk(tmp_path)
    calls: list = []
    rep = gmp.Producer("xs_ltr", paths, policy=_Policy(), donate=_door(calls),
                       days=lambda s: 100).run(60.0)
    assert rep["pass"]["too_short"] > 0 and not calls


def test_the_families_are_registered_and_not_swept_twice():
    from mt5desk import families_orthogonal as fo

    from research import orthogonal_sweep as osw
    for fam in gm.GLOBAL_METHOD_FAMILIES:
        assert fo.ORTHOGONAL_FAMILIES[fam] is gm.GLOBAL_METHOD_FAMILIES[fam]
        assert fam in fo.FAMILY_INPUTS and fam in osw.NOT_SOURCED_HERE


def test_every_leg_has_a_layer_and_the_map_points_at_the_reports():
    import generator_coverage as gc

    from libs.research import layers
    for leg in ("global_xs_ltr", "global_hf_moment", "global_value_area", "global_vol_breakout"):
        assert layers.LEG_LAYER[leg] == "prediction"
        assert leg in layers.scheduled_legs()
    reports = {row[3] for row in gc.METHODS}
    from research import global_methods as gmp
    for m in gmp.METHODS.values():
        assert f"desks/mt5/reports/{m.report_name}" in reports
