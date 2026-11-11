"""The one robots gate (Governance rulings of 2026-11-10, PR #819): a Disallow on the exact path,
a 401/403 on robots.txt and an unreachable robots.txt each stop the fetch as a billed SET_ASIDE row
under its own label; a site serving no robots.txt is fetched and counted beside the refusals."""
from __future__ import annotations

import json
import urllib.error
from pathlib import Path
from typing import Any

import pytest

from research import asia_collector as acol
from research import missed_growth as mg
from research import robots_gate as rg

URL = "https://example.invalid/data/series.csv"


@pytest.fixture(autouse=True)
def _ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    """No test may write the desk's real robots ledger."""
    paths = {"ledger": tmp_path / "robots_set_aside.jsonl",
             "report": tmp_path / "ROBOTS_SET_ASIDE.json"}
    monkeypatch.setattr(rg, "LEDGER", paths["ledger"])
    monkeypatch.setattr(rg, "REPORT", paths["report"])
    return paths


def _serve(body: str) -> rg.Opener:
    return lambda url, agent, timeout: body


def _fail(exc: Exception) -> rg.Opener:
    def opener(url: str, agent: str, timeout: float) -> str:
        raise exc
    return opener


def _http(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://example.invalid/robots.txt", code, "x",
                                  None, None)  # type: ignore[arg-type]


def test_an_allow_is_public_and_a_missing_file_is_absent() -> None:
    assert rg.read(URL, "a", opener=_serve("User-agent: *\nDisallow: /private/\n"))[0] == "PUBLIC"
    assert rg.read(URL, "a", opener=_serve(""))[0] == "PUBLIC"
    for code in (404, 410, 400):
        label, why = rg.read(URL, "a", opener=_fail(_http(code)))
        assert label == "ROBOTS_ABSENT" and str(code) in why and not rg.stops(label)


def test_a_disallow_on_the_exact_path_is_disallowed() -> None:
    label, why = rg.read(URL, "a", opener=_serve("User-agent: *\nDisallow: /data/\n"))
    assert label == "DISALLOWED" and "exact path" in why and rg.stops(label)
    # an agent-specific group binds only that agent
    body = "User-agent: other\nDisallow: /\n\nUser-agent: *\nDisallow:\n"
    assert rg.read(URL, "a", opener=_serve(body))[0] == "PUBLIC"
    assert rg.read(URL, "other", opener=_serve(body))[0] == "DISALLOWED"
    # RFC 9309 matching from the shared parser: the longest rule wins, Allow wins a tie
    body = "User-agent: *\nDisallow: /data/\nAllow: /data/series.csv\n"
    assert rg.read(URL, "a", opener=_serve(body))[0] == "PUBLIC"
    assert rg.read(URL, "a", opener=_serve("User-agent: *\nDisallow: /*.csv$\n"))[0] == "DISALLOWED"


def test_a_401_or_403_on_robots_is_a_refusal_that_stops() -> None:
    """Governance ruling 2026-11-10 20:08Z: a 401/403 on robots.txt is a refusal aimed at us; a
    429/451 is held with them (a rate limit is never worked around), as in libs/data."""
    for code in (401, 403, 429, 451):
        label, why = rg.read(URL, "a", opener=_fail(_http(code)))
        assert label == "ROBOTS_REFUSED" and str(code) in why and rg.stops(label)


def test_an_unreachable_robots_file_stops_this_pass() -> None:
    for opener in (_fail(_http(503)), _fail(_http(500)), _fail(TimeoutError()),
                   _fail(urllib.error.URLError("dns"))):
        label, why = rg.read(URL, "a", opener=opener)
        assert label == "ROBOTS_UNREACHABLE" and "next pass" in why and rg.stops(label)
    assert rg.read("ftp://example.invalid/x", "a", opener=_serve(""))[0] == "ROBOTS_UNREACHABLE"


def test_a_refusal_is_a_row_a_ledger_line_and_a_daily_count(_ledger: dict[str, Path]) -> None:
    row = rg.refuse("asia_collector", "src_a", URL, "DISALLOWED", "robots disallows")
    rg.refuse("asia_collector", "src_b", URL + "2", "ROBOTS_UNREACHABLE", "robots unreadable")
    rg.refuse("shadow_institutional", "src_a", URL, "DISALLOWED", "robots disallows")
    assert row["status"] == "SET_ASIDE" and row["billed"] is True and row["reopen"]
    assert {m["side"] for m in row["missed_growth"]} == {"cost", "gain"}
    assert all(m["verdict"] == "UNMEASURED" and m["value"] is None for m in row["missed_growth"])
    assert len(_ledger["ledger"].read_text("utf-8").splitlines()) == 3
    doc = json.loads(_ledger["report"].read_text("utf-8"))
    (day,) = doc["daily"]
    assert doc["refused_today"] == 3 and doc["daily"][day] == {
        "total": 3, "by_label": {"DISALLOWED": 2, "ROBOTS_UNREACHABLE": 1},
        "by_organ": {"asia_collector": 2, "shadow_institutional": 1}, "distinct_sources": 2,
        "absent_fetched": 0, "absent_fetched_by_organ": {}}
    assert [m["fetches_refused"] for m in doc["missed_growth"]] == [3, 3]


def test_a_fetch_with_no_robots_file_is_counted_beside_the_refusals_never_among_them(
        _ledger: dict[str, Path]) -> None:
    assert rg.note_absent("asia_collector", "src_c", URL, "no robots.txt (HTTP 404)")
    doc = json.loads(_ledger["report"].read_text("utf-8"))
    (day,) = doc["daily"]
    assert doc["refused_today"] == 0 and doc["absent_fetched_today"] == 1
    assert doc["daily"][day]["absent_fetched_by_organ"] == {"asia_collector": 1}
    assert doc["missed_growth"] == [], "a fetch that was made is not a missed-growth line"
    line = json.loads(_ledger["ledger"].read_text("utf-8").splitlines()[0])
    assert line["status"] == "ABSENT_FETCHED" and line["access_label"] == "ROBOTS_ABSENT"


def test_one_pass_asks_a_host_for_robots_once() -> None:
    asked: list[str] = []

    def opener(url: str, agent: str, timeout: float) -> str:
        asked.append(url)
        return "User-agent: *\nDisallow: /private/\n"

    cache: dict = {}
    assert rg.read(URL, "a", opener=opener, cache=cache)[0] == "PUBLIC"
    assert rg.read("https://example.invalid/private/x", "a", opener=opener,
                   cache=cache)[0] == "DISALLOWED"
    assert asked == ["https://example.invalid/robots.txt"]
    # an unreachable host is asked once a pass and stopped for the rest of it: never a loop
    unread: dict = {}
    assert rg.read(URL, "a", opener=_fail(TimeoutError()), cache=unread)[0] == "ROBOTS_UNREACHABLE"
    assert rg.read(URL, "a", opener=_serve(""), cache=unread)[0] == "ROBOTS_UNREACHABLE"


def test_no_ledger_is_unmeasured_and_a_torn_line_is_counted(_ledger: dict[str, Path]) -> None:
    assert rg.daily_counts()["status"] == "UNMEASURED"
    assert rg.publish()["missed_growth"] == []
    rg.refuse("o", "s", URL, "DISALLOWED", "w")
    with _ledger["ledger"].open("a", encoding="utf-8") as f:
        f.write("{not json\n")
    got = rg.daily_counts()
    assert got["status"] == "OK" and got["torn_lines"] == 1
    assert sum(d["total"] for d in got["days"].values()) == 1


def test_an_unwritable_ledger_is_carried_as_unbilled_never_raised(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    blocker = tmp_path / "a_file"
    blocker.write_text("x", "utf-8")
    monkeypatch.setattr(rg, "LEDGER", blocker / "ledger.jsonl")     # parent is a file
    assert rg.refuse("o", "s", URL, "DISALLOWED", "w")["billed"] is False


def test_missed_growth_carries_the_robots_line(_ledger: dict[str, Path],
                                               monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mg, "ROBOTS_SET_ASIDE", _ledger["report"])
    assert mg.organ_published_lines(mg.ROBOTS_SET_ASIDE)["verdict"] == "UNMEASURED"
    rg.refuse("asia_collector", "src_a", URL, "DISALLOWED", "robots disallows")
    got = mg.organ_published_lines(mg.ROBOTS_SET_ASIDE)
    assert {x["side"] for x in got["lines"]} == {"cost", "gain"}
    assert all(x["rail"] == rg.RAIL for x in got["lines"])


def _collect(monkeypatch: pytest.MonkeyPatch, verdict: tuple[str, str]) -> tuple[dict, list]:
    opened: list[Any] = []

    def _spy(req: Any, **_k: Any) -> Any:
        opened.append(getattr(req, "full_url", req))
        raise urllib.error.URLError("no network in this test")

    monkeypatch.setattr(acol, "_robots_verdict", lambda url, agent="x": verdict)
    monkeypatch.setattr(acol.urllib.request, "urlopen", _spy)
    rec = acol.collect_one({"id": "src_a", "plane": "p", "url": URL, "expect": "csv",
                            "access": "public"})
    return rec, opened


def test_the_asia_collector_does_not_fetch_a_disallowed_path(
        monkeypatch: pytest.MonkeyPatch, _ledger: dict[str, Path]) -> None:
    rec, opened = _collect(monkeypatch, ("DISALLOWED", "robots.txt disallows this exact path"))
    assert opened == [], "the data URL must not be requested"
    assert rec["status"] == "BLOCKED_BY_ROBOTS" and rec["access_label"] == "DISALLOWED"
    assert rec["robots_disallows"] is True and rec["reopen"] and rec["billed"] is True
    assert {m["side"] for m in rec["missed_growth"]} == {"cost", "gain"}
    line = json.loads(_ledger["ledger"].read_text("utf-8").splitlines()[0])
    assert line["organ"] == "asia_collector" and line["source"] == "src_a"


@pytest.mark.parametrize("label", ["ROBOTS_REFUSED", "ROBOTS_UNREACHABLE"])
def test_the_asia_collector_stops_on_a_refused_or_unreachable_robots_file(
        monkeypatch: pytest.MonkeyPatch, _ledger: dict[str, Path], label: str) -> None:
    rec, opened = _collect(monkeypatch, (label, "robots.txt said no"))
    assert opened == [] and rec["status"] == "BLOCKED_BY_ROBOTS"
    assert rec["access_label"] == label and rec["billed"] is True
    line = json.loads(_ledger["ledger"].read_text("utf-8").splitlines()[0])
    assert line["status"] == "SET_ASIDE" and line["access_label"] == label


def test_the_asia_collector_fetches_a_site_with_no_robots_file_and_counts_it(
        monkeypatch: pytest.MonkeyPatch, _ledger: dict[str, Path]) -> None:
    rec, opened = _collect(monkeypatch, ("ROBOTS_ABSENT", "no robots.txt (HTTP 404)"))
    assert opened == [URL] and rec["status"] == "UNREACHABLE"
    assert rec["access_label"] == "ROBOTS_ABSENT" and rec["robots_counted"] is True
    line = json.loads(_ledger["ledger"].read_text("utf-8").splitlines()[0])
    assert line["status"] == "ABSENT_FETCHED" and line["organ"] == "asia_collector"


def test_the_collector_cache_expires_by_age(monkeypatch: pytest.MonkeyPatch) -> None:
    asked: list[str] = []
    monkeypatch.setattr(acol, "_robots_open",
                        lambda url, agent, timeout: asked.append(url) or "")
    monkeypatch.setattr(acol, "_ROBOTS_CACHE", {})
    monkeypatch.setattr(acol, "_ROBOTS_CACHE_BORN", [acol.time.monotonic()])
    acol._robots_verdict(URL)
    acol._robots_verdict(URL + "2")
    assert len(asked) == 1
    monkeypatch.setattr(acol, "_ROBOTS_CACHE_BORN",
                        [acol.time.monotonic() - acol._ROBOTS_CACHE_TTL_S - 1])
    acol._robots_verdict(URL)
    assert len(asked) == 2


def test_the_asia_collector_fetches_a_public_path(monkeypatch: pytest.MonkeyPatch,
                                                  _ledger: dict[str, Path]) -> None:
    rec, opened = _collect(monkeypatch, ("PUBLIC", "robots.txt allows this path"))
    assert opened == [URL] and rec["status"] == "UNREACHABLE"
    assert not _ledger["ledger"].exists(), "an allowed fetch is not billed"


def test_every_matching_user_agent_group_is_combined() -> None:
    """RFC 9309 s2.2.1: a Disallow in a SECOND group naming our agent still binds (it was
    ignored when only the first matching group was read, which failed open)."""
    from libs.data.robots_gate import robots_allows, robots_rules
    txt = ("User-agent: quant-research\nAllow: /\n\n"
           "User-agent: other\nDisallow: /\n\n"
           "User-agent: quant-research\nDisallow: /private\n\n"
           "User-agent: *\nDisallow: /\n")
    rules = robots_rules(txt, "quant-research")
    assert not robots_allows(rules, "https://x.org/private/x")
    assert robots_allows(rules, "https://x.org/public")
    star = robots_rules("User-agent: *\nDisallow: /a\n\nUser-agent: *\nDisallow: /b\n", "q")
    assert not robots_allows(star, "https://x.org/b/1") and not robots_allows(star, "https://x.org/a")
