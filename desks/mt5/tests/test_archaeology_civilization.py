"""The organ: does it run the twenty families, spend the hour by MEASURED ROI, expand recursively
with a recorded stop, register a candidate ground with its access verdict -- and never fetch one
it may not?

NO NETWORK. `moat_collectors.fetch_text` is a recorder that serves fixtures, so every test can
assert on exactly which urls the pass asked for. The registry, the moat and the population table
all live under `tmp_path`.

THE THREE LOAD-BEARING TESTS.

`test_only_an_access_control_never_reaches_the_fetch_door` is the access boundary, asserted at the
door rather than in a comment. IT NARROWED ON 2026-09-23 (LAWS 5e): it used to admit only
`allowed`, with `unknown` resolving to NOT FETCHED; now a `forbidden` or `unknown` POLICY is a
label the row carries and the ground is mined, and only a host the desk would have to break into
-- a login, a paywall, an antibot challenge -- is refused.

`test_the_budget_follows_measured_roi_and_still_explores` asserts the hour is not spent evenly: a
ground with measured independent survivors outranks one with none, and a ground nobody has
measured still draws the exploration prior rather than starving.

`test_the_recursive_expansion_records_why_it_stopped` is the one that makes the expansion
auditable: "ran out of budget" and "ran out of value" are the same empty frontier to a later
reader and imply opposite next actions.
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
import source_frontier as sf  # noqa: E402
from archaeology import civilization as civ  # noqa: E402
from archaeology import snapshots as snap  # noqa: E402

from libs.moat import registry as R  # noqa: E402

SIGNALS_PAGE = """<html><body>
<a href="/en/signals/100001" class="signal-card">Gold Asia Scalper Growth: 120% Drawdown: 15%
 Win rate: 65% Profit factor: 1.4 Trades: 300</a>
<a href="/en/signals/100002" class="signal-card">Euro Grid Recovery Growth: 40% Drawdown: 55%
 Win rate: 92% Profit factor: 1.1 Trades: 900</a>
<a href="/en/signals/100003" class="signal-card">London Breakout Growth: 75% Drawdown: 22%
 Win rate: 44% Profit factor: 1.6 Trades: 210</a>
<a href="/en/signals/100004" class="signal-card">Silver Carry Growth: 12% Drawdown: 6%
 Win rate: 58% Profit factor: 1.2 Trades: 40</a>
<a href="/en/signals/100005" class="signal-card">NY Momentum Growth: 55% Drawdown: 18%
 Win rate: 48% Profit factor: 1.5 Trades: 120</a>
<a href="/en/signals/100006" class="signal-card">Grid Martingale Pro Growth: 30% Drawdown: 70%
 Win rate: 95% Profit factor: 1.05 Trades: 1400</a>
</body></html>"""
#: The market listing: a product's price, version and changelog are the evolution family's input.
MARKET_PAGE = """<html><body>
<a href="/en/market/product/200001" class="product-card">Gold Asia EA Price: 199 Version: 4.20
 Reviews: 88 Rating: 4.6 Trades: 0 Author: fx_lab_tokyo</a>
<a href="/en/market/product/200002" class="product-card">Euro Grid Recovery EA Price: 49
 Version: 1.30 Reviews: 410 Rating: 3.1 Author: grid_master</a>
<a href="/en/market/product/200003" class="product-card">London Breakout Pro Price: 129
 Version: 2.05 Reviews: 61 Rating: 4.1 Author: lnd_breakout</a>
</body></html>"""
#: The codebase listing: author, downloads and publication date -- the lineage family's input.
CODE_PAGE = """<html><body>
<a href="/en/code/30001" class="code-card">Session Range Breakout Author: fx_lab_tokyo
 Downloads: 4200 Rating: 4.4 Published: 2019</a>
<a href="/en/code/30002" class="code-card">Martingale Recovery Grid Author: grid_master
 Downloads: 15100 Rating: 2.9 Published: 2016</a>
</body></html>"""
#: A forum thread where the account was blown -- the graveyard's own vocabulary, three languages.
FORUM_PAGE = """<html><body>
<a href="/t/1001" class="topic">EA died after the broker change, margin call in one night</a>
<a href="/t/1002" class="topic">Backtest failed live and the spread destroyed strategy</a>
<p>Русский: слил депозит за неделю. 中文: 爆仓了, 策略失效.</p>
</body></html>"""


@pytest.fixture
def desk(tmp_path, monkeypatch):
    monkeypatch.setattr(mc, "MOAT", tmp_path / "moat")
    monkeypatch.setattr(mc, "SLEEP_S", 0.0)
    monkeypatch.setattr(snap, "POPULATION", tmp_path / "archaeology" / "population.jsonl")
    monkeypatch.setattr(civ, "REPORT", tmp_path / "reports" / "TRADING_ARCHAEOLOGY.json")
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup")
    R.set_path(tmp_path / "alpha_registry.sqlite")
    calls: list[str] = []

    def _fetch(url: str, lang: str = "") -> tuple[str, int, str]:
        calls.append(url)
        if "signals" in url:
            return SIGNALS_PAGE, 200, ""
        if "forum" in url:
            return FORUM_PAGE, 200, ""
        if url.endswith("robots.txt"):
            return "User-agent: *\nDisallow: /private\n", 200, ""
        return "", 404, "fixture has no body for this url"

    monkeypatch.setattr(mc, "fetch_text", _fetch)
    c = R.connect()
    yield {"root": tmp_path, "calls": calls, "conn": c}
    c.close()
    R.set_path(None)


def _fixtures() -> dict[str, list[tuple[str, str]]]:
    return {"mql5_signals": [("https://www.mql5.com/en/signals", SIGNALS_PAGE)],
            "forexfactory": [("https://www.forexfactory.com/forum", FORUM_PAGE)],
            "mql5_market": [("https://www.mql5.com/en/market/mt5", MARKET_PAGE)],
            "mql5_codebase": [("https://www.mql5.com/en/code", CODE_PAGE)]}


def _fixtures_minimal() -> dict[str, list[tuple[str, str]]]:
    """Two grounds only. The expansion test needs a frontier that still has value left in it:
    with four grounds in reach the walk exhausts the frontier before value decays, which is a
    different (and also correct) stop reason -- and the test is about the VALUE stop."""
    return {"mql5_signals": [("https://www.mql5.com/en/signals", SIGNALS_PAGE)],
            "forexfactory": [("https://www.forexfactory.com/forum", FORUM_PAGE)]}


# --------------------------------------------------------------------------- the twenty families
def test_the_twenty_families_are_declared_and_every_one_is_dispositioned(desk):
    assert len(civ.FAMILIES) == 20
    names = [f.name for f in civ.FAMILIES]
    assert len(set(names)) == 20
    got = civ.run(budget_s=60.0, fetch=False, fixtures=_fixtures(), conn=desk["conn"],
                  at="2026-09-01")
    assert len(got["families"]) == 20
    for fam in got["families"]:
        assert fam["ran"] is True or fam["why"], (
            f"{fam['name']} neither ran nor said why: an empty family with no reason is the "
            "silence the laws forbid")
        assert fam["what"] and fam["stage"]
    assert got["families_ran"] >= 10, got["families_unmeasured"]


def test_a_pass_populates_the_report_the_mandate_asks_for(desk):
    got = civ.run(budget_s=60.0, fetch=False, fixtures=_fixtures(), conn=desk["conn"],
                  at="2026-09-01")
    for key in ("at", "platforms", "population", "archetypes", "survivorship", "decompiled",
                "discoveries_recorded", "synthesis_top", "negative_space_top", "crowding_top",
                "source_scout", "unmeasured", "rule"):
        assert key in got, key
    assert got["rule"].startswith("public trading history is a prior generator")
    by_platform = got["population"]["by_platform"]
    # The count is the FIXTURES' own total, derived rather than typed: a magic number here turns
    # every future fixture into a test failure that says nothing about the organ.
    assert got["population"]["n"] == sum(v["n"] for v in by_platform.values()), got["population"]
    assert got["population"]["n"] >= 9, got["population"]
    assert got["population"]["by_platform"]["mql5_signals"]["n"] == 6
    assert got["archetypes"], "six planted records must cluster into named archetypes"
    assert got["decompiled"] == len(got["archetypes"])
    assert got["discoveries_recorded"] > 0
    assert got["explanation_table"]
    rows = R.discoveries(state="UNPROCESSED", conn=desk["conn"])
    assert rows and all(r["source_type"] == "archaeology" for r in rows)
    assert all(str(r["generator"]).startswith("archaeology:") for r in rows)


def test_the_archive_layer_and_the_three_labels_reach_the_report(desk):
    got = civ.run(budget_s=60.0, fetch=False, fixtures=_fixtures(), conn=desk["conn"],
                  at="2026-09-01")
    layer = got["archive_layer"]
    assert layer["n_grounds"] + layer["n_absences"] == layer["n_cells"]
    assert layer["n_absences"] > 0 and layer["absences"], (
        "the absences are the product: a coverage table with holes reads as completeness")
    assert got["labels"]["access_label"]["PUBLIC_WITH_TERMS"] >= 6
    assert sum(got["labels"]["access_label"].values()) == got["population"]["n"], (
        "every row carries exactly one access label: a row with none is an unclassified source")
    assert (got["labels"]["access_label"]["PUBLIC_SOCIAL"]
            == got["population"]["by_platform"]["forexfactory"]["n"])
    assert got["labels"]["predictive_state"] == {"UNTESTED": got["population"]["n"]}
    assert got["quarantined"] == 0 and got["access_refused_rows"] == 0
    assert got["population"]["usable"] == got["population"]["n"]


# --------------------------------------------------------------------------- the access boundary
def test_only_an_access_control_never_reaches_the_fetch_door(desk):
    """LAWS 5e (2026-09-23). This asserted that NOTHING but `allowed` reached the door, so a
    robots note and an unread policy both silenced a ground. The door is five acts wide now: a
    `forbidden` or `unknown` POLICY is a label and the ground is fetched; a host fronted by an
    antibot challenge, a login or a paywall still is not."""
    civ.run(budget_s=60.0, fetch=True, conn=desk["conn"], at="2026-09-01")
    walled = {p.host for p in snap.PLATFORMS if not snap.may_fetch(p)[0]}
    labelled = {p.host for p in snap.PLATFORMS
                if snap.machine_use(p)[0] != snap.ALLOWED and snap.may_fetch(p)[0]}
    assert walled, "the hard boundary must still name at least one host"
    assert labelled, "a merely-labelled host must exist, or this test proves nothing"
    for url in desk["calls"]:
        host = url.split("/")[2] if "//" in url else ""
        assert host not in walled, f"{url} reached the fetch door past an access control"
    assert any("mql5.com" in u for u in desk["calls"]), "an ALLOWED ground was still fetched"
    assert any(h in u for u in desk["calls"] for h in labelled), (
        "a ground carrying only a policy LABEL must now be fetched")


def test_the_pass_reports_every_platform_it_did_not_read(desk):
    got = civ.run(budget_s=60.0, fetch=False, fixtures=_fixtures(), conn=desk["conn"],
                  at="2026-09-01")
    by_platform = got["population"]["by_platform"]
    assert set(by_platform) == {p.name for p in snap.PLATFORMS}
    assert by_platform["myfxbook"]["machine_use_allowed"] == snap.FORBIDDEN
    assert by_platform["collective2"]["machine_use_allowed"] == snap.UNKNOWN
    assert len(got["unmeasured"]) >= len(snap.PLATFORMS) - len(_fixtures()), (
        "every platform the pass did not read is named, never a silent zero")


# --------------------------------------------------------------------------- budgets by ROI
def test_the_budget_follows_measured_roi_and_still_explores(desk):
    c = desk["conn"]
    sf.bump_source_yield(civ.source_id_of("mql5_signals"), conn=c,
                         independent_survivors=5, survivors=7, claims=40, compute_s=10.0)
    rows = civ.platform_budgets(list(snap.PLATFORMS), 300.0, c)
    assert rows[0]["platform"] == "mql5_signals" and rows[0]["measured"] is True
    assert rows[0]["budget_s"] > rows[-1]["budget_s"] * 5
    unmeasured = [r for r in rows if not r["measured"]]
    assert unmeasured and all(r["budget_s"] >= civ.MIN_PLATFORM_S for r in unmeasured), (
        "an unmeasured ground draws the exploration prior; it is never starved to zero")
    assert all("UNMEASURED" in r["basis"] for r in unmeasured)
    assert rows[0]["roi"][0] == pytest.approx(0.5), "independent survivors per compute second"


def test_source_roi_is_lexicographic_so_volume_cannot_buy_rank(desk):
    chatty = mc.source_roi({"claims": 100000, "compute_s": 10.0})
    good = mc.source_roi({"independent_survivors": 1, "compute_s": 10.0})
    assert good > chatty, "one independent survivor outranks a hundred thousand claims"


# --------------------------------------------------------------------------- the source scout
def test_the_scout_registers_candidates_with_their_access_verdict(desk):
    c = desk["conn"]
    got = civ.scout(c, fetch=False, limit=60)
    assert got["n_candidates"] == len(snap.PLATFORMS)
    by_id = {s["source_id"]: s for s in got["scored"]}
    fine = by_id[civ.source_id_of("mql5_signals")]
    assert fine["machine_use_allowed"] == snap.ALLOWED and fine["fetchable"] is True
    walled = by_id[civ.source_id_of("myfxbook")]
    assert walled["fetchable"] is False, "an antibot challenge is hard-boundary act 2"
    assert walled["hard_boundary"] in snap.BOUNDARY_MARKERS
    assert walled["costs"]["legal_access_cost"] == 1.0
    assert walled["v_s"] < fine["v_s"], "a refusal is priced, not filtered"
    assert civ.source_id_of("myfxbook") in got["never_fetched"]
    # The registry now carries every candidate with its verdict on the row. LAWS 5e
    # (2026-09-23): collective2's policy is merely UNREAD, which used to make it a
    # never-fetched `candidate` with a NOT FETCHED licence note. It is ACTIVE and mined now,
    # and the unread policy travels as a terms note.
    rows = sf.sources(conn=c)
    assert civ.source_id_of("collective2") in rows
    meta = json.loads(rows[civ.source_id_of("collective2")]["meta_json"])
    assert meta["machine_use_allowed"] == snap.UNKNOWN
    assert meta["terms_note"], "the unread policy is recorded, not forgotten"
    assert rows[civ.source_id_of("collective2")]["status"] == "active"
    assert "NOT FETCHED" not in rows[civ.source_id_of("collective2")]["licence_note"]
    assert rows[civ.source_id_of("mql5_signals")]["status"] == "active"
    assert "hard boundary" in rows[civ.source_id_of("myfxbook")]["licence_note"].lower()


def test_v_s_names_every_factor_and_every_cost(desk):
    got = civ.v_s({"kind": "track_record", "verification_class": "broker_verified",
                   "machine_use_allowed": snap.ALLOWED})
    assert set(got["factors"]) == {"observability", "verification", "mechanism_inferability",
                                   "novelty", "p_useful_descendant"}
    assert set(got["costs"]) == {"selection_bias", "collection_cost", "legal_access_cost",
                                 "total"}
    assert "UNMEASURED" in got["p_useful_basis"]
    # Novelty falls as the host fills up; a measured host raises P(useful descendant).
    crowded = civ.v_s({"kind": "track_record", "verification_class": "broker_verified",
                       "machine_use_allowed": snap.ALLOWED}, known_on_host=9)
    assert crowded["v_s"] < got["v_s"]
    paid = civ.v_s({"kind": "track_record", "verification_class": "broker_verified",
                    "machine_use_allowed": snap.ALLOWED},
                   host_yield={"independent_survivors": 4, "compute_s": 10.0})
    assert paid["v_s"] > got["v_s"] and "measured" in paid["p_useful_basis"]


def test_an_unread_policy_is_unknown_and_the_ground_is_mined_anyway(desk):
    """LAWS 5e (2026-09-23): the verdict still says UNKNOWN -- that is honest -- but the reason
    no longer says "not fetched". An unread policy is UNMEASURED, and UNMEASURED is not a
    prohibition."""
    verdict, why = civ._machine_use_from_robots("https://example.org/x", fetch=False)
    assert verdict == snap.UNKNOWN
    assert "mined all the same" in why and "not fetched" not in why
    assert desk["calls"] == [], "--no-fetch must not read even a robots.txt"
    ok, _why = civ._machine_use_from_robots("https://example.org/x", fetch=True)
    assert ok == snap.ALLOWED
    assert desk["calls"] == ["https://example.org/robots.txt"]


# --------------------------------------------------------------------------- expansion
def test_the_recursive_expansion_records_why_it_stopped(desk):
    def neighbours(node):
        if node["hop"] >= 3:
            return []
        return [{"name": f"{node['name']}-{i}", "url": f"https://h{node['hop']}{i}.example",
                 "v_s": 1.0} for i in range(2)]

    # The floor is the best alternative the hour could buy instead. At 0.3, three hops of
    # equally-rated neighbours (0.65 ** 3 = 0.275) fall below it, so the VALUE stop is reachable
    # inside this walk -- which is the property under test, not the constant.
    got = civ.expand_recursively(
        [{"name": "seed", "url": "https://seed.example", "v_s": 1.0}],
        neighbours=neighbours, opportunity_floor=0.3, max_nodes=50)
    assert got["status"] == "measured"
    assert got["n_visited"] > 1 and got["n_discovered"] > 0
    assert set(got["by_hop_kind"]) <= set(civ.EXPANSION_LADDER)
    reasons = set(got["stopped_by_reason"])
    assert reasons, "an expansion that ends must say why"
    assert reasons <= {"marginal_value_below_opportunity", "node_budget", "hop_ladder_exhausted",
                       "frontier_exhausted"}
    assert "marginal_value_below_opportunity" in reasons, (
        "value decays with each hop; the walk must stop on VALUE, not only on budget")
    for stop in got["stops"]:
        assert stop["why"], "a stop with no reason is the silence this test exists to prevent"


def test_the_expansion_stop_distinguishes_budget_from_value(desk):
    def neighbours(node):
        return [{"name": f"{node['name']}-{i}", "url": f"https://x{node['hop']}{i}.example",
                 "v_s": 1.0} for i in range(3)]

    starved = civ.expand_recursively([{"name": "s", "url": "https://s.example", "v_s": 1.0}],
                                     neighbours=neighbours, opportunity_floor=0.0, max_nodes=5)
    assert "node_budget" in starved["stopped_by_reason"]
    assert any("OWED" in s["why"] for s in starved["stops"])
    rich = civ.expand_recursively([{"name": "s", "url": "https://s.example", "v_s": 1.0}],
                                  neighbours=lambda _n: [], opportunity_floor=0.0, max_nodes=50)
    assert rich["stopped_by_reason"] == {"frontier_exhausted": 1}


def test_an_expansion_with_no_seed_is_unmeasured(desk):
    got = civ.expand_recursively([], neighbours=lambda _n: [], opportunity_floor=0.1)
    assert got["status"] == "UNMEASURED" and "no recovered source" in got["why"]


def test_the_pass_expands_and_reports_the_stop(desk):
    got = civ.run(budget_s=60.0, fetch=False, fixtures=_fixtures(), conn=desk["conn"],
                  at="2026-09-01")
    exp = got["expansion"]
    assert exp["status"] == "measured"
    assert exp["ladder"] == list(civ.EXPANSION_LADDER)
    assert exp["stopped_by_reason"], "every branch that ended named its reason"
    assert exp["opportunity_floor"] >= 0.0


# --------------------------------------------------------------------------- the small families
def test_the_failure_vocabulary_finds_the_graveyard_in_its_own_languages(desk):
    got = civ.failure_scan([FORUM_PAGE])
    assert got["status"] == "measured"
    assert "margin call" in got["by_language"]["en"]
    assert "слил депозит" in got["by_language"]["ru"]
    assert "爆仓" in got["by_language"]["zh"]
    assert set(got["languages"]) >= {"en", "ru", "zh", "ja", "ko", "es", "pt"}
    assert civ.failure_scan([])["status"] == "UNMEASURED"


def test_lineage_links_one_author_across_platforms(desk):
    pop = [{"platform": "mql5_market", "system_id": "p1", "raw": {"author": "ivanov"}},
           {"platform": "forexfactory", "system_id": "t9", "raw": {"author": "ivanov"}},
           {"platform": "mql5_signals", "system_id": "s3", "raw": {"author": "solo"}}]
    got = civ.lineage(pop)
    assert got["status"] == "measured" and got["n_chains"] == 1
    chain = got["cross_platform"][0]
    assert chain["author"] == "ivanov" and chain["platforms"] == ["forexfactory", "mql5_market"]
    assert civ.lineage([])["status"] == "UNMEASURED"


def test_the_explosion_is_budgeted_never_cartesian(desk):
    import transformation_miners as TM
    parents = [{"discovery_id": f"d{i}", "symbol": "XAUUSD", "family": "range_reversion",
                "chart": "H1", "session": "asia", "mechanism_id": "range_reversion",
                "information": "price_only", "horizon": "sub_4h", "params": {"entry_z": 2.0}}
               for i in range(3)]
    ctx = TM.Context(instruments={"commodities": ["XAUUSD", "XAGUSD"]}, max_per_miner=3)
    got = civ.explode(parents, ctx, budget=9, conn=desk["conn"])
    assert got["status"] == "measured"
    assert got["n_children"] <= 9, "the budget is a cap, and it holds"
    assert got["pulls"], "the UCB walk records which parents it spent the budget on"
    assert "Cartesian" in got["method"]
    assert civ.explode([], ctx)["status"] == "UNMEASURED"


# --------------------------------------------------------------------------- dry run and the CLI
def test_a_dry_run_writes_nothing_anywhere(desk):
    got = civ.run(budget_s=60.0, dry_run=True, fetch=False, fixtures=_fixtures(),
                  conn=desk["conn"], at="2026-09-01")
    assert got["dry_run"] is True
    assert got["population"]["n"] == sum(
        v["n"] for v in got["population"]["by_platform"].values()), (
        "a dry run still MEASURES; it just does not write")
    assert got["population"]["n"] >= 9
    assert not snap.POPULATION.exists(), "no population row was appended"
    assert R.discoveries(conn=desk["conn"]) == [], "no discovery was recorded"
    assert not civ.REPORT.exists()
    assert R.memories(conn=desk["conn"]) == []
    assert got["discoveries_recorded"] == 0


def test_the_cli_writes_the_report_and_dry_run_does_not(desk):
    rc = civ.main(["--budget-s", "45", "--no-fetch", "--dry-run"])
    assert rc == 0 and not civ.REPORT.exists()
    rc = civ.main(["--budget-s", "45", "--no-fetch", "--once"])
    assert rc == 0 and civ.REPORT.exists()
    doc = json.loads(civ.REPORT.read_text(encoding="utf-8"))
    assert doc["rule"] == civ.RULE
    assert len(doc["families"]) == 20
    assert doc["fetch"] is False
    assert doc["population"]["n"] == 0, "no fixtures and no network: an honest empty pass"
    assert doc["unmeasured"], "and it says, platform by platform, what it did not read"
