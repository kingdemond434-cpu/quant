"""THE ESTIMATOR BEHIND THE CROSS-MECHANISM MEASUREMENT, tested on data whose answer is known.

The measurement in `scripts/measure_cross_mechanism_corr.py` decides whether a portfolio-of-weak-
edges architecture is available to this desk at all, and its headline turns on one judgement call:
the mean off-diagonal correlation of the 19 mechanisms is +0.005, which reads as near-perfect
independence and is an artifact of CANCELLATION between a trend bloc and a mean-reversion bloc.
If the estimator could not tell those two situations apart, the artifact would say "nineteen
independent bets, 4.16x Sharpe ceiling" and the desk would size on it.

So the two-bloc case is the case tested, with the truth known by construction:

  * a genuinely independent panel must read as N bets;
  * a two-bloc panel whose blocs cancel must NOT, and must be FLAGGED as cancelling;
  * grouping must collapse parameter variants into one mechanism, since "two lookback settings of
    one mechanism are ONE mechanism" is the definition the whole measurement rests on;
  * a missing tape must produce NOT-READABLE-HERE rather than a number.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.measure_cross_mechanism_corr import (
    group_series,
    orthogonality_required,
    participation_ratio,
    summarise,
)


def _two_blocs(t: int = 1200, per_bloc: int = 6, within: float = 0.85, across: float = -0.75,
               seed: int = 0) -> np.ndarray:
    """Two internally-correlated blocs that are anti-correlated with each other.

    Mean off-diagonal correlation is near zero by cancellation while the true structure is two
    bets. This is the shape the real mechanism library turned out to have.
    """
    rng = np.random.default_rng(seed)
    a = rng.standard_normal(t)
    idio = rng.standard_normal((t, 2 * per_bloc))
    w_in, w_id = np.sqrt(abs(within)), np.sqrt(1.0 - abs(within))
    cols = [w_in * a + w_id * idio[:, i] for i in range(per_bloc)]
    sign = np.sign(across)
    cols += [sign * w_in * a + w_id * idio[:, per_bloc + i] for i in range(per_bloc)]
    return np.column_stack(cols)


def test_participation_ratio_reads_N_on_independent_columns() -> None:
    """The estimator's own ceiling, on data whose answer is exactly N."""
    rng = np.random.default_rng(1)
    m = rng.standard_normal((3000, 12))
    assert participation_ratio(np.corrcoef(m, rowvar=False)) == pytest.approx(12.0, abs=0.3)


def test_participation_ratio_reads_ONE_on_a_single_bet_in_many_costumes() -> None:
    rng = np.random.default_rng(2)
    factor = rng.standard_normal(2000)
    m = np.column_stack([factor + 0.02 * rng.standard_normal(2000) for _ in range(10)])
    assert participation_ratio(np.corrcoef(m, rowvar=False)) < 1.1


def test_offsetting_blocs_fool_the_MEAN_and_not_the_spectrum() -> None:
    """The finding that decided the real headline, reproduced on a known-answer panel.

    Mean off-diagonal correlation is ~0 and the equicorrelation reading is therefore "12 nearly
    independent series". The truth is two bets. The spectrum says two, the cancellation flag fires,
    and `headline_n_eff` follows the spectrum rather than the mean -- which is the only reason the
    real artifact does not claim a 4.16x Sharpe ceiling it cannot deliver.
    """
    m = _two_blocs()
    doc = summarise(np.corrcoef(m, rowvar=False), [f"s{i}" for i in range(m.shape[1])],
                    t_obs=m.shape[0])

    assert abs(doc["mean_offdiag_rho"]) < 0.1
    assert doc["mean_abs_offdiag_rho"] > 0.5
    assert doc["equicorrelation"]["n_eff"] > 6.0          # the misreading, recorded
    assert doc["cancellation_detected"] is True
    assert doc["calibrated_breadth"]["n_eff"] < 3.0       # the truth
    assert doc["headline_n_eff"] == doc["calibrated_breadth"]["n_eff"]
    assert "cancellation" not in doc["note"] or "NOT usable" in doc["note"]


def test_a_genuinely_independent_panel_is_NOT_flagged_as_cancelling() -> None:
    """The flag must not fire on data where the equicorrelation reading is correct."""
    rng = np.random.default_rng(3)
    m = rng.standard_normal((2000, 10))
    doc = summarise(np.corrcoef(m, rowvar=False), [f"s{i}" for i in range(10)], t_obs=2000)
    assert doc["cancellation_detected"] is False
    assert doc["calibrated_breadth"]["n_eff"] == pytest.approx(10.0, abs=0.6)
    assert doc["no_demeaning_applied"] is True


def test_two_parameter_settings_of_one_mechanism_are_ONE_mechanism() -> None:
    """The grouping definition the entire measurement rests on.

    Grouped by (family, subtype) the three parameter variants of `momentum/time_series_mom`
    collapse to a single series; grouped by the parameter tuple they stay three. If they did not
    collapse, the artifact would count knob settings as independent bets.
    """
    rng = np.random.default_rng(4)
    cands: list[dict[str, Any]] = []
    for lookback in (20, 40, 60):
        for sym in ("BTC", "ETH"):
            cands.append({"symbol": sym, "family": "momentum", "subtype": "time_series_mom",
                          "params": {"lookback": lookback}, "returns": rng.normal(0, 0.01, 300)})
    for sym in ("BTC", "ETH"):
        cands.append({"symbol": sym, "family": "carry", "subtype": "drift_proxy",
                      "params": {}, "returns": rng.normal(0, 0.01, 300)})

    mech_labels, mech_cols = group_series(cands, ("family", "subtype"), 300)
    var_labels, var_cols = group_series(cands, ("family", "subtype", "params"), 300)

    assert mech_labels == ["carry/drift_proxy", "momentum/time_series_mom"]
    assert mech_cols.shape == (300, 2)
    assert len(var_labels) == 4
    assert var_cols.shape == (300, 4)

    # the mechanism series is the equal-weight average of every variant x symbol under it
    members = np.column_stack([c["returns"] for c in cands if c["subtype"] == "time_series_mom"])
    assert np.allclose(mech_cols[:, 1], members.mean(axis=1))


def test_the_orthogonality_the_medallion_target_demands() -> None:
    """Sharpe 2.0 from Sharpe-0.2 components needs N_eff 100, i.e. rho <= 0.01. Hand-computed."""
    req = orthogonality_required()
    assert req["n_eff_required"] == 100.0
    assert req["max_rho_as_n_to_infinity"] == pytest.approx(0.01)
    # the desk's measured same-mechanism correlation is 35x too large for that target
    assert 0.348 / req["max_rho_as_n_to_infinity"] == pytest.approx(34.8)


def test_a_missing_tape_reports_NOT_READABLE_HERE_rather_than_a_number(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No panel, no answer. A partial cross-mechanism rho would be read as the finding anyway."""
    import scripts.measure_cross_mechanism_corr as mod

    monkeypatch.setattr(mod, "CACHE", tmp_path / "absent")
    monkeypatch.setattr(mod, "OUT", tmp_path / "out.json")
    out = tmp_path / "artifact.json"
    rc = mod.main(["--symbols", "BTC,ETH", "--out", str(out)])

    assert rc == 1
    doc = json.loads((tmp_path / "out.json").read_text("utf-8"))
    assert doc["status"] == "NOT-READABLE-HERE"
    assert doc["missing_inputs"]
    assert "--fetch" in doc["how_to_run"]
    assert not out.exists(), "a blocked run must not leave a measured-looking artifact behind"
