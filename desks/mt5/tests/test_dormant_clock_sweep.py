"""Every dormant sleeve or zeroed window owes a forward clock or a re-judge that can give it one
(principal 2026-11-18, every account every market day). Never a clock without a certificate."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
for p in (str(DESK), str(DESK / "research"), str(DESK.parents[1])):
    if p not in sys.path:
        sys.path.insert(0, p)

import dormant_clock_sweep as dcs  # noqa: E402

NOW = datetime(2026, 11, 18, 4, 0, tzinfo=UTC)
WINDOWS = {
    "asia": {"range_start": 7, "wait_bars": 12, "rr": 2.0, "ttl_bars": 12},
    "london_am": {"range_start": 10, "range_end": 13, "signal_at": 13, "wait_bars": 8,
                  "rr": 2.0, "ttl_bars": 12},
    "afternoon": {"range_start": 14, "range_end": 17, "signal_at": 17, "wait_bars": 8,
                  "rr": 2.0, "ttl_bars": 12},
}


@pytest.fixture(autouse=True)
def _pins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dcs, "_windows", lambda: {k: dict(v) for k, v in WINDOWS.items()})
    monkeypatch.setattr(dcs, "zeroed_windows",
                        lambda: {"gold_afternoon": "afternoon", "gold_london_am": "london_am"})
    monkeypatch.setattr(dcs, "_key", lambda sym, win, params, fam, side="LONG": f"{sym}.{win}")
    monkeypatch.setattr(dcs, "_cell_id",
                        lambda sym, fam, params: f"{sym}.{fam}.rs={params['range_start']}")


def _build(rows: list, clocks: dict, cert_keys: dict | None = None) -> dict:
    return dcs.build(NOW, sleeves={"sleeves": rows}, shadow=clocks, cert_keys=cert_keys or {})


def test_zeroed_gold_windows_without_a_clock_are_queued_at_the_gateway_spec() -> None:
    doc = _build([], {"XAUUSD.asia": {}})
    states = {r["name"]: r["state"] for r in doc["rows"]}
    assert states == {"gold_afternoon": "QUEUED_FOR_REJUDGE",
                      "gold_london_am": "QUEUED_FOR_REJUDGE"}
    by_win = {t["window"]: t for t in doc["targets"]}
    assert by_win["london_am"]["params"] == WINDOWS["london_am"]
    assert by_win["afternoon"]["params"]["rr"] == 2.0
    assert by_win["afternoon"]["params"]["wait_bars"] == 8


def test_a_window_with_a_clock_is_clocked_and_queues_nothing() -> None:
    doc = _build([], {"XAUUSD.london_am": {}, "XAUUSD.afternoon": {}})
    assert {r["state"] for r in doc["rows"]} == {"CLOCKED"}
    assert doc["targets"] == []


def test_standby_versions_share_one_target_and_retired_rows_are_only_counted() -> None:
    rows = [{"name": "gold_london_am_v2", "status": "STANDBY", "symbol": "XAUUSD",
             "window": "london_am"},
            {"name": "gold_london_am_v3", "status": "STANDBY", "symbol": "XAUUSD",
             "window": "london_am"},
            {"name": "old", "status": "RETIRED", "symbol": "EURUSD", "window": "asia"},
            {"name": "live_one", "status": "LIVE", "symbol": "XAUUSD", "window": "asia"}]
    doc = _build(rows, {})
    lam = [t for t in doc["targets"] if t["window"] == "london_am"]
    assert len(lam) == 1
    assert lam[0]["names"] == ["gold_london_am", "gold_london_am_v2", "gold_london_am_v3"]
    assert doc["n_retired_not_swept"] == 1
    assert "live_one" not in {r["name"] for r in doc["rows"]}


def test_certified_standby_is_named_never_requeued() -> None:
    rows = [{"name": "c1", "status": "STANDBY", "certificate": "external.X.c1"},
            {"name": "c2", "status": "STANDBY", "certificate": "external.X.c2"},
            {"name": "c3", "status": "STANDBY", "certificate": "external.X.c3"}]
    doc = _build(rows, {"X.ok": {}},
                 cert_keys={"external.X.c1": "X.ok", "external.X.c2": "X.missing"})
    st = {r["name"]: r for r in doc["rows"] if r["kind"] == "standby"}
    assert st["c1"]["state"] == "CLOCKED"
    assert st["c2"]["state"] == "CERTIFIED_NOT_CLOCKED"
    assert st["c2"]["why"] == "authorized, but no clock in shadow_state yet"
    assert st["c3"]["why"] == "no authorized run for this certificate"
    assert all(t["names"][0].startswith("gold_") for t in doc["targets"])


def test_a_row_with_no_exact_spec_is_unresolved_never_guessed() -> None:
    rows = [{"name": "mystery", "status": "STANDBY", "symbol": "EURUSD", "family": "x"}]
    doc = _build(rows, {"XAUUSD.london_am": {}, "XAUUSD.afternoon": {}})
    row = next(r for r in doc["rows"] if r["name"] == "mystery")
    assert row["state"] == "UNRESOLVED"
    assert doc["targets"] == []


def test_unreadable_inputs_are_unmeasured_not_clean() -> None:
    doc = dcs.build(NOW, sleeves="not a roster", shadow={}, cert_keys={})
    assert doc["status"] == dcs.UNMEASURED and doc["why"] == "sleeves.json unreadable"
    doc = dcs.build(NOW, sleeves={"sleeves": []}, shadow="x", cert_keys={})
    assert doc["status"] == dcs.UNMEASURED


def test_apply_appends_once_and_never_rewrites(tmp_path: Path,
                                                monkeypatch: pytest.MonkeyPatch) -> None:
    docket = tmp_path / "docket.json"
    docket.write_text(json.dumps([{"symbol": "EURUSD", "family": "f"}]), encoding="utf-8")
    monkeypatch.setattr(dcs, "docket_row", lambda t, now: {
        "symbol": t["symbol"], "family": t["family"], "params": t["params"],
        dcs.TAG_FIELD: t["cell_id"]})
    doc = _build([], {})
    res = dcs.apply(doc, NOW, docket=docket)
    assert res["queued"] == 2
    assert all(t["on_docket"] for t in doc["targets"])
    rows = json.loads(docket.read_text(encoding="utf-8"))
    assert rows[0] == {"symbol": "EURUSD", "family": "f"}
    assert len(rows) == 3
    doc2 = _build([], {})
    res2 = dcs.apply(doc2, NOW, docket=docket)
    assert res2["queued"] == 0 and res2["already_on_docket"] == 2
    assert len(json.loads(docket.read_text(encoding="utf-8"))) == 3


def test_apply_refuses_an_unreadable_docket(tmp_path: Path) -> None:
    doc = _build([], {})
    res = dcs.apply(doc, NOW, docket=tmp_path)            # a directory cannot be read as bytes
    assert res["queued"] == 0 and "refused" in res


def test_docket_row_carries_the_gate1_mechanism_and_tag() -> None:
    target = {"symbol": "XAUUSD", "family": dcs.BREAKOUT, "window": "london_am",
              "params": dict(WINDOWS["london_am"]), "cell_id": "cid", "names": ["gold_london_am"]}
    row = dcs.docket_row(target, NOW)
    assert row[dcs.TAG_FIELD] == "cid"
    assert row["mechanism_status"] == "NAMED"
    assert row["params"] == WINDOWS["london_am"]
    assert row["source"] == dcs.SOURCE


def test_the_leg_is_wired_hourly() -> None:
    import hourly_cycle as hc
    assert "dormant_clock_sweep" in hc.CORE_LEGS
    src = (DESK / "research" / "hourly_cycle.py").read_text(encoding="utf-8")
    assert '"dormant_clock_sweep", "research/dormant_clock_sweep.py"' in src
