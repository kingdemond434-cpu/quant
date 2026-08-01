"""The CRO's output contract, and the fences it must not be able to talk its way past.

test_the_size_lever_is_rejected_however_it_is_labelled is the load-bearing one. Everything else
here checks that a required field is required; that test checks that the ONE recommendation which
would actively destroy compounded capital -- size up -- cannot get through by being relabelled.
A rule that lives only in the prompt is advisory, and a persuasive model reworded past it.
"""
from __future__ import annotations

import json

from libs.research.cro_role import (
    DELIVERABLES,
    EVIDENCE_CLASSES,
    GROWTH_LEVERS,
    REQUIRED_FIELDS,
    RESPONSIBILITIES,
    assemble_dossier,
    build_prompt,
    parse,
    record,
    scorecard,
)


def _rec(**over) -> dict:
    base = {
        "title": "Screen setup classes by conditional hit rate",
        "deliverable": "alpha_opportunity",
        "lever": "edge",
        "kind": "activate",
        "evidence_class": "evidence",
        "why_it_matters": "raises edge per bet at unchanged size",
        "bottleneck": "admitted set correlation 0.247 vs pool 0.047",
        "mechanism": "trade only setup classes whose conditional hit rate clears breakeven",
        "expected_upside": "a few points of hit rate",
        "risks": "conditional rates are noisy on small samples",
        "dependencies": "per-setup trade labels",
        "validation_method": "out-of-sample conditional hit rate on held-out trades",
        "opportunity_cost": "defers the event sleeve",
        "estimated_roi": "high info gain, low engineering cost",
        "confidence": "medium",
        "success_metric": "conditional hit rate fails to separate classes out of sample",
    }
    base.update(over)
    return base


def _raw(*recs: dict) -> str:
    return json.dumps(list(recs))


# ------------------------------------------------------------------------------- the fences

def test_the_size_lever_is_rejected_when_declared() -> None:
    r = parse(_raw(_rec(lever="size")))
    assert not r.accepted and len(r.rejected) == 1
    assert "R0143" in r.rejected[0].rejected_reason


def test_the_size_lever_is_rejected_however_it_is_labelled() -> None:
    """THE TEST THAT MATTERS. Geometric growth peaks at Kelly f* and is negative past 2f*, so
    'size up' is the one recommendation that actively destroys compounded capital -- and it is
    also the most rhetorically appealing one available. Declaring `lever: edge` while the
    mechanism says 'increase position size' must not get through."""
    for mech in ("increase position size on the highest-conviction setups",
                 "raise leverage where the signal is strongest",
                 "scale up exposure to the admitted sleeve",
                 "allocate more notional to the winners"):
        r = parse(_raw(_rec(lever="edge", mechanism=mech)))
        assert not r.accepted, f"size mechanism slipped through: {mech}"
        assert "size lever wearing" in r.rejected[0].rejected_reason


def test_discussing_leverage_without_proposing_more_of_it_is_fine() -> None:
    """The fence must not fire on a recommendation that REDUCES the leverage needed -- that is a
    legitimate friction/edge improvement and rejecting it would punish the right answer."""
    r = parse(_raw(_rec(mechanism="vol targeting cuts the leverage required for the same risk")))
    assert len(r.accepted) == 1


def test_evidence_must_cite_a_number() -> None:
    """'Never invent edge.' A claim labelled `evidence` whose bottleneck carries no measurement is
    a hypothesis wearing the strongest available label, and mislabelling is the only dishonesty
    this contract can mechanically catch."""
    r = parse(_raw(_rec(evidence_class="evidence", bottleneck="the desk lacks breadth")))
    assert not r.accepted
    assert "cites no number" in r.rejected[0].rejected_reason


def test_the_same_claim_is_accepted_when_honestly_labelled() -> None:
    r = parse(_raw(_rec(evidence_class="hypothesis", bottleneck="the desk lacks breadth")))
    assert len(r.accepted) == 1


def test_unknown_lever_deliverable_class_and_confidence_are_all_rejected() -> None:
    for field, bad in (("lever", "vibes"), ("deliverable", "misc"),
                       ("evidence_class", "pretty_sure"), ("confidence", "very"),
                       ("kind", "rewrite")):
        r = parse(_raw(_rec(**{field: bad})))
        assert not r.accepted, f"{field}={bad} was accepted"


# ------------------------------------------------------------------------------- the contract

def test_every_mandated_field_is_required() -> None:
    """The eight scientific-discipline items plus the classification fields. A recommendation
    missing one is REJECTED, never repaired -- a repaired field is a field the desk invented."""
    for missing in REQUIRED_FIELDS:
        r = parse(_raw(_rec(**{missing: ""})))
        assert not r.accepted and r.parse_errors, f"{missing} was not required"
        assert missing in r.parse_errors[0]


def test_rejections_are_reported_never_silently_dropped() -> None:
    r = parse(_raw(_rec(), _rec(lever="size"), _rec(title="")))
    assert len(r.accepted) == 1
    assert len(r.rejected) == 1
    assert len(r.parse_errors) == 1


def test_a_fenced_response_still_parses() -> None:
    assert len(parse(f"Here you go:\n```json\n{_raw(_rec())}\n```\nHope that helps.").accepted) == 1


def test_a_response_with_no_array_reports_rather_than_crashes() -> None:
    r = parse("I cannot help with that.")
    assert not r.accepted and "no JSON array" in r.parse_errors[0]


# ------------------------------------------------------------------- the mandate is fully carried

def test_the_prompt_carries_every_responsibility_and_deliverable() -> None:
    """The whole mandate, not a summary of it. A CRO prompt that quietly drops 'meta research' or
    'data expansion' produces a CRO that never does them, and nothing would ever say so."""
    p = build_prompt({"present": {}, "missing": []}, n=12)
    for name, _ in RESPONSIBILITIES:
        assert name.split()[0].lower() in p.lower(), f"responsibility missing: {name}"
    for d in DELIVERABLES:
        assert d in p, f"deliverable missing: {d}"
    for e in EVIDENCE_CLASSES:
        assert e in p
    for lever in GROWTH_LEVERS:
        assert lever in p
    assert "Expected Long-Term ROI" in p
    assert "do NOT implement" in p or "not implement" in p


def test_the_prompt_states_the_size_fence_so_slots_are_not_wasted_on_it() -> None:
    p = build_prompt({"present": {}, "missing": []})
    assert "REJECTED AUTOMATICALLY" in p
    assert "Kelly" in p


def test_missing_dossier_artifacts_are_named_not_hidden() -> None:
    """A CRO reasoning off a dossier with invisible holes gives confident advice about a desk that
    does not exist, and that is indistinguishable from good advice until it is acted on."""
    p = build_prompt({"present": {}, "missing": ["gate_histogram (data/gate_histogram.json)"]})
    assert "gate_histogram" in p and "do not speculate" in p


def test_assemble_dossier_reports_what_is_missing(tmp_path) -> None:
    d = assemble_dossier(tmp_path)
    assert d["present"] == {}
    assert len(d["missing"]) > 10


# ------------------------------------------------------------------------------- the scorecard

def test_an_unworked_ledger_says_so(tmp_path) -> None:
    """A seat producing twelve recommendations a day that nobody dispositions is a queue, not an
    advisor -- the miner problem in a new costume."""
    p = tmp_path / "l.jsonl"
    record(parse(_raw(*[_rec(title=f"t{i}") for i in range(12)])), path=p)
    assert "UNWORKED" in scorecard(p)["verdict"]


def test_a_narrow_review_says_so(tmp_path) -> None:
    p = tmp_path / "l.jsonl"
    rows = [_rec(title=f"t{i}", deliverable="alpha_opportunity") for i in range(6)]
    record(parse(_raw(*rows)), path=p)
    sc = scorecard(p)
    assert sc["deliverables_covered"] == f"1/{len(DELIVERABLES)}"


def test_rejected_rows_are_ledgered_too(tmp_path) -> None:
    """A ledger holding only what passed cannot answer how often the seat proposes what the fences
    must catch -- and that number is how the desk learns whether the CRO earns its cadence."""
    p = tmp_path / "l.jsonl"
    n = record(parse(_raw(_rec(), _rec(lever="size"))), path=p)
    assert n == 2
    assert scorecard(p)["n_rejected"] == 1


def test_an_empty_ledger_is_unmeasured_not_zero(tmp_path) -> None:
    assert "UNMEASURED" in scorecard(tmp_path / "nothing.jsonl")["verdict"]


# ------------------------------------------------------------------ full view of the whole desk

def test_the_inventory_covers_every_artifact_not_read_in_full() -> None:
    """100% VIEW. A hand-listed dossier can only ever surface blind spots inside the slice someone
    already thought to show the CRO -- so the one category it could never report is the category
    nobody thought of, which is the failure this whole role exists to catch."""
    d = assemble_dossier()
    cov = d["coverage"]
    assert cov["truncated"] == 0, f"{cov['truncated']} artifacts fell off the inventory"
    assert cov["inventoried"] > 50
    assert cov["read_in_full"] >= 1


def test_markers_and_dotfiles_do_not_crowd_out_real_artifacts() -> None:
    """The first sweep spent all 400 inventory slots on zero-byte files in data/.fresh_markers/
    and truncated 35 real artifacts off the end. A cap that binds on noise is worse than no
    inventory at all, because it looks like coverage."""
    inv = assemble_dossier()["inventory"]
    assert inv, "inventory is empty"
    # No dotfile component anywhere in the path -- that is where the markers live.
    assert not any(p.startswith(".") for r in inv for p in str(r["path"]).split("/"))
    # And real artifacts are actually present, which is the property the slots were stolen from.
    # (`kb` is rounded to one decimal, so a legitimate 40-byte file reads as 0.0 -- the empty-file
    # filter is on the raw byte count, not on this display value.)
    assert any(str(r["path"]).endswith(".json") and (r.get("keys") or r.get("n_rows"))
               for r in inv)


def test_the_inventory_carries_shape_not_just_paths() -> None:
    """'A 40 KB JSON file exists' is a directory listing. 'A 40 KB JSON file keyed by venue and
    funding rate exists' is an artifact the CRO can reason about without it being in the prompt."""
    inv = assemble_dossier()["inventory"]
    assert any(r.get("keys") or r.get("n_rows") for r in inv)


def test_the_prompt_tells_the_cro_the_inventory_is_askable() -> None:
    p = build_prompt(assemble_dossier())
    assert "FULL DESK INVENTORY" in p
    assert "BLIND SPOT" in p
    assert "Coverage this cycle" in p


def test_a_bare_directory_inventories_to_nothing_without_crashing(tmp_path) -> None:
    d = assemble_dossier(tmp_path)
    assert d["inventory"] == [] and d["coverage"]["artifacts_found"] == 0
