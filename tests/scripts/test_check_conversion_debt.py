"""The conversion-debt ratchet: it may only fall, and it cannot be raised by hand.

EVERY INPUT IS SYNTHETIC -- a fresh registry and a fresh ratchet file in `tmp_path`. Nothing here
reads or writes the desk's own registry, and nothing here touches a tracked file.

THE LOAD-BEARING TESTS.

`test_the_ratchet_cannot_be_raised_by_hand` is the whole fence. A ratchet whose only record is
its current value is defeated by one `json.dump`, so the enforced ceiling is
`min(ceiling, lowest_ever)` and an edit that raises either number is inert. Without this the law
is a habit, and habits are what the ratchet exists to replace.

`test_debt_above_the_ratchet_is_a_breach` and `test_the_ratchet_falls_when_the_debt_falls` pin
the two directions: up fails the gate at rc 2, down lowers the ceiling automatically with no
session's permission.

`test_an_absent_registry_is_unmeasured_and_never_a_pass` is L1.28a: a checkout with no registry
reports UNMEASURED at rc 1 -- a real answer about this machine, never a clean bill of health.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# LOADED BY PATH, not by `import scripts.<name>`. `tests/scripts/__init__.py` makes a REGULAR
# package called `scripts`, and a regular package beats the repo root's namespace package
# (`scripts/` has no `__init__.py`) wherever it sits on the path -- so `import scripts.X` resolves
# to the TEST directory and raises ModuleNotFoundError for every real checker. This is the same
# route `test_build_zentech_state` already takes for the same reason.
_SPEC = importlib.util.spec_from_file_location(
    "check_conversion_debt", ROOT / "scripts" / "check_conversion_debt.py")
assert _SPEC and _SPEC.loader
ccd = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ccd)

from libs.moat import registry as R  # noqa: E402


@pytest.fixture
def registry(tmp_path: Path):
    """A registry with a known, controllable conversion debt."""
    R.set_path(tmp_path / "reg.sqlite")
    conn = R.connect()
    try:
        yield conn
    finally:
        conn.close()
        R.set_path(None)


def _donate(conn, n: int, prefix: str = "d", age_h: float = 9.0) -> list[str]:
    """`n` candidates in status `donated` -- the debt component the mandate targets.

    BACK-DATED past the in-flight grace, because a row minted this second is work-in-progress and
    the ratchet deliberately does not count it (`conversion_maximiser.IN_FLIGHT_GRACE_H`). These
    tests are about the ratchet, so they plant rows that have already missed their turn.
    """
    old = (datetime.now(tz=UTC) - timedelta(hours=age_h)).isoformat()
    out = []
    for i in range(n):
        cid, _ = R.enqueue_candidate(family="range_reversion", symbol="TESTFX",
                                     params={"k": f"{prefix}{i}"}, origin="DESK",
                                     status="donated", candidate_id=f"{prefix}_{i}", conn=conn)
        conn.execute("UPDATE research_candidates SET created_at=? WHERE id=?", (old, cid))
        out.append(cid)
    conn.commit()
    return out


def _measure(tmp_path: Path, **kw) -> dict[str, Any]:
    return ccd.measure(kw.get("registry", R.path()), kw.get("ratchet", tmp_path / "ratchet.json"))


def test_the_first_measurement_seeds_the_ratchet(registry, tmp_path: Path) -> None:
    _donate(registry, 5)
    verdict = _measure(tmp_path)
    assert verdict["status"] == "SEEDED"
    assert verdict["rc"] == 0
    assert verdict["total_debt"] == 5
    assert verdict["ceiling_after"] == 5
    ccd._persist(verdict, tmp_path / "ratchet.json")
    doc = json.loads((tmp_path / "ratchet.json").read_text(encoding="utf-8"))
    assert doc["ceiling"] == doc["lowest_ever"] == 5
    assert doc["history"][-1]["total_debt"] == 5


def test_the_ratchet_falls_when_the_debt_falls(registry, tmp_path: Path) -> None:
    ids = _donate(registry, 6)
    ccd._persist(_measure(tmp_path), tmp_path / "ratchet.json")
    # Three rows become testable cells: the debt falls, so the ceiling must follow it down.
    for cid in ids[:3]:
        R.mark_candidate(cid, "queued", conn=registry, falsifier="re-judged and it fails")
    verdict = _measure(tmp_path)
    assert verdict["status"] == "OK"
    assert verdict["rc"] == 0
    assert verdict["total_debt"] == 3
    assert verdict["ceiling_before"] == 6
    assert verdict["ceiling_after"] == 3
    ccd._persist(verdict, tmp_path / "ratchet.json")
    assert ccd.effective_ceiling(
        json.loads((tmp_path / "ratchet.json").read_text(encoding="utf-8"))) == 3


def test_debt_above_the_ratchet_is_a_breach(registry, tmp_path: Path) -> None:
    _donate(registry, 2)
    ccd._persist(_measure(tmp_path), tmp_path / "ratchet.json")
    _donate(registry, 4, prefix="more")
    verdict = _measure(tmp_path)
    assert verdict["status"] == "BREACH"
    assert verdict["rc"] == 2
    assert verdict["total_debt"] == 6
    assert "ABOVE the ratchet" in verdict["why"]
    # The breach must NOT be laundered into the new normal.
    ccd._persist(verdict, tmp_path / "ratchet.json")
    doc = json.loads((tmp_path / "ratchet.json").read_text(encoding="utf-8"))
    assert ccd.effective_ceiling(doc) == 2


def test_the_ratchet_cannot_be_raised_by_hand(registry, tmp_path: Path) -> None:
    _donate(registry, 3)
    path = tmp_path / "ratchet.json"
    ccd._persist(_measure(tmp_path), path)
    assert ccd.effective_ceiling(json.loads(path.read_text(encoding="utf-8"))) == 3

    # Somebody edits the file to buy themselves room. It must buy nothing.
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["ceiling"] = 10_000
    path.write_text(json.dumps(doc), encoding="utf-8")
    assert ccd.effective_ceiling(json.loads(path.read_text(encoding="utf-8"))) == 3

    _donate(registry, 5, prefix="extra")
    verdict = _measure(tmp_path)
    assert verdict["status"] == "BREACH", "a hand-raised ceiling must not open the gate"
    assert verdict["rc"] == 2

    # And raising `lowest_ever` alone is just as inert, because the minimum of the pair wins.
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["lowest_ever"] = 9_999
    assert ccd.effective_ceiling(doc) == min(int(doc["ceiling"]), 9_999)


def test_a_reasoned_refusal_is_not_debt(registry, tmp_path: Path) -> None:
    ids = _donate(registry, 4)
    R.mark_candidate(ids[0], "retired", conn=registry,
                     rejection_reason="OFF_UNIVERSE: the universe mandate forbids this ground")
    verdict = _measure(tmp_path)
    assert verdict["total_debt"] == 3, (
        "a row refused for a named reason is disposed of, not owed")


def test_an_absent_registry_is_unmeasured_and_never_a_pass(tmp_path: Path) -> None:
    verdict = ccd.measure(tmp_path / "nothing.sqlite", tmp_path / "ratchet.json")
    assert verdict["status"] == "UNMEASURED"
    assert verdict["rc"] == 1
    assert "never a pass" in verdict["why"]
    assert "total_debt" not in verdict


def test_the_cli_exits_on_the_verdict(registry, tmp_path: Path, capsys) -> None:
    _donate(registry, 2)
    args = ["--registry", str(R.path()), "--ratchet", str(tmp_path / "ratchet.json")]
    assert ccd.main(args) == 0
    _donate(registry, 3, prefix="z")
    assert ccd.main(args) == 2
    out = capsys.readouterr().out
    assert "conversion debt: BREACH" in out


def test_the_fence_is_registered_in_the_law_gate() -> None:
    """An unwired fence is a defect (LAWS 7): it must run at every law-gate boundary."""
    source = (ROOT / "scripts" / "run_law_gate.py").read_text(encoding="utf-8")
    body = source.split("_STATE_FENCES", 1)[1]
    assert '("check_conversion_debt.py"' in body
