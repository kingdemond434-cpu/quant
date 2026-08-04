"""R0060/R0067 fence: the Upbit alignment policy has exactly ONE executable copy.

The 2026-07-29 fix declared "both scripts now import the single source" while two more copies
(fusion_engine, signal_halflife) kept keying the raw candle field, and one of them printed a
contaminated "kimchi STRENGTHENING" row during the very audit that had refuted kimchi at depth.
A fourth copy in backfill_kimchi survived even that sweep -- and because the deep-history backfill
is what the live collector gets SCREENED AGAINST, a private keying there is the worst place for
one: the collector and its own benchmark can disagree silently. This pins the count at one.

WHY THIS READS THE AST AND NOT THE RAW TEXT. The first version substring-scanned the file, so it
could not tell a keying copy from a docstring that merely NAMES the field -- and the honest fix for
the 07-29 regression had to explain that field in prose. A fence that forces organs to stop
describing their own failure modes is a fence that gets deleted; the vocabulary is widened to
admit prose, never satisfied by rewording the organ. Comments are absent from the AST for free;
docstrings are excluded explicitly. What is left is what actually executes.
"""
from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SINGLE_SOURCE = "libs/research/upbit_data.py"
_FIELD = "candle_date_time_utc"


def _docstring_nodes(tree: ast.AST) -> set[int]:
    """id() of every string node that is a module/class/function docstring."""
    out: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            body = getattr(node, "body", None)
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                out.add(id(body[0].value))
    return out


def _executable_uses(path: Path) -> bool:
    """True if the raw candle field appears in code (not a docstring, not a comment)."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except (OSError, SyntaxError):
        return False
    skip = _docstring_nodes(tree)
    return any(
        isinstance(n, ast.Constant) and isinstance(n.value, str)
        and _FIELD in n.value and id(n) not in skip
        for n in ast.walk(tree)
    )


def test_candle_field_has_exactly_one_executable_copy() -> None:
    offenders = [
        p.relative_to(_ROOT).as_posix()
        for base in ("libs", "scripts")
        for p in sorted((_ROOT / base).rglob("*.py"))
        if _executable_uses(p)
    ]
    assert offenders == [_SINGLE_SOURCE], (
        f"The Upbit keying must live ONLY in {_SINGLE_SOURCE}; found: {offenders}. "
        "Import upbit_daily_utc_keyed() / upbit_daily_history() instead of re-deriving the join "
        "(R0060, R0067). Naming the field in a docstring is fine -- keying on it is not."
    )


def test_fence_detects_a_planted_copy(tmp_path: Path) -> None:
    """The fence's own positive control: it must FAIL on a real copy and PASS on prose.

    A governance check that has never been shown to fire on the thing it forbids is not a fence,
    it is a comment -- and this one shipped for two days reading a docstring as a violation while
    the actual fourth copy sat three lines below it.
    """
    real_copy = tmp_path / "copy.py"
    real_copy.write_text(f'def f(r):\n    return r["{_FIELD}"][:10]\n', encoding="utf-8")
    assert _executable_uses(real_copy), "fence blind to an executable keying copy"

    prose_only = tmp_path / "prose.py"
    prose_only.write_text(f'"""Explains that {_FIELD} is a UTC date."""\n# and in a comment too:'
                          f' {_FIELD}\nX = 1\n', encoding="utf-8")
    assert not _executable_uses(prose_only), "fence fires on prose -- it will get switched off"
