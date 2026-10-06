"""Scientific screens produce falsifiable hypotheses, never trading authority."""
import numpy as np
import pytest

from libs.tiers import cross_science as cs


def assert_hypotheses(rows):
    for row in rows:
        assert row["kind"] == "hypothesis"
        assert row["null"] and row["falsifier"] and row["claim"]
        assert np.isfinite(row["statistic"])
        assert "armed" not in row and "certified" not in row


def test_information_direction_against_shuffled_control():
    rng = np.random.default_rng(781)
    driver = rng.choice([-1.0, 1.0], 1600)
    target = np.roll(driver, 1)
    assert cs.transfer_entropy(driver, target) > 0.95
    assert cs.transfer_entropy(target, driver) < 0.02
    assert cs.transfer_entropy(driver[:20], target[:20]) == 0
    assert cs.transfer_entropy(np.zeros(200), np.zeros(200)) == 0
    rows = cs.info_lab({"USDJPY": driver, "CHFSGD": target}, n_shuffle=10, seed=19)
    assert rows and rows[0]["driver"] == "USDJPY" and rows[0]["target"] == "CHFSGD"
    assert rows == cs.info_lab({"USDJPY": driver, "CHFSGD": target}, n_shuffle=10, seed=19)
    assert_hypotheses(rows)


def test_spectral_known_period_and_null_flat_series():
    wave = np.sin(2 * np.pi * np.arange(1024) / 32)
    rows = cs.spectral_lab({"USDJPY": wave, "short": wave[:40], "flat": np.zeros(1024)})
    assert len(rows) == 1 and rows[0]["period"] == pytest.approx(32)
    assert_hypotheses(rows)
    assert cs.spectral_lab({"USDJPY": wave}, top=0) == []


def test_controller_reports_persistent_and_reverting_innovations():
    t = np.arange(800)
    rows = cs.kalman_lab({"trend": np.sin(t / 100), "revert": (-1.0) ** t,
                          "flat": np.zeros(800), "short": np.zeros(20)})
    by_symbol = {r["symbols"][0]: r for r in rows}
    assert by_symbol["trend"]["ac"] > 0
    assert by_symbol["revert"]["ac"] < 0
    assert "flat" not in by_symbol and "short" not in by_symbol
    assert_hypotheses(rows)


def test_queue_requires_measured_next_bar_release():
    n = 1200
    volume = np.ones(n)
    burst = np.arange(10, n - 2, 10)
    volume[burst] = 100
    returns = np.full(n - 1, 0.001)
    returns[burst] = 0.03
    price = np.exp(np.r_[0, np.cumsum(returns)])
    rows = cs.queue_lab({"USDJPY": price, "short": price[:20]},
                        {"USDJPY": volume, "short": volume[:20]})
    assert rows and rows[0]["statistic"] > 1.2
    assert_hypotheses(rows)
    assert cs.queue_lab({"flat": np.ones(n)}, {"flat": np.ones(n)}) == []
    # Move the measured bursts to quiet next bars while retaining both marginals.
    assert cs.queue_lab({"USDJPY": price}, {"USDJPY": np.roll(volume, 4)}) == []


def test_recurrence_and_ecology_against_known_cycles():
    t = np.arange(800)
    wave = np.sin(t * 2 * np.pi / 40)
    recurrent = cs.recurrence_lab({"USDJPY": wave, "short": wave[:20]}, seed=4)
    assert recurrent and recurrent[0]["lab"] == "dynamical"
    assert_hypotheses(recurrent)
    # Alternate whole seasons of trend and reversal, providing the specified predator/prey null.
    signs = np.ones(1601)
    for i in range(1, len(signs)):
        signs[i] = signs[i - 1] * (1 if (i // 20) % 2 == 0 else -1)
    ecology = cs.ecology_lab({"cycles": signs, "flat": np.zeros(800), "short": wave[:20]})
    assert ecology and ecology[0]["lab"] == "ecology"
    assert_hypotheses(ecology)


def test_network_has_no_hub_claim_without_enough_aligned_observations():
    assert cs.network_lab({"one": np.ones(100)}) == []
    assert cs.network_lab({str(i): np.ones(20) for i in range(4)}) == []
    rng = np.random.default_rng(49)
    common = rng.normal(size=1000)
    panel = {"hub": common}
    for i in range(4):
        panel[f"peer{i}"] = 0.8 * common + 0.7 * np.roll(common, 1) + rng.normal(0, 0.1, 1000)
    rows = cs.network_lab(panel)
    assert_hypotheses(rows)
    assert all(r["hub"] in panel for r in rows)


@pytest.mark.parametrize("phi", [-0.8, 0.8])
def test_metropolis_posterior_recovers_signed_persistence(phi):
    rng = np.random.default_rng(74)
    series = np.zeros(1200)
    for i in range(1, len(series)):
        series[i] = phi * series[i - 1] + rng.normal()
    posterior = cs.mcmc_ar1(series, draws=2000, seed=81)
    assert posterior["lo"] < posterior["mean"] < posterior["hi"]
    assert abs(posterior["mean"] - phi) < 0.1
    assert 0 < posterior["acceptance"] < 1
    rows = cs.bayes_lab({"USDJPY": series, "short": series[:20]})
    assert len(rows) == 1 and rows[0]["statistic"] * phi > 0
    assert_hypotheses(rows)
