"""The retail crowd recorder: parsers on fixtures, PIT stamping, append-only, charge-once.

Every fixture is synthetic, written to the shape each source is documented or observed to serve;
nothing here touches the network or box state (all paths are redirected into `tmp_path`).
"""
from __future__ import annotations

import gzip
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import retail_crowd as rc  # noqa: E402

UNI = ["EURUSD", "GBPUSD", "XAUUSD", "US500", "GER40", "USDJPY", "Apple"]

MYFXBOOK_API = {"error": False, "message": "", "symbols": [
    {"name": "EURUSD", "shortPercentage": 63, "longPercentage": 37, "shortVolume": 1200.5,
     "longVolume": 700.1, "longPositions": 3100, "shortPositions": 5200, "totalPositions": 8300,
     "avgShortPrice": 1.09, "avgLongPrice": 1.1},
    {"name": "XAUUSD", "shortPercentage": 30, "longPercentage": 70, "shortVolume": 10,
     "longVolume": 25, "longPositions": 900, "shortPositions": 400},
    {"name": "ZZZZZZ", "shortPercentage": 50, "longPercentage": 50},
]}

CHALLENGE = ("<html><head><title>Just a moment...</title></head><body>"
             "<script>window._cf_chl_opt={cType: 'managed'}</script></body></html>")

MYFXBOOK_HTML = """
<table id="outlookSymbolPopoverTableEURUSD"><tr><td>Short</td><td>61 %</td><td>1,000 lots</td></tr>
<tr><td>Long</td><td>39 %</td><td>640 lots</td></tr></table>
<table id="outlookSymbolPopoverTableGBPUSD"><tr><td>Short</td><td>45 %</td></tr>
<tr><td>Long</td><td>55 %</td></tr></table>
"""

IG_HTML = """<html><body><div class="sentiment">
<h3>EUR/USD</h3><p>72% of client accounts are long on this market</p>
<p>28% of client accounts are short</p></div>
<div><h3>Gold</h3><span>35% long</span> / <span>65% short</span></div></body></html>"""

DUKAS_JSONP = ('cb({"data":[{"instrument":"EUR/USD","long":0.58,"short":0.42},'
               '{"instrument":"US500","long":0.3,"short":0.7}]});')


def test_myfxbook_api_parser_reads_labelled_fields() -> None:
    obs = {o["raw_symbol"]: o for o in rc.parse_myfxbook_api(MYFXBOOK_API)}
    assert obs["EURUSD"]["long_pct"] == pytest.approx(37.0)
    assert obs["EURUSD"]["short_pct"] == pytest.approx(63.0)
    assert obs["EURUSD"]["net_frac"] == pytest.approx(-0.26)
    assert obs["EURUSD"]["n_positions"] == 8300
    assert obs["EURUSD"]["long_lots"] == pytest.approx(700.1)
    assert obs["XAUUSD"]["n_positions"] == 1300          # summed when no total is given
    assert rc.parse_myfxbook_api({"error": True, "message": "Invalid session"}) == []


def test_html_parsers_never_guess_which_number_is_long() -> None:
    m = {o["raw_symbol"]: o for o in rc.parse_myfxbook_html(MYFXBOOK_HTML)}
    assert m["EURUSD"]["long_pct"] == pytest.approx(39.0)
    assert m["GBPUSD"]["long_pct"] == pytest.approx(55.0)
    ig = {o["raw_symbol"]: o for o in rc.PARSERS["ig"](IG_HTML)}
    assert ig["EUR/USD"]["long_pct"] == pytest.approx(72.0)
    gold = next(o for k, o in ig.items() if k.endswith("Gold"))
    assert gold["long_pct"] == pytest.approx(35.0)
    # two percentages with no long/short label are not a reading
    assert rc.parse_html("<p>EURUSD 61% 39%</p>") == []


def test_generic_json_reads_jsonp_and_fractions() -> None:
    d = {o["raw_symbol"]: o for o in rc.PARSERS["dukascopy"](DUKAS_JSONP)}
    assert d["EUR/USD"]["long_pct"] == pytest.approx(58.0)
    assert d["US500"]["net_frac"] == pytest.approx(-0.4)


def test_symbol_mapping_uses_the_registry_and_never_guesses() -> None:
    assert rc.map_symbol("EUR/USD", UNI) == "EURUSD"
    assert rc.map_symbol("EURUSD.x", UNI) == "EURUSD"
    assert rc.map_symbol("XAUUSDm", UNI) == "XAUUSD"
    assert rc.map_symbol("Gold", UNI) == "XAUUSD"
    assert rc.map_symbol("US 500", UNI) == "US500"
    assert rc.map_symbol("Germany 40", UNI) == "GER40"
    assert rc.map_symbol("apple", UNI) == "Apple"
    assert rc.map_symbol("ZZZZZZ", UNI) is None


def test_walls_are_recorded_never_bypassed() -> None:
    calls: list[str] = []

    def fetch(url: str) -> tuple[int, str]:
        calls.append(url)
        if url.endswith("/robots.txt"):
            return 404, ""                                  # no rules published
        return 403, CHALLENGE

    res = rc.fetch_page("fxblue", fetch)
    assert res["status"] == "WALLED" and res["obs"] == []
    pages = [c for c in calls if not c.endswith("/robots.txt")]
    assert len(pages) == 1                                  # one request, no retry
    api = rc.fetch_myfxbook_api(fetch, {"session": "S3CRET"})
    assert api["status"] == "WALLED"
    assert "S3CRET" not in json.dumps(api)


def test_myfxbook_api_login_logout_and_no_secret_leaks() -> None:
    calls: list[str] = []

    def fetch(url: str) -> tuple[int, str]:
        calls.append(url)
        if "login.json" in url:
            return 200, json.dumps({"error": False, "session": "SESS%2B1"})
        if "get-community-outlook" in url:
            return 200, json.dumps(MYFXBOOK_API)
        return 200, json.dumps({"error": False})

    res = rc.fetch_myfxbook_api(fetch, {"email": "me@x.y", "password": "pw-123"})
    assert res["status"] == "OK" and len(res["obs"]) == 3
    assert any("logout.json" in c for c in calls)           # a session we opened is closed
    blob = json.dumps(res)
    for secret in ("pw-123", "me@x.y", "SESS+1", "SESS%2B1"):
        assert secret not in blob
    assert rc.fetch_myfxbook_api(fetch, {})["status"] == "UNCONFIGURED"


def test_credentials_resolve_without_printing(monkeypatch: pytest.MonkeyPatch,
                                              capsys: pytest.CaptureFixture[str]) -> None:
    assert rc._credentials({"MYFXBOOK_SESSION": "abc"}) == {"session": "abc"}
    assert rc._credentials({"MYFXBOOK_EMAIL": "e", "MYFXBOOK_PASSWORD": "p"}) == {
        "email": "e", "password": "p"}
    assert rc._credentials({"MYFXBOOK_EMAIL": "e"}) == {}
    assert capsys.readouterr().out == ""


def _paths(tmp_path: Path) -> dict[str, Path]:
    return {"store": tmp_path / "retail_crowd.csv", "raw_dir": tmp_path / "raw",
            "state_path": tmp_path / "state.json"}


def test_pit_stamp_append_only_and_once_per_hour(tmp_path: Path) -> None:
    p = _paths(tmp_path)
    at = datetime(2026, 11, 3, 10, 7, 12, tzinfo=UTC)
    res = {"myfxbook_api": {"status": "OK", "url": "u", "http": 200, "body": "{}",
                            "obs": rc.parse_myfxbook_api(MYFXBOOK_API)}}
    out = rc.record_pass(res, at, UNI, **p)
    assert out["appended"] == 2 and out["unmapped"] == {"myfxbook_api": ["ZZZZZZ"]}
    df = pd.read_csv(p["store"])
    assert list(df.columns) == list(rc.COLUMNS)
    assert (df["captured_at"] == "2026-11-03T10:07:12+00:00").all()
    assert (df["available_time"] == df["captured_at"]).all()          # PIT: known at fetch
    assert (df["cohort"] == "all").all()
    first = p["store"].read_bytes()
    # the same hour again appends nothing
    again = rc.record_pass(res, at + timedelta(minutes=20), UNI, **p)
    assert again["appended"] == 0 and p["store"].read_bytes() == first
    # the next hour only ever GROWS the file: the prior bytes are an exact prefix
    rc.record_pass(res, at + timedelta(hours=1), UNI, **p)
    grown = p["store"].read_bytes()
    assert grown.startswith(first) and len(grown) > len(first)
    snaps = sorted((p["raw_dir"] / "myfxbook_api").glob("*.json.gz"))
    assert len(snaps) == 3
    with gzip.open(snaps[0], "rt", encoding="utf-8") as fh:
        assert json.load(fh)["fetched_at"] == "2026-11-03T10:07:12+00:00"


def _store_with_history(tmp_path: Path, hours: int, start: datetime) -> Path:
    rng = np.random.default_rng(7)
    rows = []
    for h in range(hours):
        t = (start + timedelta(hours=h)).isoformat()
        net = float(np.clip(0.2 + 0.1 * rng.standard_normal(), -0.9, 0.9))
        rows.append({"captured_at": t, "available_time": t, "source": "myfxbook_api",
                     "cohort": "all", "symbol": "EURUSD", "net_frac": net,
                     "long_pct": 50 + 50 * net, "short_pct": 50 - 50 * net})
    store = tmp_path / "retail_crowd.csv"
    rc.append_rows(rows, store)
    return store


def test_per_symbol_series_and_features(tmp_path: Path) -> None:
    start = datetime(2026, 9, 1, tzinfo=UTC)
    store = _store_with_history(tmp_path, 100, start)
    series = rc.build_series(store, tmp_path)
    frame = pd.read_parquet(tmp_path / "rfx_EURUSD.parquet")
    assert len(frame) == 100 and {"available_time", "net_frac", "n_sources"} <= set(frame.columns)
    assert json.loads((tmp_path / "rfx_EURUSD.pit.json").read_text("utf-8"))["clock"] == "utc"
    f = rc.features(series, start + timedelta(hours=100))["EURUSD"]
    assert f["n_obs"] == 100 and f["net_z"] is not None
    assert f["chg_1h"] is not None and f["chg_24h"] is not None
    assert f["contrarian_side"] in (-1, 0, 1)
    # the conditioner the hypotheses name can read the series, lagged before any join
    from mt5desk.family_exogenous_conditioner import conditioner
    s = conditioner("rfx_EURUSD", "net_frac", "level_z", lag_hours=3, z_window=24, root=tmp_path)
    assert s is not None and s.index.min() >= pd.Timestamp(start) + pd.Timedelta(hours=3)


def test_hypotheses_wait_for_history_then_charge_once(tmp_path: Path) -> None:
    now = datetime(2026, 11, 3, tzinfo=UTC)
    emitted, intel = tmp_path / "emitted.jsonl", tmp_path / "intel"
    young = {"EURUSD": {"n_obs": 50, "span_days": 2.0,
                        "first": (now - timedelta(days=2)).isoformat()}}
    h0 = rc.hypotheses(young, now, emitted_path=emitted, intel_dir=intel, lane=lambda s: True)
    assert h0["donated"] == 0 and h0["pending"] == 3 and not emitted.exists()
    ready = {"EURUSD": {"n_obs": rc.MIN_HISTORY_OBS, "span_days": rc.MIN_HISTORY_DAYS,
                        "first": (now - timedelta(days=61)).isoformat()},
             "Apple": {"n_obs": 5000, "span_days": 400.0,
                       "first": (now - timedelta(days=400)).isoformat()}}
    lane = lambda s: s != "Apple"  # noqa: E731 -- single names are never hypothesised
    h1 = rc.hypotheses(ready, now, emitted_path=emitted, intel_dir=intel, lane=lane)
    assert h1["donated"] == 3 and h1["set_aside_not_hypothesis_lane"] == ["Apple"]
    rows = json.loads(next(intel.glob("*.json")).read_text("utf-8"))
    assert {r["family"] for r in rows} == {"exogenous_conditioner", "alt_series_momentum"}
    assert all(r["params"]["source"] == "rfx_EURUSD" and r["available_time"] for r in rows)
    # every later pass: nothing re-donated, nothing re-charged
    for k in range(3):
        hk = rc.hypotheses(ready, now + timedelta(hours=k + 1), emitted_path=emitted,
                           intel_dir=intel, lane=lane)
        assert hk["donated"] == 0 and hk["already_emitted"] == 3
    assert len(emitted.read_text("utf-8").splitlines()) == 3
    assert len(list(intel.glob("*.json"))) == 1


def test_donated_rows_compile_as_exact_recipes(tmp_path: Path) -> None:
    import miner_candidate_compiler as mcc
    for sp in rc.specs_for("EURUSD"):
        row = {"source": rc.SEAT, "kind": "hypothesis", "family": sp["family"],
               "params": sp["params"], "symbols": ["EURUSD"], "title": sp["key"]}
        cands, disp = mcc.compile_row(rc.SEAT, row, {"EURUSD"})
        assert disp == "EXACT_RECIPE" and cands[0]["family"] == sp["family"]


# ------------------------------------------------------------------ robots.txt (MF1)
def _robots_fetch(robots: dict[str, tuple[int, str] | Exception], page_body: str = IG_HTML
                  ) -> tuple[list[str], rc.Fetcher]:
    calls: list[str] = []

    def fetch(url: str) -> tuple[int, str]:
        calls.append(url)
        if url.endswith("/robots.txt"):
            host = url.split("/")[2]
            ans = robots.get(host, (404, ""))
            if isinstance(ans, Exception):
                raise ans
            return ans
        return 200, page_body
    return calls, fetch


def test_robots_disallowed_path_is_refused_and_never_fetched() -> None:
    calls, fetch = _robots_fetch({"www.ig.com": (200, "User-agent: *\nDisallow: /uk/\n")})
    res = rc.fetch_page("ig", fetch)
    assert res["status"] == "ROBOTS_REFUSED" and res["obs"] == []
    assert "disallows /uk/ig-client-sentiment" in res["why"] and "not fetched" in res["why"]
    assert calls == ["https://www.ig.com/robots.txt"]       # the page itself was never requested


def test_robots_is_read_for_our_user_agent_and_the_exact_path() -> None:
    # Rules aimed at our UA bind; a Disallow for another agent does not.
    ua = rc.USER_AGENT.split("/")[0]
    calls, fetch = _robots_fetch({"www.ig.com": (200, f"User-agent: {ua}\nDisallow: /\n")})
    assert rc.fetch_page("ig", fetch)["status"] == "ROBOTS_REFUSED"
    calls, fetch = _robots_fetch({"www.ig.com": (200, "User-agent: OtherBot\nDisallow: /\n")})
    assert rc.fetch_page("ig", fetch)["status"] == "OK"
    assert calls[-1] == rc.SOURCES["ig"]["url"]


def test_fxblue_refusing_terms_still_checks_the_sentiment_path() -> None:
    only_terms = "User-agent: *\nDisallow: /terms\n"
    calls, fetch = _robots_fetch({"www.fxblue.com": (200, only_terms)})
    res = rc.fetch_page("fxblue", fetch)
    assert res["robots"]["verdict"] == "ALLOWED"
    assert res["robots"]["path"] == "/market-data/tools/sentiment"
    assert calls[-1] == rc.SOURCES["fxblue"]["url"]
    refused = only_terms + "Disallow: /market-data/\n"
    calls, fetch = _robots_fetch({"www.fxblue.com": (200, refused)})
    assert rc.fetch_page("fxblue", fetch)["status"] == "ROBOTS_REFUSED"
    assert calls == ["https://www.fxblue.com/robots.txt"]


@pytest.mark.parametrize("answer", [(503, "down"), (403, CHALLENGE), (200, CHALLENGE),
                                    OSError("connection reset")])
def test_unreadable_robots_is_unmeasured_and_the_page_is_not_fetched(
        answer: tuple[int, str] | Exception) -> None:
    calls, fetch = _robots_fetch({"www.dukascopy.com": answer})
    res = rc.fetch_page("dukascopy", fetch)
    assert res["status"] == "UNMEASURED" and res["obs"] == []
    assert calls == ["https://www.dukascopy.com/robots.txt"]


def test_robots_404_means_no_rules() -> None:
    calls, fetch = _robots_fetch({"www.ig.com": (404, "not found")})
    res = rc.fetch_page("ig", fetch)
    assert res["status"] == "OK" and res["robots"]["robots_state"] == "NO_RULES"
    assert calls[-1] == rc.SOURCES["ig"]["url"]


def test_robots_cached_per_host_per_pass_and_api_recorded_not_gated() -> None:
    disallow_api = "User-agent: *\nDisallow: /api/\nDisallow: /community/\n"
    calls, fetch = _robots_fetch({"www.myfxbook.com": (200, disallow_api)},
                                 page_body=json.dumps(MYFXBOOK_API))
    out = rc.fetch_all(fetch, {"session": "S3CRET"})
    robots_calls = [c for c in calls if c.endswith("/robots.txt")]
    assert len(robots_calls) == len(set(robots_calls)) == 4  # myfxbook, dukascopy, fxblue, ig
    api = out["myfxbook_api"]
    # recorded on the API's own record, but the official API is not gated on it (see docstring)
    assert api["robots"]["verdict"] == "ROBOTS_REFUSED" and api["robots"]["gated"] is False
    assert api["status"] == "OK"
    assert "S3CRET" not in json.dumps(api["robots"])
    assert "myfxbook_html" not in out                        # the API answered; no fallback


def test_myfxbook_html_fallback_is_gated_on_robots() -> None:
    rules = "User-agent: *\nDisallow: /community/\n"
    calls, fetch = _robots_fetch({"www.myfxbook.com": (200, rules)}, page_body=MYFXBOOK_HTML)
    out = rc.fetch_all(fetch, {})
    assert out["myfxbook_api"]["status"] == "UNCONFIGURED"
    assert out["myfxbook_html"]["status"] == "ROBOTS_REFUSED"
    assert rc.SOURCES["myfxbook_html"]["url"] not in calls


def test_record_pass_names_the_robots_wall(tmp_path: Path) -> None:
    res = {"ig": {"status": "ROBOTS_REFUSED", "url": rc.SOURCES["ig"]["url"], "obs": [],
                  "why": "robots.txt ... disallows", "robots": {"verdict": "ROBOTS_REFUSED"}}}
    out = rc.record_pass(res, datetime(2026, 11, 5, tzinfo=UTC), UNI, **_paths(tmp_path))
    assert out["sources"]["ig"]["status"] == "ROBOTS_REFUSED" and out["appended"] == 0
    assert out["sources"]["ig"]["robots"]["verdict"] == "ROBOTS_REFUSED"


# ------------------------------------------------------------- access labels on donations (MF2)
def test_most_restrictive_label_and_fail_closed_terms() -> None:
    assert rc.most_restrictive(["LICENSED", "ACCESS_UNCLEAR"]) == "ACCESS_UNCLEAR"
    assert rc.most_restrictive(["PUBLIC_WITH_TERMS", "LICENSED"]) == "LICENSED"
    assert rc.most_restrictive([]) == "ACCESS_UNCLEAR"
    assert rc.most_restrictive(["SOMETHING_NEW"]) == "ACCESS_UNCLEAR"
    acc = rc.source_access(["myfxbook_api", "fxblue"])
    assert acc["access_label"] == "LICENSED" and acc["terms"] == "to_confirm"
    assert rc.source_access([]) == {"access_label": "ACCESS_UNCLEAR", "terms": "to_confirm",
                                    "access_sources": []}


@pytest.mark.parametrize("sources", [["dukascopy"], ["ig"], ["myfxbook_api", "dukascopy"],
                                     ["fxblue", "ig"]])
def test_donation_from_unclear_sources_carries_access_unclear(tmp_path: Path,
                                                              sources: list[str]) -> None:
    start = datetime(2026, 8, 1, tzinfo=UTC)
    rows = []
    for h in range(rc.MIN_HISTORY_OBS + 24):
        t = (start + timedelta(hours=h)).isoformat()
        src = sources[h % len(sources)]
        net = 0.1 + 0.05 * np.sin(h / 7.0)
        rows.append({"captured_at": t, "available_time": t, "source": src, "cohort": "all",
                     "symbol": "EURUSD", "net_frac": net, "long_pct": 50 + 50 * net,
                     "short_pct": 50 - 50 * net,
                     "access_label": rc.SOURCES[src]["access_label"]})
    store = tmp_path / "retail_crowd.csv"
    rc.append_rows(rows, store)
    series = rc.build_series(store, tmp_path / "series")
    now = start + timedelta(hours=rc.MIN_HISTORY_OBS + 24)
    feats = rc.features(series, now)
    assert sorted(feats["EURUSD"]["sources"]) == sorted(set(sources))
    emitted, intel = tmp_path / "emitted.jsonl", tmp_path / "intel"
    h = rc.hypotheses(feats, now, emitted_path=emitted, intel_dir=intel, lane=lambda s: True)
    assert h["donated"] == 3
    donated = json.loads(next(intel.glob("*.json")).read_text("utf-8"))
    for r in donated:
        assert r["access_label"] == "ACCESS_UNCLEAR"
        assert r["terms"] == "to_confirm"
        assert r["access_sources"] == sorted(set(sources))
    for line in emitted.read_text("utf-8").splitlines():
        assert json.loads(line)["access_label"] == "ACCESS_UNCLEAR"
    # the rfx_ parquet layout is unchanged by the in-memory source list
    cols = set(pd.read_parquet(tmp_path / "series" / "rfx_EURUSD.parquet").columns)
    assert cols == {"available_time", "net_frac", "long_pct", "short_pct", "n_sources"}


def test_donation_with_unknown_sources_fails_closed(tmp_path: Path) -> None:
    now = datetime(2026, 11, 3, tzinfo=UTC)
    ready = {"EURUSD": {"n_obs": rc.MIN_HISTORY_OBS, "span_days": rc.MIN_HISTORY_DAYS,
                        "first": (now - timedelta(days=61)).isoformat()}}
    rc.hypotheses(ready, now, emitted_path=tmp_path / "e.jsonl", intel_dir=tmp_path / "i",
                  lane=lambda s: True)
    rows = json.loads(next((tmp_path / "i").glob("*.json")).read_text("utf-8"))
    assert {r["access_label"] for r in rows} == {"ACCESS_UNCLEAR"}
    assert {r["terms"] for r in rows} == {"to_confirm"}


# ------------------------------------------------------------------ no session / e-mail on disk
_EMAIL_RE = r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)+"


def test_written_payload_has_no_session_or_email(tmp_path: Path,
                                                 capsys: pytest.CaptureFixture[str]) -> None:
    import re

    def fetch(url: str) -> tuple[int, str]:
        if url.endswith("/robots.txt"):
            return 404, ""
        if "login.json" in url:
            return 200, json.dumps({"error": False, "session": "SESS%2B1 x"})
        if "get-community-outlook" in url:
            # a server that echoes the request (session in a URL, the account e-mail) back
            echo = {**MYFXBOOK_API, "request": f"{url}", "account": "me@x.y",
                    "next": "https://www.myfxbook.com/api/x.json?session=OTHERTOKEN&a=1"}
            return 200, json.dumps(echo)
        return 200, json.dumps({"error": False})

    res = rc.fetch_myfxbook_api(fetch, {"email": "me@x.y", "password": "pw-123"})
    assert res["status"] == "OK"
    p = _paths(tmp_path)
    rc.record_pass({"myfxbook_api": res}, datetime(2026, 11, 5, 9, tzinfo=UTC), UNI, **p)
    snaps = list((p["raw_dir"] / "myfxbook_api").glob("*.json.gz"))
    assert len(snaps) == 1
    with gzip.open(snaps[0], "rt", encoding="utf-8") as fh:
        text = fh.read()
    assert "session=" not in text.lower()
    assert re.search(_EMAIL_RE, text) is None
    for secret in ("pw-123", "SESS", "OTHERTOKEN", "me@x.y"):
        assert secret not in text
    # already clean before the snapshot: fetch_myfxbook_api redacts and scrubs its own body
    assert "body_scrubbed" in json.loads(text)
    # a public page body is scrubbed at the snapshot itself
    rc.record_pass({"ig": {"status": "PARSE_EMPTY", "url": "https://www.ig.com/x?session=T",
                           "http": 200, "obs": [], "body": "contact me@x.y ?session=T"}},
                   datetime(2026, 11, 5, 10, tzinfo=UTC), UNI, **p)
    with gzip.open(next((p["raw_dir"] / "ig").glob("*.json.gz")), "rt", encoding="utf-8") as fh:
        page = fh.read()
    assert "session=" not in page and re.search(_EMAIL_RE, page) is None
    assert json.loads(page)["body_scrubbed"] is True
    # and nothing reaches stdout / the state file either
    assert "session=" not in capsys.readouterr().out
    assert "session=" not in p["state_path"].read_text("utf-8")


def test_scrub_removes_session_params_and_emails() -> None:
    s = rc.scrub("GET https://h/api/a.json?session=abc%2Bdef&x=1 failed for "
                 "a.b+c@mail.example.org")
    assert "session=" not in s and "abc" not in s and "@" not in s and "x=1" in s
