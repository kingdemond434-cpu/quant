"""Owner-attested permissions (2026-11-17): each source fetches only while its flag is true, the
reader fails closed, provenance rides on every row, robots and hard stops still win, and no row
can unlock a hard-refused host. The HTTP layer is a fixture transport throughout: no network."""
from __future__ import annotations

import email.message
import importlib.util
import io
import json
import subprocess
import sys
import types
import urllib.request
import urllib.response
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from libs.data import owner_permissions as op

REPO = Path(__file__).resolve().parents[2]
REAL = REPO / "desks" / "mt5" / "data" / "owner_permissions.json"
SEVEN = ("hkex_stock_connect", "boj_etf_purchases", "korea_nps_flows", "boj_jgb_operations",
         "snb_sight_deposits", "chicagofed_nfci", "exchange_options_gamma")
CHAIN = json.dumps({"timestamp": "2026-11-16 16:15:00", "data": {
    "current_price": 6000.0, "options": [
        {"option": "SPX261120C06000000", "gamma": 0.002, "open_interest": 1000},
        {"option": "SPX261120P05900000", "gamma": 0.001, "open_interest": 500}]}}).encode()


@pytest.fixture(autouse=True)
def _isolated_holds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Every test holds into its own file: no test writes the box's real hard-stop state."""
    p = tmp_path / "holds" / "hard_stops.json"
    monkeypatch.setattr(op, "HOLDS", p)
    return p


def _organ() -> types.ModuleType:
    p = REPO / "desks" / "mt5" / "research" / "owner_permitted_sources.py"
    spec = importlib.util.spec_from_file_location("owner_permitted_sources_t", p)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Wire:
    """A fixture HTTP layer that records every URL it was asked for."""

    def __init__(self, robots: tuple[int | None, bytes] = (404, b""),
                 data: tuple[int | None, bytes] = (200, b"ok"), final: str | None = None):
        self.robots, self.data, self.final = robots, data, final
        self.calls: list[str] = []

    def __call__(self, url: str, headers: Any,
                 timeout: float) -> tuple[int | None, bytes, str, str, str]:
        self.calls.append(url)
        assert "Mozilla" not in headers.get("User-Agent", "")      # honest UA, never a browser
        if url.endswith("/robots.txt"):
            code, body = self.robots
            return code, body, url, "text/plain", "" if code is not None else "URLError"
        code, body = self.data
        if "cboe" in url and code == 200:
            body = CHAIN
        err = "" if code is not None and code < 400 else f"HTTP {code}"
        return code, body if code == 200 else b"", self.final or url, "application/json", err

    def data_calls(self) -> list[str]:
        return [u for u in self.calls if not u.endswith("/robots.txt")]


def _perm(tmp_path: Path, **flags: bool) -> Path:
    doc = json.loads(REAL.read_text(encoding="utf-8"))
    for r in doc["sources"]:
        if r["id"] in flags:
            r["enabled"] = flags[r["id"]]
    p = tmp_path / "owner_permissions.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    return p


def test_the_real_file_names_the_seven_sources_with_their_basis_and_revert() -> None:
    doc = json.loads(REAL.read_text(encoding="utf-8"))
    rows = {r["id"]: r for r in doc["sources"]}
    assert set(rows) == set(SEVEN)
    for r in rows.values():
        assert r["enabled"] is True and r["basis"] == "owner_attestation_2026-11-17"
        assert len(r["cited_messages"]) == 4 and r["governance"].endswith(
            "owner-permission-attestation-2026-11-17.md")
        assert not r["governance"].startswith("/"), "the public wire carries no host paths"
        assert "enabled" in r["revert"] and r["missed_growth"].startswith("missed_growth")
        assert r["hosts"] and all(op.hard_refusal(f"https://{h}/") is None for h in r["hosts"])
    assert rows["chicagofed_nfci"]["hosts"] == ["www.chicagofed.org"]       # never FRED


@pytest.mark.parametrize("sid", SEVEN)
def test_each_source_fetches_when_enabled_and_refuses_when_false(tmp_path: Path, sid: str) -> None:
    organ = _organ()
    on = Wire()
    doc = organ.run(path=_perm(tmp_path), transport=on, today=date(2026, 11, 17),
                    raw_root=tmp_path / "raw", gex_file=tmp_path / "gex.jsonl")
    row = next(r for r in doc["sources"] if r["source"] == sid)
    assert row["status"] in ("FETCHED", "FETCHED_NEEDS_PARSER"), row
    assert any(u for u in on.data_calls() if any(h in u for h in
                                                 json.loads(REAL.read_text())["sources"]
                                                 [SEVEN.index(sid)]["hosts"]))
    off = Wire()
    doc = organ.run(path=_perm(tmp_path, **{sid: False}), transport=off,
                    today=date(2026, 11, 17), raw_root=tmp_path / "raw2",
                    gex_file=tmp_path / "gex2.jsonl")
    row = next(r for r in doc["sources"] if r["source"] == sid)
    assert row["status"] == "BLOCKED_ON_TERMS" and "disabled" in row["why"]
    assert row["missed_growth"].startswith("missed_growth")
    assert "permission" not in row                       # nothing fetched under the attestation
    # its own endpoint is never requested (two BoJ rows share a host, so match the path)
    eps = json.loads(REAL.read_text())["sources"][SEVEN.index(sid)]["endpoints"]
    stems = [e.split("{", 1)[0] for e in eps]
    assert not [u for u in off.data_calls() if any(u.startswith(st) for st in stems)]
    assert op.is_permitted(sid, _perm(tmp_path)) and not op.is_permitted(
        sid, _perm(tmp_path, **{sid: False}))


@pytest.mark.parametrize("content", [None, "", "{not json", "[]", '{"sources": "x"}'])
def test_a_missing_or_corrupt_file_permits_nothing_and_contacts_nothing(
        tmp_path: Path, content: str | None) -> None:
    p = tmp_path / "owner_permissions.json"
    if content is not None:
        p.write_text(content, encoding="utf-8")
    for sid in SEVEN:
        assert op.is_permitted(sid, p) is False
        assert str(op.refusal(sid, None, p)).startswith("BLOCKED_ON_TERMS")
    assert op.is_permitted("cdn.cboe.com", p) is False
    w = Wire()
    doc = _organ().run(path=p, transport=w, raw_root=tmp_path / "raw",
                       gex_file=tmp_path / "gex.jsonl")
    assert {r["status"] for r in doc["sources"]} == {"BLOCKED_ON_TERMS"}
    assert w.calls == []


def test_enabled_must_be_literally_true(tmp_path: Path) -> None:
    doc = json.loads(REAL.read_text(encoding="utf-8"))
    doc["sources"][0]["enabled"] = "true"
    p = tmp_path / "p.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    assert op.is_permitted(doc["sources"][0]["id"], p) is False


def test_provenance_rides_on_the_raw_sidecar_the_gex_row_and_the_report(tmp_path: Path) -> None:
    doc = _organ().run(path=_perm(tmp_path), transport=Wire(), today=date(2026, 11, 17),
                       raw_root=tmp_path / "raw", gex_file=tmp_path / "gex.jsonl")
    for row in doc["sources"]:
        assert row["permission"] == "owner_attestation_2026-11-17"
        for f in row["fetches"]:
            assert f["permission"] == "owner_attestation_2026-11-17"
            meta = json.loads(Path(f["path"] + ".meta.json").read_text(encoding="utf-8"))
            assert meta["provenance"] == "permission=owner_attestation_2026-11-17"
            assert meta["sha256"] == f["sha256"]
    gex = [json.loads(x) for x in (tmp_path / "gex.jsonl").read_text().splitlines()]
    assert len(gex) == 1 and gex[0]["permission"] == "owner_attestation_2026-11-17"
    assert gex[0]["net_gex"] > 0 and gex[0]["source"] == "exchange_options_gamma"


def test_hkex_endpoint_names_the_last_weekday() -> None:
    organ = _organ()
    assert organ.render("x_{yyyymmdd}e.js", date(2026, 11, 16)) == "x_20261113e.js"   # Mon->Fri


@pytest.mark.parametrize("robots", [
    (200, b"User-agent: *\nDisallow: /\n"), (500, b""), (None, b""), (403, b""), (429, b""),
    (200, b"<!DOCTYPE html><html>blocked</html>")])
def test_robots_refusal_still_wins_over_an_enabled_row(tmp_path: Path, robots: Any) -> None:
    w = Wire(robots=robots)
    f = op.permitted_get("snb_sight_deposits",
                         "https://data.snb.ch/api/cube/snbgwdchfsgw/data/csv/en",
                         transport=w, path=_perm(tmp_path))
    assert f.status == "robots_refused" and not f.body
    assert w.data_calls() == []


@pytest.mark.parametrize("code", [401, 403, 429, 451])
def test_a_publisher_refusal_is_a_hard_stop_and_never_retried(tmp_path: Path, code: int) -> None:
    w = Wire(data=(code, b""))
    doc = _organ().run(path=_perm(tmp_path), transport=w, today=date(2026, 11, 17),
                       raw_root=tmp_path / "raw", gex_file=tmp_path / "gex.jsonl")
    assert {r["status"] for r in doc["sources"]} == {"HARD_STOP"}
    assert all(r["missed_growth"] for r in doc["sources"])
    assert len(w.data_calls()) == len(SEVEN)                                   # one each, no retry


def test_a_redirect_into_a_refused_host_is_dropped(tmp_path: Path) -> None:
    w = Wire(final="https://api.stlouisfed.org/fred/series/observations?series_id=NFCI")
    f = op.permitted_get("chicagofed_nfci",
                         "https://www.chicagofed.org/-/media/publications/nfci/nfci-data-series-csv.csv",
                         transport=w, path=_perm(tmp_path))
    assert f.status == "refused" and "stlouisfed" in f.why and not f.body


def test_a_row_only_unlocks_its_own_hosts(tmp_path: Path) -> None:
    why = op.refusal("snb_sight_deposits", "https://www.snb.ch/en/", _perm(tmp_path))
    assert why and "not a host" in why


HARD = ["api.stlouisfed.org", "alfred.stlouisfed.org", "www.reddit.com", "query1.finance.yahoo.com",
        "comtradeapi.un.org", "web.archive.org", "www.youtube.com", "datafeed.dukascopy.com",
        "www.theice.com", "www.ssga.com", "www.spdrgoldshares.com", "ftmo.com", "the5ers.com",
        "index.baidu.com", "weixin.sogou.com", "efdsearch.senate.gov"]


@pytest.mark.parametrize("host", HARD)
def test_an_enabled_row_never_unlocks_a_hard_refused_host(tmp_path: Path, host: str) -> None:
    doc = json.loads(REAL.read_text(encoding="utf-8"))
    doc["sources"].append({"id": "sneaky", "hosts": [host], "endpoints": [f"https://{host}/x"],
                           "enabled": True, "basis": "owner_attestation_2026-11-17"})
    p = tmp_path / "p.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    assert op.is_permitted("sneaky", p) is False
    assert op.is_permitted(host, p) is False
    w = Wire()
    f = op.permitted_get("sneaky", f"https://{host}/x", transport=w, path=p)
    assert f.status == "refused" and w.calls == []
    row = next(r for r in _organ().run(path=p, transport=Wire(), raw_root=tmp_path / "r",
                                       gex_file=tmp_path / "g.jsonl")["sources"]
               if r["source"] == "sneaky")
    assert row["status"] == "BLOCKED_ON_TERMS"


def test_the_terms_refused_list_wins_except_for_the_attested_cboe_scope(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When the terms branch's libs/data/refused_hosts.py is on the tree it is consulted: its
    hosts stay refused under any row, except cboe.com, which this attestation names in scope."""
    fake = types.ModuleType("libs.data.refused_hosts")
    listed = {"cboe.com": "Cboe: refused", "dukascopy.com": "Dukascopy: refused",
              "imf.org": "IMF: refused"}

    def refusal(url: str) -> str | None:
        h = op._host(url) or ""
        return next((w for d, w in listed.items() if h == d or h.endswith("." + d)), None)

    fake.refusal = refusal  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "libs.data.refused_hosts", fake)
    # `from libs.data import refused_hosts` reads the PACKAGE attribute first, which an earlier
    # test's import of the real module has already bound: patch that too, or this test depends
    # on the order the file runs in
    import libs.data
    monkeypatch.setattr(libs.data, "refused_hosts", fake, raising=False)
    p = _perm(tmp_path)
    assert op.is_permitted("exchange_options_gamma", p) is True
    doc = json.loads(p.read_text(encoding="utf-8"))
    doc["sources"].append({"id": "imf_ports", "hosts": ["www.imf.org"], "enabled": True,
                           "endpoints": ["https://www.imf.org/x"]})
    p.write_text(json.dumps(doc), encoding="utf-8")
    assert op.is_permitted("imf_ports", p) is False
    assert str(op.refusal("imf_ports", "https://www.imf.org/x", p)).startswith("BLOCKED_ON_TERMS")


def test_the_unscheduled_observables_script_keeps_vix_refused_and_gates_the_chain(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    spec = importlib.util.spec_from_file_location(
        "ffo_t", REPO / "scripts" / "fetch_free_observables.py")
    assert spec and spec.loader
    ffo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ffo)
    w = Wire()
    monkeypatch.setattr(op, "_urllib_transport", w)
    monkeypatch.setattr(op, "PERMISSIONS", _perm(tmp_path))
    body, why = ffo._gated_get("cboe_vix_history", ffo.SOURCES["cboe_vix_history"]["url"])
    assert body is None and "no owner_permissions row" in why and w.calls == []
    body, why = ffo._gated_get("cboe_spx_options", ffo.SOURCES["cboe_spx_options"]["url"])
    assert body == CHAIN and why == ""
    monkeypatch.setattr(op, "PERMISSIONS", _perm(tmp_path, exchange_options_gamma=False))
    w.calls.clear()
    body, why = ffo._gated_get("cboe_spx_options", ffo.SOURCES["cboe_spx_options"]["url"])
    assert body is None and "disabled" in why and w.calls == []

# --------------------------------------------------------------------------- MF1: redirect hops
class _FakeNet:
    """Replaces urllib's HTTP(S) handlers' network call: the REAL opener, redirect handler and
    error processors run; only the socket is scripted. Records every URL actually requested."""

    def __init__(self, script: dict[str, tuple[int, dict[str, str], bytes]]) -> None:
        self.script = script
        self.requested: list[str] = []

    def __call__(self, handler: Any, req: urllib.request.Request) -> Any:
        url = req.full_url
        self.requested.append(url)
        code, hdrs, body = self.script.get(url, (404, {}, b""))
        msg = email.message.Message()
        for k, v in hdrs.items():
            msg[k] = v
        resp = urllib.response.addinfourl(io.BytesIO(body), msg, url, code)
        resp.msg = "scripted"  # type: ignore[attr-defined]
        return resp


@pytest.fixture
def fake_net(monkeypatch: pytest.MonkeyPatch) -> Any:
    from libs.data import polite_fetch

    def install(script: dict[str, tuple[int, dict[str, str], bytes]]) -> _FakeNet:
        net = _FakeNet(script)

        def _open(handler: Any, req: urllib.request.Request) -> Any:
            return net(handler, req)

        monkeypatch.setattr(urllib.request.HTTPSHandler, "https_open", _open)
        monkeypatch.setattr(urllib.request.HTTPHandler, "http_open", _open)
        return net

    monkeypatch.setattr(polite_fetch.GATE, "wait", lambda *a, **k: None)
    return install


NFCI = "https://www.chicagofed.org/-/media/publications/nfci/nfci-data-series-csv.csv"


@pytest.mark.parametrize("target", [
    "https://api.stlouisfed.org/fred/series/observations?series_id=NFCI",
    "https://finance.yahoo.com/quote/NFCI",
    "https://www.snb.ch/elsewhere"])                 # not hard-refused, but not this row's host
def test_a_redirect_hop_is_refused_before_it_is_requested(
        tmp_path: Path, fake_net: Any, target: str) -> None:
    net = fake_net({
        "https://www.chicagofed.org/robots.txt": (404, {}, b""),
        NFCI: (302, {"Location": target}, b""),
        target: (200, {"Content-Type": "text/csv"}, b"leaked,bytes\n")})
    f = op.permitted_get("chicagofed_nfci", NFCI, path=_perm(tmp_path))
    assert f.status == "refused" and "redirect" in f.why and not f.body
    assert net.requested == ["https://www.chicagofed.org/robots.txt", NFCI]   # NO second hop


def test_the_transport_alone_refuses_a_hard_refused_hop(fake_net: Any) -> None:
    net = fake_net({"https://example.org/a": (302, {"Location": "https://api.stlouisfed.org/x"},
                                              b"")})
    code, body, final, _ct, err = op._urllib_transport("https://example.org/a", {}, 5.0)
    assert code is None and not body and err.startswith(op.REDIRECT_REFUSED)
    assert final == "https://api.stlouisfed.org/x"
    assert net.requested == ["https://example.org/a"]


def test_a_robots_redirect_into_a_refused_host_is_never_requested(
        tmp_path: Path, fake_net: Any) -> None:
    net = fake_net({"https://www.chicagofed.org/robots.txt":
                    (301, {"Location": "https://finance.yahoo.com/robots.txt"}, b"")})
    f = op.permitted_get("chicagofed_nfci", NFCI, path=_perm(tmp_path))
    assert f.status == "robots_refused" and op.REDIRECT_REFUSED in f.why
    assert net.requested == ["https://www.chicagofed.org/robots.txt"]


def test_a_redirect_inside_the_row_is_followed(tmp_path: Path, fake_net: Any) -> None:
    moved = "https://www.chicagofed.org/moved.csv"
    net = fake_net({"https://www.chicagofed.org/robots.txt": (404, {}, b""),
                    NFCI: (302, {"Location": moved}, b""),
                    moved: (200, {"Content-Type": "text/csv"}, b"date,nfci\n")})
    f = op.permitted_get("chicagofed_nfci", NFCI, path=_perm(tmp_path))
    assert f.ok and f.body == b"date,nfci\n" and net.requested[-1] == moved


# --------------------------------------------------------------------------- MF2: robots codes
@pytest.mark.parametrize("code,allowed", [
    (404, True), (410, True), (401, False), (403, False), (400, False), (405, False),
    (406, False), (418, False), (429, False), (451, False), (500, False), (503, False),
    (301, False)])
def test_robots_allows_only_404_and_410_as_no_file(code: int, allowed: bool) -> None:
    ok, why = op.robots_allows("https://data.snb.ch/api/x", Wire(robots=(code, b"")))
    assert ok is allowed, why
    if code in (401, 403):
        assert "denied" in why


# --------------------------------------------------------------------------- MF3: output path
def test_cboe_output_lands_only_under_the_gitignored_owner_permitted_dir() -> None:
    gex = op.CBOE_GEX_FILE
    assert gex == _organ().GEX_FILE
    rel = gex.relative_to(REPO).as_posix()
    assert rel == "desks/mt5/data/owner_permitted/cboe_options/cboe_spx_options.jsonl"
    r = subprocess.run(["git", "-C", str(REPO), "check-ignore", "-q", rel], check=False)
    assert r.returncode == 0, f"{rel} is not gitignored"
    from libs.research_os.adapters import fetched_data
    assert gex == fetched_data.OWNER_PERMITTED / fetched_data.GEX_RELPATH
    spec = importlib.util.spec_from_file_location(
        "shadow_institutional_t", REPO / "desks" / "mt5" / "research" / "shadow_institutional.py")
    assert spec and spec.loader
    si = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = si
    try:
        spec.loader.exec_module(si)
    finally:
        sys.modules.pop(spec.name, None)
    assert si.OWNER_OBSERVABLES["cboe_delayed_surface"] == gex


def test_the_organ_writes_the_gex_row_there_and_nowhere_tracked(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    organ = _organ()
    gex = tmp_path / "desks/mt5/data/owner_permitted/cboe_options/cboe_spx_options.jsonl"
    monkeypatch.setattr(organ, "GEX_FILE", gex)
    before = subprocess.run(["git", "-C", str(REPO), "status", "--porcelain"],
                            capture_output=True, text=True, check=True).stdout
    # default gex_file is bound at def time: pass the module's own default explicitly
    organ.run(path=_perm(tmp_path), transport=Wire(), today=date(2026, 11, 17),
              raw_root=tmp_path / "raw", gex_file=organ.GEX_FILE)
    assert [json.loads(x)["permission"] for x in gex.read_text().splitlines()] == [
        "owner_attestation_2026-11-17"]
    after = subprocess.run(["git", "-C", str(REPO), "status", "--porcelain"],
                           capture_output=True, text=True, check=True).stdout
    assert after == before                                   # nothing tracked was touched


def test_the_observables_script_writes_owner_gated_output_under_the_ignored_dir() -> None:
    spec = importlib.util.spec_from_file_location(
        "ffo_t2", REPO / "scripts" / "fetch_free_observables.py")
    assert spec and spec.loader
    ffo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ffo)
    assert op.CBOE_GEX_FILE.parent == ffo.OWNER_OUT
    rel = (ffo.OWNER_OUT / "cboe_spx_options.jsonl").relative_to(REPO).as_posix()
    assert subprocess.run(["git", "-C", str(REPO), "check-ignore", "-q", rel],
                          check=False).returncode == 0


# --------------------------------------------------------------------------- SF: 24h hold
@pytest.mark.parametrize("code", [401, 403, 429, 451])
def test_a_hard_stop_is_held_24h_and_skipped_with_missed_growth(
        tmp_path: Path, code: int, _isolated_holds: Path) -> None:
    organ = _organ()
    w = Wire(data=(code, b""))
    organ.run(path=_perm(tmp_path), transport=w, today=date(2026, 11, 17),
              raw_root=tmp_path / "raw", gex_file=tmp_path / "gex.jsonl")
    holds = json.loads(_isolated_holds.read_text(encoding="utf-8"))
    assert set(holds) == set(SEVEN) and {h["http"] for h in holds.values()} == {code}
    until = datetime.fromisoformat(holds["snb_sight_deposits"]["until"])
    assert timedelta(hours=23, minutes=59) < until - datetime.now(UTC) <= timedelta(hours=24)
    # the next pass, within the hold: nothing is requested, every source is HELD with its line
    w2 = Wire()
    doc = organ.run(path=_perm(tmp_path), transport=w2, today=date(2026, 11, 17),
                    raw_root=tmp_path / "raw", gex_file=tmp_path / "gex.jsonl")
    assert {r["status"] for r in doc["sources"]} == {"HELD"}
    assert w2.calls == []
    for r in doc["sources"]:
        assert r["missed_growth"].startswith("missed_growth")
        assert "missed_growth" in r["fetches"][0]["why"] and "held until" in r["fetches"][0]["why"]


def test_a_hold_lifts_after_24h(tmp_path: Path, _isolated_holds: Path) -> None:
    past = (datetime.now(UTC) - timedelta(seconds=1)).isoformat(timespec="seconds")
    _isolated_holds.parent.mkdir(parents=True, exist_ok=True)
    _isolated_holds.write_text(json.dumps({"snb_sight_deposits": {
        "until": past, "http": 429, "why": "x"}}), encoding="utf-8")
    assert op.held("snb_sight_deposits") is None
    w = Wire()
    f = op.permitted_get("snb_sight_deposits", "https://data.snb.ch/api/x",
                         transport=w, path=_perm(tmp_path))
    assert f.ok and w.data_calls() == ["https://data.snb.ch/api/x"]


@pytest.mark.parametrize("code", [401, 403, 429, 451])
def test_a_robots_hard_stop_is_held_too(tmp_path: Path, code: int) -> None:
    w = Wire(robots=(code, b""))
    f = op.permitted_get("snb_sight_deposits", "https://data.snb.ch/api/x",
                         transport=w, path=_perm(tmp_path))
    assert f.status == "robots_refused" and "held until" in f.why and "missed_growth" in f.why
    assert op.held("snb_sight_deposits") is not None
    w2 = Wire()
    f = op.permitted_get("snb_sight_deposits", "https://data.snb.ch/api/x",
                         transport=w2, path=_perm(tmp_path))
    assert f.status == "held" and w2.calls == []


def test_the_default_hold_file_is_gitignored() -> None:
    rel = (REPO / "data" / "owner_permitted" / "hard_stops.json").relative_to(REPO).as_posix()
    assert subprocess.run(["git", "-C", str(REPO), "check-ignore", "-q", rel],
                          check=False).returncode == 0
