"""ADOPT-AND-SEAL'S PRIVATE PATH LIST, PINNED TO THE ONE IN `libs/ops/release.py`.

`desks/mt5/scripts/Adopt-And-Seal.ps1` refuses to seal when a tracked path under
`$releaseCodePaths` differs from HEAD. `release.seal()` asks the same question of
`release.RELEASE_CODE_PATHS`. Two lists answering one question is how the 2026-09-24 halt
happened: a private list inside that script disagreed with the Python classification on one
regenerated file, every seal was refused for the rest of the day, and the gateway's release
interlock refused every placement from 10:00Z on. `desks/mt5/tests/test_release_identity.py`
pins the gateway's mirror; this pins the script's copy the same way, parsed from the script
itself so a new path added on one side only fails here rather than on the box.
"""
from __future__ import annotations

import re
from pathlib import Path

from libs.ops import release

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "desks" / "mt5" / "scripts" / "Adopt-And-Seal.ps1"


def _script_code_paths() -> list[str]:
    src = SCRIPT.read_text("utf-8", errors="ignore")
    assert "$releaseCodePaths = @(" in src, (
        "Adopt-And-Seal.ps1 no longer declares $releaseCodePaths -- retarget this parity test")
    block = src.split("$releaseCodePaths = @(", 1)[1].split(")", 1)[0]
    return re.findall(r'"([^"]+)"', block)


def test_the_list_is_found() -> None:
    """Without this the parity below could pass vacuously on a parse miss (L1.63)."""
    assert len(_script_code_paths()) >= 5, _script_code_paths()


def test_adopt_and_seal_code_paths_equal_release_code_paths() -> None:
    script = _script_code_paths()
    assert len(script) == len(set(script)), f"duplicate entries in $releaseCodePaths: {script}"
    py = release.RELEASE_CODE_PATHS
    assert tuple(script) == py, (
        "Adopt-And-Seal.ps1 $releaseCodePaths has drifted from libs.ops.release."
        f"RELEASE_CODE_PATHS: only in script {sorted(set(script) - set(py))}"
        f", only in release.py {sorted(set(py) - set(script))}. The seal "
        "and the script must refuse on the SAME paths, or every seal is refused forever.")


def test_no_code_root_swallows_state_or_build_output() -> None:
    """A code root that contained a state prefix or build output would make the script refuse
    a seal on a file an organ rewrites every pass -- the exact 2026-09-24 shape."""
    for code in _script_code_paths():
        for prefix in (*release.STATE_PREFIXES, *release.BUILD_PREFIXES):
            assert not prefix.startswith(code.rstrip("/") + "/"), (code, prefix)
