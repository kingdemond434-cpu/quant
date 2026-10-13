"""The two daily lanes: they must resume, they must not stack, and they must not lie when idle.

Two autonomous passes run twelve hours apart against this repository and the live box. What is
pinned here is the wiring and the failure behaviour -- what the agents actually DO is in
`docs/DESK_CYCLE_PROMPT.md`, which is prose on purpose and not something a test can judge.

THE FAILURE THIS DESK ALREADY PAID FOR, and the reason the launcher exits non-zero when its CLI
is missing: `MT5-ShadowSync` fired every fifteen minutes and returned exit 0 while publishing
nothing for thirty-three hours, because its skip branch exited 0 when the sources were absent.
Publishing nothing and publishing successfully were byte-identical to every watchdog. A scheduled
task that cannot do its job must say so in its exit code.
"""
from __future__ import annotations

import re
from pathlib import Path

DESK = Path(__file__).resolve().parent.parent
REPO = DESK.parent.parent
LAUNCHER = DESK / "scripts" / "Run-DeskCycle.ps1"
PROMPT = REPO / "docs" / "DESK_CYCLE_PROMPT.md"
INSTALLER = DESK / "scripts" / "Install-QuantWindows.ps1"


CRO_INSTALLER = DESK / "scripts" / "install_cro_cycle_tasks.ps1"
CRO = REPO / "docs" / "cro"


def _installer() -> str:
    return INSTALLER.read_text("utf-8")


def _cro_installer() -> str:
    return CRO_INSTALLER.read_text("utf-8")


# ------------------------------------------------------------------ the pair exists
def test_both_lanes_are_registered_by_one_owner() -> None:
    src = _cro_installer()
    for name in ("MT5-CycleNoon", "MT5-CycleMidnight"):
        assert f"Name = '{name}'" in src
    # Both entry points delegate instead of registering a second task shape.
    assert "install_cro_cycle_tasks.ps1" in _installer()
    absent_registrar = DESK / "scripts" / "register_absent_box_tasks.ps1"
    assert "install_cro_cycle_tasks.ps1" in absent_registrar.read_text("utf-8")


def test_each_lane_passes_its_own_lane_argument() -> None:
    """The lane selects a slot and a checkpoint file -- not a scope."""
    src = _cro_installer()
    assert "Lane = 'noon'" in src and "Lane = 'midnight'" in src
    assert "-Lane {1}" in src


# ------------------------------------------------------------------ the clock
def test_the_trigger_repeats_every_day_not_only_on_registration_day() -> None:
    """A -Once trigger with an eleven-hour repetition fired on the day it was registered and
    never again. A -Daily trigger carrying an hourly repetition fires every hour of every day."""
    src = _cro_installer()
    assert "New-ScheduledTaskTrigger -Daily" in src
    assert "$trigger.Repetition = " in src
    assert "-RepetitionInterval (New-TimeSpan -Hours 1)" in src
    assert "-RepetitionDuration (New-TimeSpan -Days 1)" in src


def test_the_lane_window_is_read_on_the_dublin_clock() -> None:
    """12:00 Irish time is the principal's slot; the box's zone and DST must not move it."""
    src = LAUNCHER.read_text("utf-8")
    assert '"GMT Standard Time"' in src
    assert "ConvertTimeFromUtc" in src
    assert re.search(r'\$WindowStart = if \(\$Lane -eq "noon"\) \{ 12 \} else \{ 0 \}', src)
    assert "$WindowEnd   = $WindowStart + 11" in src


def test_the_lanes_run_as_the_cli_login_account_headless() -> None:
    """Under SYSTEM neither CLI is logged in and the lane exits 3 every day."""
    src = _cro_installer()
    assert "-LogonType S4U" in src
    assert "-ExecutionTimeLimit (New-TimeSpan -Hours 10)" in src
    assert "-MultipleInstances IgnoreNew" in src


# ------------------------------------------------------------------ resumption
def test_a_second_instance_is_refused_by_the_scheduler_and_by_the_script() -> None:
    """Hourly repetition plus a slow pass is a stack unless something says no -- twice.

    The scheduler setting is not readable from the script, and the script's check is not visible
    in the task list, so both exist.
    """
    assert "-MultipleInstances IgnoreNew" in _cro_installer()
    src = LAUNCHER.read_text("utf-8")
    assert "ALREADY RUNNING" in src
    assert "Test-ProcessAlive" in src


def test_done_is_only_set_on_a_clean_exit() -> None:
    """Marking DONE on a bad exit silently converts an interrupted pass into a finished one, and
    the stages it never reached would wait a full day."""
    src = LAUNCHER.read_text("utf-8")
    assert 'status = "DONE"' in src
    # the DONE write must be inside the rc==0 branch, and a resumable write must exist for the rest
    assert re.search(r"if \(\$code -eq 0\)(.|\n)*?status = \"DONE\"", src)
    assert "left RESUMABLE" in src


def test_a_finished_lane_exits_immediately_instead_of_re_running() -> None:
    src = LAUNCHER.read_text("utf-8")
    assert "already DONE" in src


def test_an_unreadable_checkpoint_starts_fresh_rather_than_crashing() -> None:
    """A corrupt state file must not be able to stop the desk's daily pass forever."""
    src = LAUNCHER.read_text("utf-8")
    assert "catch { return $null }" in src


# ------------------------------------------------------------------ honest failure
def test_a_missing_agent_cli_exits_non_zero() -> None:
    """The MT5-ShadowSync defect, refused by design: a task that cannot do its job must not
    report success, or the task list stays green while nothing runs."""
    src = LAUNCHER.read_text("utf-8")
    assert "exit 3" in src
    assert "is not on PATH" in src
    assert re.search(r"exit 0\s*\n\s*\}\s*\n\s*if \(\$state\.status -eq \"RUNNING\" -and", src) \
        or "already DONE" in src          # the only legitimate early exit-0 is a finished lane


def test_a_missing_prompt_is_fatal() -> None:
    """Running an agent against this repository with no brief is worse than not running one."""
    src = LAUNCHER.read_text("utf-8")
    assert "refusing to run an agent with no brief" in src
    assert "exit 2" in src


def test_the_launcher_guards_native_stderr() -> None:
    """Same trap that killed Adopt-Release: agent progress on stderr must not terminate the pass."""
    src = LAUNCHER.read_text("utf-8")
    assert '$ErrorActionPreference = "Continue"' in src


# ------------------------------------------------------------------ the brief itself
def test_the_prompt_exists_and_states_the_laws() -> None:
    text = PROMPT.read_text("utf-8")
    for law in ("No gate, threshold, floor or law is ever loosened",
                "Never raise leverage or size by fiat",
                "Never resolve a merge conflict by picking a winner",
                "never leaves the box",
                "Targeted `git add` only",
                "MT5 universe mandate",
                "UNMEASURED is a verdict"):
        assert law in text, f"the prompt no longer states: {law}"


def test_the_prompt_names_both_lanes_and_the_checkpoint() -> None:
    text = PROMPT.read_text("utf-8")
    assert "NOON" in text and "MIDNIGHT" in text
    assert "Both lanes do everything below" in text
    assert "cycle_state_<lane>.json" in text
    assert "Do not redo them" in text


def test_the_prompt_requires_a_fixer_and_a_refusal_record() -> None:
    """The two things that make a pass compound instead of repeat."""
    text = PROMPT.read_text("utf-8")
    assert "Every repair ships with a fixer" in text
    assert "Refusals are output, not silence" in text
    assert "desk_lessons.jsonl" in text


def test_the_prompt_makes_the_checklist_a_floor() -> None:
    """A pass that only checks the board can only find what something else already found."""
    text = PROMPT.read_text("utf-8")
    assert "The board is the floor, not the ceiling" in text
    assert "Optimal, not merely working" in text


def test_the_prompt_closes_canonically() -> None:
    """Two lanes a day producing forks is how a desk ends up with several quants and no quant."""
    text = PROMPT.read_text("utf-8")
    assert "The canonical close" in text
    assert "Reconcile, never overwrite" in text
    assert "Seal alone" in text
    assert "running SHA == RELEASE.code_sha" in text


# ------------------------------------------------------------------ the CRO system
def test_the_three_cro_documents_are_in_the_repository() -> None:
    for name in ("CRO_CYCLE.md", "QUANT_CONSTITUTION.md", "QUANT_REFERENCE.md"):
        assert (CRO / name).is_file(), name
    cycle_text = (CRO / "CRO_CYCLE.md").read_text("utf-8")
    assert "THIS IS AN ACTION CYCLE, NOT A REPORTING CYCLE" in cycle_text


def test_the_brief_loads_cycle_first_constitution_second_reference_on_demand() -> None:
    src = LAUNCHER.read_text("utf-8")
    first = src.index("1. docs/cro/CRO_CYCLE.md")
    second = src.index("2. docs/cro/QUANT_CONSTITUTION.md")
    third = src.index("3. docs/cro/QUANT_REFERENCE.md")
    assert first < second < third
    assert "ON DEMAND ONLY" in src
    assert 'docs\\cro\\CRO_CYCLE.md' in src


def test_all_three_cro_documents_are_readable_before_the_agent_starts() -> None:
    """A missing reference used to be omitted from the launcher's preflight."""
    src = LAUNCHER.read_text("utf-8")
    preflight = src[src.index("$Documents = @("):src.index("# ---- THE CHECKPOINT")]
    for name in ("CRO_CYCLE.md", "QUANT_CONSTITUTION.md", "QUANT_REFERENCE.md"):
        assert name in preflight
    assert "Get-Content -LiteralPath $document.Path -Raw -Encoding UTF8" in preflight
    assert "Get-FileHash -LiteralPath $document.Path -Algorithm SHA256" in preflight
    assert src.index("$Documents = @(") < src.index("controller_checkpoint.py claim")
    assert "Verified CRO documents (readable before agent launch" in src


def test_one_controller_at_a_time_through_the_canonical_lease() -> None:
    src = LAUNCHER.read_text("utf-8")
    assert "controller_checkpoint.py claim" in src
    assert "controller_checkpoint.py release" in src
    assert "exit 5" in src


def test_the_next_lane_gets_the_previous_lanes_work_to_verify() -> None:
    src = LAUNCHER.read_text("utf-8")
    assert "$OtherStateFile" in src and "work_items" in src
    assert "cro_cycle_ledger.jsonl" in src


def test_the_agents_run_headless_without_a_blanket_permission_bypass() -> None:
    src = LAUNCHER.read_text("utf-8")
    assert '"-p"' in src and '"exec", "--full-auto"' in src
    assert "dangerously" not in src
    assert '"Bash(git push --force:*)"' in src


def test_a_fresh_pass_starts_only_at_the_slot_later_firings_only_resume() -> None:
    """Once a day at 12:00 (Claude) / 00:00 (Codex) Dublin; the hourly firings only resume."""
    src = LAUNCHER.read_text("utf-8")
    assert "$DublinNow.Hour -ne $WindowStart" in src
    assert "$unfinishedToday" in src


def test_every_pass_runs_the_tier1_breadth_review() -> None:
    cycle_text = (CRO / "CRO_CYCLE.md").read_text("utf-8")
    step = cycle_text[cycle_text.index("## STEP 4B"):cycle_text.index("## STEP 5")]
    for needle in (
        "What tier is the quant today?", "maxed out", "Never assume the machinery is at its peak",
        "Never cut mining", "TIER1_BREADTH_REVIEW.json", "k_eff", "Asian",
    ):
        assert needle in step, needle
    assert "6b. **Tier verdict" in cycle_text
    assert "EVERY PASS IS THE LAST CHANCE" in cycle_text
    assert "GET PAST TECHNICAL BLOCKS ALONE" in cycle_text
    assert "is NOT a technical error" in cycle_text
    assert "NEVER ASK THE PRINCIPAL" in cycle_text
    assert "NEVER JUST NOTICE" in cycle_text
    for needle in ("is MISSED", "measured ceiling", "a fix commit", "an after-metric",
                   "the previous pass left unclosed FIRST"):
        assert needle in cycle_text, needle
    assert "`gaps_named_not_closed` = 0" in step
    assert "`gaps_named` and `gaps_closed` in the cycle ledger row" in step
    for n, duty in enumerate((
        "Read desktop over git", "Tier verdict", "Judging throughput to maximum",
        "Permanent backlog guard", "Same-day certificate and clock",
        "Conversions per stage to maximum", "Dataset hunting at world scale",
        "Hypothesis volume", "Breadth of the book", "Machinery gaps to tier-1",
        "Fully wired or it does not count", "No forced or fake work",
        "Every item fully completed this pass",
        "Every producer maximally broad, unknown-unknowns mined",
        "Judging rate on target", "UNKNOWN verdicts by cause", "Box state is fresh in git",
        "No unfed datasets", "Paid-substitute coverage", "Cross-culture orthogonality",
        "No live code drift", "Decay and markout ran", "Confident kills per day",
        "Credential coverage", "Desktop pass-2 queue age", "Six-event trend",
        "Committee health per specialist", "Global coverage tensor",
        "Deep-forest never-attempted = 0", "Stranded ingestion = 0", "Silent organs = 0",
        "No empty risk clusters", "Source ROI", "Backpressure", "GitHub resident miner",
        "QuantConnect, WorldQuant and fund civilizations",
        "Institutional coverage per jurisdiction", "Judge efficiency",
        "Effective breadth, not saturation", "Timeframe and session breadth",
        "Nothing is a museum", "Ontology never closed", "Allocator integrity", "Self-evolution",
    ), start=1):
        assert f"| D{n} | **{duty}** |" in step, duty
    for row in ("Datasets in use", "Wasted verdicts", "Unjudged backlog", "Effective breadth",
                "Cert to forward", "Deep-forest vectors", "Judged", "Live"):
        assert f"| {row} |" in step, row
    assert "STEP 4B" in LAUNCHER.read_text("utf-8")
    assert "D15-D44" in LAUNCHER.read_text("utf-8")
    assert "check_cro_duties.py" in LAUNCHER.read_text("utf-8")
    assert "--review" in LAUNCHER.read_text("utf-8")


# ------------------------------------------------------------------ no silent skips
def _claude_args(src: str) -> str:
    start = src.index('if ($agentName -eq "claude") {')
    return src[start:src.index('} elseif ($agentName -eq "codex")', start)]


def test_the_claude_lane_speaks_stream_json_and_records_every_refusal() -> None:
    """In -p mode a refused tool is skipped with no record. stream-json is the only output that
    names the refusals, and the recorder turns each one into an UNMEASURED = MISSED row."""
    src = LAUNCHER.read_text("utf-8")
    args = _claude_args(src)
    assert '"--output-format", "stream-json", "--verbose"' in args
    assert '"--output-format", "text"' not in src
    assert "scripts\\record_agent_denials.py --stream $Stream --ledger $Ledger" in src
    assert "--review $Review" in src and "--started-at" in src
    assert "permission_denials = $deniedCount" in src
    # The stream is teed to its own file; the recorder puts the result text back in the log.
    assert "Add-Content -LiteralPath $Stream -Value $text -Encoding UTF8" in src
    assert (REPO / "scripts" / "record_agent_denials.py").is_file()


def test_the_lane_widening_is_read_only_and_from_the_one_domain_file() -> None:
    src = LAUNCHER.read_text("utf-8")
    args = _claude_args(src)
    assert 'Join-Path $RepoRoot "ops\\agent_webfetch_domains.json"' in src
    assert ") + $webFetchRules + @(" in args
    # No host is hard-coded here: the data file is the one list.
    assert "go.kr" not in src and "census.gov" not in src
    for rule in ('"Bash(ls:*)"', '"Bash(pwd)"', '"Bash(date)"', '"Bash(wc:*)"'):
        assert rule in args
    allowed = args[args.index('"--allowedTools"'):args.index('"--disallowedTools"')]
    allowed = "\n".join(ln for ln in allowed.splitlines() if not ln.strip().startswith("#"))
    for forbidden in ("bypass", "dangerously", "Bash(git push:*)", "Bash(git push --", "rm ",
                      "Remove-Item", "secrets", "Bash(*)", "Bash(powershell", "Bash(cmd"):
        assert forbidden not in allowed, forbidden
    assert '"Read(data/secrets/**)"' in args
