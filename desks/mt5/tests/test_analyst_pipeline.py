"""THE ANALYST FUNNEL, MEASURED ON A WORLD WHOSE ANSWER WAS PLANTED IN IT.

Every test here builds a whole desk in `tmp_path` -- bars, a seat directory, a frontier queue, a
hypothesis graph, a gate ledger, a family registry -- with a KNOWN outcome buried in it, and
monkeypatches the module's path constants and its six guarded readers onto that world. Nothing
touches the real tree, and nothing depends on which families happen to be registered today.

THE THREE THAT WOULD MATTER MOST IF THEY BROKE.

`test_triage_refuses_an_equity_with_the_two_lane_code` pins the two-lane order at the analyst's
door. Trial count is a SHARED cost: an equity lead does not merely fail to help, it enlarges the
family-wise error budget every FX and metals cell then has to clear. A silent leak here is the
10,927-cell leak the frontier map measured, one layer earlier.

`test_a_parameter_the_family_does_not_accept_is_never_set` pins the rule that keeps a parsed claim
honest. A parameter the analyst invented is filtered out downstream and the family runs on its
defaults -- so the docket would carry a cell labelled with the claim's number and tested without
it, which is a different hypothesis wearing the claim's name.

`test_donations_with_no_verdict_yet_are_unmeasured_not_zero` pins L1.28a on the one number a
reader will quote. Five donations and no verdict is not a 0% certification rate; it is a rate
nobody has measured, and a printed 0.0 reads as a dead lane forever.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_DESK), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import analyst_pipeline as A  # noqa: E402

FX, GOLD, EQUITY, ODD = "EURUSD", "XAUUSD", "Apple", "WIDGET"

#: The stub registry. `carry` is registered and NOT price-only; `joint_genome` is a spec
#: constructor; `boom` is constructible and raises -- one family per refusal the module can make.
FAMILY_TABLE = {
    "session_range_breakout": ("breakout_liquidity", "price_only", "stop"),
    "volume_spike": ("inventory_shock", "price_only", "market"),
    "mean_reversion_rsi": ("range_reversion", "price_only", "limit"),
    "carry": ("carry_rollover", "carry", "market"),
    "joint_genome": ("UNKNOWN", "price_only", "UNKNOWN"),
}
SIGNALS = {"session_range_breakout": 60, "volume_spike": 5, "mean_reversion_rsi": 60,
           "carry": 60, "joint_genome": 60}
LANES = {FX: "hypothesis", GOLD: "hypothesis", EQUITY: "event", ODD: "unclassified"}


# =============================================================================== the stub world
def _family(name: str):
    """A constructor with a real signature, so `family_params` reads it the way it reads a live
    family: `lookback` exists here and `bb_n` does not."""
    def fn(df, *, lookback: int = 20, ttl_bars: int = 12, rr: float = 2.0,
           range_start: int = 7, active_month: int | None = None):
        assert len(df) > 0
        return ["signal"] * SIGNALS.get(name, 0)
    return fn


def _boom(df, **_kw):
    raise ValueError("this family cannot run on these bars")


def _family_func(name: str):
    if name == "boom":
        return _boom
    return _family(name) if name in FAMILY_TABLE else None


class FakeCompiler:
    """The compiler's prose readers, stood in for. The real ones are pinned by its own tests;
    what this file pins is that the pipeline ASKS them rather than re-deriving an answer."""

    @staticmethod
    def text_symbols(text: str, universe: set[str]) -> list[str]:
        folded = {u.upper(): u for u in universe}
        return [folded[k] for k in sorted(folded) if k.lower() in text][:4]

    @staticmethod
    def text_families(text: str) -> list[tuple[str, str]]:
        return [("volume_spike", "volume spike")] if "volume spike" in text else []

    @staticmethod
    def text_session(text: str) -> str | None:
        return "asia" if "asian session" in text else None

    @staticmethod
    def _text_params(family: str, text: str) -> dict | None:
        if family == "session_range_breakout":
            return {"range_start": 7} if "asian session" in text else {}
        if family == "calendar_month":
            return None                       # a month nobody stated: not a recipe
        return {}


def _bars(n: int = 400) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    close = pd.Series(np.linspace(1.0, 1.1, n), index=idx)
    return pd.DataFrame({"open": close, "high": close * 1.001, "low": close * 0.999,
                         "close": close, "tick_volume": np.arange(n, dtype=float)}, index=idx)


@pytest.fixture
def desk(tmp_path, monkeypatch):
    """A whole desk in `tmp_path`, with every path and every guarded reader redirected."""
    uni = tmp_path / "universe"
    intel = tmp_path / "intelligence"
    (intel / "seat").mkdir(parents=True)
    uni.mkdir(parents=True)
    for sym in (FX, GOLD, EQUITY, ODD):
        _bars().to_parquet(uni / f"{sym}_H1.parquet")
    monkeypatch.setattr(A, "UNI", uni)
    monkeypatch.setattr(A, "INTEL_ROOTS", (intel,))
    monkeypatch.setattr(A, "FRONTIER_QUEUE", tmp_path / "frontier_queue.jsonl")
    monkeypatch.setattr(A, "GRAPH", tmp_path / "hypothesis_graph.jsonl")
    monkeypatch.setattr(A, "GATE_LEDGER", tmp_path / "gate_verdict_ledger.jsonl")
    monkeypatch.setattr(A, "OUT_REPORT", tmp_path / "ANALYST_PIPELINE.json")
    monkeypatch.setattr(A, "LEDGER", tmp_path / "analyst_pipeline.jsonl")
    monkeypatch.setattr(A, "CURSOR", tmp_path / "analyst_pipeline_cursor.json")
    monkeypatch.setattr(A, "_lane", lambda s: LANES.get(s, "unclassified"))
    monkeypatch.setattr(A, "_family_table", lambda: dict(FAMILY_TABLE))
    monkeypatch.setattr(A, "_not_a_family", lambda: frozenset({"joint_genome"}))
    monkeypatch.setattr(A, "_family_func", _family_func)
    monkeypatch.setattr(A, "_compiler", lambda: FakeCompiler)
    donated: list[dict] = []
    monkeypatch.setattr(A, "_donate", lambda rows, tests_run: (donated.extend(rows),
                                                              tmp_path / "donation.json")[1])
    return {"tmp": tmp_path, "intel": intel / "seat", "uni": uni, "donated": donated}


def seat_rows(desk, rows: list[dict], name: str = "discoveries_1.json") -> Path:
    path = desk["intel"] / name
    path.write_text(json.dumps(rows), "utf-8")
    return path


def lead(desk, **row):
    """The ONE lead an intelligence row of this shape produces, through the live schema."""
    seat_rows(desk, [row])
    leads, _skipped = A.intake(datetime.now(tz=UTC), 10, set())
    assert leads, "the intake produced no lead for this row"
    return leads[0]


CLAIM = ("EURUSD breaks the asian session range and continues, on a 55 bar lookback, "
         "because stop-loss holders sit above it.")


# ====================================================================================== triage
def test_triage_refuses_an_equity_with_the_two_lane_code(desk):
    row = {"kind": "hypothesis", "symbols": [EQUITY], "family": "volume_spike",
           "claim": "Apple mean-reverts after a volume spike on the hour."}
    _syms, code = A.triage(lead(desk, **row), {EQUITY}, set(), set())
    assert code == "event_lane_instrument"


def test_triage_refuses_an_instrument_the_registry_does_not_classify(desk):
    row = {"kind": "hypothesis", "symbols": [ODD], "family": "volume_spike",
           "claim": "WIDGET runs after a volume spike, every session."}
    _syms, code = A.triage(lead(desk, **row), {ODD}, set(), set())
    assert code == "unclassified_instrument"


def test_triage_refuses_a_lead_that_names_no_instrument(desk):
    row = {"kind": "story", "claim": "A famous trader says patience beats prediction."}
    _syms, code = A.triage(lead(desk, **row), {FX, GOLD}, set(), set())
    assert code == "no_instrument"


def test_triage_refuses_an_operational_row_on_the_record(desk):
    """A row the schema calls not-evidence is still COUNTED here, as a stub lead with a code."""
    one = lead(desk, kind="fetch_error", url="https://x", title="walled")
    _syms, code = A.triage(one, {FX}, set(), set())
    assert code == "operational_row"


def test_triage_refuses_a_claim_the_desk_has_already_worked(desk):
    one = lead(desk, kind="hypothesis", symbols=[FX], family="volume_spike", claim=CLAIM)
    _syms, first = A.triage(one, {FX}, set(), set())
    assert first is None
    _syms, again = A.triage(one, {FX}, set(), {one.dedupe_key()})
    assert again == "duplicate_lead"


def test_triage_refuses_a_cell_the_hypothesis_graph_already_holds(desk):
    one = lead(desk, kind="hypothesis", symbols=[FX], family="volume_spike", claim=CLAIM)
    _syms, code = A.triage(one, {FX}, {f"{FX}|volume_spike"}, set())
    assert code == "duplicate_cell"


def test_triage_refuses_a_lead_with_no_mechanism_anywhere(desk):
    row = {"kind": "story", "symbols": [FX],
           "claim": "EURUSD went up on Tuesday and a lot of people noticed it."}
    _syms, code = A.triage(lead(desk, **row), {FX}, set(), set())
    assert code == "no_mechanism"


# ================================================================================== structuring
def test_structuring_maps_a_mechanism_to_the_family_that_implements_it(desk):
    one = lead(desk, kind="story", symbols=[FX], mechanism_tags=["breakout_liquidity"],
               claim="EURUSD breaks out of its range when stop holders are cleared.")
    cells, code = A.structure(one, [FX], set())
    assert code is None
    assert [c["family"] for c in cells] == ["session_range_breakout"]
    assert cells[0]["mechanism"] == "breakout_liquidity"


def test_structuring_parses_a_window_from_the_claims_own_text(desk):
    one = lead(desk, kind="story", symbols=[FX], mechanism_tags=["breakout_liquidity"],
               claim=CLAIM)
    cells, code = A.structure(one, [FX], set())
    assert code is None
    assert cells[0]["params"]["lookback"] == 55
    assert cells[0]["params"]["range_start"] == 7        # the session, via the compiler's reader
    assert cells[0]["parsed"]["window"] == 55


def test_a_parameter_the_family_does_not_accept_is_never_set(desk):
    """`volume_spike`'s stub signature has no `threshold_pct`; a parsed percent must not appear."""
    one = lead(desk, kind="story", symbols=[FX], mechanism_tags=["inventory_shock"],
               claim="EURUSD moves 3 percent after a volume spike, held 9 bars.")
    cells, _code = A.structure(one, [FX], set())
    assert "threshold_pct" not in cells[0]["params"]
    assert cells[0]["params"]["ttl_bars"] == 9           # `hold` -> the slot the family DOES have


def test_structuring_reuses_the_seats_own_family_and_parameters(desk):
    one = lead(desk, kind="hypothesis", symbols=[GOLD], family="mean_reversion_rsi",
               params={"lookback": 7}, claim="Gold reverts after a 55 bar push in the asian "
                                             "session.")
    cells, code = A.structure(one, [GOLD], set())
    assert code is None
    assert cells[0]["family"] == "mean_reversion_rsi"    # not the prose's volume_spike
    assert cells[0]["params"]["lookback"] == 7           # the seat's number beats the parse


def test_structuring_refuses_a_family_that_is_not_price_only(desk):
    one = lead(desk, kind="hypothesis", symbols=[FX], family="carry",
               claim="EURUSD pays a positive carry to the long side overnight.")
    _cells, code = A.structure(one, [FX], set())
    assert code == "family_not_price_only"


def test_structuring_refuses_a_family_the_desk_does_not_have(desk):
    one = lead(desk, kind="hypothesis", symbols=[FX], family="astrology_cycle",
               claim="EURUSD follows the lunar cycle at the london open.")
    _cells, code = A.structure(one, [FX], set())
    assert code == "family_not_registered"


def test_structuring_refuses_a_lead_whose_mechanism_maps_to_nothing(desk):
    one = lead(desk, kind="story", symbols=[FX], mechanism_tags=["astral_projection"],
               claim="EURUSD responds to something nobody here has a family for.")
    _cells, code = A.structure(one, [FX], set())
    assert code == "no_family_for_mechanism"


# ==================================================================================== pre-screen
def test_prescreen_rejects_a_cell_that_fires_too_few_trades(desk):
    ok, code, n = A.prescreen({"symbol": FX, "family": "volume_spike", "params": {}})
    assert (ok, code, n) == (False, "too_few_trades", SIGNALS["volume_spike"])
    assert n < A.MIN_TRADES


def test_prescreen_passes_a_cell_that_fires_enough(desk):
    ok, code, n = A.prescreen({"symbol": FX, "family": "session_range_breakout", "params": {}})
    assert (ok, code) == (True, None)
    assert n >= A.MIN_TRADES


def test_prescreen_reports_bars_it_could_not_read(desk):
    ok, code, n = A.prescreen({"symbol": "NOSUCH", "family": "volume_spike", "params": {}})
    assert (ok, code, n) == (False, "no_bars", 0)


def test_prescreen_counts_a_family_that_raises_rather_than_dying(desk):
    ok, code, _n = A.prescreen({"symbol": FX, "family": "boom", "params": {}})
    assert (ok, code) == (False, "signal_error")


# ================================================================================ the whole pass
def test_the_donation_carries_the_lead_kind_in_its_source_and_the_lead_in_its_lineage(desk):
    seat_rows(desk, [{"kind": "hypothesis", "symbols": [FX], "family": "session_range_breakout",
                      "claim": CLAIM}])
    report = A.run(max_leads=5, budget_s=60)
    assert report["donated"] == 1
    row = desk["donated"][0]
    # THE LEAD KIND IS THE SCHEMA'S SOURCE TAXONOMY, not the row's own `kind` field: a seat row
    # nothing identifies is `other`, and that is the bucket conversion is measured in.
    assert row["source"] == "analyst_pipeline:other"
    assert row["kind"] == "hypothesis"                  # the shape the compiler admits
    assert row["family"] == "session_range_breakout" and row["symbols"] == [FX]
    assert row["lineage"]["lead_id"] and row["lineage"]["stage"] == "analyst_pipeline"
    assert row["evidence"]["prescreen_signals"] >= A.MIN_TRADES


def test_the_cursor_skips_a_lead_the_previous_pass_already_worked(desk):
    seat_rows(desk, [{"kind": "hypothesis", "symbols": [FX], "family": "session_range_breakout",
                      "claim": CLAIM}])
    first = A.run(max_leads=5, budget_s=60)
    assert first["intake"] == 1
    cursor = json.loads(A.CURSOR.read_text("utf-8"))
    assert len(cursor["processed"]) == 1
    second = A.run(max_leads=5, budget_s=60)
    assert second["intake"] == 0
    assert second["unmeasured"]["leads_skipped_by_cursor"] == 1


def test_conversion_counts_every_stage_and_names_every_refusal(desk):
    seat_rows(desk, [
        {"kind": "hypothesis", "symbols": [FX], "family": "session_range_breakout",
         "claim": CLAIM},
        {"kind": "hypothesis", "symbols": [EQUITY], "family": "volume_spike",
         "claim": "Apple runs after a volume spike."},
        {"kind": "hypothesis", "symbols": [GOLD], "family": "carry",
         "claim": "Gold pays a carry to the long side overnight."},
        {"kind": "hypothesis", "symbols": [GOLD], "family": "volume_spike",
         "claim": "XAUUSD extends after a volume spike in the asian session."},
    ])
    report = A.run(max_leads=10, budget_s=60)
    assert report["intake"] == 4
    assert report["triage"]["passed"] == 3
    assert report["triage"]["rejected_by_reason"] == {"event_lane_instrument": 1}
    assert report["structured"] == 2
    assert report["structuring_rejected_by_reason"] == {"family_not_price_only": 1}
    assert report["prescreened"] == {"passed": 1, "rejected_by_reason": {"too_few_trades": 1}}
    assert report["donated"] == 1
    assert report["conversion"]["intake_to_donated"] == 0.25
    assert report["rule"] == A.RULE
    stages = {r["stage"] for r in A._read_jsonl(A.LEDGER)}
    assert {"triage", "structuring", "prescreen", "donation"} <= stages


def test_followup_joins_a_later_verdict_back_to_the_lead_kind(desk):
    seat_rows(desk, [{"kind": "hypothesis", "symbols": [FX], "family": "session_range_breakout",
                      "claim": CLAIM}])
    first = A.run(max_leads=5, budget_s=60)
    assert first["followup"]["by_lead_kind"]["other"] == {"donated": 1, "judged": 0,
                                                         "certified": 0}
    later = (datetime.now(tz=UTC) + timedelta(hours=1)).isoformat()
    A.GATE_LEDGER.write_text(json.dumps({"at": later, "sym": FX,
                                         "family": "session_range_breakout", "passed": True,
                                         "terminal_gate": "PASSED"}) + "\n", "utf-8")
    second = A.run(max_leads=5, budget_s=60)
    assert second["followup"]["by_lead_kind"]["other"] == {"donated": 1, "judged": 1,
                                                          "certified": 1}
    assert second["conversion"]["donated_to_certified"] == 1.0


def test_donations_with_no_verdict_yet_are_unmeasured_not_zero(desk):
    seat_rows(desk, [{"kind": "hypothesis", "symbols": [FX], "family": "session_range_breakout",
                      "claim": CLAIM}])
    report = A.run(max_leads=5, budget_s=60)
    assert report["conversion"]["donated_to_certified"] is None
    assert report["unmeasured"]["donations_awaiting_a_verdict"] == 1


def test_the_frontier_queue_is_read_as_an_intake_source(desk):
    A.FRONTIER_QUEUE.write_text(json.dumps({
        "at": "2026-09-05T21:23:30+00:00", "candidate_id": "F-b22d75874807141f",
        "state": "DISCOVERED", "firm": "Citadel Securities", "source_url": "",
        "claim": CLAIM, "evidence_grade": "D", "source_kind": "public_forum",
        "symbols": [FX], "family": "session_range_breakout"}) + "\n", "utf-8")
    report = A.run(max_leads=5, budget_s=60)
    assert report["intake"] == 1
    assert report["donated"] == 1
    # `source_kind: public_forum` is what makes this lead a `forum`, and the per-kind conversion
    # split is only meaningful because the taxonomy comes off the source rather than the miner.
    assert desk["donated"][0]["source"] == "analyst_pipeline:forum"
    assert set(report["followup"]["by_lead_kind"]) == {"forum"}


def test_the_budget_stops_the_pass_and_defers_the_rest(desk, monkeypatch):
    seat_rows(desk, [{"kind": "hypothesis", "symbols": [FX], "family": "session_range_breakout",
                      "claim": CLAIM},
                     {"kind": "hypothesis", "symbols": [GOLD], "family": "session_range_breakout",
                      "claim": CLAIM.replace("EURUSD", "XAUUSD")}])

    class Clock:
        """Zero until the first lead is inside the pass, then far past any budget."""

        def __init__(self) -> None:
            self.calls = 0

        def monotonic(self) -> float:
            self.calls += 1
            return 0.0 if self.calls <= 2 else 9_999.0

    monkeypatch.setattr(A, "time", Clock())
    report = A.run(max_leads=5, budget_s=5.0)
    assert report["unmeasured"]["stopped_on_budget"] is True
    assert report["unmeasured"]["leads_deferred_by_budget"] == 1
    assert report["prescreened"]["rejected_by_reason"] == {"budget_exhausted": 1}
    assert report["donated"] == 0
    # THE DEFERRED LEAD IS NOT MARKED WORKED. A budget stop that wrote the whole intake into the
    # cursor would lose every lead it never looked at, silently and forever.
    assert len(json.loads(A.CURSOR.read_text("utf-8"))["processed"]) == 1


def test_the_cli_dry_run_writes_nothing_and_prints_the_report(desk, capsys):
    seat_rows(desk, [{"kind": "hypothesis", "symbols": [FX], "family": "session_range_breakout",
                      "claim": CLAIM}])
    assert A.main(["--dry-run", "--max-leads", "5", "--budget-s", "60"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["dry_run"] is True and report["intake"] == 1
    assert report["donated"] == 1 and report["rule"] == A.RULE
    assert desk["donated"] == []
    for path in (A.OUT_REPORT, A.LEDGER, A.CURSOR):
        assert not path.exists(), f"{path.name} was written by a dry run"
