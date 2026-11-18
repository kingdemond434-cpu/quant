"""rea lane Z2d: the supply-chain audit flags what it says, fails closed, and repairs exactly."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "supply_chain_audit", ROOT / ".github/scripts/supply_chain_audit.py"
)
assert _spec and _spec.loader
sca = importlib.util.module_from_spec(_spec)
sys.modules["supply_chain_audit"] = sca
_spec.loader.exec_module(sca)

SHA = "a" * 40


def _tree(tmp_path: Path, req: str = "", wf: str = "", pyproject: str | None = None) -> Path:
    (tmp_path / ".github/workflows").mkdir(parents=True)
    (tmp_path / ".github/workflows/ci.yml").write_text(
        wf or f"steps:\n  - uses: actions/checkout@{SHA} # v4\n"
    )
    if req:
        (tmp_path / "requirements.txt").write_text(req)
    if pyproject is not None:
        (tmp_path / "pyproject.toml").write_text(pyproject)
    return tmp_path


def _codes(findings: list[Any]) -> list[tuple[str, str]]:
    return [(f.code, f.subject) for f in findings]


def test_clean_tree_passes(tmp_path: Path) -> None:
    root = _tree(tmp_path, req="numpy==2.4.6 \\\n    --hash=sha256:abc\n")
    assert sca.run_audit(root) == []
    assert sca.main(["--root", str(root)]) == 0


def test_mutable_action_ref_is_flagged_but_local_and_docker_are_not(tmp_path: Path) -> None:
    wf = (
        "jobs:\n  a:\n    steps:\n      - uses: actions/checkout@v4\n"
        "      - uses: ./local-action\n      - uses: docker://alpine:3\n"
        f"      - uses: 'owner/act/sub@{SHA}'\n"
    )
    found = sca.run_audit(_tree(tmp_path, wf=wf))
    assert _codes(found) == [("ACTION_NOT_SHA", "actions/checkout")]
    assert found[0].line == 4


def test_python_pin_levels(tmp_path: Path) -> None:
    req = (
        "# comment\nrequests\npandas>=2.2\nscipy==1.17.1\n-r other.txt\n"
        "numpy==2.4.6 --hash=sha256:x\npandas==2.3.3\n"
    )
    found = sca.run_audit(_tree(tmp_path, req=req))
    assert ("PY_UNPINNED", "requests") in _codes(found)
    assert ("PY_NOT_EXACT", "pandas") in _codes(found)
    assert ("PY_NO_HASH", "scipy") in _codes(found)
    assert ("PY_DUPLICATE", "pandas") in _codes(found)
    assert not any(f.subject == "numpy" for f in found)


def test_typosquat_is_flagged_and_real_names_are_not(tmp_path: Path) -> None:
    h = " --hash=sha256:x\n"
    req = f"reqeusts==1.0{h}pandsa==1.0{h}scikit-learn==1.4{h}PyYAML==6.0.3{h}"
    found = sca.run_audit(_tree(tmp_path, req=req))
    squats = {f.subject: f.detail for f in found if f.code == "PY_TYPOSQUAT"}
    assert set(squats) == {"reqeusts", "pandsa"}
    assert "requests" in squats["reqeusts"]


def test_pyproject_ranges_are_fine_but_a_bare_dependency_is_not(tmp_path: Path) -> None:
    py = (
        '[project]\nname="x"\ndependencies = ["numpy>=2,<3", "requests"]\n'
        '[project.optional-dependencies]\ndev = ["pytest>=9,<10"]\n'
    )
    found = sca.run_audit(_tree(tmp_path, pyproject=py))
    assert _codes(found) == [("PY_UNPINNED", "requests")]


def test_unreadable_manifest_fails_closed(tmp_path: Path) -> None:
    root = _tree(tmp_path, pyproject="[project\nthis is not toml")
    found = sca.run_audit(root)
    assert [f.code for f in found] == ["SCAN_ERROR"]
    assert sca.main(["--root", str(root)]) == 1


def test_no_workflows_fails_closed(tmp_path: Path) -> None:
    (tmp_path / "requirements.txt").write_text("numpy==1 --hash=sha256:x\n")
    assert [f.code for f in sca.run_audit(tmp_path)] == ["SCAN_ERROR"]


def test_fix_actions_rewrites_tags_to_shas_and_keeps_layout(tmp_path: Path) -> None:
    wf = (
        "steps:\n      - uses: actions/checkout@v4\n        with: {x: 1}\n"
        "        uses: actions/setup-python@v5\n"
    )
    root = _tree(tmp_path, wf=wf)
    calls: list[tuple[str, str]] = []

    def resolver(action: str, ref: str, token: str | None = None) -> str:
        calls.append((action, ref))
        return ("b" if "checkout" in action else "c") * 40

    assert sca.fix_actions(root, resolver=resolver) == [".github/workflows/ci.yml"]
    text = (root / ".github/workflows/ci.yml").read_text()
    assert f"      - uses: actions/checkout@{'b' * 40} # v4\n" in text
    assert f"        uses: actions/setup-python@{'c' * 40} # v5\n" in text
    assert "        with: {x: 1}\n" in text
    assert sca.run_audit(root) == []
    assert sca.fix_actions(root, resolver=resolver) == []  # idempotent


def test_this_repo_has_every_action_pinned_to_a_sha() -> None:
    """The fix shipped with the audit; a new tag-pinned action is a regression."""
    found = [
        f for f in sca.run_audit(ROOT) if f.code in ("ACTION_NOT_SHA", "SCAN_ERROR", "PY_TYPOSQUAT")
    ]
    assert found == [], sca.to_markdown(found)
