"""AN AUTO-FIXER THAT MAY EDIT CODE IS A MACHINE FOR HIDING DEFECTS.

The cheapest way to make any check stop firing is to change the check. A loop optimising for "no
defects" finds that before it finds a real repair, and it does so silently, daily, forever. That is
the single failure mode that makes autonomous remediation worse than none, so it is prevented
structurally -- an allowlist validated at import, containing only commands that PRODUCE artifacts.

The second property is verification. A remediation that ran is ATTEMPTED. Only re-running the check
and finding it silent yields FIXED, because otherwise this becomes the desk's own
"not measured = fine" failure applied to its own repairs -- and everything downstream trusts the
all-clear.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scripts.daily_max as D  # noqa: E402

# ------------------------------------------------------------------ the safety property

def test_no_remediation_can_edit_anything() -> None:
    """THE PROPERTY THAT MAKES THIS SAFE TO RUN UNATTENDED. Every entry must be a producer."""
    for key, (argv, _desc) in D.REMEDIATIONS.items():
        blob = " ".join(argv).lower()
        for verb in D._FORBIDDEN_VERBS:
            assert verb not in blob.split(), f"{key} contains editing verb {verb!r}: {blob}"
        assert argv[0] in ("python3", "bash"), f"{key} is not a script invocation"


def test_every_remediation_targets_a_script_that_exists() -> None:
    """A remediation pointing at a missing script fails daily and looks like a defect that will
    not close, which is the most expensive kind of noise."""
    for key, (argv, _d) in D.REMEDIATIONS.items():
        target = next((p for p in argv[1:] if p.endswith((".py", ".sh"))), None)
        assert target is not None, key
        assert (ROOT / target).exists(), f"{key} -> {target} does not exist"


def test_the_allowlist_validator_refuses_inline_code(monkeypatch) -> None:
    """THIS TEST FOUND A REAL HOLE. Validating argv[0] and the verb list still admitted
    `python3 -c "import os; os.remove(...)"` -- inline code carries no forbidden VERB and the
    interpreter is allowlisted, so arbitrary mutation walked through the guard built to stop
    exactly that. A remediation must now name a real script file inside the repo."""
    monkeypatch.setitem(D.REMEDIATIONS, "evil", (["python3", "-c", "import os; os.remove('x')"],
                                                 "delete something"))
    with pytest.raises(SystemExit, match=r"inline code"):
        D._validate_allowlist()


def test_the_allowlist_validator_refuses_a_missing_script(monkeypatch) -> None:
    monkeypatch.setitem(D.REMEDIATIONS, "ghost", (["python3", "scripts/nope.py"], "x"))
    with pytest.raises(SystemExit, match=r"does not name an existing script"):
        D._validate_allowlist()


def test_the_allowlist_validator_refuses_a_mutating_verb(monkeypatch) -> None:
    monkeypatch.setitem(D.REMEDIATIONS, "evil2", (["bash", "-e", "ops/commit_daily_max.sh"], "x"))
    with pytest.raises(SystemExit, match=r"inline code|forbidden verb"):
        D._validate_allowlist()


def test_the_commit_step_stages_only_tracked_docs() -> None:
    """A commit step with a wide net is how an automated loop pushes something nobody reviewed.
    `git add -u docs/` stages TRACKED changes under docs only -- never data/, never new files."""
    src = (ROOT / "ops/commit_daily_max.sh").read_text("utf-8")
    assert "git add -u docs/" in src
    assert "git add ." not in src and "git add -A" not in src
    assert "--force" not in src


# ------------------------------------------------------------------------ behaviour

def test_dry_run_attempts_nothing(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(D, "LEDGER", tmp_path / "l.json")
    monkeypatch.setattr(D, "REPORT", tmp_path / "r.json")
    monkeypatch.setattr(sys, "argv", ["daily_max.py", "--dry-run"])
    assert D.main() == 0
    rep = json.loads((tmp_path / "r.json").read_text("utf-8"))
    assert rep["dry_run"] is True
    assert rep["verified_fixed"] == [], "a dry run must never claim a fix"
    assert all("DRY RUN" in a for a in rep["remediations_attempted"])


def test_credit_blocked_defects_are_marked_human_not_retried(tmp_path, monkeypatch) -> None:
    """Retrying a credit shortage daily is how an autonomous loop becomes a noise source."""
    monkeypatch.setattr(D, "LEDGER", tmp_path / "l.json")
    monkeypatch.setattr(D, "REPORT", tmp_path / "r.json")
    monkeypatch.setattr(sys, "argv", ["daily_max.py", "--dry-run"])
    assert D.main() == 0
    rep = json.loads((tmp_path / "r.json").read_text("utf-8"))
    assert any("organ-never" in h for h in rep["needs_human"])


def test_an_artifact_with_no_producer_is_named_as_such() -> None:
    """FOUND BY THIS LOOP ON ITS FIRST REAL RUN. vendor-replacement originally mapped to
    info_class_map.py, which writes a DIFFERENT artifact. Grepping for a writer of
    data_universe_map.json returns readers only -- three scripts consume it and none produces it.
    A plausible-looking remediation would have buried that."""
    assert "vendor-replacement" not in D.REMEDIATIONS
    why = D.HUMAN_ONLY["vendor-replacement"]
    assert "NO PRODUCER" in (why[0] if isinstance(why, tuple) else why)


def test_repeated_failures_downgrade_rather_than_retry_forever() -> None:
    assert D.MAX_FAILED_ATTEMPTS >= 1


def test_the_report_disclaims_authority_over_code(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(D, "LEDGER", tmp_path / "l.json")
    monkeypatch.setattr(D, "REPORT", tmp_path / "r.json")
    monkeypatch.setattr(sys, "argv", ["daily_max.py", "--dry-run"])
    assert D.main() == 0
    rep = json.loads((tmp_path / "r.json").read_text("utf-8"))
    assert "NONE over code" in rep["authority"]


# ---------------------------------------------------------------------- the units

def test_the_timer_is_persistent() -> None:
    """A daily loop that can miss a day without saying so is not daily. Persistent=true fires a
    missed run on next boot instead of skipping it silently."""
    t = (ROOT / "ops/quant-daily-max.timer").read_text("utf-8")
    assert "Persistent=true" in t
    assert "OnCalendar=" in t


def test_the_service_runs_the_sweep_and_then_commits() -> None:
    s = (ROOT / "ops/quant-daily-max.service").read_text("utf-8")
    assert "daily_max.py" in s
    assert "commit_daily_max.sh" in s
    assert "ExecStartPost" in s, "a push failure must not mask a successful sweep"


def test_the_timeout_covers_two_full_sweeps() -> None:
    """It runs the audit twice -- once to find, once to verify -- plus every remediation."""
    s = (ROOT / "ops/quant-daily-max.service").read_text("utf-8")
    timeout = int(next(x for x in s.splitlines() if "TimeoutStartSec" in x).split("=")[1])
    assert timeout >= 3600


def test_every_remediation_key_is_one_some_check_can_actually_emit() -> None:
    """A REMEDIATION FOR A DEFECT NOTHING EMITS IS DEAD CONFIG THAT LOOKS LIKE COVERAGE.

    The allowlist already proves each entry points at a script that exists and cannot mutate
    anything. Nothing proved the other side: that the KEY it is filed under is one max_audit can
    ever produce. A typo -- `moat-clocks-unred`, `moat-survivors-unexploted` -- would sit in the
    allowlist forever looking like the defect was handled, and the loop would never fire it
    because the string never matches. Silence from an autonomous fixer is indistinguishable from
    nothing being wrong, which is exactly the comfort this desk keeps finding it has bought.

    Matching is by SUBSTRING because the loop itself matches that way: real defect messages carry
    suffixes (`production-missing: forensics`), so the key is a prefix of the live id.
    """
    src = Path("scripts/max_audit.py").read_text("utf-8")
    unmatched = [k for k in D.REMEDIATIONS if f'"{k}' not in src and f"'{k}" not in src
                 and k.split(":")[0] not in src]
    assert not unmatched, (
        "remediation keys no check in max_audit.py can emit -- dead config that reads as "
        f"coverage: {unmatched}")


def test_every_human_only_key_is_one_some_check_can_actually_emit() -> None:
    """Same argument, opposite list. A HUMAN_ONLY entry for a defect nothing emits does not stop
    the loop retrying anything -- it just records a decision about a defect that cannot occur."""
    src = Path("scripts/max_audit.py").read_text("utf-8")
    unmatched = [k for k in D.HUMAN_ONLY if f'"{k}' not in src and f"'{k}" not in src
                 and k.split(":")[0] not in src]
    assert not unmatched, f"HUMAN_ONLY keys no check can emit: {unmatched}"
