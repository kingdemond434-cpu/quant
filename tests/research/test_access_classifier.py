"""THE ACCESS ROUTER, against LAWS 5e -- every label reachable, the boundary absolute, the three
dimensions independent, and fringe material PRESERVED.

The load-bearing assertions here are the two that a timid refactor would break first:

  * AN UNRELIABLE PUBLIC CLAIM STAYS RESEARCHABLE. The moment credibility starts deciding
    legality, the desk has collapsed three axes into one and deleted its own crowding signal.
  * machine_use_allowed=false ROUTES, IT DOES NOT DROP. The source is registered and reachable by
    API or manual review; only the one prohibited use is removed. "Looks restricted -> discard"
    is the exact behaviour the law forbids.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from libs.research import access_classifier as ac  # noqa: E402


# ------------------------------------------------------------------ every label is reachable --
def test_every_access_label_is_reachable_from_real_metadata() -> None:
    """A label no metadata can produce is a label the desk cannot use."""
    cases: dict[str, dict[str, object]] = {
        "PUBLIC": {"url": "https://www.boj.or.jp/statistics", "source_class": "official"},
        "PUBLIC_WITH_TERMS": {"url": "https://example.com/data", "machine_use_allowed": False},
        "LICENSED": {"url": "https://vendor.example/feed", "obtained": "licensed_feed",
                     "licence": "vendor commercial agreement"},
        "OPEN_DATA": {"url": "https://data.gov/set", "licence": "CC0"},
        "PUBLIC_ARCHIVE": {"url": "https://web.archive.org/x", "obtained": "archive"},
        "PUBLIC_SOCIAL": {"url": "https://forum.example/t/1", "source_class": "retail_ecology"},
        "USER_SUBMITTED": {"url": "https://example.com/p", "obtained": "user_submission"},
        "ACCESS_UNCLEAR": {},
        "PRIVATE": {"url": "https://intranet.example.com/reports"},
        "CONFIDENTIAL_MNPI": {"url": "https://x.example/n", "text": "insider tip: pre-release "
                                                                   "earnings for the quarter"},
        "STOLEN_UNAUTHORIZED": {"url": "https://x.example/n", "text": "full password dump"},
    }
    assert set(cases) == set(ac.ACCESS_LABELS), "a label has no case, or a case has no label"
    for label, meta in cases.items():
        assert ac.classify(meta).access_label == label, (label, meta)


def test_the_routing_table_covers_every_label_with_a_reason_and_a_cap() -> None:
    assert set(ac.ROUTING) == set(ac.ACCESS_LABELS)
    for label, row in ac.ROUTING.items():
        assert str(row["reason"]).strip(), label
        assert 0.0 <= float(row["evidence_weight_cap"]) <= 1.0, label
        assert set(row["allowed_uses"]) <= set(ac.USES), label


def test_the_principle_and_the_hard_boundary_are_carried_verbatim() -> None:
    assert ac.PRINCIPLE == ("Mine aggressively; classify precisely; restrict only the specific "
                            "use that is actually prohibited.")
    for clause in ("no credential theft", "no access-control bypass",
                   "no private or confidential data harvesting", "no doxxing",
                   "no stolen datasets",
                   "no material nonpublic information used for trading"):
        assert clause in ac.HARD_BOUNDARY
    assert ac.STAGES == ("DISCOVER", "CAPTURE_METADATA", "LEGAL_ACCESS", "EVIDENCE_CLASS",
                         "RESEARCH")


# ------------------------------------------------------------------------------- quarantine --
def test_access_unclear_is_quarantined_and_never_discarded() -> None:
    v = ac.classify({})
    assert v.access_label == "ACCESS_UNCLEAR" and v.quarantine is True and v.refused is False
    # METADATA KEPT, CONTENT NOT CONSUMED: register is permitted, nothing else is.
    assert v.allowed_uses == ("register",) and v.may("register")
    assert not v.may("machine_extract") and not v.may("alpha_input")
    assert v.evidence_weight_cap == 0.0


def test_a_quarantined_row_keeps_its_metadata_and_drops_its_content() -> None:
    out = ac.route({"source_id": "s1"}, {"claim": "gold rallies on Tuesdays"})
    assert out.verdict.access_label == "ACCESS_UNCLEAR"
    assert out.stage == "LEGAL_ACCESS" and out.researchable is False
    assert out.dropped is False, "quarantine keeps the row: the question is answered later"
    assert out.evidence is not None
    assert out.evidence.source_id == "s1" and out.evidence.claim_text == ""
    assert out.evidence.evidence_weight == 0.0 and "QUARANTINED" in out.why


# ----------------------------------------------------------------- the three refused labels --
def test_the_three_prohibited_labels_are_refused_with_a_reason() -> None:
    for meta, label in (
            ({"url": "https://x/y", "requires_auth": True}, "PRIVATE"),
            ({"url": "https://x/y", "text": "board minutes, not yet public"},
             "CONFIDENTIAL_MNPI"),
            ({"url": "https://x/y", "text": "leaked database of the vendor"},
             "STOLEN_UNAUTHORIZED")):
        v = ac.classify(meta)
        assert v.access_label == label and v.refused is True
        assert v.allowed_uses == () and v.evidence_weight_cap == 0.0
        assert v.reason.strip() and v.basis.strip()
        out = ac.route(meta, {"claim": "x"})
        assert out.stage == "LEGAL_ACCESS" and out.researchable is False
        assert out.evidence is None and out.why.startswith("REFUSED:")
        assert label in ac.REFUSED_LABELS


def test_the_hard_boundary_beats_a_permissive_licence_field() -> None:
    """A licence saying 'public domain' on a credential list does not make it public."""
    v = ac.classify({"url": "https://x/y", "licence": "CC0",
                     "text": "combolist of accounts"})
    assert v.access_label == "STOLEN_UNAUTHORIZED" and v.refused is True


def test_a_leaked_looking_obtained_path_is_refused_without_any_keyword() -> None:
    v = ac.classify({"url": "https://x/y", "obtained": "leaked_looking"})
    assert v.access_label == "STOLEN_UNAUTHORIZED"


# -------------------------------------------------------------------- terms: route, not drop --
def test_machine_use_disallowed_routes_to_manual_or_api_and_is_never_scraped() -> None:
    v = ac.classify({"url": "https://example.com/data", "machine_use_allowed": False})
    assert v.access_label == "PUBLIC_WITH_TERMS"
    assert v.machine_use_allowed is False
    assert not v.may("machine_extract"), "the one prohibited use is the one removed"
    assert not v.may("store_raw")
    # REGISTERED, NEVER OMITTED: every other use survives.
    assert v.may("register") and v.may("read_manual") and v.may("fetch_api")
    assert v.may("alpha_input") and v.refused is False and v.quarantine is False
    out = ac.route({"url": "https://example.com/data", "machine_use_allowed": False},
                   {"claim": "cash-and-carry basis widens into quarter end"})
    assert out.researchable is True and out.stage == "RESEARCH"
    assert "manual review" in out.why


def test_a_robots_disallow_is_the_same_fact_in_another_format() -> None:
    v = ac.classify({"url": "https://example.com/x", "robots": "disallow"})
    assert v.access_label == "PUBLIC_WITH_TERMS" and v.machine_use_allowed is False
    assert not v.may("machine_extract") and v.may("fetch_api")


# ----------------------------------------------------------------------------- independence --
def test_an_unreliable_public_claim_stays_researchable_at_low_weight() -> None:
    """Legality, credibility and predictive value are INDEPENDENT. Doubt lowers weight; it never
    decides access, and it never deletes the row."""
    out = ac.route({"url": "https://forum.example/t/9", "source_class": "retail_ecology"},
                   {"claim": "a whale is about to squeeze silver", "credibility": "UNRELIABLE"})
    assert out.verdict.access_label == "PUBLIC_SOCIAL" and out.verdict.refused is False
    assert out.researchable is True and out.stage == "RESEARCH"
    assert out.evidence is not None
    assert out.evidence.credibility == "UNRELIABLE"
    assert 0.0 < out.evidence.evidence_weight < 0.5
    assert out.evidence.narrative_feature is True


def test_credibility_never_changes_the_access_label() -> None:
    base = {"url": "https://example.com/a", "source_class": "media"}
    labels = {ac.route(base, {"claim": "c", "credibility": c}).verdict.access_label
              for c in ac.CREDIBILITIES}
    assert labels == {"PUBLIC"}, "credibility moved a LEGAL label: the axes have collapsed"


def test_an_authoritative_source_can_still_be_not_predictive() -> None:
    out = ac.route({"url": "https://www.ecb.europa.eu/s", "source_class": "official"},
                   {"claim": "HICP release schedule", "predictive_state": "NOT_PREDICTIVE"})
    assert out.evidence is not None
    assert out.evidence.credibility == "AUTHORITATIVE"
    assert out.evidence.predictive_state == "NOT_PREDICTIVE"
    assert out.evidence.evidence_weight == 1.0, "usefulness is not legality and not credibility"


# ------------------------------------------------------------------- fringe is PRESERVED --
def test_fringe_material_is_preserved_with_lowered_weight_and_never_dropped() -> None:
    obj = ac.EvidenceObject(source_id="s", claim_text="the fix is manipulated every month end",
                            access_label="PUBLIC", credibility="FRINGE").preserve()
    assert obj.claim_text, "preserve() must never empty a lawful public claim"
    assert obj.evidence_weight == ac.CREDIBILITY_WEIGHT["FRINGE"]
    assert obj.evidence_weight > 0.0
    assert obj.narrative_feature is True
    assert obj.predictive_state == "NARRATIVE_FEATURE"


def test_a_contradicted_claim_becomes_a_narrative_feature_rather_than_a_deletion() -> None:
    obj = ac.EvidenceObject(source_id="s", claim_text="rumour", access_label="PUBLIC_SOCIAL",
                            credibility="RELIABLE", contradictions=("claim_7",)).preserve()
    assert obj.narrative_feature is True and obj.predictive_state == "NARRATIVE_FEATURE"
    assert obj.evidence_weight > 0.0 and obj.contradictions == ("claim_7",)


def test_the_weight_is_the_lower_of_the_access_cap_and_the_credibility_weight() -> None:
    social = ac.EvidenceObject(source_id="s", claim_text="c", access_label="PUBLIC_SOCIAL",
                               credibility="AUTHORITATIVE").preserve()
    assert social.evidence_weight == ac.ROUTING["PUBLIC_SOCIAL"]["evidence_weight_cap"]
    public = ac.EvidenceObject(source_id="s", claim_text="c", access_label="PUBLIC",
                               credibility="UNRELIABLE").preserve()
    assert public.evidence_weight == ac.CREDIBILITY_WEIGHT["UNRELIABLE"]


def test_preserve_is_idempotent() -> None:
    once = ac.EvidenceObject(source_id="s", claim_text="c", access_label="PUBLIC",
                             credibility="FRINGE").preserve()
    assert once.preserve() == once


# ------------------------------------------------------------------------ the five stages --
def test_route_names_the_stage_that_decided() -> None:
    assert ac.route({}, {}).stage == "CAPTURE_METADATA"
    assert ac.route({"url": "https://x/y", "requires_auth": True}, {"claim": "c"}).stage \
        == "LEGAL_ACCESS"
    assert ac.route({"source_id": "s"}, {"claim": "c"}).stage == "LEGAL_ACCESS"   # quarantine
    assert ac.route({"url": "https://x/y", "source_class": "academic"},
                    {"claim": "c"}).stage == "RESEARCH"
    for r in (ac.route({}, {}), ac.route({"url": "https://x/y"}, {"claim": "c"})):
        assert r.stage in ac.STAGES


def test_an_empty_row_is_the_only_thing_that_is_actually_dropped() -> None:
    assert ac.route({}, {}).dropped is True
    assert ac.route({"source_id": "s"}, {"claim": "c"}).dropped is False


def test_the_ten_source_classes_are_the_laws_ten() -> None:
    assert ac.SOURCE_CLASSES == ("official", "institutional", "academic", "practitioner",
                                 "retail_ecology", "app_ecosystem", "media", "archive",
                                 "physical_economy", "source_graph")
    assert set(ac.CLASS_CREDIBILITY) == set(ac.SOURCE_CLASSES)


def test_classification_is_deterministic() -> None:
    meta = {"url": "https://example.com/a", "source_class": "practitioner"}
    assert [ac.classify(meta) for _ in range(3)].count(ac.classify(meta)) == 3
