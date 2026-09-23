"""The injection fence must read what is INJECTED, not one of the two files that make it.

The consolidation of 2026-08-25 split the doctrine: `ops/brain_env.sh` concatenates
`ops/principal_doctrine.txt` AND `docs/LAWS.md` into the payload every organ receives. The sealed
core states the principle in prose ("TIMIDITY IS SCORED ON EVERY AXIS") while the token `L1.28`
lives in LAWS.md, six times. Reading only the first file, this fence printed "the law is not
reaching any organ" on every run while the law was reaching every organ -- and a fence that is
WRONG is worse than no fence, because it teaches the reader to skip the line where a real one
would appear (L1.43). It also buried two genuine QUOTA-CAP findings under a false headline.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load():
    spec = importlib.util.spec_from_file_location(
        "_t_timidity", ROOT / "scripts" / "check_timidity_language.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_the_injected_set_is_read_from_brain_env_not_restated() -> None:
    mod = _load()
    files = {f.relative_to(ROOT).as_posix() for f in mod._injected_doctrine_files()}
    assert "ops/principal_doctrine.txt" in files
    assert "docs/LAWS.md" in files, (
        "the fence is reading a narrower surface than brain_env.sh injects, which is how it "
        "reported a live law as absent")


def test_L1_28_is_found_in_the_real_injected_payload() -> None:
    mod = _load()
    assert "l1.28" in mod._injected_doctrine_text().lower()


def test_the_token_really_is_absent_from_the_sealed_core_alone() -> None:
    """Positive control: without this, the test above would pass even if the bug were back."""
    core = (ROOT / "ops" / "principal_doctrine.txt").read_text("utf-8").lower()
    assert "l1.28" not in core, (
        "the sealed core now carries the token, so this test no longer exercises the defect -- "
        "re-point it at whichever law is stated in prose in one file and by id in the other")
