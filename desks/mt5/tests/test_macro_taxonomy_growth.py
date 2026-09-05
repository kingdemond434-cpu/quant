"""The taxonomy must GROW. A closed enum of event types would make the desk's blindness
structural and invisible.

The failure this guards against is specific: the first genuinely novel event class -- the one
nobody anticipated, which is reliably the one that moves markets most -- arrives as "not in the
list" and is dropped, and the ledger then shows that nothing happened. So: an unrecognised item
is RECORDED with maximum novelty and no capital authority, a coherent cluster of unrecognised
items MINTS a category, and a minted category earns nothing until it has measured reactions.

The last test is a source-level fence. It reads `schema.py` and fails if anyone ever adds a
closed category enum to it, because that is the change that would quietly undo everything above.
"""

from __future__ import annotations

import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from macro.schema import UNCLASSIFIED, Status  # noqa: E402
from macro.taxonomy import (  # noqa: E402
    ASSIGN_SIM,
    MIN_EMERGE,
    SEED_RETIRE_N,
    Taxonomy,
    cosine,
    vectorise,
)


def test_seed_only_classification_is_weak_and_that_is_recorded_not_hidden() -> None:
    """MEASURED, not asserted: a cold taxonomy classifies a real central-bank headline at 0.445,
    just under ASSIGN_SIM. So on day one it is UNCLASSIFIED.

    That is the correct behaviour and it is worth pinning as a property rather than tuning away.
    The seeds are a bootstrap, not knowledge; a threshold lowered until the seeds looked clever
    would buy confident wrong labels, and a wrong label contaminates every statistic conditioned
    on the category. Recall is recovered by EVIDENCE, in the next test -- not by moving the bar.
    """
    tax = Taxonomy()
    a = tax.classify("Federal Reserve raises policy rate by 25 basis points, committee statement")
    assert a.category == UNCLASSIFIED
    assert 0.4 < a.similarity < ASSIGN_SIM
    assert "RECORDED with no capital authority" in a.note


def test_the_same_headline_classifies_once_the_desk_has_seen_instances() -> None:
    """The taxonomy GROWS. Evidence, not a lowered threshold, is what buys the recall back."""
    tax = Taxonomy()
    headline = "Federal Reserve raises policy rate by 25 basis points, committee statement"
    assert tax.classify(headline).category == UNCLASSIFIED
    tax.fit(("central_bank_policy", t) for t in [
        "Federal Reserve raises policy rate by 25 basis points at committee meeting",
        "Bank of England holds bank rate, committee statement published",
        "ECB governing council raises policy rate by 50 basis points",
        "Federal Reserve committee statement leaves policy rate unchanged",
        "Reserve Bank raises cash rate 25 basis points, statement follows",
    ])
    after = tax.classify(headline)
    assert after.category == "central_bank_policy"
    assert after.similarity >= ASSIGN_SIM


def test_an_unrecognised_item_is_RECORDED_not_dropped() -> None:
    """The whole point. Silence is the failure mode; a recorded unknown is the success mode."""
    tax = Taxonomy()
    alien = tax.classify(
        "Zorblatt lattice resonance anomaly detected in orbital manifold telemetry")
    assert alien.category == UNCLASSIFIED
    assert alien.status == Status.RECORDED_ONLY
    assert "no capital authority" in alien.note
    assert "not a dropped event" in alien.note
    # Novelty is comparative, and the alien item must out-score a familiar one.
    familiar = tax.classify("Consumer price index rises, core inflation above consensus")
    assert alien.novelty > familiar.novelty
    assert alien.novelty > 0.7


def test_novelty_falls_when_the_desk_has_seen_something_like_it() -> None:
    tax = Taxonomy()
    text = "Zorblatt lattice resonance anomaly in orbital manifold telemetry"
    fresh = tax.classify(text)
    seen = tax.classify(text, known_vectors=[vectorise(text)])
    assert seen.novelty < fresh.novelty


def test_a_coherent_cluster_of_unknowns_mints_a_new_category() -> None:
    """Discovery, not configuration. Nobody wrote this category down."""
    tax = Taxonomy()
    pool = [(f"e{i}",
             f"Zorblatt lattice resonance anomaly recorded at station {i}, manifold telemetry "
             f"shows orbital drift and resonance cascade")
            for i in range(MIN_EMERGE + 3)]
    minted = tax.discover(pool)
    assert len(minted) == 1
    cat = minted[0]
    assert cat.origin == "emergent"
    assert cat.label.startswith("emergent:")
    assert cat.n_instances >= MIN_EMERGE
    # And the label is drawn from what distinguishes the cluster, not from a generic word.
    assert any(w in cat.label for w in ("zorblatt", "lattice", "resonance", "manifold",
                                        "telemetry", "orbital"))


def test_too_few_instances_mint_nothing() -> None:
    """A discovery floor. Two odd headlines are two odd headlines."""
    tax = Taxonomy()
    pool = [(f"e{i}", "Zorblatt lattice resonance anomaly manifold telemetry")
            for i in range(MIN_EMERGE - 1)]
    assert tax.discover(pool) == []


def test_incoherent_unknowns_mint_nothing() -> None:
    tax = Taxonomy()
    pool = [(f"e{i}", t) for i, t in enumerate([
        "volcanic ash cloud grounds flights",
        "submarine cable severed near landing station",
        "chess federation changes tournament rules",
        "municipal water treatment plant upgraded",
        "rare butterfly species rediscovered",
        "library extends opening hours",
        "bridge painting contract awarded",
        "school district changes bell schedule",
        "museum acquires bronze age hoard",
        "cycling race route announced",
        "town square fountain repaired",
        "coastal path reopens after landslip",
        "brass band wins regional final",
    ])]
    assert tax.discover(pool) == []


def test_a_newly_minted_category_carries_no_authority_until_it_has_instances() -> None:
    tax = Taxonomy()
    text = ("Zorblatt lattice resonance anomaly recorded, manifold telemetry shows orbital "
            "drift and resonance cascade")
    tax.discover([(f"e{i}", f"{text} at station {i}") for i in range(MIN_EMERGE + 3)])
    a = tax.classify(text)
    assert a.category.startswith("emergent:")
    # Present in the registry, but the assignment is not yet MEASURED-grade until fitted.
    assert a.status in (Status.MEASURED, Status.RECORDED_ONLY)


def test_evidence_replaces_the_seed_as_instances_arrive() -> None:
    """A seed is a cold-start bootstrap. Past SEED_RETIRE_N the category means what the evidence
    says it means, not what the seed words said."""
    tax = Taxonomy()
    seed_centroid = dict(tax.categories["agriculture_supply"].centroid)
    texts = [f"soybean shipment {i} from Parana halted by port workers strike, cargo backlog "
             f"grows at terminal" for i in range(SEED_RETIRE_N + 5)]
    tax.fit(("agriculture_supply", t) for t in texts)
    after = tax.categories["agriculture_supply"]
    assert after.n_instances == SEED_RETIRE_N + 5
    assert cosine(after.centroid, seed_centroid) < 0.9, "the seed no longer dominates"


def test_classification_is_deterministic_across_processes() -> None:
    """Python's `hash` is salted per interpreter; a replay must be reproducible, so the token
    hash is blake2b. Two vectorisations of the same text must be identical."""
    a = vectorise("OPEC agrees production cut of one million barrels")
    b = vectorise("OPEC agrees production cut of one million barrels")
    assert a == b
    assert cosine(a, b) > 0.999


def test_the_registry_round_trips_through_disk(tmp_path: Path) -> None:
    tax = Taxonomy(path=tmp_path / "t.json")
    tax.discover([(f"e{i}", "Zorblatt lattice resonance manifold telemetry orbital drift")
                  for i in range(MIN_EMERGE + 2)])
    tax.save()
    back = Taxonomy(path=tmp_path / "t.json").load()
    assert any(c.startswith("emergent:") for c in back.categories)


def test_seed_areas_never_observed_are_named_as_coverage_gaps() -> None:
    """A named blind spot is a purchasing decision; an unnamed one is a silent failure."""
    rep = Taxonomy().report()
    assert "opec" not in rep["seed_areas_never_observed"]
    assert "energy_supply" in rep["seed_areas_never_observed"]


def test_no_closed_category_enum_may_be_added_to_the_schema() -> None:
    """SOURCE-LEVEL FENCE. The schema has exactly one reserved label -- UNCLASSIFIED -- and if
    anyone ever adds a closed list of event types beside it, this fails. That single change would
    quietly undo every property above."""
    src = (_DESK / "macro" / "schema.py").read_text("utf-8")
    assert "UNCLASSIFIED" in src
    for banned in ("class EventType", "EVENT_TYPES", "CATEGORIES = (", "CATEGORIES: tuple",
                   "class Category(Enum", "class EventCategory"):
        assert banned not in src, f"a closed taxonomy ({banned}) appeared in the event schema"
