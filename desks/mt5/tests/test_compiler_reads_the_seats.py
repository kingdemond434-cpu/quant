"""The LLM seats' findings reach the docket through the same door as every miner's row.

MEASURED 2026-09-08. Two seats produced rows and the compiler counted neither as a source:

  kimi_hunter     wrote its admitted findings to data/suggestion_ledger.jsonl and
                  data/kimi_hunt.json -- under `data/`, gitignored, read by two scripts that are
                  on no timer. The compiler walks data/intelligence/** and nothing else, so the
                  Deep Forest protocol ran, its gate ran, and no row it admitted was ever
                  compiled, deepened or graveyarded: unread.
  deepseek_cycle  donated to data/intelligence/deepseek/discoveries_*.json -- the right tree --
                  but its rows carry `family` and `symbols` and no `params`, so they missed
                  EXACT_RECIPE and fell to the prose path, which re-read the family from the
                  text alone and ignored the instruments the row had declared.

These tests run each seat's OWN writer and the compiler's OWN reader end to end: what a seat
writes is what the compiler compiles, or the reason it does not is one of the compiler's named
dispositions. No new admission path: a seat's hypothesis is held to the prose path's bounds
(price-only registered families, the family's defaults unless the text names a session or a
month, at most four declared instruments), and the ten gates remain the only arbiter.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import miner_candidate_compiler as mcc  # noqa: E402

UNI = {"EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "XAGUSD", "AUDJPY", "US500"}


def _seat_row(**kw) -> dict:
    """A row in the shape libs/ops/deepseek_cycle._donate writes."""
    base = {"source": "deepseek", "kind": "hypothesis", "title": "t", "mechanism": "",
            "testable_claim": "", "symbols": [], "family": None, "mechanism_tags": [],
            "url": "deepseek://cold_auditor/2026-09-08T00:00:00+00:00"}
    base.update(kw)
    return base


@pytest.fixture
def intel(tmp_path, monkeypatch):
    """One intelligence root under a fake repo root, isolated from the real trees."""
    root = tmp_path / "data" / "intelligence"
    root.mkdir(parents=True)
    monkeypatch.setattr(mcc, "INTEL_ROOTS", (root,))
    return tmp_path


# ------------------------------------------------------------ DeepSeek: writer -> reader -> docket
class TestTheDeepSeekSeatFeedsTheDocket:
    def test_a_donation_is_read_by_the_compiler_and_compiles_to_the_family_it_names(
            self, intel) -> None:
        """End to end on the seat's own `_donate` and the compiler's own `recent_rows`. The prose
        here names no vocabulary phrase and no instrument alias, which is exactly the row that
        went to deepening before with its family and instrument already written on it."""
        ds = pytest.importorskip("libs.ops.deepseek_cycle")
        ds._donate([{"ts": "2026-09-08T20:00:00+00:00",
                     "title": "Tokyo fix gap decay on the yen",
                     "mechanism": "exporters hedge into the fix and the flow is one-sided",
                     "testable_claim": "the fix-to-open move decays within the session",
                     "symbols": ["USDJPY"], "family": "overnight_gap_decay"}],
                   "cold_auditor", root=intel)
        rows = mcc.recent_rows(mcc.datetime.now(tz=mcc.UTC))
        assert [src for src, _ in rows] == ["deepseek"], "the donation must be read as deepseek"
        cands, disp = mcc.compile_row(*rows[0], UNI)
        assert disp == "STRUCTURED_HYPOTHESIS"
        (c,) = cands
        assert (c["symbol"], c["family"], c["params"]) == ("USDJPY", "overnight_gap_decay", {})
        assert c["source"] == "miner:deepseek"
        assert "seat hypothesis" in c["mechanism_note"]

    def test_a_session_named_in_the_text_is_taken_as_the_parameter(self) -> None:
        cands, disp = mcc.compile_row("deepseek", _seat_row(
            title="London open range on cable", symbols=["GBPUSD"],
            family="session_range_breakout",
            testable_claim="the range set at the London open resolves by 13:00"), UNI)
        assert disp == "STRUCTURED_HYPOTHESIS"
        assert cands[0]["params"] == {"range_start": 10, "range_end": 13, "signal_at": 13}

    def test_a_family_that_needs_an_external_input_is_not_built_from_defaults(self) -> None:
        """`carry` needs a swap table, `lead_lag` a peer. A seat naming one is a lead for the
        deepening worker, not a recipe -- the same rule the prose path applies."""
        for fam in ("carry", "lead_lag", "cot_positioning", "event_reaction"):
            cands, disp = mcc.compile_row("deepseek", _seat_row(
                title="x", symbols=["AUDJPY"], family=fam), UNI)
            assert cands == [] and disp == "NEEDS_EXACT_RULE_EXTRACTION", fam

    def test_a_family_the_registry_does_not_know_is_not_compiled(self) -> None:
        cands, disp = mcc.compile_row("deepseek", _seat_row(
            title="x", symbols=["EURUSD"], family="quantum_flux_reversal"), UNI)
        assert cands == [] and disp == "NEEDS_EXACT_RULE_EXTRACTION"

    def test_a_calendar_hypothesis_without_a_month_is_still_not_a_recipe(self) -> None:
        cands, disp = mcc.compile_row("deepseek", _seat_row(
            title="gold seasonality", symbols=["XAUUSD"], family="calendar_month",
            testable_claim="gold has a seasonal tendency"), UNI)
        assert cands == [] and disp == "NEEDS_EXACT_RULE_EXTRACTION"

    def test_a_hypothesis_with_no_declared_instrument_is_deepened_not_guessed(self) -> None:
        cands, disp = mcc.compile_row("deepseek", _seat_row(
            title="fade the gap", symbols=[], family="overnight_gap_decay",
            testable_claim="the overnight gap fills by noon"), UNI)
        assert cands == [] and disp == "NEEDS_SYMBOL_EXTRACTION"

    def test_an_instrument_the_registry_cannot_price_is_not_minted(self) -> None:
        """A bare currency in a seat's `symbols` mints nothing here. (The structured miners'
        `resolve_symbols` still counts "EUR" toward the disposition LABEL, which is why the row
        reads NEEDS_EXACT_RULE_EXTRACTION rather than NEEDS_SYMBOL_EXTRACTION; the property that
        matters is that no candidate is produced from it.)"""
        cands, disp = mcc.compile_row("deepseek", _seat_row(
            title="x", symbols=["EUR", "NOTATHING"], family="overnight_gap_decay"), UNI)
        assert cands == [] and disp == "NEEDS_EXACT_RULE_EXTRACTION"
        assert mcc._declared_symbols({"symbols": ["EUR", "NOTATHING"]}, UNI) == []

    def test_at_most_four_declared_instruments(self) -> None:
        cands, _ = mcc.compile_row("deepseek", _seat_row(
            title="x", symbols=["EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "XAGUSD", "AUDJPY"],
            family="overnight_gap_decay"), UNI)
        assert len(cands) == 4

    def test_the_testable_claim_is_read_as_prose(self) -> None:
        """A seat with no family of its own still converts when its claim names one."""
        cands, disp = mcc.compile_row("deepseek", _seat_row(
            title="yen", testable_claim="EURUSD fades the overnight gap at the open"), UNI)
        assert disp == "TEXT_EXTRACTED"
        assert {(c["symbol"], c["family"]) for c in cands} == {("EURUSD", "overnight_gap_decay")}


# ------------------------------------------------------ declared instruments before the prose
def test_declared_instruments_are_read_before_the_prose_names_one() -> None:
    """Any miner row, not only a seat's: `symbols: ["USDJPY"]` plus prose that names a family
    phrase but no instrument converted at zero, because the prose path read the text alone."""
    cands, disp = mcc.compile_row("reddit", {
        "source": "reddit", "kind": "post", "symbols": ["USDJPY"],
        "text": "fade the overnight gap at the Tokyo open, it fills most days"}, UNI)
    assert disp == "TEXT_EXTRACTED"
    assert {c["symbol"] for c in cands} == {"USDJPY"}


def test_a_bare_currency_in_a_structured_field_is_not_expanded_by_the_prose_path() -> None:
    assert mcc._declared_symbols({"symbols": ["EUR", "XAU/USD", "gbp-usd"]}, UNI) == [
        "XAUUSD", "GBPUSD"]


# ---------------------------------------------------------------- kimi: writer -> reader -> docket
class TestTheKimiSeatFeedsTheDocket:
    def _finding(self, **over) -> dict:
        base = {"date": "2026-09-08", "source": "kimi_k3_deep_forest", "wave": 3,
                "model": "moonshotai/kimi-k2:free", "claim_class": "VERIFIED",
                "problem": "Gold-ETF creation/redemption forces AP hedging",
                "evidence": "https://www.spdrgoldshares.com free daily flow",
                "benefit": "early warning on gold basis pressure", "cost": "1d",
                "dependencies": "NONE", "success_metric": "corr with gold basis > 0.3",
                "kill_condition": "no relation after 60d", "status": "proposed"}
        base.update(over)
        return base

    def test_a_donation_lands_in_the_tree_the_compiler_reads_and_every_row_is_accounted(
            self, intel, monkeypatch) -> None:
        K = pytest.importorskip("scripts.kimi_hunter")
        monkeypatch.setattr(K, "DONATE_DIR", intel / "data" / "intelligence" / "kimi")
        path = K._donate([
            self._finding(),
            self._finding(problem="London open range breakout on gold",
                          evidence="own bars; the range set at the London open"),
            self._finding(problem="a mock row", mock=True),
        ])
        assert path is not None and path.parent == intel / "data" / "intelligence" / "kimi"
        rows = mcc.recent_rows(mcc.datetime.now(tz=mcc.UTC))
        assert sorted(src for src, _ in rows) == ["kimi_k3_deep_forest"] * 2, (
            "both real findings are read as kimi rows and the mock row never leaves the ledger")
        by_title = {r["title"]: mcc.compile_row(src, r, UNI) for src, r in rows}
        cands, disp = by_title["London open range breakout on gold"]
        assert disp == "TEXT_EXTRACTED"
        assert {(c["symbol"], c["family"]) for c in cands} == {
            ("XAUUSD", "session_range_breakout")}
        assert cands[0]["params"] == {"range_start": 10, "range_end": 13, "signal_at": 13}
        assert cands[0]["source"] == "miner:kimi_k3_deep_forest"
        # the ETF-flow mechanism names no price-only family: a deepening task, not a guess
        cands, disp = by_title["Gold-ETF creation/redemption forces AP hedging"]
        assert cands == [] and disp == "NEEDS_EXACT_RULE_EXTRACTION"

    def test_the_donated_row_carries_its_attribution(self, intel, monkeypatch) -> None:
        K = pytest.importorskip("scripts.kimi_hunter")
        monkeypatch.setattr(K, "DONATE_DIR", intel / "data" / "intelligence" / "kimi")
        path = K._donate([self._finding()])
        doc = json.loads(path.read_text("utf-8"))
        assert doc["source"] == "kimi_k3_deep_forest"
        (row,) = doc["discoveries"]
        assert row["kind"] == "hypothesis" and row["symbols"] == []
        assert row["model"] == "moonshotai/kimi-k2:free" and row["wave"] == 3
        assert row["claim_class"] == "VERIFIED"
        assert row["url"].startswith("kimi://2026-09-08/wave3/")
        assert "early warning on gold basis pressure" in row["text"]
        assert "no relation after 60d" in row["text"]


# ------------------------------------------------------------ the seats' conversion is a field
def test_seat_conversion_is_one_block_in_the_compiled_artifact() -> None:
    """A seat with no rows in the window is reported with zeros, never omitted."""
    seats = mcc.seat_summary({"deepseek": {"rows": 12, "candidates": 3, "deepening": 9},
                              "reddit": {"rows": 900, "candidates": 4, "deepening": 896}})
    assert seats == {"deepseek": {"rows": 12, "candidates": 3, "deepening": 9},
                     "kimi_k3_deep_forest": {"rows": 0, "candidates": 0, "deepening": 0}}
    assert '"seats": seats' in Path(mcc.__file__).read_text("utf-8")
