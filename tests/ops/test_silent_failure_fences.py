"""THE TWO COMPANION FENCES to the write-or-explain contract.

`check_bare_excepts` catches the same disease one layer down (a write whose failure was caught
and discarded), and `check_box_reversion` catches it one layer up (builder work the hourly
adoption is about to revert with no message at all). Both ship with the contract because all
three are the same sentence: a loss that produces no output is a loss nobody can act on.
"""
from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


be = _load("check_bare_excepts")
br = _load("check_box_reversion")

#: One AST sweep of ~2,300 files, shared by the two tests that need it. Scanning twice doubles
#: the suite's cost here for no extra information.
_AUDIT: dict[str, object] = {}


def _audit() -> dict[str, object]:
    if not _AUDIT:
        _AUDIT.update(be.build_report())
    return _AUDIT


# ----------------------------------------------------------------- check_bare_excepts
def _findings(src: str) -> list[dict[str, object]]:
    tree = ast.parse(src)
    out: list[dict[str, object]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        kind, wrote = be._writes(node.body)
        if not kind:
            continue
        for h in node.handlers:
            if be._is_blind(h) and be._is_mute(h):
                out.append({"kind": kind, "writes": wrote, "line": h.lineno})
    return out


def test_a_blind_mute_handler_around_a_write_is_caught() -> None:
    assert _findings("try:\n    p.write_text(x)\nexcept Exception:\n    pass\n")
    assert _findings("try:\n    p.write_text(x)\nexcept:\n    pass\n")
    assert _findings('try:\n    open(p, "w").write(x)\nexcept Exception:\n    pass\n')


@pytest.mark.parametrize("src", [
    # SPEAKS: it logs, so it is doing its job
    "try:\n    p.write_text(x)\nexcept Exception as exc:\n    print(exc)\n",
    # RE-RAISES
    "try:\n    p.write_text(x)\nexcept Exception:\n    raise\n",
    # NARROW and named
    "try:\n    p.write_text(x)\nexcept OSError as exc:\n    log(exc)\n",
    # RETURNS A REASON rather than None
    'try:\n    p.write_text(x)\nexcept Exception as exc:\n    return {"why": str(exc)}\n',
])
def test_a_handler_that_says_something_is_not_a_finding(src: str) -> None:
    assert not _findings(src)


@pytest.mark.parametrize("src", [
    # pandas, not the filesystem -- these produced four of the first findings and none was a write
    'try:\n    df.rename(columns={"a": "b"})\nexcept Exception:\n    pass\n',
    'try:\n    series.rename("net")\nexcept Exception:\n    pass\n',
    'try:\n    rows.append(v)\nexcept Exception:\n    pass\n',
    'try:\n    s.replace("a", "b")\nexcept Exception:\n    pass\n',
    # a READ-mode open is not a write
    'try:\n    open(p, "r").read()\nexcept Exception:\n    pass\n',
])
def test_the_scanner_does_not_cry_wolf(src: str) -> None:
    """A fence whose findings are mostly noise gets switched off (L1.43), so the shape of the
    call has to separate `Path.replace(target)` from `str.replace(a, b)`."""
    assert not _findings(src)


def test_writes_and_donations_are_reported_apart() -> None:
    assert _findings("try:\n    p.write_text(x)\nexcept Exception:\n    pass\n")[0]["kind"] \
        == "FILE_WRITE"
    assert _findings("try:\n    donate(row)\nexcept Exception:\n    pass\n")[0]["kind"] \
        == "DONATION"


def test_the_file_write_class_stays_at_zero() -> None:
    """THE RATCHET (L1.50). The 2026-09-23 audit cleared every swallowed FILE_WRITE on the
    artifact surface; this pins the class at zero so a new one reddens the gate immediately.
    The DONATION findings are deliberately outside this ratchet and are still reported."""
    rep = _audit()
    assert rep["files_scanned"] > 500, "the scan found almost nothing -- scope is broken"
    assert rep["n_file_write"] == 0, (
        "a swallowed FILE_WRITE is back: "
        + "; ".join(f"{f['file']}:{f['line']}" for f in rep["findings"]
                    if f["kind"] == "FILE_WRITE"))


def test_the_gate_mode_never_silences_the_donation_findings() -> None:
    rep = _audit()
    assert rep["n_swallowed_writes"] == rep["n_file_write"] + rep["n_donation"]
    assert rep["findings"], "the report dropped its findings list"


# ---------------------------------------------------------------- check_box_reversion
def test_state_paths_are_not_reversion_risk_and_code_paths_are() -> None:
    """The adoption KEEPS state and reverts code, so the fence must classify the same way it
    does -- flagging the hundreds of state files the box rewrites every hour would be noise."""
    from libs.ops.release import is_state_path
    assert is_state_path("desks/mt5/reports/COVERAGE_TENSOR.json")
    assert is_state_path("desks/mt5/data/sleeves.json")
    assert not is_state_path("desks/mt5/research/hourly_cycle.py")
    assert not is_state_path("libs/ops/write_or_explain.py")


def test_a_clean_tree_reads_clean_and_a_dirty_one_does_not(tmp_path: Path) -> None:
    import subprocess

    def git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=tmp_path, check=True,
                       capture_output=True, text=True, timeout=120)

    git("init", "-q")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "t")
    (tmp_path / "libs").mkdir()
    (tmp_path / "libs" / "thing.py").write_text("x = 1\n", encoding="utf-8")
    git("add", "libs/thing.py")
    git("commit", "-qm", "seed")
    assert br.build_report(root=tmp_path)["status"] == "CLEAN"

    # a CODE edit is at risk...
    (tmp_path / "libs" / "thing.py").write_text("x = 2\n", encoding="utf-8")
    rep = br.build_report(root=tmp_path)
    assert rep["status"] == "AT_RISK"
    assert any(r["path"] == "libs/thing.py" for r in rep["uncommitted"])

    # ...and a STATE write is not
    git("checkout", "--", "libs/thing.py")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "ledger.jsonl").write_text("{}\n", encoding="utf-8")
    rep = br.build_report(root=tmp_path)
    assert rep["status"] == "CLEAN", f"state path flagged: {rep['uncommitted']}"
    assert rep["state_paths_ignored"] >= 1


def test_an_untracked_code_file_is_at_risk_too(tmp_path: Path) -> None:
    """The case that costs a builder a whole file: a NEW module never added to the index."""
    import subprocess
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True, capture_output=True,
                   timeout=120)
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "brand_new.py").write_text("print(1)\n", encoding="utf-8")
    rep = br.build_report(root=tmp_path)
    assert rep["status"] == "AT_RISK"
    assert any(r["path"] == "scripts/brand_new.py" for r in rep["uncommitted"])


def test_the_fence_never_touches_the_tree() -> None:
    """Four builders are live. A fence that 'fixed' this by committing would be staging other
    people's work under its own name, which is a worse failure than the one it reports."""
    src = (ROOT / "scripts" / "check_box_reversion.py").read_text(encoding="utf-8")
    body = src.split('def _git(', 1)[1]
    for forbidden in ('"commit"', '"stash"', '"checkout"', '"push"', '"reset"', '"add"'):
        assert forbidden not in body, f"the reversion fence must never run git {forbidden}"


def test_minutes_to_adoption_names_the_real_deadline() -> None:
    from datetime import UTC, datetime
    assert br.ADOPT_MINUTE == 12
    assert br._minutes_to_adoption(datetime(2026, 9, 23, 10, 5, tzinfo=UTC)) == 7
    assert br._minutes_to_adoption(datetime(2026, 9, 23, 10, 12, tzinfo=UTC)) == 0
    assert br._minutes_to_adoption(datetime(2026, 9, 23, 10, 30, tzinfo=UTC)) == 42
