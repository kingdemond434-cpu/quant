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


# --------------------------------------------- and every IMPORT has to be declared at all

#: Modules that are third-party by name but must NOT be declared: optional integrations the code
#: imports lazily and degrades without, plus the two cross-check engines that already live in
#: their own extra. A hard dependency hiding in this list would be the very defect being hunted,
#: so each entry names why it is optional.
_OPTIONAL_BY_DESIGN = {
    "MetaTrader5",      # Windows-only broker bridge; every import site is guarded
    "arch",             # libs/research/stationarity degrades gracefully (test skips without it)
    "backtrader",       # cross-engine extra
    "vectorbt",         # cross-engine extra
    "streamlit",        # dashboard, not importable from any library path
    # plotting only. scripts/run_intraday_rotation.py:276-281 imports it INSIDE _plots(), behind
    # try/except ImportError, and on absence writes doc["plots"] = "matplotlib absent -- data
    # tables in JSON only" and returns. The JSON tables -- the actual research output -- are
    # unaffected, so this is a cosmetic degradation, never a silent one.
    "matplotlib",
    "hypothesis", "pytest", "_pytest",   # test-only, declared in the dev extra
}


def _third_party_imports() -> dict[str, list[str]]:
    """top-level module -> files importing it, across every tracked .py outside tests/."""
    import ast
    import sys

    roots = {p.name.removesuffix(".py") for p in Path(".").glob("*.py")}
    roots |= {p.name for p in Path(".").iterdir() if p.is_dir() and (p / "__init__.py").exists()}
    roots |= {"libs", "app", "scripts", "tests", "migrations", "api", "config"}
    # SIBLING SCRIPTS IMPORT EACH OTHER BY BARE NAME. `scripts/run_edge_gated_leverage.py` does
    # `from run_leverage_opt import main`, which resolves because the script's own directory is on
    # sys.path -- it is a LOCAL module, and reading it as an undeclared package would be a false
    # accusation that trains the reader to ignore this test.
    roots |= {p.stem for p in Path("scripts").rglob("*.py")}
    out: dict[str, list[str]] = {}
    for f in [*Path("libs").rglob("*.py"), *Path("scripts").rglob("*.py"),
              *Path("app").rglob("*.py")]:
        try:
            tree = ast.parse(f.read_text("utf-8", errors="ignore"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module.split(".")[0]] if node.module and node.level == 0 else []
            else:
                continue
            for n in names:
                if n in roots or n in sys.stdlib_module_names or n.startswith("_"):
                    continue
                out.setdefault(n, []).append(str(f))
    return out


def test_every_imported_third_party_package_is_declared() -> None:
    """CERTIFI WAS IMPORTED BY NINE SCRIPTS AND DECLARED IN NEITHER pyproject EXTRA.

    It was pinned in requirements-vps.txt only, so production had it and `pip install -e .` did
    not: a fresh checkout's `scripts/reconcile_venue.py` -- which builds the SSL context every
    venue reconciliation goes through -- raised ImportError at line 26. The caps test above
    compares two dependency LISTS to each other and cannot see a package missing from both; only
    the source can say what the code actually needs.

    It stayed invisible for another reason worth naming: CI's lint step had never passed, so the
    type check that reports the missing stub was skipped on every commit in the repo's history.
    """
    declared = {_norm(k) for k in _declared()}
    #: import name -> distribution name, where they differ.
    dist = {"yaml": "pyyaml", "sklearn": "scikit-learn", "dateutil": "python-dateutil",
            "pydantic_settings": "pydantic-settings"}
    missing = {}
    for mod, files in sorted(_third_party_imports().items()):
        if mod in _OPTIONAL_BY_DESIGN:
            continue
        if _norm(dist.get(mod, mod)) not in declared:
            missing[mod] = sorted(files)[:3]
    assert not missing, (
        "imported but declared in NO pyproject dependency list -- `pip install -e .[dev]` builds "
        f"an environment where these raise ImportError: {missing}")


def test_the_optional_allowlist_names_only_modules_that_are_actually_imported() -> None:
    """An allowlist that outlives its entries stops being a decision and becomes a place to hide
    one. A name here that nothing imports any more should be deleted, not carried."""
    imported = set(_third_party_imports())
    # pytest/hypothesis are imported from tests/, which the scan deliberately excludes.
    stale = {m for m in _OPTIONAL_BY_DESIGN if m not in imported} - {
        "hypothesis", "pytest", "_pytest"}
    assert not stale, f"allowlisted as optional but imported nowhere -- delete: {sorted(stale)}"
