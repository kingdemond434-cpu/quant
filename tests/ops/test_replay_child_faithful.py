"""replay_child replays the scenario faithfully (Autonomy + Desk health, 2026-11-18).

Three defects let a replay's verdict depend on the runner rather than on the tree:
  1. e8_gold's BRACKET_SLIP_FILE (and e8_evidence's heartbeat and ledger) were written into the
     tree's tracked data/, so the second tree read the first tree's measurement;
  2. account_breakers.STATE, the daily-loss latch, was shared, so a latch one scenario tripped
     stood every later scenario down;
  3. the book read the runner's wall clock while the stubbed tick sat at scenario time, so every
     quote looked ~36 days stale and the disconnect breaker fired on all of them (#890 placed no
     E8 bracket).
Each pin runs the real child, in a subprocess, on a tiny tree whose book reports what it saw."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
CHILD = ROOT / "ops/release/replay_child.py"
_spec = importlib.util.spec_from_file_location("replay_child_t", CHILD)
assert _spec is not None and _spec.loader is not None
rc: Any = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rc)

BOOK = '''
from datetime import UTC, datetime
from pathlib import Path
import json

DATA = Path(__file__).resolve().parents[1] / "data"
OUT = INTENTS = LOG = STATE = GUARD = ARMED_MARKER = DATA / "unused.json"
BRACKET_SLIP_FILE = DATA / "E8_GOLD_SLIP.json"


def run(venue, mt5, *, armed=False):
    from mt5desk import account_breakers as ab

    import pandas as pd
    now = datetime.now(tz=UTC)
    tick = mt5.symbol_info_tick("XAUUSD").time  # broker clock, NY+7, as the terminal stamps it
    wall = pd.Timestamp(tick, unit="s") - pd.Timedelta(hours=7)
    tick_utc = wall.tz_localize("America/New_York").tz_convert("UTC").timestamp()
    BRACKET_SLIP_FILE.write_text(json.dumps({"measured_at": now.isoformat()}))
    latched = Path(ab.STATE).exists()
    Path(ab.STATE).write_text("{}")
    return {"now": now.isoformat(), "tick_age_s": now.timestamp() - tick_utc, "latched": latched,
            "isinstance": isinstance(now, datetime), "slip": str(BRACKET_SLIP_FILE),
            "breaker": str(ab.STATE)}
'''
BREAKERS = '''
from pathlib import Path
STATE = Path(__file__).resolve().parents[1] / "data" / "ACCOUNT_BREAKERS.json"
'''


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    t = tmp_path / "tree"
    prop = t / "desks" / "mt5" / "prop"
    prop.mkdir(parents=True)
    (t / "desks" / "mt5" / "data").mkdir()
    (prop / "__init__.py").write_text("")
    (prop / "e8_gold.py").write_text(BOOK)
    (t / "desks" / "mt5" / "mt5desk").mkdir()  # a namespace package, as on #890
    (t / "desks" / "mt5" / "mt5desk" / "account_breakers.py").write_text(BREAKERS)
    return t


def _run(tree: Path, tmp: Path, name: str) -> dict[str, Any]:
    work = tmp / name
    work.mkdir()
    sc = {"id": name, "day": "2026-10-13", "shape": "range", "seed": 1, "equity": 100000.0,
          "hours": [7.0, 9.5], "account_id": 1234, "server": "s"}  # fmt: skip
    (tmp / f"{name}.json").write_text(json.dumps(sc))
    p = subprocess.run([sys.executable, "-I", str(CHILD), str(tree), str(tmp / f"{name}.json"),
                        str(work / "out.json")], cwd=work, capture_output=True, text=True,
                       check=False, timeout=300)  # fmt: skip
    assert p.returncode == 0, p.stderr[-2000:]
    out: dict[str, Any] = json.loads((work / "out.json").read_text())
    return out


def _replay(tree: Path, tmp: Path, name: str) -> list[dict[str, Any]]:
    out = _run(tree, tmp, name)
    assert "mt5desk.account_breakers" not in out["sandbox_absent"]
    assert out["tree_writes"] == []
    steps = out["steps"]
    assert all(s["error"] is None for s in steps), [s["error"] for s in steps]
    return [s["doc"] for s in steps]


def test_the_book_reads_the_scenario_clock_not_the_runner_s(tree: Path, tmp_path: Path) -> None:
    docs = _replay(tree, tmp_path, "a")
    # broker 07:00 on 2026-10-13 (NY summer, so UTC+3) is 04:00 UTC
    assert [d["now"] for d in docs] == ["2026-10-13T04:00:00+00:00", "2026-10-13T06:30:00+00:00"]
    assert all(abs(d["tick_age_s"]) < 1 for d in docs)  # a fresh tick reads fresh
    assert all(d["isinstance"] for d in docs)


def test_no_state_file_lands_in_the_tree_and_no_latch_crosses_scenarios(
    tree: Path, tmp_path: Path
) -> None:
    first = _replay(tree, tmp_path, "a")
    second = _replay(tree, tmp_path, "b")
    assert sorted(p.name for p in (tree / "desks/mt5/data").iterdir()) == []  # nothing leaked
    for docs, name in ((first, "a"), (second, "b")):
        assert all(str(tmp_path / name) in d["slip"] for d in docs)
        assert all(str(tmp_path / name) in d["breaker"] for d in docs)
        # the latch set at the first step is seen at the second, and never by the next scenario
        assert [d["latched"] for d in docs] == [False, True]


def test_scenario_clock_honours_tz_and_reads_like_datetime() -> None:
    import datetime as dtm

    import pandas as pd

    clock = {"now": pd.Timestamp("2026-10-13T07:30:00", tz="UTC")}  # broker wall time
    sd = rc.scenario_clock(clock)
    assert sd.now(dtm.UTC) == dtm.datetime(2026, 10, 13, 4, 30, tzinfo=dtm.UTC)
    assert sd.now().tzinfo is None and sd.utcnow() == dtm.datetime(2026, 10, 13, 4, 30)
    assert isinstance(dtm.datetime(2020, 1, 1), sd) and issubclass(dtm.datetime, sd)
    assert sd.fromisoformat("2026-01-02T00:00:00").year == 2026


def test_the_sandbox_names_the_real_latch_module_and_reports_one_the_tree_lacks(
    tree: Path, tmp_path: Path
) -> None:
    """Audit HOLD on #1353: keyed on prop.account_breakers, the loop skipped #890's latch."""
    assert "mt5desk.account_breakers" in rc.SANDBOXED_ELSEWHERE
    (tree / "desks/mt5/mt5desk/account_breakers.py").unlink()
    (tree / "desks/mt5/prop/e8_gold.py").write_text(
        BOOK.replace("    from mt5desk import account_breakers as ab\n", "")
        .replace("latched = Path(ab.STATE).exists()\n    Path(ab.STATE).write_text(\"{}\")",
                 "latched = False")
        .replace("\"breaker\": str(ab.STATE)", "\"breaker\": None")
    )
    out = _run(tree, tmp_path, "c")
    assert "mt5desk.account_breakers" in out["sandbox_absent"]


def test_the_child_s_broker_clock_is_the_desk_s() -> None:
    """Both DST sides, the spring gap and the autumn repeat match session_clock.server_to_utc."""
    import pandas as pd

    from libs.regime.session_clock import server_to_utc

    for stamp in ("2026-01-15 07:00", "2026-07-15 07:00", "2026-03-08 09:30",
                  "2026-11-01 08:30", "2026-10-13 23:54"):  # fmt: skip
        want = pd.Timestamp(server_to_utc([pd.Timestamp(stamp)])[0])
        assert rc.broker_to_utc(pd.Timestamp(stamp, tz="UTC")) == want, stamp


def test_a_write_the_sandbox_misses_is_reported(tree: Path, tmp_path: Path) -> None:
    (tree / "desks/mt5/prop/e8_gold.py").write_text(
        BOOK + '\nOLD_RUN = run\n\n\ndef run(venue, mt5, *, armed=False):\n'
        '    (DATA / "leak.json").write_text("{}")\n    return OLD_RUN(venue, mt5, armed=armed)\n'
    )
    out = _run(tree, tmp_path, "d")
    assert out["tree_writes"] == ["desks/mt5/data/leak.json"]
