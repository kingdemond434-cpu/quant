"""The compiler reads the prose miners' text, and the ways text extraction must not lie.

MEASURED 2026-09-08 on the board: world 10,062 rows -> 1 distinct -> 0 tested; reddit 6,962 ->
1 -> 0; bis_speeches 6,160 -> 1 -> 0; github_topics 6,754 -> 1 -> 0. Every prose miner writes
`title`/`text`/`summary`/`description` and an EMPTY `symbols` list, and `resolve_symbols` read
only structured fields -- so each row took the NEEDS_SYMBOL_EXTRACTION exit unread.

A text candidate is a HYPOTHESIS for the ten gates: registry-priced instruments only, price-only
registered families only, the family's defaults unless the prose named a session or a month, and
the matched phrase written onto the candidate. These tests pin the extraction and its bounds.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import miner_candidate_compiler as mcc  # noqa: E402

UNI = {"EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "XAGUSD", "USDCAD", "AUDUSD", "NAS100", "US500",
       "BTCUSD", "EURJPY", "GBPJPY"}


def _row(**kw) -> dict:
    return {"source": "reddit", "kind": "post", "symbols": [], "url": "https://x", **kw}


# ------------------------------------------------------------------ the day's rows now convert
def test_a_reddit_post_about_a_london_range_breakout_on_cable_becomes_a_cell() -> None:
    cands, disp = mcc.compile_row("reddit", _row(
        title="London open range breakout on GBP/USD has been printing all month",
        text="I take the London breakout of the Asian range, 2R target."), UNI)
    assert disp == "TEXT_EXTRACTED"
    fams = {c["family"] for c in cands}
    assert "session_range_breakout" in fams
    srb = next(c for c in cands if c["family"] == "session_range_breakout")
    assert srb["symbol"] == "GBPUSD"
    assert srb["params"] == {"range_start": 10, "range_end": 13, "signal_at": 13}   # london_am
    assert "text extraction:" in srb["mechanism_note"]
    assert srb["source"] == "miner:reddit"


def test_a_world_page_on_gold_seasonality_names_the_month_and_the_direction() -> None:
    cands, disp = mcc.compile_row("world", _row(
        source="world", title="Gold seasonality", text="Gold tends to rally in January."), UNI)
    assert disp == "TEXT_EXTRACTED"
    cal = next(c for c in cands if c["family"] == "calendar_month")
    assert cal["symbol"] == "XAUUSD"
    assert cal["params"] == {"active_month": 1, "side_bias": 1}


def test_a_gap_fill_mention_takes_the_family_defaults() -> None:
    cands, disp = mcc.compile_row("github_topics", _row(
        text="Simple EURUSD gap fill bot: fade the overnight gap at the open."), UNI)
    assert disp == "TEXT_EXTRACTED"
    assert {(c["symbol"], c["family"]) for c in cands} >= {("EURUSD", "overnight_gap_decay")}
    assert all(c["params"] == {} for c in cands if c["family"] == "overnight_gap_decay")


# --------------------------------------------------------------- what must NOT be extracted
def test_a_central_bank_speech_with_no_instrument_and_no_mechanism_is_still_unextracted() -> None:
    cands, disp = mcc.compile_row("bis_speeches", _row(
        source="bis_speeches", kind="cb_speech",
        title="Opportunities and risks for CCPs and their overseers",
        text="Keynote speech on central counterparties and clearing resilience."), UNI)
    assert cands == [] and disp == "NEEDS_SYMBOL_EXTRACTION"


def test_an_operational_row_is_refused_not_mined() -> None:
    """A walled site or a fetch error names no mechanism; extracting instruments from an error
    message manufactures candidates out of plumbing."""
    for kind in ("walled", "fetch_error", "stub"):
        cands, disp = mcc.compile_row("darwinex", _row(
            kind=kind, title="HTTP_403 (probe not due) EURUSD gap fill",
            text="robots.txt PERMITS /leaderboard"), UNI)
        assert cands == [] and disp == "OPERATIONAL_ROW", kind
    cands, disp = mcc.compile_row("earnings", _row(
        needs_selector_work=True, text="EURUSD gap fill"), UNI)
    assert cands == [] and disp == "OPERATIONAL_ROW"


def test_a_bare_currency_code_is_never_expanded_from_prose() -> None:
    """"The euro" must not mint ten pairs. Structured rows may expand (resolve_symbols does);
    prose may not."""
    assert mcc.text_symbols("the ecb said the eur would weaken", UNI) == []


def test_an_alias_resolves_only_to_a_symbol_the_registry_holds() -> None:
    assert mcc.text_symbols("gold and silver rallied", UNI) == ["XAUUSD", "XAGUSD"]
    assert mcc.text_symbols("gold rallied", {"EURUSD"}) == []          # no XAUUSD -> nothing
    assert mcc.text_symbols("nasdaq futures", UNI) == ["NAS100"]        # first target present


def test_symbol_matching_is_word_bounded_and_case_insensitive() -> None:
    assert mcc.text_symbols("EurUsd and eur/usd and EUR-USD", UNI) == ["EURUSD"]
    assert mcc.text_symbols("myeurusdbot", UNI) == []                   # inside a token: no
    assert mcc.text_symbols("absorb the fvg", UNI) == []                # 'orb' inside 'absorb'


def test_family_phrases_are_word_bounded() -> None:
    assert mcc.text_families("we predict a move") == []                 # 'ict' inside 'predict'
    assert [f for f, _ in mcc.text_families("an ict concept trade")] == ["ict_fvg"]


def test_the_longest_phrase_wins_and_at_most_two_families_are_named() -> None:
    fams = mcc.text_families(
        "opening range breakout after a gap fill with a pin bar and rsi oversold")
    assert len(fams) == 2
    assert fams[0][0] == "session_range_breakout"                       # longest phrase first


def test_at_most_four_instruments_per_row() -> None:
    syms = mcc.text_symbols("eurusd gbpusd usdjpy xauusd usdcad audusd all gap fill", UNI)
    assert len(syms) == 4


def test_calendar_month_without_a_direction_or_with_both_is_not_a_recipe() -> None:
    assert mcc._text_params("calendar_month", "gold in january") is None
    assert mcc._text_params("calendar_month", "gold rallies then falls in january") is None
    assert mcc._text_params("calendar_month", "gold falls in september") == \
        {"active_month": 9, "side_bias": -1}


def test_only_price_only_registered_families_are_in_the_vocabulary() -> None:
    """A family that needs swap terms, COT, a peer or a calendar cannot be built from prose."""
    for needs_input in ("carry", "cot_positioning", "event_reaction", "relative_value",
                        "lead_lag", "cross_asset_residual", "discovered", "formula"):
        assert needs_input not in mcc._FAMILY_VOCAB
    for fam in mcc._FAMILY_VOCAB:
        assert mcc._registered_family(fam), f"{fam} is not a registered family"


def test_a_structured_row_still_takes_its_structured_branch_before_any_prose() -> None:
    """Text is read LAST. A COT row with a symbol and a paragraph mentioning 'gap fill' is a COT
    candidate, not a gap candidate."""
    cands, disp = mcc.compile_row("cot", {
        "source": "cot", "type": "positioning", "symbol": "USDCHF",
        "text": "specs are extreme; also usdchf gap fill"}, UNI | {"USDCHF"})
    assert disp == "STRUCTURED_COT"
    assert {c["family"] for c in cands} == {"cot_positioning"}


def test_the_session_params_are_the_forward_engine_s_own_windows() -> None:
    assert mcc._SESSION_PARAMS == {
        "asia": {"range_start": 7},
        "london_am": {"range_start": 10, "range_end": 13, "signal_at": 13},
        "ny_open": {"range_start": 13, "range_end": 14, "signal_at": 14},
        "afternoon": {"range_start": 14, "range_end": 17, "signal_at": 17},
    }


@pytest.mark.parametrize("text,session", [
    ("the asian session range", "asia"), ("new york open momentum", "ny_open"),
    ("into the london close", "afternoon"), ("no session words here", None),
])
def test_session_words(text: str, session: str | None) -> None:
    assert mcc.text_session(text) == session
