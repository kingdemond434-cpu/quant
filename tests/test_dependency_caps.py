"""EVERY PRODUCTION DEPENDENCY CARRIES AN UPPER BOUND.

WHY THIS IS A TEST AND NOT A ONE-TIME EDIT. A green suite is only evidence about production when
the two environments run the same software. Every pin in pyproject was a bare floor until
2026-08-02, so CI resolved whatever was newest while the VPS ran requirements-vps.txt -- pandas
2.3.3 in production against 3.0.5 in the test container, a MAJOR version apart, which is where
behaviour changes rather than drifts.

That was not hypothetical. Installing production's exact pins and re-running the suite immediately
failed a test that had been green for weeks: `test_max_audit_sight` asserted on stdout line ONE,
and under production's pins the dependency-drift check prints a note before the marker. The test
had been passing only because the environment was wrong -- which is the precise failure mode this
whole exercise exists to catch, caught on the first run.

A one-time edit to pyproject fixes today. This keeps it fixed: any new dependency added without a
cap, or capped below the version production actually runs, fails here.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

PYPROJECT = Path("pyproject.toml")
VPS_PINS = Path("requirements-vps.txt")

#: pyproject spells some packages differently from pip's canonical name.
_ALIAS = {"pyyaml": "pyyaml", "types-pyyaml": "types-pyyaml"}


def _norm(name: str) -> str:
    return _ALIAS.get(name.lower().replace("_", "-"), name.lower().replace("_", "-"))


def _declared() -> dict[str, str]:
    """package -> full specifier, across runtime and dev extras."""
    data = tomllib.loads(PYPROJECT.read_text("utf-8"))
    specs: list[str] = list(data["project"].get("dependencies", []))
    for extra in data["project"].get("optional-dependencies", {}).values():
        specs.extend(extra)
    out = {}
    for spec in specs:
        m = re.match(r"^([A-Za-z0-9._-]+)", spec)
        if m:
            out[_norm(m.group(1))] = spec
    return out


def _production() -> dict[str, str]:
    """package -> exact version the VPS runs."""
    out = {}
    for ln in VPS_PINS.read_text("utf-8").splitlines():
        ln = ln.split("#")[0].strip()
        if "==" in ln:
            name, ver = ln.split("==", 1)
            out[_norm(name)] = ver.strip()
    return out


def test_every_dependency_production_pins_has_an_upper_bound() -> None:
    """A bare floor lets a resolver put the test environment a major version away from the desk,
    and nothing announces it -- the suite just quietly stops being evidence."""
    declared, prod = _declared(), _production()
    uncapped = sorted(name for name, spec in declared.items()
                      if name in prod and "<" not in spec)
    assert uncapped == [], (
        f"dependencies production pins but pyproject leaves uncapped: {uncapped}. A bare floor "
        "means CI resolves whatever is newest while the VPS runs something else, and a green "
        "suite against different software is not evidence about production.")


def test_no_cap_excludes_the_version_production_actually_runs() -> None:
    """The mirror failure: a cap so tight the desk's OWN version is forbidden would make the
    install unsatisfiable on the machine that matters."""
    declared, prod = _declared(), _production()
    bad = []
    for name, spec in declared.items():
        if name not in prod:
            continue
        m = re.search(r"<\s*([0-9][0-9.]*)", spec)
        if not m:
            continue
        cap_major = m.group(1).split(".")[0]
        prod_major = prod[name].split(".")[0]
        if int(prod_major) > int(cap_major):
            bad.append(f"{name}: production {prod[name]} excluded by cap {m.group(0)}")
    assert bad == [], bad


def test_the_production_pin_file_still_exists_and_is_populated() -> None:
    """The caps above are derived from it. If it vanishes, nothing anchors them to reality and
    the whole check silently passes over an empty set."""
    prod = _production()
    assert len(prod) >= 15, f"only {len(prod)} exact pins in {VPS_PINS} -- production's "
    assert "pandas" in prod and "numpy" in prod


def test_pandas_specifically_is_capped_below_3() -> None:
    """Named explicitly because it is the one that actually bit: a 2.x/3.x split where
    Timestamp.utcnow() raises a removal warning on 3.x and is silent on 2.3.3, so identical code
    produces different signals in the two environments."""
    spec = _declared()["pandas"]
    assert "<3" in spec, spec
    assert _production()["pandas"].startswith("2."), (
        "production moved to pandas 3 -- raise the cap deliberately and re-run the suite against "
        "it before trusting anything green")
