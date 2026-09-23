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


def test_a_robots_disallowed_page_is_now_mined_and_labelled() -> None:
    """A robots.txt Disallow was read as a refusal and is now a LABEL. The page is mined and
    tested in full; what the label withholds is redistribution."""
    routed = ac.route({"source_id": "forum", "url": "https://forum.test/threads",
                       "robots": "disallow", "source_class": "media"},
                      {"claim": "the desk over there is short the carry"})

    assert routed.verdict.access_label == "PUBLIC_WITH_TERMS"
    assert routed.researchable is True
    assert routed.verdict.machine_use_allowed is True
    assert routed.verdict.may("machine_extract") is True
    assert routed.verdict.may("store_raw") is True
    # The fact is not lost -- it moved to the routing label and the provenance note.
    assert routed.verdict.redistribute_allowed is False
    assert "robots=disallow" in routed.verdict.terms_note
    assert routed.evidence is not None
    assert routed.evidence.provenance["terms_note"] == routed.verdict.terms_note


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
    """A later session must not re-derive the old caution from silence (LAWS 5e)."""
    named = " | ".join(ac.REMOVED_BRAKES).lower()
    for brake in ("quarantine", "machine-extraction veto", "robots", "machine_use_allowed",
                  "public/licensed sources only"):
        assert brake in named, brake


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
