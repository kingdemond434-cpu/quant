"""A fence that cannot ask must not instruct a destructive repair.

MEASURED 2026-09-05 on the live box. `check_authority_ratchet` imports `libs.ops.canon_lease` at
module scope; when `check_research_health` runs AS A SCRIPT its `sys.path[0]` is `scripts/`, not
the repo root, so that import raised on every run. A bare `except` swallowed it and the detector
answered False -- "no revocation recorded" -- forever. Called by hand from the repo root it
answered True, which is exactly why it read as correct for so long.

The alarm it then fired says "restore from canon before anything else". Following it would have
restored six AFG and two AFL certificates the desk had just retired, with a full record, for
being uncashable: symbols absent from the registry with no H1 bars. Silence about a real wipe is
bad. A confident instruction to undo a correct decision is worse.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]


def _load():
    spec = importlib.util.spec_from_file_location(
        "_h_test", _ROOT / "scripts" / "check_research_health.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_detector_answers_from_a_bare_script_path() -> None:
    """THE REGRESSION. Run with ONLY scripts/ importable, exactly as `python3 scripts/x.py` does."""
    code = (
        "import sys, importlib.util\n"
        f"sys.path = [p for p in sys.path if p not in ('', {str(_ROOT)!r})]\n"
        f"sys.path.insert(0, {str(_ROOT / 'scripts')!r})\n"
        f"spec = importlib.util.spec_from_file_location('h', "
        f"{str(_ROOT / 'scripts' / 'check_research_health.py')!r})\n"
        "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)\n"
        "print(m._revocation_recorded({'retired_certificates': {'a': 1}}))\n"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         cwd=str(_ROOT), timeout=120)
    assert out.stdout.strip() == "True", (out.stdout, out.stderr[-800:])


def test_the_three_answers_are_distinct() -> None:
    h = _load()
    assert h._revocation_recorded({"retired_certificates": {"a": 1}}) is True
    assert h._revocation_recorded({"n": 58}) is False
    # An unaskable ratchet is None -- neither "no revocation" nor "a wipe".
    assert h._revocation_recorded(object()) in (True, False, None)


def test_an_unanswerable_question_never_says_restore(monkeypatch) -> None:
    """The whole point: UNMEASURED is reported as UNMEASURED, and the destructive instruction is
    reserved for the case the desk actually established."""
    h = _load()
    monkeypatch.setattr(h, "_revocation_recorded", lambda _doc: None)
    # Anchor on the APPENDED breach text, not on any mention -- the docstring above quotes the
    # old instruction while explaining why it was wrong, and a naive search finds that first.
    src = (_ROOT / "scripts" / "check_research_health.py").read_text("utf-8")
    i_unmeasured = src.index("could not be asked whether it was sanctioned")
    i_restore = src.index('f"past the writer seals; restore from canon before anything else"')
    assert i_unmeasured < i_restore, "the UNMEASURED branch must come first"
    assert "UNMEASURED, not a wipe" in src
    # and the destructive instruction is reached only when the answer is an explicit False
    assert "elif not sanctioned:" in src
