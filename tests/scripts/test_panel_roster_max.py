"""Panel roster at maximum breadth, and the funding event that arms the flagship sweep.

TWO CEILINGS REMOVED, both of which capped the panel below what the market offered:

  1. The fill loop could only ever seat a lab named in the `_LABS` literal or already on the
     roster. A new frontier lab appearing on OpenRouter was unreachable -- diversity was bounded
     by this file rather than by what exists. Now discovered from the live catalog, with an
     explicit deny-list for the reasons that are real (anthropic for independence; four labs
     retired on measured evidence).

  2. The flagship upgrade ran on a 30-day clock only, so credits landing on a Friday could be
     followed by up to a month of running the previous roster on the new money.

The deny-list tests matter most. `select_roster`'s keep-alive path preserves whatever is already
on the roster, which is exactly how a retired lab -- or an anthropic seat, which breaks the
independence policy outright -- could ride forward forever without anyone deciding to keep it.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _mod(rel: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


R = _mod("scripts/refresh_panel_roster.py", "rp")


def _catalog(*ids: str) -> list[dict]:
    return [{"id": m, "created": 1_700_000_000 + i} for i, m in enumerate(ids)]


# --------------------------------------------------------------------- breadth


def test_a_brand_new_lab_gets_seated() -> None:
    """The ceiling that was removed: a lab nobody typed into `_LABS` must still be reachable."""
    cat = _catalog("openai/gpt-9", "brandnewlab/frontier-1")
    got = R.select_roster(cat, "k", "https://x", current=["openai/gpt-9"])
    labs = {r["model"].split("/")[0] for r in got}
    assert "brandnewlab" in labs, "roster breadth must follow the catalog, not a literal"


def test_discover_labs_is_ordered_best_first() -> None:
    """When the seat cap binds it must cost the desk its stalest labs, not arbitrary ones."""
    cat = _catalog("old/model-a", "mid/model-b", "new/model-c")
    assert R.discover_labs(cat) == ["new", "mid", "old"]


def test_weak_tiers_never_qualify_a_lab() -> None:
    """A lab whose only offering is a mini/flash/free variant is not a frontier seat."""
    cat = _catalog("weaklab/tiny-mini", "weaklab/thing:free", "weaklab/x-flash")
    assert "weaklab" not in R.discover_labs(cat)


def test_seat_cap_is_respected() -> None:
    cat = _catalog(*[f"lab{i}/model-{i}" for i in range(60)])
    got = R.select_roster(cat, "k", "https://x", current=[])
    assert len(got) <= R.MAX_SEATS


def test_cap_never_evicts_an_existing_working_seat() -> None:
    """Growth must not displace a lineage the desk already validated."""
    current = [f"inc{i}/model-{i}" for i in range(5)]
    cat = _catalog(*current, *[f"new{i}/model-{i}" for i in range(60)])
    got = R.select_roster(cat, "k", "https://x", current=current)
    kept = {r["model"] for r in got}
    assert set(current) <= kept


# --------------------------------------------------------------------- deny-list


@pytest.mark.parametrize("lab", ["anthropic", "mistralai", "meta-llama", "cohere", "microsoft"])
def test_denied_labs_are_never_discovered(lab: str) -> None:
    assert lab not in R.discover_labs(_catalog(f"{lab}/some-strong-model"))


@pytest.mark.parametrize("lab", ["anthropic", "mistralai", "meta-llama", "cohere", "microsoft"])
def test_denied_labs_are_never_filled(lab: str) -> None:
    got = R.select_roster(_catalog(f"{lab}/strong", "openai/gpt-9"), "k", "https://x", current=[])
    assert all(not r["model"].startswith(f"{lab}/") for r in got)


@pytest.mark.parametrize("lab", ["anthropic", "mistralai", "meta-llama", "cohere", "microsoft"])
def test_a_denied_lab_already_on_the_roster_is_dropped(lab: str) -> None:
    """KEEP-ALIVE IS THE LEAK. Being already seated is not a decision to stay seated."""
    seat = f"{lab}/whatever"
    got = R.select_roster(_catalog(seat, "openai/gpt-9"), "k", "https://x",
                          current=[seat, "openai/gpt-9"])
    assert all(not r["model"].startswith(f"{lab}/") for r in got)
    assert any(r["model"] == "openai/gpt-9" for r in got), "only the denied seat may be dropped"


def test_every_denial_states_a_reason() -> None:
    """A deny-list without reasons decays into superstition nobody dares revisit."""
    for lab, reason in R._DENY_LABS.items():
        assert isinstance(reason, str) and len(reason) > 20, lab


# --------------------------------------------------------------------- funding trigger


def test_funding_edge_latches_an_upgrade_debt(tmp_path, monkeypatch) -> None:
    P = _mod("scripts/run_external_panel.py", "pnl")
    monkeypatch.setattr(P, "_FUNDING", tmp_path / "f.json")

    P._stamp_funding(False, 0.10)
    assert json.loads(P._FUNDING.read_text())["upgrade_owed"] is False, "unfunded owes nothing"

    P._stamp_funding(True, 50.0)
    d = json.loads(P._FUNDING.read_text())
    assert d["funded"] is True and d["upgrade_owed"] is True, "funding must arm the sweep"


def test_debt_survives_a_second_panel_run(tmp_path, monkeypatch) -> None:
    """LATCHED, NOT AN EDGE. The cadence may not fire for hours; a bare boolean would be erased
    by the next panel run and the funding event would be silently forgotten."""
    P = _mod("scripts/run_external_panel.py", "pnl2")
    monkeypatch.setattr(P, "_FUNDING", tmp_path / "f.json")
    P._stamp_funding(False, 0.10)
    P._stamp_funding(True, 50.0)
    P._stamp_funding(True, 49.0)          # a later run, still funded, no new edge
    assert json.loads(P._FUNDING.read_text())["upgrade_owed"] is True


def test_only_a_sweep_that_evaluated_clears_the_debt(tmp_path, monkeypatch) -> None:
    """An unanswered question must stay owed -- the same rule as every other duty here."""
    C = _mod("scripts/run_cadence.py", "cad")
    monkeypatch.setattr(C, "_FUNDING_STATE", tmp_path / "f.json")
    (tmp_path / "f.json").write_text(json.dumps({"funded": True, "upgrade_owed": True}))

    assert C._funding_restored() is True
    C._clear_funding_debt()
    assert C._funding_restored() is False
    assert "upgrade_ran" in json.loads((tmp_path / "f.json").read_text())


def test_missing_funding_state_is_not_a_trigger(tmp_path, monkeypatch) -> None:
    """No file means no observed funding event. Absence must not fire a paid sweep."""
    C = _mod("scripts/run_cadence.py", "cad2")
    monkeypatch.setattr(C, "_FUNDING_STATE", tmp_path / "absent.json")
    assert C._funding_restored() is False


# --------------------------------------------------------------------- gap #72


def test_singleton_findings_are_surfaced_not_filtered() -> None:
    """The 32.3pp oracle gap, in the desk's own code.

    `_consensus` rendered only themes with n>=2, so a finding raised by 1 of 13 seats never
    reached the summary -- and the header then told the reader a lone claim needed extra proof.
    On a heterogeneous roster the singleton is the seat that saw what the others missed.
    """
    P = _mod("scripts/run_external_panel.py", "pnl3")
    resp = [
        {"provider": "xai", "response": "sizing and kelly are wrong"},
        {"provider": "openai", "response": "kelly sizing must change"},
        {"provider": "deepseek", "response": "a stablecoin depeg is unhandled"},
    ]
    cons = P._consensus(resp)
    lone = P.singletons(resp, cons)
    assert ("depeg/stablecoin", "deepseek") in lone
    assert all(t != "sizing/kelly" for t, _ in lone), "a 2-seat theme is consensus, not a singleton"


def test_singleton_section_and_symmetric_wording_are_rendered() -> None:
    src = (ROOT / "scripts/run_external_panel.py").read_text("utf-8")
    assert "## Singleton claims" in src
    assert "AND SO DOES A CONSENSUS CLAIM" in src, (
        "the old wording made consensus privileged; agreement among models reading the same "
        "dossier is correlated, not independent, evidence")
    assert "random.shuffle(_ordered)" in src, (
        "gap #72(4): fixed provider order + top-down reading is a self-imposed position bias")


def test_seat_order_is_randomised_not_provider_order() -> None:
    """A shuffle that never changes anything is decoration."""
    import random
    seats = [{"provider": f"p{i}", "response": "x"} for i in range(12)]
    random.seed(7)
    a = list(seats)
    random.shuffle(a)
    assert [s["provider"] for s in a] != [s["provider"] for s in seats]


def test_cadence_fires_the_sweep_on_funding_not_only_on_the_clock() -> None:
    src = (ROOT / "scripts/run_cadence.py").read_text("utf-8")
    assert "_MODEL_UPGRADE_D or _funded_now" in src, (
        "funding must be an independent trigger, not a calendar entry")
    assert "debt retained for the next run" in src, (
        "a sweep that did not evaluate must leave the debt standing")
