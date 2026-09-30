"""D18 FULL FEED: every enrolled dataset collected on a bounded cycle, parsed to a dated series,
and fed all three uses -- short histories included, without inventing a reading.

Recorded fixtures (tests/fixtures/dataset_full_feed/) and tmp_path only; nothing fetches and nothing
writes box state.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import dataset_series as DS  # noqa: E402

from libs.research import dataset_exploitation as X  # noqa: E402
from libs.research import seat_stamper as SS  # noqa: E402
from research import asia_collector as AC  # noqa: E402
from research import asia_parser as AP  # noqa: E402
from research import dataset_census as DC  # noqa: E402
from research import producer_swarm as ps  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "dataset_full_feed"
NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)


# ------------------------------------------------------------------ collector: bounded cycle
def _src(i: str, cadence: str = "daily") -> dict[str, Any]:
    return {"id": i, "url": f"https://{i}.example/x", "cadence": cadence, "expect": "any"}


def test_never_attempted_and_starved_sources_are_fetched_before_the_evig_order() -> None:
    now = 1_000_000.0
    todo = [_src("rich"), _src("fresh"), _src("never"), _src("starved"), _src("deferred")]
    state = {"rich": {"last_attempt_epoch": now - 21 * 3600},
             "fresh": {"last_attempt_epoch": now - 21 * 3600},
             "starved": {"last_attempt_epoch": now - 5 * 24 * 3600},
             "deferred": {"last_attempt_epoch": now - 21 * 3600, "deferred_streak": 3}}
    # EVIG ranks the never-collected source LAST -- the order that starved it.
    evig = ["rich", "fresh", "starved", "deferred", "never"]
    got = [s["id"] for s in AC.starvation_order(todo, state, now, evig)]
    assert got[0] == "never"
    assert set(got[1:3]) == {"deferred", "starved"} and got[1] == "deferred"
    assert got[3:] == ["rich", "fresh"]          # the rest keep EVIG order


def test_the_pass_stops_inside_the_cycle_cap_it_is_told() -> None:
    b, why = AC.effective_budget(600, 25, env={"QUANT_LEG_BUDGET_S": "300"})
    assert b == 300 - (25 + 12) - AC.WRITE_MARGIN_S and "inside the cycle cap" in why
    assert AC.effective_budget(600, 25, env={})[0] == 600
    assert AC.effective_budget(100, 25, env={"QUANT_LEG_BUDGET_S": "900"})[0] == 100


def test_coverage_names_never_attempted_and_starved_sources() -> None:
    now = 2_000_000.0
    srcs = [_src("a"), _src("b"), _src("c", "monthly"), {**_src("t"), "role": "transport"}]
    state = {"a": {"last_attempt_epoch": now - 3600, "last_status": "COLLECTED"},
             "c": {"last_attempt_epoch": now - 40 * 24 * 3600, "deferred_streak": 2}}
    cov = AC.coverage(srcs, state, now)
    assert cov["registered"] == 3 and cov["never_attempted"] == ["b"]
    assert [r["id"] for r in cov["starved"]] == ["c"]


def test_robots_is_read_once_per_host_per_pass(monkeypatch) -> None:
    calls: list[str] = []

    class _R:
        def __init__(self, body: bytes) -> None:
            self.body = body

        def read(self, n: int = -1) -> bytes:
            return self.body

        def __enter__(self) -> _R:
            return self

        def __exit__(self, *a: Any) -> None:
            return None

    def fake(req: Any, timeout: float = 0, context: Any = None) -> _R:
        calls.append(req.full_url)
        return _R(b"User-agent: *\nDisallow: /private\n")
    monkeypatch.setattr(AC.urllib.request, "urlopen", fake)
    AC._ROBOTS.clear()
    assert AC._robots_allows("https://h.example/a")[0] is True
    assert AC._robots_allows("https://h.example/private/b")[0] is False
    assert AC._robots_allows("https://h.example/c")[0] is True
    assert calls == ["https://h.example/robots.txt"]
    AC._ROBOTS.clear()


# ------------------------------------------------------------------ parser: a dated series
def _vault(vault: Path, sid: str, body: bytes, fetched: str, ctype: str = "text/html") -> None:
    d = vault / sid
    d.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256(body).hexdigest()
    (d / f"{h[:16]}.gz").write_bytes(gzip.compress(body))
    (d / f"{h[:16]}.meta.json").write_text(json.dumps(
        {"source_id": sid, "url": f"https://{sid}.example/", "content_type": ctype,
         "sha256": h, "bytes": len(body), "fetched_utc": fetched}))


@pytest.fixture()
def lake(tmp_path, monkeypatch) -> tuple[Path, Path]:
    vault, series = tmp_path / "vault", tmp_path / "series"
    series.mkdir()
    monkeypatch.setattr(AP, "VAULT", vault)
    monkeypatch.setattr(AP, "SERIES", series)
    monkeypatch.setattr(AP, "FOUND", tmp_path / "endpoints")
    return vault, series


def test_a_snapshot_page_accumulates_one_reading_per_vintage(lake) -> None:
    """The rates payload carries no date: each fetch is one reading at its fetch time, and the
    canonical frame is every vintage, not only the newest."""
    vault, series = lake
    tmpl = (FIX / "rates_snapshot.json").read_text("utf-8")
    t0 = datetime(2026, 9, 1, 8, tzinfo=UTC)
    for k in range(35):
        body = tmpl.replace("{POLICY}", f"{2.0 + 0.01 * k:.2f}").replace(
            "{DEPOSIT}", f"{1.5 + 0.02 * (k % 5):.2f}").encode()
        _vault(vault, "cb_rates", body, (t0 + timedelta(days=k)).isoformat(),
               "application/json")
    reg = {"cb_rates": {"id": "cb_rates", "cadence": "daily", "pit": {"publication_lag_days": 0}}}
    doc = AP.parse_all()
    row = next(r for r in doc["rows"] if r["id"] == "cb_rates")
    assert row["status"] == "PARSED" and row["history"]["status"] == "FOLDED"
    assert row["history"]["readings"] == 35
    df = pd.read_parquet(series / "cb_rates.parquet")
    assert pd.to_datetime(df["available_time"], utc=True).nunique() == 35
    # nothing is visible before the desk fetched it
    first = pd.to_datetime(df["available_time"], utc=True).min()
    assert first == pd.Timestamp(t0)
    # a second pass folds nothing new and changes nothing
    again = AP.fold_vintages("cb_rates", reg)
    assert again["vintages_new"] == 0 and again["readings"] == 35
    # the census reads it as a series with numeric fields
    packs = {d["id"]: d for d in DC.lake_datasets(series)}
    d = packs["lake:cb_rates"]
    assert d["fields"] and d["pit"]["points"] == 35 and d["pit"]["usable"] is True


def test_a_dated_table_republished_whole_keeps_each_row_at_its_first_sighting(lake) -> None:
    vault, series = lake
    csv1 = (FIX / "monthly_dated.csv").read_bytes()
    csv2 = csv1 + b"2026-08,104.1\n"
    _vault(vault, "stat_m", csv1, "2026-09-02T00:00:00+00:00", "text/csv")
    _vault(vault, "stat_m", csv2, "2026-09-20T00:00:00+00:00", "text/csv")
    AP.parse_all()
    df = pd.read_parquet(series / "stat_m.parquet")
    assert len(df) == len(csv2.decode().strip().splitlines()) - 1        # no duplicate periods
    per = df.set_index(pd.to_datetime(df["event_time"], utc=True))
    assert str(per.loc["2026-07-01", "ingested_time"]).startswith("2026-09-02")
    assert str(per.loc["2026-08-01", "ingested_time"]).startswith("2026-09-20")


def test_an_index_page_takes_its_linked_data_file_as_its_series(lake) -> None:
    vault, series = lake
    _vault(vault, "portal__epdeadbeef", (FIX / "monthly_dated.csv").read_bytes(),
           "2026-09-10T00:00:00+00:00", "text/csv")
    AP.parse_all()
    got = AP.alias_parents({"portal": {"id": "portal"}})
    assert got and got[0]["parent"] == "portal"
    assert (series / "portal.parquet").exists()
    ids = {d["id"] for d in DC.lake_datasets(series)}
    assert "lake:portal" in ids and not any("__" in i for i in ids)


def test_fragments_fold_into_their_pack_in_the_census(tmp_path, monkeypatch) -> None:
    s = tmp_path / "series"
    s.mkdir()
    frame = pd.DataFrame({"v": [1.0, 2.0, 3.0]})
    for name in ("p1__t0", "p1__t1", "p1__hist", "p1", "loose__t0"):
        frame.to_parquet(s / f"{name}.parquet")
    reg = tmp_path / "asia_sources.json"
    reg.write_text(json.dumps({"sources": [{"id": "p1"}, {"id": "p2"}]}))
    monkeypatch.setattr(DC, "ASIA_SOURCES", reg)
    ids = sorted(d["id"] for d in DC.lake_datasets(s))
    # p1's fragments fold; p2 is registered with no file; an unregistered fragment with no
    # pack of its own stays visible (never silently dropped)
    assert ids == ["lake:loose__t0", "lake:p1", "lake:p2"]


def test_numeric_text_columns_become_fields() -> None:
    df = pd.DataFrame({"a": ["1,234.5", "2,000", "3.5%"], "b": ["x", "y", "z"]})
    out = AP._numeric_text(df.copy())
    assert out["a"].tolist() == [1234.5, 2000.0, 3.5]
    assert out["b"].tolist() == ["x", "y", "z"]


# ------------------------------------------------------------------ macro, grounds, seats
def test_axis_records_are_series_on_their_own_knowability_stamp(tmp_path) -> None:
    axes = tmp_path / "axes"
    axes.mkdir()
    rows = [{"symbol": "EURUSD", "knowable_at": f"2026-0{m}", "carry_differential": float(m),
             "inverted": False} for m in range(1, 8)]
    (axes / "bis.json").write_text(json.dumps({"shape": "(symbol, knowable_at, "
                                                        "carry_differential)", "rows": rows}))
    (axes / "ecb.json").write_text(json.dumps({"series": {"eur_usd_ref": {"points": [
        {"d": "2026-09-01", "v": 1.1}, {"d": "2026-09-02", "v": 1.2}]}}}))
    (axes / "fred.json").write_text(json.dumps({"n_series": 0, "series": {},
                                                "failed": {"DGS10": "TimeoutError"}}))
    f = DS.macro_fields("bis", root=axes)
    assert f[0] == {"field": "carry_differential", "match": "symbol=EURUSD"}
    assert all(x["field"] != "inverted" for x in f)
    s = DS.macro_raw("bis", "carry_differential", match="symbol=EURUSD", root=axes)
    # a month is knowable at its END, never its first day
    assert s.index[0] == pd.Timestamp("2026-02-01", tz=UTC)
    e = DS.macro_raw("ecb", "eur_usd_ref", root=axes)
    # a daily print is read at the END of its next business day (Tue 09-01 -> end of Wed)
    assert e.index[0] == pd.Timestamp("2026-09-03", tz=UTC)
    assert DS.macro_fields("fred", root=axes) == []
    got = {d["id"]: d for d in DC.file_datasets(tmp_path)}
    assert got["macro:bis"]["fields"] and not got["macro:fred"]["fields"]
    assert "fetch failed" in got["macro:fred"]["pit"]["why"]


def test_a_grounds_journal_is_a_daily_activity_series(tmp_path) -> None:
    rows = [{"at": "2026-09-05T10:00:00+00:00"}, {"at": "2026-09-05T11:00:00+00:00"},
            {"at": "2026-09-07T01:00:00+00:00"}]
    (tmp_path / "mined_sources.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
    s = DS.grounds_raw("mined_sources", root=tmp_path)
    assert s.tolist() == [2.0, 0.0, 1.0]
    assert s.index[0] == pd.Timestamp("2026-09-06", tz=UTC)           # known at day's end


def test_per_record_files_count_records_per_stamp(tmp_path) -> None:
    seat = tmp_path / "hypotheses"
    seat.mkdir()
    for n in range(3):
        (seat / f"H-20260824-00{n}.yaml").write_text(f"id: H-{n}\nmechanism: m\n")
    (seat / "H-20260825-000.yaml").write_text("id: H-9\n")
    s = DS.intel_raw("hypotheses", DS.ROW_COUNT_FIELD, roots=(tmp_path,))
    assert s.tolist() == [3.0, 1.0]


def test_seat_stamper_writes_readings_for_a_state_file_seat(tmp_path) -> None:
    root = tmp_path / "intel"
    (root / "cohorts").mkdir(parents=True)
    (root / "cohorts" / "cohort_registry.json").write_text(json.dumps({"a": 1, "b": 2, "c": 3}))
    (root / "fine").mkdir()
    (root / "fine" / "discoveries_20260901_0100.json").write_text("[]")
    stamps = tmp_path / "stamps"
    r = SS.run(NOW, stamps=stamps, roots=(root,), git=False)
    assert list(r["seats"]) == ["cohorts"] and r["seats"]["cohorts"]["stamped_now"] == 1
    again = SS.run(NOW + timedelta(hours=1), stamps=stamps, roots=(root,), git=False)
    assert again["seats"]["cohorts"]["stamped_now"] == 0          # unchanged content: no reading
    (root / "cohorts" / "cohort_registry.json").write_text(json.dumps({"a": 1}))
    SS.run(NOW + timedelta(hours=2), stamps=stamps, roots=(root,), git=False)
    s = DS.intel_raw("cohorts", "records", roots=(stamps,))
    assert s.tolist() == [3.0, 1.0]
    assert s.index[0] == pd.Timestamp(NOW)


# ------------------------------------------------------------------ swarm: short history
def test_a_short_history_dataset_gets_conditioner_and_event_cells_not_the_full_trial() -> None:
    reg = ps.load_registry()
    fams, _ = ps.swarm_families(reg)
    d = {"id": "intel:acc", "kind": "intel", "fields": [{"field": "_rows", "match": ""}],
         "source_names": ["acc"], "source_culture": "GLOBAL",
         "pit": {"usable": False, "points": 400, "span_days": 17.0,
                 "why": "ACCUMULATING: 17.0 day(s) of stamped history, under 28"}}
    tiny = {**d, "id": "intel:tiny", "pit": {**d["pit"], "points": 5}}
    bars = {"H1": {"EURUSD", "USDJPY", "XAUUSD"}}
    census: dict[str, Any] = {}
    out = ps._dataset_producers(reg, fams, bars, 1, Counter(), [d, tiny], census)
    assert out and {p.dataset for p in out} == {"intel:acc"}          # 5 readings: nothing
    assert all(p.pid.endswith(".short") for p in out)
    uses = Counter(p.use for p in out)
    assert uses["direct"] >= 1 and uses["conditioner"] >= 1
    direct = next(p for p in out if p.use == "direct")
    assert direct.base["transform"] == "delta_z" and direct.base["z_window"] == 48
    cond = next(p for p in out if p.use == "conditioner")
    assert cond.base["z_window"] == 48 and cond.base["dataset"] == "intel:acc"
    assert census["short_history"] == 1 and census["short_history_producers"] == len(out)


# ------------------------------------------------------------------ fence: members and routes
def _row(status: str, uses: dict[str, bool], judged: int = 0, kind: str = "lake"
         ) -> dict[str, Any]:
    return {"status": status, "uses": uses, "judged_24h": judged, "age_h": 100.0,
            "missing": [u for u in X.USES if not uses[u]], "kind": kind, "breach": True}


def test_a_grounds_list_and_a_registry_alias_inherit_their_members_uses() -> None:
    fed = {"direct": True, "conditioner": True, "allocation": True}
    none = {"direct": False, "conditioner": False, "allocation": False}
    rows = {"lake:a": _row("FULL", fed, 2), "lake:b": _row("UNFED", none),
            "grounds:asia_sources": _row("UNFED", none, kind="grounds"),
            "macro:cot": _row("STALE_NO_JUDGED_24H", fed, kind="macro"),
            "registry:cot": _row("UNFED", none, kind="registry")}
    X.inherit(rows)
    g = rows["grounds:asia_sources"]
    assert g["status"] == "FULL" and g["uses_via"]["members"] == ["lake:a", "lake:b"]
    assert rows["registry:cot"]["status"] == "STALE_NO_JUDGED_24H"
    assert rows["lake:b"]["status"] == "UNFED"                # a member is never lifted by it


def test_walled_sources_are_routed_to_the_forest_with_their_evidence(tmp_path, monkeypatch) -> None:
    state = tmp_path / "collector_state.json"
    state.write_text(json.dumps({"keyed": {"last_status": "UNCONFIGURED"},
                                 "starved": {}, "ok": {"last_status": "COLLECTED"}}))
    reg = tmp_path / "asia_sources.json"
    reg.write_text(json.dumps({"sources": [{"id": "keyed", "name": "Keyed Feed",
                                            "access": "key", "country": "jp"},
                                           {"id": "starved", "access": "public"}]}))
    monkeypatch.setattr(X, "COLLECTOR_STATE", state)
    monkeypatch.setattr(X, "ASIA_SOURCES", reg)
    none = {"direct": False, "conditioner": False, "allocation": False}
    ev = {"rows": {"lake:keyed": _row("UNFED", none), "lake:starved": _row("UNFED", none),
                   "intel:google_trends": _row("UNFED", none, kind="intel")},
          "datasets": [{"id": "lake:keyed", "fields": []}, {"id": "lake:starved", "fields": []},
                       {"id": "intel:google_trends", "fields": []}]}
    got = {r["dataset"]: r for r in X.substitute_routes(ev)}
    assert set(got) == {"lake:keyed", "intel:google_trends"}      # starvation is not a wall
    assert got["lake:keyed"]["region"] == "jp" and "UNCONFIGURED" in got["lake:keyed"]["why"]
    assert "429" in got["intel:google_trends"]["why"]
    assert all(r["cluster"] == "dataset_substitutes" for r in got.values())


def test_history_folding_stops_inside_the_cycle_cap() -> None:
    assert AP.fold_deadline({"QUANT_LEG_BUDGET_S": "600"}, now=0.0) == 0.6 * 600 - 60
    assert AP.fold_deadline({}, now=10.0) == 10.0 + AP.FOLD_BUDGET_S
