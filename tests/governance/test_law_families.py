"""L1.36 -- law families enforced AS families, and the aggression family at maximum strength."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from scripts.check_law_families import FAMILIES, build_report
from scripts.check_timidity_language import _prompt_surfaces, audit_prompts


def _git_repo(root: Path, files: dict[str, str]) -> None:
    """A throwaway repo with one commit. NEVER mutate the shared checkout to test a git
    behaviour -- sibling sessions are writing to it right now, which is the very defect R0402
    is about."""
    def _g(*a: str) -> None:
        subprocess.run(["git", *a], cwd=root, capture_output=True, text=True, check=True)
    _g("init", "-q")
    _g("config", "user.email", "t@t"), _g("config", "user.name", "t")
    for rel, body in files.items():
        (root / rel).write_text(body, "utf-8")
    _g("add", "-A")
    _g("commit", "-qm", "base")


@pytest.fixture(autouse=True, scope="module")
def _matrix_built():
    """These tests read data/enforcement_matrix.json, which is GENERATED and gitignored.

    Without this they passed only on a machine that had already built it -- on CI, solely
    because an earlier workflow step happens to run the builder before pytest. Run `pytest`
    alone on a clean checkout and they failed, reporting six DECORATIVE families: a test
    describing the machine's history rather than the code. A test must supply its own inputs.
    """
    if not Path("data/enforcement_matrix.json").exists():
        # subprocess, not an in-process main(): the builder parses sys.argv, which under pytest
        # is pytest's own command line.
        subprocess.run([sys.executable, "scripts/build_enforcement_matrix.py"],
                       check=True, capture_output=True, timeout=180)


def test_all_six_families_fully_enforced():
    rep = build_report()
    assert rep["status"] == "OK", rep["failing"]
    assert rep["n_families"] == 6


@pytest.mark.parametrize("name", sorted(FAMILIES))
def test_family_is_complete_fenced_reaching_and_guarded(name):
    f = build_report()["families"][name]
    assert f["missing_from_constitution"] == []       # COMPLETE
    assert f["unfenced"] == []                        # ENFORCED (never prose)
    assert f["not_in_doctrine"] == []                 # REACHING every organ at spawn
    assert f["family_fence_exists"] is True           # GUARDED at family level


def test_aggression_family_holds_the_full_stack():
    members = FAMILIES["aggression"][0]
    for law in ("L1.21a", "L1.28", "L1.28a", "L1.28b", "L1.28c", "L1.25a", "L1.35"):
        assert law in members


def test_l23_reaches_the_organs_now():
    # The proving instance: fenced in the matrix, absent from doctrine, never told to an organ.
    # Reach is judged on the PAYLOAD an organ receives (doctrine + docs/LAWS.md since the
    # 2026-08-25 consolidation), the same corpus the fence and the fast gate read.
    from libs.doctrine.corpus import doctrine_text
    assert "L2.3" in doctrine_text()


def test_timidity_fence_sweeps_every_prompt_surface():
    surfaces = _prompt_surfaces()
    assert len(surfaces) >= 16                        # 11 miner briefs + prompts/ + organ genomes
    names = {p.name for p in surfaces}
    assert "kimi_hunter.py" in names                  # the only non-Claude hunter
    assert "deep_sweep_core.txt" in names             # the audit genome
    assert any(n.startswith("frontier_") for n in names)


def test_quota_caps_and_hedged_orders_are_caught(tmp_path, monkeypatch):
    import scripts.check_timidity_language as t
    p = tmp_path / "ops"
    p.mkdir()
    (p / "x_prompt.txt").write_text(
        "Report the top 3 findings.\nOptionally dig further if time permits.\n", "utf-8")
    monkeypatch.setattr(t, "_ROOT", tmp_path)
    monkeypatch.setattr(t, "_prompt_surfaces", lambda: [p / "x_prompt.txt"])
    kinds = {h["kind"] for h in t.audit_prompts()}
    assert kinds == {"QUOTA-CAP", "HEDGED-ORDER"}


def test_live_prompt_surfaces_are_clean():
    hits = audit_prompts()
    assert hits == [], [f"{h['file']}:{h['line']} {h['kind']}" for h in hits]


def test_breadth_per_run_stays_legal():
    # L1.35 REQUIRES runs to finish, so a per-run bound is a completion bound, not timidity.
    # Removing this exemption would make the desk's own completion contract illegal.
    src = Path("scripts/check_timidity_language.py").read_text("utf-8")
    assert "breadth-per-run" in src and "completion bound" in src


def test_fence_is_a_gate_not_a_report():
    src = Path("scripts/check_law_families.py").read_text("utf-8")
    assert 'return 2 if rep["status"] != "OK" else 0' in src
    assert "A gate, not a report" in src or "a gate, not a report" in src.lower()


# --- L1.37 continuous enforcement at every boundary --------------------------------------------

def test_law_and_state_fences_are_separated():
    from scripts.run_law_gate import _LAW_FENCES, _STATE_FENCES
    # Disjoint by INVOCATION, not by filename: one fence may carry a law half and a state half
    # (check_scheduler_manifest: manifest<->repo integrity is law, live-crontab drift is state),
    # but the exact same invocation must never sit on both sides of the commit gate.
    law = {(f, a) for f, a in _LAW_FENCES}
    state = {(f, a) for f, a in _STATE_FENCES}
    assert law and state and not (law & state)
    # law fences must be portable: they read the repo, so CI can run them meaningfully
    law_names = {f for f, _ in law}
    assert "check_constitution_core.py" in law_names and "check_law_families.py" in law_names
    # state fences measure box-only live state and must NOT gate a commit
    state_names = {f for f, _ in state}
    assert "check_exploration.py" in state_names and "check_conversion.py" in state_names
    # the scheduler fence's law-side invocation must suppress its state half (live drift, rc=1):
    # on a red-parked box the manifest is SUPPOSED to lead the installed crontab, and a commit
    # gate that fails on that wedges the exact push that heals it.
    sched_law = [a for f, a in _LAW_FENCES if f == "check_scheduler_manifest.py"]
    assert sched_law == [("--report-only",)]


@pytest.mark.timeout(900)
def test_laws_only_gate_passes_in_a_fresh_checkout():
    """R0402: this test asserted a property of a FRESH CHECKOUT and evaluated it against the
    shared working tree. On a box where sibling sessions build continuously that is a different
    artifact, and on 2026-08-05 it was a materially different one -- rc=2 on nine scripts whose
    manifest lines existed only in another session's uncommitted file. The gate now judges HEAD,
    so the name and the assertion finally describe the same thing; `subject` is asserted because
    a verdict that does not name its subject is what let the two drift apart unnoticed.

    STATES ITS OWN COST (gap-fixer 2026-08-29), which is the mechanism pyproject.toml's timeout
    comment prescribes: "A genuinely slow test states its own cost with @pytest.mark.timeout(N)
    rather than relaxing the floor for everything."

    MEASURED on a QUIET box: 88 seconds. It is expensive by construction and legitimately so --
    on a dirty tree `full_gate` does a real `git worktree add --detach` of this repository and
    then runs the entire law battery inside it, because judging the working tree as it sits was
    R0402's bug. The desk's tree is essentially always dirty (organs commit ~200x/day and leave
    artifacts modified), so the expensive branch is the normal one.

    WHY THIS MATTERS MORE THAN ONE TEST: under load it exceeded the 300s floor, and
    pytest-timeout kills the SESSION. That is what took the desk-wide CI gate down -- the
    2026-08-29 01:20 marker recorded `failed: ['tests (pytest)']` with an EMPTY failing-test
    list, and the 2026-08-28 08:54 marker named 25 tests that all pass in isolation. Every
    other test's verdict in those runs was simply unknown. A suite that cannot finish is worse
    than a suite with a named red: it converts one slow test into total blindness.

    900s is this test's honest cost plus contention headroom, and it is scoped to this test
    alone -- the 300s floor is untouched for everything else (the ratchet rule: one test's need
    is never the whole suite's licence)."""
    from scripts.run_law_gate import full_gate
    rep = full_gate(laws_only=True)
    assert rep["ok"] is True, rep["failures"]
    assert "HEAD" in rep["subject"], rep["subject"]


def test_a_DIRTY_tree_is_judged_at_HEAD_not_as_it_sits(tmp_path: Path) -> None:
    """The mechanism, on a throwaway repo so the shared checkout is never mutated."""
    from scripts.run_law_gate import _at_head
    _git_repo(tmp_path, {"f.txt": "committed"})
    (tmp_path / "f.txt").write_text("UNCOMMITTED SIBLING WORK", "utf-8")
    where, subject, why = _at_head(tmp_path)
    try:
        assert where != tmp_path and why == []
        assert (where / "f.txt").read_text("utf-8") == "committed"
        assert "HEAD" in subject and "1 file(s) dirty" in subject
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", str(where)],
                       cwd=tmp_path, capture_output=True, text=True)


def test_a_CLEAN_tree_is_judged_in_place_and_pays_for_no_checkout(tmp_path: Path) -> None:
    """A clean tree already IS HEAD, so CI and a fresh clone pay nothing for this: the checkout
    is bought only when the verdict would otherwise be about the wrong artifact."""
    from scripts.run_law_gate import _at_head
    _git_repo(tmp_path, {"f.txt": "committed"})
    where, subject, why = _at_head(tmp_path)
    assert where == tmp_path and why == [] and "tree clean" in subject


def test_an_UNAVAILABLE_head_checkout_is_REPORTED_never_silently_ignored(tmp_path: Path) -> None:
    """Falling back to the dirty tree in silence would re-create the defect while looking fixed:
    the reader sees PASS and cannot tell which artifact earned it (L1.28a)."""
    from scripts.run_law_gate import _at_head
    subprocess.run(["git", "init", "-q", str(tmp_path)], capture_output=True, text=True)
    (tmp_path / "f.txt").write_text("never committed -- HEAD does not resolve", "utf-8")
    where, subject, why = _at_head(tmp_path)
    assert where == tmp_path
    assert why and "head-checkout-unavailable" in why[0]
    assert "UNAVAILABLE" in subject and "UNCOMMITTED" in subject


def test_fast_gate_guards_core_and_doctrine():
    from scripts.run_law_gate import fast_gate
    rep = fast_gate()
    assert rep["ok"] is True, rep["failures"]


def test_unrunnable_fence_counts_as_failed_never_skipped():
    src = Path("scripts/run_law_gate.py").read_text("utf-8")
    assert "counts as FAILED, never skipped" in src
    assert "MISSING -- an absent fence is a failed fence" in src


def test_all_four_boundaries_are_wired():
    assert "run_law_gate.py --laws-only" in Path(".github/workflows/ci.yml").read_text("utf-8")
    hook = Path("deploy/git_hooks/pre-push")
    assert hook.exists() and "run_law_gate.py" in hook.read_text("utf-8")
    assert "_law_gate_fast" in Path("ops/brain_env.sh").read_text("utf-8")
    assert "run_law_gate.py" in Path("ops/crontab.manifest").read_text("utf-8")
    assert "git_hooks/pre-push" in Path("deploy/pull_deploy.sh").read_text("utf-8")


def test_spawn_gate_pages_but_does_not_block():
    # A governance fault must never silently stop the desk (L1.2).
    be = Path("ops/brain_env.sh").read_text("utf-8")
    assert "_brain_page" in be and "return 0" in be.split("_law_gate_fast()")[1][:900]


# --- L1.39 zero idle findings ------------------------------------------------------------------

def test_l39_in_conversion_family_and_mapped():
    from scripts.check_law_families import FAMILIES
    assert "L1.39" in FAMILIES["conversion"][0]
    mx = Path("scripts/build_enforcement_matrix.py").read_text("utf-8")
    assert '"L1.39"' in mx


def test_l39_draws_the_action_vs_validation_distinction():
    # The load-bearing safety line: no idle = zero ACTION latency, NOT zero validation latency.
    # Without this, "implement immediately" becomes the phantom-edge factory the desk bans.
    const = " ".join(Path("docs/CONSTITUTION.md").read_text("utf-8").replace("**", "").split())
    assert "L1.39 ZERO IDLE FINDINGS" in const
    assert "never size it immediately" in const
    assert "a candidate is never an edge" in const
    from libs.doctrine.corpus import doctrine_text
    assert "THE IMMEDIACY IS IN THE ROUTING, NEVER IN THE BAR" in doctrine_text()


# --- the gate must be green on a VIRGIN tree, not only on one that has run it before -----------

def test_matrix_producer_runs_before_its_consumer_in_the_law_gate():
    """build_enforcement_matrix WRITES what check_law_families READS -- so it must run first.

    REGRESSION PIN. data/enforcement_matrix.json is gitignored (data/*), so it exists on any
    machine that has run the gate before and on no clean checkout. With the consumer ordered
    first, the gate was green on the box and on dev clones while failing on EVERY clean checkout:
    master CI failed 10 consecutive runs (30651154078..30654344515) on
    "BREACH check_law_families.py (rc=2)" for commits that passed locally. Reproduced exactly by
    running the gate twice in a fresh worktree -- first run FAIL, second run PASS, the only
    difference being the artifact the first run left behind. Ordering is the fix; this pins it.
    """
    from scripts.run_law_gate import _LAW_FENCES
    names = [n for n, _args in _LAW_FENCES]
    assert names.index("build_enforcement_matrix.py") < names.index("check_law_families.py")


def test_absent_matrix_reports_unmeasured_not_sixty_five_decorative_laws(tmp_path):
    """A missing INPUT is not a verdict about the laws -- and must still never buy a pass.

    The swallowed OSError made "no matrix on this machine" arrive at the comparison as "the
    matrix says not one of these laws has a fence", so every family reported DECORATIVE -- the
    most alarming state this fence has -- with the actual cause printed nowhere. Ordering alone
    would hide that again the moment the producer fails for any other reason.
    """
    for rel in ("docs/CONSTITUTION.md", "ops/principal_doctrine.txt"):
        src, dst = Path(rel), tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(src.read_text("utf-8"), "utf-8")
    rep = build_report(tmp_path)                       # no data/enforcement_matrix.json
    assert rep["status"] == "UNMEASURED"
    assert "enforcement_matrix" in rep["matrix_why"]
    assert "build_enforcement_matrix.py" in rep["matrix_why"]
    # UNMEASURED, never DECORATIVE: the laws' fenced-ness is unknown here, not known to be absent
    assert {f["state"] for f in rep["families"].values()} == {"UNMEASURED"}
    assert all(f["unfenced"] == [] for f in rep["families"].values())
