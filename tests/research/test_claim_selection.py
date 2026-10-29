"""A source's "best of N variations" is charged N trials ONCE, to one claim family, and the cells
swept from it count as ONE breadth unit (committee dry run on PR #160, 2026-09-30: 25,520 bank
cells from one video's "best of ~200 variations" counted as 25,520 independent units)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.research import claim_selection as cs  # noqa: E402
from libs.research import experiment_ledger as el  # noqa: E402
from libs.research import trial_ledger as T  # noqa: E402

VIDEO = ("a trend anchor gates the entry. PRIOR: converted from a public video whose reported "
         "Sharpe 1.87 was the MAXIMUM of ~200 searched variations with no multiplicity charge, "
         "on one single-name equity; its own Monte Carlo median was ~1.30. A public claim is a "
         "hypothesis, never evidence.")


@pytest.mark.parametrize(("text", "n"), [
    ("the best of 200 variations", 200),
    (VIDEO, 200),
    ("we optimised over 1,500 parameter combinations and report the winner", 1500),
    ("I searched about 200 variations before this one held up", 200),
    ("top result out of 12 backtests", 12),
    ("picked from roughly 300 variants", 300),
    ("a carry premium paid for bearing crash risk in the funding leg", 0),
    ("the best trade of 2024 was 3.2%", 0),
    ("", 0),
])
def test_a_stated_search_is_read_as_its_trial_count(text: str, n: int) -> None:
    assert cs.selection_trials(text) == n


def _cell(i: int, symbol: str = "EURUSD", family: str = "htf_anchor_trend",
          note: str = VIDEO) -> dict:
    return {"genome_id": f"g{i}", "symbol": symbol, "family": family,
            "params": {"timeframe": "H1", "anchor_mult": 3 + i % 4, "expansion_mult": i / 10},
            "source": "miner:video_anchor_exit", "mechanism_note": note,
            "source_title": f"{family} on {symbol} -- video-derived cell {i}",
            "fate": "FAILED" if i % 2 else None}


def test_every_cell_of_one_claim_shares_one_family_and_counts_as_one_unit() -> None:
    rows = [_cell(i, sym, fam) for i, (sym, fam) in enumerate(
        (s, f) for s in ("EURUSD", "XAUUSD", "US500") for f in ("htf_anchor_trend",
                                                                  "exit_operated"))]
    plain = [{"genome_id": f"p{i}", "symbol": "EURUSD", "family": "carry",
              "params": {"k": i}, "mechanism_note": "a carry premium"} for i in range(4)]
    before = cs.breadth(rows + plain)
    assert before["breadth_units"] == len(rows) + 4
    frozen = [(r["family"], r["params"], r["symbol"], r["fate"]) for r in rows]
    assert cs.stamp_all(rows + plain) == len(rows)
    after = cs.breadth(rows + plain)
    assert after["cells"] == len(rows) + 4                 # nothing removed
    assert after["breadth_units"] == 1 + 4                 # the claim counts once
    assert after["distinct_mechanisms"] == 2               # one claim family + carry
    (fid, fam), = after["claim_families"].items()
    assert fam["cells"] == len(rows) and fam["selection_trials"] == 200
    assert {r["claim_family"] for r in rows} == {fid} and fid.startswith("claim:")
    # a judged cell keeps its verdict; only the lineage is added
    assert [(r["family"], r["params"], r["symbol"], r["fate"]) for r in rows] == frozen
    assert all("claim_family" not in r for r in plain)


def test_stamp_is_idempotent_and_only_ratchets_the_charge_up() -> None:
    r = _cell(1)
    assert cs.stamp(r) and cs.stamp(r)
    fid = r["claim_family"]
    r["claim_selection_trials"] = 500                      # a larger stated search stands
    cs.stamp(r)
    assert r["claim_family"] == fid and r["claim_selection_trials"] == 500


def _trials(rows: list[dict]) -> T.ChargeCensus:
    return T.effective_independent_tests(rows)


@pytest.mark.parametrize("n_cells", [5, 50, 400])
def test_the_selection_is_charged_once_per_family_never_per_cell(n_cells: int) -> None:
    rows = [_cell(i, ("EURUSD", "XAUUSD", "US500", "GBPJPY")[i % 4],
                  ("htf_anchor_trend", "exit_operated")[i % 2]) for i in range(n_cells)]
    before = _trials(rows)
    cs.stamp_all(rows)
    after = _trials(rows)
    assert after.n_mechanisms == 1
    (fam,) = after.families.values()
    assert fam.selection_trials == 200
    assert fam.n_nominal == n_cells + 200                  # 200 once, not 200 x n_cells
    # Collapsing the mechanism never makes the bar easier: the family's own tests are priced
    # exactly as before (the strategy family stays on the grid axis) and the 200 are on top.
    assert after.n_effective == pytest.approx(before.n_effective + 200, abs=1e-6)


def test_the_lifetime_ledger_charges_each_family_once(tmp_path, monkeypatch) -> None:
    ledger = tmp_path / "claim_families.json"
    monkeypatch.setattr(cs, "LEDGER", ledger)
    rows = [_cell(i) for i in range(30)]
    cs.stamp_all(rows)
    for _ in range(3):                                     # three hourly passes
        cs.update_ledger(cs.breadth(rows))
    assert cs.lifetime_charges() == {rows[0]["claim_family"]: 200}
    assert set(cs.lineage_index()) == {f"g{i}" for i in range(30)}
    monkeypatch.setattr(el, "_graph_counts", lambda: (10, {"carry": 10}))
    monkeypatch.setattr(el, "_proposer_counts", lambda *a: (5, {"carry": 5}))
    monkeypatch.setattr(el, "_prereg_counts", lambda: 0)
    doc = el.lifetime(write=False)
    assert doc["lifetime_trials"] == 10 + 5 + 200
    assert doc["source_selection_trials"] == 200
    assert doc["by_family"][rows[0]["claim_family"]] == 200


def test_a_producer_registers_its_whole_grid_including_judged_cells(tmp_path,
                                                                    monkeypatch) -> None:
    monkeypatch.setattr(cs, "LEDGER", tmp_path / "claim_families.json")
    grid = [{"symbol": s, "family": "htf_anchor_trend", "params": {"anchor_mult": m},
             "source": "video_anchor_exit", "mechanism": VIDEO}
            for s in ("EURUSD", "XAUUSD") for m in (3, 4, 6)]
    out = cs.register_grid(grid)
    (fid, fam), = out["claim_families"].items()
    assert fam == {"grid_cells": 6, "selection_trials": 200}
    idx = cs.lineage_index()
    assert len(idx) == 6 and set(idx.values()) == {fid}
    # the id a compiled candidate of the same claim carries is the same id
    cand = {"source": "miner:video_anchor_exit", "mechanism_note": VIDEO,
            "source_title": "htf_anchor_trend on EURUSD H4 -- video-derived anchor/exit"}
    assert cs.stamp(cand) and cand["claim_family"] == fid
