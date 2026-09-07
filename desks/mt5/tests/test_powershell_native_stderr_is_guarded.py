"""A native command's stderr must never terminate a PowerShell script that redirects it.

THE TRAP, WHICH THIS DESK HAS NOW HIT TWICE. PowerShell turns every stderr LINE from an external
program into an ErrorRecord. Under `$ErrorActionPreference = "Stop"` the first one is TERMINATING.
So `& git ... 2>&1` inside a `Stop` script aborts on output that is not an error at all:

    git.exe : From https://github.com/<owner>/<repo>
    At Adopt-Release.ps1:196 char:9 ... NativeCommandError

That is a SUCCESSFUL fetch reporting what it fetched. It killed `Adopt-Release.ps1` on its first
real run, before a single file had been adopted.

`sync_shadow_to_git.ps1` already carried the correct guard, with a comment explaining it, sixty
lines above a second call that did not have it -- and that unguarded call is the untracked-file
PROBE, which deliberately makes `git merge` fail so it can read the file list out of the failure
text. Stderr there is the load-bearing result, so the pass died exactly when the probe worked.

THE RULE. Exit code is the truth for a native command. Any script that both sets `Stop` and
merges a native command's stderr must relax the preference around that call and restore it after,
checking `$LASTEXITCODE` instead.

A `2>&1` inside a STRING is not a redirection -- `Install-QuantWindows.ps1` builds
`cmd.exe /c "... >> log 2>&1"` as a scheduled-task argument, where the redirect is cmd's and
PowerShell never sees it. Those are excluded, or the fence would demand a guard around a quoted
character sequence.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parent.parent
REPO = DESK.parent.parent

#: `& <native> ... 2>&1` -- an ampersand-invoked command whose streams are merged.
_NATIVE_REDIRECT = re.compile(r"^\s*(?:\$\w+\s*=\s*)?@?\(?\s*&\s*[^|\r\n]*?2>&1")
_STOP = re.compile(r'\$ErrorActionPreference\s*=\s*"Stop"')
_RELAX = re.compile(r'\$ErrorActionPreference\s*=\s*"Continue"')


def _scripts() -> list[Path]:
    return sorted(
        p for p in list((DESK / "scripts").glob("*.ps1")) + list((REPO / "ops").glob("*.ps1"))
        if p.is_file()
    )


def _in_string_literal(line: str) -> bool:
    """True when the `2>&1` sits inside a quoted string rather than being a real redirection."""
    idx = line.find("2>&1")
    if idx < 0:
        return False
    before = line[:idx]
    # A backtick-escaped quote is still a quote character for this purpose; counting both kinds
    # is enough to tell "inside a literal" from "a bare redirection operator".
    return (before.count('"') - before.count('`"')) % 2 == 1 or before.count("'") % 2 == 1


def _unguarded(path: Path) -> list[tuple[int, str]]:
    text = path.read_text("utf-8", errors="replace")
    if not _STOP.search(text):
        return []
    lines = text.splitlines()
    out: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        if "2>&1" not in line or _in_string_literal(line):
            continue
        if not _NATIVE_REDIRECT.search(line):
            continue
        # Guarded when the preference is relaxed within the preceding few lines -- the
        # `$prev = ...; $ErrorActionPreference = "Continue"; try { ... }` shape both fixes use.
        window = "\n".join(lines[max(0, i - 8):i])
        if not _RELAX.search(window):
            out.append((i + 1, line.strip()))
    return out


@pytest.mark.parametrize("script", _scripts(), ids=lambda p: p.name)
def test_no_unguarded_native_stderr_redirect(script: Path) -> None:
    offenders = _unguarded(script)
    assert not offenders, (
        f"{script.name} sets ErrorActionPreference=Stop and merges a native command's stderr "
        f"without relaxing it: {offenders}. PowerShell makes each stderr line an ErrorRecord and "
        "Stop makes the first one terminating, so the script dies on ordinary progress output. "
        'Wrap the call: $prev = $ErrorActionPreference; $ErrorActionPreference = "Continue"; '
        "try { ... } finally { $ErrorActionPreference = $prev }  -- and check $LASTEXITCODE."
    )


def test_the_fence_finds_something_to_check() -> None:
    """Guard against the suite passing because the glob or the pattern matched nothing."""
    scripts = _scripts()
    assert len(scripts) >= 5
    assert any(_STOP.search(p.read_text("utf-8", errors="replace")) for p in scripts)


def test_a_redirect_inside_a_cmd_argument_string_is_not_flagged() -> None:
    """`Install-QuantWindows.ps1` builds cmd.exe task arguments containing `>> log 2>&1`.

    That redirect belongs to cmd, not PowerShell, and demanding a guard around a quoted character
    sequence would be a fence nobody could satisfy.
    """
    line = '        $cmd = "/d /s /c `"`"$Python`" `"$script`" >> `"$log`" 2>&1`""'
    assert _in_string_literal(line)


def test_the_two_repaired_call_sites_stay_guarded() -> None:
    """Pinned by name: both were found the hard way, one of them on a live box."""
    for name, rel in (("Adopt-Release.ps1", DESK / "scripts" / "Adopt-Release.ps1"),
                      ("sync_shadow_to_git.ps1", DESK / "scripts" / "sync_shadow_to_git.ps1")):
        assert not _unguarded(rel), f"{name} regressed to an unguarded native stderr redirect"
