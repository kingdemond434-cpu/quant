"""Every text-mode subprocess in the box gate decodes UTF-8 explicitly. The Windows box defaults to
cp1252: undecoded git output pinned a trust hash no other platform reproduces (2026-11-20)."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FILES = [*sorted((ROOT / "ops" / "box_git").glob("*.py")), ROOT / ".github/scripts/audit_gate.py"]


def test_text_mode_subprocess_always_names_utf8() -> None:
    bad = []
    for f in FILES:
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call):
                continue
            kw = {k.arg: k.value for k in node.keywords if k.arg}
            text = kw.get("text") or kw.get("universal_newlines")
            if isinstance(text, ast.Constant) and text.value is True:
                enc = kw.get("encoding")
                if not (isinstance(enc, ast.Constant) and enc.value == "utf-8"):
                    bad.append(f"{f.relative_to(ROOT)}:{node.lineno}")
    assert not bad, bad
