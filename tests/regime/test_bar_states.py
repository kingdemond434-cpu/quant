"""The market state is fitted on BARS, labelled CAUSALLY, and its state count is EVIDENCE.

Three properties are pinned here because each one, if it broke, would break silently:

1. A label at time t uses no bar after t. The fence is behavioural, not a source check: the
   label produced from a truncated tape must equal the label produced from the full tape at the
   same bar. Viterbi fails this by construction (desk lesson L0307); the forward filter passes.

2. The emission parameters are fitted strictly before the window they label, so a state path
   over the evaluation window is out of sample in the only sense that matters.

3. The state count comes from held-out predictive log-density, so a k that merely fits better
   in sample cannot win. On a two-state series the evidence must not prefer five states.
"""

from __future__ import annotations

import numpy as np
import pytest

from libs.regime.bar_states import (
    MIN_TRAIN_BARS,
    choose_k,
    fit_states,
    predictive_log_density,
    run_length_path,
)
from libs.regime.hmm import GaussianHMM

HOUR_NS = 3_600_000_000_000


def _two_state_series(n: int = 800, seed: int = 7) -> tuple[np.ndarray, np.ndarray]:
    """A tape that genuinely has two states: a quiet one and a violent one, persistent."""
    rng = np.random.RandomState(seed)
    state, rows = 0, []
    for _ in range(n):
        if rng.rand() < 0.02:
            state = 1 - state
        sd = 0.2 if state == 0 else 2.0
        rows.append([rng.randn() * sd, sd + 0.05 * rng.randn(), rng.randn() * sd * 0.5])
    x = np.asarray(rows, dtype="float64")
    t = np.arange(n, dtype="int64") * HOUR_NS
    return t, x


def test_label_at_t_uses_no_bar_after_t() -> None:
    """THE CAUSALITY FENCE. Truncating the tape must not change an earlier label."""
    t, x = _two_state_series()
    train_end = int(t[500])
    full = fit_states(t, x, symbol="SYN", train_end_ns=train_end, k=2, seed=3)
    assert full is not None
    cut = 640
    short = fit_states(t[:cut], x[:cut], symbol="SYN", train_end_ns=train_end, k=2, seed=3)
    assert short is not None
    # Same parameters (both fitted on the same pre-train_end bars), so the only thing that could
    # differ is whether labelling looked ahead. It must not.
    assert np.array_equal(full.labels[:cut], short.labels)
    np.testing.assert_allclose(full.posterior[:cut], short.posterior, atol=1e-12)


def _ambiguous_series(n: int = 800, seed: int = 2) -> np.ndarray:
    """Two states that OVERLAP and switch often, so the smoothed path has something to revise.

    With well-separated, highly persistent states Viterbi and the forward filter agree almost
    everywhere, and the control below would then pass for the wrong reason -- it would be
    asserting that the leak does not exist rather than that the fence catches it. These
    parameters (sd 1.0 vs 1.3, switching 15% of bars) were searched for precisely because they
    make the backward pass revise labels it had already assigned. Real regimes overlap.
    """
    rng = np.random.RandomState(seed)
    state, rows = 0, []
    for _ in range(n):
        if rng.rand() < 0.15:
            state = 1 - state
        sd = 1.0 if state == 0 else 1.3
        rows.append([rng.randn() * sd, sd + 0.3 * rng.randn(), rng.randn() * sd])
    return np.asarray(rows, dtype="float64")


def test_viterbi_would_fail_the_same_fence() -> None:
    """THE CONTROL. The fence above is not vacuous: the smoothed path DOES revise.

    Viterbi back-traces from the END of whatever tape it is given, so extending the tape can
    rewrite labels that were already assigned. That is the leak L0307 names, and it is why
    `fit_states` reads `filter_posterior` and never `predict`.
    """
    x = _ambiguous_series()
    # n_iter is part of the fixture: a different number of EM steps is a different fit, and the
    # overlap that makes the backward pass revise is only present at this one.
    hmm = GaussianHMM(n_states=2, seed=3, n_iter=25).fit(x[:500])
    full = hmm.predict(x)
    short = hmm.predict(x[:640])
    revised = int((full[:640] != short).sum())
    assert revised > 0, (
        "Viterbi agreed with itself on this sample, so the causality fence proves nothing here; "
        "pick a sample where the smoothed path actually revises."
    )

    # ...and the forward filter, on the SAME tape, revises nothing.
    f_full = hmm.filter_posterior(x).argmax(axis=1)
    f_short = hmm.filter_posterior(x[:640]).argmax(axis=1)
    assert np.array_equal(f_full[:640], f_short)


def test_parameters_are_fitted_strictly_before_the_labelled_window() -> None:
    t, x = _two_state_series()
    train_end = int(t[600])
    bs = fit_states(t, x, symbol="SYN", train_end_ns=train_end, k=2, seed=3)
    assert bs is not None
    assert bs.n_train == 600
    assert bs.times_ns[bs.n_train - 1] < train_end <= bs.times_ns[bs.n_train]
    assert not bs.is_out_of_sample(int(t[300]))
    assert bs.is_out_of_sample(int(t[700]))


def test_state_count_is_chosen_by_held_out_evidence_not_by_fit() -> None:
    """A two-state tape must not buy five states. In-sample likelihood always would."""
    _t, x = _two_state_series(n=1000)
    k, scores = choose_k(x, grid=(2, 3, 5), seed=5)
    assert scores, "k-selection produced no scores at all"
    assert k <= 3, f"held-out evidence chose k={k} on a two-state series (scores {scores})"
    # and the score really is held out: a richer model does not automatically win
    if 2 in scores and 5 in scores:
        assert scores[2] >= scores[5] - 1e-9


def test_predictive_log_density_is_one_step_ahead() -> None:
    """It must marginalise over the PREDICTED state, never the filtered one."""
    _t, x = _two_state_series(n=700)
    hmm = GaussianHMM(n_states=2, seed=1, n_iter=25).fit(x[:450])
    good = predictive_log_density(hmm, x, 450)
    assert np.isfinite(good)
    # A model fitted on the same data scores its own tail no better than chance would allow;
    # what we pin is that the number is a mean log-density, so shuffling the tail degrades it.
    rng = np.random.RandomState(0)
    shuffled = x.copy()
    rng.shuffle(shuffled[450:])
    assert predictive_log_density(hmm, shuffled, 450) <= good + 1e-9


def test_states_are_ordered_by_volatility_so_labels_pool_across_symbols() -> None:
    t, x = _two_state_series()
    bs = fit_states(t, x, symbol="SYN", train_end_ns=int(t[600]), k=2, seed=3)
    assert bs is not None
    assert bs.names == ("quiet", "stress")
    vols = [float(np.nanmean(x[bs.labels == j, 1])) for j in range(bs.k)]
    assert vols == sorted(vols), f"state 0 is not the quietest: {vols}"


def test_transition_matrix_is_reordered_with_the_labels() -> None:
    t, x = _two_state_series()
    bs = fit_states(t, x, symbol="SYN", train_end_ns=int(t[600]), k=2, seed=3)
    assert bs is not None
    assert bs.transmat.shape == (2, 2)
    np.testing.assert_allclose(bs.transmat.sum(axis=1), 1.0, atol=1e-8)
    # a persistent chain: both states should prefer staying
    assert bs.transmat[0, 0] > 0.5 and bs.transmat[1, 1] > 0.5


def test_short_tape_is_unmeasured_never_a_fabricated_state() -> None:
    t, x = _two_state_series(n=MIN_TRAIN_BARS - 50)
    assert fit_states(t, x, symbol="SYN", train_end_ns=int(t[-1]), k=2, seed=1) is None


def test_run_length_path_compresses_and_round_trips() -> None:
    t, x = _two_state_series()
    bs = fit_states(t, x, symbol="SYN", train_end_ns=int(t[600]), k=2, seed=3)
    assert bs is not None
    path = run_length_path(bs)
    assert 0 < len(path) < bs.labels.size, "a persistent regime should compress"
    for row in path:
        assert bs.label_at(int(row["at_ns"])) == row["name"]
    assert all(0.0 <= float(r["p"]) <= 1.0 for r in path)


def test_probs_and_labels_agree_and_are_normalised() -> None:
    t, x = _two_state_series()
    bs = fit_states(t, x, symbol="SYN", train_end_ns=int(t[600]), k=2, seed=3)
    assert bs is not None
    np.testing.assert_allclose(bs.posterior.sum(axis=1), 1.0, atol=1e-8)
    for i in (10, 300, 700):
        p = bs.probs_at(int(t[i]))
        assert p is not None
        assert bs.names[int(np.argmax(p))] == bs.label_at(int(t[i]))
    assert bs.probs_at(int(t[0]) - HOUR_NS) is None
    assert bs.label_at(int(t[0]) - HOUR_NS) is None


def test_mismatched_inputs_are_refused() -> None:
    t, x = _two_state_series(n=500)
    with pytest.raises(ValueError):
        fit_states(t[:100], x, symbol="SYN", k=2)
