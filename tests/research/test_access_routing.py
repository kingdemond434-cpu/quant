"""ACCESS ROUTING (LAWS 5e, principal 2026-09-23): classification routes USE, never mining.

The law this pins is one sentence: the desk mines and tests EVERYTHING it can see on the open
internet, and licence, robots, source class and credibility are routing and provenance labels
that describe what may be REDISTRIBUTED and how much weight the evidence carries -- never whether
a row is discovered, ingested, represented or tested.

AMENDED 2026-10-14 07:35Z by the principal (decision card
cmsg_012XFUfE12Rvggnu86fDb8pr5ze7a7HLob52jUdGwu28JR): robots.txt is respected AT FETCH TIME. A
disallowed page is not fetched and the skip is a hold with a named cause; the row is still
labelled and mined. The robots tests below pin THAT rule, with urllib stubbed and no network.

The three cases the principal named are the first three tests. The rest exist because this law
has been re-derived into caution twice, and a test is the only thing that survives a rewrite:
every deleted brake gets a test that FAILS if someone puts it back, and the five refused acts get
a test that fails if someone adds a sixth.

`access_classifier` does no IO. The fetch-path tests stub urllib, make no network request
and write only under pytest's tmp_path.
"""
from __future__ import annotations

import io
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from libs.research import access_classifier as ac
from libs.research.data_contract import DatasetContract

# ------------------------------------------------------------- the three cases, named verbatim

def test_an_unclear_licence_row_is_mined_tested_and_carries_its_label() -> None:
    """"There is no ACCESS_UNCLEAR quarantine any more: an unclear row is mined and tested with
    its label attached." Before 2026-09-23 this row's only permitted use was `register`, its
    weight cap was 0.0 and its claim text was blanked at the router."""
    routed = ac.route({"source_id": "somewhere", "licence": "unclear, no terms page found"},
                      {"claim": "the metal tends to gap at the Asia open"})

    assert routed.stage == "RESEARCH"
    assert routed.researchable is True
    assert routed.dropped is False
    assert routed.verdict.quarantine is False
    # THE LABEL SURVIVES -- routing, not deletion.
    assert routed.verdict.access_label == "ACCESS_UNCLEAR"
    assert routed.evidence is not None
    assert routed.evidence.access_label == "ACCESS_UNCLEAR"
    # The content is CONSUMED, which is the whole change: the claim is not blanked.
    assert routed.evidence.claim_text == "the metal tends to gap at the Asia open"
    assert routed.evidence.evidence_weight > 0.0
    # And it may be tested, stored and turned into features.
    for use in ("machine_extract", "store_raw", "derive_features", "alpha_input"):
        assert routed.verdict.may(use), use


def test_a_login_protected_page_is_still_refused() -> None:
    """Hard-boundary acts 1 and 2: the desk does not log in as someone else and does not bypass
    an access control. This is about an ACT, and it does not move."""
    routed = ac.route({"source_id": "portal", "url": "https://example.test/account/statements",
                       "requires_auth": True},
                      {"claim": "balances by client"})

    assert routed.stage == "LEGAL_ACCESS"
    assert routed.researchable is False
    assert routed.verdict.refused is True
    assert routed.verdict.access_label == "PRIVATE"
    assert routed.verdict.allowed_uses == ()
    assert routed.verdict.mined is False
    assert "REFUSED" in routed.why


def test_a_robots_disallowed_page_is_not_fetched_and_its_row_is_still_labelled() -> None:
    """LAWS 5e AMENDED 2026-10-14: a robots.txt Disallow means THAT PAGE IS NOT FETCHED
    (`fetch_allowed` False). Everything else stands: the row keeps PUBLIC_WITH_TERMS, its
    `terms_note`, and every mining use -- content about it obtained lawfully by other means is
    still labelled and mined."""
    routed = ac.route({"source_id": "forum", "url": "https://forum.test/threads",
                       "robots": "disallow", "source_class": "media"},
                      {"claim": "the desk over there is short the carry"})

    assert routed.verdict.fetch_allowed is False
    assert routed.verdict.access_label == "PUBLIC_WITH_TERMS"
    assert "robots=disallow" in routed.verdict.terms_note
    # Robots governs the FETCH of one page, never whether the row is mined.
    assert routed.researchable is True
    assert routed.verdict.machine_use_allowed is True
    assert routed.verdict.may("machine_extract") is True
    assert routed.verdict.redistribute_allowed is False
    assert routed.evidence is not None
    assert routed.evidence.provenance["terms_note"] == routed.verdict.terms_note
    assert routed.evidence.provenance["fetch_allowed"] is False


@pytest.mark.parametrize("value", ["disallowed", "barred", "blocked"])
def test_every_robots_disallow_spelling_stops_the_fetch(value: str) -> None:
    v = ac.classify({"url": "https://x.test/p", "robots": value})
    assert v.fetch_allowed is False and v.access_label == "PUBLIC_WITH_TERMS"
    assert f"robots={value}" in v.terms_note


def test_robots_stops_the_fetch_whatever_label_the_row_earns() -> None:
    """An archive or open-data page that robots.txt disallows keeps its own label and is still
    mined -- and is still not fetched."""
    v = ac.classify({"url": "https://archive.test/x", "obtained": "archive", "robots": "disallow"})
    assert v.access_label == "PUBLIC_ARCHIVE" and v.mined is True
    assert v.fetch_allowed is False and "robots=disallow" in v.terms_note


def test_without_a_robots_disallow_the_page_may_be_fetched() -> None:
    for robots in ("allowed", "unknown", ""):
        v = ac.classify({"url": "https://x.test/p", "robots": robots})
        assert v.fetch_allowed is True, robots


# ----------------------------------------------------------------- the boundary, exactly five

def test_the_hard_boundary_is_exactly_five_acts() -> None:
    """A sixth entry here is a new brake wearing the boundary's clothes. The count is pinned so
    it cannot be added quietly."""
    assert len(ac.HARD_BOUNDARY) == ac.HARD_BOUNDARY_COUNT == 5
    joined = " | ".join(ac.HARD_BOUNDARY).lower()
    for act in ("credential theft", "logging in as someone else", "access control", "paywall",
                "material non-public", "stolen or leaked", "doxxing"):
        assert act in joined, act


def test_only_three_labels_are_ever_refused() -> None:
    """Every other label is mined. This is the list that must not grow."""
    assert ac.REFUSED_LABELS == ("PRIVATE", "CONFIDENTIAL_MNPI", "STOLEN_UNAUTHORIZED")
    refused = {lab for lab, row in ac.ROUTING.items() if row["refused"]}
    assert refused == set(ac.REFUSED_LABELS)
    assert set(ac.MINED_LABELS) == set(ac.ACCESS_LABELS) - refused


@pytest.mark.parametrize("label", [lab for lab in ac.ACCESS_LABELS
                                   if lab not in ac.REFUSED_LABELS])
def test_every_mined_label_grants_the_full_mining_vocabulary(label: str) -> None:
    """No label withholds discovery, ingestion, representation or testing -- only
    `redistribute` is ever withheld, and that is a publication question."""
    uses = ac.ROUTING[label]["allowed_uses"]
    for use in ac.MINING_USES:
        assert use in uses, f"{label} withholds {use}"
    assert ac.ROUTING[label]["quarantine"] is False
    assert ac.ROUTING[label]["evidence_weight_cap"] > 0.0


def test_no_routing_row_quarantines_anything() -> None:
    """The quarantine was the single largest brake: it kept metadata and threw the content away."""
    assert not [lab for lab, row in ac.ROUTING.items() if row["quarantine"]]


def test_the_deleted_brakes_are_named_in_the_module() -> None:
    """A later session must not re-derive the old caution from silence (LAWS 5e). Robots LEFT
    this list on 2026-10-14: the principal amended 5e so a Disallow is respected at fetch
    time."""
    named = " | ".join(ac.REMOVED_BRAKES).lower()
    for brake in ("quarantine", "machine-extraction veto", "machine_use_allowed",
                  "public/licensed sources only"):
        assert brake in named, brake
    assert "robots" not in named
    assert not any("robots" in b.lower() for b in ac.REMOVED_BRAKES)


def test_the_principle_names_robots_as_the_one_fetch_time_rule() -> None:
    text = ac.PRINCIPLE.lower()
    assert "robots is the one fetch-time rule" in text
    assert "not fetched" in text and "hold with a named cause" in text


def test_the_principle_says_labels_never_stop_mining() -> None:
    text = ac.PRINCIPLE.lower()
    assert "mines and tests everything" in text
    assert "never stop discovery, ingestion, representation or testing" in text


# ------------------------------------------------------------- the weight axis is not a brake

def test_weight_caps_lower_evidence_and_never_block_research() -> None:
    """Fringe, retail and forum ground is a FIRST-CLASS INPUT: mined and tested exactly as hard
    as an official release, carrying less weight. Weight is about truth, permission is not."""
    routed = ac.route({"source_id": "r/wallstreetbets", "url": "https://reddit.test/r/x",
                       "source_class": "retail_ecology"},
                      {"claim": "everyone is long gold", "credibility": "FRINGE"})

    assert routed.verdict.access_label == "PUBLIC_SOCIAL"
    assert routed.researchable is True
    assert routed.verdict.may("machine_extract") is True
    assert routed.evidence is not None
    assert 0.0 < routed.evidence.evidence_weight <= 0.6
    assert routed.evidence.narrative_feature is True


def test_an_archive_is_first_class_ground() -> None:
    routed = ac.route({"source_id": "wayback", "obtained": "archive"},
                      {"claim": "the 2013 circular said X"})
    assert routed.verdict.access_label == "PUBLIC_ARCHIVE"
    assert routed.verdict.may("machine_extract") is True
    assert routed.researchable is True


def test_a_paywalled_domain_is_mined_at_its_open_surface_never_bypassed() -> None:
    """"If a page is behind a login or a paywall the desk does not break in; everything reachable
    without breaking in is mined." The domain is a label, the wall is the boundary."""
    open_surface = ac.route({"source_id": "wsj", "url": "https://wsj.test/economy",
                             "paywalled": True}, {"claim": "the Fed leak piece ran"})
    assert open_surface.researchable is True
    assert open_surface.verdict.may("machine_extract") is True
    assert "paywall" in open_surface.verdict.terms_note

    bypass = ac.route({"source_id": "wsj", "url": "https://wsj.test/economy"},
                      {"claim": "full text via paywall bypass"})
    assert bypass.verdict.refused is True
    assert bypass.verdict.access_label == "STOLEN_UNAUTHORIZED"


# ---------------------------------------------------------------- the data contract agrees

def test_the_data_contract_no_longer_vetoes_machine_extraction() -> None:
    """`DataContract.may` demanded `machine_use_allowed is True`, so an UNMEASURED flag read as
    a refusal. The flag is provenance now; the declared uses are the whole answer."""
    unmeasured = DatasetContract(dataset_id="d1",
                                 permitted_uses=("machine_extract", "alpha_input"))
    assert unmeasured.machine_use_allowed is None
    assert unmeasured.may("machine_extract") is True

    restricted = DatasetContract(dataset_id="d2", permitted_uses=("machine_extract",),
                                 machine_use_allowed=False)
    assert restricted.may("machine_extract") is True
    # A use the contract never declared is still not permitted: that is a scope statement, not
    # a brake on mining.
    assert restricted.may("redistribute") is False


# ------------------------------------------------------------------- the five acts still bite

@pytest.mark.parametrize(("meta", "content", "label"), [
    ({"source_id": "s"}, {"claim": "here is a password dump from the broker"},
     "STOLEN_UNAUTHORIZED"),
    ({"source_id": "s", "obtained": "leaked_looking"}, {"claim": "internal file"},
     "STOLEN_UNAUTHORIZED"),
    ({"source_id": "s"}, {"claim": "pre-release earnings for the quarter"}, "CONFIDENTIAL_MNPI"),
    ({"source_id": "s", "is_mnpi": True}, {"claim": "guidance"}, "CONFIDENTIAL_MNPI"),
    ({"source_id": "s", "url": "https://x.test/wp-admin/"}, {"claim": "settings"}, "PRIVATE"),
    ({"source_id": "s", "is_private": True}, {"claim": "client list"}, "PRIVATE"),
])
def test_the_acts_that_remain_refused(meta: dict, content: dict, label: str) -> None:
    routed = ac.route(meta, content)
    assert routed.verdict.access_label == label
    assert routed.verdict.refused is True
    assert routed.researchable is False
    assert routed.evidence is None


def test_the_boundary_is_read_before_any_permissive_label_can_rescue_it() -> None:
    """A licence field saying "public" on a credential list does not make it public."""
    routed = ac.route({"source_id": "s", "licence": "CC0", "is_open_data": True,
                       "obtained": "public_page"},
                      {"claim": "combolist of trading accounts"})
    assert routed.verdict.access_label == "STOLEN_UNAUTHORIZED"
    assert routed.verdict.refused is True


# ---------------------------------------------- the shared fetch path respects robots (RFC 9309)

_ROOT = Path(__file__).resolve().parents[2]
_DESK = _ROOT / "desks" / "mt5"
T0 = 1_800_000_000.0


def _desk_modules() -> tuple[Any, Any]:
    for p in (str(_ROOT), str(_DESK), str(_DESK / "research")):
        if p not in sys.path:
            sys.path.insert(0, p)
    from research import asia_collector as acol
    from research import data_acquisition_scientist as das
    return acol, das


class _Clock:
    def __init__(self) -> None:
        self.t = T0

    def __call__(self) -> float:
        return self.t


@pytest.fixture
def iso(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """asia_collector with its state, robots cache, vault and clock all under tmp_path."""
    acol, das = _desk_modules()
    monkeypatch.setattr(acol, "STATE", tmp_path / "collector_state.json")
    monkeypatch.setattr(acol, "ROBOTS_CACHE", tmp_path / "robots_cache.json")
    monkeypatch.setattr(acol, "VAULT", tmp_path / "vault")
    monkeypatch.setattr(acol, "SERIES", tmp_path / "series")
    clock = _Clock()
    monkeypatch.setattr(acol, "_now", clock)
    return SimpleNamespace(acol=acol, das=das, clock=clock, tmp=tmp_path)


class _Resp:
    def __init__(self, body: bytes, ctype: str = "text/csv",
                 extra: dict[str, str] | None = None) -> None:
        self._body = body
        self.status = 200
        self.headers = {"Content-Type": ctype, **(extra or {})}

    def __enter__(self) -> _Resp:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def read(self, n: int = -1) -> bytes:
        return self._body if n < 0 else self._body[:n]


CSV = b"date,value\n2026-01-01,1\n2026-01-02,2\n2026-01-03,3\n2026-01-04,4\n"


class _Net:
    """A stub internet. `robots` is bytes (a 200 body), an int (an HTTP error code) or an
    exception instance (unreachable); it can be changed between passes. `seen` records every
    (url, user-agent) requested, in order."""

    def __init__(self, robots: Any, page: Any = None) -> None:
        self.robots = robots
        #: None = 200 CSV; an int = that HTTP error with an empty body; a tuple
        #: (code, headers, body) = that response (code 200 succeeds with those headers).
        self.page = page
        #: Per-url answers that win over the defaults: ("redirect", location[, code]), or a
        #: robots/page spec of the shapes above.
        self.routes: dict[str, Any] = {}
        self.seen: list[tuple[str, str]] = []

    def __call__(self, req: Any, *a: Any, **k: Any) -> _Resp:
        url = req.full_url if isinstance(req, urllib.request.Request) else str(req)
        ua = req.get_header("User-agent") if isinstance(req, urllib.request.Request) else ""
        self.seen.append((url, str(ua or "")))
        spec = self.routes.get(url)
        if isinstance(spec, tuple) and spec and spec[0] == "redirect":
            code = spec[2] if len(spec) > 2 else 302
            raise urllib.error.HTTPError(url, code, "stub", {"Location": spec[1]},  # type: ignore[arg-type]
                                         io.BytesIO(b""))
        if spec is not None and url.endswith("/robots.txt"):
            if isinstance(spec, bytes):
                return _Resp(spec, "text/plain")
            raise urllib.error.HTTPError(url, int(spec), "stub", {}, io.BytesIO(b""))  # type: ignore[arg-type]
        if spec is not None:
            code, hdrs, body = (spec, {}, b"") if isinstance(spec, int) else spec
            if code == 200:
                return _Resp(body or CSV, extra=hdrs)
            raise urllib.error.HTTPError(url, code, "stub", hdrs, io.BytesIO(body))
        if url.endswith("/robots.txt"):
            if isinstance(self.robots, bytes):
                return _Resp(self.robots, "text/plain")
            if isinstance(self.robots, int):
                raise urllib.error.HTTPError(url, self.robots, "stub", None, None)  # type: ignore[arg-type]
            raise self.robots
        if self.page is None:
            return _Resp(CSV)
        code, hdrs, body = (self.page, {}, b"") if isinstance(self.page, int) else self.page
        if code == 200:
            return _Resp(body or CSV, extra=hdrs)
        raise urllib.error.HTTPError(url, code, "stub", hdrs, io.BytesIO(body))

    def urls(self) -> list[str]:
        return [u for u, _ in self.seen]


def _net(monkeypatch: pytest.MonkeyPatch, robots: Any, page: Any = None) -> _Net:
    net = _Net(robots, page)
    monkeypatch.setattr(urllib.request, "urlopen", net)
    # The collector opens ONE hop at a time through `_urlopen` (no redirect following).
    monkeypatch.setattr(_desk_modules()[0], "_urlopen", net)
    return net


PAGE = "https://data.robots.test:8443/series/x.csv"
ROBOTS = "https://data.robots.test:8443/robots.txt"
HOST = "data.robots.test:8443"
DISALLOW = b"User-agent: *\nDisallow: /series/\n"


def _collect(iso: Any) -> dict[str, Any]:
    return dict(iso.acol.collect_one({"id": "robots_probe", "url": PAGE, "expect": "csv",
                                      "access": "public"}))


def test_the_desk_ua_is_exact_and_shared_by_the_robots_read_and_the_fetch(
        iso: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    acol = iso.acol
    assert acol.DESK_UA == ("quant-mt5-research-desk/1.0 (+https://github.com/kingdemond434-cpu/"
                            "quant/issues; internal research; honours robots.txt)")
    assert acol.USER_AGENT == acol.DESK_UA
    assert acol.ROBOTS_PRODUCT_TOKEN == "quant-mt5-research-desk"
    net = _net(monkeypatch, b"User-agent: *\nDisallow: /private/\n")
    rec = _collect(iso)
    assert net.urls() == [ROBOTS, PAGE]
    assert {ua for _, ua in net.seen} == {acol.DESK_UA}
    assert rec["robots_disallows"] is False and rec["status"] != "BLOCKED_BY_ROBOTS"


def test_asia_collector_never_requests_a_robots_disallowed_page(
        iso: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """BEHAVIOURAL, no network. A Disallow is a named HOLD and the page request never happens;
    robots.txt is read at the EXACT origin (port included)."""
    net = _net(monkeypatch, DISALLOW)
    rec = _collect(iso)

    assert net.urls() == [ROBOTS]
    assert rec["status"] == "BLOCKED_BY_ROBOTS"
    assert rec["hold_cause"] == "robots:disallow"
    assert rec["robots_disallows"] is True and rec["robots"]
    assert "not fetched" in rec["terms_note"] and "HOLD" in rec["why"]
    assert rec["id"] == "robots_probe", "the source's row stays visible"
    assert not (iso.tmp / "vault").exists()


def test_a_disallow_rereads_robots_at_most_once_per_24h(
        iso: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    net = _net(monkeypatch, DISALLOW)
    _collect(iso)
    iso.clock.t = T0 + 23 * 3600
    assert _collect(iso)["status"] == "BLOCKED_BY_ROBOTS"
    assert net.urls() == [ROBOTS], "inside 24h the cached robots.txt answers; no request"
    iso.clock.t = T0 + 25 * 3600
    _collect(iso)
    assert net.urls() == [ROBOTS, ROBOTS], "after 24h robots.txt is read again, page still not"


@pytest.mark.parametrize("group", [b"quant-mt5-research-desk", b"Quant-MT5-Research-Desk"])
def test_a_rule_written_for_our_product_token_binds_even_when_star_allows(
        group: bytes, iso: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    net = _net(monkeypatch, b"User-agent: " + group + b"\nDisallow: /\n\n"
                            b"User-agent: *\nAllow: /\n")
    rec = _collect(iso)
    assert rec["status"] == "BLOCKED_BY_ROBOTS" and net.urls() == [ROBOTS]


def test_robots_404_means_allow(iso: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    net = _net(monkeypatch, 404)
    v = iso.acol.robots_verdict(PAGE)
    assert v.allowed is True and v.cause == "robots_absent" and v.recheck is False
    rec = _collect(iso)
    assert rec["status"] != "BLOCKED_BY_ROBOTS" and net.urls()[-1] == PAGE


@pytest.mark.parametrize("code", [500, 503])
def test_robots_5xx_is_a_timed_recheck_not_a_refusal(
        code: int, iso: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    net = _net(monkeypatch, code)
    rec = _collect(iso)
    assert rec["status"] == "BLOCKED_BY_ROBOTS" and rec["hold_cause"] == "robots:robots_5xx"
    assert rec["robots_recheck"] is True and rec["site_hold"] is None
    assert net.urls() == [ROBOTS]
    assert iso.acol.active_site_hold(HOST) is None, "a 5xx is not a person hold"
    # Re-read on the next pass, and fetched once robots.txt answers.
    net.robots = b"User-agent: *\nAllow: /\n"
    rec = _collect(iso)
    assert net.urls() == [ROBOTS, ROBOTS, PAGE]


def test_an_unreachable_robots_is_disallow_for_now_never_allowing(
        iso: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """The old helper said "unreadable; treated as allowing". RFC 9309 says the opposite."""
    net = _net(monkeypatch, urllib.error.URLError("no route"))
    rec = _collect(iso)
    assert rec["status"] == "BLOCKED_BY_ROBOTS"
    assert rec["hold_cause"] == "robots:robots_unreachable" and rec["robots_recheck"] is True
    assert net.urls() == [ROBOTS]
    assert iso.acol.active_site_hold(HOST) is None


@pytest.mark.parametrize("code", [401, 403, 429])
def test_a_401_403_429_on_robots_is_a_person_hold_no_timer_releases(
        code: int, iso: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Auditor's ruling 2026-10-14: released only by a person, never by a timer. Passes at +25h
    and +11d send ZERO requests to that host; after release the next pass fetches."""
    acol = iso.acol
    net = _net(monkeypatch, code)
    rec = _collect(iso)
    assert net.urls() == [ROBOTS]
    assert rec["status"] == "BLOCKED_BY_ROBOTS" and rec["hold_cause"] == "robots:person_hold"
    assert rec["robots_recheck"] is False, "no timer"
    hold = acol.active_site_hold(HOST)
    assert hold == {"key": f"site:{HOST}", "verdict": "ROBOTS_HOLD", "status": code,
                    "host": HOST, "url": PAGE[:300], "held_at": T0, "released_by": None,
                    "released_at": None}
    assert rec["site_hold"] == hold

    net.robots = b"User-agent: *\nAllow: /\n"          # the site recovered; still held
    for later in (T0 + 25 * 3600, T0 + 11 * 24 * 3600):
        iso.clock.t = later
        assert acol.due({"id": "robots_probe", "cadence": "daily"},
                        {"robots_probe": {"last_attempt_epoch": T0}}, later) is True
        rec = _collect(iso)
        assert rec["status"] == "BLOCKED_BY_ROBOTS" and rec["hold_cause"] == "robots:person_hold"
        assert net.urls() == [ROBOTS], f"zero requests to a held host at +{later - T0:.0f}s"
        # The acquisition scientist's path honours the same hold.
        assert iso.acol.robots_verdict(PAGE, "Mozilla/5.0").cause == "person_hold"
        assert net.urls() == [ROBOTS]

    with pytest.raises(ValueError):
        acol.release_site_hold(HOST, "")
    released = acol.release_site_hold(HOST, "zuck")
    assert released["released_by"] == "zuck" and released["released_at"] == iso.clock.t
    assert acol.active_site_hold(HOST) is None
    rec = _collect(iso)
    assert net.urls() == [ROBOTS, ROBOTS, PAGE], "after release the next pass fetches"
    assert rec["status"] != "BLOCKED_BY_ROBOTS"


def test_the_release_cli_releases_a_hold(iso: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    acol = iso.acol
    _net(monkeypatch, 403)
    _collect(iso)
    assert acol.main(["--release-host", HOST, "--released-by", "auditor"]) == 0
    row = json.loads((iso.tmp / "collector_state.json").read_text("utf-8"))[f"site:{HOST}"]
    assert row["released_by"] == "auditor" and row["released_at"] == T0


def test_the_site_hold_record_rejects_an_unknown_verdict(iso: Any) -> None:
    rec = iso.acol.site_hold_record("h.test", "https://h.test/x", None, "HARD_STOP", at=1.0)
    assert rec["verdict"] == "HARD_STOP" and rec["status"] is None
    with pytest.raises(ValueError):
        iso.acol.site_hold_record("h.test", "https://h.test/x", 403, "MAYBE")


def test_a_robots_recheck_hold_is_due_again_before_its_cadence() -> None:
    acol, _ = _desk_modules()
    src = {"id": "s", "cadence": "monthly"}
    now = 1_000_000.0
    held = {"s": {"last_attempt_epoch": now - 10, "recheck_after_epoch": now - 1}}
    assert acol.due(src, held, now) is True
    waiting = {"s": {"last_attempt_epoch": now - 10, "recheck_after_epoch": now + 100}}
    assert acol.due(src, waiting, now) is False


def test_the_acquisition_scientist_never_requests_a_disallowed_sample(
        iso: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """The second shared fetch path: robots read under `acquire_datasets`' own UA, and a
    Disallow means `_fetch` is never reached."""
    das = iso.das
    from research import acquire_datasets as aq
    net = _net(monkeypatch, DISALLOW)
    verdict = ac.classify({"url": PAGE, "source_class": "official"})
    contract = SimpleNamespace(admissible=lambda: True)
    out = das.sample({"dataset": "probe", "url": PAGE}, contract, verdict,
                     at="2026-10-14T08:00:00+00:00", code="test", marks=set())
    assert net.urls() == [ROBOTS]
    assert net.seen[0][1] == iso.acol.DESK_UA != aq._UA, "robots read under the honest UA"
    assert out["status"] == "BLOCKED_BY_ROBOTS" and out["hold_cause"] == "robots:disallow"
    assert out["robots_disallows"] is True and "robots" in out and out["terms_note"]


# --------------------------------------- the page itself: 401/403/429 or a WAF is a HARD_STOP

ALLOW_ALL = b"User-agent: *\nAllow: /\n"
CF_PAGE = (b"<!DOCTYPE html><html><head><title>Just a moment...</title></head>"
           b"<body>Checking your browser</body></html>")


@pytest.mark.parametrize("code", [401, 403, 429])
def test_a_page_401_403_429_is_a_hard_stop_and_the_host_gets_nothing_after(
        code: int, iso: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """The principal's standing rule. The row stays visible with its hold_cause; a pass at +25h
    sends ZERO requests -- not even robots.txt -- and after release the next pass fetches."""
    acol = iso.acol
    net = _net(monkeypatch, ALLOW_ALL, code)
    rec = _collect(iso)
    assert net.urls() == [ROBOTS, PAGE]
    assert rec["status"] == "HARD_STOP" and rec["hold_cause"] == f"hard_stop:{code}"
    assert rec["id"] == "robots_probe" and rec["http"] == code
    hold = acol.active_site_hold(HOST)
    assert hold is not None and hold["verdict"] == "HARD_STOP" and hold["status"] == code
    assert hold["key"] == f"site:{HOST}" and hold["released_by"] is None
    assert hold == rec["site_hold"]

    net.page = None                                   # the site would answer now; still held
    iso.clock.t = T0 + 25 * 3600
    rec = _collect(iso)
    assert rec["status"] == "HARD_STOP" and rec["hold_cause"] == f"hard_stop:{code}"
    assert net.urls() == [ROBOTS, PAGE], "zero requests to a HARD_STOP host at +25h"

    acol.release_site_hold(HOST, "zuck")
    rec = _collect(iso)
    assert rec["status"] not in ("HARD_STOP", "BLOCKED_BY_ROBOTS")
    assert net.urls()[-1] == PAGE, "after release the next pass fetches"


def test_a_cf_mitigated_challenge_header_is_a_hard_stop_even_on_a_200(
        iso: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    _net(monkeypatch, ALLOW_ALL, (200, {"cf-mitigated": "challenge"}, CF_PAGE))
    rec = _collect(iso)
    assert rec["status"] == "HARD_STOP" and rec["hold_cause"] == "hard_stop:200"
    assert iso.acol.active_site_hold(HOST)["status"] == 200
    assert not (iso.tmp / "vault").exists(), "a challenge page is never vaulted as data"


def test_a_503_carrying_the_cloudflare_challenge_title_is_a_hard_stop(
        iso: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    _net(monkeypatch, ALLOW_ALL, (503, {}, CF_PAGE))
    rec = _collect(iso)
    assert rec["status"] == "HARD_STOP" and rec["hold_cause"] == "hard_stop:503"


def test_a_plain_503_is_an_ordinary_error_not_a_hold(
        iso: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    net = _net(monkeypatch, ALLOW_ALL, (503, {}, b"<html><title>Service Unavailable</title>"))
    rec = _collect(iso)
    assert rec["status"] == "HTTP_ERROR" and rec["http"] == 503
    assert iso.acol.active_site_hold(HOST) is None
    _collect(iso)
    assert net.urls().count(PAGE) == 2, "a 5xx host is asked again"


def test_challenge_text_on_a_200_page_is_never_a_hold() -> None:
    """Forum text quoting the title has false-positived before: a 200 body is not read."""
    acol, _ = _desk_modules()
    assert acol.is_challenge(200, {}, CF_PAGE) is False
    assert acol.is_challenge(403, {}, CF_PAGE) is True
    assert acol.is_challenge(503, {}, b"just a moment please") is False
    assert acol.is_challenge(200, {"cf-mitigated": "Challenge"}, b"") is True


def test_the_acquisition_scientist_sample_writes_a_hard_stop_on_403(
        iso: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    das = iso.das
    net = _net(monkeypatch, ALLOW_ALL, 403)
    verdict = ac.classify({"url": PAGE, "source_class": "official"})
    contract = SimpleNamespace(admissible=lambda: True)
    out = das.sample({"dataset": "probe", "url": PAGE}, contract, verdict,
                     at="2026-10-14T08:00:00+00:00", code="test", marks=set())
    assert out["status"] == "HARD_STOP" and out["hold_cause"] == "hard_stop:403"
    assert iso.acol.active_site_hold(HOST)["verdict"] == "HARD_STOP"
    assert out["site_hold"] == iso.acol.active_site_hold(HOST)
    iso.clock.t = T0 + 25 * 3600
    out = das.sample({"dataset": "probe", "url": PAGE}, contract, verdict,
                     at="2026-10-15T09:00:00+00:00", code="test", marks=set())
    assert out["status"] == "HARD_STOP" and out["hold_cause"] == "hard_stop:403"
    assert net.urls() == [ROBOTS, PAGE], "zero requests to the held host"


# ------------------------------------- one robots matcher: hard_stop.robots_verdict (audit probes)

def test_hard_stop_is_byte_identical_to_the_cleared_matcher() -> None:
    """`desks/mt5/research/hard_stop.py` is carried BYTE-IDENTICAL from alt-seat-cells bc6549361
    (CLEARed by the auditor), so the two branches merge cleanly. Pinned by its git blob id."""
    import hashlib
    raw = (_DESK / "research" / "hard_stop.py").read_bytes()
    blob = hashlib.sha1(b"blob %d\0" % len(raw) + raw).hexdigest()
    assert blob == "2bffab948c03a4a14795b38289e648d65ed81e29"
    acol, _ = _desk_modules()
    assert acol._HS.DESK_UA == acol.DESK_UA


ORIGIN = "https://data.robots.test:8443"


@pytest.mark.parametrize(("robots", "path", "allowed"), [
    # four pages the stdlib parser let through (audit 22b9c91a7)
    (b"User-agent: *\nAllow: /\nDisallow: /private\n", "/private/x.csv", False),
    (b"User-agent: *\nDisallow: /*.pdf\n", "/papers/a.pdf", False),
    (b"User-agent: *\nDisallow: /*.php$\n", "/index.php", False),
    (b"User-agent: quant-mt5-research-desk\nDisallow: /a\n\n"
     b"User-agent: quant-mt5-research-desk\nDisallow: /b\n", "/b/x.csv", False),
    # two pages it refused
    (b"User-agent: *\nDisallow: /data\nAllow: /data/public\n", "/data/public/x.csv", True),
    (b"User-agent: *\nDisallow: /x\nAllow: /x\n", "/x", True),
    # and the edges of the same rules
    (b"User-agent: *\nDisallow: /*.php$\n", "/index.php?q=1", True),
    (b"User-agent: *\nDisallow: /*.pdf\n", "/papers/a.csv", True),
])
def test_the_audit_robots_probes(robots: bytes, path: str, allowed: bool, iso: Any,
                                 monkeypatch: pytest.MonkeyPatch) -> None:
    net = _net(monkeypatch, robots)
    url = ORIGIN + path
    v = iso.acol.robots_verdict(url)
    assert v.allowed is allowed, v.why
    assert v.cause == ("allowed" if allowed else "disallow")
    rec = dict(iso.acol.collect_one({"id": "probe", "url": url, "expect": "csv"}))
    assert (url in net.urls()) is allowed, "a disallowed page is never requested"
    assert (rec["status"] == "BLOCKED_BY_ROBOTS") is (not allowed)


# ----------------------------------------------------------- every redirect hop is checked

B_HOST = "mirror.other.test"
B_ORIGIN = f"https://{B_HOST}"
B_ROBOTS = f"{B_ORIGIN}/robots.txt"


def _b_urls(net: _Net) -> list[str]:
    return [u for u in net.urls() if u.startswith(B_ORIGIN)]


def test_a_redirect_to_a_held_host_sends_it_nothing(
        iso: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    acol = iso.acol
    acol._record_site_hold(acol.site_hold_record(B_HOST, f"{B_ORIGIN}/x", 403, "HARD_STOP"))
    net = _net(monkeypatch, ALLOW_ALL)
    net.routes[PAGE] = ("redirect", f"{B_ORIGIN}/series/x.csv")
    rec = _collect(iso)
    assert _b_urls(net) == [], "zero requests to the held redirect target"
    assert rec["status"] == "HARD_STOP" and rec["redirected_to"] == f"{B_ORIGIN}/series/x.csv"
    assert acol.active_site_hold(HOST) is None, "the redirecting host is not held"
    # the scientist's path, through fetch_bytes, refuses the same hop
    raw, why = acol.fetch_bytes(PAGE)
    assert raw is None and why == "held:HARD_STOP" and _b_urls(net) == []


def test_a_redirect_to_a_robots_disallowed_path_is_not_fetched(
        iso: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    net = _net(monkeypatch, b"User-agent: *\nDisallow: /blocked/\n")
    target = f"{B_ORIGIN}/blocked/x.csv"
    net.routes[PAGE] = ("redirect", target, 301)
    rec = _collect(iso)
    assert B_ROBOTS in net.urls(), "robots is read for the redirect target's own host"
    assert target not in net.urls()
    assert rec["status"] == "BLOCKED_BY_ROBOTS" and rec["hold_cause"] == "robots:disallow"
    assert rec["robots_disallows"] is True and rec["redirected_to"] == target
    raw, why = iso.acol.fetch_bytes(PAGE)
    assert raw is None and why == "robots:disallow" and target not in net.urls()


def test_a_403_after_a_redirect_holds_the_host_that_answered(
        iso: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    acol = iso.acol
    net = _net(monkeypatch, ALLOW_ALL)
    target = f"{B_ORIGIN}/series/x.csv"
    net.routes[PAGE] = ("redirect", target)
    net.routes[target] = 403
    rec = _collect(iso)
    assert rec["status"] == "HARD_STOP" and rec["hold_cause"] == "hard_stop:403"
    held = acol.active_site_hold(B_HOST)
    assert held is not None and held["key"] == f"site:{B_HOST}" and held["url"] == target
    assert acol.active_site_hold(HOST) is None, "never the host that only redirected"
    n = len(_b_urls(net))
    iso.clock.t = T0 + 25 * 3600
    _collect(iso)
    assert len(_b_urls(net)) == n, "the answering host gets nothing after"


def test_a_followed_redirect_on_an_allowed_path_fetches(
        iso: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    net = _net(monkeypatch, ALLOW_ALL)
    target = f"{B_ORIGIN}/series/x.csv"
    net.routes[PAGE] = ("redirect", target, 308)
    rec = _collect(iso)
    assert net.urls() == [ROBOTS, PAGE, B_ROBOTS, target]
    assert rec["status"] in ("COLLECTED", "NEEDS_PARSER") and rec["redirected_to"] == target


def test_redirects_are_capped(iso: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    net = _net(monkeypatch, ALLOW_ALL)
    net.routes[PAGE] = ("redirect", PAGE)
    rec = _collect(iso)
    assert rec["status"] == "UNREACHABLE" and "redirects" in rec["why"]
    assert net.urls().count(PAGE) == iso.acol.MAX_REDIRECTS + 1


def test_a_robots_txt_redirect_to_a_held_host_sends_it_nothing(
        iso: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    acol = iso.acol
    acol._record_site_hold(acol.site_hold_record(B_HOST, B_ROBOTS, 429, "ROBOTS_HOLD"))
    net = _net(monkeypatch, ALLOW_ALL)
    net.routes[ROBOTS] = ("redirect", B_ROBOTS)
    v = acol.robots_verdict(PAGE)
    assert v.allowed is False and v.cause == "person_hold"
    assert _b_urls(net) == [] and PAGE not in net.urls()


def test_a_robots_txt_redirect_that_answers_403_holds_the_answering_host(
        iso: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    acol = iso.acol
    net = _net(monkeypatch, ALLOW_ALL)
    net.routes[ROBOTS] = ("redirect", B_ROBOTS)
    net.routes[B_ROBOTS] = 403
    v = acol.robots_verdict(PAGE)
    assert v.allowed is False and v.cause == "person_hold"
    assert acol.active_site_hold(B_HOST)["verdict"] == "ROBOTS_HOLD"
    assert acol.active_site_hold(HOST) is None


def test_a_blank_released_by_releases_nothing(iso: Any) -> None:
    """An edited state file with released_by "" or whitespace is still a hold (audit should-fix)."""
    acol = iso.acol
    for blank in ("", "   "):
        rec = {**acol.site_hold_record(HOST, PAGE, 403, "HARD_STOP"), "released_by": blank}
        acol._record_site_hold(rec)
        assert acol.active_site_hold(HOST) is not None


def test_the_acquisition_scientist_reads_and_fetches_under_desk_ua(
        iso: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Never `acquire_datasets._UA` (a browser string): robots AND the fetch carry DESK_UA."""
    das = iso.das
    net = _net(monkeypatch, ALLOW_ALL)
    verdict = ac.classify({"url": PAGE, "source_class": "official"})
    contract = SimpleNamespace(admissible=lambda: True)
    das.sample({"dataset": "probe", "url": PAGE}, contract, verdict,
               at="2026-10-14T08:00:00+00:00", code="test", marks=set())
    assert net.urls() == [ROBOTS, PAGE]
    assert {ua for _, ua in net.seen} == {iso.acol.DESK_UA}
