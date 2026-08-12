"""Gate item 22: the eight-dimension comparison, and the veto that stops a proxy being booked
as a replacement."""
from __future__ import annotations

from libs.research.free_substitute import (
    DIMENSIONS,
    Requirement,
    SourceSpec,
    compare,
    total_economic_cost,
)

# ---------------------------------------------------------------------------- the REAL case
# DefiLlama paid Emissions vs the desk's own free circulating-supply series. Both specs are read
# off docs/research/paid_dataset_targets.md and data/paywall_encounters.jsonl -- the live HTTP 402
# encountered 2026-08-05 -- not invented for the test.
_PAID = SourceSpec(
    name="defillama_emissions_paid",
    is_free=False,
    answers_question="what unlocks WILL happen, and when",
    values={"timestamp_fidelity": "dated schedule rows with known_from",
            "history": 36, "latency": "ahead of the event", "accuracy": "vendor-curated",
            "missingness": "per-protocol coverage gaps", "rights": "paid licence",
            "reliability": "vendor SLA",
            "downstream_economic_information": "forward_looking"},
    monthly_cash_usd=300.0,
)
_FREE_SUPPLY = SourceSpec(
    name="own_circulating_supply_delta",
    is_free=True,
    answers_question="what unlocks ALREADY happened, visible as a supply jump",
    values={"timestamp_fidelity": "daily supply observation",
            "history": 36, "latency": "after the event", "accuracy": "chain-derived",
            "missingness": "none for covered assets", "rights": "no licence",
            "reliability": "own collector",
            "downstream_economic_information": "contemporaneous"},
    engineering_hours=6.0, monthly_maintenance_hours=0.5,
)

_ANTICIPATION = Requirement(
    use="unlock ANTICIPATION study",
    question="does price drift ahead of a scheduled unlock?",
    needs={"history": 24, "rights": "no licence",
           "downstream_economic_information": "forward_looking"},
)
_REACTION = Requirement(
    use="unlock REACTION study",
    question="how does price behave after a realised unlock?",
    needs={"history": 24, "rights": "no licence",
           "downstream_economic_information": "contemporaneous"},
)


def test_the_veto_blocks_the_anticipation_study() -> None:
    """THE POINT OF ITEM 22, and the desk walked into it live. The free route wins or ties on
    seven dimensions and is still not a replacement: a supply delta is visible only AFTER the
    release, when everyone else can see it too."""
    out = compare(paid=_PAID, free=_FREE_SUPPLY, requirement=_ANTICIPATION)
    assert out["verdict"] == "NO_FREE_EQUIVALENT_YET"
    assert out["veto"] == "downstream_economic_information"
    assert "DIFFERENT economic question" in out["why"]


def test_the_same_free_route_is_near_equivalent_for_the_reaction_study() -> None:
    """One route, two verdicts, because there are two uses. Collapsing them into a single global
    answer is exactly how a proxy gets booked as a replacement."""
    out = compare(paid=_PAID, free=_FREE_SUPPLY, requirement=_REACTION)
    assert out["verdict"] in ("FREE_EXACT_EQUIVALENT", "FREE_NEAR_EQUIVALENT")
    assert not out["fails"]


def test_every_mandate_dimension_is_scored() -> None:
    out = compare(paid=_PAID, free=_FREE_SUPPLY, requirement=_REACTION)
    assert [d["dimension"] for d in out["dimensions"]] == list(DIMENSIONS)
    assert len(DIMENSIONS) == 8


# ---------------------------------------------------------------------------- per-use scoring
def test_a_dimension_the_use_does_not_need_is_not_a_weakness() -> None:
    """'Worse on history' is not a defect if the study needs thirty days."""
    out = compare(paid=_PAID, free=_FREE_SUPPLY,
                  requirement=Requirement(use="u", question="q", needs={"rights": "no licence"}))
    hist = next(d for d in out["dimensions"] if d["dimension"] == "history")
    assert hist["status"] == "NOT_REQUIRED"


def test_insufficient_history_fails_when_the_use_needs_it() -> None:
    short = SourceSpec(name="short", is_free=True,
                       values={**_FREE_SUPPLY.values, "history": 3})
    out = compare(paid=_PAID, free=short, requirement=_REACTION)
    assert out["verdict"] == "FREE_PROXY" and "history" in out["fails"]


def test_a_proxy_is_labelled_honestly_and_leaves_the_paid_source_open() -> None:
    short = SourceSpec(name="short", is_free=True,
                       values={**_FREE_SUPPLY.values, "history": 3})
    out = compare(paid=_PAID, free=short, requirement=_REACTION)
    assert "not a replacement" in out["why"] and "stays OPEN" in out["why"]


# ---------------------------------------------------------------------------- UNKNOWN is not a pass
def test_an_unmeasured_dimension_caps_the_verdict_below_exact() -> None:
    """'We did not check the licence' must never read as 'the licence is fine' -- that is how an
    NC-licensed feed ends up in a commercial pipeline."""
    unchecked = SourceSpec(name="u", is_free=True,
                           values={k: v for k, v in _FREE_SUPPLY.values.items()
                                   if k != "rights"},
                           answers_question=_FREE_SUPPLY.answers_question)
    out = compare(paid=_PAID, free=unchecked, requirement=_REACTION)
    assert out["verdict"] == "FREE_NEAR_EQUIVALENT"
    assert out["unresolved"] == ["rights"] and "never an answer in the desk's favour" in out["why"]


def test_unknown_never_reads_as_meets() -> None:
    unchecked = SourceSpec(name="u", is_free=True, values={})
    out = compare(paid=_PAID, free=unchecked, requirement=_REACTION)
    statuses = {d["dimension"]: d["status"] for d in out["dimensions"]}
    assert statuses["rights"] == "UNKNOWN" and statuses["history"] == "UNKNOWN"


# ---------------------------------------------------------------------------- multi-source
def test_a_reconstruction_from_several_sources_is_recorded_distinctly() -> None:
    multi = SourceSpec(name="m", is_free=True, values=dict(_FREE_SUPPLY.values),
                       n_upstream_sources=3)
    out = compare(paid=_PAID, free=multi, requirement=_REACTION)
    assert out["verdict"] == "FREE_MULTI_SOURCE_RECONSTRUCTION"
    assert "N failure modes rather than one" in out["why"]


def test_a_single_source_route_meeting_everything_is_exact() -> None:
    out = compare(paid=_PAID, free=_FREE_SUPPLY, requirement=_REACTION)
    assert out["verdict"] == "FREE_EXACT_EQUIVALENT"


# ---------------------------------------------------------------------------- total economic cost
def test_free_is_costed_on_total_economics_not_purchase_price() -> None:
    """XXIV-(7). A free feed with 6h of integration and 0.5h/month of upkeep is not free."""
    c = total_economic_cost(_FREE_SUPPLY, hourly_usd=50.0, months=12)
    assert c["cash_usd"] == 0.0
    assert c["engineering_hours"] == 12.0 and c["total_usd"] == 600.0


def test_hours_are_never_converted_at_an_invented_rate() -> None:
    """A fabricated wage would make the comparison look decided when it is not."""
    c = total_economic_cost(_FREE_SUPPLY)
    assert c["total_usd"] is None and c["engineering_hours"] == 12.0
    assert "invented wage" in c["note"]


def test_the_paid_route_is_costed_on_the_same_basis() -> None:
    out = compare(paid=_PAID, free=_FREE_SUPPLY, requirement=_REACTION, hourly_usd=50.0)
    assert out["paid_total_economic_cost"]["cash_usd"] == 3600.0
    assert out["free_total_economic_cost"]["total_usd"] == 600.0
