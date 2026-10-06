"""The alt_proxies equity hand-off reaches cells: event lane + conditioned class books, charged."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import cell_modifiers as cm  # noqa: E402
from mt5desk import family_alt_release as far  # noqa: E402
from mt5desk import family_exogenous_conditioner as fec  # noqa: E402
from mt5desk.families import Signal  # noqa: E402

from research import alt_equity_handoff as aeh  # noqa: E402
from research import alt_proxies as ap  # noqa: E402
from research import proposer_common as pc  # noqa: E402
from research import universe_policy as up  # noqa: E402

LAKE = "alt_test_src__semis_yoy"


def _handoff() -> dict:
    return {"use": "equity_handoff", "rows": [
        {"source": "kr_exports_early", "series": "semis_yoy", "lake_file": LAKE,
         "columns": ["surprise_z", "pace"], "shares": {"NVIDIA": 1, "AMD": 1},
         "dead": False, "terms": "confirmed", "usable": True},
        {"source": "us_oi_card_spend", "series": "spend_all", "lake_file": "alt_dead",
         "shares": {"Visa": 1}, "dead": True, "terms": "confirmed", "usable": False}]}


def _bars(days: int = 700) -> pd.DataFrame:
    idx = pd.date_range("2023-01-02", periods=days * 24, freq="h", tz="UTC")
    rng = np.random.default_rng(7)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.002, len(idx))))
    return pd.DataFrame({"open": close, "high": close * 1.001, "low": close * 0.999,
                         "close": close, "volume": 1.0}, index=idx)


def _lake(dirpath: Path) -> None:
    """A weekly release, alternating surprise sign and pace sign, first vintage + a revision."""
    rows = []
    for i, day in enumerate(pd.date_range("2023-02-01", periods=90, freq="7D", tz="UTC")):
        z = 1.5 if i % 2 == 0 else -1.5
        pace = 1.0 if (i // 4) % 2 == 0 else -1.0
        for rev, lag in ((0, 1), (1, 3)):          # a revision two days later is NOT an event
            at = day + pd.Timedelta(days=lag, hours=13)
            rows.append({"event_time": day.isoformat(), "available_time": at.isoformat(),
                         "published_time": at.isoformat(), "retrieval_time": at.isoformat(),
                         "revision_time": at.isoformat(), "source_id": "test",
                         "vintage_id": f"v{i}.{rev}", "value": float(i), "pace": pace,
                         "surprise_z": z if rev == 0 else -z, "pit_quality": "PIT"})
    dirpath.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(dirpath / f"{LAKE}.csv", index=False)


def _daily_family(df: pd.DataFrame, *, symbol: str, hold_d: int = 5) -> list[Signal]:
    """A stand-in class-book leg: long on even days, short on odd, one signal a day at 22:00."""
    d = df[df.index.hour == 22]
    out = []
    for i, t in enumerate(d.index[30:]):
        s = 1 if i % 2 == 0 else -1
        px = float(d.loc[t, "close"])
        out.append(Signal(time=t, side=s, stop=px - s, target=px + 2 * s, ttl_bars=24,
                          tag="fake", trigger=None, wait_bars=1))
    return out


def test_the_committed_handoff_mints_cells_in_the_two_lanes_only() -> None:
    doc = json.loads(aeh.HANDOFF.read_text("utf-8"))
    cells, census = aeh.mint(doc)
    usable = [r for r in doc["rows"] if r["usable"]]
    pairs = sum(len(r["shares"]) for r in usable)
    assert census["by_lane"]["event"] == pairs            # one event cell per (series, share)
    assert census["by_lane"].get("class_book", 0) > 0
    for c in cells:
        assert up.is_equity(c["symbol"])
        assert up.may_hypothesise(c["symbol"], c["family"]), c["family"]
        assert c["family"] in up.CROSS_SECTIONAL_FAMILIES or c["family"] in up.NEWS_LANE_FAMILIES
    # a DEAD or terms-refused row mints nothing
    minted_sources = {c["source_id"] for c in cells}
    assert not minted_sources & {r["source"] for r in doc["rows"] if not r["usable"]}


def test_release_drift_uses_first_vintage_on_the_broker_clock(tmp_path: Path) -> None:
    _lake(tmp_path)
    ev = far.releases(LAKE, root=tmp_path)
    assert len(ev) == 90 and all(v in (1.5, -1.5) for _, v in ev)
    assert ev[0][1] == 1.5                                   # the revision's -1.5 is not an event
    sigs = far.family_alt_release_drift(_bars(), source=LAKE, prior_sign=-1, series_root=tmp_path)
    assert sigs
    first_at = ev[0][0]
    assert sigs[0].time >= far.to_broker(first_at)          # never before the release
    assert sigs[0].side == -1                                # +1.5 surprise x prior -1
    # summer: New York is UTC-4, so broker = UTC + 3; winter: UTC + 2
    assert far.to_broker(pd.Timestamp("2024-07-01 12:00", tz="UTC")).hour == 15
    assert far.to_broker(pd.Timestamp("2024-01-10 12:00", tz="UTC")).hour == 14
    assert far.family_alt_release_drift(_bars(), source="absent", prior_sign=1) == []


def test_the_handoff_runs_through_to_donated_charged_cells(tmp_path: Path,
                                                           monkeypatch: pytest.MonkeyPatch
                                                           ) -> None:
    lake = tmp_path / "lake"
    _lake(lake)
    hp = tmp_path / "handoff.json"
    hp.write_text(json.dumps(_handoff()), "utf-8")
    reg = tmp_path / "data_registry.json"
    reg.write_text(json.dumps({"schema_version": 1, "datasets": {}}), "utf-8")
    monkeypatch.setattr(aeh, "SERIES_DIR", lake)
    monkeypatch.setattr(far, "SERIES_DIR", lake)
    monkeypatch.setattr(fec, "SERIES_DIR", lake)
    cm._ALT_CACHE.clear()
    monkeypatch.setattr(aeh, "REPORT", tmp_path / "ALT_EQUITY_HANDOFF.json")
    monkeypatch.setattr(aeh, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(aeh, "DATA_REGISTRY", reg)
    bars = _bars()
    monkeypatch.setattr(aeh, "_bars", lambda _sym: bars)
    monkeypatch.setattr(aeh, "class_book_registry", lambda: {
        "families": {"cross_sectional_class_momentum": _daily_family},
        "grid": {"cross_sectional_class_momentum": {"hold_d": [5]}}, "scoped": {},
        "basis": "test"})
    monkeypatch.setattr(ap, "DEFAULT_PATHS", ap.Paths(tmp_path / "desk"))
    monkeypatch.setattr(pc, "INTEL", tmp_path / "intel")
    monkeypatch.setattr(pc, "_record_in_registry", lambda *_a, **_k: None)
    monkeypatch.setattr(pc, "_preregister", lambda *_a, **_k: {"preregistered": 0, "failed": 0})

    rep = aeh.run(handoff_path=hp)
    assert rep["status"] == "OK"
    assert rep["minted"]["cells"] == 6                      # 2 shares x (1 event + 2 class-book)
    assert rep["minted"]["not_minted"] == {"DEAD": 1}
    assert rep["measured_this_pass"] == 6
    assert rep["donated_this_pass"] > 0
    files = list((tmp_path / "intel" / aeh.SOURCE).glob("discoveries_*.json"))
    assert len(files) == 1
    doc = json.loads(files[0].read_text("utf-8"))
    assert doc["tests_run"] == 6                             # every measured cell is charged
    fams = {r["family"] for r in doc["discoveries"]}
    assert "alt_release_drift" in fams
    for r in doc["discoveries"]:
        assert r["source_culture"] == "KR/ko" and r["participant_structure"]
        assert r["provenance"]["handoff_sha256"] and r["available_time"]
        assert r["required_data"][0] == aeh.DATASET_KEY
        if r["family"] != "alt_release_drift":
            assert r["params"]["conditioner"].startswith(f"alt:{LAKE}:pace:")
            assert r["params"]["side_mode"] in ("long", "short")
    # the dataset is registered for the D18 census, and a second pass re-donates nothing
    row = json.loads(reg.read_text("utf-8"))["datasets"][aeh.DATASET_KEY]
    assert row["lifecycle"] == "INGESTED" and LAKE in row["series"]
    before = reg.read_bytes()
    again = aeh.run(handoff_path=hp)
    assert reg.read_bytes() == before                    # a present row is never rewritten
    assert again["donated_this_pass"] == 0 and again["measured_this_pass"] == 0
    assert again["held"].get("ALREADY_DONATED") == rep["donated_this_pass"]


def test_an_unreadable_handoff_is_unmeasured_not_zero(tmp_path: Path,
                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(aeh, "REPORT", tmp_path / "r.json")
    rep = aeh.run(handoff_path=tmp_path / "absent.json")
    assert rep["status"] == aeh.UNMEASURED and "cells" not in rep


def test_dataset_links_reach_the_registry_row() -> None:
    got = pc._dataset_links({"required_data": [aeh.DATASET_KEY], "lineage": {"dataset": "x"}})
    assert got == {"required_data": [aeh.DATASET_KEY], "lineage": {"dataset": "x"}}
    assert pc._dataset_links({"required_data": "a string", "lineage": []}) == {}
