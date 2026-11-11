"""THE BOX PUBLISHES HOW FRESH ITS BARS AND TICKS ARE, NOT THE BARS THEMSELVES.

The bar parquets stay off the sync wire (a parquet backlog killed every push with HTTP 408), so
the repository's copies stop where they were last committed and cannot show a live feed from a
dead one. `research/bars_state.py` writes `desks/mt5/data/BARS_STATE.json` from parquet FOOTERS,
the core, always-run hourly leg `bars_state` runs it before `desk_health` (its named consumer) and
`publish_state`, and `$reportPaths` carries it.

v2 (audit of f8167d3e): the stamps are BROKER wall time, so they are labelled `time_clock:
broker` and every age comes from a true UTC source (the server anchor, the file mtime, the
recorder's last_run); a bad tape_state entry costs its own row only; the no-statistics fallback
is bounded; future and epoch-0 stamps are UNMEASURED; account-like names and keys never publish;
the summary verdict is a measured share. The login fence lives beside the other writers in
tests/ops/test_published_state_withholds_login.py.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
SYNC = DESK / "scripts" / "sync_shadow_to_git.ps1"
REL = "desks/mt5/data/BARS_STATE.json"

for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import bars_state as bs  # noqa: E402

#: 2026-10-21 is US daylight time (EDT, UTC-4), so the server (New York + 7h) is UTC+3.
NOW = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)
FAKE_ACCOUNT = "5551234"


def _load(name: str, rel: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


health = _load("_quant_bars_state_desk_health", "desks/mt5/scripts/check_desk_health.py")


def _bars(path: Path, end: str, n: int, col: str, *, row_group: int | None = None,
          stats: bool = True) -> None:
    idx = pd.date_range(end=end, periods=n, freq="1min", tz="UTC", name=col)
    df = pd.DataFrame({"open": 1.0, "close": 1.0}, index=idx)
    pq.write_table(pa.Table.from_pandas(df), path, row_group_size=row_group or n,
                   write_statistics=stats)


def _ticks(path: Path, last_ms: int, n: int = 5) -> None:
    ms = [last_ms - 1000 * i for i in range(n)][::-1]
    pq.write_table(pa.table({"time_msc": pa.array(ms, pa.int64()),
                             "bid": [1.0] * n, "ask": [1.1] * n,
                             "time": pa.array([m // 1000 for m in ms], pa.int64()),
                             "ts": pa.array(ms, type=pa.timestamp("ms", tz="UTC"))}), path)


def _ms(wall: datetime) -> int:
    return int(wall.replace(tzinfo=UTC).timestamp() * 1000)


@pytest.fixture()
def desk(tmp_path: Path) -> dict[str, Path]:
    uni = tmp_path / "universe"
    ticks = tmp_path / "tape" / "ticks"
    uni.mkdir(parents=True)
    ticks.mkdir(parents=True)
    # Broker wall 11:59 on 2026-10-21 = 08:59 UTC (server UTC+3).
    _bars(uni / "XAUUSD_M1.parquet", "2026-10-21 11:59", 300, "timestamp", row_group=100)
    _bars(uni / "EURUSD_H1.parquet", "2026-10-20 22:00", 50, "time")
    (uni / "universe.json").write_text("{}", "utf-8")       # not a bar file: ignored
    (uni / "XAUUSD_scalp_source.json").write_text("{}", "utf-8")
    (ticks / "XAUUSD").mkdir()
    last = _ms(datetime(2026, 10, 21, 11, 58, 30))
    _ticks(ticks / "XAUUSD" / "2026-10-20.parquet", last - 86_400_000)
    _ticks(ticks / "XAUUSD" / "20261021.parquet", last)       # moat_silver's naming, newest
    state = tmp_path / "tape" / "tape_state.json"
    state.write_text(json.dumps({"XAUUSD": {"last_tick_ms": last - 60_000,
                                            "last_run": "2026-10-21T11:00:00+00:00"},
                                 "GBPUSD": {"last_tick_ms": last}}), "utf-8")
    return {"universe": uni, "ticks": ticks, "tape_state": state}


# ------------------------------------------------------------------ fields and the broker clock
def test_fields_on_small_temp_parquets_and_tick_files(desk: dict[str, Path]) -> None:
    doc = bs.measure(**desk, now=NOW)
    assert doc["schema"] == "bars_state/2"
    assert doc["generated_at"] == "2026-10-21T12:00:00+00:00"
    assert doc["host"] and doc["time_clock"] == "broker" and doc["utc_conversion"]
    bars = {(r["symbol"], r["timeframe"]): r for r in doc["bars"]}
    assert set(bars) == {("XAUUSD", "M1"), ("EURUSD", "H1")}
    m1 = bars[("XAUUSD", "M1")]
    assert m1["status"] == "MEASURED" and m1["row_count"] == 300
    assert m1["time_clock"] == "broker"
    assert m1["last_bar_time"] == "2026-10-21T11:59:00", "broker wall time, no UTC offset"
    assert m1["last_bar_time_utc"] == "2026-10-21T08:59:00+00:00"
    assert m1["age_h"] == pytest.approx(3.02, abs=0.01), "age from the converted UTC time"
    assert m1["source"] == "footer_statistics"
    assert datetime.fromisoformat(m1["file_mtime"]).tzinfo is not None
    assert isinstance(m1["mtime_age_h"], float)
    x = {r["symbol"]: r for r in doc["tape"]}["XAUUSD"]
    assert x["status"] == "MEASURED" and x["time_clock"] == "broker"
    assert x["last_tick"] == "2026-10-21T11:58:30"
    assert x["last_tick_utc"] == "2026-10-21T08:58:30+00:00"
    assert x["partition"] == "XAUUSD/20261021.parquet" and x["partition_day"] == "2026-10-21"
    assert x["partitions"] == 2 and x["row_count"] == 5
    assert x["tape_state_last_tick"] == "2026-10-21T11:57:30"
    assert x["tape_state_last_run"] == "2026-10-21T11:00:00+00:00"
    assert x["tape_state_last_run_age_h"] == pytest.approx(1.0)
    late = bs.measure(**desk, now=NOW - timedelta(hours=2))
    xl = {r["symbol"]: r for r in late["tape"]}["XAUUSD"]
    assert xl["tape_state_last_run"] is None and xl["tape_state_last_run_reason"]
    gbp = {r["symbol"]: r for r in doc["tape"]}["GBPUSD"]
    assert gbp["status"] == "UNMEASURED" and "last_tick" not in gbp
    s = doc["summary"]
    assert s["newest_bar_time"] == "2026-10-21T11:59:00"
    assert s["newest_bar_time_utc"] == "2026-10-21T08:59:00+00:00"
    assert s["newest_bar_age_h"] == pytest.approx(3.02, abs=0.01)
    assert s["newest_tick_age_h"] == pytest.approx(3.03, abs=0.01)
    assert s["bars_verdict"] == "MEASURED" and s["tape_verdict"] == "PARTIAL"
    assert s["verdict"] == "PARTIAL" and doc["budget_exhausted"] is False


@pytest.mark.parametrize(("wall", "utc"), [
    (datetime(2026, 7, 1, 10, 0), datetime(2026, 7, 1, 7, 0, tzinfo=UTC)),     # summer, UTC+3
    (datetime(2026, 1, 15, 10, 0), datetime(2026, 1, 15, 8, 0, tzinfo=UTC)),   # winter, UTC+2
])
def test_broker_time_is_converted_through_the_server_anchor(wall: datetime,
                                                             utc: datetime) -> None:
    assert bs.ANCHOR is not None
    assert bs.broker_to_utc(wall) == utc


def test_no_anchor_means_no_age_never_a_broker_stamp_read_as_utc(desk: dict[str, Path],
                                                                  monkeypatch) -> None:
    monkeypatch.setattr(bs, "ANCHOR", None)
    doc = bs.measure(**desk, now=NOW)
    m1 = {(r["symbol"], r["timeframe"]): r for r in doc["bars"]}[("XAUUSD", "M1")]
    assert m1["status"] == "MEASURED" and m1["last_bar_time"] == "2026-10-21T11:59:00"
    assert m1["age_h"] is None and m1["last_bar_time_utc"] is None and m1["age_reason"]
    assert doc["summary"]["newest_bar_age_h"] is None
    assert isinstance(doc["summary"]["newest_bar_file_mtime_age_h"], float)


# ------------------------------------------------------------------ bounded and sane
def test_footer_without_statistics_reads_only_the_last_row_group(tmp_path: Path) -> None:
    p = tmp_path / "AUDUSD_M5.parquet"
    _bars(p, "2026-10-21 10:00", 40, "time", row_group=10, stats=False)
    m = bs.last_time(p)
    assert m["status"] == "MEASURED" and m["source"] == "last_row_group"
    assert m["wall"] == datetime(2026, 10, 21, 10, 0) and m["row_count"] == 40


def test_an_oversized_row_group_without_statistics_is_not_read(tmp_path: Path,
                                                               monkeypatch) -> None:
    p = tmp_path / "AUDUSD_M5.parquet"
    _bars(p, "2026-10-21 10:00", 40, "time", row_group=40, stats=False)
    monkeypatch.setattr(bs, "FALLBACK_MAX_ROWS", 10)
    m = bs.last_time(p)
    assert m["status"] == "UNMEASURED" and "too large" in m["reason"]
    monkeypatch.setattr(bs, "FALLBACK_MAX_ROWS", 2_000_000)
    monkeypatch.setattr(bs, "FALLBACK_MAX_BYTES", 8)
    assert bs.last_time(p)["status"] == "UNMEASURED"


def test_future_and_epoch_zero_stamps_are_unmeasured(desk: dict[str, Path]) -> None:
    uni = desk["universe"]
    _bars(uni / "FUTURE_H1.parquet", "2100-01-01 00:00", 5, "time")
    pq.write_table(pa.table({"time": pa.array([0, 0], pa.timestamp("s", tz="UTC"))}),
                   uni / "EPOCH_H1.parquet")
    doc = bs.measure(**desk, now=NOW)
    rows = {r["symbol"]: r for r in doc["bars"]}
    assert rows["FUTURE"]["status"] == "UNMEASURED" and "future" in rows["FUTURE"]["reason"]
    assert rows["EPOCH"]["status"] == "UNMEASURED" and "implausible" in rows["EPOCH"]["reason"]
    for r in (rows["FUTURE"], rows["EPOCH"]):
        assert "last_bar_time" not in r and "age_h" not in r
    assert doc["summary"]["newest_bar_time"] == "2026-10-21T11:59:00"


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
    gone = bs.measure(universe=tmp_path / "nope", ticks=tmp_path / "nope2",
                      tape_state=tmp_path / "nope3.json", now=NOW)
    assert gone["summary"]["verdict"] == "UNMEASURED" and gone["notes"]["bars_reason"]


def test_a_bad_tape_state_entry_costs_its_own_row_only(desk: dict[str, Path], tmp_path: Path,
                                                       monkeypatch) -> None:
    """Audit: NaN raised ValueError and 1e20 OSError, and the whole report was not written."""
    state = json.loads(desk["tape_state"].read_text("utf-8"))
    state.update({"NANSYM": {"last_tick_ms": float("nan")},
                  "BIGSYM": {"last_tick_ms": 1e20},
                  "STRSYM": {"last_tick_ms": "yesterday", "last_run": ["x"]},
                  "NOTDICT": 7,
                  "NESTED": {"last_tick_ms": 1, "last_run": {"acct_no": int(FAKE_ACCOUNT)}}})
    desk["tape_state"].write_text(json.dumps(state), "utf-8")
    real = bs.measure
    monkeypatch.setattr(bs, "measure", lambda **k: real(**k, now=NOW))
    out = tmp_path / "BARS_STATE.json"
    assert bs.main(["--out", str(out), "--universe", str(desk["universe"]),
                    "--ticks", str(desk["ticks"]), "--tape-state", str(desk["tape_state"])]) == 0
    text = out.read_text("utf-8")
    assert FAKE_ACCOUNT not in text, "a nested value in last_run was republished"
    doc = json.loads(text)
    tape = {r["symbol"]: r for r in doc["tape"]}
    assert tape["XAUUSD"]["status"] == "MEASURED", "one bad entry must not cost the others"
    for sym in ("NANSYM", "BIGSYM", "STRSYM", "NOTDICT", "NESTED"):
        assert tape[sym]["status"] == "UNMEASURED"
        assert tape[sym]["tape_state_last_run"] is None
        assert "tape_state_last_tick" not in tape[sym]


def test_account_like_names_and_keys_never_publish(desk: dict[str, Path], tmp_path: Path,
                                                   monkeypatch) -> None:
    (desk["ticks"] / FAKE_ACCOUNT).mkdir()
    _ticks(desk["ticks"] / FAKE_ACCOUNT / "2026-10-21.parquet", _ms(datetime(2026, 10, 21, 9)))
    _ticks(desk["ticks"] / "XAUUSD" / "55512345.parquet", _ms(datetime(2026, 10, 21, 9)))
    _bars(desk["universe"] / f"{FAKE_ACCOUNT}_H1.parquet", "2026-10-21 09:00", 5, "time")
    real = bs.measure
    monkeypatch.setattr(bs, "measure", lambda **k: {
        **real(**k, now=NOW), "account": {"login": 1}, "login": 1, "acct_no": 2, "mt5_login": 3,
        "accountLogin": 4, "nested": [{"Acct-Number": 5, "keep": 6}]})
    out = tmp_path / "BARS_STATE.json"
    assert bs.main(["--out", str(out), "--universe", str(desk["universe"]),
                    "--ticks", str(desk["ticks"]), "--tape-state", str(desk["tape_state"])]) == 0
    text = out.read_text("utf-8")
    assert FAKE_ACCOUNT not in text and "5551-23-45" not in text
    doc = json.loads(text)
    for k in ("account", "login", "acct_no", "mt5_login", "accountLogin"):
        assert k not in doc
    assert doc["nested"] == [{"keep": 6}]
    assert doc["notes"]["redacted_names"] == 2
    x = {r["symbol"]: r for r in doc["tape"]}["XAUUSD"]
    # v2.1: an 8-digit YYYYMMDD file name is a digit run like any other; the ISO day survives.
    assert x["invalid_partition_names"] == 1
    assert x["partition"] == f"XAUUSD/{bs.REDACTED}.parquet" and x["partition_day"] == "2026-10-21"
    assert bs.partition_day("55512345") is None and bs.partition_day("20261021") == "2026-10-21"


def test_the_summary_verdict_is_a_measured_share(tmp_path: Path) -> None:
    uni = tmp_path / "u"
    uni.mkdir()
    _bars(uni / "AAA_H1.parquet", "2026-10-21 10:00", 5, "time")
    for i in range(4):
        (uni / f"BAD{i}_H1.parquet").write_bytes(b"x")
    doc = bs.measure(universe=uni, ticks=tmp_path / "t", tape_state=tmp_path / "s.json",
                     now=NOW)
    assert doc["summary"]["bars_measured_share"] == 0.2
    assert doc["summary"]["bars_verdict"] == "PARTIAL", "one file in five is not MEASURED"
    for i in range(4):
        _bars(uni / f"BAD{i}_H1.parquet", "2026-10-21 10:00", 5, "time")
    doc = bs.measure(universe=uni, ticks=tmp_path / "t", tape_state=tmp_path / "s.json",
                     now=NOW)
    assert doc["summary"]["bars_verdict"] == "MEASURED"
    assert bs.MEASURED_SHARE == doc["summary"]["measured_share_threshold"] == 0.8


def test_the_time_budget_is_honoured(desk: dict[str, Path]) -> None:
    ticks = iter(range(0, 10_000, 10))       # every clock read advances ten seconds
    doc = bs.measure(**desk, budget_s=15.0, clock=lambda: next(ticks), now=NOW)
    assert doc["budget_exhausted"] is True
    skipped = [r for r in doc["bars"] + doc["tape"] if r.get("reason") == "time budget exhausted"]
    assert skipped, "nothing was cut although the budget was exceeded"
    for r in skipped:
        assert r["status"] == "UNMEASURED" and "last_bar_time" not in r and "last_tick" not in r
    fast = bs.measure(**desk, now=NOW)
    assert fast["elapsed_s"] < bs.DEFAULT_BUDGET_S and fast["budget_exhausted"] is False


# ------------------------------------------------------------------ the consumer: desk_health
def _report(tmp_path: Path, *, bar_age: float | None, tick_age: float | None,
            generated: datetime = NOW, verdict: str = "MEASURED") -> Path:
    p = tmp_path / "BARS_STATE.json"
    p.write_text(json.dumps({"generated_at": generated.isoformat(), "summary": {
        "newest_bar_age_h": bar_age, "newest_tick_age_h": tick_age,
        "newest_bar_time_utc": "x", "newest_tick_time_utc": "y",
        "bars_verdict": verdict, "tape_verdict": verdict,
        "newest_bar_file_mtime_age_h": 0.1}}), "utf-8")
    return p


def _findings(path: Path, now: datetime) -> list[dict[str, str]]:
    health._FINDINGS.clear()
    health.check_bars_state(path, now=now)
    return list(health._FINDINGS)


def test_desk_health_reads_bar_and_tick_ages(tmp_path: Path) -> None:
    f = _findings(_report(tmp_path, bar_age=0.5, tick_age=0.2), NOW)   # a Wednesday
    assert [x["level"] for x in f] == ["OK", "OK"]
    assert "newest bar 0.5h" in f[0]["message"] and "newest tick 0.2h" in f[1]["message"]


def test_desk_health_flags_a_stale_feed_and_a_stale_report(tmp_path: Path) -> None:
    f = _findings(_report(tmp_path, bar_age=5.0, tick_age=0.2), NOW)
    assert f[0]["level"] == "PROBLEM" and "bar feed is STALE" in f[0]["message"]
    f = _findings(_report(tmp_path, bar_age=0.5, tick_age=0.2,
                          generated=NOW - timedelta(hours=6)), NOW)
    assert f[0]["level"] == "PROBLEM" and "stopped producing" in f[0]["message"]


def test_desk_health_allows_the_fx_weekend(tmp_path: Path) -> None:
    sunday = datetime(2026, 10, 25, 12, 0, tzinfo=UTC)
    f = _findings(_report(tmp_path, bar_age=40.0, tick_age=40.0, generated=sunday), sunday)
    assert [x["level"] for x in f] == ["OK", "OK"] and "market weekend" in f[0]["message"]


def test_desk_health_absent_or_unmeasured_is_unknown_never_ok(tmp_path: Path) -> None:
    f = _findings(tmp_path / "absent.json", NOW)
    assert [x["level"] for x in f] == ["UNKNOWN"]
    f = _findings(_report(tmp_path, bar_age=None, tick_age=0.1), NOW)
    assert f[0]["level"] == "UNKNOWN" and "UNMEASURED" in f[0]["message"]
    f = _findings(_report(tmp_path, bar_age=0.5, tick_age=0.1, verdict="PARTIAL"), NOW)
    assert all(x["level"] == "UNKNOWN" for x in f)


def test_desk_health_runs_the_check_and_names_the_artifact() -> None:
    src = (DESK / "scripts" / "check_desk_health.py").read_text("utf-8")
    assert '"BARS_STATE.json"' in src, "the literal the dead-architecture census joins on"
    main = src[src.index("def main("):]
    assert "check_bars_state()" in main


# ------------------------------------------------------------------ wiring and publication
def test_the_runtime_attestation_carries_the_leg() -> None:
    doc = json.loads((ROOT / "docs" / "research" / "runtime_state.json").read_text("utf-8"))
    rows = [r for r in doc["organs"] if r.get("organ") == "leg:bars_state"]
    assert len(rows) == 1
    assert rows[0]["code"] == ["desks/mt5/research/bars_state.py"]
    assert rows[0]["artifact_declared"] == REL
    assert rows[0]["clock"] == "hourly_cycle:bars_state"


def _report_paths() -> list[str]:
    src = SYNC.read_text("utf-8", errors="ignore")
    start = src.index("$reportPaths = @(")
    block = src[start:src.index("\n)", start)]
    return [p for p in re.findall(r'"([^"]+)"', block) if "/" in p]


def test_it_is_in_the_publish_list_and_bars_stay_off_the_wire() -> None:
    from libs.ops import release, state_publication
    assert REL in _report_paths()
    wire = state_publication.published_paths(ROOT)
    assert REL in wire and release.is_state_path(REL)
    assert not [p for p in wire if p.endswith(".parquet") and "/universe/" in p], (
        "bar parquets crossed the wire")


def test_it_is_a_core_leg_before_its_consumer_and_publication() -> None:
    import hourly_cycle as hc

    from libs.research import layers
    src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert "bars_state" in hc.CORE_LEGS
    at = src.index('_costed("bars_state"')
    assert at < src.index('_costed("desk_health"') < src.index('_costed("publish_state"')
    assert layers.LEG_LAYER["bars_state"] == "meta"


def test_it_is_always_run_so_rotation_never_skips_it_on_overrun() -> None:
    import hourly_cycle as hc

    from libs.ops import leg_rotation as LR
    assert "bars_state" in LR.ALWAYS_RUN
    roster = ["bars_state", "filler"]
    att = LR.Attendance(runs={"bars_state": 50, "filler": 0})
    att.last_at["bars_state"] = datetime.now(UTC).isoformat()
    att.costs["bars_state"] = [9_000.0]
    att.costs["filler"] = [1.0]
    dec = LR.plan_pass(roster, att, plan="core", budget_s=1.0)
    assert "bars_state" in dec.admitted and "bars_state" not in dec.deferred
    ok, why = dec.should_run("bars_state", att, elapsed_s=100_000.0)
    assert ok, f"bars_state was yielded on overrun: {why}"
    src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '"research/bars_state.py", "--budget-s", "20"' in src
    assert hc.LEG_BUDGET_SEC["bars_state"] == 60


# ------------------------------------------------------------------ v2.1: the audit's should-fixes
def test_v21_digit_runs_are_redacted_anywhere_in_keys_and_values() -> None:
    assert bs.account_like("XAU5551234") and bs.account_like("acct_55512_x")
    assert not bs.account_like("US30") and not bs.account_like("JP225")
    doc = {"host": "vmi3571445", "k5551234": "keep", "note": "login 5551234 on file",
           "nested": [{"code": 5551234, "f": 55512.5, "small": 1234, "ok": True}],
           "row_count": 54205, "age_h": 12345.6, "when": "2026-10-21T11:59:00+00:00"}
    out = bs._scrub(doc)
    text = json.dumps(out)
    assert not re.search(r"\d{5,}", text.replace("54205", "").replace("12345.6", "")), text
    assert out["host"] == f"vmi{bs.REDACTED}" and out[f"k{bs.REDACTED}"] == "keep"
    assert out["note"] == f"login {bs.REDACTED} on file"
    assert out["nested"] == [{"code": bs.REDACTED, "f": bs.REDACTED, "small": 1234, "ok": True}]
    assert out["row_count"] == 54205 and out["age_h"] == 12345.6, "measurements are not accounts"
    assert out["when"] == doc["when"], "an ISO stamp has no 5-digit run and must survive"


def test_v21_every_number_the_report_emits_is_a_declared_measurement(desk: dict[str, Path]
                                                                      ) -> None:
    doc = bs.measure(**desk, now=NOW)
    seen: set[str] = set()

    def walk(o: Any, key: str | None = None) -> None:
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, k)
        elif isinstance(o, list):
            for v in o:
                walk(v, key)
        elif isinstance(o, (int, float)) and not isinstance(o, bool) and key:
            seen.add(key)
    walk(doc)
    assert seen <= bs._MEASUREMENT_KEYS, seen - bs._MEASUREMENT_KEYS


def test_v21_error_fields_carry_type_and_errno_never_a_path(tmp_path: Path) -> None:
    secret = str(tmp_path / "C_Users_someone" / "secret_dir")
    exc = PermissionError(13, "Permission denied", secret)
    assert bs._exc_reason(exc) == "PermissionError errno=13"
    assert bs._exc_reason(ValueError(f"bad value at {secret}")) == "ValueError"
    assert health._exc_reason(exc) == "PermissionError errno=13"
    bad = tmp_path / "u"
    bad.mkdir()
    (bad / "XAUUSD_H1.parquet").write_bytes(b"not a parquet at " + secret.encode())
    doc = bs.measure(universe=bad, ticks=tmp_path / "t", tape_state=tmp_path / "s.json",
                     now=NOW)
    assert str(tmp_path) not in json.dumps(doc)
    assert re.fullmatch(r"[A-Za-z]+( errno=\d+)?", doc["bars"][0]["reason"]), doc["bars"][0]
    # The consumer's unreadable-report finding is the same shape.
    rep = tmp_path / "BARS_STATE.json"
    rep.mkdir()                       # reading a directory raises IsADirectoryError with the path
    f = _findings(rep, NOW)
    assert f[0]["level"] == "UNKNOWN" and str(tmp_path) not in f[0]["message"]
    src = (DESK / "research" / "bars_state.py").read_text("utf-8")
    assert "str(exc)[" not in src and ": {exc}" not in src


def test_v21_unknown_market_state_never_gets_the_weekend_allowance(tmp_path: Path,
                                                                   monkeypatch) -> None:
    monkeypatch.setattr(health, "_market_closed", lambda now: None)
    sunday = datetime(2026, 10, 25, 12, 0, tzinfo=UTC)
    f = _findings(_report(tmp_path, bar_age=40.0, tick_age=1.0, generated=sunday), sunday)
    assert [x["level"] for x in f] == ["UNKNOWN", "OK"], f
    assert "limit 2h" in f[0]["message"] and "market state unknown" in f[0]["message"]
    assert "limit 52h" not in json.dumps(f)


# The two US/EU DST gap windows of 2026: the US moves on 03-08 and 11-01, Europe on 03-29 and
# 10-25. The server is New York + 7h, so its H1 week runs broker Fri 23:00 (last bar) to
# Mon 00:00 (first bar) in EVERY week, and the broker's UTC offset follows New York, not Europe.
@pytest.mark.parametrize("fri_last,mon_first,utc_last,utc_first,gap_h", [
    # winter -> US summer across 03-08 (the weekend the US clock moves): 48h of true UTC
    ("2026-03-06T23:00", "2026-03-09T00:00", "2026-03-06T21:00", "2026-03-08T21:00", 48),
    # inside the March gap week (US summer, Europe still winter): UTC+3, a 49h weekend
    ("2026-03-20T23:00", "2026-03-23T00:00", "2026-03-20T20:00", "2026-03-22T21:00", 49),
    # across Europe's 03-29 change: nothing moves on the server clock
    ("2026-03-27T23:00", "2026-03-30T00:00", "2026-03-27T20:00", "2026-03-29T21:00", 49),
    # across Europe's 10-25 change into the October gap week: still UTC+3
    ("2026-10-23T23:00", "2026-10-26T00:00", "2026-10-23T20:00", "2026-10-25T21:00", 49),
    # out of the gap week across the US's 11-01 change: 50h of true UTC
    ("2026-10-30T23:00", "2026-11-02T00:00", "2026-10-30T20:00", "2026-11-01T22:00", 50),
])
def test_v21_dst_gap_weeks_pin_the_broker_weekend(fri_last: str, mon_first: str, utc_last: str,
                                                  utc_first: str, gap_h: int) -> None:
    last = bs.broker_to_utc(datetime.fromisoformat(fri_last))
    first = bs.broker_to_utc(datetime.fromisoformat(mon_first))
    assert last == datetime.fromisoformat(utc_last).replace(tzinfo=UTC)
    assert first == datetime.fromisoformat(utc_first).replace(tzinfo=UTC)
    assert (first - last) == timedelta(hours=gap_h) and gap_h + 1 < health.WEEKEND_STALE_H
    assert bs.utc_to_broker(last) == datetime.fromisoformat(fri_last)
    # The FX weekend reading: closed from server Sat 00:00 to Mon 01:00, open on either side.
    sat0 = last + timedelta(hours=1)
    assert health._market_closed(sat0 - timedelta(minutes=1)) is False
    assert health._market_closed(sat0) is True
    assert health._market_closed(first + timedelta(minutes=59)) is True
    assert health._market_closed(first + timedelta(hours=1)) is False


@pytest.mark.parametrize("monday,offset_h", [("2026-03-16", 3.0), ("2026-10-26", 3.0),
                                             ("2026-03-02", 2.0), ("2026-11-02", 2.0)])
def test_v21_gap_weeks_follow_new_york_not_europe(monday: str, offset_h: float) -> None:
    from zoneinfo import ZoneInfo
    m = datetime.fromisoformat(monday).date()
    assert bs.ANCHOR is not None
    assert bs._anchor_offset_h(m, bs.ANCHOR) == offset_h
    anc = bs.fx_week_bounds(m, None)
    alt = bs.fx_week_bounds(m, ZoneInfo(bs.EURO_WALL_TZ))
    assert anc is not None and alt is not None
    assert anc == (datetime.fromisoformat(f"{monday}T00:00"),
                   datetime.fromisoformat(f"{monday}T00:00") + timedelta(days=5))
    gap = monday in ("2026-03-16", "2026-10-26")
    assert (anc != alt) is gap, "only the US/EU gap weeks tell the anchor from a European clock"
    if gap:
        assert alt[0] == anc[0] - timedelta(hours=1)


def test_v21_desk_health_across_the_gap_weekends(tmp_path: Path) -> None:
    # Sunday 22:30 UTC on 11-01 is server Mon 00:30: still the weekend; the Fri 23:00 bar
    # (20:00Z Fri) is 50.5h old and inside the allowance.
    t = datetime(2026, 11, 1, 22, 30, tzinfo=UTC)
    f = _findings(_report(tmp_path, bar_age=50.5, tick_age=50.5, generated=t), t)
    assert [x["level"] for x in f] == ["OK", "OK"], f
    # Monday 01:30 server on 10-26 (22:30Z Sunday): the market is open; a Friday bar is STALE.
    t = datetime(2026, 10, 25, 22, 30, tzinfo=UTC)
    f = _findings(_report(tmp_path, bar_age=50.5, tick_age=0.1, generated=t), t)
    assert f[0]["level"] == "PROBLEM" and "STALE" in f[0]["message"]


def _h1_week(path: Path, open_wall: str, hours: int = 120) -> None:
    """`hours` consecutive H1 broker stamps from `open_wall` (120 from an open = one FX week)."""
    idx = pd.date_range(start=pd.Timestamp(open_wall, tz="UTC"), periods=hours, freq="1h",
                        name="time")
    df = pd.DataFrame({"open": 1.0, "close": 1.0}, index=idx)
    pq.write_table(pa.Table.from_pandas(df), path)


def test_v21_dst_check_agrees_with_the_anchor_and_catches_a_european_clock(tmp_path: Path
                                                                           ) -> None:
    uni = tmp_path / "u"
    uni.mkdir()
    _h1_week(uni / "EURUSD_H1.parquet", "2026-10-26 00:00")       # NY+7: Mon 00:00..Fri 23:00
    # A European-wall broker in the same week: Sun 23:00 open, Fri 22:00 last bar.
    _h1_week(uni / "GBPUSD_H1.parquet", "2026-10-25 23:00", hours=120)
    after = datetime(2026, 10, 31, 12, tzinfo=UTC)
    rep = bs.dst_check(datetime(2026, 10, 26).date(), datetime(2026, 10, 30).date(),
                       universe=uni, symbols=("EURUSD", "GBPUSD", "USDJPY"), now=after)
    rows = {r["file"]: r for r in rep["files"]}
    eu = rows["EURUSD_H1.parquet"]
    assert eu["status"] == "AGREES" and eu["weeks"][0]["gap_week"] is True
    assert eu["weeks"][0]["first_bar"] == "2026-10-26T00:00:00"
    assert eu["weeks"][0]["last_bar"] == "2026-10-30T23:00:00"
    assert eu["weeks"][0]["anchor_utc_offset_h"] == [3.0] * 5
    gb = rows["GBPUSD_H1.parquet"]
    assert gb["status"] == "DISAGREES" and gb["weeks"][0]["fits"] == "europe_wall"
    assert rows["USDJPY_H1.parquet"]["status"] == "UNMEASURED"
    assert rep["verdict"] == "DISAGREES" and rep["window_complete"] is True
    before = bs.dst_check(datetime(2026, 10, 26).date(), datetime(2026, 10, 30).date(),
                          universe=uni, symbols=("EURUSD",), now=NOW)
    assert before["window_complete"] is False


def test_v21_dst_check_cli_is_read_only(tmp_path: Path, capsys) -> None:
    uni = tmp_path / "u"
    uni.mkdir()
    _h1_week(uni / "EURUSD_H1.parquet", "2026-03-16 00:00")
    before = sorted(p.name for p in tmp_path.rglob("*"))
    rc = bs.main(["--dst-check", "2026-03-16", "2026-03-20", "--universe", str(uni),
                  "--dst-symbols", "EURUSD", "--out", str(tmp_path / "never.json")])
    assert rc == 0
    assert sorted(p.name for p in tmp_path.rglob("*")) == before, "the check wrote a file"
    rep = json.loads(capsys.readouterr().out)
    assert rep["verdict"] == "AGREES" and rep["schema"] == "bars_state_dst_check/1"
    assert bs.main(["--dst-check", "2026-10-26", "2026-10-30", "--universe", str(tmp_path / "x"),
                    "--dst-symbols", "EURUSD"]) == 2, "nothing on disk is UNMEASURED, exit 2"
