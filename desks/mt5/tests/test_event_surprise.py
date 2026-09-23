"""The event-surprise cluster: does a planted reaction come back, and can a lie get through?

EVERY INPUT IS SYNTHETIC AND NOTHING HERE TOUCHES THE NETWORK. The grounds file, the
point-in-time store, the collector state and the report are all redirected into `tmp_path`, the
chart is a seeded array, and the only "fetcher" is a function this module wrote -- so a test that
passes here proves the mechanism, not that the box happened to have data.

THE LOAD-BEARING TESTS.

`test_a_planted_reaction_is_found_and_a_placebo_release_is_not` plants a +30bp drift after every
large upside surprise of ONE release and plants nothing after an otherwise identical second
release. The planted cell must clear and the placebo must not: an organ that reports a reaction
for both is measuring the calendar, not the news.

`test_an_equity_is_measured_and_never_donated` proves the two-lane mandate at the door with the
REAL `universe_policy` deciding against a synthetic registry -- a fence that is stubbed out in
its own test proves nothing.

`test_the_collector_refuses_ground_it_is_not_allowed_to_fetch` proves the policy is executable:
a row registered `machine_use_allowed: false` and a row declaring key access are never handed to
the fetcher at all, and both refusals are recorded with a reason.

`test_a_half_row_waits_for_its_partner` proves an unpaired consensus is never completed with a
guess, a previous value or a zero -- the one failure mode that would silently manufacture
surprises out of nothing.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_ROOT), str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import event_surprise as es  # noqa: E402

from research import universe_policy as up  # noqa: E402

#: A synthetic broker registry: one FX major in the discovery lane, one share CFD in the event
#: lane, and the real policy reads THIS rather than the box's universe.json.
REGISTRY: dict[str, dict[str, Any]] = {
    "EURUSD": {"asset_class": "Forex"},
    "APPLE": {"asset_class": "Equities"},
}
START = datetime(2024, 1, 2, 0, 0, tzinfo=UTC)
#: Bar noise and the planted bump. 5bp of hourly noise against a 30bp planted drift: a signal a
#: correct organ cannot miss and an incorrect one cannot manufacture.
NOISE_SD = 0.0005
BUMP = 0.0030
N_PRINTS = 46


@pytest.fixture
def desk(tmp_path, monkeypatch):
    """Every path the organ writes, and the real universe policy over a synthetic registry."""
    registry = tmp_path / "universe.json"
    registry.write_text(json.dumps(REGISTRY), "utf-8")
    monkeypatch.setattr(up, "UNIVERSE", registry)
    up._registry.cache_clear()
    monkeypatch.setattr(es, "GROUNDS", tmp_path / "grounds.json")
    monkeypatch.setattr(es, "STORE", tmp_path / "store.jsonl")
    monkeypatch.setattr(es, "COLLECTOR_STATE", tmp_path / "collector_state.json")
    monkeypatch.setattr(es, "REPORT", tmp_path / "EVENT_SURPRISE.json")
    # The calendar is the box's and may carry anything; these tests own their inputs.
    monkeypatch.setattr(es, "calendar_pairs", lambda days, now: ([], {"status": "absent"}))
    monkeypatch.setattr(es, "_bar_time", lambda when: (when, "TEST_IDENTITY"))
    monkeypatch.setattr(es, "_regimes", lambda: ([], "TEST_NO_REGIMES"))
    monkeypatch.setattr(es, "_cost_bp", lambda symbol, close: (0.5, "test"))
    donated: list[dict[str, Any]] = []
    monkeypatch.setattr(es, "_donate",
                        lambda candidates, tests_run: (donated.extend(candidates)
                                                       or tmp_path / "donation.json"))
    yield {"tmp": tmp_path, "donated": donated}
    up._registry.cache_clear()


# ------------------------------------------------------------------ synthetic pairs and bars
def _pairs(release: str, kind: str, symbol: str, *, n: int = N_PRINTS,
           start: datetime = START) -> list[dict[str, Any]]:
    """`n` monthly-ish prints whose surprises span several sigma, so z is measurable after ten.

    The surprise pattern repeats over a short cycle, which gives the release's own sigma a stable
    value and puts a dozen prints in each of the four buckets -- exactly the shape a real release
    has after a couple of years, compressed so a test can run in a second.
    """
    cycle = (2.4, -0.3, 1.9, 0.2, -2.1, 0.4, -1.8, 0.1, 2.2, -0.2, -2.4, 0.3)
    out = []
    for i in range(n):
        when = start + timedelta(days=3 * (i + 1), hours=13)
        out.append({"release": release, "kind": kind, "symbol": symbol,
                    "at": when.isoformat(timespec="seconds"),
                    "period": f"{when:%Y-%m}-{i}", "consensus": 100.0,
                    "actual": 100.0 + cycle[i % len(cycle)], "instruments": [symbol],
                    "source_id": "test"})
    return out


def _frame(pairs: list[dict[str, Any]], planted: set[str], *, seed: int = 11) -> pd.DataFrame:
    """Hourly bars over the whole window, with a +BUMP bar after each planted large surprise.

    The bump lands on the bar AFTER the event bar, which is the `drift` this organ measures --
    the tradable half. Nothing is added to the event bar itself, so a correct organ reads the
    planted effect in `drift` and finds `impact` empty.
    """
    rng = np.random.default_rng(seed)
    hours = 24 * 200
    index = pd.date_range(START, periods=hours, freq="h", tz="UTC")
    returns = rng.normal(0.0, NOISE_SD, hours)
    stamps = {t: i for i, t in enumerate(index)}
    for pair in pairs:
        if pair["release"] not in planted:
            continue
        surprise = float(pair["actual"]) - float(pair["consensus"])
        if surprise <= 1.0:
            continue
        when = datetime.fromisoformat(pair["at"]).replace(minute=0, second=0, microsecond=0)
        pos = stamps.get(pd.Timestamp(when))
        if pos is not None and pos + 1 < hours:
            returns[pos + 1] += BUMP
    close = 1.1000 * np.exp(np.cumsum(returns))
    return pd.DataFrame({"open": close, "close": close}, index=index)


def _plant(desk, pairs: list[dict[str, Any]], frame: pd.DataFrame, monkeypatch,
           symbol: str = "EURUSD") -> None:
    Path(es.STORE).write_text("".join(json.dumps(p) + "\n" for p in pairs), "utf-8")
    monkeypatch.setattr(es, "_chart",
                        lambda s: (frame, "H1", 60) if s == symbol else None)


# --------------------------------------------------------------------------------- the tests
def test_a_planted_reaction_is_found_and_a_placebo_release_is_not(desk, monkeypatch):
    planted = _pairs("PLANTED_CPI", "planted_release", "EURUSD")
    placebo = _pairs("PLACEBO_PMI", "placebo_release", "EURUSD",
                     start=START + timedelta(days=1))
    pairs = planted + placebo
    _plant(desk, pairs, _frame(pairs, {"PLANTED_CPI"}), monkeypatch)

    report = es.build(days=4000, budget_s=60.0, collect_enabled=False, apply=True,
                      now=START + timedelta(days=200))["report"]

    assert report["status"] == "present", report["why"]
    cells = {(c["kind"], c["bucket"], c["horizon"]): c for c in report["cells"]}
    hit = cells[("planted_release", "up_ge1sigma", "1h")]
    miss = cells[("placebo_release", "up_ge1sigma", "1h")]
    assert hit["mean_bp"] > 20.0, hit
    assert hit["clears"] is True, hit
    assert abs(miss["mean_bp"]) < 5.0, miss
    assert miss["clears"] is False, miss
    # The bump was planted AFTER the event bar, so the tradable half carries it and the impact
    # bar does not. An organ that measured from the wrong anchor would show the reverse.
    assert abs(float(hit["impact_mean_bp"])) < 5.0, hit
    assert {c["symbol"] for c in desk["donated"]} == {"EURUSD"}, desk["donated"]
    assert desk["donated"][0]["params"]["side"] == 1
    # One ticket per (symbol, kind, bucket): four horizons of one reaction is one mechanism.
    keys = [(c["evidence"]["bucket"], c["title"].split()[0]) for c in desk["donated"]]
    assert len(keys) == len(set(keys)), keys
    assert any("four horizons" in r["why"] for r in report["donated"]["refused"])


def test_a_downside_surprise_keeps_its_own_bucket(desk, monkeypatch):
    """The four buckets are separate measurements: planting only upside must leave the downside
    bucket flat. A cell that pooled the signs would report a mean of roughly zero for both."""
    pairs = _pairs("PLANTED_CPI", "planted_release", "EURUSD")
    _plant(desk, pairs, _frame(pairs, {"PLANTED_CPI"}), monkeypatch)
    report = es.build(days=4000, budget_s=60.0, collect_enabled=False, apply=False,
                      now=START + timedelta(days=200))["report"]
    cells = {(c["bucket"], c["horizon"]): c for c in report["cells"]}
    assert cells[("up_ge1sigma", "1h")]["mean_bp"] > 20.0
    assert abs(cells[("dn_ge1sigma", "1h")]["mean_bp"]) < 5.0


def test_thin_history_never_produces_a_z(desk, monkeypatch):
    """Nine prints of a release cannot define that release's own sigma, so there is no z at all.

    The count must appear as `thin_history`: a release the desk cannot yet standardize is a named
    state, and filling it with a pooled sigma or a zero would invent surprises.
    """
    pairs = _pairs("SHORT_SERIES", "planted_release", "EURUSD", n=9)
    _plant(desk, pairs, _frame(pairs, set()), monkeypatch)
    report = es.build(days=4000, budget_s=60.0, collect_enabled=False, apply=False,
                      now=START + timedelta(days=200))["report"]
    assert report["n_events"] == 0
    assert report["surprise"]["thin_history"] == 9
    assert report["status"] == es.UNMEASURED
    assert "prior surprises" in report["why"]


def test_an_equity_is_measured_and_never_donated(desk, monkeypatch):
    """A share CFD with the SAME planted reaction: the cell is measured, the donation is refused.

    The real `universe_policy.may_hypothesise` reads the synthetic registry and decides; nothing
    here stubs the fence it is testing.
    """
    assert up.may_hypothesise("APPLE") is False
    pairs = _pairs("PLANTED_CPI", "planted_release", "APPLE")
    _plant(desk, pairs, _frame(pairs, {"PLANTED_CPI"}), monkeypatch, symbol="APPLE")

    report = es.build(days=4000, budget_s=60.0, collect_enabled=False, apply=True,
                      now=START + timedelta(days=200))["report"]

    assert any(c["symbol"] == "APPLE" and c["clears"] for c in report["cells"]), "measured"
    assert desk["donated"] == []
    refusals = report["donated"]["refused"]
    assert refusals and all(r["symbol"] == "APPLE" for r in refusals)
    assert "two-lane" in refusals[0]["why"]


def test_absent_inputs_write_an_unmeasured_report(desk, monkeypatch):
    """No grounds, no store, no calendar: a verdict and a file, never a crash and never a zero."""
    monkeypatch.setattr(es, "_fetcher", lambda: (None, "UNMEASURED-NO-FETCHER: test"))
    assert es.main(["--once", "--budget-s", "20"]) == 0
    report = json.loads(Path(es.REPORT).read_text("utf-8"))
    assert report["status"] == es.UNMEASURED
    assert report["why"]
    assert report["collector"]["status"] == es.UNMEASURED
    assert "NO-FETCHER" in report["collector"]["why"]
    assert report["n_pairs"] == 0 and report["donated"]["n"] == 0


def test_dry_run_writes_nothing(desk, monkeypatch):
    pairs = _pairs("PLANTED_CPI", "planted_release", "EURUSD")
    _plant(desk, pairs, _frame(pairs, {"PLANTED_CPI"}), monkeypatch)
    before = sorted(p.name for p in Path(desk["tmp"]).iterdir())
    assert es.main(["--once", "--budget-s", "30", "--dry-run"]) == 0
    assert sorted(p.name for p in Path(desk["tmp"]).iterdir()) == before
    assert not Path(es.REPORT).exists()
    assert desk["donated"] == []


# ------------------------------------------------------------------------------ the collector
def _grounds(rows: list[dict[str, Any]]) -> None:
    Path(es.GROUNDS).write_text(json.dumps({"sources": rows}), "utf-8")


def test_the_collector_refuses_ground_it_is_not_allowed_to_fetch(desk):
    """Registered-but-forbidden ground never reaches the fetcher, and says why it did not."""
    asked: list[str] = []

    def fetcher(src, timeout=25.0, validators=None):
        asked.append(str(src.get("id")))
        return {"status": "COLLECTED", "parse": {"parsed": False}}

    _grounds([
        {"id": "forbidden", "url": "https://example.invalid/a", "access": "public",
         "machine_use_allowed": False, "licence": "terms forbid automated access",
         "fields": {"release": "r", "date": "d", "actual": "a", "consensus": "c"}},
        {"id": "keyed", "url": "https://example.invalid/b", "access": "key",
         "machine_use_allowed": True, "licence": "free key",
         "fields": {"release": "r", "date": "d", "actual": "a", "consensus": "c"}},
        {"id": "no_map", "url": "https://example.invalid/c", "access": "public",
         "machine_use_allowed": True, "licence": "public", "fields": {}},
        {"id": "allowed", "url": "https://example.invalid/d", "access": "public",
         "machine_use_allowed": True, "licence": "public domain",
         "fields": {"release": "r", "date": "d", "actual": "a", "consensus": "c"}},
    ])
    out = es.collect(budget_s=10.0, now=START, fetch=fetcher)

    assert asked == ["allowed"], "only the admissible row may be fetched"
    by_id = {row["id"]: row for row in out["sources"]}
    assert by_id["forbidden"]["status"] == "REFUSED_BY_POLICY"
    assert "never scrapes" in by_id["forbidden"]["why"]
    assert by_id["keyed"]["status"] == "REFUSED_BY_POLICY"
    assert "never reads a key" in by_id["keyed"]["why"]
    assert "NO_FIELD_MAP" in by_id["no_map"]["why"]


def test_the_registered_grounds_file_on_this_tree_is_lawful():
    """The shipped source table itself: every fetchable row is public, licensed and mapped."""
    doc = json.loads(Path(es.DESK / "data" / "event_consensus_sources.json")
                     .read_text("utf-8-sig"))
    rows = doc["sources"]
    assert rows, "a grounds file with no rows is a collector with no ground"
    for row in rows:
        ok, why = es.admissible(row)
        assert row.get("licence"), f"{row['id']} carries no licence line"
        if ok:
            assert row["access"] == "public" and row["machine_use_allowed"] is True, row["id"]
            assert row["url"].startswith("https://"), row["id"]
        else:
            assert why, row["id"]
    assert any(r.get("machine_use_allowed") is False for r in rows), (
        "ground the desk knows and refuses must be registered, so the gap has a name")


def test_the_collector_never_invents_a_consensus(desk):
    """A document carrying only actuals yields half-rows and NOT ONE pair."""
    def fetcher(src, timeout=25.0, validators=None):
        return {"status": "COLLECTED", "validators": {},
                "parse": {"parsed": True, "path": str(Path(desk["tmp"]) / "doc.json")}}

    (Path(desk["tmp"]) / "doc.json").write_text(json.dumps({"observations": [
        {"r": "US CPI", "d": "2026-01-15", "a": 3.1, "p": "2025-12"},
        {"r": "US CPI", "d": "2026-02-15", "a": 3.4, "p": "2026-01"}]}), "utf-8")
    _grounds([{"id": "actual_only", "url": "https://example.invalid/x", "access": "public",
               "machine_use_allowed": True, "licence": "public domain",
               "fields": {"provides": "actual", "path": "observations", "release": "r",
                          "date": "d", "actual": "a", "period": "p"}}])

    out = es.collect(budget_s=10.0, now=START, fetch=fetcher)
    assert len(out["rows"]) == 2
    assert all(row["consensus"] is None for row in out["rows"])
    assert es.join_sides(out["rows"]) == []


def test_a_half_row_waits_for_its_partner(desk):
    """The join is on the reference period, and it stamps the pair at the LATER half."""
    consensus = {"release": "US CPI", "period": "2026-01", "at": "2026-02-10T00:00:00+00:00",
                 "actual": None, "consensus": 3.2, "source_id": "survey",
                 "instruments": ["EURUSD"], "kind": "macro_release"}
    assert es.join_sides([consensus]) == []
    actual = {"release": "US CPI", "period": "2026-01", "at": "2026-02-15T00:00:00+00:00",
              "actual": 3.4, "consensus": None, "source_id": "agency",
              "instruments": ["EURUSD"], "kind": "macro_release"}
    joined = es.join_sides([consensus, actual])
    assert len(joined) == 1
    assert joined[0]["actual"] == 3.4 and joined[0]["consensus"] == 3.2
    assert joined[0]["at"] == actual["at"], "a pair is known when its LATER half is published"
    assert joined[0]["source_id"] == "survey+agency"


def test_the_store_is_a_vintage_and_never_restates_history(desk):
    """A revision arrives as its own row; the first writing of a pair is never edited."""
    first = {"release": "US CPI", "period": "2026-01", "at": "2026-02-15T00:00:00+00:00",
             "actual": 3.4, "consensus": 3.2, "source_id": "agency", "provides": "both"}
    rows, added = es.merge_store([first], now=START)
    Path(es.STORE).write_text("".join(json.dumps(r) + "\n" for r in rows), "utf-8")
    assert added == 1
    again, added = es.merge_store([dict(first)], now=START)
    assert added == 0 and len(again) == 1, "the same pair twice is one vintage"
    revision = {**first, "at": "2026-03-15T00:00:00+00:00", "actual": 3.5}
    rows, added = es.merge_store([revision], now=START)
    assert added == 1 and len(rows) == 2, "a revision is a new row, never an overwrite"
