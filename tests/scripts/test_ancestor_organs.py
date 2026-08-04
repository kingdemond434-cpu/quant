"""THE TWO NEW MAX-CADENCE ORGANS -- gauntlet calibration and the ancestors run.

WHY THESE EXIST AS ORGANS AND NOT LIBRARIES. Four libraries landed with full test suites and no
caller, which is the exact "built but never runs" class this desk keeps finding in itself. A
library with no caller produces nothing and decays, and the day it is finally wired its first run
meets a codebase that moved underneath it.

Running them for the first time immediately produced two defects that no unit test had caught,
because both only appear against real data:

  * `detection_floor` re-ran the SAME null paths for every strength and printed six identical
    false-positive rates as though they were six independent measurements. A suspiciously stable
    number reads as a robust finding, which is the worst way to be wrong.
  * `breed` stops at the child cap, so its rejection count measures how far the scan got and not
    how diverse the pool is -- 0 rejections out of 24 children looked like a perfectly diverse
    population and meant 24 of 820 pairs had been examined.

Both are pinned below.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import scripts.calibrate_gauntlet as CG
import scripts.run_ancestors as RA

from libs.hypmax.genealogy import BREEDING_MIN_STAGE, Lineage, Specimen, breed, lineage_report
from libs.hypmax.laboratory import detection_floor, false_positive_rate

# ============================================================ the defects real data exposed


def test_the_null_arm_is_measured_once_and_not_re_run_per_strength() -> None:
    """THE FIRST LIVE RUN'S FINDING. The null contains no planted edge, so nothing about it can
    vary with strength -- six per-strength runs were six copies of one number wearing six hats,
    and the identical column read as a robust result."""
    calls: list[int] = []

    def counting_screen(sig, fwd) -> bool:
        calls.append(len(sig))
        return bool(abs(float(np.corrcoef(sig, fwd)[0, 1])) > 0.05)

    rep = detection_floor(counting_screen, strengths=(0.3, 0.15, 0.08), trials=10, n=200)
    fprs = {row["false_positive_rate"] for row in rep["sweep"]}
    assert len(fprs) == 1, "one measurement shared across strengths, by construction"
    # 3 strengths x 10 planted + 1 null arm x 20 = 50, not 3 x (10 + 10) = 60
    assert len(calls) == 50, f"null arm re-run per strength: {len(calls)} screen calls"


def test_power_varies_across_strengths_because_the_seeds_do() -> None:
    """The planted arm MUST differ per strength, or the sweep is one measurement six times in
    the other direction -- the mirror of the bug above."""
    def weak_screen(sig, fwd) -> bool:
        return bool(abs(float(np.corrcoef(sig, fwd)[0, 1])) > 0.18)

    rep = detection_floor(weak_screen, strengths=(0.30, 0.01), trials=30, n=300)
    powers = [row["power"] for row in rep["sweep"]]
    assert powers[0] > powers[-1], f"a strong edge must be easier to find: {powers}"


def test_false_positive_rate_is_callable_on_its_own() -> None:
    assert false_positive_rate(lambda s, f: True, trials=10, n=200) == 1.0
    assert false_positive_rate(lambda s, f: False, trials=10, n=200) == 0.0


def test_a_truncated_breeding_scan_says_so_rather_than_implying_diversity() -> None:
    """0 rejections out of 24 children looks like a perfectly diverse pool and may mean 24 of 820
    pairs were examined. The count measures the scan, not the population."""
    pool = [Specimen(f"s{i}", mechanism=f"m{i}", terms=(f"t{i}", f"u{i}"),
                     stage=BREEDING_MIN_STAGE) for i in range(40)]
    out = breed(pool, max_children=5)
    assert out["scan_truncated"] is True
    assert out["pairs_scanned"] < out["pairs_total"]
    assert "measures how far the scan got" in out["scan_note"]


def test_an_exhaustive_scan_reports_no_truncation() -> None:
    pool = [Specimen(f"s{i}", mechanism=f"m{i}", terms=(f"t{i}",), stage=BREEDING_MIN_STAGE)
            for i in range(4)]
    out = breed(pool, max_children=100)
    assert out["scan_truncated"] is False
    assert out["scan_note"] == ""
    assert out["pairs_scanned"] == out["pairs_total"] == 6


def test_fertility_declares_itself_non_discriminating_on_a_flat_population() -> None:
    """THE SECOND LIVE FINDING. Every graveyard entry reached the gauntlet and every one died, so
    'reached_stage' is 100% everywhere and the ranking degenerates into a shrunk attempt count
    wearing the word 'fertility'. Acting on it would point generation at whichever tag is most
    common in a list of FAILURES -- precisely backwards."""
    lin = Lineage()
    for i in range(20):
        lin.add(Specimen(f"g{i}", family=f"f{i % 3}", stage=BREEDING_MIN_STAGE, survived=False))
    rep = lineage_report(lin)
    assert rep["discriminating"] is False
    assert "nothing to rank on" in rep["note"]
    assert "most common in a list of FAILURES" in rep["note"]


def test_a_population_with_real_stage_variation_does_discriminate() -> None:
    lin = Lineage()
    for i in range(20):
        lin.add(Specimen(f"g{i}", family="a", stage=1))
    for i in range(3):
        lin.add(Specimen(f"h{i}", family="b", stage=7))
    assert lineage_report(lin)["discriminating"] is True


# ============================================================ gauntlet calibration


def test_escalate_is_not_counted_as_a_detection() -> None:
    """The screen's OWN distinction, and it is load-bearing: PASS means 'measured and it looks
    real', ESCALATE means 'not measurable here, proceeding anyway'. Counting ESCALATE as a hit
    would report a screen with no opinion at all as having perfect power -- the exact flattery
    this calibration exists to strip out."""
    src = Path("scripts/calibrate_gauntlet.py").read_text("utf-8")
    assert 'r.decision == "PASS"' in src
    assert "ESCALATE" in src


def test_the_calibration_declares_that_it_covers_L3_only(tmp_path, monkeypatch) -> None:
    """A clean L3 result NARROWS the 420/420 question rather than answering it -- the campaign
    died at L4, which this sweep does not touch. Overstating the scope would retire a live
    suspect on evidence that never looked at it."""
    monkeypatch.setattr(CG, "OUT", tmp_path / "cal.json")
    monkeypatch.setattr(CG, "HISTORY", tmp_path / "hist.jsonl")
    monkeypatch.setattr(CG, "TRIALS", 6)
    monkeypatch.setattr(CG, "N_OBS", 300)
    assert CG.main() == 0
    d = json.loads((tmp_path / "cal.json").read_text("utf-8"))
    assert "L3 ONLY" in d["screen"]
    assert "died at L4" in d["scope"]
    assert d["false_positive_rate"] is not None


def test_the_calibration_records_history_so_the_floor_can_be_trended(tmp_path,
                                                                    monkeypatch) -> None:
    """The floor is only a progress metric if yesterday's value survives. A single-shot artifact
    can report a number and never notice it got worse."""
    monkeypatch.setattr(CG, "OUT", tmp_path / "cal.json")
    monkeypatch.setattr(CG, "HISTORY", tmp_path / "hist.jsonl")
    monkeypatch.setattr(CG, "TRIALS", 5)
    monkeypatch.setattr(CG, "N_OBS", 300)
    CG.main()
    CG.main()
    rows = (tmp_path / "hist.jsonl").read_text("utf-8").strip().splitlines()
    assert len(rows) == 2
    assert json.loads(rows[0])["detection_floor"] is not None


def test_a_blind_screen_is_named_as_a_broken_instrument(tmp_path, monkeypatch) -> None:
    """THE VERDICT THAT MATTERS MOST. If the screen cannot find a planted edge, a campaign of
    rejections carries no information at all about whether edges exist."""
    monkeypatch.setattr(CG, "OUT", tmp_path / "cal.json")
    monkeypatch.setattr(CG, "HISTORY", tmp_path / "hist.jsonl")
    monkeypatch.setattr(CG, "TRIALS", 4)
    monkeypatch.setattr(CG, "N_OBS", 300)
    monkeypatch.setattr(CG, "_screen_fires", lambda *a, **k: False)
    CG.main()
    d = json.loads((tmp_path / "cal.json").read_text("utf-8"))
    assert d["detection_floor"] is None
    assert "THE INSTRUMENT IS BROKEN" in d["verdict"]


# ============================================================ the ancestors run


@pytest.fixture
def ancestors(tmp_path, monkeypatch):
    monkeypatch.setattr(RA, "OUT", tmp_path / "ancestors.json")
    monkeypatch.setattr(RA, "QUEUE", tmp_path / "queue.jsonl")
    monkeypatch.setattr(RA, "VERDICTS", tmp_path / "verdicts.jsonl")
    monkeypatch.setattr(RA, "MAX_FEATURES", 5)
    return tmp_path


def test_the_run_reads_the_real_graveyard_and_produces_specimens(ancestors) -> None:
    """42 permanently-killed hypotheses with tags, in git, available today. Provenance is never
    recorded retroactively, so the day this is not running is a day of parentage lost."""
    assert RA.main() == 0
    d = json.loads((ancestors / "ancestors.json").read_text("utf-8"))
    assert d["sources"]["graveyard"] > 30
    assert d["specimens"] == d["sources"]["graveyard"] + d["sources"]["queue"]


def test_the_run_states_it_has_no_promotion_authority(ancestors) -> None:
    """Every child and feature is a CANDIDATE at the full bar. Inherited standing is how a
    breeding programme launders a weak idea."""
    RA.main()
    d = json.loads((ancestors / "ancestors.json").read_text("utf-8"))
    assert d["authority"].startswith("NONE")
    assert all(c["generation"] >= 1 for c in d["children"])


def test_theory_stays_dormant_against_a_graveyard_of_failures(ancestors) -> None:
    """Zero survivors means zero to be theoretical about. Inducing anyway produces confident
    prose that reads exactly like a theory."""
    RA.main()
    d = json.loads((ancestors / "ancestors.json").read_text("utf-8"))
    assert d["theory"]["state"] == "DORMANT"


def test_the_market_reports_uniform_weights_rather_than_inventing_them(ancestors) -> None:
    """With nothing settled there is no evidence any seat is better. Manufacturing weights is
    fabrication wearing the costume of sophistication."""
    RA.main()
    d = json.loads((ancestors / "ancestors.json").read_text("utf-8"))
    assert d["market"]["settled_claims"] == 0
    assert "correct output, not a limitation" in d["market"]["note"]


def test_generic_words_are_stripped_so_similarity_does_not_collapse() -> None:
    """Left in, every specimen shares them, every pair reads as near-identical, and breeding
    refuses everything -- which looks exactly like a converged population."""
    t = RA._terms("The cross-sectional premium signal effect of funding basis")
    assert "the" not in t and "premium" not in t and "signal" not in t
    assert "funding" in t and "basis" in t


def test_a_malformed_queue_line_never_kills_the_run(ancestors) -> None:
    """A dropped line is a gap; a crash is a dark organ."""
    (ancestors / "queue.jsonl").write_text('not json\n{"name":"ok","mechanism":"funding"}\n',
                                           "utf-8")
    assert RA.main() == 0
    d = json.loads((ancestors / "ancestors.json").read_text("utf-8"))
    assert d["sources"]["queue"] == 1


# ============================================================ cadence wiring


def test_both_organs_run_every_cycle() -> None:
    """A library with no caller produces nothing and decays. These were the last two."""
    src = Path("scripts/run_cadence.py").read_text("utf-8")
    for organ in ("scripts/calibrate_gauntlet.py", "scripts/run_ancestors.py"):
        assert organ in src, organ
    assert 'fired.append("gauntlet-calibration")' in src
    assert 'fired.append("ancestors")' in src


def test_both_organs_are_checked_for_PRODUCTION_not_exit_code() -> None:
    """The desk's own scar: a panel exited clean, wrote nothing, and marked its duty done. An
    exit code proves a process ended, never that it produced."""
    src = Path("scripts/run_cadence.py").read_text("utf-8")
    assert 'not Path("data/gauntlet_calibration.json").exists()' in src
    assert 'not Path("data/ancestors.json").exists()' in src


# ============================================================ the allocator

import scripts.run_allocator as AL  # noqa: E402


def test_the_allocator_refuses_to_rank_when_nothing_is_measured(tmp_path, monkeypatch) -> None:
    """THE TEMPTING MOVE THIS REFUSES. Assigning plausible priors so the allocator 'works' would
    produce a confident ranking made entirely of guesses, wearing the vocabulary of measurement.
    That is worse than no allocator, because a ranking gets acted on."""
    monkeypatch.setattr(AL, "OUT", tmp_path / "alloc.json")
    monkeypatch.setattr(AL, "LEDGER", tmp_path / "led.json")
    assert AL.main() == 0
    d = json.loads((tmp_path / "alloc.json").read_text("utf-8"))
    assert d["allocation"]["funded"] == []
    assert d["allocation"]["vip"] is None
    assert "made entirely of guesses" in d["why_no_ranking"]


def test_every_constitutional_subsystem_is_covered_by_the_instrument_map() -> None:
    """A subsystem with no declared artifact can never be instrumented, and would sit in the
    'uninstrumented' column forever with no way out. 'Instrument it' is useless advice without
    naming WHERE the number goes."""
    from libs.doctrine.constitution import SUBSYSTEM_DERIVATIVES
    missing = sorted(set(SUBSYSTEM_DERIVATIVES) - set(AL._INSTRUMENTS))
    assert missing == [], f"subsystems with no declared instrument: {missing}"


def test_every_instrument_entry_says_what_the_artifact_must_contain() -> None:
    """A path with no contract produces a file somebody creates empty to clear the check."""
    thin = sorted(k for k, (_, needs) in AL._INSTRUMENTS.items() if len(needs) < 25)
    assert thin == [], f"instruments with no stated contents: {thin}"


def test_an_empty_table_counts_as_uninstrumented(tmp_path, monkeypatch) -> None:
    """EXISTENCE IS NOT ENOUGH. An empty table and a missing table are the same fact here -- no
    contribution can be computed from either -- and the desk has repeatedly been fooled by a file
    that exists, a process that exits clean, and nothing produced."""
    import sqlite3
    db = tmp_path / "m.sqlite"
    with sqlite3.connect(db) as c:
        c.execute("create table fills (id integer)")
    monkeypatch.setattr(AL, "METRICS", db)
    assert AL._exists("desk_metrics:fills") is False
    with sqlite3.connect(db) as c:
        c.execute("insert into fills values (1)")
    assert AL._exists("desk_metrics:fills") is True


def test_a_missing_database_is_uninstrumented_rather_than_a_crash(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(AL, "METRICS", tmp_path / "absent.sqlite")
    assert AL._exists("desk_metrics:fills") is False


def test_the_starvation_ledger_survives_across_runs(tmp_path, monkeypatch) -> None:
    """Priority decides order, never entitlement -- and 'never once funded across many cycles' is
    only visible if the ledger outlives a single run."""
    monkeypatch.setattr(AL, "OUT", tmp_path / "alloc.json")
    monkeypatch.setattr(AL, "LEDGER", tmp_path / "led.json")
    AL.main()
    assert (tmp_path / "led.json").exists()
    AL.main()
    assert "misses" in json.loads((tmp_path / "led.json").read_text("utf-8"))


def test_the_allocator_runs_every_cycle_and_is_checked_for_production() -> None:
    src = Path("scripts/run_cadence.py").read_text("utf-8")
    assert "scripts/run_allocator.py" in src
    assert 'fired.append("allocator")' in src
    assert 'not Path("data/allocator.json").exists()' in src


# ============================================================ the cost model must not lie

def test_a_prose_mention_is_not_a_write() -> None:
    """CAUGHT ON THE FIRST LIVE RUN AGAINST 8GB OF REAL TAPE. The old matcher reported
    'deep_review.py is already scheduled and writes desk_metrics:fills' -- from a docstring
    reading "fills, rate limits, or a 5xx mid-sequence". deep_review is a hostile code reviewer;
    it has never written a fill. That mislabelled the gap cost-1 when nothing can close it, and an
    incorrect cost model sends the chase at the wrong gap first."""
    writers = AL._writers("desk_metrics:fills")
    assert "scripts/deep_review.py" not in writers
    assert any(w.endswith("store/trading.py") for w in writers), (
        "the real writer is the INSERT INTO fills in libs/store/trading.py")


def test_a_table_write_requires_an_insert_not_a_mention(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(AL, "ROOT", tmp_path)
    (tmp_path / "scripts").mkdir()
    (tmp_path / "libs").mkdir()
    (tmp_path / "scripts/talker.py").write_text('"""we discuss widgets here."""\n', "utf-8")
    (tmp_path / "scripts/writer.py").write_text('Q = "INSERT INTO widgets VALUES (?)"\n', "utf-8")
    assert AL._writers("desk_metrics:widgets") == ["scripts/writer.py"]


def test_a_library_only_writer_is_not_a_cheap_gap() -> None:
    """A LIBRARY is not an organ. The producing path has never executed, so no amount of
    estimate-writing closes it -- reporting cost-1 would send the chase somewhere it cannot win."""
    cost, why = AL._closure_cost("desk_metrics:fills", "")
    assert cost == AL._COST_NO_ORGAN
    assert "only a LIBRARY writes this" in why
    assert "never executed" in why


def test_libs_is_scanned_not_just_scripts() -> None:
    """The writer of record for fills lives in libs/store. A scan limited to scripts/ would have
    reported 'nothing writes this' -- wrong in the opposite direction."""
    assert any(w.startswith("libs/") for w in AL._writers("desk_metrics:fills"))


# ---------------------------------------------------------------- writers must be BOUND to paths
#
# THE THIRD TIME THIS SHAPE APPEARED. Requiring "the path is mentioned somewhere in the file" AND
# "a write call happens somewhere in the file" leaves the two unconnected, so any file that READS a
# set of artifacts and writes its own output is credited with writing all of them. On the cycle
# estimate_contributions.py landed -- it reads twenty artifacts and writes one -- the allocator
# reported it as the writer of every artifact it consumes, which would have marked twenty real
# gaps as one-estimate-away.


def test_a_path_in_a_read_map_is_not_a_write() -> None:
    """The exact regression. A module holding a dict of paths to READ, plus a write call for its
    OWN artifact, must not be credited with writing the ones it reads."""
    src = '''
SOURCES = {"a": "data/read_me.json", "b": "data/also_read.jsonl"}
REPORT = ROOT / "data/my_output.json"
REPORT.write_text(json.dumps(out), "utf-8")
'''
    assert AL._writes_path(src, "data/my_output.json") is True
    assert AL._writes_path(src, "data/read_me.json") is False
    assert AL._writes_path(src, "data/also_read.jsonl") is False


def test_a_name_bound_to_a_path_and_then_written_counts() -> None:
    """The normal idiom on this desk: assign the path to a module constant, write through it."""
    src = 'OUT = ROOT / "data/x.json"\nOUT.write_text("{}", "utf-8")\n'
    assert AL._writes_path(src, "data/x.json") is True


def test_an_inline_literal_inside_a_write_expression_counts() -> None:
    src = '(ROOT / "data/y.json").write_text("{}", "utf-8")\n'
    assert AL._writes_path(src, "data/y.json") is True


def test_opening_a_path_for_READING_is_not_a_write() -> None:
    """`.open(` was the token that made this fail: it is the most common way to READ a file, so
    admitting it bare credited every reader as a writer. The mode is now required."""
    read = 'P = ROOT / "data/z.json"\nwith P.open(encoding="utf-8") as fh:\n    d = fh.read()\n'
    assert AL._writes_path(read, "data/z.json") is False
    append = ('P = ROOT / "data/z.json"\n'
              'with P.open("a", encoding="utf-8") as fh:\n    fh.write(x)\n')
    assert AL._writes_path(append, "data/z.json") is True


def test_the_contributions_organ_is_credited_with_exactly_one_artifact() -> None:
    """Checked against the REAL file rather than a fixture, because the fixture is what passed
    while production was wrong. It reads twenty artifacts and writes one."""
    assert AL._writers("data/contributions.json") == ["scripts/estimate_contributions.py"]
    for consumed in ("data/panel_budget_state.json", "data/cadence_state.json",
                     "data/gauntlet_calibration.json"):
        assert "scripts/estimate_contributions.py" not in AL._writers(consumed), consumed
