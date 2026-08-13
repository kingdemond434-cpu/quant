"""The CRO's output contract, and the fences it must not be able to talk its way past.

test_the_size_lever_is_rejected_however_it_is_labelled is the load-bearing one. Everything else
here checks that a required field is required; that test checks that the ONE recommendation which
would actively destroy compounded capital -- size up -- cannot get through by being relabelled.
A rule that lives only in the prompt is advisory, and a persuasive model reworded past it.
"""
from __future__ import annotations

import json
from unittest import mock

from libs.research import cro_role
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


# ------------------------------------------------- coverage must not shrink as the desk grows

def test_a_growing_desk_never_reduces_artifact_coverage(tmp_path) -> None:
    """THE INVARIANT THE PRINCIPAL NAMED: coverage is 100% of everything, and adding new things
    must not reduce it. The first version capped ROWS, so a desk that grew past the cap would have
    produced a SHRINKING view while every number still looked healthy -- and an artifact the CRO
    cannot see is an artifact it cannot report as a blind spot."""
    import json as _json
    (tmp_path / "data").mkdir()
    seen = []
    for n in (50, 400, 1200):
        for i in range(n):
            (tmp_path / "data" / f"a{i}.json").write_text(
                _json.dumps({f"key_{j}": "x" * 40 for j in range(10)}), "utf-8")
        cov = assemble_dossier(tmp_path)["coverage"]
        seen.append((n, cov["inventoried"], cov["artifacts_found"], cov["truncated"]))
        assert cov["truncated"] == 0, f"{n} artifacts: {cov['truncated']} dropped"
        assert cov["inventoried"] == cov["artifacts_found"], f"{n} artifacts: view is short"
    assert [s[1] for s in seen] == sorted(s[1] for s in seen), f"coverage went backwards: {seen}"


def test_detail_is_shed_before_any_artifact_is(tmp_path) -> None:
    """Over budget, top-level keys go first and from the stalest artifacts backward. A path is
    never dropped; shape is a nice-to-have."""
    import json as _json
    (tmp_path / "data").mkdir()
    for i in range(1500):
        (tmp_path / "data" / f"b{i}.json").write_text(
            _json.dumps({f"k{j}": "y" * 60 for j in range(12)}), "utf-8")
    inv = assemble_dossier(tmp_path)["inventory"]
    assert len(inv) == 1500
    assert all(r.get("path") and r.get("kb") is not None for r in inv)
    assert not all(r.get("keys") for r in inv), "nothing was shed despite being over budget"


class TestBulkRollup:
    """R0468: the inventory ran to 102,252 rows / 10.5 MB against a 60,000-char budget -- 176x
    over -- because `_fit_budget` never shed a row and deferred to a downstream prompt cap that
    was never written. 78.9% of those rows were daily partitions of a handful of feeds.
    """

    def _partitioned(self, tmp_path, n: int):
        d = tmp_path / "data" / "lake" / "bronze"
        d.mkdir(parents=True)
        for i in range(n):
            (d / f"part-{i:05d}.zip").write_bytes(b"x" * 100)
        return d

    def test_a_partitioned_feed_becomes_one_row_carrying_its_count(self, tmp_path) -> None:
        self._partitioned(tmp_path, 60)
        inv = assemble_dossier(tmp_path)["inventory"]
        rollups = [r for r in inv if r.get("rollup")]
        assert len(rollups) == 1
        assert rollups[0]["path"] == "data/lake/bronze/**"
        assert rollups[0]["n_files"] == 60
        # BOTH bounds: a dead feed shows as a large oldest_age_days rather than hiding behind a
        # recent neighbour. A rollup carrying only the newest age would conceal the staleness
        # this inventory exists to surface.
        assert "oldest_age_days" in rollups[0] and "age_days" in rollups[0]

    def test_a_small_directory_is_still_enumerated_file_by_file(self, tmp_path) -> None:
        # The rollup folds PARTITIONED FEEDS, not ordinary nested artifacts; a handful of files
        # is still individually visible, which is what blind-spot discovery actually needs.
        self._partitioned(tmp_path, 5)
        inv = assemble_dossier(tmp_path)["inventory"]
        assert not [r for r in inv if r.get("rollup")]
        assert len([r for r in inv if r["path"].endswith(".zip")]) == 5

    def test_the_rollup_never_shrinks_the_coverage_denominator(self, tmp_path) -> None:
        # Compressing the PRESENTATION must not let the desk report better coverage by showing
        # fewer rows -- the denominator trick (L1.57/L1.60).
        self._partitioned(tmp_path, 60)
        cov = assemble_dossier(tmp_path)["coverage"]
        assert cov["artifacts_found"] == 60
        assert cov["rolled_up"] == 60
        assert cov["inventoried"] == 1

    def test_coverage_reconciles_exactly_with_all_three_buckets_live(self, tmp_path) -> None:
        # rolled_up + individual rows + omitted FILES == artifacts_found, with no slack. The
        # first cut of this rewrite was 18,738 files short because the truncation marker counted
        # ROWS while artifacts_found counted FILES, and an omitted rollup row takes its whole
        # feed with it. Budget forced down so all three buckets are non-zero -- reconciling only
        # the easy case is what let the mixed-unit bug through.
        self._partitioned(tmp_path, 60)
        for i in range(300):
            (tmp_path / "data" / f"solo{i}.json").write_text('{"a":1}', "utf-8")
        with mock.patch.object(cro_role, "_INVENTORY_CHAR_BUDGET", 3_000):
            d = assemble_dossier(tmp_path)
        inv, cov = d["inventory"], d["coverage"]
        individual = [r for r in inv if not r.get("rollup") and not r.get("truncated")]
        accounted = (sum(int(r["n_files"]) for r in inv if r.get("rollup"))
                     + len(individual) + int(cov["truncated"]))
        assert cov["truncated"] > 0 and individual, "forcing the cap did not exercise both paths"
        assert accounted == cov["artifacts_found"] == 360

    def test_the_payload_actually_fits_its_declared_budget(self, tmp_path) -> None:
        # The invariant that failed: a cap enforced somewhere else is a cap enforced nowhere.
        # The old code returned every row here on the strength of a prompt cap that did not
        # exist, so this asserts the fit is enforced WHERE IT IS DECLARED.
        self._partitioned(tmp_path, 400)
        for i in range(600):
            (tmp_path / "data" / f"solo{i}.json").write_text('{"a":1}', "utf-8")
        with mock.patch.object(cro_role, "_INVENTORY_CHAR_BUDGET", 5_000):
            inv = assemble_dossier(tmp_path)["inventory"]
        chars = len(json.dumps(inv, default=str))
        assert chars <= 5_000 * 1.10, f"{chars} chars over a 5,000 budget"

    def test_truncation_when_it_bites_is_counted_in_files_and_published(self, tmp_path) -> None:
        # Silent truncation reads as coverage. Force the cap down so the backstop fires.
        self._partitioned(tmp_path, 60)
        for i in range(400):
            (tmp_path / "data" / f"solo{i}.json").write_text('{"a":1}', "utf-8")
        with mock.patch.object(cro_role, "_INVENTORY_CHAR_BUDGET", 2_000):
            d = assemble_dossier(tmp_path)
        marker = [r for r in d["inventory"] if r.get("truncated")]
        assert len(marker) == 1, "an omitted tail must announce itself"
        assert marker[0]["truncated"] == d["coverage"]["truncated"] > 0
        assert marker[0]["truncated"] >= marker[0]["truncated_rows"]


# ------------------------------------------------------- the CRO audits itself, on evidence

def test_the_cro_sees_its_own_track_record() -> None:
    """Asking a model to 'find your blind spots' with nothing to look at produces agreeable
    introspection. Its own reject rate and its own last proposals are something it can be
    wrong about."""
    d = assemble_dossier()
    assert "scorecard" in d["self"] and "recent" in d["self"]
    p = build_prompt(d)
    assert "YOUR OWN TRACK RECORD" in p
    assert "EVIDENCE ABOUT YOU" in p


def test_self_critique_is_a_standing_responsibility_and_a_deliverable() -> None:
    """A CRO that audits the desk but never audits itself is the one blind spot the desk cannot
    see around, because it is the organ the desk relies on to find blind spots."""
    assert any("Self-critique" in name for name, _ in RESPONSIBILITIES)
    assert "cro_role_upgrade" in DELIVERABLES
    p = build_prompt({"present": {}, "missing": []})
    assert "cro_role_upgrade" in p and "audits itself" in p
