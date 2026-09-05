"""THE canonical policy resolver -- the one every brain must use (CXCV-27/38).

WHY ONE RESOLVER. Inheritance of policy is only demonstrated if the SAME code answers "what
policy is in force" for every seat. A second agent resolving policy its own way proves nothing
about whether it inherited anything; it proves only that two programs agreed today. So this
module owns the question, and `deepseek_cycle.policy_gate` -- like any future seat -- delegates
here rather than re-deriving.

ONE IMPLEMENTATION, NOT A SECOND COPY. The digesting, delimiter and floor rules already live in
`scripts/check_constitution_core.py`, which is what the law gate runs. Re-implementing them here
would create exactly the drift this module exists to prevent, so this loads that module and calls
its functions. The seal's rules therefore cannot diverge from the seal's checker: there is only
one of each.

MEASURED 2026-09-03: this module did not exist, `policy_gate` refused on the ImportError, and the
deepseek seat crashed on every launch for want of the resolver -- nine of the fifteen dead seat
launches in 24 hours. A refusal is a legitimate answer; a resolver that was never written is not
a refusal, it is an absence, and absence is never health (L1.28a).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
_CHECKER_REL = Path("scripts/check_constitution_core.py")


def _load_checker(root: Path) -> ModuleType | None:
    """Import `check_constitution_core` FOR A GIVEN ROOT, or None if that tree has no checker.

    Loaded under a root-specific module name so resolving an alternate tree (which the tests do,
    and which any sandbox check would do) never overwrites the cached real-root module.
    """
    path = root / _CHECKER_REL
    if not path.is_file():
        return None
    name = f"_canonical_policy_checker_{abs(hash(str(root)))}"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:                      # a checker that will not import cannot resolve policy
        sys.modules.pop(name, None)
        return None
    return module


def resolve(root: Path | str | None = None) -> dict[str, Any]:
    """Resolve the policy in force under `root` (default: this repo).

    Returns a dict that ALWAYS carries `verdict`, `canonical_policy_hash`,
    `canonical_policy_version` and `errors` -- present even when the verdict is a refusal, so a
    caller can report the refusal without a KeyError. `verdict` is "RESOLVED" only when the
    sealed doctrine block parses, clears its line floor and digests; every other state names
    itself (MISSING_POLICY, CHECKER_UNAVAILABLE, DOCTRINE_INVALID) and is NOT a pass.

    The hash is `sha256:<digest>` of the doctrine's immutable block -- the core that is actually
    injected into every seat -- and the version travels WITH it as the substantive line count,
    because a hash alone cannot distinguish "intact" from "gutted but hashes fine" (L1.57).
    """
    base = Path(root).resolve() if root is not None else _ROOT
    out: dict[str, Any] = {
        "root": str(base),
        "verdict": "MISSING_POLICY",
        "canonical_policy_hash": None,
        "canonical_policy_version": None,
        "errors": [],
    }
    checker = _load_checker(base)
    if checker is None:
        out["verdict"] = "CHECKER_UNAVAILABLE"
        out["errors"] = [f"{_CHECKER_REL.as_posix()} is absent or unimportable under {base}"]
        return out

    # Point the checker's module-level roots at the tree being resolved. The functions read these
    # at call time, so this is enough to resolve an alternate tree without duplicating any rule.
    # setattr, not attribute assignment: the checker is loaded from a path at runtime, so its
    # module-level names are invisible to static analysis by construction.
    setattr(checker, "_ROOT", base)                               # noqa: B010
    setattr(checker, "_CONST", base / "docs/CONSTITUTION.md")     # noqa: B010
    try:
        payload, errors = checker.doctrine_current()
    except Exception as exc:                                      # never raise past the resolver
        out["verdict"] = "DOCTRINE_INVALID"
        out["errors"] = [f"doctrine could not be digested: {exc}"]
        return out
    if payload is None:
        out["verdict"] = "MISSING_POLICY" if any("missing" in e for e in errors) \
            else "DOCTRINE_INVALID"
        out["errors"] = list(errors)
        return out

    out["verdict"] = "RESOLVED"
    out["canonical_policy_hash"] = f"sha256:{payload['sha256']}"
    out["canonical_policy_version"] = f"doctrine-{payload['lines']}L"
    out["doctrine"] = payload
    out["errors"] = list(errors)
    return out
