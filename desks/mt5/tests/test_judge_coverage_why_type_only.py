"""JUDGE_COVERAGE.json publishes an exception's TYPE, never its text.

An exception message can carry a filesystem path, a host or a credential. Every `why` that
judge_coverage builds from a caught exception is therefore `type(exc).__name__` alone.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
if str(DESK) not in sys.path:
    sys.path.insert(0, str(DESK))

from research import judge_coverage as coverage  # noqa: E402

SECRET = "fake-token-for-test-only"  # noqa: S105 - a stand-in, not a credential
HOST = "db.internal.example"


class _Leaky(Exception):
    pass


def _assert_type_only(why: object, name: str) -> None:
    text = str(why)
    assert text == name or text.endswith(f": {name}") or text == f"save failed: {name}", text
    assert SECRET not in text and HOST not in text and "/data/secrets" not in text


def test_missing_ledger_publishes_only_the_error_type(tmp_path: Path) -> None:
    ledger = tmp_path / "data" / "secrets" / HOST / f"{SECRET}.jsonl"   # never created
    out = coverage.learn_priors(ledger, limit=coverage.LEARN_TAIL + 1, state_dir=tmp_path)
    assert out["status"] == "UNMEASURED"
    _assert_type_only(out["why"], "FileNotFoundError")


def test_a_raising_scorer_publishes_only_the_error_type(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    class _Dk:
        @staticmethod
        def score(rows: object) -> dict[str, object]:
            raise _Leaky(f"connect https://{HOST}/data/secrets/key={SECRET} failed")

    monkeypatch.setattr(coverage, "_docket_keff", lambda: _Dk)
    out = coverage.keff_stamp([{"_keff": 1.0}])
    assert out["status"] == "UNMEASURED"
    _assert_type_only(out["why"], "_Leaky")


def test_no_except_handler_formats_the_exception_into_a_why() -> None:
    """Source guard: inside every `except ... as exc`, a `why` value may name the type only."""
    tree = ast.parse(Path(coverage.__file__).read_text("utf-8"))
    leaks: list[int] = []
    for handler in ast.walk(tree):
        if not isinstance(handler, ast.ExceptHandler) or not handler.name:
            continue
        bound = handler.name
        for node in ast.walk(handler):
            values: list[ast.AST] = []
            if isinstance(node, ast.keyword) and node.arg == "why":
                values.append(node.value)
            if isinstance(node, ast.Dict):
                values += [v for k, v in zip(node.keys, node.values, strict=True)
                           if isinstance(k, ast.Constant) and k.value == "why"]
            for v in values:
                for sub in ast.walk(v):
                    if isinstance(sub, ast.Name) and sub.id == bound:
                        parent_ok = any(
                            isinstance(p, ast.Call) and isinstance(p.func, ast.Name)
                            and p.func.id == "type" and p.args and p.args[0] is sub
                            for p in ast.walk(v))
                        if not parent_ok:
                            leaks.append(sub.lineno)
    assert not leaks, f"exception text reaches a published `why` at lines {leaks}"
