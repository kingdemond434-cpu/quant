"""The optional ERA5 dependency is declared once, in its own extra, with a cap (split from #263)."""
from __future__ import annotations

import tomllib
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]


def test_pyproject_declares_cdsapi_in_an_extra_with_a_cap() -> None:
    extras = tomllib.loads((_ROOT / "pyproject.toml").read_text("utf-8"))["project"][
        "optional-dependencies"]
    spec = next(s for s in extras["climate"] if s.startswith("cdsapi"))
    assert "<" in spec and ">=" in spec
