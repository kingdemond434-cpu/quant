"""Tests for the transitive-freshness fence (L1.55).

THE WIRING TESTS ARE THE POINT, for the reason the idle-cost suite gives: a suite that only
checked this fence's arithmetic would leave the original class free to come back. The class is
an artifact that is FRESH, well-formed, passes its min_rows floor, satisfies its L1.44 contract,
and was built entirely from a file that does not exist -- which is what `data/live_guard.json`
was on the day this was written, with every gate in the chain reporting green.

So four things are asserted: the fence catches the self-contradiction it exists for, it refuses
on an empty measurement set instead of reading OK, the two live repairs stay wired
(run_live_guard's ramp/stage_gate provenance, check_idle_cost's clamp-erasing defaults), and the
fence stays attached to the constitution, the build standard and the scheduler.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts import check_input_provenance as fence  # noqa: E402

# --- the fence's own logic --------------------------------------------------------------------

def _artifact(tmp_path: Path, name: str, obj: object) -> None:
    p = tmp_path / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj), "utf-8")


def _registry(tmp_path: Path, paths: list[str]) -> None:
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data/freshness_contracts.jsonl").write_text(
        "\n".join(json.dumps({"event": "contract", "path": p, "caller": "t"}) for p in paths),
        "utf-8")


@pytest.fixture()
def sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(fence, "_ROOT", tmp_path)
    monkeypatch.setattr(fence, "_REGISTRY", tmp_path / "data/freshness_contracts.jsonl")
    monkeypatch.setattr(fence, "_OUT", tmp_path / "data/input_provenance.json")
    return tmp_path


def test_fabricated_is_the_failing_state(sandbox: Path) -> None:
    """A declared-absent input published as measured is the contradiction, and it must fail."""
    _registry(sandbox, ["data/guard.json"])
    _artifact(sandbox, "data/guard.json", {
        "ramp": {"size_fraction": 0.1, "measured": True,
                 "provenance": [{"path": "data/ramp_state.json", "status": "ABSENT"}]}})
    rep = fence.build()
    assert rep["status"] == "FABRICATED"
    assert "ramp_state.json" in rep["next_action"]


def test_honest_gap_is_not_a_failure(sandbox: Path) -> None:
    """Declaring an absent input AND saying measured=false is a CORRECT artifact whose producer
    is missing. The defect is upstream; failing here would punish the honesty."""
    _registry(sandbox, ["data/guard.json"])
    _artifact(sandbox, "data/guard.json", {
        "ramp": {"size_fraction": 0.1, "measured": False,
                 "provenance": [{"path": "data/ramp_state.json", "status": "ABSENT"}]}})
    rep = fence.build()
    assert rep["status"] == "OK"
    assert rep["by_verdict"]["HONEST-GAP"] == 1


def test_undeclared_lowers_coverage_but_does_not_cry_wolf(sandbox: Path) -> None:
    """Coverage is a ratchet (L1.0) whose gap is the work queue; a fence red from day one gets
    switched off (L1.43)."""
    _registry(sandbox, ["data/a.json", "data/b.json"])
    _artifact(sandbox, "data/a.json", {"v": 1})
    _artifact(sandbox, "data/b.json", {
        "x": {"measured": True, "provenance": [{"path": "data/c.json", "status": "READ"}]}})
    rep = fence.build()
    assert rep["status"] == "PARTIAL"
    assert rep["coverage"] == 0.5
    assert "data/a.json" in rep["next_action"], "the undeclared artifact must be named"


def test_empty_measurement_set_is_unmeasured_never_ok(sandbox: Path) -> None:
    """L1.28a: zero examinable artifacts can never read OK."""
    _registry(sandbox, [])
    assert fence.build()["status"] == "UNMEASURED"


def test_absent_registry_is_unmeasured_not_ok(sandbox: Path) -> None:
    rep = fence.build()
    assert rep["status"] == "UNMEASURED"
    assert "ABSENT" in rep["detail"]


def test_nested_provenance_blocks_are_found(sandbox: Path) -> None:
    """A producer declares provenance PER DERIVED BLOCK; a top-level-only reader would score
    run_live_guard's two blocks as UNDECLARED."""
    _registry(sandbox, ["data/g.json"])
    _artifact(sandbox, "data/g.json", {
        "ramp": {"measured": False, "provenance": [{"path": "x", "status": "ABSENT"}]},
        "stage_gate": {"measured": False, "provenance": [{"path": "x", "status": "ABSENT"}]}})
    rep = fence.build()
    assert rep["by_verdict"]["HONEST-GAP"] == 1
    assert "ramp" in rep["artifacts"][0]["detail"]
    assert "stage_gate" in rep["artifacts"][0]["detail"]


def test_optional_absent_input_is_not_a_gap(sandbox: Path) -> None:
    _registry(sandbox, ["data/g.json"])
    _artifact(sandbox, "data/g.json", {
        "b": {"measured": True,
              "provenance": [{"path": "x", "status": "ABSENT", "required": False}]}})
    assert fence.build()["by_verdict"]["DECLARED"] == 1


def test_torn_registry_line_does_not_blind_the_fence(sandbox: Path) -> None:
    (sandbox / "data").mkdir(parents=True, exist_ok=True)
    (sandbox / "data/freshness_contracts.jsonl").write_text(
        '{"event": "contract", "path": "data/g.json"}\n{not json\n', "utf-8")
    _artifact(sandbox, "data/g.json", {"v": 1})
    assert fence.build()["n_consumed"] == 1


def test_foreign_pytest_paths_are_excluded(sandbox: Path) -> None:
    """85% of the live registry is pytest temp rows; measuring them would drown the signal."""
    _registry(sandbox, ["/tmp/pytest-of-quant/x.json", "data/g.json"])
    _artifact(sandbox, "data/g.json", {"v": 1})
    assert fence.build()["n_consumed"] == 1


# --- the wiring: these fail if the live repairs are reverted -----------------------------------

# THE PROVING INSTANCE WAS `scripts/run_live_guard.py`, AND IT IS GONE (2026-09-05).
#
# Three tests stood here. They pinned that run_live_guard's ramp and promotion gate declared their
# provenance through `Inputs`, and that the ramp was never read through `_load(_RAMP, {})` -- the
# idiom that returns the same default for a missing file as for an empty one. That organ was the
# retired crypto-exchange desk's Gate-0 size governor; it was deleted with the desk under the MT5
# universe mandate (2026-08-18), its cron row is retired in ops/crontab.manifest with the reason,
# and the alerts that paged on it went with it.
#
# THE TESTS ARE DELETED RATHER THAN REPOINTED, and that is the honest call rather than the
# convenient one. A wiring test buys its keep by naming a SPECIFIC repair on a SPECIFIC organ; the
# MT5 gateway has its own sizing path and has never committed this defect, so pointing these
# assertions at it would invent a regression site instead of guarding one. What must NOT be lost is
# the general law, and it is not lost: `check_input_provenance.py` scans the whole tree, the
# arithmetic tests above still prove it catches a fabricated measurement and refuses on an empty
# set, and `test_idle_cost_does_not_erase_clamps_when_the_guard_is_unreadable` below keeps a live
# repair of exactly this class fenced. If a future MT5 organ publishes a default as a measurement,
# the fence -- not a deleted test -- is what catches it.


def test_idle_cost_does_not_erase_clamps_when_the_guard_is_unreadable() -> None:
    """An unreadable live_guard.json used to default entries_allowed=True and frac=1.0 -- "no
    clamp" -- inside the very fence built to price the cost of caution. A dead guard read as a
    FREER desk than a live one."""
    src = (_ROOT / "scripts/check_idle_cost.py").read_text("utf-8")
    assert 'Inputs("check_idle_cost.live_guard")' in src
    assert "guard_measured" in src
    assert "unmeasured=True" in src, "the unknown-clamp row must survive"


def test_idle_cost_unmeasured_clamp_is_unpriced_not_zero() -> None:
    """L1.51: an unmeasured floor is NEVER 0% -- a zero holding prices the clamp as FREE.

    Asserted on the emitted row, not just the source: an unmeasured clamp must carry holds_usd
    None and priced False, so it reads as a defect to close rather than a free restraint.
    """
    from scripts import check_idle_cost as ic
    # a root with no live_guard.json at all: the guard is UNMEASURED by construction
    out = ic._clamps(root=_ROOT / "tests/governance/__nonexistent__",
                     floor_annual=0.05, idle_usd=1000.0, paper=True)
    unknown = [r for r in out if r.get("unmeasured")]
    assert unknown, "an unreadable guard must leave an UNKNOWN clamp row, not zero rows"
    for r in unknown:
        assert r["holds_usd"] is None, "a zero holding prices an unknown clamp as FREE"
        assert r["priced"] is False


# --- L1.41: the organ is attached to the desk -------------------------------------------------

def test_law_is_in_the_constitution_and_reaches_every_organ() -> None:
    """L1.36: a law that never reaches an organ cannot change behaviour -- so it is checked at BOTH
    ends, the full statement and the document every seat is handed.

    THE ORGAN-FACING ADDRESS MOVED, AND THE FENCE FOLLOWED IT (2026-09-05). This used to require
    L1.55 in `ops/principal_doctrine.txt`. That file was COMPACTED by principal order on 2026-08-25
    and says so in its own second paragraph -- "the sprawling duty text that used to live here is
    compacted there", meaning docs/LAWS.md and docs/RESEARCH.md, "with zero law regression". The
    law did not stop reaching organs; its address changed, and the doctrine file now points at
    LAWS.md by name. A fence still pinning the old address goes red on a deliberate consolidation,
    and the way a red-but-wrong fence gets satisfied is by pasting the law back into the file it
    was deliberately moved out of. Same correction the source-universality fences took, for the
    same reason. The assertion is unchanged in strength: the law must be in the constitution AND in
    the document every organ is handed.
    """
    con = (_ROOT / "docs/CONSTITUTION.md").read_text("utf-8")
    assert "L1.55" in con
    laws = (_ROOT / "docs/LAWS.md").read_text("utf-8")
    assert "L1.55" in laws, "a law that never reaches an organ cannot change behaviour (L1.36)"
    doc = (_ROOT / "ops/principal_doctrine.txt").read_text("utf-8")
    assert "docs/LAWS.md" in doc, (
        "the doctrine no longer routes organs to LAWS.md, so the compaction that moved the law "
        "there has broken its only path to a reader")


def test_fence_is_mapped_in_the_enforcement_matrix() -> None:
    src = (_ROOT / "scripts/build_enforcement_matrix.py").read_text("utf-8")
    assert "check_input_provenance.py" in src and "L1.55" in src


def test_fence_is_scheduled() -> None:
    man = (_ROOT / "ops/crontab.manifest").read_text("utf-8")
    assert "check_input_provenance.py" in man, "an unscheduled fence runs never (L1.28c)"


def test_fence_is_registered_to_the_build_standard() -> None:
    src = (_ROOT / "scripts/check_build_standard.py").read_text("utf-8")
    assert "check_input_provenance.py" in src, "registration IS the mechanism (L1.41)"


def test_fence_calls_the_law_guard() -> None:
    """L1.42: every entry point passes the laws."""
    src = (_ROOT / "scripts/check_input_provenance.py").read_text("utf-8")
    assert "_law_guard()" in src


def test_fence_runs_clean_end_to_end() -> None:
    r = subprocess.run([sys.executable, str(_ROOT / "scripts/check_input_provenance.py"),
                        "--report-only", "--json"], capture_output=True, text=True, cwd=_ROOT)
    assert r.returncode == 0, r.stderr[-2000:]
    rep = json.loads(r.stdout)
    assert rep["status"] in ("OK", "PARTIAL", "FABRICATED", "UNMEASURED")
    assert rep["law"] == "L1.55"
