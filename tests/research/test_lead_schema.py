"""ONE LEAD SCHEMA over the intake shapes the desk actually writes.

Every row below is a SHRUNKEN COPY OF A REAL ARTIFACT on this tree, field names and all --
`data/intelligence/literature/discoveries_20260916.json`, `.../asia/asia_plane_*.json`,
`.../reddit/rollup_*.jsonl.gz`, `.../arxiv_qfin/rollup_*.jsonl.gz`,
`.../world/discoveries_deepforest_*.json`, `.../mql5/signals_*.json` and
`frontier_intel/data/frontier_queue.jsonl`. A schema tested against invented rows is a schema
tested against itself.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from libs.research import lead_schema as ls  # noqa: E402

# --------------------------------------------------------------- the real intake shapes

LITERATURE = {
    "kind": "hypothesis", "family": "trend_ma_cross",
    "symbols": ["EURUSD", "USDJPY", "GBPUSD"], "source": "literature",
    "title": "Time series momentum in FX majors (Moskowitz, Ooi, Pedersen 2012)",
    "text": "Time series momentum: the sign of the past 12-month excess return predicts the next "
            "month's return across 58 liquid futures including FX majors. A moving-average cross "
            "is the executable proxy. We thank the referees.",
    "url": "https://www.aqr.com/Insights/Research/Journal-Article/Time-Series-Momentum",
    "found_at": "2026-09-16T08:00:00+00:00",
}

ASIA_PLANE = {
    "kind": "hypothesis", "family": "overnight_drift", "symbols": ["USDCNH"],
    "source": "asia:safe_fx_settlement", "cell_id": "f378d33e7bdd9e28",
    "asia_source_id": "safe_fx_settlement", "asia_plane": "cn_hard", "expression_kind": "flow",
    "tier": "BLOCKED_ON_DATA", "mechanism_status": "NAMED",
    "mechanism": "corporate FX demand imbalance is RMB pressure before it is a price",
    "url": "https://www.safe.gov.cn/safe/whxsdsj/index.html",
    "title": "SAFE bank FX settlement and sales -- cn_hard",
    "pit": {"event_time": "reference month", "publication_lag_days": 20},
    "text": "overnight_drift on USDCNH in the asia session drifts 0.3% into the fix.",
}

DEEP_FOREST = {
    "source": "deep_forest", "kind": "story_mechanism",
    "title": "七禾网: rebar basis converges the week before rollover",
    "description": "Rebar basis converges in the week before rollover and shorting the near "
                   "contract wins 62% of the time, held three sessions.",
    "url": "https://www.7hcn.com/article/1", "symbols": ["XAUUSD"],
    "mechanism_tags": ["basis"], "lang": "zh", "language": "zh",
    "ground": "七禾网", "ground_kind": "web", "region": "cn", "cluster": "cn",
    "channel": "direct", "mechanism_class": "carry", "evidence_grade": "COMMUNITY_POST",
    "claim_hash": "abc123", "published_time": "2026-09-01T00:00:00+00:00",
    "available_time": "2026-09-04T22:50:12+00:00", "n_tellings": 1,
}

REDDIT = {
    "source": "reddit", "subreddit": "Forex",
    "title": "6 NFP mornings on gold 5m: first 15 minute ranges from $5.73 to $48.48",
    "url": "", "symbols": ["XAUUSD"], "patterns": ["breakout"], "confidence": 0.3,
}

ARXIV = {
    "source": "arxiv_qfin", "kind": "paper",
    "title": "Convex Modeling of Price Cross-Impact over Time",
    "url": "http://arxiv.org/abs/2609.04712v1",
    "text": "Transaction costs can make or break a trading strategy. Price impact models omit "
            "cross-impact, which moves related contracts by 30 basis points. We are grateful to "
            "our colleagues.",
    "found_at": "2026-09-08T08:24:52+00:00",
}

FRONTIER = {
    "at": "2026-09-05T21:23:30+00:00", "candidate_id": "F-cc2f67f57bcdb874",
    "state": "DISCOVERED", "firm": "Two Sigma", "capability": "OPS",
    "source_url": "https://example.invalid/post",
    "claim": "market makers know where SPY will trade by 10am",
    "evidence_grade": "D", "source_kind": "public_forum",
}

DATASET = {
    "source": "deep_forest", "kind": "dataset", "title": "BCRP statistics database",
    "url": "https://estadisticas.bcrp.gob.pe/", "published": "2026-09-12T10:56:01+00:00",
    "symbols": [], "timeframes": [], "patterns": [], "confidence": 0.85, "lang": "es",
    "language": "es", "endpoints": ["https://a.invalid/x.xlsx"], "n_endpoints": 1,
    "ground": "BCRP", "region": "latam", "dataset_class": "macro_vintages",
}

MQL5_SIGNAL = {"source": "mql5_signals", "name": "Filter", "profit": "", "drawdown": "",
               "url": "https://www.mql5.com/en/signals", "confidence": 0.3}

CORPUS = (LITERATURE, ASIA_PLANE, DEEP_FOREST, REDDIT, ARXIV, FRONTIER, DATASET, MQL5_SIGNAL)


def _one(row, **kw):
    lead = ls.from_intelligence_row(row, **kw)
    assert lead is not None, f"row produced no lead: {row.get('source')}"
    return lead


# --------------------------------------------------------------- the adapters

def test_a_seat_hypothesis_row_keeps_its_family_and_is_testable() -> None:
    lead = _one(LITERATURE, seat="literature")
    assert lead.kind == "paper" and lead.source_id == "literature"
    assert lead.executable == {"family": "trend_ma_cross",
                               "params": {},
                               "symbols": ["EURUSD", "USDJPY", "GBPUSD"]}
    assert lead.instruments == ["EURUSD", "USDJPY", "GBPUSD"]
    assert lead.testable is True and lead.quality["verbatim"] is True
    assert lead.seen_at == "2026-09-16T08:00:00+00:00"
    assert not ls.validate(lead)


def test_the_asia_plane_row_carries_its_mechanism_and_a_lagged_pit_status() -> None:
    lead = _one(ASIA_PLANE, seat="asia")
    assert lead.instruments == ["USDCNH"]
    assert lead.structured is not None
    assert lead.structured["pit_status"] == "LAGGED", "a 20-day publication lag is not PIT clean"
    assert lead.structured["mechanism"].startswith("corporate FX demand")
    assert lead.axes.get("information_source") == "flow"
    assert lead.provenance["run"] == "f378d33e7bdd9e28"
    assert not ls.validate(lead)


def test_a_deep_forest_story_is_a_story_in_its_own_language_with_its_own_timestamps() -> None:
    lead = _one(DEEP_FOREST, seat="world")
    assert lead.kind == "story" and lead.language == "zh"
    assert "carry" in lead.mechanism_ids and "basis" in lead.mechanism_ids
    assert lead.knowable_at == "2026-09-01T00:00:00+00:00", "the POST time, never the crawl time"
    assert lead.seen_at == "2026-09-04T22:50:12+00:00"
    assert lead.testable is True
    assert not ls.validate(lead)


def test_a_crawler_row_with_no_body_is_carried_and_marked_not_verbatim() -> None:
    lead = _one(REDDIT, seat="reddit")
    assert lead.kind == "forum"
    assert lead.claim_text.startswith("6 NFP mornings")
    assert lead.quality["verbatim"] is False, "a title is a label, not the source's own claim"
    assert lead.quality["has_instrument"] is True and lead.quality["has_mechanism"] is True
    assert lead.testable is True


def test_a_frontier_queue_row_reads_its_claim_its_url_and_its_crawl_time() -> None:
    lead = _one(FRONTIER, seat="frontier")
    assert lead.kind == "forum", "source_kind public_forum"
    assert lead.claim_text == "market makers know where SPY will trade by 10am"
    assert lead.url_or_ref == "https://example.invalid/post"
    assert lead.seen_at == "2026-09-05T21:23:30+00:00"
    assert lead.testable is False, "no instrument the desk can price and no mechanism named"
    assert "ops" not in lead.mechanism_ids, "a firm's capability is an org chart, not a mechanism"
    assert "regime" not in lead.axes, "DISCOVERED is a workflow state, not a market regime"


def test_a_dataset_row_is_a_data_release_and_is_not_testable_on_its_own() -> None:
    lead = _one(DATASET, seat="world")
    assert lead.kind == "data_release"
    assert lead.testable is False, "a data endpoint is not a hypothesis"
    assert lead.structured is not None and lead.structured["required_data"] == [
        "https://a.invalid/x.xlsx"]


def test_operational_bookkeeping_is_never_a_lead() -> None:
    assert ls.from_intelligence_row({"source": "equiti_copy", "kind": "fetch_error",
                                     "title": "x"}) is None
    assert ls.from_intelligence_row({"source": "s", "needs_selector_work": True,
                                     "title": "x"}) is None
    assert ls.from_intelligence_row({"source": "s"}) is None
    assert ls.from_intelligence_row("not a row") is None  # type: ignore[arg-type]


def test_every_real_shape_adapts_and_validates_clean() -> None:
    for row in CORPUS:
        lead = _one(row, seat="seat", run="run-1")
        assert ls.validate(lead) == [], f"{row.get('source')}: {ls.validate(lead)}"
        assert lead.kind in ls.KINDS
        assert set(lead.provenance) >= {"miner", "seat", "run", "cell_key"}


# --------------------------------------------------------------- atomic claims

def test_claims_from_text_keeps_the_sentences_that_assert_something() -> None:
    text = ("We thank the anonymous referees. Gold rallies into the London fix in 62% of "
            "sessions. This paper is organised as follows. EURUSD mean-reverts after the "
            "New York close.")
    claims = ls.claims_from_text(text)
    assert len(claims) == 2
    assert claims[0].startswith("Gold rallies") and claims[1].startswith("EURUSD mean-reverts")
    assert ls.claims_from_text("") == []
    assert ls.claims_from_text(text, max_claims=1) == claims[:1]


def test_a_document_becomes_one_lead_per_claim_sharing_one_doc_id() -> None:
    leads = ls.leads_from_intelligence_row(ARXIV, seat="arxiv_qfin")
    assert len(leads) == 2, "two claim-bearing sentences, the acknowledgement dropped"
    assert [lead.claim_index for lead in leads] == [0, 1]
    assert len({lead.doc_id for lead in leads}) == 1, "one document"
    assert len({lead.lead_id for lead in leads}) == 2, "two claims"
    assert all(lead.kind == "paper" for lead in leads)


def test_a_cjk_document_splits_on_its_own_terminators() -> None:
    # The fullwidth comma is the one glyph here with an ASCII lookalike, so it is built from
    # its codepoint; the rest stay readable as themselves.
    text = ("黄金在伦敦定盘前上涨" + chr(0xFF0C)
            + "胜率 62%。"
            + "本文不提供建议。"
            + "原油在换月前一周基差收敛。")
    claims = ls.claims_from_text(text)
    assert len(claims) == 2, "the disclaimer sentence asserts nothing"


# --------------------------------------------------------------- the fourteen fields

def test_the_structured_block_is_exactly_fourteen_fields() -> None:
    assert len(ls.SPEC_FIELDS) == 14
    assert set(ls.blank_spec()) == set(ls.SPEC_FIELDS)
    assert all(v is None for v in ls.blank_spec().values())


def test_structured_complete_needs_all_fourteen_and_nothing_else() -> None:
    block = dict.fromkeys(ls.SPEC_FIELDS, "stated")
    assert ls.structured_complete(block) is True
    short = dict(block)
    short["falsifier"] = None
    assert ls.structured_complete(short) is False
    extra = dict(block)
    extra["extra_field"] = "x"
    assert ls.structured_complete(extra) is False, "a different schema is not a complete one"
    assert ls.structured_complete(None) is False


def test_an_incomplete_lead_is_low_priority_and_is_never_dropped() -> None:
    lead = _one(DEEP_FOREST, seat="world")
    assert lead.structured_complete is False
    assert lead.priority == ls.PRIORITY_LOW
    assert lead.spec_gaps(), "the gaps are named, not hidden"
    assert "counterparty" in lead.spec_gaps()
    assert not ls.validate(lead), "low priority is a state, not a validation failure"


def test_a_fully_specified_row_is_complete_and_normal_priority() -> None:
    spec = dict.fromkeys(ls.SPEC_FIELDS, "stated")
    spec["asset_mapping"] = ["XAUUSD"]
    spec["required_data"] = ["bars"]
    spec["pit_status"] = "PIT_CLEAN"
    row = {"source": "kimi", "title": "t", "text": "Gold rallies into the fix in 62% of sessions.",
           "symbols": ["XAUUSD"], "mechanism_class": "session", "structured": spec}
    lead = _one(row, seat="kimi")
    assert lead.structured_complete is True and lead.priority == ls.PRIORITY_NORMAL
    assert lead.spec_gaps() == []
    assert not ls.validate(lead)


# --------------------------------------------------------------- knowable_at

def test_knowable_at_is_the_publish_time_and_seen_at_the_crawl_time() -> None:
    lead = _one(DEEP_FOREST, seat="world")
    assert lead.knowable_at < lead.seen_at
    no_publish = _one(REDDIT, seat="reddit")
    assert no_publish.knowable_at == "", "unknown is empty, never back-filled from the crawl"


def test_a_lead_crawled_before_it_was_publishable_is_a_validation_problem() -> None:
    lead = _one(DEEP_FOREST, seat="world")
    broken = ls.from_row({**ls.to_row(lead), "knowable_at": "2026-09-30T00:00:00+00:00"})
    problems = ls.validate(broken)
    assert any("knowable_at is after seen_at" in p for p in problems)


# --------------------------------------------------------------- identity and dedupe

def test_the_same_claim_from_two_sources_is_two_leads_and_one_dedupe_key() -> None:
    claim = "Gold rallies into the London fix in 62% of sessions."
    a = _one({"source": "reddit", "title": "t", "text": claim, "symbols": ["XAUUSD"]})
    b = _one({"source": "七禾网", "title": "t", "text": claim,
              "symbols": ["XAUUSD"]})
    assert a.lead_id != b.lead_id, "the witness is part of the lead's identity"
    assert a.dedupe_key() == b.dedupe_key(), "the claim is one claim"
    c = _one({"source": "reddit", "title": "t", "text": claim, "symbols": ["XAGUSD"]})
    assert c.dedupe_key() != a.dedupe_key(), "same words, different instrument, different claim"


def test_the_cell_key_is_the_compilers_own_parent_hash() -> None:
    """Recomputed with `hypothesis_graph.record_candidates`'s recipe, spelled out here so a
    change to either side fails loudly instead of silently costing every BECAME edge."""
    row = REDDIT
    candidate = {"source": f"miner:{row['source']}",
                 "source_url": row.get("url") or row.get("link") or "",
                 "source_title": str(row.get("title") or row.get("description") or "")[:300]}
    expected = hashlib.sha256(json.dumps({"u": candidate["source_url"],
                                          "t": candidate["source_title"],
                                          "s": candidate["source"]},
                                         sort_keys=True, default=str).encode()).hexdigest()[:16]
    assert ls.row_cell_key(row, "reddit") == expected
    assert _one(row, seat="reddit").provenance["cell_key"] == expected


def test_the_cell_key_falls_back_the_way_the_compiler_falls_back() -> None:
    by_description = {"source": "github", "description": "A backtesting framework",
                      "link": "https://github.invalid/x"}
    assert ls.row_cell_key(by_description) == ls.compiler_parent_key(
        "github", "A backtesting framework", "https://github.invalid/x")
    no_source = {"title": "t", "url": "u"}
    assert ls.row_cell_key(no_source, "cot") == ls.compiler_parent_key("cot", "t", "u")
    assert ls.row_cell_key(no_source) == ls.compiler_parent_key("unknown", "t", "u")
    assert ls.compiler_parent_key("miner:cot", "t", "u") == ls.compiler_parent_key("cot", "t", "u")


def test_doc_id_and_title_key() -> None:
    assert ls.doc_id_of("s", "u", "t") == ls.doc_id_of("s", "u", "t")
    assert ls.doc_id_of("s", "u", "t") != ls.doc_id_of("s", "u", "other")
    assert ls.title_key("Time Series Momentum in FX Majors (2012)") == \
        "time series momentum majors 2012"


# --------------------------------------------------------------- validation

def test_validate_names_every_way_a_lead_can_be_wrong() -> None:
    lead = _one(LITERATURE, seat="literature")
    row = ls.to_row(lead)
    assert ls.validate(ls.from_row({**row, "kind": "rumour"}))
    assert any("lead_id" in p for p in ls.validate(ls.from_row({**row, "claim_text": "edited"})))
    assert any("priority" in p or "low priority" in p
               for p in ls.validate(ls.from_row({**row, "priority": "urgent"})))
    assert any("fourteen" in p for p in
               ls.validate(ls.from_row({**row, "structured": {"actor": "x"}})))
    assert any("testable" in p for p in ls.validate(ls.from_row({**row, "testable": False})))
    assert any("instruments repeat" in p for p in
               ls.validate(ls.from_row({**row, "instruments": ["EURUSD", "eurusd"]})))
    assert any("source_id" in p for p in ls.validate(ls.from_row({**row, "source_id": ""})))


def test_validate_returns_problems_rather_than_raising() -> None:
    broken = ls.from_row({"lead_id": "x", "kind": "nope", "claim_text": "c"})
    assert isinstance(ls.validate(broken), list) and ls.validate(broken)


def test_to_row_and_from_row_round_trip_through_json() -> None:
    for row in CORPUS:
        lead = _one(row, seat="seat", run="r")
        again = ls.from_row(json.loads(json.dumps(ls.to_row(lead))))
        assert again == lead


# --------------------------------------------------------------- text utilities

def test_direction_is_a_majority_and_a_tie_is_no_direction() -> None:
    assert ls.direction_of("gold falls after a positive excess return, short it") == -1
    assert ls.direction_of("Gold rises after a positive excess return") == 1
    assert ls.direction_of("buy the dip and sell the rip") == 0
    assert ls.direction_of("the London fix exists") == 0


def test_token_cosine_and_urls_in_text() -> None:
    a = ls.token_set("gold rallies into the london fix")
    assert ls.token_cosine(a, a) == 1.0
    assert ls.token_cosine(a, ls.token_set("silver sells off at the tokyo open")) < 0.5
    assert ls.token_cosine(a, []) == 0.0
    text = "see https://arxiv.org/abs/1 and https://arxiv.org/abs/1 and http://b.invalid/x."
    assert ls.urls_in_text(text) == ["https://arxiv.org/abs/1", "http://b.invalid/x"]
    assert ls.urls_in_text("no links here") == []
