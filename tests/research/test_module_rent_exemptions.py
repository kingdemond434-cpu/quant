"""NO EXEMPTION WITHOUT A FALSIFIER -- the rent ledger's excuses must be able to expire.

    "A module cannot exist forever for free."                        -- the principal, 2026-09-17

`module_rent` retires an organ that burns compute and mints no cells, UNLESS it carries a
declared exemption. Until 2026-09-24 that exemption was a token -> reason map and nothing else:
a sentence with no condition under which it stops being true, which made it the one structure on
this desk that could never be wrong. What is pinned here:

  * every declaration -- the 21 owned rows AND the two inherited ones -- carries a `retire_if`
    over the length bar and names checks the module actually measures;
  * the CONSTRUCTOR refuses a row without one, so there is no code path that writes a
    falsifier-less exemption, and `EXEMPT_TOKENS` stays DERIVED so the old shape cannot return;
  * each of the three checks fires on the evidence it claims to read and NOT on anything else;
  * UNMEASURED never deletes an exemption and never quietly passes as "it holds" (L1.28a) --
    a half-measured condition leaves the shield up and says so;
  * a fired falsifier stops shielding in the SAME pass, so a module whose excuse has been shown
    false is judged like every other module rather than waiting for a person;
  * the census names a declaration a person should delete, and the fence reads that census.
"""

from __future__ import annotations

import json
import subprocess
import sys
import token as _token
import tokenize
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "scripts"), str(ROOT / "desks" / "mt5"),
           str(ROOT / "desks" / "mt5" / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import module_rent as mr  # noqa: E402  (the desk imports its research organs by bare name)


def _row(module: str = "scripts/check_thing.py", **kw: Any) -> dict[str, Any]:
    """A rent row with every field the falsifiers read, defaulted to 'measured, nothing fired'."""
    base: dict[str, Any] = {"module": module, "clock": "none", "attribution": "declared_producer",
                            "candidates_30d": 0, "admissions_30d": 0, "survivors_30d": 0}
    base.update(kw)
    return base


# --------------------------------------------------------------------------- the schema
def test_every_declared_exemption_carries_a_falsifier() -> None:
    """The whole point: an exemption that cannot expire is a permanent excuse."""
    assert mr.EXEMPTIONS, "an empty registry would pass every check below vacuously"
    for key, ex in [*mr.EXEMPTIONS.items(), *mr.INHERITED.items()]:
        assert ex.retire_if.strip(), f"{key}: no retire_if"
        assert len(ex.retire_if.strip()) >= mr.MIN_RETIRE_IF_CHARS, f"{key}: retire_if too thin"
        assert ex.checks, f"{key}: retire_if names no measured check"
        for c in ex.checks:
            assert c in mr.RETIRE_CHECKS, f"{key}: unknown check {c!r}"
            assert c in mr._RETIRE_FN, f"{key}: check {c!r} is declared with no implementation"
        assert ex.declared_utc, f"{key}: an undated claim cannot be aged"
    assert mr.validate_exemptions() == []


def test_the_constructor_refuses_an_exemption_with_no_falsifier() -> None:
    """Validation in the module itself, not only in this file: a fence you can forget to run is
    not a fence. Every rejected form below is a way someone could have written a permanent
    excuse without noticing."""
    ok = {"why": "governance: a law gate thing", "retire_if": "x" * 60,
          "checks": ("mints_cells",), "declared_utc": "2026-09-24"}
    mr.Exemption(**ok)                                            # the control: this is valid
    for bad, needle in (({"retire_if": ""}, "permanent excuse"),
                        ({"retire_if": "it stops being true"}, "permanent excuse"),
                        ({"checks": ()}, "no measured check"),
                        ({"checks": ("no_such_check",)}, "unknown check"),
                        ({"why": "thin"}, "not a decision"),
                        ({"declared_utc": "soon"}, "not a YYYY-MM-DD date")):
        with pytest.raises(ValueError, match=needle):
            mr.Exemption(**{**ok, **bad})


def test_exempt_tokens_stays_derived_so_the_old_shape_cannot_return() -> None:
    """The falsifier-less map was `EXEMPT_TOKENS: dict[str, str] = {...}`. It survives only as a
    DERIVED view; a literal there would be a second exemption surface with no condition on it."""
    assert {tok: ex.why for tok, ex in mr.EXEMPTIONS.items()} == mr.EXEMPT_TOKENS
    src = (ROOT / "desks" / "mt5" / "research" / "module_rent.py").read_text("utf-8")
    decl = [ln for ln in src.splitlines() if ln.startswith("EXEMPT_TOKENS")]
    assert decl and "{tok: ex.why for tok, ex in EXEMPTIONS.items()}" in decl[0]


def test_reason_lookup_still_answers_the_old_question() -> None:
    """`simplifier.dead` asks only "is this excused", so the old signature must keep working."""
    assert mr.exempt_reason("scripts/check_thing.py", {}, ()) == mr.EXEMPTIONS["check_"].why
    assert mr.exempt_reason("desks/mt5/research/alpha_breadth.py", {}, ()) is None
    why = mr.exempt_reason("scripts/learn.py", {"scripts/learn.py": "a CLI a person runs"}, ())
    assert why == "a CLI a person runs (wiring_ceo.EXEMPT)"


def test_precedence_is_unchanged_and_the_borrowed_rows_inherit_a_falsifier() -> None:
    """wiring_ceo's two lists arrive as bare strings; neither may reach the retire decision
    without a condition on it, and the order they are consulted in must not have moved."""
    key, ex = mr.exemption_for("scripts/learn.py", {"scripts/learn.py": "a CLI a person runs"},
                               ("learn",))
    assert key == "scripts/learn.py" and ex.checks == ("gains_a_clock", "mints_cells")
    # A 19-char borrowed reason used to RAISE out of `replace` and take the whole build down.
    assert ex.why == "a CLI a person runs (wiring_ceo.EXEMPT)" and ex.retire_if.strip()
    key, ex = mr.exemption_for("scripts/run_gateway.py", {}, ("gateway",))
    assert key == "gateway" and ex.checks == ("mints_cells",)
    assert ex.unmeasured, "the un-measurable half of a money-path excuse must be SAID (L1.28a)"


# --------------------------------------------------------------------------- the checks
def test_mints_cells_fires_only_on_measured_downstream_research() -> None:
    fired, why = mr._check_mints_cells(_row(candidates_30d=4), None)
    assert fired is True and "4 candidate" in why
    assert mr._check_mints_cells(_row(survivors_30d=1), None)[0] is True
    assert mr._check_mints_cells(_row(), None)[0] is False
    fired, why = mr._check_mints_cells(_row(candidates_30d=None, attribution="none"), None)
    assert fired is None and "absence is not a zero" in why


def test_output_reaches_nobody_reads_the_dead_architecture_verdict_and_nothing_else() -> None:
    """BURNING is that census's own word for "on a clock and no reader found". UNREACHED is
    explicitly NOT a verdict of death there, so it must not delete an exemption here."""
    assert mr._check_output_reaches_nobody(_row(), {"verdict": "BURNING"})[0] is True
    assert mr._check_output_reaches_nobody(_row(), {"verdict": "LIVE"})[0] is False
    assert mr._check_output_reaches_nobody(_row(), {"verdict": "NO_CLOCK"})[0] is False
    assert mr._check_output_reaches_nobody(_row(), {"verdict": "UNREACHED"})[0] is None
    assert mr._check_output_reaches_nobody(_row(), None)[0] is None


def test_gains_a_clock_falsifies_a_no_schedule_claim() -> None:
    assert mr._check_gains_a_clock(_row(clock="clock names it"), None)[0] is True
    assert mr._check_gains_a_clock(_row(clock="none"), None)[0] is False


def test_any_declared_check_firing_retires_the_row() -> None:
    ex = mr.EXEMPTIONS["check_"]
    assert mr.retire_if_fires(ex, _row(candidates_30d=9), {"verdict": "LIVE"})[0] is True
    assert mr.retire_if_fires(ex, _row(), {"verdict": "BURNING"})[0] is True
    assert mr.retire_if_fires(ex, _row(), {"verdict": "LIVE"})[0] is False


def test_a_half_measured_condition_is_unmeasured_and_keeps_the_shield_up() -> None:
    """L1.28a: "one of the two halves could not be looked at" is not "the claim survived", and
    absence never deletes anything either. The gap has to carry the check's name."""
    ex = mr.EXEMPTIONS["check_"]
    fired, why = mr.retire_if_fires(ex, _row(), None)             # no dead_architecture row
    assert fired is None and "UNMEASURED" in why and "output_reaches_nobody" in why
    fired, why = mr.retire_if_fires(ex, _row(candidates_30d=None), {"verdict": "LIVE"})
    assert fired is None and "mints_cells" in why


# --------------------------------------------------------------------------- the effect
def test_a_fired_falsifier_stops_shielding_in_the_same_pass() -> None:
    """An excuse shown false must stop working immediately -- a condition that fires and changes
    nothing until a person acts is decoration, which is what this whole change refuses."""
    row = _row(clock="hourly_cycle:x", candidates_30d=0)
    st = mr.exemption_status(row["module"], row, {"verdict": "BURNING"}, {}, ())
    assert st is not None and st["fired"] is True
    verdict, _ = mr._verdict({**row, "roi": 0.0, "exempt_why": None if st["fired"] else st["why"],
                              "merge_with": None, "compute_h_30d": 1.0}, 1.0, 0.5)
    assert verdict == "RETIRE_CANDIDATE"
    st_ok = mr.exemption_status(row["module"], row, {"verdict": "LIVE"}, {}, ())
    assert st_ok is not None and st_ok["fired"] is False
    verdict, _ = mr._verdict({**row, "roi": 0.0, "exempt_why": st_ok["why"],
                              "merge_with": None, "compute_h_30d": 1.0}, 1.0, 0.5)
    assert verdict != "RETIRE_CANDIDATE"


def test_the_census_names_a_declaration_a_person_should_delete() -> None:
    rows = [
        {"module": "scripts/check_a.py", "exempt_key": "check_", "exempt_fired": True,
         "exempt_fired_why": "output_reaches_nobody: BURNING"},
        {"module": "scripts/check_b.py", "exempt_key": "check_", "exempt_fired": False},
        {"module": "scripts/report_x.py", "exempt_key": "report", "exempt_fired": True,
         "exempt_fired_why": "mints_cells: 3 candidates"},
        {"module": "scripts/smoke_y.py", "exempt_key": "smoke", "exempt_fired": None},
    ]
    by = {d["key"]: d for d in mr.exemption_census(rows)}
    assert by["check_"]["verdict"] == "PARTIAL"
    assert by["check_"]["fired_modules"][0]["module"] == "scripts/check_a.py"
    assert by["report"]["verdict"] == "RETIRE"
    assert by["smoke"]["verdict"] == "UNMEASURED"
    assert by["audit"]["verdict"] == "COVERS_NOTHING"          # seeded, covered by nothing here
    for d in by.values():                                      # every row can be acted on
        assert d["retire_if"] and d["checks"] and d["why_verdict"]


def test_an_unmeasured_exemption_is_never_reported_as_holding() -> None:
    rows = [{"module": "scripts/check_a.py", "exempt_key": "check_", "exempt_fired": None}]
    by = {d["key"]: d for d in mr.exemption_census(rows)}
    assert by["check_"]["verdict"] == "UNMEASURED"
    assert by["check_"]["n_measured"] == 0


def test_build_publishes_the_census_on_an_empty_tree(tmp_path: Path) -> None:
    """The measurement has to survive a host with no artifacts: every exemption reads UNMEASURED
    or COVERS_NOTHING, none reads HOLDS, and the report says the dead-architecture half is
    missing rather than passing on its absence."""
    (tmp_path / "desks" / "mt5" / "reports").mkdir(parents=True)
    (tmp_path / "desks" / "mt5" / "data").mkdir(parents=True)
    doc = mr.build(tmp_path, budget_s=10.0)
    assert doc["exemption_schema_problems"] == []
    assert doc["exemptions"] and doc["exemptions_summary"]["n_declared_here"] == len(mr.EXEMPTIONS)
    assert {e["verdict"] for e in doc["exemptions"]} <= {"COVERS_NOTHING", "UNMEASURED"}
    assert any("dead_architecture" in u for u in doc["unmeasured"])


# --------------------------------------------------------------------------- the fence
def test_the_fence_exists_and_is_wired_into_the_law_gate() -> None:
    """LAWS 7 / III.16: a fence that runs on no clock is a claim the desk cannot cash. The law
    gate fires on every commit, every push, in CI and hourly on the VPS crontab."""
    fence = ROOT / "scripts" / "check_exemption_falsifiers.py"
    assert fence.is_file()
    gate = (ROOT / "scripts" / "run_law_gate.py").read_text("utf-8")
    assert "check_exemption_falsifiers.py" in gate
    from scripts.run_law_gate import _LAW_FENCES
    picked = [a for f, a in _LAW_FENCES if f == "check_exemption_falsifiers.py"]
    assert picked == [("--schema-only",)], "the law half must be the portable one"


def test_the_fence_passes_on_this_tree_and_breaks_on_a_falsifier_less_exemption() -> None:
    """The schema half is a GATE, not a report: it has to go red on the defect it names."""
    import check_exemption_falsifiers as fence

    problems, census = fence.check_module_schema()
    assert problems == [] and census["n_declared"] == len(mr.EXEMPTIONS)
    blk, blk_census = fence.check_blockers()
    assert blk == [] and blk_census["measured"] and blk_census["n_exempt"] > 0

    saved = dict(mr.EXEMPTIONS)
    try:
        mr.EXEMPTIONS["_smuggled"] = object.__new__(mr.Exemption)   # bypasses __post_init__
        object.__setattr__(mr.EXEMPTIONS["_smuggled"], "why", "governance: a law gate thing")
        object.__setattr__(mr.EXEMPTIONS["_smuggled"], "retire_if", "")
        object.__setattr__(mr.EXEMPTIONS["_smuggled"], "checks", ())
        object.__setattr__(mr.EXEMPTIONS["_smuggled"], "declared_utc", "2026-09-24")
        object.__setattr__(mr.EXEMPTIONS["_smuggled"], "source", "test")
        object.__setattr__(mr.EXEMPTIONS["_smuggled"], "unmeasured", "")
        problems, _ = fence.check_module_schema()
        assert any("permanent excuse" in p for p in problems)
    finally:
        mr.EXEMPTIONS.clear()
        mr.EXEMPTIONS.update(saved)
    assert fence.check_module_schema()[0] == []


@pytest.mark.timeout(180)
def test_the_fence_runs_as_a_process_and_exits_zero_on_the_schema_half() -> None:
    r = subprocess.run([sys.executable, "scripts/check_exemption_falsifiers.py",
                        "--schema-only", "--json"], cwd=ROOT, capture_output=True, text=True,
                       check=False)
    assert r.returncode == 0, r.stdout + r.stderr
    rep = json.loads(r.stdout)
    assert rep["schema_problems"] == []
    assert rep["module_rent"]["n_declared"] == len(mr.EXEMPTIONS)
    assert sorted(rep["module_rent"]["checks"]) == sorted(mr.RETIRE_CHECKS)


#: Identifiers that would mean this change had become a brake. Matched against NAME tokens only
#: -- prose about not throttling anything is not throttling anything, and a substring search over
#: the raw text cannot tell the two apart.
_THROTTLE_NAMES = frozenset({"disable", "throttle", "shrink", "heat_floor", "cap", "cadence_s",
                             "MAX_COMPUTE", "budget_cap"})


def _identifiers(path: Path) -> set[str]:
    with path.open("rb") as fh:
        return {t.string for t in tokenize.tokenize(fh.readline) if t.type == _token.NAME}


def test_the_expiry_never_became_a_brake() -> None:
    """NEVER REDUCE AGGRESSIVENESS (principal, 2026-09-08): deleting a stale excuse must not turn
    into a cap on any organ's compute. Neither file may NAME a throttle -- and the rent report
    still says in its own words that nothing here is disabled."""
    for rel in ("scripts/check_exemption_falsifiers.py", "desks/mt5/research/module_rent.py"):
        hit = _identifiers(ROOT / rel) & _THROTTLE_NAMES
        assert not hit, f"{rel} names {sorted(hit)}: an expiry is not a cap"
    doc = mr.build.__doc__ or ""
    src = (ROOT / "desks" / "mt5" / "research" / "module_rent.py").read_text("utf-8")
    assert "NOTHING IS DISABLED HERE" in src, doc


def test_the_fence_writes_one_artifact_and_changes_no_state() -> None:
    """A law fence that edited the thing it judges would be a fence nobody could trust. The only
    file this one writes is its own report."""
    import ast

    fence = ROOT / "scripts" / "check_exemption_falsifiers.py"
    tree = ast.parse(fence.read_text("utf-8"))
    writes = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
              and isinstance(n.func, ast.Attribute)
              and n.func.attr in ("write_text", "write_bytes", "unlink", "replace", "mkdir")]
    targets = {ast.unparse(n.func.value) for n in writes}
    assert targets <= {"ARTIFACT", "ARTIFACT.parent"}, targets
