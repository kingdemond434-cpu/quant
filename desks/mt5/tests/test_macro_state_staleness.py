"""A STALE SERIES IS NOT OK, ONE BAD SERIES NEVER TAKES THE FILE, AND A STALE FILE IS UNMEASURED.

Measured 2026-10-21: PAYEMS, UNRATE, CPIAUCSL and CPILFESL read ok:true with last_date
2025-01-01 (a mirror ~20 months stale), GROWTH_STATE / INFLATION_STATE were built on them, and
macro_intelligence read the six-week-old file as MEASURED. The file the desk publishes now
declares its cadence, and `read_state` judges it by its own `updated`. No network here.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESK / "research"))
sys.path.insert(0, str(DESK))

import macro_desk  # noqa: E402
import macro_intelligence as mi  # noqa: E402
import macro_sources as ms  # noqa: E402

NOW = datetime(2026, 11, 17, 12, tzinfo=UTC)


def _monthly(last: str, n: int = 180, growth: float = 0.0) -> dict[str, float]:
    idx = pd.date_range(end=last, periods=n, freq="MS")
    return {d.date().isoformat(): 100.0 * (1 + growth) ** (i / 12) + (0 if growth else i)
            for i, d in enumerate(idx)}


def _daily(last: str, n: int = 400) -> dict[str, float]:
    idx = pd.date_range(end=last, periods=n, freq="D")
    return {d.date().isoformat(): 1.0 + (i % 7) for i, d in enumerate(idx)}


def _f(sid: str, data: dict[str, float] | None) -> ms.Fetched:
    return ms.Fetched(sid, data=data, status="MEASURED" if data else "UNMEASURED",
                      reason="test", route="test")


def _cycle(table: dict[str, dict[str, float] | None]) -> dict[str, ms.Fetched]:
    out = {sid: _f(sid, None) for sid in list(ms.SOURCED) + list(ms.BLOCKED)}
    for sid, b in ms.BLOCKED.items():
        out[sid] = ms.Fetched(sid, status=ms.BLOCKED_ON_TERMS, reason=b["why"], route="none")
    out.update({sid: _f(sid, d) for sid, d in table.items()})
    return out


@pytest.fixture
def state_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    out = tmp_path / "macro_state.json"
    monkeypatch.setattr(macro_desk, "STATE_F", out)
    monkeypatch.setattr(macro_desk, "log", lambda msg: None)
    return out


def test_a_frozen_print_is_stale() -> None:
    e = macro_desk.series_state("PAYEMS", NOW, _f("PAYEMS", _monthly("2025-01-01")))
    assert e["ok"] is False and e["stale"] is True
    assert e["last_date"] == "2025-01-01" and e["frequency"] == "monthly"
    assert "2025-01-01" in e["reason"] and f"{e['age_days']} days" in e["reason"]
    assert "z" not in e and "mom" not in e, "nothing may be built on a frozen print"


@pytest.mark.parametrize("sid,data,ok", [
    ("DCOILWTICO", _daily("2026-11-13"), True),     # a weekend + a day: fresh
    ("DCOILWTICO", _daily("2026-11-01"), False),    # 16 days > 10
    ("CPIAUCSL", _monthly("2026-10-31"), True),     # October CPI, month-end dated
    ("CPIAUCSL", _monthly("2026-08-31"), False),    # 78 days > 75
])
def test_ceilings_follow_the_declared_frequency(sid: str, data: dict[str, float],
                                                ok: bool) -> None:
    assert macro_desk.series_state(sid, NOW, _f(sid, data))["ok"] is ok


def test_an_undeclared_id_infers_its_frequency_from_spacing() -> None:
    q = pd.DatetimeIndex(pd.date_range(end="2026-07-01", periods=40, freq="QS"))
    assert macro_desk._frequency("SOME_QUARTERLY", q) == "quarterly"
    d = pd.DatetimeIndex(pd.date_range(end="2026-10-20", periods=40, freq="B"))
    assert macro_desk._frequency("SOME_DAILY", d) == "daily"


def test_a_blocked_series_carries_its_reason() -> None:
    got = _cycle({})
    e = macro_desk.series_state("T5YIE", NOW, got["T5YIE"])
    assert e["ok"] is False and e["reason"].startswith(ms.BLOCKED_ON_TERMS)
    assert e["source"]["status"] == ms.BLOCKED_ON_TERMS


@pytest.mark.parametrize("freq,periods,step", [
    ("monthly", 13, "MS"), ("quarterly", 5, "QS"), ("weekly", 53, "W"), ("daily", 260, "D")])
def test_the_one_year_change_looks_back_one_year_at_each_frequency(freq: str, periods: int,
                                                                   step: str) -> None:
    idx = pd.date_range(end="2026-10-01", periods=periods, freq=step)
    s = pd.Series([100.0] * (periods - 1) + [110.0], index=idx)
    assert macro_desk._mom(s, yoy=True, freq=freq) == pytest.approx(0.10)
    assert macro_desk._mom(s.iloc[1:], yoy=True, freq=freq) is None


def test_the_file_is_built_from_ok_series_only(state_file: Path,
                                               monkeypatch: pytest.MonkeyPatch) -> None:
    got = _cycle({"PAYEMS": _monthly("2025-01-01"), "UNRATE": _monthly("2026-10-31"),
                  "CPIAUCSL": _monthly("2026-10-31", growth=0.03),
                  "CPILFESL": _monthly("2026-10-31"),
                  "CP0000EZ19M086NEST": _monthly("2026-10-31", growth=0.02),
                  "DCOILWTICO": _daily("2026-11-16")})
    monkeypatch.setattr(macro_desk, "_CYCLE", got)
    macro_desk.build_state(NOW)
    doc = json.loads(state_file.read_text("utf-8"))
    assert doc["updated"] == NOW.isoformat() and doc["status"] == "MEASURED"
    assert doc["cadence"]["interval_s"] == 3600 and doc["cadence"]["max_age_h"] == 6.0
    s = doc["series"]
    assert s["PAYEMS"]["stale"] is True and s["UNRATE"]["ok"] is True
    assert s["DGS10"]["ok"] is False and s["DGS10"]["source"]["status"] == ms.BLOCKED_ON_TERMS
    assert doc["states"]["WTI"] is not None and doc["states"]["POLICY_RATE"] is None
    assert doc["differentials"]["US_MINUS_EU_CPI_YOY"] == pytest.approx(0.01, abs=1e-3)
    assert "US_MINUS_JP_CPI_YOY" not in doc["differentials"]
    cov = doc["coverage"]
    assert cov["stale"] == ["PAYEMS"] and "DGS10" in cov["blocked_on_terms"]
    assert set(doc["blocked"]) == set(ms.BLOCKED)
    assert all(b["missed_growth"].startswith("missed_growth:") for b in doc["blocked"].values())
    assert doc["sources"]["alfred_vintages"]["status"] == ms.BLOCKED_ON_TERMS
    assert "GOLDAMGBD228NLBM" in doc["dropped"] and "RETAILSMxSA" in doc["dropped"]
    assert not state_file.with_suffix(".json.tmp").exists()


def test_nothing_measured_is_a_verdict_not_a_quiet_file(state_file: Path,
                                                        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(macro_desk, "_CYCLE", _cycle({}))
    macro_desk.build_state(NOW)
    doc = json.loads(state_file.read_text("utf-8"))
    assert doc["status"] == ms.UNMEASURED and doc["reason"]
    r = macro_desk.read_state(state_file, NOW)
    assert r["status"] == ms.UNMEASURED and "doc" not in r


def test_one_failing_series_never_takes_the_file(state_file: Path,
                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_a: object, **_k: object) -> dict:
        raise RuntimeError("boom")
    got = _cycle({"UNRATE": _monthly("2026-10-31")})
    monkeypatch.setattr(macro_desk, "_CYCLE", got)
    real = macro_desk.series_state

    def flaky(sid: str, now: datetime | None = None, g: ms.Fetched | None = None) -> dict:
        return boom() if sid == "CPILFESL" else real(sid, now, g)
    monkeypatch.setattr(macro_desk, "series_state", flaky)
    macro_desk.build_state(NOW)
    doc = json.loads(state_file.read_text("utf-8"))
    assert doc["series"]["CPILFESL"]["ok"] is False and "boom" in doc["series"]["CPILFESL"]["error"]
    assert doc["series"]["UNRATE"]["ok"] is True


# --------------------------------------------------------------------------- read_state ----
def _write(p: Path, doc: object) -> Path:
    p.write_text(json.dumps(doc), "utf-8")
    return p


def test_read_state_absent_is_unmeasured(tmp_path: Path) -> None:
    r = macro_desk.read_state(tmp_path / "nope.json", NOW)
    assert r["status"] == ms.UNMEASURED and "absent" in r["reason"]


@pytest.mark.parametrize("doc", [{"series": {}}, {"updated": "yesterday"}, [1, 2]])
def test_read_state_without_a_stamp_is_unmeasured(tmp_path: Path, doc: object) -> None:
    assert macro_desk.read_state(_write(tmp_path / "m.json", doc), NOW)["status"] == "UNMEASURED"


def test_read_state_judges_by_age_not_mtime(tmp_path: Path) -> None:
    stale = _write(tmp_path / "m.json", {"updated": "2026-09-12T11:26:35+00:00",
                                         "status": "MEASURED"})
    r = macro_desk.read_state(stale, NOW)
    assert r["status"] == ms.UNMEASURED and "stale" in r["reason"]
    fresh = _write(tmp_path / "f.json", {"updated": (NOW - timedelta(hours=2)).isoformat(),
                                         "status": "MEASURED", "cadence": {"max_age_h": 6}})
    r = macro_desk.read_state(fresh, NOW)
    assert r["status"] == "MEASURED" and r["age_h"] == pytest.approx(2.0) and r["doc"]
    late = _write(tmp_path / "l.json", {"updated": (NOW - timedelta(hours=7)).isoformat()})
    assert macro_desk.read_state(late, NOW)["status"] == ms.UNMEASURED


def test_read_state_refuses_a_future_stamp(tmp_path: Path) -> None:
    p = _write(tmp_path / "m.json", {"updated": (NOW + timedelta(hours=3)).isoformat()})
    assert macro_desk.read_state(p, NOW)["status"] == ms.UNMEASURED


# ------------------------------------------------------------------ macro_intelligence ----
def _mi_state(tmp_path: Path, updated: str | None) -> Path:
    doc: dict = {"series": {}, "states": {"RISK_STATE": 1.5}}
    if updated is not None:
        doc["updated"] = updated
    return _write(tmp_path / "macro_state.json", doc)


def test_the_reader_ceiling_is_the_declared_one() -> None:
    assert mi.MAX_AGE_H["macro_state"] == macro_desk.MAX_AGE_H


def test_a_stale_macro_state_is_unmeasured_to_macro_intelligence(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    p = _mi_state(tmp_path, "2026-09-12T11:26:35+00:00")
    monkeypatch.setattr(mi, "INPUTS", {"macro_state": p})
    doc = mi.build(NOW)
    entry = doc["inputs"]["macro_state"]
    assert entry["status"] == "UNMEASURED" and "stale" in entry["reason"]
    assert doc["status"] == "UNMEASURED" and doc["consumed_units"] == []


def test_a_fresh_macro_state_is_measured_to_macro_intelligence(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    p = _mi_state(tmp_path, (NOW - timedelta(hours=1)).isoformat())
    monkeypatch.setattr(mi, "INPUTS", {"macro_state": p})
    doc = mi.build(NOW)
    assert doc["inputs"]["macro_state"]["status"] == "MEASURED"
    assert doc["inputs"]["macro_state"]["age_h"] == pytest.approx(1.0)


def test_an_unstamped_macro_state_is_unmeasured_to_macro_intelligence(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(mi, "INPUTS", {"macro_state": _mi_state(tmp_path, None)})
    entry = mi.build(NOW)["inputs"]["macro_state"]
    assert entry["status"] == "UNMEASURED" and "no readable timestamp" in entry["reason"]


def test_the_cycle_reads_each_route_once(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(ms, "collect", lambda now=None: calls.append("collect") or {})
    macro_desk.begin_cycle()
    macro_desk._sources()
    macro_desk._sources()
    assert calls == ["collect"]
    macro_desk.begin_cycle()
    macro_desk._sources()
    assert calls == ["collect", "collect"]
