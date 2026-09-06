"""The files the dashboard is computed from must be committable, or the desk cannot be seen.

MEASURED 2026-09-06, and it cost a day. `.gitignore` allowlisted `shadow_health.json` at line
142 and then re-excluded it at line 244 with `**/shadow_health.json`. Git applies the LAST
matching rule, so the allowlist did nothing. On the trading box PR #47 untracked the runtime
state, and from that moment the file was untracked AND ignored.

Every component then behaved perfectly. `sync_shadow_to_git.ps1` ran every fifteen minutes,
staged the file, and git silently dropped it; the script honestly logged "no change since last
sync" about a thousand times over eleven days. The dashboard read "box has not reported for
266.4h" while the file on disk was twenty-six minutes old and the desk was recording ticks and
completing its daily cycle. Nothing failed, nothing was reported, and the symptom pointed at the
one machine that was working.

Its siblings survived only by the accident of their negations sitting BELOW line 244 rather than
above it -- so this was never a considered rule, and nothing would have caught the next one.

THE TEST IS ON THE OUTCOME, not on the text of any rule: `git check-ignore` is asked, so however
the file is reorganised, the question answered here stays "can this be committed at all".
"""
from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

#: Everything `build_zentech_state.py` needs from the trading box. A file absent from this list is
#: not thereby unimportant -- it is unprotected, which is how shadow_health.json was lost.
DASHBOARD_INPUTS = (
    "desks/mt5/reports/shadow/shadow_health.json",
    "desks/mt5/reports/shadow/shadow_state.json",
    "desks/mt5/reports/shadow/scalp_shadow_state.json",
    "desks/mt5/reports/shadow/qquant_shadow_state.json",
    "desks/mt5/reports/shadow/external_shadow_state.json",
    "desks/mt5/data/account_state.json",
    "desks/mt5/data/sleeves.json",
)


@pytest.fixture(scope="module")
def sandbox() -> Path:
    """A throwaway repo carrying only this .gitignore.

    ASKED ON A CLEAN TREE ON PURPOSE. `git check-ignore` reports a TRACKED file as not ignored
    whatever the rules say, so asking inside this repo -- where these files are tracked -- would
    pass while the box, which had them untracked, was silently broken. The box's condition is the
    one that must be tested.
    """
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        (root / ".gitignore").write_text((ROOT / ".gitignore").read_text("utf-8"), "utf-8")
        for rel in DASHBOARD_INPUTS:
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("{}", "utf-8")
        yield root


@pytest.mark.parametrize("rel", DASHBOARD_INPUTS)
def test_the_dashboard_input_can_be_committed(sandbox: Path, rel: str) -> None:
    ignored = subprocess.run(["git", "check-ignore", "-q", rel],
                             cwd=sandbox, capture_output=True).returncode == 0
    if ignored:
        why = subprocess.run(["git", "check-ignore", "-v", rel],
                             cwd=sandbox, capture_output=True, text=True).stdout.strip()
        pytest.fail(
            f"{rel} is IGNORED, so the box can never publish it and the dashboard cannot see the "
            f"desk. Git applies the LAST matching rule, so an allowlist must sit BELOW every "
            f"exclusion that matches it.\n  winning rule: {why}"
        )


def test_no_gitignore_line_is_two_patterns_joined() -> None:
    """`**/sync_marker.jsonbackups/` was two rules that lost their newline, so NEITHER was in
    force -- sync_marker was not ignored and neither was backups/, which is how a backup
    directory gets committed. A joined line is silently valid, matches nothing, and reads as
    two working rules."""
    # THE SIGNATURE IS EXTENSION -> LETTERS -> SLASH, not merely "extension followed by a letter".
    # The naive form flagged every legitimate `.jsonl` rule, because `.json` is a prefix of it --
    # a fence that fires on correct lines gets deleted within a week, so it must discriminate.
    # `**/sync_marker.jsonbackups/` matches: a file extension, glued letters, then a directory
    # separator that can only have come from a second pattern.
    joined = re.compile(r"\.(?:jsonl|json|txt|ya?ml|parquet|db|log)[A-Za-z_][^/]*/")
    suspicious = [f"{n}: {s}"
                  for n, line in enumerate((ROOT / ".gitignore").read_text("utf-8").splitlines(), 1)
                  if (s := line.strip()) and not s.startswith("#") and joined.search(s)]
    assert not suspicious, "gitignore lines that look like two patterns joined:\n  " + \
        "\n  ".join(suspicious)
