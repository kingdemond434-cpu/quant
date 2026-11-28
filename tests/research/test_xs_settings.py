"""WorldQuant panel settings: group neutralisation, linear decay, truncation (N8 gaps
`wq_group_neutralization` and `wq_decay_truncation`, found by #1020's donor diff).

Pinned:
  * neutralisation demeans within each member's group, falls back to the basket for a thin or
    unlabelled member, and never zeroes a one-member group; "market" and "none" do what they say;
  * linear decay is BRAIN's weights d..1, renormalised over the lags a member has;
  * truncation keeps unit gross and the sign, caps every |w| at the setting, redistributes pro rata,
    returns equal weight when the cap is infeasible, and is off at None;
  * the DSL's panel seeding applies them to `xzscore` (the transpiled IndNeutralize) and never to
    `xrank`; the expression factory evaluates panel cells with peer groups and says so.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import alpha_dsl as dsl  # noqa: E402
from libs.research import xs_settings as xss  # noqa: E402

GROUPS = {"EURUSD": "fx_usd", "GBPUSD": "fx_usd", "USDJPY": "fx_usd",
          "EURGBP": "fx_cross", "EURJPY": "fx_cross", "GBPJPY": "fx_cross"}


def _panel(rows: list[list[float]], cols: list[str] | None = None) -> pd.DataFrame:
    cols = cols or list(GROUPS)
    return pd.DataFrame(rows, columns=cols, dtype=float)


# ------------------------------------------------------------------------ neutralisation ---
def test_group_neutralisation_demeans_within_each_group():
    p = _panel([[1, 2, 3, 10, 20, 30], [3, 3, 6, 0, 1, 5]])
    out = xss.neutralize(p, GROUPS, level="group", scale=False)
    for g in ("fx_usd", "fx_cross"):
        cols = [c for c, lab in GROUPS.items() if lab == g]
        assert np.allclose(out[cols].sum(axis=1), 0.0)
    # the common move of each group is gone: the market-level answer differs
    mkt = xss.neutralize(p, level="market", scale=False)
    assert not np.allclose(out.to_numpy(), mkt.to_numpy())
    assert np.allclose(mkt.sum(axis=1), 0.0)
    z = xss.neutralize(p, GROUPS, level="group", scale=True)
    for g in ("fx_usd", "fx_cross"):
        cols = [c for c, lab in GROUPS.items() if lab == g]
        assert np.allclose(z[cols].std(axis=1, ddof=0), 1.0)


def test_a_thin_or_unlabelled_member_falls_back_to_the_basket_never_to_zero():
    groups = {**GROUPS, "EURGBP": "lonely"}            # a one-member group
    groups.pop("EURJPY")                                # an unlabelled member
    p = _panel([[1, 2, 3, 10, 20, 30]])
    out = xss.neutralize(p, groups, level="group", scale=False, min_members=3)
    mkt = xss.neutralize(p, level="market", scale=False)
    for c in ("EURGBP", "EURJPY", "GBPJPY"):           # fx_cross has < 3 labelled members now
        assert out.loc[0, c] == pytest.approx(mkt.loc[0, c])
        assert out.loc[0, c] != 0.0


def test_nan_stays_nan_and_levels_are_validated():
    p = _panel([[1, np.nan, 3, 10, 20, 30]])
    out = xss.neutralize(p, GROUPS, level="group", scale=False, min_members=2)
    assert np.isnan(out.loc[0, "GBPUSD"])
    assert out.loc[0, "EURUSD"] == pytest.approx(-1.0)
    # at the default floor of 3 the two finite fx_usd members fall back to the basket
    dflt = xss.neutralize(p, GROUPS, level="group", scale=False)
    assert dflt.loc[0, "EURUSD"] == pytest.approx(1 - (1 + 3 + 10 + 20 + 30) / 5)
    assert xss.neutralize(p, level="none").equals(p)
    with pytest.raises(ValueError):
        xss.neutralize(p, level="sector")
    with pytest.raises(ValueError):
        xss.neutralize(p, None, level="group")


# ------------------------------------------------------------------------------- decay ------
def test_linear_decay_is_brain_weights_and_renormalises_over_missing_lags():
    p = pd.DataFrame({"A": [1.0, 2.0, 3.0, 4.0], "B": [1.0, np.nan, 3.0, np.nan]})
    out = xss.decay_linear(p, 3)
    assert out.loc[3, "A"] == pytest.approx((3 * 4 + 2 * 3 + 1 * 2) / 6)
    assert out.loc[3, "B"] == pytest.approx(3.0)       # only the lag-1 value, weight 2 of 2
    assert out.loc[0, "A"] == pytest.approx(1.0)
    assert xss.decay_linear(p, 1).equals(p)


# ---------------------------------------------------------------------------- truncation ---
def test_truncation_caps_keeps_unit_gross_and_sign():
    w = pd.DataFrame([[0.7, -0.1, 0.1, 0.05, -0.05], [5.0, 1.0, -1.0, 1.0, 1.0]],
                     columns=list("ABCDE"))
    out = xss.truncate(w, 0.3)
    assert np.allclose(out.abs().sum(axis=1), 1.0)
    assert (out.abs().to_numpy() <= 0.3 + 1e-9).all()
    assert (np.sign(out.to_numpy()) == np.sign(w.to_numpy())).all()
    # pro rata: the members under the cap keep their ordering
    assert abs(out.loc[0, "B"]) == pytest.approx(abs(out.loc[0, "C"]))
    assert abs(out.loc[0, "B"]) > abs(out.loc[0, "D"])


def test_truncation_infeasible_is_equal_weight_and_none_is_off():
    w = pd.DataFrame([[0.9, 0.1]], columns=["A", "B"])
    out = xss.truncate(w, 0.3)                          # 2 members can never sit under 0.3
    assert np.allclose(out.to_numpy(), [[0.5, 0.5]])
    assert np.allclose(xss.truncate(w, None).to_numpy(), [[0.9, 0.1]])
    with pytest.raises(ValueError):
        xss.truncate(w, 0.0)
    nan_row = pd.DataFrame([[np.nan, np.nan]], columns=["A", "B"])
    assert xss.truncate(nan_row, 0.5).isna().all().all()


def test_apply_settings_runs_brain_order():
    rng = np.random.default_rng(3)
    p = pd.DataFrame(rng.normal(size=(30, 6)), columns=list(GROUPS))
    out = xss.apply_settings(p, GROUPS, neutralization="group", decay=4, truncation=0.25)
    tail = out.iloc[3:]
    assert np.allclose(tail.abs().sum(axis=1), 1.0)
    assert (tail.abs().to_numpy() <= 0.25 + 1e-9).all()


# ----------------------------------------------------------------- the DSL and the factory ---
def _frames(seed: int, n: int = 300) -> dict[str, pd.Series]:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2025-01-01", periods=n, freq="1h", tz="UTC")
    close = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 1e-3, n))), index=idx)
    return {"close": close}


def test_seed_panels_groups_xzscore_and_leaves_xrank_market_wide():
    frames = {s: _frames(i) for i, s in enumerate(GROUPS)}
    child = ["delta", "close", 4]
    z_market = {s: dsl.evaluate_cell(["xzscore", child], frames, s) for s in GROUPS}
    z_group = {s: dsl.evaluate_cell(["xzscore", child], frames, s, groups=GROUPS)
               for s in GROUPS}
    zg = pd.DataFrame(z_group).dropna()
    for g in ("fx_usd", "fx_cross"):
        cols = [c for c, lab in GROUPS.items() if lab == g]
        assert np.allclose(zg[cols].mean(axis=1), 0.0, atol=1e-9)
    assert not np.allclose(pd.DataFrame(z_market).dropna().to_numpy(), zg.to_numpy())
    r_market = dsl.evaluate_cell(["xrank", child], frames, "EURUSD")
    r_group = dsl.evaluate_cell(["xrank", child], frames, "EURUSD", groups=GROUPS)
    assert r_market.dropna().equals(r_group.dropna())
    w = pd.DataFrame({s: dsl.evaluate_cell(["xzscore", child], frames, s, groups=GROUPS,
                                           truncation=0.25) for s in GROUPS}).dropna()
    assert np.allclose(w.abs().sum(axis=1), 1.0)
    assert (w.abs().to_numpy() <= 0.25 + 1e-9).all()


def test_the_expression_factory_evaluates_panels_with_peer_groups(monkeypatch, tmp_path):
    from research import expression_factory as XF
    assert XF.PANEL_NEUTRALIZATION == "group"
    lake = XF.Lake(XF.Paths(tmp_path / "desk"), meta={})
    from research import universe_policy as up
    monkeypatch.setattr(up, "peer_class", lambda s: GROUPS.get(s))
    assert lake.peer_groups(["EURUSD", "EURGBP", "XXX"]) == {
        "EURUSD": "fx_usd", "EURGBP": "fx_cross", "XXX": None}
    seen = {}

    def spy(expr, frames, sym, memos=None, *, groups=None, truncation=None):
        seen.update(groups=groups, truncation=truncation)
        return pd.Series(dtype=float)

    monkeypatch.setattr(XF.dsl, "evaluate_cell", spy)
    fac = XF.Factory.__new__(XF.Factory)
    fac.lake = lake
    fac.memos = {}
    fac.cache = None

    class W:
        def __init__(self) -> None:
            self.asset_class, self.frames = "forex", {}

    lake.worlds = {"EURUSD": W(), "EURGBP": W()}
    fac.evaluate(["xzscore", ["delta", "close", 4]], "EURUSD")
    assert seen["groups"] == {"EURUSD": "fx_usd", "EURGBP": "fx_cross"}
    assert seen["truncation"] is XF.PANEL_TRUNCATION


def test_the_panel_setting_rides_each_cell_and_splits_its_dedupe_key(monkeypatch):
    """The Auditor's should-fix on #1028: the same AST under market z-scoring and under group
    neutralisation are two computations, so the setting is on the cell's own row, its campaign
    row, its registry params and its donation provenance, and in the dedupe/twin key."""
    from research import expression_factory as XF
    z_expr = ["xzscore", ["delta", "close", 4]]
    single = ["delta", "close", 4]
    rank_only = ["xrank", ["delta", "close", 4]]

    monkeypatch.setattr(XF, "PANEL_NEUTRALIZATION", "market")
    monkeypatch.setattr(XF, "PANEL_TRUNCATION", None)
    market = XF.Cell(expr=z_expr, symbol="EURUSD", hold=6)
    market_key = market.key
    assert market.as_dict()["panel_settings"] == {"xzscore_neutralization": "market"}
    # the pre-setting computation keeps its bare key, so an old seen.json still dedupes it
    assert market_key.endswith(XF.dsl.canonical_key(z_expr))

    monkeypatch.setattr(XF, "PANEL_NEUTRALIZATION", "group")
    group = XF.Cell(expr=z_expr, symbol="EURUSD", hold=6)
    group_key = group.key                 # the settings are module constants, fixed per pass
    assert group_key != market_key
    assert group.as_dict()["panel_settings"] == {"xzscore_neutralization": "group"}

    monkeypatch.setattr(XF, "PANEL_TRUNCATION", 0.25)
    capped = XF.Cell(expr=z_expr, symbol="EURUSD", hold=6)
    assert capped.key not in (market_key, group_key)
    ps = capped.as_dict()["panel_settings"]
    assert ps == {"xzscore_neutralization": "group", "truncation": 0.25}

    # a single-series or xrank-only cell carries no setting and its key never changes
    for e in (single, rank_only):
        c = XF.Cell(expr=e, symbol="EURUSD", hold=6)
        assert c.as_dict()["panel_settings"] == {}
        assert c.key.endswith(XF.dsl.canonical_key(e))

    # the duplicate-AST check: a seen market-z key does not block the group cell
    seen = {market_key}
    assert group_key not in seen

    # campaign row, registry params and donation provenance all carry it
    camp = XF.Campaign.__new__(XF.Campaign)
    camp.rows, camp.pass_counts = {}, dict.fromkeys(XF.CAMPAIGN_STATES, 0)
    assert camp.propose(capped)["panel_settings"] == ps
    row = capped.as_dict()
    assert XF._panel_params(row) == {"panel_settings": ps}
    assert XF._panel_params(XF.Cell(expr=single, symbol="EURUSD", hold=6).as_dict()) == {}

    fac = XF.Factory.__new__(XF.Factory)
    fac.counts = {"survivors": [{"cell": row, "t1": {"side_mode": "follow"}, "t2": {},
                                 "orthogonality": 1.0, "falsifier": "f"}]}
    fac.lake = XF.Lake(XF.Paths(Path("/nonexistent")), meta={})
    fac.lake.worlds = {}
    cand = fac._candidates()[0]
    assert cand["panel_settings"] == ps
    assert cand["params"]["panel_settings"] == ps
    assert cand["exact_rule"]["params"]["panel_settings"] == ps

    class _Credits:
        def op_weight(self, op: str, klass: str) -> float:
            return 1.0

    fac.credits = _Credits()
    assert fac._provenance(row, "", None, None)["panel_settings"] == ps
