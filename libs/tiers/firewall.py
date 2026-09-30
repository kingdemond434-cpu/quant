"""THE EPISTEMIC FIREWALL (Tier S layers 12 and 32): roles, and a static proof of who can touch
what.

    generator    cannot see lockbox data or lockbox results
    developer    cannot alter the evaluator (no generator/miner writes validation code)
    evaluator    cannot alter strategy code
    lockbox      accepts immutable candidates only
    reviewer     cannot promote
    allocator    accepts certificates only (never raw hypotheses or gauntlet candidates)
    execution    cannot increase allocator exposure (never writes the allocation)
    attribution  cannot rewrite historical forecasts

Policy text is not architecture. This module turns each sentence into a machine check over the
source of every organ that plays the role: the string literals and imports an organ holds are the
paths and modules it can reach, so a generator whose source names the lockbox, or an execution
organ whose source writes the allocation file, is a VIOLATION the law gate can see. The count is a
ratchet (`baseline`): it may fall, never rise, so a new organ must arrive clean.

`may(role, verb, target)` is the runtime half: new organs call it before a read or write that
crosses a role boundary, and it raises instead of trusting the caller.
"""
from __future__ import annotations

import ast
import fnmatch
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Role:
    name: str
    organs: tuple[str, ...]
    #: substrings that must not appear in any string literal of the role's organs
    forbid_tokens: tuple[str, ...] = ()
    #: module prefixes the role's organs must not import
    forbid_imports: tuple[str, ...] = ()
    #: substrings that must not appear as a WRITE target (open(...,'w'), write_text, dump)
    forbid_writes: tuple[str, ...] = ()
    sentence: str = ""


ROLES: tuple[Role, ...] = (
    Role("generator",
         ("desks/mt5/research/*_miner.py", "desks/mt5/research/expression_factory.py",
          "desks/mt5/research/alpha_evolution.py", "desks/mt5/research/deep_forest_miner.py",
          "desks/mt5/research/representation_forge.py", "desks/mt5/research/descendants.py",
          "desks/mt5/research/math_lab.py", "desks/mt5/research/physics_lab.py"),
         forbid_tokens=("LOCKBOX_RESULTS", "lockbox_holdout", "lockbox_vault"),
         forbid_imports=("libs.validation.lockbox",),
         forbid_writes=("universal_gate", "gauntlet", "gate_policy", "UNIVERSAL_SURVIVORS"),
         sentence="Generator cannot access lockbox results and cannot write evaluator state."),
    Role("evaluator",
         ("desks/mt5/research/universal_gate.py", "libs/validation/gauntlet.py",
          "desks/mt5/research/blind_reviewer.py"),
         forbid_writes=("sleeves.json", "strategies/", "families/"),
         sentence="Evaluator cannot alter strategy code or the live sleeve book."),
    Role("reviewer",
         ("desks/mt5/research/blind_reviewer.py", "libs/research/review_rubric.py",
          "libs/tiers/review_panel.py"),
         forbid_writes=("sleeves.json", "UNIVERSAL_SURVIVORS", "sleeve_registry"),
         sentence="Reviewer cannot promote."),
    Role("allocator",
         ("desks/mt5/research/pf_allocator.py",),
         forbid_tokens=("gauntlet_candidates", "hypothesis_graph", "intelligence/"),
         sentence="Allocator accepts certificates only."),
    Role("promoter",
         ("desks/mt5/research/promoter.py", "libs/tiers/promotion_authority.py"),
         forbid_tokens=("gauntlet_candidates", "hypothesis_graph", "intelligence/"),
         forbid_writes=("pf_allocation", "allocation.json"),
         sentence="Promoter reads certificates and verdicts only; it cannot write the "
                  "allocator's capital allocation."),
    Role("execution",
         ("desks/mt5/mt5desk/gateway.py", "desks/mt5/mt5desk/gateway_*.py",
          "desks/mt5/mt5desk/scalp_exec.py", "desks/mt5/mt5desk/netting.py"),
         forbid_writes=("pf_allocation", "allocation.json"),
         sentence="Execution cannot increase allocator exposure."),
    Role("attribution",
         ("desks/mt5/research/fill_attribution.py", "desks/mt5/research/forward_reconcile.py",
          "desks/mt5/research/attribution_reconcile.py"),
         forbid_writes=("pf_forecast_log", "forecast_log", "FORECAST_REGISTRY"),
         sentence="Live attribution cannot rewrite historical forecasts."),
)

_WRITE_CALLS = {"write_text", "write_bytes", "dump", "to_json", "to_parquet", "to_csv",
                "replace", "rename"}


def _string_literals(tree: ast.AST) -> list[str]:
    return [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant)
            and isinstance(n.value, str)]


def _imports(tree: ast.AST) -> list[str]:
    out: list[str] = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            out.extend(a.name for a in n.names)
        elif isinstance(n, ast.ImportFrom) and n.module:
            out.append(n.module)
    return out


def _write_targets(tree: ast.AST) -> list[str]:
    """String literals that reach a write call: open(x, 'w'/'a'), Path(x).write_text, json.dump
    into open(x,'w'), and module-level NAME = <path literal> used as a write target."""
    consts: dict[str, str] = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0],
                                                                           ast.Name):
            lits = [c.value for c in ast.walk(n.value) if isinstance(c, ast.Constant)
                    and isinstance(c.value, str)]
            if lits:
                consts[n.targets[0].id] = "/".join(lits)
    targets: list[str] = []

    def _lit(node: ast.AST) -> str:
        parts = [c.value for c in ast.walk(node) if isinstance(c, ast.Constant)
                 and isinstance(c.value, str)]
        names = [consts[c.id] for c in ast.walk(node) if isinstance(c, ast.Name)
                 and c.id in consts]
        return "/".join(parts + names)

    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        if isinstance(f, ast.Name) and f.id == "open" and n.args:
            mode = ""
            if len(n.args) > 1 and isinstance(n.args[1], ast.Constant):
                mode = str(n.args[1].value)
            for kw in n.keywords:
                if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                    mode = str(kw.value.value)
            if any(c in mode for c in "wax"):
                targets.append(_lit(n.args[0]))
        elif isinstance(f, ast.Attribute) and f.attr in _WRITE_CALLS:
            if f.attr in ("write_text", "write_bytes"):
                targets.append(_lit(f.value))
            elif f.attr in ("replace", "rename") and n.args:
                targets.append(_lit(n.args[0]))
            elif n.args:
                targets.append(_lit(n.args[-1]) if f.attr == "dump" else _lit(f.value))
    return [t for t in targets if t]


def _organs(root: Path, globs: Iterable[str]) -> list[Path]:
    out: list[Path] = []
    for g in globs:
        out.extend(p for p in sorted(root.glob(g)) if p.is_file())
    return out


def audit(root: Path, roles: Iterable[Role] = ROLES) -> dict[str, Any]:
    """Every role sentence checked against every organ that plays the role."""
    violations: list[dict[str, Any]] = []
    checked: dict[str, int] = {}
    for role in roles:
        organs = _organs(root, role.organs)
        checked[role.name] = len(organs)
        for p in organs:
            rel = p.relative_to(root).as_posix()
            try:
                tree = ast.parse(p.read_text("utf-8", errors="replace"))
            except SyntaxError:
                violations.append({"role": role.name, "organ": rel, "kind": "UNPARSEABLE"})
                continue
            lits = _string_literals(tree)
            for tok in role.forbid_tokens:
                if any(tok in s for s in lits):
                    violations.append({"role": role.name, "organ": rel, "kind": "READ",
                                       "token": tok, "rule": role.sentence})
            for imp in _imports(tree):
                if any(imp == f or imp.startswith(f + ".") for f in role.forbid_imports):
                    violations.append({"role": role.name, "organ": rel, "kind": "IMPORT",
                                       "token": imp, "rule": role.sentence})
            for tgt in _write_targets(tree):
                for tok in role.forbid_writes:
                    if tok in tgt:
                        violations.append({"role": role.name, "organ": rel, "kind": "WRITE",
                                           "token": tok, "target": tgt[:160],
                                           "rule": role.sentence})
    return {"roles": {r.name: r.sentence for r in roles}, "organs_checked": checked,
            "violations": violations, "n_violations": len(violations)}


def ratchet(current: Mapping[str, Any], baseline: Mapping[str, Any] | None) -> dict[str, Any]:
    """The count may fall, never rise; a NEW violation (not in the baseline) is a breach."""
    def key(v: Mapping[str, Any]) -> str:
        return f"{v.get('role')}|{v.get('organ')}|{v.get('kind')}|{v.get('token')}"
    now = {key(v) for v in current.get("violations") or []}
    base = {key(v) for v in (baseline or {}).get("violations") or []} if baseline else now
    new = sorted(now - base)
    return {"breach": bool(new), "new": new, "cleared": sorted(base - now),
            "n_now": len(now), "n_baseline": len(base)}


class FirewallError(PermissionError):
    pass


def may(role: str, verb: str, target: str, roles: Iterable[Role] = ROLES) -> None:
    """Runtime check for new organs. verb is 'read' or 'write'. Raises FirewallError."""
    for r in roles:
        if r.name != role:
            continue
        if verb == "read" and any(t in target for t in r.forbid_tokens):
            raise FirewallError(f"{role} may not read {target}: {r.sentence}")
        if verb == "write" and any(t in target for t in r.forbid_writes):
            raise FirewallError(f"{role} may not write {target}: {r.sentence}")
        return
    raise FirewallError(f"unknown role {role!r}")


def role_of(rel_path: str, roles: Iterable[Role] = ROLES) -> list[str]:
    return [r.name for r in roles if any(fnmatch.fnmatch(rel_path, g) for g in r.organs)]
