"""The one robots gate: only PUBLIC fetches, every refusal is a billed SET_ASIDE row, and the
collectors that share it stop on a Disallow (ruling of 2026-11-10, PR #819)."""
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


def test_only_an_allow_or_a_missing_file_is_public() -> None:
    assert rg.read(URL, "a", opener=_serve("User-agent: *\nDisallow: /private/\n"))[0] == "PUBLIC"
    assert rg.read(URL, "a", opener=_serve(""))[0] == "PUBLIC"
    assert rg.read(URL, "a", opener=_fail(_http(404)))[0] == "PUBLIC"
    assert rg.read(URL, "a", opener=_fail(_http(410)))[0] == "PUBLIC"


def test_a_disallow_on_the_exact_path_is_disallowed() -> None:
    label, why = rg.read(URL, "a", opener=_serve("User-agent: *\nDisallow: /data/\n"))
    assert label == "DISALLOWED" and "exact path" in why
    assert rg.read(URL, "a", opener=_fail(_http(403)))[0] == "DISALLOWED"
    # an agent-specific group binds only that agent
    body = "User-agent: other\nDisallow: /\n\nUser-agent: *\nDisallow:\n"
    assert rg.read(URL, "a", opener=_serve(body))[0] == "PUBLIC"
    assert rg.read(URL, "other", opener=_serve(body))[0] == "DISALLOWED"


def test_an_unread_policy_is_never_a_yes() -> None:
    assert rg.read(URL, "a", opener=_fail(_http(503)))[0] == "ACCESS_UNCLEAR"
    assert rg.read(URL, "a", opener=_fail(TimeoutError()))[0] == "ACCESS_UNCLEAR"
    assert rg.read("ftp://example.invalid/x", "a", opener=_serve(""))[0] == "ACCESS_UNCLEAR"


def test_a_refusal_is_a_row_a_ledger_line_and_a_daily_count(_ledger: dict[str, Path]) -> None:
    row = rg.refuse("asia_collector", "src_a", URL, "DISALLOWED", "robots disallows")
    rg.refuse("asia_collector", "src_b", URL + "2", "ACCESS_UNCLEAR", "robots unreadable")
    rg.refuse("shadow_institutional", "src_a", URL, "DISALLOWED", "robots disallows")
    assert row["status"] == "SET_ASIDE" and row["billed"] is True and row["reopen"]
    assert {m["side"] for m in row["missed_growth"]} == {"cost", "gain"}
    assert all(m["verdict"] == "UNMEASURED" and m["value"] is None for m in row["missed_growth"])
    assert len(_ledger["ledger"].read_text("utf-8").splitlines()) == 3
    doc = json.loads(_ledger["report"].read_text("utf-8"))
    (day,) = doc["daily"]
    assert doc["refused_today"] == 3 and doc["daily"][day] == {
        "total": 3, "by_label": {"DISALLOWED": 2, "ACCESS_UNCLEAR": 1},
        "by_organ": {"asia_collector": 2, "shadow_institutional": 1}, "distinct_sources": 2}
    assert [m["fetches_refused"] for m in doc["missed_growth"]] == [3, 3]


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


def test_the_asia_collector_does_not_fetch_on_an_unread_robots_file(
        monkeypatch: pytest.MonkeyPatch) -> None:
    rec, opened = _collect(monkeypatch, ("ACCESS_UNCLEAR", "robots.txt unreadable (HTTP 503)"))
    assert opened == [] and rec["status"] == "BLOCKED_BY_ROBOTS"
    assert rec["access_label"] == "ACCESS_UNCLEAR" and rec["robots_disallows"] is False


def test_the_asia_collector_fetches_a_public_path(monkeypatch: pytest.MonkeyPatch,
                                                  _ledger: dict[str, Path]) -> None:
    rec, opened = _collect(monkeypatch, ("PUBLIC", "no robots.txt (HTTP 404)"))
    assert opened == [URL] and rec["status"] == "UNREACHABLE"
    assert not _ledger["ledger"].exists(), "an allowed fetch is not billed"
