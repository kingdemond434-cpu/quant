"""The population archive: is a capture really immutable, does the watchtower see a disappearance,
and is a ground the desk may not fetch really never fetched.

EVERY FETCH IS STUBBED. The module's one door to the network is `moat_collectors.fetch_text`
(which wraps the desk's single http client), and it is replaced here with a recorder, so no test
reaches a host AND every test can assert on exactly which urls the pass would have asked for.

THE THREE LOAD-BEARING TESTS.

`test_a_capture_is_never_overwritten` plants different bytes at the content-addressed path and
asserts the archive REFUSES. An archive with a repair path is a cache, and the point of keeping
the population is that a page which changed under the desk cannot change what the desk recorded.

`test_diff_sees_a_disappearance` is the whole reason the loser rows are kept: a system that is no
longer listed is the numerator of P(survive | phi), and it is invisible to anybody reading the
page today.

`test_a_platform_behind_an_access_control_is_never_fetched` asserts the access boundary holds at
the fetch door and not merely in a comment. THE BOUNDARY NARROWED ON 2026-09-23 (LAWS 5e): it is
five ACTS wide, so a robots note, an unread terms page and an `unknown` policy are LABELS the row
carries and the ground is mined; only something the desk would have to DEFEAT -- a login, a
paywall, an antibot challenge -- still refuses.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_ROOT), str(_DESK), str(_DESK / "research"), str(_DESK / "side_channels")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import moat_collectors as mc  # noqa: E402
from archaeology import snapshots as snap  # noqa: E402

#: MQL5-signals shape: linked cards whose text carries the platform's own published statistics.
SIGNALS_PAGE = """<html><body>
<a href="/en/signals/100001" class="signal-card">Gold Asia Scalper Growth: 120% Drawdown: 15%
 Win rate: 65% Profit factor: 1.4 Trades: 300 Subscribers: 42</a>
<a href="/en/signals/100002" class="signal-card">Euro Grid Recovery Growth: 40% Drawdown: 55%
 Win rate: 92% Profit factor: 1.1 Trades: 900 Subscribers: 8</a>
<a href="/en/signals/100003" class="signal-card">London Breakout Growth: 75% Drawdown: 22%
 Win rate: 44% Profit factor: 1.6 Trades: 210 Subscribers: 17</a>
<a href="/en/about" class="footer-link">About</a>
</body></html>"""
#: The same page a week later: 100002 is gone (delisted), 100004 has appeared, 100001 has moved.
SIGNALS_PAGE_LATER = """<html><body>
<a href="/en/signals/100001" class="signal-card">Gold Asia Scalper Growth: 150% Drawdown: 18%
 Win rate: 64% Profit factor: 1.5 Trades: 340 Subscribers: 51</a>
<a href="/en/signals/100003" class="signal-card">London Breakout Growth: 70% Drawdown: 24%
 Win rate: 43% Profit factor: 1.5 Trades: 250 Subscribers: 15</a>
<a href="/en/signals/100004" class="signal-card">Silver Carry Growth: 12% Drawdown: 6%
 Win rate: 58% Profit factor: 1.2 Trades: 40 Subscribers: 1</a>
</body></html>"""
#: A competition-standings shape: the organiser's own table, a rank per row.
STANDINGS_PAGE = """<html><body><h1>2019 standings</h1><table>
<tr><th>Trader</th><th>Return</th><th>Drawdown</th></tr>
<tr><td><a href="/t/ivanov">Ivanov</a></td><td>214%</td><td>31%</td></tr>
<tr><td><a href="/t/tanaka">Tanaka</a></td><td>98%</td><td>12%</td></tr>
</table></body></html>"""
#: A code-listing shape: a JSON search result, the way a repository API answers.
REPOS_JSON = json.dumps({"items": [
    {"full_name": "someone/mt5-session-breakout", "stars": 31, "archived": 0,
     "html_url": "https://example.org/r/1"},
    {"full_name": "someone/dead-grid-ea", "stars": 4, "archived": 1,
     "html_url": "https://example.org/r/2"}]})


@pytest.fixture
def archive(tmp_path, monkeypatch):
    """The whole store pointed at `tmp_path`, and the network door replaced by a recorder."""
    monkeypatch.setattr(mc, "MOAT", tmp_path / "moat")
    monkeypatch.setattr(snap, "POPULATION", tmp_path / "archaeology" / "population.jsonl")
    calls: list[str] = []

    def _fetch(url: str, lang: str = "") -> tuple[str, int, str]:
        calls.append(url)
        if "signals" in url:
            return SIGNALS_PAGE, 200, ""
        return "", 0, "fixture has no body for this url"

    monkeypatch.setattr(mc, "fetch_text", _fetch)
    return {"root": tmp_path, "calls": calls}


def _platform(name: str) -> snap.Platform:
    return snap.BY_NAME[name]


def test_the_platform_table_declares_access_and_verification(archive):
    rows = snap.as_rows()
    assert len(rows) == len(snap.PLATFORMS)
    for row in rows:
        assert row["machine_use_allowed"] in (snap.ALLOWED, snap.FORBIDDEN, snap.UNKNOWN)
        assert row["verification_class"] in snap.VERIFICATION
        assert row["access_why"], f"{row['name']} declares an access verdict with no reason"
    # Every family the twenty-family mandate names has at least one declared population.
    families = {r["family"] for r in rows}
    for needed in ("performance_archaeology", "competition_archaeology", "product_archaeology",
                   "code_archaeology", "forum_archaeology", "institutional_archaeology"):
        assert needed in families


def test_a_snapshot_writes_population_rows_and_an_immutable_capture(archive):
    got = snap.snapshot(_platform("mql5_signals"), 30.0, fetch=False,
                        pages=[("https://www.mql5.com/en/signals", SIGNALS_PAGE)], at="2026-09-01")
    assert got["n"] == 3, got
    assert got["captures_new"] == 1
    ids = {r["system_id"] for r in got["rows"]}
    assert ids == {"100001", "100002", "100003"}
    row = next(r for r in got["rows"] if r["system_id"] == "100002")
    assert row["stats"]["drawdown"] == 55.0
    assert row["verification"] == "platform_verified"
    assert row["status"] == "listed"
    # The capture landed under the archaeology layout, named by its own hash.
    day = snap.archive_root() / "mql5_signals" / "2026-09-01"
    files = list(day.glob("*.html"))
    assert len(files) == 1 and files[0].stem == got["captures"][0]
    # And it reached the append-only population table.
    assert len(snap.load_population("mql5_signals", "2026-09-01")) == 3


def test_a_capture_is_never_overwritten(archive):
    path, sha, created = snap.capture("mql5_signals", b"first bytes", "html", at="2026-09-01")
    assert created
    again = snap.capture("mql5_signals", b"first bytes", "html", at="2026-09-01")
    assert again[1] == sha and again[2] is False, "the same bytes must be a no-op, not a rewrite"
    path.write_bytes(b"tampered")
    with pytest.raises(mc.ImmutableCaptureError):
        snap.capture("mql5_signals", b"first bytes", "html", at="2026-09-01")
    assert path.read_bytes() == b"tampered", "the refusal must leave the evidence of tampering"


def test_diff_sees_a_disappearance(archive):
    p = _platform("mql5_signals")
    snap.snapshot(p, 30.0, fetch=False, pages=[("u", SIGNALS_PAGE)], at="2026-09-01")
    snap.snapshot(p, 30.0, fetch=False, pages=[("u", SIGNALS_PAGE_LATER)], at="2026-09-08")
    d = snap.watchtower("mql5_signals")
    assert d["disappeared"] == ["100002"], d
    assert d["appeared"] == ["100004"]
    assert d["n_prev"] == 3 and d["n_cur"] == 3
    assert d["disappearance_rate"] == pytest.approx(1 / 3)
    # The earlier row is never rewritten: it still says `listed` on the day it said it.
    old = snap.load_population("mql5_signals", "2026-09-01")
    assert all(r["status"] == "listed" for r in old)
    changed = {c["system_id"]: c["deltas"] for c in d["changed"]}
    assert changed["100001"]["growth"]["delta"] == pytest.approx(30.0)
    assert "100002" in [r["system_id"] for r in d["disappeared_rows"]]


def test_one_snapshot_is_not_a_cohort(archive):
    snap.snapshot(_platform("mql5_signals"), 30.0, fetch=False, pages=[("u", SIGNALS_PAGE)],
                  at="2026-09-01")
    got = snap.watchtower("mql5_signals")
    assert got["status"] == "UNMEASURED"
    assert "two" in got["why"]


def test_a_platform_behind_an_access_control_is_never_fetched(archive):
    """THE ONE REFUSAL THAT SURVIVED (LAWS 5e, 2026-09-23). myfxbook is `forbidden` because a
    managed antibot CHALLENGE fronts the host -- reading it would mean defeating an access
    control, which is hard-boundary act 2. `forbidden` on its own is only a label now; it is the
    marker in the reason that refuses."""
    forbidden = _platform("myfxbook")
    ok, why = snap.may_fetch(forbidden)
    assert ok is False and "hard boundary" in why.lower()
    assert snap.boundary_hit(forbidden.note) in snap.BOUNDARY_MARKERS
    got = snap.snapshot(forbidden, 30.0, fetch=True, at="2026-09-01")
    assert got["rows"] == [] and got["refused"]
    assert got["fetched"] == 0
    assert archive["calls"] == [], "an access control must not reach the fetch door at all"
    assert got["unmeasured"], "the refusal is reported, never a silent zero"


def test_unknown_access_is_a_label_and_the_ground_is_fetched(archive):
    """LAWS 5e (2026-09-23). This asserted `unknown resolves to NOT FETCHED` until then, on the
    reading that absence of a readable permission is not permission. That was the desk's biggest
    self-imposed discovery brake: an unread policy is UNMEASURED, and UNMEASURED is not a
    prohibition. collective2 is fetched now and carries `unknown` as provenance."""
    unknown = _platform("collective2")
    assert snap.machine_use(unknown)[0] == snap.UNKNOWN
    ok, why = snap.may_fetch(unknown)
    assert ok is True and "unknown" in why
    got = snap.snapshot(unknown, 30.0, fetch=True, at="2026-09-01")
    assert got["fetched"] == 1 and archive["calls"] == [unknown.root]
    assert got["refused"] == ""
    assert got["machine_use_allowed"] == snap.UNKNOWN


def test_an_allowed_platform_reaches_the_fetch_door(archive):
    got = snap.snapshot(_platform("mql5_signals"), 30.0, fetch=True, at="2026-09-01")
    assert archive["calls"] == ["https://www.mql5.com/en/signals"]
    assert got["fetched"] == 1 and got["n"] == 3


def test_no_fetch_with_no_fixture_is_unmeasured_not_empty(archive):
    got = snap.snapshot(_platform("mql5_signals"), 30.0, fetch=False, at="2026-09-01")
    assert got["rows"] == [] and archive["calls"] == []
    assert any("UNMEASURED" in u for u in got["unmeasured"])
    assert not snap.POPULATION.exists(), "an unmeasured platform writes no population rows"


def test_standings_and_json_shapes_parse(archive):
    comp = _platform("world_cup_championship")
    rows = snap.parse_standings(STANDINGS_PAGE, comp)
    assert [r["system_id"] for r in rows] == ["ivanov", "tanaka"]
    assert rows[0]["stats"]["rank"] == 1.0 and rows[0]["stats"]["year"] == 2019.0
    assert rows[0]["stats"]["return"] == 214.0
    code = _platform("github_strategies")
    repos = snap.parse_json_rows(REPOS_JSON, code)
    assert [r["system_id"] for r in repos] == ["someone/mt5-session-breakout",
                                               "someone/dead-grid-ea"]
    assert repos[1]["stats"]["archived"] == 1.0, "a dead repository is a row, not an omission"


def test_summary_names_what_is_fetchable_and_what_is_not(archive):
    snap.snapshot(_platform("mql5_signals"), 30.0, fetch=False, pages=[("u", SIGNALS_PAGE)],
                  at="2026-09-01")
    s = snap.summary()
    assert s["n_rows"] == 3
    assert "mql5_signals" in s["fetchable"]
    # LAWS 5e (2026-09-23): `never_fetched` is the five-acts list now, and `collective2` --
    # whose policy is merely UNREAD -- moved out of it into `policy_labelled`.
    assert "myfxbook" in s["never_fetched"]
    assert "collective2" not in s["never_fetched"]
    assert "collective2" in s["policy_labelled"]
    assert s["by_platform"]["mql5_signals"]["snapshots"] == ["2026-09-01"]


# --------------------------------------------------------------------------- the archive layer
def test_every_archive_cell_is_a_ground_or_a_named_absence(archive):
    layer = snap.archive_layer()
    assert layer["n_cells"] == len(snap.ARCHIVE_REGIONS) * len(snap.ARCHIVE_KINDS)
    assert layer["n_grounds"] + layer["n_absences"] == layer["n_cells"]
    for cell in layer["cells"]:
        assert cell["state"] in ("GROUND", "NAMED_ABSENCE")
        assert cell["note"] or cell["url"], (
            f"{cell['region']}/{cell['archive_kind']} is a blank cell: a hole in a coverage "
            "table reads as completeness to anybody who skims")
    kinds = {c["archive_kind"] for c in layer["cells"]}
    for needed in ("dead_forums", "historical_pages", "broker_education_portals",
                   "retired_ea_listings", "delisted_strategies", "old_research_blogs",
                   "abandoned_code_repos", "archived_competition_results", "vanished_newsletters",
                   "fund_failures", "public_performance_archives"):
        assert needed in kinds
    # A ground the desk declares but cannot locate is still NAMED, with the reason.
    named_absences = [c for c in layer["cells"] if c["state"] == "NAMED_ABSENCE" and c["name"]]
    assert any("deep_forest" in c["name"] for c in named_absences)


# --------------------------------------------------------------------------- the three labels
def test_every_recovered_row_carries_the_three_labels(archive):
    got = snap.snapshot(_platform("mql5_signals"), 30.0, fetch=False,
                        pages=[("u", SIGNALS_PAGE)], at="2026-09-01")
    for row in got["rows"]:
        assert row["access_label"] in snap.ACCESS_LABELS
        assert row["credibility"] in snap.CREDIBILITY_LABELS
        assert row["predictive_state"] == "UNTESTED", "only the gauntlet may move this"
        assert 0.0 < row["evidence_weight"] <= 1.0
        assert row["usable"] is True


def test_the_three_labels_are_independent(archive):
    """Fringe material on an open ground is USABLE at low weight; authoritative material on a
    private one is not usable at all. One collapsed 'quality' field could not say both."""
    fringe = snap.labels("OPEN_DATA", "FRINGE")
    assert fringe["usable"] is True and fringe["evidence_weight"] < 0.15
    private = snap.labels("PRIVATE", "AUTHORITATIVE")
    assert private["usable"] is False and private["refused"] is True
    assert private["evidence_weight"] == 0.0
    contradicted = snap.labels("PUBLIC_ARCHIVE", "CONTRADICTED")
    assert contradicted["usable"] is True, "false-looking public material is kept, not discarded"
    assert contradicted["evidence_weight"] > 0.0


def test_access_unclear_is_usable_and_labelled_not_quarantined(archive):
    """LAWS 5e (2026-09-23). This test pinned the quarantine: ACCESS_UNCLEAR rows were kept but
    `usable is False`, excluded from every downstream use, and priced at evidence weight 0. All
    three were the same brake wearing three hats. The row is USABLE now, at the weight its
    CREDIBILITY earns, with the unresolved access path attached as a note."""
    unclear = snap.labels("ACCESS_UNCLEAR", "RELIABLE")
    assert unclear["quarantined"] is False and unclear["usable"] is True
    assert unclear["refused"] is False
    assert unclear["evidence_weight"] > 0.0, "access has nothing to say about truth"
    assert "access path unresolved" in unclear["terms_note"]
    assert not snap.ACCESS_QUARANTINE
    p = _platform("prop_leaderboards")
    assert p.access == "ACCESS_UNCLEAR"
    row = snap.normalise(p, {"system_id": "x1", "stats": {"return": 10.0}}, "2026-09-01")
    assert row["quarantined"] is False and row["usable"] is True
    assert row["stats"] == {"return": 10.0}, "the row is KEPT and it is now also USED"


def test_private_and_stolen_material_is_never_recorded(archive):
    p = snap.Platform("leaked", "https://example.org/x", "track_record", snap.ALLOWED,
                      "broker_verified", ("growth",), access_label="STOLEN_UNAUTHORIZED")
    got = snap.snapshot(p, 30.0, fetch=False,
                        pages=[("u", '<html><a href="/s/9" class="signal">X Growth: 10%</a>'
                                     "</html>")], at="2026-09-01")
    assert got["rows"] == [] and got["refused_rows"] == 1
    assert not snap.POPULATION.exists(), "unauthorised material leaves no row at all"
    assert snap.labels("CONFIDENTIAL_MNPI", "AUTHORITATIVE")["refused"] is True


def test_a_wall_may_tighten_access_but_never_loosen_it(archive):
    """myfxbook is declared forbidden here and the desk's wall ledger calls it ANTIBOT_CHALLENGE,
    which alone maps to `unknown`. A wall that made a ground MORE fetchable would be the bug."""
    assert snap.machine_use(_platform("myfxbook"))[0] == snap.FORBIDDEN
    assert snap._STRICTNESS[snap.FORBIDDEN] > snap._STRICTNESS[snap.UNKNOWN]
    assert snap._STRICTNESS[snap.UNKNOWN] > snap._STRICTNESS[snap.ALLOWED]


def test_the_label_census_is_reported(archive):
    snap.snapshot(_platform("mql5_signals"), 30.0, fetch=False, pages=[("u", SIGNALS_PAGE)],
                  at="2026-09-01")
    s = snap.summary()
    assert s["labels"]["access_label"]["PUBLIC_WITH_TERMS"] == 3
    assert s["labels"]["predictive_state"]["UNTESTED"] == 3
    assert s["n_quarantined"] == 0
    assert s["archive_layer"]["n_absences"] > 0
