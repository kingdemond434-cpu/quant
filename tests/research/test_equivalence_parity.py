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
    assert len(part2) == 86
    assert [c.mandate_id for c in part2] == [f"ASIA-{i}" for i in range(1207, 1293)]
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
    assert row["parity"] == (0.0 if eligible else None)
    assert row["unmeasured_share"] is not None and row["unmeasured_share"] > 0
