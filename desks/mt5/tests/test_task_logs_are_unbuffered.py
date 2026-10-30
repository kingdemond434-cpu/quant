"""EVERY TASK THAT REDIRECTS PYTHON TO A LOG RUNS IT UNBUFFERED (fence, 2026-10-29).

A redirected Python block-buffers stdout, so its log shows nothing until the process exits and
nothing at all if it is killed. `MT5-IndependenceIntake` ran 100+ minutes on a 600 s budget and
its log's last line was the PREVIOUS pass's: a hung run and a working one read the same. The
same defect was repaired once on the box by `unbuffer_tasks.ps1`, and came back every time an
installer re-registered its task without `-u`. So this is the class's fence: any launcher in the
repo that runs Python with its output redirected to a file must pass `-u` (or set
PYTHONUNBUFFERED) -- on the line, through a shared args variable that carries `-u`, or once for
the whole file.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_DESK), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
#: Where launchers and task installers live. `_retired` and docs are history, not launchers.
_DIRS = ("desks/mt5/scripts", "desks/mt5/recorders", "ops", "scripts", "deploy")
_EXTS = (".ps1", ".cmd", ".bat")
#: A Python interpreter token: a python(.exe) path, the `py -3` launcher, or a variable that
#: holds one ($Python, $py, %PY%, %PYTHON%).
_PY = re.compile(r'(python(?:w)?(?:3)?(?:\.exe)?"?|\bpy(?:\.exe)?\s+-3'
                 r'|\$python\b|\$py\b|%py%|%python%)', re.IGNORECASE)
#: Output to a file: cmd/sh `>>`/`>` (not `>nul`, not `2>&1` alone), PowerShell `*>>`, Out-File.
_REDIRECT = re.compile(r'(\*?>>|(?<=\s)1?>(?=\s)(?!\s*nul\b)|\bOut-File\b|\bTee-Object\b)',
                       re.IGNORECASE)
_UNBUFFERED = re.compile(r'(\s-u\b|PYTHONUNBUFFERED)')


def _launchers() -> list[Path]:
    out: list[Path] = []
    for d in _DIRS:
        base = _ROOT / d
        if not base.is_dir():
            continue
        out += [p for p in base.rglob("*") if p.suffix.lower() in _EXTS
                and "_retired" not in p.parts]
    return sorted(out)


def _args_vars_with_u(text: str) -> set[str]:
    """Shared args variables (`$pyArgs`, `%PYARGS%`) every assignment of which carries -u."""
    names: dict[str, list[bool]] = {}
    for m in re.finditer(r'^\s*(?:set\s+")?\$?(\w*args)\s*=\s*(.*)$', text,
                         re.IGNORECASE | re.MULTILINE):
        names.setdefault(m.group(1).lower(), []).append(bool(re.search(r'-u\b', m.group(2))))
    return {n for n, flags in names.items() if flags and all(flags)}


def offenders() -> list[str]:
    bad: list[str] = []
    for path in _launchers():
        try:
            text = path.read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            continue
        if re.search(r'PYTHONUNBUFFERED\s*=\s*"?1', text, re.IGNORECASE):
            continue                                   # set once for the whole file
        with_u = _args_vars_with_u(text)
        for no, line in enumerate(text.splitlines(), 1):
            code = line.strip()
            if not code or code.startswith(("#", "rem ", "REM ", "::")):
                continue
            if not (_PY.search(code) and _REDIRECT.search(code)):
                continue
            if "powershell" in code.lower() and ".ps1" in code.lower():
                continue                               # a PowerShell task, not a Python one
            if _UNBUFFERED.search(code):
                continue
            used = {m.group(1).lower() for m in re.finditer(r'[$%](\w*args)\b%?', code,
                                                            re.IGNORECASE)}
            if used & with_u:
                continue
            bad.append(f"{path.relative_to(_ROOT).as_posix()}:{no}: {code[:140]}")
    return bad


def test_every_redirected_python_launch_is_unbuffered() -> None:
    bad = offenders()
    assert not bad, ("Python launched with stdout redirected to a log but without -u or "
                     "PYTHONUNBUFFERED -- its log stays empty until exit:\n  " + "\n  ".join(bad))


def test_the_fence_catches_the_shape_it_exists_for(tmp_path: Path) -> None:
    """The exact action that hid a 100-minute hang must read as an offender."""
    line = ('''('/d /s /c ""{0}" -W ignore "{1}" --once --budget-s 600 >> "{2}" 2>&1"' '''
            "-f $Python, $Organ, $Log)")
    assert _PY.search(line) and _REDIRECT.search(line) and not _UNBUFFERED.search(line)
    fixed = line.replace("-W ignore", "-u -W ignore")
    assert _UNBUFFERED.search(fixed)
    assert _PY.search('py -3 research\\deepening_worker.py --limit 25 >> {1} 2>&1')
    assert not _REDIRECT.search("timeout /t 60 /nobreak >nul")


def test_the_box_repair_sweep_knows_both_launcher_spellings() -> None:
    """`unbuffer_tasks.ps1` repairs tasks already registered on the box; it must match the
    `py -3` launcher as well as python.exe, or it walks past the tasks this fence found."""
    src = (_ROOT / "desks/mt5/scripts/unbuffer_tasks.ps1").read_text("utf-8")
    assert "py(?:\\.exe)?" in src and "-3" in src
