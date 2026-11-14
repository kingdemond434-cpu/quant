"""A cell parked on an input its reader could not see comes back when the reader is fixed.

The tape readers opened only the writer whose files carry no `ts`, so every liquidity_regime and
orderflow_imbalance cell was judged on an empty tape and parked as never_fires. Nothing re-asked
them when the reader was fixed, because the bars never grew. `judge_coverage.READER_FIXES` is the
class fix: these tests pin that a registered fix re-admits once, only once it is live, never on an
unwritten stamp, and goes RED when it strands cells.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
for p in (ROOT, ROOT / "desks" / "mt5"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from research import judge_coverage as jc  # noqa: E402

T0 = datetime(2026, 10, 29, 12, tzinfo=UTC)
FAM = "liquidity_regime"
CELL = "EURUSD.liquidity_regime.p=1"


def _fix(tmp_path: Path, *, live: bool) -> tuple[dict, Path]:
    reader = tmp_path / "repo" / "reader.py"
    reader.parent.mkdir(parents=True, exist_ok=True)
    reader.write_text("from tape import fixed\n" if live else "from tape import broken\n",
                      "utf-8")
    return ({"id": "fix1", "families": (FAM,), "reader": "reader.py",
             "marker": "from tape import fixed"}, reader.parent)


def _bank(tmp_path: Path, rows: dict) -> Path:
    path = tmp_path / "unrunnable_specs.json"
    path.write_text(json.dumps(rows), "utf-8")
    return path


def _row(parked: datetime, **extra) -> dict:
    return {"reason": "never_fires", "sym": "EURUSD", "family": FAM, "tf": "H1", "days": 0,
            "bar_bytes": 100, "parked_at": parked.isoformat(), **extra}


def _pass(tmp_path, monkeypatch, at: datetime, *, live: bool, named: dict | None = None):
    fix, root = _fix(tmp_path, live=live)
    monkeypatch.setattr(jc, "READER_FIXES", (fix,))
    monkeypatch.setattr(jc, "_REPO", root)
    monkeypatch.setattr(jc, "_bar_bytes", lambda sym, tf="H1": 100)
    monkeypatch.setattr(jc, "_fire_probe", lambda s, f: {"status": "PRESENT"})
    return jc.update_unrunnable_bank(named or {}, at=at.isoformat(),
                                     path=tmp_path / "unrunnable_specs.json")


def test_nothing_comes_back_until_the_fixed_reader_is_on_the_tree(tmp_path, monkeypatch) -> None:
    _bank(tmp_path, {CELL: _row(T0 - timedelta(days=3))})
    got = _pass(tmp_path, monkeypatch, T0, live=False)
    assert got["bank_size"] == 1 and got["readmitted_by_cause"] == {}
    assert got["reader_fixes"]["live"] == {} and got["reader_fixes"]["status"] == "OK"
    assert not (tmp_path / jc.READER_FIXES_LIVE.name).exists()


def test_a_live_fix_readmits_every_cell_of_its_families_parked_before_it(
        tmp_path, monkeypatch) -> None:
    other = "EURUSD.trend_ma_cross.p=1"
    _bank(tmp_path, {CELL: _row(T0 - timedelta(days=3)),
                     other: {**_row(T0 - timedelta(days=3)), "family": "trend_ma_cross"}})
    got = _pass(tmp_path, monkeypatch, T0, live=True)
    assert got["readmitted_by_cause"] == {"reader_fixed": 1}
    assert got["readmitted_not_testable_by_family"] == {FAM: 1}
    bank = json.loads((tmp_path / "unrunnable_specs.json").read_text("utf-8"))
    assert list(bank) == [other]                       # another family's park is untouched
    stamps = json.loads((tmp_path / jc.READER_FIXES_LIVE.name).read_text("utf-8"))
    assert stamps == {"fix1": {"live_since": T0.isoformat()}}
    assert got["reader_fixes"]["stamped_now"] == ["fix1"]
    log = (tmp_path / jc.READMISSION_LOG.name).read_text("utf-8").splitlines()
    assert json.loads(log[-1])["all_by_cause"] == {"reader_fixed": 1}


def test_a_cell_named_inside_the_grace_window_is_re_asked_and_after_it_stays_parked(
        tmp_path, monkeypatch) -> None:
    _bank(tmp_path, {})
    _pass(tmp_path, monkeypatch, T0, live=True)                  # stamps live_since = T0
    early = T0 + timedelta(hours=jc.READER_FIX_GRACE_H - 1)
    named = {CELL: _row(early)}
    _pass(tmp_path, monkeypatch, early, live=True, named=named)  # a pre-fix sweep's report
    bank = json.loads((tmp_path / "unrunnable_specs.json").read_text("utf-8"))
    assert "reader_fixes" not in bank[CELL]
    nxt = _pass(tmp_path, monkeypatch, early + timedelta(hours=1), live=True)
    assert nxt["readmitted_by_cause"] == {"reader_fixed": 1}
    late = T0 + timedelta(hours=jc.READER_FIX_GRACE_H + 1)
    _pass(tmp_path, monkeypatch, late, live=True, named={CELL: _row(late)})
    bank = json.loads((tmp_path / "unrunnable_specs.json").read_text("utf-8"))
    assert bank[CELL]["reader_fixes"] == ["fix1"]
    again = _pass(tmp_path, monkeypatch, late + timedelta(hours=1), live=True)
    assert again["readmitted_by_cause"] == {} and again["bank_size"] == 1
    assert again["reader_fixes"]["stranded"] == {} and again["reader_fixes"]["status"] == "OK"


def test_a_stamp_that_did_not_land_readmits_nothing(tmp_path, monkeypatch) -> None:
    _bank(tmp_path, {CELL: _row(T0 - timedelta(days=3))})
    real = jc._replace_retry

    def refuse(src, dst):
        if Path(dst).name == jc.READER_FIXES_LIVE.name:
            raise OSError("disk full")
        return real(src, dst)

    monkeypatch.setattr(jc, "_replace_retry", refuse)
    got = _pass(tmp_path, monkeypatch, T0, live=True)
    assert got["readmitted_by_cause"] == {} and got["bank_size"] == 1
    assert got["reader_fixes"]["state"] == "STAMP_WRITE_FAILED"
    assert got["reader_fixes"]["status"] == "RED"


def test_an_unreadable_stamp_file_is_never_overwritten(tmp_path, monkeypatch) -> None:
    _bank(tmp_path, {CELL: _row(T0 - timedelta(days=3))})
    state = tmp_path / jc.READER_FIXES_LIVE.name
    state.write_text("{torn", "utf-8")
    got = _pass(tmp_path, monkeypatch, T0, live=True)
    assert got["readmitted_by_cause"] == {} and got["reader_fixes"]["status"] == "RED"
    assert state.read_text("utf-8") == "{torn"


def test_cells_left_parked_past_the_grace_window_are_red(tmp_path, monkeypatch) -> None:
    _bank(tmp_path, {})
    _pass(tmp_path, monkeypatch, T0, live=True)
    late = T0 + timedelta(hours=jc.READER_FIX_GRACE_H + 2)
    _bank(tmp_path, {CELL: _row(T0 - timedelta(days=3))})
    # The bank's lock is held elsewhere this pass: nothing can be re-admitted, so it strands.
    monkeypatch.setattr(jc, "readmit_cause", lambda *a, **k: None)
    got = _pass(tmp_path, monkeypatch, late, live=True)
    assert got["reader_fixes"]["stranded"] == {"fix1": 1}
    assert got["reader_fixes"]["status"] == "RED"


def test_the_tape_reader_fix_is_registered_against_the_reader_the_judge_uses() -> None:
    (fix,) = [f for f in jc.READER_FIXES if f["id"].startswith("tape_reader")]
    assert set(fix["families"]) == {"liquidity_regime", "orderflow_imbalance"}
    assert (jc._REPO / fix["reader"]).is_file()
    assert "reader_fixed" in jc.READMIT_CAUSES
