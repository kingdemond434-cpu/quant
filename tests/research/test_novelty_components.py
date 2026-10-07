"""DATA-30: novelty beyond lexical. One test per axis, on synthetic documents, several of them in
languages other than English, plus the backward-compatibility contract on the old score.

The rule every axis is held to: a document that carries nothing the axis can read is UNMEASURED
on it (score None, `measured` False), never a clean zero.
"""
# ruff: noqa: RUF001 -- the multilingual fixtures are made of the characters this rule flags.
from __future__ import annotations

from typing import Any

from libs.research import event_ontology as eo


def _row(claim: str, *, kind: str = "central_bank_surprise", ents: tuple[str, ...] = ("US",),
         eid: str = "ev_a", src: str = "reuters", doc: str = "") -> dict[str, Any]:
    return {"kind": kind, "entities": list(ents), "claim": claim, "event_id": eid,
            "source_id": src, "doc_id": doc or f"{src}:{claim[:12]}"}


def _c(event: dict[str, Any], window: list[dict[str, Any]], name: str) -> dict[str, Any]:
    return dict(eo.novelty_of(event, window).components[name])


# ----------------------------------------------------------------------------- the contract
def test_the_old_score_is_unchanged_and_the_vector_names_every_axis() -> None:
    window = [_row("The Fed raises rates to 5.25%")]
    event = _row("The Fed raises rates to 5.25%", src="ap")
    nov = eo.novelty_of(event, window)
    assert nov.repeats == 1 and nov.score < 0.5
    assert eo.novelty(event, window) == nov.score
    assert tuple(nov.vector()) == eo.NOVELTY_COMPONENTS
    assert len(eo.NOVELTY_COMPONENTS) == 11
    # Positional construction, as every older caller wrote it, still works.
    assert eo.Novelty(1.0, 0, 0.0).components == {}


def test_an_empty_window_makes_every_readable_axis_new() -> None:
    nov = eo.novelty_of(_row("The Fed raises rates to 5.25% as inflation rises"), [])
    v = nov.vector()
    assert v["semantic"] == 1.0 and v["entity"] == 1.0 and v["geographic"] == 1.0
    assert v["numerical"] == 1.0 and v["causal_channel"] == 1.0
    assert v["confirmation"] == 0.0          # nothing earlier to confirm: measured, not None


# ----------------------------------------------------------------------------- each axis
def test_semantic_reads_paraphrase_closer_than_a_different_story() -> None:
    window = [_row("Oil tanker seized in the Strait of Hormuz by naval forces", kind="other",
                   ents=())]
    same = _c(_row("Naval forces seize an oil tanker in the Strait of Hormuz", kind="other",
                   ents=()), window, "semantic")
    other = _c(_row("Coffee harvest in Brazil hit by frost", kind="other", ents=()), window,
               "semantic")
    assert same["measured"] and other["measured"]
    assert same["score"] < other["score"]


def test_semantic_works_without_word_boundaries() -> None:
    window = [_row("美联储宣布加息二十五个基点", ents=("US",))]
    close = _c(_row("美联储宣布再次加息二十五个基点", ents=("US",)), window, "semantic")
    far = _c(_row("日本央行维持利率不变", ents=("JP",)), window, "semantic")
    assert close["score"] < far["score"]


def test_entity_counts_only_entities_the_window_never_named() -> None:
    window = [_row("Iran threatens shipping", kind="war_escalation", ents=("IR",))]
    c = _c(_row("Iran and Israel exchange strikes", kind="war_escalation", ents=("IR", "IL")),
           window, "entity")
    assert c["score"] == 0.5 and c["new"] == ["IL"]
    none = _c(_row("markets drift", kind="other", ents=()), window, "entity")
    assert none["score"] is None and not none["measured"]


def test_relationship_sees_a_new_pair_of_known_entities() -> None:
    window = [_row("Iran news", kind="war_escalation", ents=("IR",)),
              _row("Saudi news", kind="war_escalation", ents=("SA",))]
    c = _c(_row("Iran strikes Saudi facility", kind="war_escalation", ents=("IR", "SA")),
           window, "relationship")
    assert "IR&SA" in c["new"]
    assert _c(_row("x", kind="war_escalation", ents=("IR", "SA")), window, "entity")["score"] == 0


def test_numerical_flags_a_changed_figure_and_ignores_years() -> None:
    window = [_row("US CPI rose 3.1% in 2026", kind="inflation_surprise")]
    same = _c(_row("US CPI at 3.1% for 2026", kind="inflation_surprise"), window, "numerical")
    moved = _c(_row("US CPI at 3.4% for 2026", kind="inflation_surprise"), window, "numerical")
    assert same["score"] == 0.0
    assert moved["score"] == 1.0 and moved["prior"] == [[3.1, "%"]]
    words = _c(_row("US CPI ran hot", kind="inflation_surprise"), window, "numerical")
    assert words["score"] is None


def test_numerical_reads_full_width_digits_and_comma_decimals() -> None:
    assert eo.figures_in("金利は５．２５％") == [(5.25, "%")]
    assert eo.figures_in("Leitzins bei 4,50 %") == [(4.5, "%")]
    assert eo.figures_in("exports of 1,250 million") == [(1250.0, "million")]


def test_severity_rises_on_an_escalation_and_not_on_a_repeat() -> None:
    window = [_row("Border clashes reported", kind="political_instability", ents=("IR",))]
    worse = _c(_row("Full-scale invasion, nuclear alert declared", kind="war_escalation",
                    ents=("IR",)), window, "severity")
    calm = _c(_row("Border clashes reported again", kind="political_instability",
                   ents=("IR",)), window, "severity")
    assert worse["score"] == 1.0 and worse["level"] > worse["prior_max"]
    assert calm["score"] == 0.0


def test_policy_state_flags_hike_to_hold_in_three_languages() -> None:
    hike = [_row("The Fed raises rates by 25bp", src="a")]
    hold = _c(_row("The Fed holds rates steady", src="b"), hike, "policy_state")
    assert hold["score"] == 1.0 and (hold["prior"], hold["stance"]) == ("tighten", "hold")
    again = _c(_row("Fed officials call the rate hike necessary", src="c"), hike, "policy_state")
    assert again["score"] == 0.0
    jp = [_row("日銀が利上げを決定", ents=("JP",))]
    assert _c(_row("日銀は金利を据え置き", ents=("JP",)), jp, "policy_state")["score"] == 1.0
    de = [_row("Die EZB erhöht den Leitzins", ents=("EU",))]
    assert _c(_row("Die EZB senkt den Leitzins", ents=("EU",)), de, "policy_state")["score"] == 1
    assert _c(_row("Fed minutes published"), hike, "policy_state")["score"] is None


def test_geographic_reads_new_countries_and_new_regions() -> None:
    window = [_row("Drought", kind="natural_disaster", ents=("BR",))]
    region = _c(_row("Drought", kind="natural_disaster", ents=("AU",)), window, "geographic")
    assert region["new_regions"] == ["oceania"] and region["score"] == 1.0
    neighbour = _c(_row("Drought", kind="natural_disaster", ents=("MX",)), window, "geographic")
    assert neighbour["new_regions"] == [] and neighbour["score"] == 0.5


def test_confirmation_is_an_independent_source_never_a_copy_or_an_echo() -> None:
    first = _row("Iran seizes a tanker near Hormuz, officials say", kind="war_escalation",
                 ents=("IR",), src="reuters")
    window = [first]
    indep = _c(_row("Tehran's navy detained a tanker close to the strait, ministry confirms",
                    kind="war_escalation", ents=("IR",), src="afp"), window, "confirmation")
    assert indep["score"] == 1.0 and indep["independent_sources"] == 2
    copy = _c(_row("Iran seizes a tanker near Hormuz, officials say", kind="war_escalation",
                   ents=("IR",), src="yahoo"), window, "confirmation")
    assert copy["score"] == 0.0 and "copy" in copy["basis"]
    echo = _c(_row("Update: Iran tanker seizure details", kind="war_escalation",
                   ents=("IR",), src="reuters"), window, "confirmation")
    assert echo["score"] == 0.0
    anon = _row("x", kind="war_escalation", ents=("IR",))
    anon["source_id"] = ""
    assert _c(anon, window, "confirmation")["score"] is None


def test_contradiction_flags_an_opposite_direction_and_a_denial() -> None:
    window = [_row("US payrolls rose sharply", kind="labour_surprise")]
    opp = _c(_row("US payrolls fell, revised data show", kind="labour_surprise"), window,
             "contradiction")
    assert opp["score"] == 1.0 and opp["prior"] == "up"
    same = _c(_row("US payrolls jumped", kind="labour_surprise"), window, "contradiction")
    assert same["score"] == 0.0
    denial = _c(_row("Labour department denies the payroll report", kind="labour_surprise"),
                window, "contradiction")
    assert denial["score"] == 1.0
    ru = [_row("Ставка выросла", ents=("RU",))]
    assert _c(_row("Инфляция упала", ents=("RU",)), ru, "contradiction")["score"] == 1.0
    assert _c(_row("Fed statement", kind="labour_surprise"), window,
              "contradiction")["score"] is None


def test_revision_links_the_revised_figure_on_the_same_event() -> None:
    window = [_row("Q2 GDP grew 2.1%", kind="labour_surprise", eid="ev_gdp", doc="d1")]
    rev = _c(_row("Q2 GDP revised to 1.6%", kind="labour_surprise", eid="ev_gdp", doc="d2"),
             window, "revision")
    assert rev["score"] == 1.0 and rev["revised_ref"] == "d1"
    assert rev["before"] == [[2.1, "%"]] and rev["after"] == [[1.6, "%"]]
    silent = _c(_row("Q2 GDP at 1.6%", kind="labour_surprise", eid="ev_gdp"), window,
                "revision")
    assert silent["score"] == 0.6                   # changed, but not stated as a revision
    fr = [_row("Le PIB progresse de 0,3 %", ents=("FR",), eid="ev_fr")]
    assert _c(_row("PIB révisé à 0,1 %", ents=("FR",), eid="ev_fr"), fr,
              "revision")["score"] == 1.0
    other = _c(_row("Q2 GDP revised to 1.6%", kind="labour_surprise", eid="ev_other"), window,
               "revision")
    assert other["score"] == 0.0


def test_causal_channel_is_new_when_the_entity_reaches_a_market_it_had_not() -> None:
    window = [_row("Chile copper strike", kind="strike", ents=("copper",))]
    cb = _c(_row("Copper export ban", kind="sanctions", ents=("copper",)), window,
            "causal_channel")
    assert cb["score"] is not None and cb["score"] > 0
    assert any(n.startswith("COPPER>") for n in cb["new"])
    rep = _c(_row("Chile copper strike continues", kind="strike", ents=("copper",)), window,
             "causal_channel")
    assert rep["score"] == 0.0
    other = _c(_row("unclassified", kind="other", ents=("copper",)), window, "causal_channel")
    assert other["score"] is None


def test_a_near_verbatim_line_with_a_changed_figure_is_a_revision_not_a_copy() -> None:
    window = [_row("Q2 GDP grew 2.1% says the statistics office", kind="labour_surprise",
                   src="reuters")]
    moved = _row("Q2 GDP grew 1.6% says the statistics office", kind="labour_surprise",
                 src="afp")
    conf = _c(moved, window, "confirmation")
    assert "copy" not in conf["basis"]
    assert eo.is_copy(0.99, [(2.1, "%")], [(2.1, "%")])
    assert not eo.is_copy(0.99, [(1.6, "%")], [(2.1, "%")])
