"""THE OUTPUT CONTRACT IS THE PRODUCT -- 150 statements, untested until now.

The principal was explicit: *"not as another dormant doctrine document."* So this is not prose about
strategy -- it is a dossier, a prompt, and an OUTPUT CONTRACT validated in code. An LLM asked for
strategy returns fluent, plausible, unfalsifiable advice ("improve research throughput", "strengthen
the validation stack"), and fluent advice is WORSE than none because it feels like progress and
cannot be checked.

So the parser is the whole module, and every test here is about a way fluent advice gets through:

  THE FOUR REQUIRED FIELDS turn advice into something that can later be shown to be WRONG. A
  minimum length is what stops them being filled with "improves things" (15 characters, says
  nothing) -- so the boilerplate floor is asserted, not just field presence.

  THE PRIORITY RULE IS ENFORCED ON A DECLARED FIELD, not on keyword-sniffing the prose. A rule that
  lives only in the prompt is advisory, and the model will ignore it, because proposing new
  construction is more rhetorically satisfying than proposing activation. Enforcing on `kind` is
  what makes it un-dodgeable by rewording.

  IT ONLY BITES WHEN THERE IS GENUINELY UNUSED CAPABILITY. On a desk with zero dormant
  capabilities, `build` must pass freely -- a rule that always fires is one that gets switched off.

  REJECTIONS ARE REPORTED, NEVER DROPPED. A director whose bad output is silently discarded looks
  identical to one that produced nothing, and the desk could not tell a credit problem from a
  quality problem.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from libs.research import strategic_director as SD

_LONG = "a genuinely specific statement that clears the boilerplate floor comfortably"


def _rec(**over) -> dict:
    r = {"title": "Wire the dormant allocator", "kind": SD.KIND_ACTIVATE,
         "bottleneck": _LONG, "expected_impact": _LONG,
         "opportunity_cost": _LONG, "success_metric": _LONG}
    r.update(over)
    return r


def _dossier(dormant: int = 0) -> SD.Dossier:
    return SD.Dossier(present={"x": {}}, missing=[], dormant_count=dormant)


# ============================================================ the four required fields

def test_a_complete_recommendation_is_ACCEPTED() -> None:
    """The positive control. A parser that rejected everything would satisfy every rejection test
    below and produce nothing -- indistinguishable from the 402 that currently blocks the call."""
    res = SD.parse_recommendations(json.dumps([_rec()]), _dossier())
    assert len(res.accepted) == 1 and res.rejected == []
    assert res.accepted[0].kind == SD.KIND_ACTIVATE


@pytest.mark.parametrize("field", SD.REQUIRED_FIELDS)
def test_a_MISSING_required_field_rejects_and_NAMES_it(field: str) -> None:
    """These four are exactly what turn advice into something judgeable. A rejection that did not
    name the missing one would send the model to guess."""
    rec = _rec()
    del rec[field]
    res = SD.parse_recommendations(json.dumps([rec]), _dossier())
    assert res.accepted == []
    assert field in res.rejected[0].reason


@pytest.mark.parametrize("filler", ["improves things", "TBD", "", "   ", "n/a"])
def test_BOILERPLATE_in_a_required_field_rejects(filler: str) -> None:
    """'improves things' is 15 characters and says nothing. Presence alone is not a contract --
    it is a field a model fills to get past a validator."""
    res = SD.parse_recommendations(json.dumps([_rec(bottleneck=filler)]), _dossier())
    assert res.accepted == [] and "boilerplate" in res.rejected[0].reason


def test_a_NON_STRING_required_field_rejects() -> None:
    """A number or a nested object satisfies `is not None` and says nothing a reader can judge."""
    for bad in (42, {"a": 1}, ["x"], None, True):
        res = SD.parse_recommendations(json.dumps([_rec(success_metric=bad)]), _dossier())
        assert res.accepted == [], bad


def test_the_boilerplate_floor_is_exactly_MIN_FIELD_CHARS() -> None:
    just_under = "x" * (SD.MIN_FIELD_CHARS - 1)
    just_over = "x" * SD.MIN_FIELD_CHARS
    assert SD.parse_recommendations(json.dumps([_rec(bottleneck=just_under)]),
                                    _dossier()).accepted == []
    assert len(SD.parse_recommendations(json.dumps([_rec(bottleneck=just_over)]),
                                        _dossier()).accepted) == 1


# ============================================================ the priority rule

def test_BUILD_is_REJECTED_while_capabilities_sit_dormant() -> None:
    """*Find unused capability BEFORE inventing new capability.* Authoring another subsystem while
    171 sit disconnected is negative-ROI by the desk's own arithmetic."""
    res = SD.parse_recommendations(json.dumps([_rec(kind=SD.KIND_BUILD)]), _dossier(dormant=171))
    assert res.accepted == []
    assert "171 capabilities already built and unwired" in res.rejected[0].reason
    assert "why_not_activation" in res.rejected[0].reason


def test_BUILD_is_ACCEPTED_when_it_ARGUES_why_activation_will_not_do() -> None:
    """Not a ban -- a burden of proof. A build with a real argument is exactly what the desk wants;
    a build with none is the failure mode."""
    res = SD.parse_recommendations(
        json.dumps([_rec(kind=SD.KIND_BUILD, why_not_activation=_LONG)]), _dossier(dormant=171))
    assert len(res.accepted) == 1
    assert res.accepted[0].why_not_activation == _LONG


def test_a_BOILERPLATE_why_not_activation_does_not_clear_the_burden() -> None:
    res = SD.parse_recommendations(
        json.dumps([_rec(kind=SD.KIND_BUILD, why_not_activation="nothing to activate")]),
        _dossier(dormant=171))
    assert res.accepted == []


def test_the_rule_DOES_NOT_BITE_when_nothing_is_dormant() -> None:
    """A rule that always fires is one that gets switched off. With zero unused capability the
    priority rule has nothing to prefer, and `build` is simply the right answer."""
    res = SD.parse_recommendations(json.dumps([_rec(kind=SD.KIND_BUILD)]), _dossier(dormant=0))
    assert len(res.accepted) == 1


def test_the_rule_is_enforced_on_the_DECLARED_KIND_not_on_the_prose() -> None:
    """Keyword-sniffing the text would be dodgeable by rewording -- and a model that wants to
    propose construction will reword. `kind` is a field it must commit to."""
    sneaky = _rec(kind=SD.KIND_ACTIVATE,
                  title="Build an entirely new subsystem from scratch",
                  bottleneck="we should construct and author a brand new engine " + _LONG)
    assert len(SD.parse_recommendations(json.dumps([sneaky]), _dossier(dormant=171)).accepted) == 1


@pytest.mark.parametrize("kind", ["", "improve", "BUILD_NEW", None, 7])
def test_an_UNDECLARED_or_UNKNOWN_kind_is_rejected(kind) -> None:
    """The priority rule is enforced on this field, so an undeclared kind cannot be accepted --
    otherwise omitting it would be the way around the rule."""
    res = SD.parse_recommendations(json.dumps([_rec(kind=kind)]), _dossier(dormant=171))
    assert res.accepted == [] and "not one of" in res.rejected[0].reason


def test_the_kind_is_case_and_whitespace_insensitive() -> None:
    assert len(SD.parse_recommendations(json.dumps([_rec(kind="  ACTIVATE  ")]),
                                        _dossier()).accepted) == 1


# ============================================================ hostile output shapes

def test_JSON_wrapped_in_prose_is_still_parsed() -> None:
    """Models preface and follow their JSON however they like. Rejecting the whole response for
    surrounding prose would make the contract unusable in practice."""
    raw = f"Here are my recommendations:\n\n{json.dumps([_rec()])}\n\nLet me know if..."
    assert len(SD.parse_recommendations(raw, _dossier()).accepted) == 1


def test_JSON_in_a_FENCED_block_is_still_parsed() -> None:
    raw = f"Thoughts below.\n```json\n{json.dumps([_rec()])}\n```\nDone."
    assert len(SD.parse_recommendations(raw, _dossier()).accepted) == 1


def test_a_PROSE_ONLY_response_is_rejected_as_a_whole() -> None:
    """Prose cannot be validated or ledgered. This is the fluent-advice case, caught at the
    envelope rather than field by field."""
    res = SD.parse_recommendations(
        "The desk should focus on strengthening its validation stack.", _dossier())
    assert res.accepted == []
    assert res.rejected[0].title == "<whole response>"
    assert "no JSON array" in res.rejected[0].reason


def test_UNPARSEABLE_json_is_rejected_with_the_parser_error() -> None:
    res = SD.parse_recommendations("[{'title': 'single quotes'}]", _dossier())
    assert res.accepted == [] and "unparseable JSON" in res.rejected[0].reason


def test_a_JSON_OBJECT_instead_of_an_array_is_rejected() -> None:
    """One recommendation returned bare is still a contract violation: the ledger writer iterates,
    and a dict would be silently iterated as its keys."""
    res = SD.parse_recommendations('{"a": [1]}', _dossier())
    assert res.accepted == []


def test_a_NON_OBJECT_array_element_is_rejected_individually() -> None:
    """One malformed element must not cost the valid ones -- a director whose whole batch is
    discarded for one bad row produces nothing on most runs."""
    raw = json.dumps([_rec(), "just a string", 42, _rec(title="second")])
    res = SD.parse_recommendations(raw, _dossier())
    assert [r.title for r in res.accepted] == ["Wire the dormant allocator", "second"]
    assert len(res.rejected) == 2


def test_an_EMPTY_array_is_accepted_as_zero_recommendations() -> None:
    """"I have nothing to propose" is a legitimate answer and must not read as a parse failure."""
    res = SD.parse_recommendations("[]", _dossier())
    assert res.accepted == [] and res.rejected == [] and res.n_seen == 0


def test_EVERY_rejection_carries_a_reason() -> None:
    """A director whose bad output is silently discarded looks identical to one that produced
    nothing, and the desk could not tell a credit problem from a quality problem."""
    raw = json.dumps([_rec(kind="nonsense"), _rec(bottleneck="short"), "not an object"])
    res = SD.parse_recommendations(raw, _dossier())
    assert len(res.rejected) == 3
    assert all(r.reason for r in res.rejected)


def test_n_seen_counts_BOTH_accepted_and_rejected() -> None:
    """The acceptance RATE is the quality signal. Counting only what passed would make a director
    proposing ten fluent items look identical to one proposing a single good one."""
    res = SD.parse_recommendations(json.dumps([_rec(), _rec(kind="bad")]), _dossier())
    assert res.n_seen == 2


# ============================================================ roi

def test_ROI_is_OPTIONAL_and_a_non_numeric_value_becomes_None() -> None:
    """A missing ROI is honest; a string coerced to a number would rank a recommendation on a
    figure nobody supplied."""
    assert SD.parse_recommendations(json.dumps([_rec()]), _dossier()).accepted[0].roi_bps is None
    got = SD.parse_recommendations(json.dumps([_rec(roi_bps="lots")]), _dossier()).accepted[0]
    assert got.roi_bps is None
    got2 = SD.parse_recommendations(json.dumps([_rec(roi_bps=12.5)]), _dossier()).accepted[0]
    assert got2.roi_bps == pytest.approx(12.5)


# ============================================================ ranking

def test_ACTIVATION_OUTRANKS_AUTHORING_at_equal_roi() -> None:
    """The ordering encodes the rule the parser enforces. The desk's demonstrated failure mode is
    building capability faster than it wires it, so the report must not put a build first."""
    recs = [SD.Recommendation("b", SD.KIND_BUILD, *[_LONG] * 4, roi_bps=100.0),
            SD.Recommendation("a", SD.KIND_ACTIVATE, *[_LONG] * 4, roi_bps=100.0)]
    assert [r.kind for r in SD.rank(recs)] == [SD.KIND_ACTIVATE, SD.KIND_BUILD]


def test_within_a_kind_HIGHER_ROI_comes_first() -> None:
    recs = [SD.Recommendation("low", SD.KIND_ACTIVATE, *[_LONG] * 4, roi_bps=5.0),
            SD.Recommendation("high", SD.KIND_ACTIVATE, *[_LONG] * 4, roi_bps=500.0)]
    assert [r.title for r in SD.rank(recs)] == ["high", "low"]


def test_a_MISSING_ROI_ranks_last_within_its_kind_rather_than_first() -> None:
    """Treating None as infinity would let an unquantified proposal outrank a measured one."""
    recs = [SD.Recommendation("none", SD.KIND_ACTIVATE, *[_LONG] * 4),
            SD.Recommendation("some", SD.KIND_ACTIVATE, *[_LONG] * 4, roi_bps=1.0)]
    assert [r.title for r in SD.rank(recs)] == ["some", "none"]


def test_ranking_an_empty_list_is_empty() -> None:
    assert SD.rank([]) == []


# ============================================================ the ledger route

def test_EVERY_ACCEPTED_recommendation_becomes_a_LEDGER_COMMAND() -> None:
    """Routing through the ledger is what makes this a ROLE rather than a report: §41 then forces
    every row to reach implemented / rejected / scheduled. A director whose output nobody had to
    answer for would be a document with extra steps."""
    res = SD.parse_recommendations(json.dumps([_rec(), _rec(title="second")]), _dossier())
    cmds = SD.to_ledger_commands(res)
    assert len(cmds) == 2
    for argv in cmds:
        assert argv[0] == "add" and "--source" in argv and "--summary" in argv


def test_the_ledger_SUMMARY_carries_all_four_judgeable_fields() -> None:
    """A ledger row missing them is one nobody can later show to be wrong -- which is exactly the
    state the contract exists to prevent, re-created one step downstream."""
    res = SD.parse_recommendations(json.dumps([_rec()]), _dossier())
    summary = SD.to_ledger_commands(res)[0][4]
    for marker in ("BOTTLENECK:", "IMPACT:", "COST:", "SUCCESS:"):
        assert marker in summary
    assert summary.startswith(f"[{SD.KIND_ACTIVATE}]")


def test_REJECTED_recommendations_never_reach_the_ledger() -> None:
    res = SD.parse_recommendations(json.dumps([_rec(kind="nonsense")]), _dossier())
    assert SD.to_ledger_commands(res) == []


def test_roi_is_passed_through_to_the_ledger_only_when_present() -> None:
    with_roi = SD.parse_recommendations(json.dumps([_rec(roi_bps=42.0)]), _dossier())
    without = SD.parse_recommendations(json.dumps([_rec()]), _dossier())
    assert "--roi-bps" in SD.to_ledger_commands(with_roi)[0]
    assert "--roi-bps" not in SD.to_ledger_commands(without)[0]


# ============================================================ the dossier

def test_a_MISSING_artifact_is_NAMED_not_silently_omitted(tmp_path: Path) -> None:
    """A director reasoning off a dossier with invisible holes is GAP_REGISTER #77 in a new
    costume: it will confidently propose work on a subsystem it simply could not see."""
    d = SD.assemble_dossier(tmp_path)
    assert d.complete is False
    assert len(d.missing) == len(SD.DOSSIER_SOURCES)
    assert all("(" in m and ")" in m for m in d.missing), "the path must be named, not just the key"


def test_an_UNPARSEABLE_artifact_counts_as_MISSING(tmp_path: Path) -> None:
    """A torn write is not a present artifact. Carrying it as present with a null payload would
    let the director reason from a hole it believed was data."""
    p = tmp_path / SD.DOSSIER_SOURCES["gate_histogram"]
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{not json", "utf-8")
    d = SD.assemble_dossier(tmp_path)
    assert any("gate_histogram" in m for m in d.missing)
    assert "gate_histogram" not in d.present


def test_a_PRESENT_artifact_is_carried_as_parsed_json(tmp_path: Path) -> None:
    p = tmp_path / SD.DOSSIER_SOURCES["gate_histogram"]
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"gates": {"dsr": 12}}), "utf-8")
    d = SD.assemble_dossier(tmp_path)
    assert d.present["gate_histogram"] == {"gates": {"dsr": 12}}


def test_the_GAP_REGISTER_is_carried_as_its_OPEN_rows_only(tmp_path: Path) -> None:
    """Markdown, not JSON, and the whole file would swamp the prompt. Carrying only OPEN rows is
    what stops the director re-proposing things the desk already knows are broken."""
    p = tmp_path / SD.DOSSIER_SOURCES["gap_register"]
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        "# Register\n"
        "| id | title | status |\n"
        "| 12 | the pager is silent | OPEN |\n"
        "| 13 | the tape has a gap | CLOSED |\n"
        "| 14 | slots never free | RESOLVED |\n"
        "| 15 | coverage below floor | OPEN |\n"
        "not a table row at all\n", "utf-8")
    rows = SD.assemble_dossier(tmp_path).present["gap_register"]
    assert [r.split()[0] for r in rows] == ["#12", "#15"]


def test_the_register_rows_are_CAPPED_so_one_input_cannot_swamp_the_prompt(
        tmp_path: Path) -> None:
    p = tmp_path / SD.DOSSIER_SOURCES["gap_register"]
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(f"| {i} | row {i} | OPEN |" for i in range(200)), "utf-8")
    assert len(SD.assemble_dossier(tmp_path).present["gap_register"]) == 40


def test_the_DORMANT_COUNT_is_read_from_the_intelligence_cycle(tmp_path: Path) -> None:
    """It is the number the priority rule is enforced against. If it silently read zero the rule
    would never bite, and the enforcement would be decorative."""
    p = tmp_path / SD.DOSSIER_SOURCES["dormancy"]
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"capabilities": [
        {"capability": "something_else", "report": {"counts": {"module": 999}}},
        {"capability": "dormancy_hunter", "report": {"counts": {"module": 120, "script": 51}}},
    ]}), "utf-8")
    assert SD.assemble_dossier(tmp_path).dormant_count == 171


def test_the_dormant_count_falls_back_to_the_LIST_LENGTH(tmp_path: Path) -> None:
    p = tmp_path / SD.DOSSIER_SOURCES["dormancy"]
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"capabilities": [
        {"capability": "dormancy_hunter",
         "report": {"dormant": [{"path": "a.py"}, {"path": "b.py"}]}}]}), "utf-8")
    assert SD.assemble_dossier(tmp_path).dormant_count == 2


def test_a_MISSING_dormancy_artifact_leaves_the_count_at_zero(tmp_path: Path) -> None:
    """Zero means the rule does not bite, which is the PERMISSIVE direction -- so the missing
    artifact is named in `missing` and the report shows it. Guessing a number would be worse: the
    rule would fire on a figure nobody measured."""
    d = SD.assemble_dossier(tmp_path)
    assert d.dormant_count == 0
    assert any("dormancy" in m for m in d.missing)


def test_the_summary_states_BOTH_completeness_and_the_dormant_count() -> None:
    s = SD.Dossier(present={"a": 1, "b": 2}, missing=["c (x)"], dormant_count=171).summary()
    assert "2/" in s and "171 dormant" in s


# ============================================================ the prompt

def test_the_prompt_LEADS_WITH_THE_OBJECTIVE() -> None:
    """This seat is the INDEPENDENT model family, which is precisely why it needs the objective
    stated rather than inferred: it does not share the desk's priors, so anything left implicit is
    filled in from its own training."""
    p = SD.build_prompt(_dossier(dormant=171))
    assert p.startswith(SD.OBJECTIVE_PREAMBLE.strip()[:40])


def test_the_prompt_NAMES_the_dormant_count_and_the_next_number() -> None:
    """"Authoring capability number 172 while 171 sit disconnected" is a far harder sentence to
    argue with than a general instruction to prefer activation."""
    p = " ".join(SD.build_prompt(_dossier(dormant=171)).split())
    assert "171" in p and "172" in p


def test_the_prompt_DECLARES_the_missing_artifacts() -> None:
    """A director told what it cannot see will say so; one that is not will fill the hole."""
    d = SD.Dossier(present={"a": 1}, missing=["moat_audit (data/moat_quality.json)"])
    assert "MISSING FROM YOUR DOSSIER" in SD.build_prompt(d)
    assert "moat_audit" in SD.build_prompt(d)


def test_a_COMPLETE_dossier_says_nothing_about_missing_artifacts() -> None:
    assert "MISSING FROM YOUR DOSSIER" not in SD.build_prompt(_dossier())


def test_the_prompt_states_the_UNKNOWN_UNKNOWNS_duty() -> None:
    """"Everything important is already on the register" is the claim the seat exists to attack."""
    # Whitespace-normalised: the phrase wraps across a line in the source, and a test that broke
    # when someone reflowed a paragraph would teach the desk to loosen it. Assert the MEANING.
    p = " ".join(SD.build_prompt(_dossier()).split())
    assert "UNKNOWN-UNKNOWNS" in p
    assert "already on the register" in p


def test_the_prompt_states_that_STATISTICAL_BARS_ARE_IMMUTABLE() -> None:
    """Aggression is law here -- in SCOPE, never in EVIDENCE. Without that sentence the seat's
    anti-timidity mandate reads as licence to lower a bar."""
    p = " ".join(SD.build_prompt(_dossier()).split())
    assert "immutable" in p and "aggression in scope, never in evidence" in p.lower()


# ============================================================ the report

def test_the_report_carries_the_CONTRACT_so_a_rejection_is_actionable() -> None:
    """A rejected model told only "invalid" retries the same shape. The report ships the fields,
    the kinds and the floor."""
    res = SD.parse_recommendations(json.dumps([_rec(), _rec(kind="bad")]), _dossier())
    rep = SD.director_report(res, _dossier(dormant=171))
    assert rep["contract"]["required_fields"] == list(SD.REQUIRED_FIELDS)
    assert rep["contract"]["kinds"] == list(SD.KINDS)
    assert rep["contract"]["min_field_chars"] == SD.MIN_FIELD_CHARS


def test_the_report_is_RANKED_and_serialisable() -> None:
    raw = json.dumps([_rec(title="build", kind=SD.KIND_BUILD, why_not_activation=_LONG),
                      _rec(title="activate", kind=SD.KIND_ACTIVATE)])
    rep = SD.director_report(SD.parse_recommendations(raw, _dossier(dormant=5)), _dossier(5))
    assert [r["title"] for r in rep["accepted"]] == ["activate", "build"]
    json.dumps(rep)


def test_the_report_shows_the_REJECTIONS_and_the_dossier_holes() -> None:
    res = SD.parse_recommendations(json.dumps([_rec(kind="bad")]), _dossier())
    rep = SD.director_report(res, SD.Dossier(present={"a": 1}, missing=["b (x)"]))
    assert rep["n_seen"] == 1
    assert rep["rejected"][0]["reason"]
    assert rep["dossier"]["missing"] == ["b (x)"]
