"""THE MACRO STATE ENGINE, BUILT OVER A WORLD WHOSE EVERY EFFECT IS PLANTED.

An organ that reads a broker registry, a FRED archive, 250 parquets and a causal graph is exactly
the organ nobody can eyeball on live data: a beta that broke looks identical to a window that
happened to be noisy. So every series here is generated with a KNOWN answer and each test asserts
the engine recovered THAT answer:

  * a beta that genuinely flips at bar 300 is found within one window of bar 300, with a small
    permutation p-value -- and a stationary control with the same noise does not fire;
  * the change point is POINT-IN-TIME: truncating the series at t leaves the score at t bit-for-bit
    identical, so nothing the scan reports at t used a bar after t;
  * the trailing rank agrees print-for-print with `libs.portfolio.macro_state`'s, so the two
    organs mean the same thing by "the top of its year";
  * a single-name equity is MEASURED and published and never donated, at either end of an edge;
  * an absent causal graph yields UNMEASURED rows and a written report, never a crash;
  * `--dry-run` writes nothing and donates nothing.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import macro_state_engine as mse  # noqa: E402
from research import universe_policy as up  # noqa: E402

#: The synthetic broker registry. NAS100 is an index, EURUSD/USDJPY are the hypothesis lane,
#: XAUUSD is metals, and Apple is a share CFD settling in USD -- tradable, event lane, never hunted.
REGISTRY: dict[str, dict[str, Any]] = {
    "NAS100": {"asset_class": "Indices"},
    "EURUSD": {"asset_class": "Forex"},
    "USDJPY": {"asset_class": "Forex"},
    "XAUUSD": {"asset_class": "Commodities"},
    "Apple": {"asset_class": "Equities", "currency_profit": "USD"},
}


# ------------------------------------------------------------------------------ synthetic world
def _prices(rets: np.ndarray, start: float = 100.0) -> np.ndarray:
    return np.asarray(start * np.exp(np.cumsum(rets)), dtype=float)


def _write_parquet(uni: Path, symbol: str, rets: np.ndarray) -> None:
    uni.mkdir(parents=True, exist_ok=True)
    idx = pd.date_range("2022-01-03", periods=rets.size, freq="D", tz="UTC", name="time")
    pd.DataFrame({"close": _prices(rets)}, index=idx).to_parquet(uni / f"{symbol}_D1.parquet")


def _flip_pair(n: int = 600, brk: int = 300, seed: int = 7) -> tuple[np.ndarray, np.ndarray]:
    """x, and a y whose beta on x is +1.0 before `brk` and -1.0 after it. Nothing else changes."""
    rng = np.random.default_rng(seed)
    x = rng.normal(0.0, 0.01, n)
    beta = np.where(np.arange(n) < brk, 1.0, -1.0)
    y = beta * x + rng.normal(0.0, 0.002, n)
    return x, y


def _stationary_pair(n: int = 600, seed: int = 11) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    x = rng.normal(0.0, 0.01, n)
    y = 1.0 * x + rng.normal(0.0, 0.002, n)
    return x, y


def _flip_on(x: np.ndarray, brk: int = 300, seed: int = 99) -> np.ndarray:
    """A responder whose beta on THIS driver flips at `brk` -- the planted edge change."""
    rng = np.random.default_rng(seed)
    beta = np.where(np.arange(x.size) < brk, 1.0, -1.0)
    return np.asarray(beta * x + rng.normal(0.0, 0.002, x.size), dtype=float)


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """One synthetic desk: registry, bars, graph and report path all under tmp_path."""
    uni = tmp_path / "universe"
    (tmp_path / "reports").mkdir(parents=True, exist_ok=True)
    (uni).mkdir(parents=True, exist_ok=True)
    (uni / "universe.json").write_text(json.dumps(REGISTRY), "utf-8")

    # NAS100 is the driver; EURUSD and Apple are two responders whose beta ON IT flips at bar
    # 300, and USDJPY's beta on APPLE flips too. So the equity edges are as strong as the FX one
    # and the only thing that separates them at the door is the mandate.
    x, y = _flip_pair()
    y_apple = _flip_on(x, seed=23)
    _write_parquet(uni, "NAS100", x)
    _write_parquet(uni, "EURUSD", y)
    _write_parquet(uni, "Apple", y_apple)
    _write_parquet(uni, "USDJPY", _flip_on(y_apple, seed=31))
    _write_parquet(uni, "XAUUSD", _stationary_pair(seed=37)[1])

    monkeypatch.setattr(mse, "UNI", uni)
    monkeypatch.setattr(mse, "REGISTRY_PATH", uni / "universe.json")
    monkeypatch.setattr(mse, "REPORT", tmp_path / "reports" / "MACRO_STATE_ENGINE.json")
    monkeypatch.setattr(mse, "WORLD_REPORT", tmp_path / "reports" / "WORLD_CAUSAL_GRAPH.json")
    monkeypatch.setattr(mse, "WORLD_GRAPH", tmp_path / "data_world_causal_graph.json")
    monkeypatch.setattr(mse, "CROSS_ASSET", tmp_path / "reports" / "CROSS_ASSET_GRAPH.json")
    # The FRED archive is EMPTY unless a test plants one: a test that silently read the live
    # archive would pass or fail on whatever the collector last fetched.
    monkeypatch.setattr(mse, "fred_levels", lambda: {})
    monkeypatch.setattr(up, "UNIVERSE", uni / "universe.json")
    mse._registry.cache_clear()
    up._registry.cache_clear()
    yield tmp_path
    mse._registry.cache_clear()
    up._registry.cache_clear()


def _graph(tmp_path: Path, edges: list[dict[str, Any]]) -> None:
    (tmp_path / "reports" / "WORLD_CAUSAL_GRAPH.json").write_text(
        json.dumps({"generated_at": "2026-09-22T00:00:00+00:00", "admitted_edges": [],
                    "recorded_not_admitted": edges}), "utf-8")


# ------------------------------------------------------------------- (a) the mechanism itself
def test_planted_beta_flip_is_found_at_its_own_date() -> None:
    """The break is at bar 300. A trailing double window can only SEE it once the post window is
    clear of it, so the honest claim is 'detected between 300 and 300 + window' -- and that is
    what is asserted, because a test that demanded bar 300 exactly would be demanding a look
    into the future."""
    x, y = _flip_pair(n=600, brk=300)
    res = mse.changepoint(x, y, window=100, n_perm=199, seed=5)
    assert res["status"] == "measured"
    assert res["kind"] == "sign_flip", res
    assert 300 <= int(res["index"]) <= 300 + 100 + 20, res["index"]
    assert float(res["p_perm"]) <= 0.01, res["p_perm"]
    assert float(res["beta_pre"]) > 0.5 and float(res["beta_post"]) < -0.5, res


@pytest.mark.parametrize("seed", [11, 13, 17])
def test_stationary_control_does_not_fire(seed: int) -> None:
    """Same noise, same scan, one constant beta. The permutation null is the whole point: a
    scan over ~400 candidate break points finds a 'best' one every time, and only the null says
    whether it means anything."""
    x, y = _stationary_pair(n=600, seed=seed)
    res = mse.changepoint(x, y, window=100, n_perm=199, seed=3)
    assert res["status"] == "measured"
    assert float(res["p_perm"]) > 0.05, (seed, res["p_perm"], res["abs_z"])


def test_changepoint_scores_are_point_in_time() -> None:
    """THE ANTI-LOOKAHEAD PROOF. The score the scan reports at t must be computable at t. So run
    the scan on the whole series, truncate the series at t, run it again, and demand the value
    at t be identical -- if any window reached past t the two would differ."""
    x, y = _flip_pair(n=600, brk=300)
    z_full, *_ = mse._scan(x, y, 100)
    for t in (250, 399, 450, 599):
        z_trunc, *_ = mse._scan(x[: t + 1], y[: t + 1], 100)
        assert np.isfinite(z_full[t]) == np.isfinite(z_trunc[t])
        if np.isfinite(z_full[t]):
            assert z_full[t] == pytest.approx(float(z_trunc[t]), abs=1e-12), t


def test_rolling_ols_matches_a_plain_least_squares_fit() -> None:
    """The cumulative-sum recursion is an optimisation, not a different estimator."""
    rng = np.random.default_rng(2)
    x = rng.normal(size=300)
    y = 0.7 * x + rng.normal(scale=0.3, size=300)
    beta, se, corr = mse._rolling_ols(x, y, 60)
    i = 199
    w = slice(i - 59, i + 1)
    ref = np.polyfit(x[w], y[w], 1)[0]
    assert float(beta[i]) == pytest.approx(float(ref), rel=1e-9)
    assert float(corr[i]) == pytest.approx(float(np.corrcoef(x[w], y[w])[0, 1]), rel=1e-9)
    assert float(se[i]) > 0.0


def test_pit_rank_agrees_with_macro_state() -> None:
    """Two organs, one definition of 'the top of its year'."""
    from libs.portfolio.macro_state import _rank as macro_rank
    rng = np.random.default_rng(1)
    v = np.cumsum(rng.normal(size=400))
    mine, theirs = mse.pit_rank(v, 250), macro_rank(v, 250)
    assert np.array_equal(np.isnan(mine), np.isnan(theirs))
    assert np.allclose(mine[~np.isnan(mine)], theirs[~np.isnan(theirs)], atol=1e-12)


def test_short_series_is_unmeasured_not_guessed() -> None:
    res = mse.changepoint(np.zeros(40), np.zeros(40), window=100, n_perm=9)
    assert res["status"] == "UNMEASURED" and "fewer than" in res["why"]


# ------------------------------------------------------------------------ (b) the two-lane door
def test_equity_is_measured_but_never_donated(world: Path, monkeypatch: pytest.MonkeyPatch,
                                              ) -> None:
    """Apple's edge breaks exactly as EURUSD's does. It is measured, it is published, and the
    door refuses it with the mandate's own reason -- at the DST end here and at the SRC end in
    the second edge, because a hypothesis conditions on its driver as much as it trades its
    responder."""
    _graph(world, [{"src": "NAS100", "dst": "EURUSD", "lag": 0, "clock": "D1", "strength": 0.4},
                   {"src": "NAS100", "dst": "Apple", "lag": 0, "clock": "D1", "strength": 0.4},
                   {"src": "Apple", "dst": "USDJPY", "lag": 0, "clock": "D1", "strength": 0.2}])
    sent: list[list[dict[str, Any]]] = []
    monkeypatch.setattr(mse, "_donate", lambda c, n: sent.append(c) or Path("intake.json"))
    rep = mse.build(budget_s=120.0, n_perm=99, max_donations=5, p_max=0.2)

    measured = {(r["src"], r["dst"]) for r in rep["edge_changes"]["rows"]}
    assert ("NAS100", "Apple") in measured, "the equity edge must be MEASURED"
    assert ("NAS100", "EURUSD") in measured
    donated = {c["symbol"] for c in (sent[0] if sent else [])}
    assert "EURUSD" in donated, rep["donations"]
    assert "Apple" not in donated
    assert not any(str(c.get("src") or "") == "Apple" for c in (sent[0] if sent else []))
    refusals = [r for r in rep["donations"]["refused"] if "two-lane" in r["why"]]
    assert {(r["src"], r["dst"]) for r in refusals} >= {("NAS100", "Apple"), ("Apple", "USDJPY")}
    # And the equity still appears in its region's EVENT lane, which is the measurement.
    assert "Apple" in rep["blocks"]["US"]["instruments"]["event_lane"]


def test_donated_rows_carry_the_edge_and_its_p_value(world: Path,
                                                     monkeypatch: pytest.MonkeyPatch) -> None:
    _graph(world, [{"src": "NAS100", "dst": "EURUSD", "lag": 0, "clock": "D1"}])
    sent: list[list[dict[str, Any]]] = []
    monkeypatch.setattr(mse, "_donate", lambda c, n: sent.append(c) or Path("intake.json"))
    rep = mse.build(budget_s=120.0, n_perm=99, max_donations=5, p_max=0.2)
    assert sent and len(sent[0]) == 1
    cand = sent[0][0]
    ev = cand["evidence"]
    assert cand["kind"] == "hypothesis" and cand["symbols"] == ["EURUSD"]
    assert cand["family"] in mse.registered_families()
    assert ev["edge"] == "NAS100->EURUSD" and ev["lag"] == 0
    assert ev["beta_pre"] > 0.5 > ev["beta_post"]
    assert 0.0 < ev["p_perm"] <= 0.2 and ev["n_perm"] == 99
    assert ev["t_change"] and ev["window_bars"] >= 20
    assert rep["donations"]["trials"]["n_raw"] == 1


def test_a_weak_change_is_refused_with_its_p_value(world: Path,
                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    """USDJPY and XAUUSD are independent stationary series: the scan still finds a best break,
    and the p-value is what stops it spending the shared trial budget."""
    _graph(world, [{"src": "USDJPY", "dst": "XAUUSD", "lag": 0, "clock": "D1"}])
    sent: list[Any] = []
    monkeypatch.setattr(mse, "_donate", lambda c, n: sent.append(c) or Path("x"))
    rep = mse.build(budget_s=120.0, n_perm=99, max_donations=5, p_max=0.01)
    assert rep["edge_changes"]["measured"] == 1
    assert not sent
    assert any("p_perm" in r["why"] for r in rep["donations"]["refused"])


# ------------------------------------------------------------- (c) absence is a written verdict
def test_absent_graph_yields_unmeasured_rows_and_a_report(world: Path,
                                                          monkeypatch: pytest.MonkeyPatch,
                                                          ) -> None:
    monkeypatch.setattr(mse, "_donate", lambda c, n: pytest.fail("nothing to donate"))
    assert mse.main(["--once", "--budget-s", "60", "--n-perm", "9"]) == 0
    doc = json.loads(mse.REPORT.read_text("utf-8"))
    ec = doc["edge_changes"]
    assert ec["pairs"] == 0 and ec["measured"] == 0
    assert ec["unmeasured_rows"] and "no causal-graph artifact" in ec["unmeasured_rows"][0]["why"]
    assert doc["inputs"]["world_causal_graph_report"]["status"] == "absent"
    assert doc["inputs"]["cross_asset_graph"]["status"] == "absent"
    # The region half is unaffected by the missing neighbour -- that is why it is a verdict.
    assert doc["blocks"]["US"]["states"]["growth"]["status"] == "measured"


def test_everything_absent_still_writes_a_report(tmp_path: Path,
                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mse, "UNI", tmp_path / "nope")
    monkeypatch.setattr(mse, "REGISTRY_PATH", tmp_path / "nope" / "universe.json")
    monkeypatch.setattr(mse, "REPORT", tmp_path / "R.json")
    monkeypatch.setattr(mse, "WORLD_REPORT", tmp_path / "a.json")
    monkeypatch.setattr(mse, "WORLD_GRAPH", tmp_path / "b.json")
    monkeypatch.setattr(mse, "CROSS_ASSET", tmp_path / "c.json")
    monkeypatch.setattr(mse, "fred_levels", lambda: {})
    mse._registry.cache_clear()
    try:
        assert mse.main(["--once", "--budget-s", "20", "--n-perm", "9"]) == 0
        doc = json.loads((tmp_path / "R.json").read_text("utf-8"))
        assert doc["status"] == "UNMEASURED" and doc["blocks"] == {}
        assert doc["inputs"]["instrument_registry"]["status"] == "absent"
    finally:
        mse._registry.cache_clear()


# --------------------------------------------------------------------- the per-country blocks
def test_blocks_are_derived_and_every_state_is_named(world: Path) -> None:
    blocks, summary, census = mse.build_blocks()
    assert set(blocks) == {"US", "EZ", "JP"}, "a block exists only where the registry put one"
    for region, block in blocks.items():
        assert set(block["states"]) == set(mse.STATES), region
        for name, row in block["states"].items():
            assert row["status"] in ("measured", "UNMEASURED")
            assert row["status"] == "measured" or row["why"], (region, name)
    us = blocks["US"]["states"]
    assert us["growth"]["status"] == "measured" and us["growth"]["instrument"] == "NAS100"
    assert 0.0 <= float(us["growth"]["value"]) <= 1.0
    assert us["risk_appetite"]["status"] == "measured"
    assert us["inflation"]["status"] == "UNMEASURED" and "FRED" in us["inflation"]["why"]
    assert us["liquidity"]["status"] == "UNMEASURED"
    assert blocks["JP"]["states"]["growth"]["status"] == "UNMEASURED"
    assert "no equity index" in blocks["JP"]["states"]["growth"]["why"]
    assert summary["measured"] + summary["unmeasured"] == summary["n_blocks"] * len(mse.STATES)
    assert census["registry_rows"] == len(REGISTRY)


def test_fred_states_light_up_when_the_archive_is_there(world: Path,
                                                        monkeypatch: pytest.MonkeyPatch) -> None:
    """The US block's inflation, policy and liquidity states are FRED's, and they are measured
    the moment the archive carries the series -- no code path changes, only the input."""
    days = tuple(str(d.date()) for d in pd.date_range("2024-01-01", periods=400, freq="D"))
    rng = np.random.default_rng(4)
    nom = tuple(4.0 + np.cumsum(rng.normal(0, 0.02, 400)))
    real = tuple(float(v) - 2.0 for v in nom)
    monkeypatch.setattr(mse, "fred_levels", lambda: {
        "DGS10": (days, nom), "DFII10": (days, real),
        "WALCL": (days[:100], tuple(7e6 + np.cumsum(rng.normal(0, 1e4, 100)))),
    })
    blocks, _, _ = mse.build_blocks()
    us = blocks["US"]["states"]
    assert us["inflation"]["status"] == "measured" and "DFII10" in us["inflation"]["basis"]
    assert us["policy_rates"]["status"] == "measured" and "DGS10" in us["policy_rates"]["basis"]
    assert us["liquidity"]["status"] == "measured" and "WALCL" in us["liquidity"]["basis"]
    assert blocks["JP"]["states"]["inflation"]["status"] == "UNMEASURED"


def test_global_factors_publish_the_cross_section(world: Path) -> None:
    blocks, _, _ = mse.build_blocks()
    g = mse.global_factors(blocks)
    assert {f"dispersion_{s}" for s in mse.STATES} <= set(g)
    assert g["dispersion_growth"]["n_blocks_measured"] >= 1
    assert g["dispersion_inflation"]["status"] == "UNMEASURED"


# ------------------------------------------------------------------------------ (d) --dry-run
def test_dry_run_writes_nothing_and_donates_nothing(world: Path,
                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    _graph(world, [{"src": "NAS100", "dst": "EURUSD", "lag": 0, "clock": "D1"}])
    monkeypatch.setattr(mse, "_donate", lambda c, n: pytest.fail("--dry-run donated"))
    assert mse.main(["--dry-run", "--budget-s", "60", "--n-perm", "19"]) == 0
    assert not mse.REPORT.exists()
    assert not (world / "reports" / "MACRO_STATE_ENGINE.json").exists()


def test_budget_stops_the_scan_and_says_so(world: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _graph(world, [{"src": "NAS100", "dst": "EURUSD", "lag": 0, "clock": "D1"},
                   {"src": "NAS100", "dst": "USDJPY", "lag": 0, "clock": "D1"},
                   {"src": "NAS100", "dst": "XAUUSD", "lag": 0, "clock": "D1"}])
    pairs, _ = mse.graph_pairs()
    rows, unmeasured, counts = mse.hunt_edges(pairs, deadline=-1.0, n_perm=9)
    assert rows == [] and unmeasured == []
    assert counts["skipped_budget"] == 3 and counts["tests_run"] == 0
