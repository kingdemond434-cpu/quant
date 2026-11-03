"""THE CONGRESS ATTEST SWITCH -- OFF by default, no request, no reader, data on disk ignored.

Auditor ruling 2026-11-03: congressional periodic transaction reports may not be used for a
commercial purpose (5 U.S.C. 13107(c)), and trading is the case the statute names. So collection
and every downstream reader stay OFF until the principal attests through `libs.data.congress_gate`.

Three properties, each on a temp store so nothing here touches the desk's own data:
  1. default OFF makes no request and returns a HELD verdict with its missed-growth line;
  2. every downstream reader ignores congressional files ALREADY ON DISK while OFF;
  3. the switch ON lets the same data through every one of those readers.
"""
from __future__ import annotations

import io
import json
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import free_stack as fs  # noqa: E402

FIX = _DESK / "tests" / "fixtures" / "free_stack"
NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
SID = "congress_trades"
SERIES = f"fs_{SID}"


def _house_zip() -> bytes:
    xml = ("<FinancialDisclosure><Member><FilingType>P</FilingType><FilingDate>9/21/2026"
           "</FilingDate><DocID>1</DocID></Member></FinancialDisclosure>")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("2026FD.xml", xml)
    return buf.getvalue()


class Recorder:
    def __init__(self) -> None:
        self.urls: list[str] = []

    def __call__(self, url: str, headers=None, body=None) -> bytes:
        self.urls.append(url)
        if "disclosures-clerk.house.gov" in url:
            return _house_zip()
        if "house-stock-watcher" in url:
            return (FIX / "stockwatcher.synthetic.json").read_bytes()
        raise fs.FetchError("http_403", url)


def _row() -> dict:
    doc = json.loads((_DESK / "data" / "free_stack_sources.json").read_text("utf-8"))
    return next(r for r in doc["sources"] if r["id"] == SID)


@pytest.fixture()
def off(monkeypatch) -> None:
    monkeypatch.delenv("QUANT_CONGRESS_ATTEST", raising=False)


@pytest.fixture()
def on(monkeypatch) -> None:
    monkeypatch.setenv("QUANT_CONGRESS_ATTEST", "1")


def _plant(desk: Path) -> dict:
    """Congressional data an earlier pass already stored: PIT obs, lake series, columns."""
    obs = desk / "data" / "free_stack" / "obs" / f"{SID}.jsonl"
    obs.parent.mkdir(parents=True, exist_ok=True)
    days = pd.date_range("2026-06-01", periods=60, freq="D", tz="UTC")
    rng = np.random.default_rng(3)
    with obs.open("w", encoding="utf-8") as fh:
        for d, v in zip(days, rng.normal(0, 1, len(days)), strict=True):
            fh.write(json.dumps({"key": "net_all", "period_end": d.strftime("%Y-%m-%d"),
                                 "value": float(v), "available_time": d.isoformat(),
                                 "first_seen_utc": d.isoformat(), "vintage": "backfill"}) + "\n")
    series = desk / "data" / "lake" / "series"
    series.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"period_end": days.strftime("%Y-%m-%d"),
                  "available_time": [d.isoformat() for d in days],
                  "net_all": rng.normal(0, 1, len(days))}).to_parquet(
        series / f"{SERIES}.parquet", index=False)
    return {SID: {"net_all": {"hypothesis": ["US500"], "event": [], "why": "planted"}}}


# ------------------------------------------------------------------- 1. default OFF ----
def test_default_off_makes_no_request_and_returns_held_with_missed_growth(off) -> None:
    from libs.data import congress_gate
    rec = Recorder()
    h = fs.fetch_congress(rec, _row(), {}, NOW)
    assert rec.urls == []
    assert h.requests == 0 and not h.obs and not h.raw and not h.columns
    assert h.status == congress_gate.HELD
    mg = h.verdict["missed_growth"]
    assert mg["rail"] == congress_gate.RAIL and mg["verdict"] == "UNMEASURED"
    assert mg["two_sided"] is True and "13107(c)" in mg["legal_basis"]


def test_default_off_through_the_hunter_stores_nothing(off, tmp_path: Path) -> None:
    from free_stack_hunter import Store, run
    store = Store(tmp_path / "desk")
    roster = tmp_path / "roster.json"
    roster.write_text(json.dumps({"sources": [_row()]}), "utf-8")
    rec = Recorder()
    rep = run(budget_s=60, fetch=rec, store=store, roster=roster, now=NOW, live=False)
    assert rec.urls == []
    per = rep["per_source"][SID]
    assert per["status"] == "AWAITING_PRINCIPAL"
    assert per["missed_growth"]["verdict"] == "UNMEASURED"
    assert not (store.obs / f"{SID}.jsonl").exists()
    assert not (store.series / f"{SERIES}.parquet").exists()


def test_only_exactly_one_turns_it_on() -> None:
    """informed_capital.congress_attested() reads the same variable the same way: one switch."""
    from libs.data import congress_gate as g
    assert not g.attested(env={})
    for v in ("0", "true", "yes", "on", "maybe", " "):
        assert not g.attested(env={"QUANT_CONGRESS_ATTEST": v}), v
    assert g.attested(env={"QUANT_CONGRESS_ATTEST": "1"})
    assert g.attested(env={"QUANT_CONGRESS_ATTEST": " 1 "})
    assert g.RAIL == "congress_attestation_gate" and g.HELD == "AWAITING_PRINCIPAL"


# --------------------------------------------------- 2. readers ignore data on disk ----
def test_off_every_reader_ignores_congress_data_already_on_disk(off, tmp_path: Path,
                                                               monkeypatch) -> None:
    desk = tmp_path / "desk"
    cols = _plant(desk)
    series = desk / "data" / "lake" / "series"
    # the conditioner families (exogenous_conditioner, alt_series_*, cell_modifiers)
    from mt5desk.family_exogenous_conditioner import conditioner, series_path
    assert series_path(SERIES, series) is None
    assert conditioner(SERIES, "net_all", "level_z", root=series) is None
    from mt5desk.family_alt_series import momentum_z
    assert momentum_z(SERIES, "net_all", lookback=1, z_window=20, root=series) is None
    from mt5desk import family_alt_release
    assert family_alt_release.series_path(SERIES, series) is None
    # the lake's PIT door
    from libs.data.lake_pit import usable_series
    view = usable_series(series, NOW)
    assert SERIES not in view.visible and SERIES in view.held
    # the proposer never mints a cell from it
    import free_stack_proposer as P
    monkeypatch.setattr(P, "series_exists", lambda sid: True)
    grid, skipped = P.build_grid(cols, P.roster_rows())
    assert grid == [] and "AWAITING_PRINCIPAL" in skipped[SID]
    # the hunter's allocation state reads it as UNMEASURED
    from free_stack_hunter import Store, build_alt_state
    store = Store(desk)
    out = build_alt_state(store, cols, NOW)
    assert out["symbols"] == 0 and out["held"] == [SID]
    doc = json.loads(store.alt_state.read_text("utf-8"))
    assert doc["symbols"] == {} and SID in doc["held_principal_switch"]


# --------------------------------------------------------------- 3. the switch ON ----
def test_on_lets_the_data_through_every_reader(on, tmp_path: Path, monkeypatch) -> None:
    rec = Recorder()
    h = fs.fetch_congress(rec, _row(), {}, NOW)
    assert rec.urls and h.status == "OK" and h.obs and not h.verdict
    desk = tmp_path / "desk"
    cols = _plant(desk)
    series = desk / "data" / "lake" / "series"
    from mt5desk.family_exogenous_conditioner import conditioner, series_path
    assert series_path(SERIES, series) is not None
    assert conditioner(SERIES, "net_all", "level_z", root=series) is not None
    from mt5desk import family_alt_release
    assert family_alt_release.series_path(SERIES, series) is not None
    from libs.data.lake_pit import usable_series
    assert SERIES in usable_series(series, NOW).visible
    import free_stack_proposer as P
    monkeypatch.setattr(P, "series_exists", lambda sid: True)
    grid, skipped = P.build_grid(cols, P.roster_rows())
    assert grid and SID not in skipped
    from free_stack_hunter import Store, build_alt_state
    out = build_alt_state(Store(desk), cols, NOW)
    assert out["symbols"] == 1 and out["held"] == []
