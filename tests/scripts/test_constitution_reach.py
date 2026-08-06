"""The constitution's REACH -- does every reasoning organ actually carry it?

A constitution that lives in one module is a preference. The desk has already learned this the
expensive way twice: universal duties parked in the brain's own prompt left diggers ordered to do
the dangerous half of a job without the discipline that makes it safe, and a seat cap written as
`n=len(SEATS)` meant five organs consulted three of thirteen funded lineages. Both were laws the
desk believed it was enforcing.

So these tests check the WIRING, not the words -- and, critically, that the check FAILS when the
wiring is broken. A green check that cannot go red is decoration.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import scripts.max_audit as M

from libs.doctrine import ratchet as R


def _keys(defects) -> set[str]:
    return {k for k, _ in defects}


# ------------------------------------------------------------------ live state

def test_the_desk_currently_satisfies_its_own_constitution() -> None:
    d: list = []
    M.check_constitution(d)
    assert d == [], [msg for _, msg in d]


@pytest.mark.parametrize("organ", M._CONSTITUTION_ORGANS)
def test_every_reasoning_organ_injects_the_objective(organ: str) -> None:
    """Parametrised so the failure names the organ. An organ without the objective is still
    optimising something -- the reviewer's instinct for caution, the shape of a tidy answer --
    and nothing in its output announces which."""
    p = Path("scripts") / f"{organ}.py"
    if not p.exists():
        pytest.skip(f"{organ} not present")
    # THE SAME RESOLUTION THE FENCE USES, called rather than restated. A second flat grep here
    # would be a second definition of "carries the objective", and the two would disagree the
    # first time an organ builds its prompt in libs/ -- which `run_strategic_director` does. Then
    # the test is red while max_audit is green, or the reverse, and neither is trustworthy.
    assert M._carries_objective(p), (
        f"{organ} sends a reasoning prompt with no objective in it, and none in the libs module "
        f"it builds the prompt from")


#: Scripts that hold the panel keys but send no reasoning prompt. Argued in writing rather than
#: assumed by silence -- the same discipline `_CHECKS_EXEMPT` uses, and for the same reason: an
#: exemption nobody had to justify is how a list quietly stops covering anything.
_NOT_ORGANS = {
    "seats":                 "key/roster resolution helper -- resolves who to ask, asks nobody",
    "refresh_panel_roster":  "fetches the live model catalog; no prompt, no judgement",
    "score_panel":           "scores completed panel output after the fact",
    "capacity_test":         "probes provider rate limits with a throwaway token",
    "model_upgrade":         "capability BENCHMARK -- its prompts test the model, and seeding "
                             "them with the desk's objective would contaminate the measurement",
    "max_audit":             "the auditor itself; it reads organs, it is not one",
}


def test_the_organ_list_covers_every_script_holding_the_panel_keys() -> None:
    """THE LIST MUST NOT GO STALE the first time somebody adds an organ.

    The net is deliberately over-inclusive -- anything that loads llm_panel.json -- because a
    precise net keyed on how a prompt happens to be spelled misses the next organ that spells it
    differently, and misses it silently. Over-inclusion costs one line in _NOT_ORGANS with a
    reason attached; under-inclusion costs an organ running with no objective and nobody
    noticing, which is the failure this whole file exists to prevent.
    """
    holders = {p.stem for p in Path("scripts").glob("*.py")
               if "llm_panel.json" in p.read_text("utf-8", errors="ignore")}
    missed = sorted(holders - set(M._CONSTITUTION_ORGANS) - set(_NOT_ORGANS))
    assert missed == [], (
        f"script(s) hold the panel keys but are on neither list: {missed}. Either add to "
        "_CONSTITUTION_ORGANS and inject OBJECTIVE_PREAMBLE, or argue the exemption in "
        "_NOT_ORGANS -- the objective must not stop at the boundary of a list nobody updated.")


def test_the_exemptions_are_real_scripts_and_not_stale_names() -> None:
    """An exemption for a file that no longer exists is a hole with a comment over it."""
    gone = sorted(n for n in _NOT_ORGANS if not Path(f"scripts/{n}.py").exists())
    assert gone == [], f"exemptions for scripts that do not exist: {gone}"


# ------------------------------------------------------------------ the check can go red

def test_a_naked_organ_is_detected(monkeypatch, tmp_path) -> None:
    """THE BAR. If this check could not fail, its passing would mean nothing."""
    fake = tmp_path / "scripts"
    fake.mkdir()
    (fake / "pretend_organ.py").write_text("SYSTEM = 'no objective here'\n", "utf-8")
    monkeypatch.setattr(M, "ROOT", tmp_path)
    monkeypatch.setattr(M, "_CONSTITUTION_ORGANS", ("pretend_organ",))
    d: list = []
    M.check_constitution(d)
    assert "constitution-not-injected" in _keys(d)


def test_a_weakened_principle_is_detected(monkeypatch) -> None:
    """The ratchet's only job, exercised through the audit rather than only through its own unit
    test -- the audit is what actually runs every cycle."""
    monkeypatch.setattr(R, "check", lambda *a, **k: R.RatchetReport(
        False, ["P3: aggression 10 -> 4."], [], {}))
    d: list = []
    M.check_constitution(d)
    assert "constitution-ratchet-broken" in _keys(d)
    assert "10 -> 4" in dict(d)["constitution-ratchet-broken"]


def test_removing_the_objective_from_the_shared_doctrine_is_detected(monkeypatch,
                                                                     tmp_path) -> None:
    """Every local organ injects principal_doctrine.txt as its system prompt. An aggression
    stance with no objective for it to serve is the worst of both."""
    (tmp_path / "ops").mkdir()
    (tmp_path / "ops/principal_doctrine.txt").write_text("be aggressive, somehow", "utf-8")
    (tmp_path / "scripts").mkdir()
    monkeypatch.setattr(M, "ROOT", tmp_path)
    monkeypatch.setattr(M, "_CONSTITUTION_ORGANS", ())
    d: list = []
    M.check_constitution(d)
    assert "constitution-absent-from-doctrine" in _keys(d)


def test_the_check_is_registered_and_therefore_actually_runs() -> None:
    """A written check that is never registered is a law the desk believes it is enforcing --
    four consecutive charters shipped that way before check_registry_complete existed."""
    assert any(name == "constitution" for name, _ in M.CHECKS)
    d: list = []
    M.check_registry_complete(d)
    assert d == [], d


# ------------------------------------------------------------------ the committed baseline

def test_the_committed_high_water_mark_is_in_git_not_just_on_disk() -> None:
    """data/ is gitignored, so a mark stored there would vanish on every fresh checkout and the
    ratchet would silently re-baseline to whatever the constitution said that day."""
    assert R.BASELINE_PATH.parts[0] == "docs", (
        f"{R.BASELINE_PATH} must live in a tracked directory or the ratchet resets itself")
    assert R.BASELINE_PATH.exists()


# ------------------------------------------------------------------ the doctrine copy

def test_the_doctrine_copy_is_byte_identical_to_the_module() -> None:
    """A prompt cannot import Python, so the doctrine necessarily holds a COPY. Copies drift --
    the module gets edited, the file does not, and every local organ then runs on a superseded
    objective while the audit enforces the current one. Both look correct in isolation."""
    assert R.preamble_in_sync() is True, (
        "run libs.doctrine.ratchet.sync_preamble() and commit the doctrine")


def test_a_stale_doctrine_copy_is_detected(monkeypatch, tmp_path) -> None:
    """The check must be able to go red, or its passing means nothing."""
    (tmp_path / "ops").mkdir()
    (tmp_path / "scripts").mkdir()
    (tmp_path / "ops/principal_doctrine.txt").write_text(
        "=== CONSTITUTION (immutable) ===\nmax_pi E[log W_T] but an old wording\n"
        "=== END CONSTITUTION ===\nrest of doctrine\n", "utf-8")
    monkeypatch.setattr(M, "ROOT", tmp_path)
    monkeypatch.setattr(M, "_CONSTITUTION_ORGANS", ())
    d: list = []
    M.check_constitution(d)
    assert "constitution-doctrine-stale" in _keys(d)


def test_the_sync_is_one_directional_from_code_to_prompt(tmp_path) -> None:
    """Syncing the other way would let an untested edit to a text file become constitutional."""
    from libs.doctrine.constitution import OBJECTIVE_PREAMBLE
    f = tmp_path / "doctrine.txt"
    f.write_text("=== CONSTITUTION old ===\nstale\n=== END CONSTITUTION ===\ntail\n", "utf-8")
    assert R.sync_preamble(f) == "resynced"
    assert R.preamble_in_sync(f) is True
    assert f.read_text("utf-8").endswith("tail\n"), "the rest of the doctrine must survive"
    assert OBJECTIVE_PREAMBLE in f.read_text("utf-8")


def test_a_doctrine_with_no_constitution_block_gets_one_prepended(tmp_path) -> None:
    """Absent is a different and worse fact than stale, and is not folded into it."""
    f = tmp_path / "doctrine.txt"
    f.write_text("just some standing orders\n", "utf-8")
    assert R.preamble_in_sync(f) is None
    assert R.sync_preamble(f) == "prepended"
    assert R.preamble_in_sync(f) is True


# ------------------------------------------------------------------ P20 everywhere

def test_no_organ_declares_itself_complete() -> None:
    """PRINCIPAL 2026-08-02: the constitutional laws apply everywhere regardless. A law that holds
    only in the module that happens to import it is a local habit -- the same finding as universal
    duties parked in the brain's own prompt, and the doctrine six organs injected and three did
    not. P20 recognises no completion claim for any component."""
    d: list = []
    M.check_no_ceiling(d)
    assert d == [], [msg for _, msg in d]


@pytest.mark.parametrize("organ", M._COVERAGE_ORGANS)
def test_every_progress_organ_names_its_successor(organ: str) -> None:
    """A percentage with no next ceiling reads as a finish line, so the organ goes quiet exactly
    when it turns green -- which is exactly when the next constraint starts binding and nobody is
    looking for it. Parametrised so the failure names the organ."""
    p = Path("scripts") / f"{organ}.py"
    if not p.exists():
        pytest.skip(f"{organ} not present")
    assert "next_ceiling" in p.read_text("utf-8"), (
        f"{organ} reports progress and names no successor")


def test_the_trigger_is_membership_not_a_keyword(monkeypatch, tmp_path) -> None:
    """AN EARLIER VERSION ONLY ASKED ORGANS WHOSE SOURCE CONTAINED THE WORD 'coverage', so two
    progress-reporting organs escaped on a technicality -- the same 'applies only where somebody
    remembered' failure the check exists to close."""
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts/silent_organ.py").write_text("PCT = 100.0\n", "utf-8")
    monkeypatch.setattr(M, "ROOT", tmp_path)
    monkeypatch.setattr(M, "_COVERAGE_ORGANS", ("silent_organ",))
    d: list = []
    M.check_no_ceiling(d)
    assert "coverage-without-next-ceiling" in _keys(d)


def test_a_completion_claim_is_detected(monkeypatch, tmp_path) -> None:
    """The check must be able to go red, or its passing means nothing."""
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts/proud_organ.py").write_text(
        'NEXT = "next_ceiling"\nNOTE = "the miner is fully built. "\n', "utf-8")
    monkeypatch.setattr(M, "ROOT", tmp_path)
    monkeypatch.setattr(M, "_COVERAGE_ORGANS", ("proud_organ",))
    d: list = []
    M.check_no_ceiling(d)
    assert "no-ceiling-violated" in _keys(d)


def test_forbidding_a_completion_claim_is_not_itself_a_violation(monkeypatch, tmp_path) -> None:
    """An organ that FORBIDS the claim necessarily contains the words. A detector that fires on
    the rule against the thing gets switched off within a week -- strictly worse than none."""
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts/careful_organ.py").write_text(
        'NEXT = "next_ceiling"\nRULE = "never say the work is finished here. "\n', "utf-8")
    monkeypatch.setattr(M, "ROOT", tmp_path)
    monkeypatch.setattr(M, "_COVERAGE_ORGANS", ("careful_organ",))
    d: list = []
    M.check_no_ceiling(d)
    assert d == [], d


# ------------------------------------------------------------------ P25: fixers, not watchers

def test_every_detector_carries_a_fix_path() -> None:
    """PRINCIPAL 2026-08-02: everything here is a fixer, not a notifier. A monitor that finds a
    defect and leaves it open is worse than no monitor -- the desk gets the defect AND the false
    comfort of watching it, and the attention the alarm consumes every cycle is a real recurring
    cost bought against nothing."""
    d: list = []
    M.check_fixers_not_watchers(d)
    assert d == [], [msg for _, msg in d]


def test_a_pure_watcher_is_detected(monkeypatch, tmp_path) -> None:
    """The check must go red, and it DID on its first run -- catching two of my own organs."""
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts/nagger.py").write_text(
        'def main():\n    print("something looks wrong")\n', "utf-8")
    monkeypatch.setattr(M, "ROOT", tmp_path)
    monkeypatch.setattr(M, "_DETECTOR_ORGANS", ("nagger",))
    d: list = []
    M.check_fixers_not_watchers(d)
    assert "detector-without-fix-path" in _keys(d)


def test_a_detector_that_cannot_age_its_findings_is_detected(monkeypatch, tmp_path) -> None:
    """Without a counter that only CLOSING clears, a three-week-old leak reads as a fresh finding
    every morning -- which is precisely how a monitor becomes wallpaper."""
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts/tiered.py").write_text('TIER = "PATCH_READY"\n', "utf-8")
    monkeypatch.setattr(M, "ROOT", tmp_path)
    monkeypatch.setattr(M, "_DETECTOR_ORGANS", ("tiered",))
    d: list = []
    M.check_fixers_not_watchers(d)
    assert "detector-cannot-age-its-findings" in _keys(d)


def test_the_pager_is_exempt_by_name_not_by_resemblance() -> None:
    """The alert channel's whole job is to reach a human, so it is the one legitimate pure
    notifier. Exempting by name means nothing else can claim the exemption by looking like it."""
    assert "run_alerts" in M._PURE_NOTIFIER_EXEMPT
    assert not set(M._DETECTOR_ORGANS) & set(M._PURE_NOTIFIER_EXEMPT)


def test_investigate_is_not_an_allowed_outcome() -> None:
    """Three tiers and no fourth. 'Investigate', 'monitor' and 'escalated' are excuses with
    ticket numbers."""
    assert set(M._FIX_TIERS) == {"AUTOFIX", "PATCH_READY", "BLOCKED"}
