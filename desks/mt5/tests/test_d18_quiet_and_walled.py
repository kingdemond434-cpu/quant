"""D18 after #168: the 19 non-lake UNFED datasets -- quiet seat writers, walled sources, FRED --
plus the #168 audit's point-in-time and trial-charge fixes.

tmp_path and injected fetchers only: nothing fetches, nothing writes box state.
"""
from __future__ import annotations

import json
import subprocess
import sys
import urllib.error
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT), str(ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import dataset_series as DS  # noqa: E402

from libs.research import dataset_exploitation as X  # noqa: E402
from libs.research import dataset_substitutes as SUB  # noqa: E402
from libs.research import experiment_ledger as EL  # noqa: E402
from libs.research import seat_stamper as SS  # noqa: E402
from research import asia_parser as AP  # noqa: E402
from research import dataset_census as DC  # noqa: E402
from research import deep_forest_miner as DF  # noqa: E402
from research import fred_fetch as FF  # noqa: E402

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
NONE = {"direct": False, "conditioner": False, "allocation": False}


def _row(status: str, uses: dict[str, Any], kind: str = "intel") -> dict[str, Any]:
    return {"status": status, "uses": dict(uses), "judged_24h": 0, "age_h": 100.0,
            "missing": [u for u in X.USES if uses[u] is False], "kind": kind, "breach": True}


# ------------------------------------------------------------------ quiet writers
def test_a_run_that_donated_nothing_is_a_zero_reading(tmp_path) -> None:
    stamps = tmp_path / "stamps"
    assert SS.record_run("plumbing", 3, organ="x", now=NOW, stamps=stamps) is None
    p = SS.record_run("plumbing", 0, organ="plumbing_miner", tests_run=1198, now=NOW,
                      stamps=stamps)
    assert p is not None and p.parent == stamps / "plumbing"
    SS.record_run("plumbing", 0, organ="plumbing_miner", now=NOW + timedelta(hours=1),
                  stamps=stamps)
    s = DS.intel_raw("plumbing", DS.ROW_COUNT_FIELD, roots=(stamps,))
    assert s.tolist() == [0.0, 0.0] and s.index[0] == pd.Timestamp(NOW)


def test_proposer_door_records_a_quiet_run(tmp_path, monkeypatch) -> None:
    from research import proposer_common as pc
    stamps = tmp_path / "stamps"
    monkeypatch.setattr(SS, "STAMPS", stamps)
    assert pc.donate("plumbing", [], tests_run=12) is None
    got = list((stamps / "plumbing").glob("run_*.json"))
    assert len(got) == 1 and json.loads(got[0].read_text())["tests_run"] == 12


def _git(repo: Path, *args: str, when: str) -> None:
    env = {"GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when, "GIT_AUTHOR_NAME": "t",
           "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
           "PATH": "/usr/bin:/bin"}
    subprocess.run(["git", "-C", str(repo), *args], check=True, env=env, capture_output=True)


def test_git_activity_reads_each_rewrite_in_place_once(tmp_path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    seat = repo / "intel" / "recombinants"
    seat.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    f = seat / "REC-20260901-aa.json"
    f.write_text(json.dumps({"discoveries": [{"id": 0}]}))
    _git(repo, "add", "-A", when="2026-09-01T10:00:00+00:00")
    _git(repo, "commit", "-qm", "add", when="2026-09-01T10:00:00+00:00")
    for k in range(1, 4):
        f.write_text(json.dumps({"discoveries": [{"id": k}]}))
        _git(repo, "commit", "-qam", f"rewrite {k}", when=f"2026-09-01T1{k}:00:00+00:00")
    monkeypatch.setattr(SS, "ROOT", repo)
    stamps = tmp_path / "stamps"
    r = SS.stamp_git_activity(NOW, stamps=stamps, roots=(repo / "intel",))
    assert r["recombinants"]["modifying_commits"] == 3 and r["recombinants"]["stamped_now"] == 3
    again = SS.stamp_git_activity(NOW, stamps=stamps, roots=(repo / "intel",))
    assert again["recombinants"]["stamped_now"] == 0              # idempotent
    s = DS.intel_raw("recombinants", DS.ROW_COUNT_FIELD, roots=(repo / "intel", stamps))
    # the added file's own name stamp (the day, known at its end) plus three rewrite readings
    assert len(s) == 4 and s.iloc[0] == 1.0


def test_every_quiet_seat_names_its_writer_and_closure(tmp_path) -> None:
    root = tmp_path / "intel"
    for seat in SS.SEAT_WRITERS:
        (root / seat).mkdir(parents=True)
        (root / seat / "discoveries_20260901_0100.json").write_text("[]")
    (root / "mystery").mkdir()
    (root / "mystery" / "discoveries_20260901_0100.json").write_text("[]")
    c = SS.writer_census((root,))
    assert set(c["seats"]) == {*SS.SEAT_WRITERS, "mystery"}
    assert c["seats"]["mystery"]["writer"] == "UNMAPPED"
    assert "box_step" in c["seats"]["brain"] and "box_step" not in c["seats"]["plumbing"]
    assert len(SS.SEAT_WRITERS) == 13


def test_seed_miners_record_mql5_output_through_the_reputation_tracker(tmp_path) -> None:
    sys.path.insert(0, str(DESK / "side_channels"))
    import seed_miners
    n = seed_miners.record_mql5_reputation(
        {"mql5_signals": {"discoveries": [{"url": "a"}, {"url": "b"},
                                          {"needs_selector_work": True}]},
         "darwinex": {"discoveries": [{"url": "c"}]}}, base_path=tmp_path)
    assert n == 1
    hist = (tmp_path / "data" / "intelligence" / "mql5_reputation" / "reputation_history.jsonl")
    rows = [json.loads(x) for x in hist.read_text().splitlines()]
    assert [r["source_id"] for r in rows] == ["mql5_signals"]
    assert rows[0]["details"]["hypotheses"] == 2


# ------------------------------------------------------------------ FRED
def test_fetch_failures_are_classified_env_or_http() -> None:
    assert FF.classify(urllib.error.URLError(OSError("Tunnel connection failed: 403"))) == FF.ENV
    assert FF.classify(TimeoutError("read timed out")) == FF.ENV
    assert FF.classify(ConnectionResetError("[WinError 10054]")) == FF.ENV
    assert FF.classify(urllib.error.HTTPError("u", 404, "nf", {}, None)) == FF.HTTP  # type: ignore[arg-type]


def test_fetch_retries_with_backoff_then_succeeds() -> None:
    calls: list[str] = []
    sleeps: list[float] = []

    def get(url: str) -> bytes:
        calls.append(url)
        if len(calls) < 3:
            raise urllib.error.URLError("reset")
        return b"observation_date,DGS10\n2026-09-24,4.1\n2026-09-25,4.2\n"
    body, log = FF.fetch_with_retry("https://x", get=get, sleep=sleeps.append)
    assert body and log["attempts"] == 3 and sleeps == [2.0, 4.0]
    # a publisher's 404 is its answer: never retried
    calls.clear()

    def nf(url: str) -> bytes:
        calls.append(url)
        raise urllib.error.HTTPError(url, 404, "nf", {}, None)  # type: ignore[arg-type]
    body, log = FF.fetch_with_retry("https://x", get=nf, sleep=sleeps.append)
    assert body is None and len(calls) == 1 and log["status"] == FF.HTTP


def test_monthly_points_are_knowable_after_their_period_ends_not_a_day_after_their_date() -> None:
    # FRED dates a monthly print at its FIRST day; +1 day was weeks of lookahead
    assert FF.knowable_at("CPIAUCSL", "2026-07-01", "M").startswith("2026-08-18")
    assert FF.knowable_at("ZZZ", "2026-07-01", "M").startswith("2026-09-15")
    # ALFRED's first-release date wins
    assert FF.knowable_at("CPIAUCSL", "2026-07-01", "M", "2026-08-12").startswith("2026-08-13")
    # a Friday's daily print is read at the end of Monday, its publication day
    assert FF.knowable_at("DGS10", "2026-09-25", "D").startswith("2026-09-29")
    assert FF.frequency_of("X", ["2026-01-01", "2026-02-01", "2026-03-01"]) == "M"


def test_macro_raw_never_reads_a_monthly_series_before_its_release(tmp_path) -> None:
    axes = tmp_path / "axes"
    axes.mkdir()
    pts = [{"d": f"2026-0{m}-01", "v": float(m)} for m in range(1, 8)]
    (axes / "fredm.json").write_text(json.dumps({"series": {"CPI": {"points": pts}}}))
    s = DS.macro_raw("fredm", "CPI", root=axes)
    # January (dated 2026-01-01) is read 45 days after its period END, never 2026-01-02
    assert s.index[0] == pd.Timestamp("2026-03-18", tz=UTC)
    stamped = [{**p, "k": "2026-02-13T00:00:00+00:00"} if p["d"] == "2026-01-01" else p
               for p in pts]
    (axes / "fredk.json").write_text(json.dumps({"series": {"CPI": {"points": stamped}}}))
    assert DS.macro_raw("fredk", "CPI", root=axes).index[0] == pd.Timestamp("2026-02-13",
                                                                              tz=UTC)


def test_a_failed_pass_keeps_the_previous_points_and_says_why() -> None:
    def down(url: str) -> bytes:
        raise urllib.error.URLError(OSError("Tunnel connection failed: 403"))
    prev = {"at": "2026-09-01T00:00:00+00:00", "series": {"DGS10": {
        "points": [{"d": "2026-08-31", "v": 4.0, "k": "2026-09-02T00:00:00+00:00"}]}}}
    doc = FF.ingest_fred(get=down, previous=prev, series={"DGS10": "10y", "DGS2": "2y"},
                         sleep=lambda s: None)
    assert doc["fetch_status"] == FF.ENV and doc["n_fetched"] == 0
    assert doc["series"]["DGS10"]["carried_from"] == prev["at"]
    assert "DGS2" not in doc["series"] and doc["failed"]["DGS2"].startswith(FF.ENV)


def test_an_environment_failure_reads_unmeasured_never_unfed(tmp_path) -> None:
    (tmp_path / "axes").mkdir()
    (tmp_path / "axes" / "fred.json").write_text(json.dumps({
        "n_series": 0, "series": {}, "failed": {
            "DGS10": "TimeoutError: The read operation timed out",
            "DGS2": "ConnectionResetError: [WinError 10054]"}}))
    got = {d["id"]: d for d in DC.file_datasets(tmp_path)}
    assert got["macro:fred"]["pit"]["fetch_status"] == "FETCH_FAILED_ENV"
    ds = [got["macro:fred"], {"id": "registry:fred_macro", "pit": {}},
          {"id": "lake:x", "pit": {}}]
    rows = {"macro:fred": _row("UNFED", NONE, "macro"),
            "registry:fred_macro": _row("UNFED", NONE, "registry"),
            "lake:x": _row("UNFED", NONE, "lake")}
    changed = SUB.unmeasured_by_environment(
        rows, ds, {"registry:fred_macro": (("macro:fred",), "alias")})
    assert changed == ["macro:fred", "registry:fred_macro"]
    assert rows["macro:fred"]["status"] == "UNMEASURED"
    assert "FETCH_FAILED_ENV" in rows["registry:fred_macro"]["unmeasured_why"]
    assert rows["lake:x"]["status"] == "UNFED"                   # a real UNFED stays UNFED
    # an HTTP answer from the publisher is not the environment
    assert DC.fetch_failure({"n_series": 0, "failed": {"X": "HTTPError: HTTP Error 404"}}) \
        == "FETCH_FAILED_HTTP"


# ------------------------------------------------------------------ walled datasets
def test_every_walled_dataset_has_a_clean_registered_substitute() -> None:
    m = SUB.members()
    assert set(m) == {"intel:google_trends", "intel:investing", "intel:china"}
    assert "intel:attention_substitutes" in m["intel:google_trends"][0]      # #162, not a copy
    assert "lake:cfets_fixing" in m["intel:china"][0] and "lake:safe_reserves" in m["intel:china"][0]
    assert "macro:fred" in m["intel:investing"][0]
    for wid in m:                                   # the fence inherits through them
        assert X.MEMBERS[wid] == m[wid]


def test_a_blocked_terms_source_is_never_requested(tmp_path) -> None:
    reg = tmp_path / "subs.json"
    reg.write_text(json.dumps({"walled": {"intel:w": {"wall": "403", "substitutes": [
        {"id": "nasdaq", "kind": "fetch", "provider": "N", "url": "https://api.nasdaq.com/x",
         "terms": "BLOCKED_TERMS", "series": [{"key": "k", "search": "s", "must": ["a"],
                                               "revises": False}]}]}}}))

    def boom(url: str) -> bytes:
        raise AssertionError(f"requested {url}")
    doc = SUB.run(NOW, get=boom, path=reg, lake=tmp_path / "lake", write=False)
    assert doc["walled"]["intel:w"]["substitutes"]["nasdaq"]["status"] == SUB.BLOCKED_TERMS
    assert SUB.members(reg) == {}


def _dbn(url: str) -> bytes:
    if "/search?" in url:
        return json.dumps({"results": {"docs": [
            {"provider_code": "NBS", "code": "M_PMI"}, {"provider_code": "IMF", "code": "Z"}]}}
            ).encode()
    return json.dumps({"series": {"docs": [
        {"dataset_code": "M_PMI", "series_code": "A0B0101", "series_name":
         "Manufacturing PMI (%)", "period": ["2026-06", "2026-07"], "value": [49.7, 49.3]},
        {"dataset_code": "M_PMI", "series_code": "A0B0201", "series_name": "Non-manufacturing "
         "business activity index", "period": ["2026-07"], "value": [50.2]}]}}).encode()


def test_a_dbnomics_series_is_resolved_by_name_and_stamped_point_in_time(tmp_path) -> None:
    lake = tmp_path / "lake"
    sub = {"id": "dbnomics_nbs", "kind": "fetch", "provider": "NBS", "series": [
        {"key": "cn_pmi", "search": "pmi", "must": ["manufacturing", "pmi"], "lag_days": 7,
         "revises": False}]}
    res = SUB.fetch_source(sub, NOW, _dbn, lake)
    assert res["cn_pmi"]["status"] == "OK" and res["cn_pmi"]["rows"] == 2
    df = pd.read_csv(lake / "sub_dbnomics_nbs_cn_pmi.csv")
    # July's PMI: its period ends 2026-08-01 and is read 7 days later, never on 2026-07-01
    assert df.iloc[-1]["available_time"].startswith("2026-08-08")
    # a later DIFFERENT value for a held period is ignored: the first sighting stands

    def revised(url: str) -> bytes:
        return _dbn(url).replace(b"49.3", b"55.5")
    SUB.fetch_source(sub, NOW + timedelta(days=3), revised, lake)
    assert pd.read_csv(lake / "sub_dbnomics_nbs_cn_pmi.csv").iloc[-1]["value"] == 49.3


def test_an_ambiguous_name_is_unresolved_never_guessed(tmp_path) -> None:
    sub = {"id": "d", "provider": "NBS", "series": [
        {"key": "k", "search": "pmi", "must": ["manufacturing"], "revises": False},
        {"key": "rev", "search": "cpi", "must": ["cpi"], "revises": True}]}
    res = SUB.fetch_source(sub, NOW, _dbn, tmp_path)
    assert res["k"]["status"] == "UNRESOLVED" and res["rev"]["status"] == "SKIPPED"


def test_a_wall_stops_the_source_and_is_never_retried(tmp_path) -> None:
    calls: list[str] = []

    def walled(url: str) -> bytes:
        calls.append(url)
        raise urllib.error.HTTPError(url, 429, "slow down", {}, None)  # type: ignore[arg-type]
    sub = {"id": "d", "provider": "NBS", "series": [
        {"key": "a", "search": "x", "must": ["x"], "revises": False},
        {"key": "b", "search": "y", "must": ["y"], "revises": False}]}
    res = SUB.fetch_source(sub, NOW, walled, tmp_path)
    assert res["a"]["status"] == "WALLED" and "b" not in res and len(calls) == 1


# ------------------------------------------------------------------ grounds:asia_sources
def test_asia_sources_is_credited_once_any_pack_is_fed() -> None:
    rows = {"lake:a": _row("PARTIAL:conditioner,allocation",
                           {"direct": True, "conditioner": False, "allocation": False}, "lake"),
            "lake:b": _row("UNFED", NONE, "lake"),
            "grounds:asia_sources": _row("UNFED", NONE, "grounds")}
    X.inherit(rows)
    g = rows["grounds:asia_sources"]
    assert g["status"] != "UNFED" and g["uses"]["direct"] is True
    assert g["uses_via"]["uses"] == ["direct"]
    rows2 = {"lake:b": _row("UNFED", NONE, "lake"),
             "grounds:asia_sources": _row("UNFED", NONE, "grounds")}
    X.inherit(rows2)
    assert rows2["grounds:asia_sources"]["status"] == "UNFED"      # no pack fed, no credit


# ------------------------------------------------------------------ deep-forest reader
def test_the_substitute_queue_has_a_reader_that_never_double_reads(tmp_path, monkeypatch) -> None:
    q = tmp_path / "dataset_substitutes.json"
    q.write_text(json.dumps({"grounds": [
        {"name": "dataset_substitute|intel:china", "route": "search", "queries": ["x"]},
        {"name": "registered", "route": "search"}, {"name": "no_route"}]}))
    got = DF.substitute_grounds({"registered"}, path=q)
    assert [g["name"] for g in got] == ["dataset_substitute|intel:china"]
    # once #152's queued_grounds is in the module it reads the whole queue: this one no-ops
    monkeypatch.setattr(DF, "queued_grounds", lambda *a, **k: [], raising=False)
    assert DF.substitute_grounds(set(), path=q) == []


# ------------------------------------------------------------------ audit: revisions
def test_a_revised_value_is_knowable_at_its_fetch_never_at_the_original_release() -> None:
    t_rel = pd.Timestamp("2026-08-15", tz=UTC)
    base = {"event_time": pd.Timestamp("2026-07-01", tz=UTC), "available_time": t_rel,
            "published_time": t_rel, "source_id": "s"}
    h = pd.DataFrame([
        {**base, "index_level": 103.6, "ingested_time": "2026-09-02T00:00:00+00:00",
         "vintage_id": "v1"},
        {**base, "index_level": 103.9, "ingested_time": "2026-09-20T00:00:00+00:00",
         "vintage_id": "v2"},
        {**base, "index_level": 103.9, "ingested_time": "2026-09-25T00:00:00+00:00",
         "vintage_id": "v3"}])
    h["_first_seen"] = pd.to_datetime(h["ingested_time"], utc=True)
    key = [c for c in h.columns if c not in AP._VINTAGE_ONLY and c != "_first_seen"]
    out = AP.restamp_revisions(h, key).sort_values("available_time")
    assert out["index_level"].tolist() == [103.6, 103.9]           # v3 repeats: no news
    first, rev = out.iloc[0], out.iloc[1]
    assert pd.Timestamp(first["available_time"]) == t_rel           # first print keeps its release
    assert pd.Timestamp(rev["available_time"]) == pd.Timestamp("2026-09-20", tz=UTC)
    # the series a reader builds never shows the revision at the original instant
    s = pd.Series(out["index_level"].to_numpy(),
                  index=pd.to_datetime(out["available_time"], utc=True))
    assert s[s.index <= t_rel].iloc[-1] == 103.6


def test_a_revised_vintage_folds_without_lookahead(tmp_path, monkeypatch) -> None:
    import gzip
    import hashlib
    vault, series = tmp_path / "vault", tmp_path / "series"
    series.mkdir()
    monkeypatch.setattr(AP, "VAULT", vault)
    monkeypatch.setattr(AP, "SERIES", series)
    monkeypatch.setattr(AP, "FOUND", tmp_path / "endpoints")
    fix = (ROOT / "tests" / "fixtures" / "dataset_full_feed" / "monthly_dated.csv").read_bytes()
    for body, fetched in ((fix, "2026-09-02T00:00:00+00:00"),
                          (fix.replace(b"103.6", b"103.9"), "2026-09-20T00:00:00+00:00")):
        d = vault / "stat_r"
        d.mkdir(parents=True, exist_ok=True)
        h = hashlib.sha256(body).hexdigest()
        (d / f"{h[:16]}.gz").write_bytes(gzip.compress(body))
        (d / f"{h[:16]}.meta.json").write_text(json.dumps(
            {"source_id": "stat_r", "url": "https://stat_r.example/", "content_type": "text/csv",
             "sha256": h, "bytes": len(body), "fetched_utc": fetched}))
    AP.parse_all()
    df = pd.read_parquet(series / "stat_r.parquet")
    jul = df[pd.to_datetime(df["event_time"], utc=True) == pd.Timestamp("2026-07-01", tz=UTC)]
    got = sorted(zip(pd.to_datetime(jul["available_time"], utc=True),
                     jul["index_level"].astype(float), strict=True))
    assert [v for _t, v in got] == [103.6, 103.9]
    assert got[1][0] >= pd.Timestamp("2026-09-20", tz=UTC) > got[0][0]


# ------------------------------------------------------------------ audit: trial charge
def test_producer_swarm_trials_are_charged_to_the_lifetime_union(tmp_path, monkeypatch) -> None:
    p = tmp_path / "PRODUCER_SWARM_TRIALS.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in (
        {"family": "dataset_stance", "cells_screened": 40},
        {"family": "dataset_conditioned", "cells_screened": 25},
        {"family": "dataset_stance", "cells_screened": 9, "dry_run": True})) + "\n")
    monkeypatch.setattr(EL, "PRODUCER_SWARM_TRIALS", p)
    monkeypatch.setattr(EL, "_graph_counts", lambda: (0, {}))
    monkeypatch.setattr(EL, "_proposer_counts", lambda: (0, {}))
    monkeypatch.setattr(EL, "MASS_SCREEN_TRIALS", tmp_path / "none1")
    monkeypatch.setattr(EL, "UNKNOWN_UNKNOWN_TRIALS", tmp_path / "none2")
    monkeypatch.setattr(EL, "REGIME_SPLIT_TRIALS", tmp_path / "none3")
    doc = EL.lifetime(write=False)
    assert doc["producer_swarm_cells"] == 65 and doc["lifetime_trials"] == 65
    assert doc["by_family"] == {"dataset_stance": 40, "dataset_conditioned": 25}


@pytest.mark.parametrize("seat", sorted(SS.SEAT_WRITERS))
def test_seat_writer_rows_are_complete(seat: str) -> None:
    w = SS.SEAT_WRITERS[seat]
    assert {"writer", "host", "clock", "cause", "closure"} <= set(w)


# ------------------------------------------------------------------ #166's repo-mined feeds
def test_the_repo_mined_feeds_are_enrolled_and_read_on_their_first_print_clock(tmp_path) -> None:
    acq = tmp_path / "acquired"
    acq.mkdir()
    idx = pd.date_range("2026-01-01", periods=40, freq="D", tz=UTC)
    pd.DataFrame({"value": range(40)}, index=idx).to_parquet(acq / "gpr_daily_gprd.parquet")
    got = {d["id"]: d for d in DC.acquired_datasets(acq)}
    assert {"acquired:gpr_daily", "acquired:epu_us_daily", "acquired:crypto_fear_greed"} \
        <= set(got)
    g = got["acquired:gpr_daily"]
    assert g["fields"] == [{"field": "gpr_daily_gprd", "match": ""}]
    assert g["pit"]["points"] == 40 and "ext_gpr_daily" in g["source_names"]
    assert got["acquired:epu_us_daily"]["fields"] == []             # not acquired: no series
    s = DS.raw("acquired:gpr_daily", "gpr_daily_gprd", root=acq)
    assert s is not None and s.index[0] == idx[0] and s.iloc[-1] == 39.0
    # a cell naming the feed credits it; nothing else does
    idx_names = X.name_index(list(got.values()))
    assert idx_names["ext_gpr_daily"] == {"acquired:gpr_daily"}
