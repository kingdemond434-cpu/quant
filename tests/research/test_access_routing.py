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


def _desk_modules() -> tuple[Any, Any]:
    for p in (str(_ROOT), str(_DESK), str(_DESK / "research")):
        if p not in sys.path:
            sys.path.insert(0, p)
    from research import asia_collector as acol
    from research import data_acquisition_scientist as das
    return acol, das


class _Resp:
    def __init__(self, body: bytes, ctype: str = "text/csv") -> None:
        self._body = body
        self.status = 200
        self.headers = {"Content-Type": ctype}

    def __enter__(self) -> _Resp:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def read(self, n: int = -1) -> bytes:
        return self._body if n < 0 else self._body[:n]


CSV = b"date,value\n2026-01-01,1\n2026-01-02,2\n2026-01-03,3\n2026-01-04,4\n"


def _stub_urllib(monkeypatch: pytest.MonkeyPatch, robots: Any) -> list[tuple[str, str]]:
    """Replace urlopen. `robots` is bytes (a 200 body), an int (an HTTP error code) or an
    exception instance (unreachable). Returns every (url, user-agent) requested, in order."""
    seen: list[tuple[str, str]] = []

    def fake(req: Any, *a: Any, **k: Any) -> _Resp:
        url = req.full_url if isinstance(req, urllib.request.Request) else str(req)
        ua = req.get_header("User-agent") if isinstance(req, urllib.request.Request) else ""
        seen.append((url, str(ua or "")))
        if url.endswith("/robots.txt"):
            if isinstance(robots, bytes):
                return _Resp(robots, "text/plain")
            if isinstance(robots, int):
                raise urllib.error.HTTPError(url, robots, "stub", None, None)  # type: ignore[arg-type]
            raise robots
        return _Resp(CSV)

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    return seen


PAGE = "https://data.robots.test:8443/series/x.csv"
DISALLOW = b"User-agent: *\nDisallow: /series/\n"


def _collect(acol: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    monkeypatch.setattr(acol, "VAULT", tmp_path / "vault")
    monkeypatch.setattr(acol, "SERIES", tmp_path / "series")
    return dict(acol.collect_one({"id": "robots_probe", "url": PAGE, "expect": "csv",
                                  "access": "public"}))


def test_asia_collector_never_requests_a_robots_disallowed_page(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """BEHAVIOURAL, no network. A Disallow is a named HOLD and the page request never happens;
    robots.txt is read at the EXACT origin (port included) under the UA the fetch sends."""
    acol, _ = _desk_modules()
    seen = _stub_urllib(monkeypatch, DISALLOW)
    rec = _collect(acol, tmp_path, monkeypatch)

    assert [u for u, _ in seen] == ["https://data.robots.test:8443/robots.txt"]
    assert seen[0][1] == acol.USER_AGENT
    assert rec["status"] == "BLOCKED_BY_ROBOTS"
    assert rec["hold_cause"] == "robots:disallow"
    assert rec["robots_disallows"] is True and rec["robots"]
    assert "not fetched" in rec["terms_note"] and "HOLD" in rec["why"]
    assert rec["id"] == "robots_probe", "the source's row stays visible"
    assert not (tmp_path / "vault").exists()


def test_asia_collector_fetches_an_allowed_page_under_the_same_agent(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    acol, _ = _desk_modules()
    seen = _stub_urllib(monkeypatch, b"User-agent: *\nDisallow: /private/\n")
    rec = _collect(acol, tmp_path, monkeypatch)
    assert [u for u, _ in seen] == ["https://data.robots.test:8443/robots.txt", PAGE]
    assert {ua for _, ua in seen} == {acol.USER_AGENT}
    assert rec["robots_disallows"] is False and rec["status"] != "BLOCKED_BY_ROBOTS"


def test_a_rule_written_for_our_agent_binds_even_when_star_allows(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    acol, _ = _desk_modules()
    seen = _stub_urllib(monkeypatch, b"User-agent: quant-desk-collector\nDisallow: /\n\n"
                                     b"User-agent: *\nAllow: /\n")
    rec = _collect(acol, tmp_path, monkeypatch)
    assert rec["status"] == "BLOCKED_BY_ROBOTS" and len(seen) == 1


def test_robots_404_means_allow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    acol, _ = _desk_modules()
    seen = _stub_urllib(monkeypatch, 404)
    v = acol.robots_verdict(PAGE)
    assert v.allowed is True and v.cause == "robots_absent" and v.recheck is False
    rec = _collect(acol, tmp_path, monkeypatch)
    assert rec["status"] != "BLOCKED_BY_ROBOTS" and seen[-1][0] == PAGE


@pytest.mark.parametrize("code", [500, 503])
def test_robots_5xx_means_disallow_for_now_and_recheck(
        code: int, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    acol, _ = _desk_modules()
    seen = _stub_urllib(monkeypatch, code)
    rec = _collect(acol, tmp_path, monkeypatch)
    assert rec["status"] == "BLOCKED_BY_ROBOTS" and rec["hold_cause"] == "robots:robots_5xx"
    assert rec["robots_recheck"] is True
    assert [u for u, _ in seen] == ["https://data.robots.test:8443/robots.txt"]


def test_an_unreachable_robots_is_disallow_for_now_never_allowing(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The old helper said "unreadable; treated as allowing". RFC 9309 says the opposite."""
    acol, _ = _desk_modules()
    seen = _stub_urllib(monkeypatch, urllib.error.URLError("no route"))
    rec = _collect(acol, tmp_path, monkeypatch)
    assert rec["status"] == "BLOCKED_BY_ROBOTS"
    assert rec["hold_cause"] == "robots:robots_unreachable" and rec["robots_recheck"] is True
    assert len(seen) == 1


def test_robots_403_is_a_hold(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    acol, _ = _desk_modules()
    seen = _stub_urllib(monkeypatch, 403)
    rec = _collect(acol, tmp_path, monkeypatch)
    assert rec["status"] == "BLOCKED_BY_ROBOTS"
    assert rec["hold_cause"] == "robots:robots_forbidden" and rec["robots_recheck"] is True
    assert len(seen) == 1


def test_a_robots_recheck_hold_is_due_again_before_its_cadence() -> None:
    acol, _ = _desk_modules()
    src = {"id": "s", "cadence": "monthly"}
    now = 1_000_000.0
    held = {"s": {"last_attempt_epoch": now - 10, "recheck_after_epoch": now - 1}}
    assert acol.due(src, held, now) is True
    waiting = {"s": {"last_attempt_epoch": now - 10, "recheck_after_epoch": now + 100}}
    assert acol.due(src, waiting, now) is False


def test_the_acquisition_scientist_never_requests_a_disallowed_sample(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """The second shared fetch path: robots read under `acquire_datasets`' own UA, and a
    Disallow means `_fetch` is never reached."""
    _, das = _desk_modules()
    from research import acquire_datasets as aq
    seen = _stub_urllib(monkeypatch, DISALLOW)
    verdict = ac.classify({"url": PAGE, "source_class": "official"})
    contract = SimpleNamespace(admissible=lambda: True)
    out = das.sample({"dataset": "probe", "url": PAGE}, contract, verdict,
                     at="2026-10-14T08:00:00+00:00", code="test", marks=set())
    assert [u for u, _ in seen] == ["https://data.robots.test:8443/robots.txt"]
    assert seen[0][1] == aq._UA
    assert out["status"] == "BLOCKED_BY_ROBOTS" and out["hold_cause"] == "robots:disallow"
    assert out["robots_disallows"] is True and "robots" in out and out["terms_note"]
