"""FRED/ALFRED are refused on terms (governance/fred-terms-ruling-2026-11-13.md): no door asks.

The HTTP layer is patched to RAISE and to record what it was asked for, at every level a fetcher
here can reach: `urllib.request.OpenerDirector.open` (urlopen and every built opener), requests'
`Session.request` (requests.get and friends), `http.client.HTTPConnection.connect`, and
`socket.socket.connect` as the floor. Each fenced entry point is then driven, and the test
asserts that it returned its no-data shape with a BLOCKED_ON_TERMS (or UNMEASURED) status and
that nothing was asked of any stlouisfed.org host -- and, where the door has no lawful
alternate, that nothing was asked of anyone.

The last test is a repo-wide scan. THE RULE: in every tracked non-test .py file, a line that is
not a pure comment and carries a stlouisfed.org URL (`<scheme>://...stlouisfed.org`) must have,
within six lines either side, one of BLOCKED_ON_TERMS, REFUSED or the ruling's file name. A
comment line can never be requested, and a bare host name ("stlouisfed.org" in a scoring hint)
is not an address; everything else must sit visibly inside a refusal or be marked record-only.
The scan is a tripwire for a NEW door, and the entry-point tests above prove the old ones.
"""
from __future__ import annotations

import http.client
import json
import re
import socket
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
for _p in (str(DESK / "side_channels"), str(DESK), str(DESK / "research"), str(ROOT),
           str(ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

pytest.importorskip("pandas")
requests = pytest.importorskip("requests")

FRED_HOST = re.compile(r"stlouisfed\.org", re.I)


class _Refused(OSError):
    """What the patched HTTP layer raises. An OSError, so callers' own handling still runs."""


@pytest.fixture
def asked(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    seen: list[str] = []

    def _opener_open(self: Any, fullurl: Any, *a: Any, **k: Any) -> Any:
        seen.append(str(getattr(fullurl, "full_url", fullurl)))
        raise _Refused("network is patched off")

    def _session_request(self: Any, method: str, url: str, *a: Any, **k: Any) -> Any:
        seen.append(str(url))
        raise _Refused("network is patched off")

    def _connect(self: Any, *a: Any, **k: Any) -> Any:
        seen.append(f"connect:{getattr(self, 'host', a)}")
        raise _Refused("network is patched off")

    monkeypatch.setattr(urllib.request.OpenerDirector, "open", _opener_open)
    monkeypatch.setattr(requests.sessions.Session, "request", _session_request)
    monkeypatch.setattr(http.client.HTTPConnection, "connect", _connect)
    monkeypatch.setattr(socket.socket, "connect", _connect)
    return seen


def _fred_asked(seen: list[str]) -> list[str]:
    return [u for u in seen if FRED_HOST.search(u)]


# ----------------------------------------------------------------- the shared guard -------
def test_the_two_copies_of_the_refusal_say_the_same_thing() -> None:
    from libs.data import fred_terms as ft
    from research import free_data as fd
    assert fd.FRED_TERMS_STATUS == ft.STATUS == "BLOCKED_ON_TERMS"
    assert fd.FRED_TERMS_REASON == ft.REASON and fd.FRED_TERMS_RULING == ft.RULING
    assert fd.FRED_MISSED_GROWTH == ft.MISSED_GROWTH
    for host in ("https://fred.stlouisfed.org/x", "https://API.stlouisfed.org/fred",
                 "https://alfred.stlouisfed.org/", "https://fredaccount.stlouisfed.org/"):
        assert ft.is_fred_url(host), host
    for host in ("https://notstlouisfed.org/", "https://www.federalreserve.gov/", ""):
        assert not ft.is_fred_url(host), host


def test_off_limits_and_polite_fetch_refuse_every_stlouisfed_host(asked: list[str]) -> None:
    from libs.data import polite_fetch as pf
    from libs.data.off_limits import off_limits
    for url in ("https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10",
                "https://api.stlouisfed.org/fred/series/observations",
                "https://fraser.stlouisfed.org/", "https://alfred.stlouisfed.org/robots.txt"):
        why = off_limits(url)
        assert why and why.startswith("BLOCKED_ON_TERMS") and "fred-terms-ruling" in why
        r = pf.get(url, timeout=1.0, retries=0, leg="fred_fence_test")
        assert r.status is None and r.error == why
    assert asked == []


# ----------------------------------------------------------------- free_data and callers ---
@pytest.fixture
def cold_free_data(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """Every loaded copy of free_data with its cache read switched off, so a refusal is seen."""
    import free_data

    from research import free_data as fd2
    mods = [free_data, fd2]
    for m in mods:
        monkeypatch.setattr(m, "_cache_get", lambda name: None)
        monkeypatch.setattr(m, "_cache_put", lambda name, obj: None)
    return mods


def test_fred_series_builds_no_fred_request(asked: list[str], cold_free_data: list[Any]) -> None:
    fd = cold_free_data[1]
    # VIXCLS has no publisher mirror: nothing at all may be asked.
    assert fd.fred_series("VIXCLS") is None
    assert fd.fred_series("DGS10", vintage="2020-01-31") is None
    assert fd.fred_vintage_series("PAYEMS", ["2020-01-31", "2020-02-28"]) == {}
    assert asked == []
    # DGS10 has a DBnomics mirror of the Fed's own H.15 series: that may be asked, FRED never.
    assert fd.fred_series("DGS10") is None
    assert _fred_asked(asked) == []
    rec = fd.fred_refusal("VIXCLS")
    assert rec["status"] == "BLOCKED_ON_TERMS" and rec["what"] == "VIXCLS"
    assert rec["missed_growth"]["mechanism"] == "fred_terms_refusal"


def test_fred_series_still_serves_what_is_already_on_disk(
        asked: list[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from research import free_data as fd
    monkeypatch.setattr(fd, "CACHE", tmp_path)
    held = {f"2020-01-{d:02d}": float(d) for d in range(1, 31)}
    (tmp_path / "fred_VIXCLS_cur.json").write_text(json.dumps(held), "utf-8")
    assert fd.fred_series("VIXCLS") == held
    assert asked == []


def test_vol_archive_fred_fallback_reads_blocked(asked: list[str],
                                                 cold_free_data: list[Any]) -> None:
    from recorders import vol_archive as va
    src = va.YahooVolSource()
    assert src.fred_status == "UNMEASURED"
    assert src._fred("^VIX") is None
    assert src.fred_status == "BLOCKED_ON_TERMS"
    assert asked == []


def test_ops_redundancy_independent_source_reads_blocked(
        asked: list[str], cold_free_data: list[Any], monkeypatch: pytest.MonkeyPatch) -> None:
    import ops_redundancy as ops
    for m in cold_free_data:
        monkeypatch.setattr(m, "yahoo_daily", lambda ticker: None)
    closes, src = ops._independent_closes("EURUSD")
    assert closes == {} and src == "BLOCKED_ON_TERMS:fred"
    doc = ops.market_data_crosscheck(venue=lambda s: {"2026-01-02": 1.0},
                                     independent=lambda s: ({}, "BLOCKED_ON_TERMS:fred"))
    assert doc["status"] == "UNMEASURED"
    assert all("BLOCKED_ON_TERMS" in v["why"] for v in doc["pairs"].values())
    assert asked == []


def test_macro_desk_series_state_is_unmeasured_with_the_refusal(
        asked: list[str], cold_free_data: list[Any]) -> None:
    import macro_desk
    st = macro_desk.series_state("VIXCLS")
    assert st["ok"] is False and st["status"] == "UNMEASURED"
    assert st["fred"]["status"] == "BLOCKED_ON_TERMS"
    assert asked == []


# ----------------------------------------------------------------- direct fetchers ---------
def test_fetch_fred_refuses_and_writes_its_blocked_state(
        asked: list[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from research import fetch_fred as ff
    with pytest.raises(RuntimeError, match="BLOCKED_ON_TERMS"):
        ff.fetch("DGS10")
    monkeypatch.setattr(ff, "OUT", tmp_path)
    ff.main()
    doc = json.loads((tmp_path / "fred_fetch_state.json").read_text("utf-8"))
    assert doc["status"] == "BLOCKED_ON_TERMS" and doc["missed_growth"]
    assert asked == []


def test_fetch_alfred_has_no_transport_left(asked: list[str], monkeypatch: pytest.MonkeyPatch,
                                            tmp_path: Path) -> None:
    from research import fetch_alfred as fa
    assert not hasattr(fa, "requests")
    monkeypatch.setattr(fa, "REPORTS", tmp_path)
    monkeypatch.setenv("FRED_API_KEY", "dummy-not-a-key")
    assert fa.fetch_vintages("DGS10", "dummy-not-a-key") is None
    assert fa.main(["DGS10"]) == 2
    assert json.loads((tmp_path / "alfred_vintages.json").read_text())["status"] == \
        "BLOCKED_ON_TERMS"
    assert asked == []


def test_sge_premium_fred_fallback_is_refused(asked: list[str]) -> None:
    from research import fetch_sge_premium as sge
    assert sge._fred_csv(sge.USDCNY_FRED, "usdcny") is None
    assert sge.FRED_FALLBACK_REFUSAL["status"] == "BLOCKED_ON_TERMS"
    assert sge.FRED_FALLBACK_REFUSAL["missed_growth"]["mechanism"] == "fred_terms_refusal"
    assert asked == []


def test_world_dataset_hunter_declares_no_fred_door_and_refuses_one(asked: list[str]) -> None:
    from research import world_dataset_hunter as wdh
    assert not [s for s in wdh.direct_sources() if FRED_HOST.search(str(s.get("url")))]
    client = wdh.Client(None, deadline=10 ** 12)
    with pytest.raises(wdh.FetchError) as err:
        client.get("https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10")
    assert err.value.reason == "blocked_on_terms"
    assert client.requests == 0 and client.failures["blocked_on_terms"] == 1
    assert asked == []


def test_world_crawler_fetch_refuses_every_fred_page(asked: list[str]) -> None:
    import world_crawler as wc
    assert not [u for u in wc.SEEDS if FRED_HOST.search(u)]
    for url in ("https://fred.stlouisfed.org/categories", "https://alfred.stlouisfed.org/"):
        raw, why = wc.fetch(url)
        assert raw is None and why.startswith("BLOCKED_ON_TERMS")
    assert asked == []


def test_source_route_probe_never_touches_fred(asked: list[str]) -> None:
    import check_source_routes as csr
    fred = [r for r in csr.ROUTES if FRED_HOST.search(r["url"])]
    assert len(fred) == 3 and all(r["terms"] == "REFUSED" for r in fred)
    for route in [*fred, {"name": "unflagged", "url": "https://fred.stlouisfed.org/x",
                          "expect": "csv"}]:
        out = csr.probe(route)
        assert out["status"] == "BLOCKED_ON_TERMS" and out["missed_growth"]
    assert asked == []


def test_collect_fred_macro_writes_blocked_and_requests_nothing(
        asked: list[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import collect_fred_macro as cfm

    from libs.data.fred_terms import FredTermsRefused
    monkeypatch.setattr(cfm, "_ARCHIVE", tmp_path / "fred_macro.json")
    monkeypatch.setattr(cfm, "_STATUS", tmp_path / "fred_macro_status.json")
    monkeypatch.setenv("FRED_API_KEY", "dummy-not-a-key")
    cfm.main()
    doc = json.loads((tmp_path / "fred_macro_status.json").read_text("utf-8"))
    assert doc["status"] == "BLOCKED_ON_TERMS" and doc["archive_present"] is False
    with pytest.raises(FredTermsRefused):
        cfm._fetch("dummy-not-a-key", "DGS10")
    assert asked == []


def test_data_alternates_fred_route_is_refused_and_logged(
        asked: list[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import data_alternates as da
    monkeypatch.setattr(da, "PROVENANCE", tmp_path / "prov.json")
    with pytest.raises(da.FredTermsRefused):
        da.fred_route("DGS10")
    with pytest.raises(RuntimeError, match="ALL routes failed"):
        da.fetch_macro_series("VIXCLS")          # no mirror mapped: both routes fail
    rows = json.loads((tmp_path / "prov.json").read_text())["feeds"]["macro:VIXCLS"]
    assert rows[0]["route"] == "fred" and rows[0]["why"].startswith("BLOCKED_ON_TERMS")
    assert asked == []


def test_cot_screen_reads_cached_legs_and_refuses_missing_ones(
        asked: list[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import run_cot_screen as cot
    monkeypatch.setattr(cot, "_CACHE", tmp_path)
    with pytest.raises(cot.FredTermsRefused):
        cot._fred("DEXUSEU")
    (tmp_path / "fred_DEXUSEU.csv").write_text("DATE,DEXUSEU\n2020-01-02,1.12\n", "utf-8")
    assert cot._fred("DEXUSEU") == {"2020-01-02": 1.12}
    assert asked == []


def test_fred_macro_screen_reads_only_the_deep_archive(
        asked: list[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import screen_fred_macro_axis as sfa

    from libs.data.fred_terms import FredTermsRefused
    monkeypatch.setattr(sfa, "DEEP", tmp_path / "deep.json")
    with pytest.raises(FredTermsRefused):
        sfa.fred_deep("DGS10")
    (tmp_path / "deep.json").write_text(json.dumps({"series": {"DGS10": [["2020-01-02", 1.9]]}}))
    assert float(sfa.fred_deep("DGS10").iloc[0]) == 1.9
    assert asked == []


# ----------------------------------------------------------------- the repo-wide scan ------
_URL = re.compile(r"[a-z][a-z0-9+.-]*://[^\s\"'<>]*stlouisfed\.org", re.I)
_MARK = re.compile(r"BLOCKED_ON_TERMS|REFUSED|fred-terms-ruling", re.I)
_WINDOW = 6


def _source_files() -> list[str]:
    out = subprocess.run(["git", "ls-files", "*.py"], cwd=ROOT, capture_output=True,
                         text=True, check=True).stdout.split()
    return [p for p in out if "/tests/" not in f"/{p}" and not Path(p).name.startswith("test_")
            and "/_retired/" not in p and Path(p).name != "conftest.py"]


def test_no_live_stlouisfed_url_outside_a_refused_or_record_only_context() -> None:
    files = _source_files()
    assert len(files) > 100, "the scan found almost nothing to scan: it would prove nothing"
    hits: list[str] = []
    for rel in files:
        path = ROOT / rel
        if not path.exists():
            continue
        lines = path.read_text("utf-8", errors="replace").splitlines()
        for i, line in enumerate(lines):
            if line.lstrip().startswith("#") or not _URL.search(line):
                continue
            window = "\n".join(lines[max(0, i - _WINDOW):i + _WINDOW + 1])
            if not _MARK.search(window):
                hits.append(f"{rel}:{i + 1}: {line.strip()[:90]}")
    assert not hits, ("a stlouisfed.org URL outside a refused or record-only context -- refuse "
                      "it before any request (libs.data.fred_terms) or mark it: " + str(hits))
