"""THE TEST THAT FAILS IF A DEPARTMENT CAN STOP PRODUCING IN SILENCE.

Three external reviews of this repository closed on one question -- "does every claimed
department actually run 24/7, use real data, generate real hypotheses, produce measurable
artifacts, enter the same canonical validation pipeline, and have its resource allocation changed
according to real survivor yield?" -- and on 2026-09-25 the desk could not answer it. Not because
the measurements were absent, but because it had THREE censuses whose rosters shared ZERO
producers: `PRODUCER_CENSUS.json` (1,568 names), `PRODUCTIVITY_CENSUS.json` (2,124) and
`DEAD_ARCHITECTURE.json` (711, keyed by CODE PATH rather than producer name). Union 2,817,
intersection nil. Every total the desk published about itself was a total in one roster's private
vocabulary.

What is pinned here, and they are five different claims:

  1. THE JOIN WORKS. A path-keyed roster resolves onto a name-keyed one when the code path is
     unambiguous, and refuses to when it is not -- because crediting one shared runner's liveness
     to the forty seats it fills is the flattery that would make the census worthless.
  2. THE CENSUS SEES A SILENT STOP -- an organ that produced a real artifact last pass and
     produces none now -- and does NOT see shapes that are not defects: a mirror host, a first
     pass with no baseline, an organ that declares no artifact at all.
  3. TRIVIALITY IS MEASURED. A fresh EMPTY artifact is a failure, not a healthy organ. Every
     other fence on this desk measures age alone, which is how `fred.json` refreshed every
     thirty minutes, landed 893 bytes, and read green everywhere.
  4. THE YIELD ORDER KEEPS ITS GUARDS. The exploration floor is positive, so a weak generator
     STARVES and is never eliminated by a run of bad luck; and nothing in the census can refuse a
     cell judgement, because multiplicity is pinned at `fixed_trial_count: 109` and judging one
     more cell therefore costs nothing at the bar.
  5. IT IS WIRED. A checker nobody runs is the same silence with more files in it (LAWS III.16).
"""
from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

from libs.ops import organ_census as oc

ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location(
    "check_organ_census", ROOT / "scripts" / "check_organ_census.py")
assert _SPEC and _SPEC.loader
fence = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(fence)

DEBT = ROOT / "docs" / "research" / "organ_census_debt.json"


# ------------------------------------------------------------------------------- 5. the wiring
def test_fence_is_registered_in_the_law_gate() -> None:
    """An unwired fence is a file, not a gate."""
    from scripts import run_law_gate as gate

    state = {f for f, _args in gate._STATE_FENCES}
    law = {f for f, _args in gate._LAW_FENCES}
    assert "check_organ_census.py" in state | law, (
        "check_organ_census.py is in neither _LAW_FENCES nor _STATE_FENCES in run_law_gate.py. "
        "A census nobody runs is the same silence with more files in it (LAWS III.16)")
    assert "check_organ_census.py" in state, (
        "the organ census reads LIVE desk state -- seven report artifacts the box writes -- so it "
        "belongs in _STATE_FENCES. In the law half it would report BLIND on every PR, and a gate "
        "that cries wolf gets switched off (L1.43)")
    assert ("check_organ_census.py", ("--require-state",)) in set(gate._STATE_FENCES), (
        "the state half must pass --require-state, or an absent roster reads as a pass and the "
        "fence goes quiet exactly when the box stops writing its censuses")


def test_leg_is_on_a_clock_and_in_a_layer() -> None:
    """DONE MEANS RUNS ON A SCHEDULE AND LEAVES AN ARTIFACT (LAWS III.16)."""
    cycle = (ROOT / "desks" / "mt5" / "research" / "hourly_cycle.py").read_text(encoding="utf-8")
    assert '_costed("organ_census"' in cycle, (
        "the organ census has no hourly leg: it would publish nothing between commits")
    assert '"organ_census": ogc' in cycle, (
        "the organ_census leg is built and never returned, so the cycle would drop its result")
    from libs.research.layers import LEG_LAYER

    assert LEG_LAYER.get("organ_census") == "meta", (
        "every leg must belong to a strategy layer, and a census of the desk's own organs is "
        "meta: it generates no hypothesis")


def test_the_debt_file_is_real_and_shrinkable() -> None:
    doc = json.loads(DEBT.read_text(encoding="utf-8-sig"))
    assert isinstance(doc.get("silent_stops"), list)
    assert isinstance(doc.get("max_ambiguous_code_paths"), int)
    assert doc["max_ambiguous_code_paths"] >= 0


# ------------------------------------------------------------------------------- 1. the join
def _claim(roster: str, name: str, **kw: object) -> oc.Claim:
    return oc.Claim(roster, name, str(kw.pop("kind", "")),
                    tuple(kw.pop("code_paths", ())),          # type: ignore[arg-type]
                    tuple(kw.pop("artifacts", ())),           # type: ignore[arg-type]
                    kw.pop("clock", None),                    # type: ignore[arg-type]
                    kw.pop("clocked", None),                  # type: ignore[arg-type]
                    kw.pop("detail", {}))                     # type: ignore[arg-type]


def test_a_path_keyed_roster_joins_a_name_keyed_one_on_an_unambiguous_path() -> None:
    claims = [
        _claim("producer_census", "miner", code_paths=("desks/mt5/research/miner.py",),
               clock="hourly_cycle:miner", clocked=True),
        _claim("dead_architecture", "desks/mt5/research/miner.py",
               code_paths=("desks/mt5/research/miner.py",), detail={"verdict": "LIVE"}),
    ]
    organs, rec = oc.reconcile(claims)
    assert set(organs) == {"miner"}, (
        "the path-keyed claim did not merge: the census would report one organ as two, which is "
        "the defect it exists to fix")
    assert organs["miner"].rosters == {"producer_census", "dead_architecture"}
    assert rec["path_claims_merged"] == 1


def test_a_shared_runner_is_never_credited_to_one_seat() -> None:
    """A file that fills forty seats belongs to none of them for liveness purposes."""
    shared = "desks/mt5/side_channels/full_pipeline.py"
    claims = [
        _claim("producer_census", "aaii", code_paths=(shared,)),
        _claim("producer_census", "cot", code_paths=(shared,)),
        _claim("dead_architecture", shared, code_paths=(shared,), detail={"verdict": "LIVE"}),
    ]
    organs, rec = oc.reconcile(claims)
    assert rec["n_ambiguous_code_paths"] == 1
    assert rec["path_claims_merged"] == 0
    assert "dead_architecture" not in organs["aaii"].rosters, (
        "a shared runner's LIVE verdict was credited to one of the seats it fills. Forty seats "
        "would read healthy off one file's mtime, which is exactly the flattery that makes a "
        "census worthless")
    assert shared in organs and organs[shared].detail.get("ambiguous_owners")


def test_an_organ_no_producer_roster_names_still_gets_a_row() -> None:
    claims = [_claim("dead_architecture", "desks/mt5/edge_search.py",
                     code_paths=("desks/mt5/edge_search.py",), detail={"verdict": "NO_CLOCK"})]
    organs, rec = oc.reconcile(claims)
    assert "desks/mt5/edge_search.py" in organs
    assert rec["path_claims_standalone"] == 1


# --------------------------------------------------------------------------- 3. triviality
def test_a_fresh_but_empty_artifact_is_not_production(tmp_path: Path) -> None:
    """THE fred.json SHAPE: refreshed every thirty minutes, 893 bytes, green on every age fence."""
    empty = tmp_path / "fred.json"
    empty.write_text("{}", encoding="utf-8")
    trivial, why = oc.is_trivial(empty)
    assert trivial and why, f"an empty JSON object read as production: {why}"

    padded = tmp_path / "padded.json"
    padded.write_text(json.dumps({"series": {}, "observations": []}) + " " * 2000,
                      encoding="utf-8")
    trivial, why = oc.is_trivial(padded)
    assert not trivial, ("over the byte floor the census stops guessing and says so: triviality "
                        "is cheap evidence, and claiming more would be the flattery this file "
                        "exists to prevent")

    receipt = tmp_path / "receipt.json"
    receipt.write_text(json.dumps({"at": "2026-09-25T00:00:00Z", "host": "box",
                                   "elapsed_s": 0.2, "ok": True}), encoding="utf-8")
    trivial, why = oc.is_trivial(receipt)
    assert trivial, "an artifact whose only keys are its own paperwork is a receipt, not a payload"

    real = tmp_path / "real.json"
    real.write_text(json.dumps({"at": "x", "rows": [{"cell": i} for i in range(400)]}),
                    encoding="utf-8")
    trivial, _ = oc.is_trivial(real)
    assert not trivial


def test_the_artifact_link_fails_a_fresh_empty_file(tmp_path: Path) -> None:
    (tmp_path / "desks" / "mt5" / "reports").mkdir(parents=True)
    art = tmp_path / "desks" / "mt5" / "reports" / "THING.json"
    art.write_text("{}", encoding="utf-8")
    organ = oc.Organ("thing", artifacts={"desks/mt5/reports/THING.json"})
    chain = oc.chain_for(organ, root=tmp_path, now=art.stat().st_mtime + 1.0, mirror=False)
    assert chain["artifact"]["verdict"] == oc.BROKEN
    assert "TRIVIAL" in chain["artifact"]["why"]


def test_a_stalled_input_is_a_broken_link_even_when_the_organ_runs(tmp_path: Path) -> None:
    """The question nothing on this desk asked: is it reading a file that stopped updating?"""
    (tmp_path / "data").mkdir()
    src = tmp_path / "data" / "feed.json"
    src.write_text(json.dumps({"rows": list(range(500))}), encoding="utf-8")
    organ = oc.Organ("reader", inputs={"data/feed.json"})
    fresh = oc.chain_for(organ, root=tmp_path, now=src.stat().st_mtime + 60.0, mirror=False)
    assert fresh["input"]["verdict"] == oc.REAL
    stale = oc.chain_for(organ, root=tmp_path, now=src.stat().st_mtime + 40 * 3600, mirror=False)
    assert stale["input"]["verdict"] == oc.BROKEN
    assert "stopped updating" in stale["input"]["why"]


def test_a_lock_file_is_never_convicted_of_being_empty(tmp_path: Path) -> None:
    """A LIVENESS TOKEN IS NOT A PRODUCT. The first payload rule put all thirteen department
    residents on the list of organs that "run, write and donate nothing", because the registry
    declares their only output as `data/locks/dept_<x>.lock` -- a file that is SUPPOSED to be a
    few bytes. The organs were working and the census was wrong; a census that convicts thirteen
    departments on a category error is worth exactly as much as one that flatters them."""
    (tmp_path / "desks" / "mt5" / "data" / "locks").mkdir(parents=True)
    lock = tmp_path / "desks" / "mt5" / "data" / "locks" / "dept_africa.lock"
    lock.write_text("4711", encoding="utf-8")
    organ = oc.Organ("resident:dept_africa",
                     artifacts={"desks/mt5/data/locks/dept_africa.lock"})
    chain = oc.chain_for(organ, root=tmp_path, now=lock.stat().st_mtime + 60.0, mirror=False)
    assert chain["artifact"]["verdict"] == oc.UNMEASURED, (
        "a four-byte lock file was judged as an empty product. It is a heartbeat: it proves the "
        "organ RUNS and says nothing about whether it PRODUCED")
    assert chain["artifact"]["declares_no_product"] is True
    stale = oc.chain_for(organ, root=tmp_path, now=lock.stat().st_mtime + 40 * 3600,
                         mirror=False)
    assert stale["artifact"]["verdict"] == oc.BROKEN, (
        "a heartbeat is still judged on AGE -- a resident whose lock has not moved in forty "
        "hours is not running")


def test_an_undeclared_input_reads_unmeasured_never_healthy(tmp_path: Path) -> None:
    """UNMEASURED IS A REAL ANSWER (L1.28a). 2,580 of 2,657 organs declare no input at all, and
    reporting that as a pass would be the census flattering the desk about its worst blind spot."""
    chain = oc.chain_for(oc.Organ("quiet"), root=tmp_path, now=0.0, mirror=False)
    assert chain["input"]["verdict"] == oc.UNMEASURED
    assert "gap in the contract" in chain["input"]["why"]


# ------------------------------------------------------------------------- 2. the silent stop
def _doc(artifact_verdict: str) -> dict[str, object]:
    return {"rows": [{"organ": "dept_x", "chain": {"artifact": artifact_verdict},
                      "why": {"artifact": "measured"}}],
            "yield_ledger": {"exploration_floor": oc.EXPLORATION_FLOOR,
                             "rations_the_judge": False}}


def test_an_organ_that_was_producing_and_stops_is_a_breach() -> None:
    stops = oc.silent_stops(_doc(oc.BROKEN), _doc(oc.REAL))
    assert [s["organ"] for s in stops] == ["dept_x"]
    problems = oc.breach(_doc(oc.BROKEN), previous=_doc(oc.REAL), debt={})
    assert problems and "produce nothing now" in problems[0]


def test_a_first_pass_and_a_mirror_host_convict_nobody() -> None:
    assert oc.silent_stops(_doc(oc.BROKEN), None) == [], (
        "with no previous census there is nothing to compare against, and inventing a baseline "
        "is how a fence starts convicting organs that were never measured")
    mirror = dict(_doc(oc.BROKEN))
    mirror["mirror_host"] = True
    assert oc.breach(mirror, previous=_doc(oc.REAL), debt={}) == []


def test_an_organ_that_never_produced_is_not_a_silent_stop() -> None:
    assert oc.silent_stops(_doc(oc.BROKEN), _doc(oc.UNMEASURED)) == []
    assert oc.silent_stops(_doc(oc.UNMEASURED), _doc(oc.REAL)) == []


def test_an_unresolved_stop_is_carried_forward_and_does_not_blink() -> None:
    """A stop reported only at the instant of the transition fails the gate for ONE pass, and the
    next census -- comparing broken against broken -- goes green over an organ that is still
    dark. That is the same silence wearing the comparison's clothes."""
    first = _doc(oc.BROKEN)
    first["silent_stops"] = oc.silent_stops(first, _doc(oc.REAL))
    assert [s["organ"] for s in first["silent_stops"]] == ["dept_x"]

    second = _doc(oc.BROKEN)
    still = oc.silent_stops(second, first)
    assert [s["organ"] for s in still] == ["dept_x"], (
        "the stop vanished on the next pass while the organ was still producing nothing")
    assert "unresolved" in still[0]["since"]
    assert oc.breach(second, previous=first, debt={})

    recovered = _doc(oc.REAL)
    assert oc.silent_stops(recovered, first) == [], (
        "an organ that resumed producing must clear: a fence that cannot be satisfied by the "
        "repair it asks for is a fence that gets switched off")


def test_declared_debt_excuses_a_named_organ_and_nothing_else() -> None:
    assert oc.breach(_doc(oc.BROKEN), previous=_doc(oc.REAL),
                     debt={"silent_stops": ["dept_x"]}) == []
    assert oc.breach(_doc(oc.BROKEN), previous=_doc(oc.REAL),
                     debt={"silent_stops": ["someone_else"]})


# --------------------------------------------------------------- 4. the yield order's guards
def _organ(name: str, hours: float, certs: int, cells: int) -> oc.Organ:
    o = oc.Organ(name, kind="generator")
    o.detail.update({"compute_hours": hours, "certificates_attributed": certs,
                     "unique_cells": cells, "cells_judged": certs})
    return o


def test_weak_generators_are_starved_and_never_eliminated() -> None:
    """A yield optimiser with no exploration budget stops discovering, which is the opposite of
    the goal, and a run of bad luck must never permanently kill a search method."""
    organs = {"strong": _organ("strong", 1.0, 10, 100),
              "weak": _organ("weak", 5.0, 0, 50),
              "untried": _organ("untried", 0.0, 0, 7)}
    led = oc.yield_ledger(organs)
    by = {r["producer"]: r for r in led["rows"]}
    assert by["strong"]["survivors_per_compute_hour"] == 10.0
    assert by["weak"]["floor_share"] > 0.0, (
        "a generator with a measured yield of zero was given a share of zero. That eliminates a "
        "search method on a run of bad luck; the floor exists so it starves instead")
    assert by["untried"]["floor_share"] > 0.0, (
        "a generator with NO track record was given nothing. No track record is evidence the "
        "desk has not looked, never evidence the generator is bad")
    assert led["exploration_floor"] > 0.0
    assert by["strong"]["floor_share"] < by["strong"]["share"], (
        "the floor must actually be taken out of the yield-proportional split, or it is a label")


def test_a_census_with_no_exploration_floor_is_a_breach() -> None:
    doc = {"rows": [], "yield_ledger": {"exploration_floor": 0.0}}
    assert any("exploration floor" in p for p in oc.breach(doc, previous=None, debt={}))


def test_the_census_can_never_ration_what_reaches_the_judge() -> None:
    """BARS ARE FIXED: `gate_spec.yaml` pins `fixed_trial_count: 109`, so judging one more cell
    costs nothing at the bar and refusing one would be a pure loss. This orders RESEARCH COMPUTE.

    Pinned structurally, not by intent: the module must contain no verb that could withhold a
    cell from the gauntlet. A future edit that adds one fails here before it can ship.
    """
    doc = {"rows": [], "yield_ledger": {"exploration_floor": 0.25, "rations_the_judge": True}}
    assert any("ration" in p for p in oc.breach(doc, previous=None, debt={}))

    source = (ROOT / "libs" / "ops" / "organ_census.py").read_text(encoding="utf-8")
    forbidden = ("run_gauntlet", "enqueue_candidate", "docket.write", "skip_cell",
                 "drop_cell", "refuse_judgement", "defer_cell")
    hits = [token for token in forbidden if token in source]
    assert not hits, (
        f"the organ census names {hits}, which means it could touch what reaches the judge. It "
        "measures and it orders research compute; multiplicity is pinned and rationing the "
        "gauntlet is a pure loss (NEVER REDUCE AGGRESSIVENESS)")
    for verb in ("cap", "throttle", "retire", "shrink", "starve", "kill"):
        assert not re.search(rf"^def {verb}\b", source, re.M), (
            f"the organ census defines `{verb}`: it reports and never reduces the desk's "
            "aggressiveness by fiat")


# -------------------------------------------------------------------------------- end to end
def test_the_fence_is_portable_and_never_cries_wolf_on_a_clean_tree(tmp_path: Path) -> None:
    """With no desk state the links are UNMEASURED and the check passes, with the reason
    published. A gate that fails on every PR is a gate that gets switched off (L1.43)."""
    doc = oc.census(root=tmp_path, now=0.0, mirror=False)
    assert doc["totals"]["organs_claimed"] == 0
    assert len(doc["feeders_missing"]) >= 6
    assert oc.breach(doc, previous=None, debt={}) == []


def test_the_seven_links_are_all_present_and_ordered() -> None:
    assert oc.LINKS == ("code", "clock", "input", "artifact", "pipeline", "yield", "allocation"), (
        "the chain is the review's own question in order; dropping or reordering a link changes "
        "what the census claims to have shown")
    chain = oc.chain_for(oc.Organ("x"), root=ROOT, now=0.0, mirror=True)
    assert set(chain) == set(oc.LINKS)
    assert all(chain[link]["why"] for link in oc.LINKS), (
        "every link must carry its own reason: a verdict a reader cannot check is a number this "
        "desk has been burned by")


@pytest.mark.parametrize("verdict", [oc.REAL, oc.BROKEN, oc.UNMEASURED])
def test_no_link_verdict_is_ever_invented(verdict: str) -> None:
    assert verdict in (oc.REAL, oc.BROKEN, oc.UNMEASURED)
