"""The macro region's constitution: is it complete, and does it still refuse what it must refuse.

WHY A MANDATE NEEDS TESTS AT ALL. It is data, and data rots quietly: an actor loses a field in a
merge, a domain is added with no control leg, a miner is renamed and its entry point stops
pointing at anything, and every one of those failures is invisible at import time. The validator
is the gate; these tests are what keep the GATE honest, by planting each defect and asserting it
is caught rather than merely trusting that `validate()` returns an empty list today.

THE THREE THAT ARE NOT ARITHMETIC.

`test_every_actor_carries_all_eleven_fields` is the one the principal's shape depends on. An
actor without an `observable` is a story; an actor without `instruments` is a story about a
market the desk cannot trade. Both have reached this desk before.

`test_a_domain_without_controls_is_refused` plants the failure mode that produces flattering
macro research: a domain that measures a reaction and never names what it measures it against.

`test_capital_authority_cannot_be_flipped_by_accident` pins the field a later session would be
most tempted to change while adding a feature. A research department that can size is a research
department that will.
"""
from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(DESK / "research"), str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from macro_region import mandate as M  # noqa: E402


def test_the_mandate_validates_with_no_problems() -> None:
    assert M.validate() == []
    assert M.MANDATE.region == "macro"
    assert M.MANDATE.tag == "macro:"


def test_every_actor_carries_all_eleven_fields() -> None:
    assert len(M.ACTOR_FIELDS) == 11
    assert M.ACTORS, "the region declares no actors"
    for actor in M.ACTORS:
        for field_name in M.ACTOR_FIELDS:
            value = getattr(actor, field_name)
            assert value not in (None, "", ()), f"{actor.actor}: empty {field_name}"
        assert 0.0 < float(actor.confidence) <= 1.0
        assert isinstance(actor.instruments, tuple)
        # Selector tokens, never a hand-kept symbol list: the registry resolves them.
        for token in actor.instruments:
            assert token.split(":")[0] in {"class", "fx", "prefix", "symbol"}, token


def test_an_actor_missing_a_field_is_refused() -> None:
    broken = replace(M.ACTORS[0], observable="")
    problems = M.validate(replace(M.MANDATE, actors=(broken, *M.ACTORS[1:])))
    assert any("observable" in p for p in problems), problems


def test_every_domain_names_controls_measures_and_when_it_is_unmeasured() -> None:
    assert M.DOMAINS
    for domain in M.DOMAINS:
        assert domain.controls, f"{domain.name} declares no controls"
        assert domain.measures, f"{domain.name} declares no measures"
        assert domain.unmeasured_when, f"{domain.name} never says when it is UNMEASURED"
        assert domain.question.strip().endswith(tuple("abcdefghijklmnopqrstuvwxyz)"))
        assert domain.instruments


def test_a_domain_without_controls_is_refused() -> None:
    broken = replace(M.DOMAINS[0], controls=())
    problems = M.validate(replace(M.MANDATE, domains=(broken, *M.DOMAINS[1:])))
    assert any("declares no controls" in p for p in problems), problems


def test_every_miner_names_an_existing_domain_and_an_entry_in_this_package() -> None:
    names = {d.name for d in M.DOMAINS}
    for spec in M.MINER_SPECS:
        assert spec.domain in names, f"{spec.name} names unknown domain {spec.domain}"
        assert spec.entry.startswith("desks.mt5.research.macro_region.")
        module, _, func = spec.entry.partition(":")
        assert module.rsplit(".", 1)[-1] in {"miners", "intelligence"}
        assert func == f"mine_{spec.snake}"
        assert spec.budget_s > 0
        assert spec.inputs and spec.outputs and spec.why


def test_every_declared_entry_point_actually_imports() -> None:
    """A miner spec that names a function nobody wrote is a clock with nothing on the end."""
    import importlib

    for spec in M.MINER_SPECS:
        module_path, _, func = spec.entry.partition(":")
        module = importlib.import_module(module_path)
        assert callable(getattr(module, func, None)), spec.entry


def test_every_domain_has_at_least_one_miner() -> None:
    covered = {spec.domain for spec in M.MINER_SPECS}
    assert {d.name for d in M.DOMAINS} <= covered


def test_a_miner_naming_an_unknown_domain_is_refused() -> None:
    broken = replace(M.MINER_SPECS[0], domain="a_domain_that_does_not_exist")
    problems = M.validate(replace(M.MANDATE, miners=(broken, *M.MINER_SPECS[1:])))
    assert any("unknown domain" in p for p in problems), problems


def test_the_shared_vocabularies_are_the_declared_lengths() -> None:
    assert len(M.MANDATE.loop_steps) == 20
    assert len(M.MANDATE.requirements) == 25
    assert len(M.MANDATE.operators) == 14
    assert len(M.MANDATE.dispositions) == 7
    assert len(set(M.MANDATE.operators)) == 14, "an operator is declared twice"


def test_capital_authority_cannot_be_flipped_by_accident() -> None:
    assert M.MANDATE.capital_authority is False
    problems = M.validate(replace(M.MANDATE, capital_authority=True))
    assert any("capital_authority" in p for p in problems), problems


def test_the_governing_law_carries_the_standing_refusals() -> None:
    law = M.MANDATE.governing_law
    for clause in ("47.2", "47.3", "47.4", "47.5", "47.7", "47.8", "47.9", "47.10"):
        assert clause in law
    assert "crypto" in law.lower()
    assert "single-name equity" in law.lower()
    assert "no capital authority" in law.lower()


def test_the_boundaries_repeat_the_universe_mandate() -> None:
    joined = " ".join(M.MANDATE.boundaries).lower()
    assert "crypto-exchange" in joined
    assert "single-name equit" in joined
    assert "secrets" in joined
    assert "point-in-time" in joined


def test_the_tag_is_the_generator_prefix_every_organ_stamps() -> None:
    assert M.TAG == "macro:"
    assert all(spec.entry.startswith("desks.mt5.research.macro_region.") for spec in M.MINER_SPECS)
    problems = M.validate(replace(M.MANDATE, tag="japan:"))
    assert any("tag" in p for p in problems), problems


def test_the_dataset_catalogue_is_attached_and_every_domain_dataset_exists() -> None:
    assert M.MANDATE.datasets, "the mandate carries no dataset catalogue"
    known = {row.dataset_id for row in M.MANDATE.datasets}
    for domain in M.DOMAINS:
        for dataset in domain.datasets:
            assert dataset in known, f"{domain.name} names unknown dataset {dataset!r}"


def test_the_era_split_is_the_five_the_law_names() -> None:
    assert [e[0] for e in M.MANDATE.eras] == [
        "pre_2015", "2015_2019", "covid_2020_2021", "hiking_2022_2023", "post_2024"]


def test_summary_reports_the_shape_and_no_problems() -> None:
    got = M.summary()
    assert got["region"] == "macro"
    assert got["capital_authority"] is False
    assert got["problems"] == []
    assert got["n_actors"] == len(M.ACTORS)
    assert got["n_domains"] == len(M.DOMAINS)
    assert got["n_miners"] == len(M.MINER_SPECS)
    assert got["n_datasets"] >= 20


@pytest.mark.parametrize("bank", ["Fed", "ECB", "BoE", "SNB", "RBA", "RBNZ", "BoC",
                                  "Riksbank", "Norges"])
def test_every_g10_bank_is_an_actor_in_its_own_right(bank: str) -> None:
    assert any(f"({bank})" in a.actor for a in M.ACTORS), bank
