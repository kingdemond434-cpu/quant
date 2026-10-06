"""Acquisition is not promotion: short history kept, every column and archive member reached by
cursor, unchanged bytes skipped, keyed URLs given an access state, first value wins, and the
acquired series reach the representation factory and record who read them."""

from __future__ import annotations

import io
import json
import sys
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
if str(DESK) not in sys.path:
    sys.path.insert(0, str(DESK))

from research import acquire_datasets as A  # noqa: E402

from libs.data import dataset_use as U  # noqa: E402


def _cert(authority: bool = True) -> Any:
    return SimpleNamespace(authority=authority, certificate_id="c1",
                           span={"schema_hash": "h"}, failures=lambda: [],
                           unmeasured=lambda: [] if authority else ["revision"])


def _csv(rows: int, cols: int, freq: str = "D", shift: float = 0.0) -> bytes:
    idx = pd.date_range("2010-01-31", periods=rows, freq=freq)
    df = pd.DataFrame({"date": idx.strftime("%Y-%m-%d")})
    for c in range(cols):
        df[f"c{c}"] = [float(i * (c + 1)) + shift + c / 7 for i in range(rows)]
    return df.to_csv(index=False).encode()


@pytest.fixture
def desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    monkeypatch.setattr(A, "STORE", tmp_path / "acquired")
    monkeypatch.setattr(A, "REGISTRY", tmp_path / "acquired" / "registry.json")
    monkeypatch.setattr(A, "REPORT", tmp_path / "report.json")
    monkeypatch.setattr(A, "ASIA_SOURCES", tmp_path / "asia_sources.json")
    monkeypatch.setattr(A, "certify", lambda meta, frame, now: _cert(True))
    monkeypatch.setattr(A, "write_certificate", lambda cert: None)
    monkeypatch.setattr(U, "USE_DIR", tmp_path / "use")
    served: dict[str, bytes] = {}
    monkeypatch.setattr(A, "_fetch", lambda url: (served[url], "text/csv"))
    state: dict[str, Any] = {"served": served, "urls": []}
    monkeypatch.setattr(A, "_endpoints",
                        lambda limit, keyed=None: [(u, "example.test") for u in state["urls"]])
    return state


def test_short_monthly_history_is_kept_and_withheld_from_the_vocabulary(desk):
    url = "https://example.test/monthly.csv"
    desk["served"][url], desk["urls"] = _csv(120, 1, freq="ME"), [url]
    report = A.acquire()
    reg = json.loads(A.REGISTRY.read_text())
    (name,) = reg["by_url"][url]["series"]
    meta = reg["series"][name]
    assert meta["rows"] == 120 and meta["history_status"] == "INSUFFICIENT_HISTORY"
    assert meta["research_eligible"] is False
    assert report["insufficient_history"] == 1
    assert A.acquired_series() == {}                     # retention is not research eligibility
    assert name in A.acquired_series(min_rows=100)


def test_every_column_is_reached_by_a_resumable_cursor_then_unchanged(desk, monkeypatch):
    monkeypatch.setattr(A, "COLUMNS_PER_RUN", 4)
    url = "https://example.test/wide.csv"
    desk["served"][url], desk["urls"] = _csv(220, 10), [url]
    A.acquire()
    row = json.loads(A.REGISTRY.read_text())["by_url"][url]
    assert len(row["series"]) == 4 and row["cursor_open"] and row["columns_remaining"] == 6
    A.acquire()
    A.acquire()
    row = json.loads(A.REGISTRY.read_text())["by_url"][url]
    assert len(row["series"]) == 10 and not row["cursor_open"]
    report = A.acquire()
    assert report["unchanged"] == 1
    assert json.loads(A.REGISTRY.read_text())["by_url"][url]["status"] == "UNCHANGED"


def test_every_archive_member_becomes_its_own_dataset(desk):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for i in range(3):
            z.writestr(f"table_{i}.csv", _csv(30 + i, 1, shift=i).decode())
        z.writestr("readme.pdf", b"%PDF")
    url = "https://example.test/bulk.zip"
    desk["served"][url], desk["urls"] = buf.getvalue(), [url]
    A.acquire()
    reg = json.loads(A.REGISTRY.read_text())
    members = {reg["series"][n]["member"] for n in reg["by_url"][url]["series"]}
    assert members == {"table_0.csv", "table_1.csv", "table_2.csv"}


def test_archive_members_are_capped_on_inflated_bytes_and_per_window(monkeypatch):
    """A member is read in chunks and abandoned past the cap; a window stops at its cumulative
    budget and the cursor resumes at the member it did not read."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("bomb.csv", b"0" * (3 << 20))           # 3 MiB that deflates to a few KB
        for i in range(4):
            z.writestr(f"t{i}.csv", _csv(30, 1, shift=i).decode())
    raw = buf.getvalue()
    assert A._read_member(raw, "bomb.csv", limit=1 << 20) is None
    assert A._read_member(raw, "t0.csv", limit=1 << 20) is not None
    size = len(A._read_member(raw, "t0.csv") or b"")
    monkeypatch.setattr(A, "MAX_BYTES", 1 << 20)
    monkeypatch.setattr(A, "WINDOW_BYTES", 2 * size + 1)
    names = A._archive_members(raw)
    assert "bomb.csv" not in names                           # an honest declared size is refused early
    out, nxt, left = A._tables(raw, "https://example.test/b.zip", start=0, budget=16)
    assert len(out) <= 2 and nxt < len(names) and left == len(names) - nxt
    out2, nxt2, _ = A._tables(raw, "https://example.test/b.zip", start=nxt, budget=16)
    assert nxt2 > nxt


def test_first_value_wins_revisions_are_counted_and_new_points_appended(desk):
    url = "https://example.test/rev.csv"
    desk["urls"] = [url]
    desk["served"][url] = _csv(20, 1)
    A.acquire()
    revised = pd.read_csv(io.BytesIO(_csv(21, 1)))
    revised.loc[3, "c0"] = 999.0
    desk["served"][url] = revised.to_csv(index=False).encode()
    A.acquire()
    reg = json.loads(A.REGISTRY.read_text())
    (name,) = reg["by_url"][url]["series"]
    frame = pd.read_parquet(reg["series"][name]["path"])
    assert len(frame) == 21 and reg["series"][name]["revisions_seen"] == 1
    assert float(frame["value"].iloc[3]) == 3.0 and float(frame["value_latest"].iloc[3]) == 999.0
    assert reg["series"][name]["points_added_last"] == 1


def test_keyed_urls_get_an_explicit_access_state(tmp_path, monkeypatch):
    monkeypatch.setattr(A, "ASIA_SOURCES", tmp_path / "asia.json")
    (tmp_path / "asia.json").write_text(json.dumps({"sources": [
        {"id": "eia_energy", "url": "https://api.eia.gov/v2/x", "key_env": "EIA_API_KEY"},
        {"id": "bok", "url": "https://ecos.bok.or.kr/api/", "key_env": "BOK_API_KEY"}]}))
    keyed = [("https://api.eia.gov/v2/series?api_key=SECRET", "us"),
             ("https://ecos.bok.or.kr/api/StatisticSearch?apikey=X", "kr"),
             ("https://unknown.test/data?token=abc", "world")]
    rows = A._access_states(keyed, environ={"EIA_API_KEY": "set"})
    states = {r["host"]: r["state"] for r in rows}
    assert states["api.eia.gov"] == "ROUTED:asia_collector:eia_energy"
    assert states["ecos.bok.or.kr"] == "BLOCKED_ON_KEY:BOK_API_KEY"
    assert states["unknown.test"] == "NEEDS_KEY_UNDECLARED"
    assert not any(secret in r["url"] for r in rows for secret in ("SECRET", "=X", "abc"))
    assert rows[0]["url"] == "https://api.eia.gov/v2/series?api_key=REDACTED"


def test_hourly_discovery_calling_convention_exists():
    assert callable(A.main)


def test_reads_are_recorded_with_version_and_go_stale(tmp_path):
    now = datetime(2026, 10, 6, tzinfo=UTC)
    assert U.record_reads("organ_a", {"ds1": "v1"}, use="nowcast", root=tmp_path, now=now)
    assert not U.record_reads("organ_a", {"ds1": "v1"}, use="not_a_use", root=tmp_path, now=now)
    U.record_reads("organ_b", {"ds1": "v2"}, use="risk", root=tmp_path,
                   now=now - timedelta(days=10))
    c = U.census(tmp_path, now=now)
    assert c["ds1"]["live_consumers"] == 1 and c["ds1"]["uses"] == ["nowcast"]
    assert c["ds1"]["consumers"]["organ_b"]["stale"] is True
    assert c["ds1"]["consumers"]["organ_a"]["version"] == "v1"


def test_acquired_series_reach_the_world_model_with_a_late_pit_stamp(desk, monkeypatch, tmp_path):
    from research import world_model as WM
    url = "https://example.test/weekly.csv"
    desk["served"][url], desk["urls"] = _csv(60, 1, freq="W"), [url]
    A.acquire()
    monkeypatch.setattr(WM, "ACQUIRED", A.REGISTRY)
    unmeasured: list[dict[str, str]] = []
    (series,) = WM._acquired_inputs(unmeasured)
    first = series.points[0]
    lag = datetime.fromisoformat(first.available_time) - datetime.fromisoformat(first.period_time)
    assert lag == timedelta(days=3, hours=WM.CLOCK_PAD_H)        # weekly cadence default + pad
    monkeypatch.setattr(WM, "AXES", tmp_path / "no_axes")
    monkeypatch.setattr(WM, "FRED", tmp_path / "no_fred.json")
    monkeypatch.setattr(WM, "REPRESENTATIONS", tmp_path / "no_reps")
    kept = WM.load_inputs()
    assert [s.series_id for s in kept.series] == [series.series_id]
    assert series.series_id in U.census()                        # the kept read was recorded
    reg = json.loads(A.REGISTRY.read_text())
    for meta in reg["series"].values():
        meta["pit_authority"] = False
    A.REGISTRY.write_text(json.dumps(reg))
    assert WM._acquired_inputs(unmeasured) == []
    assert any(u["name"] == "acquired:uncertified" for u in unmeasured)


def test_d18_census_counts_unfed_on_reads(tmp_path):
    from research import dataset_use_census as C
    (tmp_path / "axes").mkdir()
    (tmp_path / "axes" / "alt_kr.json").write_text("{}")
    (tmp_path / "axes" / "macro.json").write_text("{}")
    (tmp_path / "lake").mkdir()
    (tmp_path / "lake" / "pack_x.csv").write_text("a\n")
    (tmp_path / "reg.json").write_text(json.dumps({"series": {"s1": {}}}))
    now = datetime(2026, 10, 6, tzinfo=UTC)
    U.record_reads("world_model", {"axis:alt_kr": "v"}, use="regime_state",
                   root=tmp_path / "use", now=now)
    U.record_reads("old", {"lake:pack_x": "v"}, use="conditioning", root=tmp_path / "use",
                   now=now - timedelta(days=9))
    doc = C.build(now, use_root=tmp_path / "use", acquired=tmp_path / "reg.json",
                  axes=tmp_path / "axes", lake=tmp_path / "lake")
    assert doc["datasets_held"] == 4 and doc["fed"] == 1 and doc["unfed_datasets"] == 3
    status = {r["dataset"]: r["status"] for r in doc["unfed"]}
    assert status == {"acquired:s1": "UNFED", "axis:macro": "UNFED", "lake:pack_x": "STALE"}
    assert doc["fed_by_use"]["regime_state"] == 1 and doc["target"] == 0


def test_discovered_endpoints_hold_a_reserved_share_of_the_pass(tmp_path, monkeypatch):
    monkeypatch.setattr(A, "REGISTRY", tmp_path / "missing.json")
    monkeypatch.setattr(A, "WORLD", tmp_path / "world")
    monkeypatch.setattr(A, "_SEED_ENDPOINTS", ())
    (tmp_path / "world").mkdir()
    rows = [{"host": "catalog.test", "endpoints": [f"https://catalog.test/d{i}.csv"
                                                   for i in range(30)]}]
    (tmp_path / "world" / "discoveries_catalog_20261006.json").write_text(json.dumps(rows))
    out = A._endpoints(40, now=datetime(2026, 10, 6, tzinfo=UTC))
    assert len(out) == 40
    assert sum(1 for _u, h in out if h == "catalog.test") == 10      # a quarter, packs the rest


def test_information_value_prices_novelty_per_fetch_second_without_reading_a_return(tmp_path):
    """ROMAN-1003: a copy of a held series reads near-zero novelty; an orthogonal one near one;
    cost comes from the acquirer's measured fetch; outcome is UNMEASURED until the gauntlet credits it."""
    import numpy as np

    from research import dataset_use_census as C
    rng = np.random.default_rng(7)
    idx = pd.date_range("2010-01-31", periods=120, freq="ME")
    base = np.cumsum(rng.normal(size=120))
    frames = {"a": base, "a_copy": base * 2.0 + 1.0, "orth": np.cumsum(rng.normal(size=120))}
    series, by_url = {}, {}
    for name, vals in frames.items():
        path = tmp_path / f"{name}.parquet"
        pd.DataFrame({"value": vals}, index=idx).to_parquet(path)
        url = f"https://x.test/{name}.csv"
        series[name] = {"path": str(path), "url": url, "refreshed_at": "2026-10-06"}
        by_url[url] = {"series": [name], "bytes": 2_000_000, "visits": 2, "fetch_s_total": 4.0}
    reg = tmp_path / "reg.json"
    reg.write_text(json.dumps({"series": series, "by_url": by_url}))
    value = C.information_value(reg, tmp_path / "no_roi.json")
    assert value["acquired:a_copy"]["novelty"] < 0.01
    assert value["acquired:a_copy"]["nearest"] == "a"
    assert value["acquired:orth"]["novelty"] > 0.8
    assert value["acquired:orth"]["cost"]["fetch_s_per_visit"] == 2.0
    assert value["acquired:orth"]["outcome"]["status"] == "UNMEASURED"
    doc = C.build(datetime(2026, 10, 6, tzinfo=UTC), use_root=tmp_path / "use", acquired=reg,
                  axes=tmp_path / "none", lake=tmp_path / "none", research_roi=tmp_path / "x")
    assert doc["unfed"][0]["dataset"] == "acquired:orth"          # most novel unfed first
    assert doc["information_value"]["near_duplicates"] == 2


def test_every_intermediate_print_is_kept_in_the_revision_log(desk):
    url = "https://example.test/rev3.csv"
    desk["urls"] = [url]
    desk["served"][url] = _csv(20, 1)
    A.acquire()
    for v in (500.0, 600.0):
        frame = pd.read_csv(io.BytesIO(_csv(20, 1)))
        frame.loc[3, "c0"] = v
        desk["served"][url] = frame.to_csv(index=False).encode()
        A.acquire()
    reg = json.loads(A.REGISTRY.read_text())
    (name,) = reg["by_url"][url]["series"]
    path = Path(reg["series"][name]["path"])
    log = pd.read_parquet(path.with_name(path.stem + ".revisions.parquet"))
    assert list(log["value"]) == [500.0, 600.0]                  # the second print survives
    stored = pd.read_parquet(path)
    assert float(stored["value"].iloc[3]) == 3.0 and float(stored["value_latest"].iloc[3]) == 600.0


def test_a_live_capture_is_available_no_earlier_than_the_desk_saw_it(tmp_path, monkeypatch):
    from research import world_model as WM
    idx = pd.date_range("2025-01-05", periods=60, freq="W", tz="UTC")
    seen = [(t + timedelta(days=1)).isoformat() for t in idx]          # backfill-free, live
    seen[-1] = (idx[-1] + timedelta(days=5)).isoformat()                 # seen late but live
    seen[0] = "2026-10-06T00:00:00+00:00"                                # a backfilled point
    pd.DataFrame({"value": range(60), "value_latest": range(60), "first_seen_at": seen},
                 index=idx).to_parquet(tmp_path / "s.parquet")
    reg = tmp_path / "reg.json"
    reg.write_text(json.dumps({"series": {"s": {"path": str(tmp_path / "s.parquet"),
                                                "pit_authority": True}}}))
    monkeypatch.setattr(WM, "ACQUIRED", reg)
    unmeasured: list[dict[str, str]] = []
    (series,) = WM._acquired_inputs(unmeasured)
    last = series.points[-1]
    assert datetime.fromisoformat(last.available_time) == idx[-1] + timedelta(days=5)
    first = series.points[0]
    assert datetime.fromisoformat(first.available_time) == datetime(2026, 10, 6, tzinfo=UTC)
    assert any(u["name"] == "acquired:backfilled_reference" for u in unmeasured)


def test_a_point_without_any_receipt_is_withheld(tmp_path, monkeypatch):
    from research import world_model as WM
    idx = pd.date_range("2025-01-05", periods=60, freq="W", tz="UTC")
    pd.DataFrame({"value": range(60)}, index=idx).to_parquet(tmp_path / "s.parquet")
    reg = tmp_path / "reg.json"
    reg.write_text(json.dumps({"series": {"s": {"path": str(tmp_path / "s.parquet"),
                                                "pit_authority": True}}}))
    monkeypatch.setattr(WM, "ACQUIRED", reg)
    unmeasured: list[dict[str, str]] = []
    assert WM._acquired_inputs(unmeasured) == []
    assert any(u["name"] == "acquired:no_receipt" for u in unmeasured)
    meta = {"path": str(tmp_path / "s.parquet"), "pit_authority": True,
            "acquired_at": "2026-10-01T00:00:00+00:00"}
    reg.write_text(json.dumps({"series": {"s": meta}}))
    (series,) = WM._acquired_inputs([])
    assert all(datetime.fromisoformat(p.available_time) >= datetime(2026, 10, 1, tzinfo=UTC)
               for p in series.points)
