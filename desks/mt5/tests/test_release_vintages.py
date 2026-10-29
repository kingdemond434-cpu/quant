"""The calendar's PIT consensus joined to ALFRED's FIRST print, revisions appended, and the whole
surprise family measured or named UNMEASURED.

EVERYTHING IS SYNTHETIC: a hand-built ALFRED vintage file for payrolls in which every release
revises the previous month by +10k, and a hand-built calendar rollup. No network, no key.
"""
from __future__ import annotations

import gzip
import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_ROOT), str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import event_surprise as es  # noqa: E402
from macro import release_vintages as rv  # noqa: E402
from macro.surprise import composite_z, surprise_family  # noqa: E402

from libs.research import sensor_contract as sc  # noqa: E402

NOW = datetime(2026, 9, 10, 12, 0, tzinfo=UTC)
TITLE = "USD Non-Farm Employment Change"


def _month(i: int) -> pd.Timestamp:
    return pd.Timestamp("2020-01-01") + pd.DateOffset(months=i)


def _vintage(i: int) -> pd.Timestamp:
    """Release date of month i: the next month's 7th."""
    return _month(i + 1) + pd.Timedelta(days=6)


N = 80          # 2020-01 .. 2026-08: the last first print is 2026-09-07


def _alfred(folder: Path) -> None:
    rows = []
    for i in range(N):
        base = 1000.0 + 150.0 * i
        rows.append({"observation_date": _month(i), "realtime_date": _vintage(i), "value": base})
        if i + 1 < N:                                   # the next release revises it by +10
            rows.append({"observation_date": _month(i), "realtime_date": _vintage(i + 1),
                         "value": base + 10.0})
    folder.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(folder / "PAYEMS.csv", index=False)


def _rollup(folder: Path, rows: list[dict[str, Any]]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    with gzip.open(folder / "rollup_20260907.jsonl.gz", "wt", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    monkeypatch.setattr(rv, "alfred_key_present", lambda: False)
    alfred, vint = tmp_path / "alfred", tmp_path / "ff"
    _alfred(alfred)
    _rollup(vint, [
        {"title": TITLE, "event_date": "2026-09-07T08:30:00-04:00", "forecast": "125K",
         "previous": "140K", "impact": "High", "captured_at": "2026-09-05T10:00:00+00:00"},
        {"title": TITLE, "event_date": "2026-09-07T08:30:00-04:00", "forecast": "130K",
         "previous": "140K", "impact": "High", "captured_at": "2026-09-06T12:00:00+00:00"},
        # captured AFTER the 12:30Z print: not an expectation, refused
        {"title": TITLE, "event_date": "2026-09-07T08:30:00-04:00", "forecast": "999K",
         "previous": "140K", "impact": "High", "captured_at": "2026-09-07T13:00:00+00:00"},
        # next month's consensus: its first print does not exist yet
        {"title": TITLE, "event_date": "2026-10-07T08:30:00-04:00", "forecast": "120K",
         "previous": "140K", "impact": "High", "captured_at": "2026-09-09T12:00:00+00:00"},
    ])
    return alfred, vint


def test_consensus_is_the_last_capture_before_the_instant(world: tuple[Path, Path]) -> None:
    _, vint = world
    cons = rv.consensus_vintages(vint)
    got = cons[(TITLE, "2026-09-07")]
    assert got["consensus"] == 130.0                   # not 999: captured after the print
    assert got["first_consensus"] == 125.0             # the drift into the release is kept
    assert got["captured_at"] == "2026-09-06T12:00:00+00:00"


def test_first_print_and_revisions_are_vintage_true(world: tuple[Path, Path]) -> None:
    alfred, _ = world
    prints = rv.release_vintage(rv.load_alfred("PAYEMS", alfred), rv.BY_TITLE[TITLE])
    by_day = {p["vintage"]: p for p in prints}
    last = by_day["2026-09-07"]
    # the first print as published: this month at base, last month already revised up 10
    assert last["actual"] == pytest.approx(140.0)
    assert last["previous_first"] == pytest.approx(140.0)
    assert last["previous_revised"] == pytest.approx(150.0)
    assert last["revisions"] == []                     # not revised yet
    earlier = by_day["2026-08-07"]
    assert earlier["revisions"] == [{"vintage": "2026-09-07", "value": pytest.approx(150.0)}]
    # the start of ALFRED's record is not a release
    assert _vintage(0).date().isoformat() not in by_day


def test_build_pairs_waits_and_never_completes(world: tuple[Path, Path]) -> None:
    alfred, vint = world
    out = rv.build(now=NOW, vintages=vint, alfred=alfred)
    rows = out["rows"]
    pair = [r for r in rows if r["release"] == TITLE and r["provides"] == "both"]
    assert len(pair) == 1
    p = pair[0]
    assert (p["actual"], p["consensus"]) == (140.0, 130.0)
    assert p["family"]["raw"] == pytest.approx(10.0)
    assert p["family"]["previous_revision"] == pytest.approx(10.0)
    assert p["family"]["revision_adjusted"] == pytest.approx(20.0)
    assert p["family"]["dispersion_adjusted"]["value"] == rv.UNMEASURED
    assert p["pit"]["knowable_at"] == "2026-09-07T12:30:00+00:00"
    assert p["survey_high"] == rv.UNMEASURED
    waiting = [r for r in rows if r["provides"] == "consensus"]
    assert [(w["period"], w["actual"]) for w in waiting] == [("2026-10-07", None)]
    nowcast = [r for r in rows if r["release"] == f"{TITLE}|nowcast_ewm12"]
    assert nowcast and all(r["expectation_kind"] == "nowcast_ewm12" for r in nowcast)
    # the nowcast never has a print from the future: every row is at or before now
    assert all(r["at"] <= NOW.isoformat() for r in rows if r["provides"] == "both")
    # and event_surprise joins exactly one consensus pair for the release (the half waits)
    joined = es.join_sides([r for r in rows if r["release"] == TITLE])
    assert [(j["period"], j["actual"]) for j in joined] == [("2026-09-07", 140.0)]
    assert out["census"]["status"] == "present"
    assert out["census"]["releases"][TITLE]["pairs"] == 1


def test_no_alfred_means_blocked_auth_and_the_consensus_waits(
        world: tuple[Path, Path], tmp_path: Path) -> None:
    _, vint = world
    out = rv.build(now=NOW, vintages=vint, alfred=tmp_path / "empty")
    assert out["census"]["status"] == "BLOCKED_AUTH"
    assert all(r["actual"] is None for r in out["rows"])
    assert {r["period"] for r in out["rows"]} == {"2026-09-07", "2026-10-07"}
    assert all("BLOCKED_AUTH" in r["waiting_for"] for r in out["rows"])
    assert rv.refresh_alfred(10.0, folder=tmp_path)["status"] == "BLOCKED_AUTH"


def test_releases_reach_the_sensor_ledger_with_revisions_appended(
        world: tuple[Path, Path], tmp_path: Path) -> None:
    alfred, vint = world
    out = rv.build(now=NOW, vintages=vint, alfred=alfred)
    recent = [s for s in out["sensor_inputs"] if s["sched"].date() >= date(2026, 7, 1)]
    obs = rv.sensor_observations(recent, NOW)
    assert all(sc.defects(o) == [] for o in obs)
    led = sc.SensorLedger(tmp_path / "sensors")
    res = led.append(obs)
    assert res["appended"] >= 3 and res["revisions"] >= 1 and res["refused"] == 0
    cons = [o for o in obs if o.metric.endswith("|consensus")]
    assert cons and cons[0].knowable_at == "2026-09-06T12:00:00+00:00"
    assert all(o.authority == "NONE" for o in obs)


def test_surprise_family_measures_or_names_every_variant() -> None:
    hist = [float(x) for x in range(-10, 11)]
    fam = surprise_family(150.0, 130.0, history=hist, high=160.0, low=100.0,
                          previous_first=140.0, previous_revised=150.0,
                          model_expectation=135.0, model_history=hist, peer_z=[0.5],
                          priced_fraction=0.25, release_id="t")
    assert fam["raw"] == 20.0
    assert fam["dispersion_adjusted"] == pytest.approx(20.0 / 15.0, rel=1e-5)
    assert fam["revision_adjusted"] == 30.0
    assert fam["percentile"] == 1.0
    assert fam["nowcast_relative"] == 15.0
    assert fam["market_implied"] == pytest.approx(15.0)
    assert isinstance(fam["z_release"], float)
    assert fam["direction_from"] == "not_used_for_direction"
    thin = surprise_family(150.0, None)
    assert all(thin[k]["value"] == "UNMEASURED"
               for k in ("raw", "z_release", "dispersion_adjusted", "percentile",
                         "market_implied", "relative_country"))
    assert composite_z({"a": 1.0})["value"] == "UNMEASURED"
    assert composite_z({"a": 1.0, "b": 3.0, "c": None})["value"] == 2.0


def test_event_surprise_takes_the_rows_without_touching_disk(
        world: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    alfred, vint = world
    real = rv.build
    monkeypatch.setattr(rv, "build", lambda **kw: real(**{**kw, "vintages": vint,
                                                          "alfred": alfred}))
    monkeypatch.setattr(es, "STORE", tmp_path / "store.jsonl")
    got = es.release_vintage_rows(now=NOW, refresh=False, budget_s=0.0)
    assert any(r["provides"] == "both" for r in got["rows"])
    assert got["census"]["status"] == "present"
    stored, added = es.merge_store(got["rows"], now=NOW)
    assert added == len(got["rows"])
    assert es.release_vintage_rows(now=NOW, refresh=False, budget_s=0.0,
                                   enabled=False)["rows"] == []


def test_ff_consensus_pairs_are_stored_but_held_from_the_gauntlet(
        world: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Audit #204 item 4: the Forex Factory survey median is stored and counted, but no pair built
    on it reaches the gauntlet until its terms are cleared; nowcast_ewm12 ships alone."""
    alfred, vint = world
    monkeypatch.setattr(rv, "CLEARANCES", tmp_path / "terms_clearances.json")
    out = rv.build(now=NOW, vintages=vint, alfred=alfred)
    rows = out["rows"]
    assert any(r["provides"] == "both" and r["expectation_kind"] == "consensus_median"
               for r in rows)                              # stored
    assert out["census"]["terms"]["gauntlet"] == "HELD"
    assert out["census"]["releases"][TITLE]["held_terms"] == 1
    kept, held = es.terms_filter(rows)
    assert kept and all(r.get("expectation_kind") == "nowcast_ewm12" for r in kept)
    assert held["n"] == len(rows) - len(kept) and held["n"] >= 2
    assert all("HELD_TERMS" in w for w in held["why"].values())
    # a recorded clearance admits them; a non-CLEARED record does not
    (tmp_path / "terms_clearances.json").write_text(
        json.dumps({"ff_calendar": {"status": "PENDING"}}), "utf-8")
    assert rv.gauntlet_terms("ff_calendar_vintage+alfred:PAYEMS")[0] is False
    (tmp_path / "terms_clearances.json").write_text(
        json.dumps({"ff_calendar": {"status": "CLEARED", "by": "terms review"}}), "utf-8")
    kept, held = es.terms_filter(rows)
    assert len(kept) == len(rows) and held["n"] == 0
    # the nowcast source was never held, and an unknown source is not whitelisted away
    assert rv.gauntlet_terms("alfred:PAYEMS") == (True, "")
