"""Patent filings per sector: keyed routes fail closed, counts land whole, the series is PIT."""
from __future__ import annotations

import inspect
import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import hourly_cycle  # noqa: E402
import patent_filings as pf  # noqa: E402

NOW = datetime(2026, 11, 11, 12, tzinfo=UTC)


class _Open:
    consulted: dict = {}  # noqa: RUF012
    ua = "quant-research/1.0 (test)"

    def refusal(self, url):
        return None


def _paths(tmp_path, monkeypatch):
    for name, sub in (("COUNTS", "counts.json"), ("MINTED", "minted.json"),
                      ("REPORT", "r.json")):
        monkeypatch.setattr(pf, name, tmp_path / sub)
    monkeypatch.setattr(pf, "SERIES_DIR", tmp_path / "series")


def test_no_key_is_needs_credential_on_every_route(tmp_path, monkeypatch) -> None:
    _paths(tmp_path, monkeypatch)
    calls: list[str] = []
    doc = pf.run(now=NOW, http=lambda *a: calls.append(a[1]) or (200, b""), gate=_Open(),
                 env={}, secrets=tmp_path, dry_run=True)
    assert calls == []
    assert {v["status"] for v in doc["routes"].values()} == {"NEEDS_CREDENTIAL"}
    assert doc["status"] == "UNMEASURED"


def test_epo_counts_a_whole_week_and_reads_total_result_count(tmp_path, monkeypatch) -> None:
    _paths(tmp_path, monkeypatch)
    monkeypatch.setattr(pf, "MAX_REQUESTS", 1 + len(pf.SECTORS))     # exactly one week
    seen: list[str] = []

    def http(method, url, headers, body):
        if url == pf.EPO_AUTH:
            assert headers["Authorization"].startswith("Basic ")
            return 200, json.dumps({"access_token": "t"}).encode()
        seen.append(url)
        assert headers["Authorization"] == "Bearer t"
        n = 1000 if "cpc" not in url else 40
        return 200, f'<ops:biblio-search total-result-count="{n}">'.encode()
    doc = pf.run(now=NOW, http=http, gate=_Open(),
                 env={"EPO_OPS_KEY": "k", "EPO_OPS_SECRET": "s"}, secrets=tmp_path,
                 dry_run=True)
    r = doc["routes"]["epo_ops"]
    assert r["weeks_added"] == ["2026-10-26"] and r["requests"] == len(seen)
    held = json.loads((tmp_path / "counts.json").read_text("utf-8"))["epo_ops"]["2026-10-26"]
    assert held["_total"] == 1000 and held["compute_semis"] == 40
    assert "keyk" not in (tmp_path / "r.json").read_text("utf-8")
    assert doc["routes"]["uspto_odp"]["status"] == "NEEDS_CREDENTIAL"


def test_an_unrecognised_body_stores_nothing_for_the_week(tmp_path, monkeypatch) -> None:
    _paths(tmp_path, monkeypatch)
    doc = pf.run(now=NOW, http=lambda *a: (200, b'{"nope": 1}'), gate=_Open(),
                 env={"USPTO_API_KEY": "k"}, secrets=tmp_path, dry_run=True)
    r = doc["routes"]["uspto_odp"]
    assert r["status"] == "FAILED" and r["weeks_added"] == []
    assert r["errors"] == {"SHAPE_UNRECOGNISED": 1}


def test_robots_refusal_stops_the_route() -> None:
    class Shut(_Open):
        def refusal(self, url):
            return "robots.txt disallows this path for our agent"
    route = pf.UsptoRoute({"key": "k"}, lambda *a: (_ for _ in ()).throw(AssertionError))
    rep = pf.fetch_route(route, {}, NOW, Shut(), max_requests=99, deadline=1e18)
    assert rep["requests"] == 0 and "REFUSED" in rep["stopped"]


def test_the_cql_is_a_publication_week() -> None:
    q = pf.epo_query(date(2026, 10, 26), ("H01M", "B60L"))
    assert q == 'pd within "20261026 20261101" and (cpc=H01M or cpc=B60L)'


def test_series_is_available_after_the_week_and_mints_once(tmp_path, monkeypatch) -> None:
    import pandas as pd
    weeks = {}
    for i in range(120):
        w = (pd.Timestamp("2024-01-01") + pd.Timedelta(days=7 * i)).date().isoformat()
        row = {"_total": 1000 + i, "retrieved": "2026-11-11T00:00:00+00:00"}
        row.update(dict.fromkeys(pf.SECTORS, 10 + i % 7))
        weeks[w] = row
    df = pf.series_frame(weeks)
    assert (df["available_time"] > (df["week_start"] + pd.Timedelta(days=7)).dt.tz_localize(UTC)
            ).all()
    assert df["backfilled"].iloc[0] and df["compute_semis_share13"].notna().sum() == 108
    assert df["compute_semis_yoy13"].notna().sum() == 56
    cells = pf.grid({"epo_ops": df})
    syms = {c["symbol"] for c in cells}
    assert syms <= {s for v in pf.SECTORS.values() for s in v[1]}
    import proposer_common as pc
    monkeypatch.setattr(pc, "donate", lambda source, candidates, tests_run: tmp_path / "c")
    monkeypatch.setattr(pc, "donation_counts", lambda: {"donated": 1})
    st = tmp_path / "m.json"
    assert pf.mint(cells, dry_run=False, state_path=st)["new"] == len(cells)
    assert pf.mint(cells, dry_run=False, state_path=st)["new"] == 0


def test_the_leg_is_wired() -> None:
    src = inspect.getsource(hourly_cycle.main)
    assert '_costed("patent_filings"' in src and '"patent_filings": pat' in src
    assert hourly_cycle.department_of("patent_filings") == "intel"
