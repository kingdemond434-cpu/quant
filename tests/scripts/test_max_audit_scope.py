"""THE AUDITOR MUST SAY WHICH MACHINE A DEFECT IS ABOUT.

`data/` and `web/` are gitignored, so every artifact under them is absent in a fresh checkout BY
CONSTRUCTION. max_audit fired on that absence in exactly the same words it used for a genuinely
broken organ, and the two readings were indistinguishable in the report. That is not hypothetical
damage: five defects were relayed to the principal as real when three of them rested on `data/`
paths that no clone can have. The auditor was not wrong to fire -- on the machine that owns the
history an absent artifact IS the defect -- it was wrong to present both readings identically and
leave the reader to guess.

These tests pin the discrimination:

  REPO     the defect names git-tracked evidence -- verifiable and closable from any checkout.
  RUNTIME  it names only untracked paths -- real on the machine that runs the organ, and
           unresolvable here, so it must not page the principal from a clone.
  UNSCOPED it names nothing and the check read nothing -- escalated AS REPO, because unknown
           provenance must never become an excuse.

And the tie-break, which is the part that points at me: a defect citing BOTH kinds is REPO.
Misfiling a runtime defect as mine costs an investigation; misfiling mine as the machine's lets it
live forever behind "needs the VPS". Only the second failure is self-serving.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scripts.max_audit as M  # noqa: E402

# --------------------------------------------------------------------- scope_of

def test_tracked_evidence_is_repo_scope() -> None:
    assert M.scope_of(["docs/graveyard.md"], []) == "REPO"


def test_untracked_only_is_runtime_scope() -> None:
    assert M.scope_of([], ["data/panel_verdicts.jsonl"]) == "RUNTIME"


def test_no_evidence_at_all_is_unscoped() -> None:
    assert M.scope_of([], []) == "UNSCOPED"


def test_mixed_evidence_breaks_toward_repo_when_nothing_is_missing() -> None:
    """THE ASYMMETRY IS DELIBERATE. Both failure modes are possible; only one is self-serving.

    Conditioned on nothing being ABSENT -- see the test below, which is the case that matters far
    more often in practice.
    """
    assert M.scope_of(["docs/graveyard.md"], ["docs/graveyard.md"]) == "REPO"


def test_an_ABSENT_untracked_artifact_outranks_a_present_tracked_remedy() -> None:
    """THE REFINEMENT, AND IT WAS PADDING THE PRINCIPAL PAGE. Defect prose names two kinds of path
    and they mean opposite things:

        "data/moat_screen.json absent -- ... Run scripts/screen_moat.py."
         ^ the EVIDENCE: untracked and NOT THERE      ^ the REMEDY: tracked and present

    Counting the tracked one first returned REPO, so a defect true on every fresh checkout BY
    CONSTRUCTION -- data/ is gitignored -- was paged as a repository fault left unfixed. Three of
    eleven REPO defects on the live page were this, and a page padded with things no commit can
    fix is how a page stops being read.

    The discriminator is EXISTENCE, not vocabulary.
    """
    assert not (M.ROOT / "data/definitely_not_written_by_anything.json").exists()
    assert M.scope_of(["scripts/screen_moat.py"],
                      ["data/definitely_not_written_by_anything.json"]) == "RUNTIME"
    # ...and a defect naming only present, tracked files is STILL a repo defect. A rule that
    # answered RUNTIME to everything would satisfy the assertion above by being useless.
    assert M.scope_of(["scripts/run_allocator.py", "scripts/run_cadence.py"], []) == "REPO"


# --------------------------------------------------------------- cited_evidence

def test_a_gitignored_path_in_the_message_is_untracked_evidence() -> None:
    tr, un = M.cited_evidence("panel-verdicts: NO product artifact exists "
                              "(data/panel_verdicts.jsonl) -- never produced")
    assert un == ["data/panel_verdicts.jsonl"]
    assert tr == []


def test_a_glob_names_its_directory_even_when_nothing_matches() -> None:
    """"No file matched" is the whole point of the defect, so the evidence has to be the DIRECTORY
    the glob points at -- otherwise every never-produced defect is unscoped exactly when it fires.
    """
    _, un = M.cited_evidence("cron-cycle: NO product artifact exists "
                             "(data/cro_ai_logs/2026*_????.log)")
    assert un and un[0].startswith("data/cro_ai_logs/")


def test_a_bare_basename_resolves_to_its_tracked_path() -> None:
    """Defect prose names artifacts the way a person would, not by full path."""
    tr, _ = M.cited_evidence("frontier-product: prospector_coverage.md 155h old (cad 30h)")
    assert tr == ["docs/research/prospector_coverage.md"]


def test_an_ambiguous_basename_is_dropped_rather_than_guessed() -> None:
    """Two tracked files sharing a name cannot settle which the sentence meant. Picking either
    would fabricate the evidence, and fabricated evidence is worse than none."""
    idx = M._basename_index()
    dupes = [b for b in ("__init__.py", "conftest.py") if b not in idx]
    assert dupes, "expected at least one genuinely ambiguous basename to be excluded"


def test_message_evidence_outranks_what_the_check_incidentally_read() -> None:
    """check_organs stats the TRACKED ORGAN_ARTIFACTS docs on its way to concluding an UNTRACKED
    log is missing. Scoping by the check's read-set alone marked all ten organ-never defects REPO;
    scoping by what the sentence asserts is missing puts them where they belong."""
    tr, un = M.cited_evidence(
        "frontier-en: no substantial log (data/cro_ai_logs/frontier_en_*.log, >= 1500b) AND no "
        "declared artifact written in 36.0h -- organ has never fired or always dies")
    assert M.scope_of(tr, un) == "RUNTIME"


# ------------------------------------------------------------ production ageing

def test_tracked_artifact_age_uses_the_worse_of_mtime_and_commit_time() -> None:
    """MTIME LIES ABOUT TRACKED FILES, ALWAYS IN THE FLATTERING DIRECTION. `git clone` stamps
    every file with the CLONE time, so a doc authored a week ago reads as hours old on a fresh
    machine -- measured at 131h reported against 155h real. A freshness gate that gets younger
    every time you clone the repo is not measuring production."""
    p = ROOT / "docs/research/prospector_coverage.md"
    if not p.exists():
        pytest.skip("artifact absent in this checkout")
    mtime_age = (M.NOW - p.stat().st_mtime) / 3600.0
    assert M._production_age_h(p) >= mtime_age - 1e-6


def test_untracked_artifact_age_stays_on_mtime() -> None:
    """Git knows nothing about them, so mtime is the only truth available and is the right one."""
    p = ROOT / "data" / "__scope_probe__.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{}", "utf-8")
    try:
        assert M._production_age_h(p) < 1.0
    finally:
        p.unlink(missing_ok=True)


# ----------------------------------------------------------------- integration

def test_every_defect_carries_a_scope_and_its_evidence() -> None:
    """The report's own contract: no defect may reach the principal unlabelled."""
    defects: list = []
    M._fenced(lambda d: d.append(("probe-runtime", "missing data/panel_verdicts.jsonl")),
              defects, "probe")
    assert len(defects) == 1
    did, _msg, scope, tracked, untracked = defects[0]
    assert did == "probe-runtime"
    assert scope == "RUNTIME"
    assert untracked == ["data/panel_verdicts.jsonl"]
    assert tracked == []


def test_a_check_that_raises_still_produces_a_scoped_defect() -> None:
    """The fence must not become a hole in the labelling. A blind checker is a defect, and a
    defect without provenance is the thing this module exists to prevent."""
    def boom(_d):
        raise RuntimeError("kaboom")

    defects: list = []
    M._fenced(boom, defects, "exploder")
    assert len(defects) == 1
    assert defects[0][0] == "sweep-broken-exploder"
    assert len(defects[0]) == 5, "the fence's own defect must be scoped like any other"


# ------------------------------------------- machine-local ratchets vs committed ones

def test_the_data_surface_high_water_mark_is_machine_local() -> None:
    """A RATCHET MUST LIVE WHERE THE THING IT MEASURES LIVES.

    `best_surface` counted `data/lake/bronze` directories and `data/*.jsonl` files -- both
    gitignored -- while its record sat in a git-TRACKED file. Every clone therefore measured a
    near-empty data/ against the VPS's 37 and filed `holdings-shrank` having dropped nothing;
    this checkout read 9. Same shape as the `n_snapshots` ratchet fixed the same day, same fix.
    """
    assert "data/" in str(M.HOLDINGS_LOCAL), "the surface ratchet must not be committed"
    assert "docs/" in str(M.HOLDINGS_RECORD), "the paid-target ratchet is genuinely institutional"


def test_the_committed_record_no_longer_carries_the_surface() -> None:
    """And it says WHERE it went, so the next reader does not helpfully restore it."""
    import json
    d = json.loads((ROOT / "docs/research/holdings_record.json").read_text("utf-8"))
    assert "best_surface" not in d
    assert "holdings_surface_local" in d.get("best_surface_moved_to", "")


def test_holdings_does_not_fire_on_a_checkout_with_no_local_record(tmp_path, monkeypatch) -> None:
    """The regression bar: absent a local record the ratchet SEEDS rather than accuses."""
    monkeypatch.setattr(M, "HOLDINGS_LOCAL", tmp_path / "surface.json")
    defects: list = []
    M.check_holdings_never_shrink(defects)
    assert not [d for d in defects if d[0] == "holdings-shrank"]


# ------------------------------------------------- ack storage follows ack scope (R0393)
#
# The scope above decided how a defect was REPORTED and never where its ack was STORED, so a
# REPO defect -- a property of a committed file, identically true in every checkout -- was
# disposed of in an untracked per-box registry. Acking it here left it firing on the VPS, where
# ">48h un-acked ESCALATES to the principal page" then paged him for a defect that already
# carried a full reasoned disposition somewhere he could not see. These pin the routing.


def _ack(until: str = "2099-01-01T00:00:00+00:00") -> dict:
    return {"reason": "a reason a reader can act on", "by": "test", "until": until}


@pytest.fixture
def registries(tmp_path, monkeypatch):
    repo, local = tmp_path / "repo.json", tmp_path / "local.json"
    monkeypatch.setattr(M, "ACKS_REPO", repo)
    monkeypatch.setattr(M, "ACKS", local)
    return repo, local


def _write(path: Path, payload: dict) -> None:
    import json
    path.write_text(json.dumps(payload), "utf-8")


def test_an_ack_in_either_registry_counts(registries) -> None:
    """The split governs WHERE a disposition is written, never whether it counts -- so landing it
    could not silently un-ack the 61 acks already on the desk."""
    repo, local = registries
    _write(repo, {"repo-defect": _ack()})
    _write(local, {"local-defect": _ack()})
    defects = [("repo-defect", "m", "REPO", [], []), ("local-defect", "m", "RUNTIME", [], []),
               ("neither", "m", "REPO", [], [])]
    live, acked, state = M.split_acked(defects)
    assert state == "known"
    assert {d[0] for d in acked} == {"repo-defect", "local-defect"}
    assert [d[0] for d in live] == ["neither"]


def test_tracked_wins_over_local_for_the_same_id(registries) -> None:
    """A local entry must not quietly extend or shorten a disposition the repo already records:
    the tracked copy is the one every checkout sees and a reviewer reads in the diff."""
    repo, local = registries
    _write(repo, {"d": dict(_ack(), reason="the committed reason")})
    _write(local, {"d": dict(_ack(), reason="a local override")})
    _, acked, _ = M.split_acked([("d", "m", "REPO", [], [])])
    assert acked == [("d", "the committed reason")]


def test_an_unparseable_registry_degrades_the_whole_view(registries) -> None:
    """Half-read is not known. Guessing "nothing is acked" writes a permanent false accusation;
    guessing "all acked" buries real work -- so the state must say it does not know."""
    repo, local = registries
    repo.write_text("{not json", "utf-8")
    _write(local, {"d": _ack()})
    _, acked, state = M.split_acked([("d", "m", "REPO", [], [])])
    assert state == "unknown"
    assert [a[0] for a in acked] == ["d"], "a readable ack still counts; only the STATE degrades"


def test_a_repo_defect_acked_only_locally_is_reported_as_misfiled(registries) -> None:
    """The defect R0393 names, in one assertion: the ack exists, the defect is REPO, and the ack
    cannot travel to the machine that is about to escalate it."""
    _, local = registries
    _write(local, {"d": _ack()})
    assert M.misfiled_acks([("d", "m", "REPO", [], [])]) == [("d", "REPO")]


def test_a_runtime_defect_acked_locally_is_correct(registries) -> None:
    """The other half, and the reason this is a split rather than a move: a RUNTIME defect's truth
    genuinely differs per machine, so a per-box ack is right and must not be nagged about."""
    _, local = registries
    _write(local, {"d": _ack()})
    assert M.misfiled_acks([("d", "m", "RUNTIME", [], [])]) == []


def test_unscoped_is_treated_as_repo_for_storage_too(registries) -> None:
    """Unknown provenance never becomes an excuse -- the same tie-break the report already uses."""
    _, local = registries
    _write(local, {"d": _ack()})
    assert M.misfiled_acks([("d", "m", "UNSCOPED", [], [])]) == [("d", "UNSCOPED")]


def test_an_ack_carried_by_the_tracked_registry_is_not_misfiled(registries) -> None:
    repo, local = registries
    _write(repo, {"d": _ack()})
    _write(local, {"d": _ack()})
    assert M.misfiled_acks([("d", "m", "REPO", [], [])]) == []


def test_an_expired_local_ack_is_not_misfiled(registries) -> None:
    """It is not an ack at all any more -- the defect is simply live, which the report already
    says. Counting it here would put work on the queue that is already on the queue."""
    _, local = registries
    _write(local, {"d": _ack(until="2000-01-01T00:00:00+00:00")})
    assert M.misfiled_acks([("d", "m", "REPO", [], [])]) == []


def test_misfiled_is_deduped_by_id(registries) -> None:
    """One check emits many defects under one id -- producer-cadence-stale fires five times in a
    normal run -- and there is only ever ONE ack to move. Reporting 17 where 12 are owed inflates
    a queue, which is the same class of error as hiding one."""
    _, local = registries
    _write(local, {"d": _ack()})
    dup = [("d", "m", "REPO", [], [])] * 5
    assert M.misfiled_acks(dup) == [("d", "REPO")]


def test_the_tracked_registry_is_actually_tracked() -> None:
    """The whole point is that it travels. A tracked FILENAME under a wholesale `data/*` ignore
    is still an untracked file -- the negation has to exist, or this fix is cosmetic."""
    import subprocess
    r = subprocess.run(["git", "check-ignore", "data/max_audit_acks_repo.json"],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 1, f"the repo ack registry is gitignored: {r.stdout.strip()}"
