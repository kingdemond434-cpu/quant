"""Unknown-unknown mining: a causal typed grammar, novelty against the named features, FDR over
the full screened width, every cell charged, only novel survivors donated as buildable cells.

Synthetic bars only; the registry and every output are redirected into `tmp_path`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parent.parent
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import families_orthogonal as FO  # noqa: E402
from mt5desk import mass_screen_rules as MR  # noqa: E402
from mt5desk import uu_grammar as UG  # noqa: E402

from research import mass_screen as MS  # noqa: E402
from research import unknown_unknown as UU  # noqa: E402

META = {"contract_size": 100000.0, "tick_size": 1e-5, "tick_value": 1.0,
        "median_spread_pts": 10.0, "swap_long": 0.0, "swap_short": 0.0}


def bars(n_days: int = 900, seed: int = 7, plant: float = 0.0) -> pd.DataFrame:
    """Weekday hourly bars; optionally a drift in the 6 bars after a VOLUME spike -- a relation
    no named feature (all of them price-only) carries."""
    idx = pd.date_range("2019-01-01", periods=n_days * 24, freq="h", tz="UTC")
    idx = idx[idx.weekday < 5]
    rng = np.random.default_rng(seed)
    r = rng.normal(0.0, 0.001, len(idx))
    vol = rng.integers(80, 120, len(idx)).astype(float)
    spike = rng.random(len(idx)) < 0.04
    vol[spike] *= 8
    if plant:
        for lag in range(1, 7):
            r[lag:][spike[:-lag]] += plant
    close = 1.1 * np.exp(np.cumsum(r))
    opn = np.r_[close[0], close[:-1]]
    wig = np.abs(rng.normal(0.0, 0.0004, len(idx)))
    df = pd.DataFrame({"open": opn, "close": close, "high": np.maximum(opn, close) + wig,
                       "low": np.minimum(opn, close) - wig, "tick_volume": vol}, index=idx)
    df.index.name = "time"
    return df


# ------------------------------------------------------------------ the language
def test_parse_render_round_trip_and_refusals() -> None:
    for e in ("r1", "xr1@XAUUSD", "z120(sum24(r1))", "corr24(r1,lvol)",
              "sub(rank120(rng),rank120(xrng@US500))", "neg(abs(gap))", "lag1(mend)"):
        assert UG.render(UG.parse(e)) == e
    assert UG.references("sub(r1,xr1@EURUSD)") == ("EURUSD",)
    for bad in ("z7(r1)", "sum(r1)", "abs3(r1)", "r1@EURUSD", "xr1", "foo(r1)", "sub(r1)",
                "corr24(r1)", "z120(r1"):
        with pytest.raises(UG.GrammarError):
            UG.parse(bad)


def test_every_expression_is_causal() -> None:
    """Truncating the future never changes a past value -- including a cross-asset leaf."""
    df = bars(200, seed=3)
    ref = bars(200, seed=4)
    UG.REF_LOADER = lambda s: ref
    try:
        cut = len(df) - 300
        rng = np.random.default_rng(0)
        exprs = ["z120(sum24(r1))", "corr24(r1,lvol)", "rank120(xrng@REF)", "ema48(body)",
                 "sub(rank24(rng),rank24(xr1@REF))", "ratio(vol24(r1),vol120(r1))"]
        exprs += [UU.random_tree(rng, ["REF"]) for _ in range(10)]
        for e in exprs:
            full = UG.evaluate(e, df)
            part = UG.evaluate(e, df.iloc[:cut])
            np.testing.assert_allclose(full[:cut], part, equal_nan=True, rtol=1e-9, atol=1e-12,
                                       err_msg=e)
    finally:
        UG.REF_LOADER = None


def test_the_families_are_registered_buildable_h1_only_and_have_axis_groups() -> None:
    from research import axis_registry as AX
    from research.breadth_sweep import default_families
    from research.gauntlet_buildability import BUILDABLE, TIMEFRAME_REFUSED, cell_verdict
    ok, blocked = default_families()
    for g in UG.GRAMMARS:
        fam = f"uu_{g}"
        assert FO.ORTHOGONAL_FAMILIES[fam] is UG.family_uu_rule
        assert fam in AX.FAMILY_TABLE and AX.FAMILY_TABLE[fam][0] == "UNKNOWN"
        assert fam not in ok and fam in blocked            # a default sweep sets it aside
        p = {"expr": "z120(r1)", "op": "gt", "thr": 1.0, "direction": 1, "hold": 8,
             "stop_atr": 2.0}
        assert cell_verdict(fam, p)[0] == BUILDABLE
        assert cell_verdict(fam, {**p, "timeframe": "M5"})[0] == TIMEFRAME_REFUSED
    assert AX.FAMILY_TABLE["uu_cross"][1] == "cross_asset"


def test_novelty_is_low_for_a_named_feature_and_high_for_volume() -> None:
    df = bars(500, seed=9)
    P = MS.Prepared("SYN", df, META, None)
    nov = UU.Novelty(P)
    n_named, near = nov.of("ret_24", P.feats["ret_24"])
    assert n_named < 0.05 and near == "trend"
    n_vol, _ = nov.of("rank24(lvol)", UG.evaluate("rank24(lvol)", P.df))
    assert n_vol > 0.8


# ------------------------------------------------------------------ the run
@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    from libs.moat import registry as R
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup")
    R.set_path(tmp_path / "alpha_registry.sqlite")
    frames: dict[str, pd.DataFrame] = {}
    monkeypatch.setattr(MR, "load_bars", lambda s, tf="H1": frames.get(s))
    monkeypatch.setattr(MS, "universe_meta", lambda: dict.fromkeys(frames, META))
    monkeypatch.setattr(UU, "reference_symbols", lambda s: [])
    yield tmp_path, frames
    R.set_path(None)


def test_a_planted_unnamed_edge_is_found_charged_rebuilt_and_donated(sandbox, monkeypatch):
    tmp, frames = sandbox
    frames["SYNV"] = bars(900, seed=11, plant=0.0005)
    monkeypatch.setattr(UU, "unary_space", lambda: ["rank24(lvol)", "z24(lvol)", "sum4(r1)"])
    doc = UU.run(budget_s=600, workers=1, symbols=["SYNV"], out_dir=tmp / "out",
                 day="2026-09-30")
    assert doc["status"] == "MEASURED"
    m = doc["fdr"]["m_full_screened_width"]
    assert m == sum(a["cells_screened"] for a in doc["by_grammar"].values())
    rows = [json.loads(x) for x in (tmp / "out" / "UNKNOWN_UNKNOWN_TRIALS.jsonl").read_text()
            .splitlines()]
    assert sum(r["cells_screened"] for r in rows) == m                 # the full width charged
    from libs.research import experiment_ledger as EL
    total, by_fam = EL._unknown_unknown_counts(tmp / "out" / "UNKNOWN_UNKNOWN_TRIALS.jsonl")
    assert total == m and set(by_fam) <= {f"uu_{g}" for g in UG.GRAMMARS}
    assert doc["forward"]["created"] >= 1
    top = next(r for r in doc["forwarded_sample"] if "lvol" in r["params"]["expr"])
    assert top["novelty"] >= UU.NOVELTY_MIN
    # the sealed build path rebuilds it from its params alone, on the same bars
    fn = FO.ORTHOGONAL_FAMILIES[top["family"]]
    sigs = fn(frames["SYNV"], side=1, **top["params"])
    assert sigs and all(s.side == top["params"]["direction"] for s in sigs)
    # through the registry door into the docket feed
    from libs.moat import docket_feed
    fed, census = docket_feed.feed()
    assert census["refused_unstamped"] == 0
    assert any(r["family"].startswith("uu_") for r in fed)
    # the same day again: nothing new forwarded, the width still charged
    doc2 = UU.run(budget_s=600, workers=1, symbols=["SYNV"], out_dir=tmp / "out",
                  day="2026-09-30")
    assert doc2["forward"]["created"] == 0
    assert len((tmp / "out" / "UNKNOWN_UNKNOWN_TRIALS.jsonl").read_text().splitlines()) > len(rows)


def test_the_screen_and_the_family_agree_on_the_trades(sandbox) -> None:
    tmp, frames = sandbox
    df = bars(700, seed=21, plant=0.0005)
    P = MS.Prepared("SYNV", df, META, None)
    e = "rank24(lvol)"
    P.feats[e] = UG.evaluate(e, P.df)
    conds = UU._threshold_conds(P, "unary", e)
    res = MS.screen_symbol(P, META, q=1.0, conds=conds, horizons=UU.UU_HORIZONS)
    c = next(c for c in res["candidates"] if c["cond"]["op"] == "gt")
    params = UU.params_of(c)
    sigs = UG.family_uu_rule(df, **params)
    pos = P.df.index.get_indexer(pd.DatetimeIndex([s.time for s in sigs]))
    fam_days = np.unique(MR.entry_days(P.df.index)[pos])
    assert set(c["days"].tolist()) <= set(fam_days.tolist())
    np.testing.assert_array_equal(fam_days[: len(c["days"])], np.sort(c["days"]))


def test_pure_noise_donates_nothing_and_is_still_charged(sandbox) -> None:
    tmp, frames = sandbox
    frames["NOISE"] = bars(700, seed=5)
    doc = UU.run(budget_s=600, workers=1, symbols=["NOISE"], out_dir=tmp / "o2",
                 day="2026-09-30")
    assert doc["fdr"]["m_full_screened_width"] > 10_000
    assert doc["forward"]["created"] == 0
    assert (tmp / "o2" / "UNKNOWN_UNKNOWN_TRIALS.jsonl").exists()


def test_each_day_draws_new_expressions() -> None:
    a = UU._sample(UU.unary_space(), 60, UU._rng("2026-09-30", "EURUSD", "unary"))
    b = UU._sample(UU.unary_space(), 60, UU._rng("2026-10-01", "EURUSD", "unary"))
    assert a != b and len(set(a) & set(b)) < 30
    assert UU._sample(UU.unary_space(), 60, UU._rng("2026-09-30", "EURUSD", "unary")) == a


def test_the_leg_is_wired() -> None:
    import hourly_cycle as HC

    from libs.research.layers import LEG_LAYER
    assert HC.department_of("unknown_unknown") == "discovery"
    assert LEG_LAYER["unknown_unknown"] == "prediction"
    assert HC.LEG_BUDGET_SEC["unknown_unknown"] > HC.UNKNOWN_UNKNOWN_BUDGET_S
    src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_costed("unknown_unknown", unknown_unknown)' in src
    assert f'"--budget-s", "{HC.UNKNOWN_UNKNOWN_BUDGET_S}")' in src
    assert src.index('_costed("unknown_unknown"') < src.index('_costed("merge_docket"')
