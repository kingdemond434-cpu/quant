"""The alt_proxies equity hand-off reaches TRUE cross-sectional books, charged once per cell.

Pinned here, on synthetic bars, a synthetic hand-off and synthetic lake series only:
  * the committed hand-off mints ONLY class-book legs (no news-lane cell: a macro release is not
    company news), every one admitted for a share CFD, and dead / terms-refused rows mint nothing;
  * the books RANK the prior-signed reading ACROSS the equity class on the same date: the top of
    the class is long, the bottom short, the middle flat; an unmapped member is absent from the
    rank (never scored zero), and a class with too few scored members ranks nobody;
  * nothing is visible before its first vintage's available_time on the broker clock;
  * a cell is charged to the trial census ONCE: re-measuring on a later day charges nothing, the
    charged ledger only grows, a changed book membership is a new hypothesis and charges again,
    and an unreadable ledger is set aside rather than overwritten by a smaller one.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import class_books as books  # noqa: E402
from mt5desk import families_alt_exposure as alt  # noqa: E402
from mt5desk import families_cross_sectional as xs  # noqa: E402

from research import alt_equity_handoff as aeh  # noqa: E402
from research import alt_proxies as ap  # noqa: E402
from research import proposer_common as pc  # noqa: E402
from research import universe_policy as up  # noqa: E402

EQUITIES = ["EQA", "EQB", "EQC", "EQD", "EQE", "EQF"]
#: prior-signed release surprise per member: EQF is mapped with prior -1 to a +2 surprise.
SURPRISE = {"EQA": (2.0, 1), "EQB": (1.0, 1), "EQC": (0.5, 1), "EQD": (-0.5, 1),
            "EQE": (-1.0, 1), "EQF": (2.0, -1)}
DAYS = 520
FIRST_RELEASE = pd.Timestamp("2020-03-02 12:00", tz="UTC")


def _bars(seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2020-01-06", periods=DAYS, tz="UTC")
    idx = pd.DatetimeIndex([d + pd.Timedelta(hours=h) for d in dates for h in range(24)])
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.002, len(idx))))
    open_ = np.r_[close[0], close[:-1]]
    return pd.DataFrame({"open": open_, "high": np.maximum(open_, close) * 1.0005,
                         "low": np.minimum(open_, close) * 0.9995, "close": close,
                         "tick_volume": 100}, index=idx)


def _lake_file(sym: str) -> str:
    return f"alt_test__{sym.lower()}"


#: pace per member: a steady trend standardises to about +-1.7 against its own history; an
#: alternating series to about +-1. EQF falls with prior -1, so it ranks with EQA on top.
PACE = {"EQA": lambda i: 0.03 * i, "EQE": lambda i: -0.03 * i, "EQF": lambda i: -0.03 * i}


def _write_series(lake: Path, sym: str, z: float) -> None:
    """A daily release, first vintage + a later revision that must NOT count."""
    rows = []
    fn = PACE.get(sym, lambda i: float((-1) ** i))
    for i, day in enumerate(pd.date_range(FIRST_RELEASE, periods=DAYS + 200, freq="D")):
        pace = fn(i)
        for rev, lag_h in ((0, 0), (1, 50)):
            at = day + pd.Timedelta(hours=lag_h)
            rows.append({"event_time": day.date().isoformat(), "available_time": at.isoformat(),
                         "published_time": at.isoformat(), "retrieval_time": at.isoformat(),
                         "revision_time": at.isoformat(), "source_id": "test",
                         "vintage_id": f"v{i}.{rev}", "value": float(i), "pace": pace,
                         "surprise_z": z if rev == 0 else -z, "pit_quality": "live"})
    lake.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(lake / f"{_lake_file(sym)}.csv", index=False)


def _handoff(members: list[str]) -> dict:
    rows = [{"source": "kr_exports_early", "series": sym.lower(), "lake_file": _lake_file(sym),
             "columns": ["surprise_z", "pace"], "shares": {sym: SURPRISE[sym][1]},
             "dead": False, "terms": "confirmed", "usable": True} for sym in members]
    rows.append({"source": "us_oi_card_spend", "series": "spend_all", "lake_file": "alt_dead",
                 "shares": {"Visa": 1}, "dead": True, "terms": "confirmed", "usable": False})
    return {"use": "equity_handoff", "rows": rows}


@pytest.fixture()
def book(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    frames = {}
    bars_dir, lake = tmp_path / "bars", tmp_path / "lake"
    bars_dir.mkdir()
    for i, sym in enumerate(EQUITIES):
        frames[sym] = _bars(30 + i)
        frames[sym].to_parquet(bars_dir / f"{sym}_H1.parquet")
        _write_series(lake, sym, SURPRISE[sym][0])
    hp = tmp_path / "handoff.json"
    hp.write_text(json.dumps(_handoff(EQUITIES)), "utf-8")
    monkeypatch.setattr(xs, "UNIVERSE_DIR", bars_dir)
    monkeypatch.setattr(xs, "class_of", lambda s: "equity" if s in EQUITIES else None)
    monkeypatch.setattr(xs, "class_symbols", lambda k: list(EQUITIES) if k == "equity" else [])
    monkeypatch.setattr(alt, "HANDOFF", hp)
    monkeypatch.setattr(alt, "SERIES_DIR", lake)
    xs._SERIES_CACHE.clear()
    alt._HANDOFF_CACHE.clear()
    alt._SERIES_CACHE.clear()
    yield frames, hp, lake
    xs._SERIES_CACHE.clear()
    alt._HANDOFF_CACHE.clear()
    alt._SERIES_CACHE.clear()


def _first(fam: str) -> dict:
    return {k: v[0] for k, v in books.PARAM_GRID[fam].items()}


# ----------------------------------------------------------------------------- minting ---
def test_the_committed_handoff_mints_only_class_book_legs() -> None:
    doc = json.loads(aeh.HANDOFF.read_text("utf-8"))
    cells, census = aeh.mint(doc)
    mapped = {s for r in doc["rows"] if r["usable"] for s in r["shares"]}
    grid = sum(len(books.grid(f, "equity")) for f in alt.ALT_EXPOSURE_FAMILIES)
    assert census["by_lane"] == {"class_book": len(mapped) * grid} == {"class_book": len(cells)}
    for c in cells:
        assert up.is_equity(c["symbol"])
        assert c["family"] in up.CROSS_SECTIONAL_FAMILIES
        assert up.may_hypothesise(c["symbol"], c["family"]), c["family"]
        assert c["family"] not in up.NEWS_LANE_FAMILIES
    assert not {c["source_id"] for c in cells} & {r["source"] for r in doc["rows"]
                                                  if not r["usable"]}


def test_macro_release_is_off_the_news_lane_and_the_single_name_family_is_retired() -> None:
    from mt5desk import families_orthogonal as fo
    assert "alt_release_drift" not in up.NEWS_LANE_FAMILIES
    assert "alt_release_drift" not in fo.ORTHOGONAL_FAMILIES
    assert set(alt.ALT_EXPOSURE_FAMILIES) <= up.CROSS_SECTIONAL_FAMILIES
    # the generic seeder and the regime operator never walk a dedicated book
    assert not set(alt.ALT_EXPOSURE_FAMILIES) & set(books.families_for("equity"))
    assert all(c["base_family"] not in alt.ALT_EXPOSURE_FAMILIES
               for c in books.grid(books.OPERATOR, "equity"))


# ------------------------------------------------------------------------------ the rank ---
def test_release_book_ranks_across_the_class_on_the_same_date(book) -> None:
    frames, _hp, _lake = book
    fam = alt.family_alt_exposure_release_book
    sides = {s: {sig.side for sig in fam(frames[s], symbol=s, **_first(
        "alt_exposure_release_book"))} for s in EQUITIES}
    # scores: EQA +2, EQB +1, EQC +.5, EQD -.5, EQE -1, EQF +2 x prior -1 = -2; k = 2 of 6
    assert sides["EQA"] == {1} and sides["EQB"] == {1}
    assert sides["EQE"] == {-1} and sides["EQF"] == {-1}
    assert sides["EQC"] == set() and sides["EQD"] == set()


def test_pace_book_ranks_self_standardised_pace(book) -> None:
    frames, _hp, _lake = book
    fam = alt.family_alt_exposure_pace_book
    long_ = fam(frames["EQA"], symbol="EQA", **_first("alt_exposure_pace_book"))
    short = fam(frames["EQF"], symbol="EQF", **_first("alt_exposure_pace_book"))
    assert long_ and {s.side for s in long_} == {1}
    # EQF's pace falls and its prior is -1: a rising prior-signed reading, so it ranks on top
    assert short and {s.side for s in short} == {1}
    low = fam(frames["EQE"], symbol="EQE", **_first("alt_exposure_pace_book"))
    assert low and {s.side for s in low} == {-1}              # EQE falls with prior +1


def test_nothing_is_visible_before_its_first_vintage(book) -> None:
    frames, _hp, _lake = book
    sigs = alt.family_alt_exposure_release_book(frames["EQA"], symbol="EQA",
                                                **_first("alt_exposure_release_book"))
    first = pd.Timestamp(alt.to_broker_ns(pd.Series([FIRST_RELEASE]))[0], tz="UTC")
    assert sigs and min(pd.Timestamp(s.time) for s in sigs) >= first
    # the revision (surprise flipped, 50h later) is not a new release: EQA never goes short
    assert {s.side for s in sigs} == {1}
    # summer: New York is UTC-4, so broker = UTC + 3; winter: UTC + 2
    summer = pd.Series([pd.Timestamp("2024-07-01 12:00", tz="UTC")])
    winter = pd.Series([pd.Timestamp("2024-01-10 12:00", tz="UTC")])
    assert pd.Timestamp(alt.to_broker_ns(summer)[0]).hour == 15
    assert pd.Timestamp(alt.to_broker_ns(winter)[0]).hour == 14


def test_an_unmapped_member_is_absent_not_zero(book, tmp_path: Path) -> None:
    frames, hp, _lake = book
    hp.write_text(json.dumps(_handoff(["EQA", "EQB", "EQC", "EQE"])), "utf-8")
    alt._HANDOFF_CACHE.clear()
    params = _first("alt_exposure_release_book")
    assert alt.family_alt_exposure_release_book(frames["EQD"], symbol="EQD", **params) == []
    # four scored members is below MIN_MEMBERS: the day ranks nobody, never a rank against zeros
    assert alt.family_alt_exposure_release_book(frames["EQA"], symbol="EQA", **params) == []


# ------------------------------------------------------------------- charged once, ever ---
def _wire_organ(book, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    frames, hp, lake = book
    reg = tmp_path / "data_registry.json"
    reg.write_text(json.dumps({"schema_version": 1, "datasets": {}}), "utf-8")
    monkeypatch.setattr(aeh, "SERIES_DIR", lake)
    monkeypatch.setattr(aeh, "REPORT", tmp_path / "ALT_EQUITY_HANDOFF.json")
    monkeypatch.setattr(aeh, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(aeh, "CHARGED", tmp_path / "charged.json")
    monkeypatch.setattr(aeh, "DATA_REGISTRY", reg)
    monkeypatch.setattr(aeh, "_bars", lambda sym: xs._h1(frames[sym]) if sym in frames else None)
    monkeypatch.setattr(aeh, "applies", lambda sym, klass: sym in EQUITIES)
    monkeypatch.setattr(ap, "DEFAULT_PATHS", ap.Paths(tmp_path / "desk"))
    monkeypatch.setattr(pc, "INTEL", tmp_path / "intel")
    monkeypatch.setattr(pc, "_record_in_registry", lambda *_a, **_k: None)
    monkeypatch.setattr(pc, "_preregister", lambda *_a, **_k: {"preregistered": 0, "failed": 0})
    return hp


def _tests_run(tmp_path: Path) -> int:
    total = 0
    for f in (tmp_path / "intel" / aeh.SOURCE).glob("discoveries_*.json"):
        total += int(json.loads(f.read_text("utf-8"))["tests_run"])
    null = tmp_path / "desk" / "data" / "null_pass_trials.jsonl"
    if null.exists():
        total += sum(int(json.loads(ln)["tests_run"])
                     for ln in null.read_text("utf-8").splitlines() if ln.strip())
    return total


def test_each_cell_is_charged_once_and_the_ledger_only_grows(book, tmp_path: Path,
                                                             monkeypatch: pytest.MonkeyPatch
                                                             ) -> None:
    hp = _wire_organ(book, tmp_path, monkeypatch)
    n = len(EQUITIES) * len(alt.ALT_EXPOSURE_FAMILIES)
    day1 = datetime(2026, 10, 1, 12, tzinfo=UTC)
    rep = aeh.run(handoff_path=hp, now=day1)
    assert rep["status"] == "OK" and rep["minted"]["cells"] == n
    assert rep["minted"]["not_minted"] == {"DEAD": 1}
    assert rep["measured_this_pass"] == n and rep["trials_charged_this_pass"] == n
    assert _tests_run(tmp_path) == n
    assert rep["donated_this_pass"] > 0
    files = list((tmp_path / "intel" / aeh.SOURCE).glob("discoveries_*.json"))
    for r in json.loads(files[0].read_text("utf-8"))["discoveries"]:
        assert r["family"] in alt.ALT_EXPOSURE_FAMILIES
        assert r["required_data"][0] == aeh.DATASET_KEY and r["provenance"]["handoff_sha256"]
        assert "conditioner" not in r["params"] and "side_mode" not in r["params"]
    ledger1 = json.loads((tmp_path / "charged.json").read_text("utf-8"))
    assert ledger1["count"] == n

    # the NEXT DAY re-measures the undonated cells but charges nothing new
    for day in (2, 3, 30):
        again = aeh.run(handoff_path=hp, now=datetime(2026, 10, day, 12, tzinfo=UTC))
        assert again["measured_this_pass"] == n - rep["donated_this_pass"]
        assert again["trials_charged_this_pass"] == 0
        assert again["trials"]["remeasured_not_recharged"] == again["measured_this_pass"]
    assert _tests_run(tmp_path) == n                           # 66k/yr is now n, once
    ledger2 = json.loads((tmp_path / "charged.json").read_text("utf-8"))
    assert set(ledger1["charged"]) <= set(ledger2["charged"]) and ledger2["count"] == n

    # a changed book membership is a different hypothesis: charged again, ledger grows
    hp.write_text(json.dumps(_handoff(EQUITIES[:5])), "utf-8")
    alt._HANDOFF_CACHE.clear()
    grown = aeh.run(handoff_path=hp, now=datetime(2026, 10, 31, 12, tzinfo=UTC))
    assert grown["trials_charged_this_pass"] > 0
    ledger3 = json.loads((tmp_path / "charged.json").read_text("utf-8"))
    assert set(ledger2["charged"]) < set(ledger3["charged"])


def test_a_dry_run_charges_nothing_and_writes_no_ledger(book, tmp_path: Path,
                                                        monkeypatch: pytest.MonkeyPatch) -> None:
    hp = _wire_organ(book, tmp_path, monkeypatch)
    rep = aeh.run(handoff_path=hp, dry_run=True)
    assert rep["trials_charged_this_pass"] == 0 and not (tmp_path / "charged.json").exists()
    assert _tests_run(tmp_path) == 0


def test_an_unreadable_ledger_is_set_aside_not_shrunk(tmp_path: Path) -> None:
    p = tmp_path / "charged.json"
    aeh.save_charged({"charged": {}}, {"a": {"at": "x"}, "b": {"at": "y"}}, p)
    doc = aeh.save_charged({"charged": {}}, {"c": {"at": "z"}}, p)
    assert set(doc["charged"]) == {"a", "b", "c"}             # a smaller in-memory set cannot
    p.write_text("{not json", "utf-8")                       # shrink what is on disk
    ledger, status = aeh.load_charged(p)
    assert ledger == {"charged": {}} and status.startswith("UNREADABLE")
    assert list(tmp_path.glob("charged.json.unreadable-*"))


def test_an_unreadable_handoff_is_unmeasured_not_zero(tmp_path: Path,
                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(aeh, "REPORT", tmp_path / "r.json")
    rep = aeh.run(handoff_path=tmp_path / "absent.json")
    assert rep["status"] == aeh.UNMEASURED and "cells" not in rep


def test_dataset_links_reach_the_registry_row() -> None:
    got = pc._dataset_links({"required_data": [aeh.DATASET_KEY], "lineage": {"dataset": "x"}})
    assert got == {"required_data": [aeh.DATASET_KEY], "lineage": {"dataset": "x"}}
    assert pc._dataset_links({"required_data": "a string", "lineage": []}) == {}
