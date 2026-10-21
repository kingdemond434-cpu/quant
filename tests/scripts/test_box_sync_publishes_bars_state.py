"""THE BOX PUBLISHES HOW FRESH ITS BARS AND TICKS ARE, NOT THE BARS THEMSELVES.

The bar parquets stay off the sync wire (a parquet backlog killed every push with HTTP 408), so
the repository's copies stop where they were last committed and cannot show a live feed from a
dead one. `research/bars_state.py` writes `desks/mt5/data/BARS_STATE.json` from parquet FOOTERS,
the core hourly leg `bars_state` runs it just before `publish_state`, and `$reportPaths` carries
it. These pin: the fields on small temp files, UNMEASURED for anything unreadable, the time
budget, the publish list and the wiring. The login fence lives beside the other writers in
tests/ops/test_published_state_withholds_login.py.
"""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
SYNC = DESK / "scripts" / "sync_shadow_to_git.ps1"
REL = "desks/mt5/data/BARS_STATE.json"

import sys  # noqa: E402

for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import bars_state as bs  # noqa: E402

NOW = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)


def _bars(path: Path, end: str, n: int, col: str, *, row_group: int | None = None,
          stats: bool = True) -> None:
    idx = pd.date_range(end=end, periods=n, freq="1min", tz="UTC", name=col)
    df = pd.DataFrame({"open": 1.0, "close": 1.0}, index=idx)
    table = pa.Table.from_pandas(df)
    pq.write_table(table, path, row_group_size=row_group or n, write_statistics=stats)


def _ticks(path: Path, last_ms: int, n: int = 5) -> None:
    ms = [last_ms - 1000 * i for i in range(n)][::-1]
    pq.write_table(pa.table({"time_msc": pa.array(ms, pa.int64()),
                             "bid": [1.0] * n, "ask": [1.1] * n,
                             "time": pa.array([m // 1000 for m in ms], pa.int64()),
                             "ts": pa.array(ms, type=pa.timestamp("ms", tz="UTC"))}), path)


@pytest.fixture()
def desk(tmp_path: Path) -> dict[str, Path]:
    uni = tmp_path / "universe"
    ticks = tmp_path / "tape" / "ticks"
    uni.mkdir(parents=True)
    ticks.mkdir(parents=True)
    _bars(uni / "XAUUSD_M1.parquet", "2026-10-21 11:59", 300, "timestamp", row_group=100)
    _bars(uni / "EURUSD_H1.parquet", "2026-10-20 22:00", 50, "time")
    (uni / "universe.json").write_text("{}", "utf-8")       # not a bar file: ignored
    (uni / "XAUUSD_scalp_source.json").write_text("{}", "utf-8")
    (ticks / "XAUUSD").mkdir()
    last = int(datetime(2026, 10, 21, 11, 58, 30, tzinfo=UTC).timestamp() * 1000)
    _ticks(ticks / "XAUUSD" / "2026-10-20.parquet", last - 86_400_000)
    _ticks(ticks / "XAUUSD" / "20261021.parquet", last)       # moat_silver's naming, newest
    state = tmp_path / "tape" / "tape_state.json"
    state.write_text(json.dumps({"XAUUSD": {"last_tick_ms": last - 60_000,
                                            "last_run": "2026-10-21T11:59:00+00:00"},
                                 "GBPUSD": {"last_tick_ms": last}}), "utf-8")
    return {"universe": uni, "ticks": ticks, "tape_state": state}


def test_fields_on_small_temp_parquets_and_tick_files(desk: dict[str, Path]) -> None:
    doc = bs.measure(**desk, now=NOW)
    assert doc["schema"] == "bars_state/1"
    assert doc["generated_at"] == "2026-10-21T12:00:00+00:00"
    assert doc["host"]
    bars = {(r["symbol"], r["timeframe"]): r for r in doc["bars"]}
    assert set(bars) == {("XAUUSD", "M1"), ("EURUSD", "H1")}
    m1 = bars[("XAUUSD", "M1")]
    assert m1["status"] == "MEASURED" and m1["row_count"] == 300
    assert m1["last_bar_time"] == "2026-10-21T11:59:00+00:00"
    assert m1["source"] == "footer_statistics"
    assert m1["file_mtime"] and datetime.fromisoformat(m1["file_mtime"]).tzinfo is not None
    assert bars[("EURUSD", "H1")]["last_bar_time"] == "2026-10-20T22:00:00+00:00"
    tape = {r["symbol"]: r for r in doc["tape"]}
    x = tape["XAUUSD"]
    assert x["status"] == "MEASURED"
    assert x["last_tick"] == "2026-10-21T11:58:30+00:00"
    assert x["partition"] == "XAUUSD/20261021.parquet" and x["partition_day"] == "2026-10-21"
    assert x["partitions"] == 2 and x["row_count"] == 5
    assert x["tape_state_last_tick"] == "2026-10-21T11:57:30+00:00"
    # In tape_state but with no partition on disk: named, and never fresh.
    assert tape["GBPUSD"]["status"] == "UNMEASURED"
    assert "last_tick" not in tape["GBPUSD"]
    s = doc["summary"]
    assert s["newest_bar_time"] == "2026-10-21T11:59:00+00:00"
    assert s["newest_bar_age_h"] == pytest.approx(1 / 60, abs=1e-3)
    assert s["newest_tick_time"] == "2026-10-21T11:58:30+00:00"
    assert s["verdict"] == "MEASURED" and doc["budget_exhausted"] is False


def test_footer_without_statistics_reads_only_the_last_row_group(tmp_path: Path) -> None:
    p = tmp_path / "AUDUSD_M5.parquet"
    _bars(p, "2026-10-21 10:00", 40, "time", row_group=10, stats=False)
    m = bs.last_time(p)
    assert m["status"] == "MEASURED" and m["source"] == "last_row_group"
    assert m["last_time"] == "2026-10-21T10:00:00+00:00" and m["row_count"] == 40


def test_unreadable_input_is_unmeasured_never_fresh(tmp_path: Path) -> None:
    uni = tmp_path / "universe"
    uni.mkdir()
    (uni / "BROKEN_M1.parquet").write_bytes(b"not a parquet at all")
    pq.write_table(pa.table({"open": [1.0, 2.0]}), uni / "NOTIME_H1.parquet")
    pq.write_table(pa.table({"time": pa.array([], pa.timestamp("ns", tz="UTC"))}),
                   uni / "EMPTY_M15.parquet")
    ticks = tmp_path / "ticks"
    (ticks / "XAUUSD").mkdir(parents=True)
    (ticks / "XAUUSD" / "2026-10-21.parquet").write_bytes(b"garbage")
    state = tmp_path / "tape_state.json"
    state.write_text("{ not json", "utf-8")
    doc = bs.measure(universe=uni, ticks=ticks, tape_state=state, now=NOW)
    rows = doc["bars"] + doc["tape"]
    assert len(rows) == 4
    for r in rows:
        assert r["status"] == "UNMEASURED" and r["reason"], r
        assert "last_bar_time" not in r and "last_tick" not in r
    assert doc["summary"]["verdict"] == "UNMEASURED"
    assert doc["summary"]["newest_bar_time"] is None
    assert "unreadable" in doc["notes"]["tape_state_reason"]
    # An absent desk is UNMEASURED too, and still writes a report.
    gone = bs.measure(universe=tmp_path / "nope", ticks=tmp_path / "nope2",
                      tape_state=tmp_path / "nope3.json", now=NOW)
    assert gone["summary"]["verdict"] == "UNMEASURED" and gone["notes"]["bars_reason"]


def test_the_time_budget_is_honoured(desk: dict[str, Path]) -> None:
    ticks = iter(range(0, 10_000, 10))       # every clock read advances ten seconds
    doc = bs.measure(**desk, budget_s=15.0, clock=lambda: next(ticks), now=NOW)
    assert doc["budget_exhausted"] is True
    skipped = [r for r in doc["bars"] + doc["tape"] if r.get("reason") == "time budget exhausted"]
    assert skipped, "nothing was cut although the budget was exceeded"
    for r in skipped:
        assert r["status"] == "UNMEASURED" and "last_bar_time" not in r and "last_tick" not in r
    # The real clock on the real-sized fixture stays far inside the default.
    fast = bs.measure(**desk, now=NOW)
    assert fast["elapsed_s"] < bs.DEFAULT_BUDGET_S and fast["budget_exhausted"] is False


def test_main_writes_the_report_and_scrubs_account_keys(desk: dict[str, Path], tmp_path: Path,
                                                        monkeypatch: pytest.MonkeyPatch) -> None:
    out = tmp_path / "out" / "BARS_STATE.json"
    real = bs.measure
    monkeypatch.setattr(bs, "measure", lambda **k: {**real(**k), "account": {"login": 1},
                                                    "login": 1})
    rc = bs.main(["--out", str(out), "--universe", str(desk["universe"]),
                  "--ticks", str(desk["ticks"]), "--tape-state", str(desk["tape_state"])])
    assert rc == 0
    doc = json.loads(out.read_text("utf-8"))
    assert "login" not in doc and "account" not in doc
    assert doc["summary"]["bar_files_measured"] == 2


def _report_paths() -> list[str]:
    src = SYNC.read_text("utf-8", errors="ignore")
    start = src.index("$reportPaths = @(")
    block = src[start:src.index("\n)", start)]
    return [p for p in re.findall(r'"([^"]+)"', block) if "/" in p]


def test_it_is_in_the_publish_list_and_bars_stay_off_the_wire() -> None:
    from libs.ops import release, state_publication
    listed = _report_paths()
    assert REL in listed
    assert REL in state_publication.published_paths(ROOT)
    assert release.is_state_path(REL)
    wire = state_publication.published_paths(ROOT)
    assert not [p for p in wire if p.endswith(".parquet") and "/universe/" in p], (
        "bar parquets crossed the wire")


def test_it_is_a_core_leg_before_publication() -> None:
    import hourly_cycle as hc

    from libs.research import layers
    src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert "bars_state" in hc.CORE_LEGS
    assert src.index('_costed("bars_state"') < src.index('_costed("publish_state"')
    assert '"research/bars_state.py", "--budget-s", "20"' in src
    assert hc.LEG_BUDGET_SEC["bars_state"] <= 60
    assert layers.LEG_LAYER["bars_state"] == "meta"
