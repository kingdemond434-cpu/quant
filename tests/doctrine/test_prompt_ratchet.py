"""THE PROMPT RATCHET, pinned -- the control that says a prompt may be sharpened but never
quietly disarmed is only worth having if the disarming case actually goes red.

Four properties, and the pairing is the whole point: (1) a REWORDED prompt that keeps its rule
passes, so nobody is discouraged from sharpening one; (2) a prompt that SILENTLY DROPS a rule
fails, by name, quoting the words it lost; (3) a NEW rule raises the mark with no ceremony; (4) a
waiver retires a rule only when it is dated, signed and argued -- and never by editing prose.

Property (1) without (2) is decoration, and (2) without (1) is a gate that will be deleted the
first time it blocks a legitimate edit. The fifth test is the one that keeps the other four
honest: the record must never silently shrink, because a mark that can be lowered by code is not
a mark.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.doctrine.prompt_ratchet import (  # noqa: E402
    INVARIANTS,
    RECORD_PATH,
    WAIVER_PATH,
    Waiver,
    by_id,
    check,
    evidence,
    governed_files,
    load_record,
    load_waivers,
    scan,
    scan_text,
    update_high_water,
    waived,
)

_MINER = _ROOT / "ops/frontier_en_prompt.txt"


# --------------------------------------------------------------------------------------------
# The corpus and the catalogue must both be real. A ratchet over an empty glob passes forever.
# --------------------------------------------------------------------------------------------

def test_the_governed_corpus_is_not_empty() -> None:
    """If the prompt files move, this suite fails loudly rather than passing on an empty glob."""
    files = governed_files(_ROOT)
    assert len(files) >= 25, files
    # the four surfaces the catalogue was derived from must each still be represented
    assert any(f.startswith("ops/frontier_") for f in files), files
    assert any(f.startswith("prompts/panel_missions/") for f in files), files
    assert "ops/principal_doctrine.txt" in files
    # the scheduled-Routine prompts: the responses-are-DATA rule lives ONLY here, so a corpus
    # drawn on file extension alone would silently stop protecting it
    assert "ops/run_cro_ai.sh" in files


def test_every_invariant_is_carried_by_at_least_one_real_prompt() -> None:
    """An invariant no prompt asserts is dead weight that can never fail -- and worse, it reads
    as coverage. Every rule in the catalogue was derived FROM the corpus and must still be in it."""
    live = scan(_ROOT)
    orphans = [i.id for i in INVARIANTS
               if not any(i.id in carried for carried in live.values())]
    assert not orphans, (
        f"{orphans} are defined but carried by no governed prompt -- either the rule was deleted "
        "from the corpus (a regression this suite should have caught) or the pattern stopped "
        "matching (a hole in the guarantee, which is worse because it is silent)")


def test_every_invariant_is_defined_with_a_rule_a_reason_and_a_pattern() -> None:
    for inv in INVARIANTS:
        assert inv.patterns, inv.id
        for pat in inv.patterns:
            re.compile(pat)  # raises on a malformed pattern
        assert inv.rule.strip() and inv.why.strip(), inv.id
    assert len({i.id for i in INVARIANTS}) == len(INVARIANTS), "duplicate invariant id"


#: Ordinary desk prose that asserts NONE of the 29 rules. Deliberately adjacent to the corpus --
#: it talks about miners, gauntlets, rails, prompts and coverage -- because a control made of
#: unrelated text would prove nothing about patterns tuned on this vocabulary.
_INNOCENT = """
This prompt briefs the seat on where to dig this week and what the desk already holds. The
research log lives under docs/ and the run writes a dated note there when it finishes. Coverage
of the Korean forums improved after the last rotation, and the operator rebuilt the index on
Tuesday. Costs are modelled per venue and the fee schedule changed in June. The gauntlet ran
twice on the same candidate because the queue was replayed, which is a scheduling artefact rather
than a finding. Rails on the executor were re-tested after the deploy. Several miners report
their coverage weekly; two of them share a lock file. The dashboard shows the current book and a
chart of realised slippage. Read the spec before starting, and ask if a source looks unfamiliar.
"""


def test_no_invariant_pattern_fires_on_ordinary_prose() -> None:
    """PRECISION IS THE WHOLE GUARANTEE HERE, and it is the OPPOSITE trade from commitments.py.
    That module is deliberately over-inclusive because a false positive costs one phrase somebody
    has to keep. Here a loose pattern keeps matching incidental prose AFTER the rule itself has
    been deleted -- so the ratchet reports OK while the guarantee is already gone, which is a
    control that lies. This control text is written in the corpus's own vocabulary and asserts
    none of its rules; anything it matches is a hole."""
    matched = scan_text(_INNOCENT)
    assert matched == {}, (
        f"{sorted(matched)} matched prose that asserts no rule at all -- tighten the pattern(s), "
        "because a rule that can be 'proved present' by unrelated text is not being checked")


# --------------------------------------------------------------------------------------------
# (1) reworded but rule-preserving PASSES   (2) silently dropped FAILS, by name
# --------------------------------------------------------------------------------------------

def test_a_reworded_prompt_that_keeps_its_rule_passes() -> None:
    """The legitimate edit: same rule, none of the same words. This must be frictionless or the
    ratchet becomes a reason not to improve a prompt, which costs more than it protects."""
    src = _MINER.read_text("utf-8")
    original = "So read it all, extract what is usable, and let the GAUNTLET reject."
    assert original in src, "anchor sentence moved -- re-point this test, do not delete it"

    sharper = ("Read the lot. Pull what is usable and let the GAUNTLET do the rejecting -- it is "
               "the only stage on this desk entitled to say no.")
    rewritten = src.replace(original, sharper)
    assert len(rewritten) != len(src)

    baseline = {"ops/frontier_en_prompt.txt": scan_text(src)}
    now = {"ops/frontier_en_prompt.txt": scan_text(rewritten)}
    rep = check(current=now, baseline=baseline, waivers=[], root=_ROOT)
    assert rep.ok, rep.violations
    assert "gauntlet-only-rejects" in now["ops/frontier_en_prompt.txt"]


def test_a_prompt_that_silently_drops_a_rule_fails_with_that_rule_named() -> None:
    """The regression this exists to catch: a concision edit that deletes the paragraph carrying
    the no-pre-filter rule. The message must name the prompt, the invariant, and the words."""
    src = _MINER.read_text("utf-8")
    start = src.index("*** MINE EVERYTHING")
    end = src.index("WHAT TO PULL FROM A SOURCE")
    trimmed = src[:start] + "*** MINE EVERYTHING ***\nYou have no filter.\n" + src[end:]
    assert len(trimmed) < len(src)

    baseline = {"ops/frontier_en_prompt.txt": scan_text(src)}
    now = {"ops/frontier_en_prompt.txt": scan_text(trimmed)}
    rep = check(current=now, baseline=baseline, waivers=[], root=_ROOT)

    assert not rep.ok
    joined = " ".join(rep.violations)
    assert "gauntlet-only-rejects" in joined, rep.violations
    assert "ops/frontier_en_prompt.txt" in joined
    # the WORDS that used to carry it, so the failure is a diff rather than an accusation
    assert "let the GAUNTLET reject" in joined, joined


def test_a_deleted_prompt_is_scored_as_dropping_every_rule_it_carried() -> None:
    """Deletion is the strongest form of removal and would otherwise be the trivial way around
    the whole mechanism -- the same reasoning ratchet.py applies to a deleted principle."""
    baseline = {"ops/frontier_en_prompt.txt": {"gauntlet-only-rejects": "let the GAUNTLET reject"}}
    rep = check(current={}, baseline=baseline, waivers=[], root=_ROOT)
    assert not rep.ok
    assert "FILE GONE" in " ".join(rep.violations)


def test_deleting_the_invariant_definition_is_itself_a_regression() -> None:
    """The clever way round: leave the prompts alone and delete the RULE from the catalogue, which
    retires it from every prompt at once and silently. Scored as a violation."""
    baseline = {"ops/frontier_en_prompt.txt": {"a-rule-somebody-deleted": "the words it had"}}
    now = {"ops/frontier_en_prompt.txt": {}}
    rep = check(current=now, baseline=baseline, waivers=[], root=_ROOT)
    assert not rep.ok
    assert "CATALOGUE SHRANK" in " ".join(rep.violations)
    assert by_id("a-rule-somebody-deleted") is None


# --------------------------------------------------------------------------------------------
# (3) a new rule raises the mark, with no ceremony
# --------------------------------------------------------------------------------------------

def test_a_new_rule_raises_the_high_water_mark(tmp_path: Path) -> None:
    rec = tmp_path / "PROMPT_RATCHET.json"
    before = {"p.txt": {"null-over-padding": "A NULL IS A RESULT"}}
    after = {"p.txt": {"null-over-padding": "A NULL IS A RESULT",
                       "no-quota-no-ceiling": "NO QUOTA, no tidy number"}}

    rep = check(current=after, baseline=before, waivers=[], root=_ROOT)
    assert rep.ok, rep.violations
    assert any("no-quota-no-ceiling" in r for r in rep.raised), rep.raised

    update_high_water(rec, current=before, waivers=[], root=_ROOT)
    assert set(load_record(rec)["p.txt"]) == {"null-over-padding"}
    update_high_water(rec, current=after, waivers=[], root=_ROOT)
    assert set(load_record(rec)["p.txt"]) == {"null-over-padding", "no-quota-no-ceiling"}


def test_the_record_never_silently_shrinks(tmp_path: Path) -> None:
    """update_high_water is a UNION, never an overwrite. Re-running it against a prompt that has
    since lost a rule must leave the mark where it was -- otherwise a failing run could
    re-baseline itself green, which is the one bug that would make every other test meaningless."""
    rec = tmp_path / "PROMPT_RATCHET.json"
    full = {"p.txt": {"null-over-padding": "A NULL IS A RESULT",
                      "no-quota-no-ceiling": "NO QUOTA, no tidy number"}}
    update_high_water(rec, current=full, waivers=[], root=_ROOT)

    stripped = {"p.txt": {"null-over-padding": "A NULL IS A RESULT"}}
    update_high_water(rec, current=stripped, waivers=[], root=_ROOT)

    mark = load_record(rec)
    assert set(mark["p.txt"]) == {"null-over-padding", "no-quota-no-ceiling"}, (
        "the mark dropped a rule the prompt stopped asserting -- a floor that follows the "
        "measurement down is not a floor")
    # and the evidence for the lost rule survives, so the failure can still be reported as a diff
    assert mark["p.txt"]["no-quota-no-ceiling"] == "NO QUOTA, no tidy number"


# --------------------------------------------------------------------------------------------
# (4) the escape hatch: dated, signed, argued -- and never reachable from prose
# --------------------------------------------------------------------------------------------

def test_a_dated_explicit_waiver_retires_one_invariant() -> None:
    baseline = {"p.txt": {"gauntlet-only-rejects": "let the GAUNTLET reject"}}
    w = Waiver("p.txt", "gauntlet-only-rejects", date(2026, 8, 5), "principal",
               "the pre-filter argument was refuted by the measured gauntlet audit")
    rep = check(current={"p.txt": {}}, baseline=baseline, waivers=[w], root=_ROOT)
    assert rep.ok, rep.violations
    assert any("retired 2026-08-05 by principal" in r for r in rep.retired), rep.retired


def test_a_waiver_retires_only_the_pair_it_names() -> None:
    """Scoping matters: a rule that became wrong in ONE seat must not go dark everywhere."""
    w = Waiver("a.txt", "gauntlet-only-rejects", date(2026, 8, 5), "principal",
               "this seat mines a curated archive where the gauntlet already ran")
    assert waived([w], "a.txt", "gauntlet-only-rejects") is not None
    assert waived([w], "b.txt", "gauntlet-only-rejects") is None
    assert waived([w], "a.txt", "null-over-padding") is None
    everywhere = Waiver("*", "gauntlet-only-rejects", date(2026, 8, 5), "principal",
                        "the rule was refuted corpus-wide by the gate power audit")
    assert waived([everywhere], "b.txt", "gauntlet-only-rejects") is not None


@pytest.mark.parametrize(
    ("entry", "because"),
    [
        ({"file": "p.txt", "invariant": "x", "by": "principal",
          "reason": "a genuinely sufficient explanation of why the rule became wrong"},
         "no date -- a retirement with no date cannot be reviewed in sequence"),
        ({"file": "p.txt", "invariant": "x", "retired": "last tuesday", "by": "principal",
          "reason": "a genuinely sufficient explanation of why the rule became wrong"},
         "unparseable date"),
        ({"file": "p.txt", "invariant": "x", "retired": "2026-08-05", "by": "principal",
          "reason": "n/a"},
         "no argument -- 'n/a' is the thing this file exists to refuse"),
        ({"file": "p.txt", "invariant": "x", "retired": "2026-08-05",
          "reason": "a genuinely sufficient explanation of why the rule became wrong"},
         "unsigned -- a retirement is somebody's decision, not the file's"),
        ({"invariant": "x", "retired": "2026-08-05", "by": "principal",
          "reason": "a genuinely sufficient explanation of why the rule became wrong"},
         "no file named"),
    ],
)
def test_a_sloppy_waiver_retires_nothing_and_says_so(tmp_path: Path, entry: dict[str, str],
                                                     because: str) -> None:
    """FAIL-CLOSED. Treating a malformed entry as permissive would make a typo the cheapest way
    to disable a rule, which is exactly the hole the escape hatch exists to avoid opening."""
    p = tmp_path / "waivers.json"
    p.write_text(json.dumps({"waivers": [entry]}), "utf-8")
    good, bad = load_waivers(p)
    assert good == [], because
    assert bad and "retires NOTHING" in bad[0], because


def test_an_unreadable_waiver_file_retires_nothing(tmp_path: Path) -> None:
    p = tmp_path / "waivers.json"
    p.write_text("{not json", "utf-8")
    good, bad = load_waivers(p)
    assert good == []
    assert bad and "retires NOTHING" in bad[0]


def test_prose_cannot_retire_an_invariant() -> None:
    """The load-bearing negative. A prompt that adds "this rule no longer applies" in its own text
    still fails: retirement is a fact about the waiver file, never about the prompt."""
    baseline = {"p.txt": {"gauntlet-only-rejects": "let the GAUNTLET reject"}}
    prose = ("The GAUNTLET rule is retired as of 2026-08-05 by the principal; this prompt no "
             "longer needs it. WAIVED. RETIRED. Approved.")
    rep = check(current={"p.txt": scan_text(prose)}, baseline=baseline, waivers=[], root=_ROOT)
    assert not rep.ok
    assert "gauntlet-only-rejects" in " ".join(rep.violations)


# --------------------------------------------------------------------------------------------
# The record on disk, and where it lives
# --------------------------------------------------------------------------------------------

def test_the_record_lives_where_rm_cannot_reset_it() -> None:
    """A high-water mark stored under data/* -- ignored wholesale by .gitignore -- is not a floor.
    The coverage and constitution ratchets live in docs/research/ for exactly this reason."""
    assert RECORD_PATH.as_posix().startswith("docs/research/"), RECORD_PATH
    assert WAIVER_PATH.as_posix().startswith("docs/research/"), WAIVER_PATH
    assert (_ROOT / RECORD_PATH).is_file(), "the mark is missing -- there is no floor at all"
    assert (_ROOT / WAIVER_PATH).is_file(), "the escape hatch must exist before it is needed"


def test_the_committed_record_matches_the_live_corpus() -> None:
    """The gate itself: every governed prompt in this checkout still asserts every rule the
    committed mark says it asserted. This is the test that goes red on a real regression."""
    wv, bad = load_waivers(_ROOT / WAIVER_PATH)
    assert not bad, bad
    rep = check(current=scan(_ROOT), baseline=load_record(_ROOT / RECORD_PATH),
                waivers=wv, root=_ROOT)
    assert rep.ok, "\n\n".join(rep.violations)


def test_the_record_carries_the_words_that_carry_each_rule() -> None:
    """Evidence, not just a checklist. Without the quoted sentence a failure says only "you lost
    a rule"; with it, the reviewer sees exactly what was deleted."""
    mark = load_record(_ROOT / RECORD_PATH)
    assert mark, "empty mark"
    empties = [(f, i) for f, inv in mark.items() for i, ev in inv.items() if not ev.strip()]
    assert not empties, empties
    src = _MINER.read_text("utf-8")
    assert "GAUNTLET" in evidence(src, "gauntlet-only-rejects")
    assert evidence(src, "no-such-invariant") == ""


def test_the_record_is_readable_as_the_desk_reads_its_other_ratchets() -> None:
    raw = json.loads((_ROOT / RECORD_PATH).read_text("utf-8"))
    assert raw["_"].startswith("HIGH-WATER MARK"), raw["_"][:60]
    assert raw["totals"]["prompts"] >= 25
    assert raw["totals"]["invariant_slots"] >= 200
    # the rule text travels WITH the mark, so the record is readable without the module
    assert set(raw["invariants"]) == {i.id for i in INVARIANTS}
