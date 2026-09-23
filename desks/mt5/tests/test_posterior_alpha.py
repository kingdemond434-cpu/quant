"""POSTERIOR ALPHA -- the posterior is the product, so these pin the arithmetic, not the prose.

What is fenced here, and why each one is worth a test:

  * the NIG update against the closed form written out by hand -- if kappa_n, mu_n, a_n or b_n
    ever drifts, every number this desk publishes about an edge drifts with it silently;
  * the Student-t CDF/quantile against scipy, because they are hand-rolled here (numpy only) and
    a wrong tail is a wrong P(mu > 0), which is the one field a promoter would read;
  * SHRINKAGE IN BOTH DIRECTIONS: 60 trades at +0.3R stays credible (rule 2 -- strong evidence
    must be allowed to say so), 5 trades at the same +0.3R collapses toward zero with an interval
    that straddles it (rule 1 -- thin evidence never buys size);
  * the evidence rules: forward-phase rows only, a moments fallback that says it is one, a 0.0 R
    stamped on a paying fill dropped rather than counted as an observation of no edge;
  * UNMEASURED as a real answer -- absent inputs, rho without 20 common days, decay without the
    hazard report -- because a clean zero in place of any of those is a lie the desk would size on.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import posterior_alpha as pa  # noqa: E402

UNMEASURED = pa.UNMEASURED
DAY0 = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)


def _stamp(i: int) -> str:
    return (DAY0 + timedelta(days=i)).isoformat()


def _series(mean: float, sd: float, n: int, seed: int) -> list[float]:
    """n draws whose sample mean is EXACTLY `mean`, so the closed form is checkable by hand."""
    a = np.random.default_rng(seed).normal(0.0, sd, n)
    return [float(v) for v in (a - a.mean() + mean)]


@pytest.fixture
def desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An empty desk tree with every input path of the organ pointed into it."""
    data, reports = tmp_path / "data", tmp_path / "reports"
    shadow = reports / "shadow"
    data.mkdir(parents=True)
    shadow.mkdir(parents=True)
    monkeypatch.setattr(pa, "SLEEVES", data / "sleeves.json")
    monkeypatch.setattr(pa, "LIVE_LEDGER", data / "live_ledger.jsonl")
    monkeypatch.setattr(pa, "SHADOW_DIR", shadow)
    monkeypatch.setattr(pa, "SHADOW_STATE", shadow / "shadow_state.json")
    monkeypatch.setattr(pa, "HAZARD", reports / "ALPHA_HAZARD.json")
    monkeypatch.setattr(pa, "OUT", reports / "POSTERIOR_ALPHA.json")
    return tmp_path


def _write_sleeves(desk: Path, rows: list[dict]) -> None:
    pa.SLEEVES.write_text(json.dumps({"sleeves": rows}), "utf-8")


def _write_fills(desk: Path, fills: list[dict]) -> None:
    pa.LIVE_LEDGER.write_text("\n".join(json.dumps(f) for f in fills) + "\n", "utf-8")


def _live(name: str, values: list[float], *, family: str = "carry", symbol: str = "EURUSD",
          day0: int = 0) -> tuple[dict, list[dict]]:
    sleeve = {"name": name, "symbol": symbol, "family": family, "status": "LIVE"}
    fills = [{"sleeve": name, "symbol": symbol, "r_multiple": v, "pl_quote": 10.0 * v,
              "r_unreconstructible": False, "time": _stamp(day0 + i)}
             for i, v in enumerate(values)]
    return sleeve, fills


def _by_name(payload: dict[str, Any]) -> dict[str, dict]:
    return {str(r["name"]): r for r in payload["sleeves"]}


# ------------------------------------------------------------------- shrinkage, in both senses
def test_a_strong_live_sleeve_is_credible_and_still_shrunk(desk: Path) -> None:
    sleeve, fills = _live("strong_carry_asia", _series(0.3, 0.4, 60, seed=11))
    _write_sleeves(desk, [sleeve])
    _write_fills(desk, fills)

    row = _by_name(pa.run(write=False))["strong_carry_asia"]

    assert row["n"] == 60
    assert row["basis"] == "live_ledger"
    # 60 trades against 30 prior pseudo-trades: mu_n = 60 * 0.3 / 90, exactly.
    assert row["mu_mean"] == pytest.approx(0.2, abs=1e-6)
    assert row["p_positive"] > 0.9
    assert row["edge_credible"] is True
    assert row["mu_p05"] > 0.0 and row["mu_p95"] > row["mu_p05"]
    # The predictive Sharpe carries parameter uncertainty, so it sits below the sample Sharpe.
    assert 0.0 < row["sharpe_pp"] < 0.2 / 0.4


def test_a_thin_sleeve_collapses_toward_zero_with_a_straddling_interval(desk: Path) -> None:
    strong, strong_fills = _live("strong_carry_asia", _series(0.3, 0.4, 60, seed=11))
    thin, thin_fills = _live("thin_gap_asia", _series(0.3, 0.4, 5, seed=5),
                             family="overnight_gap_decay", symbol="AUDUSD", day0=100)
    _write_sleeves(desk, [strong, thin])
    _write_fills(desk, strong_fills + thin_fills)

    rows = _by_name(pa.run(write=False))
    weak, hard = rows["thin_gap_asia"], rows["strong_carry_asia"]

    assert weak["n"] == 5
    assert weak["mu_mean"] == pytest.approx(5 * 0.3 / 35, abs=1e-6)   # 0.0429, not 0.30
    assert weak["mu_mean"] < hard["mu_mean"]
    assert weak["p_positive"] < pa.CREDIBLE_P
    assert weak["edge_credible"] is False
    assert weak["mu_p05"] < 0.0 < weak["mu_p95"]
    # Thin evidence is WIDER, never smaller: the same sample mean buys a bigger interval.
    assert (weak["mu_p95"] - weak["mu_p05"]) > (hard["mu_p95"] - hard["mu_p05"])


def test_a_family_pools_its_members_and_each_shrinks_toward_the_others(desk: Path) -> None:
    big, big_fills = _live("a_carry_asia", _series(0.4, 0.3, 40, seed=3))
    small, small_fills = _live("b_carry_asia", _series(0.2, 0.3, 10, seed=4),
                               symbol="GBPUSD", day0=200)
    _write_sleeves(desk, [big, small])
    _write_fills(desk, big_fills + small_fills)

    payload = pa.run(write=False)
    family = payload["families"]["carry"]
    rows = _by_name(payload)

    assert family["n_members"] == 2
    assert family["n_obs"] == 50 and family["n_measured"] == 50
    # pooled mean = (40*0.4 + 10*0.2)/50 = 0.36; posterior = 50*0.36/80.
    assert family["mu_mean"] == pytest.approx(50 * 0.36 / 80, abs=1e-6)
    # LEAVE ONE OUT: no sleeve shrinks toward itself.
    assert rows["a_carry_asia"]["mu_family"] == pytest.approx(10 * 0.2 / 40, abs=1e-6)
    assert rows["b_carry_asia"]["mu_family"] == pytest.approx(40 * 0.4 / 70, abs=1e-6)
    assert rows["a_carry_asia"]["shrink_to_family"] == pytest.approx(30 / 70, abs=1e-6)
    blend = rows["a_carry_asia"]
    assert min(blend["mu_mean"], blend["mu_family"]) <= blend["mu_shrunk_family"] <= max(
        blend["mu_mean"], blend["mu_family"])


def test_pooling_equals_a_direct_fit_on_the_concatenated_sample() -> None:
    left, right = _series(0.4, 0.3, 17, seed=1), _series(-0.1, 0.8, 23, seed=2)

    def moments(values: list[float]) -> tuple[float, float, float]:
        a = np.asarray(values, dtype=float)
        return float(a.size), float(a.mean()), float(((a - a.mean()) ** 2).sum())

    pooled = pa.pool([moments(left), moments(right)])
    direct = moments(left + right)
    for got, want in zip(pooled, direct, strict=True):
        assert got == pytest.approx(want, rel=1e-12, abs=1e-12)


# -------------------------------------------------------------------------------- rho and decay
def test_rho_is_measured_against_the_rest_of_the_book_and_unmeasured_without_20_days(
        desk: Path) -> None:
    swing = [float((i % 5) - 2) for i in range(24)]
    a, a_fills = _live("a_carry_asia", swing)
    b, b_fills = _live("b_carry_asia", [-v for v in swing], symbol="GBPUSD")
    c, c_fills = _live("c_carry_asia", _series(0.2, 0.3, 5, seed=9), symbol="USDJPY", day0=300)
    _write_sleeves(desk, [a, b, c])
    _write_fills(desk, a_fills + b_fills + c_fills)

    rows = _by_name(pa.run(write=False))

    assert rows["a_carry_asia"]["rho_days"] == 24
    assert rows["a_carry_asia"]["rho_book"] == pytest.approx(-1.0, abs=1e-9)
    assert rows["b_carry_asia"]["rho_book"] == pytest.approx(-1.0, abs=1e-9)
    assert rows["c_carry_asia"]["rho_book"] == UNMEASURED
    assert rows["c_carry_asia"]["rho_days"] == 5


def test_decay_is_unmeasured_without_the_hazard_report_and_read_with_it(desk: Path) -> None:
    sleeve, fills = _live("a_carry_asia", _series(0.3, 0.4, 25, seed=7))
    _write_sleeves(desk, [sleeve])
    _write_fills(desk, fills)

    without = pa.run(write=False)
    assert _by_name(without)["a_carry_asia"]["decay_p"] == UNMEASURED
    assert any("hazard report absent" in note for note in without["unmeasured"])

    pa.HAZARD.write_text(json.dumps(
        {"sleeves": {"a_carry_asia": {"p_die_k": {"k7": 0.10, "k30": 0.42}}}}), "utf-8")
    with_card = _by_name(pa.run(write=False))["a_carry_asia"]

    assert with_card["decay_p"] == pytest.approx(0.42)   # the longest horizon published


# --------------------------------------------------------------------- what counts as evidence
def test_a_zero_r_stamped_on_a_paying_fill_is_dropped_not_counted(desk: Path) -> None:
    _write_sleeves(desk, [{"name": "a_carry_asia", "symbol": "EURUSD", "family": "carry",
                           "status": "LIVE"}])
    _write_fills(desk, [
        {"sleeve": "a_carry_asia", "r_multiple": 0.0, "pl_quote": 57.75, "time": _stamp(0)},
        {"sleeve": "a_carry_asia", "r_multiple": 0.9, "pl_quote": 9.0, "time": _stamp(1),
         "r_unreconstructible": True},
        {"sleeve": "a_carry_asia", "r_multiple": 0.25, "pl_quote": 2.5, "time": _stamp(2)},
        {"sleeve": "a_carry_asia", "r_multiple": 0.0, "pl_quote": 0.0, "time": _stamp(3)},
        {"sleeve": "[sl 4360.71]", "r_multiple": -1.0, "pl_quote": -9.0, "time": _stamp(4)},
    ])

    payload = pa.run(write=False)
    row = _by_name(payload)["a_carry_asia"]

    assert row["n"] == 2                       # the flat fill counts; the paying "0.0R" does not
    assert payload["counts"]["live_rows_dropped"] == 2
    assert "[sl 4360.71]" not in _by_name(payload)
    assert row["mu_mean"] == pytest.approx(2 * 0.125 / 32, abs=1e-6)


def test_forward_clocks_use_forward_rows_only_and_fall_back_to_declared_moments(
        desk: Path) -> None:
    state = {
        "EURUSD.carry.asia": {"status": "ACTIVE", "n": 7, "exp_r": 0.9},
        "AUDUSD.carry.asia": {"status": "ACTIVE", "n": 9, "exp_r": 0.1},
        "GBPUSD.carry.asia": {"status": "RETIRED_ORPHAN", "n": 40, "exp_r": 0.5},
    }
    pa.SHADOW_STATE.write_text(json.dumps(state), "utf-8")
    (pa.SHADOW_DIR / "ledger_EURUSD_carry_asia.json").write_text(json.dumps([
        {"phase": "historical", "r_multiple": 5.0, "exit_time": "2026-07-01 10:00:00+00:00"},
        {"phase": "historical", "r_multiple": 5.0, "exit_time": "2026-07-02 10:00:00+00:00"},
        {"phase": "forward", "r_multiple": 0.2, "exit_time": "2026-08-01 10:00:00+00:00"},
        {"phase": "forward", "r_multiple": 0.6, "exit_time": "2026-08-02 10:00:00+00:00"},
        {"phase": "forward", "r_multiple": -0.4, "exit_time": "2026-08-03 10:00:00+00:00"},
        {"phase": "forward", "r_multiple": 0.4, "exit_time": "2026-08-04 10:00:00+00:00"},
    ]), "utf-8")

    payload = pa.run(write=False)
    rows = _by_name(payload)

    measured = rows["EURUSD.carry.asia"]
    assert measured["basis"] == "shadow_ledger_forward"
    assert measured["n"] == 4                                  # the two historical rows are out
    assert measured["lane"] == "forward" and measured["family"] == "carry"
    assert measured["mu_mean"] == pytest.approx(4 * 0.2 / 34, abs=1e-6)

    imputed = rows["AUDUSD.carry.asia"]
    assert imputed["basis"] == "shadow_moments"
    assert imputed["n"] == 9 and imputed["sigma_sample"] == UNMEASURED
    assert imputed["mu_mean"] == pytest.approx(9 * 0.1 / 39, abs=1e-6)

    assert "GBPUSD.carry.asia" not in rows                     # not a running clock
    assert payload["counts"]["skipped_clocks_by_status"] == {"RETIRED_ORPHAN": 1}


def test_absent_inputs_are_unmeasured_and_the_artifact_is_still_written(desk: Path) -> None:
    payload = pa.run()

    assert payload["n_sleeves"] == 0 and payload["n_credible"] == 0
    assert any("live sleeve registry" in n for n in payload["unmeasured"])
    assert any("forward clocks unreadable" in n for n in payload["unmeasured"])
    assert any("hazard report absent" in n for n in payload["unmeasured"])
    assert set(payload["inputs"].values()) == {"absent"}
    assert json.loads(pa.OUT.read_text("utf-8"))["n_sleeves"] == 0


def test_every_published_row_carries_the_contract_fields(desk: Path) -> None:
    sleeve, fills = _live("a_carry_asia", _series(0.3, 0.4, 25, seed=13))
    _write_sleeves(desk, [sleeve])
    _write_fills(desk, fills)

    row = _by_name(pa.run(write=False))["a_carry_asia"]

    assert set(row) >= {"name", "lane", "family", "symbol", "n", "mu_mean", "mu_sd", "mu_p05",
                        "mu_p95", "p_positive", "sigma_mean", "sharpe_pp", "rho_book", "decay_p",
                        "edge_credible", "basis"}
    assert row["lane"] == "live" and row["family"] == "carry" and row["symbol"] == "EURUSD"


# ------------------------------------------------------------------------------ the arithmetic
def test_the_nig_update_matches_the_closed_form() -> None:
    sample = [0.4, -0.2, 0.9, 0.1]                     # n = 4, mean = 0.3
    mean = 0.3
    sumsq = sum((v - mean) ** 2 for v in sample)
    n0, a0, sigma0 = 30.0, pa.PRIOR_A0, 1.0

    post = pa.nig_update(4, mean, sumsq, n0=n0, mu0=0.0, a0=a0, sigma0=sigma0)

    assert post["kappa_n"] == pytest.approx(34.0)
    assert post["mu_n"] == pytest.approx(4 * 0.3 / 34.0)
    assert post["a_n"] == pytest.approx(a0 + 2.0)
    assert post["b_n"] == pytest.approx(
        (a0 - 1.0) * sigma0 ** 2 + sumsq / 2.0 + (30.0 * 4 * 0.3 ** 2) / (2 * 34.0))

    out = pa.summarise(post)
    nu = 2 * post["a_n"]
    scale = (post["b_n"] / (post["a_n"] * post["kappa_n"])) ** 0.5
    assert out["mu_mean"] == pytest.approx(post["mu_n"], abs=1e-6)
    assert out["p_positive"] == pytest.approx(pa._t_cdf(post["mu_n"] / scale, nu), abs=1e-6)
    assert out["mu_p05"] == pytest.approx(post["mu_n"] + scale * pa._t_ppf(0.05, nu), abs=1e-6)
    assert out["mu_p95"] == pytest.approx(post["mu_n"] + scale * pa._t_ppf(0.95, nu), abs=1e-6)
    assert out["sigma_mean"] == pytest.approx((post["b_n"] / (post["a_n"] - 1.0)) ** 0.5, abs=1e-6)
    # An empty sample is the prior exactly: no edge, no evidence, no verdict dressed as one.
    assert pa.summarise(pa.nig_update(0, 0.0, 0.0))["mu_mean"] == 0.0
    assert pa.summarise(pa.nig_update(0, 0.0, 0.0))["p_positive"] == pytest.approx(0.5, abs=1e-9)


def test_the_hand_rolled_student_t_matches_scipy() -> None:
    stats = pytest.importorskip("scipy.stats")
    for nu in (3.0, 8.0, 63.0):
        for t in (-4.0, -1.0, -0.25, 0.0, 0.25, 1.0, 4.0):
            assert pa._t_cdf(t, nu) == pytest.approx(float(stats.t.cdf(t, nu)), abs=1e-10)
        for p in (0.01, 0.05, 0.5, 0.95, 0.99):
            assert pa._t_ppf(p, nu) == pytest.approx(float(stats.t.ppf(p, nu)), abs=1e-7)


def test_the_cli_dry_run_prints_and_writes_nothing_then_the_real_pass_writes(
        desk: Path, capsys: pytest.CaptureFixture[str]) -> None:
    sleeve, fills = _live("a_carry_asia", _series(0.3, 0.4, 30, seed=17))
    _write_sleeves(desk, [sleeve])
    _write_fills(desk, fills)

    assert pa.main(["--dry-run", "--n0", "5"]) == 0
    printed = capsys.readouterr().out
    assert "POSTERIOR ALPHA" in printed and "a_carry_asia" in printed
    assert "(dry run, nothing written)" in printed
    assert not pa.OUT.exists()

    assert pa.main([]) == 0
    assert "written:" in capsys.readouterr().out
    payload = json.loads(pa.OUT.read_text("utf-8"))
    assert payload["prior"]["n0"] == pa.PRIOR_N0 and payload["n_sleeves"] == 1
    assert payload["sleeves"][0]["mu_mean"] == pytest.approx(30 * 0.3 / 60, abs=1e-6)
    # --n0 is plumbed through: a weaker prior lets the same evidence say more.
    assert pa.run(n0=5.0, write=False)["sleeves"][0]["mu_mean"] == pytest.approx(
        30 * 0.3 / 35, abs=1e-6)
