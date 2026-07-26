"""Quota-death catch-up decision rules (libs/ops/organ_catchup.py)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from libs.ops.organ_catchup import ORGANS, organ_owed, pick_organ

NOW = datetime(2026, 7, 24, 23, 30, tzinfo=UTC)
BRAIN = ORGANS[0]
DATAAXIS = ORGANS[1]


def _write(logdir: Path, name: str, size: int, age_s: float) -> Path:
    p = logdir / name
    p.write_bytes(b"x" * size)
    ts = (NOW - timedelta(seconds=age_s)).timestamp()
    import os

    os.utime(p, (ts, ts))
    return p


def test_stub_death_past_cooldown_is_owed(tmp_path: Path) -> None:
    _write(tmp_path, "dataaxis_20260724T1400.log", 51, 4 * 3600)
    assert organ_owed(DATAAXIS, tmp_path, NOW) is True


def test_success_log_today_clears_the_debt(tmp_path: Path) -> None:
    _write(tmp_path, "dataaxis_20260724T1400.log", 51, 4 * 3600)
    _write(tmp_path, "dataaxis_20260724T2330.log", 5000, 600)
    assert organ_owed(DATAAXIS, tmp_path, NOW) is False


def test_no_attempt_today_is_not_owed(tmp_path: Path) -> None:
    _write(tmp_path, "dataaxis_20260723T1400.log", 51, 30 * 3600)  # yesterday's stub
    assert organ_owed(DATAAXIS, tmp_path, NOW) is False


def test_recent_attempt_respects_cooldown(tmp_path: Path) -> None:
    _write(tmp_path, "dataaxis_20260724T2320.log", 51, 10 * 60)
    assert organ_owed(DATAAXIS, tmp_path, NOW) is False


def test_pick_prioritizes_brain_when_the_field_is_clear(tmp_path: Path) -> None:
    _write(tmp_path, "20260724_0845.log", 162, 10 * 3600)
    _write(tmp_path, "dataaxis_20260724T1400.log", 51, 9 * 3600)
    picked = pick_organ(tmp_path, NOW, lambda pat: False)
    assert picked is not None and picked.name == "brain"


def test_any_running_organ_blocks_every_retry(tmp_path: Path) -> None:
    """REGRESSION (2026-07-26): catch-up must never stack a retry on a live organ.

    The old rule skipped only the organ that was running and happily fired the NEXT owed one,
    so a busy field still produced a launch. Observed live: the quota window reset at 15:00,
    the frontier timer fired at 15:00:02, catch-up re-fired the brain at 15:00:05 and
    deep_sweep at 15:05 -- three max-effort organs in one just-reopened window. All organs
    draw the SAME pool, so a second launch does not add throughput, it turns two runs that
    would have completed into two stub deaths (the logs show paired deaths quoting one shared
    reset stamp). With dataaxis owed and the brain live, the answer must be "wait", not
    "start dataaxis instead".
    """
    _write(tmp_path, "20260724_0845.log", 162, 10 * 3600)
    _write(tmp_path, "dataaxis_20260724T1400.log", 51, 9 * 3600)
    assert organ_owed(DATAAXIS, tmp_path, NOW) is True, "precondition: dataaxis is owed"
    assert pick_organ(tmp_path, NOW, lambda pat: pat == "run_cro_ai.sh") is None
    # and the gate is not brain-specific -- any live organ holds the field
    assert pick_organ(tmp_path, NOW, lambda pat: pat == "run_frontier") is None


def test_fresh_artifact_counts_as_production_despite_stub_log(tmp_path):
    """REGRESSION (2026-07-25): claude writes deliverables via FILE TOOLS, so a SUCCESSFUL dig can
    leave only the shell's ~58-byte start/exit header in its log. Judging success by log size alone
    made max_audit report false 'never fired' defects and made catchup re-fire completed organs
    (frontier_en ran 3x on 07-25 for exactly this reason). A declared artifact written inside the
    interval must count as production."""
    from libs.ops.organ_catchup import OrganSpec, organ_owed

    logdir = tmp_path / "data" / "cro_ai_logs"
    logdir.mkdir(parents=True)
    stub = logdir / f"dataaxis_{NOW.strftime('%Y%m%dT%H%M')}.log"
    stub.write_text("=== dataaxis start ===\n")          # attempted, stub-sized log

    spec = OrganSpec("dataaxis", "ops/run_dataaxis_dig.sh", "dataaxis_*.log", 1500,
                     "run_dataaxis_dig.sh", artifacts=("docs/research/data_axis_watchlist.md",))

    # no artifact yet -> genuinely owed (past cooldown handled by the stub's fresh mtime being old
    # enough is not guaranteed, so assert only the artifact effect below)
    art = tmp_path / "docs" / "research"
    art.mkdir(parents=True)
    (art / "data_axis_watchlist.md").write_text("session note: 2 sources verified\n")

    assert organ_owed(spec, logdir, NOW) is False, (
        "a fresh declared artifact must count as production even when the log is a stub"
    )


def test_artifacts_are_exclusive() -> None:
    """No artifact may be declared by two organs.

    A shared artifact silently credits one organ for another's work: the frontier rotation writing
    prospector_coverage.md marked the prospector as produced, and two genuine quota deaths were
    never retried. Exclusivity is what makes the artifact signal mean anything, so it is fenced
    rather than left to review.
    """
    from libs.ops.organ_catchup import ORGANS
    seen: dict[str, str] = {}
    for spec in ORGANS:
        for art in spec.artifacts:
            assert art not in seen, (
                f"{art} is declared by both {seen[art]} and {spec.name} -- a shared artifact lets "
                "one organ's write mark the other as produced, so the dead one is never retried")
            seen[art] = spec.name


def test_log_patterns_match_what_the_shell_writes() -> None:
    """Every organ's log glob must match the name its runner actually builds.

    An organ whose pattern matches nothing is invisible to catch-up -- _window_logs comes back
    empty and organ_owed takes its `if not logs: return False` branch, so the organ can die every
    cycle forever and nothing notices. Runners build names with $(date ...), so the shell's LOG=
    assignment is compared with expansions collapsed to a wildcard.
    """
    import fnmatch
    import re
    from datetime import UTC, datetime
    from pathlib import Path

    from libs.ops.organ_catchup import ORGANS
    root = Path(__file__).resolve().parents[2]
    for spec in ORGANS:
        sh = root / spec.script
        if not sh.exists():
            continue
        m = re.search(r'LOG=\"?([^\"\n]+\.log)', sh.read_text("utf-8", errors="ignore"))
        if not m:
            continue
        # render $(date -u +FMT) for real -- a dummy placeholder cannot tell a %Y%m%d_%H%M
        # name from a %Y%m%dT%H%M one, which is precisely the mismatch class being fenced
        raw = re.sub(r"\$\(date[^+]*\+([^)]*)\)",
                     lambda d: datetime(2026, 1, 2, 3, 4, tzinfo=UTC).strftime(d.group(1)),
                     m.group(1))
        name = Path(re.sub(r"\$\([^)]*\)|\$\{[^}]*\}", "X", raw)).name
        assert fnmatch.fnmatch(name, spec.pattern), (
            f"{spec.name}: glob {spec.pattern!r} does not match {name!r} from {spec.script} -- "
            "an organ whose pattern never matches is invisible to catch-up and never retried")
