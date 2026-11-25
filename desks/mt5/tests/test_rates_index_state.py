"""rates_index_state: PIT rates axis from primary publishers, terms-gated (IDEA_QUEUE 206).

No network: every fetch goes through a fake fetcher serving synthetic CSVs in each publisher's own
column layout, and every terms verdict is injected. The ledger's REAL verdicts are exercised once,
to pin that a HELD publisher is never contacted.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
FIX = Path(__file__).resolve().parent / "fixtures" / "rates_index_state"
SRC = DESK / "research" / "rates_index_state.py"
_spec = importlib.util.spec_from_file_location("rates_index_state", SRC)
ris = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("rates_index_state", ris)
_spec.loader.exec_module(ris)

AS_OF = date(2026, 10, 21)
NOW = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)
LAST = date(2026, 10, 20)
NOM = {"2 Yr": 3.6, "5 Yr": 3.8, "10 Yr": 4.1}
REAL10 = 1.9
VIX = 18.0


def _bdays(end: date, n: int) -> list[date]:
    out, d = [], end
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d -= timedelta(days=1)
    return sorted(out)


def _days_in(yr: int, end: date = LAST, n: int = 400) -> list[date]:
    return [d for d in _bdays(end, n) if d.year == yr]


def _treasury_nominal(yr: int, end: date = LAST) -> str:
    rows = ['Date,"1 Mo","2 Yr","3 Yr","5 Yr","7 Yr","10 Yr","30 Yr"']
    for i, d in enumerate(reversed(_days_in(yr, end))):       # Treasury lists newest first
        bump = 0.01 * (i % 7)
        rows.append(f"{d.strftime('%m/%d/%Y')},4.0,{NOM['2 Yr'] + bump:.2f},3.7,"
                    f"{NOM['5 Yr'] + bump:.2f},3.9,{NOM['10 Yr'] + bump:.2f},4.5")
    return "\n".join(rows) + "\n"


def _treasury_real(yr: int, end: date = LAST) -> str:
    rows = ['Date,"5 YR","7 YR","10 YR","20 YR","30 YR"']
    for d in reversed(_days_in(yr, end)):
        rows.append(f"{d.strftime('%m/%d/%Y')},1.5,1.7,{REAL10:.2f},2.1,2.2")
    return "\n".join(rows) + "\n"


def _vix(end: date = LAST, n: int = 300) -> str:
    rows = ["DATE,OPEN,HIGH,LOW,CLOSE"]
    days = _bdays(end, n)
    for i, d in enumerate(days):
        c = VIX + 0.1 * (i % 5) + (8.0 if i == len(days) - 1 else 0.0)   # a spike on the last print
        rows.append(f"{d.strftime('%m/%d/%Y')},{c:.2f},{c:.2f},{c:.2f},{c:.2f}")
    return "\n".join(rows) + "\n"


def _acm_csv(n: int = 30, end: date = LAST) -> str:
    rows = ["DATE,ACMTP10"]
    for i, d in enumerate(_bdays(end, n)):
        rows.append(f"{d.strftime('%d-%b-%Y')},{0.30 + 0.01 * i:.2f}")
    return "\n".join(rows) + "\n"


ALLOW_ALL = (200, "User-agent: *\nAllow: /\n")


class FakeNet:
    def __init__(self, codes: dict[str, int] | None = None, end: date = LAST,
                 robots: dict[str, tuple[int, str]] | None = None,
                 redirect: set[str] | None = None):
        self.codes = codes or {}
        self.calls: list[str] = []
        self.robots_calls: list[str] = []
        self.end = end
        self.robots = robots or {}
        self.redirect = redirect or set()

    def __call__(self, url: str) -> tuple[int, str]:
        if url.endswith("/robots.txt"):
            host = url.split("/")[2]
            self.robots_calls.append(host)
            return self.robots.get(host, ALLOW_ALL)
        if "daily_treasury_real_yield_curve" in url:
            key = "real"
        elif "daily_treasury_yield_curve" in url:
            key = "nominal"
        elif "cboe" in url:
            key = "vix"
        else:
            key = "acm"
        self.calls.append(key)
        if key in self.redirect:
            return 302, ""
        code = self.codes.get(key, 200)
        if code != 200:
            return code, "ConnectionError" if code == -1 else "nope"
        yr = int(m.group(1)) if (m := re.search(r"\.csv/(\d{4})/", url)) else self.end.year
        return 200, {"nominal": lambda: _treasury_nominal(yr, self.end),
                     "real": lambda: _treasury_real(yr, self.end),
                     "vix": lambda: _vix(self.end),
                     "acm": lambda: _acm_csv(end=self.end)}[key]()


def permit(_url: str) -> str:
    return "PERMITTED"


def test_no_terms_refused_aggregator_is_named_in_the_source():
    text = SRC.read_text(encoding="utf-8").lower()
    for host in ("stlouisfed", "alfred.", "fred_api", "api_key", "yahoo", "cboe.com"):
        assert host not in text, host


def test_treasury_csv_parse_newest_first_and_pit_stamp():
    known = datetime(2026, 10, 21, 9, 0, tzinfo=UTC)
    got = ris.parse_columns(_treasury_nominal(2026), {"UST10Y": "10 YR", "UST2Y": "2 YR"},
                            known, AS_OF)
    assert got["UST10Y"] and got["UST10Y"] == sorted(got["UST10Y"], key=lambda o: o.obs_date)
    assert got["UST10Y"][-1].obs_date == LAST
    assert all(o.released == known.date() for o in got["UST2Y"])
    # a file first seen after as_of does not exist as of as_of
    assert ris.parse_columns(_treasury_nominal(2026), {"UST10Y": "10 YR"}, known,
                             date(2026, 10, 20))["UST10Y"] == []


def test_rows_dated_after_as_of_are_dropped():
    known = datetime(2026, 10, 1, tzinfo=UTC)
    got = ris.parse_columns(_treasury_nominal(2026), {"UST10Y": "10 YR"}, known,
                            date(2026, 10, 9))["UST10Y"]
    assert got and max(o.obs_date for o in got) <= date(2026, 10, 9)


def test_acm_csv_parse_and_stamp():
    known = datetime(2026, 10, 7, 9, 0, tzinfo=UTC)
    obs = ris.parse_acm_csv((FIX / "acm_sample.csv").read_text(), known, AS_OF)
    assert [o.value for o in obs] == [0.40, 0.42, 0.44]
    assert all(o.released == known.date() for o in obs)
    assert ris.parse_acm_csv((FIX / "acm_sample.csv").read_text(), known, date(2026, 10, 6)) == []


def test_full_build_measured_where_a_source_exists_and_hy_oas_is_named_unmeasured():
    net = FakeNet()
    series, log = ris.collect(AS_OF, fetch=net, terms=permit, now=NOW)
    rep = ris.build(series, log, AS_OF, NOW)
    m = rep["metrics"]
    assert rep["status"] == "PARTIAL"                     # HY OAS has no primary source
    assert m["hy_oas_z"]["status"] == "UNMEASURED" and "ICE" in m["hy_oas_z"]["why"]
    for k, v in m.items():
        if k in ("hy_oas_z", "vix_z", "vix_level"):
            continue
        assert v["status"] == "MEASURED", (k, v)
        assert v["freshness"]["obs_date"] == "2026-10-20", k
    assert m["curve_curvature_2s5s10s"]["formula"] == "2 x UST5Y - UST2Y - UST10Y"
    assert m["curve_slope_10y2y"]["value"] == pytest.approx(NOM["10 Yr"] - NOM["2 Yr"])
    assert m["breakeven_10y"]["value"] == pytest.approx(NOM["10 Yr"] - REAL10)
    assert m["term_premium_acm_10y_change_20obs"]["value"] == pytest.approx(0.20)
    assert m["vix_z"]["status"] == m["vix_level"]["status"] == "UNMEASURED"  # Cboe: owner-only
    assert "vix" not in net.calls
    # two calendar years of Treasury files and one ACM
    assert net.calls.count("nominal") == 2 and net.calls.count("real") == 2


def test_terms_held_publisher_is_never_contacted():
    net = FakeNet()
    series, log = ris.collect(AS_OF, fetch=net, now=NOW)   # the desk's REAL terms ledger
    rep = ris.build(series, log, AS_OF, NOW)
    allowed = {k for k, s in rep["sources"].items() if s["status"] == "MEASURED"}
    held = {k for k, s in rep["sources"].items() if s["status"] == "UNMEASURED"}
    called = set(net.calls)
    src_key = {"treasury_nominal": "nominal", "treasury_real": "real",
               "nyfed_acm": "acm"}
    for k in held:
        assert src_key[k] not in called, k
        assert "not fetched (fail closed)" in rep["sources"][k]["why"]
    assert allowed | held == set(src_key)


def test_an_unreadable_terms_ledger_holds_everything(monkeypatch):
    monkeypatch.setitem(sys.modules, "libs.research.equivalence_ontology", None)
    assert ris.ledger_terms_verdict(ris.ACM_URL) == "HELD"
    net = FakeNet()
    series, log = ris.collect(AS_OF, fetch=net, now=NOW)
    assert net.calls == []
    rep = ris.build(series, log, AS_OF, NOW)
    assert rep["status"] == "UNMEASURED"


@pytest.mark.parametrize("code", [401, 403, 429, -1])
def test_hard_stop_codes_stop_all_further_requests(code):
    net = FakeNet(codes={"real": code})
    series, log = ris.collect(AS_OF, fetch=net, terms=permit, now=NOW)
    assert net.calls == ["nominal", "nominal", "real"]    # nothing after the stop
    assert log["hard_stop"].startswith("home.treasury.gov ")
    assert "(hard stop)" in log["hard_stop"]
    rep = ris.build(series, log, AS_OF, NOW)
    assert rep["inputs"]["USTREAL10Y"]["status"] == "UNMEASURED"
    assert rep["inputs"]["VIX"]["status"] == "UNMEASURED"
    assert rep["inputs"]["ACMTP10"]["status"] == "UNMEASURED"
    assert rep["metrics"]["curve_curvature_2s5s10s"]["status"] == "MEASURED"
    assert rep["metrics"]["breakeven_10y"]["status"] == "UNMEASURED"


def test_local_acm_file_needs_no_fetch():
    net = FakeNet()
    known = datetime(2026, 10, 7, 9, 0, tzinfo=UTC)
    series, log = ris.collect(AS_OF, fetch=net, terms=lambda u: "HELD", now=NOW,
                              acm_text=(FIX / "acm_sample.csv").read_text(),
                              acm_known_at=known)
    assert net.calls == []
    assert log["sources"]["nyfed_acm"]["via"] == "local file"
    rep = ris.build(series, log, AS_OF, NOW)
    assert rep["metrics"]["term_premium_acm_10y"]["value"] == pytest.approx(0.44)


def test_stale_series_is_marked_stale():
    series, _ = ris.collect(AS_OF, fetch=FakeNet(end=date(2026, 9, 9)), terms=permit, now=NOW)
    out = ris.single("UST10Y", series, AS_OF)
    assert out["status"] == "STALE"
    assert out["freshness"]["age_business_days"] > ris.STALE_BDAYS


def test_short_history_z_is_unmeasured():
    known = datetime(2026, 10, 21, tzinfo=UTC)
    s = ris.parse_columns(_vix(n=50), {"VIX": "CLOSE"}, known, AS_OF)
    assert ris.zscore("VIX", dict(s), AS_OF)["status"] == "UNMEASURED"


def test_report_carries_no_path_and_no_exception_text(tmp_path):
    series, log = ris.collect(AS_OF, fetch=FakeNet(codes={"nominal": -1}), terms=permit,
                              now=NOW)
    rep = ris.build(series, log, AS_OF, NOW)
    blob = json.dumps(rep)
    assert "network error ConnectionError" in rep["hard_stop"]
    assert str(DESK) not in blob and str(tmp_path) not in blob
    assert "Traceback" not in blob and "$" not in blob


def test_write(tmp_path):
    rep = ris.build({}, {}, AS_OF, NOW)
    out = ris.write(rep, tmp_path / "RATES_INDEX_STATE.json")
    assert json.loads(out.read_text())["status"] == "UNMEASURED"


TREASURY = "home.treasury.gov"
NYFED = "www.newyorkfed.org"


def test_robots_is_read_under_the_fetch_user_agent_before_every_permitted_fetch():
    net = FakeNet()
    ris.collect(AS_OF, fetch=net, terms=permit, now=NOW)
    assert set(net.robots_calls) == {TREASURY, NYFED}
    assert len(net.robots_calls) == 2                       # one read per host per run
    src = SRC.read_text(encoding="utf-8")
    assert "can_fetch(USER_AGENT, url)" in src              # the same UA the fetch sends


def test_a_robots_disallow_means_no_fetch():
    net = FakeNet(robots={TREASURY: (200, "User-agent: quant-desk-research\nDisallow: /\n")})
    series, log = ris.collect(AS_OF, fetch=net, terms=permit, now=NOW)
    assert "nominal" not in net.calls and "real" not in net.calls
    assert "acm" in net.calls                               # the other host is unaffected
    assert isinstance(series["UST10Y"], str) and "disallows" in series["UST10Y"]
    assert log["sources"]["treasury_nominal"]["status"] == ris.UNMEASURED


def test_a_path_specific_disallow_is_honoured():
    net = FakeNet(robots={TREASURY: (200, "User-agent: *\nDisallow: /resource-center/\n")})
    ris.collect(AS_OF, fetch=net, terms=permit, now=NOW)
    assert "nominal" not in net.calls and "real" not in net.calls


@pytest.mark.parametrize("code", [401, 403, 429, 500, 503, 301, -1])
def test_unreadable_robots_means_no_fetch_and_a_missed_growth_line(code):
    net = FakeNet(robots={TREASURY: (code, "ConnectionError" if code == -1 else "")})
    series, log = ris.collect(AS_OF, fetch=net, terms=permit, now=NOW)
    assert "nominal" not in net.calls and "real" not in net.calls
    assert isinstance(series["UST10Y"], str) and "unreadable" in series["UST10Y"]
    lines = log["missed_growth"]
    assert lines and all(x["rail"] == "rates_robots_gate" for x in lines)
    assert all(x["verdict"] == "UNMEASURED" and x["value"] is None for x in lines)
    assert {"UST10Y", "USTREAL10Y"} <= {i for x in lines for i in x["inputs"]}
    rep = ris.build(series, log, AS_OF, NOW)
    assert rep["missed_growth"] == lines                    # published on the artifact


def test_absent_robots_is_no_rules_and_allows():
    net = FakeNet(robots={TREASURY: (404, "")})
    _, log = ris.collect(AS_OF, fetch=net, terms=permit, now=NOW)
    assert "nominal" in net.calls and log["missed_growth"] == []


def test_a_redirect_is_never_followed():
    net = FakeNet(redirect={"acm"})
    series, log = ris.collect(AS_OF, fetch=net, terms=permit, now=NOW)
    assert net.calls.count("acm") == 1                      # no second request to a Location
    assert isinstance(series["ACMTP10"], str) and "redirect not followed" in series["ACMTP10"]
    assert log["hard_stop"] is None


def test_http_get_sends_allow_redirects_false(monkeypatch):
    import requests

    seen: dict[str, object] = {}

    class R:
        status_code = 302
        text = ""

    def fake_get(url, **kw):
        seen.update(kw)
        return R()

    monkeypatch.setattr(requests, "get", fake_get)
    assert ris.http_get("https://example.invalid/x")[0] == 302
    assert seen["allow_redirects"] is False
    assert seen["headers"] == {"User-Agent": ris.USER_AGENT}


def test_missed_growth_carries_the_rates_robots_lines():
    src = (DESK / "research" / "missed_growth.py").read_text(encoding="utf-8")
    assert '"rates_robots_gate": organ_published_lines(' in src
    assert "RATES_INDEX_STATE.json" in src
