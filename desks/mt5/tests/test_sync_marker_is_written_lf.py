"""The cycle marker is written LF on every box, and the desk-root CRLF copy is not dirty.

MEASURED 2026-10-06: `desks/mt5/sync_marker.json` showed as modified on every fresh checkout.
Its blob holds CRLF (fd327ca89, 2026-08-17) and desks/mt5/.gitattributes says `*.json text
eol=lf`, so the checkout could never match the index. It is a release.py STATE_FILES path (box
state), so its content is never rewritten on origin; `-text` on that exact path stores it
byte-for-byte instead.

The one writer of the live marker is `hourly_cycle.main` (data/sync_marker.json). It dumps with
`indent=1`, and `Path.write_text` with no `newline` emits os.linesep -- CRLF on the Windows box.
`newline="\\n"` pins LF. sync_to_vps.ps1 only Copy-Items the file (bytes preserved) and
push_to_vps.py only stages it, so neither writes it.
"""
from __future__ import annotations

import ast
import shutil
import subprocess
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
REPO = DESK.parent.parent
SRC = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")


def _marker_writes() -> list[ast.Call]:
    """Every `<...sync_marker.json...>.write_text(...)` call in hourly_cycle.py."""
    out = []
    for n in ast.walk(ast.parse(SRC)):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr in {"write_text", "write_bytes", "open"}
                and any(isinstance(c, ast.Constant) and c.value == "sync_marker.json"
                        for c in ast.walk(n.func.value))):
            out.append(n)
    return out


def test_the_marker_writer_pins_lf() -> None:
    writes = _marker_writes()
    assert writes, "hourly_cycle no longer writes sync_marker.json -- find the new writer"
    for call in writes:
        if call.func.attr == "write_bytes":  # type: ignore[union-attr]
            continue
        kw = {k.arg: k.value for k in call.keywords}
        assert "newline" in kw, f"line {call.lineno}: write without newline= emits CRLF on Windows"
        assert isinstance(kw["newline"], ast.Constant) and kw["newline"].value == "\n"


def test_newline_lf_survives_a_windows_linesep(tmp_path: Path) -> None:
    """What the pinned keyword buys: the text layer never translates "\\n" when newline="\\n"."""
    p = tmp_path / "m.json"
    p.write_text('{\n "a": 1\n}', encoding="utf-8", newline="\n")
    assert b"\r" not in p.read_bytes()


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True,
                          check=False)


@pytest.mark.skipif(shutil.which("git") is None or not (REPO / ".git").exists(),
                    reason="not a git checkout")
def test_the_desk_root_marker_is_stored_as_is_and_the_live_marker_stays_lf() -> None:
    attrs = _git("check-attr", "text", "eol", "--", "desks/mt5/sync_marker.json",
                 "desks/mt5/data/sync_marker.json").stdout
    assert "desks/mt5/sync_marker.json: text: unset" in attrs
    assert "desks/mt5/data/sync_marker.json: text: set" in attrs
    assert "desks/mt5/data/sync_marker.json: eol: lf" in attrs
