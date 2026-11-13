"""FRED is terms-refused on every host (governance ruling 2026-11-13): no fetch path sends a
request, and organs keep serving the last held copy."""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

import pytest

from libs.data import terms_refused as T

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT / "desks" / "mt5"), str(ROOT / "desks" / "mt5" / "research"),
           str(ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


@pytest.mark.parametrize("url", [
    "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10",
    "https://alfred.stlouisfed.org/graph/fredgraph.csv?id=PAYEMS&vintage_date=2020-01-01",
    "https://api.stlouisfed.org/fred/series/observations?series_id=DGS10",
    "https://FRED.stlouisfed.org.", "stlouisfed.org/anything",
    "https://fraser.stlouisfed.org/title/1"])          # no exemption without its own terms
def test_every_fred_host_is_refused(url: str) -> None:
    assert T.refused(url) and "governance ruling 2026-11-13" in T.refused(url)
    with pytest.raises(T.TermsRefused):
        T.guard(url)


@pytest.mark.parametrize("url", [
    "https://www.federalreserve.gov/releases/h15/",
    "https://fiscaldata.treasury.gov/", "https://notstlouisfed.org/x"])
def test_other_hosts_pass(url: str) -> None:
    assert T.refused(url) is None


@pytest.fixture
def no_network(monkeypatch):
    def boom(*_a, **_k):
        raise AssertionError("a refused host reached the network")
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    try:
        import requests
        monkeypatch.setattr(requests, "get", boom)
    except ImportError:
        pass


def test_shared_transports_refuse_without_a_request(no_network) -> None:
    from libs.data import free_stack, polite_fetch
    r = polite_fetch.get("https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10",
                         gate=None)
    assert r.error and "FRED" in r.error
    with pytest.raises(free_stack.FetchError) as e:
        free_stack.http_fetch("https://api.stlouisfed.org/fred/series/observations")
    assert e.value.reason == "BLOCKED_TERMS"


def test_free_data_serves_the_held_copy_whatever_its_age(no_network, monkeypatch,
                                                         tmp_path) -> None:
    import free_data as F
    monkeypatch.setattr(F, "CACHE", tmp_path)
    held = {f"2020-01-{d:02d}": float(d) for d in range(1, 32)}
    p = tmp_path / "fred_DGS10_cur.json"
    p.write_text(json.dumps(held), "utf-8")
    import os
    os.utime(p, (1, 1))                                    # decades stale
    monkeypatch.setattr(F, "_fred_alternate", lambda *a: pytest.fail("held copy skipped"))
    monkeypatch.setattr(F, "_primary", lambda *a: None)       # publisher unreachable
    assert F.fred_series("DGS10") == held
    assert F.served_from("DGS10") == "held"


def test_free_data_without_a_held_copy_goes_to_the_publisher_route(no_network, monkeypatch,
                                                                   tmp_path) -> None:
    import free_data as F
    monkeypatch.setattr(F, "CACHE", tmp_path)
    monkeypatch.setattr(F, "_fred_alternate", lambda sid, vintage, key: {"route": sid})
    assert F.fred_series("UNRATE") == {"route": "UNRATE"}
    assert F.served_from("UNRATE") == "dbnomics_publisher_series"


def test_free_data_prefers_the_primary_publisher(monkeypatch, tmp_path) -> None:
    import free_data as F
    monkeypatch.setattr(F, "CACHE", tmp_path)
    held = tmp_path / "fred_DGS2_cur.json"
    held.write_text('{"2020-01-01": 1.0}', "utf-8")
    os.utime(held, (1, 1))              # stale, so the refused branch is reached
    monkeypatch.setattr(F, "_primary", lambda sid, start, key: {"2026-11-12": 3.5})
    assert F.fred_series("DGS2") == {"2026-11-12": 3.5}
    assert F.served_from("DGS2") == "primary_publisher"


def test_us_pack_lists_no_refused_root() -> None:
    from research.countries.us import pack
    roots = [r for sc in pack.SOURCE_CLASSES for r in sc["roots"]]
    assert roots and not [r for r in roots if T.refused(r)]


def test_collector_never_fetches_fred_and_keeps_what_it_holds(no_network, monkeypatch,
                                                               tmp_path, capsys) -> None:
    import collect_fred_macro as C
    archive, long_ = tmp_path / "fred_macro.json", tmp_path / "fred_macro_long.json"
    archive.write_text('{"held": true}', "utf-8")
    monkeypatch.setattr(C, "_ROOT", tmp_path)
    monkeypatch.setattr(C, "_ARCHIVE", archive)
    monkeypatch.setattr(C, "_ARCHIVE_LONG", long_)
    monkeypatch.setattr(C, "_WEB", tmp_path / "web.json")
    C.main()                         # no network at all: no primary route, nothing held
    assert archive.read_text("utf-8") == '{"held": true}' and not long_.exists()
    assert "BLOCKED_TERMS" in capsys.readouterr().out


def test_probes_and_routes_report_blocked_terms(no_network) -> None:
    import check_source_routes as R
    import data_alternates as A
    out = R.probe({"name": "fred_graph_csv",
                   "url": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10"})
    assert out["status"] == "BLOCKED_TERMS"
    with pytest.raises(RuntimeError, match="BLOCKED_TERMS"):
        A.fred_route("DGS10")


def test_futures_state_registry_never_fetches_fred() -> None:
    reg = json.loads((ROOT / "desks" / "mt5" / "research" / "futures_state_sources.json")
                     .read_text("utf-8"))
    fred = [s for s in reg["sources"] if "stlouisfed" in str(s.get("url", ""))
            or s["id"] in ("fred_rates", "fred_vixcls")]
    assert fred and all(s["terms"] == "REFUSED" for s in fred)
