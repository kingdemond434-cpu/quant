"""Register rows 87-88: the sealed holdout and the campaign-level false-discovery screen.

Both modules existed, were tested, and were called by nothing. What they add is specifically a
CAMPAIGN-level control -- every gate before them judges one candidate in isolation, which says
nothing about the error rate of the SET the desk promotes."""

from __future__ import annotations

import numpy as np
import pytest

from libs.autodiscovery.validation import _FDR_ALPHA, campaign_fdr
from libs.validation.errors import ValidationError
from libs.validation.lockbox import LockedHoldout


class TestCampaignFdr:
    def test_a_single_candidate_is_never_screened(self) -> None:
        """There is no multiplicity to correct with one test, and rejecting a lone candidate for
        being alone would be nonsense."""
        assert campaign_fdr([0.5]) == ([True], 1.0)
        assert campaign_fdr([]) == ([], 1.0)

    def test_strong_candidates_survive_and_weak_ones_do_not(self) -> None:
        mask, thresh = campaign_fdr([0.999, 0.998, 0.60, 0.20])
        assert mask[0] and mask[1]
        assert not mask[2] and not mask[3]
        assert 0.0 < thresh < 1.0

    def test_a_uniformly_strong_campaign_is_NOT_penalised(self) -> None:
        """Twenty candidates all at DSR 0.96 is strong COLLECTIVE evidence, and BH promotes all
        twenty. Worth pinning: the intuition that a multiplicity correction must shrink any large
        set is wrong, and a future 'fix' based on that intuition would be a real regression."""
        mask, _ = campaign_fdr([0.96] * 20)
        assert sum(mask) == 20

    def test_junk_candidates_DILUTE_the_good_ones(self) -> None:
        """The operationally important case, and the sharpest edge of this change.

        Three genuine candidates (DSR 0.96) among seventeen nulls promotes NONE -- BH reads a
        campaign that is mostly noise and declines to call anything a discovery. That is correct
        false-discovery control and it prices the search: padding a campaign with weak generators
        now costs you the good candidates too. Nothing is lost outright -- the orchestrator demotes
        to PAPER rather than rejecting -- but it will not reach the registry that cycle.
        """
        mask, _ = campaign_fdr([0.96] * 3 + [0.50] * 17)
        assert sum(mask) == 0

    def test_a_standout_survives_a_noisy_campaign(self) -> None:
        mask, _ = campaign_fdr([0.999] + [0.50] * 19)
        assert sum(mask) == 1 and mask[0]

    def test_a_uniformly_null_campaign_promotes_nothing(self) -> None:
        mask, _ = campaign_fdr([0.5] * 15)
        assert not any(mask)

    def test_dsr_values_outside_0_1_do_not_break_the_screen(self) -> None:
        mask, _ = campaign_fdr([1.5, -0.3, 0.99, 0.5])
        assert len(mask) == 4

    def test_alpha_is_the_documented_level(self) -> None:
        assert _FDR_ALPHA == 0.10

    def test_a_looser_alpha_never_rejects_more(self) -> None:
        dsrs = [0.99, 0.97, 0.93, 0.80, 0.55]
        tight = sum(campaign_fdr(dsrs, alpha=0.01)[0])
        loose = sum(campaign_fdr(dsrs, alpha=0.20)[0])
        assert loose >= tight


class TestLockboxDiscipline:
    def test_the_research_slice_excludes_the_holdout(self) -> None:
        data = np.arange(100, dtype="float64")
        box = LockedHoldout(data, holdout_fraction=0.2)
        assert len(box.research()) == 80
        assert len(box.open_lockbox()) == 20

    def test_a_second_open_raises(self) -> None:
        """A holdout you can reopen is not a holdout -- this is the property that makes the
        sealed slice independent evidence rather than just more backtest."""
        box = LockedHoldout(np.arange(100, dtype="float64"), holdout_fraction=0.2)
        box.open_lockbox()
        with pytest.raises(ValidationError):
            box.open_lockbox()

    def test_opening_is_logged(self) -> None:
        box = LockedHoldout(np.arange(100, dtype="float64"))
        assert box.access_log == [] and not box.is_opened
        box.open_lockbox()
        assert box.is_opened and len(box.access_log) == 1

    def test_research_stays_readable_after_the_open(self) -> None:
        box = LockedHoldout(np.arange(100, dtype="float64"), holdout_fraction=0.2)
        box.open_lockbox()
        assert len(box.research()) == 80


class TestOrchestratorWiring:
    """Wiring is the whole change -- both modules already worked in isolation."""

    def test_the_orchestrator_seals_a_holdout_and_screens_the_campaign(self) -> None:
        import inspect

        from libs.autodiscovery import orchestrator
        src = inspect.getsource(orchestrator.AutoDiscoveryLab._validate_and_archive)
        assert "LockedHoldout(" in src, "no sealed holdout is created"
        assert "box.research()" in src, "validation does not run on the research slice"
        assert "open_lockbox()" in src, "the holdout is never opened"
        assert "campaign_fdr(" in src, "no campaign-level FDR screen"

    def test_validation_never_sees_the_sealed_slice(self) -> None:
        """If validate() were handed the full series the holdout would be worthless -- it would
        have already been fitted on."""
        import inspect

        from libs.autodiscovery import orchestrator
        src = inspect.getsource(orchestrator.AutoDiscoveryLab._validate_and_archive)
        assert "validate(\n                research," in src or "validate(research," in src

    def test_the_lockbox_only_opens_for_a_registry_bound_candidate(self) -> None:
        """Opening it for an already-rejected candidate would burn its independence for no
        decision."""
        import inspect

        from libs.autodiscovery import orchestrator
        src = inspect.getsource(orchestrator.AutoDiscoveryLab._validate_and_archive)
        idx = src.index("open_lockbox()")
        assert "CandidateStatus.REGISTRY" in src[max(0, idx - 400):idx]
