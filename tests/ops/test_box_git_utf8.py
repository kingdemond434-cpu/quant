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


def test_trust_paths_read_git_as_bytes_only() -> None:
    """MF-6: the readers that feed the trust hash never use text mode: bytes, strict UTF-8."""
    for rel in ("ops/box_git/pin_writer.py", "ops/box_git/protect.py"):
        assert "text=True" not in (ROOT / rel).read_text(encoding="utf-8"), rel
    loop = ast.parse((ROOT / "ops/box_git/box_loop.py").read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(loop) if isinstance(n, ast.FunctionDef)
              and n.name == "trust_status")
    assert "text=True" not in ast.unparse(fn) and "strict_git" in ast.unparse(fn)


def test_a_non_utf8_frozen_file_is_unmeasured_never_replaced(tmp_path: Path) -> None:
    import json
    import subprocess
    import sys

    import pytest
    sys.path.insert(0, str(ROOT))
    from ops.box_git import trust_check as T

    repo = tmp_path / "r"
    repo.mkdir()
    def g(*a: str) -> None:
        subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True)
    g("init", "-q", "-b", "main")
    g("config", "user.email", "t@x")
    g("config", "user.name", "t")
    pol = {"files": ["keys/*"], "grow_only": [], "symbols": {}}
    (repo / "keys").mkdir()
    (repo / "keys" / "a").write_bytes(b"key \x9d one\n")
    (repo / T.POLICY_PATH).parent.mkdir(parents=True, exist_ok=True)
    (repo / T.POLICY_PATH).write_text(json.dumps(pol))
    g("add", "-A")
    g("commit", "-q", "-m", "c")
    git = T.strict_git("git", "-C", str(repo))
    with pytest.raises(T.Unmeasured):
        T.t_hash(git, "HEAD", pol)
    with pytest.raises(T.Unmeasured):
        git("show", "HEAD:no/such/file")
