"""ENFORCED BLINDING BETWEEN RESEARCH COHORTS (Tier S layer 4).

The researcher market counts a mechanism as INDEPENDENTLY DISCOVERED when two cohorts that cannot
read each other's output both reach it. "Cannot read" was a sentence until this module. Now it is
a firewall role per seat:

    seat:<name>   the organs whose own code writes data/intelligence/<name>/ (its HOME);
                  forbidden to read data/intelligence/<other>/ for every seat of another cohort

Seats are measured, never listed: a seat is a directory under either intelligence root, or one an
organ's code writes into. A seat's cohort is its epistemology (the caller's `cohort_of`, the same
function the market prices cohorts by). The roles are fed to the existing firewall:

  * STATIC: `firewall.audit` checks every home organ's resolved path strings for another cohort's
    seat (BLIND_READ); this module adds BLIND_TREE, a home organ that walks the WHOLE intelligence
    tree (it can read every cohort at once).
  * RUNTIME: `firewall.register` makes the roles visible to `firewall.may`, and `guard_read` is
    the one-line call a seat organ makes before it opens another seat's file.
  * CONSEQUENCE: `contaminated_pairs` turns the violations into the cohort pairs that are NOT
    blind to each other, and the market stops counting their joint discoveries as independent.

Nothing here reads a discovery file's contents; it reads code and directory names.
"""
from __future__ import annotations

import ast
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any

from libs.tiers import firewall

#: where seat organs live (tests excluded)
SCAN: tuple[str, ...] = ("desks/mt5/research/*.py", "desks/mt5/scripts/*.py", "scripts/*.py",
                         "desks/mt5/side_channels/*.py", "libs/**/*.py")
INTEL_ROOTS: tuple[str, ...] = ("data/intelligence", "desks/mt5/data/intelligence")
_WALKS = ("glob", "rglob", "iterdir", "walk", "listdir", "scandir")


def disk_seats(root: Path, roots: Iterable[str] = INTEL_ROOTS) -> set[str]:
    out: set[str] = set()
    for r in roots:
        d = root / r
        if d.is_dir():
            out |= {p.name for p in d.iterdir() if p.is_dir()}
    return out


def _tree_walker(tree: ast.AST) -> bool:
    """True when the module walks an intelligence ROOT (not one seat) with glob/rglob/iterdir/
    os.walk/listdir/scandir."""
    nodes, consts = firewall.index(tree)
    for n in nodes:
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        name = f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else ""
        if name not in _WALKS:
            continue
        srcs: list[ast.AST] = list(n.args[:1])
        if isinstance(f, ast.Attribute):
            srcs.append(f.value)
        for s in srcs:
            for p in firewall._resolve(s, consts):
                if p.replace("\\", "/").rstrip("/").endswith("intelligence"):
                    return True
    return False


def seat_map(root: Path, globs: Iterable[str] = SCAN,
             roots: Iterable[str] = INTEL_ROOTS) -> dict[str, Any]:
    """organ -> the seats it writes (home), the seats it names (refs), whether it walks the tree;
    seat -> its home organs."""
    known = disk_seats(root, roots)
    organs: dict[str, dict[str, Any]] = {}
    for p in firewall._organs(root, globs):
        rel = p.relative_to(root).as_posix()
        if "/tests/" in f"/{rel}" or rel.startswith("tests/"):
            continue
        text = p.read_text("utf-8", errors="replace")
        if "intelligence" not in text:
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        home = {s for t in firewall.written_paths(tree) for s in firewall.seats_in(t)}
        refs = {s for t in firewall.path_strings(tree) for s in firewall.seats_in(t)}
        organs[rel] = {"home": home, "refs": refs, "tree": _tree_walker(tree)}
    seats: dict[str, dict[str, Any]] = {s: {"home_organs": [], "on_disk": True} for s in known}
    for rel, o in organs.items():
        for s in o["home"]:
            seats.setdefault(s, {"home_organs": [], "on_disk": s in known})
            seats[s]["home_organs"].append(rel)
    for o in organs.values():
        o["refs"] = sorted(s for s in o["refs"] if s in seats)
        o["home"] = sorted(o["home"])
    return {"seats": seats, "organs": organs}


def cohort_roles(smap: Mapping[str, Any], cohort_of: Callable[[str], str]
                 ) -> tuple[firewall.Role, ...]:
    """One firewall role per seat that has a home organ: forbidden every other cohort's seats."""
    seats = smap.get("seats") or {}
    cohort = {s: cohort_of(s) for s in seats}
    out: list[firewall.Role] = []
    for s, row in sorted(seats.items()):
        others = tuple(sorted(o for o in seats if cohort[o] != cohort[s]))
        out.append(firewall.Role(
            f"seat:{s}", tuple(sorted(set(row.get("home_organs") or []))),
            forbid_seats=others,
            sentence=f"Seat {s} (cohort {cohort[s]}) may not read another cohort's "
                     "data/intelligence output."))
    return tuple(out)


def contaminated_pairs(violations: Iterable[Mapping[str, Any]],
                       cohort_of: Callable[[str], str]) -> set[frozenset[str]]:
    """Cohort pairs that are not blind to each other, from BLIND_READ violations. A BLIND_TREE
    organ contaminates its cohort with every other cohort (`*`)."""
    out: set[frozenset[str]] = set()
    for v in violations:
        role = str(v.get("role") or "")
        if not role.startswith("seat:"):
            continue
        mine = cohort_of(role.removeprefix("seat:"))
        if v.get("kind") == "BLIND_READ":
            other = cohort_of(str(v.get("token") or ""))
            if other != mine:
                out.add(frozenset((mine, other)))
        elif v.get("kind") == "BLIND_TREE":
            out.add(frozenset((mine, "*")))
    return out


def audit(root: Path, cohort_of: Callable[[str], str], *, register: bool = True,
          globs: Iterable[str] = SCAN) -> dict[str, Any]:
    smap = seat_map(root, globs)
    roles = cohort_roles(smap, cohort_of)
    if register:
        firewall.register(roles)
    homed = [r for r in roles if r.organs]
    rep = firewall.audit(root, homed)
    viol = list(rep["violations"])
    for r in homed:
        for organ in r.organs:
            if (smap["organs"].get(organ) or {}).get("tree"):
                viol.append({"role": r.name, "organ": organ, "kind": "BLIND_TREE",
                             "token": "data/intelligence/**", "rule": r.sentence})
    cohorts: dict[str, list[str]] = {}
    for s in smap["seats"]:
        cohorts.setdefault(cohort_of(s), []).append(s)
    pairs = contaminated_pairs(viol, cohort_of)
    return {"n_seats": len(smap["seats"]), "n_homed_seats": len(homed),
            "n_cohorts": len(cohorts),
            "cohorts": {c: sorted(v) for c, v in sorted(cohorts.items())},
            "home_organs": {r.name: list(r.organs) for r in homed},
            "violations": viol, "n_violations": len(viol),
            "contaminated_pairs": sorted(sorted(p) for p in pairs),
            "roles": [r.name for r in roles], "registered": len(roles) if register else 0}


def guard_read(seat: str, target: str) -> None:
    """The runtime call: a seat organ asks before it reads another seat's file. Raises
    `firewall.FirewallError` when the target belongs to another cohort (roles must have been
    registered by `audit` or `firewall.register`)."""
    firewall.may(f"seat:{seat}", "read", target.replace("\\", "/"))


def is_blind(a: str, b: str, pairs: set[frozenset[str]]) -> bool:
    return a != b and frozenset((a, b)) not in pairs and frozenset((a, "*")) not in pairs \
        and frozenset((b, "*")) not in pairs
