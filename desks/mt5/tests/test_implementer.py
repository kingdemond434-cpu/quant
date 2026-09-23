"""THE IMPLEMENTER'S CONTRACT: every open row leaves the pass owned, and no proof is invented.

These are the four properties the organ exists for, each pinned against the failure that produced
it rather than against the code's current shape:

  * a planted OPEN row reaches a terminal state OR carries a NAMED blocker with an owner;
  * nothing may leave a pass open with no owner and no next action -- the defect itself;
  * a recommendation the desk already settled is never re-proposed by intake;
  * `implemented` is only written with a resolvable commit and a file born AFTER the ask, because
    the dry run that disposed twenty rows on "an artifact this organ writes is fresh" was wrong
    about every one it was checked against.

Every fixture is a tmp_path repo. The organ takes `root` for exactly this reason: a test that had
to monkeypatch module constants would be testing the monkeypatching.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from research import implementer as I  # noqa: E402


def _ledger(root: Path, rows: list[dict[str, Any]]) -> Path:
    p = root / "docs" / "research" / "recommendation_ledger.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"recommendations": rows}, indent=1, ensure_ascii=False), "utf-8")
    return p


def _row(rid: str, summary: str, **kw: Any) -> dict[str, Any]:
    base = {"id": rid, "source": "test", "summary": summary, "roi_bps": None, "rank": None,
            "roi_basis": None,
            "raised": (datetime.now(tz=UTC) - timedelta(days=30)).isoformat(),
            "status": "open", "reason": None, "commit": None, "due": None, "disposed": None}
    base.update(kw)
    return base


def _repo(root: Path) -> None:
    """A real git repo -- `_added_commit` is a git question and a stub would not answer it."""
    for args in (["init", "-q"], ["config", "user.email", "t@t"], ["config", "user.name", "t"]):
        subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def _commit(root: Path, msg: str = "c") -> str:
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-q", "-m", msg], cwd=root, check=True, capture_output=True)
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, check=True,
                          capture_output=True, text=True).stdout.strip()


# ------------------------------------------------------------------ the core property
def test_every_open_row_leaves_the_pass_with_an_owner_and_a_next_action(tmp_path: Path) -> None:
    """THE DEFECT THIS ORGAN EXISTS TO REMOVE, stated as a test over deliberately varied rows.

    Four shapes that used to share one outcome (sit open forever): prose with no target, a cited
    file that is not here, a sealed file, and a file that exists. Whatever the ladder decides,
    none of them may end the pass open with nobody on it.
    """
    _repo(tmp_path)
    (tmp_path / "libs").mkdir()
    (tmp_path / "libs" / "thing.py").write_text("x = 1\n", "utf-8")
    _ledger(tmp_path, [
        _row("R0001", "Make the miners better somehow, no file named."),
        _row("R0002", "Rewrite scripts/does_not_exist_anywhere.py to stop dropping rows."),
        _row("R0003", "Change desks/mt5/research/promoter.py so the gold lane re-derives."),
        _row("R0004", "Fix libs/thing.py which returns the wrong sign."),
    ])
    _commit(tmp_path)

    doc = I.run(root=tmp_path, budget_s=60.0, do_intake=False)

    rows = json.loads((tmp_path / "docs/research/recommendation_ledger.json")
                      .read_text("utf-8"))["recommendations"]
    still_open = [r for r in rows if r["status"] == "open"]
    assert still_open, "the fixture is built so some rows stay open; zero would make this vacuous"
    for r in still_open:
        assert r.get("owner"), f"{r['id']} left open with no owner"
        assert r.get("next_action"), f"{r['id']} left open with no next action"
        assert r.get("blocker"), f"{r['id']} left open with no named blocker"
    assert doc["n_open_without_owner"] == 0
    assert doc["n_moved"] == 4


def test_a_sealed_file_is_blocked_on_the_principal_never_disposed(tmp_path: Path) -> None:
    """A sealed judge is not a rejection and not a schedule: it is somebody else's decision."""
    _repo(tmp_path)
    _ledger(tmp_path, [_row("R0009",
                            "Loosen desks/mt5/research/allocator_proof.py's staleness window.")])
    _commit(tmp_path)
    I.run(root=tmp_path, budget_s=30.0, do_intake=False)
    row = json.loads((tmp_path / "docs/research/recommendation_ledger.json")
                     .read_text("utf-8"))["recommendations"][0]
    assert row["status"] == "open"
    assert row["owner"] == "principal"
    assert row["blocker_class"] == "needs_principal"
    assert "allocator_proof.py" in row["blocker"]


def test_a_timid_row_is_rejected_by_the_standing_order_with_a_real_reason(tmp_path: Path) -> None:
    """NEVER REDUCE AGGRESSIVENESS is a law, so the ladder must reach it before anything else."""
    _repo(tmp_path)
    _ledger(tmp_path, [_row("R0010", "Add a cap on the allocator's gold fraction and lower the "
                                     "heat floor to 12% so drawdowns are gentler.")])
    _commit(tmp_path)
    I.run(root=tmp_path, budget_s=30.0, do_intake=False)
    row = json.loads((tmp_path / "docs/research/recommendation_ledger.json")
                     .read_text("utf-8"))["recommendations"][0]
    assert row["status"] == "rejected"
    assert len(row["reason"]) >= 25
    assert "standing order" in row["reason"].lower()
    assert row["disposed"], "a terminal row with no `disposed` stamp is invisible to every rate"


def test_implemented_needs_a_file_born_after_the_ask_and_cites_that_commit(
        tmp_path: Path) -> None:
    """THE ONLY PROOF PROSE CANNOT FAKE, and the lag rule that stops evidence posing as delivery."""
    _repo(tmp_path)
    (tmp_path / "docs").mkdir(exist_ok=True)
    (tmp_path / "seed.txt").write_text("seed\n", "utf-8")
    _commit(tmp_path, "seed")
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "delivered.py").write_text("print(1)\n", "utf-8")
    _ledger(tmp_path, [_row("R0020", "Build scripts/delivered.py so the sweep has a runner.")])
    sha = _commit(tmp_path, "add the deliverable")

    I.run(root=tmp_path, budget_s=60.0, do_intake=False)
    row = json.loads((tmp_path / "docs/research/recommendation_ledger.json")
                     .read_text("utf-8"))["recommendations"][0]
    assert row["status"] == "implemented"
    assert row["commit"] == sha, "the citation must be the ADD commit, not a later touch"
    assert row["disposed"]


def test_a_file_born_inside_the_grace_window_is_evidence_not_delivery(tmp_path: Path) -> None:
    """R0742's class: the hunter writes its measurement WHILE raising the row, minutes later.

    Without the lag rule this reads as "the cited file appeared after the ask" and disposes the
    row implemented, which removes a live recommendation from view permanently.
    """
    _repo(tmp_path)
    (tmp_path / "seed.txt").write_text("seed\n", "utf-8")
    _commit(tmp_path, "seed")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "evidence.json").write_text("{}", "utf-8")
    _ledger(tmp_path, [_row("R0021", "rank_score is undeclared, measured: data/evidence.json -- "
                                     "declare the unit.",
                            raised=(datetime.now(tz=UTC) - timedelta(minutes=5)).isoformat())])
    _commit(tmp_path, "evidence written with the row")

    I.run(root=tmp_path, budget_s=60.0, do_intake=False)
    row = json.loads((tmp_path / "docs/research/recommendation_ledger.json")
                     .read_text("utf-8"))["recommendations"][0]
    assert row["status"] == "open", "evidence born with the ask must not read as delivery"
    assert row.get("owner") and row.get("next_action")


# ------------------------------------------------------------------ the loop back to the CEO
def test_an_already_settled_recommendation_is_not_re_proposed(tmp_path: Path) -> None:
    """The docket proposes daily; the ledger remembers. Intake must let the ledger win."""
    _repo(tmp_path)
    settled = ("Generate vol_transition cells across the registry and measure the marginal "
               "dE[log W] of the best survivor after residualising against the funded book")
    _ledger(tmp_path, [_row("R0100", settled, status="implemented",
                            reason="done", commit="0" * 40,
                            disposed=datetime.now(tz=UTC).isoformat())])
    docket = tmp_path / "desks" / "mt5" / "reports" / "CEO_DOCKET.json"
    docket.parent.mkdir(parents=True, exist_ok=True)
    docket.write_text(json.dumps({"proposals": [
        {"id": "breadth:vol_transition", "adds": "the vol_transition mechanism as a fundable "
                                                 "family",
         "experiment": "generate vol_transition cells across the registry, judge them in the "
                       "standing gauntlet, and measure the marginal dE[log W] of the best "
                       "survivor after residualising against the funded book",
         "refuted_if": "no cell survives", "rank": 1},
        {"id": "new:thing", "adds": "an entirely unrelated overnight gap decay sleeve on silver",
         "experiment": "screen silver overnight gaps in the standing gauntlet",
         "refuted_if": "no survivor", "rank": 2}]}), "utf-8")
    _commit(tmp_path)

    doc = I.run(root=tmp_path, budget_s=60.0, do_intake=True)
    assert doc["intake"]["n_added"] == 1, "only the unrelated proposal is new work"
    assert [s["id"] for s in doc["intake"]["skipped_already_settled"]] == ["R0100"]

    summaries = [r["summary"] for r in json.loads(
        (tmp_path / "docs/research/recommendation_ledger.json").read_text("utf-8")
    )["recommendations"]]
    assert not any("vol_transition" in s for s in summaries[1:])


def test_already_settled_ignores_open_rows(tmp_path: Path) -> None:
    """Only TERMINAL rows settle anything. An open twin is a duplicate, not an answer."""
    rows = [_row("R0200", "wire the silver overnight gap decay sleeve into the gauntlet")]
    assert I.already_settled("wire the silver overnight gap decay sleeve into the gauntlet",
                             rows) is None


# ------------------------------------------------------------------ the ratchet
def test_the_open_ratchet_only_falls_and_a_rise_must_name_its_cause(tmp_path: Path) -> None:
    p = tmp_path / "ratchet.json"
    assert I.update_ratchet(50, None, p)["floor"] == 50          # seeded
    assert I.update_ratchet(40, None, p)["floor"] == 40          # falls freely
    d = I.update_ratchet(60, None, p)
    assert d["floor"] == 40, "an unexplained rise must never move the floor"
    assert d["rises"] == []
    d = I.update_ratchet(60, "intake: 20 row(s) from the CEO docket", p)
    assert d["floor"] == 40 and len(d["rises"]) == 1
    assert d["rises"][0]["reason"].startswith("intake")


# ------------------------------------------------------------------ the artifact and the page
def test_the_pass_publishes_its_artifact_and_renders_the_page(tmp_path: Path) -> None:
    _repo(tmp_path)
    _ledger(tmp_path, [_row("R0300", "Make something better, no file named at all.")])
    _commit(tmp_path)
    doc = I.run(root=tmp_path, budget_s=30.0, do_intake=False)
    art = json.loads((tmp_path / "desks/mt5/reports/IMPLEMENTER.json").read_text("utf-8"))
    assert art["open_after"] == doc["open_after"]
    assert art["oldest_open"]["id"] == "R0300"
    page = (tmp_path / "docs/research/IMPLEMENTATION.md").read_text("utf-8")
    assert "Implementation lane" in page and "R0300" in page
    assert "DERIVED FILE" in page, "the page must say it is derived, or someone will edit it"


def test_the_ledger_is_written_in_its_one_canonical_form(tmp_path: Path) -> None:
    """tests/governance/test_ledger_format_canonical.py pins these bytes for the whole desk."""
    _repo(tmp_path)
    _ledger(tmp_path, [_row("R0400", "A row with CJK in it: 韭菜 and a § sign.")])
    _commit(tmp_path)
    I.run(root=tmp_path, budget_s=30.0, do_intake=False)
    raw = (tmp_path / "docs/research/recommendation_ledger.json").read_text("utf-8")
    assert raw == json.dumps(json.loads(raw), indent=1, ensure_ascii=False)
    assert "韭菜" in raw, "escaped CJK is ungreppable and reads as unexplored ground (R0368)"


def test_an_unreadable_ledger_refuses_rather_than_reading_as_empty(tmp_path: Path) -> None:
    p = tmp_path / "docs" / "research" / "recommendation_ledger.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("<<<<<<< HEAD\n{}\n", "utf-8")
    with pytest.raises(SystemExit, match="REFUSING"):
        I.load_ledger(tmp_path)


def test_the_clock_index_reads_runners_not_only_the_cycles(tmp_path: Path) -> None:
    """The census that missed thirty organs: ops/run_*.cmd schedules, brain_env.sh does not."""
    (tmp_path / "ops").mkdir()
    (tmp_path / "desks" / "mt5" / "research").mkdir(parents=True)
    (tmp_path / "desks" / "mt5" / "research" / "organ.py").write_text("x = 1\n", "utf-8")
    (tmp_path / "desks" / "mt5" / "research" / "sourced.py").write_text("x = 1\n", "utf-8")
    (tmp_path / "ops" / "run_thing.cmd").write_text(
        'python -u "desks\\mt5\\research\\organ.py" --apply\n', "utf-8")
    (tmp_path / "ops" / "brain_env.sh").write_text("python desks/mt5/research/sourced.py\n",
                                                   "utf-8")
    idx = I._clock_index(tmp_path)
    assert idx["desks/mt5/research/organ.py"] == "runner:run_thing.cmd"
    assert "desks/mt5/research/sourced.py" not in idx


def test_a_lag_is_measured_in_time_not_in_text(tmp_path: Path) -> None:
    """Two ISO stamps with different offsets compare backwards as strings (see `_lag_h`)."""
    raised, born = "2026-09-01T22:00:00+00:00", "2026-09-01T23:00:00+02:00"
    assert born > raised                       # the lexical trap
    assert I._lag_h(raised, born) < 0.0        # the truth: the file predates the ask
