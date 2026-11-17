"""The onion forest: roster schema and verdicts, the forbidden-kind guard, registration and riding,
the content-shape dump guard, MNPI tagging, the evolving mission, and the Tor installer.

FIXTURES ONLY. No Tor, no .onion host and no clearnet host is contacted: the transport, the
clearnet reader and the Tor status are all injected.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import onion_fetch as OF  # noqa: E402
from libs.research import forests as F  # noqa: E402
from libs.research import mission_evolution as ME  # noqa: E402
from research import onion_forest as OFR  # noqa: E402

HOST = "c" * 56 + ".onion"
FEED = f"http://{HOST}/rss.xml"
PRESENT = {"status": OF.TOR_PRESENT, "proxy": "socks5h://127.0.0.1:9050", "why": "fixture"}
ABSENT = {"status": OF.TOR_ABSENT, "why": "fixture", "missed_growth": OF.MISSED_TOR}


def _roster(tmp_path: Path, rows: list[dict]) -> Path:
    p = tmp_path / "onion_sources.json"
    p.write_text(json.dumps({"sources": rows, "excluded_by_rule": []}), encoding="utf-8")
    return p


def _row(**kw) -> dict:
    base = {"id": "pub", "publisher": "Publisher", "kind": "news_mirror", "language": "en",
            "onion_host": HOST, "feed_urls": [FEED], "address_status": "VERIFIED",
            "address_source": "https://publisher.example/onion", "terms_url":
            "https://publisher.example/terms", "terms_verdict": "ALLOWED",
            "terms_why": "fixture", "attachments": False, "mechanism_note": "fixture"}
    return {**base, **kw}


@pytest.fixture
def paths(tmp_path, monkeypatch):
    monkeypatch.setattr(OFR, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(OFR, "CLAIMS", tmp_path / "claims.jsonl")
    monkeypatch.setattr(OFR, "MISSION_LOG", tmp_path / "missions" / "onion.jsonl")
    monkeypatch.setattr(OFR, "INTEL", tmp_path / "intel")
    donated: list = []
    monkeypatch.setattr(OFR, "_donate", lambda claims, at: (
        donated.append(list(claims)) or {"tasks_queued": len(claims), "intelligence_rows": 0}))
    return tmp_path, donated


# ------------------------------------------------------------------ the committed roster
def test_the_committed_roster_validates_and_every_row_has_a_terms_verdict():
    doc = OFR.load_roster()
    rows = doc["sources"]
    assert len(rows) >= 8
    for r in rows:
        assert r["terms_verdict"] in ("ALLOWED", "BLOCKED_ON_TERMS", "TERMS_UNREAD", "REFUSED")
        assert r["terms_why"] and r["terms_url"] and r["address_source"]
        v, why = OFR.effective_verdict(r, {})
        assert v in OFR.VERDICTS and why
    ids = {r["id"]: r for r in rows}
    assert OFR.effective_verdict(ids["ahmia"], {})[0] == "REFUSED"
    assert "zenodo_tor_onion_graph" in ids
    assert {c["category"] for c in doc["excluded_by_rule"]} >= {"darknet markets",
                                                                "carding sites"}


def test_nothing_unverified_is_ever_fetchable():
    for r in OFR.load_roster()["sources"]:
        if r["address_status"] != "VERIFIED":
            assert OFR.effective_verdict(r, {})[0] != "ALLOWED"


@pytest.mark.parametrize("kind", sorted(OFR.FORBIDDEN_KINDS))
def test_the_roster_cannot_hold_a_market_forum_leak_or_carding_kind(tmp_path, kind):
    with pytest.raises(OFR.RosterError, match="FORBIDDEN"):
        OFR.load_roster(_roster(tmp_path, [_row(kind=kind)]))


def test_feeds_must_be_onion_and_on_the_rows_own_host(tmp_path):
    with pytest.raises(OFR.RosterError, match=r"not a \.onion URL"):
        OFR.load_roster(_roster(tmp_path, [_row(feed_urls=["https://clearnet.example/rss"])]))
    other = "d" * 56 + ".onion"
    with pytest.raises(OFR.RosterError, match="own onion host"):
        OFR.load_roster(_roster(tmp_path, [_row(feed_urls=[f"http://{other}/rss"])]))


def test_effective_verdict_requires_address_and_terms_and_forum_review():
    assert OFR.effective_verdict(_row(), {})[0] == "ALLOWED"
    assert OFR.effective_verdict(_row(address_status="UNVERIFIED_ADDRESS"), {})[0] == \
        "UNVERIFIED_ADDRESS"
    assert OFR.effective_verdict(_row(address_status="UNVERIFIED_ADDRESS"),
                                 {"pub": {"address_verified_host": HOST}})[0] == "ALLOWED"
    assert OFR.effective_verdict(_row(terms_verdict="TERMS_UNREAD"), {})[0] == "TERMS_UNREAD"
    assert OFR.effective_verdict(_row(), {"pub": {"terms_auto": "BLOCKED_ON_TERMS",
                                                  "terms_auto_why": "x"}})[0] == \
        "BLOCKED_ON_TERMS"
    assert OFR.effective_verdict(_row(kind="public_forum"), {})[0] == "REVIEW_PENDING"
    assert OFR.effective_verdict(_row(kind="public_forum", review={
        "login_required": False, "not_market_leak_or_carding": True}), {})[0] == "ALLOWED"


def test_box_reads_verify_verbatim_and_refuse_on_stated_terms_never_allow():
    pages = {"https://publisher.example/onion": (200, f"our onion is {HOST} today"),
             "https://publisher.example/terms": (200, "You must not use robots or scrapers to "
                                                      "extract content.")}
    state: dict = {}
    rows = [_row(address_status="UNVERIFIED_ADDRESS", terms_verdict="TERMS_UNREAD")]
    out = OFR.verify_roster(rows, state, get=lambda u: pages[u], at="t", clock=lambda: 1e9)
    assert out[0]["address_read"]["found_verbatim"] is True
    assert state["pub"]["address_verified_host"] == HOST
    assert OFR.effective_verdict(rows[0], state)[0] == "BLOCKED_ON_TERMS"
    calm = {"https://publisher.example/onion": (200, "no address here"),
            "https://publisher.example/terms": (200, "Be nice.")}
    state2: dict = {}
    OFR.verify_roster(rows, state2, get=lambda u: calm[u], at="t", clock=lambda: 1e9)
    assert OFR.effective_verdict(rows[0], state2)[0] == "UNVERIFIED_ADDRESS"
    state3: dict = {}
    OFR.verify_roster(rows, state3, get=lambda u: (200, HOST if "onion" in u else "Be nice."),
                      at="t", clock=lambda: 1e9)
    assert OFR.effective_verdict(rows[0], state3)[0] == "TERMS_UNREAD", \
        "a machine may read a refusal; it never reads a permission"


# ------------------------------------------------------------------ registration and riding
def test_onion_is_a_registered_evolving_global_forest_riding_regions():
    f = F.forest("onion")
    assert f.kind == "global" and not f.countries and f.evolving and f.languages
    assert f.miner == "research/onion_forest.py" and f.claims_ledger
    assert F.resident_task("onion") == "MT5-Dept-Regions"
    assert "onion" not in F.OWN_RESIDENT
    assert F.mission_log("onion", DESK) == OFR.MISSION_LOG or OFR.MISSION_LOG.name == "onion.jsonl"
    assert all(not g.evolving for fid, g in F.FORESTS.items() if fid != "onion")


def test_the_hourly_cycle_runs_the_onion_leg_on_the_regions_resident():
    src = (DESK / "research" / "hourly_cycle.py").read_text(encoding="utf-8")
    assert '"forest_onion", "research/forest_runner.py", "--forest", "onion"' in src
    from research import hourly_cycle as hc
    assert "forest_onion" in hc.GLOBAL_FOREST_LEGS
    assert hc.LEG_DEPARTMENT.get("forest_onion") == "regions"
    from libs.research import layers
    assert layers.LEG_LAYER.get("forest_onion") == "information"


# ------------------------------------------------------------------ guards and tags
def _luhn_card(prefix: str) -> str:
    digits = [int(c) for c in prefix]
    for check in range(10):
        total = 0
        for i, d in enumerate(reversed([*digits, check])):
            total += (d * 2 - 9 if d * 2 > 9 else d * 2) if i % 2 else d
        if total % 10 == 0:
            return prefix + str(check)
    raise AssertionError


def test_dump_shape_is_content_shape_never_keyword():
    creds = "\n".join(f"user{i}@mail.example:hunter{i}{i}x" for i in range(5))
    assert OFR.dump_shape(creds) == "credential_pairs"
    cards = " ".join(_luhn_card(p) for p in ("400000000000000", "510000000000000",
                                            "601100000000000"))
    assert OFR.dump_shape(cards) == "card_numbers_luhn"
    table = "name,email,phone\n" + "\n".join(f"n{i},p{i}@x.example,555{i}" for i in range(12))
    assert OFR.dump_shape(table) == "bulk_pii_table"
    assert OFR.dump_shape("Leaked memo: insiders say gold will rally; this is a leak.") is None
    assert OFR.dump_shape("Order 1234 5678 9012 3456 was not a card number") is None


def test_claimed_leak_is_a_rumour_claim_and_mnpi_strips_share_cfds():
    c = OFR.tag_claim({"claim": "Leaked: insiders say the merger lifts ACME 8% next week.",
                       "instruments": {"analogues": ["ACME.US", "US500"], "mentioned": []}},
                      is_equity=lambda s: s.endswith(".US"))
    assert c["claim_type"] == "rumour" and c["claimed_leak"] is True
    assert c["mnpi_risk"] is True and c["exclude_share_cfd"] is True
    assert c["instruments"]["analogues"] == ["US500"]
    macro = OFR.tag_claim({"claim": "Insiders say oil rose 4% within two days.",
                           "instruments": {"analogues": ["XTIUSD"]}}, is_equity=lambda s: False)
    assert macro["claim_type"] == "rumour" and macro["mnpi_risk"] is False
    att = OFR.tag_claim({"claim": "x", "instruments": {}}, attached=True)
    assert att["claim_type"] == "attached" and att["provenance_note"] == "attached, unverified"


# ------------------------------------------------------------------ the pass
FEED_XML = (
    "<rss><channel>"
    "<item><title>OPEC</title><link>http://" + HOST + "/a</link>"
    "<description>Insiders say oil rose 4% within two days after OPEC cut output."
    "</description></item>"
    "<item><title>Gold</title><link>http://" + HOST + "/b</link>"
    "<description>Gold rose 2% within a week after the central bank cut rates by 50 basis "
    "points.</description></item>"
    "<item><title>dump</title><link>http://" + HOST + "/c</link><description>"
    + "\n".join(f"u{i}@m.example:pw{i}{i}{i}x" for i in range(5))
    + "</description></item>"
    "</channel></rss>")


def _transport(answers):
    calls = []

    def t(url, headers, timeout, proxy):
        calls.append(url)
        assert OF.onion_host(url)
        return answers.get(url, (404, "", b""))
    t.calls = calls
    return t


def test_tor_absent_pass_reports_and_holds_the_mission(paths, tmp_path):
    tmp, donated = paths
    doc = OFR.run(60, network=False, status=ABSENT, roster_path=_roster(tmp, [_row()]),
                  report_path=tmp / "ONION_FOREST.json", at="2026-11-17T21:00:00+00:00")
    assert doc["tor"]["status"] == OF.TOR_ABSENT
    assert any("Tor" in m for m in doc["missed_growth"])
    assert doc["mission"]["changed"] is False and "held_why" in doc["mission"]["diff"]
    assert doc["claims"]["new"] == 0 and donated == []
    rows = ME.load_log(OFR.MISSION_LOG)
    assert len(rows) == 1 and rows[0]["parent"] is None          # the seed is recorded once
    assert json.loads((tmp / "ONION_FOREST.json").read_text())["roster"]["allowed"] == 1


def test_present_pass_mines_tags_drops_dumps_donates_and_evolves(paths, tmp_path):
    tmp, donated = paths
    t = _transport({f"http://{HOST}/robots.txt": (404, "", b""),
                    FEED: (200, "application/rss+xml", FEED_XML.encode())})
    roster = _roster(tmp, [_row(), _row(id="unverified", address_status="UNVERIFIED_ADDRESS",
                                        onion_host="e" * 56 + ".onion",
                                        feed_urls=[f"http://{'e' * 56}.onion/rss"])])
    doc = OFR.run(60, network=False, status=PRESENT, transport=t, roster_path=roster,
                  report_path=tmp / "R.json", at="2026-11-17T21:00:00+00:00",
                  is_equity=lambda s: False)
    assert all("e" * 56 not in u for u in t.calls), "an unverified row was fetched"
    assert doc["claims"]["new"] == 2 and doc["claims"]["rumour"] == 1
    assert doc["claims"]["dropped_dump_shape"] == 1
    stored = OFR.CLAIMS.read_text()
    assert "pw000x" not in stored and "u0@m.example" not in stored
    assert donated and len(donated[0]) == 2
    assert doc["mission"]["changed"] is True
    chain = ME.verify_chain(OFR.MISSION_LOG)
    assert chain["ok"] and chain["rows"] == 2
    diff = doc["mission"]["diff"]
    assert "xtiusd" in diff["added"] or "xauusd" in diff["added"]
    assert doc["claims"]["corroboration"]["mechanisms"] == 2
    # a later, non-rumour report of the same mechanism from another source is a confirmation
    with OFR.CLAIMS.open("a", encoding="utf-8") as fh:
        rumour = next(json.loads(x) for x in stored.splitlines()
                      if json.loads(x)["claim_type"] == "rumour")
        fh.write(json.dumps({**rumour, "claim_type": "report", "ground": "other",
                             "fetched_utc": "2026-11-17T23:00:00+00:00"}) + "\n")
    lag = OFR.corroboration(OFR._ledger(OFR.CLAIMS))
    assert lag["rumours_confirmed"] == 1 and lag["median_lag_to_confirmation_h"] == 2.0


def test_the_evolution_step_is_deterministic_on_the_same_yield(paths, tmp_path):
    tmp, _d = paths
    seed = OFR.current_mission(["pub"], "s0", log=tmp / "none.jsonl")
    y = ME.Yield(terms={"oil": 1}, sources={"pub": 1}, tried_terms=list(seed.terms),
                 tried_sources=["pub"], harvest={"XTIUSD": 1})
    a = ME.evolve(seed, y, "s1", sources=["pub"])
    b = ME.evolve(seed, y, "s1", sources=["pub"])
    assert a[0].as_row(a[1]) == b[0].as_row(b[1])


# ------------------------------------------------------------------ the Tor installer
INSTALLER = DESK / "scripts" / "install_tor_service.ps1"
CREDENTIAL = re.compile(
    r"autologon|gh\s+auth|get-credential|convertto-securestring|-password\b|lsastoreprivatedata"
    r"|credential\s*manager|cmdkey|authority\\key|data[\\/]secrets|\.key\b",
    re.IGNORECASE,
)


def test_tor_installer_is_pinned_torproject_only_loopback_and_credential_free():
    src = INSTALLER.read_text(encoding="utf-8")
    assert re.search(r"\$TorVersion\s*=\s*'\d+\.\d+(\.\d+)?'", src)
    pin = re.search(r"\$PinnedSha256\s*=\s*'([^']*)'", src)
    assert pin, "the installer carries a pinned SHA-256 value"
    assert "-notmatch '^[0-9a-f]{64}$'" in src, "an unpinned hash refuses to install"
    assert "Get-FileHash -Algorithm SHA256" in src
    urls = re.findall(r"https?://[^\s'\"<>)]+", src)
    hosts = {urlsplit(u.replace("\\", "")).hostname for u in urls}
    assert urls and hosts <= {"archive.torproject.org", "www.torproject.org"}
    assert "SocksPort 127.0.0.1:9050" in src and "ClientOnly 1" in src
    assert "ControlPort 0" in src and "ExitRelay 0" in src and "ORPort 0" in src
    assert not re.search(r"SocksPort\s+(0\.0\.0\.0|\d+\s*$)", src, re.M)
    assert "--service install -options -f" in src
    assert "[switch]$IfMissing" in src
    assert CREDENTIAL.search(src) is None


def test_the_forest_scout_seeds_from_the_evolving_mission_head(tmp_path, monkeypatch):
    from research import forest_runner as fr
    log = tmp_path / "onion.jsonl"
    m = ME.seed("onion", "base.", ["oil", "gold"], ["pub"], stamp="s0")
    ME.append(log, m)
    child, diff, _ = ME.evolve(m, ME.Yield(terms={"gold": 2}, tried_terms=["oil", "gold"],
                                           harvest={"XAUUSD": 2}), "s1")
    ME.append(log, child, diff)
    monkeypatch.setattr(F, "mission_log", lambda fid, desk=None: log)
    doc = fr.run_pass("onion", budget_s=60, workers=1, dry_run=True, roles=["source_scouts"])
    scout = next(r for r in doc["roles"] if r["role"] == F.SCOUT_ROLE)
    assert any(s.startswith(f"mission:{child.version}") for s in scout["seeded_by"])
    assert not any(s.startswith("polyglot") for s in scout["seeded_by"])
    assert not any(s == "mandate_seeds" for s in scout["seeded_by"])
