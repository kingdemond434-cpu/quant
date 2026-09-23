"""THE ADOPTION MUST REACH THE BRANCH TIP EVERY HOUR, OR SAY LOUDLY WHY NOT.

WHAT BROKE, measured on the trading box 2026-09-23. `MT5-AdoptRelease` ran, took the git-writer
mutex, and ended every single hour at

    Adopt-Release exited 1 -- partial adoption; NOT sealing a tree that only half-matches
    the branch

with nothing else in the log. Underneath it, one hand run showed the texture:

    adopting 23270 path(s) in place...
    chunk add failed; retrying 2 path(s) individually
    skipped 2 pathspec(s) that match nothing on disk or in the index
    fatal: Unable to create 'C:/opt/quant/.git/index.lock': File exists.

and a bucket of that same diff showed WHY it took long enough to collide with everything else on
the box:

    total diff records 23270  ->  INTEL 22910, STATE 235, CODE 125

Twenty-two thousand nine hundred and ten of the paths were the miner discovery corpus, which
`MT5-IntelShip` lands hourly from its own data-only branch and which the verify step can never
let block a seal. Each one cost a `git cat-file` child process: the pass ran for FIVE HOURS (one
was still alive at 56s of CPU after five), the next hour's pass queued on the mutex behind it,
declined after nine minutes, and the box kept running code from before the fix.

THIS SUITE PINS THE FOUR PROPERTIES THAT MAKE THAT IMPOSSIBLE TO REPEAT:

  1. the discovery corpus is left to the organ that ships it, so the adoption's lock window is
     minutes rather than hours;
  2. a contended `.git/index.lock` is retried with a bounded backoff, and a genuinely STALE one
     (old, with no git alive) is removed WITH THE FACT RECORDED -- never one a live writer holds;
  3. a partial adoption always publishes the paths that remain, to
     `desks/mt5/reports/ADOPTION_STATE.json` and to the console log, so the next session does not
     have to re-run a slow adoption to learn what the last one already knew;
  4. the two scripts resolve each other, so a fix to the adoption can be tested against the live
     repository without first committing it into the tree the adoption is about to overwrite.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parents[1]
ADOPT = BASE / "scripts" / "Adopt-Release.ps1"
SEAL = BASE / "scripts" / "Adopt-And-Seal.ps1"

#: The prefixes the discovery corpus lives under, and the organ that delivers it.
SHIPPED_PREFIXES = ("data/intelligence/", "desks/mt5/data/intelligence/")

_POWERSHELL = shutil.which("powershell") or shutil.which("pwsh")
needs_powershell = pytest.mark.skipif(
    _POWERSHELL is None, reason="no PowerShell on this host; the source assertions still run")


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True,
                          capture_output=True, text=True).stdout


def _init(repo: Path) -> Path:
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    _git(repo, "config", "commit.gpgsign", "false")
    return repo


def _write(repo: Path, rel: str, text: str) -> None:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _run_adopt(repo: Path, extra: list[str] | None = None) -> subprocess.CompletedProcess[str]:
    assert _POWERSHELL is not None
    return subprocess.run(
        [_POWERSHELL, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
         "-File", str(ADOPT), "-RepoRoot", str(repo), "-Branch", "main", "-NoFetch",
         *(extra or [])],
        capture_output=True, text=True, check=False, timeout=600)


# --------------------------------------------------------------------- 1. the discovery corpus
def test_the_discovery_corpus_is_left_to_the_organ_that_ships_it() -> None:
    src = ADOPT.read_text(encoding="utf-8")
    for prefix in SHIPPED_PREFIXES:
        assert f'"{prefix}"' in src, f"{prefix} is not in $ShippedPrefixes"
    assert "Test-ShippedByOwnOrgan" in src
    # It must be checked BEFORE anything that spends a git process on the path: before the
    # untrack branch, before the keep rule, before Get-WorktreeBytes.
    loop = src.index("foreach ($rec in $records)")
    shipped_at = src.index("if (Test-ShippedByOwnOrgan $rel)", loop)
    assert shipped_at < src.index("Test-KeptByBox $rel", loop)
    assert shipped_at < src.index("Get-WorktreeBytes", loop)
    # And it must say so: a skipped corpus that is not counted is a silent gap.
    assert "MT5-IntelShip" in src


def test_the_skip_names_the_organ_that_actually_delivers_those_paths() -> None:
    """The claim "another organ lands this" is only true while that organ exists on a clock."""
    manifest = (BASE / "ops" / "box_tasks.manifest").read_text(encoding="utf-8")
    row = [ln for ln in manifest.splitlines() if 'name="MT5-IntelShip"' in ln]
    assert row, "MT5-IntelShip is not a declared box task; the skip would drop the corpus"
    ship = (BASE / "scripts" / "intel_ship_adopt.ps1").read_text(encoding="utf-8")
    for prefix in SHIPPED_PREFIXES:
        assert prefix.rstrip("/") in ship, f"the ship does not carry {prefix}"


@needs_powershell
def test_an_adoption_lands_code_and_leaves_the_discovery_corpus_alone(tmp_path: Path) -> None:
    origin = _init(tmp_path / "origin")
    _write(origin, "desks/mt5/research/engine.py", "v1\n")
    _write(origin, "data/intelligence/kimi/discoveries_1.json", '{"v": 1}\n')
    _git(origin, "add", "-A")
    _git(origin, "commit", "-q", "-m", "base")

    box = tmp_path / "box"
    subprocess.run(["git", "clone", "-q", str(origin), str(box)], check=True)
    _git(box, "config", "user.email", "t@t")
    _git(box, "config", "user.name", "t")
    _git(box, "config", "commit.gpgsign", "false")

    _write(origin, "desks/mt5/research/engine.py", "v2 -- the shipped fix\n")
    _write(origin, "data/intelligence/kimi/discoveries_1.json", '{"v": 2}\n')
    _git(origin, "add", "-A")
    _git(origin, "commit", "-q", "-m", "ship")
    _git(box, "fetch", "-q", str(origin), "main")

    r = _run_adopt(box)
    assert r.returncode == 0, r.stdout + r.stderr
    # CODE landed.
    assert (box / "desks/mt5/research/engine.py").read_text(encoding="utf-8").startswith("v2")
    # The corpus did NOT: it is the intel ship's, and the box keeps what it had until then.
    assert json.loads((box / "data/intelligence/kimi/discoveries_1.json")
                      .read_text(encoding="utf-8")) == {"v": 1}
    assert "left 1 discovery path(s) to MT5-IntelShip" in r.stdout
    # And the merge is recorded even though one tracked path still differs from the target,
    # because that path is not this script's to land.
    assert _git(box, "rev-parse", "HEAD") != _git(box, "rev-parse", "FETCH_HEAD")
    assert subprocess.run(["git", "-C", str(box), "merge-base", "--is-ancestor",
                           "FETCH_HEAD", "HEAD"], check=False).returncode == 0


# ----------------------------------------- 1b. the executable bit no write could ever land
def test_a_mode_only_difference_is_landed_through_the_index(tmp_path: Path) -> None:
    """THE ACTUAL FOUR-DAY BLOCKER, measured on the box 2026-09-23:

        ops/gates.sh                HEAD 100755  TARGET 100644  blob 50c2d034...  IDENTICAL
        scripts/recommendations.py  HEAD 100755  TARGET 100644  blob 1596a179...  IDENTICAL
        core.fileMode = false

    Same bytes, different executable bit. `git diff --name-only` reports the path; writing the
    content cannot change a mode; and `git add` under `core.fileMode=false` -- correct on
    Windows, where NTFS has no bit to read -- re-stages the mode already in the index. So every
    hourly pass wrote the right bytes, staged the wrong mode and refused, forever. This is the
    one class of drift that no retry could ever have cleared.
    """
    src = ADOPT.read_text(encoding="utf-8")
    assert "function Sync-IndexMode" in src
    assert "update-index" in src and "--chmod=$flag" in src
    # Only where the two actually disagree, and never on a gitlink or symlink.
    fn = src[src.index("function Sync-IndexMode"):src.index("# ---- THE STATE PREFIXES")] \
        if "# ---- THE STATE PREFIXES" in src else src[src.index("function Sync-IndexMode"):]
    assert "if ($targetMode -eq $indexMode) { return \"\" }" in fn
    assert "not this script's to rewrite" in fn


@needs_powershell
def test_an_adoption_converges_a_tree_that_differs_only_by_the_exec_bit(tmp_path: Path) -> None:
    origin = _init(tmp_path / "origin")
    _write(origin, "ops/gates.sh", "#!/bin/sh\necho gates\n")
    _write(origin, "desks/mt5/research/engine.py", "v1\n")
    _git(origin, "add", "-A")
    _git(origin, "commit", "-q", "-m", "base")

    box = tmp_path / "box"
    subprocess.run(["git", "clone", "-q", str(origin), str(box)], check=True)
    for k, v in (("user.email", "t@t"), ("user.name", "t"), ("commit.gpgsign", "false"),
                 ("core.fileMode", "false")):
        _git(box, "config", k, v)
    # The box's HEAD carries the executable bit; origin's does not. Content is untouched.
    _git(box, "update-index", "--chmod=+x", "--", "ops/gates.sh")
    _git(box, "commit", "-q", "-m", "box marked it executable")

    _write(origin, "desks/mt5/research/engine.py", "v2\n")
    _git(origin, "add", "-A")
    _git(origin, "commit", "-q", "-m", "ship")
    _git(box, "fetch", "-q", str(origin), "main")

    before = _git(box, "ls-tree", "HEAD", "--", "ops/gates.sh").split()[0]
    assert before == "100755"
    r = _run_adopt(box)
    assert r.returncode == 0, r.stdout + r.stderr
    after = _git(box, "ls-tree", "HEAD", "--", "ops/gates.sh").split()[0]
    assert after == "100644", "the mode-only drift survived the adoption, as it did for four days"
    assert "mode 100755 -> 100644" in r.stdout


# ------------------------------------------------------------------------ 2. the index.lock
def test_a_lost_lock_race_gets_a_repair_pass_before_the_adoption_refuses() -> None:
    """MEASURED 2026-09-23: thirteen paths failed to stage because a foreign writer held the
    index; two of them were code, so a perfectly good adoption refused and the box ran stale
    engines for another hour. Both staged by hand a minute later -- nothing was wrong with
    them. The repair pass is what turns that into a landed tree."""
    src = ADOPT.read_text(encoding="utf-8")
    assert "repair pass" in src
    assert "$repairPasses -lt 2" in src, "the repair is unbounded or absent"
    # It must run BEFORE the refusal, and the tree must be RE-MEASURED after it -- a repair that
    # is not re-verified is a claim, not a landing.
    repair = src.index("while ($drift.Count -gt 0 -and $repairPasses -lt 2)")
    refuse = src.index("REFUSING to record the merge: {0} CODE path(s)")
    assert repair < refuse
    tail = src[repair:refuse]
    assert 'diff", "--name-only", "HEAD", $target' in tail, "the repair never re-measures"
    assert "nothing could be re-landed" in tail, "a repair that cannot move anything must stop"


def test_a_path_that_fails_to_stage_is_reported_with_its_measured_reason() -> None:
    """"match nothing on disk or in the index" was printed for EVERY add failure, including the
    lost lock races that were the real outage. A wrong reason sends the next session hunting a
    phantom."""
    src = ADOPT.read_text(encoding="utf-8")
    assert "$script:LastGitError" in src, "git's own words are still thrown away"
    assert "lost the index.lock race" in src
    assert "matches nothing on disk or in the index" in src
    assert "ignored by .gitignore" in src


def test_a_contended_index_lock_is_retried_rather_than_fatal() -> None:
    src = ADOPT.read_text(encoding="utf-8")
    assert "index\\.lock" in src, "Invoke-Git does not recognise an index.lock failure"
    assert "$attempt -ge 5" in src, "the retry is unbounded or absent"
    assert "Clear-StaleIndexLock" in src
    # Bounded backoff, not a spin.
    assert "[Math]::Min($delayMs * 2, 16000)" in src


def test_a_stale_lock_is_removable_only_with_both_guards_and_the_fact_recorded() -> None:
    """Removing a lock a LIVE git holds corrupts that writer's index; refusing forever wedges
    the box. Both guards, and a sentence for every outcome including the ones it leaves alone."""
    src = ADOPT.read_text(encoding="utf-8")
    fn = src[src.index("function Clear-StaleIndexLock"):src.index("function Invoke-Git")]
    assert "$StaleIndexLockS" in fn, "no age guard"
    assert 'Get-Process -Name "git"' in fn, "no live-writer guard"
    assert "REMOVED a stale index.lock" in fn
    # The three non-removal outcomes each get their own sentence (L1.28a).
    assert "a live writer between two of its own git calls" in fn
    assert "could corrupt that writer's index" in fn
    assert "could not be removed" in fn


def test_the_stale_threshold_is_the_same_number_python_writers_use() -> None:
    """Two writers with different ideas of "stale" is one writer deleting the other's lock."""
    import sys
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from libs.ops import git_writer_lock as gwl
    src = ADOPT.read_text(encoding="utf-8")
    line = next(ln for ln in src.splitlines() if ln.startswith("$StaleIndexLockS"))
    assert int(line.split("=")[1].strip()) == int(gwl.DEFAULT_STALE_S)


# ------------------------------------------------------- 3. a partial adoption names its paths
@needs_powershell
def test_a_refusal_publishes_every_remaining_path_as_an_artifact(tmp_path: Path) -> None:
    origin = _init(tmp_path / "origin")
    _write(origin, "desks/mt5/research/engine.py", "v1\n")
    _git(origin, "add", "-A")
    _git(origin, "commit", "-q", "-m", "base")

    box = tmp_path / "box"
    subprocess.run(["git", "clone", "-q", str(origin), str(box)], check=True)
    _git(box, "config", "user.email", "t@t")
    _git(box, "config", "user.name", "t")
    _git(box, "config", "commit.gpgsign", "false")

    _write(origin, "desks/mt5/research/engine.py", "v2\n")
    _git(origin, "add", "-A")
    _git(origin, "commit", "-q", "-m", "ship")
    _git(box, "fetch", "-q", str(origin), "main")

    # A code path that cannot be written in place OR unlinked: the box's real failure was a
    # corrupt NTFS entry, and a directory standing where the file must go reproduces the class
    # (both Truncate and Delete refuse it) without needing a damaged filesystem.
    target = box / "desks/mt5/research/engine.py"
    target.unlink()
    target.mkdir()
    (target / "keep").write_text("in the way", encoding="utf-8")

    r = _run_adopt(box)
    assert r.returncode == 1, r.stdout
    art = json.loads((box / "desks/mt5/reports/ADOPTION_STATE.json")
                     .read_text(encoding="utf-8"))
    assert art["ok"] is False
    assert "desks/mt5/research/engine.py" in art["code_drift"]
    assert art["counts"]["code_drift"] == len(art["code_drift"])
    assert art["counts"]["repair_passes"] >= 1, "the refusal did not try to re-land anything"
    assert art["target"] and art["head"]
    # The console names them too, all of them -- not the first twenty.
    assert "REFUSING to record the merge" in r.stdout
    assert "desks/mt5/research/engine.py" in r.stdout
    assert "ADOPTION_STATE.json" in r.stdout


@needs_powershell
def test_a_clean_adoption_publishes_the_same_artifact_saying_so(tmp_path: Path) -> None:
    """An artifact written only on failure is a defect detector that cannot tell "healthy" from
    "never ran"."""
    origin = _init(tmp_path / "origin")
    _write(origin, "desks/mt5/research/engine.py", "v1\n")
    _git(origin, "add", "-A")
    _git(origin, "commit", "-q", "-m", "base")
    box = tmp_path / "box"
    subprocess.run(["git", "clone", "-q", str(origin), str(box)], check=True)
    _git(box, "config", "user.email", "t@t")
    _git(box, "config", "user.name", "t")
    _git(box, "config", "commit.gpgsign", "false")
    _write(origin, "desks/mt5/research/engine.py", "v2\n")
    _git(origin, "add", "-A")
    _git(origin, "commit", "-q", "-m", "ship")
    _git(box, "fetch", "-q", str(origin), "main")

    r = _run_adopt(box)
    assert r.returncode == 0, r.stdout + r.stderr
    art = json.loads((box / "desks/mt5/reports/ADOPTION_STATE.json")
                     .read_text(encoding="utf-8"))
    assert art["ok"] is True
    assert art["code_drift"] == []


def test_the_seal_script_keeps_the_console_and_names_the_paths_in_its_log() -> None:
    src = SEAL.read_text(encoding="utf-8")
    assert "adopt_release_console.log" in src, "the adoption console is still discarded"
    # STREAMED, not buffered to the end: a pass that hangs must still leave what it managed to
    # say. A five-hour hang was measured on 2026-09-23 and left nothing at all.
    assert "Tee-Object -FilePath $adoptConsole -Append" in src
    assert "$adoptOut = @(& powershell.exe" in src
    assert "$adoptExit = $LASTEXITCODE" in src
    # And the one-line status must be followed by the evidence.
    fail = src.index("partial adoption; NOT sealing")
    tail = src[fail:fail + 1200]
    assert "ADOPTION_STATE.json" in tail
    assert "Log (" in tail, "the paths are not written into adopt_and_seal.log"


# --------------------------------------------------------------- 4. the two scripts ship as a pair
def test_the_seal_script_resolves_the_adopt_script_beside_itself_first() -> None:
    src = SEAL.read_text(encoding="utf-8")
    assert '$adoptScript = Join-Path $PSScriptRoot "Adopt-Release.ps1"' in src
    # With the repository copy as the fallback, so an old install still works.
    assert 'Join-Path $desk "scripts\\Adopt-Release.ps1"' in src


def test_neither_script_uses_the_operations_this_desk_has_banned() -> None:
    """R0423, re-checked here because this change touched both files."""
    for path in (ADOPT, SEAL):
        src = path.read_text(encoding="utf-8")
        # Both files OPEN with a comment-based-help block that quotes the banned operations in
        # order to say it never uses them; a check that cannot tell prose from a statement fails
        # on the documentation of its own rule.
        if src.lstrip().startswith("<#"):
            src = src[src.index("#>") + 2:]
        code = "\n".join(ln for ln in src.splitlines() if not ln.strip().startswith("#"))
        assert "git stash" not in code, path.name
        assert "commit -a" not in code, path.name
        assert "add -A" not in code and "add --all ." not in code, path.name
