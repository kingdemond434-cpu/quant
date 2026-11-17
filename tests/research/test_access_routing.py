"""ACCESS ROUTING (LAWS 5e, principal 2026-09-23): classification routes USE, never mining.

The law this pins is one sentence: the desk mines and tests EVERYTHING it can see on the open
internet, and licence, robots, source class and credibility are routing and provenance labels
that describe what may be REDISTRIBUTED and how much weight the evidence carries -- never whether
a row is discovered, ingested, represented or tested.

The three cases the principal named are the first three tests. The rest exist because this law
has been re-derived into caution twice, and a test is the only thing that survives a rewrite:
every deleted brake gets a test that FAILS if someone puts it back, and the five refused acts get
a test that fails if someone adds a sixth.

PURE. `access_classifier` does no IO; nothing here writes a file.
"""
from __future__ import annotations

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


def test_a_robots_disallowed_page_is_catalogued_and_never_fetched() -> None:
    """INVERTED 2026-11-17 (LAWS 5e act 6). A robots.txt Disallow refuses the automated fetch
    again. The row is NOT dropped: it is catalogued as PUBLIC_WITH_TERMS from what was lawfully
    seen elsewhere, with the reason in `terms_note`, and never fetched."""
    routed = ac.route({"source_id": "forum", "url": "https://forum.test/threads",
                       "robots": "disallow", "source_class": "media"},
                      {"claim": "the desk over there is short the carry"})

    assert routed.verdict.access_label == "PUBLIC_WITH_TERMS"
    assert routed.researchable is True and routed.dropped is False
    assert routed.verdict.refused is False, "act 6 is not a refused LABEL"
    assert routed.verdict.fetch_allowed is False
    assert routed.verdict.machine_use_allowed is False
    assert routed.verdict.may("machine_extract") is False
    assert routed.verdict.may("store_raw") is False
    assert routed.verdict.may("fetch_api") is False
    assert routed.verdict.may("register") is True
    assert routed.verdict.redistribute_allowed is False
    assert "robots=disallow" in routed.verdict.terms_note
    assert routed.evidence is not None
    assert routed.evidence.provenance["terms_note"] == routed.verdict.terms_note
    assert routed.evidence.provenance["fetch_allowed"] is False


# ----------------------------------------------------------------- the boundary, exactly five

def test_the_hard_boundary_is_exactly_six_acts() -> None:
    """A seventh entry here is a new brake wearing the boundary's clothes. The count is pinned so
    it cannot be added quietly. Act 6 is the Governance amendment of 2026-11-17."""
    assert len(ac.HARD_BOUNDARY) == ac.HARD_BOUNDARY_COUNT == 6
    joined = " | ".join(ac.HARD_BOUNDARY).lower()
    for act in ("credential theft", "logging in as someone else", "access control", "paywall",
                "material non-public", "stolen or leaked", "doxxing",
                "no automated fetch that the host's robots.txt or terms refuse"):
        assert act in joined, act
    assert ac.HARD_BOUNDARY[5] == ac.FETCH_ACT


def test_only_three_labels_are_ever_refused() -> None:
    """Every other label is mined. This is the list that must not grow."""
    assert ac.REFUSED_LABELS == ("PRIVATE", "CONFIDENTIAL_MNPI", "STOLEN_UNAUTHORIZED")
    refused = {lab for lab, row in ac.ROUTING.items() if row["refused"]}
    assert refused == set(ac.REFUSED_LABELS)
    assert set(ac.MINED_LABELS) == set(ac.ACCESS_LABELS) - refused


@pytest.mark.parametrize("label", [lab for lab in ac.ACCESS_LABELS
                                   if lab not in ac.REFUSED_LABELS])
def test_every_mined_label_grants_the_full_mining_vocabulary(label: str) -> None:
    """No label withholds discovery, ingestion, representation or testing of content the desk
    may fetch -- only `redistribute` is withheld by the label, and that is a publication
    question. Act 6 withholds the FETCH uses on the VERDICT of a refused row, never in this
    table (see `test_each_fetch_refusal_is_enforced`)."""
    uses = ac.ROUTING[label]["allowed_uses"]
    for use in ac.MINING_USES:
        assert use in uses, f"{label} withholds {use}"
    assert ac.ROUTING[label]["quarantine"] is False
    assert ac.ROUTING[label]["evidence_weight_cap"] > 0.0


def test_no_routing_row_quarantines_anything() -> None:
    """The quarantine was the single largest brake: it kept metadata and threw the content away."""
    assert not [lab for lab, row in ac.ROUTING.items() if row["quarantine"]]


def test_the_deleted_brakes_are_named_in_the_module() -> None:
    """A later session must not re-derive the old caution from silence (LAWS 5e). The robots,
    machine-use and machine-extraction items are RESTORED as fetch refusals (2026-11-17) and are
    no longer named as deleted."""
    named = " | ".join(ac.REMOVED_BRAKES).lower()
    for brake in ("quarantine", "public/licensed sources only", "source-class and credibility"):
        assert brake in named, brake
    for restored in ("machine-extraction veto", "robots", "machine_use_allowed"):
        assert restored not in named, restored
    assert set(ac.FETCH_REFUSALS).isdisjoint(ac.REMOVED_BRAKES)


@pytest.mark.parametrize(("item", "meta"), [
    ("machine-extraction veto on PUBLIC_WITH_TERMS", {"machine_extraction_allowed": False}),
    ("robots.txt Disallow treated as a refusal", {"robots": "disallow"}),
    ("machine_use_allowed=false treated as 'registered, never scraped'",
     {"machine_use_allowed": False}),
])
def test_each_fetch_refusal_is_enforced(item: str, meta: dict) -> None:
    """Every item of FETCH_REFUSALS is a LIVE refusal of the automated fetch (LAWS 5e act 6):
    catalogued as PUBLIC_WITH_TERMS, reason in terms_note, never fetched, never dropped."""
    assert item in ac.FETCH_REFUSALS
    routed = ac.route({"source_id": "s", "url": "https://host.test/p", **meta},
                      {"claim": "a snippet seen in a search result"})
    v = routed.verdict
    assert v.access_label == "PUBLIC_WITH_TERMS"
    assert v.fetch_allowed is False and v.fetchable is False and v.machine_use_allowed is False
    assert v.refused is False and routed.dropped is False
    for use in ac.FETCH_USES:
        assert not v.may(use), (item, use)
    assert v.may("register")
    assert v.fetch_refusal and v.fetch_refusal in v.terms_note
    assert "never fetched" in v.terms_note


def test_every_fetch_refusal_item_is_covered_by_a_test() -> None:
    assert len(ac.FETCH_REFUSALS) == 3


def test_the_principle_says_robots_and_terms_decide_the_fetch() -> None:
    text = ac.PRINCIPLE.lower()
    assert "mines and tests everything" in text
    assert "robots and terms decide whether the desk fetches" in text
    assert "never stop ingestion, representation or testing of that content" in text


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


# -------------------------------------------------- the shared fetch path carries no brake

def test_the_shared_fetch_path_obeys_robots_and_fails_closed() -> None:
    """STRUCTURAL, as before, but inverted by Governance with the Auditor (2026-11-13): our own
    crawling OBEYS robots.txt. `asia_collector.collect_one` (called by `event_surprise` and
    `data_acquisition_scientist`) must return ROBOTS_REFUSED before its fetch, and the sampler
    must not fetch past a refusal either. Labels still route use and weight (LAWS 5e)."""
    from pathlib import Path

    repo = Path(__file__).resolve().parents[2]
    acol = (repo / "desks/mt5/research/asia_collector.py").read_text("utf-8")
    assert 'rec.update({"status": ROBOTS_STATUS' in acol
    fetch_at = acol.index("urllib.request.urlopen(req, timeout=timeout")
    assert acol.index("allowed, why_robots = _robots_allows(url)") < fetch_at
    das = (repo / "desks/mt5/research/data_acquisition_scientist.py").read_text("utf-8")
    assert '"status": "ROBOTS_REFUSED"' in das
    assert "never a skip (LAWS 5e)" not in das
