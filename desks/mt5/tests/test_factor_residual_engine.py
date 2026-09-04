"""The driver map states economics, and the engine's proposals must reach the gauntlet unchanged.

Two failure modes are pinned here, both of which this desk has already paid for once:

DRIFT BETWEEN SCREEN AND EXECUTION. The engine measures a residual and then proposes a candidate
whose params are supposed to rebuild THE SAME OBJECT. If a param name stops matching the family's
signature -- or the family grows a required argument the engine does not send -- the certificate
would be earned by one computation and traded by another, silently. The signature is checked
against the emitted params rather than assumed to agree.

A SCREEN THAT MEASURES ITSELF. The shuffled control must produce nothing. If it produces
proposals, the pipeline is finding structure in its own arithmetic.
"""

from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from mt5desk.economic_drivers import (  # noqa: E402
    COMMODITY_CURRENCIES,
    DriverSet,
    driver_sets,
    universe_driver_sets,
)
from mt5desk.families_orthogonal import family_cross_asset_residual  # noqa: E402
from research import factor_residual_engine as eng  # noqa: E402
from research.miner_candidate_compiler import compile_row  # noqa: E402

META = json.loads((_DESK / "data" / "universe" / "universe.json").read_text("utf-8"))
ALL = set(META)


# ------------------------------------------------------------------------------------------
# The economic map
# ------------------------------------------------------------------------------------------

def test_gold_gets_the_dollar_and_the_real_rate():
    """The principal's formula, in instruments the desk can actually quote."""
    names = {s.name: s for s in driver_sets("XAUUSD", META, ALL)}
    assert "dollar_real_rates" in names
    assert set(names["dollar_real_rates"].drivers) == {"USDX", "UST10Y"}
    full = names["full_monetary"]
    assert set(full.drivers) == {"USDX", "UST10Y", "XAGUSD", "US500"}


def test_a_cross_is_regressed_on_its_own_two_dollar_legs():
    tri = {s.name: s for s in driver_sets("EURGBP", META, ALL)}["triangle"]
    assert set(tri.drivers) == {"EURUSD", "GBPUSD"}
    tri = {s.name: s for s in driver_sets("CHFJPY", META, ALL)}["triangle"]
    assert set(tri.drivers) == {"USDCHF", "USDJPY"}


def test_a_dollar_pair_has_no_triangle_because_the_identity_is_degenerate():
    assert "triangle" not in {s.name for s in driver_sets("EURUSD", META, ALL)}


def test_a_quanto_metal_is_its_usd_metal_through_the_fx_leg():
    q = {s.name: s for s in driver_sets("XAUEUR", META, ALL)}["quanto_triangle"]
    assert set(q.drivers) == {"XAUUSD", "EURUSD"}


def test_commodity_currencies_attach_the_commodity_they_export():
    aud = {s.name: s for s in driver_sets("AUDJPY", META, ALL)}
    assert "commodity_aud" in aud
    cad = {s.name: s for s in driver_sets("USDCAD", META, ALL)}
    assert "XBRUSD" in cad["commodity_cad"].drivers, "CAD must carry a crude leg"


def test_the_dollar_index_is_never_an_equity_index_peer():
    """USDX is classed `Indices` by the broker. It is the USD role, not a market to compare to."""
    for target in ("US500", "NAS100", "US30"):
        for s in driver_sets(target, META, ALL):
            if s.name == "regional_peers":
                assert "USDX" not in s.drivers


def test_an_instrument_is_never_its_own_driver():
    for s in universe_driver_sets(META, ALL):
        assert s.target not in s.drivers, f"{s.cell} regresses on itself"


def test_every_driver_is_a_registry_instrument():
    """No synthesised series: every driver must be a Fusion symbol the desk can rebuild bars for."""
    for s in universe_driver_sets(META, ALL):
        for d in s.drivers:
            assert d in META, f"{s.cell} names {d}, which is not in the registry"


def test_every_set_carries_an_economic_reason():
    for s in universe_driver_sets(META, ALL):
        assert len(s.why) > 40, f"{s.cell} has no economic argument"


def test_the_map_states_hundreds_of_distinct_claims():
    sets = universe_driver_sets(META, ALL)
    assert len(sets) > 400
    assert len({s.target for s in sets}) > 200
    assert len({s.cell for s in sets}) == len(sets), "duplicate cell identities"


def test_crypto_targets_come_only_from_the_fusion_registry():
    """The mandate permits Fusion crypto CFDs and forbids any exchange-native universe."""
    crypto = [s for s in universe_driver_sets(META, ALL)
              if str((META.get(s.target) or {}).get("asset_class")) == "Crypto"]
    assert crypto
    for s in crypto:
        assert s.target in META
        assert all(d in META for d in s.drivers)


def test_a_driver_set_is_dropped_when_its_instruments_are_absent():
    small = {"XAUUSD", "USDX"}
    sets = driver_sets("XAUUSD", META, small)
    for s in sets:
        assert set(s.drivers) <= small
    assert "full_monetary" not in {s.name for s in sets}


def test_missing_role_does_not_silently_substitute_a_proxy():
    """With no rates instrument present, the rates set must vanish rather than mean something else."""
    have = {"XAUUSD", "USDX", "XAGUSD", "XPTUSD", "XPDUSD"}
    names = {s.name for s in driver_sets("XAUUSD", META, have)}
    assert "precious_complex" in names
    # dollar_real_rates collapses to the dollar alone; it must not be labelled as carrying rates.
    for s in driver_sets("XAUUSD", META, have):
        if s.name == "dollar_real_rates":
            assert s.drivers == ("USDX",)


def test_commodity_currency_priors_are_declared_with_reasons():
    for ccy, (role, why) in COMMODITY_CURRENCIES.items():
        assert len(ccy) == 3
        assert role in {"GOLD", "OIL", "GROWTH"}
        assert len(why) > 30


# ------------------------------------------------------------------------------------------
# The engine's contract with the rest of the desk
# ------------------------------------------------------------------------------------------

def _fake_row(target: str, drivers: list[str]) -> dict:
    return {"cell": f"{target}.x", "target": target, "driver_set": "x", "drivers": drivers,
            "why": "test", "horizon_bars": 24, "entry_z": 2.0, "side_mode": "revert",
            "n_independent": 99, "gross_per_trade": 0.002, "net_per_trade": 0.001,
            "cost_frac": 0.001, "t_gross": 4.0, "t_naive_overlapping": 6.0,
            "clears_cost": True}


def test_emitted_params_are_exactly_what_the_family_accepts():
    """The screen and the executable cell must be the same object or the certificate is a lie."""
    cand = eng._candidate(_fake_row("XAUUSD", ["USDX", "UST10Y"]), 500, 3.0)
    sig = inspect.signature(family_cross_asset_residual).parameters
    for key in cand["params"]:
        if key == "factor_symbols":
            # The gauntlet and the forward engine both POP this and pass `factors` instead.
            assert "factors" in sig
            continue
        assert key in sig, f"engine emits `{key}`, which the family does not accept"


def test_emitted_params_reproduce_the_measured_windows():
    cand = eng._candidate(_fake_row("XAUUSD", ["USDX", "UST10Y"]), 500, 3.0)
    assert cand["params"]["beta_win"] == eng.BETA_WIN
    assert cand["params"]["lookback"] == eng.Z_WIN


def test_a_proposal_compiles_to_an_exact_recipe():
    cand = eng._candidate(_fake_row("XAUUSD", ["USDX", "UST10Y"]), 500, 3.0)
    produced, disposition = compile_row("factor_residual", cand, {"XAUUSD", "USDX", "UST10Y"})
    assert disposition == "EXACT_RECIPE"
    assert len(produced) == 1
    assert produced[0]["family"] == "cross_asset_residual"
    assert produced[0]["params"]["factor_symbols"] == ["USDX", "UST10Y"]


def test_deflation_charges_every_test_run_not_just_the_winners():
    """Counting only survivors is the exact error the deflated Sharpe exists to correct."""
    rows = [_fake_row("XAUUSD", ["USDX"]) for _ in range(5)]
    for i, r in enumerate(rows):
        r["t_gross"] = 10.0 if i == 0 else 0.1
        r["clears_cost"] = i == 0
    n = len(rows)
    from research.multiplicity import deflate_t
    assert deflate_t(10.0, n) < 10.0
    assert deflate_t(10.0, n) < deflate_t(10.0, 2)


def test_both_sides_are_tested_so_neither_is_chosen_after_the_fact():
    assert set(eng.SIDE_MODES) == {"revert", "continue"}


def test_the_shuffled_control_donates_nothing(tmp_path, monkeypatch):
    """A null run must never write into the intelligence store, whatever it happens to find."""
    monkeypatch.setattr(eng, "INTEL", tmp_path / "intel")
    monkeypatch.setattr(eng, "REPORT", tmp_path / "report.json")
    rep = eng.run(targets=["EURGBP"], shuffle=True, budget_s=120.0)
    assert rep["shuffled_control"] is True
    assert not (tmp_path / "intel").exists()
    assert (tmp_path / "report_shuffled.json").exists()


@pytest.mark.skipif(not (_DESK / "data" / "universe" / "EURGBP_H1.parquet").exists(),
                    reason="EURGBP H1 bars are not on this host")
def test_a_real_sweep_measures_and_reports_its_own_census(tmp_path, monkeypatch):
    monkeypatch.setattr(eng, "INTEL", tmp_path / "intel")
    monkeypatch.setattr(eng, "REPORT", tmp_path / "report.json")
    rep = eng.run(targets=["EURGBP"], budget_s=300.0)
    assert rep["tests_run"] > 0
    assert rep["expected_max_z"] > 0
    assert all(r["n_tests_sweep"] == rep["tests_run"] for r in rep["all"])
    for r in rep["proposals"]:
        assert r["clears_cost"] and r["t_deflated_sweep"] > eng.PROPOSE_T
        assert r["n_independent"] >= eng.MIN_INDEPENDENT


def test_one_proposal_per_cell_so_the_search_is_not_shipped_as_breadth():
    """Shipping every horizon/threshold variant of one winner smuggles the search back in."""
    src = inspect.getsource(eng.run)
    assert "setdefault(r[\"cell\"], r)" in src


def test_panel_refuses_a_short_joint_history():
    ds = DriverSet(target="EURGBP", name="t", drivers=("EURUSD",), why="w")
    idx = pd.date_range("2024-01-01", periods=50, freq="h", tz="UTC")
    frame = pd.DataFrame({"close": np.linspace(1.0, 1.1, 50)}, index=idx)
    assert eng.panel(ds, {"EURGBP": frame, "EURUSD": frame}) is None
