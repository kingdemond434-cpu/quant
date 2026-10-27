"""THE SIGN TRAIN RE-PINS QB-002 EXACTLY AND NOTHING ELSE.

`scripts/sign_train.py` exists because the re-sign and the QB-002 re-pin came apart by hand
(#329). These cases drive its two pure pieces: `repin` on the shipped quantbench.py source, and
`moved_files` on a scratch tree.
"""
from __future__ import annotations

import ast
import importlib.util
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
            return ast.literal_eval(node.value)
    raise AssertionError(name)


@pytest.mark.parametrize("name", sorted(st.ROTATIONS.values()))
def test_repin_moves_to_and_signer_and_keeps_from(name: str) -> None:
    before = _constant(SRC, name)
    after_src = st.repin(SRC, name, "a" * 64)
    after = _constant(after_src, name)
    assert after == {"path": before["path"], "from": before["from"], "to": "a" * 64,
                     "signed_by": "principal"}
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
    signed = {"files": {"a.py": st.full_sha("a.py", tmp_path)[:16],
                        "b.py": "0" * 16, "gone.py": "1" * 16}}
    assert list(st.moved_files(signed, tmp_path)) == ["b.py"]
