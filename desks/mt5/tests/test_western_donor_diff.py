"""N8, the Western donor-capability diff (research/western_donor_diff.py).

What is pinned:

  * the access law is ordered and fails closed: terms before anything (UNKNOWN and
    LOGIN_REQUIRED are never requested), a repository LICENSE before any of its files (no
    LICENSE, or a non-permissive one, closes the repo), robots.txt before every path (a Disallow
    stops the fetch, unreadable robots are not permission, 401/403 is Disallow-all), one honest
    User-Agent;
  * the diff is MEASURED on the tree: a missing anchor is PARTIAL/GAP, code nothing imports is
    EXISTS_NO_CONSUMER, a bare word is not a consumer;
  * an alpha capability that is not COVERED becomes a challenger in the seat directory, once,
    naming only MT5 instruments the lane policy admits; claims are written in the deep-forest
    task shape with kind story_mechanism;
  * the organ is wired: an hourly leg in the intel department, a layer, and an organ contract.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from research import western_donor_diff as w  # noqa: E402

_LEAN_IBS = (
    "# Licensed under the Apache License, Version 2.0 (the \"License\");\n"
    "#\n"
    "# Equity indices exhibit mean reversion in daily returns. The Internal Bar Strength "
    "indicator (IBS), which relates the closing price of a security to its daily range can be "
    "used to identify overbought and oversold securities.\n"
    "class GlobalEquityMeanReversionIBSAlpha(QCAlgorithm):\n    pass\n")
_APACHE = "                                 Apache License\n   Version 2.0, January 2004\n"
_STORY = ("Gold tends to rise in the first hour after the London open when the Asian session "
          "closed near its low; buy XAUUSD and hold for one day. ")


class _Net:
    """A transport that records every URL and answers from a table."""

    def __init__(self, table: dict[str, tuple[int | None, str]]) -> None:
        self.table = table
        self.asked: list[str] = []

    def __call__(self, url: str) -> tuple[int | None, str]:
        self.asked.append(url)
        for prefix, ans in self.table.items():
            if url.startswith(prefix):
                return ans
        return 404, "not found"


@pytest.fixture()
def desk(tmp_path, monkeypatch):
    monkeypatch.setattr(w, "REPORT", tmp_path / "reports" / "WESTERN_DONOR_DIFF.json")
    monkeypatch.setattr(w, "OUT", tmp_path / "data" / "intelligence" / w.SOURCE)
    monkeypatch.setattr(w, "STATE", tmp_path / "data" / "western_donor_state.json")
    monkeypatch.setattr(w, "CLAIMS", tmp_path / "data" / "western_donor_claims.jsonl")
    uni = tmp_path / "universe.json"
    uni.write_text(json.dumps({s: {} for s in ("US500", "NAS100", "GER40", "XAUUSD", "EURUSD",
                                               "AAPL")}), "utf-8")
    monkeypatch.setattr(w, "UNIVERSE", uni)
    monkeypatch.setattr(w, "_may_hypothesise", lambda s, f: s != "AAPL")
    return tmp_path


def _gate(table):
    net = _Net(table)
    return w.Gate(net, sleep=lambda s: None), net


def _src(**kw):
    base = {"id": "s", "donor": "quantconnect_lean", "urls": ("https://h.example/a",),
            "machine_use": w.PERMITTED, "basis": "test"}
    return w.Source(**{**base, **kw})


# ------------------------------------------------------------------------- the access law ---
@pytest.mark.parametrize("use", [w.UNKNOWN, w.FORBIDDEN, w.LOGIN_REQUIRED])
def test_terms_that_are_not_permitted_are_never_requested(use):
    gate, net = _gate({})
    outcome, detail, text = gate.read(_src(machine_use=use), "https://h.example/a")
    assert outcome == "TERMS_FAIL_CLOSED" and use in detail and text == ""
    assert net.asked == []                      # not even robots.txt


def test_a_repository_without_a_permissive_licence_stays_closed():
    for licence in ((404, "nope"), (200, "Business Source License 1.1"),
                    (200, "GNU LESSER GENERAL PUBLIC LICENSE")):
        gate, net = _gate({"https://h.example/robots.txt": (404, ""),
                           "https://h.example/LICENSE": licence})
        src = _src(licence_url="https://h.example/LICENSE")
        outcome, _, _ = gate.read(src, "https://h.example/a")
        assert outcome == "LICENCE_FAIL_CLOSED"
        assert "https://h.example/a" not in net.asked


def test_a_permissive_licence_opens_the_repository_and_is_read_once():
    gate, net = _gate({"https://h.example/robots.txt": (404, ""),
                       "https://h.example/LICENSE": (200, _APACHE),
                       "https://h.example/": (200, "body")})
    src = _src(licence_url="https://h.example/LICENSE")
    assert gate.read(src, "https://h.example/a")[0] == "FETCHED"
    assert gate.read(src, "https://h.example/b")[0] == "FETCHED"
    assert net.asked.count("https://h.example/LICENSE") == 1
    assert net.asked.count("https://h.example/robots.txt") == 1


def test_robots_disallow_unreadable_and_forbidden_all_refuse():
    gate, net = _gate({"https://h.example/robots.txt": (200, "User-agent: *\nDisallow: /priv")})
    assert gate.read(_src(), "https://h.example/priv/x")[0] == "ROBOTS_REFUSED"
    assert "https://h.example/priv/x" not in net.asked
    for status in (500, None):
        gate, net = _gate({"https://h.example/robots.txt": (status, "boom")})
        out, detail, _ = gate.read(_src(), "https://h.example/a")
        assert out == "ROBOTS_REFUSED" and "unreadable" in detail
        assert net.asked == ["https://h.example/robots.txt"]
    gate, net = _gate({"https://h.example/robots.txt": (403, "")})
    assert gate.read(_src(), "https://h.example/a")[0] == "ROBOTS_REFUSED"


def test_the_user_agent_is_honest_and_the_default_transport_sends_it(monkeypatch):
    assert "quant-desk-donor-diff" in w.UA and "Mozilla" not in w.UA
    seen = {}

    class R:
        status, text, error = 200, "ok", ""

    from libs.data import polite_fetch as pf

    def fake_get(url, **kw):
        seen.update(kw)
        return R()

    monkeypatch.setattr(pf, "get", fake_get)
    assert w._default_fetch("https://h.example/a") == (200, "ok")
    assert seen["headers"]["User-Agent"] == w.UA


def test_every_registered_source_states_terms_and_the_closed_ones_say_why():
    ids = {s.id for s in w.SOURCES}
    assert len(ids) == len(w.SOURCES)
    for s in w.SOURCES:
        assert s.machine_use in (w.PERMITTED, w.FORBIDDEN, w.UNKNOWN, w.LOGIN_REQUIRED)
        assert s.basis.strip()
        if s.kind == "github":
            assert s.licence_url, f"{s.id}: a repository route must name its LICENSE"
        joined = " ".join(s.urls).lower()
        for venue in ("binance", "bybit", "okx", "hyperliquid"):
            assert venue not in joined
    closed = {s.id for s in w.SOURCES if s.machine_use != w.PERMITTED}
    assert {"wq_brain_platform", "man_institute"} <= closed
    assert set(w.DONORS) == {s.donor for s in w.SOURCES} == {c.donor for c in w.CAPABILITIES}


# ------------------------------------------------------------------------------ the diff ---
def _cap(anchors, **kw):
    base = dict(id="c", donor="numerai", name="n", kind="method", public_capability="p",
                evidence_grade="FIRST_PARTY_TECHNICAL_DISCLOSURE", economic_mechanism="m",
                anchors=anchors, desk_analogue="d", solo_scale_implementation="s",
                controlled_test="t")
    return w.Capability(**{**base, **kw})


def test_the_status_is_measured_on_the_tree(tmp_path):
    (tmp_path / "libs").mkdir()
    (tmp_path / "libs" / "thing.py").write_text("def neutralize(x):\n    return x\n")
    (tmp_path / "libs" / "user.py").write_text("from libs import thing\n")
    (tmp_path / "libs" / "lonely.py").write_text("def neutralize(x):\n    return x\n")
    (tmp_path / "libs" / "mentions.py").write_text("# the lonely road\nx = 'lonely'\n")
    texts = w._scan_texts(tmp_path)
    m = w.measure(_cap((("libs/thing.py", r"def neutralize"),)), tmp_path, texts)
    assert m["status"] == "COVERED"
    m = w.measure(_cap((("libs/lonely.py", r"def neutralize"),)), tmp_path, texts)
    assert m["status"] == "EXISTS_NO_CONSUMER"          # a bare word is not a consumer
    m = w.measure(_cap((("libs/thing.py", r"neutralize"), ("libs/thing.py", r"truncate"))),
                  tmp_path, texts)
    assert m["status"] == "PARTIAL" and m["anchors_present"] == 1
    m = w.measure(_cap((("libs/gone.py", r"x"),)), tmp_path, texts)
    assert m["status"] == "GAP" and not m["anchors"][0]["file_exists"]
    assert w.measure(_cap(()), tmp_path, texts)["status"] == "GAP"


def test_every_capability_walks_all_eight_stations():
    from libs.research import capability_challenger as cc
    for cap in w.CAPABILITIES:
        assert cap.evidence_grade in cc.EVIDENCE_GRADES
        assert cap.kind in ("alpha", "method")
        assert w._registration(cap, "GAP")["status"] == "REGISTERED", cap.id
        if cap.challenger:
            assert cap.kind == "alpha"


# ------------------------------------------------------------------------- the pass ---------
def test_a_pass_writes_challengers_and_story_tasks_to_the_seat_once(desk, monkeypatch):
    lean = w.LEAN
    table = {"https://raw.githubusercontent.com/robots.txt": (404, ""),
             "https://export.arxiv.org/robots.txt": (200, "User-agent: *\nDisallow: /"),
             f"{lean}/LICENSE": (200, _APACHE),
             f"{lean}/Algorithm.Python/Alphas/GlobalEquityMeanReversionIBSAlpha.py":
                 (200, _LEAN_IBS),
             f"{lean}/readme.md": (200, _STORY * 3)}
    net = _Net(table)
    rep = w.run(fetch=net, max_fetches=100, sleep=lambda s: None)
    outcomes = rep["fetch"]["outcomes"]
    assert outcomes.get("TERMS_FAIL_CLOSED", 0) >= 4
    assert outcomes.get("ROBOTS_REFUSED", 0) >= 1           # arXiv disallowed in this fixture
    assert outcomes.get("FETCHED", 0) >= 2
    for e in rep["fetch"]["log"]:
        if e["outcome"] == "TERMS_FAIL_CLOSED":
            assert e["url"] not in net.asked
    # numerai docs repo has no LICENSE in this fixture -> closed; its pages never requested
    assert not any("numerai/docs/master/numerai-tournament" in u for u in net.asked)

    files = sorted((desk / "data" / "intelligence" / w.SOURCE).glob("discoveries_*.json"))
    assert len(files) == 1
    rows = json.loads(files[0].read_text("utf-8"))
    ibs = [r for r in rows if r.get("capability_id") == "lean_ibs_reversion"]
    assert ibs, "the IBS gap (no range-position score in the class book) must be challenged"
    r = ibs[0]
    assert r["kind"] == "story_mechanism" and "AAPL" not in r["symbols"]
    assert set(r["symbols"]) <= {"US500", "NAS100", "GER40"}
    assert "Internal Bar Strength" in r["description"]      # the donor's own words ride along
    assert "Apache" not in r["description"]                 # the licence header does not
    # ATTRIBUTION TRAVELS WITH THE QUOTE: the licence the gate read, and where it came from.
    assert r["licence"] == "Apache-2.0"
    assert r["quoted_from"] == f"{lean}/Algorithm.Python/Alphas/GlobalEquityMeanReversionIBSAlpha.py"
    assert r["quoted_from"] in r["attribution"] and "Apache-2.0" in r["attribution"]
    assert all(r["source"] == w.SOURCE for r in rows)
    stories = [r for r in rows if r.get("kind") == "story_mechanism" and "provenance" in r]
    for t in stories:
        assert t["consumer"].startswith("deepening_worker")
        assert t["symbols"] and "XAUUSD" in t["symbols"]
        assert t["licence"] == "Apache-2.0" and t["quoted_from"].startswith(lean)

    report = json.loads((desk / "reports" / "WESTERN_DONOR_DIFF.json").read_text("utf-8"))
    assert report["user_agent"] == w.UA
    caps = {c["id"]: c for c in report["capabilities"]}
    assert caps["lean_ibs_reversion"]["challenger"] == "EMITTED"
    assert caps["lean_ibs_reversion"]["evidence_confirmed_online"] != w.UNMEASURED
    assert any(q["capability"] == "lean_ibs_reversion" for q in report["work_queue"])

    # SECOND PASS: nothing new, so nothing is re-donated (each emission is a trial).
    rep2 = w.run(fetch=_Net(table), max_fetches=100, sleep=lambda s: None)
    assert rep2["challengers"]["new"] == 0 and rep2["claims"]["new"] == 0
    assert len(sorted((desk / "data" / "intelligence" / w.SOURCE).glob("*.json"))) == 1


def test_no_fetch_names_what_it_did_not_measure(desk):
    rep = w.run(network=False, write=False)
    assert rep["fetch"]["requests"] == 0
    assert set(rep["fetch"]["outcomes"]) == {"NO_FETCH"}
    assert rep["unmeasured"]
    assert all(c["evidence_confirmed_online"] == w.UNMEASURED for c in rep["capabilities"])


def test_the_rotation_reaches_every_document():
    flat = [(s.id, u) for s in w.SOURCES for u in s.urls]
    seen: set[tuple[str, str]] = set()
    cursor = 0
    for _ in range(len(flat)):
        plan = w._plan(w.SOURCES, cursor, 5)
        seen.update((s.id, u) for s, u in plan)
        cursor = (cursor + len(plan)) % len(flat)
    assert seen == set(flat)


# ------------------------------------------------------------------------------- the wiring --
def test_the_organ_is_wired_on_a_clock_with_a_contract():
    hc = (_DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '"research/western_donor_diff.py"' in hc
    import hourly_cycle
    assert hourly_cycle.LEG_DEPARTMENT.get("western_donors") == "intel"
    from libs.research import layers
    assert layers.LEG_LAYER.get("western_donors") == "information"
    sys.path.insert(0, str(_ROOT / "ops"))
    import organ_contract
    art, age, _ = organ_contract.CONTRACTS["MT5-Dept-Intel (western donors)"]
    assert art == "desks/mt5/reports/WESTERN_DONOR_DIFF.json" and age > 60


def test_a_quote_without_a_known_licence_is_never_carried(desk):
    cap = next(c for c in w.CAPABILITIES if c.id == "lean_ibs_reversion")
    diff = {cap.id: {"status": "PARTIAL"}}
    url = cap.evidence[0]
    uni = {"US500", "NAS100"}
    rows = w.challenger_rows([cap], diff, uni, {url: "the donor's sentence"}, {url: None})
    assert rows and "the donor's sentence" not in rows[0]["description"]
    assert "licence" not in rows[0]
    rows = w.challenger_rows([cap], diff, uni, {url: "the donor's sentence"},
                             {url: "Apache-2.0"})
    assert "the donor's sentence" in rows[0]["description"]
    assert rows[0]["licence"] == "Apache-2.0" and rows[0]["quoted_from"] == url


def test_the_organs_bookkeeping_is_never_committed():
    import subprocess
    for rel in ("desks/mt5/data/western_donor_claims.jsonl",
                "desks/mt5/data/western_donor_state.json"):
        r = subprocess.run(["git", "check-ignore", "-q", rel], cwd=_ROOT, check=False)
        assert r.returncode == 0, f"{rel} must be gitignored"
