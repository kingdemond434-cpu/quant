"""CROSS-PLATFORM VENV RESOLUTION -- 8 statements, and every spawned organ depends on it.

The desk was authored on Windows (`.venv/Scripts/python.exe`) and migrated to a Linux VPS
(`.venv/bin/python`) on 2026-07-12. Interpreter paths must resolve on BOTH, because the same code
runs on the laptop and the server -- and a wrong path here does not raise here. It raises in the
SPAWNED process, as a FileNotFoundError from `subprocess`, at whatever hour the organ was
scheduled, and the traceback names the caller rather than this function.

Small enough that testing it looks unnecessary, which is exactly why it was never tested. Both
branches are asserted with the OS forced, so the Windows path is covered from Linux -- otherwise
half this file is unexercised on every machine that runs the suite, and the half that is unexercised
is the one nobody would notice breaking.

HOW THE OS IS FORCED, and why not the obvious way: the obvious way is
`monkeypatch.setattr(os, "name", "nt")`, and it does not merely fail -- it takes pytest down with an
INTERNALERROR. `pathlib.Path.__new__` dispatches on `os.name`, so while the patch is live EVERY
`Path(...)` anywhere in the process returns a `WindowsPath`, which refuses to instantiate on Linux.
pytest builds paths inside `pytest_runtest_makereport`, which runs BEFORE function-scoped
monkeypatch teardown, so the first assertion failure under the patch crashes the runner instead of
reporting. Patching the *module's* `os` reference (`platform_paths.os`) confines the lie to the one
namespace under test and leaves `pathlib` looking at the real OS.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from libs.ops import platform_paths
from libs.ops.platform_paths import venv_python

_ROOT = Path("/srv/quant")


def _force_os(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    """Make `platform_paths` believe it is on `name` without lying to `pathlib`."""
    monkeypatch.setattr(platform_paths, "os", SimpleNamespace(name=name))


def test_POSIX_resolves_to_the_bin_interpreter(monkeypatch: pytest.MonkeyPatch) -> None:
    _force_os(monkeypatch, "posix")
    assert venv_python(_ROOT) == str(_ROOT / ".venv" / "bin" / "python")


def test_WINDOWS_resolves_to_the_Scripts_interpreter(monkeypatch: pytest.MonkeyPatch) -> None:
    """Covered from Linux by forcing the module's OS. Without this the Windows branch is dead code
    on every machine that runs the suite, and it is the branch the laptop depends on."""
    _force_os(monkeypatch, "nt")
    assert venv_python(_ROOT) == str(_ROOT / ".venv" / "Scripts" / "python.exe")


def test_WINDOWLESS_picks_pythonw_ONLY_on_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    """`pythonw.exe` is what stops a console flashing on every detached spawn. On POSIX there is no
    windowless variant, so asking for one must return plain python rather than a path that does not
    exist -- a silent downgrade is correct here, an error would break every POSIX caller that passes
    the flag unconditionally."""
    _force_os(monkeypatch, "nt")
    assert venv_python(_ROOT, windowless=True).endswith("pythonw.exe")

    _force_os(monkeypatch, "posix")
    assert venv_python(_ROOT, windowless=True) == venv_python(_ROOT, windowless=False)


def test_the_path_is_ABSOLUTE_when_the_root_is(monkeypatch: pytest.MonkeyPatch) -> None:
    """Spawned organs inherit whatever cwd the scheduler happened to set. A relative interpreter
    path resolves against that -- which is how a cron job finds no python at 03:00 and nothing
    else."""
    _force_os(monkeypatch, "posix")
    assert Path(venv_python(_ROOT)).is_absolute()


def test_the_SEPARATOR_is_the_TARGET_platforms_not_the_hosts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The honest limit of forcing the OS from Linux: `root / ".venv"` uses the *host's* pathlib
    flavour, so the Windows branch yields forward slashes here. That is fine -- Windows accepts
    them, and the part that actually matters (`Scripts/python.exe` vs `bin/python`) is what this
    file pins. Asserted rather than left implicit so nobody later reads a passing suite as proof
    that Windows separators were checked.
    """
    _force_os(monkeypatch, "nt")
    assert venv_python(_ROOT).endswith("/.venv/Scripts/python.exe")


@pytest.mark.parametrize("name", ["posix", "nt"])
def test_the_root_is_never_mutated(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    """It is a Path the caller keeps using. Returning a str built from it is what makes that safe,
    and an in-place mutation would be invisible until the caller's next use of the same object."""
    _force_os(monkeypatch, name)
    root = Path("/srv/quant")
    venv_python(root)
    assert root == Path("/srv/quant")
    assert isinstance(venv_python(root), str), "callers pass this straight to subprocess"
