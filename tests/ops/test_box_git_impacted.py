"""Impacted-test selection for box CI: narrow only when traced, wide whenever in doubt."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ops.box_git import impacted as I  # noqa: E402


def _repo(tmp: Path) -> Path:
    files = {
        "libs/__init__.py": "",
        "libs/a.py": "X = 1\n",
        "libs/b.py": "from libs.a import X\n",
        "libs/c.py": "Y = 2\n",
        "tests/test_b.py": "from libs.b import X\n",
        "tests/test_c.py": "import libs.c\n",
        "tests/conftest.py": "",
        "data/table.json": "{}",
        "README.md": "x",
    }
    for rel, body in files.items():
        p = tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)
    return tmp


def test_a_change_selects_the_tests_that_reach_it_transitively(tmp_path: Path) -> None:
    r = _repo(tmp_path)
    assert I.select(r, ["libs/a.py"]) == ["tests/test_b.py"]
    assert I.select(r, ["libs/c.py"]) == ["tests/test_c.py"]


def test_a_changed_test_selects_itself(tmp_path: Path) -> None:
    assert I.select(_repo(tmp_path), ["tests/test_c.py"]) == ["tests/test_c.py"]


def test_docs_only_selects_nothing(tmp_path: Path) -> None:
    assert I.select(_repo(tmp_path), ["README.md"]) == []


def test_anything_untraceable_selects_everything(tmp_path: Path) -> None:
    r = _repo(tmp_path)
    for c in (["tests/conftest.py"], ["pyproject.toml"], ["data/table.json"], ["libs/gone.py"]):
        assert I.select(r, c) == I.ALL, c
    (r / "libs/a.py").write_text("def (:\n")
    assert I.select(r, ["libs/a.py"]) == I.ALL


def test_the_real_repo_resolves_its_own_spellings() -> None:
    got = I.select(ROOT, ["ops/box_git/protect.py"])
    assert got != I.ALL and "tests/ops/test_box_git_protect.py" in got
