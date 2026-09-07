"""The capability gap matrix must describe this tree, because it decides where research goes.

WHAT WAS WRONG. `ontology.unaddressed()` reported twelve capability groups with no module here,
and that list is not decoration: `frontier_supervisor.gap_matrix()` ranks it, `roi.priority`
scores it, and the frontier miner spends its hours on whatever it names. Four of the twelve
already had a real owner and the `owner` field was simply left empty:

    CACHING        desks/mt5/research/experiment_cache.py   (P39, the experiment cache)
    ENSEMBLES      desks/mt5/mt5desk/family_ensemble.py     (a weighted vote over member cells)
    GRAPH_MODELS   desks/mt5/research/cross_asset_graph.py  (the cross-asset information graph)
    CAPACITY       desks/mt5/research/capacity.py           (written and then not registered)

So a third of the "largest remaining institutional gaps" were solved problems, and the miner
would have spent real effort rebuilding them while the eight genuine gaps waited. An empty owner
is not a neutral default -- it is an assertion that nothing on this tree does the thing.

TWO FAILURE DIRECTIONS, and both are checked. An owner naming a file that does not exist claims
a capability the desk lacks; a capability with a real module and no owner hides one it has. The
second is the one that actually happened, and it is the harder of the two to notice because
everything looks fine -- there is simply a gap on a list.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parent.parent
REPO = BASE.parent.parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from frontier_intel import ontology  # noqa: E402


def _owned() -> list[tuple[str, str]]:
    return [(c.name, c.owner) for c in ontology.CAPABILITIES if c.owner]


@pytest.mark.parametrize(("name", "owner"), _owned())
def test_every_declared_owner_exists_on_disk(name: str, owner: str) -> None:
    """An owner naming a missing file claims a capability the desk does not have.

    That reads as PARTIAL on the gap matrix -- "a module exists, whether it is as good is what
    measurement decides" -- when the truth is MISSING, so the capability is never investigated.
    """
    target = REPO / owner
    assert target.exists(), (
        f"{name} claims {owner}, which does not exist. An owner is an assertion that something "
        "on this tree does the thing; a missing one hides a real gap behind a PARTIAL."
    )


@pytest.mark.parametrize(("name", "owner"), [
    ("CACHING", "desks/mt5/research/experiment_cache.py"),
    ("ENSEMBLES", "desks/mt5/mt5desk/family_ensemble.py"),
    ("GRAPH_MODELS", "desks/mt5/research/cross_asset_graph.py"),
    ("CAPACITY", "desks/mt5/research/capacity.py"),
])
def test_the_four_recovered_owners_stay_claimed(name: str, owner: str) -> None:
    """Pinned individually, because each was found by reading the tree rather than the registry.

    If one is ever un-set again the miner starts re-solving a solved problem, and nothing else
    would say so.
    """
    assert ontology.BY_NAME[name].owner == owner


def test_the_unaddressed_list_is_exactly_the_eight_genuine_gaps() -> None:
    """The real frontier, after the registry stopped under-reporting the desk.

    Kept as an exact set rather than a count: a capability quietly leaving this list because
    someone set an owner without a module is the same defect in the other direction, and a
    count would not catch the substitution.
    """
    assert set(ontology.unaddressed()) == {
        "ALT_DATA",                 # no ingestion of flows, physical or text outside price
        "REPRESENTATION_LEARNING",  # no learned latent state
        "MULTIMODAL",               # no joint text + price + cross-asset event model
        "SELF_SUPERVISED",          # nothing learns from unlabelled bars
        "DISTRIBUTED_TRAINING",     # experiments run in sequence
        "MIXTURE_OF_EXPERTS",       # no gate choosing a specialist per regime
        "MARKET_IMPACT",            # unmeasurable: matched_fills is 0
        "GEOPOLITICS",              # no unscheduled structural event model
    }


def test_an_owner_is_a_path_not_a_description() -> None:
    """Owners are read as repo-relative paths, so prose in the field is a silent lie.

    `REPO / "we do this in the allocator"` simply does not exist, and the capability would then
    report PARTIAL forever on a file nobody can open.

    `.json` IS ALLOWED AND IS THE WEAKER FORM. Two capabilities name their ARTIFACT rather than
    the producer that writes it, and that has cost this desk once already: `scheduler_for`
    searched for a schedule matching a `.json` path, found none, and the empty result read as
    "no surface" rather than "never looked for the right thing" -- which is how release_identity
    ran on no clock for months. Naming the producer is better. It is not asserted here because
    swapping an owner to a module this test cannot verify is the defect it exists to prevent.
    """
    for name, owner in _owned():
        assert " " not in owner, f"{name}'s owner is prose, not a path: {owner!r}"
        assert owner.endswith((".py", ".ps1", ".json", "/")), (
            f"{name}'s owner is not a module, script, artifact or directory: {owner!r}")


def test_owners_resolve_against_the_repository_root_not_the_desk() -> None:
    """The two-root confusion, which has now caused three separate defects.

    The research organs live under `desks/mt5/...` and the publication and maintenance scripts
    live at the REPOSITORY root. MONITORING claimed `desks/mt5/scripts/build_zentech_state.py`;
    the file is at `scripts/build_zentech_state.py`. The same mistake made `hourly_cycle._producer`
    resolve against both roots, and made the Windows installer print `[SKIP]` for the dashboard
    publisher while exiting successfully.

    A capability whose owner points at nothing reports PARTIAL -- "a module exists, whether it is
    as good is what measurement decides" -- when the honest answer is that the path is wrong.
    """
    assert ontology.BY_NAME["MONITORING"].owner == "scripts/build_zentech_state.py"
    assert (REPO / "scripts" / "build_zentech_state.py").exists()
