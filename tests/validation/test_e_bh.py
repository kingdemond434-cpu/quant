"""e-BH: FDR control on e-values under ARBITRARY dependence, and the arbitrary-dependence merge.

THE ABSENCE THIS CLOSES. `docs/research/deep_sweep/20260726_validation-stats.md:752` recorded
"ABSENT: e_bh -> no e-value multiplicity procedure for the forward cohort (W-8)" and called it one
of "the two absences that matter most". The desk has run an e-process on every forward clock since
(four live consumers of `libs.research.anytime_valid.e_value`) with no way to correct the COHORT.

THE TEST THAT MATTERS MOST IS THE DEPENDENCE ONE. e-BH's whole claim over Benjamini-Yekutieli is
that it needs no dependence correction and pays no log-factor for it, and the desk's forward slots
are heavily dependent by construction -- twelve crypto sleeves sharing one market factor, a
measured raw cross-section of 1.54 independent bets. A procedure that only held under
independence would be worse than useless here: it would look correct on every synthetic test and
under-control on the only cohort the desk actually has.
"""
from __future__ import annotations

import numpy as np

from libs.research.anytime_valid import e_value
from libs.validation.fdr import benjamini_yekutieli, e_benjamini_hochberg, merge_evalues


class TestTheProcedureItself:
    def test_a_crushing_evalue_is_rejected(self):
        r = e_benjamini_hochberg([1000.0, 1.0, 1.0, 1.0], alpha=0.1)
        assert r.rejected[0] is True
        assert r.n_rejected == 1
        assert r.method == "e_benjamini_hochberg"

    def test_uninformative_evalues_reject_nothing(self):
        """An e-value of 1 is exactly 'no evidence' -- the null bettor never grew its capital."""
        assert e_benjamini_hochberg([1.0] * 12, alpha=0.1).n_rejected == 0

    def test_the_empty_cohort_is_not_a_rejection(self):
        r = e_benjamini_hochberg([], alpha=0.1)
        assert r.n_rejected == 0 and r.rejected == []

    def test_ties_are_included_jointly_which_is_correct_not_a_leak(self):
        """WRITTEN AS A TRAP AND IT CAUGHT ME. The first version asserted n_rejected == 1 here,
        on the theory that ties at the boundary must be excluded to protect the guarantee. That
        is wrong: crit_k = m/(alpha*k) DECREASES in k, so anything tied with the k*-th already
        clears its own looser bar and belongs in the rejection set. All 20 sit at 200, which is
        20x the k=m critical value of 1/alpha, so rejecting all 20 is the right answer."""
        n = 20
        e = [float(n / (0.1 * 1))] * n          # every one sits exactly on the k=1 critical value
        r = e_benjamini_hochberg(e, alpha=0.1)
        assert r.n_rejected == n
        assert all(r.rejected)

    def test_the_step_up_takes_the_largest_k_not_the_first_failure(self):
        """e-BH is a STEP-UP procedure: a hypothesis below its own critical value is still
        rejected when a lower-ranked one meets the bar."""
        # K=4, alpha=0.5 -> critical values 8, 4, 2.67, 2. The 2nd entry misses its own bar (4)
        # but the 3rd meets its own (2.67), so k*=3 and all three are rejected.
        r = e_benjamini_hochberg([50.0, 3.0, 3.0, 0.1], alpha=0.5)
        assert r.n_rejected == 3
        assert r.rejected[:3] == [True, True, True]
        assert r.rejected[3] is False


class TestAbsenceNeverResolvesToARejection:
    def test_nan_is_floored_and_can_never_be_rejected(self):
        r = e_benjamini_hochberg([np.nan, np.nan, 1000.0], alpha=0.1)
        assert r.rejected == [False, False, True]

    def test_infinity_is_legitimate_evidence_and_is_kept(self):
        """inf means the null was crushed; unlike NaN it is a real reading, not a missing one."""
        r = e_benjamini_hochberg([np.inf, 1.0, 1.0], alpha=0.1)
        assert r.rejected[0] is True

    def test_a_negative_entry_cannot_outrank_a_real_one(self):
        r = e_benjamini_hochberg([-5.0, 1000.0, 1.0], alpha=0.1)
        assert r.rejected == [False, True, False]


class TestItControlsFDRUnderTheDependenceTheDeskActuallyHas:
    def _cohort(self, rng, n_hyp, n_obs, *, rho, n_true_null):
        """One shared market factor across every sleeve -- the desk's real correlation structure,
        not an independent-null fiction."""
        common = rng.standard_normal((n_obs, 1))
        idio = rng.standard_normal((n_obs, n_hyp))
        r = np.sqrt(rho) * common + np.sqrt(1.0 - rho) * idio
        r[:, n_true_null:] += 0.35              # the genuine edges
        return [e_value(r[:, j]) for j in range(n_hyp)]

    def test_fdr_is_controlled_when_every_hypothesis_is_null(self, ):
        """The strongest form: all nulls, heavy shared factor. ANY rejection is a false one, so
        the realised false-discovery PROPORTION is the rejection rate and must sit under alpha."""
        rng = np.random.default_rng(7)
        alpha, trials, false_discoveries = 0.2, 300, 0
        for _ in range(trials):
            e = self._cohort(rng, n_hyp=12, n_obs=250, rho=0.64, n_true_null=12)
            if e_benjamini_hochberg(e, alpha=alpha).n_rejected > 0:
                false_discoveries += 1
        assert false_discoveries / trials <= alpha, (
            f"FDR {false_discoveries / trials:.3f} exceeds alpha={alpha} under rho=0.64")

    def test_it_still_finds_a_planted_edge_and_the_false_share_stays_under_alpha(self):
        """A procedure that rejects nothing controls FDR trivially and is worthless, so this is
        the positive control -- without it the all-null test above passes on a dead function.

        THE FIRST VERSION ASSERTED ZERO FALSE REJECTIONS, WHICH IS FWER, NOT FDR, and it failed
        exactly as it should have. FDR bounds the expected PROPORTION of false discoveries among
        the rejections; some are allowed, and demanding none would be quietly re-imposing a
        stricter error criterion than the procedure claims."""
        rng = np.random.default_rng(11)
        found, false_props = 0, []
        for _ in range(30):
            e = self._cohort(rng, n_hyp=12, n_obs=400, rho=0.64, n_true_null=8)
            r = e_benjamini_hochberg(e, alpha=0.2)
            n_rej = r.n_rejected
            false_props.append(sum(r.rejected[:8]) / n_rej if n_rej else 0.0)
            found += n_rej
        assert found > 0, "never detected a planted edge -- the procedure is inert"
        assert float(np.mean(false_props)) <= 0.2, (
            f"false-discovery proportion {np.mean(false_props):.3f} exceeds alpha=0.2")

    def test_it_is_not_weaker_than_benjamini_yekutieli_on_the_same_evidence(self):
        """The power claim, made concrete. BY buys arbitrary dependence with a sum(1/i) penalty --
        3.10 at K=12. e-BH pays nothing for the same guarantee, so converting e-values to
        p-values (p <= 1/e by Markov) and running BY must not beat it."""
        rng = np.random.default_rng(3)
        e_wins = by_wins = 0
        for _ in range(40):
            e = self._cohort(rng, n_hyp=12, n_obs=400, rho=0.64, n_true_null=8)
            n_e = e_benjamini_hochberg(e, alpha=0.2).n_rejected
            p = np.minimum(1.0, 1.0 / np.maximum(np.asarray(e), 1e-12))
            n_by = benjamini_yekutieli(p, alpha=0.2).n_rejected
            e_wins += n_e > n_by
            by_wins += n_by > n_e
        assert e_wins >= by_wins, f"e-BH lost to BY ({e_wins} vs {by_wins})"


class TestMergingEvidenceAboutOneClaim:
    def test_the_mean_is_the_merge(self):
        assert merge_evalues([2.0, 4.0, 6.0]) == 4.0

    def test_no_evidence_is_zero_not_the_one_of_a_null_result(self):
        """Returning 1.0 would report 'measured, and the null stands' for a claim never tested."""
        assert merge_evalues([]) == 0.0
        assert merge_evalues([np.nan, np.nan]) == 0.0

    def test_a_merged_evalue_feeds_straight_into_the_cohort_procedure(self):
        merged = merge_evalues([1000.0, 2000.0])
        r = e_benjamini_hochberg([merged, 1.0, 1.0, 1.0], alpha=0.1)
        assert r.rejected[0] is True
