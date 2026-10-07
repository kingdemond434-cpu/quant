"""The desk's state JSON is written LF on every box, and the seven desk-root CRLF copies are not dirty.

MEASURED 2026-10-06: seven desk-root JSON files showed as modified on every fresh checkout --
sync_marker, gateway_state, hunt11, mech_battery, mech_split, portfolio_projection and
regime_state. Each blob holds CRLF (the retired Dell hourly sync, 2026-08-17) and
desks/mt5/.gitattributes says `*.json text eol=lf`, so the checkout could never match the index.
All seven are release.py STATE_FILES paths (box state), so their content is never rewritten on
origin; an exact-path `-text` rule stores each byte-for-byte instead.

Nothing writes the desk-root paths any more. The live copies are written under data/ or reports/,
and every writer that is not sealed pins `newline="\\n"`, because `Path.write_text` and `open(...,
"w")` with no `newline` emit os.linesep -- CRLF on the Windows box. The gateway's own writer
(mt5desk/gateway.py save_state) is sealed, so its fix travels as a patch file and is not pinned here.
"""
from __future__ import annotations

import ast
import shutil
import subprocess
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
REPO = DESK.parent.parent

ROOT_STATE = ("sync_marker", "gateway_state", "hunt11", "mech_battery", "mech_split",
              "portfolio_projection", "regime_state")

#: writer module -> the artifact file name it writes.
WRITERS = {
    "research/hourly_cycle.py": "sync_marker.json",
    "research/regime_monitor.py": None,  # writes via the module constant STATE
    "research/run_hunt11.py": "hunt11.json",
    "run_hunt11.py": "hunt11.json",
    "mech_split.py": "mech_split.json",
    "research/portfolio_projection.py": "portfolio_projection.json",
    "mech_battery.py": "reports/mech_battery.json",
    "research/mech_battery.py": "reports/mech_battery.json",
    "side_channels/mech_battery.py": "reports/mech_battery.json",
}


def _writes(rel: str, name: str | None) -> list[ast.Call]:
    """Every text write of `name` (or of STATE, when name is None) in DESK/rel."""
    out = []
    for n in ast.walk(ast.parse((DESK / rel).read_text("utf-8"))):
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        if isinstance(f, ast.Attribute) and f.attr == "write_text":
            target = f.value
        elif isinstance(f, ast.Name) and f.id == "open" and n.args:
            target = n.args[0]
            if not (len(n.args) > 1 and isinstance(n.args[1], ast.Constant)
                    and "w" in str(n.args[1].value)):
                continue
        else:
            continue
        hit = any(
            (isinstance(c, ast.Constant) and name is not None and c.value == name)
            or (isinstance(c, ast.Name) and name is None and c.id == "STATE")
            for c in ast.walk(target))
        if hit:
            out.append(n)
    return out


@pytest.mark.parametrize("rel", sorted(WRITERS))
def test_every_writer_pins_lf(rel: str) -> None:
    writes = _writes(rel, WRITERS[rel])
    assert writes, f"{rel} no longer writes its artifact here -- find the new writer"
    for call in writes:
        kw = {k.arg: k.value for k in call.keywords}
        assert "newline" in kw, f"{rel}:{call.lineno}: write without newline= emits CRLF on Windows"
        assert isinstance(kw["newline"], ast.Constant) and kw["newline"].value == "\n"


def test_newline_lf_survives_a_windows_linesep(tmp_path: Path) -> None:
    """What the pinned keyword buys: the text layer never translates "\\n" when newline="\\n"."""
    p = tmp_path / "m.json"
    p.write_text('{\n "a": 1\n}', encoding="utf-8", newline="\n")
    assert b"\r" not in p.read_bytes()


def _git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True,
                          check=False).stdout


needs_git = pytest.mark.skipif(shutil.which("git") is None or not (REPO / ".git").exists(),
                               reason="not a git checkout")


@needs_git
@pytest.mark.parametrize("stem", ROOT_STATE)
def test_the_desk_root_copy_is_box_state_stored_as_is(stem: str) -> None:
    from libs.ops.release import is_state_path

    root = f"desks/mt5/{stem}.json"
    assert is_state_path(root), f"{root} left STATE_FILES: re-decide its attribute rule"
    assert f"{root}: text: unset" in _git("check-attr", "text", "--", root)


@needs_git
@pytest.mark.parametrize("stem", ("sync_marker", "gateway_state", "regime_state"))
def test_the_live_copy_under_data_stays_lf(stem: str) -> None:
    live = f"desks/mt5/data/{stem}.json"
    attrs = _git("check-attr", "text", "eol", "--", live)
    assert f"{live}: text: set" in attrs and f"{live}: eol: lf" in attrs
