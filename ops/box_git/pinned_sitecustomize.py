"""The pinned adopter's runtime fence (r24.2, Audit C4): installed as sitecustomize.py in the
guard's own venv (C:\\ProgramData\\QuantBox\\guard\\adopt\\venv) by install_guard.ps1.

Inert unless QUANT_ADOPT_PINNED=1. Then, for the life of the interpreter:

* any import whose source lies under QUANT_LEDGER_ROOT (the live tree quantrun can write)
  raises ImportError -- the tree is data to the adopter, never code;
* any unpickling of a global (pickle, joblib, numpy allow_pickle) raises RuntimeError;
* any subprocess or os.system/exec whose executable or a file argument lies under that root and
  is a script or binary (.py .pyw .ps1 .psm1 .bat .cmd .exe .dll .vbs .js) raises RuntimeError.

It does not decide anything: a refusal makes the adoption fail closed, and the adopter's log says
which path was refused. sys._quant_pinned_fence is set so Adopt-And-Seal can see it is armed.
"""
from __future__ import annotations

import contextlib
import os
import sys
from typing import Any

_EXEC_EXT = (".py", ".pyw", ".pyc", ".ps1", ".psm1", ".bat", ".cmd", ".exe", ".dll", ".vbs", ".js")


def _norm(p: str) -> str:
    return os.path.normcase(os.path.abspath(p)).rstrip("\\/") + os.sep


def _under(path: Any, root: str) -> bool:
    if not isinstance(path, (str, bytes, os.PathLike)):
        return False
    try:
        s = os.fsdecode(path)
    except (TypeError, ValueError):
        return False
    if not s:
        return False
    try:
        return _norm(s).startswith(root)
    except (TypeError, ValueError):
        return False


def _arm(root_env: str) -> None:
    root = _norm(root_env)

    class _Fence:
        """Asks the other finders, then refuses any spec that would load from the tree."""

        @staticmethod
        def find_spec(name: str, path: Any = None, target: Any = None) -> Any:
            for f in list(sys.meta_path):
                if f is fence:
                    continue
                find = getattr(f, "find_spec", None)
                if find is None:
                    continue
                spec = find(name, path, target)
                if spec is None:
                    continue
                locs = [spec.origin, *(spec.submodule_search_locations or [])]
                bad = [x for x in locs if x not in (None, "built-in", "frozen") and _under(x, root)]
                if bad:
                    raise ImportError(
                        f"pinned fence: {name} would load from the live tree ({bad[0]})")
                return spec
            return None

    fence: Any = _Fence
    sys.meta_path.insert(0, fence)

    def _args(args: Any) -> list[Any]:
        if isinstance(args, (list, tuple)):
            return list(args)
        if isinstance(args, (str, bytes)):
            return [x.strip('"') for x in os.fsdecode(args).split()]
        return [args]

    def _hook(event: str, args: tuple[Any, ...]) -> None:
        if event == "pickle.find_class":
            # tree files are data read as JSON or text: nothing is ever unpickled (incl. joblib,
            # numpy allow_pickle), because a pickle is code
            raise RuntimeError(f"pinned fence: refused to unpickle {args[0]}.{args[1]}")
        if event == "subprocess.Popen":
            cand = [args[0], *_args(args[1])]
        elif event in ("os.system", "os.exec", "os.posix_spawn", "os.spawn", "os.startfile"):
            cand = [*(_args(args[0]) if args else []), *(_args(args[1]) if len(args) > 1 else [])]
        else:
            return
        for c in cand:
            if _under(c, root) and os.fsdecode(c).lower().endswith(_EXEC_EXT):
                raise RuntimeError(
                    f"pinned fence: refused to run {os.fsdecode(c)} from the live tree")

    sys.addaudithook(_hook)
    sys._quant_pinned_fence = True  # type: ignore[attr-defined]


if os.environ.get("QUANT_ADOPT_PINNED") == "1" and os.environ.get("QUANT_LEDGER_ROOT"):
    _arm(os.environ["QUANT_LEDGER_ROOT"])

# a sitecustomize the copied site-packages already carried keeps working
with contextlib.suppress(ImportError):
    import sitecustomize_orig  # type: ignore[import-not-found]  # noqa: F401
