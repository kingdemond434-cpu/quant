"""macro_desk READS PRIMARY PUBLISHERS ONLY: no FRED/ALFRED/Yahoo route, keys by name, fail closed.

FRED, ALFRED and every stlouisfed.org host are refused for automated use (ruling 2026-11-13), as
are Yahoo, Cboe and ICE. These pin that no macro route can reach them, that every id the desk
used to ask FRED for is either sourced from its primary publisher or BLOCKED_ON_TERMS with a
missed_growth line, that the BLS key is read by NAME and never lands in an artifact or a cache,
and that terms, robots and a 401/403/429/451 each stop a fetch before or after one request.
No network.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.error
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

DESK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESK / "research"))
sys.path.insert(0, str(DESK))

import macro_desk  # noqa: E402
import macro_sources as ms  # noqa: E402

NOW = datetime(2026, 11, 17, 12, tzinfo=UTC)
KEY = "BLSKEY-TEST-0123456789"
REFUSED = re.compile(r"https?://[^\s\"']*(stlouisfed|yahoo|cboe|theice)", re.I)
#: Every id macro_desk asked FRED for on LIVE before this change.
FORMER_FRED_IDS = {"PAYEMS", "UNRATE", "INDPRO", "UMCSENT", "CPIAUCSL", "CPILFESL", "T10YIE",
                   "T5YIE", "DFEDTARU", "DFF", "SOFR", "DGS2", "DGS10", "T10Y2Y", "RRPONTSYD",
                   "WALCL", "BAMLH0A0HYM2", "VIXCLS", "DCOILWTICO", "DTWEXBGS",
                   "CP0000EZ19M086NEST", "JPNCPIALLMINMEI"}


@pytest.fixture(autouse=True)
def _isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ms, "CACHE", tmp_path / "macro_sources")
    monkeypatch.setattr(ms, "HALT_F", tmp_path / "macro_sources" / "halt.json")


def _allow(_url: str) -> tuple[bool, str]:
    return True, "robots.txt consulted: allowed"


def _bls_body(codes: list[str], last_year: int = 2026, last_month: int = 10) -> bytes:
    series = []
    for code in codes:
        data = []
        y, m = last_year, last_month
        for i in range(180):
            data.append({"year": str(y), "period": f"M{m:02d}", "value": str(100.0 + i)})
            m -= 1
            if m == 0:
                y, m = y - 1, 12
        series.append({"seriesID": code, "data": data})
    return json.dumps({"status": "REQUEST_SUCCEEDED", "Results": {"series": series}}).encode()


def _ecb_body() -> bytes:
    lines = ["KEY,TIME_PERIOD,OBS_VALUE"]
    for i in range(160):
        y, m = 2013 + (i + 9) // 12, (i + 9) % 12 + 1
        lines.append(f"ICP.M.U2.N.000000.4.INX,{y}-{m:02d},{100 + i * 0.2:.2f}")
    return "\n".join(lines).encode()


class _Getter:
    def __init__(self, answers: dict[str, Any]) -> None:
        self.answers, self.calls = answers, []

    def __call__(self, req: Any) -> bytes:
        self.calls.append(req)
        for host, ans in self.answers.items():
            if host in req.url:
                if isinstance(ans, Exception):
                    raise ans
                return ans
        raise OSError(f"unexpected url {req.url}")


# ------------------------------------------------------------------------- the route map ----
def test_no_macro_route_reaches_a_refused_host() -> None:
    for mod in ("macro_desk.py", "macro_sources.py"):
        src = (DESK / "research" / mod).read_text("utf-8")
        assert not REFUSED.search(src), f"{mod} still names a refused URL"
        code = src.split('"""', 2)[-1]          # past the module docstring
        assert "fredgraph" not in code and "import free_data" not in code
    for spec in ms.SOURCED.values():
        assert not REFUSED.search(spec.get("url", ""))


def test_every_former_fred_id_is_sourced_or_blocked_with_missed_growth() -> None:
    assert set(ms.SOURCED).isdisjoint(ms.BLOCKED)
    for sid in FORMER_FRED_IDS:
        assert sid in ms.SOURCED or sid in ms.BLOCKED, sid
    for sid, b in {**ms.BLOCKED, **ms.BLOCKED_ROUTES}.items():
        assert b["missed_growth"].startswith("missed_growth:"), sid
        assert len(b["why"]) > 30, sid
    declared = set(macro_desk.GROWTH + macro_desk.INFLATION + macro_desk.POLICY + macro_desk.RISK
                   + macro_desk.COMMOD + macro_desk.DOLLAR + macro_desk.DIFF_INPUTS)
    assert declared <= set(ms.SOURCED) | set(ms.BLOCKED)


def test_keyless_routes_are_permitted_by_terms_evidence_on_file() -> None:
    for route in ("eia_xls", "ecb_sdmx"):
        ok, why = ms.terms_verdict(route, ms._route_url(route))
        assert ok, (route, why)
    ok, why = ms.terms_verdict("bls", ms._route_url("bls"))
    assert ok and "public domain" in why


def test_the_treasury_route_would_be_held_on_terms() -> None:
    from libs.research.equivalence_ontology import HELD, terms_verdict
    assert terms_verdict("https://home.treasury.gov/resource-center/x.csv") == HELD
    assert terms_verdict("https://markets.newyorkfed.org/api/rates/all/latest.json") == HELD
    assert terms_verdict("https://fred.stlouisfed.org/graph/fredgraph.csv") == HELD


# ------------------------------------------------------------------------------ fetching ----
def _answers() -> dict[str, Any]:
    return {"api.bls.gov": _bls_body([s["native"] for s in ms.SOURCED.values()
                                      if s["route"] == "bls"]),
            "data-api.ecb.europa.eu": _ecb_body(),
            "www.eia.gov": OSError("eia offline in this test")}


def test_no_bls_key_is_blocked_auth_and_sends_nothing() -> None:
    get = _Getter(_answers())
    got = ms.collect(NOW, get=get, environ={}, robots=_allow)
    assert got["PAYEMS"].status == "BLOCKED_AUTH" and not got["PAYEMS"].data
    assert "BLS_API_KEY" in got["PAYEMS"].reason
    assert not [c for c in get.calls if "bls.gov" in c.url]


def test_the_key_is_read_by_name_and_never_written(tmp_path: Path,
                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    get = _Getter(_answers())
    got = ms.collect(NOW, get=get, environ={"BLS_API_KEY": KEY}, robots=_allow)
    bls = [c for c in get.calls if "bls.gov" in c.url]
    assert len(bls) == 1 and KEY.encode() in (bls[0].data or b"")
    assert bls[0].secrets == (KEY,)
    assert got["PAYEMS"].status == "MEASURED" and len(got["PAYEMS"].data or {}) == 180
    assert got["CP0000EZ19M086NEST"].data
    assert got["DCOILWTICO"].status == "UNMEASURED" and "eia offline" in got["DCOILWTICO"].reason
    assert got["DGS10"].status == ms.BLOCKED_ON_TERMS and not got["DGS10"].data
    for f in (tmp_path / "macro_sources").glob("*.json"):
        assert KEY not in f.read_text("utf-8")
    monkeypatch.setattr(macro_desk, "STATE_F", tmp_path / "macro_state.json")
    monkeypatch.setattr(macro_desk, "log", lambda msg: None)
    monkeypatch.setattr(macro_desk, "_CYCLE", got)
    macro_desk.build_state(NOW)
    assert KEY not in (tmp_path / "macro_state.json").read_text("utf-8")


def test_a_route_not_due_is_served_from_cache_without_a_request() -> None:
    env = {"BLS_API_KEY": KEY}
    first = _Getter(_answers())
    ms.collect(NOW, get=first, environ=env, robots=_allow)
    again = _Getter(_answers())
    got = ms.collect(NOW + timedelta(hours=1), get=again, environ=env, robots=_allow)
    assert not [c for c in again.calls if "bls.gov" in c.url or "ecb.europa" in c.url]
    assert got["PAYEMS"].data and got["PAYEMS"].reason == "cache"


def test_terms_refused_sends_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ms, "terms_verdict", lambda route, url: (False, "held for the test"))
    get = _Getter(_answers())
    got = ms.collect(NOW, get=get, environ={"BLS_API_KEY": KEY}, robots=_allow)
    assert get.calls == []
    assert got["PAYEMS"].status == ms.BLOCKED_ON_TERMS and not got["PAYEMS"].data


def test_robots_refusal_sends_nothing() -> None:
    get = _Getter(_answers())
    got = ms.collect(NOW, get=get, environ={"BLS_API_KEY": KEY},
                     robots=lambda url: (False, "robots.txt Disallow covers this path"))
    assert get.calls == []
    assert got["CPIAUCSL"].status == ms.UNMEASURED and "robots" in got["CPIAUCSL"].reason


@pytest.mark.parametrize("code", [401, 403, 429, 451])
def test_a_hard_stop_halts_the_host_and_is_not_retried(code: int) -> None:
    err = urllib.error.HTTPError("https://api.bls.gov/x", code, "no", {}, None)  # type: ignore[arg-type]
    get = _Getter({**_answers(), "api.bls.gov": err})
    got = ms.collect(NOW, get=get, environ={"BLS_API_KEY": KEY}, robots=_allow)
    assert got["PAYEMS"].status == "HARD_STOP" and str(code) in got["PAYEMS"].reason
    assert ms.halted("api.bls.gov", NOW + timedelta(hours=1))
    later = _Getter(_answers())
    got = ms.collect(NOW + timedelta(hours=7), get=later, environ={"BLS_API_KEY": KEY},
                     robots=_allow)
    assert not [c for c in later.calls if "bls.gov" in c.url]
    assert got["PAYEMS"].status == "HARD_STOP"
    assert ms.halted("api.bls.gov", NOW + timedelta(hours=25)) is None


def test_the_eia_workbook_parser_reads_dated_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    from libs.data import xls_reader
    cells = {(0, 0): "Back to Contents", (0, 1): "Data 1: Cushing WTI",
             (2, 0): "Date", (2, 1): "price", (3, 0): 45000.0, (3, 1): 71.5,
             (4, 0): 45001.0, (4, 1): 72.0, (5, 0): "note", (5, 1): "x"}
    monkeypatch.setattr(xls_reader, "read_xls",
                        lambda body: [xls_reader.Sheet("Contents", {(0, 0): "x"}),
                                      xls_reader.Sheet("Data 1", cells)])
    out = ms.parse_eia_xls(b"ignored")
    assert out == {"2023-03-15": 71.5, "2023-03-16": 72.0}


def test_routes_report_names_the_blocked_alfred_and_yahoo_routes() -> None:
    rep = ms.routes_report(ms.collect(NOW, get=_Getter(_answers()), environ={}, robots=_allow,
                                      fetch=False))
    for name in ("alfred_vintages", "yahoo_anchors"):
        assert rep[name]["status"] == ms.BLOCKED_ON_TERMS
        assert rep[name]["missed_growth"].startswith("missed_growth:")


def test_pit_backfill_and_anchors_fetch_nothing_refused(tmp_path: Path,
                                                        monkeypatch: pytest.MonkeyPatch) -> None:
    import pandas as pd
    lines: list[str] = []
    monkeypatch.setattr(macro_desk, "log", lines.append)
    macro_desk.pit_backfill()
    assert lines and ms.BLOCKED_ON_TERMS in lines[0]
    anchors_f = tmp_path / "anchors.pkl"
    idx = pd.to_datetime(["2026-11-01", "2026-11-02"])
    pd.DataFrame({"DGS10": [4.1, 4.2], "GC": [2700.0, 2710.0]}, index=idx).to_pickle(anchors_f)
    monkeypatch.setattr(macro_desk, "ANCHORS_F", anchors_f)
    wti = ms.Fetched("DCOILWTICO", data={"2026-11-03": 70.0, "2026-11-04": 71.0},
                     status="MEASURED", route="eia_xls")
    monkeypatch.setattr(macro_desk, "_CYCLE", {"DCOILWTICO": wti})
    macro_desk.anchors()
    df = pd.read_pickle(anchors_f)  # noqa: S301 -- written by this test
    assert df["DGS10"].dropna().tolist() == [4.1, 4.2], "a blocked column keeps its history"
    assert df["DCOILWTICO"].dropna().tolist() == [70.0, 71.0]
