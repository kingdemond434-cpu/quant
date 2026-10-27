"""THE SIGN TRAIN RE-PINS QB-002 EXACTLY AND NOTHING ELSE.

`scripts/sign_train.py` exists because the re-sign and the QB-002 re-pin came apart by hand
(#329). These cases drive its two pure pieces: `repin` on the shipped quantbench.py source, and
`moved_files` on a scratch tree.
"""

from __future__ import annotations

import ast
import importlib.util
import io
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("sign_train", ROOT / "scripts" / "sign_train.py")
assert SPEC and SPEC.loader
st = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(st)

SRC = (ROOT / "desks" / "mt5" / "research" / "quantbench.py").read_text("utf-8")


def _constant(src: str, name: str) -> dict[str, str]:
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", None) == name:
            value: dict[str, str] = ast.literal_eval(node.value)
            return value
    raise AssertionError(name)


@pytest.mark.parametrize("name", sorted(st.ROTATIONS.values()))
def test_repin_moves_to_and_signer_and_keeps_from(name: str) -> None:
    before = _constant(SRC, name)
    after_src = st.repin(SRC, name, "a" * 64)
    after = _constant(after_src, name)
    assert after == {
        "path": before["path"],
        "from": before["from"],
        "to": "a" * 64,
        "signed_by": "principal",
    }
    for other in set(st.ROTATIONS.values()) - {name}:
        assert _constant(after_src, other) == _constant(SRC, other)


def test_every_rotation_path_matches_its_constant() -> None:
    for path, name in st.ROTATIONS.items():
        assert _constant(SRC, name)["path"] == path


def test_repin_refuses_an_unknown_constant() -> None:
    with pytest.raises(ValueError):
        st.repin(SRC, "NO_SUCH_SEAL_ROTATION", "a" * 64)


def test_moved_files_reads_crlf_as_unchanged(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_bytes(b"x = 1\r\n")
    (tmp_path / "b.py").write_bytes(b"y = 2\n")
    signed = {
        "files": {
            "a.py": st.full_sha("a.py", tmp_path)[:16],
            "b.py": "0" * 16,
            "gone.py": "1" * 16,
        }
    }
    moved = st.moved_files(signed, tmp_path)
    assert moved == {"b.py": st.full_sha("b.py", tmp_path), "gone.py": "<absent>"}


def test_binding_names_every_moved_file_with_its_audited_bytes() -> None:
    a, b = "a" * 64, "b" * 64
    assert st.binding_problems({"x.py": a}, {"x.py": a}) == []
    assert st.binding_problems({"x.py": a}, {}) != []
    assert st.binding_problems({"x.py": a}, {"x.py": b}) != []
    assert st.binding_problems({}, {"x.py": a}) != []
    assert st.binding_problems({"x.py": a, "y.py": b}, {"x.py": a}) != []


def test_denied_bytes_are_refused_even_when_named() -> None:
    bad = "1aa4b33f" + "0" * 56
    assert st.binding_problems({"x.py": bad}, {"x.py": bad}) != []


def test_expect_wants_a_full_sha256() -> None:
    assert st.parse_expect(["x.py=" + "A" * 64]) == {"x.py": "a" * 64}
    for item in ("x.py=abc", "x.py", "x.py=" + "g" * 64):
        with pytest.raises(ValueError):
            st.parse_expect([item])


def test_no_terminal_no_sign(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("whatever\n"))
    assert st._confirm({"x.py": "a" * 64}) is False


def test_typed_hash_must_match(monkeypatch: pytest.MonkeyPatch) -> None:
    class Tty(io.StringIO):
        def isatty(self) -> bool:
            return True

    monkeypatch.setattr("sys.stdin", Tty())
    monkeypatch.setattr("builtins.input", lambda _: "a" * 12)
    assert st._confirm({"x.py": "a" * 64}) is True
    monkeypatch.setattr("builtins.input", lambda _: "b" * 12)
    assert st._confirm({"x.py": "a" * 64}) is False


def test_repin_writes_the_signer() -> None:
    name = "GAUNTLET_SEAL_ROTATION"
    after = _constant(st.repin(SRC, name, "c" * 64, st.AUDITOR), name)
    assert after["signed_by"] == "auditor-clear" and after["to"] == "c" * 64


def test_only_committed_clear_rows_with_a_report_count() -> None:
    a, b = "a" * 64, "b" * 64
    text = "\n".join(
        [
            json.dumps({"path": "x.py", "sha256": a, "verdict": "CLEAR", "report": "R1"}),
            json.dumps({"path": "x.py", "sha256": b, "verdict": "HOLD", "report": "R2"}),
            json.dumps({"path": "y.py", "sha256": b, "verdict": "CLEAR"}),
            "not json",
        ]
    )
    assert st.parse_clears(text) == {"x.py": {a}}


def test_the_audit_signs_only_cleared_bytes() -> None:
    a, b = "a" * 64, "b" * 64
    clears = {"x.py": {a}}
    expect = st.cleared_expect({"x.py": a, "y.py": b}, clears)
    assert expect == {"x.py": a}
    assert st.binding_problems({"x.py": a, "y.py": b}, expect) != []
    assert st.binding_problems({"x.py": a}, expect) == []
