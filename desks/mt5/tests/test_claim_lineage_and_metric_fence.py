"""The two data defects the PR #160 committee dry run found, fenced where rows become cells.

1. One video's "best of ~200 variations" was swept into 25,520 bank cells that each counted as
   independent breadth. Every row the proposer mints, and every candidate the compiler builds
   from one, now carries ONE claim family charged the 200 trials once.
2. The MQL5 hunter read `Profit Trades: 2 281 (76.90%)` as a 2,281% win rate. The parser reads
   the percent now, and the compiler refuses any impossible metric with a counted reason.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK / "side_channels"),
           str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from side_channels import mql5_survivor_hunter as hunter  # noqa: E402

from libs.research import claim_selection as cs  # noqa: E402
from research import htf_anchor_proposer as hp  # noqa: E402
from research import miner_candidate_compiler as mcc  # noqa: E402

UNI = {"EURUSD", "XAUUSD"}


# ------------------------------------------------------------------ 1. the searched claim
def test_the_video_grid_is_one_claim_family_charged_200_once() -> None:
    rows = hp.build_candidates({"binding": [{"family": "session_range_breakout", "chart": "H1",
                                             "expansion_mult": 1.5}]}, ["EURUSD", "XAUUSD"])
    assert all(r["claim_selection_trials"] == hp.SOURCE_SELECTION_TRIALS == 200 for r in rows)
    assert cs.stamp_all(rows) == len(rows)
    b = cs.breadth(rows)
    assert b["breadth_units"] == 1 and len(b["claim_families"]) == 1
    (fam,) = b["claim_families"].values()
    assert fam["selection_trials"] == 200 and fam["cells"] == len(rows)
    assert set(fam["families"]) == {"htf_anchor_trend", "exit_operated"}


def test_a_compiled_candidate_carries_the_claim_family_of_its_row() -> None:
    row = hp._row("EURUSD", "htf_anchor_trend",
                  {"timeframe": "H1", "anchor_mult": 4, "expansion_mult": 4.0,
                   "exit_on_anchor_flip": False}, "arm=vol4.0")
    cands, why = mcc.compile_row(hp.SEAT, row, UNI)
    assert why == "EXACT_RECIPE" and cands
    probe = dict(row)
    cs.stamp(probe)
    assert {c["claim_family"] for c in cands} == {probe["claim_family"]}
    assert all(c["breadth_unit"] == c["claim_family"] and c["claim_selection_trials"] == 200
               for c in cands)


def test_any_source_claiming_best_of_n_is_charged_n_at_the_family() -> None:
    """GENERALISED: not only the video. A forum row whose own words say its recipe was the best of
    1,200 backtests compiles to cells that share one family charged 1,200."""
    row = {"kind": "hypothesis", "family": "overnight_gap_decay", "symbols": ["EURUSD", "XAUUSD"],
           "params": {}, "title": "gap fade",
           "text": "This was the best of 1,200 backtests I ran over the weekend."}
    cands, _ = mcc.compile_row("reddit", row, UNI)
    assert len(cands) == 2
    assert len({c["claim_family"] for c in cands}) == 1
    assert {c["claim_selection_trials"] for c in cands} == {1200}
    plain, _ = mcc.compile_row("reddit", {**row, "text": "gaps fade by the London open"}, UNI)
    # every candidate carries the key; None records "the source stated no search"
    assert plain and all(c["claim_family"] is None and "breadth_unit" not in c for c in plain)


# ------------------------------------------------------------------ 2. the impossible metric
def _track(win: object) -> dict:
    return {"source": "mql5_survivors", "kind": "track_record", "title": "Gold grid",
            "url": "https://www.mql5.com/en/signals/2304847", "symbols": ["XAUUSD"],
            "phenotypes": ["trend", "gold"], "growth_pct": 20585.63, "weeks": 90.0, "pf": 1.9,
            "trades": 2966.0, "win_pct": win, "max_dd_pct": 22.0}


def test_the_compiler_refuses_an_impossible_metric_before_any_cell() -> None:
    # a win "rate" no arithmetic on the row can recover (more wins than trades) is refused
    assert mcc.compile_row("mql5_survivors", _track(3500.0), UNI) == ([], "IMPOSSIBLE_METRIC")
    no_trades = {k: v for k, v in _track(2281.0).items() if k != "trades"}
    assert mcc.compile_row("mql5_survivors", no_trades, UNI) == ([], "IMPOSSIBLE_METRIC")
    _, why = mcc.compile_row("mql5_survivors", _track(76.9), UNI)
    assert why != "IMPOSSIBLE_METRIC"


def test_the_compiler_repairs_a_derivable_win_rate_instead_of_refusing() -> None:
    """The MQL5 defect exactly: the COUNT 2,281 in the percent field beside 2,966 trades is a
    76.9% win rate, derived from the row's own numbers -- repaired, recorded, and compiled."""
    row = _track(2281.0)
    _, why = mcc.compile_row("mql5_survivors", row, UNI)
    assert why != "IMPOSSIBLE_METRIC"
    assert row["win_pct"] == pytest.approx(100 * 2281 / 2966, abs=1e-3)
    assert row["metric_repairs"] and row["metric_repairs"][0].startswith("win_rate_derived:")


class _GraphStub:
    def prior_failures(self, *_a, **_k):
        return {"n_failed": 0, "region": ""}

    def rows(self):
        return []


def test_the_refusal_is_counted_in_the_artifact_and_never_deepened(tmp_path,
                                                                   monkeypatch) -> None:
    import libs.ops.repair_invoke as ri
    import libs.research.hypothesis_graph as hg
    root = tmp_path / "intel"
    (root / "mql5_survivors").mkdir(parents=True)
    (root / "mql5_survivors" / "discoveries_1.json").write_text(json.dumps(
        [_track(3500.0), _track(4100.0) | {"url": "u2"}, _track(76.9) | {"url": "u3"},
         _track(2281.0) | {"url": "u4"}]), "utf-8")
    for name, val in (("INTEL_ROOTS", (root,)), ("OUT", tmp_path / "out.json"),
                      ("DEEPEN", tmp_path / "deepen.json"),
                      ("DEEPEN_WORKED", tmp_path / "worked.jsonl"),
                      ("DEEPENED", tmp_path / "deepened.json"),
                      ("CURSOR", tmp_path / "cursor.json")):
        monkeypatch.setattr(mcc, name, val)
    monkeypatch.setattr(mcc, "known_symbols", lambda: set(UNI))
    monkeypatch.setattr(mcc, "structurally_untestable_families", dict)
    monkeypatch.setattr(mcc, "expand_axes", lambda rows: rows)
    monkeypatch.setattr(hg, "Graph", _GraphStub)
    monkeypatch.setattr(hg, "record_candidates", lambda *a, **k: 0)
    monkeypatch.setattr(ri, "request_repair", lambda reason, **kw: False)
    assert mcc.main() == 0
    out = json.loads((tmp_path / "out.json").read_text("utf-8"))
    fence = out["impossible_metrics"]
    assert (fence["checked"], fence["refused"], fence["repaired"]) == (4, 2, 1)
    assert fence["by_repair"] == {"win_rate_derived": 1}
    assert fence["by_reason"] == {"win_rate_out_of_bounds": 2}
    assert fence["by_source"] == {"mql5_survivors": 2}
    assert out["per_source"]["mql5_survivors"]["valid_refusals"] == 2
    tasks = json.loads((tmp_path / "deepen.json").read_text("utf-8"))["tasks"]
    assert not any(t.get("disposition") == "IMPOSSIBLE_METRIC" for t in tasks)


# ------------------------------------------------------------------ the MQL5 parser itself
_PAGE = ('<div class="s-list-info__label">Trades:</div><div class="s-list-info__value">2 966'
         '</div><div class="s-list-info__label">Profit Trades:</div>'
         '<div class="s-list-info__value">2 281 (76.90%)</div>'
         '<div class="s-list-info__label">Loss Trades:</div>'
         '<div class="s-list-info__value">685 (23.10%)</div>')


def test_the_win_rate_is_the_percent_in_parentheses_never_the_count() -> None:
    trades = hunter.field(_PAGE, hunter.TRADES_LABEL)
    assert trades == 2966.0
    assert hunter.win_rate(_PAGE, trades) == (76.9, "percent_in_parentheses")


@pytest.mark.parametrize(("html", "trades", "expect"), [
    ("Profit Trades: 2 281 (76,90%)", 2966.0, (76.9, "percent_in_parentheses")),
    ("Profit Trades: 2,281", 2966.0, (76.9, "count_over_trades")),
    ("Profit Trades: 2 281", None, (None, "count_without_trades")),
    ("Profitable Trades: 64%", None, (64.0, "bare_percent")),
    ("Profit Trades: 2296%", None, (None, "percent_out_of_bounds")),
    ("Growth: 120%", 10.0, (None, "absent")),
])
def test_every_win_rate_read_is_a_rate_or_unmeasured(html: str, trades: float | None,
                                                     expect: tuple) -> None:
    assert hunter.win_rate(html, trades) == expect


def test_the_trades_label_is_not_the_profit_trades_line() -> None:
    html = "Profit Trades: 2 281 (76.90%) Loss Trades: 685 (23.10%) Trades: 2 966"
    assert hunter.field(html, hunter.TRADES_LABEL) == 2966.0


def test_separate_numbers_are_never_glued_across_whitespace() -> None:
    assert hunter.field("Weeks: 150\n  3 more", "Weeks") == 150.0
    assert hunter.field("Growth: 20 585.63%", "Growth") == 20585.63
