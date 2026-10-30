"""MT5-AxisIngest's FRED axis: every failure mode the box hit, reproduced on fixtures.

Measured on the trading box (desks/mt5/data/axes/fred.json, 2026-09-12, still the published copy
on 2026-10-29): 0 series, 7 failed -- three TimeoutError and four ConnectionResetError from the
fredgraph.csv website host, read with no key. The task exited 0 throughout because the driver
returns 0 when ANY axis lands, so the board read it OK. No network here: every fetch is a fixture.
"""
from __future__ import annotations

import importlib.util
import io
import json
import sys
import urllib.error
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_DESK = _ROOT / "desks" / "mt5"
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import axis_ingest as AI  # noqa: E402
import axis_ingest_all as AIA  # noqa: E402

_spec = importlib.util.spec_from_file_location("process_health_fred_test",
                                               _ROOT / "ops" / "process_health.py")
assert _spec and _spec.loader
PH = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(PH)

KEY = "abcdefghijklmnopqrstuvwxyz123456"   # a fixture, shaped like a FRED key; not a real one


def _api_body(points: list[tuple[str, str]]) -> str:
    return json.dumps({"observations": [{"date": d, "value": v} for d, v in points]})


def _sid(url: str) -> str:
    if "series_id=" in url:
        return url.split("series_id=")[1].split("&")[0]
    return url.split("id=")[1]


class Fetch:
    """A fixture fetcher: per-route behaviour, and a record of every URL asked."""

    def __init__(self, api: Any = None, graph: Any = None) -> None:
        self.api, self.graph, self.calls = api, graph, []

    def __call__(self, url: str) -> str:
        self.calls.append(url)
        beh = self.api if "api.stlouisfed.org" in url else self.graph
        out = beh(_sid(url)) if callable(beh) else beh
        if isinstance(out, BaseException):
            raise out
        if out is None:
            raise AssertionError(f"unexpected fetch {url}")
        return out


GOOD = {
    "DGS10": [("2026-10-26", "4.10"), ("2026-10-27", "4.20"), ("2026-10-28", ".")],
    "DGS2": [("2026-10-26", "3.60"), ("2026-10-27", "3.50")],
    "DFII10": [("2026-10-27", "1.90")],
    "DTWEXBGS": [("2026-10-23", "121.3202")],
}


# ------------------------------------------------------------------ failure modes, as measured
def test_the_box_failure_reproduced_timeout_and_reset_with_no_key_is_a_named_error() -> None:
    """2026-09-12 on the box: fredgraph.csv timed out or reset on every series, no key used."""
    seen: dict[str, int] = {}

    def graph(sid: str) -> BaseException:
        seen[sid] = seen.get(sid, 0) + 1
        return (TimeoutError("The read operation timed out") if sid in ("DGS10", "DTWEXBGS")
                else ConnectionResetError(10054, "An existing connection was forcibly closed"))

    doc = AI.ingest_fred(fetch=Fetch(graph=graph), key=None)
    assert doc["n_series"] == 0 and doc["key_present"] is False
    assert set(doc["failed"]) == set(AI.FRED_SERIES) | set(AI.FRED_DERIVED)
    assert "NEEDS_KEY" in doc["failed"]["DGS10"] and "TIMEOUT" in doc["failed"]["DGS10"]
    assert "RESET" in doc["failed"]["DGS2"]
    assert doc["series_state"]["DGS10"] == "ERROR"
    assert doc["series_state"]["T10Y2Y"] == "EMPTY"           # derived: its legs are absent
    # one polite retry for a transient edge failure, never more
    assert all(n == 2 for n in seen.values())


def test_the_keyed_api_is_read_first_and_the_key_never_reaches_the_document() -> None:
    f = Fetch(api=lambda sid: _api_body(GOOD[sid]))
    doc = AI.ingest_fred(fetch=f, key=KEY)
    assert doc["n_failed"] == 0 and doc["key_present"] is True
    assert all("api.stlouisfed.org" in u for u in f.calls)    # the website host was never asked
    assert all("api_key=" in u for u in f.calls)              # FRED's documented query parameter
    assert set(doc["transport"].values()) == {"api"}
    assert doc["series"]["DGS10"]["n"] == 2                   # "." is a missing print, dropped
    assert KEY not in json.dumps(doc)


def test_the_two_spreads_are_derived_from_public_domain_legs_on_shared_dates() -> None:
    doc = AI.ingest_fred(fetch=Fetch(api=lambda sid: _api_body(GOOD[sid])), key=KEY)
    t10y2y = doc["series"]["T10Y2Y"]
    assert t10y2y["derived_from"] == ["DGS10", "DGS2"]
    assert [(p["d"], p["v"]) for p in t10y2y["points"]] == [("2026-10-26", 0.5),
                                                            ("2026-10-27", 0.7)]
    assert [(p["d"], p["v"]) for p in doc["series"]["T10YIE"]["points"]] == [("2026-10-27", 2.3)]


def test_an_empty_response_is_a_recorded_failure_never_a_missing_row() -> None:
    """THE CODE BUG: the old loop put a series that parsed to nothing in neither dict."""
    f = Fetch(api=lambda sid: _api_body([]) if sid == "DTWEXBGS" else _api_body(GOOD[sid]),
              graph=lambda sid: "DATE,DTWEXBGS\n")
    doc = AI.ingest_fred(fetch=f, key=KEY)
    assert "DTWEXBGS" not in doc["series"]
    assert doc["failed"]["DTWEXBGS"].count("EMPTY") == 2      # api, then the fallback
    assert doc["series_state"]["DTWEXBGS"] == "EMPTY"
    assert doc["n_series"] + doc["n_failed"] == len(AI.FRED_SERIES) + len(AI.FRED_DERIVED)


def test_a_block_page_is_not_parsed_as_an_empty_csv() -> None:
    doc = AI.ingest_fred(fetch=Fetch(graph="<html><body>Access denied</body></html>"), key=None)
    assert "NOT_CSV" in doc["failed"]["DGS10"]


def test_a_429_stops_the_pass_and_is_never_retried_around() -> None:
    def api(sid: str) -> Any:
        if sid == "DGS2":
            return urllib.error.HTTPError("u", 429, "Too Many Requests", None,  # type: ignore[arg-type]
                                          io.BytesIO(b"{}"))
        return _api_body(GOOD[sid])

    f = Fetch(api=api, graph=lambda sid: pytest.fail("the website host must not be tried"))
    doc = AI.ingest_fred(fetch=f, key=KEY)
    assert doc["series_state"]["DGS2"] == "RATE_LIMITED"
    assert doc["series_state"]["DFII10"] == "RATE_LIMITED"    # not asked after the 429
    assert len(f.calls) == 2                                  # DGS10, DGS2 -- then stop


def test_a_refused_key_names_fred_s_reason_and_redacts_the_key() -> None:
    body = json.dumps({"error_code": 400, "error_message":
                       f"Bad Request.  The value for variable api_key is not registered: {KEY}"})

    def api(sid: str) -> Any:
        return urllib.error.HTTPError("u", 400, "Bad Request", None,  # type: ignore[arg-type]
                                      io.BytesIO(body.encode()))

    doc = AI.ingest_fred(fetch=Fetch(api=api, graph=TimeoutError("timed out")), key=KEY)
    reason = doc["failed"]["DGS10"]
    assert "HTTP_400" in reason and "not registered" in reason
    assert KEY not in json.dumps(doc)


def test_copyrighted_third_party_series_are_ideas_only_and_never_requested() -> None:
    f = Fetch(api=lambda sid: _api_body(GOOD[sid]))
    doc = AI.ingest_fred(fetch=f, key=KEY)
    for sid in ("VIXCLS", "BAMLH0A0HYM2"):
        assert sid not in AI.FRED_SERIES and sid not in doc["series"]
        assert not any(sid in u for u in f.calls)
        row = doc["ideas_only"][sid]
        assert row["missed_growth"]["delta_elogw"] == "UNMEASURED" and row["missed_growth"]["cause"]
        assert "Copyright" in row["terms"] or "copyright" in row["terms"].lower()


def test_the_key_is_resolved_from_the_repo_root_not_the_working_directory(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    kf = tmp_path / "fred.json"
    kf.write_text(json.dumps({"key": KEY}), "utf-8")
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    monkeypatch.setattr(AI, "FRED_KEY_FILE", kf)
    monkeypatch.chdir(tmp_path.parent)
    assert AI._fred_key() == KEY
    monkeypatch.setattr(AI, "FRED_KEY_FILE", tmp_path / "absent.json")
    assert AI._fred_key() is None


# ------------------------------------------------------------------ the RED check (Rule 23)
def _axes(fred_ok: bool) -> dict[str, Any]:
    state = dict.fromkeys(AI.FRED_SERIES, "OK" if fred_ok else "ERROR")
    return {
        "cot": {"axis": "cot", "state": "OK", "n": 4060},
        "fred": {"axis": "fred", "state": "OK" if fred_ok else "EMPTY",
                 "n": 6 if fred_ok else 0, "series_state": state,
                 "failed": {} if fred_ok else dict.fromkeys(state, "fredgraph: TIMEOUT"),
                 "key_present": False},
        "gnn_forecast": {"axis": "gnn_forecast", "state": "EMPTY", "n": 0},
    }


def test_red_only_after_more_than_two_consecutive_empty_passes_and_green_on_recovery() -> None:
    t0 = datetime(2026, 10, 29, tzinfo=UTC)
    doc: dict[str, Any] | None = None
    verdicts = []
    for i in range(3):
        doc = AIA.update_liveness(doc, _axes(False), t0 + timedelta(hours=i))
        verdicts.append(doc["verdict"])
    assert verdicts == ["GREEN", "GREEN", "RED"]
    assert doc is not None and "fred" in doc["red"] and "fred/DGS10" in doc["red"]
    assert doc["dependencies"]["fred/DGS10"]["empty_streak"] == 3
    assert doc["dependencies"]["fred/DGS10"]["first_empty_at"] == t0.isoformat()
    assert "TIMEOUT" in doc["dependencies"]["fred/DGS10"]["last_reason"]
    assert "cot" not in doc["red"]
    assert not any(k.startswith("gnn_forecast") for k in doc["dependencies"])  # internal axis
    doc = AIA.update_liveness(doc, _axes(True), t0 + timedelta(hours=3))
    assert doc["verdict"] == "GREEN" and doc["dependencies"]["fred"]["empty_streak"] == 0


def test_a_source_that_raised_still_advances_its_series_streaks() -> None:
    t0 = datetime(2026, 10, 29, tzinfo=UTC)
    doc = AIA.update_liveness(None, _axes(False), t0)
    boom = {"fred": {"axis": "fred", "state": "UNMEASURED", "error": "ImportError: x"}}
    doc = AIA.update_liveness(doc, boom, t0 + timedelta(hours=1))
    doc = AIA.update_liveness(doc, boom, t0 + timedelta(hours=2))
    assert doc["verdict"] == "RED" and doc["dependencies"]["fred/DGS2"]["empty_streak"] == 3


def test_no_external_source_read_is_unmeasured_never_green() -> None:
    doc = AIA.update_liveness(None, {}, datetime(2026, 10, 29, tzinfo=UTC))
    assert doc["verdict"] == "UNMEASURED"


def test_the_driver_never_overwrites_data_with_an_empty_pass_and_writes_the_red_check(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out = tmp_path / "axes"
    out.mkdir()
    (out / "fred.json").write_text(json.dumps({"n_series": 4, "series": {"DGS10": {}}}), "utf-8")
    monkeypatch.setattr(AIA, "OUT_DIR", out)
    monkeypatch.setattr(AIA, "REPORT", tmp_path / "AXIS_INGEST.json")
    monkeypatch.setattr(AIA, "LIVENESS", tmp_path / "DEPENDENCY_LIVENESS.json")
    empty = AI.ingest_fred(fetch=Fetch(graph=TimeoutError("timed out")), key=None)
    monkeypatch.setattr(AI, "INGESTERS", {"fred": lambda: empty,
                                          "cot": lambda: {"n_rows": 3, "symbols": ["XAUUSD"]}})
    for _ in range(3):
        assert AIA.main(["--apply"]) == 0
    assert json.loads((out / "fred.json").read_text("utf-8"))["n_series"] == 4
    report = json.loads((tmp_path / "AXIS_INGEST.json").read_text("utf-8"))
    assert report["axes"]["fred"]["kept_previous"] is True
    assert report["axes"]["fred"]["state"] == "EMPTY"
    live = json.loads((tmp_path / "DEPENDENCY_LIVENESS.json").read_text("utf-8"))
    assert live["verdict"] == "RED" and "fred" in live["red"]
    assert live["sources"]["fred"]["key_present"] is False


def test_process_health_raises_attention_on_a_red_dependency(tmp_path: Path) -> None:
    p = tmp_path / "DEPENDENCY_LIVENESS.json"
    assert PH.dependency_liveness(p)["verdict"] == "UNMEASURED"       # absent is not GREEN
    t0 = datetime(2026, 10, 29, tzinfo=UTC)
    doc = None
    for i in range(3):
        doc = AIA.update_liveness(doc, _axes(False), t0 + timedelta(hours=i))
    p.write_text(json.dumps(doc), "utf-8")
    summary = PH.dependency_liveness(p)
    assert summary["verdict"] == "RED"
    assert {r["dependency"] for r in summary["red"]} >= {"fred", "fred/DGS10"}
    assert "TIMEOUT" in summary["not_delivering"]["fred/DGS10"]["reason"]


def test_the_red_check_is_contracted_on_the_ingest_clock() -> None:
    src = (_ROOT / "ops" / "organ_contract.py").read_text("utf-8")
    assert '"MT5-AxisIngest (dependency liveness)"' in src
    assert "DEPENDENCY_LIVENESS.json" in src
