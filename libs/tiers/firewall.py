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
import re
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
    #: data/intelligence/<seat>/ directories the role's organs must not read (cohort blinding,
    #: layer 4): matched on the path SEGMENT after `intelligence/`, never as a substring, so
    #: seat `kimi` never forbids `kimi_archive`
    forbid_seats: tuple[str, ...] = ()


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
            if role.forbid_seats:
                seen = {s for t in path_strings(tree) for s in seats_in(t)}
                for seat in sorted(seen & set(role.forbid_seats)):
                    violations.append({"role": role.name, "organ": rel, "kind": "BLIND_READ",
                                       "token": seat, "rule": role.sentence})
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


def may(role: str, verb: str, target: str, roles: Iterable[Role] | None = None) -> None:
    """Runtime check for new organs. verb is 'read' or 'write'. Raises FirewallError.

    `roles` defaults to the static table plus every role registered at runtime (`register`):
    the cohort-blinding seat roles are built from the repository and the seat map, so the organ
    that measured them registers them instead of this module hard-coding a seat list."""
    for r in (tuple(roles) if roles is not None else ROLES + tuple(_REGISTERED.values())):
        if r.name != role:
            continue
        if verb == "read" and any(t in target for t in r.forbid_tokens):
            raise FirewallError(f"{role} may not read {target}: {r.sentence}")
        if verb == "read" and r.forbid_seats:
            hit = sorted(set(seats_in(target)) & set(r.forbid_seats))
            if hit:
                raise FirewallError(f"{role} may not read {target} (seat {hit[0]}): "
                                    f"{r.sentence}")
        if verb == "write" and any(t in target for t in r.forbid_writes):
            raise FirewallError(f"{role} may not write {target}: {r.sentence}")
        return
    raise FirewallError(f"unknown role {role!r}")


_REGISTERED: dict[str, Role] = {}


def register(roles: Iterable[Role]) -> int:
    """Make measured roles visible to `may()` by default (a role of the same name is replaced)."""
    n = 0
    for r in roles:
        _REGISTERED[r.name] = r
        n += 1
    return n


def registered() -> tuple[Role, ...]:
    return tuple(_REGISTERED.values())


_SEAT_RX = re.compile(r"intelligence[/\\]+([A-Za-z0-9_\-]+)(?![A-Za-z0-9_\-{}*]*\.[A-Za-z]|[{*])")


def seats_in(text: str) -> list[str]:
    """The data/intelligence/<seat> directories a path string names. A FILE directly under the
    intelligence root (`intelligence/latest_discoveries.json`) names no seat."""
    return _SEAT_RX.findall(str(text).replace("\\", "/"))


def _resolve(node: ast.AST, consts: Mapping[str, list[str]], depth: int = 0) -> list[str]:
    """Every path string an expression can spell: literals, f-string skeletons, names bound to
    literals, `a / b` joins, `Path(a, b)` / `joinpath` and tuples of those. An unknown part is
    empty, so `self.root / "intelligence" / "kimi"` still resolves to `/intelligence/kimi`."""
    if depth > 12:
        return []
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, ast.JoinedStr):
        return ["".join(v.value if isinstance(v, ast.Constant) and isinstance(v.value, str)
                        else "{}" for v in node.values)]
    if isinstance(node, ast.Name):
        return list(consts.get(node.id, [""]))
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Div, ast.Add)):
        sep = "/" if isinstance(node.op, ast.Div) else ""
        left = _resolve(node.left, consts, depth + 1) or [""]
        right = _resolve(node.right, consts, depth + 1) or [""]
        return [a + sep + b for a in left[:8] for b in right[:8]]
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        out: list[str] = []
        for e in node.elts:
            out.extend(_resolve(e, consts, depth + 1))
        return out
    if isinstance(node, ast.Call):
        f = node.func
        fname = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute)
                                                      else "")
        if fname in ("Path", "PurePath", "joinpath"):
            parts: list[list[str]] = []
            if isinstance(f, ast.Attribute) and fname == "joinpath":
                parts.append(_resolve(f.value, consts, depth + 1) or [""])
            parts.extend(_resolve(a, consts, depth + 1) or [""] for a in node.args)
            acc = [""]
            for p in parts:
                acc = [(a + "/" + b) if a else b for a in acc[:8] for b in p[:8]]
            return acc
    return []


_INDEX: dict[int, tuple[ast.AST, list[ast.AST], dict[str, list[str]]]] = {}


def index(tree: ast.AST) -> tuple[list[ast.AST], dict[str, list[str]]]:
    """(every node, NAME -> the path strings it is bound to), computed once per tree: the audits
    ask several questions of one module and a full walk per question cost seconds per organ."""
    hit = _INDEX.get(id(tree))
    if hit is not None and hit[0] is tree:
        return hit[1], hit[2]
    nodes = list(ast.walk(tree))
    assigns = [n for n in nodes if isinstance(n, (ast.Assign, ast.AnnAssign))
               and n.value is not None]
    consts: dict[str, list[str]] = {}
    for _ in range(2):  # two passes, so a name built from a later-bound name resolves
        for n in assigns:
            tgts = n.targets if isinstance(n, ast.Assign) else [n.target]
            for t in tgts:
                if isinstance(t, ast.Name) and n.value is not None:
                    vals = _resolve(n.value, consts)
                    if any(vals):
                        consts[t.id] = vals[:16]
    if len(_INDEX) > 8:
        _INDEX.clear()
    _INDEX[id(tree)] = (tree, nodes, consts)
    return nodes, consts


def path_constants(tree: ast.AST) -> dict[str, list[str]]:
    """NAME -> the path strings it is bound to anywhere in the module."""
    return index(tree)[1]


def path_strings(tree: ast.AST) -> list[str]:
    """Every path string the module can spell: its literals, its bound names and every join."""
    nodes, consts = index(tree)
    out = [n.value for n in nodes if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    for vals in consts.values():
        out.extend(vals)
    for n in nodes:
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div):
            out.extend(_resolve(n, consts))
    return out


#: call names that put data somewhere: a seat's HOME is the intelligence directory its own code
#: hands to one of these
_PUT_WORDS = ("write", "dump", "save", "append", "emit", "donate", "publish", "atomic", "mkdir",
              "to_json", "to_csv", "to_parquet")


def written_paths(tree: ast.AST) -> list[str]:
    """Path strings the module hands to a writing call (`open(x, 'w')`, `x.write_text`,
    `_write(x, doc)`, `x.mkdir()`, `json.dump(doc, open(x, 'a'))` ...), names resolved."""
    nodes, consts = index(tree)
    out: list[str] = []
    for n in nodes:
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        name = (f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute)
                else "").lower()
        if name == "open":
            mode = ""
            if len(n.args) > 1 and isinstance(n.args[1], ast.Constant):
                mode = str(n.args[1].value)
            for kw in n.keywords:
                if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                    mode = str(kw.value.value)
            if any(c in mode for c in "wax"):
                srcs: list[ast.AST] = list(n.args[:1])
                if isinstance(f, ast.Attribute):
                    srcs.append(f.value)
                for a in srcs:
                    out.extend(_resolve(a, consts))
            continue
        if not any(w in name for w in _PUT_WORDS):
            continue
        srcs = [*n.args, *(kw.value for kw in n.keywords)]
        if isinstance(f, ast.Attribute):
            srcs.append(f.value)
        for a in srcs:
            out.extend(_resolve(a, consts))
    return [t for t in out if t]


# ------------------------------------------------------------------------------------------------
# DEVELOPER -> EVALUATOR (layer 12): an organ that writes code may not write the evaluator
# ------------------------------------------------------------------------------------------------

#: organs that generate or rewrite code by construction; `developer_role` adds every organ whose
#: own source writes a `.py` file
DEVELOPER_ORGANS: tuple[str, ...] = (
    "desks/mt5/research/implementer.py", "desks/mt5/research/alpha_evolution.py",
    "desks/mt5/research/expression_factory.py", "desks/mt5/research/descendants.py",
    "desks/mt5/research/research_evolution.py", "desks/mt5/research/*_factory.py",
    "desks/mt5/research/*_miner.py", "desks/mt5/research/strategy_*.py",
    "libs/research/codegen*.py", "libs/tiers/evolution.py", "libs/tiers/grammar_bias.py")
#: where the evaluator lives: the signed judge files and the validation library
EVALUATOR_PATHS: tuple[str, ...] = (
    "universal_gate", "external_gauntlet", "libs/validation/", "validation/gauntlet",
    "gate_policy", "multiplicity", "certificate_truth", "blind_reviewer", "evidence_vault",
    "heat_policy", "IMMUTABLE_MANIFEST", "check_immutable_evaluator")
_SCAN_FOR_CODE_WRITERS: tuple[str, ...] = ("desks/mt5/research/*.py", "libs/research/*.py",
                                           "libs/tiers/*.py", "scripts/*.py")


def code_writers(root: Path, globs: Iterable[str] = _SCAN_FOR_CODE_WRITERS) -> list[str]:
    """Organs whose own source writes a Python file: developers, whatever they are called."""
    out: list[str] = []
    for p in _organs(root, globs):
        text = p.read_text("utf-8", errors="replace")
        if '.py"' not in text and ".py'" not in text:
            continue            # it cannot spell a Python target, so it cannot write one
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        if any(t.rstrip("'\" )").endswith(".py") for t in written_paths(tree)
               + _write_targets(tree)):
            out.append(p.relative_to(root).as_posix())
    return sorted(set(out))


def developer_role(root: Path | None = None) -> Role:
    """The static developer organs, plus (given a root) every organ measured to write code."""
    extra = tuple(c for c in code_writers(root) if c not in DEVELOPER_ORGANS) if root else ()
    return Role("developer", DEVELOPER_ORGANS + extra, forbid_writes=EVALUATOR_PATHS,
                sentence="Developer cannot alter the evaluator: no organ that writes code may "
                         "write the gauntlet, the gate policy or the validation library.")


ROLES = (*ROLES, developer_role())


# ------------------------------------------------------------------------------------------------
# LOCKBOX ACCEPTS FROZEN CANDIDATES ONLY (layer 12)
# ------------------------------------------------------------------------------------------------

#: names a function must use before it opens a lockbox, as proof the candidate was frozen first
FREEZE_MARKERS: tuple[str, ...] = ("frozen", "freeze", "sha256", "spec_hash", "code_hash",
                                   "config_hash", "seal", "immutable", "lockbox_accepts")
_LOCKBOX_SCAN: tuple[str, ...] = ("libs/**/*.py", "desks/mt5/research/*.py",
                                  "desks/mt5/side_channels/*.py", "desks/mt5/scripts/*.py",
                                  "scripts/*.py")
LOCKBOX_SENTENCE = "Lockbox accepts immutable candidates only."


def lockbox_audit(root: Path, globs: Iterable[str] = _LOCKBOX_SCAN) -> dict[str, Any]:
    """Every function that opens a lockbox (`.open_lockbox()`) must show, in its own body, that
    the candidate it scores was frozen first (a hash, a seal, a frozen spec, `lockbox_accepts`).
    A function that opens the lockbox with no such mark is UNFROZEN_OPEN."""
    violations: list[dict[str, Any]] = []
    openers = 0
    for p in _organs(root, globs):
        rel = p.relative_to(root).as_posix()
        if "/tests/" in f"/{rel}" or rel.endswith("libs/validation/lockbox.py"):
            continue
        text = p.read_text("utf-8", errors="replace")
        if "open_lockbox" not in text:
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            opens = [c for c in ast.walk(fn) if isinstance(c, ast.Call)
                     and isinstance(c.func, ast.Attribute) and c.func.attr == "open_lockbox"]
            if not opens:
                continue
            openers += 1
            # identifiers only: a comment or a message that SAYS "sealed" proves nothing
            words = [n.id for n in ast.walk(fn) if isinstance(n, ast.Name)]
            words += [n.attr for n in ast.walk(fn) if isinstance(n, ast.Attribute)]
            low = " ".join(words).lower()
            if not any(m in low for m in FREEZE_MARKERS):
                violations.append({"role": "lockbox", "organ": rel, "kind": "UNFROZEN_OPEN",
                                   "token": fn.name, "line": opens[0].lineno,
                                   "rule": LOCKBOX_SENTENCE})
    return {"openers": openers, "violations": violations}


def _canon(spec: Mapping[str, Any]) -> str:
    import json
    return json.dumps(spec, sort_keys=True, default=str, separators=(",", ":"))


def freeze(spec: Mapping[str, Any]) -> dict[str, Any]:
    """A candidate the lockbox will accept: its spec and the hash that pins it."""
    import hashlib
    body = {k: v for k, v in spec.items() if k not in ("spec_hash", "frozen")}
    return {**body, "frozen": True,
            "spec_hash": hashlib.sha256(_canon(body).encode()).hexdigest()}


def lockbox_accepts(candidate: Mapping[str, Any]) -> str:
    """Runtime half of the lockbox role: raise unless the candidate is frozen and its spec still
    hashes to the pin it was frozen with (a candidate edited after freezing is refused)."""
    import hashlib
    pin = candidate.get("spec_hash")
    if not candidate.get("frozen") or not isinstance(pin, str):
        raise FirewallError(f"lockbox refuses an unfrozen candidate: {LOCKBOX_SENTENCE}")
    body = {k: v for k, v in candidate.items() if k not in ("spec_hash", "frozen")}
    if hashlib.sha256(_canon(body).encode()).hexdigest() != pin:
        raise FirewallError("lockbox refuses a candidate changed after it was frozen: "
                            f"{LOCKBOX_SENTENCE}")
    return pin


# ------------------------------------------------------------------------------------------------
# EVALUATORS MAY NOT SHARE A REWARD ARTIFACT WITH WHAT THEY JUDGE (layer 32)
# ------------------------------------------------------------------------------------------------

#: artifacts that pay a producer (compute budget, price, bounty) for what the gates made of it
REWARD_TOKENS: tuple[str, ...] = ("researcher_prices", "leg_prices", "cycle_pricing",
                                  "research_budget", "bounty")
EVALUATOR_REWARD = Role(
    "evaluator_reward",
    ("desks/mt5/research/universal_gate.py", "libs/validation/gauntlet.py",
     "desks/mt5/research/blind_reviewer.py", "libs/research/review_rubric.py",
     "libs/tiers/review_panel.py", "libs/tiers/red_queen.py", "libs/tiers/meta_benchmark.py",
     "libs/tiers/test_invention.py", "libs/tiers/online_fdr.py"),
    forbid_tokens=REWARD_TOKENS,
    sentence="An evaluator cannot read the reward artifact that pays the thing it judges.")


def shared_reward(judges: Mapping[str, Iterable[str]], producer_of: Mapping[str, str],
                  rewarded: Mapping[str, Iterable[str]],
                  host_of: Mapping[str, str]) -> dict[str, Any]:
    """Flag every (evaluator, judged candidate) pair that one reward artifact pays together.

    judges       evaluator -> the candidates it judges
    producer_of  candidate -> the producer (researcher) that bore it
    rewarded     reward artifact -> the producer names it pays
    host_of      evaluator -> the producer name its own host process is paid under

    SELF when the candidate was born by the evaluator's own host (it judges its own output and
    both are paid from the same book); SHARED when the artifact merely pays both. A candidate
    with no producer is counted UNATTRIBUTED, never cleared."""
    paid = {a: {str(n) for n in names} for a, names in rewarded.items()}

    def under(name: str, host: str) -> bool:
        return name == host or name.startswith(host + ":")

    flags: list[dict[str, Any]] = []
    unattributed = 0
    per: dict[str, dict[str, int]] = {}
    for ev, cands in judges.items():
        host = host_of.get(ev)
        mine = sorted(a for a, names in paid.items()
                      if host and any(under(n, host) for n in names))
        row = per.setdefault(ev, {"judged": 0, "self": 0, "shared": 0})
        for c in cands:
            row["judged"] += 1
            pr = producer_of.get(str(c))
            if not pr:
                unattributed += 1
                continue
            shared = [a for a in mine if pr in paid[a]]
            if not shared:
                continue
            sev = "SELF" if host and under(pr, host) else "SHARED"
            row["self" if sev == "SELF" else "shared"] += 1
            flags.append({"evaluator": ev, "candidate": str(c), "producer": pr,
                          "artifacts": shared, "severity": sev})
    return {"flags": flags, "n_flags": len(flags),
            "n_self": sum(1 for f in flags if f["severity"] == "SELF"),
            "unattributed": unattributed, "per_evaluator": per,
            "reward_artifacts": sorted(paid)}


def role_signature(role: Role) -> str:
    """A rule's identity: when it changes, the rule is new and starts from what it measures."""
    import hashlib
    return hashlib.sha256(repr(role).encode()).hexdigest()[:16]


def seed_baseline(current: Mapping[str, Any], baseline: Mapping[str, Any] | None,
                  roles: Iterable[Role]) -> dict[str, Any]:
    """The ratchet's baseline with every NEW or CHANGED rule seeded from its first measurement.

    A rule that did not exist when the baseline was taken would otherwise read every violation it
    finds on its first hour as a breach -- and the baseline, which only ever shrinks, would keep
    it breached forever. So a rule enters at what it measured; after that it may only fall."""
    base = dict(baseline or {})
    sigs = dict(base.get("signatures") or {})
    viol = list(base.get("violations") or []) if baseline else list(
        current.get("violations") or [])
    fresh = [r for r in roles if sigs.get(r.name) != role_signature(r)]
    if baseline:
        names = {r.name for r in fresh}
        known = {(v.get("role"), v.get("organ"), v.get("kind"), v.get("token")) for v in viol}
        for v in current.get("violations") or []:
            k = (v.get("role"), v.get("organ"), v.get("kind"), v.get("token"))
            if v.get("role") in names and k not in known:
                viol.append(v)
    for r in roles:
        sigs[r.name] = role_signature(r)
    return {**base, "violations": viol, "signatures": sigs,
            "seeded": sorted(r.name for r in fresh)}


def role_of(rel_path: str, roles: Iterable[Role] = ROLES) -> list[str]:
    return [r.name for r in roles if any(fnmatch.fnmatch(rel_path, g) for g in r.organs)]
