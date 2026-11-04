"""The daily swap logger in carry_state (GD queue row c, 2026-10-14): the broker's own swap table,
per symbol per complete UTC day, into the lake's PIT envelope that `alt:` conditioners read.
Synthetic panel files; no terminal, no network."""
from __future__ import annotations

import gzip
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research"), str(DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import carry_state as C  # noqa: E402
from mt5desk import cell_modifiers as cm  # noqa: E402

NOW = datetime(2026, 9, 10, 12, tzinfo=UTC)


def _row(sym: str, at: str, lo: float, sh: float) -> dict:
    return {"source": "broker_swaps", "kind": "swap_table", "symbols": [sym], "found_at": at,
            "swap_long": lo, "swap_short": sh, "url": "mt5://symbol_info"}


def _panel(tmp: Path) -> Path:
    p = tmp / "broker_swaps"
    p.mkdir()
    (p / "discoveries_20260909_0822.json").write_text(json.dumps([
        _row("EURUSD", "2026-09-09T08:22:00+00:00", -6.0, 1.0),
        _row("EURUSD", "2026-09-09T20:22:00+00:00", -6.5, 1.2),      # the day's last wins
        _row("EURUSD", "2026-09-10T08:22:00+00:00", -9.9, 9.9),      # today: not complete
        {"kind": "news", "symbols": ["EURUSD"]},                     # not a swap row
        _row("XAUUSD", "not-a-time", -30.0, 5.0)]), "utf-8")          # unstamped: dropped
    roll = [_row("EURUSD", "2026-09-07T10:00:00+00:00", -5.5, 0.9),
            _row("USD/JPY", "2026-09-07T10:00:00+00:00", 6.35, -15.0)]
    (p / "rollup_20260907.jsonl.gz").write_bytes(
        gzip.compress("\n".join(json.dumps(r) for r in roll).encode()))
    return p


def test_one_row_per_symbol_per_complete_day_stamped_at_its_capture(tmp_path: Path) -> None:
    rows = C.daily_swap_rows(_panel(tmp_path), NOW)
    assert set(rows) == {"EURUSD", "USD/JPY"}                      # XAUUSD had no stamp
    eu = rows["EURUSD"]
    assert set(eu) == {"2026-09-07", "2026-09-09"}                 # 09-10 is today
    d = eu["2026-09-09"]
    assert (d["swap_long"], d["swap_short"], d["n_obs_day"]) == (-6.5, 1.2, 2)
    assert d["available_time"] == "2026-09-09T20:22:00+00:00" == d["published_time"]
    assert d["swap_diff"] == -7.7


def test_the_log_is_append_only_and_reads_as_a_conditioner(tmp_path: Path) -> None:
    panel, lake = _panel(tmp_path), tmp_path / "lake"
    rep = C.log_daily_swaps(panel, lake, NOW)
    assert rep["status"] == "LOGGED" and rep["n_rows_added"] == 3 and rep["n_symbols"] == 2
    f = lake / "swap_EURUSD.csv"
    df = pd.read_csv(f)
    assert list(df.columns) == list(C.SWAP_LOG_COLUMNS) and len(df) == 2
    assert (lake / "swap_USD_JPY.csv").exists()                    # a safe file stem
    # a later pass never rewrites a logged day, even if the panel now says otherwise
    (panel / "discoveries_20260909_2300.json").write_text(json.dumps([
        _row("EURUSD", "2026-09-09T23:00:00+00:00", 99.0, 99.0)]), "utf-8")
    later = datetime(2026, 9, 11, 12, tzinfo=UTC)
    rep2 = C.log_daily_swaps(panel, lake, later)
    df2 = pd.read_csv(f)
    assert float(df2.loc[df2.event_time == "2026-09-09", "swap_long"].iloc[0]) == -6.5
    assert "2026-09-10" in set(df2.event_time) and rep2["n_rows_added"] == 1
    # the alt: conditioner door reads it on its available_time clock
    spec = cm.alt_conditioner("alt:swap_EURUSD:swap_diff:lt:0")
    assert spec == ("swap_EURUSD", "swap_diff", "lt", 0.0)
    assert cm._alt_series("swap_EURUSD", "swap_diff", root=lake) is not None


def test_no_capture_is_unmeasured_and_writes_nothing(tmp_path: Path) -> None:
    rep = C.log_daily_swaps(tmp_path / "absent", tmp_path / "lake", NOW)
    assert rep["status"].startswith("UNMEASURED") and rep["n_symbols"] == 0
    assert not (tmp_path / "lake").exists()


def test_main_logs_swaps_before_the_carry_state(tmp_path: Path) -> None:
    out = tmp_path / "carry_state.json"
    C.main(["--panel", str(_panel(tmp_path)), "--terms", str(tmp_path / "noterms"),
            "--universe", str(tmp_path / "nouni"), "--lake-dir", str(tmp_path / "lake"),
            "--out", str(out)])
    assert list((tmp_path / "lake").glob("swap_*.csv"))           # logged even with no terms


def test_an_unreadable_log_is_skipped_and_never_overwritten(tmp_path: Path) -> None:
    """GD queue-rows audit MF2: a corrupt log plus a pruned panel must never lose logged days."""
    panel, lake = _panel(tmp_path), tmp_path / "lake"
    lake.mkdir()
    bad = lake / "swap_EURUSD.csv"
    bad.write_bytes(b"\x00\xff not,a\ncsv")
    before = bad.read_bytes()
    rep = C.log_daily_swaps(panel, lake, NOW)
    assert bad.read_bytes() == before                              # untouched
    assert [u["symbol"] for u in rep["unreadable_logs"]] == ["EURUSD"]
    assert (lake / "swap_USD_JPY.csv").exists()                    # other symbols still logged


def test_an_unreadable_log_marks_the_pass_and_is_printed(
        tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Auditor should-fix: a pass that skipped an unreadable log is LOGGED_WITH_UNREADABLE, not a
    clean LOGGED, and main prints how many were skipped."""
    panel, lake = _panel(tmp_path), tmp_path / "lake"
    lake.mkdir()
    (lake / "swap_EURUSD.csv").write_bytes(b"\x00\xff not,a\ncsv")
    rep = C.log_daily_swaps(panel, lake, NOW)
    assert rep["status"] == "LOGGED_WITH_UNREADABLE" and len(rep["unreadable_logs"]) == 1
    C.main(["--panel", str(panel), "--terms", str(tmp_path / "noterms"),
            "--universe", str(tmp_path / "nouni"), "--lake-dir", str(lake),
            "--out", str(tmp_path / "carry_state.json")])
    out = capsys.readouterr().out
    assert "swap log LOGGED_WITH_UNREADABLE" in out
    assert "1 unreadable swap log(s) skipped" in out and "EURUSD" in out
