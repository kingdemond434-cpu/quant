"""THE COUNTRY EQUIVALENCE ONTOLOGY AND ITS PARITY PROJECTION.

What is fenced here (completion audit 2026-10-06 rank 11; directive CORE LAW, PARTS II and III):

  * THE CLASS LIST IS THE DIRECTIVE'S, NOT AN INVENTION: PART II's twelve classes and 86
    sub-classes in order (ASIA-1207..ASIA-1292, contiguous) plus the five PART III functions with
    no PART II home, and every one of PART III's thirteen functions maps to a real class key;
  * NO SILENT COVERED: a declared cell without ledger proof is DECLARED; an unreadable ledger is
    proof_state UNMEASURED, never a clean "not fed"; only a proof lifts a cell to COVERED;
  * UNMEASURED IS THE DEFAULT, never NO_EQUIVALENT and never zero: NO_EQUIVALENT needs a rule with
    a reason, and a pack's declaration beats the rule;
  * MULTI-COUNTRY PACKS CREDIT ONLY THE COUNTRY A ROW NAMES, except the euro area's shared
    competence; a row naming nobody is reported unattributed, never spread;
  * THE WORK QUEUE PUTS A KNOWN-BUT-UNDECLARED EQUIVALENT FIRST.
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from libs.research import equivalence_ontology as EQ
from libs.research import regional_parity as RP


def _pack(**kw: Any) -> SimpleNamespace:
    base: dict[str, Any] = {"release_classes": (), "datasets": (), "positioning_sources": (),
                            "institutional_flow_sources": (), "series": {},
                            "fixing_conventions": (), "central_bank": None, "cot_currency": ""}
    base.update(kw)
    return SimpleNamespace(**base)


def _rel(name: str, series: str = "", source: str = "") -> SimpleNamespace:
    return SimpleNamespace(name=name, actual_series=series, source=source)


# ------------------------------------------------------------------------------- the class list
def test_class_list_is_the_directives_part_ii_then_part_iii() -> None:
    part2 = [c for c in EQ.CLASSES if c.part == "II"]
    part3 = [c for c in EQ.CLASSES if c.part == "III"]
    # THE ONTOLOGY IS OPEN: the directive's 86 are the FLOOR, and the extension file may add more.
    assert len(part2) >= 86
    assert [c.mandate_id for c in part2[:86]] == [f"ASIA-{i}" for i in range(1207, 1293)]
    assert EQ.BASE_CLASS_COUNT == 91 and len(EQ.CLASSES) >= EQ.BASE_CLASS_COUNT
    groups = list(dict.fromkeys(c.group for c in part2))
    assert groups == ["Monetary / rates", "FX", "Inflation", "Growth", "Labour", "Credit",
                      "Fiscal", "Trade", "Commodities", "Housing", "Consumer", "Business"]
    assert {c.name for c in part3} == {"FX positioning", "retail positioning",
                                       "investor flows", "shipping", "energy"}
    assert len(set(EQ.CLASS_KEYS)) == len(EQ.CLASS_KEYS)


def test_every_part_iii_function_maps_to_real_classes() -> None:
    assert len(EQ.FUNCTIONS) == 13
    for fn, keys in EQ.FUNCTIONS.items():
        assert keys, fn
        for k in keys:
            assert EQ.class_of(k) is not None, (fn, k)
    for anchor, key in EQ.CORE_LAW_ANCHORS.items():
        assert EQ.class_of(key) is not None, anchor


def test_every_known_equivalent_names_a_real_class_and_a_url() -> None:
    for e in EQ.KNOWN:
        assert EQ.class_of(e.key) is not None, e
        assert e.url.startswith(("http://", "https://")), e
        assert all(u.startswith("https://") for u in e.endpoints), e
    for t in EQ.TRANSNATIONAL:
        assert t.countries and all(EQ.class_of(k) is not None for k in t.keys), t.source_id


# ------------------------------------------------------------------------------- dispositions
def test_no_silent_covered() -> None:
    decl = [{"pack": "kr", "id": "kr_cpi", "keys": ["kr_cpi"]}]
    unread = EQ.dispose("kr", "Inflation:CPI", declared=decl, proof=None, proof_readable=False)
    assert unread.disposition == "DECLARED" and unread.proof_state == EQ.UNMEASURED
    assert "UNMEASURED" in unread.why
    read = EQ.dispose("kr", "Inflation:CPI", declared=decl, proof=None, proof_readable=True)
    assert read.disposition == "DECLARED" and read.proof_state == "NOT_FOUND"
    proved = EQ.dispose("kr", "Inflation:CPI", declared=decl, proof_readable=True,
                        proof={"key": "kr_cpi", "state": "CANDIDATE_INPUT", "unit": "x:kr_cpi"})
    assert proved.disposition == "COVERED" and proved.proof_state == "FOUND"


def test_unmeasured_is_the_default_and_known_equivalents_are_named() -> None:
    nobody = EQ.dispose("so", "FX:option activity")
    assert nobody.disposition == EQ.UNMEASURED and not nobody.equivalents
    known = EQ.dispose("cn", "Commodities:member positions")
    assert known.disposition == "ABSENT_KNOWN_EQUIVALENT"
    assert known.equivalents[0].source_id == "shfe_member_rankings"
    us = EQ.dispose("us", "Commodities:member positions")
    assert us.equivalents[0].endpoints, "the US COT equivalent carries its CFTC endpoint"


def test_no_equivalent_needs_a_reason_and_a_declaration_beats_it() -> None:
    cell = EQ.dispose("ec", "Monetary / rates:policy rates")
    assert cell.disposition == "NO_EQUIVALENT" and "dollarized" in cell.why
    assert EQ.dispose("mn", "Part III:shipping").disposition == "NO_EQUIVALENT"
    declared = EQ.dispose("ec", "Monetary / rates:policy rates",
                          declared=[{"pack": "ec", "id": "ec_rate", "keys": []}])
    assert declared.disposition == "DECLARED"
    # a Caspian littoral state is NOT landlocked-without-a-port
    assert EQ.dispose("kz", "Part III:shipping").disposition != "NO_EQUIVALENT"


def test_matching_reads_declarations_not_brand_names() -> None:
    assert "Commodities:member positions" in EQ.match_classes(
        "KRX 선물옵션 투자자별 미결제약정 (open interest by investor type)")
    assert "FX:bank settlement/sales" in EQ.match_classes("SAFE 银行结售汇 monthly")
    assert "FX:official fixes" not in EQ.match_classes("LBMA Gold Price (the London fix)")
    assert "Commodities:basis" not in EQ.match_classes("kimchi premium reported")
    assert EQ.match_classes("") == ()


# ------------------------------------------------------------------------------- projection
def _project(**kw: Any) -> dict[str, Any]:
    packs = kw.pop("packs")
    juris = kw.pop("jurisdictions")
    return RP.equivalence_parity(packs=packs, jurisdictions=juris, **kw)


def test_projection_never_covers_without_a_ledger() -> None:
    packs = {"kr": _pack(release_classes=(_rel("kr_cpi", "", "통계청"),))}
    doc = _project(packs=packs, jurisdictions={"kr": ("kr",)}, countries=["kr", "so"])
    assert doc["totals"]["counts"]["COVERED"] == 0
    assert any("ingestion ledger" in u for u in doc["unmeasured"])
    cell = next(c for c in doc["cells"] if c["country"] == "kr" and c["class"] == "Inflation:CPI")
    assert cell["disposition"] == "DECLARED" and cell["proof_state"] == EQ.UNMEASURED
    assert doc["n_cells"] == 2 * len(EQ.CLASSES)
    assert set(doc["totals"]["counts"]) == set(EQ.DISPOSITIONS)


def test_projection_covers_only_past_awaiting_experiment() -> None:
    packs = {"kr": _pack(release_classes=(_rel("kr_cpi", "", "통계청"),))}
    waiting = {"datasets": {"kr_cpi": {"downstream_states": {"AWAITING_EXPERIMENT": 3}}}}
    doc = _project(packs=packs, jurisdictions={"kr": ("kr",)}, ingestion=waiting)
    cell = next(c for c in doc["cells"] if c["class"] == "Inflation:CPI")
    assert cell["disposition"] == "DECLARED" and cell["proof_state"] == "NOT_FOUND"
    fed = {"datasets": {"kr_cpi": {"downstream_states": {"CANDIDATE_INPUT": 1}}}}
    doc = _project(packs=packs, jurisdictions={"kr": ("kr",)}, ingestion=fed)
    cell = next(c for c in doc["cells"] if c["class"] == "Inflation:CPI")
    assert cell["disposition"] == "COVERED" and cell["proof"]["state"] == "CANDIDATE_INPUT"
    ledger = [{"kind": "axis", "unit_id": "kr_cpi", "downstream_state": "WORLD_MODEL_INPUT"}]
    doc = _project(packs=packs, jurisdictions={"kr": ("kr",)}, ledger_rows=ledger)
    assert doc["totals"]["counts"]["COVERED"] == 1


def test_multi_country_rows_credit_only_the_country_they_name() -> None:
    pack = _pack(series={"SN_CPI": "ANSD:ihpc"},
                 release_classes=(_rel("Regional consumer price bulletin"),))
    doc = _project(packs={"west_africa": pack},
                   jurisdictions={"west_africa": ("sn", "ci", "ml")})
    cpi = {c["country"]: c["disposition"] for c in doc["cells"] if c["class"] == "Inflation:CPI"}
    assert cpi["sn"] == "DECLARED"
    assert cpi["ci"] != "DECLARED" and cpi["ml"] != "DECLARED"
    assert doc["unattributed_declarations"] == {"west_africa": 1}


def test_euro_area_shared_competence_credits_every_member() -> None:
    cb = SimpleNamespace(name="European Central Bank", policy_rate_series="ecb_dfr")
    doc = _project(packs={"ea": _pack(central_bank=cb)},
                   jurisdictions={"ea": ("de", "fr", "it")})
    pol = {c["country"]: c["disposition"] for c in doc["cells"]
           if c["class"] == "Monetary / rates:policy rates"}
    assert pol == {"de": "DECLARED", "fr": "DECLARED", "it": "DECLARED"}


def test_gap_declarations_are_not_declarations() -> None:
    pack = _pack(positioning_sources=("cftc_cot_absent :: CFTC Commitments of Traders -- NO KRW "
                                      "CONTRACT EXISTS :: n/a",))
    assert RP.pack_declarations("kr", pack) == []


def test_work_queue_puts_known_equivalents_first() -> None:
    doc = _project(packs={}, jurisdictions={}, countries=["cn", "so"])
    queue = doc["work_queue"]
    assert queue and queue[0]["disposition"] == "ABSENT_KNOWN_EQUIVALENT"
    seen_lower = False
    for q in queue:
        if q["disposition"] != "ABSENT_KNOWN_EQUIVALENT":
            seen_lower = True
        else:
            assert not seen_lower, "a known equivalent ranked below an unmeasured hunt"
    assert doc["work_queue_total"] >= len(queue)


@pytest.mark.parametrize("cc", ["us", "cn", "kr", "de", "sn"])
def test_parity_metrics_exclude_no_equivalent_cells(cc: str) -> None:
    doc = _project(packs={}, jurisdictions={}, countries=[cc])
    row = doc["by_country"][cc]
    eligible = row["n"] - row["counts"]["NO_EQUIVALENT"]
    # with no ledger nothing is measured, so the HEADLINE is UNMEASURED -- never 0.0
    assert row["parity"] == EQ.UNMEASURED and row["measured"] == 0 and row["fed"] == 0
    assert row["unmeasured"] == eligible
    assert row["unmeasured_share"] == (1.0 if eligible else None)


# ------------------------------------------------------------------------------- audit 2026-10-06
_TREASURY = ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
             "daily-treasury-rates.csv/2026/all?type=daily_treasury_yield_curve")


def test_headline_parity_is_evaluated_over_measured_never_declared() -> None:
    packs = {"kr": _pack(release_classes=(_rel("kr_cpi", "", "통계청"),))}
    # no ledger: DECLARED is not fed, nothing is measured -> the headline itself is UNMEASURED
    doc = _project(packs=packs, jurisdictions={"kr": ("kr",)})
    row = doc["by_country"]["kr"]
    assert row["counts"]["DECLARED"] >= 1 and row["fed"] == 0
    assert row["parity"] == EQ.UNMEASURED and row["measured"] == 0
    assert doc["totals"]["parity"] == EQ.UNMEASURED
    assert doc["parity_spread"]["median"] == EQ.UNMEASURED
    # a ledger read but the unit only AWAITING_EXPERIMENT: measured, not fed -> 0.0, and every
    # cell nobody measured stays OUT of the denominator, published as its own count
    waiting = {"datasets": {"kr_cpi": {"downstream_states": {"AWAITING_EXPERIMENT": 1}}}}
    doc = _project(packs=packs, jurisdictions={"kr": ("kr",)}, ingestion=waiting)
    row = doc["by_country"]["kr"]
    assert row["measured"] >= 1 and row["fed"] == 0 and row["parity"] == 0.0
    assert row["unmeasured"] == row["n"] - row["counts"]["NO_EQUIVALENT"] - row["measured"]
    assert row["unmeasured"] > 0
    # evaluated past AWAITING_EXPERIMENT: fed
    fed = {"datasets": {"kr_cpi": {"downstream_states": {"CANDIDATE_INPUT": 1}}}}
    row = _project(packs=packs, jurisdictions={"kr": ("kr",)}, ingestion=fed)["by_country"]["kr"]
    assert row["fed"] == 1 and row["parity"] == round(1 / row["measured"], 6)


def test_terms_gate_holds_what_no_quote_permits() -> None:
    for url in ("https://data.bis.org/static/bulk/WS_CBPOL_csv_col.zip",
                "https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A",
                "https://www.cftc.gov/dea/newcot/FinFutWk.txt"):
        assert EQ.terms_verdict(url) == EQ.PERMITTED, url
        assert all(t["terms_quote"] and t["terms_url"].startswith("https://")
                   and t["checked_at"] == "2026-10-06" for t in EQ.terms_for(url))
    assert EQ.terms_verdict(_TREASURY) == EQ.HELD
    assert EQ.terms_verdict("https://example.org/data.csv") == EQ.HELD, "no rule -> fail closed"
    us = EQ.dispose("us", "Monetary / rates:yield curves")
    eq = us.equivalents[0].to_json()
    assert not any(u.startswith("https://home.treasury.gov") for u in eq["endpoints"])
    assert eq["held_endpoints"] and eq["held_endpoints"][0]["verdict"] == EQ.HELD
    assert eq["access"] == EQ.HELD


def test_ontology_extension_merges_and_refuses_by_name(tmp_path: Any) -> None:
    ext = tmp_path / "ext.json"
    ext.write_text(json.dumps({"schema": 1, "classes": [
        {"group": "Shipping", "name": "port calls", "terms": r"port\s+calls?"},
        {"group": "Inflation", "name": "CPI", "terms": "cpi"},           # duplicate
        {"group": "Bad", "name": "regex", "terms": "("},                   # bad regex
    ], "known": [
        {"key": "Shipping:port calls", "country": "sg", "source_id": "mpa_port_calls",
         "url": "https://www.mpa.gov.sg"},
        {"key": "No:such class", "country": "sg", "source_id": "x", "url": "https://x.sg"},
    ]}), "utf-8")
    try:
        rep = EQ.load_extension(ext)
        assert rep["state"] == "READ" and rep["classes_added"] == ["Shipping:port calls"]
        assert rep["known_added"] == 1 and len(rep["refused"]) == 3
        assert len(EQ.CLASSES) == EQ.BASE_CLASS_COUNT + 1
        assert "Shipping:port calls" in EQ.match_classes("weekly port calls bulletin")
        assert EQ.dispose("sg", "Shipping:port calls").disposition == "ABSENT_KNOWN_EQUIVALENT"
        bad = tmp_path / "bad.json"
        bad.write_text("{not json", "utf-8")
        rep = EQ.load_extension(bad)
        assert rep["state"].startswith(EQ.UNMEASURED)
        assert len(EQ.CLASSES) == EQ.BASE_CLASS_COUNT, "the base survives an unreadable file"
    finally:
        EQ.load_extension()
    assert "Shipping:port calls" not in EQ.CLASS_KEYS


def test_unmatched_declarations_become_candidate_classes_never_dropped() -> None:
    pack = _pack(release_classes=(_rel("kr_cpi", "", "통계청"),
                                  _rel("Korean drama box office receipts tally"),))
    doc = _project(packs={"kr": pack}, jurisdictions={"kr": ("kr",)})
    cands = doc["candidate_classes"]
    assert doc["n_candidate_classes"] == len(cands) >= 1
    row = next(c for c in cands if "box office" in str(c["text"]))
    assert row["status"] == "CANDIDATE_CLASS" and row["countries"] == ["kr"]
    assert len(row["candidate_id"]) == 16
    assert not any(c["id"] == "kr_cpi" for c in cands), "a matched declaration is not a candidate"
