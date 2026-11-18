"""The backward tape walk: it copies the terminal's own older days, never re-fetches a day the desk
holds (on disk or archived), confirms the end of the store on a SECOND pass, pauses at the disk
floor, and imports nothing from the money path."""
from __future__ import annotations

import ast
import json
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

DESK = Path(__file__).resolve().parents[1]
for p in (str(DESK), str(DESK.parents[1])):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk import tape  # noqa: E402
from recorders import tape_deepen as td  # noqa: E402

DT = np.dtype([("time", "<i8"), ("bid", "<f8"), ("ask", "<f8"), ("last", "<f8"),
               ("volume", "<u8"), ("time_msc", "<i8"), ("flags", "<u4"),
               ("volume_real", "<f8")])
TODAY = date(2026, 11, 14)


def _ms(d: date, h: int = 12) -> int:
    return int(datetime(d.year, d.month, d.day, h, tzinfo=UTC).timestamp() * 1000)


class FakeTerminal:
    """A terminal whose store holds ticks on `days` (two per day) and nothing else."""

    def __init__(self, days: set[date], *, sync_lag: set[date] | None = None) -> None:
        self.days = days
        self.sync_lag = set(sync_lag or ())     # held, but not yet served by the terminal
        self.calls: list[tuple[str, int, int]] = []

    def ticks(self, symbol: str, start_ms: int, end_ms: int) -> np.ndarray | None:
        self.calls.append((symbol, start_ms, end_ms))
        rows = []
        for d in sorted(self.days):
            if d in self.sync_lag:
                continue
            for h in (9, 15):
                t = _ms(d, h)
                if start_ms <= t < end_ms:
                    rows.append((t // 1000, 1.1, 1.1002, 0.0, 0, t, 6, 0.0))
        return np.array(rows, dtype=DT)


def _seed(root: Path, sym: str, days: list[date]) -> None:
    for d in days:
        df = pd.DataFrame(np.array([(_ms(d) // 1000, 1.0, 1.0001, 0.0, 0, _ms(d), 6, 0.0)],
                                   dtype=DT))
        df["ts"] = pd.to_datetime(df["time_msc"], unit="ms", utc=True)
        tape.write_day(df, root / sym / f"{d.isoformat()}.parquet")


def _run(src, syms, tmp_path, **kw):
    kw.setdefault("budget_s", 0)
    return td.deepen(src, syms, today=TODAY, root=tmp_path / "ticks",
                     state_path=tmp_path / "state.json", manifest=tmp_path / "manifest.jsonl",
                     free_gb=lambda _p: 500.0, **kw)


def _days(n_back: int, first: date = TODAY - timedelta(days=1)) -> set[date]:
    return {first - timedelta(days=i) for i in range(n_back)}


def test_it_walks_below_the_first_recorded_day_and_writes_the_forward_writers_file(tmp_path):
    _seed(tmp_path / "ticks", "EURUSD", [TODAY - timedelta(days=1)])
    store = _days(40)
    rep = _run(FakeTerminal(store), ["EURUSD"], tmp_path)
    files = {d for d, _ in tape.day_files("EURUSD", tmp_path / "ticks")}
    assert files == {d.isoformat() for d in store}
    assert rep["days_added"] == 39
    got = pd.read_parquet(tmp_path / "ticks" / "EURUSD" / f"{(TODAY - timedelta(days=5))}.parquet")
    assert len(got) == 2 and "sided" in got.columns        # through write_day's merge
    assert rep["per_symbol"]["EURUSD"]["days_on_disk"] == 40


def test_a_held_day_is_stepped_over_never_refetched(tmp_path):
    held = [TODAY - timedelta(days=i) for i in range(1, 6)]
    _seed(tmp_path / "ticks", "XAUUSD", held)
    (tmp_path / "manifest.jsonl").write_text(
        json.dumps({"symbol": "XAUUSD", "day": (TODAY - timedelta(days=7)).strftime("%Y%m%d")})
        + "\n", encoding="utf-8")
    term = FakeTerminal(_days(10))
    _run(term, ["XAUUSD"], tmp_path)
    asked = {datetime.fromtimestamp(s / 1000, tz=UTC).date() for _sym, s, _e in term.calls}
    assert not asked & set(held)
    assert TODAY - timedelta(days=7) not in asked            # archived off the box = recorded


def test_the_end_of_the_store_is_confirmed_on_a_second_pass(tmp_path):
    term = FakeTerminal(_days(20))
    first = _run(term, ["USDJPY"], tmp_path)
    assert first["per_symbol"]["USDJPY"]["pending_confirm"] is True
    assert first["exhausted"] == 0                            # one silence is not proof
    second = _run(term, ["USDJPY"], tmp_path)
    assert second["exhausted"] == 1 and second["status"] == td.STATUS_DONE
    third = _run(term, ["USDJPY"], tmp_path)
    assert third["days_added"] == 0                           # exhausted symbols are not asked


def test_history_still_syncing_is_written_on_the_confirming_ask(tmp_path):
    lagged = TODAY - timedelta(days=30)
    store = _days(20) | {lagged}
    term = FakeTerminal(store)
    term.sync_lag = {lagged}
    _run(term, ["GBPUSD"], tmp_path)
    term.sync_lag = set()                                     # the terminal caught up
    rep = _run(term, ["GBPUSD"], tmp_path)
    assert lagged.isoformat() in {d for d, _ in tape.day_files("GBPUSD", tmp_path / "ticks")}
    assert rep["per_symbol"]["GBPUSD"]["exhausted"] is False  # the walk goes on below it


def test_the_disk_floor_pauses_and_writes_nothing(tmp_path):
    rep = td.deepen(FakeTerminal(_days(10)), ["EURUSD"], budget_s=0, today=TODAY,
                    root=tmp_path / "ticks", state_path=tmp_path / "s.json",
                    manifest=tmp_path / "m.jsonl", free_gb=lambda _p: 1.0)
    assert rep["status"] == td.STATUS_DISK and rep["days_added"] == 0
    assert not (tmp_path / "ticks").exists()


def test_a_terminal_failure_does_not_move_the_floor(tmp_path):
    class Down:
        def ticks(self, *_a):
            return None
    rep = _run(Down(), ["EURUSD"], tmp_path)
    st = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert st["symbols"]["EURUSD"]["floor"] == TODAY.isoformat()
    assert rep["terminal_failures"] == 1 and rep["exhausted"] == 0


def test_the_budget_bounds_a_pass_and_the_next_resumes(tmp_path):
    ticks = iter(range(10_000))
    term = FakeTerminal(_days(60))
    rep = _run(term, ["EURUSD", "XAUUSD"], tmp_path, budget_s=5,
               clock=lambda: float(next(ticks)))
    assert rep["status"] == td.STATUS_BUDGET and 0 < rep["days_added"] < 120
    before = rep["days_added"]
    rep2 = _run(term, ["EURUSD", "XAUUSD"], tmp_path)
    assert rep2["days_added"] == 120 - before


def test_the_cycle_cap_bounds_the_pass():
    assert td.effective_budget(300, None) == 300
    assert td.effective_budget(300, "200") == 200 - td.CAP_MARGIN_S
    assert td.effective_budget(0, "420") == 420 - td.CAP_MARGIN_S
    assert td.effective_budget(0, None) == 0


def test_nearest_the_bar_goes_first():
    assert td.order(["A", "B", "C", "D"], {"A": 10, "B": 60, "C": 90, "D": 70}) == \
        ["B", "A", "D", "C"]


def test_it_reaches_the_bar_and_says_so(tmp_path):
    _seed(tmp_path / "ticks", "NAS100", [TODAY - timedelta(days=1)])
    rep = _run(FakeTerminal(_days(80)), ["NAS100"], tmp_path)
    assert rep["crossed_bar_this_pass"] == ["NAS100"] and rep["at_or_above_bar"] == 1


def test_it_imports_nothing_from_the_money_path():
    src = (DESK / "recorders" / "tape_deepen.py").read_text(encoding="utf-8")
    mods = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            mods |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module)
    banned = ("gateway", "execution_policy", "netting", "decision_core")
    assert not [m for m in mods if any(b in m for b in banned)]
    assert "venue_refusal" in src                             # the Fusion pin, never FTMO
